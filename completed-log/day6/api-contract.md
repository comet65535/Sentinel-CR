# Sentinel-CR Day6 API Contract

## 1. 文档目的

本文档定义 Sentinel-CR 在 **Day6「平台能力日」** 的接口契约。写法采用：

- **当前 Day5 可运行基线**
- **Day6 增量扩展**
- **兼容性优先**

也就是说，这不是一份“README 理想态”契约，而是一份 **能指导 Codex 在现有代码上增量实现 Day6 的工程契约**。

---

## 2. 设计原则

### 2.1 外部接口稳定优先
以下 public API 必须保持可用，字段名不允许破坏性修改：

- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/events`

### 2.2 Day6 只做增量，不做大爆炸重写
Day6 新能力通过以下方式落地：

- 给现有 DTO 增加 **可选字段**
- 增加新的 internal endpoint
- 给现有 result / event payload 增加 **可选 block**
- 保留已有事件名与主要 payload 结构

### 2.3 后端仍然是外部事件的权威源
Python 内部事件流不带 `timestamp` 与 `sequence`；Day6 之后也保持这个分层：

- **Python**：负责生成业务事件
- **Java Backend**：负责补 `timestamp / sequence / SSE event id`

### 2.4 Day6 的 public 入口仍以 snippet 为主
Day6 重点是平台骨架，不是 Day7 的 repo / PR 最终产品化入口。

因此：

- public `sourceType` 仍以 `snippet` 为稳定路径
- repo / PR / MCP 能力先通过 internal contract 打底
- public repo/PR 模式暂不作为 Day6 强制要求

---

## 3. Public API（Frontend ↔ Backend）

## 3.1 创建评审任务

### Endpoint
`POST /api/reviews`

### 当前稳定请求体
```json
{
  "codeText": "public class Demo { ... }",
  "language": "java",
  "sourceType": "snippet",
  "options": {
    "enable_verifier": true,
    "max_retries": 2,
    "enable_security_rescan": false
  }
}
```

### Day6 扩展后的请求体（推荐）
```json
{
  "codeText": "public class Demo { ... }",
  "language": "java",
  "sourceType": "snippet",
  "options": {
    "enable_verifier": true,
    "max_retries": 2,
    "enable_security_rescan": false,
    "debug": true,
    "context_policy": "lazy",
    "context_budget_tokens": 12000,
    "persist_verified_case": false
  },
  "metadata": {
    "requested_by": "frontend-ui",
    "debug_mode": true,
    "trace_id": "trace_xxx",
    "repo_id": null,
    "repo_profile_id": null,
    "pr_url": null,
    "labels": ["day6"]
  }
}
```

### 字段说明
| 字段 | 是否必须 | Day5 现状 | Day6 约定 |
|---|---:|---|---|
| `codeText` | 是 | 已有 | 不变 |
| `language` | 是 | 已有，当前仅支持 `java` | 不变 |
| `sourceType` | 是 | 已有，当前仅支持 `snippet` | Day6 仍保持 `snippet` 稳定 |
| `options.enable_verifier` | 否 | 已有 | 不变 |
| `options.max_retries` | 否 | 已有 | 不变 |
| `options.enable_security_rescan` | 否 | 已有 | 不变 |
| `options.debug` | 否 | 新增 | 控制 debug payload / 面板细节 |
| `options.context_policy` | 否 | 新增 | `none` / `lazy`，默认 `none` |
| `options.context_budget_tokens` | 否 | 新增 | Lazy Context token 预算 |
| `options.persist_verified_case` | 否 | 新增 | 是否将 verified patch 回写 case store |
| `metadata` | 否 | Day5 public DTO 尚未暴露 | Day6 必须补齐为可选字段并透传 |

### 响应体
```json
{
  "taskId": "rev_20260403130000_ab12cd",
  "status": "CREATED",
  "message": "review task created"
}
```

### 兼容性要求
- `taskId / status / message` 不允许改名
- status 仍为 `CREATED | RUNNING | COMPLETED | FAILED`
- 即使新增 `metadata`，不提供时也必须保持当前行为

---

## 3.2 查询任务详情

### Endpoint
`GET /api/reviews/{taskId}`

### 响应体顶层
```json
{
  "taskId": "rev_20260403130000_ab12cd",
  "status": "COMPLETED",
  "createdAt": "2026-04-03T13:00:00Z",
  "updatedAt": "2026-04-03T13:00:09Z",
  "result": {},
  "errorMessage": null
}
```

### `result` 当前稳定结构
Day5 已有的结果块必须保留：

```json
{
  "engine": "python",
  "summary": {},
  "analyzer": {},
  "analyzer_evidence": {
    "issues": [],
    "symbols": [],
    "context_summary": {},
    "diagnostics": []
  },
  "issues": [],
  "symbols": [],
  "contextSummary": {},
  "diagnostics": [],
  "issue_graph": {},
  "repair_plan": [],
  "planner_summary": {},
  "memory": {
    "matches": []
  },
  "patch": {},
  "attempts": [],
  "verification": {}
}
```

### Day6 扩展后的 `result` 推荐结构
```json
{
  "engine": "python",
  "summary": {
    "issue_count": 2,
    "repair_plan_count": 2,
    "memory_match_count": 1,
    "attempt_count": 2,
    "retry_count": 1,
    "verified_level": "L2",
    "final_outcome": "verified_patch",
    "failed_stage": null,
    "failure_reason": null,
    "failure_detail": null,
    "retry_exhausted": false,
    "no_fix_needed": false,
    "user_message": "Patch verified at L1 or above."
  },
  "analyzer": {},
  "analyzer_evidence": {
    "issues": [],
    "symbols": [],
    "context_summary": {},
    "diagnostics": []
  },
  "issues": [],
  "symbols": [],
  "contextSummary": {},
  "diagnostics": [],
  "issue_graph": {
    "schema_version": "day6.v1",
    "nodes": [],
    "edges": []
  },
  "repair_plan": [],
  "planner_summary": {},
  "memory": {
    "matches": [],
    "short_term": {},
    "repo_profile": {},
    "case_store": {
      "source": "jsonl",
      "promotion_candidate": false
    }
  },
  "context_budget": {
    "enabled": true,
    "policy": "lazy",
    "budget_tokens": 12000,
    "used_tokens": 2480,
    "remaining_tokens": 9520,
    "load_stage": "symbol_graph",
    "sources": []
  },
  "tool_trace": [],
  "patch": {},
  "attempts": [],
  "verification": {}
}
```

### 兼容性要求
1. Day5 已有字段必须继续返回  
2. Day6 新增字段必须是 **optional**  
3. 前端可优先从 `review_completed.payload.result` 取结果；若为空，再 fallback 到 `GET /api/reviews/{taskId}`

---

## 3.3 订阅事件流

### Endpoint
`GET /api/reviews/{taskId}/events`

### 媒体类型
`text/event-stream`

### SSE 约定
- `id = sequence`
- `event = eventType`
- `data = ReviewEvent`

### `ReviewEvent` 外部结构
```json
{
  "taskId": "rev_20260403130000_ab12cd",
  "eventType": "issue_graph_built",
  "message": "issue graph built",
  "timestamp": "2026-04-03T13:00:04Z",
  "sequence": 8,
  "status": "RUNNING",
  "payload": {}
}
```

### 外部事件 envelope 约束
| 字段 | 必须 | 说明 |
|---|---:|---|
| `taskId` | 是 | 任务 ID |
| `eventType` | 是 | 事件名 |
| `message` | 是 | 简短说明 |
| `timestamp` | 是 | 由 backend 生成 |
| `sequence` | 是 | 单任务内严格递增 |
| `status` | 是 | `CREATED / RUNNING / COMPLETED / FAILED` |
| `payload` | 是 | 结构化数据，允许为空对象 |

---

## 4. Internal Python Engine API（Backend ↔ Python）

## 4.1 启动内部评审流

### Endpoint
`POST /internal/reviews/run`

### 媒体类型
- Request: `application/json`
- Response: `application/x-ndjson`

### 请求体
```json
{
  "taskId": "rev_20260403130000_ab12cd",
  "codeText": "public class Demo { ... }",
  "language": "java",
  "sourceType": "snippet",
  "options": {
    "enable_verifier": true,
    "max_retries": 2,
    "enable_security_rescan": false,
    "debug": true,
    "context_policy": "lazy",
    "context_budget_tokens": 12000,
    "persist_verified_case": false
  },
  "metadata": {
    "requested_by": "backend-java",
    "debug_mode": false,
    "trace_id": "trace_xxx",
    "repo_id": null,
    "repo_profile_id": null,
    "pr_url": null
  }
}
```

### 内部 NDJSON 事件结构
```json
{
  "taskId": "rev_20260403130000_ab12cd",
  "eventType": "analysis_started",
  "message": "python engine started analyzer state graph",
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

### 注意
- Python internal event **不带** `timestamp / sequence`
- Java backend 接收后统一补 timestamp、sequence，再转成 SSE

---

## 5. Internal MCP API（Day6 新增）

> 这些接口是 **backend-java internal** 能力，不直接暴露给最终用户页面作为稳定 public API。  
> 其目标是为 Python Planner / Fixer / Verifier 提供 **Resources + Tools** 双通道。

## 5.1 通用返回 envelope

### 成功
```json
{
  "ok": true,
  "kind": "resource",
  "name": "repo-tree",
  "request_id": "mcp_01",
  "data": {},
  "meta": {
    "latency_ms": 12,
    "cache_hit": false
  },
  "error": null
}
```

### 失败
```json
{
  "ok": false,
  "kind": "tool",
  "name": "run-sandbox",
  "request_id": "mcp_02",
  "data": null,
  "meta": {
    "latency_ms": 9,
    "cache_hit": false
  },
  "error": {
    "code": "workspace_missing",
    "message": "workspace not found"
  }
}
```

---

## 5.2 Resource Endpoints

## 5.2.1 获取仓库树
`GET /internal/mcp/resources/repo-tree`

### Query
- `taskId`：必填
- `depth`：可选，默认 `2`

### 响应 `data`
```json
{
  "root": "/workspace/rev_xxx",
  "entries": [
    {
      "path": "src/main/java/com/demo/UserService.java",
      "kind": "file"
    },
    {
      "path": "src/main/java/com/demo",
      "kind": "directory"
    }
  ]
}
```

---

## 5.2.2 获取文件内容 / 片段
`GET /internal/mcp/resources/file`

### Query
- `taskId`：必填
- `path`：必填
- `startLine`：可选
- `endLine`：可选

### 响应 `data`
```json
{
  "path": "src/main/java/com/demo/UserService.java",
  "startLine": 1,
  "endLine": 120,
  "truncated": false,
  "content": "package com.demo; ..."
}
```

---

## 5.2.3 获取 schema 摘要
`GET /internal/mcp/resources/schema`

### Query
- `taskId`：必填
- `schemaType`：可选，例如 `api_contract` / `event_schema`

### 响应 `data`
```json
{
  "schemaType": "api_contract",
  "version": "day6.v1",
  "summary": "Current contract summary ..."
}
```

---

## 5.2.4 获取 build log 摘要
`GET /internal/mcp/resources/build-log-summary`

### Query
- `taskId`：必填

### 响应 `data`
```json
{
  "status": "available",
  "latest_build": {
    "command": "mvn -q -DskipTests compile",
    "exit_code": 1,
    "stderr_summary": "cannot find symbol ..."
  }
}
```

---

## 5.2.5 获取测试摘要
`GET /internal/mcp/resources/test-summary`

### Query
- `taskId`：必填

### 响应 `data`
```json
{
  "status": "available",
  "suggested_test_commands": [
    "mvn -q -Dtest=UserServiceTest test"
  ],
  "last_result": {
    "passed": 12,
    "failed": 1,
    "skipped": 0
  }
}
```

---

## 5.2.6 解析 PR diff
`POST /internal/mcp/resources/pr-diff/parse`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "pr_url": "https://github.com/org/repo/pull/1",
  "diff_text": null
}
```

### 响应 `data`
```json
{
  "changed_files": [
    {
      "path": "src/main/java/com/demo/UserService.java",
      "hunks": [
        {
          "old_start": 10,
          "new_start": 10,
          "header": "@@ -10,6 +10,7 @@"
        }
      ]
    }
  ]
}
```

---

## 5.3 Tool Endpoints

## 5.3.1 resolve-symbol
`POST /internal/mcp/tools/resolve-symbol`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "symbol": "createUser",
  "language": "java"
}
```

### 响应 `data`
```json
{
  "definitions": [
    {
      "path": "src/main/java/com/demo/UserService.java",
      "line": 42,
      "kind": "method"
    }
  ]
}
```

---

## 5.3.2 find-references
`POST /internal/mcp/tools/find-references`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "symbol": "createUser",
  "path": "src/main/java/com/demo/UserService.java"
}
```

### 响应 `data`
```json
{
  "references": [
    {
      "path": "src/main/java/com/demo/UserController.java",
      "line": 19,
      "kind": "call"
    }
  ]
}
```

---

## 5.3.3 run-analyzer
`POST /internal/mcp/tools/run-analyzer`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "paths": [
    "src/main/java/com/demo/UserService.java"
  ],
  "analyzers": ["ast", "semgrep", "symbol_graph"]
}
```

### 响应 `data`
```json
{
  "issues": [],
  "symbols": [],
  "summary": {}
}
```

---

## 5.3.4 run-sandbox
`POST /internal/mcp/tools/run-sandbox`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "stage": "compile",
  "command": "mvn -q -DskipTests compile",
  "working_directory": "/workspace/rev_xxx"
}
```

### 响应 `data`
```json
{
  "stage": "compile",
  "status": "passed",
  "exit_code": 0,
  "stdout_summary": "",
  "stderr_summary": ""
}
```

---

## 5.3.5 query-tests
`POST /internal/mcp/tools/query-tests`

### 请求体
```json
{
  "taskId": "rev_xxx",
  "paths": [
    "src/main/java/com/demo/UserService.java"
  ],
  "symbols": ["createUser"]
}
```

### 响应 `data`
```json
{
  "suggested_tests": [
    "UserServiceTest",
    "UserControllerTest"
  ],
  "commands": [
    "mvn -q -Dtest=UserServiceTest test"
  ]
}
```

---

## 6. 共享业务对象契约

## 6.1 Issue Graph（兼容 Day5，扩展 Day6）

### 当前 Day5 必保字段
```json
{
  "schema_version": "day3.v1",
  "nodes": [
    {
      "issue_id": "ISSUE-1",
      "type": "null_pointer",
      "severity": "MEDIUM",
      "location": {
        "file_path": "snippet.java",
        "line": 12
      },
      "related_symbols": ["getUser"],
      "depends_on": [],
      "conflicts_with": [],
      "fix_scope": "single_file",
      "strategy_hint": "null_guard",
      "requires_test": false,
      "requires_context": false
    }
  ],
  "edges": [
    {
      "from_issue_id": "ISSUE-1",
      "to_issue_id": "ISSUE-2",
      "edge_type": "depends_on"
    }
  ]
}
```

### Day6 推荐扩展字段
```json
{
  "schema_version": "day6.v1",
  "nodes": [
    {
      "issue_id": "ISSUE-1",
      "node_type": "issue",
      "type": "null_pointer",
      "severity": "MEDIUM",
      "location": {
        "file_path": "snippet.java",
        "line": 12
      },
      "file_path": "snippet.java",
      "related_symbols": ["getUser"],
      "symbol_refs": ["getUser"],
      "depends_on": [],
      "conflicts_with": [],
      "fix_scope": "single_file",
      "strategy_hint": "null_guard",
      "requires_test": false,
      "requires_context": false,
      "patch_group": "group-1",
      "verifier_result": null
    }
  ],
  "edges": [
    {
      "from_issue_id": "ISSUE-1",
      "to_issue_id": "ISSUE-2",
      "edge_type": "depends_on"
    }
  ]
}
```

### 兼容性要求
- `location.file_path` 与 `related_symbols` 必须继续存在
- Day6 新加的 `node_type / file_path / symbol_refs / patch_group / verifier_result` 为 optional

---

## 6.2 Repair Plan
```json
[
  {
    "issue_id": "ISSUE-1",
    "priority": 1,
    "strategy": "null_guard",
    "patch_group": "group-1",
    "fix_scope": "single_file",
    "requires_context": false,
    "requires_test": false,
    "blocked_by": []
  }
]
```

---

## 6.3 Memory Block
```json
{
  "matches": [
    {
      "case_id": "case-null-001",
      "pattern": "null guard",
      "success_rate": 0.91
    }
  ],
  "short_term": {
    "latest_analyzer_evidence": {},
    "latest_patch": {},
    "latest_verifier_failure": {},
    "retry_context": {},
    "token_usage": {
      "used_tokens": 2480
    }
  },
  "repo_profile": {
    "repo_id": "demo-repo",
    "style_preferences": [],
    "preferred_build_command": "mvn -q -DskipTests compile",
    "preferred_test_command": "mvn -q test",
    "hotspots": []
  },
  "case_store": {
    "source": "jsonl",
    "promotion_candidate": false
  }
}
```

---

## 6.4 Context Budget Block
```json
{
  "enabled": true,
  "policy": "lazy",
  "budget_tokens": 12000,
  "used_tokens": 2480,
  "remaining_tokens": 9520,
  "load_stage": "symbol_graph",
  "sources": [
    {
      "source_id": "ctx-1",
      "kind": "snippet_window",
      "path": "snippet.java",
      "token_count": 620,
      "reason": "issue vicinity"
    },
    {
      "source_id": "ctx-2",
      "kind": "symbol_summary",
      "symbol": "createUser",
      "token_count": 180,
      "reason": "planner requested related symbol summary"
    }
  ]
}
```

---

## 6.5 Tool Trace（Day6 Debug 扩展）
```json
[
  {
    "tool_name": "resolve-symbol",
    "selected_by": "planner",
    "args": {
      "symbol": "createUser"
    },
    "status": "success",
    "latency_ms": 18
  }
]
```

---

## 6.6 Verification Block
```json
{
  "status": "passed",
  "verified_level": "L3",
  "passed_stages": ["patch_apply", "compile", "lint", "test"],
  "failed_stage": null,
  "stages": [
    {
      "stage": "patch_apply",
      "status": "passed",
      "exit_code": 0,
      "stdout_summary": "",
      "stderr_summary": "",
      "reason": null
    },
    {
      "stage": "compile",
      "status": "passed",
      "exit_code": 0,
      "stdout_summary": "",
      "stderr_summary": "",
      "reason": null
    },
    {
      "stage": "lint",
      "status": "passed",
      "exit_code": 0,
      "stdout_summary": "",
      "stderr_summary": "",
      "reason": null
    },
    {
      "stage": "test",
      "status": "passed",
      "exit_code": 0,
      "stdout_summary": "",
      "stderr_summary": "",
      "reason": null
    }
  ],
  "summary": "Verifier passed at L3"
}
```

### Verified Level 规则
- `L1 = patch_apply + compile`
- `L2 = L1 + lint`
- `L3 = L2 + test`
- `L4 = L3 + security_rescan`

---

## 7. 兼容性与降级策略

## 7.1 不允许破坏的字段 / 事件
以下名字禁止重命名：

- `taskId`
- `eventType`
- `payload`
- `summary`
- `issue_graph`
- `repair_plan`
- `patch`
- `verification`

### 当前稳定事件名也必须保持
包括但不限于：

- `task_created`
- `analysis_started`
- `ast_parsing_started`
- `ast_parsing_completed`
- `symbol_graph_started`
- `symbol_graph_completed`
- `semgrep_scan_started`
- `semgrep_scan_completed`
- `semgrep_scan_warning`
- `analyzer_completed`
- `planner_started`
- `issue_graph_built`
- `repair_plan_created`
- `planner_completed`
- `case_memory_search_started`
- `case_memory_matched`
- `case_memory_completed`
- `fixer_started`
- `patch_generated`
- `fixer_completed`
- `fixer_failed`
- `verifier_started`
- `patch_apply_started/completed/failed`
- `compile_started/completed/failed`
- `lint_started/completed/failed`
- `test_started/completed/failed`
- `security_rescan_started/completed/failed`
- `verifier_completed`
- `verifier_failed`
- `review_retry_scheduled`
- `review_retry_started`
- `review_completed`
- `review_failed`

---

## 7.2 MCP 不可用时的降级
若 Day6 MCP 资源 / 工具暂不可用：

- 主链仍必须支持 snippet-only
- context budget 可退化为仅统计当前 snippet 上下文
- `context_budget.enabled=false`
- `tool_trace=[]`
- 不得影响 Day5 主链路出结果

---

## 7.3 L2/L3/L4 暂无配置时的降级
若 lint / test / security rescan 未配置：

- 返回结构化 `skipped`
- 不允许抛异常导致整条链路失败
- 但要保留真实 stage 结果，方便前端展示“为什么是 skipped”

---

## 8. Day6 落地检查清单

实现完成后，必须满足：

1. `/api/reviews` 外部接口继续可用  
2. `CreateReviewRequest` public DTO 新增可选 `metadata`，并透传到 Python internal request  
3. `/internal/reviews/run` 保持 NDJSON 事件流  
4. 新增 `/internal/mcp/resources/*` 与 `/internal/mcp/tools/*`  
5. `result` 中新增 `context_budget` 与扩展版 `memory` block  
6. `issue_graph` 兼容 Day5 字段并支持 Day6 视图字段  
7. `verification` block 能承载真实 L1/L2/L3/L4 骨架结果  
8. 所有 Day6 新字段均为 optional，不能破坏老前端读取
