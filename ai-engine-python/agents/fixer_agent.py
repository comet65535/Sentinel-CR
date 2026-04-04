from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

from agents.planner_agent import run_planner_agent
from analyzers import build_symbol_graph, compose_day2_output, parse_java_code, run_semgrep
from core.issue_graph import build_issue_graph
from llm import build_llm_client
from memory import retrieve_case_matches, search_standards
from prompts import build_fixer_messages, build_fixer_prompt_payload
from tools import apply_patch_to_snippet, compile_java_snippet, run_lint_stage, run_security_rescan_stage, run_test_stage

MAX_ACTION_STEPS = 3


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
    message_text: str | None = None,
    action_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    options = options or {}
    selected_context = list(selected_context or [])
    repo_profile = dict(repo_profile or {})
    action_history = list(action_history or [])
    last_failure = dict(last_failure or {})

    llm_client = build_llm_client(options)
    if llm_client is None:
        return _failed_output(
            attempt_no=attempt_no,
            reason="llm_not_enabled_or_missing_credentials",
            detail="LLM disabled or missing credentials. Configure SENTINEL_LLM_* or request llm_enabled=true.",
            llm_trace=[],
            tool_trace=[],
            selected_context=selected_context,
            memory_hits={"cases": memory_matches, "standards": []},
            issues=issues,
            symbols=symbols,
            context_summary=context_summary,
            repair_plan=repair_plan,
            issue_graph={"schema_version": "day3.v1", "nodes": [], "edges": []},
            planner_summary={},
            action_history=action_history,
        )

    state = {
        "code_text": code_text,
        "issues": list(issues),
        "symbols": list(symbols),
        "context_summary": dict(context_summary),
        "repair_plan": list(repair_plan),
        "issue_graph": {"schema_version": "day3.v1", "nodes": [], "edges": []},
        "planner_summary": {},
        "memory_matches": list(memory_matches),
        "standards_matches": _load_standards(code_text, message_text, issues),
        "selected_context": selected_context,
        "repo_profile": repo_profile,
        "last_failure": last_failure,
    }

    llm_trace: list[dict[str, Any]] = []
    tool_trace: list[dict[str, Any]] = []
    prompt_history = list(action_history)

    tool_handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
        "analyze_ast": lambda args: _tool_analyze_ast(state),
        "run_semgrep": lambda args: _tool_run_semgrep(state),
        "build_issue_graph": lambda args: _tool_build_issue_graph(state),
        "resolve_symbol": lambda args: _tool_resolve_symbol(state, args),
        "fetch_context": lambda args: _tool_fetch_context(state, args),
        "get_repo_profile": lambda args: _tool_get_repo_profile(state),
        "search_case_memory": lambda args: _tool_search_case_memory(state),
        "search_short_term_memory": lambda args: _tool_search_short_term_memory(state),
        "apply_patch": lambda args: _tool_apply_patch(state, args),
        "compile_java": lambda args: _tool_compile_java(state, args),
        "lint_java": lambda args: _tool_lint_java(state, args, options),
        "run_tests": lambda args: _tool_run_tests(state, args, options),
        "security_rescan": lambda args: _tool_security_rescan(state, args, options),
    }

    for step_no in range(1, MAX_ACTION_STEPS + 1):
        prompt_payload = build_fixer_prompt_payload(
            code_text=state["code_text"],
            message_text=message_text,
            repair_plan=state["repair_plan"],
            issues=state["issues"],
            symbols=state["symbols"],
            context_summary=state["context_summary"],
            memory_matches=state["memory_matches"],
            standards_matches=state["standards_matches"],
            attempt_no=attempt_no,
            selected_context=state["selected_context"],
            last_failure=state["last_failure"],
            repo_profile=state["repo_profile"],
            action_history=prompt_history,
        )
        messages = build_fixer_messages(prompt_payload)

        action_result = _request_action(
            llm_client=llm_client,
            messages=messages,
            options=options,
        )
        llm_trace.extend(action_result["llm_trace"])

        if not action_result["ok"]:
            return _failed_output(
                attempt_no=attempt_no,
                reason="llm_action_invalid",
                detail=action_result["detail"],
                llm_trace=llm_trace,
                tool_trace=tool_trace,
                selected_context=state["selected_context"],
                memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
                issues=state["issues"],
                symbols=state["symbols"],
                context_summary=state["context_summary"],
                repair_plan=state["repair_plan"],
                issue_graph=state["issue_graph"],
                planner_summary=state["planner_summary"],
                action_history=prompt_history,
            )

        action = action_result["action"]
        next_action = str(action.get("next_action") or "").strip()
        action_args = action.get("action_args") if isinstance(action.get("action_args"), dict) else {}
        candidate_patch = str(action.get("candidate_patch") or "").strip()
        explanation = str(action.get("explanation") or "").strip() or "LLM generated patch"

        if next_action == "finalize_patch":
            if not candidate_patch:
                return _failed_output(
                    attempt_no=attempt_no,
                    reason="no_valid_patch",
                    detail="finalize_patch was requested without candidate_patch",
                    llm_trace=llm_trace,
                    tool_trace=tool_trace,
                    selected_context=state["selected_context"],
                    memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
                    issues=state["issues"],
                    symbols=state["symbols"],
                    context_summary=state["context_summary"],
                    repair_plan=state["repair_plan"],
                    issue_graph=state["issue_graph"],
                    planner_summary=state["planner_summary"],
                    action_history=prompt_history,
                )
            validation_error = _validate_patch(candidate_patch, state["last_failure"], tool_trace)
            if validation_error is not None:
                return _failed_output(
                    attempt_no=attempt_no,
                    reason=validation_error["reason"],
                    detail=validation_error["detail"],
                    llm_trace=llm_trace,
                    tool_trace=tool_trace,
                    selected_context=state["selected_context"],
                    memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
                    issues=state["issues"],
                    symbols=state["symbols"],
                    context_summary=state["context_summary"],
                    repair_plan=state["repair_plan"],
                    issue_graph=state["issue_graph"],
                    planner_summary=state["planner_summary"],
                    action_history=prompt_history,
                )
            patch_artifact = {
                "patch_id": f"patch_attempt_{attempt_no}",
                "attempt_no": attempt_no,
                "status": "generated",
                "format": "unified_diff",
                "content": candidate_patch,
                "content_hash": _hash_text(candidate_patch),
                "explanation": explanation,
                "risk_level": "medium",
                "target_files": [_resolve_target_file(state["issues"])],
                "strategy_used": "llm_generation",
                "memory_case_ids": [str(item.get("case_id")) for item in state["memory_matches"] if item.get("case_id")],
            }
            attempt = _build_attempt_record(attempt_no, patch_artifact["patch_id"], "generated", None, None)
            return {
                "ok": True,
                "patch_artifact": patch_artifact,
                "attempt": attempt,
                "llm_trace": llm_trace,
                "tool_trace": tool_trace,
                "selected_context": state["selected_context"],
                "memory_hits": {"cases": state["memory_matches"], "standards": state["standards_matches"]},
                "issues": state["issues"],
                "symbols": state["symbols"],
                "context_summary": state["context_summary"],
                "repair_plan": state["repair_plan"],
                "issue_graph": state["issue_graph"],
                "planner_summary": state["planner_summary"],
                "action_history": prompt_history,
            }

        if next_action == "fail":
            return _failed_output(
                attempt_no=attempt_no,
                reason="llm_declared_failure",
                detail=explanation or "LLM orchestrator requested failure.",
                llm_trace=llm_trace,
                tool_trace=tool_trace,
                selected_context=state["selected_context"],
                memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
                issues=state["issues"],
                symbols=state["symbols"],
                context_summary=state["context_summary"],
                repair_plan=state["repair_plan"],
                issue_graph=state["issue_graph"],
                planner_summary=state["planner_summary"],
                action_history=prompt_history,
            )

        handler = tool_handlers.get(next_action)
        if handler is None:
            return _failed_output(
                attempt_no=attempt_no,
                reason="unknown_action",
                detail=f"Unsupported action: {next_action}",
                llm_trace=llm_trace,
                tool_trace=tool_trace,
                selected_context=state["selected_context"],
                memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
                issues=state["issues"],
                symbols=state["symbols"],
                context_summary=state["context_summary"],
                repair_plan=state["repair_plan"],
                issue_graph=state["issue_graph"],
                planner_summary=state["planner_summary"],
                action_history=prompt_history,
            )

        started = time.perf_counter()
        tool_output = handler(action_args)
        latency_ms = int((time.perf_counter() - started) * 1000)
        tool_success = bool(tool_output.get("ok", True))
        tool_trace.append(
            {
                "tool_name": next_action,
                "args": action_args,
                "success": tool_success,
                "latency_ms": latency_ms,
                "selected_by": "llm",
                "expected_tool": next_action,
                "phase": f"action_loop_step_{step_no}",
                "result_preview": _preview(tool_output),
            }
        )

        prompt_history.append(
            {
                "step": step_no,
                "thought_summary": action.get("thought_summary"),
                "next_action": next_action,
                "action_args": action_args,
                "need_more_context": bool(action.get("need_more_context", False)),
                "tool_result": _preview(tool_output),
            }
        )

    return _failed_output(
        attempt_no=attempt_no,
        reason="action_loop_exhausted",
        detail="LLM did not produce a valid patch within the maximum action steps.",
        llm_trace=llm_trace,
        tool_trace=tool_trace,
        selected_context=state["selected_context"],
        memory_hits={"cases": state["memory_matches"], "standards": state["standards_matches"]},
        issues=state["issues"],
        symbols=state["symbols"],
        context_summary=state["context_summary"],
        repair_plan=state["repair_plan"],
        issue_graph=state["issue_graph"],
        planner_summary=state["planner_summary"],
        action_history=prompt_history,
    )


def _request_action(*, llm_client: Any, messages: list[dict[str, str]], options: dict[str, Any]) -> dict[str, Any]:
    tool_mode = str(options.get("llm_tool_mode") or "auto").strip().lower() or "auto"
    tools = _tool_specs()
    llm_result = llm_client.create_chat_completion(
        phase="fixer_orchestrator",
        prompt_name="fixer_action_loop",
        messages=messages,
        stream=False,
        json_mode=True,
        tool_mode=tool_mode,
        tools=tools,
    )

    llm_trace = [llm_result.trace]
    if not llm_result.ok:
        return {"ok": False, "detail": llm_result.error or "LLM call failed", "llm_trace": llm_trace}

    if llm_result.tool_calls:
        call = llm_result.tool_calls[0]
        fn = call.get("function") if isinstance(call.get("function"), dict) else {}
        action_args = _safe_json(str(fn.get("arguments") or "{}"))
        action = {
            "thought_summary": llm_result.content or "provider-native tool call",
            "next_action": str(fn.get("name") or ""),
            "action_args": action_args,
            "need_more_context": True,
            "candidate_patch": None,
            "explanation": llm_result.content or "",
        }
        return {"ok": True, "action": action, "llm_trace": llm_trace}

    payload = _safe_json(llm_result.content)
    if not payload:
        return {"ok": False, "detail": "LLM did not return valid JSON action", "llm_trace": llm_trace}
    if "next_action" not in payload:
        return {"ok": False, "detail": "LLM JSON missing next_action", "llm_trace": llm_trace}
    return {"ok": True, "action": payload, "llm_trace": llm_trace}


def _tool_analyze_ast(state: dict[str, Any]) -> dict[str, Any]:
    ast_result = parse_java_code(state["code_text"])
    symbols_result = build_symbol_graph(state["code_text"], ast_result)
    semgrep_result = run_semgrep(state["code_text"], language="java")
    merged = compose_day2_output(
        language="java",
        ast_result=ast_result,
        symbol_graph_result=symbols_result,
        semgrep_result=semgrep_result,
    )
    state["issues"] = merged["issues"]
    state["symbols"] = merged["symbols"]
    state["context_summary"] = merged["contextSummary"]
    return {
        "ok": True,
        "issues_count": len(state["issues"]),
        "symbols_count": len(state["symbols"]),
    }


def _tool_run_semgrep(state: dict[str, Any]) -> dict[str, Any]:
    semgrep_result = run_semgrep(state["code_text"], language="java")
    state["issues"] = semgrep_result.get("issues", [])
    return {"ok": True, "issues_count": len(state["issues"])}


def _tool_build_issue_graph(state: dict[str, Any]) -> dict[str, Any]:
    planner_output = run_planner_agent(
        issues=state["issues"],
        symbols=state["symbols"],
        context_summary=state["context_summary"],
    )
    state["issue_graph"] = planner_output["issue_graph"]
    state["repair_plan"] = planner_output["repair_plan"]
    state["planner_summary"] = planner_output["planner_summary"]
    return {
        "ok": True,
        "nodes": len(state["issue_graph"].get("nodes", [])),
        "plans": len(state["repair_plan"]),
    }


def _tool_resolve_symbol(state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    name = str(args.get("name") or "").strip().lower()
    matches = []
    for symbol in state.get("symbols", []):
        if name and name in str(symbol.get("name") or "").lower():
            matches.append(symbol)
    return {"ok": True, "matches": matches[:8]}


def _tool_fetch_context(state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    line = int(args.get("line") or 1)
    window = int(args.get("window") or 8)
    lines = state["code_text"].splitlines()
    start = max(1, line - window)
    end = min(len(lines), line + window)
    snippet = "\n".join(lines[start - 1 : end])
    item = {
        "kind": "issue_vicinity",
        "line": line,
        "start": start,
        "end": end,
        "snippet": snippet,
        "tokens": max(1, int(len(snippet) / 4)),
    }
    state["selected_context"].append(item)
    return {"ok": True, "context": item}


def _tool_get_repo_profile(state: dict[str, Any]) -> dict[str, Any]:
    profile = state.get("repo_profile", {})
    return {"ok": True, "repo_profile": profile}


def _tool_search_case_memory(state: dict[str, Any]) -> dict[str, Any]:
    cases = retrieve_case_matches(
        issues=state.get("issues", []),
        repair_plan=state.get("repair_plan", []),
        symbols=state.get("symbols", []),
        context_summary=state.get("context_summary", {}),
        top_k=3,
    )
    state["memory_matches"] = cases
    return {"ok": True, "matches": cases}


def _tool_search_short_term_memory(state: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "latest_verifier_failure": state.get("last_failure", {})}


def _tool_apply_patch(state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    patch = str(args.get("patch") or "")
    stage = apply_patch_to_snippet(
        original_code=state["code_text"],
        patch_content=patch,
        target_file=_resolve_target_file(state.get("issues", [])),
    )
    return {
        "ok": stage.get("status") == "passed",
        "status": stage.get("status"),
        "stderr_summary": stage.get("stderr_summary"),
    }


def _tool_compile_java(state: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    code = str(args.get("code_text") or state["code_text"])
    stage = compile_java_snippet(code_text=code, file_name="snippet.java")
    return {
        "ok": stage.get("status") == "passed",
        "status": stage.get("status"),
        "stderr_summary": stage.get("stderr_summary"),
    }


def _tool_lint_java(state: dict[str, Any], args: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    stage = run_lint_stage(options=options, repo_profile=state.get("repo_profile", {}), working_directory=None)
    return {"ok": stage.get("status") in {"passed", "skipped"}, "status": stage.get("status")}


def _tool_run_tests(state: dict[str, Any], args: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    stage = run_test_stage(options=options, repo_profile=state.get("repo_profile", {}), working_directory=None)
    return {"ok": stage.get("status") in {"passed", "skipped"}, "status": stage.get("status")}


def _tool_security_rescan(state: dict[str, Any], args: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    stage = run_security_rescan_stage(options=options, working_directory=None)
    return {"ok": stage.get("status") in {"passed", "skipped"}, "status": stage.get("status")}


def _tool_specs() -> list[dict[str, Any]]:
    specs = []
    for name in [
        "build_issue_graph",
        "analyze_ast",
        "run_semgrep",
        "resolve_symbol",
        "fetch_context",
        "get_repo_profile",
        "search_case_memory",
        "search_short_term_memory",
        "apply_patch",
        "compile_java",
        "lint_java",
        "run_tests",
        "security_rescan",
    ]:
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Sentinel tool {name}",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": True},
                },
            }
        )
    return specs


def _load_standards(code_text: str, message_text: str | None, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query = " ".join(
        [
            message_text or "",
            code_text[:400],
            " ".join(str(item.get("message") or "") for item in issues[:5]),
        ]
    ).strip()
    if not query:
        return []
    return search_standards(query, limit=3)


def _validate_patch(patch: str, last_failure: dict[str, Any], tool_trace: list[dict[str, Any]]) -> dict[str, str] | None:
    if not _is_valid_unified_diff(patch):
        return {"reason": "invalid_diff", "detail": "candidate_patch is not a valid unified diff"}
    if not _is_meaningful_patch(patch):
        return {"reason": "no_valid_patch", "detail": "candidate_patch is whitespace/no-op/comment-only"}
    previous_hash = _resolve_previous_patch_hash(last_failure)
    if previous_hash and previous_hash == _hash_text(patch):
        return {"reason": "duplicate_patch_candidate", "detail": "candidate_patch duplicates previous patch"}
    if len(tool_trace) == 0:
        return {"reason": "insufficient_context", "detail": "at least one tool call is required before finalize_patch"}
    return None


def _resolve_target_file(issues: list[dict[str, Any]]) -> str:
    for issue in issues:
        file_path = str(issue.get("file_path") or issue.get("filePath") or "").strip()
        if file_path:
            return file_path.replace("\\", "/")
    return "snippet.java"


def _is_valid_unified_diff(content: str) -> bool:
    lines = content.splitlines()
    if len(lines) < 3:
        return False
    return lines[0].startswith("diff --git a/") and lines[1].startswith("--- a/") and lines[2].startswith("+++ b/")


def _is_meaningful_patch(content: str) -> bool:
    for line in content.splitlines():
        if not line.startswith("+") and not line.startswith("-"):
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        payload = line[1:].strip()
        if not payload:
            continue
        if payload.startswith("//") or payload.startswith("/*") or payload.startswith("*"):
            continue
        return True
    return False


def _resolve_previous_patch_hash(last_failure: dict[str, Any]) -> str | None:
    hash_value = str(last_failure.get("previous_patch_hash") or "").strip()
    if hash_value:
        return hash_value
    content = str(last_failure.get("previous_patch_content") or "")
    if content:
        return _hash_text(content)
    return None


def _build_attempt_record(attempt_no: int, patch_id: str, status: str, reason: str | None, detail: str | None) -> dict[str, Any]:
    return {
        "attempt_no": attempt_no,
        "patch_id": patch_id,
        "status": status,
        "verified_level": "L0",
        "failure_stage": "fixer" if status == "failed" else None,
        "failure_reason": reason,
        "failure_detail": detail,
        "memory_case_ids": [],
    }


def _failed_output(
    *,
    attempt_no: int,
    reason: str,
    detail: str,
    llm_trace: list[dict[str, Any]],
    tool_trace: list[dict[str, Any]],
    selected_context: list[dict[str, Any]],
    memory_hits: dict[str, Any],
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    repair_plan: list[dict[str, Any]],
    issue_graph: dict[str, Any],
    planner_summary: dict[str, Any],
    action_history: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": False,
        "patch_artifact": None,
        "attempt": _build_attempt_record(attempt_no, f"patch_attempt_{attempt_no}", "failed", reason, detail),
        "llm_trace": llm_trace,
        "tool_trace": tool_trace,
        "selected_context": selected_context,
        "memory_hits": memory_hits,
        "issues": issues,
        "symbols": symbols,
        "context_summary": context_summary,
        "repair_plan": repair_plan,
        "issue_graph": issue_graph,
        "planner_summary": planner_summary,
        "action_history": action_history,
    }


def _safe_json(content: str) -> dict[str, Any]:
    raw = str(content or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _preview(value: Any) -> Any:
    if isinstance(value, dict):
        keys = list(value.keys())[:8]
        return {k: value.get(k) for k in keys}
    if isinstance(value, list):
        return value[:3]
    return value
