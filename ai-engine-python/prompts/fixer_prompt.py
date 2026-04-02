from __future__ import annotations

from typing import Any


def build_fixer_prompt_payload(
    *,
    repair_plan: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    memory_matches: list[dict[str, Any]],
    attempt_no: int,
) -> dict[str, Any]:
    return {
        "instruction": (
            "You are a code fixer. Input includes repair_plan, analyzer evidence, and memory_matches. "
            "Output must be one JSON object with keys: patch, explanation, risk_level. "
            "patch must be a unified diff string beginning with 'diff --git'. "
            "Do not output markdown, prose blocks, or extra keys."
        ),
        "attempt_no": attempt_no,
        "repair_plan": repair_plan,
        "analyzer_evidence": {
            "issues": issues,
            "symbols": symbols,
            "context_summary": context_summary,
        },
        "memory_matches": memory_matches,
        "expected_output_schema": {
            "patch": "diff --git a/... b/...\\n...",
            "explanation": "short explanation",
            "risk_level": "low|medium|high",
        },
    }
