from __future__ import annotations

import re
from typing import Any

HUNK_HEADER_RE = re.compile(r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def apply_patch_to_snippet(
    *,
    original_code: str,
    patch_content: str,
    target_file: str = "snippet.java",
) -> dict[str, Any]:
    stage = "patch_apply"
    parsed = _parse_unified_diff(patch_content=patch_content, target_file=target_file)
    if not parsed["ok"]:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 1,
            "stdout_summary": "",
            "stderr_summary": parsed["reason"],
            "reason": parsed["reason"],
            "retryable": True,
        }

    source_lines = original_code.splitlines()
    result = _apply_hunks(source_lines=source_lines, hunks=parsed["hunks"])
    if not result["ok"]:
        return {
            "stage": stage,
            "status": "failed",
            "exit_code": 1,
            "stdout_summary": "",
            "stderr_summary": result["reason"],
            "reason": result["reason"],
            "retryable": True,
        }

    patched_lines = result["patched_lines"]
    patched_code = "\n".join(patched_lines)
    if original_code.endswith("\n"):
        patched_code += "\n"

    return {
        "stage": stage,
        "status": "passed",
        "exit_code": 0,
        "stdout_summary": "unified diff applied",
        "stderr_summary": "",
        "reason": None,
        "retryable": False,
        "patched_code": patched_code,
    }


def _parse_unified_diff(*, patch_content: str, target_file: str) -> dict[str, Any]:
    if not patch_content or not patch_content.strip():
        return {"ok": False, "reason": "empty patch content"}

    lines = patch_content.splitlines()
    if len(lines) < 4:
        return {"ok": False, "reason": "patch too short"}

    diff_line = lines[0].strip()
    old_line = lines[1].strip()
    new_line = lines[2].strip()
    expected_diff = f"diff --git a/{target_file} b/{target_file}"
    expected_old = f"--- a/{target_file}"
    expected_new = f"+++ b/{target_file}"
    if diff_line != expected_diff or old_line != expected_old or new_line != expected_new:
        return {
            "ok": False,
            "reason": f"patch target mismatch, expected {expected_diff}",
        }

    hunks: list[dict[str, Any]] = []
    index = 3
    while index < len(lines):
        header = lines[index]
        if not header.startswith("@@ "):
            index += 1
            continue
        match = HUNK_HEADER_RE.match(header)
        if match is None:
            return {"ok": False, "reason": f"invalid hunk header: {header}"}

        old_start = int(match.group("old_start"))
        old_count = int(match.group("old_count") or 1)
        new_start = int(match.group("new_start"))
        new_count = int(match.group("new_count") or 1)
        index += 1
        hunk_lines: list[str] = []
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line.startswith("\\ No newline at end of file"):
                index += 1
                continue
            hunk_lines.append(line)
            index += 1

        hunks.append(
            {
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": hunk_lines,
            }
        )

    if not hunks:
        return {"ok": False, "reason": "no hunk found in patch"}
    return {"ok": True, "hunks": hunks}


def _apply_hunks(*, source_lines: list[str], hunks: list[dict[str, Any]]) -> dict[str, Any]:
    patched: list[str] = []
    source_index = 0

    for hunk in hunks:
        old_start = int(hunk["old_start"]) - 1
        if old_start < source_index:
            return {"ok": False, "reason": "overlapping hunks are not supported"}
        if old_start > len(source_lines):
            return {"ok": False, "reason": f"hunk start out of bounds: {old_start + 1}"}

        patched.extend(source_lines[source_index:old_start])
        cursor = old_start

        for line in hunk["lines"]:
            if not line:
                return {"ok": False, "reason": "malformed hunk line"}

            prefix = line[0]
            text = line[1:]
            if prefix == " ":
                if cursor >= len(source_lines) or source_lines[cursor] != text:
                    return {"ok": False, "reason": f"context mismatch near line {cursor + 1}"}
                patched.append(text)
                cursor += 1
                continue
            if prefix == "-":
                if cursor >= len(source_lines) or source_lines[cursor] != text:
                    return {"ok": False, "reason": f"remove mismatch near line {cursor + 1}"}
                cursor += 1
                continue
            if prefix == "+":
                patched.append(text)
                continue
            return {"ok": False, "reason": f"unsupported hunk line prefix: {prefix}"}

        source_index = cursor

    patched.extend(source_lines[source_index:])
    return {"ok": True, "patched_lines": patched}
