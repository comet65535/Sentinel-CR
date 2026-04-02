from __future__ import annotations

import re
from typing import Any

from core.diagnostics import build_diagnostic

JAVA_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "new",
    "throw",
    "assert",
    "synchronized",
    "this",
    "super",
}


def build_symbol_graph(code_text: str, ast_result: dict[str, Any]) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    code_lines = code_text.splitlines()

    classes = ast_result.get("classes", []) or []
    classes_count = len(classes)
    methods_count = 0
    fields_count = 0
    call_edges_count = 0
    variable_refs_count = 0

    seen_relations: set[tuple[Any, ...]] = set()

    for class_item in classes:
        class_name = str(class_item.get("name") or "AnonymousClass")
        class_qualified_name = str(class_item.get("qualifiedName") or class_name)
        class_symbol_id = f"class:{class_qualified_name}"
        symbols.append(
            {
                "symbolId": class_symbol_id,
                "kind": "class",
                "name": class_name,
                "qualifiedName": class_qualified_name,
                "ownerClass": None,
                "signature": None,
                "startLine": int(class_item.get("startLine", 1)),
                "endLine": int(class_item.get("endLine", class_item.get("startLine", 1))),
            }
        )

        class_fields = class_item.get("fields", []) or []
        class_methods = class_item.get("methods", []) or []
        fields_count += len(class_fields)
        methods_count += len(class_methods)

        for field in class_fields:
            field_name = str(field.get("name") or "unknownField")
            field_signature = str(field.get("signature") or "").strip() or None
            field_symbol_id = f"field:{class_name}.{field_name}"
            symbols.append(
                {
                    "symbolId": field_symbol_id,
                    "kind": "field",
                    "name": field_name,
                    "qualifiedName": f"{class_qualified_name}.{field_name}",
                    "ownerClass": class_name,
                    "signature": field_signature,
                    "startLine": int(field.get("startLine", field.get("line", 1))),
                    "endLine": int(field.get("endLine", field.get("line", 1))),
                }
            )
            _append_relation(
                relations,
                seen_relations,
                {"type": "class_has_field", "from": class_symbol_id, "to": field_symbol_id},
            )

        for method in class_methods:
            method_name = str(method.get("name") or "unknownMethod")
            parameters = method.get("parameters", []) or []
            param_types = [str(parameter.get("type") or "?").strip() or "?" for parameter in parameters]
            method_symbol_id = _build_method_symbol_id(class_name, method_name, param_types)
            method_signature = str(method.get("signature") or "").strip() or None
            method_start = int(method.get("startLine", 1))
            method_end = int(method.get("endLine", method_start))
            symbols.append(
                {
                    "symbolId": method_symbol_id,
                    "kind": "method",
                    "name": method_name,
                    "qualifiedName": f"{class_qualified_name}.{method_name}",
                    "ownerClass": class_name,
                    "signature": method_signature,
                    "startLine": method_start,
                    "endLine": method_end,
                }
            )
            _append_relation(
                relations,
                seen_relations,
                {"type": "class_has_method", "from": class_symbol_id, "to": method_symbol_id},
            )

            try:
                method_calls = _extract_method_calls(
                    method=method,
                    owner_class=class_name,
                    method_symbol_id=method_symbol_id,
                    code_lines=code_lines,
                )
                for edge in method_calls:
                    _append_relation(relations, seen_relations, edge)
                call_edges_count += len(method_calls)

                variable_relations = _extract_variable_usage(
                    method=method,
                    owner_class=class_name,
                    method_symbol_id=method_symbol_id,
                    class_fields=class_fields,
                    code_lines=code_lines,
                )
                for relation in variable_relations:
                    _append_relation(relations, seen_relations, relation)
                variable_refs_count += len(variable_relations)
            except Exception as exc:
                diagnostics.append(
                    build_diagnostic(
                        "SYMBOL_GRAPH_PARTIAL",
                        "symbol graph extraction was partially completed",
                        source="symbol_graph",
                        level="warning",
                        details={
                            "ownerClass": class_name,
                            "method": method_name,
                            "error": str(exc),
                        },
                    )
                )

    if ast_result.get("errors"):
        diagnostics.append(
            build_diagnostic(
                "SYMBOL_GRAPH_PARTIAL",
                "symbol graph was built from partial ast",
                source="symbol_graph",
                level="warning",
                details={"astErrorsCount": len(ast_result.get("errors", []))},
            )
        )

    return {
        "symbols": symbols,
        "relations": relations,
        "summary": {
            "classesCount": classes_count,
            "methodsCount": methods_count,
            "fieldsCount": fields_count,
            "callEdgesCount": call_edges_count,
            "variableRefsCount": variable_refs_count,
        },
        "diagnostics": diagnostics,
    }


def _build_method_symbol_id(owner_class: str, method_name: str, param_types: list[str]) -> str:
    return f"method:{owner_class}.{method_name}({', '.join(param_types)})"


def _append_relation(
    relations: list[dict[str, Any]],
    seen_relations: set[tuple[Any, ...]],
    relation: dict[str, Any],
) -> None:
    key = (
        relation.get("type"),
        relation.get("from"),
        relation.get("to"),
        relation.get("line"),
    )
    if key in seen_relations:
        return
    seen_relations.add(key)
    relations.append(relation)


def _extract_method_calls(
    *,
    method: dict[str, Any],
    owner_class: str,
    method_symbol_id: str,
    code_lines: list[str],
) -> list[dict[str, Any]]:
    body_lines, body_start = _method_body_lines(method, code_lines)
    if not body_lines:
        return []

    relations: list[dict[str, Any]] = []
    for offset, line in enumerate(body_lines):
        line_no = body_start + offset

        for qualifier, call_name in re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            line,
        ):
            target = f"method:{qualifier}.{call_name}(?)"
            relations.append(
                {
                    "type": "method_calls",
                    "from": method_symbol_id,
                    "to": target,
                    "line": line_no,
                    "confidence": "medium",
                }
            )

        for call_name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", line):
            if call_name in JAVA_KEYWORDS:
                continue
            if f".{call_name}(" in line:
                continue
            target = f"method:{owner_class}.{call_name}(?)"
            relations.append(
                {
                    "type": "method_calls",
                    "from": method_symbol_id,
                    "to": target,
                    "line": line_no,
                    "confidence": "low",
                }
            )
    return relations


def _extract_variable_usage(
    *,
    method: dict[str, Any],
    owner_class: str,
    method_symbol_id: str,
    class_fields: list[dict[str, Any]],
    code_lines: list[str],
) -> list[dict[str, Any]]:
    body_lines, body_start = _method_body_lines(method, code_lines)
    if not body_lines:
        return []

    candidates: list[str] = []
    for field in class_fields:
        field_name = str(field.get("name") or "").strip()
        if field_name:
            candidates.append(field_name)
    for parameter in method.get("parameters", []) or []:
        param_name = str(parameter.get("name") or "").strip()
        if param_name:
            candidates.append(param_name)

    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for offset, line in enumerate(body_lines):
        line_no = body_start + offset
        for var_name in candidates:
            if not re.search(rf"\b{re.escape(var_name)}\b", line):
                continue
            key = (var_name, line_no)
            if key in seen:
                continue
            seen.add(key)
            relations.append(
                {
                    "type": "variable_usage",
                    "from": f"variable:{owner_class}.{var_name}",
                    "to": method_symbol_id,
                    "line": line_no,
                }
            )
    return relations


def _method_body_lines(method: dict[str, Any], code_lines: list[str]) -> tuple[list[str], int]:
    body_start = method.get("bodyStartLine")
    body_end = method.get("bodyEndLine")
    if not isinstance(body_start, int) or not isinstance(body_end, int):
        return [], 0
    if body_start < 1 or body_end < body_start:
        return [], 0

    start_index = max(body_start - 1, 0)
    end_index = min(body_end, len(code_lines))
    return code_lines[start_index:end_index], body_start
