from __future__ import annotations

from core.context_budget import initialize_context_budget, register_loaded_context


def test_context_budget_lazy_updates_usage() -> None:
    budget = initialize_context_budget({"context_policy": "lazy", "context_budget_tokens": 100})
    assert budget["enabled"] is True
    updated, exhausted = register_loaded_context(
        budget,
        source_item={"source_id": "ctx-1", "kind": "snippet_window", "content": "abcd" * 20},
        load_stage="issue_snippet",
    )
    assert updated["used_tokens"] > 0
    assert updated["remaining_tokens"] < 100
    assert exhausted is False
