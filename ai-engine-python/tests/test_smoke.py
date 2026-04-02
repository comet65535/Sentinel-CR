from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "service": "ai-engine-python"}


def test_internal_review_run_returns_day1_ndjson_stream() -> None:
    request_body = {
        "taskId": "rev_test_001",
        "codeText": "public class Demo {}",
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }

    response = client.post("/internal/reviews/run", json=request_body)

    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]

    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]

    assert [event["eventType"] for event in events] == [
        "analysis_started",
        "analysis_completed",
        "review_completed",
    ]
    assert events[0]["payload"]["source"] == "python-engine"
    assert events[-1]["status"] == "COMPLETED"
