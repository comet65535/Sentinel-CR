from __future__ import annotations

import copy
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.failure_taxonomy import classify_compile_failure_bucket
from tools import apply_patch_to_snippet

STAGE_ORDER = ["patch_apply", "compile", "lint", "test", "security_rescan"]


def run_verifier_agent(
    *,
    code_text: str,
    patch_artifact: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
    repo_profile: dict[str, Any] | None = None,
    stage_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    options = options or {}
    repo_profile = repo_profile or {}
    stages: dict[str, dict[str, Any]] = {stage: _pending_stage(stage) for stage in STAGE_ORDER}

    if patch_artifact is None:
        _mark_running(stages["patch_apply"], stage_callback)
        _mark_terminal(
            stages["patch_apply"],
            status="failed",
            summary="Patch artifact missing; cannot verify.",
            details="patch artifact absent",
            failure_code="patch_missing",
            retryable=False,
            retry_hint="Regenerate unified diff patch before verifier.",
            stderr_summary="patch artifact absent",
        )
        _emit(stage_callback, stages["patch_apply"])
        _block_remaining(
            stages=stages,
            after_stage="patch_apply",
            reason="blocked_by_patch_apply_failure",
            summary_prefix="Blocked because patch_apply failed",
            stage_callback=stage_callback,
        )
        return _build_result(stages=_ordered_stages(stages))

    target_files = patch_artifact.get("target_files") or ["snippet.java"]
    target_file = str(target_files[0]) if target_files else "snippet.java"
    patch_content = str(patch_artifact.get("content") or patch_artifact.get("unified_diff") or "")

    _mark_running(stages["patch_apply"], stage_callback)
    patch_stage = apply_patch_to_snippet(
        original_code=code_text,
        patch_content=patch_content,
        target_file=target_file,
    )
    normalized_patch = _normalize_patch_apply_stage(patch_stage)
    _mark_terminal(
        stages["patch_apply"],
        status=normalized_patch["status"],
        summary=normalized_patch["summary"],
        details=normalized_patch.get("details"),
        failure_code=normalized_patch.get("failure_code"),
        retryable=bool(normalized_patch.get("retryable", False)),
        retry_hint=normalized_patch.get("retry_hint"),
        stderr_summary=normalized_patch.get("stderr_summary", ""),
        stdout_summary=normalized_patch.get("stdout_summary", ""),
        exit_code=normalized_patch.get("exit_code"),
        skip_reason=normalized_patch.get("skip_reason"),
    )
    _emit(stage_callback, stages["patch_apply"])

    if stages["patch_apply"]["status"] != "passed":
        _block_remaining(
            stages=stages,
            after_stage="patch_apply",
            reason="blocked_by_patch_apply_failure",
            summary_prefix="Blocked because patch_apply failed",
            stage_callback=stage_callback,
        )
        return _build_result(stages=_ordered_stages(stages))

    patched_code = str(patch_stage.get("patched_code") or code_text)

    with tempfile.TemporaryDirectory(prefix="sentinel-verify-") as temp_dir:
        workdir = Path(temp_dir)
        source_file = workdir / target_file
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text(patched_code, encoding="utf-8")

        compile_cmd = str(options.get("compile_command") or f"javac {target_file}").strip()
        _mark_running(stages["compile"], stage_callback)
        compile_result = _run_command_stage(
            stage="compile",
            command=compile_cmd,
            workdir=workdir,
            timeout_seconds=int(options.get("compile_timeout_seconds") or 30),
            default_failure_code="compile_failed",
            default_retry_hint="Fix compile errors and missing symbols/imports.",
            success_summary="javac compile passed.",
        )
        if compile_result["status"] == "failed":
            bucket = classify_compile_failure_bucket(
                compile_result.get("stderr_summary"),
                compile_result.get("failure_code"),
            )
            if bucket:
                compile_result["compile_failure_bucket"] = bucket
                compile_result["failure_code"] = f"compile_{bucket}"
        _mark_terminal(
            stages["compile"],
            **compile_result,
        )
        if compile_result.get("compile_failure_bucket"):
            stages["compile"]["compile_failure_bucket"] = compile_result.get("compile_failure_bucket")
        _emit(stage_callback, stages["compile"])
        if stages["compile"]["status"] != "passed":
            _block_remaining(
                stages=stages,
                after_stage="compile",
                reason="blocked_by_compile_failure",
                summary_prefix="Blocked because compile failed",
                stage_callback=stage_callback,
            )
            return _build_result(stages=_ordered_stages(stages))

        lint_cmd = str(options.get("lint_command") or "").strip()
        _mark_running(stages["lint"], stage_callback)
        if not lint_cmd:
            _mark_terminal(
                stages["lint"],
                status="skipped",
                summary="No lint command configured for this snippet.",
                skip_reason="missing_lint_runner",
                details="Configure options.lint_command or repo profile preferred_lint_command.",
            )
        else:
            lint_result = _run_command_stage(
                stage="lint",
                command=lint_cmd,
                workdir=workdir,
                timeout_seconds=int(options.get("lint_timeout_seconds") or 30),
                default_failure_code="lint_failed",
                default_retry_hint="Resolve lint warnings/errors introduced by patch.",
                success_summary="Lint command passed.",
            )
            _mark_terminal(stages["lint"], **lint_result)
        _emit(stage_callback, stages["lint"])
        if stages["lint"]["status"] == "failed":
            _block_remaining(
                stages=stages,
                after_stage="lint",
                reason="blocked_by_lint_failure",
                summary_prefix="Blocked because lint failed",
                stage_callback=stage_callback,
            )
            return _build_result(stages=_ordered_stages(stages))

        test_cmd = str(options.get("test_command") or "").strip()
        _mark_running(stages["test"], stage_callback)
        if not test_cmd:
            _mark_terminal(
                stages["test"],
                status="blocked",
                summary="No executable regression test target found.",
                skip_reason="missing_test_target",
                details="Configure options.test_command or repo profile preferred_test_command.",
            )
        else:
            test_result = _run_command_stage(
                stage="test",
                command=test_cmd,
                workdir=workdir,
                timeout_seconds=int(options.get("test_timeout_seconds") or 60),
                default_failure_code="test_failed",
                default_retry_hint="Fix regression behavior and failing assertions.",
                success_summary="Regression tests passed.",
            )
            _mark_terminal(stages["test"], **test_result)
        _emit(stage_callback, stages["test"])
        if stages["test"]["status"] == "failed":
            _block_remaining(
                stages=stages,
                after_stage="test",
                reason="blocked_by_test_failure",
                summary_prefix="Blocked because test failed",
                stage_callback=stage_callback,
            )
            return _build_result(stages=_ordered_stages(stages))

        security_enabled = bool(options.get("enable_security_rescan", False))
        security_cmd = str(options.get("security_rescan_command") or options.get("semgrep_command") or "").strip()
        _mark_running(stages["security_rescan"], stage_callback)
        if not security_enabled:
            _mark_terminal(
                stages["security_rescan"],
                status="skipped",
                summary="Security rescan disabled by options.",
                skip_reason="security_rescan_disabled",
            )
        elif not security_cmd:
            _mark_terminal(
                stages["security_rescan"],
                status="skipped",
                summary="Security rescan command not configured.",
                skip_reason="missing_security_runner",
                details="Configure options.security_rescan_command or semgrep_command.",
            )
        else:
            security_result = _run_command_stage(
                stage="security_rescan",
                command=security_cmd,
                workdir=workdir,
                timeout_seconds=int(options.get("security_timeout_seconds") or 45),
                default_failure_code="security_rescan_failed",
                default_retry_hint="Remove newly introduced security findings.",
                success_summary="Security rescan passed.",
            )
            _mark_terminal(stages["security_rescan"], **security_result)
        _emit(stage_callback, stages["security_rescan"])

    return _build_result(stages=_ordered_stages(stages))


def _pending_stage(stage: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "duration_ms": None,
        "summary": "Pending execution.",
        "details": None,
        "skip_reason": None,
        "exit_code": None,
        "stdout_summary": "",
        "stderr_summary": "",
        "stderr_excerpt": "",
        "failure_code": None,
        "retryable": False,
        "retry_hint": None,
    }


def _mark_running(stage_payload: dict[str, Any], stage_callback: Callable[[dict[str, Any]], None] | None) -> None:
    stage_payload["status"] = "running"
    stage_payload["summary"] = f"{stage_payload['stage']} running..."
    stage_payload["started_at"] = stage_payload.get("started_at") or _now_iso()
    _emit(stage_callback, stage_payload)


def _mark_terminal(
    stage_payload: dict[str, Any],
    *,
    status: str,
    summary: str,
    details: str | None = None,
    skip_reason: str | None = None,
    failure_code: str | None = None,
    retryable: bool = False,
    retry_hint: str | None = None,
    stderr_summary: str = "",
    stdout_summary: str = "",
    exit_code: int | None = None,
) -> None:
    if stage_payload.get("started_at") is None:
        stage_payload["started_at"] = _now_iso()
    stage_payload["status"] = status
    stage_payload["summary"] = summary
    stage_payload["details"] = details
    stage_payload["skip_reason"] = skip_reason
    stage_payload["failure_code"] = failure_code
    stage_payload["retryable"] = bool(retryable)
    stage_payload["retry_hint"] = retry_hint
    stage_payload["stderr_summary"] = stderr_summary
    stage_payload["stdout_summary"] = stdout_summary
    stage_payload["stderr_excerpt"] = _excerpt(stderr_summary)
    stage_payload["exit_code"] = exit_code
    stage_payload["finished_at"] = _now_iso()
    stage_payload["duration_ms"] = _duration_ms(stage_payload.get("started_at"), stage_payload.get("finished_at"))


def _run_command_stage(
    *,
    stage: str,
    command: str,
    workdir: Path,
    timeout_seconds: int,
    default_failure_code: str,
    default_retry_hint: str,
    success_summary: str,
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
        return {
            "status": "failed",
            "summary": f"{stage} command not found.",
            "details": f"command not found: {command}",
            "failure_code": "command_not_found",
            "retryable": False,
            "retry_hint": f"Install required tool then rerun {stage}.",
            "stderr_summary": f"command not found: {command}",
            "stdout_summary": "",
            "exit_code": 127,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "failed",
            "summary": f"{stage} timed out.",
            "details": f"{stage} timeout after {timeout_seconds}s",
            "failure_code": f"{stage}_timeout",
            "retryable": True,
            "retry_hint": default_retry_hint,
            "stderr_summary": f"{stage} timeout",
            "stdout_summary": "",
            "exit_code": 124,
        }
    except Exception as exc:
        text = _compact(str(exc))
        return {
            "status": "failed",
            "summary": f"{stage} execution error.",
            "details": text,
            "failure_code": f"{stage}_exec_error",
            "retryable": True,
            "retry_hint": default_retry_hint,
            "stderr_summary": text,
            "stdout_summary": "",
            "exit_code": 1,
        }

    stdout = _compact(completed.stdout)
    stderr = _compact(completed.stderr)
    if completed.returncode == 0:
        return {
            "status": "passed",
            "summary": success_summary,
            "details": None,
            "failure_code": None,
            "retryable": False,
            "retry_hint": None,
            "stderr_summary": stderr,
            "stdout_summary": stdout,
            "exit_code": 0,
        }

    return {
        "status": "failed",
        "summary": f"{stage} failed.",
        "details": stderr or f"{stage} failed",
        "failure_code": default_failure_code,
        "retryable": True,
        "retry_hint": default_retry_hint,
        "stderr_summary": stderr or f"{stage} failed",
        "stdout_summary": stdout,
        "exit_code": int(completed.returncode),
    }


def _normalize_patch_apply_stage(stage: dict[str, Any]) -> dict[str, Any]:
    status = str(stage.get("status") or "failed")
    stderr = str(stage.get("stderr_summary") or "")
    if status == "passed":
        return {
            "status": "passed",
            "summary": "Patch applied cleanly.",
            "details": None,
            "failure_code": None,
            "retryable": False,
            "retry_hint": None,
            "stderr_summary": stderr,
            "stdout_summary": str(stage.get("stdout_summary") or ""),
            "exit_code": int(stage.get("exit_code") or 0),
            "skip_reason": None,
        }
    return {
        "status": "failed",
        "summary": "Patch could not be applied.",
        "details": stderr or str(stage.get("reason") or "patch apply failed"),
        "failure_code": "patch_apply_failed",
        "retryable": bool(stage.get("retryable", True)),
        "retry_hint": "Fix unified diff header/hunk context and regenerate patch.",
        "stderr_summary": stderr,
        "stdout_summary": str(stage.get("stdout_summary") or ""),
        "exit_code": int(stage.get("exit_code") or 1),
        "skip_reason": None,
    }


def _block_remaining(
    *,
    stages: dict[str, dict[str, Any]],
    after_stage: str,
    reason: str,
    summary_prefix: str,
    stage_callback: Callable[[dict[str, Any]], None] | None,
) -> None:
    active = False
    for stage in STAGE_ORDER:
        if stage == after_stage:
            active = True
            continue
        if not active:
            continue
        target = stages[stage]
        _mark_terminal(
            target,
            status="blocked",
            summary=f"{summary_prefix}: {stage} not executed.",
            details=f"{stage} blocked due to upstream failure.",
            skip_reason=reason,
            retryable=False,
        )
        _emit(stage_callback, target)


def _build_result(*, stages: list[dict[str, Any]]) -> dict[str, Any]:
    failed_stage_payload = next((stage for stage in stages if stage.get("status") == "failed"), None)
    failed_stage = failed_stage_payload.get("stage") if isinstance(failed_stage_payload, dict) else None
    passed_stages = [str(stage.get("stage")) for stage in stages if stage.get("status") == "passed"]

    if failed_stage_payload:
        overall_status = "failed"
    elif any(stage.get("status") in {"skipped", "blocked"} for stage in stages):
        overall_status = "partial_pass"
    else:
        overall_status = "full_pass"

    status = "failed" if failed_stage_payload else "passed"
    regression_risk = _resolve_regression_risk(stages)

    result = {
        "status": status,
        "overall_status": overall_status,
        "verified_level": _resolve_verified_level(stages),
        "passed_stages": passed_stages,
        "failed_stage": failed_stage,
        "stages": stages,
        "summary": _build_summary(overall_status, failed_stage),
        "retryable": bool(failed_stage_payload.get("retryable", False)) if failed_stage_payload else False,
        "failure_reason": str(failed_stage_payload.get("summary") or "") if failed_stage_payload else None,
        "failure_code": str(failed_stage_payload.get("failure_code") or "") if failed_stage_payload else None,
        "stderr_excerpt": str(failed_stage_payload.get("stderr_excerpt") or "") if failed_stage_payload else "",
        "retry_hint": str(failed_stage_payload.get("retry_hint") or "") if failed_stage_payload else None,
        "regression_risk": regression_risk,
    }
    if isinstance(failed_stage_payload, dict) and failed_stage_payload.get("compile_failure_bucket"):
        result["compile_failure_bucket"] = failed_stage_payload.get("compile_failure_bucket")
    return result


def _resolve_verified_level(stages: list[dict[str, Any]]) -> str:
    status_by_stage = {str(stage.get("stage")): str(stage.get("status")) for stage in stages}
    if status_by_stage.get("patch_apply") != "passed" or status_by_stage.get("compile") != "passed":
        return "L0"
    if status_by_stage.get("lint") != "passed":
        return "L1"
    if status_by_stage.get("test") != "passed":
        return "L2"
    if status_by_stage.get("security_rescan") != "passed":
        return "L3"
    return "L4"


def _resolve_regression_risk(stages: list[dict[str, Any]]) -> str:
    status_by_stage = {str(stage.get("stage")): str(stage.get("status")) for stage in stages}
    if status_by_stage.get("patch_apply") == "failed" or status_by_stage.get("compile") == "failed":
        return "unknown"
    test_status = status_by_stage.get("test")
    security_status = status_by_stage.get("security_rescan")
    if test_status in {"blocked", "skipped", "pending", "running"}:
        return "untested"
    if test_status == "failed":
        return "high"
    if test_status == "passed" and security_status == "passed":
        return "low"
    if test_status == "passed":
        return "medium"
    return "unknown"


def _build_summary(overall_status: str, failed_stage: str | None) -> str:
    if overall_status == "full_pass":
        return "All configured verifier stages passed."
    if overall_status == "partial_pass":
        return "Verifier completed with skipped/blocked stages."
    return f"Verification failed at {failed_stage or 'unknown'} stage."


def _ordered_stages(stages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [stages[key] for key in STAGE_ORDER]


def _compact(text: str, *, max_lines: int = 8, max_chars: int = 600) -> str:
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = " | ".join(lines[:max_lines])
    if len(compact) > max_chars:
        return compact[: max_chars - 3] + "..."
    return compact


def _excerpt(text: str, *, max_chars: int = 220) -> str:
    return _compact(text, max_lines=4, max_chars=max_chars)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(finished_at)
        return max(0, int((end - start).total_seconds() * 1000))
    except Exception:
        return None


def _emit(stage_callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if stage_callback is None:
        return
    stage_callback(copy.deepcopy(payload))
