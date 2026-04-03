from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_python_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    engine_path = repo_root / "ai-engine-python"
    if str(engine_path) not in sys.path:
        sys.path.insert(0, str(engine_path))


def main() -> int:
    _ensure_python_path()
    from tools.knowledge_ingest import run_knowledge_ingest

    parser = argparse.ArgumentParser(description="Ingest standards PDF and repair cases into Chroma.")
    parser.add_argument("--manifest", default="knowledge/manifests/ingest_manifest.json")
    parser.add_argument("--persist-dir", default="storage/chroma")
    parser.add_argument("--processed-dir", default="knowledge/processed")
    parser.add_argument("--chunks-dir", default="knowledge/chunks")
    parser.add_argument("--embedding-provider", default="local")
    parser.add_argument("--embedding-model", default="BAAI/bge-small-en-v1.5")
    args = parser.parse_args()

    report = run_knowledge_ingest(
        manifest_path=args.manifest,
        persist_dir=args.persist_dir,
        processed_dir=args.processed_dir,
        chunks_dir=args.chunks_dir,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
