from __future__ import annotations

from typing import Any

from core.diagnostics import build_diagnostic


SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


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
    merged_issues: list[dict[str, Any]],
    ast_syntax_issues: list[dict[str, Any]],
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
        "issuesCount": len(merged_issues),
        "syntaxErrorsCount": len(ast_syntax_issues),
        "semgrepIssuesCount": int(semgrep_summary.get("issuesCount", 0)),
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
    ast_syntax_issues = ast_result.get("syntaxIssues", []) or []
    semgrep_issues = semgrep_result.get("issues", []) or []
    issues = _merge_issues(ast_syntax_issues, semgrep_issues)

    context_summary = build_context_summary(ast_result)
    analyzer_summary = build_analyzer_summary(
        language=language,
        ast_result=ast_result,
        symbol_graph_result=symbol_graph_result,
        semgrep_result=semgrep_result,
        merged_issues=issues,
        ast_syntax_issues=ast_syntax_issues,
    )

    return {
        "issues": issues,
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


def _merge_issues(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for group in groups:
        for raw_issue in group:
            normalized = _normalize_issue(raw_issue)
            key = (
                normalized["type"],
                normalized["line"],
                normalized["column"],
                normalized["message"],
                normalized["source"],
                normalized["ruleId"],
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)

    merged.sort(
        key=lambda item: (
            _severity_rank(item.get("severity")),
            int(item.get("line") or 1),
            str(item.get("source") or ""),
            str(item.get("issue_id") or item.get("issueId") or ""),
        )
    )

    next_id = 1
    existing_ids = {
        str(item.get("issue_id") or item.get("issueId") or "").strip()
        for item in merged
        if str(item.get("issue_id") or item.get("issueId") or "").strip()
    }

    for item in merged:
        issue_id = str(item.get("issue_id") or item.get("issueId") or "").strip()
        if not issue_id:
            while f"ISSUE-{next_id}" in existing_ids:
                next_id += 1
            issue_id = f"ISSUE-{next_id}"
            next_id += 1
            existing_ids.add(issue_id)
        item["issue_id"] = issue_id
        item["issueId"] = issue_id

    return merged


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(issue)

    issue_type = str(
        issue.get("type")
        or issue.get("issue_type")
        or issue.get("issueType")
        or issue.get("ruleId")
        or issue.get("rule_id")
        or "unknown_issue"
    ).strip()
    if issue_type == "parse_error":
        issue_type = "syntax_error"

    severity = str(issue.get("severity") or "MEDIUM").strip().upper()
    if severity not in SEVERITY_ORDER:
        severity = "MEDIUM"

    line = _to_int(issue.get("line"), default=None)
    if line is None:
        line = _to_int(issue.get("startLine"), default=1)

    column = _to_int(issue.get("column"), default=None)
    if column is None:
        column = _to_int(issue.get("startColumn"), default=1)

    start_line = _to_int(issue.get("startLine"), default=line)
    end_line = _to_int(issue.get("endLine"), default=start_line)
    start_column = _to_int(issue.get("startColumn"), default=column)
    end_column = _to_int(issue.get("endColumn"), default=start_column)

    source = str(issue.get("source") or issue.get("engine") or "unknown").strip()
    if issue_type == "syntax_error" and source in {"", "unknown"}:
        source = "ast_parser"

    rule_id = str(issue.get("ruleId") or issue.get("rule_id") or "").strip()
    if issue_type == "syntax_error" and not rule_id:
        rule_id = "AST_PARSE_ERROR"

    related_symbols = issue.get("related_symbols")
    if not isinstance(related_symbols, list):
        related_symbols = issue.get("relatedSymbols")
    if not isinstance(related_symbols, list):
        related_symbols = []

    message = str(issue.get("message") or "Issue detected").strip()
    location = str(issue.get("location") or f"snippet.java:{line}")

    normalized.update(
        {
            "type": issue_type,
            "issueType": issue_type,
            "severity": severity,
            "message": message,
            "line": line,
            "column": column,
            "startLine": start_line,
            "endLine": end_line,
            "startColumn": start_column,
            "endColumn": end_column,
            "location": location,
            "rule_id": rule_id,
            "ruleId": rule_id,
            "source": source,
            "related_symbols": related_symbols,
            "relatedSymbols": related_symbols,
        }
    )

    return normalized


def _severity_rank(value: Any) -> int:
    return SEVERITY_ORDER.get(str(value or "MEDIUM").upper(), 2)


def _to_int(value: Any, *, default: int | None = 0) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return int(float(text))
            except ValueError:
                pass
    if default is None:
        return None
    return default
