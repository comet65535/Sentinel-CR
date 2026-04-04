from __future__ import annotations

import json
import shutil
from typing import Any

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str, options: dict[str, Any] | None = None) -> list[dict]:
    response = client.post(
        "/internal/reviews/run",
        json={
            "taskId": task_id,
            "codeText": code_text,
            "language": "java",
            "sourceType": "snippet",
            "options": options or {},
            "metadata": {},
        },
    )
    assert response.status_code == 200
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _require_javac() -> None:
    if shutil.which("javac") is None:
        pytest.skip("javac is required for compile-stage acceptance")


def test_day6_unbalanced_brace_java_case_can_reach_l1(monkeypatch) -> None:
    _require_javac()

    broken_code = """
class snippet {
    int plus(int a, int b) {
        return a + b;
}
""".strip()

    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": "patch_brace",
                "attempt_no": kwargs.get("attempt_no", 1),
                "status": "generated",
                "format": "unified_diff",
                "content": "\n".join(
                    [
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,4 +1,5 @@",
                        " class snippet {",
                        "     int plus(int a, int b) {",
                        "         return a + b;",
                        " }",
                        "+}",
                    ]
                ),
                "content_hash": "h_brace",
                "strategy_used": "llm_generation",
                "target_files": ["snippet.java"],
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no", 1), "patch_id": "patch_brace"},
            "llm_trace": [{"phase": "fixer_orchestrator"}],
            "tool_trace": [{"tool_name": "analyze_ast", "success": True}],
            "selected_context": [{"kind": "issue_vicinity", "line": 4}],
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
        broken_code,
        task_id="rev_day6_unbalanced_brace",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False, "llm_enabled": True},
    )
    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] in {"L1", "L2", "L3", "L4"}


def test_day6_compile_failure_enters_retry_context(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": f"patch_{kwargs.get('attempt_no', 1)}",
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
                        "+UnknownType x;",
                    ]
                ),
                "content_hash": "dup_hash",
                "strategy_used": "llm_generation",
                "target_files": ["snippet.java"],
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no", 1), "patch_id": f"patch_{kwargs.get('attempt_no', 1)}"},
            "llm_trace": [{"phase": "fixer_orchestrator"}],
            "tool_trace": [{"tool_name": "compile_java", "success": True}],
            "selected_context": [],
            "memory_hits": {"cases": [], "standards": []},
            "issues": kwargs.get("issues", []),
            "symbols": kwargs.get("symbols", []),
            "context_summary": kwargs.get("context_summary", {}),
            "repair_plan": kwargs.get("repair_plan", []),
            "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
            "planner_summary": {},
            "action_history": [{"step": kwargs.get("attempt_no", 1), "next_action": "finalize_patch"}],
        },
    )

    verify_calls = {"count": 0}

    def _verifier(**kwargs):
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
                    "stderr_summary": "cannot find symbol UnknownType" if first else "",
                    "reason": "compile_failed" if first else None,
                    "retryable": first,
                },
            ],
            "summary": "forced",
            "retryable": first,
            "failure_reason": "compile_failed" if first else None,
        }

    monkeypatch.setattr("core.state_graph.run_verifier_agent", _verifier)

    events = _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day6_retry_context",
        options={"enable_verifier": True, "max_retries": 1, "llm_enabled": True},
    )
    event_types = [event["eventType"] for event in events]
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    result = events[-1]["payload"]["result"]
    assert result["summary"]["verified_level"] == "L1"
