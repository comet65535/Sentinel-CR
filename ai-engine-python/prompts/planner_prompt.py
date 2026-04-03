from __future__ import annotations

from typing import Any


def build_planner_prompt_payload(
    *,
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "instruction": (
            "Build issue ordering and repair strategies. "
            "Prefer syntax_fix for parse errors and semantic_compile_fix for compile semantics."
        ),
        "issues": issues,
        "symbols": symbols,
        "context_summary": context_summary,
    }
