from __future__ import annotations

from typing import Any

from .case_store import promote_verified_patch_to_case, search_cases

DEFAULT_SNIPPET_FILE = "snippet.java"


CASE_LIBRARY: list[dict[str, Any]] = [
    {
        "case_id": "case-null-guard-001",
        "pattern": "null_pointer_guard",
        "trigger_signals": ["null_pointer", "null_guard", "optional", "nullable"],
        "before_code": "User u = repo.findById(id).get(); return u.getName();",
        "after_code": "return repo.findById(id).map(User::getName).orElse(null);",
        "diff": "\n".join(
            [
                "diff --git a/snippet.java b/snippet.java",
                "--- a/snippet.java",
                "+++ b/snippet.java",
                "@@ -1,3 +1,3 @@",
                "-User u = repo.findById(id).get();",
                "-return u.getName();",
                "+return repo.findById(id).map(User::getName).orElse(null);",
            ]
        ),
        "risk_note": "Behavior may change when id is absent; now returns null.",
        "success_rate": 0.89,
        "strategy": "null_guard",
    },
    {
        "case_id": "case-sql-parameterized-001",
        "pattern": "sql_parameterized_query",
        "trigger_signals": ["sql_injection", "parameterized_query", "statement", "query"],
        "before_code": 'String sql = "select * from users where id=" + userInput;',
        "after_code": "PreparedStatement ps = conn.prepareStatement(\"select * from users where id=?\");",
        "diff": "\n".join(
            [
                "diff --git a/snippet.java b/snippet.java",
                "--- a/snippet.java",
                "+++ b/snippet.java",
                "@@ -1,2 +1,4 @@",
                '-String sql = "select * from users where id=" + userInput;',
                "-ResultSet rs = stmt.executeQuery(sql);",
                '+PreparedStatement ps = conn.prepareStatement("select * from users where id=?");',
                "+ps.setString(1, userInput);",
                "+ResultSet rs = ps.executeQuery();",
            ]
        ),
        "risk_note": "Requires compatible JDBC connection object in scope.",
        "success_rate": 0.93,
        "strategy": "parameterized_query",
    },
    {
        "case_id": "case-try-with-resources-001",
        "pattern": "resource_management_try_with_resources",
        "trigger_signals": ["resource_leak", "try_with_resources", "close", "stream"],
        "before_code": "InputStream in = new FileInputStream(path); return in.read();",
        "after_code": "try (InputStream in = new FileInputStream(path)) { return in.read(); }",
        "diff": "\n".join(
            [
                "diff --git a/snippet.java b/snippet.java",
                "--- a/snippet.java",
                "+++ b/snippet.java",
                "@@ -1,2 +1,3 @@",
                "-InputStream in = new FileInputStream(path);",
                "-return in.read();",
                "+try (InputStream in = new FileInputStream(path)) {",
                "+    return in.read();",
                "+}",
            ]
        ),
        "risk_note": "Resource lifecycle changes; ensure caller does not reuse handle.",
        "success_rate": 0.9,
        "strategy": "try_with_resources",
    },
    {
        "case_id": "case-exception-logging-001",
        "pattern": "exception_logging_completion",
        "trigger_signals": ["bad_exception_handling", "exception_logging", "catch", "log"],
        "before_code": "catch (Exception e) { throw e; }",
        "after_code": "catch (Exception e) { logger.error(\"operation failed\", e); throw e; }",
        "diff": "\n".join(
            [
                "diff --git a/snippet.java b/snippet.java",
                "--- a/snippet.java",
                "+++ b/snippet.java",
                "@@ -1 +1,2 @@",
                "-catch (Exception e) { throw e; }",
                '+catch (Exception e) { logger.error("operation failed", e); throw e; }',
            ]
        ),
        "risk_note": "Logging may expose sensitive data if message is too broad.",
        "success_rate": 0.84,
        "strategy": "exception_logging",
    },
    {
        "case_id": "case-n-plus-one-001",
        "pattern": "n_plus_one_batch_query",
        "trigger_signals": ["n_plus_one", "batch_query", "loop", "repository"],
        "before_code": "for (id : ids) { list.add(repo.findById(id)); }",
        "after_code": "Map<Long, User> m = repo.findAllById(ids)...",
        "diff": "\n".join(
            [
                "diff --git a/snippet.java b/snippet.java",
                "--- a/snippet.java",
                "+++ b/snippet.java",
                "@@ -1,3 +1,4 @@",
                "-for (Long id : ids) {",
                "-    users.add(repo.findById(id).orElse(null));",
                "-}",
                "+Map<Long, User> usersById = repo.findAllById(ids).stream()",
                "+    .collect(Collectors.toMap(User::getId, u -> u));",
                "+for (Long id : ids) { users.add(usersById.get(id)); }",
            ]
        ),
        "risk_note": "Batch query can increase memory usage for large input sets.",
        "success_rate": 0.76,
        "strategy": "batch_query",
    },
]


def retrieve_case_matches(
    issues: list[dict[str, Any]],
    repair_plan: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    try:
        issue_tokens = _collect_issue_tokens(issues)
        plan_tokens = _collect_plan_tokens(repair_plan)
        symbol_tokens = _collect_symbol_tokens(symbols)
        context_tokens = _collect_context_tokens(context_summary)
        query_tokens = issue_tokens | plan_tokens | symbol_tokens | context_tokens

        if not query_tokens:
            return []

        persisted_matches = search_cases(query_tokens=query_tokens, top_k=top_k)
        if persisted_matches:
            return [_to_case_match(item) for item in persisted_matches]

        scored: list[tuple[float, dict[str, Any]]] = []
        for case in CASE_LIBRARY:
            match_tokens = set(case.get("trigger_signals", [])) | {str(case.get("pattern", "")), str(case.get("strategy", ""))}
            overlap = query_tokens.intersection({token.lower() for token in match_tokens if token})
            if not overlap:
                continue

            overlap_score = min(len(overlap) / max(len(match_tokens), 1), 1.0)
            score = round((overlap_score * 0.7) + (float(case.get("success_rate", 0.0)) * 0.3), 4)
            scored.append(
                (
                    score,
                    {
                        "case_id": case["case_id"],
                        "pattern": case["pattern"],
                        "score": score,
                        "trigger_signals": case["trigger_signals"],
                        "strategy": case["strategy"],
                        "risk_note": case["risk_note"],
                        "success_rate": case["success_rate"],
                        "before_code": case["before_code"],
                        "after_code": case["after_code"],
                        "diff": case["diff"],
                    },
                )
            )

        scored.sort(key=lambda item: (-item[0], item[1]["case_id"]))
        limit = max(1, int(top_k))
        return [item[1] for item in scored[:limit]]
    except Exception:
        return []


def promote_patch_from_verification(
    *,
    patch: dict[str, Any] | None,
    verification: dict[str, Any] | None,
    tool_trace: list[dict[str, Any]] | None,
    accepted_by_human: bool = False,
) -> dict[str, Any] | None:
    try:
        return promote_verified_patch_to_case(
            patch=patch,
            verification=verification,
            tool_trace=tool_trace,
            accepted_by_human=accepted_by_human,
        )
    except Exception:
        return None


def resolve_default_target_file(issues: list[dict[str, Any]]) -> str:
    for issue in issues:
        file_path = str(issue.get("file_path") or issue.get("filePath") or "").strip()
        if file_path and file_path not in {"snippet.java", "snippet"}:
            return file_path
    return DEFAULT_SNIPPET_FILE


def _collect_issue_tokens(issues: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for issue in issues:
        value = str(issue.get("type") or issue.get("issueType") or issue.get("issue_type") or "").lower()
        if value:
            tokens.add(value)
            tokens.update(value.replace(".", "_").replace("-", "_").split("_"))
        message = str(issue.get("message") or "").lower()
        tokens.update(_split_keywords(message))
    return {token for token in tokens if token}


def _collect_plan_tokens(repair_plan: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for item in repair_plan:
        strategy = str(item.get("strategy") or "").lower()
        if strategy:
            tokens.add(strategy)
            tokens.update(strategy.split("_"))
    return {token for token in tokens if token}


def _collect_symbol_tokens(symbols: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for symbol in symbols:
        name = str(symbol.get("name") or "").lower()
        owner = str(symbol.get("ownerClass") or symbol.get("owner_class") or "").lower()
        tokens.update(_split_keywords(name))
        tokens.update(_split_keywords(owner))
    return {token for token in tokens if token}


def _collect_context_tokens(context_summary: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    methods = context_summary.get("methods", [])
    if isinstance(methods, list):
        for method in methods:
            if isinstance(method, dict):
                tokens.update(_split_keywords(str(method.get("name") or "")))
            else:
                tokens.update(_split_keywords(str(method)))
    return {token for token in tokens if token}


def _split_keywords(text: str) -> set[str]:
    raw = text.replace(".", " ").replace("-", " ").replace("_", " ")
    return {part.strip() for part in raw.split() if part.strip()}


def _to_case_match(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": item.get("case_id"),
        "pattern": item.get("pattern"),
        "score": item.get("score", item.get("success_rate", 0.0)),
        "trigger_signals": item.get("trigger_signals", []),
        "strategy": item.get("strategy", item.get("pattern")),
        "risk_note": item.get("risk_note", ""),
        "success_rate": item.get("success_rate", 0.0),
        "before_code": item.get("before_code", ""),
        "after_code": item.get("after_code", ""),
        "diff": item.get("diff", ""),
    }
