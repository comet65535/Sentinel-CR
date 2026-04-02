from __future__ import annotations

import json

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "service": "ai-engine-python"}


def test_internal_review_run_returns_day2_ndjson_stream() -> None:
    request_body = {
        "taskId": "rev_test_001",
        "codeText": "public class Demo { public String hi(String n){ return \"hi\" + n; } }",
        "language": "java",
        "sourceType": "snippet",
        "metadata": {},
    }

    response = client.post("/internal/reviews/run", json=request_body)

    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers["content-type"]

    lines = [line for line in response.text.splitlines() if line.strip()]
    events = [json.loads(line) for line in lines]
    event_types = [event["eventType"] for event in events]

    assert event_types[0] == "analysis_started"
    assert event_types[1:6] == [
        "ast_parsing_started",
        "ast_parsing_completed",
        "symbol_graph_started",
        "symbol_graph_completed",
        "semgrep_scan_started",
    ]
    assert event_types[-2:] == ["analyzer_completed", "review_completed"]
    assert event_types[6] in {"semgrep_scan_completed", "semgrep_scan_warning"}

    final_event = events[-1]
    assert final_event["status"] == "COMPLETED"
    assert "result" in final_event["payload"]
    assert "symbols" in final_event["payload"]["result"]
    assert "contextSummary" in final_event["payload"]["result"]
