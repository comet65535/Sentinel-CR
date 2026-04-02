from __future__ import annotations

import pytest

from analyzers.ast_parser import parse_java_code


def _has_parser_support() -> bool:
    result = parse_java_code("public class Probe {}")
    diagnostic_codes = {item.get("code") for item in result.get("diagnostics", [])}
    return "AST_PARSE_FAILED" not in diagnostic_codes


@pytest.mark.skipif(not _has_parser_support(), reason="tree-sitter-java is not available in this environment")
def test_parse_java_code_extracts_class_method_field_import() -> None:
    code = """
package com.example.demo;
import java.util.Optional;

public class UserService {
    private final String name = "x";

    public String findUser(String id) {
        return Optional.ofNullable(id).orElse(name);
    }
}
""".strip()

    result = parse_java_code(code)

    assert result["language"] == "java"
    assert result["package"] == "com.example.demo"
    assert "java.util.Optional" in result["imports"]
    assert result["summary"]["classesCount"] >= 1

    class_item = result["classes"][0]
    assert class_item["name"] == "UserService"
    assert class_item["methods"][0]["name"] == "findUser"
    assert class_item["fields"][0]["name"] == "name"
    assert class_item["startLine"] >= 1
    assert class_item["endLine"] >= class_item["startLine"]


def test_parse_java_code_handles_invalid_snippet_without_crashing() -> None:
    code = "public class Broken { public void x( {"
    result = parse_java_code(code)

    assert isinstance(result, dict)
    assert "classes" in result
    assert "diagnostics" in result
    diagnostic_codes = {item.get("code") for item in result["diagnostics"]}
    assert diagnostic_codes.intersection({"AST_PARSE_PARTIAL", "AST_PARSE_FAILED"})
