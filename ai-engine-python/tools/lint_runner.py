from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any


def run_lint_stage(
    *,
    options: dict[str, Any] | None = None,
    repo_profile: dict[str, Any] | None = None,
    working_directory: str | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    options = options or {}
    repo_profile = repo_profile or {}
    command = (
        str(options.get("lint_command") or "").strip()
        or str(repo_profile.get("preferred_lint_command") or "").strip()
    )
    if not command:
        return _skipped("lint command not configured")
    if not working_directory:
        return _skipped("lint workspace not configured")

    return _run_command_stage(
        stage="lint",
        command=command,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
    )


def _run_command_stage(
    *,
    stage: str,
    command: str,
    working_directory: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    try:
        parsed = shlex.split(command)
        completed = subprocess.run(
            parsed,
            cwd=str(Path(working_directory)),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 127,
            "stdout_summary": "",
            "stderr_summary": f"command not found: {command}",
            "reason": "command_not_found",
            "retryable": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 124,
            "stdout_summary": "",
            "stderr_summary": f"{stage} timeout",
            "reason": f"{stage}_timeout",
            "retryable": True,
        }
    except Exception as exc:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 1,
            "stdout_summary": "",
            "stderr_summary": _compact(str(exc)),
            "reason": f"{stage}_exec_error",
            "retryable": True,
        }

    if completed.returncode == 0:
        return {
            "stage": stage,
            "status": "passed",
            "exit_code": 0,
            "stdout_summary": _compact(completed.stdout),
            "stderr_summary": _compact(completed.stderr),
            "reason": None,
            "retryable": False,
        }

    return {
        "stage": stage,
        "status": "failed",
        "exit_code": int(completed.returncode),
        "stdout_summary": _compact(completed.stdout),
        "stderr_summary": _compact(completed.stderr) or f"{stage} failed",
        "reason": f"{stage}_failed",
        "retryable": True,
    }


def _compact(text: str, *, max_lines: int = 8, max_chars: int = 480) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = " | ".join(lines[:max_lines])
    if len(compact) > max_chars:
        return compact[: max_chars - 3] + "..."
    return compact


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "stage": "lint",
        "status": "skipped",
        "exit_code": None,
        "stdout_summary": "",
        "stderr_summary": "",
        "reason": reason,
        "retryable": False,
    }
