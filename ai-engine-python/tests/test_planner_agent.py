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
