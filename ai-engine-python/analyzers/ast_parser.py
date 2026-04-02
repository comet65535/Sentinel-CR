from __future__ import annotations

import re
from typing import Any

from core.diagnostics import build_diagnostic

JAVA_CLASS_NODE_TYPES = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "record_declaration",
}

_JAVA_PARSER: Any | None = None


def parse_java_code(code_text: str) -> dict[str, Any]:
    source_bytes = code_text.encode("utf-8", errors="ignore")
    result: dict[str, Any] = {
        "language": "java",
        "package": None,
        "imports": [],
        "classes": [],
        "errors": [],
        "syntaxIssues": [],
        "summary": {
            "classesCount": 0,
            "methodsCount": 0,
            "fieldsCount": 0,
            "importsCount": 0,
            "parseErrorsCount": 0,
            "syntaxIssuesCount": 0,
        },
        "diagnostics": [],
    }

    try:
        parser = _get_java_parser()
        tree = parser.parse(source_bytes)
    except Exception as exc:
        result["errors"].append({"message": str(exc)})
        result["diagnostics"].append(
            build_diagnostic(
                "AST_PARSE_FAILED",
                "java ast parser is unavailable",
                source="ast_parser",
                level="warning",
                details={"error": str(exc)},
            )
        )
        return result

    root = tree.root_node
    package_name = _extract_package(root, source_bytes)
    imports = _extract_imports(root, source_bytes)
    classes = _extract_classes(root, source_bytes, package_name)

    structural_errors = _collect_parse_errors(root)
    heuristic_errors = _collect_heuristic_parse_errors(code_text, classes)
    parse_errors = _dedupe_parse_errors(structural_errors + heuristic_errors)
    syntax_issues = _build_syntax_issues(parse_errors, classes)

    result["package"] = package_name
    result["imports"] = imports
    result["classes"] = classes
    result["errors"] = parse_errors
    result["syntaxIssues"] = syntax_issues

    methods_count = sum(len(class_item["methods"]) for class_item in classes)
    fields_count = sum(len(class_item["fields"]) for class_item in classes)

    result["summary"] = {
        "classesCount": len(classes),
        "methodsCount": methods_count,
        "fieldsCount": fields_count,
        "importsCount": len(imports),
        "parseErrorsCount": len(parse_errors),
        "syntaxIssuesCount": len(syntax_issues),
    }

    if parse_errors:
        result["diagnostics"].append(
            build_diagnostic(
                "AST_PARSE_PARTIAL",
                "java ast parsing completed with recoverable errors",
                source="ast_parser",
                level="warning",
                details={
                    "errorsCount": len(parse_errors),
                    "syntaxIssuesCount": len(syntax_issues),
                },
            )
        )

    return result


def _get_java_parser() -> Any:
    global _JAVA_PARSER
    if _JAVA_PARSER is not None:
        return _JAVA_PARSER

    from tree_sitter import Language, Parser
    import tree_sitter_java

    parser = Parser()
    lang_capsule = tree_sitter_java.language()

    language = None
    try:
        language = Language(lang_capsule)
    except Exception:
        language = lang_capsule

    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language

    _JAVA_PARSER = parser
    return parser


def _extract_package(root: Any, source_bytes: bytes) -> str | None:
    for node in _walk_nodes(root):
        if node.type != "package_declaration":
            continue
        raw_text = _node_text(source_bytes, node)
        clean = raw_text.replace("package", "", 1).replace(";", "").strip()
        return clean or None
    return None


def _extract_imports(root: Any, source_bytes: bytes) -> list[str]:
    imports: list[str] = []
    for node in _walk_nodes(root):
        if node.type != "import_declaration":
            continue
        raw_text = _node_text(source_bytes, node).strip()
        clean = raw_text.replace("import", "", 1).replace(";", "").strip()
        if clean:
            imports.append(clean)
    return imports


def _extract_classes(root: Any, source_bytes: bytes, package_name: str | None) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []
    for node in _walk_nodes(root):
        if node.type not in JAVA_CLASS_NODE_TYPES:
            continue
        class_name = _child_text(node, source_bytes, "name") or "AnonymousClass"
        modifiers = _extract_modifiers(node, source_bytes)
        body_node = node.child_by_field_name("body")
        fields = _extract_fields(body_node, source_bytes)
        methods = _extract_methods(body_node, source_bytes, class_name)
        qualified_name = f"{package_name}.{class_name}" if package_name else class_name
        classes.append(
            {
                "name": class_name,
                "qualifiedName": qualified_name,
                "modifiers": modifiers,
                "startLine": _start_line(node),
                "endLine": _end_line(node),
                "fields": fields,
                "methods": methods,
            }
        )
    return classes


def _extract_fields(body_node: Any, source_bytes: bytes) -> list[dict[str, Any]]:
    if body_node is None:
        return []

    fields: list[dict[str, Any]] = []
    for node in body_node.named_children:
        if node.type != "field_declaration":
            continue
        field_type = _child_text(node, source_bytes, "type")
        field_modifiers = _extract_modifiers(node, source_bytes)
        for declarator in _walk_nodes(node):
            if declarator.type != "variable_declarator":
                continue
            field_name = _child_text(declarator, source_bytes, "name") or _node_text(source_bytes, declarator)
            fields.append(
                {
                    "name": field_name,
                    "type": field_type,
                    "modifiers": field_modifiers,
                    "line": _start_line(declarator),
                    "startLine": _start_line(node),
                    "endLine": _end_line(node),
                    "signature": f"{field_type} {field_name}".strip(),
                }
            )
    return fields


def _extract_methods(body_node: Any, source_bytes: bytes, owner_class: str) -> list[dict[str, Any]]:
    if body_node is None:
        return []

    methods: list[dict[str, Any]] = []
    for node in body_node.named_children:
        if node.type not in {"method_declaration", "constructor_declaration"}:
            continue

        method_name = _child_text(node, source_bytes, "name") or owner_class
        return_type = _child_text(node, source_bytes, "type")
        parameters = _extract_parameters(node, source_bytes)
        modifiers = _extract_modifiers(node, source_bytes)
        parameters_signature = ", ".join(_format_parameter_signature(param) for param in parameters)
        if node.type == "constructor_declaration":
            signature = f"{method_name}({parameters_signature})"
        else:
            return_type_value = return_type or "void"
            signature = f"{return_type_value} {method_name}({parameters_signature})"

        body = node.child_by_field_name("body")
        methods.append(
            {
                "name": method_name,
                "ownerClass": owner_class,
                "signature": signature.strip(),
                "returnType": return_type,
                "parameters": parameters,
                "modifiers": modifiers,
                "startLine": _start_line(node),
                "endLine": _end_line(node),
                "bodyStartLine": _start_line(body) if body is not None else None,
                "bodyEndLine": _end_line(body) if body is not None else None,
            }
        )
    return methods


def _extract_parameters(method_node: Any, source_bytes: bytes) -> list[dict[str, Any]]:
    params_node = method_node.child_by_field_name("parameters")
    if params_node is None:
        return []

    parameters: list[dict[str, Any]] = []
    for param in _walk_nodes(params_node):
        if param.type not in {"formal_parameter", "spread_parameter", "receiver_parameter"}:
            continue
        param_name = _child_text(param, source_bytes, "name") or ""
        param_type = _child_text(param, source_bytes, "type")
        parameters.append({"name": param_name, "type": param_type})
    return parameters


def _extract_modifiers(node: Any, source_bytes: bytes) -> list[str]:
    modifiers_node = node.child_by_field_name("modifiers")
    if modifiers_node is None:
        return []
    raw = _node_text(source_bytes, modifiers_node)
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", raw)


def _collect_parse_errors(root: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for node in _walk_nodes(root):
        is_error = node.type == "ERROR"
        is_missing = bool(getattr(node, "is_missing", False))
        if not is_error and not is_missing:
            continue

        if is_missing:
            message = "Missing token or incomplete syntax"
            kind = "missing_node"
        else:
            message = "Malformed syntax near this location"
            kind = "error_node"

        errors.append(
            {
                "kind": kind,
                "message": message,
                "nodeType": node.type,
                "startLine": _start_line(node),
                "endLine": _end_line(node),
                "startColumn": node.start_point[1] + 1,
                "endColumn": node.end_point[1] + 1,
            }
        )
    return errors


def _collect_heuristic_parse_errors(code_text: str, classes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = code_text.splitlines()
    errors: list[dict[str, Any]] = []

    brace_delta = 0
    paren_delta = 0
    for line_no, raw_line in enumerate(lines, start=1):
        sanitized = _strip_strings(raw_line)
        brace_delta += sanitized.count("{") - sanitized.count("}")
        paren_delta += sanitized.count("(") - sanitized.count(")")

        stripped = sanitized.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped.endswith(("+", "-", "*", "/", "&&", "||", "=")):
            errors.append(
                {
                    "kind": "incomplete_statement",
                    "message": "Incomplete expression or statement",
                    "startLine": line_no,
                    "endLine": line_no,
                    "startColumn": max(1, len(raw_line.rstrip())),
                    "endColumn": max(1, len(raw_line.rstrip()) + 1),
                }
            )

        if _looks_like_missing_semicolon(stripped):
            errors.append(
                {
                    "kind": "missing_semicolon",
                    "message": "Missing semicolon or incomplete statement",
                    "startLine": line_no,
                    "endLine": line_no,
                    "startColumn": max(1, len(raw_line.rstrip())),
                    "endColumn": max(1, len(raw_line.rstrip()) + 1),
                }
            )

    if brace_delta != 0:
        errors.append(
            {
                "kind": "brace_mismatch",
                "message": "Unmatched curly braces detected",
                "startLine": max(1, len(lines)),
                "endLine": max(1, len(lines)),
                "startColumn": 1,
                "endColumn": 1,
            }
        )

    if paren_delta != 0:
        errors.append(
            {
                "kind": "paren_mismatch",
                "message": "Unmatched parentheses detected",
                "startLine": max(1, len(lines)),
                "endLine": max(1, len(lines)),
                "startColumn": 1,
                "endColumn": 1,
            }
        )

    errors.extend(_collect_method_body_heuristics(lines, classes))
    return errors


def _collect_method_body_heuristics(
    lines: list[str],
    classes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for class_item in classes:
        owner_class = str(class_item.get("name") or "")
        for method in class_item.get("methods", []) or []:
            method_name = str(method.get("name") or "")
            return_type = str(method.get("returnType") or "").strip()
            body_start = method.get("bodyStartLine")
            body_end = method.get("bodyEndLine")

            if body_start is None or body_end is None:
                errors.append(
                    {
                        "kind": "method_body_incomplete",
                        "message": f"Incomplete method body for {owner_class}.{method_name}",
                        "startLine": int(method.get("startLine") or 1),
                        "endLine": int(method.get("endLine") or method.get("startLine") or 1),
                        "startColumn": 1,
                        "endColumn": 1,
                    }
                )
                continue

            if not return_type or return_type.lower() == "void":
                continue

            start_index = max(int(body_start) - 1, 0)
            end_index = min(int(body_end), len(lines))
            body_lines = lines[start_index:end_index]
            body_compact = [line.strip() for line in body_lines if line.strip() and line.strip() not in {"{", "}"}]
            if not body_compact:
                errors.append(
                    {
                        "kind": "missing_return",
                        "message": f"Non-void method {owner_class}.{method_name} is missing return statement",
                        "startLine": int(method.get("startLine") or 1),
                        "endLine": int(method.get("endLine") or method.get("startLine") or 1),
                        "startColumn": 1,
                        "endColumn": 1,
                    }
                )
                continue

            has_return = any(re.search(r"\breturn\b", line) for line in body_compact)
            if not has_return:
                errors.append(
                    {
                        "kind": "missing_return",
                        "message": f"Non-void method {owner_class}.{method_name} is missing return statement",
                        "startLine": int(method.get("startLine") or 1),
                        "endLine": int(method.get("endLine") or method.get("startLine") or 1),
                        "startColumn": 1,
                        "endColumn": 1,
                    }
                )
    return errors


def _build_syntax_issues(
    parse_errors: list[dict[str, Any]],
    classes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sorted_errors = sorted(
        parse_errors,
        key=lambda item: (
            int(item.get("startLine") or 1),
            int(item.get("startColumn") or 1),
            str(item.get("message") or ""),
        ),
    )
    issues: list[dict[str, Any]] = []
    for index, error in enumerate(sorted_errors, start=1):
        line = int(error.get("startLine") or 1)
        column = int(error.get("startColumn") or 1)
        related_symbols = _resolve_related_symbols_for_line(line, classes)
        issue_id = f"AST-{index}"
        issue = {
            "issue_id": issue_id,
            "issueId": issue_id,
            "type": "syntax_error",
            "issueType": "syntax_error",
            "severity": "HIGH",
            "message": str(error.get("message") or "Syntax error"),
            "line": line,
            "column": column,
            "startLine": line,
            "endLine": int(error.get("endLine") or line),
            "startColumn": column,
            "endColumn": int(error.get("endColumn") or column),
            "location": f"snippet.java:{line}",
            "rule_id": "AST_PARSE_ERROR",
            "ruleId": "AST_PARSE_ERROR",
            "source": "ast_parser",
            "engine": "tree-sitter",
            "category": "syntax",
            "related_symbols": related_symbols,
            "relatedSymbols": related_symbols,
        }
        issues.append(issue)
    return issues


def _resolve_related_symbols_for_line(line: int, classes: list[dict[str, Any]]) -> list[str]:
    symbols: set[str] = set()
    for class_item in classes:
        class_name = str(class_item.get("name") or "")
        class_start = int(class_item.get("startLine") or 1)
        class_end = int(class_item.get("endLine") or class_start)
        if class_start <= line <= class_end and class_name:
            symbols.add(class_name)

        for method in class_item.get("methods", []) or []:
            method_name = str(method.get("name") or "")
            method_start = int(method.get("startLine") or class_start)
            method_end = int(method.get("endLine") or method_start)
            if method_start <= line <= method_end and class_name and method_name:
                symbols.add(f"{class_name}.{method_name}")
    return sorted(symbols)


def _dedupe_parse_errors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in items:
        key = (
            int(item.get("startLine") or 1),
            int(item.get("startColumn") or 1),
            int(item.get("endLine") or item.get("startLine") or 1),
            str(item.get("message") or ""),
            str(item.get("kind") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _looks_like_missing_semicolon(stripped_line: str) -> bool:
    if not stripped_line:
        return False
    if stripped_line.endswith((";", "{", "}", ",", ":")):
        return False
    if re.match(r"^(if|for|while|switch|catch|else|do|try)\b", stripped_line):
        return False
    if re.match(r"^(class|interface|enum|record)\b", stripped_line):
        return False
    if re.match(r"^(public|private|protected)\b.*\)$", stripped_line):
        return False
    if "=" in stripped_line or re.search(r"\breturn\b", stripped_line) or re.search(r"\bthrow\b", stripped_line):
        return True
    return False


def _strip_strings(line: str) -> str:
    return re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', line)


def _child_text(node: Any, source_bytes: bytes, field_name: str) -> str | None:
    child = node.child_by_field_name(field_name)
    if child is None:
        return None
    text = _node_text(source_bytes, child).strip()
    return text or None


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _walk_nodes(node: Any):
    yield node
    for child in node.children:
        yield from _walk_nodes(child)


def _start_line(node: Any) -> int:
    return int(node.start_point[0]) + 1


def _end_line(node: Any) -> int:
    return int(node.end_point[0]) + 1


def _format_parameter_signature(parameter: dict[str, Any]) -> str:
    name = str(parameter.get("name") or "").strip()
    param_type = str(parameter.get("type") or "").strip()
    if name and param_type:
        return f"{param_type} {name}".strip()
    return param_type or name
