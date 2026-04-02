from __future__ import annotations

import json
from typing import Any

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


def _verification_success_l1() -> dict[str, Any]:
    return {
        "status": "passed",
        "verified_level": "L1",
        "passed_stages": ["patch_apply", "compile"],
        "failed_stage": None,
        "stages": [
            {
                "stage": "patch_apply",
                "status": "passed",
                "exit_code": 0,
                "stdout_summary": "patch applied",
                "stderr_summary": "",
                "reason": None,
                "retryable": False,
            },
            {
                "stage": "compile",
                "status": "passed",
                "exit_code": 0,
                "stdout_summary": "javac succeeded",
                "stderr_summary": "",
                "reason": None,
                "retryable": False,
            },
            {
                "stage": "lint",
                "status": "skipped",
                "exit_code": None,
                "stdout_summary": "",
                "stderr_summary": "",
                "reason": "lint command not configured",
                "retryable": False,
            },
            {
                "stage": "test",
                "status": "skipped",
                "exit_code": None,
                "stdout_summary": "",
                "stderr_summary": "",
                "reason": "test command not configured",
                "retryable": False,
            },
            {
                "stage": "security_rescan",
                "status": "skipped",
                "exit_code": None,
                "stdout_summary": "",
                "stderr_summary": "",
                "reason": "security rescan disabled",
                "retryable": False,
            },
        ],
        "summary": "verification passed at L1",
        "retryable": False,
        "failure_reason": None,
    }


def test_day5_l1_success_path_with_review_completed(monkeypatch) -> None:
    monkeypatch.setattr("core.state_graph.run_verifier_agent", lambda **kwargs: _verification_success_l1())

    events = _run_review(
        """
class snippet {
    String greet(String name) {
        if (name == null) {
            return "hi";
        }
        return "hi " + name;
    }
}
""".strip(),
        task_id="rev_day5_l1_success",
        options={"enable_verifier": True, "max_retries": 1},
    )
    event_types = [event["eventType"] for event in events]

    assert "patch_generated" in event_types
    assert "fixer_completed" in event_types
    assert "verifier_started" in event_types
    assert "patch_apply_started" in event_types
    assert "patch_apply_completed" in event_types
    assert "compile_started" in event_types
    assert "compile_completed" in event_types
    assert "verifier_completed" in event_types
    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types

    idx_verifier_started = event_types.index("verifier_started")
    idx_patch_apply_completed = event_types.index("patch_apply_completed")
    idx_compile_completed = event_types.index("compile_completed")
    idx_verifier_completed = event_types.index("verifier_completed")
    idx_review_completed = event_types.index("review_completed")
    assert idx_verifier_started < idx_patch_apply_completed < idx_compile_completed < idx_verifier_completed < idx_review_completed

    payload = events[-1]["payload"]
    result = payload["result"]
    assert result["patch"]["status"] == "generated"
    assert result["summary"]["final_outcome"] == "verified_patch"
    assert result["summary"]["verified_level"] == "L1"
    assert result["verification"]["verified_level"] == "L1"
    assert any(item["status"] == "skipped" for item in result["verification"]["stages"])
    assert result["attempts"][0]["status"] == "generated"


def test_day5_compile_failed_then_retry_success(monkeypatch) -> None:
    call_count = {"value": 0}

    def _verifier_with_retry(**kwargs) -> dict[str, Any]:
        call_count["value"] += 1
        if call_count["value"] == 1:
            return {
                "status": "failed",
                "verified_level": "L0",
                "passed_stages": ["patch_apply"],
                "failed_stage": "compile",
                "stages": [
                    {
                        "stage": "patch_apply",
                        "status": "passed",
                        "exit_code": 0,
                        "stdout_summary": "patch applied",
                        "stderr_summary": "",
                        "reason": None,
                        "retryable": False,
                    },
                    {
                        "stage": "compile",
                        "status": "failed",
                        "exit_code": 1,
                        "stdout_summary": "",
                        "stderr_summary": "cannot find symbol UserDTO",
                        "reason": "compile_failed",
                        "retryable": True,
                    },
                ],
                "summary": "verification failed at compile",
                "retryable": True,
                "failure_reason": "compile_failed",
            }
        return _verification_success_l1()

    monkeypatch.setattr("core.state_graph.run_verifier_agent", _verifier_with_retry)

    events = _run_review(
        """
class snippet {
    void run() {
        System.out.println("x");
    }
}
""".strip(),
        task_id="rev_day5_retry_success",
        options={"enable_verifier": True, "max_retries": 1},
    )
    event_types = [event["eventType"] for event in events]

    assert "compile_failed" in event_types
    assert "verifier_failed" in event_types
    assert "review_retry_scheduled" in event_types
    assert "review_retry_started" in event_types
    assert event_types.count("fixer_started") == 2
    assert event_types.count("verifier_started") == 2
    assert event_types.count("review_completed") == 1
    assert "review_failed" not in event_types

    failed_compile_event = next(event for event in events if event["eventType"] == "compile_failed")
    assert failed_compile_event["payload"]["reason"] == "compile_failed"
    assert failed_compile_event["payload"]["retryable"] is True

    payload = events[-1]["payload"]
    result = payload["result"]
    assert result["summary"]["retry_count"] == 1
    assert result["summary"]["attempt_count"] == 2
    assert result["summary"]["final_outcome"] == "verified_patch"
    assert result["verification"]["status"] == "passed"
    assert result["verification"]["verified_level"] == "L1"

    attempts = result["attempts"]
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["failure_stage"] == "compile"
    assert attempts[1]["status"] == "generated"
