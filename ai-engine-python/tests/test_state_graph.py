from __future__ import annotations

import asyncio

from core.schemas import InternalReviewRunRequest
from core.state_graph import run_day2_state_graph, run_day3_state_graph, run_review_state_graph


def _run_graph(request: InternalReviewRunRequest, *, entry: str = "day3") -> list[dict]:
    async def _collect() -> list[dict]:
        events = []
        if entry == "review":
            iterator = run_review_state_graph(request)
        elif entry == "day2":
            iterator = run_day2_state_graph(request)
        else:
            iterator = run_day3_state_graph(request)
        async for event in iterator:
            events.append(event.model_dump(by_alias=True))
        return events

    return asyncio.run(_collect())


def test_state_graph_aliases_still_share_same_event_sequence() -> None:
    request = InternalReviewRunRequest(
        taskId="rev_alias",
        codeText="class snippet { void run(){} }",
        language="java",
        sourceType="snippet",
        options={"llm_enabled": False},
    )
    events_review = _run_graph(request, entry="review")
    events_day3 = _run_graph(request, entry="day3")
    events_day2 = _run_graph(request, entry="day2")
    assert [e["eventType"] for e in events_review] == [e["eventType"] for e in events_day3]
    assert [e["eventType"] for e in events_day3] == [e["eventType"] for e in events_day2]


def test_state_graph_surfaces_llm_disabled_reason() -> None:
    request = InternalReviewRunRequest(
        taskId="rev_llm_disabled",
        codeText="class snippet { int plus(int a,int b){ return a+b; } }",
        language="java",
        sourceType="snippet",
        options={"llm_enabled": False},
    )
    events = _run_graph(request)
    result = events[-1]["payload"]["result"]
    assert result["summary"]["final_outcome"] == "failed_no_patch"
    assert result["attempts"][-1]["failure_reason"] == "llm_not_enabled_or_missing_credentials"
    assert result["patch"]["status"] == "absent"


def test_state_graph_includes_debug_traces_when_fixer_returns_them(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": False,
            "patch_artifact": None,
            "attempt": {
                "attempt_no": kwargs.get("attempt_no", 1),
                "patch_id": "p1",
                "status": "failed",
                "verified_level": "L0",
                "failure_stage": "fixer",
                "failure_reason": "llm_not_enabled_or_missing_credentials",
                "failure_detail": "missing key",
                "memory_case_ids": [],
            },
            "llm_trace": [{"phase": "fixer", "provider": "stub"}],
            "tool_trace": [{"tool_name": "analyze_ast", "success": True}],
            "selected_context": [{"kind": "issue_vicinity", "line": 1}],
            "memory_hits": {"cases": [{"case_id": "CASE-1"}], "standards": []},
            "issues": [],
            "symbols": [],
            "context_summary": {},
            "repair_plan": [],
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": 1, "next_action": "fail"}],
        },
    )
    request = InternalReviewRunRequest(
        taskId="rev_debug_payload",
        codeText="class snippet { void run(){} }",
        language="java",
        sourceType="snippet",
        options={"debug": True, "llm_enabled": True},
    )
    events = _run_graph(request)
    completed = next(event for event in reversed(events) if event["eventType"] == "review_completed")
    result = completed["payload"]["result"]
    assert len(result["llm_trace"]) > 0
    assert len(result["tool_trace"]) > 0
    assert len(result["selected_context"]) > 0
    assert "memory_hits" in result
