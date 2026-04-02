from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any


def compile_java_snippet(
    *,
    code_text: str,
    file_name: str = "snippet.java",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    stage = "compile"
    try:
        with tempfile.TemporaryDirectory(prefix="sentinel-compile-") as temp_dir:
            workdir = Path(temp_dir)
            source_file = workdir / file_name
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text(code_text, encoding="utf-8")

            completed = subprocess.run(
                ["javac", file_name],
                cwd=str(workdir),
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
            "stderr_summary": "javac not found",
            "reason": "javac_unavailable",
            "retryable": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 124,
            "stdout_summary": "",
            "stderr_summary": "javac timeout",
            "reason": "compile_timeout",
            "retryable": True,
        }
    except Exception as exc:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 1,
            "stdout_summary": "",
            "stderr_summary": _compact(str(exc)),
            "reason": "compile_exec_error",
            "retryable": True,
        }

    if completed.returncode == 0:
        return {
            "stage": stage,
            "status": "passed",
            "exit_code": 0,
            "stdout_summary": _compact(completed.stdout) or "javac succeeded",
            "stderr_summary": _compact(completed.stderr),
            "reason": None,
            "retryable": False,
        }

    stderr_summary = _compact(completed.stderr) or "javac failed"
    return {
        "stage": stage,
        "status": "failed",
        "exit_code": int(completed.returncode),
        "stdout_summary": _compact(completed.stdout),
        "stderr_summary": stderr_summary,
        "reason": "compile_failed",
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
