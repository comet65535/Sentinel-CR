from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "service": "ai-engine-python"}
    assert app.version == "0.7.0-day7"


def test_internal_review_run_returns_day3_ndjson_stream(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "null_pointer",
                    "severity": "MEDIUM",
                    "message": "null may dereference",
                    "line": 3,
                    "column": 1,
                    "ruleId": "forced.issue",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    request_body = {
        "taskId": "rev_test_001",
        "codeText": "public class Demo { public String hi(String n){ return \"hi\" + n; } }",
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }

    response = client.post("/internal/reviews/run", json=request_body)

    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]

    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]
    event_types = [event["eventType"] for event in events]

    assert event_types[0] == "analysis_started"
    assert event_types[1:6] == [
        "ast_parsing_started",
        "ast_parsing_completed",
        "symbol_graph_started",
        "symbol_graph_completed",
        "semgrep_scan_started",
    ]
    assert event_types[6] in {"semgrep_scan_completed", "semgrep_scan_warning"}
    assert "analyzer_completed" in event_types
    assert "planner_started" in event_types
    assert "issue_graph_built" in event_types
    assert "repair_plan_created" in event_types
    assert "planner_completed" in event_types
    assert "case_memory_search_started" in event_types
    assert "case_memory_completed" in event_types
    assert "fixer_started" in event_types
    assert any(item in event_types for item in {"patch_generated", "fixer_failed"})
    assert event_types[-1] == "review_completed"

    final_event = events[-1]
    assert final_event["status"] == "COMPLETED"
    assert "result" in final_event["payload"]
    assert "symbols" in final_event["payload"]["result"]
    assert "contextSummary" in final_event["payload"]["result"]
    assert "issue_graph" in final_event["payload"]
    assert "repair_plan" in final_event["payload"]
    assert "issue_graph" in final_event["payload"]["result"]
    assert "repair_plan" in final_event["payload"]["result"]
    assert "memory" in final_event["payload"]["result"]
    assert "patch" in final_event["payload"]["result"]
    assert "attempts" in final_event["payload"]["result"]


def test_internal_review_run_broken_java_reports_syntax_issue() -> None:
    request_body = {
        "taskId": "rev_test_syntax_001",
        "codeText": """
public class Demo {
    public String greet(String name) {
        if (name == null) {
            return "hello"
        }
    }
}
""".strip(),
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }

    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    final_payload = events[-1]["payload"]["result"]
    issues = final_payload["issues"]
    assert len(issues) > 0
    assert any((item.get("type") or item.get("issueType")) == "syntax_error" for item in issues)
    assert len(final_payload["issue_graph"]["nodes"]) > 0
    assert len(final_payload["repair_plan"]) > 0
