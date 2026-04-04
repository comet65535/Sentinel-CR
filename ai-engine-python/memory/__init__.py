"""Memory package for Sentinel-CR."""

from .case_memory import promote_patch_from_verification, retrieve_case_matches, resolve_default_target_file
from .case_store import (
    append_case,
    load_case_examples,
    load_cases,
    promote_verified_patch_to_case,
    search_cases,
    search_repair_cases,
)
from .knowledge_store import get_repo_profile, search_semantic_compile_repairs, search_standards
from .repo_memory import load_repo_profile, resolve_repo_profile, summarize_repo_profile
from .short_term import (
    build_short_term_snapshot,
    get_latest_verifier_failure,
    load_conversation_short_term_memory,
    update_short_term_memory,
)

__all__ = [
    "append_case",
    "build_short_term_snapshot",
    "get_repo_profile",
    "get_latest_verifier_failure",
    "load_conversation_short_term_memory",
    "load_case_examples",
    "load_cases",
    "load_repo_profile",
    "promote_patch_from_verification",
    "promote_verified_patch_to_case",
    "resolve_default_target_file",
    "resolve_repo_profile",
    "retrieve_case_matches",
    "search_cases",
    "search_repair_cases",
    "search_semantic_compile_repairs",
    "search_standards",
    "summarize_repo_profile",
    "update_short_term_memory",
]
