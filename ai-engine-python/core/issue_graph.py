from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, TypedDict


class IssueLocation(TypedDict):
    file_path: str
    line: int


class IssueNode(TypedDict):
    issue_id: str
    type: str
    severity: str
    location: IssueLocation
    related_symbols: list[str]
    depends_on: list[str]
    conflicts_with: list[str]
    fix_scope: str
    strategy_hint: str
    requires_test: bool
    requires_context: bool


class IssueEdge(TypedDict):
    from_issue_id: str
    to_issue_id: str
    edge_type: str


class IssueGraph(TypedDict):
    schema_version: str
    nodes: list[IssueNode]
    edges: list[IssueEdge]


class RepairPlanItem(TypedDict):
    issue_id: str
    priority: int
    strategy: str
    patch_group: str
    fix_scope: str
    requires_context: bool
    requires_test: bool
    blocked_by: list[str]


ALLOWED_EDGE_TYPES = {"depends_on", "conflicts_with", "same_symbol"}
DEFAULT_FILE_PATH = "snippet.java"
SCHEMA_VERSION = "day3.v1"
SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}
SCOPE_ORDER = {
    "single_file": 0,
    "multi_file": 1,
    "unknown": 2,
}
HIGH_RISK_TYPE_TOKENS = {
    "sql_injection",
    "resource_leak",
    "missing_validation",
    "bad_exception_handling",
}
STRATEGY_HINT_MAPPING = {
    "null_pointer": "null_guard",
    "sql_injection": "parameterized_query",
    "resource_leak": "try_with_resources",
    "missing_validation": "input_validation",
    "bad_exception_handling": "exception_logging",
    "syntax_error": "syntax_fix",
}


def build_issue_graph(
    issues: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    context_summary: dict[str, Any],
) -> IssueGraph:
    prepared_issues = [_prepare_issue(issue, index) for index, issue in enumerate(issues, start=1)]
    symbol_entries = [_prepare_symbol(symbol) for symbol in symbols]
    symbol_owner_index: dict[str, str] = {}
    symbol_line_entries: list[dict[str, Any]] = []
    for entry in symbol_entries:
        symbol_owner_index[entry["label"]] = entry["owner_class"]
        symbol_line_entries.append(entry)

    nodes: list[IssueNode] = []
    for issue in prepared_issues:
        related_symbols = _resolve_related_symbols(issue, symbol_line_entries)
        owner_classes = sorted(
            {
                symbol_owner_index.get(symbol_name, "")
                for symbol_name in related_symbols
                if symbol_owner_index.get(symbol_name, "")
            }
        )
        fix_scope = _infer_fix_scope(owner_classes)
        issue_type = _normalize_issue_type(issue)
        strategy_hint = _resolve_strategy_hint(issue_type)
        requires_test = _resolve_requires_test(issue_type, issue["severity"], fix_scope, owner_classes)

        node: IssueNode = {
            "issue_id": issue["issue_id"],
            "type": issue_type,
            "severity": issue["severity"],
            "location": {
                "file_path": issue["file_path"],
                "line": issue["line"],
            },
            "related_symbols": sorted(related_symbols),
            "depends_on": [],
            "conflicts_with": [],
            "fix_scope": fix_scope,
            "strategy_hint": strategy_hint,
            "requires_test": requires_test,
            "requires_context": fix_scope in {"multi_file", "unknown"},
        }
        nodes.append(node)

    nodes_by_id: dict[str, IssueNode] = {node["issue_id"]: node for node in nodes}

    _populate_dependencies(nodes)
    _populate_conflicts(nodes)
    _sort_node_relations(nodes)

    edges = _build_edges(nodes_by_id)

    nodes_sorted = sorted(nodes, key=lambda item: item["issue_id"])
    edges_sorted = sorted(
        edges,
        key=lambda item: (item["from_issue_id"], item["to_issue_id"], item["edge_type"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": nodes_sorted,
        "edges": edges_sorted,
    }


def build_repair_plan(issue_graph: IssueGraph) -> list[RepairPlanItem]:
    nodes = [dict(node) for node in issue_graph.get("nodes", [])]
    node_map = {node["issue_id"]: node for node in nodes}
    indegree: dict[str, int] = {node["issue_id"]: 0 for node in nodes}
    dependents: dict[str, list[str]] = defaultdict(list)

    for node in nodes:
        valid_dependencies = [dep for dep in node.get("depends_on", []) if dep in indegree]
        indegree[node["issue_id"]] = len(valid_dependencies)
        for dependency in valid_dependencies:
            dependents[dependency].append(node["issue_id"])

    available = [issue_id for issue_id, degree in indegree.items() if degree == 0]
    sorted_issue_ids: list[str] = []
    while available:
        available.sort(key=lambda issue_id: _node_sort_key(node_map[issue_id]))
        selected = available.pop(0)
        sorted_issue_ids.append(selected)
        for dep_issue_id in dependents.get(selected, []):
            indegree[dep_issue_id] -= 1
            if indegree[dep_issue_id] == 0:
                available.append(dep_issue_id)

    remaining = [issue_id for issue_id in indegree if issue_id not in sorted_issue_ids]
    if remaining:
        remaining.sort(key=lambda issue_id: _node_sort_key(node_map[issue_id]))
        sorted_issue_ids.extend(remaining)

    plan_items_unsorted: list[RepairPlanItem] = []
    patch_groups: list[list[str]] = []
    for index, issue_id in enumerate(sorted_issue_ids, start=1):
        node = node_map[issue_id]
        patch_group_id = _assign_patch_group(node, patch_groups, node_map)
        plan_items_unsorted.append(
            {
                "issue_id": issue_id,
                "priority": index,
                "strategy": node["strategy_hint"],
                "patch_group": patch_group_id,
                "fix_scope": node["fix_scope"],
                "requires_context": bool(node.get("requires_context", False)),
                "requires_test": bool(node.get("requires_test", False)),
                "blocked_by": sorted(node.get("depends_on", [])),
            }
        )

    plan_items_sorted = sorted(plan_items_unsorted, key=lambda item: (item["priority"], item["issue_id"]))
    for priority, item in enumerate(plan_items_sorted, start=1):
        item["priority"] = priority
    return plan_items_sorted


def _prepare_issue(issue: dict[str, Any], index: int) -> dict[str, Any]:
    issue_id = str(
        issue.get("issue_id")
        or issue.get("issueId")
        or issue.get("id")
        or ""
    ).strip()
    if not issue_id:
        issue_id = f"ISSUE-{index}"

    severity = str(issue.get("severity") or "MEDIUM").strip().upper()
    if severity not in SEVERITY_ORDER:
        severity = "MEDIUM"

    line = _to_int(issue.get("line"), default=None)
    if line is None:
        line = _to_int(issue.get("startLine"), default=1)

    file_path = str(
        issue.get("file_path")
        or issue.get("filePath")
        or issue.get("path")
        or DEFAULT_FILE_PATH
    ).strip() or DEFAULT_FILE_PATH

    issue_type = str(
        issue.get("type")
        or issue.get("issue_type")
        or issue.get("issueType")
        or issue.get("ruleId")
        or issue.get("rule_id")
        or "unknown_issue"
    ).strip()

    related_symbols_seed = _collect_related_symbol_hints(issue)

    return {
        "issue_id": issue_id,
        "severity": severity,
        "line": line,
        "file_path": file_path,
        "raw": issue,
        "issue_type_raw": issue_type,
        "related_symbols_seed": related_symbols_seed,
    }


def _prepare_symbol(symbol: dict[str, Any]) -> dict[str, Any]:
    owner_class = str(symbol.get("ownerClass") or symbol.get("owner_class") or "").strip()
    label = str(
        symbol.get("symbolId")
        or symbol.get("symbol_id")
        or symbol.get("qualifiedName")
        or symbol.get("name")
        or ""
    ).strip()
    if not label:
        label = f"symbol:{owner_class}:{symbol.get('name', 'unknown')}"

    start_line = _to_int(symbol.get("startLine"), default=1)
    end_line = _to_int(symbol.get("endLine"), default=start_line)
    if end_line < start_line:
        end_line = start_line

    return {
        "label": label,
        "owner_class": owner_class,
        "start_line": start_line,
        "end_line": end_line,
        "name": str(symbol.get("name") or "").strip(),
    }


def _collect_related_symbol_hints(issue: dict[str, Any]) -> list[str]:
    values: list[str] = []
    candidate_keys = [
        "related_symbols",
        "relatedSymbols",
        "symbol_hints",
        "symbolHints",
    ]
    for key in candidate_keys:
        raw = issue.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            text = str(item).strip()
            if text:
                values.append(text)
    return sorted(set(values))


def _resolve_related_symbols(issue: dict[str, Any], symbol_entries: list[dict[str, Any]]) -> set[str]:
    related_symbols: set[str] = set(issue["related_symbols_seed"])
    issue_line = issue["line"]
    issue_raw = issue["raw"]

    snippet_text = str(issue_raw.get("snippet") or issue_raw.get("message") or "")
    for entry in symbol_entries:
        if entry["start_line"] <= issue_line <= entry["end_line"]:
            related_symbols.add(entry["label"])
            continue
        owner_class = entry["owner_class"]
        if owner_class and owner_class in snippet_text:
            related_symbols.add(entry["label"])
            continue
        symbol_name = entry["name"]
        if symbol_name and symbol_name in snippet_text:
            related_symbols.add(entry["label"])
    return related_symbols


def _infer_fix_scope(owner_classes: list[str]) -> str:
    unique_owner_classes = sorted({item for item in owner_classes if item})
    if len(unique_owner_classes) == 1:
        return "single_file"
    if len(unique_owner_classes) > 1:
        return "multi_file"
    return "unknown"


def _normalize_issue_type(issue: dict[str, Any]) -> str:
    raw = issue["issue_type_raw"].lower()
    if "syntax_error" in raw or "parse_error" in raw or "ast_parse_error" in raw:
        return "syntax_error"
    if "null" in raw and ("pointer" in raw or "deref" in raw):
        return "null_pointer"
    if "sql" in raw and "injection" in raw:
        return "sql_injection"
    if "resource" in raw and ("leak" in raw or "close" in raw):
        return "resource_leak"
    if "validation" in raw:
        return "missing_validation"
    if "exception" in raw and ("handling" in raw or "log" in raw):
        return "bad_exception_handling"
    return raw.replace("-", "_").replace(".", "_") or "unknown_issue"


def _resolve_strategy_hint(issue_type: str) -> str:
    return STRATEGY_HINT_MAPPING.get(issue_type, "manual_review")


def _resolve_requires_test(
    issue_type: str,
    severity: str,
    fix_scope: str,
    owner_classes: list[str],
) -> bool:
    if issue_type == "syntax_error":
        return False
    if issue_type in HIGH_RISK_TYPE_TOKENS:
        return True
    if severity in {"HIGH", "CRITICAL"}:
        return True
    if fix_scope == "multi_file":
        return True
    unique_owner_classes = {item for item in owner_classes if item}
    if len(unique_owner_classes) > 1:
        return True
    return False


def _populate_dependencies(nodes: list[IssueNode]) -> None:
    validation_nodes = [node for node in nodes if node["type"] == "missing_validation"]
    if not validation_nodes:
        return

    for node in nodes:
        if node["type"] == "missing_validation":
            continue
        node_symbols = set(node["related_symbols"])
        for validation in validation_nodes:
            validation_symbols = set(validation["related_symbols"])
            if node_symbols and validation_symbols and node_symbols.intersection(validation_symbols):
                node["depends_on"].append(validation["issue_id"])


def _populate_conflicts(nodes: list[IssueNode]) -> None:
    for index, node in enumerate(nodes):
        for peer in nodes[index + 1 :]:
            if _is_conflict(node, peer):
                node["conflicts_with"].append(peer["issue_id"])
                peer["conflicts_with"].append(node["issue_id"])


def _is_conflict(left: IssueNode, right: IssueNode) -> bool:
    left_loc = left["location"]
    right_loc = right["location"]
    if (
        left_loc["file_path"] == right_loc["file_path"]
        and left_loc["line"] == right_loc["line"]
    ):
        return True

    shared_symbols = set(left["related_symbols"]).intersection(set(right["related_symbols"]))
    if not shared_symbols:
        return False

    if (
        left["strategy_hint"] != right["strategy_hint"]
        and left["strategy_hint"] != "manual_review"
        and right["strategy_hint"] != "manual_review"
    ):
        return True

    return len(shared_symbols) >= 2


def _sort_node_relations(nodes: list[IssueNode]) -> None:
    for node in nodes:
        node["depends_on"] = sorted(set(node["depends_on"]))
        node["conflicts_with"] = sorted(set(node["conflicts_with"]))
        node["related_symbols"] = sorted(set(node["related_symbols"]))


def _build_edges(nodes_by_id: dict[str, IssueNode]) -> list[IssueEdge]:
    edges: list[IssueEdge] = []
    seen: set[tuple[str, str, str]] = set()
    node_values = list(nodes_by_id.values())

    for node in node_values:
        for dependency_id in node.get("depends_on", []):
            if dependency_id not in nodes_by_id:
                continue
            _append_edge(seen, edges, node["issue_id"], dependency_id, "depends_on")

        for conflict_id in node.get("conflicts_with", []):
            if conflict_id not in nodes_by_id:
                continue
            from_issue_id, to_issue_id = sorted([node["issue_id"], conflict_id])
            _append_edge(seen, edges, from_issue_id, to_issue_id, "conflicts_with")

    for index, node in enumerate(node_values):
        symbols = set(node.get("related_symbols", []))
        if not symbols:
            continue
        for peer in node_values[index + 1 :]:
            if symbols.intersection(set(peer.get("related_symbols", []))):
                from_issue_id, to_issue_id = sorted([node["issue_id"], peer["issue_id"]])
                _append_edge(seen, edges, from_issue_id, to_issue_id, "same_symbol")

    return edges


def _append_edge(
    seen: set[tuple[str, str, str]],
    edges: list[IssueEdge],
    from_issue_id: str,
    to_issue_id: str,
    edge_type: str,
) -> None:
    if edge_type not in ALLOWED_EDGE_TYPES:
        return
    key = (from_issue_id, to_issue_id, edge_type)
    if key in seen:
        return
    seen.add(key)
    edges.append(
        {
            "from_issue_id": from_issue_id,
            "to_issue_id": to_issue_id,
            "edge_type": edge_type,
        }
    )


def _node_sort_key(node: dict[str, Any]) -> tuple[int, int, int, int, str]:
    severity_rank = SEVERITY_ORDER.get(str(node.get("severity", "MEDIUM")).upper(), 2)
    depends_count = len(node.get("depends_on", []))
    scope_rank = SCOPE_ORDER.get(str(node.get("fix_scope", "unknown")), 2)
    strategy_rank = 0 if str(node.get("strategy_hint", "manual_review")) != "manual_review" else 1
    return (severity_rank, depends_count, scope_rank, strategy_rank, str(node.get("issue_id", "")))


def _assign_patch_group(
    node: dict[str, Any],
    patch_groups: list[list[str]],
    node_map: dict[str, dict[str, Any]],
) -> str:
    for index, group in enumerate(patch_groups, start=1):
        if _can_join_group(node, group, node_map):
            group.append(node["issue_id"])
            return f"PATCH-{index}"

    patch_groups.append([node["issue_id"]])
    return f"PATCH-{len(patch_groups)}"


def _can_join_group(
    node: dict[str, Any],
    group: list[str],
    node_map: dict[str, dict[str, Any]],
) -> bool:
    node_id = node["issue_id"]
    conflicts = set(node.get("conflicts_with", []))
    depends = set(node.get("depends_on", []))
    for peer_id in group:
        peer = node_map[peer_id]
        peer_conflicts = set(peer.get("conflicts_with", []))
        if peer_id in conflicts or node_id in peer_conflicts:
            return False
        if peer_id in depends or node_id in set(peer.get("depends_on", [])):
            return False
    return True


def _to_int(value: Any, *, default: int | None = 0) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                return int(float(text))
            except ValueError:
                pass
    if default is None:
        return None
    return default
