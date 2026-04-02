from __future__ import annotations

from core.issue_graph import build_issue_graph, build_repair_plan


def test_build_issue_graph_fills_issue_id_and_node_structure() -> None:
    issues = [
        {
            "issueType": "sql_injection",
            "severity": "HIGH",
            "line": 12,
            "snippet": "findUser(id)",
        },
        {
            "issueId": "CUSTOM-1",
            "issueType": "missing_validation",
            "severity": "MEDIUM",
            "line": 12,
        },
    ]
    symbols = [
        {
            "symbolId": "method:UserService.findUser(String)",
            "name": "findUser",
            "ownerClass": "UserService",
            "startLine": 10,
            "endLine": 20,
        }
    ]

    graph = build_issue_graph(issues=issues, symbols=symbols, context_summary={})

    assert graph["schema_version"] == "day3.v1"
    assert isinstance(graph["nodes"], list)
    assert isinstance(graph["edges"], list)

    issue_ids = [node["issue_id"] for node in graph["nodes"]]
    assert "ISSUE-1" in issue_ids
    assert issue_ids == sorted(issue_ids)

    required_fields = {
        "issue_id",
        "type",
        "severity",
        "location",
        "related_symbols",
        "depends_on",
        "conflicts_with",
        "fix_scope",
        "strategy_hint",
        "requires_test",
    }
    for node in graph["nodes"]:
        assert required_fields.issubset(node.keys())

    by_id = {node["issue_id"]: node for node in graph["nodes"]}
    assert by_id["ISSUE-1"]["strategy_hint"] == "parameterized_query"
    assert by_id["ISSUE-1"]["fix_scope"] == "single_file"
    assert by_id["ISSUE-1"]["depends_on"] == ["CUSTOM-1"]


def test_build_issue_graph_fix_scope_and_edges_are_predictable() -> None:
    issues = [
        {
            "issueId": "ISSUE-A",
            "issueType": "null_pointer",
            "severity": "LOW",
            "line": 50,
            "filePath": "Demo.java",
        },
        {
            "issueId": "ISSUE-B",
            "issueType": "bad_exception_handling",
            "severity": "HIGH",
            "line": 50,
            "filePath": "Demo.java",
        },
    ]
    symbols = [
        {
            "symbolId": "method:A.run()",
            "name": "run",
            "ownerClass": "A",
            "startLine": 40,
            "endLine": 60,
        },
        {
            "symbolId": "method:B.run()",
            "name": "run",
            "ownerClass": "B",
            "startLine": 45,
            "endLine": 55,
        },
    ]

    graph = build_issue_graph(issues=issues, symbols=symbols, context_summary={})
    by_id = {node["issue_id"]: node for node in graph["nodes"]}

    assert by_id["ISSUE-A"]["fix_scope"] == "multi_file"
    assert by_id["ISSUE-A"]["requires_test"] is True
    assert by_id["ISSUE-A"]["strategy_hint"] == "null_guard"
    assert by_id["ISSUE-B"]["strategy_hint"] == "exception_logging"
    assert "ISSUE-B" in by_id["ISSUE-A"]["conflicts_with"]

    edge_keys = [(edge["from_issue_id"], edge["to_issue_id"], edge["edge_type"]) for edge in graph["edges"]]
    assert edge_keys == sorted(edge_keys)
    assert ("ISSUE-A", "ISSUE-B", "conflicts_with") in edge_keys


def test_build_repair_plan_is_stable_and_sorted() -> None:
    issues = [
        {"issueId": "ISSUE-2", "issueType": "manual_check", "severity": "LOW", "line": 8},
        {"issueId": "ISSUE-1", "issueType": "sql_injection", "severity": "HIGH", "line": 8},
    ]
    symbols = [
        {
            "symbolId": "method:Demo.run()",
            "name": "run",
            "ownerClass": "Demo",
            "startLine": 1,
            "endLine": 30,
        }
    ]

    graph = build_issue_graph(issues=issues, symbols=symbols, context_summary={})
    plan = build_repair_plan(graph)

    assert isinstance(plan, list)
    assert [item["issue_id"] for item in plan] == ["ISSUE-1", "ISSUE-2"]
    assert [item["priority"] for item in plan] == [1, 2]
    assert plan == sorted(plan, key=lambda item: (item["priority"], item["issue_id"]))


def test_build_issue_graph_supports_syntax_error_strategy() -> None:
    issues = [
        {
            "issue_id": "AST-1",
            "type": "syntax_error",
            "severity": "HIGH",
            "message": "Missing semicolon or incomplete statement",
            "line": 4,
            "column": 22,
            "source": "ast_parser",
            "rule_id": "AST_PARSE_ERROR",
            "related_symbols": ["Demo.greet"],
        }
    ]
    symbols = [
        {
            "symbolId": "method:Demo.greet(String)",
            "name": "greet",
            "ownerClass": "Demo",
            "startLine": 2,
            "endLine": 6,
        }
    ]

    graph = build_issue_graph(issues=issues, symbols=symbols, context_summary={})
    assert len(graph["nodes"]) == 1

    node = graph["nodes"][0]
    assert node["issue_id"] == "AST-1"
    assert node["type"] == "syntax_error"
    assert node["fix_scope"] == "single_file"
    assert node["strategy_hint"] == "syntax_fix"
    assert node["requires_test"] is False

    plan = build_repair_plan(graph)
    assert len(plan) == 1
    assert plan[0]["issue_id"] == "AST-1"
    assert plan[0]["strategy"] == "syntax_fix"
