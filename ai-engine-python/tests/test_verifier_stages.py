from __future__ import annotations

from tools.lint_runner import run_lint_stage
from tools.security_rescan import run_security_rescan_stage
from tools.test_runner import run_test_stage


def test_lint_stage_skipped_without_command() -> None:
    stage = run_lint_stage(options={}, repo_profile={}, working_directory=None)
    assert stage["stage"] == "lint"
    assert stage["status"] == "skipped"


def test_test_stage_skipped_without_command() -> None:
    stage = run_test_stage(options={}, repo_profile={}, working_directory=None)
    assert stage["stage"] == "test"
    assert stage["status"] == "skipped"


def test_security_stage_skipped_when_disabled() -> None:
    stage = run_security_rescan_stage(options={"enable_security_rescan": False}, working_directory=None)
    assert stage["stage"] == "security_rescan"
    assert stage["status"] == "skipped"
