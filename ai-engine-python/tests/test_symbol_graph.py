from __future__ import annotations

from analyzers.symbol_graph import build_symbol_graph


def test_build_symbol_graph_emits_stable_symbol_fields_and_relations() -> None:
    code = """
public class UserService {
    private UserRepository repo;
    public User findUser(String id) {
        validate(id);
        return repo.findById(id);
    }
}
""".strip()
    ast_result = {
        "package": "com.example",
        "classes": [
            {
                "name": "UserService",
                "qualifiedName": "com.example.UserService",
                "startLine": 1,
                "endLine": 7,
                "fields": [
                    {
                        "name": "repo",
                        "signature": "UserRepository repo",
                        "startLine": 2,
                        "endLine": 2,
                    }
                ],
                "methods": [
                    {
                        "name": "findUser",
                        "signature": "User findUser(String id)",
                        "parameters": [{"name": "id", "type": "String"}],
                        "startLine": 3,
                        "endLine": 6,
                        "bodyStartLine": 3,
                        "bodyEndLine": 6,
                    }
                ],
            }
        ],
        "errors": [],
    }

    result = build_symbol_graph(code, ast_result)

    assert result["summary"]["classesCount"] == 1
    assert result["summary"]["methodsCount"] == 1
    assert result["summary"]["fieldsCount"] == 1

    class_symbol = next(item for item in result["symbols"] if item["kind"] == "class")
    method_symbol = next(item for item in result["symbols"] if item["kind"] == "method")
    field_symbol = next(item for item in result["symbols"] if item["kind"] == "field")

    for symbol in [class_symbol, method_symbol, field_symbol]:
        for key in [
            "symbolId",
            "kind",
            "name",
            "qualifiedName",
            "ownerClass",
            "signature",
            "startLine",
            "endLine",
        ]:
            assert key in symbol

    relation_types = {item["type"] for item in result["relations"]}
    assert "class_has_method" in relation_types
    assert "method_calls" in relation_types
    assert "variable_usage" in relation_types


def test_build_symbol_graph_marks_partial_when_ast_has_errors() -> None:
    result = build_symbol_graph(
        "public class Demo {}",
        {
            "classes": [],
            "errors": [{"message": "recoverable parse error"}],
        },
    )
    diagnostic_codes = {item.get("code") for item in result["diagnostics"]}
    assert "SYMBOL_GRAPH_PARTIAL" in diagnostic_codes
