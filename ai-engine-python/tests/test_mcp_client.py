from __future__ import annotations

from core.mcp_client import McpClient


def test_mcp_client_returns_structured_error_on_unreachable_endpoint() -> None:
    client = McpClient(base_url="http://127.0.0.1:1", timeout_seconds=0.1)
    envelope, trace = client.get_resource("schema", query={"taskId": "rev_x", "schemaType": "api_contract"})
    assert envelope["ok"] is False
    assert envelope["kind"] == "resource"
    assert envelope["error"] is not None
    assert trace["status"] == "error"
