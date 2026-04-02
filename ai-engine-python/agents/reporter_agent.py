from __future__ import annotations

from typing import Any

from core.schemas import EngineState


def build_review_completed_payload(state: EngineState) -> dict[str, Any]:
    patch_artifact = state.patch_artifact or None
    patch_status = "generated" if patch_artifact else "absent"
    attempts = [_sanitize_attempt(item) for item in state.attempts]
    memory_matches = list(state.memory_matches or [])

    verification_result = _sanitize_verification(state.verification_result)
    verified_level = str((verification_result or {}).get("verified_level") or "L0")
    final_outcome = _resolve_final_outcome(state=state, patch_artifact=patch_artifact, verification_result=verification_result)

    analyzer_block = state.analyzer_summary
    patch_block = _build_patch_block(patch_artifact, patch_status)

    summary_block = {
        "issue_count": len(state.issues),
        "repair_plan_count": len(state.repair_plan),
        "memory_match_count": len(memory_matches),
        "attempt_count": len(attempts),
        "retry_count": state.retry_count,
        "verified_level": verified_level,
        "final_outcome": final_outcome,
    }

    result_block = {
        "engine": "python",
        "summary": summary_block,
        "analyzer": analyzer_block,
        "analyzer_evidence": {
            "issues": state.issues,
            "symbols": state.symbols,
            "context_summary": state.context_summary,
            "diagnostics": state.diagnostics,
        },
        "issues": state.issues,
        "symbols": state.symbols,
        "contextSummary": state.context_summary,
        "diagnostics": state.diagnostics,
        "issue_graph": state.issue_graph,
        "repair_plan": state.repair_plan,
        "planner_summary": state.planner_summary,
        "memory": {"matches": memory_matches},
        "patch": patch_block,
        "attempts": attempts,
        "verification": verification_result,
    }

    return {
        "source": "python-engine",
        "stage": "finalize_result",
        "engine": "python",
        "result": result_block,
        "summary": summary_block,
        "analyzer": analyzer_block,
        "analyzer_evidence": result_block["analyzer_evidence"],
        "issues": state.issues,
        "symbols": state.symbols,
        "contextSummary": state.context_summary,
        "diagnostics": state.diagnostics,
        "issue_graph": state.issue_graph,
        "repair_plan": state.repair_plan,
        "planner_summary": state.planner_summary,
        "memory": {"matches": memory_matches},
        "patch": patch_block,
        "attempts": attempts,
        "verification": verification_result,
    }


def _resolve_final_outcome(
    *,
    state: EngineState,
    patch_artifact: dict[str, Any] | None,
    verification_result: dict[str, Any] | None,
) -> str:
    if patch_artifact is None:
        return "failed_no_patch"
    if not state.enable_verifier:
        return "patch_generated_unverified"
    if verification_result is None:
        return "patch_generated_unverified"
    if str(verification_result.get("status")) == "passed" and str(verification_result.get("verified_level")) != "L0":
        return "verified_patch"
    if str(verification_result.get("status")) == "failed":
        return "failed_after_retries"
    return "patch_generated_unverified"


def _sanitize_verification(verification_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if verification_result is None:
        return None
    stages = []
    for stage in verification_result.get("stages", []) or []:
        stages.append(
            {
                "stage": stage.get("stage"),
                "status": stage.get("status"),
                "exit_code": stage.get("exit_code"),
                "stdout_summary": stage.get("stdout_summary", ""),
                "stderr_summary": stage.get("stderr_summary", ""),
                "reason": stage.get("reason"),
            }
        )

    return {
        "status": verification_result.get("status"),
        "verified_level": verification_result.get("verified_level", "L0"),
        "passed_stages": verification_result.get("passed_stages", []),
        "failed_stage": verification_result.get("failed_stage"),
        "stages": stages,
        "summary": verification_result.get("summary", ""),
    }


def _build_patch_block(patch_artifact: dict[str, Any] | None, status: str) -> dict[str, Any]:
    if not patch_artifact:
        return {
            "status": status,
            "patch_id": None,
            "attempt_no": None,
            "format": "unified_diff",
            "content": None,
            "explanation": None,
            "risk_level": None,
            "target_files": [],
            "strategy_used": None,
            "memory_case_ids": [],
        }
    return {
        "status": status,
        "patch_id": patch_artifact.get("patch_id"),
        "attempt_no": patch_artifact.get("attempt_no"),
        "format": patch_artifact.get("format", "unified_diff"),
        "content": patch_artifact.get("content"),
        "explanation": patch_artifact.get("explanation"),
        "risk_level": patch_artifact.get("risk_level"),
        "target_files": patch_artifact.get("target_files", []),
        "strategy_used": patch_artifact.get("strategy_used"),
        "memory_case_ids": patch_artifact.get("memory_case_ids", []),
    }


def _sanitize_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    status = str(attempt.get("status") or "").strip().lower()
    if status not in {"generated", "failed"}:
        status = "failed"

    if status == "generated":
        failure_stage = None
        failure_reason = None
        failure_detail = None
    else:
        failure_stage = str(attempt.get("failure_stage") or "fixer")
        raw_reason = str(attempt.get("failure_reason") or "").strip()
        failure_reason = raw_reason or None
        raw_detail = str(attempt.get("failure_detail") or "").strip()
        failure_detail = raw_detail or None

    return {
        "attempt_no": attempt.get("attempt_no"),
        "patch_id": attempt.get("patch_id"),
        "status": status,
        "verified_level": attempt.get("verified_level", "L0"),
        "failure_stage": failure_stage,
        "failed_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_detail": failure_detail,
        "memory_case_ids": attempt.get("memory_case_ids", []),
    }
