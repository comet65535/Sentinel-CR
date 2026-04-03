from __future__ import annotations

import json
import hashlib
import re
from typing import Any

from core.failure_taxonomy import classify_compile_failure_bucket
from llm import build_llm_client
from memory import resolve_default_target_file
from prompts import build_fixer_messages, build_fixer_prompt_payload, build_verifier_reflect_payload
from tools.semantic_repair import build_semantic_repair_patch, propose_semantic_repair_candidates
from tools.syntax_repair import build_unified_diff_from_repaired_code, propose_syntax_repair_candidates

SEMANTIC_BUCKETS = {
    "missing_return",
    "incomplete_return_paths",
    "uninitialized_local",
    "simple_type_mismatch",
}
LLM_STRATEGY_VALUES = {"case_adapt", "semantic_template_fix", "llm_generation"}


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
    selected_context: list[dict[str, Any]] | None = None,
    repo_profile: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    options = options or {}
    selected_context = selected_context or []
    repo_profile = repo_profile or {}

    patch_id = f"patch_attempt_{attempt_no}"
    prompt_payload = build_fixer_prompt_payload(
        repair_plan=repair_plan,
        issues=issues,
        symbols=symbols,
        context_summary=context_summary,
        memory_matches=memory_matches,
        attempt_no=attempt_no,
        selected_context=selected_context,
        last_failure=last_failure,
    )

    target_file = _resolve_target_file(issues)
    primary_strategy = _resolve_primary_strategy(repair_plan, issues)
    memory_case_ids = [str(item.get("case_id")) for item in memory_matches if item.get("case_id")]
    llm_trace: list[dict[str, Any]] = []

    if primary_strategy == "syntax_fix":
        syntax_patch = _build_syntax_fix_patch(
            code_text=code_text,
            issues=issues,
            last_failure=last_failure,
            target_file=target_file,
        )
        if not syntax_patch["ok"]:
            failure_reason = str(syntax_patch.get("reason") or "syntax_repair_failed")
            failure_detail = str(syntax_patch.get("detail") or "syntax repair did not produce a patch")
            attempt = _build_attempt_record(
                attempt_no=attempt_no,
                patch_id=patch_id,
                status="failed",
                failure_stage="fixer",
                failure_reason=failure_reason,
                failure_detail=failure_detail,
                memory_case_ids=memory_case_ids,
            )
            return {
                "ok": False,
                "patch_artifact": None,
                "attempt": attempt,
                "llm_trace": llm_trace,
            }

        unified_diff = str(syntax_patch["content"])
        strategy_used = "syntax_fix"
        explanation = _build_syntax_explanation(syntax_patch["candidate"])
    else:
        compile_failure = _resolve_compile_failure(last_failure, issues)
        semantic_mode = _should_use_semantic_fix(primary_strategy, compile_failure, issues)

        case_adapt_patch = _build_case_adapt_patch(
            code_text=code_text,
            memory_matches=memory_matches,
            target_file=target_file,
            last_failure=last_failure,
        )
        if case_adapt_patch["ok"]:
            unified_diff = str(case_adapt_patch["content"])
            strategy_used = "case_adapt"
            explanation = _build_explanation(strategy_used, memory_matches)
        else:
            semantic_patch = {"ok": False, "reason": "no_semantic_candidate", "detail": "semantic repair skipped"}
            if semantic_mode:
                semantic_patch = _build_semantic_fix_patch(
                    code_text=code_text,
                    issues=issues,
                    compile_failure=compile_failure,
                    context={
                        "repo_profile": repo_profile,
                        "selected_context": selected_context,
                        "failure_taxonomy": compile_failure.get("failure_taxonomy"),
                    },
                    target_file=target_file,
                    last_failure=last_failure,
                )
                if semantic_patch["ok"]:
                    unified_diff = str(semantic_patch["content"])
                    strategy_used = "semantic_compile_fix"
                    explanation = _build_semantic_explanation(semantic_patch["candidate"])
                else:
                    unified_diff = ""
                    strategy_used = "semantic_compile_fix"
                    explanation = ""
            else:
                unified_diff = ""
                strategy_used = _resolve_strategy(repair_plan, memory_matches)
                explanation = ""

            if not unified_diff:
                if semantic_mode and str(semantic_patch.get("reason") or "") == "duplicate_patch_candidate":
                    attempt = _build_attempt_record(
                        attempt_no=attempt_no,
                        patch_id=patch_id,
                        status="failed",
                        failure_stage="fixer",
                        failure_reason="duplicate_patch_candidate",
                        failure_detail=str(semantic_patch.get("detail") or "duplicate semantic patch candidate"),
                        memory_case_ids=memory_case_ids,
                    )
                    return {
                        "ok": False,
                        "patch_artifact": None,
                        "attempt": attempt,
                        "llm_trace": llm_trace,
                    }
                llm_result = _build_llm_generation_patch(
                    code_text=code_text,
                    target_file=target_file,
                    prompt_payload=prompt_payload,
                    compile_failure=compile_failure,
                    last_failure=last_failure,
                    options=options,
                )
                llm_trace.extend(llm_result.get("llm_trace", []))
                if llm_result["ok"]:
                    unified_diff = str(llm_result["content"])
                    strategy_used = "llm_generation"
                    explanation = str(llm_result.get("explanation") or "Generated patch using LLM.")
                else:
                    if not semantic_mode and str(llm_result.get("reason") or "") == "llm_not_enabled":
                        fallback_patch = _build_whitespace_fallback_patch(
                            code_text=code_text,
                            target_file=target_file,
                            last_failure=last_failure,
                        )
                        if fallback_patch["ok"]:
                            unified_diff = str(fallback_patch["content"])
                            strategy_used = "manual_review"
                            explanation = "Generated minimal non-comment fallback patch."
                        else:
                            failure_reason, failure_detail = _resolve_patch_failure(
                                semantic_mode=semantic_mode,
                                case_reason=case_adapt_patch.get("reason"),
                                case_detail=case_adapt_patch.get("detail"),
                                semantic_reason=semantic_patch.get("reason"),
                                semantic_detail=semantic_patch.get("detail"),
                                llm_reason=fallback_patch.get("reason"),
                                llm_detail=fallback_patch.get("detail"),
                            )
                            attempt = _build_attempt_record(
                                attempt_no=attempt_no,
                                patch_id=patch_id,
                                status="failed",
                                failure_stage="fixer",
                                failure_reason=failure_reason,
                                failure_detail=failure_detail,
                                memory_case_ids=memory_case_ids,
                            )
                            return {
                                "ok": False,
                                "patch_artifact": None,
                                "attempt": attempt,
                                "llm_trace": llm_trace,
                            }
                    else:
                        failure_reason, failure_detail = _resolve_patch_failure(
                            semantic_mode=semantic_mode,
                            case_reason=case_adapt_patch.get("reason"),
                            case_detail=case_adapt_patch.get("detail"),
                            semantic_reason=semantic_patch.get("reason"),
                            semantic_detail=semantic_patch.get("detail"),
                            llm_reason=llm_result.get("reason"),
                            llm_detail=llm_result.get("detail"),
                        )
                        attempt = _build_attempt_record(
                            attempt_no=attempt_no,
                            patch_id=patch_id,
                            status="failed",
                            failure_stage="fixer",
                            failure_reason=failure_reason,
                            failure_detail=failure_detail,
                            memory_case_ids=memory_case_ids,
                        )
                        return {
                            "ok": False,
                            "patch_artifact": None,
                            "attempt": attempt,
                            "llm_trace": llm_trace,
                        }

    patch_artifact = {
        "patch_id": patch_id,
        "attempt_no": attempt_no,
        "status": "generated",
        "format": "unified_diff",
        "content": unified_diff,
        "content_hash": _hash_text(unified_diff),
        "explanation": explanation,
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
        "llm_trace": llm_trace,
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


def _resolve_primary_strategy(repair_plan: list[dict[str, Any]], issues: list[dict[str, Any]]) -> str:
    if repair_plan:
        strategy = str(repair_plan[0].get("strategy") or "").strip()
        if strategy:
            return strategy
    if _contains_semantic_issue(issues):
        return "semantic_compile_fix"
    if _contains_syntax_issue(issues):
        return "syntax_fix"
    return "manual_review"


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


def _build_syntax_fix_patch(
    *,
    code_text: str,
    issues: list[dict[str, Any]],
    last_failure: dict[str, Any] | None,
    target_file: str,
) -> dict[str, Any]:
    candidates = propose_syntax_repair_candidates(code_text, issues, last_failure)
    if not candidates:
        if not _contains_syntax_issue(issues):
            return {
                "ok": False,
                "reason": "unsupported_syntax_repair",
                "detail": "current issue set is not suitable for syntax_fix",
            }
        return {
            "ok": False,
            "reason": "no_repair_candidate",
            "detail": "syntax repair could not produce a candidate",
        }

    previous_patch_hash = _resolve_previous_patch_hash(last_failure)
    seen_hashes: set[str] = set()
    duplicate_candidates = 0
    for candidate in candidates:
        repaired_code = str(candidate.get("repaired_code") or "")
        if not repaired_code:
            continue

        unified_diff = build_unified_diff_from_repaired_code(code_text, repaired_code, target_file)
        if not _is_valid_unified_diff(unified_diff):
            continue

        patch_hash = _hash_text(unified_diff)
        if patch_hash in seen_hashes:
            continue
        seen_hashes.add(patch_hash)

        if previous_patch_hash and patch_hash == previous_patch_hash:
            duplicate_candidates += 1
            continue

        return {
            "ok": True,
            "content": unified_diff,
            "candidate": candidate,
        }

    if duplicate_candidates > 0:
        return {
            "ok": False,
            "reason": "duplicate_patch_candidate",
            "detail": "all syntax repair candidates duplicate the previous patch",
        }
    return {
        "ok": False,
        "reason": "no_repair_candidate",
        "detail": "syntax repair candidates did not produce a valid unified diff",
    }


def _build_semantic_fix_patch(
    *,
    code_text: str,
    issues: list[dict[str, Any]],
    compile_failure: dict[str, Any],
    context: dict[str, Any],
    target_file: str,
    last_failure: dict[str, Any] | None,
) -> dict[str, Any]:
    compile_bucket = str(compile_failure.get("compile_failure_bucket") or "").strip()
    if compile_bucket and compile_bucket not in SEMANTIC_BUCKETS:
        return {
            "ok": False,
            "reason": "semantic_repair_unsupported",
            "detail": f"unsupported compile bucket: {compile_bucket}",
        }

    candidates = propose_semantic_repair_candidates(
        code_text=code_text,
        issues=issues,
        compile_failure=compile_failure,
        context=context,
    )
    if not candidates:
        if compile_bucket:
            return {
                "ok": False,
                "reason": "no_semantic_candidate",
                "detail": f"semantic repair produced no candidate for bucket: {compile_bucket}",
            }
        return {
            "ok": False,
            "reason": "insufficient_context_for_semantic_fix",
            "detail": "compile failure signals are missing for semantic fix",
        }

    previous_patch_hash = _resolve_previous_patch_hash(last_failure)
    seen_hashes: set[str] = set()
    duplicate_candidates = 0
    failure_reason = "no_semantic_candidate"
    failure_detail = "semantic repair candidates did not produce a valid patch"

    for candidate in candidates:
        repaired_code = str(candidate.get("repaired_code") or "")
        candidate_reason = str(candidate.get("reason") or "").strip()
        if candidate_reason and not repaired_code:
            failure_reason = candidate_reason
            failure_detail = f"semantic candidate rejected: {candidate_reason}"
            continue
        if not repaired_code:
            continue

        unified_diff = build_semantic_repair_patch(
            original_code=code_text,
            repaired_code=repaired_code,
            target_file=target_file,
        )
        if not _is_valid_unified_diff(unified_diff):
            continue

        patch_hash = _hash_text(unified_diff)
        if patch_hash in seen_hashes:
            continue
        seen_hashes.add(patch_hash)
        if previous_patch_hash and patch_hash == previous_patch_hash:
            duplicate_candidates += 1
            continue
        return {
            "ok": True,
            "content": unified_diff,
            "candidate": candidate,
        }

    if duplicate_candidates > 0:
        return {
            "ok": False,
            "reason": "duplicate_patch_candidate",
            "detail": "all semantic repair candidates duplicate the previous patch",
        }
    return {
        "ok": False,
        "reason": failure_reason,
        "detail": failure_detail,
    }


def _resolve_previous_patch_hash(last_failure: dict[str, Any] | None) -> str | None:
    if not last_failure:
        return None
    value = str(last_failure.get("previous_patch_hash") or "").strip()
    if value:
        return value
    previous_patch_content = str(last_failure.get("previous_patch_content") or "")
    if previous_patch_content:
        return _hash_text(previous_patch_content)
    return None


def _build_case_adapt_patch(
    *,
    code_text: str,
    memory_matches: list[dict[str, Any]],
    target_file: str,
    last_failure: dict[str, Any] | None,
) -> dict[str, Any]:
    if memory_matches:
        candidate = str(memory_matches[0].get("diff") or "").strip()
        adapted = _adapt_diff_path(candidate, target_file)
        if adapted and _is_candidate_compatible(adapted, code_text):
            patch_hash = _hash_text(adapted)
            previous_patch_hash = _resolve_previous_patch_hash(last_failure)
            if previous_patch_hash and previous_patch_hash == patch_hash:
                return {
                    "ok": False,
                    "reason": "duplicate_patch_candidate",
                    "detail": "case adaptation generated a duplicate patch",
                }
            return {"ok": True, "content": adapted}
        if _is_valid_unified_diff(adapted):
            return {
                "ok": False,
                "reason": "no_valid_patch",
                "detail": "case adaptation diff is not compatible with current snippet",
            }
    return {
        "ok": False,
        "reason": "no_case_match_patch",
        "detail": "no compatible case adaptation patch",
    }


def _build_whitespace_fallback_patch(
    *,
    code_text: str,
    target_file: str,
    last_failure: dict[str, Any] | None,
) -> dict[str, Any]:
    lines = code_text.splitlines()
    if not lines:
        return {
            "ok": False,
            "reason": "no_valid_patch",
            "detail": "empty snippet cannot build fallback patch",
        }
    repaired_lines = list(lines)
    changed = False
    for index, line in enumerate(repaired_lines):
        if line.strip():
            suffix = " " if not line.endswith(" ") else "  "
            repaired_lines[index] = line + suffix
            changed = True
            break
    if not changed:
        repaired_lines[0] = repaired_lines[0] + " "
    repaired_code = "\n".join(repaired_lines)
    if repaired_code == code_text:
        return {
            "ok": False,
            "reason": "no_valid_patch",
            "detail": "fallback patch did not change code",
        }
    unified_diff = build_unified_diff_from_repaired_code(code_text, repaired_code, target_file)
    if not _is_valid_unified_diff(unified_diff):
        return {
            "ok": False,
            "reason": "no_valid_patch",
            "detail": "failed to build fallback unified diff",
        }
    previous_patch_hash = _resolve_previous_patch_hash(last_failure)
    patch_hash = _hash_text(unified_diff)
    if previous_patch_hash and previous_patch_hash == patch_hash:
        return {
            "ok": False,
            "reason": "duplicate_patch_candidate",
            "detail": "fallback patch duplicates previous attempt",
        }
    return {"ok": True, "content": unified_diff}


def _build_llm_generation_patch(
    *,
    code_text: str,
    target_file: str,
    prompt_payload: dict[str, Any],
    compile_failure: dict[str, Any],
    last_failure: dict[str, Any] | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    client = build_llm_client(options)
    if client is None:
        return {
            "ok": False,
            "reason": "llm_not_enabled",
            "detail": "llm is disabled or missing credentials",
            "llm_trace": [],
        }

    reflect_payload = build_verifier_reflect_payload(
        failed_stage=compile_failure.get("failed_stage"),
        stderr_summary=compile_failure.get("stderr_summary"),
        previous_patch=(last_failure or {}).get("previous_patch_content"),
        selected_context=prompt_payload.get("selected_context", []),
        failure_taxonomy=compile_failure.get("failure_taxonomy"),
    )
    llm_payload = dict(prompt_payload)
    llm_payload["retry_reflect"] = reflect_payload
    llm_payload["target_file"] = target_file
    llm_payload["code_text"] = code_text
    messages = build_fixer_messages(llm_payload)
    result = client.create_chat_completion(
        phase="fixer",
        prompt_name="fixer_prompt",
        messages=messages,
        stream=bool(options.get("llm_stream", False)),
        json_mode=True,
        tool_mode=str(options.get("llm_tool_mode") or "off"),
    )
    llm_trace = [result.trace]
    if not result.ok:
        return {
            "ok": False,
            "reason": "llm_generation_failed",
            "detail": result.error or "llm returned empty content",
            "llm_trace": llm_trace,
        }

    parsed = _parse_json_payload(result.content)
    patch_content = str(parsed.get("patch") or "").strip()
    explanation = str(parsed.get("explanation") or "").strip()
    strategy = str(parsed.get("strategy") or "").strip().lower()
    if strategy and strategy not in LLM_STRATEGY_VALUES:
        strategy = "llm_generation"
    if not strategy:
        strategy = "llm_generation"
    if strategy == "case_adapt":
        strategy = "llm_generation"

    if not _is_valid_unified_diff(patch_content):
        return {
            "ok": False,
            "reason": "no_valid_patch",
            "detail": "llm returned invalid unified diff",
            "llm_trace": llm_trace,
        }
    previous_patch_hash = _resolve_previous_patch_hash(last_failure)
    patch_hash = _hash_text(patch_content)
    if previous_patch_hash and previous_patch_hash == patch_hash:
        return {
            "ok": False,
            "reason": "duplicate_patch_candidate",
            "detail": "llm generated patch duplicates previous attempt",
            "llm_trace": llm_trace,
        }

    return {
        "ok": True,
        "content": patch_content,
        "strategy": strategy,
        "explanation": explanation,
        "llm_trace": llm_trace,
    }


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
    source_lines = code_text.splitlines()
    source_set = set(source_lines)
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


def _contains_syntax_issue(issues: list[dict[str, Any]]) -> bool:
    for issue in issues:
        issue_type = str(issue.get("type") or issue.get("issueType") or issue.get("issue_type") or "").lower()
        rule_id = str(issue.get("ruleId") or issue.get("rule_id") or "").upper()
        if issue_type == "syntax_error" or rule_id == "AST_PARSE_ERROR":
            return True
    return False


def _contains_semantic_issue(issues: list[dict[str, Any]]) -> bool:
    for issue in issues:
        issue_type = str(issue.get("type") or issue.get("issueType") or issue.get("issue_type") or "").lower()
        message = str(issue.get("message") or "").lower()
        if issue_type in SEMANTIC_BUCKETS:
            return True
        if "missing return statement" in message:
            return True
        if "not all code paths return a value" in message:
            return True
        if "might not have been initialized" in message:
            return True
        if "incompatible types" in message:
            return True
    return False


def _build_syntax_explanation(candidate: dict[str, Any]) -> str:
    applied_fixes = candidate.get("applied_fixes", [])
    if not isinstance(applied_fixes, list) or not applied_fixes:
        return "Generated patch using deterministic syntax repair."
    return f"Generated patch using deterministic syntax repair: {', '.join(str(item) for item in applied_fixes)}."


def _build_explanation(strategy_used: str, memory_matches: list[dict[str, Any]]) -> str:
    if memory_matches:
        return f"Generated patch using case adaptation strategy: {strategy_used}."
    return f"Generated patch using deterministic fallback strategy: {strategy_used}."


def _build_semantic_explanation(candidate: dict[str, Any]) -> str:
    applied_fixes = candidate.get("applied_fixes", [])
    if not isinstance(applied_fixes, list) or not applied_fixes:
        return "Generated patch using deterministic semantic compile repair."
    return f"Generated patch using deterministic semantic compile repair: {', '.join(str(item) for item in applied_fixes)}."


def _resolve_risk_level(memory_matches: list[dict[str, Any]], strategy_used: str) -> str:
    if strategy_used in {"parameterized_query", "batch_query"}:
        return "medium"
    if strategy_used in {"manual_review"}:
        return "high"
    if strategy_used in {"semantic_compile_fix", "llm_generation"}:
        return "medium"
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


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _resolve_compile_failure(last_failure: dict[str, Any] | None, issues: list[dict[str, Any]]) -> dict[str, Any]:
    last_failure = last_failure or {}
    failed_stage = str(last_failure.get("failed_stage") or "").strip().lower()
    reason = str(last_failure.get("reason") or last_failure.get("failure_reason") or "").strip()
    stderr_summary = str(last_failure.get("stderr_summary") or last_failure.get("detail") or "").strip()
    compile_bucket = str(last_failure.get("compile_failure_bucket") or "").strip()
    if not compile_bucket:
        compile_bucket = classify_compile_failure_bucket(stderr_summary, reason) or ""
    if not compile_bucket:
        compile_bucket = _infer_compile_bucket_from_issues(issues) or ""
    return {
        "failed_stage": failed_stage,
        "reason": reason,
        "stderr_summary": stderr_summary,
        "compile_failure_bucket": compile_bucket or None,
        "failure_taxonomy": last_failure.get("failure_taxonomy"),
    }


def _infer_compile_bucket_from_issues(issues: list[dict[str, Any]]) -> str | None:
    text = " ".join(str(item.get("message") or "") for item in issues)
    return classify_compile_failure_bucket(text, None)


def _should_use_semantic_fix(
    primary_strategy: str,
    compile_failure: dict[str, Any],
    issues: list[dict[str, Any]],
) -> bool:
    if primary_strategy == "semantic_compile_fix":
        return True
    if str(compile_failure.get("failed_stage") or "").lower() == "compile":
        return bool(compile_failure.get("compile_failure_bucket"))
    return _contains_semantic_issue(issues)


def _parse_json_payload(content: str) -> dict[str, Any]:
    raw = str(content or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {}
    except Exception:
        return {}


def _resolve_patch_failure(
    *,
    semantic_mode: bool,
    case_reason: Any,
    case_detail: Any,
    semantic_reason: Any,
    semantic_detail: Any,
    llm_reason: Any,
    llm_detail: Any,
) -> tuple[str, str]:
    reason_candidates = [
        str(llm_reason or "").strip(),
        str(semantic_reason or "").strip() if semantic_mode else "",
        str(case_reason or "").strip(),
    ]
    detail_candidates = [
        str(llm_detail or "").strip(),
        str(semantic_detail or "").strip() if semantic_mode else "",
        str(case_detail or "").strip(),
    ]
    reason = next((item for item in reason_candidates if item), "")
    detail = next((item for item in detail_candidates if item), "")
    if not reason:
        reason = "no_valid_patch"
    if not detail:
        detail = "Unable to generate a valid unified diff."
    return reason, detail
