from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph
from memory import load_conversation_short_term_memory

from .context_budget import initialize_context_budget, register_loaded_context
from .mcp_client import McpClient, build_mcp_base_url
from .events import build_event
from .failure_taxonomy import build_failure_taxonomy
from .schemas import EngineState, InternalReviewRunRequest, PythonEngineEvent, default_issue_graph, default_planner_summary

SEMGREP_WARNING_CODES = {"SEMGREP_UNAVAILABLE", "SEMGREP_TIMEOUT", "SEMGREP_EXEC_ERROR"}


@dataclass
class EngineOps:
    validate_day2_input: Callable[[str, str], list[dict[str, Any]]]
    parse_java_code: Callable[[str], dict[str, Any]]
    build_symbol_graph: Callable[[str, dict[str, Any]], dict[str, Any]]
    run_semgrep: Callable[[str, str], dict[str, Any]]
    compose_day2_output: Callable[..., dict[str, Any]]
    run_planner_agent: Callable[..., dict[str, Any]]
    retrieve_case_matches: Callable[..., list[dict[str, Any]]]
    search_standards: Callable[..., list[dict[str, Any]]]
    run_fixer_agent: Callable[..., dict[str, Any]]
    run_verifier_agent: Callable[..., dict[str, Any]]
    build_review_completed_payload: Callable[[EngineState], dict[str, Any]]
    resolve_repo_profile: Callable[..., dict[str, Any]]
    summarize_repo_profile: Callable[[dict[str, Any] | None], dict[str, Any]]
    update_short_term_memory: Callable[..., dict[str, Any]]
    get_latest_verifier_failure: Callable[[dict[str, Any] | None], dict[str, Any] | None]
    promote_patch_from_verification: Callable[..., dict[str, Any] | None]


def bootstrap_state(request: InternalReviewRunRequest) -> dict[str, Any]:
    options = dict(request.options or {})
    if not isinstance(options.get("llm_trace"), list):
        options["llm_trace"] = []
    short_term_memory = (
        load_conversation_short_term_memory(request.conversation_id)
        if request.conversation_id
        else {}
    )
    return EngineState(
        task_id=request.task_id,
        conversation_id=request.conversation_id,
        message_id=request.message_id,
        parent_message_id=request.parent_message_id,
        message_text=request.message_text,
        code_text=request.code_text,
        language=request.language,
        issues=[],
        symbols=[],
        context_summary={},
        analyzer_summary={},
        diagnostics=[],
        issue_graph=default_issue_graph(),
        repair_plan=[],
        planner_summary=default_planner_summary(),
        memory_matches=[],
        short_term_memory=short_term_memory,
        repo_profile={},
        case_store_summary={"source": "jsonl", "promotion_candidate": False},
        patch_artifact=None,
        attempts=[],
        patch=None,
        verification_result=None,
        context_budget=initialize_context_budget(options),
        selected_context=[],
        memory_hits={},
        tool_trace=[],
        llm_trace=[],
        action_history=[],
        options=options,
        metadata=request.metadata or {},
        debug_enabled=bool(options.get("debug", False)),
        enable_verifier=bool(options.get("enable_verifier", False)),
        enable_security_rescan=bool(options.get("enable_security_rescan", False)),
        max_retries=_to_int(options.get("max_retries"), default=2),
        final_status="running",
        events=[],
        retry_count=0,
        no_fix_needed=False,
    ).model_dump()


def build_langgraph(ops: EngineOps):
    graph = StateGraph(dict)
    graph.add_node("bootstrap", _bootstrap_node(ops))
    graph.add_node("analyzer", _analyzer_node(ops))
    graph.add_node("planner", _planner_node(ops))
    graph.add_node("memory_context", _memory_node(ops))
    graph.add_node("fixer", _fixer_node(ops))
    graph.add_node("verifier", _verifier_node(ops))
    graph.add_node("retry_reflection", _retry_reflection_node(ops))
    graph.add_node("retry_router", _retry_router_node())
    graph.add_node("reporter", _reporter_node(ops))

    graph.set_entry_point("bootstrap")
    graph.add_edge("bootstrap", "analyzer")
    graph.add_conditional_edges("analyzer", _route_after_analyzer, {"planner": "planner", "reporter": "reporter"})
    graph.add_edge("planner", "memory_context")
    graph.add_edge("memory_context", "fixer")
    graph.add_conditional_edges("fixer", _route_after_fixer, {"verifier": "verifier", "reporter": "reporter"})
    graph.add_conditional_edges(
        "verifier",
        _route_after_verifier,
        {"retry_reflection": "retry_reflection", "reporter": "reporter"},
    )
    graph.add_edge("retry_reflection", "retry_router")
    graph.add_conditional_edges(
        "retry_router",
        _route_after_retry,
        {"memory_context": "memory_context", "reporter": "reporter"},
    )
    graph.add_edge("reporter", END)
    return graph.compile()


async def run_langgraph_state_graph(
    request: InternalReviewRunRequest,
    *,
    ops: EngineOps,
) -> AsyncIterator[PythonEngineEvent]:
    state = bootstrap_state(request)
    app = build_langgraph(ops)
    _record_debug_event(
        state,
        "langgraph_compiled",
        "langgraph compiled",
        {
            "source": "python-engine",
            "stage": "langgraph",
            "graph_name": "day6_flow",
            "entry_point": "bootstrap",
        },
    )

    emitted = 0
    try:
        async for update in app.astream(state, stream_mode="updates"):
            for node_name, delta in update.items():
                for key, value in delta.items():
                    state[key] = value
                _record_debug_event(
                    state,
                    "langgraph_node_completed",
                    "langgraph node completed",
                    {
                        "source": "python-engine",
                        "stage": "langgraph",
                        "node_name": node_name,
                        "attempt_no": _attempt_no(state),
                        "state_delta_keys": sorted(list(delta.keys())),
                    },
                )
                all_events = list(state.get("events", []))
                while emitted < len(all_events):
                    raw_event = all_events[emitted]
                    emitted += 1
                    yield PythonEngineEvent.model_validate(raw_event)
    except Exception as exc:
        state["final_status"] = "failed"
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="review_failed",
                message="review failed",
                status="FAILED",
                payload={
                    "source": "python-engine",
                    "stage": "state_graph",
                    "errorType": exc.__class__.__name__,
                    "error": str(exc),
                    "diagnostics": state.get("diagnostics", []),
                },
            ),
        )
        all_events = list(state.get("events", []))
        while emitted < len(all_events):
            raw_event = all_events[emitted]
            emitted += 1
            yield PythonEngineEvent.model_validate(raw_event)


def _bootstrap_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "bootstrap", "attempt_no": _attempt_no(state)},
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="analysis_started",
                message="python engine started analyzer state graph",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "bootstrap_state", "language": state["language"]},
            ),
        )
        _record_execution_stage(
            state,
            stage_id="intake_received",
            status="running",
            summary="Request received and bootstrap state initialized.",
        )
        if state.get("context_budget"):
            _record_debug_event(
                state,
                "context_budget_initialized",
                "context budget initialized",
                {"source": "python-engine", "stage": "context_budget", "context_budget": state["context_budget"]},
            )
        user_constraints = str(state.get("message_text") or "").strip()
        if user_constraints:
            state["short_term_memory"] = ops.update_short_term_memory(
                state,
                snapshot_type="user_constraints",
                payload={
                    "message_text": user_constraints,
                    "message_id": state.get("message_id"),
                    "parent_message_id": state.get("parent_message_id"),
                },
            )
        state["short_term_memory"] = ops.update_short_term_memory(
            state,
            snapshot_type="latest_code",
            payload={
                "code_text": state.get("code_text", ""),
                "language": state.get("language", "java"),
                "task_id": state.get("task_id"),
            },
        )
        _record_execution_stage(
            state,
            stage_id="intake_received",
            status="passed",
            summary="Bootstrap completed.",
        )
        return _full_state(state)

    return _node


def _analyzer_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_execution_stage(
            state,
            stage_id="analyzer_running",
            status="running",
            summary="Analyzer is parsing syntax, symbols, and diagnostics.",
        )
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "analyzer", "attempt_no": _attempt_no(state)},
        )
        validation_diagnostics = ops.validate_day2_input(state["code_text"], state["language"])
        if validation_diagnostics:
            state["diagnostics"] = validation_diagnostics
            state["final_status"] = "failed"
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="review_failed",
                    message="review failed",
                    status="FAILED",
                    payload={"source": "python-engine", "stage": "input_validation", "diagnostics": state["diagnostics"]},
                ),
            )
            return _full_state(state)

        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="ast_parsing_started",
                message="ast parsing started",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "ast", "language": str(state["language"]).lower()},
            ),
        )
        ast_result = ops.parse_java_code(state["code_text"])
        state["diagnostics"] = list(state.get("diagnostics", [])) + list(ast_result.get("diagnostics", []) or [])
        ast_summary = ast_result.get("summary", {}) or {}
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="ast_parsing_completed",
                message="ast parsing completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "ast",
                    "language": str(state["language"]).lower(),
                    "classesCount": int(ast_summary.get("classesCount", 0)),
                    "methodsCount": int(ast_summary.get("methodsCount", 0)),
                    "fieldsCount": int(ast_summary.get("fieldsCount", 0)),
                    "importsCount": int(ast_summary.get("importsCount", 0)),
                    "hasParseErrors": bool(ast_result.get("errors")),
                    "parseErrorsCount": len(ast_result.get("errors", []) or []),
                    "syntaxIssuesCount": len(ast_result.get("syntaxIssues", []) or []),
                },
            ),
        )

        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="symbol_graph_started",
                message="symbol graph build started",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "symbol_graph"},
            ),
        )
        symbol_result = ops.build_symbol_graph(state["code_text"], ast_result)
        state["diagnostics"] = list(state["diagnostics"]) + list(symbol_result.get("diagnostics", []) or [])
        symbol_summary = symbol_result.get("summary", {}) or {}
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="symbol_graph_completed",
                message="symbol graph build completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "symbol_graph",
                    "symbolsCount": len(symbol_result.get("symbols", []) or []),
                    "callEdgesCount": int(symbol_summary.get("callEdgesCount", 0)),
                    "variableRefsCount": int(symbol_summary.get("variableRefsCount", 0)),
                },
            ),
        )

        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="semgrep_scan_started",
                message="semgrep scan started",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "semgrep", "ruleset": "auto"},
            ),
        )
        semgrep_result = ops.run_semgrep(state["code_text"], language=str(state["language"]).lower())
        semgrep_diagnostics = semgrep_result.get("diagnostics", []) or []
        state["diagnostics"] = list(state["diagnostics"]) + list(semgrep_diagnostics)
        semgrep_summary = semgrep_result.get("summary", {}) or {}
        warning = next((item for item in semgrep_diagnostics if item.get("code") in SEMGREP_WARNING_CODES), None)
        if warning:
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="semgrep_scan_warning",
                    message="semgrep scan warning",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "semgrep",
                        "ruleset": semgrep_summary.get("ruleset", "auto"),
                        "issuesCount": int(semgrep_summary.get("issuesCount", 0)),
                        "code": warning.get("code"),
                        "message": warning.get("message"),
                    },
                ),
            )
        else:
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="semgrep_scan_completed",
                    message="semgrep scan completed",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "semgrep",
                        "ruleset": semgrep_summary.get("ruleset", "auto"),
                        "issuesCount": int(semgrep_summary.get("issuesCount", 0)),
                        "severityBreakdown": semgrep_summary.get("severityBreakdown", {}),
                    },
                ),
            )

        analyzer_output = ops.compose_day2_output(
            language=state["language"],
            ast_result=ast_result,
            symbol_graph_result=symbol_result,
            semgrep_result=semgrep_result,
        )
        state["issues"] = analyzer_output["issues"]
        state["symbols"] = analyzer_output["symbols"]
        state["context_summary"] = analyzer_output["contextSummary"]
        state["analyzer_summary"] = analyzer_output["analyzerSummary"]
        state["diagnostics"] = analyzer_output["diagnostics"]

        state["short_term_memory"] = ops.update_short_term_memory(
            state,
            snapshot_type="analyzer_evidence",
            payload={
                "issues": state["issues"],
                "symbols": state["symbols"],
                "context_summary": state["context_summary"],
                "diagnostics": state["diagnostics"],
            },
        )
        _record_debug_event(
            state,
            "short_term_memory_updated",
            "short term memory updated",
            {"source": "python-engine", "stage": "memory", "snapshot_type": "analyzer_evidence", "summary": {"issue_count": len(state["issues"])}},
        )

        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="analyzer_completed",
                message="analyzer completed",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "analyzer_pipeline", "analyzerSummary": state["analyzer_summary"]},
            ),
        )
        allow_no_fix_needed = bool(state.get("options", {}).get("allow_no_fix_needed", False))
        has_user_constraints = bool(str(state.get("message_text") or "").strip())
        state["no_fix_needed"] = bool(allow_no_fix_needed and len(state["issues"]) == 0 and not has_user_constraints)
        _record_execution_stage(
            state,
            stage_id="analyzer_running",
            status="passed",
            summary=f"Analyzer completed with {len(state['issues'])} detected issues.",
        )
        return _full_state(state)

    return _node


def _planner_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_execution_stage(
            state,
            stage_id="issue_graph_building",
            status="running",
            summary="Building issue graph and repair batches.",
        )
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "planner", "attempt_no": _attempt_no(state)},
        )
        if state.get("no_fix_needed"):
            return _full_state(state)
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="planner_started",
                message="planner started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "inputIssueCount": len(state.get("issues", [])),
                    "inputSymbolCount": len(state.get("symbols", [])),
                },
            ),
        )
        planner_output = ops.run_planner_agent(
            issues=state.get("issues", []),
            symbols=state.get("symbols", []),
            context_summary=state.get("context_summary", {}),
        )
        state["issue_graph"] = planner_output["issue_graph"]
        state["repair_plan"] = planner_output["repair_plan"]
        state["planner_summary"] = planner_output["planner_summary"]
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="issue_graph_built",
                message="issue graph built",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "issue_graph": state["issue_graph"],
                    "issueCount": len(state["issue_graph"].get("nodes", [])),
                    "edgeCount": len(state["issue_graph"].get("edges", [])),
                },
            ),
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="repair_plan_created",
                message="repair plan created",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "planner", "repair_plan": state["repair_plan"], "planCount": len(state["repair_plan"])},
            ),
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="planner_completed",
                message="planner completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "issueCount": len(state["issue_graph"].get("nodes", [])),
                    "planCount": len(state["repair_plan"]),
                    "plannerSummary": state["planner_summary"],
                },
            ),
        )
        _record_execution_stage(
            state,
            stage_id="issue_graph_building",
            status="passed",
            summary=f"Issue graph ready with {len(state['repair_plan'])} repair tasks.",
        )
        return _full_state(state)

    return _node


def _memory_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_execution_stage(
            state,
            stage_id="context_loading",
            status="running",
            summary="Loading context within token budget.",
        )
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "memory_retrieval", "attempt_no": _attempt_no(state)},
        )
        if state.get("no_fix_needed"):
            return _full_state(state)
        attempt_no = _attempt_no(state)
        _record_execution_stage(
            state,
            stage_id="memory_matching",
            status="running",
            summary="Matching similar historical repair cases.",
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="case_memory_search_started",
                message="case memory search started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "memory",
                    "attempt_no": attempt_no,
                    "issue_count": len(state.get("issues", [])),
                    "strategy_hints": [str(item.get("strategy") or "") for item in state.get("repair_plan", [])],
                },
            ),
        )
        state["memory_matches"] = ops.retrieve_case_matches(
            issues=state.get("issues", []),
            repair_plan=state.get("repair_plan", []),
            symbols=state.get("symbols", []),
            context_summary=state.get("context_summary", {}),
            top_k=3,
        )
        if state["memory_matches"]:
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="case_memory_matched",
                    message="case memory matched",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "memory",
                        "attempt_no": attempt_no,
                        "match_count": len(state["memory_matches"]),
                        "matches": state["memory_matches"],
                    },
                ),
            )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="case_memory_completed",
                message="case memory completed",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "memory", "attempt_no": attempt_no, "match_count": len(state["memory_matches"])},
            ),
        )
        _record_execution_stage(
            state,
            stage_id="memory_matching",
            status="passed",
            summary=f"Case memory matched {len(state['memory_matches'])} candidates.",
        )
        state["repo_profile"] = ops.resolve_repo_profile(state.get("metadata", {}), state.get("options", {})) or {}
        if state["repo_profile"]:
            _record_debug_event(
                state,
                "repo_memory_loaded",
                "repo memory loaded",
                {
                    "source": "python-engine",
                    "stage": "memory",
                    "repo_profile_id": state.get("metadata", {}).get("repo_profile_id"),
                    "summary": ops.summarize_repo_profile(state["repo_profile"]),
                },
            )
        budget = state.get("context_budget", {})
        selected_context: list[dict[str, Any]] = []
        if budget:
            summary_item = {
                "source_id": f"ctx-{attempt_no}-summary",
                "kind": "summary",
                "path": "snippet.java",
                "content": str(state.get("context_summary", {})),
                "token_count": max(1, int(len(str(state.get("context_summary", {}))) / 4)),
                "reason": "planner summary first",
            }
            updated, exhausted = register_loaded_context(budget, source_item=summary_item, load_stage="summary")
            state["context_budget"] = updated
            selected_context.append(summary_item)
            if not exhausted:
                focus_line = _resolve_focus_line_from_issues(state.get("issues", []))
                snippet_item = _build_local_snippet_context(
                    code_text=str(state.get("code_text") or ""),
                    focus_line=focus_line,
                    window=12,
                    source_id=f"ctx-{attempt_no}-snippet",
                )
                updated, exhausted = register_loaded_context(updated, source_item=snippet_item, load_stage="issue_snippet")
                state["context_budget"] = updated
                selected_context.append(snippet_item)
            state["selected_context"] = selected_context
            _record_debug_event(
                state,
                "context_budget_updated",
                "context budget updated",
                {"source": "python-engine", "stage": "context_budget", "context_budget": state["context_budget"]},
            )
            if exhausted:
                _record_debug_event(
                    state,
                    "context_budget_exhausted",
                    "context budget exhausted",
                    {
                        "source": "python-engine",
                        "stage": "context_budget",
                        "reason": "remaining_tokens=0",
                        "context_budget": state["context_budget"],
                    },
                )
            state["short_term_memory"] = ops.update_short_term_memory(
                state,
                snapshot_type="token_usage",
                payload={"used_tokens": state["context_budget"].get("used_tokens", 0)},
            )

        if bool(state.get("options", {}).get("enable_mcp", False)):
            client = McpClient(base_url=build_mcp_base_url(state.get("metadata", {})))
            focus_line = _resolve_focus_line_from_issues(state.get("issues", []))
            start_line = max(1, focus_line - 10)
            end_line = focus_line + 10
            envelope, trace_item = client.get_resource(
                "file",
                query={
                    "taskId": state["task_id"],
                    "path": "snippet.java",
                    "startLine": start_line,
                    "endLine": end_line,
                },
            )
            trace_item["selected_by"] = "context_broker"
            state["tool_trace"] = list(state.get("tool_trace", [])) + [trace_item]
            data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
            mcp_content = str(data.get("content") or "").strip()
            if mcp_content:
                state["selected_context"] = list(state.get("selected_context", [])) + [
                    {
                        "source_id": f"ctx-{attempt_no}-mcp-file",
                        "kind": "mcp_file_window",
                        "path": str(data.get("path") or "snippet.java"),
                        "startLine": int(data.get("startLine") or start_line),
                        "endLine": int(data.get("endLine") or end_line),
                        "content": mcp_content,
                        "token_count": max(1, int(len(mcp_content) / 4)),
                        "reason": "mcp evidence",
                    }
                ]
            _record_debug_event(
                state,
                "mcp_resource_completed",
                "mcp file resource completed",
                {
                    "source": "backend-mcp",
                    "stage": "mcp",
                    "resource_name": "file",
                    "request_id": envelope.get("request_id"),
                    "ok": envelope.get("ok", False),
                    "latency_ms": (envelope.get("meta", {}) or {}).get("latency_ms", 0),
                },
            )

        _record_execution_stage(
            state,
            stage_id="context_loading",
            status="passed",
            summary=f"Context ready with {len(state.get('selected_context', []))} selected slices.",
        )
        _record_execution_stage(
            state,
            stage_id="standards_retrieving",
            status="running",
            summary="Retrieving standards knowledge hits.",
        )
        standards_query = " ".join(
            [
                str(state.get("message_text") or ""),
                " ".join(str(item.get("message") or "") for item in state.get("issues", [])[:5]),
                str(state.get("code_text") or "")[:400],
            ]
        ).strip()
        standards_hits = ops.search_standards(standards_query, limit=3) if standards_query else []
        state["standards_hits"] = [item for item in standards_hits if isinstance(item, dict)]
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="standards_hits_updated",
                message="standards hits updated",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "standards",
                    "hit_count": len(state["standards_hits"]),
                    "sources": sorted(
                        {str(item.get("source") or "unknown") for item in state["standards_hits"]}
                    ),
                },
            ),
        )
        _record_execution_stage(
            state,
            stage_id="standards_retrieving",
            status="passed",
            summary=f"Retrieved {len(state['standards_hits'])} standards hits.",
            details={"hit_count": len(state["standards_hits"])},
        )
        return _full_state(state)

    return _node


def _fixer_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_execution_stage(
            state,
            stage_id="fixer_generating_patch",
            status="running",
            summary="LLM is generating a patch from evidence and constraints.",
        )
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "fixer", "attempt_no": _attempt_no(state)},
        )
        if state.get("no_fix_needed"):
            return _full_state(state)
        attempt_no = _attempt_no(state)
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="fixer_started",
                message="fixer started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "fixer",
                    "attempt_no": attempt_no,
                    "plan_count": len(state.get("repair_plan", [])),
                    "memory_match_count": len(state.get("memory_matches", [])),
                    "retry_count": state.get("retry_count", 0),
                },
            ),
        )
        fixer_output = ops.run_fixer_agent(
            code_text=state["code_text"],
            repair_plan=state.get("repair_plan", []),
            issues=state.get("issues", []),
            symbols=state.get("symbols", []),
            context_summary=state.get("context_summary", {}),
            memory_matches=state.get("memory_matches", []),
            attempt_no=attempt_no,
            last_failure=ops.get_latest_verifier_failure(state.get("short_term_memory")),
            selected_context=state.get("selected_context", []),
            repo_profile=state.get("repo_profile", {}),
            options=state.get("options", {}),
            message_text=state.get("message_text"),
            action_history=state.get("action_history", []),
            standards_matches=state.get("standards_hits", []),
            retry_hints=state.get("retry_hints", {}),
        )
        if isinstance(fixer_output.get("llm_trace"), list):
            state["llm_trace"] = list(state.get("llm_trace", [])) + [
                item for item in fixer_output.get("llm_trace", []) if isinstance(item, dict)
            ]
            options = dict(state.get("options", {}))
            options["llm_trace"] = state["llm_trace"]
            state["options"] = options
        if isinstance(fixer_output.get("tool_trace"), list):
            state["tool_trace"] = list(state.get("tool_trace", [])) + [
                item for item in fixer_output.get("tool_trace", []) if isinstance(item, dict)
            ]
        if isinstance(fixer_output.get("selected_context"), list):
            state["selected_context"] = [item for item in fixer_output["selected_context"] if isinstance(item, dict)]
        if isinstance(fixer_output.get("memory_hits"), dict):
            state["memory_hits"] = dict(fixer_output["memory_hits"])
            cases = state["memory_hits"].get("cases")
            if isinstance(cases, list):
                state["memory_matches"] = [item for item in cases if isinstance(item, dict)]
        if isinstance(fixer_output.get("issues"), list):
            state["issues"] = [item for item in fixer_output["issues"] if isinstance(item, dict)]
        if isinstance(fixer_output.get("symbols"), list):
            state["symbols"] = [item for item in fixer_output["symbols"] if isinstance(item, dict)]
        if isinstance(fixer_output.get("context_summary"), dict):
            state["context_summary"] = dict(fixer_output["context_summary"])
        if isinstance(fixer_output.get("repair_plan"), list):
            state["repair_plan"] = [item for item in fixer_output["repair_plan"] if isinstance(item, dict)]
        if isinstance(fixer_output.get("issue_graph"), dict):
            state["issue_graph"] = dict(fixer_output["issue_graph"])
        if isinstance(fixer_output.get("planner_summary"), dict):
            state["planner_summary"] = dict(fixer_output["planner_summary"])
        if isinstance(fixer_output.get("action_history"), list):
            state["action_history"] = [item for item in fixer_output["action_history"] if isinstance(item, dict)]
        state["latest_fixer_output"] = fixer_output
        state["patch_artifact"] = fixer_output.get("patch_artifact")
        state["patch"] = state["patch_artifact"]
        if not fixer_output.get("ok", False):
            failed_attempt = {**(fixer_output.get("attempt", {}) or {}), "status": "failed", "verified_level": "L0"}
            state["attempts"] = list(state.get("attempts", [])) + [failed_attempt]
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="fixer_failed",
                    message="fixer failed",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "fixer",
                        "attempt_no": attempt_no,
                        "reason": failed_attempt.get("failure_reason"),
                        "failure_detail": failed_attempt.get("failure_detail"),
                        "retryable": False,
                    },
                ),
            )
            _record_execution_stage(
                state,
                stage_id="fixer_generating_patch",
                status="failed",
                summary="Patch generation failed.",
                details={
                    "failure_reason": failed_attempt.get("failure_reason"),
                    "failure_detail": failed_attempt.get("failure_detail"),
                },
            )
            return _full_state(state)

        state["short_term_memory"] = ops.update_short_term_memory(state, snapshot_type="patch", payload=state["patch_artifact"] or {})
        _record_debug_event(
            state,
            "short_term_memory_updated",
            "short term memory updated",
            {"source": "python-engine", "stage": "memory", "snapshot_type": "patch", "summary": {"attempt_no": attempt_no}},
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="patch_generated",
                message="patch generated",
                status="RUNNING",
                payload={"source": "python-engine", "stage": "fixer", "attempt_no": attempt_no, "patch": state["patch_artifact"]},
            ),
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="fixer_completed",
                message="fixer completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "fixer",
                    "attempt_no": attempt_no,
                    "patch_id": (state["patch_artifact"] or {}).get("patch_id"),
                    "llm_trace_count": len(state.get("llm_trace", [])),
                    "tool_trace_count": len(state.get("tool_trace", [])),
                },
            ),
        )
        _record_execution_stage(
            state,
            stage_id="fixer_generating_patch",
            status="passed",
            summary="Patch generated and ready for verifier.",
            details={"patch_id": (state["patch_artifact"] or {}).get("patch_id")},
        )
        if not state.get("enable_verifier", False):
            state["attempts"] = list(state.get("attempts", [])) + [
                _build_attempt_summary(fixer_output.get("attempt", {}), "generated", "L0", None, None, None)
            ]
        return _full_state(state)

    return _node


def _verifier_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "verifier", "attempt_no": _attempt_no(state)},
        )
        if state.get("no_fix_needed"):
            return _full_state(state)
        fixer_output = state.get("latest_fixer_output", {}) or {}
        if not fixer_output.get("ok", False):
            return _full_state(state)
        if not state.get("enable_verifier", False):
            state["attempts"] = list(state.get("attempts", [])) + [
                _build_attempt_summary(fixer_output.get("attempt", {}), "generated", "L0", None, None, None)
            ]
            return _full_state(state)

        attempt_no = _attempt_no(state)
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="verifier_started",
                message="verifier started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "verifier",
                    "attempt_no": attempt_no,
                    "enabled_stages": ["patch_apply", "compile", "lint", "test", "security_rescan"],
                },
            ),
        )

        execution_stage_map = {
            "patch_apply": "patch_apply_running",
            "compile": "compile_running",
            "lint": "lint_running",
            "test": "test_running",
            "security_rescan": "security_rescan_running",
        }

        def _on_stage_update(stage_payload: dict[str, Any]) -> None:
            stage_name = str(stage_payload.get("stage") or "")
            stage_status = str(stage_payload.get("status") or "pending")
            execution_stage_id = execution_stage_map.get(stage_name)
            if execution_stage_id:
                _record_execution_stage(
                    state,
                    stage_id=execution_stage_id,
                    status=stage_status,
                    summary=str(stage_payload.get("summary") or f"{stage_name} {stage_status}"),
                    details={
                        "failure_code": stage_payload.get("failure_code"),
                        "skip_reason": stage_payload.get("skip_reason"),
                        "stderr_excerpt": stage_payload.get("stderr_excerpt"),
                        "retry_hint": stage_payload.get("retry_hint"),
                    },
                )
            if stage_status == "running":
                event_type = f"{stage_name}_started"
                message = f"{stage_name} started"
            elif stage_status == "failed":
                event_type = f"{stage_name}_failed"
                message = f"{stage_name} failed"
            else:
                event_type = f"{stage_name}_completed"
                message = f"{stage_name} completed"
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type=event_type,
                    message=message,
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "verifier",
                        "attempt_no": attempt_no,
                        "target_stage": stage_name,
                        **stage_payload,
                    },
                ),
            )

        verifier_options = dict(state.get("options", {}))
        verifier_options["enable_security_rescan"] = bool(state.get("enable_security_rescan", False))
        verification = ops.run_verifier_agent(
            code_text=state["code_text"],
            patch_artifact=state.get("patch_artifact"),
            options=verifier_options,
            repo_profile=state.get("repo_profile", {}),
            stage_callback=_on_stage_update,
        )
        state["verification_result"] = verification

        if verification.get("status") == "passed":
            state["attempts"] = list(state.get("attempts", [])) + [
                _build_attempt_summary(
                    fixer_output.get("attempt", {}),
                    "generated",
                    verification.get("verified_level", "L0"),
                    None,
                    None,
                    None,
                )
            ]
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type="verifier_completed",
                    message="verifier completed",
                    status="RUNNING",
                    payload={"source": "python-engine", "stage": "verifier", "attempt_no": attempt_no, "verification": verification},
                ),
            )
            state["retry_hints"] = {}
            state["should_retry"] = False
            return _full_state(state)

        failed_stage = verification.get("failed_stage")
        failure_reason = verification.get("failure_reason") or _extract_failure_reason(verification)
        failure_detail = _extract_failure_detail(verification)
        failure_code = str(verification.get("failure_code") or "").strip() or None
        stderr_excerpt = str(verification.get("stderr_excerpt") or "").strip() or None
        retry_hint = str(verification.get("retry_hint") or "").strip() or None
        compile_failure_bucket = _extract_compile_failure_bucket(verification)
        patch_artifact = state.get("patch_artifact") or {}
        if failed_stage == "compile" and str(patch_artifact.get("strategy_used") or "") == "syntax_fix":
            failure_reason = "compile_failed_after_repair"
        verification["failure_reason"] = failure_reason
        verification["failure_code"] = failure_code
        verification["stderr_excerpt"] = stderr_excerpt
        verification["retry_hint"] = retry_hint
        if compile_failure_bucket:
            verification["compile_failure_bucket"] = compile_failure_bucket
        state["attempts"] = list(state.get("attempts", [])) + [
            _build_attempt_summary(
                fixer_output.get("attempt", {}),
                "failed",
                verification.get("verified_level", "L0"),
                failed_stage,
                failure_reason,
                failure_detail,
            )
        ]
        retryable = bool(verification.get("retryable", False))
        retry_budget_left = max(int(state.get("max_retries", 2)) - int(state.get("retry_count", 0)), 0)
        failure_taxonomy = build_failure_taxonomy(
            final_outcome="failed_after_retries",
            failed_stage=failed_stage,
            failure_reason=failure_reason,
            failure_detail=failure_detail,
            issue_count=len(state.get("issues", [])),
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="verifier_failed",
                message="verifier failed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "verifier",
                    "attempt_no": attempt_no,
                    "failed_stage": failed_stage,
                    "reason": failure_reason,
                    "failure_detail": failure_detail,
                    "compile_failure_bucket": compile_failure_bucket,
                    "failure_code": failure_code,
                    "stderr_excerpt": stderr_excerpt,
                    "retry_hint": retry_hint,
                    "failure_taxonomy": failure_taxonomy,
                    "retryable": retryable,
                    "retry_budget_left": retry_budget_left,
                },
            ),
        )
        previous_patch_hash = str(patch_artifact.get("content_hash") or "").strip()
        if not previous_patch_hash:
            patch_content = str(patch_artifact.get("content") or "")
            if patch_content:
                previous_patch_hash = _hash_text(patch_content)
        state["short_term_memory"] = ops.update_short_term_memory(
            state,
            snapshot_type="verifier_failure",
            payload={
                "failed_stage": failed_stage,
                "reason": failure_reason,
                "detail": failure_detail,
                "stderr_summary": failure_detail,
                "compile_failure_bucket": compile_failure_bucket,
                "failure_code": failure_code,
                "stderr_excerpt": stderr_excerpt,
                "retry_hint": retry_hint,
                "failure_taxonomy": failure_taxonomy,
                "attempt_no": attempt_no,
                "previous_patch_id": patch_artifact.get("patch_id"),
                "previous_patch_hash": previous_patch_hash,
                "previous_patch_content": patch_artifact.get("content"),
            },
        )
        _record_debug_event(
            state,
            "short_term_memory_updated",
            "short term memory updated",
            {"source": "python-engine", "stage": "memory", "snapshot_type": "verifier_failure", "summary": {"failed_stage": failed_stage}},
        )
        should_retry = retryable and retry_budget_left > 0
        state["should_retry"] = should_retry
        state["retry_failed_stage"] = failed_stage
        state["retry_failure_reason"] = failure_reason
        return _full_state(state)

    return _node


def _retry_reflection_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        if not state.get("should_retry", False):
            return _full_state(state)
        _record_execution_stage(
            state,
            stage_id="retry_reflection",
            status="running",
            summary="Reflecting on verifier failure for next retry.",
        )
        verification = state.get("verification_result", {}) or {}
        failed_stage = str(verification.get("failed_stage") or state.get("retry_failed_stage") or "unknown")
        failure_code = str(verification.get("failure_code") or "")
        stderr_excerpt = str(verification.get("stderr_excerpt") or "")
        retry_hint = str(verification.get("retry_hint") or "")
        hints = {
            "next_context_hint": _derive_next_context_hint(failed_stage, failure_code, stderr_excerpt),
            "next_constraint_hint": _derive_next_constraint_hint(state, failed_stage),
            "next_retry_strategy": _derive_next_retry_strategy(failed_stage, retry_hint),
        }
        state["retry_hints"] = hints
        state["short_term_memory"] = ops.update_short_term_memory(
            state,
            snapshot_type="retry_context",
            payload=hints,
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="retry_reflection_completed",
                message="retry reflection completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "retry_reflection",
                    "attempt_no": _attempt_no(state),
                    **hints,
                },
            ),
        )
        _record_execution_stage(
            state,
            stage_id="retry_reflection",
            status="passed",
            summary="Retry hints prepared for next patch generation.",
            details=hints,
        )
        return _full_state(state)

    return _node


def _retry_router_node():
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "retry_router", "attempt_no": _attempt_no(state)},
        )
        if not state.get("should_retry", False):
            return _full_state(state)
        attempt_no = _attempt_no(state)
        next_attempt_no = attempt_no + 1
        retry_budget_left = max(int(state.get("max_retries", 2)) - int(state.get("retry_count", 0)) - 1, 0)
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="review_retry_scheduled",
                message="review retry scheduled",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "review",
                    "attempt_no": attempt_no,
                    "next_attempt_no": next_attempt_no,
                    "failed_stage": state.get("retry_failed_stage"),
                    "failure_reason": state.get("retry_failure_reason"),
                    "retry_budget_left": retry_budget_left,
                },
            ),
        )
        state["retry_count"] = int(state.get("retry_count", 0)) + 1
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="review_retry_started",
                message="review retry started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "review",
                    "attempt_no": next_attempt_no,
                    "retry_count": state["retry_count"],
                    "max_retries": state.get("max_retries", 2),
                },
            ),
        )
        state["should_retry"] = False
        return _full_state(state)

    return _node


def _reporter_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_execution_stage(
            state,
            stage_id="final_answer_writing",
            status="running",
            summary="Compiling final patch delivery and verification truth.",
        )
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "reporter", "attempt_no": _attempt_no(state)},
        )
        if state.get("final_status") == "failed":
            return _full_state(state)

        if bool(state.get("options", {}).get("persist_verified_case", False)):
            promoted = ops.promote_patch_from_verification(
                patch=state.get("patch_artifact"),
                verification=state.get("verification_result"),
                tool_trace=state.get("tool_trace", []),
                accepted_by_human=False,
            )
            if promoted is not None:
                state["case_store_summary"] = {
                    "source": "jsonl",
                    "promotion_candidate": True,
                    "case_id": promoted.get("case_id"),
                }
                _record_debug_event(
                    state,
                    "case_store_promoted",
                    "case store promoted",
                    {
                        "source": "python-engine",
                        "stage": "memory",
                        "case_id": promoted.get("case_id"),
                        "patch_id": (state.get("patch_artifact") or {}).get("patch_id"),
                        "verified_level": (state.get("verification_result") or {}).get("verified_level"),
                    },
                )

        state["final_status"] = "completed"
        review_payload = ops.build_review_completed_payload(EngineState.model_validate(state))
        _record_execution_stage(
            state,
            stage_id="final_answer_writing",
            status="passed",
            summary="Final answer payload compiled.",
        )
        _record_execution_stage(
            state,
            stage_id="completed",
            status="passed",
            summary="Review pipeline completed.",
        )
        _record_event(
            state,
            build_event(
                task_id=state["task_id"],
                event_type="review_completed",
                message="review completed",
                status="COMPLETED",
                payload=review_payload,
            ),
        )
        return _full_state(state)

    return _node


def _route_after_analyzer(state: dict[str, Any]) -> str:
    if state.get("final_status") == "failed":
        return "reporter"
    if state.get("no_fix_needed", False):
        return "reporter"
    return "planner"


def _route_after_fixer(state: dict[str, Any]) -> str:
    fixer_output = state.get("latest_fixer_output", {}) or {}
    if not fixer_output.get("ok", False):
        return "reporter"
    if not state.get("enable_verifier", False):
        return "reporter"
    return "verifier"


def _route_after_verifier(state: dict[str, Any]) -> str:
    verification = state.get("verification_result", {}) or {}
    if verification.get("status") == "passed":
        return "reporter"
    if state.get("should_retry", False):
        return "retry_reflection"
    return "reporter"


def _route_after_retry(state: dict[str, Any]) -> str:
    if int(state.get("retry_count", 0)) <= int(state.get("max_retries", 2)):
        return "memory_context"
    return "reporter"


def _record_event(state: dict[str, Any], event: PythonEngineEvent) -> None:
    events = list(state.get("events", []))
    events.append(event.model_dump(by_alias=True))
    state["events"] = events


def _record_debug_event(state: dict[str, Any], event_type: str, message: str, payload: dict[str, Any]) -> None:
    if not bool(state.get("debug_enabled", False)):
        return
    _record_event(
        state,
        build_event(task_id=state["task_id"], event_type=event_type, message=message, status="RUNNING", payload=payload),
    )


def _record_execution_stage(
    state: dict[str, Any],
    *,
    stage_id: str,
    status: str,
    summary: str,
    details: Any = None,
) -> None:
    execution = dict(state.get("execution_stages", {}) or {})
    current = dict(execution.get(stage_id, {}) or {})
    started_at = str(current.get("started_at") or "")
    if status == "running":
        started_at = started_at or _now_iso()
        finished_at = None
        duration_ms = None
    else:
        started_at = started_at or _now_iso()
        finished_at = _now_iso()
        duration_ms = _duration_ms(started_at, finished_at)
    next_payload = {
        "stage_id": stage_id,
        "status": status,
        "summary": summary,
        "details": details,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
    }
    execution[stage_id] = next_payload
    state["execution_stages"] = execution
    _record_event(
        state,
        build_event(
            task_id=state["task_id"],
            event_type="execution_stage_update",
            message=f"{stage_id} {status}",
            status="RUNNING",
            payload={
                "source": "python-engine",
                "stage": "execution",
                **next_payload,
            },
        ),
    )


def _build_attempt_summary(
    base_attempt: dict[str, Any],
    status: str,
    verified_level: str,
    failure_stage: str | None,
    failure_reason: str | None,
    failure_detail: str | None,
) -> dict[str, Any]:
    return {
        "attempt_no": base_attempt.get("attempt_no"),
        "patch_id": base_attempt.get("patch_id"),
        "status": status,
        "verified_level": verified_level,
        "failure_stage": failure_stage,
        "failed_stage": failure_stage,
        "failure_reason": failure_reason,
        "failure_detail": failure_detail,
        "failure_code": base_attempt.get("failure_code"),
        "memory_case_ids": base_attempt.get("memory_case_ids", []),
    }


def _extract_failure_reason(verification: dict[str, Any]) -> str:
    for stage in verification.get("stages", []):
        if stage.get("status") == "failed":
            reason = str(stage.get("failure_code") or "").strip()
            if reason:
                return reason
            reason = str(stage.get("summary") or "").strip()
            if reason:
                return reason
            stderr = str(stage.get("stderr_summary") or "").strip()
            if stderr:
                return stderr
    return "verification_failed"


def _extract_failure_detail(verification: dict[str, Any]) -> str | None:
    for stage in verification.get("stages", []):
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
    return None


def _extract_compile_failure_bucket(verification: dict[str, Any]) -> str | None:
    for stage in verification.get("stages", []):
        if stage.get("status") != "failed":
            continue
        if str(stage.get("stage") or "").strip().lower() != "compile":
            continue
        bucket = str(stage.get("compile_failure_bucket") or "").strip()
        if bucket:
            return bucket
    return None


def _derive_next_context_hint(failed_stage: str, failure_code: str, stderr_excerpt: str) -> str:
    stage = failed_stage.strip().lower()
    if stage == "patch_apply":
        return "Please include the exact current snippet around the target hunk so diff context can align."
    if stage == "compile":
        return "Provide missing symbol/import definitions and related method signatures referenced by compile errors."
    if stage == "lint":
        return "Provide repository lint rule set or style constraints to align generated patch with lint expectations."
    if stage == "test":
        return "Provide regression test entry command and failing test output to guide behavioral fix."
    if stage == "security_rescan":
        return "Provide security rule identifiers or scanner output to target the newly introduced findings."
    if "llm" in failure_code.lower():
        return "Clarify expected output contract and include one valid unified diff example for the same snippet style."
    if stderr_excerpt:
        return "Provide surrounding code for the failing line and dependent methods/classes referenced in stderr."
    return "Provide minimal reproducible failing context: target method + caller + expected behavior constraints."


def _derive_next_constraint_hint(state: dict[str, Any], failed_stage: str) -> str:
    user_constraints = str(state.get("message_text") or "").strip()
    if user_constraints:
        return f"Current user constraints should remain enforced: {user_constraints[:180]}"
    if failed_stage == "compile":
        return "Do not change public signatures unless explicitly required; prioritize import/type consistency."
    return "Clarify whether API signatures, exception behavior, or performance constraints are strict requirements."


def _derive_next_retry_strategy(failed_stage: str, retry_hint: str) -> str:
    if retry_hint.strip():
        return retry_hint.strip()
    stage = failed_stage.strip().lower()
    if stage == "patch_apply":
        return "Regenerate a smaller unified diff with accurate file header and hunk context."
    if stage == "compile":
        return "Patch compile blockers first, then rerun verifier before semantic refactor."
    if stage in {"lint", "test", "security_rescan"}:
        return f"Target {stage} failures directly using verifier stderr excerpts as acceptance criteria."
    return "Generate a non-duplicate patch that directly addresses the latest failed verifier stage."


def _attempt_no(state: dict[str, Any]) -> int:
    return int(state.get("retry_count", 0)) + 1


def _to_int(value: Any, *, default: int) -> int:
    try:
        if value is None:
            return default
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except Exception:
        return default


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def _resolve_focus_line_from_issues(issues: list[dict[str, Any]]) -> int:
    for issue in issues:
        try:
            value = int(issue.get("line") or issue.get("startLine") or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return 1


def _build_local_snippet_context(*, code_text: str, focus_line: int, window: int, source_id: str) -> dict[str, Any]:
    lines = code_text.splitlines()
    start_line = max(1, focus_line - window)
    end_line = min(len(lines), focus_line + window) if lines else 1
    snippet = "\n".join(lines[start_line - 1 : end_line]) if lines else ""
    return {
        "source_id": source_id,
        "kind": "snippet_window",
        "path": "snippet.java",
        "startLine": start_line,
        "endLine": end_line,
        "content": snippet,
        "token_count": max(1, int(len(snippet) / 4)) if snippet else 1,
        "reason": "issue vicinity",
    }


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


def _full_state(state: dict[str, Any]) -> dict[str, Any]:
    return dict(state)
