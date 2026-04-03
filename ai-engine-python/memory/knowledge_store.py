from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .case_store import search_repair_cases as search_repair_cases_from_store
from .repo_memory import load_repo_profile


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_chroma_dir() -> Path:
    return _repo_root() / "storage" / "chroma"


def default_chunks_dir() -> Path:
    return _repo_root() / "knowledge" / "chunks"


def search_standards(
    query: str,
    *,
    limit: int = 5,
    persist_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    client = _build_chroma_client(persist_dir=persist_dir)
    if client is not None:
        try:
            collection = client.get_or_create_collection("standards_knowledge")
            result = collection.query(query_texts=[query], n_results=max(1, int(limit)))
            return _normalize_chroma_query_result(result=result, source="chroma:standards_knowledge")
        except Exception:
            pass

    return _search_chunks_file(query=query, limit=limit, file_name="standards_knowledge.jsonl", source="chunk_index")


def search_repair_cases(
    query: str,
    *,
    limit: int = 5,
    bug_type: str | None = None,
    semantic_only: bool = False,
    persist_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    client = _build_chroma_client(persist_dir=persist_dir)
    if client is not None:
        try:
            collection = client.get_or_create_collection("repair_cases")
            where: dict[str, Any] | None = None
            if bug_type:
                where = {"bug_type": bug_type}
            result = collection.query(query_texts=[query], n_results=max(1, int(limit)), where=where)
            normalized = _normalize_chroma_query_result(result=result, source="chroma:repair_cases")
            if semantic_only:
                normalized = [
                    item
                    for item in normalized
                    if str((item.get("metadata") or {}).get("category") or "").lower() in {"semantic_compile_fix", "semantic_compile"}
                ]
            if normalized:
                return normalized[: max(1, int(limit))]
        except Exception:
            pass

    fallback = search_repair_cases_from_store(
        query=query,
        limit=limit,
        bug_type=bug_type,
        semantic_only=semantic_only,
    )
    normalized_fallback: list[dict[str, Any]] = []
    for item in fallback:
        normalized_fallback.append(
            {
                "id": item.get("case_id"),
                "score": item.get("score", item.get("success_rate", 0.0)),
                "source": "case_store",
                "metadata": {
                    "bug_type": item.get("bug_type"),
                    "pattern_name": item.get("pattern_name"),
                    "category": item.get("category"),
                    "verified_level": item.get("verified_level"),
                },
                "snippet": item.get("fixed_code_snippet") or item.get("after_code") or "",
                "text": item.get("explanation") or "",
            }
        )
    return normalized_fallback


def search_semantic_compile_repairs(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    return search_repair_cases(query=query, limit=limit, semantic_only=True)


def get_repo_profile(repo_name: str) -> dict[str, Any]:
    repo_token = repo_name.strip()
    if not repo_token:
        return {}
    profile = load_repo_profile(repo_profile_id=repo_token, repo_id=repo_token)
    if profile:
        return profile
    # Try common default profile as a final fallback.
    return load_repo_profile(repo_profile_id="sentinel-cr")


def _build_chroma_client(*, persist_dir: str | Path | None = None):
    try:
        import chromadb  # type: ignore
    except Exception:
        return None

    target_dir = Path(persist_dir) if persist_dir else default_chroma_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        return chromadb.PersistentClient(path=str(target_dir))
    except Exception:
        return None


def _normalize_chroma_query_result(*, result: dict[str, Any], source: str) -> list[dict[str, Any]]:
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    normalized: list[dict[str, Any]] = []
    for idx, item_id in enumerate(ids):
        metadata = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
        distance = float(distances[idx]) if idx < len(distances) and distances[idx] is not None else 1.0
        score = round(max(0.0, 1.0 - distance), 4)
        text = docs[idx] if idx < len(docs) else ""
        normalized.append(
            {
                "id": item_id,
                "score": score,
                "source": source,
                "metadata": metadata,
                "snippet": metadata.get("snippet") if isinstance(metadata, dict) else "",
                "text": text,
            }
        )
    return normalized


def _search_chunks_file(*, query: str, limit: int, file_name: str, source: str) -> list[dict[str, Any]]:
    target = default_chunks_dir() / file_name
    if not target.exists():
        return []

    query_tokens = _tokenize(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except Exception:
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        text_tokens = _tokenize(text)
        if not text_tokens:
            continue
        overlap = query_tokens.intersection(text_tokens)
        if not overlap:
            continue
        score = round(len(overlap) / max(len(text_tokens), 1), 4)
        scored.append(
            (
                score,
                {
                    "id": item.get("chunk_id"),
                    "score": score,
                    "source": source,
                    "metadata": item.get("metadata", {}),
                    "snippet": text[:240],
                    "text": text,
                },
            )
        )
    scored.sort(key=lambda x: (-x[0], str(x[1].get("id") or "")))
    return [item for _, item in scored[: max(1, int(limit))]]


def _tokenize(text: str) -> set[str]:
    normalized = (
        text.replace(".", " ")
        .replace(",", " ")
        .replace("(", " ")
        .replace(")", " ")
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .lower()
    )
    return {piece.strip() for piece in normalized.split() if piece.strip()}
