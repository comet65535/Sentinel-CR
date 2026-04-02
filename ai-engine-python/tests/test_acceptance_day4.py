from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _run_review(code_text: str, *, task_id: str) -> list[dict]:
    request_body = {
        "taskId": task_id,
        "codeText": code_text,
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_day4_success_contract_and_event_order() -> None:
    events = _run_review(
        """
public class UserService {
    public String findName(String id) {
        User user = repo.findById(id).get();
        return user.getName();
    }
}
""".strip(),
        task_id="rev_day4_success",
    )
    event_types = [event["eventType"] for event in events]

    assert event_types.count("review_completed") == 1
    assert "patch_generated" in event_types
    assert "fixer_failed" not in event_types

    idx_search = event_types.index("case_memory_search_started")
    idx_completed = event_types.index("case_memory_completed")
    idx_fixer_started = event_types.index("fixer_started")
    idx_patch_generated = event_types.index("patch_generated")
    idx_fixer_completed = event_types.index("fixer_completed")
    idx_review_completed = event_types.index("review_completed")
    assert idx_search < idx_completed < idx_fixer_started < idx_patch_generated < idx_fixer_completed < idx_review_completed

    if "case_memory_matched" in event_types:
        idx_matched = event_types.index("case_memory_matched")
        assert idx_search < idx_matched < idx_completed

    payload = events[-1]["payload"]
    result = payload["result"]

    assert "memory" in result
    assert isinstance(result["memory"]["matches"], list)
    assert len(result["memory"]["matches"]) >= 0

    assert "patch" in result
    patch = result["patch"]
    assert patch["status"] == "generated"
    assert patch["format"] == "unified_diff"
    assert patch["content"].startswith("diff --git a/snippet.java b/snippet.java")
    assert patch["target_files"] == ["snippet.java"]
    assert "--- a/snippet.java" in patch["content"]
    assert "+++ b/snippet.java" in patch["content"]

    attempts = result["attempts"]
    assert len(attempts) >= 1
    assert attempts[0]["status"] == "generated"
    assert attempts[0]["failure_stage"] is None
    assert attempts[0]["failure_reason"] is None
    assert attempts[0]["failure_detail"] is None

    assert result["summary"]["final_outcome"] == "patch_generated"
    assert result["summary"]["memory_match_count"] >= 0
    assert payload["result"] is not None


def test_day4_failure_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.state_graph.run_fixer_agent",
        lambda **kwargs: {
            "ok": False,
            "patch_artifact": None,
            "attempt": {
                "attempt_no": 1,
                "patch_id": "patch_attempt_1",
                "status": "failed",
                "verified_level": "L0",
                "failure_stage": "fixer",
                "failure_reason": "no_valid_patch",
                "failure_detail": "forced by test",
                "memory_case_ids": [],
            },
        },
    )

    events = _run_review(
        """
public class Demo {
    public void run() {
        System.out.println("x");
    }
}
""".strip(),
        task_id="rev_day4_failure",
    )
    event_types = [event["eventType"] for event in events]

    assert event_types.count("review_completed") == 1
    assert "fixer_failed" in event_types
    assert "patch_generated" not in event_types
    assert "fixer_completed" not in event_types

    idx_search = event_types.index("case_memory_search_started")
    idx_completed = event_types.index("case_memory_completed")
    idx_fixer_started = event_types.index("fixer_started")
    idx_fixer_failed = event_types.index("fixer_failed")
    idx_review_completed = event_types.index("review_completed")
    assert idx_search < idx_completed < idx_fixer_started < idx_fixer_failed < idx_review_completed

    payload = events[-1]["payload"]
    result = payload["result"]
    patch = result["patch"]
    assert patch["status"] == "absent"
    assert result["summary"]["final_outcome"] == "failed_no_patch"

    attempts = result["attempts"]
    assert attempts[0]["status"] == "failed"
    assert attempts[0]["failure_stage"] == "fixer"
    assert attempts[0]["failure_reason"] == "no_valid_patch"
