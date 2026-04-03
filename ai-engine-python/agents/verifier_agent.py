from __future__ import annotations

from typing import Any

from tools import apply_patch_to_snippet, compile_java_snippet, run_lint_stage, run_security_rescan_stage, run_test_stage


def run_verifier_agent(
    *,
    code_text: str,
    patch_artifact: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
    repo_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    repo_profile = repo_profile or {}
    stages: list[dict[str, Any]] = []
    if patch_artifact is None:
        verification = _build_verification_result(
            status="failed",
            stages=[
                {
                    "stage": "patch_apply",
                    "status": "failed",
                    "exit_code": 1,
                    "stdout_summary": "",
                    "stderr_summary": "patch artifact absent",
                    "reason": "patch_missing",
                    "retryable": False,
                }
            ],
        )
        verification["retryable"] = False
        verification["failure_reason"] = "patch_missing"
        return verification

    target_files = patch_artifact.get("target_files") or ["snippet.java"]
    target_file = str(target_files[0]) if target_files else "snippet.java"

    patch_stage = apply_patch_to_snippet(
        original_code=code_text,
        patch_content=str(patch_artifact.get("content") or ""),
        target_file=target_file,
    )
    stages.append(_sanitize_stage_for_result(patch_stage))
    if patch_stage["status"] != "passed":
        verification = _build_verification_result(status="failed", stages=stages)
        verification["retryable"] = bool(patch_stage.get("retryable", True))
        verification["failure_reason"] = patch_stage.get("reason") or patch_stage.get("stderr_summary")
        return verification

    compile_stage = compile_java_snippet(
        code_text=str(patch_stage.get("patched_code") or code_text),
        file_name=target_file,
    )
    stages.append(_sanitize_stage_for_result(compile_stage))
    if compile_stage["status"] != "passed":
        verification = _build_verification_result(status="failed", stages=stages)
        verification["retryable"] = bool(compile_stage.get("retryable", True))
        verification["failure_reason"] = compile_stage.get("reason") or compile_stage.get("stderr_summary")
        return verification

    working_directory = str(options.get("verifier_working_directory") or "").strip() or None

    lint_stage = run_lint_stage(
        options=options,
        repo_profile=repo_profile,
        working_directory=working_directory,
    )
    stages.append(_sanitize_stage_for_result(lint_stage))
    if lint_stage["status"] == "failed":
        verification = _build_verification_result(status="failed", stages=stages)
        verification["retryable"] = bool(lint_stage.get("retryable", True))
        verification["failure_reason"] = lint_stage.get("reason") or lint_stage.get("stderr_summary")
        return verification

    test_stage = run_test_stage(
        options=options,
        repo_profile=repo_profile,
        working_directory=working_directory,
    )
    stages.append(_sanitize_stage_for_result(test_stage))
    if test_stage["status"] == "failed":
        verification = _build_verification_result(status="failed", stages=stages)
        verification["retryable"] = bool(test_stage.get("retryable", True))
        verification["failure_reason"] = test_stage.get("reason") or test_stage.get("stderr_summary")
        return verification

    security_stage = run_security_rescan_stage(
        options=options,
        working_directory=working_directory,
    )
    stages.append(_sanitize_stage_for_result(security_stage))
    if security_stage["status"] == "failed":
        verification = _build_verification_result(status="failed", stages=stages)
        verification["retryable"] = bool(security_stage.get("retryable", True))
        verification["failure_reason"] = security_stage.get("reason") or security_stage.get("stderr_summary")
        return verification

    verification = _build_verification_result(status="passed", stages=stages)
    verification["retryable"] = False
    verification["failure_reason"] = None
    return verification


def _sanitize_stage_for_result(stage: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": str(stage.get("stage")),
        "status": str(stage.get("status")),
        "exit_code": stage.get("exit_code"),
        "stdout_summary": stage.get("stdout_summary", ""),
        "stderr_summary": stage.get("stderr_summary", ""),
        "reason": stage.get("reason"),
        "retryable": bool(stage.get("retryable", False)),
    }


def _build_verification_result(*, status: str, stages: list[dict[str, Any]]) -> dict[str, Any]:
    passed_stages = [stage["stage"] for stage in stages if stage.get("status") == "passed"]
    failed_stage = next((stage["stage"] for stage in stages if stage.get("status") == "failed"), None)
    verified_level = _resolve_verified_level(stages)

    if status == "passed":
        summary = f"verification passed at {verified_level}"
    else:
        summary = f"verification failed at {failed_stage or 'unknown_stage'}"

    return {
        "status": status,
        "verified_level": verified_level,
        "passed_stages": passed_stages,
        "failed_stage": failed_stage,
        "stages": stages,
        "summary": summary,
    }


def _resolve_verified_level(stages: list[dict[str, Any]]) -> str:
    status_by_stage = {stage["stage"]: stage["status"] for stage in stages}
    if status_by_stage.get("patch_apply") == "passed" and status_by_stage.get("compile") == "passed":
        level = "L1"
        if status_by_stage.get("lint") == "passed":
            level = "L2"
            if status_by_stage.get("test") == "passed":
                level = "L3"
                if status_by_stage.get("security_rescan") == "passed":
                    level = "L4"
        return level
    return "L0"
