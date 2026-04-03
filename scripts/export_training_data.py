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
    from tools.export_training_data import export_training_data

    parser = argparse.ArgumentParser(description="Export SWIFT and VERL training jsonl files.")
    parser.add_argument("--cases", default="data/cases")
    parser.add_argument("--golden", default="benchmark/golden_cases")
    parser.add_argument("--splits", default="benchmark/splits")
    parser.add_argument("--swift-output", default="training/swift/data")
    parser.add_argument("--verl-output", default="training/verl/data")
    args = parser.parse_args()

    summary = export_training_data(
        cases_dir=args.cases,
        golden_dir=args.golden,
        splits_dir=args.splits,
        swift_output_dir=args.swift_output,
        verl_output_dir=args.verl_output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
