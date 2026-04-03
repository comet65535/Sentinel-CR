from __future__ import annotations

import json
from typing import Any


def build_fixer_prompt_payload(
    *,
    repair_plan: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    memory_matches: list[dict[str, Any]],
    attempt_no: int,
    selected_context: list[dict[str, Any]] | None = None,
    last_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_context = selected_context or []
    return {
        "instruction": (
            "You are Sentinel-CR Fixer. Always return strict JSON with keys: "
            "strategy, patch, explanation, risk_level. "
            "Allowed strategy values: case_adapt, semantic_template_fix, llm_generation. "
            "patch must be unified diff starting with 'diff --git'."
        ),
        "attempt_no": attempt_no,
        "layered_strategy": ["case_adapt", "semantic_template_fix", "llm_generation"],
        "repair_plan": repair_plan,
        "analyzer_evidence": {
            "issues": issues,
            "symbols": symbols,
            "context_summary": context_summary,
        },
        "memory_matches": memory_matches,
        "selected_context": selected_context,
        "retry_context": {
            "failed_stage": (last_failure or {}).get("failed_stage"),
            "stderr_summary": (last_failure or {}).get("stderr_summary"),
            "previous_patch": (last_failure or {}).get("previous_patch_content"),
            "failure_taxonomy": (last_failure or {}).get("failure_taxonomy"),
        },
        "expected_output_schema": {
            "strategy": "case_adapt|semantic_template_fix|llm_generation",
            "patch": "diff --git a/... b/...\\n...",
            "explanation": "short explanation",
            "risk_level": "low|medium|high",
        },
    }


def build_fixer_messages(prompt_payload: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a senior Java code repair agent. "
                "Output JSON only. Never output markdown."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(prompt_payload, ensure_ascii=False),
        },
    ]
