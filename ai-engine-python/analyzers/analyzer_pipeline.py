from __future__ import annotations

from typing import Any

from core.diagnostics import build_diagnostic


def validate_day2_input(code_text: str, language: str) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    if not code_text or not code_text.strip():
        diagnostics.append(
            build_diagnostic(
                "EMPTY_INPUT",
                "codeText must not be empty",
                source="state_graph",
                level="error",
            )
        )
    if (language or "").lower() != "java":
        diagnostics.append(
            build_diagnostic(
                "UNSUPPORTED_LANGUAGE",
                "day2 analyzer only supports language=java",
                source="state_graph",
                level="error",
                details={"language": language},
            )
        )
    return diagnostics


def build_context_summary(ast_result: dict[str, Any]) -> dict[str, Any]:
    classes = ast_result.get("classes", []) or []
    class_summary: list[dict[str, Any]] = []
    methods_summary: list[dict[str, Any]] = []
    fields_summary: list[dict[str, Any]] = []

    for class_item in classes:
        class_summary.append(
            {
                "name": class_item.get("name"),
                "qualifiedName": class_item.get("qualifiedName"),
                "startLine": class_item.get("startLine"),
                "endLine": class_item.get("endLine"),
                "methodsCount": len(class_item.get("methods", []) or []),
                "fieldsCount": len(class_item.get("fields", []) or []),
            }
        )
        for method in class_item.get("methods", []) or []:
            methods_summary.append(
                {
                    "ownerClass": class_item.get("name"),
                    "name": method.get("name"),
                    "signature": method.get("signature"),
                    "startLine": method.get("startLine"),
                    "endLine": method.get("endLine"),
                }
            )
        for field in class_item.get("fields", []) or []:
            fields_summary.append(
                {
                    "ownerClass": class_item.get("name"),
                    "name": field.get("name"),
                    "signature": field.get("signature"),
                    "startLine": field.get("startLine"),
                    "endLine": field.get("endLine"),
                }
            )

    return {
        "package": ast_result.get("package"),
        "imports": ast_result.get("imports", []) or [],
        "classes": class_summary,
        "methods": methods_summary,
        "fields": fields_summary,
    }


def build_analyzer_summary(
    *,
    language: str,
    ast_result: dict[str, Any],
    symbol_graph_result: dict[str, Any],
    semgrep_result: dict[str, Any],
) -> dict[str, Any]:
    ast_summary = ast_result.get("summary", {}) or {}
    symbol_summary = symbol_graph_result.get("summary", {}) or {}
    semgrep_summary = semgrep_result.get("summary", {}) or {}

    return {
        "language": language.lower(),
        "classesCount": int(ast_summary.get("classesCount", 0)),
        "methodsCount": int(ast_summary.get("methodsCount", 0)),
        "fieldsCount": int(ast_summary.get("fieldsCount", 0)),
        "symbolsCount": len(symbol_graph_result.get("symbols", []) or []),
        "issuesCount": int(semgrep_summary.get("issuesCount", 0)),
        "callEdgesCount": int(symbol_summary.get("callEdgesCount", 0)),
        "engines": ["tree-sitter", "semgrep"],
    }


def compose_day2_output(
    *,
    language: str,
    ast_result: dict[str, Any],
    symbol_graph_result: dict[str, Any],
    semgrep_result: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = _merge_diagnostics(
        ast_result.get("diagnostics", []) or [],
        symbol_graph_result.get("diagnostics", []) or [],
        semgrep_result.get("diagnostics", []) or [],
    )
    context_summary = build_context_summary(ast_result)
    analyzer_summary = build_analyzer_summary(
        language=language,
        ast_result=ast_result,
        symbol_graph_result=symbol_graph_result,
        semgrep_result=semgrep_result,
    )

    return {
        "issues": semgrep_result.get("issues", []) or [],
        "symbols": symbol_graph_result.get("symbols", []) or [],
        "relations": symbol_graph_result.get("relations", []) or [],
        "contextSummary": context_summary,
        "analyzerSummary": analyzer_summary,
        "diagnostics": diagnostics,
    }


def _merge_diagnostics(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for item in group:
            key = (
                str(item.get("code", "")),
                str(item.get("source", "")),
                str(item.get("message", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged
