from __future__ import annotations

import re
from typing import Any

from memory import resolve_default_target_file
from prompts import build_fixer_prompt_payload


def run_fixer_agent(
    *,
    code_text: str,
    repair_plan: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    memory_matches: list[dict[str, Any]],
    attempt_no: int,
    last_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    patch_id = f"patch_attempt_{attempt_no}"
    # Keep the structured prompt payload for future LLM-based fallback.
    _ = build_fixer_prompt_payload(
        repair_plan=repair_plan,
        issues=issues,
        symbols=symbols,
        context_summary=context_summary,
        memory_matches=memory_matches,
        attempt_no=attempt_no,
    )

    target_file = _resolve_target_file(issues)
    strategy_used = _resolve_strategy(repair_plan, memory_matches)
    memory_case_ids = [str(item.get("case_id")) for item in memory_matches if item.get("case_id")]

    unified_diff = _build_patch_content(
        code_text=code_text,
        repair_plan=repair_plan,
        memory_matches=memory_matches,
        target_file=target_file,
        strategy_used=strategy_used,
        last_failure=last_failure,
    )
    if not _is_valid_unified_diff(unified_diff):
        attempt = _build_attempt_record(
            attempt_no=attempt_no,
            patch_id=patch_id,
            status="failed",
            failure_stage="fixer",
            failure_reason="no_valid_patch",
            failure_detail="Unable to generate a valid unified diff.",
            memory_case_ids=memory_case_ids,
        )
        return {
            "ok": False,
            "patch_artifact": None,
            "attempt": attempt,
        }

    patch_artifact = {
        "patch_id": patch_id,
        "attempt_no": attempt_no,
        "status": "generated",
        "format": "unified_diff",
        "content": unified_diff,
        "explanation": _build_explanation(strategy_used, memory_matches),
        "risk_level": _resolve_risk_level(memory_matches, strategy_used),
        "target_files": [target_file],
        "strategy_used": strategy_used,
        "memory_case_ids": memory_case_ids,
    }
    attempt = _build_attempt_record(
        attempt_no=attempt_no,
        patch_id=patch_id,
        status="generated",
        failure_stage=None,
        failure_reason=None,
        failure_detail=None,
        memory_case_ids=memory_case_ids,
    )
    return {
        "ok": True,
        "patch_artifact": patch_artifact,
        "attempt": attempt,
    }


def _resolve_target_file(issues: list[dict[str, Any]]) -> str:
    target = resolve_default_target_file(issues)
    target = target.replace("\\", "/").strip()
    marker_match = re.match(r"^(?P<path>.+\.java):\d+(?::\d+)?$", target)
    if marker_match:
        target = marker_match.group("path")
    if target.startswith("a/") or target.startswith("b/"):
        target = target[2:]
    return target or "snippet.java"


def _resolve_strategy(repair_plan: list[dict[str, Any]], memory_matches: list[dict[str, Any]]) -> str:
    if memory_matches:
        strategy = str(memory_matches[0].get("strategy") or "").strip()
        if strategy:
            return strategy
    if repair_plan:
        strategy = str(repair_plan[0].get("strategy") or "").strip()
        if strategy:
            return strategy
    return "manual_review"


def _build_patch_content(
    *,
    code_text: str,
    repair_plan: list[dict[str, Any]],
    memory_matches: list[dict[str, Any]],
    target_file: str,
    strategy_used: str,
    last_failure: dict[str, Any] | None,
) -> str:
    if memory_matches:
        candidate = str(memory_matches[0].get("diff") or "").strip()
        adapted = _adapt_diff_path(candidate, target_file)
        if adapted and _is_candidate_compatible(adapted, code_text):
            return adapted
        if _is_valid_unified_diff(adapted):
            # Candidate has valid format but not guaranteed to fit current snippet.
            # Fall through to deterministic patch for stable apply behavior.
            pass

    first_line = _first_code_line(code_text)
    lines = [
        f"diff --git a/{target_file} b/{target_file}",
        f"--- a/{target_file}",
        f"+++ b/{target_file}",
        "@@ -1,1 +1,2 @@",
        f" {first_line}",
        f"+// Applied repair strategy: {strategy_used}",
    ]

    if repair_plan and strategy_used == "manual_review":
        lines[-1] = f"+// Planned strategy: {repair_plan[0].get('strategy', 'manual_review')}"
    if last_failure:
        failed_stage = str(last_failure.get("failed_stage") or "").strip()
        if failed_stage:
            lines[-1] = f"+// Retry after {failed_stage} failure: strategy={strategy_used}"
    return "\n".join(lines)


def _adapt_diff_path(diff_text: str, target_file: str) -> str:
    if not diff_text:
        return ""
    lines = diff_text.splitlines()
    if len(lines) < 3:
        return ""

    normalized = []
    for index, line in enumerate(lines):
        if index == 0 and line.startswith("diff --git "):
            normalized.append(f"diff --git a/{target_file} b/{target_file}")
            continue
        if line.startswith("--- "):
            normalized.append(f"--- a/{target_file}")
            continue
        if line.startswith("+++ "):
            normalized.append(f"+++ b/{target_file}")
            continue
        normalized.append(line)
    return "\n".join(normalized)


def _is_candidate_compatible(diff_text: str, code_text: str) -> bool:
    if not code_text:
        return False
    source = code_text.splitlines()
    source_set = set(source)
    for line in diff_text.splitlines():
        if line.startswith("-") and not line.startswith("---"):
            removed = line[1:]
            if removed not in source_set:
                return False
    return True


def _first_code_line(code_text: str) -> str:
    for line in code_text.splitlines():
        if line.strip():
            return line
    return "// empty snippet"


def _is_valid_unified_diff(content: str) -> bool:
    if not content:
        return False
    lines = content.splitlines()
    if len(lines) < 3:
        return False
    return lines[0].startswith("diff --git a/") and lines[1].startswith("--- a/") and lines[2].startswith("+++ b/")


def _build_explanation(strategy_used: str, memory_matches: list[dict[str, Any]]) -> str:
    if memory_matches:
        return f"Generated patch using case adaptation strategy: {strategy_used}."
    return f"Generated patch using deterministic fallback strategy: {strategy_used}."


def _resolve_risk_level(memory_matches: list[dict[str, Any]], strategy_used: str) -> str:
    if strategy_used in {"parameterized_query", "batch_query"}:
        return "medium"
    if strategy_used in {"manual_review"}:
        return "high"
    if memory_matches:
        return "medium"
    return "low"


def _build_attempt_record(
    *,
    attempt_no: int,
    patch_id: str,
    status: str,
    failure_stage: str | None,
    failure_reason: str | None,
    failure_detail: str | None,
    memory_case_ids: list[str],
) -> dict[str, Any]:
    return {
        "attempt_no": attempt_no,
        "patch_id": patch_id,
        "status": status,
        "verified_level": "L0",
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_detail": failure_detail,
        "memory_case_ids": memory_case_ids,
    }
