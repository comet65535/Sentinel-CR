from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from .context_budget import initialize_context_budget, register_loaded_context
from .mcp_client import McpClient, build_mcp_base_url
from .events import build_event
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
    run_fixer_agent: Callable[..., dict[str, Any]]
    run_verifier_agent: Callable[..., dict[str, Any]]
    build_review_completed_payload: Callable[[EngineState], dict[str, Any]]
    resolve_repo_profile: Callable[..., dict[str, Any]]
    summarize_repo_profile: Callable[[dict[str, Any] | None], dict[str, Any]]
    update_short_term_memory: Callable[..., dict[str, Any]]
    get_latest_verifier_failure: Callable[[dict[str, Any] | None], dict[str, Any] | None]
    promote_patch_from_verification: Callable[..., dict[str, Any] | None]


def bootstrap_state(request: InternalReviewRunRequest) -> dict[str, Any]:
    options = request.options or {}
    return EngineState(
        task_id=request.task_id,
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
        short_term_memory={},
        repo_profile={},
        case_store_summary={"source": "jsonl", "promotion_candidate": False},
        patch_artifact=None,
        attempts=[],
        patch=None,
        verification_result=None,
        context_budget=initialize_context_budget(options),
        selected_context=[],
        tool_trace=[],
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
    graph.add_node("memory_retrieval", _memory_node(ops))
    graph.add_node("fixer", _fixer_node(ops))
    graph.add_node("verifier", _verifier_node(ops))
    graph.add_node("retry_router", _retry_router_node())
    graph.add_node("reporter", _reporter_node(ops))

    graph.set_entry_point("bootstrap")
    graph.add_edge("bootstrap", "analyzer")
    graph.add_conditional_edges("analyzer", _route_after_analyzer, {"planner": "planner", "reporter": "reporter"})
    graph.add_edge("planner", "memory_retrieval")
    graph.add_edge("memory_retrieval", "fixer")
    graph.add_conditional_edges("fixer", _route_after_fixer, {"verifier": "verifier", "reporter": "reporter"})
    graph.add_conditional_edges("verifier", _route_after_verifier, {"retry_router": "retry_router", "reporter": "reporter"})
    graph.add_conditional_edges("retry_router", _route_after_retry, {"fixer": "fixer", "reporter": "reporter"})
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
        if state.get("context_budget"):
            _record_debug_event(
                state,
                "context_budget_initialized",
                "context budget initialized",
                {"source": "python-engine", "stage": "context_budget", "context_budget": state["context_budget"]},
            )
        return _full_state(state)

    return _node


def _analyzer_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
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
        state["no_fix_needed"] = len(state["issues"]) == 0
        return _full_state(state)

    return _node


def _planner_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
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
        return _full_state(state)

    return _node


def _memory_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
        _record_debug_event(
            state,
            "langgraph_node_started",
            "langgraph node started",
            {"source": "python-engine", "stage": "langgraph", "node_name": "memory_retrieval", "attempt_no": _attempt_no(state)},
        )
        if state.get("no_fix_needed"):
            return _full_state(state)
        attempt_no = _attempt_no(state)
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
        if budget:
            source_item = {
                "source_id": f"ctx-{attempt_no}-snippet",
                "kind": "snippet_window",
                "path": "snippet.java",
                "token_count": max(1, int(len(state.get("code_text", "")) / 4)),
                "reason": "issue vicinity",
            }
            updated, exhausted = register_loaded_context(budget, source_item=source_item, load_stage="issue_snippet")
            state["context_budget"] = updated
            state["selected_context"] = [source_item]
            _record_debug_event(
                state,
                "context_resource_loaded",
                "context resource loaded",
                {"source": "python-engine", "stage": "context_budget", "source_item": source_item, "context_budget": updated},
            )
            _record_debug_event(
                state,
                "context_budget_updated",
                "context budget updated",
                {"source": "python-engine", "stage": "context_budget", "context_budget": updated},
            )
            if exhausted:
                _record_debug_event(
                    state,
                    "context_budget_exhausted",
                    "context budget exhausted",
                    {"source": "python-engine", "stage": "context_budget", "reason": "remaining_tokens=0", "context_budget": updated},
                )
            state["short_term_memory"] = ops.update_short_term_memory(
                state, snapshot_type="token_usage", payload={"used_tokens": updated.get("used_tokens", 0)}
            )

        if bool(state.get("options", {}).get("enable_mcp", False)):
            client = McpClient(base_url=build_mcp_base_url(state.get("metadata", {})))
            _record_debug_event(
                state,
                "mcp_resource_requested",
                "mcp resource requested",
                {"source": "backend-mcp", "stage": "mcp", "resource_name": "schema"},
            )
            envelope, trace_item = client.get_resource(
                "schema",
                query={"taskId": state["task_id"], "schemaType": "api_contract"},
            )
            trace_item["selected_by"] = "context_budget"
            state["tool_trace"] = list(state.get("tool_trace", [])) + [trace_item]
            _record_debug_event(
                state,
                "mcp_resource_completed",
                "mcp resource completed",
                {
                    "source": "backend-mcp",
                    "stage": "mcp",
                    "resource_name": "schema",
                    "request_id": envelope.get("request_id"),
                    "ok": envelope.get("ok", False),
                    "latency_ms": (envelope.get("meta", {}) or {}).get("latency_ms", 0),
                },
            )

        return _full_state(state)

    return _node


def _fixer_node(ops: EngineOps):
    async def _node(state: dict[str, Any]) -> dict[str, Any]:
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
        )
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
                },
            ),
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
        verifier_options = dict(state.get("options", {}))
        verifier_options["enable_security_rescan"] = bool(state.get("enable_security_rescan", False))
        verification = ops.run_verifier_agent(
            code_text=state["code_text"],
            patch_artifact=state.get("patch_artifact"),
            options=verifier_options,
            repo_profile=state.get("repo_profile", {}),
        )
        state["verification_result"] = verification
        for stage_result in verification.get("stages", []):
            stage_name = str(stage_result.get("stage"))
            stage_status = str(stage_result.get("status"))
            _record_event(
                state,
                build_event(
                    task_id=state["task_id"],
                    event_type=f"{stage_name}_started",
                    message=f"{stage_name} started",
                    status="RUNNING",
                    payload={"source": "python-engine", "stage": "verifier", "attempt_no": attempt_no, "target_stage": stage_name},
                ),
            )
            payload = {
                "source": "python-engine",
                "stage": "verifier",
                "attempt_no": attempt_no,
                "target_stage": stage_name,
                "status": stage_status,
                "exit_code": stage_result.get("exit_code"),
                "stdout_summary": stage_result.get("stdout_summary", ""),
                "stderr_summary": stage_result.get("stderr_summary", ""),
                "reason": stage_result.get("reason"),
                "retryable": bool(stage_result.get("retryable", False)),
            }
            if stage_status in {"passed", "skipped"}:
                _record_event(
                    state,
                    build_event(
                        task_id=state["task_id"],
                        event_type=f"{stage_name}_completed",
                        message=f"{stage_name} {'skipped' if stage_status == 'skipped' else 'completed'}",
                        status="RUNNING",
                        payload=payload,
                    ),
                )
            else:
                _record_event(
                    state,
                    build_event(
                        task_id=state["task_id"],
                        event_type=f"{stage_name}_failed",
                        message=f"{stage_name} failed",
                        status="RUNNING",
                        payload=payload,
                    ),
                )
                break

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
            state["should_retry"] = False
            return _full_state(state)

        failed_stage = verification.get("failed_stage")
        failure_reason = verification.get("failure_reason") or _extract_failure_reason(verification)
        failure_detail = _extract_failure_detail(verification)
        patch_artifact = state.get("patch_artifact") or {}
        if failed_stage == "compile" and str(patch_artifact.get("strategy_used") or "") == "syntax_fix":
            failure_reason = "compile_failed_after_repair"
        verification["failure_reason"] = failure_reason
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
                "attempt_no": attempt_no,
                "previous_patch_id": patch_artifact.get("patch_id"),
                "previous_patch_hash": previous_patch_hash,
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
        return "retry_router"
    return "reporter"


def _route_after_retry(state: dict[str, Any]) -> str:
    if int(state.get("retry_count", 0)) <= int(state.get("max_retries", 2)):
        return "fixer"
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
        "memory_case_ids": base_attempt.get("memory_case_ids", []),
    }


def _extract_failure_reason(verification: dict[str, Any]) -> str:
    for stage in verification.get("stages", []):
        if stage.get("status") == "failed":
            reason = str(stage.get("reason") or "").strip()
            if reason:
                return reason
            stderr = str(stage.get("stderr_summary") or "").strip()
            if stderr:
                return stderr
    return "verification_failed"


def _extract_failure_detail(verification: dict[str, Any]) -> str | None:
    for stage in verification.get("stages", []):
        if stage.get("status") == "failed":
            stderr = str(stage.get("stderr_summary") or "").strip()
            if stderr:
                return stderr
            stdout = str(stage.get("stdout_summary") or "").strip()
            if stdout:
                return stdout
    return None


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


def _full_state(state: dict[str, Any]) -> dict[str, Any]:
    return dict(state)
