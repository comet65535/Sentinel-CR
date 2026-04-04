from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(
    code_text: str,
    *,
    task_id: str,
    options: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    conversation_id: str | None = None,
) -> list[dict]:
    body = {
        "taskId": task_id,
        "codeText": code_text,
        "language": "java",
        "sourceType": "snippet",
        "options": options or {},
        "metadata": metadata or {},
    }
    if conversation_id:
        body["conversationId"] = conversation_id
    response = client.post("/internal/reviews/run", json=body)
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_day3_success_payload_has_llm_and_tool_trace(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": "p1",
                "attempt_no": kwargs.get("attempt_no", 1),
                "status": "generated",
                "format": "unified_diff",
                "content": "\n".join(
                    [
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,1 +1,2 @@",
                        " class snippet { void run(){} }",
                        "+class extra {}",
                    ]
                ),
                "content_hash": "hash1",
                "strategy_used": "llm_generation",
                "target_files": ["snippet.java"],
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no", 1), "patch_id": "p1"},
            "llm_trace": [{"phase": "fixer_orchestrator", "provider": "stub"}],
            "tool_trace": [{"tool_name": "fetch_context", "success": True}],
            "selected_context": [{"kind": "issue_vicinity"}],
            "memory_hits": {"cases": [], "standards": []},
            "issues": kwargs.get("issues", []),
            "symbols": kwargs.get("symbols", []),
            "context_summary": kwargs.get("context_summary", {}),
            "repair_plan": kwargs.get("repair_plan", []),
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": 1, "next_action": "finalize_patch"}],
        },
    )

    events = _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day3_trace",
        options={"enable_verifier": False, "llm_enabled": True},
    )
    result = events[-1]["payload"]["result"]
    assert len(result["llm_trace"]) > 0
    assert len(result["tool_trace"]) > 0
    assert result["summary"]["final_outcome"] == "patch_generated_unverified"


def test_day3_follow_up_reuses_latest_verifier_failure(monkeypatch) -> None:
    conversation_id = f"conv_py_{uuid.uuid4().hex[:12]}"

    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": "p_fail",
                "attempt_no": kwargs.get("attempt_no", 1),
                "status": "generated",
                "format": "unified_diff",
                "content": "\n".join(
                    [
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,1 +1,2 @@",
                        " class snippet { void run(){} }",
                        "+UnknownType bad;",
                    ]
                ),
                "content_hash": "hash_fail",
                "strategy_used": "llm_generation",
                "target_files": ["snippet.java"],
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no", 1), "patch_id": "p_fail"},
            "llm_trace": [{"phase": "fixer_orchestrator"}],
            "tool_trace": [{"tool_name": "analyze_ast", "success": True}],
            "selected_context": [],
            "memory_hits": {"cases": [], "standards": []},
            "issues": kwargs.get("issues", []),
            "symbols": kwargs.get("symbols", []),
            "context_summary": kwargs.get("context_summary", {}),
            "repair_plan": kwargs.get("repair_plan", []),
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": 1, "next_action": "finalize_patch"}],
        },
    )
    monkeypatch.setattr(
        "core.state_graph.run_verifier_agent",
        lambda **kwargs: {
            "status": "failed",
            "verified_level": "L0",
            "passed_stages": ["patch_apply"],
            "failed_stage": "compile",
            "stages": [
                {"stage": "patch_apply", "status": "passed", "exit_code": 0, "stderr_summary": "", "retryable": False},
                {
                    "stage": "compile",
                    "status": "failed",
                    "exit_code": 1,
                    "stderr_summary": "cannot find symbol UnknownType",
                    "reason": "compile_failed",
                    "retryable": False,
                },
            ],
            "summary": "compile failed",
            "retryable": False,
            "failure_reason": "compile_failed",
        },
    )

    _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day3_first",
        options={"enable_verifier": True, "max_retries": 0, "llm_enabled": True},
        conversation_id=conversation_id,
    )

    captured: dict[str, Any] = {}

    def _capture_last_failure(**kwargs):
        captured["last_failure"] = kwargs.get("last_failure")
        return {
            "ok": False,
            "patch_artifact": None,
            "attempt": {
                "attempt_no": kwargs.get("attempt_no", 1),
                "patch_id": "p2",
                "status": "failed",
                "verified_level": "L0",
                "failure_stage": "fixer",
                "failure_reason": "llm_not_enabled_or_missing_credentials",
                "failure_detail": "second round capture",
                "memory_case_ids": [],
            },
            "llm_trace": [],
            "tool_trace": [],
            "selected_context": [],
            "memory_hits": {"cases": [], "standards": []},
            "issues": kwargs.get("issues", []),
            "symbols": kwargs.get("symbols", []),
            "context_summary": kwargs.get("context_summary", {}),
            "repair_plan": kwargs.get("repair_plan", []),
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [],
        }

    monkeypatch.setattr("core.state_graph.run_fixer_agent", _capture_last_failure)
    _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day3_followup",
        options={"enable_verifier": False, "llm_enabled": True},
        conversation_id=conversation_id,
    )
    last_failure = captured.get("last_failure") or {}
    assert last_failure.get("failed_stage") == "compile"
    assert "cannot find symbol" in str(last_failure.get("detail") or "")
