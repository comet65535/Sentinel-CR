from __future__ import annotations

from typing import Any


def build_verifier_reflect_payload(
    *,
    failed_stage: Any,
    stderr_summary: Any,
    previous_patch: Any,
    selected_context: list[dict[str, Any]] | None,
    failure_taxonomy: Any,
) -> dict[str, Any]:
    return {
        "instruction": (
            "Reflect on previous verification failure and provide concrete guidance "
            "for next patch attempt."
        ),
        "failed_stage": str(failed_stage or ""),
        "stderr_summary": str(stderr_summary or ""),
        "previous_patch": str(previous_patch or ""),
        "selected_context": list(selected_context or []),
        "failure_taxonomy": failure_taxonomy,
    }
