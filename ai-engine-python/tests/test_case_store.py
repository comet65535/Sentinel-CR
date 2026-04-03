from __future__ import annotations

import json
from pathlib import Path

from memory.case_store import append_case, load_case_examples, load_cases, search_cases, search_repair_cases


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


def test_case_store_reads_extended_schema_and_semantic_search(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    data_file = cases_dir / "semantic_compile_cases.jsonl"
    data_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "case_id": "case-semantic-1",
                        "pattern_name": "missing_return_string",
                        "language": "java",
                        "category": "semantic_compile_fix",
                        "bug_type": "missing_return_string",
                        "rule_source": "javac",
                        "trigger_analyzer": "javac",
                        "trigger_signals": ["missing_return", "string"],
                        "buggy_code_snippet": "String a(){ if(true){return \"x\";} }",
                        "fixed_code_snippet": "String a(){ if(true){return \"x\";} return \"y\"; }",
                        "patch_diff": "diff --git a/A.java b/A.java",
                        "explanation": "add fallback return",
                        "risk_note": "default literal",
                        "verified_level": "L1",
                        "success_rate": 0.9,
                        "accepted_by_human": False,
                        "tags": ["semantic"],
                    },
                    ensure_ascii=False,
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    all_cases = load_cases(cases_dir=cases_dir)
    assert all_cases
    assert all_cases[0]["pattern"] == "missing_return_string"
    assert all_cases[0]["diff"] == "diff --git a/A.java b/A.java"

    loaded = load_case_examples(pattern_name="missing_return_string", cases_dir=cases_dir, limit=10)
    assert len(loaded) == 1
    assert loaded[0]["bug_type"] == "missing_return_string"

    semantic_hits = search_repair_cases(query="missing return compile", semantic_only=True, cases_dir=cases_dir, limit=3)
    assert semantic_hits
    assert semantic_hits[0]["case_id"] == "case-semantic-1"
