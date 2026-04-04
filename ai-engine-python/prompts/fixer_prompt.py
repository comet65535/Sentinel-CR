from __future__ import annotations

import json
from typing import Any


TOOL_NAMES = [
    "build_issue_graph",
    "analyze_ast",
    "run_semgrep",
    "resolve_symbol",
    "fetch_context",
    "get_repo_profile",
    "search_case_memory",
    "search_short_term_memory",
    "apply_patch",
    "compile_java",
    "lint_java",
    "run_tests",
    "security_rescan",
]


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
) -> dict[str, Any]:
    return {
        "role": "Sentinel-CR LLM Orchestrator",
        "hard_rules": [
            "candidate_patch must be unified diff and start with diff --git",
            "forbid whitespace-only, no-op, comment-only patch",
            "forbid repeating previous patch hash/content",
            "do not change public API/method signature unless user explicitly allows",
            "prioritize latest verifier failure",
            "if context is insufficient, request tool/action first",
            "explanation must state why patch should pass current verifier stage",
        ],
        "tool_catalog": TOOL_NAMES,
        "prompt_injection_order": [
            "repo_rules",
            "user_constraints",
            "latest_verifier_failure",
            "selected_context",
            "matched_cases",
            "matched_standards",
        ],
        "conversation_input": {
            "message_text": message_text or "",
            "code_text": code_text,
        },
        "attempt_no": attempt_no,
        "repo_rules": repo_profile or {},
        "latest_verifier_failure": last_failure or {},
        "selected_context": selected_context or [],
        "matched_cases": memory_matches,
        "matched_standards": standards_matches,
        "planner_hint": {
            "repair_plan": repair_plan,
            "issues": issues,
            "symbols": symbols,
            "context_summary": context_summary,
        },
        "action_history": action_history or [],
        "response_schema": {
            "thought_summary": "string",
            "next_action": "tool name from catalog or finalize_patch or fail",
            "action_args": "object",
            "need_more_context": "boolean",
            "candidate_patch": "string or null",
            "explanation": "string",
        },
    }


def build_fixer_messages(prompt_payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Sentinel-CR orchestrator. Always output strict JSON only. "
                "Prefer tool actions before patching when uncertain. "
                "Use finalize_patch only when candidate_patch is valid unified diff."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt_payload, ensure_ascii=False),
        },
    ]
