from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from llm.clients import LlmCallResult


class StubLlmClient:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def create_chat_completion(self, *, phase: str, prompt_name: str, **_: Any) -> LlmCallResult:
        if not self._responses:
            payload = {
                "thought_summary": "default action",
                "next_action": "fail",
                "action_args": {},
                "need_more_context": False,
                "candidate_patch": None,
                "explanation": "no scripted response",
            }
        else:
            payload = self._responses[min(self._idx, len(self._responses) - 1)]
            self._idx += 1
        return LlmCallResult(
            ok=True,
            content=json.dumps(payload, ensure_ascii=False),
            error=None,
            raw={"stub": True},
            trace={
                "phase": phase,
                "prompt_name": prompt_name,
                "provider": "stub",
                "model": "stub-model",
                "token_in": 32,
                "token_out": 24,
                "latency_ms": 2,
                "json_mode": True,
                "tool_mode": "auto",
                "tool_call_count": 0,
                "cache_hit_tokens": 0,
                "cache_miss_tokens": 32,
            },
            tool_calls=[],
        )
