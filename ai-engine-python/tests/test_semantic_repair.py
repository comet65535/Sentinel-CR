from __future__ import annotations

import json
from typing import Any

from agents.fixer_agent import run_fixer_agent
from llm.clients import LlmCallResult


class _LlmForSemantic:
    def __init__(self, patch: str) -> None:
        self.patch = patch
        self.calls = 0

    def create_chat_completion(self, *, phase: str, prompt_name: str, **_: Any) -> LlmCallResult:
        self.calls += 1
        if self.calls == 1:
            payload = {
                "thought_summary": "need context",
                "next_action": "search_short_term_memory",
                "action_args": {},
                "need_more_context": True,
                "candidate_patch": None,
                "explanation": "read latest verifier failure",
            }
        else:
            payload = {
                "thought_summary": "apply semantic fix",
                "next_action": "finalize_patch",
                "action_args": {},
                "need_more_context": False,
                "candidate_patch": self.patch,
                "explanation": "add missing return path",
            }
        return LlmCallResult(
            ok=True,
            content=json.dumps(payload),
            error=None,
            raw={"stub": True},
            trace={
                "phase": phase,
                "prompt_name": prompt_name,
                "provider": "stub",
                "model": "stub-model",
                "token_in": 20,
                "token_out": 20,
                "latency_ms": 2,
                "json_mode": True,
                "tool_mode": "auto",
                "tool_call_count": 0,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 20,
            },
            tool_calls=[],
        )


def test_semantic_path_records_llm_trace_when_enabled(monkeypatch) -> None:
    patch = "\n".join(
        [
            "diff --git a/snippet.java b/snippet.java",
            "--- a/snippet.java",
            "+++ b/snippet.java",
            "@@ -1,4 +1,6 @@",
            " class snippet {",
            "     int value(boolean ok) {",
            "         if (ok) return 1;",
            "+        return 0;",
            "     }",
            " }",
        ]
    )
    monkeypatch.setattr("agents.fixer_agent.build_llm_client", lambda options: _LlmForSemantic(patch))
    output = run_fixer_agent(
        code_text="""
class snippet {
    int value(boolean ok) {
        if (ok) return 1;
    }
}
""".strip(),
        repair_plan=[{"issue_id": "C1", "priority": 1, "strategy": "semantic_compile_fix"}],
        issues=[{"type": "compile_error", "line": 3, "message": "missing return statement"}],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        last_failure={"failed_stage": "compile", "reason": "compile_failed", "detail": "missing return statement"},
        options={"llm_enabled": True, "llm_api_key": "x"},
    )
    assert output["ok"] is True
    assert len(output["llm_trace"]) > 0
    assert len(output["tool_trace"]) > 0
    assert output["patch_artifact"]["strategy_used"] == "llm_generation"


def test_semantic_path_without_llm_fails_explicitly() -> None:
    output = run_fixer_agent(
        code_text="class snippet { int plus(int a,int b){ return a+b; } }",
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": True, "llm_api_key": ""},
    )
    assert output["ok"] is False
    assert output["attempt"]["failure_reason"] == "llm_not_enabled_or_missing_credentials"
    assert output["patch_artifact"] is None
