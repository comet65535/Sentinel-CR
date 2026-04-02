from __future__ import annotations

from typing import Any

DIAGNOSTIC_CODES = {
    "AST_PARSE_FAILED",
    "AST_PARSE_PARTIAL",
    "SYMBOL_GRAPH_PARTIAL",
    "SEMGREP_UNAVAILABLE",
    "SEMGREP_TIMEOUT",
    "SEMGREP_EXEC_ERROR",
    "EMPTY_INPUT",
    "UNSUPPORTED_LANGUAGE",
}


def build_diagnostic(
    code: str,
    message: str,
    *,
    source: str,
    level: str = "warning",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if code not in DIAGNOSTIC_CODES:
        raise ValueError(f"unsupported diagnostic code: {code}")

    diagnostic: dict[str, Any] = {
        "code": code,
        "message": message,
        "source": source,
        "level": level,
    }
    if details:
        diagnostic["details"] = details
    return diagnostic
