from __future__ import annotations

import asyncio

from core.schemas import InternalReviewRunRequest
from core.state_graph import run_day2_state_graph, run_day3_state_graph


def _run_graph(request: InternalReviewRunRequest, *, use_day2_alias: bool = False) -> list[dict]:
    async def _collect() -> list[dict]:
        events = []
        iterator = run_day2_state_graph(request) if use_day2_alias else run_day3_state_graph(request)
        async for event in iterator:
            events.append(event.model_dump(by_alias=True))
        return events

    return asyncio.run(_collect())


def test_state_graph_emits_full_event_sequence(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.parse_java_code",
        lambda code: {
            "language": "java",
            "package": "com.example",
            "imports": ["java.util.Optional"],
            "classes": [
                {
                    "name": "Demo",
                    "qualifiedName": "com.example.Demo",
                    "startLine": 1,
                    "endLine": 6,
                    "fields": [],
                    "methods": [
                        {
                            "name": "run",
                            "signature": "void run()",
                            "parameters": [],
                            "startLine": 2,
                            "endLine": 5,
                            "bodyStartLine": 2,
                            "bodyEndLine": 5,
                        }
                    ],
                }
            ],
            "errors": [],
            "summary": {
                "classesCount": 1,
                "methodsCount": 1,
                "fieldsCount": 0,
                "importsCount": 1,
            },
            "diagnostics": [],
        },
    )
    monkeypatch.setattr(
        "core.state_graph.build_symbol_graph",
        lambda code, ast: {
            "symbols": [
                {
                    "symbolId": "class:com.example.Demo",
                    "kind": "class",
                    "name": "Demo",
                    "qualifiedName": "com.example.Demo",
                    "ownerClass": None,
                    "signature": None,
                    "startLine": 1,
                    "endLine": 6,
                }
            ],
            "relations": [],
            "summary": {
                "classesCount": 1,
                "methodsCount": 1,
                "fieldsCount": 0,
                "callEdgesCount": 0,
                "variableRefsCount": 0,
            },
            "diagnostics": [],
        },
    )
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
        taskId="rev_state_graph_ok",
        codeText="public class Demo { void run() {} }",
        language="java",
        sourceType="snippet",
    )
    events = _run_graph(request)
    event_types = [event["eventType"] for event in events]

    assert event_types == [
        "analysis_started",
        "ast_parsing_started",
        "ast_parsing_completed",
        "symbol_graph_started",
        "symbol_graph_completed",
        "semgrep_scan_started",
        "semgrep_scan_completed",
        "analyzer_completed",
        "planner_started",
        "issue_graph_built",
        "repair_plan_created",
        "planner_completed",
        "case_memory_search_started",
        "case_memory_completed",
        "fixer_started",
        "patch_generated",
        "fixer_completed",
        "review_completed",
    ]

    completed_payload = events[-1]["payload"]
    assert "result" in completed_payload
    assert "summary" in completed_payload["result"]
    assert "analyzer" in completed_payload["result"]
    assert "issues" in completed_payload["result"]
    assert "symbols" in completed_payload["result"]
    assert "contextSummary" in completed_payload["result"]
    assert "diagnostics" in completed_payload["result"]

    assert "issue_graph" in completed_payload
    assert "repair_plan" in completed_payload
    assert "issue_graph" in completed_payload["result"]
    assert "repair_plan" in completed_payload["result"]
    assert "memory" in completed_payload
    assert "patch" in completed_payload
    assert "attempts" in completed_payload
    assert completed_payload["summary"]["final_outcome"] in {
        "patch_generated_unverified",
        "failed_no_patch",
    }
    assert completed_payload["patch"]["status"] in {"generated", "absent"}
    assert all(item["status"] in {"generated", "failed"} for item in completed_payload["attempts"])

    assert "classes" not in completed_payload


def test_state_graph_uses_semgrep_warning_event(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.parse_java_code",
        lambda code: {
            "language": "java",
            "package": None,
            "imports": [],
            "classes": [],
            "errors": [],
            "summary": {"classesCount": 0, "methodsCount": 0, "fieldsCount": 0, "importsCount": 0},
            "diagnostics": [],
        },
    )
    monkeypatch.setattr(
        "core.state_graph.build_symbol_graph",
        lambda code, ast: {
            "symbols": [],
            "relations": [],
            "summary": {
                "classesCount": 0,
                "methodsCount": 0,
                "fieldsCount": 0,
                "callEdgesCount": 0,
                "variableRefsCount": 0,
            },
            "diagnostics": [],
        },
    )
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
            "diagnostics": [
                {
                    "code": "SEMGREP_UNAVAILABLE",
                    "message": "semgrep unavailable",
                    "source": "semgrep_runner",
                    "level": "warning",
                }
            ],
        },
    )

    request = InternalReviewRunRequest(
        taskId="rev_state_graph_warning",
        codeText="public class Demo {}",
        language="java",
        sourceType="snippet",
    )
    events = _run_graph(request)
    event_types = [event["eventType"] for event in events]
    assert "semgrep_scan_warning" in event_types
    assert "issue_graph_built" in event_types
    assert "repair_plan_created" in event_types
    assert "planner_completed" in event_types
    assert "case_memory_search_started" in event_types
    assert "fixer_started" in event_types
    assert "review_completed" in event_types


def test_state_graph_fails_on_empty_input() -> None:
    request = InternalReviewRunRequest(
        taskId="rev_state_graph_empty",
        codeText="   ",
        language="java",
        sourceType="snippet",
    )
    events = _run_graph(request)

    assert [event["eventType"] for event in events] == ["analysis_started", "review_failed"]
    diagnostics = events[-1]["payload"]["diagnostics"]
    assert any(item.get("code") == "EMPTY_INPUT" for item in diagnostics)


def test_state_graph_fails_on_unsupported_language() -> None:
    request = InternalReviewRunRequest(
        taskId="rev_state_graph_lang",
        codeText="print('hello')",
        language="python",
        sourceType="snippet",
    )
    events = _run_graph(request, use_day2_alias=True)

    assert [event["eventType"] for event in events] == ["analysis_started", "review_failed"]
    diagnostics = events[-1]["payload"]["diagnostics"]
    assert any(item.get("code") == "UNSUPPORTED_LANGUAGE" for item in diagnostics)


def test_state_graph_propagates_syntax_issue_into_final_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.parse_java_code",
        lambda code: {
            "language": "java",
            "package": None,
            "imports": [],
            "classes": [],
            "errors": [
                {
                    "message": "Missing semicolon or incomplete statement",
                    "startLine": 4,
                    "startColumn": 22,
                    "endLine": 4,
                    "endColumn": 23,
                }
            ],
            "syntaxIssues": [
                {
                    "issue_id": "AST-1",
                    "type": "syntax_error",
                    "severity": "HIGH",
                    "message": "Missing semicolon or incomplete statement",
                    "line": 4,
                    "column": 22,
                    "location": "snippet.java:4",
                    "rule_id": "AST_PARSE_ERROR",
                    "source": "ast_parser",
                    "related_symbols": [],
                }
            ],
            "summary": {
                "classesCount": 0,
                "methodsCount": 0,
                "fieldsCount": 0,
                "importsCount": 0,
                "parseErrorsCount": 1,
                "syntaxIssuesCount": 1,
            },
            "diagnostics": [],
        },
    )
    monkeypatch.setattr(
        "core.state_graph.build_symbol_graph",
        lambda code, ast: {
            "symbols": [],
            "relations": [],
            "summary": {
                "classesCount": 0,
                "methodsCount": 0,
                "fieldsCount": 0,
                "callEdgesCount": 0,
                "variableRefsCount": 0,
            },
            "diagnostics": [],
        },
    )
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
        taskId="rev_state_graph_syntax",
        codeText="public class Demo {",
        language="java",
        sourceType="snippet",
    )
    events = _run_graph(request)

    completed_payload = events[-1]["payload"]
    assert completed_payload["result"]["issues"]
    assert completed_payload["result"]["issues"][0]["type"] == "syntax_error"
    assert completed_payload["result"]["issue_graph"]["nodes"]
    assert completed_payload["result"]["repair_plan"]
