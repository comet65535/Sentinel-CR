from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str, options: dict | None = None) -> list[dict]:
    request_body = {
        "taskId": task_id,
        "codeText": code_text,
        "language": "java",
        "sourceType": "snippet",
        "options": options or {},
        "metadata": {},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_day6_zero_issue_short_circuit_returns_review_completed(monkeypatch) -> None:
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
class snippet {
    int plus(int a, int b) {
        return a + b;
    }
}
""".strip(),
        task_id="rev_day6_no_fix_needed",
        options={"enable_verifier": True, "max_retries": 2},
    )
    event_types = [event["eventType"] for event in events]

    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types
    assert "planner_started" not in event_types
    assert "fixer_started" not in event_types
    assert "verifier_started" not in event_types

    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["issue_count"] == 0
    assert summary["attempt_count"] == 0
    assert summary["no_fix_needed"] is True
    assert summary["failed_stage"] is None
    assert summary["failure_reason"] is None
    assert summary["failure_detail"] is None
    assert isinstance(summary["user_message"], str) and "No fix is needed" in summary["user_message"]
    assert result["patch"]["status"] == "absent"
