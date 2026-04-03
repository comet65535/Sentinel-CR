from __future__ import annotations

import json
from pathlib import Path

from memory.repo_memory import resolve_repo_profile, summarize_repo_profile


def test_repo_memory_resolve_and_summarize(tmp_path: Path) -> None:
    profiles_dir = tmp_path / "repo_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    profile_path = profiles_dir / "sample.json"
    profile_path.write_text(
        json.dumps(
            {
                "repo_id": "sample",
                "style_preferences": ["small_patch"],
                "common_issue_types": ["null_pointer"],
                "common_failed_stages": ["compile"],
                "preferred_build_command": "mvn -q -DskipTests compile",
                "preferred_test_command": "mvn -q test",
                "rejected_patch_patterns": ["broad_refactor"],
                "hotspots": ["snippet.java"],
            }
        ),
        encoding="utf-8",
    )

    profile = resolve_repo_profile({"repo_profile_id": "sample"}, {}, profiles_dir=profiles_dir)
    assert profile["repo_id"] == "sample"
    summary = summarize_repo_profile(profile)
    assert summary["preferred_build_command"] == "mvn -q -DskipTests compile"
