from __future__ import annotations

import json

from agents.fixer_agent import run_fixer_agent
from llm.clients import LlmCallResult


def test_fixer_action_loop_produces_patch_and_tool_trace(monkeypatch) -> None:
    class _StubClient:
        def __init__(self) -> None:
            self.step = 0

        def create_chat_completion(self, **kwargs):
            self.step += 1
            if self.step == 1:
                payload = {
                    "thought_summary": "need analyzer evidence",
                    "next_action": "analyze_ast",
                    "action_args": {},
                    "need_more_context": True,
                    "candidate_patch": None,
                    "explanation": "collect evidence",
                }
            elif self.step == 2:
                payload = {
                    "thought_summary": "need issue graph",
                    "next_action": "build_issue_graph",
                    "action_args": {},
                    "need_more_context": True,
                    "candidate_patch": None,
                    "explanation": "plan fix",
                }
            else:
                payload = {
                    "thought_summary": "ready to patch",
                    "next_action": "finalize_patch",
                    "action_args": {},
                    "need_more_context": False,
                    "candidate_patch": "\n".join(
                        [
                            "diff --git a/snippet.java b/snippet.java",
                            "--- a/snippet.java",
                            "+++ b/snippet.java",
                            "@@ -1,4 +1,4 @@",
                            " class snippet {",
                            "     void run(){",
                            "-        int x = 1",
                            "+        int x = 1;",
                            "     }",
                            " }",
                        ]
                    ),
                    "explanation": "add missing semicolon",
                }
            return LlmCallResult(
                ok=True,
                content=json.dumps(payload),
                error=None,
                raw=None,
                trace={
                    "phase": "fixer_orchestrator",
                    "prompt_name": "fixer_action_loop",
                    "provider": "stub",
                    "model": "stub",
                    "token_in": 10,
                    "token_out": 10,
                    "latency_ms": 1,
                    "json_mode": True,
                    "tool_mode": "auto",
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 10,
                },
            )

    monkeypatch.setattr("agents.fixer_agent.build_llm_client", lambda options: _StubClient())

    output = run_fixer_agent(
        code_text="""
class snippet {
    void run(){
        int x = 1
    }
}
""".strip(),
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": True, "llm_tool_mode": "auto"},
        message_text="just fix syntax",
    )

    assert output["ok"] is True
    assert output["patch_artifact"]["strategy_used"] == "llm_generation"
    assert len(output["llm_trace"]) == 3
    assert len(output["tool_trace"]) >= 2


def test_fixer_fails_when_llm_disabled_and_does_not_generate_patch() -> None:
    output = run_fixer_agent(
        code_text="class snippet { void run(){} }",
        repair_plan=[],
        issues=[],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": False},
    )
    assert output["ok"] is False
    assert output["patch_artifact"] is None
    assert output["attempt"]["failure_reason"] == "llm_not_enabled_or_missing_credentials"
