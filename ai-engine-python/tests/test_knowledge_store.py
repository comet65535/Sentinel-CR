from __future__ import annotations

import json
from pathlib import Path

from memory import knowledge_store


def test_search_standards_uses_chunk_fallback(monkeypatch, tmp_path: Path) -> None:
    chunk_dir = tmp_path / "chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    (chunk_dir / "standards_knowledge.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "std-1",
                "text": "Use parameterized query to avoid SQL injection in Java DAO.",
                "metadata": {"source_id": "manual", "page_no": 12},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(knowledge_store, "_build_chroma_client", lambda persist_dir=None: None)
    monkeypatch.setattr(knowledge_store, "default_chunks_dir", lambda: chunk_dir)

    hits = knowledge_store.search_standards("parameterized sql query", limit=3)
    assert hits
    assert hits[0]["id"] == "std-1"
    assert hits[0]["source"] == "chunk_index"
    assert isinstance(hits[0]["metadata"], dict)


def test_search_repair_cases_returns_structured_fallback(monkeypatch) -> None:
    monkeypatch.setattr(knowledge_store, "_build_chroma_client", lambda persist_dir=None: None)
    monkeypatch.setattr(
        knowledge_store,
        "search_repair_cases_from_store",
        lambda **kwargs: [
            {
                "case_id": "case-a",
                "score": 0.9,
                "bug_type": "missing_return_string",
                "pattern_name": "missing_return_string",
                "category": "semantic_compile_fix",
                "verified_level": "L1",
                "fixed_code_snippet": "return \"x\";",
                "explanation": "add return",
            }
        ],
    )

    hits = knowledge_store.search_repair_cases("missing return", limit=1, semantic_only=True)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["id"] == "case-a"
    assert hit["source"] == "case_store"
    assert hit["metadata"]["bug_type"] == "missing_return_string"
