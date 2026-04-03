from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_python(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def test_benchmark_offline_and_live_not_configured_share_schema(tmp_path: Path) -> None:
    repo = _repo_root()
    offline_output = tmp_path / "offline.json"
    live_output = tmp_path / "live.json"

    offline = _run_python(
        [
            "benchmark/run_eval.py",
            "--split",
            "val",
            "--output",
            str(offline_output),
        ],
        cwd=repo,
    )
    assert offline.returncode == 0, offline.stderr
    offline_payload = json.loads(offline_output.read_text(encoding="utf-8"))

    live = _run_python(
        [
            "benchmark/run_eval.py",
            "--split",
            "val",
            "--live",
            "--output",
            str(live_output),
        ],
        cwd=repo,
    )
    assert live.returncode == 0, live.stderr
    live_payload = json.loads(live_output.read_text(encoding="utf-8"))

    assert set(offline_payload.keys()) == set(live_payload.keys())
    assert live_payload["ok"] is False
    assert live_payload["error"]["code"] == "not_configured"


def test_tool_eval_smoke(tmp_path: Path) -> None:
    repo = _repo_root()
    input_path = tmp_path / "eval.json"
    output_path = tmp_path / "tool.json"
    input_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_a",
                        "expected_tools": ["analyzer", "fixer"],
                        "tool_trace": [{"tool_name": "analyzer"}, {"tool_name": "verifier"}],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = _run_python(
        [
            "benchmark/tool_eval.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert "tool_calling_recall" in payload["metrics"]
    assert "tool_calling_precision" in payload["metrics"]


def test_ingest_handbook_is_idempotent_and_reports_fields(tmp_path: Path) -> None:
    repo = _repo_root()
    manifest_path = tmp_path / "manifest.json"
    report_path = tmp_path / "report.json"
    persist_dir = tmp_path / "persist"
    processed_dir = tmp_path / "processed"
    chunks_dir = tmp_path / "chunks"
    manifest_path.write_text(json.dumps({"sources": []}, ensure_ascii=False), encoding="utf-8")

    args = [
        "scripts/ingest_handbook.py",
        "--manifest",
        str(manifest_path),
        "--persist-dir",
        str(persist_dir),
        "--processed-dir",
        str(processed_dir),
        "--chunks-dir",
        str(chunks_dir),
        "--embedding-provider",
        "unsupported_provider",
        "--report",
        str(report_path),
    ]
    first = _run_python(args, cwd=repo)
    assert first.returncode == 0, first.stderr
    first_payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert "ingest_time" in first_payload
    assert "collections" in first_payload

    second = _run_python(args, cwd=repo)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(report_path.read_text(encoding="utf-8"))
    first_counts = {row["collection"]: row["chunk_count"] for row in first_payload["collections"]}
    second_counts = {row["collection"]: row["chunk_count"] for row in second_payload["collections"]}
    assert first_counts == second_counts
    for row in second_payload["collections"]:
        assert "collection" in row
        assert "chunk_count" in row
        assert "extracted_pages" in row
        assert "failed_pages" in row
        assert "ingest_time" in row
    for row in second_payload["sources"]:
        assert "collection" in row
        assert "chunk_count" in row
        assert "extracted_pages" in row
        assert "failed_pages" in row
        assert "ingest_time" in row


def test_promote_verified_cases_not_configured_when_input_missing(tmp_path: Path) -> None:
    repo = _repo_root()
    report_path = tmp_path / "promote_report.json"
    result = _run_python(
        [
            "scripts/promote_verified_cases.py",
            "--input",
            str(tmp_path / "missing.jsonl"),
            "--report",
            str(report_path),
        ],
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "not_configured"


def test_training_shell_scripts_smoke_or_have_fallback_markers() -> None:
    repo = _repo_root()
    scripts = [
        repo / "training" / "swift" / "train_swift.sh",
        repo / "training" / "swift" / "eval_swift.sh",
        repo / "training" / "verl" / "run_verl.sh",
    ]

    bash = shutil.which("bash")
    if bash:
        for script in scripts:
            completed = subprocess.run(
                [bash, str(script)],
                cwd=str(repo),
                capture_output=True,
                text=True,
                check=False,
            )
            assert completed.returncode == 0, completed.stderr
    else:
        for script in scripts:
            text = script.read_text(encoding="utf-8")
            assert "smoke success" in text
