from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from failure_taxonomy import normalize_failure_taxonomy


SCHEMA_VERSION = "day7.eval.v1"


def run_offline_eval(
    *,
    case_ids: list[str],
    golden_dir: Path,
    results_file: Path | None,
) -> dict[str, Any]:
    result_by_case: dict[str, dict[str, Any]] = {}
    if results_file and results_file.exists():
        payload = json.loads(results_file.read_text(encoding="utf-8"))
        for row in payload.get("cases", []):
            if isinstance(row, dict):
                result_by_case[str(row.get("case_id") or "")] = row

    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        meta = _load_case_meta(golden_dir, case_id)
        row = result_by_case.get(case_id, {})
        case_result = _build_case_result(case_id=case_id, meta=meta, row=row, default_mode="offline")
        cases.append(case_result)

    return _assemble_report(mode="offline", ok=True, error=None, cases=cases)


def run_live_eval(
    *,
    case_ids: list[str],
    golden_dir: Path,
    backend_base_url: str,
    poll_interval_sec: float,
    timeout_sec: int,
) -> dict[str, Any]:
    if not backend_base_url.strip():
        return _assemble_report(
            mode="live",
            ok=False,
            error={"code": "not_configured", "message": "Live mode requires --backend-base-url."},
            cases=[],
        )

    try:
        import requests
    except Exception:
        return _assemble_report(
            mode="live",
            ok=False,
            error={"code": "not_configured", "message": "Live mode requires python package `requests`."},
            cases=[],
        )

    cases: list[dict[str, Any]] = []
    for case_id in case_ids:
        meta = _load_case_meta(golden_dir, case_id)
        snippet = _read_buggy_snippet(golden_dir, case_id)
        if not snippet:
            cases.append(
                _build_case_result(
                    case_id=case_id,
                    meta=meta,
                    row={
                        "final_outcome": "failed_no_patch",
                        "failure_taxonomy": {"bucket": "F7_context_insufficient", "code": None, "explanation": "missing_snippet"},
                    },
                    default_mode="live",
                )
            )
            continue

        row = _execute_live_case(
            requests_module=requests,
            backend_base_url=backend_base_url,
            code_text=snippet,
            timeout_sec=timeout_sec,
            poll_interval_sec=poll_interval_sec,
        )
        cases.append(_build_case_result(case_id=case_id, meta=meta, row=row, default_mode="live"))

    return _assemble_report(mode="live", ok=True, error=None, cases=cases)


def _execute_live_case(
    *,
    requests_module,
    backend_base_url: str,
    code_text: str,
    timeout_sec: int,
    poll_interval_sec: float,
) -> dict[str, Any]:
    create_resp = requests_module.post(
        f"{backend_base_url.rstrip('/')}/api/reviews",
        json={"codeText": code_text, "language": "java", "sourceType": "snippet"},
        timeout=15,
    )
    if create_resp.status_code >= 400:
        return {
            "final_outcome": "failed_no_patch",
            "failure_taxonomy": {"bucket": "F8_wrong_tool_selection", "code": "create_review_failed", "explanation": "backend_rejected"},
        }
    task = create_resp.json()
    task_id = str(task.get("taskId") or "")
    if not task_id:
        return {
            "final_outcome": "failed_no_patch",
            "failure_taxonomy": {"bucket": "F8_wrong_tool_selection", "code": "missing_task_id", "explanation": "backend_response_invalid"},
        }

    start = time.monotonic()
    while time.monotonic() - start <= timeout_sec:
        detail_resp = requests_module.get(
            f"{backend_base_url.rstrip('/')}/api/reviews/{task_id}",
            timeout=15,
        )
        if detail_resp.status_code >= 400:
            return {
                "final_outcome": "failed_no_patch",
                "failure_taxonomy": {"bucket": "F8_wrong_tool_selection", "code": "detail_failed", "explanation": "detail_endpoint_error"},
            }
        detail = detail_resp.json()
        status = str(detail.get("status") or "")
        if status in {"COMPLETED", "FAILED"}:
            result = detail.get("result") if isinstance(detail.get("result"), dict) else {}
            summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
            delivery = result.get("delivery") if isinstance(result.get("delivery"), dict) else {}
            verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
            patch = result.get("patch") if isinstance(result.get("patch"), dict) else {}
            return {
                "final_outcome": delivery.get("final_outcome") or summary.get("final_outcome"),
                "verified_level": delivery.get("verified_level") or summary.get("verified_level"),
                "retry_count": summary.get("retry_count", 0),
                "failure_taxonomy": summary.get("failure_taxonomy"),
                "issues": result.get("issues", []),
                "patch": patch,
                "delivery": delivery,
                "verification": verification,
                "tool_trace": result.get("tool_trace", []),
                "llm_trace": result.get("llm_trace", []),
                "latency_sec": _task_latency_seconds(detail.get("createdAt"), detail.get("updatedAt")),
            }
        time.sleep(max(0.1, poll_interval_sec))

    return {
        "final_outcome": "failed_after_retries",
        "failure_taxonomy": {"bucket": "not_configured", "code": "live_timeout", "explanation": "poll_timeout"},
    }


def _task_latency_seconds(created_at: Any, updated_at: Any) -> float:
    try:
        c = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        u = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        return max(0.0, (u - c).total_seconds())
    except Exception:
        return 0.0


def _build_case_result(*, case_id: str, meta: dict[str, Any], row: dict[str, Any], default_mode: str) -> dict[str, Any]:
    issue_count = len(row.get("issues", [])) if isinstance(row.get("issues"), list) else 0
    delivery = row.get("delivery") if isinstance(row.get("delivery"), dict) else {}
    patch = row.get("patch") if isinstance(row.get("patch"), dict) else {}
    verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
    taxonomy = normalize_failure_taxonomy(row.get("failure_taxonomy"))
    tool_trace = row.get("tool_trace") if isinstance(row.get("tool_trace"), list) else []
    llm_trace = row.get("llm_trace") if isinstance(row.get("llm_trace"), list) else []
    expected_tools = [str(item) for item in meta.get("expected_detection", []) if str(item).strip()]

    patch_diff = str(delivery.get("unified_diff") or patch.get("unified_diff") or patch.get("content") or "")
    verified_level = str(row.get("verified_level") or delivery.get("verified_level") or verification.get("verified_level") or "L0")
    stage_status = {
        "patch_apply": _stage_status(verification, "patch_apply"),
        "compile": _stage_status(verification, "compile"),
        "lint": _stage_status(verification, "lint"),
        "test": _stage_status(verification, "test"),
        "security_rescan": _stage_status(verification, "security_rescan"),
    }

    return {
        "case_id": case_id,
        "mode": default_mode,
        "issue_count": issue_count,
        "detection_hit": issue_count > 0,
        "patch_generated": bool(patch_diff.strip()),
        "patch_apply_pass": _stage_passed(verification, "patch_apply"),
        "l1_pass": _verified_at_least(verified_level, "L1"),
        "l2_pass": _verified_at_least(verified_level, "L2"),
        "l3_pass": _verified_at_least(verified_level, "L3"),
        "l4_pass": _verified_at_least(verified_level, "L4"),
        "final_verified": str(row.get("final_outcome") or "") == "verified_patch",
        "retry_count": int(row.get("retry_count") or 0),
        "latency_sec": float(row.get("latency_sec") or 0.0),
        "token_cost": int(_token_cost(llm_trace)),
        "verified_level": verified_level,
        "final_verified_level": verified_level,
        "patch_apply": stage_status["patch_apply"],
        "compile": stage_status["compile"],
        "lint": stage_status["lint"],
        "test": stage_status["test"],
        "security_rescan": stage_status["security_rescan"],
        "failure_taxonomy": taxonomy.to_dict(),
        "tool_trace": tool_trace,
        "expected_tools": expected_tools,
    }


def _assemble_report(*, mode: str, ok: bool, error: dict[str, Any] | None, cases: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = _compute_metrics(cases)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "ok": ok,
        "error": error,
        "summary": {
            "case_count": len(cases),
            "ok_cases": sum(1 for item in cases if item.get("final_verified")),
            "failed_cases": sum(1 for item in cases if not item.get("final_verified")),
        },
        "metrics": metrics,
        "funnel": _compute_funnel(cases),
        "cases": cases,
    }


def _compute_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    detection_hit = sum(1 for item in cases if item.get("detection_hit"))
    patch_generated = sum(1 for item in cases if item.get("patch_generated"))
    patch_apply_pass = sum(1 for item in cases if item.get("patch_apply_pass"))
    l1 = sum(1 for item in cases if item.get("l1_pass"))
    l2 = sum(1 for item in cases if item.get("l2_pass"))
    l3 = sum(1 for item in cases if item.get("l3_pass"))
    l4 = sum(1 for item in cases if item.get("l4_pass"))
    final_verified = sum(1 for item in cases if item.get("final_verified"))

    retries = [int(item.get("retry_count") or 0) for item in cases]
    latencies = [float(item.get("latency_sec") or 0.0) for item in cases]
    token_costs = [float(item.get("token_cost") or 0.0) for item in cases]

    tool_expected = 0
    tool_actual = 0
    tool_tp = 0
    for item in cases:
        expected = {str(x) for x in item.get("expected_tools", []) if str(x).strip()}
        actual = {
            str(x.get("tool_name"))
            for x in item.get("tool_trace", [])
            if isinstance(x, dict) and str(x.get("tool_name", "")).strip()
        }
        tool_expected += len(expected)
        tool_actual += len(actual)
        tool_tp += len(expected.intersection(actual))

    detection_recall = _rate(detection_hit, total)
    detection_precision = _rate(detection_hit, detection_hit) if detection_hit else 0.0

    return {
        "detection_precision": detection_precision,
        "detection_recall": detection_recall,
        "patch_generation_rate": _rate(patch_generated, total),
        "patch_apply_rate": _rate(patch_apply_pass, total),
        "l1_pass_rate": _rate(l1, total),
        "l2_pass_rate": _rate(l2, total),
        "l3_pass_rate": _rate(l3, total),
        "l4_pass_rate": _rate(l4, total),
        "final_verified_patch_rate": _rate(final_verified, total),
        "retry_avg": round(sum(retries) / total, 6) if total else 0.0,
        "latency_avg": round(sum(latencies) / total, 6) if total else 0.0,
        "token_cost": round(sum(token_costs), 6),
        "tool_calling_recall": _rate(tool_tp, tool_expected),
        "tool_calling_precision": _rate(tool_tp, tool_actual),
    }


def _compute_funnel(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    stages = {
        "detected": sum(1 for item in cases if item.get("detection_hit")),
        "patch_generated": sum(1 for item in cases if item.get("patch_generated")),
        "patch_applied": sum(1 for item in cases if item.get("patch_apply_pass")),
        "l1": sum(1 for item in cases if item.get("l1_pass")),
        "l2": sum(1 for item in cases if item.get("l2_pass")),
        "l3": sum(1 for item in cases if item.get("l3_pass")),
        "l4": sum(1 for item in cases if item.get("l4_pass")),
        "verified": sum(1 for item in cases if item.get("final_verified")),
    }
    return {
        "total": total,
        "stages": {key: {"count": value, "rate": _rate(value, total)} for key, value in stages.items()},
    }


def _load_case_ids(splits_dir: Path, split: str) -> list[str]:
    names = ("train", "val", "test") if split == "all" else (split,)
    case_ids: list[str] = []
    for name in names:
        path = splits_dir / f"{name}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("case_ids", [])
        else:
            rows = payload
        for item in rows:
            value = str(item).strip()
            if value and value not in case_ids:
                case_ids.append(value)
    return case_ids


def _load_case_meta(golden_dir: Path, case_id: str) -> dict[str, Any]:
    meta_path = golden_dir / case_id / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _read_buggy_snippet(golden_dir: Path, case_id: str) -> str:
    case_dir = golden_dir / case_id
    candidates = sorted(case_dir.glob("src/main/java/**/BuggySnippet.java.txt"))
    if not candidates:
        return ""
    try:
        return candidates[0].read_text(encoding="utf-8")
    except Exception:
        return ""


def _verified_at_least(actual: str, target: str) -> bool:
    order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}
    return order.get(actual, 0) >= order.get(target, 0)


def _stage_passed(verification: dict[str, Any], stage: str) -> bool:
    stages = verification.get("stages")
    if not isinstance(stages, list):
        return False
    for item in stages:
        if not isinstance(item, dict):
            continue
        if str(item.get("stage") or "") != stage:
            continue
        return str(item.get("status") or "") == "passed"
    return False


def _stage_status(verification: dict[str, Any], stage: str) -> str:
    stages = verification.get("stages")
    if not isinstance(stages, list):
        return "pending"
    for item in stages:
        if not isinstance(item, dict):
            continue
        if str(item.get("stage") or "") != stage:
            continue
        return str(item.get("status") or "pending")
    return "pending"


def _token_cost(llm_trace: list[Any]) -> int:
    total = 0
    for item in llm_trace:
        if not isinstance(item, dict):
            continue
        total += int(item.get("token_in") or 0)
        total += int(item.get("token_out") or 0)
    return total


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Sentinel-CR benchmark evaluation.")
    parser.add_argument("--golden-dir", default="benchmark/golden_cases")
    parser.add_argument("--splits-dir", default="benchmark/splits")
    parser.add_argument("--split", default="all", choices=["all", "train", "val", "test"])
    parser.add_argument("--results-file", default="benchmark/results/latest_results.json")
    parser.add_argument("--output", default="benchmark/results/latest_eval.json")
    parser.add_argument("--live", action="store_true", help="Run live evaluation via backend API")
    parser.add_argument("--backend-base-url", default="")
    parser.add_argument("--poll-interval-sec", type=float, default=1.0)
    parser.add_argument("--timeout-sec", type=int, default=180)
    args = parser.parse_args()

    golden_dir = Path(args.golden_dir)
    splits_dir = Path(args.splits_dir)
    case_ids = _load_case_ids(splits_dir, args.split)

    if args.live:
        report = run_live_eval(
            case_ids=case_ids,
            golden_dir=golden_dir,
            backend_base_url=args.backend_base_url,
            poll_interval_sec=args.poll_interval_sec,
            timeout_sec=args.timeout_sec,
        )
    else:
        results_file = Path(args.results_file) if args.results_file else None
        report = run_offline_eval(case_ids=case_ids, golden_dir=golden_dir, results_file=results_file)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
