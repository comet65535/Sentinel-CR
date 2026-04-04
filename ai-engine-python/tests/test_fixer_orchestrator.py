from __future__ import annotations

import json

from agents.fixer_agent import run_fixer_agent
from llm.clients import LlmCallResult


def test_fixer_generates_patch_from_evidence(monkeypatch) -> None:
    class _StubClient:
        def create_chat_completion(self, **kwargs):
            payload = {
                "unified_diff": "\n".join(
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
                "risk_level": "low",
                "target_files": ["snippet.java"],
            }
            return LlmCallResult(
                ok=True,
                content=json.dumps(payload),
                error=None,
                raw=None,
                trace={
                    "phase": "fixer_patch_generation",
                    "prompt_name": "fixer_patch_generation",
                    "provider": "stub",
                    "model": "stub",
                    "token_in": 10,
                    "token_out": 10,
                    "latency_ms": 1,
                    "json_mode": True,
                    "tool_mode": "off",
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
        selected_context=[{"kind": "snippet_window", "line": 3}],
        options={"llm_enabled": True},
        message_text="just fix syntax",
    )

    assert output["ok"] is True
    assert output["patch_artifact"]["strategy_used"] == "llm_patch_generation"
    assert len(output["llm_trace"]) == 1
    assert len(output["tool_trace"]) == 1


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
