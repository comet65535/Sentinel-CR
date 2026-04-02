from __future__ import annotations

from typing import Any


def run_lint_stage(*, reason: str = "lint command not configured") -> dict[str, Any]:
    return _skipped_stage(stage="lint", reason=reason)


def run_test_stage(*, reason: str = "test command not configured") -> dict[str, Any]:
    return _skipped_stage(stage="test", reason=reason)


def run_security_rescan_stage(*, reason: str = "security rescan disabled") -> dict[str, Any]:
    return _skipped_stage(stage="security_rescan", reason=reason)


def _skipped_stage(*, stage: str, reason: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "skipped",
        "exit_code": None,
        "stdout_summary": "",
        "stderr_summary": "",
        "reason": reason,
        "retryable": False,
    }
