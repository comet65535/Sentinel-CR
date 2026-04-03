from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LEGACY_REQUIRED_FIELDS = {
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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_cases_dir() -> Path:
    return _repo_root() / "data" / "cases"


def legacy_cases_dir() -> Path:
    return _repo_root() / "ai-engine-python" / "data" / "cases"


def _candidate_case_dirs(cases_dir: str | Path | None = None) -> list[Path]:
    if cases_dir:
        return [Path(cases_dir)]
    candidates = [default_cases_dir(), legacy_cases_dir()]
    unique: list[Path] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique


def load_cases(cases_dir: str | Path | None = None) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for base_dir in _candidate_case_dirs(cases_dir):
        if not base_dir.exists():
            continue
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
    return _dedupe_cases(cases)


def load_case_examples(
    *,
    pattern_name: str | None = None,
    bug_type: str | None = None,
    limit: int | None = None,
    cases_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    pattern_token = (pattern_name or "").strip().lower()
    bug_token = (bug_type or "").strip().lower()

    filtered: list[dict[str, Any]] = []
    for case in load_cases(cases_dir=cases_dir):
        if pattern_token:
            case_pattern = str(case.get("pattern_name") or case.get("pattern") or "").lower()
            if case_pattern != pattern_token:
                continue
        if bug_token:
            case_bug = str(case.get("bug_type") or "").lower()
            if case_bug != bug_token:
                continue
        filtered.append(case)

    if limit is None:
        return filtered
    return filtered[: max(1, int(limit))]


def search_repair_cases(
    *,
    query: str,
    limit: int = 3,
    bug_type: str | None = None,
    semantic_only: bool = False,
    cases_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    query_tokens = _extract_tokens(query)
    if not query_tokens:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    bug_type_token = (bug_type or "").strip().lower()
    for case in load_cases(cases_dir=cases_dir):
        if bug_type_token and str(case.get("bug_type") or "").lower() != bug_type_token:
            continue
        if semantic_only:
            category = str(case.get("category") or "").lower()
            if category not in {"semantic_compile_fix", "semantic_compile"}:
                continue

        searchable: set[str] = set()
        for raw in case.get("trigger_signals", []):
            token = str(raw).lower()
            if not token:
                continue
            searchable.add(token)
            searchable.update(_extract_tokens(token))
        for raw in (
            case.get("pattern_name"),
            case.get("pattern"),
            case.get("bug_type"),
            case.get("category"),
            case.get("explanation"),
        ):
            token = str(raw or "").lower()
            if not token:
                continue
            searchable.add(token)
            searchable.update(_extract_tokens(token))
        overlap = query_tokens.intersection(searchable)
        if not overlap:
            continue
        overlap_score = min(len(overlap) / max(len(searchable), 1), 1.0)
        success_rate = float(case.get("success_rate", 0.0))
        score = round((overlap_score * 0.7) + (success_rate * 0.3), 4)
        item = dict(case)
        item["score"] = score
        scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], str(x[1].get("case_id", ""))))
    return [item for _, item in scored[: max(1, int(limit))]]


def search_cases(
    *,
    query_tokens: set[str],
    top_k: int = 3,
    cases_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not query_tokens:
        return []
    query = " ".join(sorted({str(token).strip().lower() for token in query_tokens if str(token).strip()}))
    return search_repair_cases(query=query, limit=top_k, cases_dir=cases_dir)


def append_case(case_record: dict[str, Any], *, cases_dir: str | Path | None = None) -> dict[str, Any]:
    record = _normalize_case(case_record)
    target_dir = default_cases_dir() if cases_dir is None else Path(cases_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "cases.jsonl"
    with target_file.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")
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
        "pattern_name": strategy,
        "language": "java",
        "category": "runtime_promoted",
        "bug_type": strategy,
        "rule_source": "runtime_verification",
        "trigger_analyzer": "verifier",
        "trigger_signals": [strategy],
        "buggy_code_snippet": "",
        "fixed_code_snippet": "",
        "patch_diff": diff,
        "explanation": "Promoted from verified runtime patch artifact.",
        "risk_note": str(patch.get("risk_level") or "unknown"),
        "verified_level": str(verification.get("verified_level") or "L1"),
        "success_rate": 1.0,
        "accepted_by_human": bool(accepted_by_human),
        "tags": ["promoted", "runtime"],
        "tool_trace": list(tool_trace or []),
    }
    return append_case(record, cases_dir=cases_dir)


def _normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    record = dict(case)

    pattern_name = str(record.get("pattern_name") or record.get("pattern") or "").strip() or "unknown_pattern"
    patch_diff = str(record.get("patch_diff") or record.get("diff") or "")
    buggy_code = str(record.get("buggy_code_snippet") or record.get("before_code") or "")
    fixed_code = str(record.get("fixed_code_snippet") or record.get("after_code") or "")

    record["case_id"] = str(record.get("case_id") or "").strip() or "case-unknown"
    record["pattern_name"] = pattern_name
    record["pattern"] = pattern_name
    record["language"] = str(record.get("language") or "java")
    record["category"] = str(record.get("category") or "general")
    record["bug_type"] = str(record.get("bug_type") or pattern_name)
    record["rule_source"] = str(record.get("rule_source") or "heuristic")
    record["trigger_analyzer"] = str(record.get("trigger_analyzer") or "analyzer")
    record["trigger_signals"] = _to_string_list(record.get("trigger_signals"))
    record["buggy_code_snippet"] = buggy_code
    record["fixed_code_snippet"] = fixed_code
    record["patch_diff"] = patch_diff
    record["explanation"] = str(record.get("explanation") or "")
    record["risk_note"] = str(record.get("risk_note") or "")
    record["verified_level"] = str(record.get("verified_level") or "L0")
    record["success_rate"] = _to_float(record.get("success_rate"), default=0.0)
    record["accepted_by_human"] = bool(record.get("accepted_by_human", False))
    record["tags"] = _to_string_list(record.get("tags"))
    record["tool_trace"] = list(record.get("tool_trace") or [])

    # Legacy aliases used by existing pipeline and tests.
    record["before_code"] = buggy_code
    record["after_code"] = fixed_code
    record["diff"] = patch_diff
    record.setdefault("strategy", pattern_name)
    for field in LEGACY_REQUIRED_FIELDS:
        record.setdefault(field, None)

    return record


def _extract_tokens(text: str) -> set[str]:
    normalized = text.replace(".", " ").replace("-", " ").replace("_", " ").replace("/", " ").lower()
    return {item.strip() for item in normalized.split() if item.strip()}


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


def _dedupe_cases(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("case_id") or "").strip()
        key = case_id or json.dumps(case, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(case)
    return deduped
