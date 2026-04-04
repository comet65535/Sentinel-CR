from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx


@dataclass
class LlmCallResult:
    ok: bool
    content: str
    error: str | None
    raw: dict[str, Any] | None
    trace: dict[str, Any]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_ms: int = 60000,
        default_json_mode: bool = True,
        default_tool_mode: str = "off",
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_ms = timeout_ms
        self.default_json_mode = default_json_mode
        self.default_tool_mode = default_tool_mode

    def create_chat_completion(
        self,
        *,
        phase: str,
        prompt_name: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        json_mode: bool | None = None,
        tool_mode: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> LlmCallResult:
        request_json_mode = self.default_json_mode if json_mode is None else json_mode
        request_tool_mode = self.default_tool_mode if tool_mode is None else tool_mode
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if request_json_mode:
            payload["response_format"] = {"type": "json_object"}
        if request_tool_mode and request_tool_mode != "off":
            payload["tool_choice"] = request_tool_mode
            if tools:
                payload["tools"] = tools
        if extra_payload:
            payload.update(extra_payload)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        start = time.perf_counter()
        raw_response: dict[str, Any] | None = None
        error: str | None = None
        content = ""
        usage: dict[str, Any] = {}
        tool_calls: list[dict[str, Any]] = []
        try:
            with httpx.Client(timeout=self.timeout_ms / 1000.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                if stream:
                    content = _parse_stream_content(response.text)
                    raw_response = {"stream": True, "raw_text": response.text}
                else:
                    raw_response = response.json()
                    content = _extract_message_content(raw_response)
                    usage = dict(raw_response.get("usage") or {})
                    tool_calls = _extract_tool_calls(raw_response)
        except Exception as exc:
            error = str(exc)

        latency_ms = int((time.perf_counter() - start) * 1000)
        token_in = _safe_int(usage.get("prompt_tokens"))
        token_out = _safe_int(usage.get("completion_tokens"))
        cache_hit_tokens = _safe_int(
            usage.get("prompt_cache_hit_tokens")
            or usage.get("cache_hit_tokens")
            or usage.get("cached_tokens")
        )
        cache_miss_tokens = _safe_int(
            usage.get("prompt_cache_miss_tokens")
            or usage.get("cache_miss_tokens")
            or max(token_in - cache_hit_tokens, 0)
        )
        trace = {
            "phase": phase,
            "prompt_name": prompt_name,
            "provider": self.provider,
            "model": self.model,
            "token_in": token_in,
            "token_out": token_out,
            "latency_ms": latency_ms,
            "json_mode": bool(request_json_mode),
            "tool_mode": request_tool_mode,
            "tool_call_count": len(tool_calls),
            "cache_hit_tokens": cache_hit_tokens,
            "cache_miss_tokens": cache_miss_tokens,
        }

        return LlmCallResult(
            ok=error is None and (bool(content.strip()) or bool(tool_calls)),
            content=content,
            error=error,
            raw=raw_response,
            trace=trace,
            tool_calls=tool_calls,
        )


def build_llm_client(options: dict[str, Any] | None = None) -> OpenAICompatibleClient | None:
    options = options or {}
    env = _load_runtime_env()
    llm_enabled = options.get("llm_enabled")
    if llm_enabled is None:
        has_env_key = any(
            str(env.get(key) or "").strip()
            for key in ("SENTINEL_LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY")
        )
        has_option_key = bool(str(options.get("llm_api_key") or "").strip())
        llm_enabled = has_env_key or has_option_key
    if not _to_bool(llm_enabled, default=False):
        return None

    provider = str(
        options.get("llm_provider")
        or env.get("SENTINEL_LLM_PROVIDER")
        or env.get("LLM_PROVIDER")
        or "deepseek"
    ).strip().lower()
    model = str(
        options.get("llm_model")
        or env.get("SENTINEL_LLM_MODEL")
        or env.get("LLM_MODEL")
        or "deepseek-chat"
    ).strip()
    timeout_ms = _safe_int(options.get("llm_timeout_ms"), default=60000)
    json_mode = _to_bool(options.get("llm_json_mode"), default=True)
    tool_mode = str(options.get("llm_tool_mode") or "off").strip().lower() or "off"

    if provider == "deepseek":
        base_url = str(
            options.get("llm_base_url")
            or env.get("SENTINEL_LLM_BASE_URL")
            or env.get("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com/v1"
        ).strip()
        if "llm_api_key" in options and options.get("llm_api_key") is not None:
            api_key = str(options.get("llm_api_key")).strip()
        else:
            api_key = str(
                env.get("SENTINEL_LLM_API_KEY")
                or env.get("DEEPSEEK_API_KEY")
                or ""
            ).strip()
    else:
        base_url = str(
            options.get("llm_base_url")
            or env.get("SENTINEL_LLM_BASE_URL")
            or env.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).strip()
        if "llm_api_key" in options and options.get("llm_api_key") is not None:
            api_key = str(options.get("llm_api_key")).strip()
        else:
            api_key = str(
                env.get("SENTINEL_LLM_API_KEY")
                or env.get("OPENAI_API_KEY")
                or ""
            ).strip()

    if not api_key:
        return None
    return OpenAICompatibleClient(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_ms=timeout_ms,
        default_json_mode=json_mode,
        default_tool_mode=tool_mode,
    )


def _extract_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = str(item.get("text") or "")
                if text:
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def _parse_stream_content(raw_text: str) -> str:
    content_parts: list[str] = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        body = line[len("data:") :].strip()
        if body == "[DONE]":
            break
        try:
            payload = json.loads(body)
        except Exception:
            continue
        choices = payload.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        text = delta.get("content")
        if isinstance(text, str):
            content_parts.append(text)
    return "".join(content_parts)


def _extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    choices = payload.get("choices") or []
    if not choices:
        return []
    message = choices[0].get("message") or {}
    raw_calls = message.get("tool_calls") or []
    calls: list[dict[str, Any]] = []
    for item in raw_calls:
        if isinstance(item, dict):
            calls.append(item)
    return calls


def _load_runtime_env() -> dict[str, str]:
    env = dict(os.environ)
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return env
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            env.setdefault(key, value)
    except Exception:
        return env
    return env


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _to_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default
