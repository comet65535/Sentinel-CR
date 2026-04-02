from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .events import build_event
from .schemas import EngineState, InternalReviewRunRequest, PythonEngineEvent


def bootstrap_state(request: InternalReviewRunRequest) -> EngineState:
    return EngineState(
        task_id=request.task_id,
        code_text=request.code_text,
        language=request.language,
        issues=[],
        issue_graph=[],
        patch=None,
        verification_result=None,
        events=[],
        retry_count=0,
    )


def run_analysis_stub(state: EngineState) -> EngineState:
    # Day1 only keeps placeholders for Day2 analyzers.
    state.issues = []
    state.issue_graph = []
    return state


def finalize_result(state: EngineState) -> dict[str, str]:
    return {
        "summary": "day1 python engine skeleton completed",
        "engine": "python",
    }


async def run_day1_state_graph(request: InternalReviewRunRequest) -> AsyncIterator[PythonEngineEvent]:
    state = bootstrap_state(request)

    started_event = build_event(
        task_id=state.task_id,
        event_type="analysis_started",
        message="python engine started state graph",
        status="RUNNING",
        payload={
            "source": "python-engine",
            "stage": "bootstrap_state",
        },
    )
    state.events.append(started_event.model_dump(by_alias=True))
    yield started_event

    await asyncio.sleep(0.2)
    state = run_analysis_stub(state)
    completed_event = build_event(
        task_id=state.task_id,
        event_type="analysis_completed",
        message="python analysis stub completed",
        status="RUNNING",
        payload={
            "source": "python-engine",
            "stage": "run_analysis_stub",
            "issues": state.issues,
            "issueGraph": state.issue_graph,
        },
    )
    state.events.append(completed_event.model_dump(by_alias=True))
    yield completed_event

    await asyncio.sleep(0.2)
    result = finalize_result(state)
    review_completed_event = build_event(
        task_id=state.task_id,
        event_type="review_completed",
        message="review completed",
        status="COMPLETED",
        payload={
            "source": "python-engine",
            "stage": "finalize_result",
            "result": result,
        },
    )
    state.events.append(review_completed_event.model_dump(by_alias=True))
    yield review_completed_event
