from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any


def run_security_rescan_stage(
    *,
    options: dict[str, Any] | None = None,
    working_directory: str | None = None,
    timeout_seconds: int = 45,
) -> dict[str, Any]:
    options = options or {}
    if not bool(options.get("enable_security_rescan", False)):
        return _skipped("security rescan disabled")

    command = str(options.get("security_rescan_command") or options.get("semgrep_command") or "").strip()
    if not command:
        return _skipped("security rescan command not configured")
    if not working_directory:
        return _skipped("security rescan workspace not configured")

    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(Path(working_directory)),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return {
            "stage": "security_rescan",
            "status": "failed",
            "exit_code": 127,
            "stdout_summary": "",
            "stderr_summary": f"command not found: {command}",
            "reason": "command_not_found",
            "retryable": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stage": "security_rescan",
            "status": "failed",
            "exit_code": 124,
            "stdout_summary": "",
            "stderr_summary": "security rescan timeout",
            "reason": "security_rescan_timeout",
            "retryable": True,
        }
    except Exception as exc:
        return {
            "stage": "security_rescan",
            "status": "failed",
            "exit_code": 1,
            "stdout_summary": "",
            "stderr_summary": _compact(str(exc)),
            "reason": "security_rescan_exec_error",
            "retryable": True,
        }

    if completed.returncode == 0:
        return {
            "stage": "security_rescan",
            "status": "passed",
            "exit_code": 0,
            "stdout_summary": _compact(completed.stdout),
            "stderr_summary": _compact(completed.stderr),
            "reason": None,
            "retryable": False,
        }

    return {
        "stage": "security_rescan",
        "status": "failed",
        "exit_code": int(completed.returncode),
        "stdout_summary": _compact(completed.stdout),
        "stderr_summary": _compact(completed.stderr) or "security rescan failed",
        "reason": "security_rescan_failed",
        "retryable": True,
    }


def _skipped(reason: str) -> dict[str, Any]:
    return {
        "stage": "security_rescan",
        "status": "skipped",
        "exit_code": None,
        "stdout_summary": "",
        "stderr_summary": "",
        "reason": reason,
        "retryable": False,
    }


def _compact(text: str, *, max_lines: int = 8, max_chars: int = 480) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = " | ".join(lines[:max_lines])
    if len(compact) > max_chars:
        return compact[: max_chars - 3] + "..."
    return compact
