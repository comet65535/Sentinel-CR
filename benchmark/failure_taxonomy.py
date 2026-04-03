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
}


@dataclass
class FailureTaxonomy:
    bucket: str
    code: str | None = None
    explanation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "code": self.code,
            "explanation": self.explanation,
        }


def normalize_failure_taxonomy(value: Any) -> FailureTaxonomy:
    if isinstance(value, dict):
        bucket = str(value.get("bucket") or "none")
        code = value.get("code")
        explanation = value.get("explanation")
        if bucket not in KNOWN_BUCKETS:
            bucket = "none"
        return FailureTaxonomy(
            bucket=bucket,
            code=str(code) if code is not None else None,
            explanation=str(explanation) if explanation is not None else None,
        )
    if isinstance(value, str) and value in KNOWN_BUCKETS:
        return FailureTaxonomy(bucket=value)
    return FailureTaxonomy(bucket="none")
