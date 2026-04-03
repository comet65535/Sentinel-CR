from __future__ import annotations

from collections.abc import AsyncIterator

from agents import build_review_completed_payload, run_fixer_agent, run_planner_agent, run_verifier_agent
from analyzers import (
    build_symbol_graph,
    compose_day2_output,
    parse_java_code,
    run_semgrep,
    validate_day2_input,
)
from memory import (
    get_latest_verifier_failure,
    promote_patch_from_verification,
    resolve_repo_profile,
    retrieve_case_matches,
    summarize_repo_profile,
    update_short_term_memory,
)

from .langgraph_flow import EngineOps, run_langgraph_state_graph
from .schemas import InternalReviewRunRequest, PythonEngineEvent


def _build_ops() -> EngineOps:
    # Keep these references in this module so existing tests can monkeypatch
    # `core.state_graph.<function_name>` and still affect graph execution.
    return EngineOps(
        validate_day2_input=validate_day2_input,
        parse_java_code=parse_java_code,
        build_symbol_graph=build_symbol_graph,
        run_semgrep=run_semgrep,
        compose_day2_output=compose_day2_output,
        run_planner_agent=run_planner_agent,
        retrieve_case_matches=retrieve_case_matches,
        run_fixer_agent=run_fixer_agent,
        run_verifier_agent=run_verifier_agent,
        build_review_completed_payload=build_review_completed_payload,
        resolve_repo_profile=resolve_repo_profile,
        summarize_repo_profile=summarize_repo_profile,
        update_short_term_memory=update_short_term_memory,
        get_latest_verifier_failure=get_latest_verifier_failure,
        promote_patch_from_verification=promote_patch_from_verification,
    )


async def run_day3_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_review_state_graph(request):
        yield event


async def run_review_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_langgraph_state_graph(request, ops=_build_ops()):
        yield event


async def run_day2_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_review_state_graph(request):
        yield event


async def run_day1_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    async for event in run_review_state_graph(request):
        yield event
