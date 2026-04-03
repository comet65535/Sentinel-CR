from __future__ import annotations

import math
from typing import Any


DEFAULT_BUDGET_TOKENS = 12_000
ALLOWED_POLICIES = {"none", "lazy"}


def initialize_context_budget(options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = options or {}
    policy = str(options.get("context_policy") or "none").strip().lower()
    if policy not in ALLOWED_POLICIES:
        policy = "none"

    budget_tokens = _to_int(options.get("context_budget_tokens"), default=DEFAULT_BUDGET_TOKENS)
    if budget_tokens <= 0:
        budget_tokens = DEFAULT_BUDGET_TOKENS

    enabled = policy == "lazy"
    return {
        "enabled": enabled,
        "policy": policy,
        "budget_tokens": budget_tokens if enabled else 0,
        "used_tokens": 0,
        "remaining_tokens": budget_tokens if enabled else 0,
        "load_stage": "bootstrap",
        "sources": [],
    }


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    # Safe approximation for Day6; replace with tokenizer later.
    return max(1, int(math.ceil(len(text) / 4)))


def register_loaded_context(
    context_budget: dict[str, Any],
    *,
    source_item: dict[str, Any],
    load_stage: str,
) -> tuple[dict[str, Any], bool]:
    if not context_budget or not bool(context_budget.get("enabled", False)):
        snapshot = dict(context_budget or {})
        snapshot.setdefault("sources", [])
        snapshot["load_stage"] = load_stage
        return snapshot, False

    snapshot = dict(context_budget)
    sources = list(snapshot.get("sources", []))
    token_count = _to_int(source_item.get("token_count"), default=0)
    if token_count <= 0:
        token_count = estimate_tokens_from_text(str(source_item.get("content") or ""))

    source_record = dict(source_item)
    source_record["token_count"] = token_count
    sources.append(source_record)

    used_tokens = _to_int(snapshot.get("used_tokens"), default=0) + token_count
    budget_tokens = _to_int(snapshot.get("budget_tokens"), default=0)
    remaining_tokens = max(budget_tokens - used_tokens, 0)

    snapshot["sources"] = sources
    snapshot["used_tokens"] = used_tokens
    snapshot["remaining_tokens"] = remaining_tokens
    snapshot["load_stage"] = load_stage

    exhausted = remaining_tokens <= 0
    return snapshot, exhausted


def update_load_stage(context_budget: dict[str, Any], load_stage: str) -> dict[str, Any]:
    snapshot = dict(context_budget or {})
    snapshot["load_stage"] = load_stage
    snapshot.setdefault("sources", [])
    return snapshot


def _to_int(value: Any, *, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default
