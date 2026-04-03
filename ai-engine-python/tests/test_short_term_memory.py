from __future__ import annotations

from memory.short_term import get_latest_verifier_failure, update_short_term_memory


def test_short_term_memory_update_and_readback() -> None:
    state = {"short_term_memory": {}}
    updated = update_short_term_memory(
        state,
        snapshot_type="verifier_failure",
        payload={"failed_stage": "compile", "reason": "compile_failed"},
    )
    assert updated["latest_verifier_failure"]["failed_stage"] == "compile"
    assert get_latest_verifier_failure(updated) == {"failed_stage": "compile", "reason": "compile_failed"}
