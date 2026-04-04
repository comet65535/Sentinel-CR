from __future__ import annotations

import json
from typing import Any

from agents.fixer_agent import run_fixer_agent
from llm.clients import LlmCallResult


class _SequenceLlm:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.idx = 0

    def create_chat_completion(self, *, phase: str, prompt_name: str, **_: Any) -> LlmCallResult:
        payload = self.responses[min(self.idx, len(self.responses) - 1)]
        self.idx += 1
        return LlmCallResult(
            ok=True,
            content=json.dumps(payload),
            error=None,
            raw={"stub": True},
            trace={
                "phase": phase,
                "prompt_name": prompt_name,
                "provider": "stub",
                "model": "stub",
                "token_in": 8,
                "token_out": 8,
                "latency_ms": 1,
                "json_mode": True,
                "tool_mode": "auto",
                "tool_call_count": 0,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 8,
            },
            tool_calls=[],
        )


def test_fixer_rejects_comment_only_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        "agents.fixer_agent.build_llm_client",
        lambda options: _SequenceLlm(
            [
                {
                    "thought_summary": "inspect",
                    "next_action": "analyze_ast",
                    "action_args": {},
                    "need_more_context": True,
                    "candidate_patch": None,
                    "explanation": "collect",
                },
                {
                    "thought_summary": "finalize",
                    "next_action": "finalize_patch",
                    "action_args": {},
                    "need_more_context": False,
                    "candidate_patch": "\n".join(
                        [
                            "diff --git a/snippet.java b/snippet.java",
                            "--- a/snippet.java",
                            "+++ b/snippet.java",
                            "@@ -1,1 +1,2 @@",
                            " class snippet { void run(){} }",
                            "+// noop comment only",
                        ]
                    ),
                    "explanation": "comment",
                },
            ]
        ),
    )
    result = run_fixer_agent(
        code_text="class snippet { void run(){} }",
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": True, "llm_api_key": "x"},
    )
    assert result["ok"] is False
    assert result["attempt"]["failure_reason"] == "no_valid_patch"


def test_fixer_rejects_duplicate_patch_candidate(monkeypatch) -> None:
    patch = "\n".join(
        [
            "diff --git a/snippet.java b/snippet.java",
            "--- a/snippet.java",
            "+++ b/snippet.java",
            "@@ -1,1 +1,2 @@",
            " class snippet { void run(){} }",
            "+class X {}",
        ]
    )
    monkeypatch.setattr(
        "agents.fixer_agent.build_llm_client",
        lambda options: _SequenceLlm(
            [
                {
                    "thought_summary": "inspect",
                    "next_action": "analyze_ast",
                    "action_args": {},
                    "need_more_context": True,
                    "candidate_patch": None,
                    "explanation": "collect",
                },
                {
                    "thought_summary": "finalize",
                    "next_action": "finalize_patch",
                    "action_args": {},
                    "need_more_context": False,
                    "candidate_patch": patch,
                    "explanation": "duplicate",
                },
            ]
        ),
    )
    first = run_fixer_agent(
        code_text="class snippet { void run(){} }",
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": True, "llm_api_key": "x"},
    )
    assert first["ok"] is True

    second = run_fixer_agent(
        code_text="class snippet { void run(){} }",
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=2,
        last_failure={"previous_patch_content": patch},
        options={"llm_enabled": True, "llm_api_key": "x"},
    )
    assert second["ok"] is False
    assert second["attempt"]["failure_reason"] == "duplicate_patch_candidate"
