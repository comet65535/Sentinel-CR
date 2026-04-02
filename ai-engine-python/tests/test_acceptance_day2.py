from __future__ import annotations

import json
import shutil

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, language: str = "java") -> list[dict]:
    request_body = {
        "taskId": "rev_acceptance_case",
        "codeText": code_text,
        "language": language,
        "sourceType": "snippet",
        "metadata": {},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_case1_normal_java_snippet_completes_review() -> None:
    events = _run_review(
        """
public class Demo {
    public String greet(String name) {
        return "hello " + name;
    }
}
""".strip()
    )
    event_types = [event["eventType"] for event in events]

    assert event_types[0] == "analysis_started"
    assert event_types[-1] == "review_completed"
    assert event_types[6] in {"semgrep_scan_completed", "semgrep_scan_warning"}

    payload = events[-1]["payload"]
    assert "result" in payload
    for key in ["summary", "engine", "analyzer", "issues", "symbols", "contextSummary", "diagnostics"]:
        assert key in payload
        assert key in payload["result"]


def test_case2_empty_input_returns_review_failed_with_empty_input_diagnostic() -> None:
    events = _run_review("   ")
    assert [event["eventType"] for event in events] == ["analysis_started", "review_failed"]

    diagnostics = events[-1]["payload"]["diagnostics"]
    codes = {item.get("code") for item in diagnostics}
    assert "EMPTY_INPUT" in codes


def test_case3_risky_snippet_semgrep_completed_or_warning() -> None:
    events = _run_review(
        """
public class RiskyQuery {
    public void run(String userInput) throws Exception {
        String sql = "select * from users where id = " + userInput;
        java.sql.Statement stmt = null;
        stmt.executeQuery(sql);
    }
}
""".strip()
    )
    semgrep_event = events[6]
    assert semgrep_event["eventType"] in {"semgrep_scan_completed", "semgrep_scan_warning"}

    if shutil.which("semgrep") is None:
        assert semgrep_event["eventType"] == "semgrep_scan_warning"
        assert semgrep_event["payload"].get("code") == "SEMGREP_UNAVAILABLE"
    elif semgrep_event["eventType"] == "semgrep_scan_warning":
        assert semgrep_event["payload"].get("code") in {
            "SEMGREP_UNAVAILABLE",
            "SEMGREP_TIMEOUT",
            "SEMGREP_EXEC_ERROR",
        }


def test_case4_clean_code_issues_empty_and_full_day2_sequence(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [],
            "summary": {
                "issuesCount": 0,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    events = _run_review(
        """
public class CleanService {
    public int plus(int a, int b) {
        return a + b;
    }
}
""".strip()
    )
    assert [event["eventType"] for event in events] == [
        "analysis_started",
        "ast_parsing_started",
        "ast_parsing_completed",
        "symbol_graph_started",
        "symbol_graph_completed",
        "semgrep_scan_started",
        "semgrep_scan_completed",
        "analyzer_completed",
        "planner_started",
        "issue_graph_built",
        "repair_plan_created",
        "planner_completed",
        "review_completed",
    ]
    assert events[-1]["payload"]["result"]["issues"] == []
