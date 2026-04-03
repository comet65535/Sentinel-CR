from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ensure_python_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    engine_path = repo_root / "ai-engine-python"
    if str(engine_path) not in sys.path:
        sys.path.insert(0, str(engine_path))


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def main() -> int:
    _ensure_python_path()
    from memory.case_store import load_cases, promote_verified_patch_to_case

    parser = argparse.ArgumentParser(description="Promote verified patches into long-term case store.")
    parser.add_argument("--input", default="completed-log/verified_cases.jsonl")
    parser.add_argument("--cases-dir", default="data/cases")
    parser.add_argument("--report", default="knowledge/reports/promote_verified_cases_report.json")
    args = parser.parse_args()

    ingest_time = datetime.now(timezone.utc).isoformat()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    if not input_path.exists():
        report = {
            "ok": False,
            "error": {"code": "not_configured", "message": "verified case source file is not configured"},
            "ingest_time": ingest_time,
            "promoted_count": 0,
            "skipped_existing": 0,
            "failed_entries": 0,
            "collection": "repair_cases",
        }
        text = json.dumps(report, ensure_ascii=False, indent=2)
        report_path.write_text(text, encoding="utf-8")
        print(text)
        return 0

    existing_case_ids = {str(case.get("case_id") or "") for case in load_cases(cases_dir=args.cases_dir)}
    promoted_count = 0
    skipped_existing = 0
    failed_entries = 0
    promoted_ids: list[str] = []

    for row in _iter_jsonl(input_path):
        patch = row.get("patch") if isinstance(row.get("patch"), dict) else {}
        verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
        tool_trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), list) else []
        patch_id = str(patch.get("patch_id") or patch.get("hash") or row.get("task_id") or "unknown")
        expected_case_id = f"case-promoted-{patch_id}"

        if expected_case_id in existing_case_ids:
            skipped_existing += 1
            continue

        promoted = promote_verified_patch_to_case(
            patch=patch,
            verification=verification,
            tool_trace=tool_trace,
            accepted_by_human=bool(row.get("accepted_by_human", False)),
            cases_dir=args.cases_dir,
        )
        if not promoted:
            failed_entries += 1
            continue

        promoted_case_id = str(promoted.get("case_id") or expected_case_id)
        existing_case_ids.add(promoted_case_id)
        promoted_ids.append(promoted_case_id)
        promoted_count += 1

    report = {
        "ok": True,
        "error": None,
        "ingest_time": ingest_time,
        "collection": "repair_cases",
        "promoted_count": promoted_count,
        "skipped_existing": skipped_existing,
        "failed_entries": failed_entries,
        "promoted_case_ids": promoted_ids,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
