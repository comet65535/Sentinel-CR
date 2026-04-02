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
        "summary": {
            "classesCount": 0,
            "methodsCount": 0,
            "fieldsCount": 0,
            "importsCount": 0,
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
    parse_errors = _collect_parse_errors(root)

    result["package"] = package_name
    result["imports"] = imports
    result["classes"] = classes
    result["errors"] = parse_errors

    methods_count = sum(len(class_item["methods"]) for class_item in classes)
    fields_count = sum(len(class_item["fields"]) for class_item in classes)

    result["summary"] = {
        "classesCount": len(classes),
        "methodsCount": methods_count,
        "fieldsCount": fields_count,
        "importsCount": len(imports),
    }

    if parse_errors:
        result["diagnostics"].append(
            build_diagnostic(
                "AST_PARSE_PARTIAL",
                "java ast parsing completed with recoverable errors",
                source="ast_parser",
                level="warning",
                details={"errorsCount": len(parse_errors)},
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
        if node.type != "ERROR":
            continue
        errors.append(
            {
                "message": "recoverable parse error",
                "nodeType": node.type,
                "startLine": _start_line(node),
                "endLine": _end_line(node),
                "startColumn": node.start_point[1] + 1,
                "endColumn": node.end_point[1] + 1,
            }
        )
    return errors


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
