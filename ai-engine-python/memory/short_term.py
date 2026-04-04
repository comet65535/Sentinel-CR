from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parents[2] / "data" / "state" / "sentinel.db"


def build_short_term_snapshot(*, snapshot_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_type": snapshot_type,
        "payload": deepcopy(payload),
    }


def update_short_term_memory(
    state: dict[str, Any] | Any,
    *,
    snapshot_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = {}
    if isinstance(state, dict):
        existing = dict(state.get("short_term_memory", {}) or {})
    elif hasattr(state, "short_term_memory"):
        existing = dict(getattr(state, "short_term_memory") or {})

    mapping = {
        "analyzer_evidence": "latest_analyzer_evidence",
        "patch": "latest_patch",
        "verifier_failure": "latest_verifier_failure",
        "retry_context": "retry_context",
        "user_constraints": "user_constraints",
        "token_usage": "token_usage",
        "latest_code": "latest_code",
    }
    key = mapping.get(snapshot_type, snapshot_type)
    existing[key] = deepcopy(payload)

    conversation_id = _resolve_conversation_id(state)
    if conversation_id:
        persisted = _load_thread_state(conversation_id)
        latest_code_payload = existing.get("latest_code")
        latest_code = persisted.get("latest_code")
        if isinstance(latest_code_payload, dict):
            latest_code_candidate = str(latest_code_payload.get("code_text") or "").strip()
            if latest_code_candidate:
                latest_code = latest_code_candidate
        elif isinstance(state, dict):
            latest_code_candidate = str(state.get("code_text") or "").strip()
            if latest_code_candidate:
                latest_code = latest_code_candidate
        latest_patch = existing.get("latest_patch") if isinstance(existing.get("latest_patch"), dict) else persisted.get("latest_patch")
        latest_failure = (
            existing.get("latest_verifier_failure")
            if isinstance(existing.get("latest_verifier_failure"), dict)
            else persisted.get("latest_verifier_failure")
        )
        _upsert_thread_state(
            conversation_id=conversation_id,
            latest_code=latest_code,
            latest_patch=latest_patch,
            latest_verifier_failure=latest_failure,
            short_term_memory=existing,
            repo_profile_id=persisted.get("repo_profile_id"),
            repo_id=persisted.get("repo_id"),
        )

    return existing


def get_latest_verifier_failure(short_term_memory: dict[str, Any] | None) -> dict[str, Any] | None:
    if not short_term_memory:
        return None
    value = short_term_memory.get("latest_verifier_failure")
    if not isinstance(value, dict):
        return None

    merged = deepcopy(value)
    latest_patch = short_term_memory.get("latest_patch")
    if isinstance(latest_patch, dict):
        patch_hash = str(latest_patch.get("content_hash") or "").strip()
        patch_content = str(latest_patch.get("content") or "")
        if not patch_hash and patch_content:
            patch_hash = hashlib.sha256(patch_content.encode("utf-8", errors="ignore")).hexdigest()
        if patch_hash:
            merged.setdefault("previous_patch_hash", patch_hash)
        if patch_content:
            merged.setdefault("previous_patch_content", patch_content)
        patch_id = str(latest_patch.get("patch_id") or "").strip()
        if patch_id:
            merged.setdefault("previous_patch_id", patch_id)
    return merged


def load_conversation_short_term_memory(conversation_id: str) -> dict[str, Any]:
    state = _load_thread_state(conversation_id)
    memory = state.get("short_term_memory")
    return memory if isinstance(memory, dict) else {}


def _resolve_conversation_id(state: dict[str, Any] | Any) -> str | None:
    if isinstance(state, dict):
        value = state.get("conversation_id") or (state.get("metadata") or {}).get("conversation_id")
    else:
        value = getattr(state, "conversation_id", None)
        if not value:
            metadata = getattr(state, "metadata", None)
            if isinstance(metadata, dict):
                value = metadata.get("conversation_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_thread_state(conversation_id: str) -> dict[str, Any]:
    _ensure_schema()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            SELECT latest_code, latest_patch, latest_verifier_failure, short_term_memory, repo_profile_id, repo_id
            FROM thread_state
            WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return {}
        return {
            "latest_code": row[0],
            "latest_patch": _parse_json_dict(row[1]),
            "latest_verifier_failure": _parse_json_dict(row[2]),
            "short_term_memory": _parse_json_dict(row[3]),
            "repo_profile_id": row[4],
            "repo_id": row[5],
        }


def _upsert_thread_state(
    *,
    conversation_id: str,
    latest_code: str | None,
    latest_patch: dict[str, Any] | None,
    latest_verifier_failure: dict[str, Any] | None,
    short_term_memory: dict[str, Any] | None,
    repo_profile_id: str | None,
    repo_id: str | None,
) -> None:
    _ensure_schema()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO thread_state(
                conversation_id, latest_code, latest_patch, latest_verifier_failure, short_term_memory,
                repo_profile_id, repo_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(conversation_id) DO UPDATE SET
                latest_code = excluded.latest_code,
                latest_patch = excluded.latest_patch,
                latest_verifier_failure = excluded.latest_verifier_failure,
                short_term_memory = excluded.short_term_memory,
                repo_profile_id = excluded.repo_profile_id,
                repo_id = excluded.repo_id,
                updated_at = excluded.updated_at
            """,
            (
                conversation_id,
                latest_code,
                _to_json(latest_patch),
                _to_json(latest_verifier_failure),
                _to_json(short_term_memory),
                repo_profile_id,
                repo_id,
            ),
        )
        conn.commit()


def _ensure_schema() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS thread_state (
                conversation_id TEXT PRIMARY KEY,
                latest_code TEXT,
                latest_patch TEXT,
                latest_verifier_failure TEXT,
                short_term_memory TEXT,
                repo_profile_id TEXT,
                repo_id TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _to_json(value: dict[str, Any] | None) -> str:
    if not value:
        return "{}"
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return "{}"


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}
