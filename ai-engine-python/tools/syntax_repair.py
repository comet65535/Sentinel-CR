from __future__ import annotations

import difflib
import re
from typing import Any

CONTROL_HEADER_RE = re.compile(
    r"^(if|else\b|for|while|switch|try|catch|finally|do|synchronized|class|interface|enum|record)\b"
)
METHOD_DECL_RE = re.compile(
    r"^(?:(?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp)\s+)*"
    r"[A-Za-z_][\w<>\[\]]*\s+[A-Za-z_]\w*\s*\([^;{}]*\)\s*(?:throws\s+[A-Za-z0-9_.,\s]+)?$"
)
CONSTRUCTOR_DECL_RE = re.compile(
    r"^(?:(?:public|protected|private)\s+)?[A-Za-z_]\w*\s*\([^;{}]*\)\s*(?:throws\s+[A-Za-z0-9_.,\s]+)?$"
)
CONTROL_PREFIXES = ("if", "for", "while", "switch", "catch")


def propose_syntax_repair_candidates(
    code_text: str,
    issues: list[dict[str, Any]],
    last_failure: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not code_text.strip():
        return []

    hints = _collect_hints(issues, last_failure)
    specs = [
        {
            "candidate_id": "syntax_fix_primary",
            "aggressive": False,
            "fix_open_brace": hints["fix_open_brace"],
            "fix_semicolon": hints["fix_semicolon"],
            "balance_brace": True,
            "balance_paren": hints["fix_paren"] or hints["generic_syntax"],
        },
        {
            "candidate_id": "syntax_fix_aggressive",
            "aggressive": True,
            "fix_open_brace": True,
            "fix_semicolon": True,
            "balance_brace": True,
            "balance_paren": True,
        },
        {
            "candidate_id": "syntax_fix_balance_only",
            "aggressive": False,
            "fix_open_brace": False,
            "fix_semicolon": False,
            "balance_brace": True,
            "balance_paren": True,
        },
    ]

    unique_codes: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for spec in specs:
        repaired_code, applied_fixes = _repair_code(code_text, spec)
        if repaired_code == code_text:
            continue
        if repaired_code in unique_codes:
            continue
        unique_codes.add(repaired_code)
        candidates.append(
            {
                "candidate_id": spec["candidate_id"],
                "repaired_code": repaired_code,
                "applied_fixes": applied_fixes,
            }
        )
    return candidates


def build_unified_diff_from_repaired_code(
    original_code: str,
    repaired_code: str,
    target_file: str,
) -> str:
    normalized_target = target_file.replace("\\", "/").strip() or "snippet.java"
    if original_code == repaired_code:
        return ""

    diff_lines = list(
        difflib.unified_diff(
            original_code.splitlines(),
            repaired_code.splitlines(),
            fromfile=f"a/{normalized_target}",
            tofile=f"b/{normalized_target}",
            lineterm="",
        )
    )
    if not diff_lines:
        return ""

    return "\n".join([f"diff --git a/{normalized_target} b/{normalized_target}", *diff_lines])


def _repair_code(code_text: str, spec: dict[str, Any]) -> tuple[str, list[str]]:
    lines = code_text.splitlines()
    applied_fixes: list[str] = []

    if spec["fix_open_brace"]:
        lines = _fix_missing_open_braces(lines, applied_fixes, aggressive=bool(spec["aggressive"]))

    if spec["fix_semicolon"]:
        lines = _fix_missing_semicolons(lines, applied_fixes)

    if spec["balance_paren"]:
        lines = _balance_parentheses(lines, applied_fixes)

    if spec["balance_brace"]:
        lines = _balance_braces(lines, applied_fixes)

    repaired_code = "\n".join(lines)
    if code_text.endswith("\n"):
        repaired_code += "\n"
    return repaired_code, applied_fixes


def _fix_missing_open_braces(lines: list[str], applied_fixes: list[str], *, aggressive: bool) -> list[str]:
    patched = list(lines)
    for index, raw_line in enumerate(patched):
        stripped = _strip_inline_comment(raw_line).strip()
        if not stripped:
            continue
        if stripped.endswith("{") or stripped.endswith(";"):
            continue

        next_non_empty = _next_non_empty_line(patched, index)
        if next_non_empty == "{":
            continue

        if _is_control_header(stripped) or _is_method_signature(stripped, aggressive=aggressive):
            patched[index] = _append_before_comment(raw_line, " {")
            applied_fixes.append(f"insert_open_brace@line:{index + 1}")
    return patched


def _fix_missing_semicolons(lines: list[str], applied_fixes: list[str]) -> list[str]:
    patched = list(lines)
    for index, raw_line in enumerate(patched):
        stripped = _strip_inline_comment(raw_line).strip()
        if not stripped:
            continue
        if not _looks_like_missing_semicolon(stripped):
            continue
        patched[index] = _append_before_comment(raw_line, ";")
        applied_fixes.append(f"insert_semicolon@line:{index + 1}")
    return patched


def _balance_braces(lines: list[str], applied_fixes: list[str]) -> list[str]:
    patched = list(lines)
    brace_delta = _curly_brace_delta(patched)
    if brace_delta > 0:
        for _ in range(brace_delta):
            patched.append("}")
            applied_fixes.append("append_closing_brace@eof")
        return patched

    if brace_delta < 0:
        to_remove = -brace_delta
        for index in range(len(patched) - 1, -1, -1):
            if to_remove == 0:
                break
            if patched[index].strip() == "}":
                patched.pop(index)
                to_remove -= 1
                applied_fixes.append(f"remove_extra_closing_brace@line:{index + 1}")
    return patched


def _balance_parentheses(lines: list[str], applied_fixes: list[str]) -> list[str]:
    patched = list(lines)
    paren_delta = _paren_delta(patched)
    if paren_delta > 0:
        for index in range(len(patched) - 1, -1, -1):
            stripped = _strip_inline_comment(patched[index]).strip()
            if "(" not in stripped:
                continue
            patched[index] = _append_before_comment(patched[index], ")" * paren_delta)
            applied_fixes.append(f"append_closing_paren@line:{index + 1}")
            return patched
    elif paren_delta < 0:
        to_remove = -paren_delta
        for index in range(len(patched) - 1, -1, -1):
            if to_remove == 0:
                break
            stripped = _strip_inline_comment(patched[index]).rstrip()
            while to_remove > 0 and stripped.endswith(")"):
                stripped = stripped[:-1].rstrip()
                to_remove -= 1
                applied_fixes.append(f"remove_extra_closing_paren@line:{index + 1}")
            if stripped != _strip_inline_comment(patched[index]).rstrip():
                suffix = ""
                comment_index = patched[index].find("//")
                if comment_index >= 0:
                    suffix = " " + patched[index][comment_index:].lstrip()
                patched[index] = stripped + suffix
    return patched


def _collect_hints(issues: list[dict[str, Any]], last_failure: dict[str, Any] | None) -> dict[str, bool]:
    source_text_parts: list[str] = []
    for issue in issues:
        source_text_parts.append(str(issue.get("type") or issue.get("issueType") or ""))
        source_text_parts.append(str(issue.get("message") or ""))
        source_text_parts.append(str(issue.get("ruleId") or issue.get("rule_id") or ""))

    if last_failure:
        source_text_parts.append(str(last_failure.get("failed_stage") or ""))
        source_text_parts.append(str(last_failure.get("reason") or ""))
        source_text_parts.append(str(last_failure.get("detail") or ""))
        source_text_parts.append(str(last_failure.get("stderr_summary") or ""))

    text = " ".join(source_text_parts).lower()
    return {
        "generic_syntax": ("syntax_error" in text) or ("ast_parse_error" in text) or ("parsing" in text),
        "fix_open_brace": any(
            token in text
            for token in [
                "brace",
                "incomplete method body",
                "missing token",
                "'{' expected",
                "reached end of file while parsing",
                "method body",
            ]
        ),
        "fix_semicolon": ("semicolon" in text) or ("';' expected" in text),
        "fix_paren": ("paren" in text) or ("parenthes" in text) or ("')' expected" in text),
    }


def _looks_like_missing_semicolon(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped.endswith((";", "{", "}", ",", ":")):
        return False
    if stripped.startswith("//") or stripped.startswith("@"):
        return False
    if _is_control_header(stripped):
        return False
    if _is_method_signature(stripped, aggressive=True):
        return False
    if stripped.startswith(("return ", "throw ", "break", "continue")):
        return True
    if "=" in stripped:
        return True
    if re.search(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\([^)]*\)$", stripped):
        return True
    return False


def _is_control_header(stripped: str) -> bool:
    return CONTROL_HEADER_RE.match(stripped) is not None


def _is_method_signature(stripped: str, *, aggressive: bool) -> bool:
    if any(stripped.startswith(f"{prefix} ") for prefix in CONTROL_PREFIXES):
        return False
    if "." in stripped:
        return False
    if "=" in stripped:
        return False
    if METHOD_DECL_RE.match(stripped):
        return True
    if aggressive and CONSTRUCTOR_DECL_RE.match(stripped):
        return True
    return False


def _next_non_empty_line(lines: list[str], index: int) -> str | None:
    for cursor in range(index + 1, len(lines)):
        stripped = _strip_inline_comment(lines[cursor]).strip()
        if stripped:
            return stripped
    return None


def _append_before_comment(line: str, token: str) -> str:
    comment_index = line.find("//")
    if comment_index < 0:
        return line.rstrip() + token

    code_part = line[:comment_index].rstrip()
    comment_part = line[comment_index:].lstrip()
    if not code_part:
        return line
    return f"{code_part}{token}  {comment_part}"


def _curly_brace_delta(lines: list[str]) -> int:
    delta = 0
    for line in lines:
        sanitized = _sanitize_for_balance(line)
        delta += sanitized.count("{")
        delta -= sanitized.count("}")
    return delta


def _paren_delta(lines: list[str]) -> int:
    delta = 0
    for line in lines:
        sanitized = _sanitize_for_balance(line)
        delta += sanitized.count("(")
        delta -= sanitized.count(")")
    return delta


def _sanitize_for_balance(line: str) -> str:
    no_comment = _strip_inline_comment(line)
    return re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', no_comment)


def _strip_inline_comment(line: str) -> str:
    if "//" not in line:
        return line
    return line.split("//", 1)[0]
