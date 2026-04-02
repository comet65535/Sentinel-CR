from __future__ import annotations

import json
import shutil
from typing import Any

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str, options: dict[str, Any] | None = None) -> list[dict]:
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
        pytest.skip("javac is required for real verifier acceptance test")


def _build_fixer_output(diff_content: str, attempt_no: int) -> dict[str, Any]:
    return {
        "ok": True,
        "patch_artifact": {
            "patch_id": f"patch_attempt_{attempt_no}",
            "attempt_no": attempt_no,
            "status": "generated",
            "format": "unified_diff",
            "content": diff_content,
            "explanation": "forced patch for day5 real verifier test",
            "risk_level": "low",
            "target_files": ["snippet.java"],
            "strategy_used": "test_stub",
            "memory_case_ids": [],
        },
        "attempt": {
            "attempt_no": attempt_no,
            "patch_id": f"patch_attempt_{attempt_no}",
            "status": "generated",
            "verified_level": "L0",
            "failure_stage": None,
            "failure_reason": None,
            "failure_detail": None,
            "memory_case_ids": [],
        },
    }


def _force_issue(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_semgrep",
        lambda code, language="java": {
            "issues": [
                {
                    "type": "null_check_missing",
                    "severity": "MEDIUM",
                    "message": "force fixer path for day5 acceptance",
                    "line": 3,
                    "column": 9,
                    "ruleId": "forced.day5.issue",
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


def test_day5_real_verifier_l1_success(monkeypatch) -> None:
    _require_javac()
    _force_issue(monkeypatch)

    def _stub_fixer(**kwargs: Any) -> dict[str, Any]:
        return _build_fixer_output(
            "\n".join(
                [
                    "diff --git a/snippet.java b/snippet.java",
                    "--- a/snippet.java",
                    "+++ b/snippet.java",
                    "@@ -1,5 +1,6 @@",
                    " class snippet {",
                    "     void run() {",
                    "         System.out.println(\"ok\");",
                    "+        int verified = 1;",
                    "     }",
                    " }",
                ]
            ),
            int(kwargs.get("attempt_no") or 1),
        )

    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        _stub_fixer,
    )

    events = _run_review(
        """
class snippet {
    void run() {
        System.out.println("ok");
    }
}
""".strip(),
        task_id="rev_day5_real_success",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    event_types = [event["eventType"] for event in events]

    assert "patch_apply_started" in event_types
    assert "patch_apply_completed" in event_types
    assert "compile_started" in event_types
    assert "compile_completed" in event_types
    assert "verifier_completed" in event_types
    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types

    payload = events[-1]["payload"]
    result = payload["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "verified_patch"
    assert summary["verified_level"] == "L1"
    assert summary["failed_stage"] is None
    assert summary["retry_exhausted"] is False
    assert result["verification"]["verified_level"] == "L1"


def test_day5_real_verifier_compile_failed_after_retry(monkeypatch) -> None:
    _require_javac()
    _force_issue(monkeypatch)

    def _stub_fixer(**kwargs: Any) -> dict[str, Any]:
        return _build_fixer_output(
            "\n".join(
                [
                    "diff --git a/snippet.java b/snippet.java",
                    "--- a/snippet.java",
                    "+++ b/snippet.java",
                    "@@ -1,5 +1,6 @@",
                    " class snippet {",
                    "     void run() {",
                    "         System.out.println(\"ok\");",
                    "+        UnknownType missing = null;",
                    "     }",
                    " }",
                ]
            ),
            int(kwargs.get("attempt_no") or 1),
        )

    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        _stub_fixer,
    )

    events = _run_review(
        """
class snippet {
    void run() {
        System.out.println("ok");
    }
}
""".strip(),
        task_id="rev_day5_real_compile_fail",
        options={"enable_verifier": True, "max_retries": 1, "enable_security_rescan": False},
    )
    event_types = [event["eventType"] for event in events]

    assert "patch_apply_completed" in event_types
    assert "compile_failed" in event_types
    assert "verifier_failed" in event_types
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types

    payload = events[-1]["payload"]
    result = payload["result"]
    summary = result["summary"]
    assert summary["final_outcome"] == "failed_after_retries"
    assert summary["failed_stage"] == "compile"
    assert summary["retry_exhausted"] is True
    assert isinstance(summary["failure_detail"], str) and summary["failure_detail"]
    assert isinstance(summary["user_message"], str) and summary["user_message"]
    assert result["verification"]["status"] == "failed"
