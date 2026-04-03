from __future__ import annotations

import json
from pathlib import Path

from tools import knowledge_ingest


def test_run_knowledge_ingest_writes_processed_and_chunks(monkeypatch, tmp_path: Path) -> None:
    manifest = {
        "sources": [
            {
                "source_id": "alibaba_manual",
                "title": "Alibaba Java Manual",
                "path": "knowledge/raw/standards/alibaba-java-manual/阿里巴巴java开发手册.pdf",
                "kind": "pdf",
                "language": "zh-CN",
                "domain": "java_standards",
                "chunk_strategy": "page_window",
                "enabled": True,
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        knowledge_ingest,
        "_ingest_pdf_source",
        lambda source, source_path, processed_root, warnings: {
            "source_id": source["source_id"],
            "path": str(source_path),
            "pages": [
                {"page_no": 1, "text": "Use final keyword for constants.", "extracted": True, "needs_ocr": False},
                {"page_no": 2, "text": "", "extracted": False, "needs_ocr": True},
            ],
            "failed_pages": [2],
            "extracted_pages": 1,
            "total_pages": 2,
        },
    )
    monkeypatch.setattr(knowledge_ingest, "load_cases", lambda: [])
    monkeypatch.setattr(
        knowledge_ingest,
        "_persist_to_chroma",
        lambda **kwargs: {"mode": "json_fallback", "collections": ["standards_knowledge", "repair_cases"]},
    )

    report = knowledge_ingest.run_knowledge_ingest(
        manifest_path=manifest_path,
        persist_dir=tmp_path / "storage",
        processed_dir=tmp_path / "processed",
        chunks_dir=tmp_path / "chunks",
    )

    assert report.standards_chunks >= 1
    assert report.chroma_collections == ["standards_knowledge", "repair_cases"]
    assert (tmp_path / "chunks" / "standards_knowledge.jsonl").exists()
