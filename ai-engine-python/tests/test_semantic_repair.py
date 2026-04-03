from __future__ import annotations

import json
import shutil

import pytest

from agents.fixer_agent import run_fixer_agent
from llm.clients import LlmCallResult
from tools.patch_apply import apply_patch_to_snippet
from tools.sandbox_env import compile_java_snippet
from tools.semantic_repair import build_semantic_repair_patch, propose_semantic_repair_candidates


def _require_javac() -> None:
    if shutil.which("javac") is None:
        pytest.skip("javac is required for semantic repair compile verification")


def _compile_failure_for(code_text: str) -> dict:
    stage = compile_java_snippet(code_text=code_text, file_name="snippet.java")
    assert stage["status"] == "failed"
    return {
        "failed_stage": "compile",
        "reason": stage.get("reason"),
        "stderr_summary": stage.get("stderr_summary"),
        "compile_failure_bucket": stage.get("compile_failure_bucket"),
    }


def test_semantic_repair_missing_return_string_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    String greet(String name) {
        if (name == null) {
            return "hello";
        }
    }
}
""".strip()
    compile_failure = _compile_failure_for(original)
    issues = [{"type": "missing_return", "message": "missing return statement", "line": 2}]

    candidates = propose_semantic_repair_candidates(original, issues, compile_failure, {"repo_profile": {}})
    repaired = next(item for item in candidates if item.get("repaired_code"))
    diff_content = build_semantic_repair_patch(
        original_code=original,
        repaired_code=str(repaired["repaired_code"]),
        target_file="snippet.java",
    )

    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_semantic_repair_incomplete_return_paths_boolean_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    boolean ok(int v) {
        if (v > 0) {
            return true;
        }
    }
}
""".strip()
    compile_failure = _compile_failure_for(original)
    issues = [{"type": "incomplete_return_paths", "message": "not all code paths return a value", "line": 2}]

    candidates = propose_semantic_repair_candidates(original, issues, compile_failure, {"repo_profile": {}})
    repaired = next(item for item in candidates if item.get("repaired_code"))
    diff_content = build_semantic_repair_patch(
        original_code=original,
        repaired_code=str(repaired["repaired_code"]),
        target_file="snippet.java",
    )

    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_semantic_repair_uninitialized_local_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    int parse(String v) {
        int x;
        if (v != null) {
            x = Integer.parseInt(v);
        }
        return x;
    }
}
""".strip()
    compile_failure = _compile_failure_for(original)
    issues = [{"type": "uninitialized_local", "message": "variable x might not have been initialized", "line": 3}]

    candidates = propose_semantic_repair_candidates(original, issues, compile_failure, {"repo_profile": {}})
    repaired = next(item for item in candidates if item.get("repaired_code"))
    diff_content = build_semantic_repair_patch(
        original_code=original,
        repaired_code=str(repaired["repaired_code"]),
        target_file="snippet.java",
    )

    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_semantic_repair_simple_type_mismatch_compiles() -> None:
    _require_javac()
    original = """
class snippet {
    int parse(String v) {
        return v;
    }
}
""".strip()
    compile_failure = _compile_failure_for(original)
    issues = [{"type": "simple_type_mismatch", "message": "incompatible types", "line": 3}]

    candidates = propose_semantic_repair_candidates(original, issues, compile_failure, {"repo_profile": {}})
    repaired = next(item for item in candidates if item.get("repaired_code"))
    diff_content = build_semantic_repair_patch(
        original_code=original,
        repaired_code=str(repaired["repaired_code"]),
        target_file="snippet.java",
    )

    patch_stage = apply_patch_to_snippet(original_code=original, patch_content=diff_content, target_file="snippet.java")
    assert patch_stage["status"] == "passed"
    compile_stage = compile_java_snippet(code_text=patch_stage["patched_code"], file_name="snippet.java")
    assert compile_stage["status"] == "passed"


def test_semantic_retry_stops_on_duplicate_patch_candidate() -> None:
    code_text = """
class snippet {
    String greet(String name) {
        if (name == null) {
            return "hello";
        }
    }
}
""".strip()
    repair_plan = [{"issue_id": "ISSUE-1", "priority": 1, "strategy": "semantic_compile_fix"}]
    issues = [{"type": "missing_return", "message": "missing return statement", "line": 2}]
    compile_failure = _compile_failure_for(code_text)

    first = run_fixer_agent(
        code_text=code_text,
        repair_plan=repair_plan,
        issues=issues,
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        last_failure=compile_failure,
    )
    assert first["ok"] is True
    first_patch = first["patch_artifact"]
    assert first_patch is not None

    second = run_fixer_agent(
        code_text=code_text,
        repair_plan=repair_plan,
        issues=issues,
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=2,
        last_failure={
            **compile_failure,
            "previous_patch_hash": first_patch["content_hash"],
            "previous_patch_content": first_patch["content"],
        },
    )
    assert second["ok"] is False
    assert second["attempt"]["failure_reason"] == "duplicate_patch_candidate"


def test_fixer_records_llm_trace_when_enabled(monkeypatch) -> None:
    class _StubClient:
        def create_chat_completion(self, **kwargs):
            return LlmCallResult(
                ok=True,
                content=json.dumps(
                    {
                        "strategy": "llm_generation",
                        "patch": "\n".join(
                            [
                                "diff --git a/snippet.java b/snippet.java",
                                "--- a/snippet.java",
                                "+++ b/snippet.java",
                                "@@ -1,3 +1,4 @@",
                                " class snippet {",
                                "     void run() {",
                                "+        int repaired = 1;",
                                "     }",
                                " }",
                            ]
                        ),
                        "explanation": "llm patch",
                        "risk_level": "medium",
                    }
                ),
                error=None,
                raw=None,
                trace={
                    "phase": "fixer",
                    "prompt_name": "fixer_prompt",
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "token_in": 10,
                    "token_out": 20,
                    "latency_ms": 5,
                    "json_mode": True,
                    "tool_mode": "off",
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 10,
                },
            )

    monkeypatch.setattr("agents.fixer_agent.build_llm_client", lambda options: _StubClient())
    output = run_fixer_agent(
        code_text="""
class snippet {
    void run() {
    }
}
""".strip(),
        repair_plan=[{"issue_id": "ISSUE-1", "priority": 1, "strategy": "manual_review"}],
        issues=[{"type": "custom_bug", "message": "needs llm patch", "line": 2}],
        symbols=[],
        context_summary={},
        memory_matches=[],
        attempt_no=1,
        options={"llm_enabled": True},
    )
    assert output["ok"] is True
    assert output["patch_artifact"]["strategy_used"] == "llm_generation"
    assert len(output["llm_trace"]) == 1
    assert output["llm_trace"][0]["provider"] == "deepseek"
