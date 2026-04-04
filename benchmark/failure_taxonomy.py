from __future__ import annotations

from dataclasses import dataclass
from typing import Any


KNOWN_BUCKETS = {
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

CANONICAL_TO_LEGACY = {
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


@dataclass
class FailureTaxonomy:
    bucket: str
    code: str | None = None
    explanation: str | None = None
    legacy_bucket: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "legacy_bucket": self.legacy_bucket,
            "code": self.code,
            "explanation": self.explanation,
        }


def normalize_failure_taxonomy(value: Any) -> FailureTaxonomy:
    if isinstance(value, dict):
        raw_bucket = str(value.get("bucket") or value.get("legacy_bucket") or "none")
        code = value.get("code")
        explanation = value.get("explanation")
        if raw_bucket not in KNOWN_BUCKETS:
            raw_bucket = "none"
        if raw_bucket in CANONICAL_TO_LEGACY:
            bucket = raw_bucket
            legacy_bucket = str(value.get("legacy_bucket") or CANONICAL_TO_LEGACY[raw_bucket])
        else:
            bucket = raw_bucket
            legacy_bucket = str(value.get("legacy_bucket") or raw_bucket)
        return FailureTaxonomy(
            bucket=bucket,
            legacy_bucket=legacy_bucket,
            code=str(code) if code is not None else None,
            explanation=str(explanation) if explanation is not None else None,
        )
    if isinstance(value, str) and value in KNOWN_BUCKETS:
        if value in CANONICAL_TO_LEGACY:
            return FailureTaxonomy(bucket=value, legacy_bucket=CANONICAL_TO_LEGACY[value])
        return FailureTaxonomy(bucket=value, legacy_bucket=value)
    return FailureTaxonomy(bucket="none", legacy_bucket="none")
