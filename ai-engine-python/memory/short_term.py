from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_short_term_snapshot(*, snapshot_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_type": snapshot_type,
        "payload": deepcopy(payload),
    }


def update_short_term_memory(
    state: dict[str, Any] | Any,
    *,
    snapshot_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = {}
    if isinstance(state, dict):
        existing = dict(state.get("short_term_memory", {}) or {})
    elif hasattr(state, "short_term_memory"):
        existing = dict(getattr(state, "short_term_memory") or {})

    mapping = {
        "analyzer_evidence": "latest_analyzer_evidence",
        "patch": "latest_patch",
        "verifier_failure": "latest_verifier_failure",
        "retry_context": "retry_context",
        "user_constraints": "user_constraints",
        "token_usage": "token_usage",
    }
    key = mapping.get(snapshot_type, snapshot_type)
    existing[key] = deepcopy(payload)
    return existing


def get_latest_verifier_failure(short_term_memory: dict[str, Any] | None) -> dict[str, Any] | None:
    if not short_term_memory:
        return None
    value = short_term_memory.get("latest_verifier_failure")
    if isinstance(value, dict):
        return value
    return None
