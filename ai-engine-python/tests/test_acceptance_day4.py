from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from llm.clients import LlmCallResult
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


def test_day4_missing_credentials_never_emit_fake_patch() -> None:
    events = _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day4_missing_credentials",
        options={"llm_enabled": True, "llm_api_key": ""},
    )
    event_types = [event["eventType"] for event in events]
    assert "patch_generated" not in event_types
    result = events[-1]["payload"]["result"]
    assert result["patch"]["status"] == "absent"
    assert result["attempts"][-1]["failure_reason"] == "llm_not_enabled_or_missing_credentials"


def test_day4_action_loop_generates_patch_and_traces(monkeypatch) -> None:
    class _StubLlm:
        def __init__(self) -> None:
            self.calls = 0

        def create_chat_completion(self, *, phase: str, prompt_name: str, **_: Any) -> LlmCallResult:
            self.calls += 1
            if self.calls == 1:
                content = json.dumps(
                    {
                        "thought_summary": "need evidence",
                        "next_action": "analyze_ast",
                        "action_args": {},
                        "need_more_context": True,
                        "candidate_patch": None,
                        "explanation": "collect signals",
                    }
                )
            else:
                content = json.dumps(
                    {
                        "thought_summary": "ready to patch",
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
                                "+class Added {}",
                            ]
                        ),
                        "explanation": "minimal meaningful change",
                    }
                )
            return LlmCallResult(
                ok=True,
                content=content,
                error=None,
                raw={"stub": True},
                trace={
                    "phase": phase,
                    "prompt_name": prompt_name,
                    "provider": "stub",
                    "model": "stub-model",
                    "token_in": 16,
                    "token_out": 16,
                    "latency_ms": 2,
                    "json_mode": True,
                    "tool_mode": "auto",
                    "tool_call_count": 0,
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 16,
                },
                tool_calls=[],
            )

    monkeypatch.setattr("agents.fixer_agent.build_llm_client", lambda options: _StubLlm())

    events = _run_review(
        "class snippet { void run(){} }",
        task_id="rev_day4_llm_orchestrator",
        options={"llm_enabled": True, "llm_tool_mode": "auto", "enable_verifier": False},
    )
    event_types = [event["eventType"] for event in events]
    assert "patch_generated" in event_types
    result = events[-1]["payload"]["result"]
    assert result["summary"]["final_outcome"] == "patch_generated_unverified"
    assert len(result["llm_trace"]) > 0
    assert len(result["tool_trace"]) > 0
    assert "Generated minimal non-comment fallback patch." not in json.dumps(result, ensure_ascii=False)
