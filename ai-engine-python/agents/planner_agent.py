from __future__ import annotations

from typing import Any

from core.issue_graph import build_issue_graph, build_repair_plan


def run_planner_agent(
    *,
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
) -> dict[str, Any]:
    issue_graph = build_issue_graph(issues=issues, symbols=symbols, context_summary=context_summary)
    repair_plan = build_repair_plan(issue_graph)

    nodes = issue_graph.get("nodes", [])
    planner_summary = {
        "total_issues": len(issues),
        "total_nodes": len(nodes),
        "total_edges": len(issue_graph.get("edges", [])),
        "total_plans": len(repair_plan),
        "high_severity_count": sum(
            1 for node in nodes if str(node.get("severity", "")).upper() in {"HIGH", "CRITICAL"}
        ),
        "requires_test_count": sum(1 for node in nodes if bool(node.get("requires_test", False))),
    }

    return {
        "issue_graph": issue_graph,
        "repair_plan": repair_plan,
        "planner_summary": planner_summary,
    }
