from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str, options: dict | None = None, metadata: dict | None = None) -> list[dict]:
    response = client.post(
        "/internal/reviews/run",
        json={
            "taskId": task_id,
            "codeText": code_text,
            "language": "java",
            "sourceType": "snippet",
            "options": options or {},
            "metadata": metadata or {},
        },
    )
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_day2_llm_disabled_returns_explicit_failure_reason() -> None:
    events = _run_review(
        "class snippet { void run(){ System.out.println(\"ok\"); } }",
        task_id="rev_day2_llm_disabled",
        options={"llm_enabled": False},
    )
    event_types = [event["eventType"] for event in events]
    assert event_types[0] == "analysis_started"
    assert "fixer_failed" in event_types
    assert event_types[-1] == "review_completed"
    result = events[-1]["payload"]["result"]
    assert result["summary"]["final_outcome"] == "failed_no_patch"
    assert result["attempts"][-1]["failure_reason"] == "llm_not_enabled_or_missing_credentials"
    assert result["patch"]["status"] == "absent"


def test_day2_output_contains_debug_traces_when_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": False,
            "patch_artifact": None,
            "attempt": {
                "attempt_no": 1,
                "patch_id": "p1",
                "status": "failed",
                "verified_level": "L0",
                "failure_stage": "fixer",
                "failure_reason": "llm_not_enabled_or_missing_credentials",
                "failure_detail": "missing credentials",
                "memory_case_ids": [],
            },
            "llm_trace": [{"phase": "fixer_orchestrator"}],
            "tool_trace": [{"tool_name": "analyze_ast", "success": True}],
            "selected_context": [{"kind": "issue_vicinity", "line": 1}],
            "memory_hits": {"cases": [], "standards": []},
            "issues": [],
            "symbols": [],
            "context_summary": {},
            "repair_plan": [],
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": 1, "next_action": "fail"}],
        },
    )
    events = _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day2_debug_fields",
        options={"llm_enabled": True, "debug": True},
    )
    completed = next(event for event in reversed(events) if event["eventType"] == "review_completed")
    result = completed["payload"]["result"]
    assert len(result["llm_trace"]) > 0
    assert len(result["tool_trace"]) > 0
    assert len(result["selected_context"]) > 0
