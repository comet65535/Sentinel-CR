from __future__ import annotations

from pathlib import Path

from memory.case_store import append_case, load_cases, search_cases


def test_case_store_append_and_search(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    append_case(
        {
            "case_id": "case-test-1",
            "pattern": "null_guard",
            "trigger_signals": ["null_pointer", "null_guard"],
            "before_code": "a",
            "after_code": "b",
            "diff": "diff --git a/snippet.java b/snippet.java",
            "risk_note": "low",
            "success_rate": 0.9,
            "verified_level": "L1",
            "accepted_by_human": False,
            "tool_trace": [],
        },
        cases_dir=cases_dir,
    )

    all_cases = load_cases(cases_dir=cases_dir)
    assert len(all_cases) == 1
    matches = search_cases(query_tokens={"null_guard"}, top_k=3, cases_dir=cases_dir)
    assert matches
    assert matches[0]["case_id"] == "case-test-1"
