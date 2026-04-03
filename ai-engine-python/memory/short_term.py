from __future__ import annotations

import hashlib
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
    if not isinstance(value, dict):
        return None

    merged = deepcopy(value)
    latest_patch = short_term_memory.get("latest_patch")
    if isinstance(latest_patch, dict):
        patch_hash = str(latest_patch.get("content_hash") or "").strip()
        patch_content = str(latest_patch.get("content") or "")
        if not patch_hash and patch_content:
            patch_hash = hashlib.sha256(patch_content.encode("utf-8", errors="ignore")).hexdigest()
        if patch_hash:
            merged.setdefault("previous_patch_hash", patch_hash)
        if patch_content:
            merged.setdefault("previous_patch_content", patch_content)
        patch_id = str(latest_patch.get("patch_id") or "").strip()
        if patch_id:
            merged.setdefault("previous_patch_id", patch_id)
    return merged
