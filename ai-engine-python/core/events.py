from __future__ import annotations

from typing import Any

from .schemas import PythonEngineEvent


def build_event(
    task_id: str,
    event_type: str,
    message: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> PythonEngineEvent:
    return PythonEngineEvent(
        taskId=task_id,
        eventType=event_type,
        message=message,
        status=status,
        payload=payload or {},
    )


def to_ndjson_line(event: PythonEngineEvent) -> str:
    return event.model_dump_json(by_alias=True) + "\n"
