from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_repo_profiles_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "repo_profiles"


def legacy_repo_profiles_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "repo_profiles"


def _candidate_profile_dirs(profiles_dir: str | Path | None = None) -> list[Path]:
    if profiles_dir:
        return [Path(profiles_dir)]
    candidates = [default_repo_profiles_dir(), legacy_repo_profiles_dir()]
    unique: list[Path] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique


def load_repo_profile(
    *,
    repo_profile_id: str | None = None,
    repo_id: str | None = None,
    profiles_dir: str | Path | None = None,
) -> dict[str, Any]:
    profile = {}
    for base_dir in _candidate_profile_dirs(profiles_dir):
        if not base_dir.exists():
            continue

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
                profile = _merge_profile(profile, parsed)
                if repo_profile_id or repo_id:
                    return _normalize_profile(profile)

    # Optional repository-local rules.
    local_rules = _load_local_agent_rules()
    profile = _merge_profile(profile, local_rules)
    return _normalize_profile(profile) if profile else {}


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
        "repo_rules": dict(profile.get("repo_rules") or {}),
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
    normalized.setdefault("repo_rules", {})
    return normalized


def _merge_profile(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, list):
            merged[key] = _unique_list(list(merged.get(key) or []) + list(value))
        elif isinstance(value, dict):
            current = dict(merged.get(key) or {})
            current.update(value)
            merged[key] = current
        else:
            merged[key] = value
    return merged


def _unique_list(items: list[Any]) -> list[Any]:
    seen = set()
    unique: list[Any] = []
    for item in items:
        token = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
        if token in seen:
            continue
        seen.add(token)
        unique.append(item)
    return unique


def _load_local_agent_rules() -> dict[str, Any]:
    # Optional workspace rules at <repo>/.agent_config.yaml
    path = Path(__file__).resolve().parents[2] / ".agent_config.yaml"
    if not path.exists():
        return {}

    rules: dict[str, Any] = {"repo_rules": {}}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            rules["repo_rules"][key] = value
    except Exception:
        return {}
    return rules
