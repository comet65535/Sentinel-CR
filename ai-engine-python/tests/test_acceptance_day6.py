from __future__ import annotations

import json
import shutil
from typing import Any

import pytest
from fastapi.testclient import TestClient

from llm.clients import LlmCallResult
from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str, options: dict | None = None) -> list[dict]:
    request_body = {
        "taskId": task_id,
        "codeText": code_text,
        "language": "java",
        "sourceType": "snippet",
        "options": options or {},
        "metadata": {},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _require_javac() -> None:
    if shutil.which("javac") is None:
        pytest.skip("javac is required for day6 syntax-fix acceptance")


def test_day6_syntax_fix_end_to_end_missing_method_brace() -> None:
    _require_javac()
    events = _run_review(
        """
class snippet {
    String greet(String name)
        if (name == null) {
            return "hello";
        }
        return "hello " + name;
    }
}
""".strip(),
        task_id="rev_day6_syntax_fix_method_brace",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    event_types = [event["eventType"] for event in events]

    assert "patch_generated" in event_types
    assert "verifier_completed" in event_types
    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types

    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    repair_plan = result["repair_plan"]
    patch = result["patch"]

    assert any((item.get("type") or item.get("issueType")) == "syntax_error" for item in result["issues"])
    assert repair_plan and repair_plan[0]["strategy"] == "syntax_fix"
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] in {"L1", "L2", "L3", "L4"}
    assert summary["failed_stage"] is None
    assert summary["failure_reason"] is None
    assert "Syntax repair completed" in summary["user_message"]

    patch_content = str(patch["content"] or "")
    assert patch["status"] == "generated"
    assert patch["strategy_used"] == "syntax_fix"
    assert "diff --git a/snippet.java b/snippet.java" in patch_content
    assert "@@ " in patch_content
    assert "Applied repair strategy" not in patch_content
    assert "Retry after" not in patch_content


def test_day6_syntax_fix_missing_file_end_brace() -> None:
    _require_javac()
    events = _run_review(
        """
class snippet {
    int plus(int a, int b) {
        return a + b;
    }
""".strip(),
        task_id="rev_day6_syntax_fix_eof_brace",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] in {"L1", "L2", "L3", "L4"}
    assert result["patch"]["strategy_used"] == "syntax_fix"


def test_day6_syntax_fix_missing_semicolon() -> None:
    _require_javac()
    events = _run_review(
        """
class snippet {
    int plus(int a, int b) {
        int c = a + b
        return c;
    }
}
""".strip(),
        task_id="rev_day6_syntax_fix_semicolon",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] in {"L1", "L2", "L3", "L4"}
    assert result["patch"]["strategy_used"] == "syntax_fix"


def test_day6_retry_stops_when_patch_candidate_duplicates(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_verifier_agent",
        lambda **kwargs: {
            "status": "failed",
            "verified_level": "L0",
            "passed_stages": ["patch_apply"],
            "failed_stage": "compile",
            "stages": [
                {
                    "stage": "patch_apply",
                    "status": "passed",
                    "exit_code": 0,
                    "stdout_summary": "",
                    "stderr_summary": "",
                    "reason": None,
                    "retryable": False,
                },
                {
                    "stage": "compile",
                    "status": "failed",
                    "exit_code": 1,
                    "stdout_summary": "",
                    "stderr_summary": "simulated compile failure",
                    "reason": "compile_failed",
                    "retryable": True,
                },
            ],
            "summary": "forced verifier failure",
            "retryable": True,
            "failure_reason": "compile_failed",
        },
    )

    events = _run_review(
        """
class snippet {
    int plus(int a, int b) {
        int c = a + b
        return c;
    }
}
""".strip(),
        task_id="rev_day6_retry_duplicate_patch",
        options={"enable_verifier": True, "max_retries": 2, "enable_security_rescan": False},
    )
    event_types = [event["eventType"] for event in events]
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    assert "fixer_failed" in event_types

    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "failed_no_patch"
    assert summary["failure_reason"] == "duplicate_patch_candidate"
    assert "duplicated the previous attempt" in summary["user_message"]


def test_day6_zero_issue_short_circuit_returns_review_completed(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [],
            "summary": {
                "issuesCount": 0,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    events = _run_review(
        """
class snippet {
    int plus(int a, int b) {
        return a + b;
    }
}
""".strip(),
        task_id="rev_day6_no_fix_needed",
        options={"enable_verifier": True, "max_retries": 2},
    )
    event_types = [event["eventType"] for event in events]

    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types
    assert "planner_started" not in event_types
    assert "fixer_started" not in event_types
    assert "verifier_started" not in event_types

    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    assert summary["issue_count"] == 0
    assert summary["attempt_count"] == 0
    assert summary["no_fix_needed"] is True
    assert summary["failed_stage"] is None
    assert summary["failure_reason"] is None
    assert summary["failure_detail"] is None
    assert isinstance(summary["user_message"], str) and "No fix is needed" in summary["user_message"]
    assert result["patch"]["status"] == "absent"


def test_day6_non_syntax_fix_path_stays_compatible(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "null_pointer",
                    "severity": "MEDIUM",
                    "message": "null may dereference",
                    "line": 3,
                    "column": 1,
                    "ruleId": "forced.non.syntax",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    events = _run_review(
        """
class snippet {
    void run() {
        System.out.println("ok");
    }
}
""".strip(),
        task_id="rev_day6_non_syntax_compat",
        options={"enable_verifier": False},
    )
    result = events[-1]["payload"]["result"]
    assert result["summary"]["issue_count"] == 1
    assert result["summary"]["attempt_count"] >= 1
    assert result["patch"]["status"] in {"generated", "absent"}
    assert "summary" in result
    assert "verification" in result
    assert "memory" in result


def test_day7_result_contract_fields_are_stable() -> None:
    events = _run_review(
        """
class snippet {
    int plus(int a, int b) {
        return a + b;
    }
}
""".strip(),
        task_id="rev_day7_contract_fields",
        options={"enable_verifier": False, "context_policy": "lazy", "context_budget_tokens": 12000},
    )
    result = events[-1]["payload"]["result"]
    summary = result["summary"]

    assert "failure_taxonomy" in summary
    assert set(summary["failure_taxonomy"].keys()) == {"bucket", "code", "explanation"}
    assert "analyzer" in result
    assert "analyzer_evidence" in result
    assert "context_budget" in result
    assert "selected_context" in result
    assert "tool_trace" in result
    assert "llm_trace" in result
    assert "repo_profile" in result


def test_day7_semantic_compile_fix_missing_return_end_to_end(monkeypatch) -> None:
    _require_javac()
    monkeypatch.setattr("core.state_graph.retrieve_case_matches", lambda **kwargs: [])
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "missing_return",
                    "severity": "HIGH",
                    "message": "missing return statement",
                    "line": 2,
                    "column": 1,
                    "ruleId": "forced.semantic.missing_return",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 0, "HIGH": 1, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

    events = _run_review(
        """
class snippet {
    String greet(String name) {
        if (name == null) {
            return "hello";
        }
    }
}
""".strip(),
        task_id="rev_day7_semantic_missing_return",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    event_types = [event["eventType"] for event in events]
    assert "patch_generated" in event_types
    assert "verifier_completed" in event_types
    assert event_types[-1] == "review_completed"

    result = events[-1]["payload"]["result"]
    summary = result["summary"]
    patch = result["patch"]
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] in {"L1", "L2", "L3", "L4"}
    assert patch["strategy_used"] == "semantic_compile_fix"
    assert "diff --git a/snippet.java b/snippet.java" in str(patch["content"])
    assert "Applied repair strategy" not in str(patch["content"])
    assert "Retry after" not in str(patch["content"])


def test_day7_llm_trace_is_persisted_to_final_result(monkeypatch) -> None:
    monkeypatch.setattr("core.state_graph.retrieve_case_matches", lambda **kwargs: [])
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "custom_bug",
                    "severity": "MEDIUM",
                    "message": "requires llm_generation",
                    "line": 2,
                    "column": 1,
                    "ruleId": "forced.llm.issue",
                    "source": "semgrep",
                }
            ],
            "summary": {
                "issuesCount": 1,
                "ruleset": "auto",
                "engine": "semgrep",
                "severityBreakdown": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 0},
            },
            "diagnostics": [],
        },
    )

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
                                "@@ -1,5 +1,6 @@",
                                " class snippet {",
                                "     void run() {",
                                "         System.out.println(\"ok\");",
                                "+        int llmApplied = 1;",
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
                    "token_in": 12,
                    "token_out": 23,
                    "latency_ms": 4,
                    "json_mode": True,
                    "tool_mode": "off",
                    "cache_hit_tokens": 0,
                    "cache_miss_tokens": 12,
                },
            )

    monkeypatch.setattr("agents.fixer_agent.build_llm_client", lambda options: _StubClient())
    events = _run_review(
        """
class snippet {
    void run() {
        System.out.println("ok");
    }
}
""".strip(),
        task_id="rev_day7_llm_trace",
        options={"enable_verifier": False, "llm_enabled": True},
    )
    result = events[-1]["payload"]["result"]
    assert result["patch"]["strategy_used"] == "llm_generation"
    assert len(result["llm_trace"]) == 1
    assert result["llm_trace"][0]["phase"] == "fixer"
