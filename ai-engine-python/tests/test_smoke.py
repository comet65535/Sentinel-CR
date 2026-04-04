from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _events_from_response(response) -> list[dict]:
    lines = [line for line in response.text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def test_internal_review_run_returns_ndjson_stream() -> None:
    request_body = {
        "taskId": "rev_smoke_stream",
        "codeText": "public class Demo { void run(){} }",
        "language": "java",
        "sourceType": "snippet",
        "options": {"llm_enabled": False},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]
    events = _events_from_response(response)
    assert events[0]["eventType"] == "analysis_started"
    assert events[-1]["eventType"] == "review_completed"


def test_internal_review_run_without_llm_credentials_fails_explicitly() -> None:
    request_body = {
        "taskId": "rev_smoke_llm_missing",
        "codeText": "public class Demo { void run(){} }",
        "language": "java",
        "sourceType": "snippet",
        "options": {"llm_enabled": True, "llm_api_key": ""},
    }
    response = client.post("/internal/reviews/run", json=request_body)
    assert response.status_code == 200
    events = _events_from_response(response)
    result = events[-1]["payload"]["result"]
    assert result["summary"]["final_outcome"] == "failed_no_patch"
    assert result["attempts"][-1]["failure_reason"] == "llm_not_enabled_or_missing_credentials"
    assert result["patch"]["status"] == "absent"
