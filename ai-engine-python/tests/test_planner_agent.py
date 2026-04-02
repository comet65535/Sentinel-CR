from __future__ import annotations

from agents.planner_agent import run_planner_agent


def test_run_planner_agent_returns_graph_plan_and_summary() -> None:
    issues = [
        {
            "issueId": "SG-1",
            "issueType": "sql_injection",
            "severity": "HIGH",
            "line": 18,
            "startLine": 18,
            "endLine": 18,
        },
        {
            "issueId": "SG-2",
            "issueType": "missing_validation",
            "severity": "MEDIUM",
            "line": 18,
            "startLine": 18,
            "endLine": 18,
        },
    ]
    symbols = [
        {
            "symbolId": "method:UserService.findUser(String)",
            "kind": "method",
            "name": "findUser",
            "ownerClass": "UserService",
            "signature": "User findUser(String id)",
            "startLine": 10,
            "endLine": 25,
        }
    ]
    context_summary = {
        "package": "com.example",
        "imports": ["java.sql.Statement"],
    }

    output = run_planner_agent(issues=issues, symbols=symbols, context_summary=context_summary)

    assert "issue_graph" in output
    assert "repair_plan" in output
    assert "planner_summary" in output

    graph = output["issue_graph"]
    plan = output["repair_plan"]
    summary = output["planner_summary"]

    assert graph["schema_version"] == "day3.v1"
    assert isinstance(graph["nodes"], list)
    assert isinstance(graph["edges"], list)

    assert isinstance(plan, list)
    assert all("issue_id" in item and "priority" in item and "strategy" in item for item in plan)

    assert summary == {
        "total_issues": 2,
        "total_nodes": len(graph["nodes"]),
        "total_edges": len(graph["edges"]),
        "total_plans": len(plan),
        "high_severity_count": 1,
        "requires_test_count": sum(1 for node in graph["nodes"] if node["requires_test"]),
    }


def test_run_planner_agent_handles_syntax_error_input() -> None:
    issues = [
        {
            "issue_id": "AST-1",
            "type": "syntax_error",
            "severity": "HIGH",
            "message": "Missing semicolon or incomplete statement",
            "line": 4,
            "column": 18,
            "source": "ast_parser",
            "rule_id": "AST_PARSE_ERROR",
            "related_symbols": ["Demo.greet"],
        }
    ]
    symbols = [
        {
            "symbolId": "method:Demo.greet(String)",
            "kind": "method",
            "name": "greet",
            "ownerClass": "Demo",
            "signature": "String greet(String name)",
            "startLine": 2,
            "endLine": 6,
        }
    ]

    output = run_planner_agent(issues=issues, symbols=symbols, context_summary={})
    graph = output["issue_graph"]
    plan = output["repair_plan"]

    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["type"] == "syntax_error"
    assert graph["nodes"][0]["strategy_hint"] == "syntax_fix"
    assert graph["nodes"][0]["requires_test"] is False

    assert len(plan) == 1
    assert plan[0]["strategy"] == "syntax_fix"
