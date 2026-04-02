from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str = "rev_day3_acceptance") -> list[dict]:
    request_body = {
        "taskId": task_id,
        "codeText": code_text,
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_day3_case1_event_chain_contains_planner_stage() -> None:
    events = _run_review(
        """
public class Demo {
    public String findUser(String userInput) {
        String sql = "select * from users where id = " + userInput;
        return sql;
    }
}
""".strip(),
        task_id="rev_day3_case1",
    )
    event_types = [event["eventType"] for event in events]

    assert "analyzer_completed" in event_types
    assert "planner_started" in event_types
    assert "issue_graph_built" in event_types
    assert "repair_plan_created" in event_types
    assert "planner_completed" in event_types
    assert event_types[-1] == "review_completed"


def test_day3_case2_issue_graph_structure() -> None:
    events = _run_review(
        """
public class Demo {
    public String greet(String name) {
        return "hello " + name;
    }
}
""".strip(),
        task_id="rev_day3_case2",
    )
    payload = events[-1]["payload"]
    issue_graph = payload["result"]["issue_graph"]

    assert isinstance(issue_graph["nodes"], list)
    if issue_graph["nodes"]:
        node = issue_graph["nodes"][0]
        assert "issue_id" in node
        assert "type" in node
        assert "fix_scope" in node


def test_day3_case3_repair_plan_structure() -> None:
    events = _run_review(
        """
public class Demo {
    public void run(String userInput) {
        String sql = "select * from t where id = " + userInput;
        System.out.println(sql);
    }
}
""".strip(),
        task_id="rev_day3_case3",
    )
    payload = events[-1]["payload"]
    repair_plan = payload["result"]["repair_plan"]

    assert isinstance(repair_plan, list)
    if repair_plan:
        item = repair_plan[0]
        assert "issue_id" in item
        assert "priority" in item
        assert "strategy" in item


def test_day3_case4_review_completed_dual_paths_exist() -> None:
    events = _run_review("public class Demo {}", task_id="rev_day3_case4")
    payload = events[-1]["payload"]

    assert "result" in payload
    assert "issue_graph" in payload["result"]
    assert "repair_plan" in payload["result"]
    assert "issue_graph" in payload
    assert "repair_plan" in payload


def test_day3_case5_empty_issue_input_still_emits_planner_events(monkeypatch) -> None:
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
""".strip(),
        task_id="rev_day3_case5",
    )
    event_types = [event["eventType"] for event in events]

    assert "planner_started" in event_types
    assert "issue_graph_built" in event_types
    assert "repair_plan_created" in event_types
    assert "planner_completed" in event_types

    payload = events[-1]["payload"]
    issue_graph = payload["result"]["issue_graph"]
    repair_plan = payload["result"]["repair_plan"]

    assert issue_graph == {"schema_version": "day3.v1", "nodes": [], "edges": []}
    assert repair_plan == []


def test_day3_case6_broken_java_surfaces_syntax_errors_in_planner_outputs() -> None:
    events = _run_review(
        """
public class Demo {
    public String greet(String name) {
        if (name == null) {
            return "hello"
        }
    }
""".strip(),
        task_id="rev_day3_case6",
    )
    event_types = [event["eventType"] for event in events]
    assert event_types[0:6] == [
        "analysis_started",
        "ast_parsing_started",
        "ast_parsing_completed",
        "symbol_graph_started",
        "symbol_graph_completed",
        "semgrep_scan_started",
    ]
    assert event_types[6] in {"semgrep_scan_completed", "semgrep_scan_warning"}
    assert event_types[7:] == [
        "analyzer_completed",
        "planner_started",
        "issue_graph_built",
        "repair_plan_created",
        "planner_completed",
        "review_completed",
    ]

    payload = events[-1]["payload"]
    issues = payload["result"]["issues"]
    assert len(issues) > 0
    assert any((item.get("type") or item.get("issueType")) == "syntax_error" for item in issues)

    assert "issue_graph" in payload["result"]
    assert "issue_graph" in payload
    assert len(payload["result"]["issue_graph"]["nodes"]) > 0
    assert len(payload["result"]["repair_plan"]) > 0
