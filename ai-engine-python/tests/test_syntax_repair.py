from __future__ import annotations

import shutil

import pytest

from agents.fixer_agent import run_fixer_agent
from tools.patch_apply import apply_patch_to_snippet
from tools.sandbox_env import compile_java_snippet
from tools.syntax_repair import build_unified_diff_from_repaired_code, propose_syntax_repair_candidates


def _syntax_issue(line: int, message: str = "Malformed syntax near this location") -> dict:
    return {
        "issue_id": "AST-1",
        "type": "syntax_error",
        "issueType": "syntax_error",
        "severity": "HIGH",
        "message": message,
        "line": line,
        "column": 1,
        "ruleId": "AST_PARSE_ERROR",
        "source": "ast_parser",
    }


def _require_javac() -> None:
    if shutil.which("javac") is None:
        pytest.skip("javac is required for syntax repair compile verification")


def test_syntax_repair_missing_method_open_brace_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    String greet(String name)
        if (name == null) {
            return "hello";
        }
        return "hello " + name;
    }
}
""".strip()
    issues = [_syntax_issue(2, "Missing token or incomplete syntax")]

    candidates = propose_syntax_repair_candidates(original, issues, None)
    assert candidates
    repaired_code = str(candidates[0]["repaired_code"])
    diff_content = build_unified_diff_from_repaired_code(original, repaired_code, "snippet.java")

    assert "diff --git a/snippet.java b/snippet.java" in diff_content
    assert "@@ " in diff_content
    assert "Applied repair strategy" not in diff_content
    assert "Retry after" not in diff_content

    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_syntax_repair_missing_eof_closing_brace_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    int plus(int a, int b) {
        return a + b;
    }
""".strip()
    issues = [_syntax_issue(4, "Unmatched curly braces detected")]

    candidates = propose_syntax_repair_candidates(original, issues, None)
    assert candidates
    repaired_code = str(candidates[0]["repaired_code"])
    diff_content = build_unified_diff_from_repaired_code(original, repaired_code, "snippet.java")
    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_syntax_repair_missing_semicolon_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    int plus(int a, int b) {
        int c = a + b
        return c;
    }
}
""".strip()
    issues = [_syntax_issue(3, "Missing semicolon or incomplete statement")]

    candidates = propose_syntax_repair_candidates(original, issues, None)
    assert candidates
    repaired_code = str(candidates[0]["repaired_code"])
    diff_content = build_unified_diff_from_repaired_code(original, repaired_code, "snippet.java")
    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_fixer_returns_duplicate_patch_candidate_on_retry() -> None:
    code_text = """
class snippet {
    int plus(int a, int b) {
        int c = a + b
        return c;
    }
}
""".strip()
    issues = [_syntax_issue(3, "Missing semicolon or incomplete statement")]
    repair_plan = [{"issue_id": "AST-1", "priority": 1, "strategy": "syntax_fix"}]

    first_attempt = run_fixer_agent(
        code_text=code_text,
        repair_plan=repair_plan,
        issues=issues,
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        last_failure=None,
    )
    assert first_attempt["ok"] is True
    first_patch = first_attempt["patch_artifact"]
    assert first_patch is not None

    second_attempt = run_fixer_agent(
        code_text=code_text,
        repair_plan=repair_plan,
        issues=issues,
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=2,
        last_failure={
            "failed_stage": "compile",
            "stderr_summary": "simulated compile failure",
            "previous_patch_hash": first_patch["content_hash"],
        },
    )
    assert second_attempt["ok"] is False
    assert second_attempt["attempt"]["failure_reason"] == "duplicate_patch_candidate"
