from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InternalReviewRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    code_text: str = Field(alias="codeText")
    language: str
    source_type: str = Field(alias="sourceType")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PythonEngineEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    event_type: str = Field(alias="eventType")
    message: str
    status: Literal["CREATED", "RUNNING", "COMPLETED", "FAILED"]
    payload: dict[str, Any] = Field(default_factory=dict)


class EngineState(BaseModel):
    task_id: str
    code_text: str
    language: str
    issues: list[dict[str, Any]] = Field(default_factory=list)
    symbols: list[dict[str, Any]] = Field(default_factory=list)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    analyzer_summary: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    issue_graph: list[dict[str, Any]] = Field(default_factory=list)
    patch: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
