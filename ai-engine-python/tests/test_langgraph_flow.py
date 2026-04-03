from __future__ import annotations

import asyncio

from core.schemas import InternalReviewRunRequest
from core.state_graph import run_day3_state_graph


def _collect_events(request: InternalReviewRunRequest) -> list[dict]:
    async def _run() -> list[dict]:
        items: list[dict] = []
        async for event in run_day3_state_graph(request):
            items.append(event.model_dump(by_alias=True))
        return items

    return asyncio.run(_run())


def test_langgraph_normal_flow(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "null_pointer",
                    "severity": "MEDIUM",
                    "message": "null may dereference",
                    "line": 3,
                    "column": 1,
                    "ruleId": "forced.issue",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    request = InternalReviewRunRequest(
        taskId="rev_langgraph_ok",
        codeText="class snippet { void run(){ System.out.println(\"ok\"); } }",
        language="java",
        sourceType="snippet",
        options={"enable_verifier": False},
        metadata={},
    )
    events = _collect_events(request)
    event_types = [item["eventType"] for item in events]
    assert "planner_started" in event_types
    assert "issue_graph_built" in event_types
    assert "fixer_started" in event_types
    assert "review_completed" in event_types


def test_langgraph_retry_branch(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "null_pointer",
                    "severity": "MEDIUM",
                    "message": "null may dereference",
                    "line": 3,
                    "column": 1,
                    "ruleId": "forced.issue",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": True,
            "patch_artifact": {
                "patch_id": f"patch_{kwargs.get('attempt_no')}",
                "attempt_no": kwargs.get("attempt_no"),
                "status": "generated",
                "format": "unified_diff",
                "content": "\n".join(
                    [
                        "diff --git a/snippet.java b/snippet.java",
                        "--- a/snippet.java",
                        "+++ b/snippet.java",
                        "@@ -1,1 +1,2 @@",
                        " class snippet {",
                        "+// force patch",
                    ]
                ),
                "target_files": ["snippet.java"],
                "strategy_used": "test",
                "memory_case_ids": [],
            },
            "attempt": {"attempt_no": kwargs.get("attempt_no"), "patch_id": f"patch_{kwargs.get('attempt_no')}", "memory_case_ids": []},
        },
    )

    verify_calls = {"count": 0}

    def _stub_verifier(**kwargs):
        verify_calls["count"] += 1
        first_attempt = verify_calls["count"] == 1
        return {
            "status": "failed" if first_attempt else "passed",
            "verified_level": "L0" if first_attempt else "L1",
            "passed_stages": [] if first_attempt else ["patch_apply", "compile"],
            "failed_stage": "compile" if first_attempt else None,
            "stages": [
                {
                    "stage": "patch_apply",
                    "status": "passed",
                    "exit_code": 0,
                    "stdout_summary": "",
                    "stderr_summary": "",
                    "reason": None,
                    "retryable": False,
                },
                {
                    "stage": "compile",
                    "status": "failed" if first_attempt else "passed",
                    "exit_code": 1 if first_attempt else 0,
                    "stdout_summary": "",
                    "stderr_summary": "compile error" if first_attempt else "",
                    "reason": "compile_failed" if first_attempt else None,
                    "retryable": first_attempt,
                },
            ],
            "summary": "forced",
            "retryable": first_attempt,
            "failure_reason": "compile_failed" if first_attempt else None,
        }

    monkeypatch.setattr("core.state_graph.run_verifier_agent", _stub_verifier)

    request = InternalReviewRunRequest(
        taskId="rev_langgraph_retry",
        codeText="class snippet { void run(){ System.out.println(\"ok\"); } }",
        language="java",
        sourceType="snippet",
        options={"enable_verifier": True, "max_retries": 1},
        metadata={},
    )
    events = _collect_events(request)
    event_types = [item["eventType"] for item in events]
    assert "verifier_failed" in event_types
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    assert "review_completed" in event_types


def test_langgraph_zero_issue_short_circuit(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [],
            "summary": {
                "issuesCount": 0,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    request = InternalReviewRunRequest(
        taskId="rev_langgraph_zero_issue",
        codeText="class snippet { int plus(int a, int b){ return a+b; } }",
        language="java",
        sourceType="snippet",
        options={},
        metadata={},
    )
    events = _collect_events(request)
    event_types = [item["eventType"] for item in events]
    assert "planner_started" not in event_types
    assert "fixer_started" not in event_types
    assert event_types[-1] == "review_completed"
