from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InternalReviewRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    code_text: str = Field(alias="codeText")
    language: str
    source_type: str = Field(alias="sourceType")
    options: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PythonEngineEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(alias="taskId")
    event_type: str = Field(alias="eventType")
    message: str
    status: Literal["CREATED", "RUNNING", "COMPLETED", "FAILED"]
    payload: dict[str, Any] = Field(default_factory=dict)


def default_issue_graph() -> dict[str, Any]:
    return {
        "schema_version": "day3.v1",
        "nodes": [],
        "edges": [],
    }


def default_planner_summary() -> dict[str, int]:
    return {
        "total_issues": 0,
        "total_nodes": 0,
        "total_edges": 0,
        "total_plans": 0,
        "high_severity_count": 0,
        "requires_test_count": 0,
    }


class EngineState(BaseModel):
    task_id: str
    code_text: str
    language: str
    issues: list[dict[str, Any]] = Field(default_factory=list)
    symbols: list[dict[str, Any]] = Field(default_factory=list)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    analyzer_summary: dict[str, Any] = Field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    issue_graph: dict[str, Any] = Field(default_factory=default_issue_graph)
    repair_plan: list[dict[str, Any]] = Field(default_factory=list)
    planner_summary: dict[str, int] = Field(default_factory=default_planner_summary)
    memory_matches: list[dict[str, Any]] = Field(default_factory=list)
    patch_artifact: dict[str, Any] | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    patch: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    enable_verifier: bool = False
    enable_security_rescan: bool = False
    max_retries: int = 2
    final_status: str = "running"
    events: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    no_fix_needed: bool = False
