from __future__ import annotations

from typing import Any

FAILURE_BUCKETS = {
    "F1_detection_miss",
    "F2_wrong_patch",
    "F3_compile_error",
    "F4_lint_fail",
    "F5_test_fail",
    "F6_security_rescan_fail",
    "F7_context_insufficient",
    "F8_wrong_tool_selection",
    "semantic_compile_error",
}

SEMANTIC_COMPILE_BUCKETS = {
    "missing_return",
    "incomplete_return_paths",
    "uninitialized_local",
    "simple_type_mismatch",
}


def classify_compile_failure_bucket(stderr_summary: str | None, reason: str | None = None) -> str | None:
    text = f"{reason or ''} {stderr_summary or ''}".lower()
    if not text.strip():
        return None
    if "missing return statement" in text or "缺少返回语句" in text:
        return "missing_return"
    if "not all code paths return a value" in text or "并非所有执行路径都返回值" in text:
        return "incomplete_return_paths"
    if "might not have been initialized" in text or "可能尚未初始化" in text:
        return "uninitialized_local"
    if "incompatible types" in text or "cannot be converted to" in text or "不兼容的类型" in text or "无法转换为" in text:
        return "simple_type_mismatch"
    return None


def build_failure_taxonomy(
    *,
    final_outcome: str,
    failed_stage: str | None,
    failure_reason: str | None,
    failure_detail: str | None,
    issue_count: int = 0,
) -> dict[str, Any]:
    if final_outcome in {"verified_patch", "patch_generated_unverified", "no_fix_needed"}:
        return {"bucket": "none", "code": None, "explanation": None}

    normalized_stage = str(failed_stage or "").strip().lower()
    normalized_reason = str(failure_reason or "").strip().lower()
    normalized_detail = str(failure_detail or "").strip().lower()

    if normalized_stage == "compile":
        semantic_bucket = classify_compile_failure_bucket(failure_detail, failure_reason)
        if semantic_bucket:
            return {
                "bucket": "semantic_compile_error",
                "code": semantic_bucket,
                "explanation": failure_reason or failure_detail,
            }
        return {
            "bucket": "F3_compile_error",
            "code": "compile_failed",
            "explanation": failure_reason or failure_detail,
        }

    if normalized_stage == "lint":
        return {"bucket": "F4_lint_fail", "code": "lint_failed", "explanation": failure_reason or failure_detail}
    if normalized_stage == "test":
        return {"bucket": "F5_test_fail", "code": "test_failed", "explanation": failure_reason or failure_detail}
    if normalized_stage == "security_rescan":
        return {
            "bucket": "F6_security_rescan_fail",
            "code": "security_rescan_failed",
            "explanation": failure_reason or failure_detail,
        }

    if normalized_reason in {"wrong_tool_selection", "tool_mismatch"}:
        return {"bucket": "F8_wrong_tool_selection", "code": normalized_reason, "explanation": failure_detail}
    if normalized_reason in {
        "insufficient_context_for_semantic_fix",
        "insufficient_context",
        "action_loop_exhausted",
        "context_budget_exhausted",
    }:
        return {"bucket": "F7_context_insufficient", "code": normalized_reason, "explanation": failure_detail}
    if normalized_reason in {
        "duplicate_patch_candidate",
        "no_repair_candidate",
        "syntax_repair_failed",
        "semantic_repair_unsupported",
        "no_semantic_candidate",
        "unsafe_default_return",
        "no_valid_patch",
        "invalid_diff",
        "llm_call_failed",
    }:
        return {"bucket": "F2_wrong_patch", "code": normalized_reason, "explanation": failure_detail}
    if issue_count == 0 and final_outcome.startswith("failed"):
        return {"bucket": "F1_detection_miss", "code": "no_issues_detected", "explanation": failure_reason or failure_detail}

    return {"bucket": "F7_context_insufficient", "code": failure_reason, "explanation": failure_detail}
