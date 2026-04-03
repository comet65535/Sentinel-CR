from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memory.case_store import load_cases


def export_training_data(
    *,
    cases_dir: str | Path,
    golden_dir: str | Path,
    splits_dir: str | Path,
    swift_output_dir: str | Path,
    verl_output_dir: str | Path,
) -> dict[str, Any]:
    case_records = load_cases(cases_dir=cases_dir)
    case_by_bug_type = _index_cases_by_bug_type(case_records)
    golden_meta = _load_golden_meta(golden_dir)
    splits = _load_splits(splits_dir)

    swift_dir = Path(swift_output_dir)
    verl_dir = Path(verl_output_dir)
    swift_dir.mkdir(parents=True, exist_ok=True)
    verl_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {"swift": {}, "verl": {}}
    for split_name, case_ids in splits.items():
        swift_rows: list[dict[str, Any]] = []
        verl_rows: list[dict[str, Any]] = []
        for case_id in case_ids:
            meta = golden_meta.get(case_id)
            if not meta:
                continue
            bug_type = str(meta.get("bug_type") or "unknown")
            matched_case = _pick_case_for_bug_type(case_by_bug_type, bug_type)
            expected_patch = (matched_case.get("patch_diff") or matched_case.get("diff") or "") if matched_case else ""
            source_case_id = str(matched_case.get("case_id") or case_id) if matched_case else case_id

            swift_rows.append(
                {
                    "id": f"swift::{split_name}::{case_id}",
                    "instruction": _build_instruction(meta),
                    "input_context": _build_input_context(meta, matched_case),
                    "expected_patch": expected_patch,
                    "expected_verification": {
                        "verified_level_min": meta.get("expected_verified_level_min"),
                        "build_command": meta.get("build_command"),
                        "test_command": meta.get("test_command"),
                    },
                    "bug_type": bug_type,
                    "source_case_id": source_case_id,
                }
            )

            verl_rows.append(
                {
                    "id": f"verl::{split_name}::{case_id}",
                    "task": _build_instruction(meta),
                    "context": _build_input_context(meta, matched_case),
                    "expected_tool_sequence": _expected_tool_sequence(meta),
                    "expected_final_action": "emit_verified_patch",
                    "bug_type": bug_type,
                    "source_case_id": source_case_id,
                }
            )

        _write_jsonl(swift_dir / f"{split_name}.jsonl", swift_rows)
        _write_jsonl(verl_dir / f"{split_name}.jsonl", verl_rows)
        summary["swift"][split_name] = len(swift_rows)
        summary["verl"][split_name] = len(verl_rows)

    return summary


def _load_splits(splits_dir: str | Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for split_name in ("train", "val", "test"):
        split_path = Path(splits_dir) / f"{split_name}.json"
        if not split_path.exists():
            result[split_name] = []
            continue
        parsed = json.loads(_read_json_text(split_path))
        if isinstance(parsed, dict):
            case_ids = parsed.get("case_ids", [])
        else:
            case_ids = parsed
        normalized = [str(item).strip() for item in case_ids if str(item).strip()]
        result[split_name] = normalized
    return result


def _load_golden_meta(golden_dir: str | Path) -> dict[str, dict[str, Any]]:
    root = Path(golden_dir)
    result: dict[str, dict[str, Any]] = {}
    for meta_file in sorted(root.glob("*/meta.json")):
        try:
            parsed = json.loads(_read_json_text(meta_file))
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        case_id = str(parsed.get("case_id") or meta_file.parent.name)
        result[case_id] = parsed
    return result


def _index_cases_by_bug_type(case_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = {}
    for case in case_records:
        bug_type = str(case.get("bug_type") or "").strip().lower()
        if not bug_type:
            continue
        mapping.setdefault(bug_type, []).append(case)
    return mapping


def _pick_case_for_bug_type(indexed: dict[str, list[dict[str, Any]]], bug_type: str) -> dict[str, Any] | None:
    items = indexed.get(bug_type.strip().lower(), [])
    if not items:
        return None
    ranked = sorted(items, key=lambda item: float(item.get("success_rate", 0.0)), reverse=True)
    return ranked[0]


def _build_instruction(meta: dict[str, Any]) -> str:
    title = str(meta.get("title") or "Repair Java code")
    strategy = str(meta.get("expected_strategy") or "unknown_strategy")
    return f"{title}. Use strategy `{strategy}` and produce a unified diff patch."


def _build_input_context(meta: dict[str, Any], matched_case: dict[str, Any] | None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "case_id": meta.get("case_id"),
        "bug_type": meta.get("bug_type"),
        "difficulty": meta.get("difficulty"),
        "expected_detection": meta.get("expected_detection"),
        "entry_files": meta.get("entry_files", []),
        "notes": meta.get("notes", ""),
    }
    if matched_case:
        context["retrieved_case"] = {
            "case_id": matched_case.get("case_id"),
            "pattern_name": matched_case.get("pattern_name") or matched_case.get("pattern"),
            "trigger_signals": matched_case.get("trigger_signals", []),
            "explanation": matched_case.get("explanation", ""),
        }
    return context


def _expected_tool_sequence(meta: dict[str, Any]) -> list[str]:
    bug_type = str(meta.get("bug_type") or "").lower()
    sequence = ["analyzer", "planner", "memory_retrieval", "fixer", "verifier_compile"]
    if any(token in bug_type for token in ("sql", "n_plus_one", "resource_leak")):
        sequence.append("verifier_test")
    return sequence


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_json_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")
