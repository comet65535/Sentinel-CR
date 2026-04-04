from __future__ import annotations

from typing import Any

LEGACY_BUCKETS = {
    "none",
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

CANONICAL_BUCKETS = {
    "none",
    "detection_miss",
    "wrong_patch",
    "patch_apply_error",
    "compile_error",
    "lint_fail",
    "test_fail",
    "regression_introduced",
    "security_rescan_fail",
    "context_insufficient",
    "tool_selection_error",
    "llm_output_invalid",
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
    if "missing return statement" in text:
        return "missing_return"
    if "not all code paths return a value" in text:
        return "incomplete_return_paths"
    if "might not have been initialized" in text:
        return "uninitialized_local"
    if "incompatible types" in text or "cannot be converted to" in text:
        return "simple_type_mismatch"
    return None


def canonical_to_legacy(bucket: str) -> str:
    mapping = {
        "none": "none",
        "detection_miss": "F1_detection_miss",
        "wrong_patch": "F2_wrong_patch",
        "patch_apply_error": "F2_wrong_patch",
        "compile_error": "F3_compile_error",
        "lint_fail": "F4_lint_fail",
        "test_fail": "F5_test_fail",
        "regression_introduced": "F5_test_fail",
        "security_rescan_fail": "F6_security_rescan_fail",
        "context_insufficient": "F7_context_insufficient",
        "tool_selection_error": "F8_wrong_tool_selection",
        "llm_output_invalid": "F2_wrong_patch",
    }
    return mapping.get(bucket, "F7_context_insufficient")


def build_failure_taxonomy(
    *,
    final_outcome: str,
    failed_stage: str | None,
    failure_reason: str | None,
    failure_detail: str | None,
    issue_count: int = 0,
) -> dict[str, Any]:
    if final_outcome in {"verified_patch", "patch_generated_unverified", "no_fix_needed"}:
        return {
            "bucket": "none",
            "legacy_bucket": "none",
            "code": None,
            "explanation": None,
        }

    normalized_stage = str(failed_stage or "").strip().lower()
    normalized_reason = str(failure_reason or "").strip().lower()

    if normalized_stage == "patch_apply":
        return _taxonomy("patch_apply_error", "patch_apply_failed", failure_reason or failure_detail)

    if normalized_stage == "compile":
        semantic_bucket = classify_compile_failure_bucket(failure_detail, failure_reason)
        code = semantic_bucket if semantic_bucket else "compile_failed"
        return _taxonomy("compile_error", code, failure_reason or failure_detail)

    if normalized_stage == "lint":
        return _taxonomy("lint_fail", "lint_failed", failure_reason or failure_detail)

    if normalized_stage == "test":
        if "regression" in normalized_reason:
            return _taxonomy("regression_introduced", "regression_introduced", failure_reason or failure_detail)
        return _taxonomy("test_fail", "test_failed", failure_reason or failure_detail)

    if normalized_stage == "security_rescan":
        return _taxonomy("security_rescan_fail", "security_rescan_failed", failure_reason or failure_detail)

    if normalized_reason in {"wrong_tool_selection", "tool_mismatch", "tool_selection_error"}:
        return _taxonomy("tool_selection_error", normalized_reason, failure_detail)

    if normalized_reason in {
        "insufficient_context_for_semantic_fix",
        "insufficient_context",
        "action_loop_exhausted",
        "context_budget_exhausted",
    }:
        return _taxonomy("context_insufficient", normalized_reason, failure_detail)

    if normalized_reason in {
        "invalid_diff",
        "llm_call_failed",
        "llm_output_invalid",
    }:
        return _taxonomy("llm_output_invalid", normalized_reason, failure_detail)

    if normalized_reason in {
        "duplicate_patch_candidate",
        "no_repair_candidate",
        "syntax_repair_failed",
        "semantic_repair_unsupported",
        "no_semantic_candidate",
        "unsafe_default_return",
        "no_valid_patch",
    }:
        return _taxonomy("wrong_patch", normalized_reason, failure_detail)

    if issue_count == 0 and final_outcome.startswith("failed"):
        return _taxonomy("detection_miss", "no_issues_detected", failure_reason or failure_detail)

    return _taxonomy("context_insufficient", normalized_reason or None, failure_detail)


def _taxonomy(bucket: str, code: str | None, explanation: str | None) -> dict[str, Any]:
    canonical = bucket if bucket in CANONICAL_BUCKETS else "context_insufficient"
    return {
        "bucket": canonical,
        "legacy_bucket": canonical_to_legacy(canonical),
        "code": code,
        "explanation": explanation,
    }
