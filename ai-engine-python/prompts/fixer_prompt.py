from __future__ import annotations

import json
from typing import Any


def build_fixer_prompt_payload(
    *,
    code_text: str,
    message_text: str | None,
    repair_plan: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    memory_matches: list[dict[str, Any]],
    standards_matches: list[dict[str, Any]],
    attempt_no: int,
    selected_context: list[dict[str, Any]] | None = None,
    last_failure: dict[str, Any] | None = None,
    repo_profile: dict[str, Any] | None = None,
    action_history: list[dict[str, Any]] | None = None,
    retry_hints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "role": "Sentinel-CR Verified Patch Agent",
        "goal": "Return one valid unified diff patch that directly addresses the planned issues.",
        "hard_rules": [
            "Output must be valid JSON only.",
            "Patch must be unified diff and start with diff --git.",
            "Do not produce no-op/comment-only patch.",
            "Do not repeat a previously failed patch.",
            "Prefer minimal safe change set.",
            "Respect user constraints and repo rules first.",
        ],
        "response_schema": {
            "unified_diff": "string",
            "explanation": "short string",
            "risk_level": "low|medium|high",
            "target_files": ["snippet.java"],
        },
        "inputs": {
            "message_text": message_text or "",
            "code_text": code_text,
            "attempt_no": attempt_no,
            "issues": issues,
            "repair_plan": repair_plan,
            "symbols": symbols,
            "context_summary": context_summary,
            "selected_context": selected_context or [],
            "last_failure": last_failure or {},
            "retry_hints": retry_hints or {},
            "memory_matches": memory_matches,
            "standards_matches": standards_matches,
            "repo_profile": repo_profile or {},
            "action_history": action_history or [],
        },
    }


def build_fixer_messages(prompt_payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Sentinel-CR patch generator. "
                "You must return strict JSON that matches response_schema and includes unified_diff."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt_payload, ensure_ascii=False),
        },
    ]
