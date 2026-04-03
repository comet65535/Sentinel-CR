from __future__ import annotations

import re
from typing import Any

from core.failure_taxonomy import classify_compile_failure_bucket
from tools.syntax_repair import build_unified_diff_from_repaired_code

METHOD_DECL_RE = re.compile(
    r"^\s*(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
    r"(?P<return>[A-Za-z_][\w<>\[\]]*)\s+(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:throws\s+[A-Za-z0-9_.,\s]+)?\s*\{\s*$"
)
VARIABLE_DECL_RE_TEMPLATE = r"(?P<prefix>\b{type_name}\s+{var_name}\s*)\s*;"
INCOMPATIBLE_TYPES_RE = re.compile(
    r"incompatible types:\s*(?P<left>[A-Za-z0-9_$.<>\[\]]+)\s+cannot be converted to\s+(?P<right>[A-Za-z0-9_$.<>\[\]]+)"
)
INCOMPATIBLE_TYPES_ZH_RE = re.compile(
    r"不兼容的类型[:：]\s*(?P<left>[A-Za-z0-9_$.<>\[\]]+)\s*无法转换为\s*(?P<right>[A-Za-z0-9_$.<>\[\]]+)"
)
UNINITIALIZED_RE = re.compile(r"variable\s+(?P<name>[A-Za-z_]\w*)\s+might not have been initialized")


def propose_semantic_repair_candidates(
    code_text: str,
    issues: list[dict[str, Any]],
    compile_failure: dict[str, Any] | None,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not code_text.strip():
        return [
            {
                "candidate_id": "semantic_fix_empty_input",
                "bucket": None,
                "repaired_code": "",
                "applied_fixes": [],
                "reason": "insufficient_context_for_semantic_fix",
            }
        ]

    context = context or {}
    failure_reason = ""
    failure_detail = ""
    bucket = None
    if isinstance(compile_failure, dict):
        failure_reason = str(compile_failure.get("reason") or "")
        failure_detail = str(
            compile_failure.get("stderr_summary")
            or compile_failure.get("detail")
            or compile_failure.get("failure_detail")
            or ""
        )
        bucket = str(compile_failure.get("compile_failure_bucket") or "").strip() or None
    if not bucket:
        bucket = classify_compile_failure_bucket(failure_detail, failure_reason)
    if not bucket:
        bucket = _infer_bucket_from_issues(issues)
    if not bucket:
        return [
            {
                "candidate_id": "semantic_fix_no_bucket",
                "bucket": None,
                "repaired_code": "",
                "applied_fixes": [],
                "reason": "no_semantic_candidate",
            }
        ]

    style_preferences = list((context.get("repo_profile") or {}).get("style_preferences") or [])
    lines = code_text.splitlines()
    candidates: list[dict[str, Any]] = []

    if bucket in {"missing_return", "incomplete_return_paths"}:
        generated = _repair_missing_return(lines, style_preferences=style_preferences, issue_bucket=bucket)
        if generated:
            candidates.append(generated)
    elif bucket == "uninitialized_local":
        generated = _repair_uninitialized_local(lines, failure_detail=failure_detail, style_preferences=style_preferences)
        if generated:
            candidates.append(generated)
    elif bucket == "simple_type_mismatch":
        generated = _repair_simple_type_mismatch(lines, failure_detail=failure_detail)
        if generated:
            candidates.append(generated)
    else:
        return [
            {
                "candidate_id": "semantic_fix_unsupported_bucket",
                "bucket": bucket,
                "repaired_code": "",
                "applied_fixes": [],
                "reason": "semantic_repair_unsupported",
            }
        ]

    normalized: list[dict[str, Any]] = []
    for idx, candidate in enumerate(candidates, start=1):
        repaired_code = str(candidate.get("repaired_code") or "")
        candidate_reason = str(candidate.get("reason") or "").strip()
        if candidate_reason and (not repaired_code or repaired_code == code_text):
            normalized.append(
                {
                    "candidate_id": f"semantic_fix_{bucket}_{idx}",
                    "bucket": bucket,
                    "repaired_code": "",
                    "applied_fixes": [],
                    "reason": candidate_reason,
                }
            )
            continue
        if not repaired_code or repaired_code == code_text:
            continue
        normalized.append(
            {
                "candidate_id": f"semantic_fix_{bucket}_{idx}",
                "bucket": bucket,
                "repaired_code": repaired_code,
                "applied_fixes": candidate.get("applied_fixes", []),
                "reason": candidate.get("reason"),
            }
        )
    return normalized


def build_semantic_repair_patch(
    *,
    original_code: str,
    repaired_code: str,
    target_file: str,
) -> str:
    return build_unified_diff_from_repaired_code(original_code, repaired_code, target_file)


def _repair_missing_return(
    lines: list[str],
    *,
    style_preferences: list[str],
    issue_bucket: str,
) -> dict[str, Any] | None:
    methods = _find_methods(lines)
    for method in methods:
        return_type = method["return_type"]
        if return_type.lower() == "void":
            continue

        default_return = _default_return_expr(return_type, style_preferences=style_preferences)
        if default_return is None:
            return {
                "repaired_code": "\n".join(lines),
                "applied_fixes": [],
                "reason": "unsafe_default_return",
            }

        body_lines = lines[method["body_start"] + 1 : method["body_end"]]
        has_any_return = any("return " in _strip_comment(item) for item in body_lines)
        if issue_bucket == "missing_return" and has_any_return:
            # Prefer methods that truly miss returns.
            pass
        insert_line = method["body_end"]
        indent = _line_indent(lines[insert_line - 1] if insert_line > 0 else lines[method["body_start"]])
        patched = list(lines)
        patched.insert(insert_line, f"{indent}return {default_return};")
        return {
            "repaired_code": "\n".join(patched),
            "applied_fixes": [f"append_default_return:{method['name']}"],
            "reason": None,
        }
    return None


def _repair_uninitialized_local(
    lines: list[str],
    *,
    failure_detail: str,
    style_preferences: list[str],
) -> dict[str, Any] | None:
    variable_match = UNINITIALIZED_RE.search(failure_detail)
    target_var = variable_match.group("name") if variable_match else None
    patched = list(lines)
    for idx, raw in enumerate(lines):
        stripped = _strip_comment(raw).strip()
        if not stripped or "=" in stripped or not stripped.endswith(";"):
            continue
        decl_match = re.match(r"^(?P<type>[A-Za-z_][\w<>\[\]]*)\s+(?P<name>[A-Za-z_]\w*)\s*;$", stripped)
        if not decl_match:
            continue
        var_name = decl_match.group("name")
        if target_var and var_name != target_var:
            continue
        var_type = decl_match.group("type")
        default_expr = _default_return_expr(var_type, style_preferences=style_preferences)
        if default_expr is None:
            return {
                "repaired_code": "\n".join(lines),
                "applied_fixes": [],
                "reason": "insufficient_context_for_semantic_fix",
            }
        indent = _line_indent(raw)
        patched[idx] = f"{indent}{var_type} {var_name} = {default_expr};"
        return {
            "repaired_code": "\n".join(patched),
            "applied_fixes": [f"initialize_local:{var_name}"],
            "reason": None,
        }
    return None


def _repair_simple_type_mismatch(lines: list[str], *, failure_detail: str) -> dict[str, Any] | None:
    mismatch = INCOMPATIBLE_TYPES_RE.search(failure_detail)
    if mismatch is None:
        mismatch = INCOMPATIBLE_TYPES_ZH_RE.search(failure_detail)
    if mismatch:
        source_type = _normalize_type_name(mismatch.group("left"))
        target_type = _normalize_type_name(mismatch.group("right"))
    else:
        source_type, target_type = "", ""

    patched = list(lines)
    for idx, raw in enumerate(lines):
        stripped = _strip_comment(raw).strip()
        return_match = re.match(r"^return\s+(?P<expr>.+);$", stripped)
        if return_match:
            expr = return_match.group("expr").strip()
            converted = _convert_expression(expr, source_type=source_type, target_type=target_type)
            if converted is None:
                inferred_source, inferred_target = _infer_conversion_from_method_context(lines, idx, expr)
                converted = _convert_expression(expr, source_type=inferred_source, target_type=inferred_target)
            if converted is not None:
                indent = _line_indent(raw)
                patched[idx] = f"{indent}return {converted};"
                return {
                    "repaired_code": "\n".join(patched),
                    "applied_fixes": ["return_type_conversion"],
                    "reason": None,
                }
        assign_match = re.match(r"^(?P<left>.+?)=\s*(?P<expr>[^;]+);$", stripped)
        if assign_match:
            expr = assign_match.group("expr").strip()
            converted = _convert_expression(expr, source_type=source_type, target_type=target_type)
            if converted is not None:
                indent = _line_indent(raw)
                left = assign_match.group("left").rstrip()
                patched[idx] = f"{indent}{left} = {converted};"
                return {
                    "repaired_code": "\n".join(patched),
                    "applied_fixes": ["assignment_type_conversion"],
                    "reason": None,
                }
    return None


def _convert_expression(expr: str, *, source_type: str, target_type: str) -> str | None:
    src = _normalize_type_name(source_type).lower()
    dst = _normalize_type_name(target_type).lower()
    if "string" in src and dst in {"int", "integer"}:
        return f"Integer.parseInt({expr})"
    if "string" in src and dst == "long":
        return f"Long.parseLong({expr})"
    if "string" in src and dst == "double":
        return f"Double.parseDouble({expr})"
    if "string" in src and dst == "float":
        return f"Float.parseFloat({expr})"
    if "string" in src and dst == "boolean":
        return f"Boolean.parseBoolean({expr})"
    if dst == "string":
        return f"String.valueOf({expr})"
    return None


def _normalize_type_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text


def _infer_conversion_from_method_context(lines: list[str], line_idx: int, expr: str) -> tuple[str, str]:
    expr_name = expr.strip()
    if not re.match(r"^[A-Za-z_]\w*$", expr_name):
        return "", ""

    method_line_idx = -1
    return_type = ""
    params = ""
    for idx in range(line_idx, -1, -1):
        match = METHOD_DECL_RE.match(_strip_comment(lines[idx]))
        if not match:
            continue
        method_line_idx = idx
        return_type = _normalize_type_name(match.group("return"))
        params_match = re.search(r"\((?P<params>[^)]*)\)", lines[idx])
        params = params_match.group("params") if params_match else ""
        break
    if method_line_idx < 0:
        return "", ""

    for item in params.split(","):
        token = item.strip()
        if not token:
            continue
        pair = token.split()
        if len(pair) < 2:
            continue
        param_type = _normalize_type_name(pair[0])
        param_name = pair[-1].strip()
        if param_name == expr_name:
            return param_type, return_type

    for idx in range(method_line_idx + 1, line_idx + 1):
        stripped = _strip_comment(lines[idx]).strip()
        local = re.match(r"^(?P<type>[A-Za-z_][\w<>\[\]]*)\s+(?P<name>[A-Za-z_]\w*)\s*(?:=|;)", stripped)
        if not local:
            continue
        if local.group("name") == expr_name:
            return _normalize_type_name(local.group("type")), return_type
    return "", return_type


def _default_return_expr(type_name: str, *, style_preferences: list[str]) -> str | None:
    lowered = type_name.strip().lower()
    if lowered == "string":
        if any("null_string" in pref for pref in style_preferences):
            return "null"
        return "\"\""
    if lowered in {"boolean", "boolean"}:
        return "false"
    if lowered in {"int", "integer", "short", "byte"}:
        return "0"
    if lowered == "long":
        return "0L"
    if lowered in {"double", "float"}:
        return "0.0"
    if lowered == "char":
        return "'\\0'"
    # Reference types are unsafe without stronger context.
    return None


def _find_methods(lines: list[str]) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        match = METHOD_DECL_RE.match(_strip_comment(line))
        if not match:
            continue
        body_end = _find_matching_brace(lines, idx)
        if body_end is None:
            continue
        methods.append(
            {
                "name": match.group("name"),
                "return_type": match.group("return"),
                "body_start": idx,
                "body_end": body_end,
            }
        )
    return methods


def _find_matching_brace(lines: list[str], start_idx: int) -> int | None:
    depth = 0
    saw_open = False
    for idx in range(start_idx, len(lines)):
        sanitized = _strip_strings(_strip_comment(lines[idx]))
        for ch in sanitized:
            if ch == "{":
                depth += 1
                saw_open = True
            elif ch == "}":
                depth -= 1
                if saw_open and depth == 0:
                    return idx
    return None


def _infer_bucket_from_issues(issues: list[dict[str, Any]]) -> str | None:
    text = " ".join(str(item.get("message") or "") for item in issues).lower()
    return classify_compile_failure_bucket(text, None)


def _strip_strings(text: str) -> str:
    return re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', text)


def _strip_comment(line: str) -> str:
    return line.split("//", 1)[0]


def _line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]
