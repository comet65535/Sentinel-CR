from __future__ import annotations

from collections.abc import AsyncIterator

from agents import build_review_completed_payload, run_fixer_agent, run_planner_agent
from analyzers import (
    build_symbol_graph,
    compose_day2_output,
    parse_java_code,
    run_semgrep,
    validate_day2_input,
)
from memory import retrieve_case_matches

from .events import build_event
from .schemas import (
    EngineState,
    InternalReviewRunRequest,
    PythonEngineEvent,
    default_issue_graph,
    default_planner_summary,
)

SEMGREP_WARNING_CODES = {
    "SEMGREP_UNAVAILABLE",
    "SEMGREP_TIMEOUT",
    "SEMGREP_EXEC_ERROR",
}


def bootstrap_state(request: InternalReviewRunRequest) -> EngineState:
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
        patch_artifact=None,
        attempts=[],
        patch=None,
        verification_result=None,
        events=[],
        retry_count=0,
    )


def _record_event(state: EngineState, event: PythonEngineEvent) -> PythonEngineEvent:
    state.events.append(event.model_dump(by_alias=True))
    return event


async def run_day3_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    state = bootstrap_state(request)

    started_event = _record_event(
        state,
        build_event(
            task_id=state.task_id,
            event_type="analysis_started",
            message="python engine started analyzer state graph",
            status="RUNNING",
            payload={
                "source": "python-engine",
                "stage": "bootstrap_state",
                "language": state.language,
            },
        ),
    )
    yield started_event

    validation_diagnostics = validate_day2_input(state.code_text, state.language)
    if validation_diagnostics:
        state.diagnostics = validation_diagnostics
        failed_event = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="review_failed",
                message="review failed",
                status="FAILED",
                payload={
                    "source": "python-engine",
                    "stage": "input_validation",
                    "diagnostics": state.diagnostics,
                },
            ),
        )
        yield failed_event
        return

    try:
        ast_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="ast_parsing_started",
                message="ast parsing started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "ast",
                    "language": state.language.lower(),
                },
            ),
        )
        yield ast_started

        ast_result = parse_java_code(state.code_text)
        state.diagnostics.extend(ast_result.get("diagnostics", []) or [])

        ast_summary = ast_result.get("summary", {}) or {}
        ast_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="ast_parsing_completed",
                message="ast parsing completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "ast",
                    "language": state.language.lower(),
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
        yield ast_completed

        symbol_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="symbol_graph_started",
                message="symbol graph build started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "symbol_graph",
                },
            ),
        )
        yield symbol_started

        symbol_graph_result = build_symbol_graph(state.code_text, ast_result)
        state.diagnostics.extend(symbol_graph_result.get("diagnostics", []) or [])
        symbol_summary = symbol_graph_result.get("summary", {}) or {}

        symbol_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="symbol_graph_completed",
                message="symbol graph build completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "symbol_graph",
                    "symbolsCount": len(symbol_graph_result.get("symbols", []) or []),
                    "callEdgesCount": int(symbol_summary.get("callEdgesCount", 0)),
                    "variableRefsCount": int(symbol_summary.get("variableRefsCount", 0)),
                },
            ),
        )
        yield symbol_completed

        semgrep_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="semgrep_scan_started",
                message="semgrep scan started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "semgrep",
                    "ruleset": "auto",
                },
            ),
        )
        yield semgrep_started

        semgrep_result = run_semgrep(state.code_text, language=state.language.lower())
        semgrep_diagnostics = semgrep_result.get("diagnostics", []) or []
        state.diagnostics.extend(semgrep_diagnostics)
        semgrep_summary = semgrep_result.get("summary", {}) or {}

        warning_diagnostic = next(
            (item for item in semgrep_diagnostics if item.get("code") in SEMGREP_WARNING_CODES),
            None,
        )
        if warning_diagnostic is not None:
            semgrep_event_type = "semgrep_scan_warning"
            semgrep_message = "semgrep scan warning"
            semgrep_payload = {
                "source": "python-engine",
                "stage": "semgrep",
                "ruleset": semgrep_summary.get("ruleset", "auto"),
                "issuesCount": int(semgrep_summary.get("issuesCount", 0)),
                "code": warning_diagnostic.get("code"),
                "message": warning_diagnostic.get("message"),
            }
        else:
            semgrep_event_type = "semgrep_scan_completed"
            semgrep_message = "semgrep scan completed"
            semgrep_payload = {
                "source": "python-engine",
                "stage": "semgrep",
                "ruleset": semgrep_summary.get("ruleset", "auto"),
                "issuesCount": int(semgrep_summary.get("issuesCount", 0)),
                "severityBreakdown": semgrep_summary.get("severityBreakdown", {}),
            }

        semgrep_event = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type=semgrep_event_type,
                message=semgrep_message,
                status="RUNNING",
                payload=semgrep_payload,
            ),
        )
        yield semgrep_event

        analyzer_output = compose_day2_output(
            language=state.language,
            ast_result=ast_result,
            symbol_graph_result=symbol_graph_result,
            semgrep_result=semgrep_result,
        )

        state.issues = analyzer_output["issues"]
        state.symbols = analyzer_output["symbols"]
        state.context_summary = analyzer_output["contextSummary"]
        state.analyzer_summary = analyzer_output["analyzerSummary"]
        state.diagnostics = analyzer_output["diagnostics"]

        analyzer_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="analyzer_completed",
                message="analyzer completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "analyzer_pipeline",
                    "analyzerSummary": state.analyzer_summary,
                },
            ),
        )
        yield analyzer_completed

        planner_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="planner_started",
                message="planner started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "inputIssueCount": len(state.issues),
                    "inputSymbolCount": len(state.symbols),
                },
            ),
        )
        yield planner_started

        planner_output = run_planner_agent(
            issues=state.issues,
            symbols=state.symbols,
            context_summary=state.context_summary,
        )
        state.issue_graph = planner_output["issue_graph"]
        state.repair_plan = planner_output["repair_plan"]
        state.planner_summary = planner_output["planner_summary"]

        issue_graph_nodes = state.issue_graph.get("nodes", [])
        issue_graph_edges = state.issue_graph.get("edges", [])

        issue_graph_built = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="issue_graph_built",
                message="issue graph built",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "issue_graph": state.issue_graph,
                    "issueCount": len(issue_graph_nodes),
                    "edgeCount": len(issue_graph_edges),
                },
            ),
        )
        yield issue_graph_built

        repair_plan_created = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="repair_plan_created",
                message="repair plan created",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "repair_plan": state.repair_plan,
                    "planCount": len(state.repair_plan),
                },
            ),
        )
        yield repair_plan_created

        planner_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="planner_completed",
                message="planner completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "planner",
                    "issueCount": len(issue_graph_nodes),
                    "planCount": len(state.repair_plan),
                    "plannerSummary": state.planner_summary,
                },
            ),
        )
        yield planner_completed

        # Day4 strict event order starts here.
        case_memory_search_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="case_memory_search_started",
                message="case memory search started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "memory",
                    "attempt_no": 1,
                    "issue_count": len(state.issues),
                    "strategy_hints": [str(item.get("strategy") or "") for item in state.repair_plan],
                },
            ),
        )
        yield case_memory_search_started

        state.memory_matches = retrieve_case_matches(
            issues=state.issues,
            repair_plan=state.repair_plan,
            symbols=state.symbols,
            context_summary=state.context_summary,
            top_k=3,
        )

        if state.memory_matches:
            case_memory_matched = _record_event(
                state,
                build_event(
                    task_id=state.task_id,
                    event_type="case_memory_matched",
                    message="case memory matched",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "memory",
                        "attempt_no": 1,
                        "match_count": len(state.memory_matches),
                        "matches": state.memory_matches,
                    },
                ),
            )
            yield case_memory_matched

        case_memory_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="case_memory_completed",
                message="case memory completed",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "memory",
                    "attempt_no": 1,
                    "match_count": len(state.memory_matches),
                },
            ),
        )
        yield case_memory_completed

        fixer_started = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="fixer_started",
                message="fixer started",
                status="RUNNING",
                payload={
                    "source": "python-engine",
                    "stage": "fixer",
                    "attempt_no": 1,
                    "plan_count": len(state.repair_plan),
                    "memory_match_count": len(state.memory_matches),
                },
            ),
        )
        yield fixer_started

        fixer_output = run_fixer_agent(
            repair_plan=state.repair_plan,
            issues=state.issues,
            symbols=state.symbols,
            context_summary=state.context_summary,
            memory_matches=state.memory_matches,
            attempt_no=1,
        )
        state.patch_artifact = fixer_output["patch_artifact"]
        state.patch = state.patch_artifact
        state.attempts.append(fixer_output["attempt"])

        if fixer_output["ok"]:
            patch_generated = _record_event(
                state,
                build_event(
                    task_id=state.task_id,
                    event_type="patch_generated",
                    message="patch generated",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "fixer",
                        "attempt_no": 1,
                        "patch": state.patch_artifact,
                    },
                ),
            )
            yield patch_generated

            fixer_completed = _record_event(
                state,
                build_event(
                    task_id=state.task_id,
                    event_type="fixer_completed",
                    message="fixer completed",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "fixer",
                        "attempt_no": 1,
                        "patch_id": state.patch_artifact.get("patch_id"),
                    },
                ),
            )
            yield fixer_completed
        else:
            fixer_failed = _record_event(
                state,
                build_event(
                    task_id=state.task_id,
                    event_type="fixer_failed",
                    message="fixer failed",
                    status="RUNNING",
                    payload={
                        "source": "python-engine",
                        "stage": "fixer",
                        "attempt_no": 1,
                        "reason": state.attempts[-1].get("failure_reason"),
                        "failure_detail": state.attempts[-1].get("failure_detail"),
                    },
                ),
            )
            yield fixer_failed

        review_payload = build_review_completed_payload(state)
        review_completed = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="review_completed",
                message="review completed",
                status="COMPLETED",
                payload=review_payload,
            ),
        )
        yield review_completed
    except Exception as exc:
        failed_event = _record_event(
            state,
            build_event(
                task_id=state.task_id,
                event_type="review_failed",
                message="review failed",
                status="FAILED",
                payload={
                    "source": "python-engine",
                    "stage": "state_graph",
                    "errorType": exc.__class__.__name__,
                    "error": str(exc),
                    "diagnostics": state.diagnostics,
                },
            ),
        )
        yield failed_event


async def run_day2_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_day3_state_graph(request):
        yield event


async def run_day1_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_day3_state_graph(request):
        yield event
