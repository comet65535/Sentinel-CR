from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _ensure_python_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    engine_path = repo_root / "ai-engine-python"
    if str(engine_path) not in sys.path:
        sys.path.insert(0, str(engine_path))


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _build_project_doc_chunks(repo_root: Path) -> list[dict[str, Any]]:
    candidates = [
        repo_root / "README.md",
        repo_root / "PLAN.md",
        repo_root / "docs" / "architecture.md",
        repo_root / "docs" / "api-contract.md",
        repo_root / "docs" / "event-schema.md",
    ]
    chunks: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue
        chunk_id = "project-doc-" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "metadata": {
                    "source_id": "project_docs",
                    "title": path.name,
                    "path": str(path.relative_to(repo_root)).replace("\\", "/"),
                    "kind": "markdown",
                    "domain": "project_design",
                },
            }
        )
    return chunks


def _dedupe_chunks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        chunk_id = str(row.get("chunk_id") or "").strip()
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(row)
    return deduped


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _normalize_failed_pages(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    pages: list[int] = []
    for item in value:
        if isinstance(item, int):
            pages.append(item)
    return pages


def main() -> int:
    _ensure_python_path()
    from tools import knowledge_ingest

    parser = argparse.ArgumentParser(description="Ingest handbook/docs/cases into long-term knowledge store.")
    parser.add_argument("--manifest", default="knowledge/manifests/ingest_manifest.json")
    parser.add_argument("--persist-dir", default="storage/chroma")
    parser.add_argument("--processed-dir", default="knowledge/processed")
    parser.add_argument("--chunks-dir", default="knowledge/chunks")
    parser.add_argument("--embedding-provider", default="local")
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--report", default="knowledge/reports/ingest_handbook_report.json")
    args = parser.parse_args()

    ingest_time = datetime.now(timezone.utc).isoformat()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        ingest_report = knowledge_ingest.run_knowledge_ingest(
            manifest_path=args.manifest,
            persist_dir=args.persist_dir,
            processed_dir=args.processed_dir,
            chunks_dir=args.chunks_dir,
            embedding_provider=args.embedding_provider,
            embedding_model=args.embedding_model,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        error_report = {
            "ok": False,
            "error": {"code": "ingest_failed", "message": str(exc)},
            "ingest_time": ingest_time,
            "sources": [],
            "collections": [],
        }
        text = json.dumps(error_report, ensure_ascii=False, indent=2)
        report_path.write_text(text, encoding="utf-8")
        print(text)
        return 0

    repo_root = Path(__file__).resolve().parents[1]
    standards_path = Path(args.chunks_dir) / "standards_knowledge.jsonl"
    standards_rows = _load_jsonl_rows(standards_path)
    standards_rows.extend(_build_project_doc_chunks(repo_root))
    standards_rows = _dedupe_chunks(standards_rows)
    _write_jsonl(standards_path, standards_rows)
    repair_rows = _load_jsonl_rows(Path(args.chunks_dir) / "repair_cases.jsonl")

    knowledge_ingest._persist_to_chroma(
        persist_dir=Path(args.persist_dir),
        standards_chunks=standards_rows,
        repair_chunks=repair_rows,
        provider_name=args.embedding_provider,
        model_name=args.embedding_model,
        warnings=[],
    )

    source_chunk_counter: dict[str, int] = {}
    for row in standards_rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source_id = str(metadata.get("source_id") or "unknown")
        source_chunk_counter[source_id] = source_chunk_counter.get(source_id, 0) + 1

    sources: list[dict[str, Any]] = []
    for source in ingest_report.processed_sources:
        source_id = str(source.get("source_id") or "unknown")
        failed_pages = _normalize_failed_pages(source.get("failed_pages"))
        sources.append(
            {
                "source_id": source_id,
                "collection": "standards_knowledge",
                "chunk_count": int(source_chunk_counter.get(source_id, 0)),
                "extracted_pages": int(source.get("extracted_pages") or 0),
                "failed_pages": failed_pages,
                "ingest_time": ingest_time,
            }
        )
    sources.append(
        {
            "source_id": "project_docs",
            "collection": "standards_knowledge",
            "chunk_count": int(source_chunk_counter.get("project_docs", 0)),
            "extracted_pages": int(source_chunk_counter.get("project_docs", 0)),
            "failed_pages": [],
            "ingest_time": ingest_time,
        }
    )

    standards_extracted_pages = sum(int(row.get("extracted_pages") or 0) for row in sources)
    standards_failed_pages: list[int] = []
    for row in sources:
        for page in _normalize_failed_pages(row.get("failed_pages")):
            if page not in standards_failed_pages:
                standards_failed_pages.append(page)

    collections = [
        {
            "collection": "standards_knowledge",
            "chunk_count": len(standards_rows),
            "extracted_pages": standards_extracted_pages,
            "failed_pages": standards_failed_pages,
            "ingest_time": ingest_time,
        },
        {
            "collection": "repair_cases",
            "chunk_count": len(repair_rows),
            "extracted_pages": 0,
            "failed_pages": [],
            "ingest_time": ingest_time,
        },
    ]

    report = {
        "ok": True,
        "error": None,
        "ingest_time": ingest_time,
        "warnings": ingest_report.warnings,
        "sources": sources,
        "collections": collections,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
