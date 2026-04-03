from __future__ import annotations

import time
import uuid
from typing import Any

import httpx


def build_mcp_base_url(metadata: dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    url = str(metadata.get("mcp_base_url") or "http://localhost:8080").strip()
    return url.rstrip("/")


class McpClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_resource(
        self,
        name: str,
        *,
        query: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = f"/internal/mcp/resources/{name}"
        return self._request("GET", endpoint, params=query)

    def post_resource(
        self,
        name: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = f"/internal/mcp/resources/{name}"
        return self._request("POST", endpoint, json=payload)

    def call_tool(
        self,
        name: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = f"/internal/mcp/tools/{name}"
        return self._request("POST", endpoint, json=payload)

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        request_id = f"mcp_{uuid.uuid4().hex[:10]}"
        url = f"{self.base_url}{endpoint}"
        started = time.time()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(method, url, params=params, json=json)
            latency_ms = int((time.time() - started) * 1000)
        except Exception as exc:
            envelope = {
                "ok": False,
                "kind": _infer_kind(endpoint),
                "name": _infer_name(endpoint),
                "request_id": request_id,
                "data": None,
                "meta": {"latency_ms": int((time.time() - started) * 1000), "cache_hit": False},
                "error": {"code": "request_error", "message": str(exc)},
            }
            return envelope, _trace_item(method, endpoint, request_id, False, envelope["meta"]["latency_ms"], None)

        try:
            parsed = response.json()
            if isinstance(parsed, dict) and {"ok", "kind", "name", "request_id", "data", "meta", "error"}.issubset(
                parsed.keys()
            ):
                envelope = parsed
            else:
                envelope = {
                    "ok": response.status_code < 400,
                    "kind": _infer_kind(endpoint),
                    "name": _infer_name(endpoint),
                    "request_id": request_id,
                    "data": parsed if response.status_code < 400 else None,
                    "meta": {"latency_ms": latency_ms, "cache_hit": False},
                    "error": None
                    if response.status_code < 400
                    else {"code": f"http_{response.status_code}", "message": str(parsed)},
                }
        except Exception:
            text = response.text if hasattr(response, "text") else ""
            envelope = {
                "ok": response.status_code < 400,
                "kind": _infer_kind(endpoint),
                "name": _infer_name(endpoint),
                "request_id": request_id,
                "data": {"raw": text[:1000]} if response.status_code < 400 else None,
                "meta": {"latency_ms": latency_ms, "cache_hit": False},
                "error": None
                if response.status_code < 400
                else {"code": f"http_{response.status_code}", "message": text[:500]},
            }

        if not envelope.get("request_id"):
            envelope["request_id"] = request_id
        envelope.setdefault("meta", {"latency_ms": latency_ms, "cache_hit": False})
        if "latency_ms" not in envelope["meta"]:
            envelope["meta"]["latency_ms"] = latency_ms
        envelope["meta"].setdefault("cache_hit", False)

        trace_item = _trace_item(
            method=method,
            endpoint=endpoint,
            request_id=str(envelope["request_id"]),
            ok=bool(envelope.get("ok", False)),
            latency_ms=int(envelope["meta"].get("latency_ms", latency_ms)),
            error=envelope.get("error"),
        )
        return envelope, trace_item


def _infer_kind(endpoint: str) -> str:
    if "/resources/" in endpoint:
        return "resource"
    return "tool"


def _infer_name(endpoint: str) -> str:
    return endpoint.rsplit("/", 1)[-1]


def _trace_item(
    method: str,
    endpoint: str,
    request_id: str,
    ok: bool,
    latency_ms: int,
    error: Any,
) -> dict[str, Any]:
    return {
        "tool_name": _infer_name(endpoint),
        "endpoint": endpoint,
        "http_method": method,
        "request_id": request_id,
        "status": "success" if ok else "error",
        "latency_ms": latency_ms,
        "error": error,
    }
