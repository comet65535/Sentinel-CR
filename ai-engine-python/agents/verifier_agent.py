from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core.failure_taxonomy import classify_compile_failure_bucket
from tools import apply_patch_to_snippet


def run_verifier_agent(
    *,
    code_text: str,
    patch_artifact: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
    repo_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    repo_profile = repo_profile or {}
    if patch_artifact is None:
        stage = _failed_stage(
            stage="patch_apply",
            reason="patch_missing",
            stderr="patch artifact absent",
            exit_code=1,
            retryable=False,
        )
        return _build_result(stages=[stage])

    target_files = patch_artifact.get("target_files") or ["snippet.java"]
    target_file = str(target_files[0]) if target_files else "snippet.java"
    patch_content = str(patch_artifact.get("content") or patch_artifact.get("unified_diff") or "")

    stages: list[dict[str, Any]] = []
    patch_stage = apply_patch_to_snippet(
        original_code=code_text,
        patch_content=patch_content,
        target_file=target_file,
    )
    stages.append(_normalize_stage(patch_stage, default_code="patch_apply_failed", retry_hint="fix diff header/hunk context"))
    if stages[-1]["status"] == "failed":
        return _build_result(stages=stages)

    patched_code = str(patch_stage.get("patched_code") or code_text)

    with tempfile.TemporaryDirectory(prefix="sentinel-verify-") as temp_dir:
        workdir = Path(temp_dir)
        source_file = workdir / target_file
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text(patched_code, encoding="utf-8")

        compile_cmd = str(options.get("compile_command") or f"javac {target_file}").strip()
        compile_stage = _run_command_stage(
            stage="compile",
            command=compile_cmd,
            workdir=workdir,
            timeout_seconds=int(options.get("compile_timeout_seconds") or 30),
            default_failure_code="compile_failed",
            default_retry_hint="fix compile errors and missing symbols/imports",
        )
        if compile_stage["status"] == "failed":
            bucket = classify_compile_failure_bucket(compile_stage.get("stderr_summary"), compile_stage.get("failure_code"))
            if bucket:
                compile_stage["compile_failure_bucket"] = bucket
                compile_stage["failure_code"] = f"compile_{bucket}"
        stages.append(compile_stage)
        if compile_stage["status"] == "failed":
            return _build_result(stages=stages)

        lint_cmd = str(
            options.get("lint_command")
            or repo_profile.get("preferred_lint_command")
            or f"javac -Xlint {target_file}"
        ).strip()
        lint_stage = _run_command_stage(
            stage="lint",
            command=lint_cmd,
            workdir=workdir,
            timeout_seconds=int(options.get("lint_timeout_seconds") or 30),
            default_failure_code="lint_failed",
            default_retry_hint="resolve lint warnings/errors introduced by patch",
        )
        stages.append(lint_stage)
        if lint_stage["status"] == "failed":
            return _build_result(stages=stages)

        test_cmd = str(options.get("test_command") or repo_profile.get("preferred_test_command") or "").strip()
        if not test_cmd:
            stages.append(_skipped_stage("test", "test command not configured"))
        else:
            test_stage = _run_command_stage(
                stage="test",
                command=test_cmd,
                workdir=workdir,
                timeout_seconds=int(options.get("test_timeout_seconds") or 60),
                default_failure_code="test_failed",
                default_retry_hint="fix behavioral regressions and failing assertions",
            )
            stages.append(test_stage)
            if test_stage["status"] == "failed":
                return _build_result(stages=stages)

        security_enabled = bool(options.get("enable_security_rescan", False))
        security_cmd = str(options.get("security_rescan_command") or options.get("semgrep_command") or "").strip()
        if not security_enabled:
            stages.append(_skipped_stage("security_rescan", "security rescan disabled"))
        elif not security_cmd:
            stages.append(_skipped_stage("security_rescan", "security rescan command not configured"))
        else:
            security_stage = _run_command_stage(
                stage="security_rescan",
                command=security_cmd,
                workdir=workdir,
                timeout_seconds=int(options.get("security_timeout_seconds") or 45),
                default_failure_code="security_rescan_failed",
                default_retry_hint="remove newly introduced security findings",
            )
            stages.append(security_stage)
            if security_stage["status"] == "failed":
                return _build_result(stages=stages)

    return _build_result(stages=stages)


def _run_command_stage(
    *,
    stage: str,
    command: str,
    workdir: Path,
    timeout_seconds: int,
    default_failure_code: str,
    default_retry_hint: str,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return _failed_stage(
            stage=stage,
            reason="command_not_found",
            stderr=f"command not found: {command}",
            failure_code="command_not_found",
            retry_hint=f"install tool and re-run {stage}",
            exit_code=127,
            retryable=False,
        )
    except subprocess.TimeoutExpired:
        return _failed_stage(
            stage=stage,
            reason=f"{stage}_timeout",
            stderr=f"{stage} timeout",
            failure_code=f"{stage}_timeout",
            retry_hint=default_retry_hint,
            exit_code=124,
            retryable=True,
        )
    except Exception as exc:
        return _failed_stage(
            stage=stage,
            reason=f"{stage}_exec_error",
            stderr=_compact(str(exc)),
            failure_code=f"{stage}_exec_error",
            retry_hint=default_retry_hint,
            exit_code=1,
            retryable=True,
        )

    if completed.returncode == 0:
        return {
            "stage": stage,
            "status": "passed",
            "exit_code": 0,
            "stdout_summary": _compact(completed.stdout),
            "stderr_summary": _compact(completed.stderr),
            "reason": None,
            "retryable": False,
            "failure_code": None,
            "stderr_excerpt": "",
            "retry_hint": None,
        }

    stderr = _compact(completed.stderr) or f"{stage} failed"
    return _failed_stage(
        stage=stage,
        reason=default_failure_code,
        stderr=stderr,
        failure_code=default_failure_code,
        retry_hint=default_retry_hint,
        exit_code=int(completed.returncode),
        retryable=True,
        stdout_summary=_compact(completed.stdout),
    )


def _failed_stage(
    stage: str,
    reason: str,
    stderr: str,
    *,
    failure_code: str | None = None,
    retry_hint: str | None = None,
    exit_code: int | None = 1,
    retryable: bool = True,
    stdout_summary: str = "",
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "failed",
        "exit_code": exit_code,
        "stdout_summary": stdout_summary,
        "stderr_summary": stderr,
        "reason": reason,
        "retryable": retryable,
        "failure_code": failure_code or reason,
        "stderr_excerpt": _excerpt(stderr),
        "retry_hint": retry_hint or "review verifier stderr and retry with targeted fix",
    }


def _normalize_stage(stage: dict[str, Any], *, default_code: str, retry_hint: str) -> dict[str, Any]:
    status = str(stage.get("status") or "failed")
    stderr = str(stage.get("stderr_summary") or "")
    reason = str(stage.get("reason") or "") or (default_code if status == "failed" else "")
    return {
        "stage": str(stage.get("stage") or "unknown"),
        "status": status,
        "exit_code": stage.get("exit_code"),
        "stdout_summary": str(stage.get("stdout_summary") or ""),
        "stderr_summary": stderr,
        "reason": reason or None,
        "retryable": bool(stage.get("retryable", False)),
        "failure_code": default_code if status == "failed" else None,
        "stderr_excerpt": _excerpt(stderr),
        "retry_hint": retry_hint if status == "failed" else None,
    }


def _skipped_stage(stage: str, reason: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "skipped",
        "exit_code": None,
        "stdout_summary": "",
        "stderr_summary": "",
        "reason": reason,
        "retryable": False,
        "failure_code": None,
        "stderr_excerpt": "",
        "retry_hint": None,
    }


def _build_result(*, stages: list[dict[str, Any]]) -> dict[str, Any]:
    failed_stage_payload = next((stage for stage in stages if stage.get("status") == "failed"), None)
    failed_stage = failed_stage_payload.get("stage") if isinstance(failed_stage_payload, dict) else None
    status = "failed" if failed_stage else "passed"
    passed_stages = [str(stage.get("stage")) for stage in stages if stage.get("status") == "passed"]

    result = {
        "status": status,
        "verified_level": _resolve_verified_level(stages),
        "passed_stages": passed_stages,
        "failed_stage": failed_stage,
        "stages": stages,
        "summary": f"verification {status} at {failed_stage or 'L4'}",
        "retryable": bool(failed_stage_payload.get("retryable", False)) if failed_stage_payload else False,
        "failure_reason": str(failed_stage_payload.get("reason") or "") if failed_stage_payload else None,
        "failure_code": str(failed_stage_payload.get("failure_code") or "") if failed_stage_payload else None,
        "stderr_excerpt": str(failed_stage_payload.get("stderr_excerpt") or "") if failed_stage_payload else "",
        "retry_hint": str(failed_stage_payload.get("retry_hint") or "") if failed_stage_payload else None,
    }
    if isinstance(failed_stage_payload, dict) and failed_stage_payload.get("compile_failure_bucket"):
        result["compile_failure_bucket"] = failed_stage_payload.get("compile_failure_bucket")
    return result


def _resolve_verified_level(stages: list[dict[str, Any]]) -> str:
    status_by_stage = {str(stage.get("stage")): str(stage.get("status")) for stage in stages}
    if status_by_stage.get("patch_apply") != "passed":
        return "L0"
    if status_by_stage.get("compile") != "passed":
        return "L0"
    if status_by_stage.get("lint") == "passed":
        if status_by_stage.get("test") == "passed":
            if status_by_stage.get("security_rescan") == "passed":
                return "L4"
            return "L3"
        return "L2"
    return "L1"


def _compact(text: str, *, max_lines: int = 8, max_chars: int = 600) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = " | ".join(lines[:max_lines])
    if len(compact) > max_chars:
        return compact[: max_chars - 3] + "..."
    return compact


def _excerpt(text: str, *, max_chars: int = 220) -> str:
    compact = _compact(text, max_lines=4, max_chars=max_chars)
    return compact
