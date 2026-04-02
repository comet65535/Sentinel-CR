from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from core.diagnostics import build_diagnostic

SEVERITY_CANONICAL = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def run_semgrep(
    code_text: str,
    *,
    language: str = "java",
    timeout_seconds: int = 20,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "issuesCount": 0,
        "ruleset": "auto",
        "engine": "semgrep",
        "severityBreakdown": {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        },
    }

    suffix = ".java" if language.lower() == "java" else ".txt"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            prefix="sentinel-semgrep-",
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(code_text)
            temp_path = Path(temp_file.name)

        command = [
            "semgrep",
            "--json",
            "--quiet",
            "--config",
            "auto",
            str(temp_path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_UNAVAILABLE",
                "semgrep executable is unavailable, fallback to empty issues",
                source="semgrep_runner",
                level="warning",
            )
        )
        return {"issues": [], "summary": summary, "diagnostics": diagnostics}
    except subprocess.TimeoutExpired:
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_TIMEOUT",
                "semgrep execution timed out, fallback to empty issues",
                source="semgrep_runner",
                level="warning",
                details={"timeoutSeconds": timeout_seconds},
            )
        )
        return {"issues": [], "summary": summary, "diagnostics": diagnostics}
    except Exception as exc:
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_EXEC_ERROR",
                "semgrep execution failed, fallback to empty issues",
                source="semgrep_runner",
                level="warning",
                details={"error": str(exc)},
            )
        )
        return {"issues": [], "summary": summary, "diagnostics": diagnostics}
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    parsed: dict[str, Any]
    try:
        parsed = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_EXEC_ERROR",
                "semgrep returned invalid json output",
                source="semgrep_runner",
                level="warning",
                details={
                    "returnCode": completed.returncode,
                    "stderr": (completed.stderr or "").strip(),
                    "error": str(exc),
                },
            )
        )
        return {"issues": [], "summary": summary, "diagnostics": diagnostics}

    if completed.returncode not in {0, 1} and not parsed.get("results"):
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_EXEC_ERROR",
                "semgrep returned non-success exit code",
                source="semgrep_runner",
                level="warning",
                details={
                    "returnCode": completed.returncode,
                    "stderr": (completed.stderr or "").strip(),
                },
            )
        )
        return {"issues": [], "summary": summary, "diagnostics": diagnostics}

    issues = _normalize_issues(parsed.get("results", []))
    for issue in issues:
        severity = issue["severity"]
        summary["severityBreakdown"][severity] += 1
    summary["issuesCount"] = len(issues)

    if parsed.get("errors"):
        diagnostics.append(
            build_diagnostic(
                "SEMGREP_EXEC_ERROR",
                "semgrep reported execution warnings or parser errors",
                source="semgrep_runner",
                level="warning",
                details={"errorsCount": len(parsed.get("errors", []))},
            )
        )

    return {"issues": issues, "summary": summary, "diagnostics": diagnostics}


def _normalize_issues(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(results, start=1):
        extra = item.get("extra", {}) if isinstance(item.get("extra"), dict) else {}
        metadata = extra.get("metadata", {}) if isinstance(extra.get("metadata"), dict) else {}
        start = item.get("start", {}) if isinstance(item.get("start"), dict) else {}
        end = item.get("end", {}) if isinstance(item.get("end"), dict) else {}

        rule_id = str(item.get("check_id") or "semgrep.unknown")
        issue_type = str(metadata.get("issue_type") or rule_id)
        severity = _normalize_severity(extra.get("severity"))
        start_line = int(start.get("line") or 1)
        end_line = int(end.get("line") or start_line)
        message = str(extra.get("message") or "Semgrep issue detected")
        snippet = str(extra.get("lines") or "").strip()
        category = str(metadata.get("category") or _default_category(rule_id))

        normalized.append(
            {
                "issueId": f"SG-{index}",
                "issueType": issue_type,
                "severity": severity,
                "ruleId": rule_id,
                "message": message,
                "line": start_line,
                "startLine": start_line,
                "endLine": end_line,
                "engine": "semgrep",
                "category": category,
                "snippet": snippet,
            }
        )
    return normalized


def _normalize_severity(raw_severity: Any) -> str:
    text = str(raw_severity or "").strip().upper()
    mapping = {
        "INFO": "LOW",
        "WARNING": "MEDIUM",
        "ERROR": "HIGH",
        "LOW": "LOW",
        "MEDIUM": "MEDIUM",
        "HIGH": "HIGH",
        "CRITICAL": "CRITICAL",
    }
    normalized = mapping.get(text, "MEDIUM")
    return normalized if normalized in SEVERITY_CANONICAL else "MEDIUM"


def _default_category(rule_id: str) -> str:
    lowered = rule_id.lower()
    if "security" in lowered or "sql" in lowered or "xss" in lowered:
        return "security"
    if "performance" in lowered:
        return "performance"
    return "code-quality"
