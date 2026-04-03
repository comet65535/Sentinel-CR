from __future__ import annotations

import json
from pathlib import Path

from tools.export_training_data import export_training_data


def test_export_training_data_from_cases_and_splits(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    (cases_dir / "semantic_compile_cases.jsonl").write_text(
        json.dumps(
            {
                "case_id": "case-sem-1",
                "pattern_name": "missing_return_string",
                "bug_type": "missing_return_string",
                "category": "semantic_compile_fix",
                "trigger_signals": ["missing_return"],
                "patch_diff": "diff --git a/A.java b/A.java",
                "success_rate": 0.9,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    golden_dir = tmp_path / "golden_cases"
    case_dir = golden_dir / "case_001_missing_return_string"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "meta.json").write_text(
        json.dumps(
            {
                "case_id": "case_001_missing_return_string",
                "title": "missing return string",
                "bug_type": "missing_return_string",
                "difficulty": "medium",
                "expected_detection": ["analyzer"],
                "expected_strategy": "semantic_compile_fix",
                "expected_verified_level_min": "L1",
                "build_command": "mvn -q -DskipTests compile",
                "test_command": "mvn -q test",
                "entry_files": ["src/main/java"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    splits_dir = tmp_path / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)
    for split_name in ("train", "val", "test"):
        payload = {"case_ids": ["case_001_missing_return_string"]} if split_name == "train" else {"case_ids": []}
        (splits_dir / f"{split_name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    swift_dir = tmp_path / "swift"
    verl_dir = tmp_path / "verl"
    summary = export_training_data(
        cases_dir=cases_dir,
        golden_dir=golden_dir,
        splits_dir=splits_dir,
        swift_output_dir=swift_dir,
        verl_output_dir=verl_dir,
    )

    assert summary["swift"]["train"] == 1
    assert summary["verl"]["train"] == 1
    assert (swift_dir / "train.jsonl").exists()
    assert (verl_dir / "train.jsonl").exists()
