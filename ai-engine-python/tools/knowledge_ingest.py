from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory.case_store import load_cases


@dataclass
class IngestReport:
    processed_sources: list[dict[str, Any]]
    standards_chunks: int
    repair_case_chunks: int
    chroma_mode: str
    chroma_collections: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed_sources": self.processed_sources,
            "standards_chunks": self.standards_chunks,
            "repair_case_chunks": self.repair_case_chunks,
            "chroma_mode": self.chroma_mode,
            "chroma_collections": self.chroma_collections,
            "warnings": self.warnings,
        }


def run_knowledge_ingest(
    *,
    manifest_path: str | Path,
    persist_dir: str | Path,
    processed_dir: str | Path,
    chunks_dir: str | Path,
    embedding_provider: str = "local",
    embedding_model: str = "BAAI/bge-small-en-v1.5",
) -> IngestReport:
    manifest = _load_manifest(manifest_path)
    processed_root = Path(processed_dir)
    chunks_root = Path(chunks_dir)
    chroma_root = Path(persist_dir)
    processed_root.mkdir(parents=True, exist_ok=True)
    chunks_root.mkdir(parents=True, exist_ok=True)
    chroma_root.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    standards_chunks: list[dict[str, Any]] = []
    processed_sources: list[dict[str, Any]] = []

    for source in manifest:
        if not bool(source.get("enabled", True)):
            continue
        kind = str(source.get("kind") or "").lower()
        source_path = Path(str(source.get("path") or ""))
        if not source_path.is_absolute():
            source_path = (Path.cwd() / source_path).resolve()

        if kind == "pdf":
            processed = _ingest_pdf_source(source=source, source_path=source_path, processed_root=processed_root, warnings=warnings)
            processed_sources.append(processed)
            standards_chunks.extend(_build_chunks_from_processed(processed, source=source))
        else:
            warnings.append(f"unsupported source kind: {kind}")

    standards_chunk_file = chunks_root / "standards_knowledge.jsonl"
    _write_jsonl(standards_chunk_file, standards_chunks)

    repair_cases = load_cases()
    repair_chunks = _build_repair_case_chunks(repair_cases)
    repair_chunk_file = chunks_root / "repair_cases.jsonl"
    _write_jsonl(repair_chunk_file, repair_chunks)

    chroma_result = _persist_to_chroma(
        persist_dir=chroma_root,
        standards_chunks=standards_chunks,
        repair_chunks=repair_chunks,
        provider_name=embedding_provider,
        model_name=embedding_model,
        warnings=warnings,
    )

    return IngestReport(
        processed_sources=processed_sources,
        standards_chunks=len(standards_chunks),
        repair_case_chunks=len(repair_chunks),
        chroma_mode=chroma_result["mode"],
        chroma_collections=chroma_result["collections"],
        warnings=warnings,
    )


def _load_manifest(manifest_path: str | Path) -> list[dict[str, Any]]:
    raw = json.loads(Path(manifest_path).read_text(encoding="utf-8").lstrip("\ufeff"))
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("sources"), list):
        return [item for item in raw["sources"] if isinstance(item, dict)]
    return []


def _ingest_pdf_source(
    *,
    source: dict[str, Any],
    source_path: Path,
    processed_root: Path,
    warnings: list[str],
) -> dict[str, Any]:
    source_id = str(source.get("source_id") or _stable_id(str(source_path)))
    pages: list[dict[str, Any]] = []
    total_pages = 0

    if not source_path.exists():
        warnings.append(f"source file missing: {source_path}")
    else:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(source_path))
            total_pages = len(reader.pages)
            for idx, page in enumerate(reader.pages, start=1):
                try:
                    text = (page.extract_text() or "").strip()
                    if text:
                        pages.append({"page_no": idx, "text": text, "extracted": True, "needs_ocr": False})
                    else:
                        pages.append({"page_no": idx, "text": "", "extracted": False, "needs_ocr": True})
                except Exception as exc:
                    pages.append(
                        {
                            "page_no": idx,
                            "text": "",
                            "extracted": False,
                            "needs_ocr": True,
                            "error": str(exc),
                        }
                    )
        except Exception as exc:
            warnings.append(f"pypdf extraction failed for {source_path.name}: {exc}")
            pages.append(
                {
                    "page_no": None,
                    "text": "",
                    "extracted": False,
                    "needs_ocr": True,
                    "error": f"pdf_extract_unavailable: {exc}",
                }
            )

    processed = {
        "source_id": source_id,
        "title": source.get("title"),
        "path": str(source_path),
        "kind": source.get("kind"),
        "language": source.get("language"),
        "domain": source.get("domain"),
        "chunk_strategy": source.get("chunk_strategy", "page_window"),
        "total_pages": total_pages,
        "extracted_pages": len([item for item in pages if item.get("extracted")]),
        "failed_pages": [item.get("page_no") for item in pages if not item.get("extracted")],
        "pages": pages,
    }
    (processed_root / f"{source_id}.json").write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")
    return processed


def _build_chunks_from_processed(processed: dict[str, Any], *, source: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = str(processed.get("source_id") or "source")
    chunks: list[dict[str, Any]] = []
    for page in processed.get("pages", []):
        text = str(page.get("text") or "").strip()
        page_no = int(page.get("page_no") or 0)
        if not text:
            continue
        for idx, chunk_text in enumerate(_chunk_text(text, chunk_size=900, overlap=120), start=1):
            chunk_id = f"{source_id}-p{page_no:04d}-c{idx:02d}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "source_id": source_id,
                        "title": source.get("title"),
                        "path": processed.get("path"),
                        "kind": source.get("kind"),
                        "language": source.get("language"),
                        "domain": source.get("domain"),
                        "page_no": page_no,
                    },
                }
            )
    if chunks:
        return chunks

    failed_pages = processed.get("failed_pages", [])
    diag_text = (
        f"Extraction diagnostic for {source.get('title')}: extracted_pages={processed.get('extracted_pages', 0)}, "
        f"failed_pages={failed_pages}, needs_ocr={True}."
    )
    chunks.append(
        {
            "chunk_id": f"{source_id}-diagnostic-0001",
            "text": diag_text,
            "metadata": {
                "source_id": source_id,
                "title": source.get("title"),
                "path": processed.get("path"),
                "kind": source.get("kind"),
                "language": source.get("language"),
                "domain": source.get("domain"),
                "diagnostic": True,
            },
        }
    )
    return chunks


def _build_repair_case_chunks(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id") or "case-unknown")
        text = "\n".join(
            [
                f"bug_type: {case.get('bug_type')}",
                f"pattern_name: {case.get('pattern_name') or case.get('pattern')}",
                f"trigger_signals: {', '.join(case.get('trigger_signals', []))}",
                f"explanation: {case.get('explanation')}",
                f"patch_diff:\n{case.get('patch_diff') or case.get('diff')}",
            ]
        ).strip()
        chunks.append(
            {
                "chunk_id": f"repair-{case_id}",
                "text": text,
                "metadata": {
                    "case_id": case_id,
                    "bug_type": case.get("bug_type"),
                    "pattern_name": case.get("pattern_name") or case.get("pattern"),
                    "category": case.get("category"),
                    "verified_level": case.get("verified_level"),
                    "snippet": (case.get("fixed_code_snippet") or case.get("after_code") or "")[:240],
                },
            }
        )
    return chunks


def _persist_to_chroma(
    *,
    persist_dir: Path,
    standards_chunks: list[dict[str, Any]],
    repair_chunks: list[dict[str, Any]],
    provider_name: str,
    model_name: str,
    warnings: list[str],
) -> dict[str, Any]:
    collections = ["standards_knowledge", "repair_cases"]
    try:
        import chromadb  # type: ignore
    except Exception:
        warnings.append("chromadb unavailable, using json fallback index")
        _write_chroma_fallback(
            persist_dir=persist_dir,
            standards_chunks=standards_chunks,
            repair_chunks=repair_chunks,
            mode="json_fallback",
            provider_name=provider_name,
            model_name=model_name,
        )
        return {"mode": "json_fallback", "collections": collections}

    embedding = _build_embedding_function(provider_name=provider_name, model_name=model_name, warnings=warnings)
    client = chromadb.PersistentClient(path=str(persist_dir))

    standards = client.get_or_create_collection(name="standards_knowledge", embedding_function=embedding)
    _upsert_chunks(standards, standards_chunks)

    repair = client.get_or_create_collection(name="repair_cases", embedding_function=embedding)
    _upsert_chunks(repair, repair_chunks)

    return {"mode": "chroma", "collections": collections}


def _build_embedding_function(*, provider_name: str, model_name: str, warnings: list[str]):
    try:
        from chromadb.api.types import EmbeddingFunction  # type: ignore
    except Exception:
        return None

    class _FallbackEmbedding:
        def __call__(self, input: list[str]) -> list[list[float]]:
            return [_hash_embed(item) for item in input]

    if provider_name != "local":
        warnings.append(f"unsupported embedding provider: {provider_name}, fallback hash embedding enabled")
        return _FallbackEmbedding()

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer(model_name)

        class _SentenceTransformerEmbedding(EmbeddingFunction):
            def __call__(self, input: list[str]) -> list[list[float]]:
                vectors = model.encode(input, normalize_embeddings=True)
                return [vector.tolist() for vector in vectors]

        return _SentenceTransformerEmbedding()
    except Exception as exc:
        warnings.append(f"sentence-transformers unavailable ({exc}); fallback hash embedding enabled")
        return _FallbackEmbedding()


def _upsert_chunks(collection, chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        return
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    for item in chunks:
        ids.append(str(item.get("chunk_id")))
        documents.append(str(item.get("text") or ""))
        metadata = dict(item.get("metadata") or {})
        metadata["chunk_id"] = ids[-1]
        metadatas.append(metadata)
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


def _write_chroma_fallback(
    *,
    persist_dir: Path,
    standards_chunks: list[dict[str, Any]],
    repair_chunks: list[dict[str, Any]],
    mode: str,
    provider_name: str,
    model_name: str,
) -> None:
    fallback_dir = persist_dir / "fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(fallback_dir / "standards_knowledge.jsonl", standards_chunks)
    _write_jsonl(fallback_dir / "repair_cases.jsonl", repair_chunks)
    manifest = {
        "mode": mode,
        "collections": ["standards_knowledge", "repair_cases"],
        "embedding_provider": provider_name,
        "embedding_model": model_name,
    }
    (persist_dir / "collections_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for item in rows:
            fp.write(json.dumps(item, ensure_ascii=False) + "\n")


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if not compact:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(compact):
        end = min(start + chunk_size, len(compact))
        chunks.append(compact[start:end])
        if end >= len(compact):
            break
        start = max(end - overlap, 0)
    return chunks


def _stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _hash_embed(text: str, *, dim: int = 64) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    values: list[float] = []
    for idx in range(dim):
        byte = digest[idx % len(digest)]
        values.append((byte / 255.0) * 2.0 - 1.0)
    return values
