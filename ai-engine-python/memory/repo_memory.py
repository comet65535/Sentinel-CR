from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_repo_profiles_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "repo_profiles"


def load_repo_profile(
    *,
    repo_profile_id: str | None = None,
    repo_id: str | None = None,
    profiles_dir: str | Path | None = None,
) -> dict[str, Any]:
    base_dir = Path(profiles_dir) if profiles_dir else default_repo_profiles_dir()
    if not base_dir.exists():
        return {}

    candidates: list[Path] = []
    if repo_profile_id:
        candidates.append(base_dir / f"{repo_profile_id}.json")
    if repo_id:
        candidates.append(base_dir / f"{repo_id}.json")
    if not candidates:
        candidates.extend(sorted(base_dir.glob("*.json")))

    for path in candidates:
        if not path.exists():
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(parsed, dict):
            return _normalize_profile(parsed)
    return {}


def resolve_repo_profile(
    metadata: dict[str, Any] | None,
    options: dict[str, Any] | None = None,
    *,
    profiles_dir: str | Path | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    options = options or {}
    profile_id = str(metadata.get("repo_profile_id") or options.get("repo_profile_id") or "").strip() or None
    repo_id = str(metadata.get("repo_id") or options.get("repo_id") or "").strip() or None
    return load_repo_profile(repo_profile_id=profile_id, repo_id=repo_id, profiles_dir=profiles_dir)


def summarize_repo_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        "repo_id": profile.get("repo_id"),
        "style_preferences": list(profile.get("style_preferences") or []),
        "common_issue_types": list(profile.get("common_issue_types") or []),
        "common_failed_stages": list(profile.get("common_failed_stages") or []),
        "preferred_build_command": profile.get("preferred_build_command"),
        "preferred_test_command": profile.get("preferred_test_command"),
        "rejected_patch_patterns": list(profile.get("rejected_patch_patterns") or []),
        "hotspots": list(profile.get("hotspots") or []),
    }


def _normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(profile)
    normalized.setdefault("repo_id", "")
    normalized.setdefault("style_preferences", [])
    normalized.setdefault("common_issue_types", [])
    normalized.setdefault("common_failed_stages", [])
    normalized.setdefault("preferred_build_command", None)
    normalized.setdefault("preferred_test_command", None)
    normalized.setdefault("rejected_patch_patterns", [])
    normalized.setdefault("hotspots", [])
    return normalized
