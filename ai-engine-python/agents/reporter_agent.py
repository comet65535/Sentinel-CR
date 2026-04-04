from __future__ import annotations

from typing import Any

from core.failure_taxonomy import build_failure_taxonomy
from core.schemas import EngineState


def build_review_completed_payload(state: EngineState) -> dict[str, Any]:
    patch_artifact = state.patch_artifact or None
    attempts = [_sanitize_attempt(item) for item in state.attempts]
    memory_matches = list(state.memory_matches or [])
    short_term_memory = dict(state.short_term_memory or {})
    repo_profile = dict(state.repo_profile or {})
    case_store_summary = dict(state.case_store_summary or {})
    context_budget = dict(state.context_budget or {})
    selected_context = list(state.selected_context or [])
    memory_hits = dict(state.memory_hits or {})
    tool_trace = list(state.tool_trace or [])
    llm_trace = list(state.llm_trace or []) or _extract_llm_trace(state.options)
    standards_hits = list(state.standards_hits or [])

    verification_result = _sanitize_verification(state.verification_result)
    verified_level = str((verification_result or {}).get("verified_level") or "L0")
    final_outcome = _resolve_final_outcome(state=state, patch_artifact=patch_artifact, verification_result=verification_result)
    failed_stage = _resolve_failed_stage(state=state, verification_result=verification_result, final_outcome=final_outcome)
    failure_reason = _resolve_failure_reason(state=state, verification_result=verification_result, final_outcome=final_outcome)
    failure_detail = _resolve_failure_detail(state=state, verification_result=verification_result, final_outcome=final_outcome)
    failure_code = _resolve_failure_code(verification_result, failure_reason)
    failure_taxonomy = build_failure_taxonomy(
        final_outcome=final_outcome,
        failed_stage=failed_stage,
        failure_reason=failure_reason,
        failure_detail=failure_detail,
        issue_count=len(state.issues),
    )

    retry_exhausted = bool(
        final_outcome == "failed_after_retries" and state.enable_verifier and state.retry_count >= state.max_retries
    )
    execution_truth = _build_execution_truth(
        verification_result=verification_result,
        failure_taxonomy=failure_taxonomy,
        retry_hints=state.retry_hints,
    )
    user_message = _build_user_message(
        final_outcome=final_outcome,
        verified_level=verified_level,
        execution_truth=execution_truth,
        failure_reason=failure_reason,
        retry_count=state.retry_count,
        no_fix_needed=state.no_fix_needed,
    )

    patch_content = str((patch_artifact or {}).get("content") or "")
    delivery = {
        "unified_diff": patch_content,
        "verified_level": verified_level,
        "verification_stages": list((verification_result or {}).get("stages", [])),
        "final_outcome": final_outcome,
        "failed_stage": failed_stage,
        "failure_code": failure_code,
        "failure_reason": failure_reason,
        "retryable": bool((verification_result or {}).get("retryable", False)),
    }

    summary_block = {
        "issue_count": len(state.issues),
        "repair_plan_count": len(state.repair_plan),
        "memory_match_count": len(memory_matches),
        "attempt_count": len(attempts),
        "retry_count": state.retry_count,
        "verified_level": verified_level,
        "final_outcome": final_outcome,
        "failed_stage": failed_stage,
        "failure_code": failure_code,
        "failure_reason": failure_reason,
        "failure_detail": failure_detail,
        "failure_taxonomy": failure_taxonomy,
        "retry_exhausted": retry_exhausted,
        "no_fix_needed": state.no_fix_needed,
        "user_message": user_message,
    }

    user_events, debug_events = _split_user_debug_events(state.events)

    result_block = {
        "engine": "python",
        "delivery": delivery,
        "summary": summary_block,
        "execution_truth": execution_truth,
        "analyzer": state.analyzer_summary,
        "analyzer_evidence": {
            "issues": state.issues,
            "symbols": state.symbols,
            "contextSummary": state.context_summary,
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
        "memory": {
            "matches": memory_matches,
            "short_term": short_term_memory,
            "repo_profile": repo_profile,
            "case_store": case_store_summary,
            "case_store_summary": case_store_summary,
        },
        "memory_hits": memory_hits,
        "standards_hits": _build_standards_hits(standards_hits),
        "execution_stages": dict(state.execution_stages or {}),
        "context_budget": context_budget,
        "selected_context": selected_context,
        "tool_trace": tool_trace,
        "llm_trace": llm_trace,
        "repo_profile": repo_profile,
        "patch": _build_patch_block(patch_artifact),
        "attempts": attempts,
        "verification": verification_result,
        "user_events": user_events,
        "debug_events": debug_events,
    }

    return {
        "source": "python-engine",
        "stage": "finalize_result",
        "engine": "python",
        "result": result_block,
        "delivery": delivery,
        "summary": summary_block,
        "execution_truth": execution_truth,
        "patch": result_block["patch"],
        "verification": verification_result,
        "user_events": user_events,
        "debug_events": debug_events,
    }


def _resolve_final_outcome(
    *,
    state: EngineState,
    patch_artifact: dict[str, Any] | None,
    verification_result: dict[str, Any] | None,
) -> str:
    if state.no_fix_needed:
        return "no_fix_needed"
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
                "started_at": stage.get("started_at"),
                "finished_at": stage.get("finished_at"),
                "duration_ms": stage.get("duration_ms"),
                "summary": stage.get("summary"),
                "details": stage.get("details"),
                "skip_reason": stage.get("skip_reason"),
                "exit_code": stage.get("exit_code"),
                "stdout_summary": stage.get("stdout_summary", ""),
                "stderr_summary": stage.get("stderr_summary", ""),
                "failure_code": stage.get("failure_code"),
                "stderr_excerpt": stage.get("stderr_excerpt"),
                "retry_hint": stage.get("retry_hint"),
                "retryable": bool(stage.get("retryable", False)),
            }
        )

    return {
        "status": verification_result.get("status"),
        "overall_status": verification_result.get("overall_status"),
        "verified_level": verification_result.get("verified_level", "L0"),
        "passed_stages": verification_result.get("passed_stages", []),
        "failed_stage": verification_result.get("failed_stage"),
        "stages": stages,
        "summary": verification_result.get("summary", ""),
        "retryable": bool(verification_result.get("retryable", False)),
        "failure_reason": verification_result.get("failure_reason"),
        "failure_code": verification_result.get("failure_code"),
        "stderr_excerpt": verification_result.get("stderr_excerpt"),
        "retry_hint": verification_result.get("retry_hint"),
        "regression_risk": verification_result.get("regression_risk", "unknown"),
    }


def _build_execution_truth(
    *,
    verification_result: dict[str, Any] | None,
    failure_taxonomy: dict[str, Any],
    retry_hints: dict[str, Any] | None,
) -> dict[str, Any]:
    retry_hints = dict(retry_hints or {})
    stage_status = {str(item.get("stage") or ""): str(item.get("status") or "pending") for item in (verification_result or {}).get("stages", [])}
    return {
        "patch_apply_status": stage_status.get("patch_apply", "pending"),
        "compile_status": stage_status.get("compile", "pending"),
        "lint_status": stage_status.get("lint", "pending"),
        "test_status": stage_status.get("test", "pending"),
        "security_rescan_status": stage_status.get("security_rescan", "pending"),
        "regression_risk": str((verification_result or {}).get("regression_risk") or "unknown"),
        "failure_taxonomy": failure_taxonomy,
        "next_context_hint": retry_hints.get("next_context_hint"),
        "next_constraint_hint": retry_hints.get("next_constraint_hint"),
        "next_retry_strategy": retry_hints.get("next_retry_strategy"),
    }


def _build_standards_hits(standards_hits: list[dict[str, Any]]) -> dict[str, Any]:
    sources = sorted({str(item.get("source") or "unknown") for item in standards_hits if isinstance(item, dict)})
    condensed = []
    for item in standards_hits[:3]:
        if not isinstance(item, dict):
            continue
        condensed.append(
            {
                "id": item.get("id"),
                "source": item.get("source"),
                "score": item.get("score"),
                "summary": str(item.get("text") or item.get("snippet") or "")[:240],
                "used_by": ["fixer", "response"],
            }
        )
    return {
        "hit_count": len(standards_hits),
        "sources": sources,
        "hits": condensed,
    }


def _build_patch_block(patch_artifact: dict[str, Any] | None) -> dict[str, Any]:
    if not patch_artifact:
        return {
            "status": "absent",
            "patch_id": None,
            "attempt_no": None,
            "format": "unified_diff",
            "content": None,
            "unified_diff": None,
            "explanation": None,
            "risk_level": None,
            "target_files": [],
            "strategy_used": None,
            "memory_case_ids": [],
        }
    content = patch_artifact.get("content")
    return {
        "status": patch_artifact.get("status", "generated"),
        "patch_id": patch_artifact.get("patch_id"),
        "attempt_no": patch_artifact.get("attempt_no"),
        "format": patch_artifact.get("format", "unified_diff"),
        "content": content,
        "unified_diff": content,
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
    return {
        "attempt_no": attempt.get("attempt_no"),
        "patch_id": attempt.get("patch_id"),
        "status": status,
        "verified_level": attempt.get("verified_level", "L0"),
        "failure_stage": attempt.get("failure_stage") or attempt.get("failed_stage"),
        "failed_stage": attempt.get("failure_stage") or attempt.get("failed_stage"),
        "failure_reason": attempt.get("failure_reason"),
        "failure_detail": attempt.get("failure_detail"),
        "memory_case_ids": attempt.get("memory_case_ids", []),
    }


def _resolve_failed_stage(
    *,
    state: EngineState,
    verification_result: dict[str, Any] | None,
    final_outcome: str,
) -> str | None:
    if final_outcome in {"verified_patch", "no_fix_needed"}:
        return None
    if verification_result is not None:
        stage = str(verification_result.get("failed_stage") or "").strip()
        if stage:
            return stage
    for attempt in reversed(state.attempts):
        stage = str(attempt.get("failure_stage") or attempt.get("failed_stage") or "").strip()
        if stage:
            return stage
    return None


def _resolve_failure_reason(
    *,
    state: EngineState,
    verification_result: dict[str, Any] | None,
    final_outcome: str,
) -> str | None:
    if final_outcome in {"verified_patch", "no_fix_needed"}:
        return None
    if verification_result is not None:
        reason = str(verification_result.get("failure_reason") or "").strip()
        if reason:
            return reason
        for stage in verification_result.get("stages", []) or []:
            if stage.get("status") == "failed":
                s = str(stage.get("failure_code") or stage.get("summary") or "").strip()
                if s:
                    return s
    for attempt in reversed(state.attempts):
        reason = str(attempt.get("failure_reason") or "").strip()
        if reason:
            return reason
    return None


def _resolve_failure_detail(
    *,
    state: EngineState,
    verification_result: dict[str, Any] | None,
    final_outcome: str,
) -> str | None:
    if final_outcome in {"verified_patch", "no_fix_needed"}:
        return None
    if verification_result is not None:
        for stage in verification_result.get("stages", []) or []:
            if stage.get("status") == "failed":
                detail = str(stage.get("details") or "").strip()
                if detail:
                    return detail
                stderr = str(stage.get("stderr_summary") or "").strip()
                if stderr:
                    return stderr
                stdout = str(stage.get("stdout_summary") or "").strip()
                if stdout:
                    return stdout
    for attempt in reversed(state.attempts):
        detail = str(attempt.get("failure_detail") or "").strip()
        if detail:
            return detail
    return None


def _resolve_failure_code(verification_result: dict[str, Any] | None, failure_reason: str | None) -> str | None:
    if verification_result is not None:
        code = str(verification_result.get("failure_code") or "").strip()
        if code:
            return code
        for stage in verification_result.get("stages", []) or []:
            if stage.get("status") == "failed":
                stage_code = str(stage.get("failure_code") or "").strip()
                if stage_code:
                    return stage_code
    if failure_reason:
        return str(failure_reason).strip().lower().replace(" ", "_")
    return None


def _build_user_message(
    *,
    final_outcome: str,
    verified_level: str,
    execution_truth: dict[str, Any],
    failure_reason: str | None,
    retry_count: int,
    no_fix_needed: bool,
) -> str:
    if no_fix_needed:
        return "No fix needed. Analyzer found no actionable issue."
    if final_outcome == "verified_patch":
        return (
            f"Patch applied: {execution_truth.get('patch_apply_status')}; "
            f"compile={execution_truth.get('compile_status')}, lint={execution_truth.get('lint_status')}, "
            f"test={execution_truth.get('test_status')}, security={execution_truth.get('security_rescan_status')}. "
            f"Current verified level is {verified_level}; regression risk={execution_truth.get('regression_risk')}."
        )
    if final_outcome == "patch_generated_unverified":
        return "Patch generated, but verifier was not fully executed."
    if final_outcome == "failed_no_patch":
        return "No valid patch was generated from current evidence."
    if final_outcome == "failed_after_retries":
        failure_tax = execution_truth.get("failure_taxonomy") if isinstance(execution_truth.get("failure_taxonomy"), dict) else {}
        bucket = str(failure_tax.get("bucket") or "unknown")
        return (
            f"Verification failed after {retry_count} retries. Failure taxonomy={bucket}; "
            f"reason={failure_reason or 'unknown'}. "
            f"Next context hint: {execution_truth.get('next_context_hint') or 'provide failing context'}."
        )
    return "Review did not complete successfully."


def _extract_llm_trace(options: dict[str, Any]) -> list[dict[str, Any]]:
    trace = options.get("llm_trace")
    if not isinstance(trace, list):
        return []
    return [dict(item) for item in trace if isinstance(item, dict)]


def _split_user_debug_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    user_events: list[dict[str, Any]] = []
    debug_events: list[dict[str, Any]] = []
    for item in events or []:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("eventType") or item.get("event_type") or "")
        if _is_debug_event_type(event_type):
            debug_events.append(item)
        else:
            user_events.append(item)
    return user_events, debug_events


def _is_debug_event_type(event_type: str) -> bool:
    prefixes = (
        "langgraph_",
        "context_budget_",
        "context_resource_",
        "repo_memory_",
        "short_term_memory_",
        "mcp_resource_",
        "mcp_tool_",
        "case_store_",
    )
    return event_type.startswith(prefixes)
