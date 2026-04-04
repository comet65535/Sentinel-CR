from __future__ import annotations

import asyncio

from core.schemas import InternalReviewRunRequest
from core.state_graph import run_day3_state_graph


def _collect_events(request: InternalReviewRunRequest) -> list[dict]:
    async def _run() -> list[dict]:
        items: list[dict] = []
        async for event in run_day3_state_graph(request):
            items.append(event.model_dump(by_alias=True))
        return items

    return asyncio.run(_run())


def test_langgraph_reports_llm_disabled_without_fake_patch() -> None:
    request = InternalReviewRunRequest(
        taskId="rev_langgraph_llm_disabled",
        codeText="class snippet { void run(){} }",
        language="java",
        sourceType="snippet",
        options={"llm_enabled": False},
    )
    events = _collect_events(request)
    event_types = [item["eventType"] for item in events]
    assert event_types[:2] == ["analysis_started", "fixer_started"]
    assert "fixer_failed" in event_types
    assert event_types[-1] == "review_completed"
    result = events[-1]["payload"]["result"]
    assert result["summary"]["final_outcome"] == "failed_no_patch"
    assert result["patch"]["status"] == "absent"
    assert result["attempts"][-1]["failure_reason"] == "llm_not_enabled_or_missing_credentials"


def test_langgraph_retry_path_keeps_closed_loop(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": f"patch_{kwargs.get('attempt_no')}",
                "attempt_no": kwargs.get("attempt_no"),
                "status": "generated",
                "format": "unified_diff",
                "content": "\n".join(
                    [
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,1 +1,2 @@",
                        " class snippet { void run(){} }",
                        "+class marker {}",
                    ]
                ),
                "content_hash": "hash",
                "strategy_used": "llm_generation",
                "target_files": ["snippet.java"],
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no"), "patch_id": f"patch_{kwargs.get('attempt_no')}"},
            "llm_trace": [{"phase": "fixer", "provider": "stub"}],
            "tool_trace": [{"tool_name": "analyze_ast", "success": True}],
            "selected_context": [{"kind": "issue_vicinity"}],
            "memory_hits": {"cases": [], "standards": []},
            "issues": kwargs.get("issues", []),
            "symbols": kwargs.get("symbols", []),
            "context_summary": kwargs.get("context_summary", {}),
            "repair_plan": kwargs.get("repair_plan", []),
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": kwargs.get("attempt_no"), "next_action": "finalize_patch"}],
        },
    )

    verify_calls = {"count": 0}

    def _stub_verifier(**kwargs):
        verify_calls["count"] += 1
        first = verify_calls["count"] == 1
        return {
            "status": "failed" if first else "passed",
            "verified_level": "L0" if first else "L1",
            "passed_stages": ["patch_apply"] if first else ["patch_apply", "compile"],
            "failed_stage": "compile" if first else None,
            "stages": [
                {"stage": "patch_apply", "status": "passed", "exit_code": 0, "stderr_summary": "", "retryable": False},
                {
                    "stage": "compile",
                    "status": "failed" if first else "passed",
                    "exit_code": 1 if first else 0,
                    "stderr_summary": "compile error" if first else "",
                    "reason": "compile_failed" if first else None,
                    "retryable": first,
                },
            ],
            "summary": "forced",
            "retryable": first,
            "failure_reason": "compile_failed" if first else None,
        }

    monkeypatch.setattr("core.state_graph.run_verifier_agent", _stub_verifier)

    request = InternalReviewRunRequest(
        taskId="rev_langgraph_retry",
        codeText="class snippet { void run(){} }",
        language="java",
        sourceType="snippet",
        options={"enable_verifier": True, "max_retries": 1},
    )
    events = _collect_events(request)
    event_types = [item["eventType"] for item in events]
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    assert event_types[-1] == "review_completed"
    assert events[-1]["payload"]["result"]["summary"]["verified_level"] == "L1"
