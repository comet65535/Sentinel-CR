from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_CASE_FIELDS = {
    "case_id",
    "pattern",
    "trigger_signals",
    "before_code",
    "after_code",
    "diff",
    "risk_note",
    "success_rate",
    "verified_level",
    "accepted_by_human",
    "tool_trace",
}


def default_cases_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "cases"


def load_cases(cases_dir: str | Path | None = None) -> list[dict[str, Any]]:
    base_dir = Path(cases_dir) if cases_dir else default_cases_dir()
    if not base_dir.exists():
        return []

    cases: list[dict[str, Any]] = []
    for jsonl_file in sorted(base_dir.glob("*.jsonl")):
        for line in jsonl_file.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            cases.append(_normalize_case(record))
    return cases


def search_cases(
    *,
    query_tokens: set[str],
    top_k: int = 3,
    cases_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not query_tokens:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for case in load_cases(cases_dir):
        signals = {str(item).lower() for item in case.get("trigger_signals", [])}
        signals.add(str(case.get("pattern", "")).lower())
        overlap = query_tokens.intersection(signals)
        if not overlap:
            continue
        overlap_score = min(len(overlap) / max(len(signals), 1), 1.0)
        success_rate = float(case.get("success_rate", 0.0))
        score = round((overlap_score * 0.7) + (success_rate * 0.3), 4)
        item = dict(case)
        item["score"] = score
        scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("case_id", ""))))
    limit = max(1, int(top_k))
    return [item for _, item in scored[:limit]]


def append_case(case_record: dict[str, Any], *, cases_dir: str | Path | None = None) -> dict[str, Any]:
    record = _normalize_case(case_record)
    base_dir = Path(cases_dir) if cases_dir else default_cases_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    target_file = base_dir / "cases.jsonl"
    with target_file.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=True) + "\n")
    return record


def promote_verified_patch_to_case(
    *,
    patch: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    tool_trace: list[dict[str, Any]] | None,
    accepted_by_human: bool = False,
    cases_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    if not patch or not verification:
        return None
    if str(verification.get("status")) != "passed":
        return None

    case_id = f"case-promoted-{str(patch.get('patch_id') or 'unknown')}"
    strategy = str(patch.get("strategy_used") or "manual_review")
    diff = str(patch.get("content") or "").strip()
    if not diff:
        return None

    record = {
        "case_id": case_id,
        "pattern": strategy,
        "trigger_signals": [strategy],
        "before_code": "",
        "after_code": "",
        "diff": diff,
        "risk_note": str(patch.get("risk_level") or "unknown"),
        "success_rate": 1.0,
        "verified_level": str(verification.get("verified_level") or "L1"),
        "accepted_by_human": bool(accepted_by_human),
        "tool_trace": list(tool_trace or []),
    }
    return append_case(record, cases_dir=cases_dir)


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    record = dict(case)
    for field in REQUIRED_CASE_FIELDS:
        record.setdefault(field, None)

    record["case_id"] = str(record.get("case_id") or "").strip() or "case-unknown"
    record["pattern"] = str(record.get("pattern") or "").strip() or "unknown_pattern"
    record.setdefault("strategy", record["pattern"])
    record["trigger_signals"] = _to_string_list(record.get("trigger_signals"))
    record["before_code"] = str(record.get("before_code") or "")
    record["after_code"] = str(record.get("after_code") or "")
    record["diff"] = str(record.get("diff") or "")
    record["risk_note"] = str(record.get("risk_note") or "")
    record["success_rate"] = _to_float(record.get("success_rate"), default=0.0)
    record["verified_level"] = str(record.get("verified_level") or "L0")
    record["accepted_by_human"] = bool(record.get("accepted_by_human", False))
    record["tool_trace"] = list(record.get("tool_trace") or [])
    return record


def _to_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _to_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default
