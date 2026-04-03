from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "day7.eval.v1"


def evaluate_tool_traces(cases: list[dict[str, Any]]) -> dict[str, Any]:
    expected_total = 0
    actual_total = 0
    true_positive = 0
    wrong_tool_calls = 0
    case_rows: list[dict[str, Any]] = []

    for case in cases:
        expected_tools = [str(item) for item in case.get("expected_tools", []) if str(item).strip()]
        actual_tools = [
            str(item.get("tool_name"))
            for item in case.get("tool_trace", [])
            if isinstance(item, dict) and str(item.get("tool_name", "")).strip()
        ]
        expected_set = set(expected_tools)
        actual_set = set(actual_tools)

        tp = len(expected_set.intersection(actual_set))
        expected_total += len(expected_set)
        actual_total += len(actual_set)
        true_positive += tp
        wrong_tool_calls += max(0, len(actual_set.difference(expected_set)))

        case_rows.append(
            {
                "case_id": str(case.get("case_id") or ""),
                "expected_count": len(expected_set),
                "actual_count": len(actual_set),
                "true_positive": tp,
            }
        )

    recall = true_positive / expected_total if expected_total else 0.0
    precision = true_positive / actual_total if actual_total else 0.0

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": True,
        "error": None,
        "summary": {
            "cases_total": len(cases),
            "expected_total": expected_total,
            "actual_total": actual_total,
            "true_positive_total": true_positive,
            "wrong_tool_calls": wrong_tool_calls,
        },
        "metrics": {
            "tool_calling_recall": round(recall, 6),
            "tool_calling_precision": round(precision, 6),
            "wrong_tool_call_rate": round((wrong_tool_calls / actual_total) if actual_total else 0.0, 6),
        },
        "cases": case_rows,
    }


def _load_cases(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        return [item for item in payload["cases"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate tool trace recall/precision metrics.")
    parser.add_argument("--input", default="benchmark/results/latest_eval.json", help="Input evaluation JSON file")
    parser.add_argument("--output", default="", help="Output path; prints to stdout when omitted")
    args = parser.parse_args()

    cases = _load_cases(Path(args.input))
    report = evaluate_tool_traces(cases)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
