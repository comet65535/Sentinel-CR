# Sentinel-CR Day6 Event Schema

## 1. 文档目的

本文档定义 Sentinel-CR 的事件协议，覆盖：

- 当前 Day5 已经在发的稳定事件
- Day6 新增的 LangGraph / Memory / Context / MCP 事件
- backend 外部 SSE envelope
- python 内部 NDJSON envelope
- 事件排序、终止条件与 payload 规范

**设计原则：兼容 Day5，增量扩展 Day6。**

---

## 2. 事件分层

## 2.1 Python Internal Event
Python 引擎通过 NDJSON 向 backend 输出：

```json
{
  "taskId": "rev_xxx",
  "eventType": "analysis_started",
  "message": "python engine started analyzer state graph",
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

### 特征
- 不带 `timestamp`
- 不带 `sequence`
- payload 更偏业务层

---

## 2.2 Backend External Event
backend 对 Python 事件进行包装后，以 SSE 发给前端：

```json
{
  "taskId": "rev_xxx",
  "eventType": "analysis_started",
  "message": "python engine started analyzer state graph",
  "timestamp": "2026-04-03T13:00:01Z",
  "sequence": 2,
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

### 特征
- `timestamp` 由 backend 生成
- `sequence` 由 backend 保证单任务内递增
- SSE:
  - `id = sequence`
  - `event = eventType`
  - `data = ReviewEvent`

---

## 3. 顶层 envelope 约束

## 3.1 Internal Envelope
| 字段 | 必须 | 说明 |
|---|---:|---|
| `taskId` | 是 | 任务 ID |
| `eventType` | 是 | 事件名 |
| `message` | 是 | 简短描述 |
| `status` | 是 | `CREATED / RUNNING / COMPLETED / FAILED` |
| `payload` | 是 | 结构化 payload |

## 3.2 External Envelope
| 字段 | 必须 | 说明 |
|---|---:|---|
| `taskId` | 是 | 任务 ID |
| `eventType` | 是 | 事件名 |
| `message` | 是 | 简短描述 |
| `timestamp` | 是 | backend 生成 |
| `sequence` | 是 | backend 生成 |
| `status` | 是 | `CREATED / RUNNING / COMPLETED / FAILED` |
| `payload` | 是 | 结构化 payload |

---

## 4. payload 通用约束

## 4.1 必备键
除 terminal summary 之外，payload 推荐至少携带：

- `source`
- `stage`

### `source` 允许值
- `backend`
- `python-engine`
- `backend-mcp`

### `stage` 常见值
- `bootstrap_state`
- `input_validation`
- `ast`
- `symbol_graph`
- `semgrep`
- `analyzer_pipeline`
- `planner`
- `memory`
- `fixer`
- `verifier`
- `review`
- `finalize_result`
- `engine_error`
- `langgraph`
- `context_budget`
- `mcp`

---

## 4.2 调试字段规范
Day6 payload 可增量加入以下字段：

- `attempt_no`
- `target_stage`
- `retry_count`
- `retry_budget_left`
- `schema_version`
- `context_budget`
- `tool_trace`
- `selected_context`
- `repo_profile_summary`
- `graph_stats`

这些字段均为 optional，旧前端不应强依赖。

---

## 5. 当前稳定事件目录（Day5，Day6 必须保持）

## 5.1 Backend 事件

| eventType | emitter | status | payload 最少字段 | 说明 |
|---|---|---|---|---|
| `task_created` | backend | `CREATED` | `source`, `engine` | 任务创建成功 |
| `review_failed` | backend | `FAILED` | `source=backend`, `stage=engine_error`, `errorType`, `error` | Python engine 流程失败或未给 terminal event |

---

## 5.2 Bootstrap / Validation

| eventType | emitter | status | payload 最少字段 | 说明 |
|---|---|---|---|---|
| `analysis_started` | python-engine | `RUNNING` | `source`, `stage=bootstrap_state`, `language` | 评审流开始 |
| `review_failed` | python-engine | `FAILED` | `source`, `stage=input_validation`, `diagnostics` | 输入校验失败 |
| `review_failed` | python-engine | `FAILED` | `source`, `stage=state_graph`, `errorType`, `error`, `diagnostics` | state graph 级异常 |

---

## 5.3 Analyzer 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `ast_parsing_started` | `RUNNING` | `source`, `stage=ast`, `language` | AST 开始 |
| `ast_parsing_completed` | `RUNNING` | `source`, `stage=ast`, `classesCount`, `methodsCount`, `fieldsCount`, `importsCount`, `hasParseErrors`, `parseErrorsCount`, `syntaxIssuesCount` | AST 完成 |
| `symbol_graph_started` | `RUNNING` | `source`, `stage=symbol_graph` | Symbol Graph 开始 |
| `symbol_graph_completed` | `RUNNING` | `source`, `stage=symbol_graph`, `symbolsCount`, `callEdgesCount`, `variableRefsCount` | Symbol Graph 完成 |
| `semgrep_scan_started` | `RUNNING` | `source`, `stage=semgrep`, `ruleset` | Semgrep 开始 |
| `semgrep_scan_completed` | `RUNNING` | `source`, `stage=semgrep`, `ruleset`, `issuesCount`, `severityBreakdown` | Semgrep 完成 |
| `semgrep_scan_warning` | `RUNNING` | `source`, `stage=semgrep`, `ruleset`, `issuesCount`, `code`, `message` | Semgrep 警告但不中断主链 |
| `analyzer_completed` | `RUNNING` | `source`, `stage=analyzer_pipeline`, `analyzerSummary` | Analyzer 阶段完成 |

---

## 5.4 Planner 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `planner_started` | `RUNNING` | `source`, `stage=planner`, `inputIssueCount`, `inputSymbolCount` | Planner 开始 |
| `issue_graph_built` | `RUNNING` | `source`, `stage=planner`, `issue_graph`, `issueCount`, `edgeCount` | Issue Graph 构建完成 |
| `repair_plan_created` | `RUNNING` | `source`, `stage=planner`, `repair_plan`, `planCount` | Repair Plan 生成完成 |
| `planner_completed` | `RUNNING` | `source`, `stage=planner`, `issueCount`, `planCount`, `plannerSummary` | Planner 阶段完成 |

---

## 5.5 Memory 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `case_memory_search_started` | `RUNNING` | `source`, `stage=memory`, `attempt_no`, `issue_count`, `strategy_hints` | Case 检索开始 |
| `case_memory_matched` | `RUNNING` | `source`, `stage=memory`, `attempt_no`, `match_count`, `matches` | Case 命中 |
| `case_memory_completed` | `RUNNING` | `source`, `stage=memory`, `attempt_no`, `match_count` | Case 检索结束 |

---

## 5.6 Fixer 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `fixer_started` | `RUNNING` | `source`, `stage=fixer`, `attempt_no`, `plan_count`, `memory_match_count`, `retry_count` | Fixer 开始 |
| `patch_generated` | `RUNNING` | `source`, `stage=fixer`, `attempt_no`, `patch` | 补丁已生成 |
| `fixer_completed` | `RUNNING` | `source`, `stage=fixer`, `attempt_no`, `patch_id` | Fixer 正常结束 |
| `fixer_failed` | `RUNNING` | `source`, `stage=fixer`, `attempt_no`, `reason`, `failure_detail`, `retryable` | Fixer 未产出有效 patch |

---

## 5.7 Verifier 事件

### 5.7.1 Verifier 总事件
| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `verifier_started` | `RUNNING` | `source`, `stage=verifier`, `attempt_no`, `enabled_stages` | Verifier 开始 |
| `verifier_completed` | `RUNNING` | `source`, `stage=verifier`, `attempt_no`, `verification` | Verifier 通过 |
| `verifier_failed` | `RUNNING` | `source`, `stage=verifier`, `attempt_no`, `failed_stage`, `reason`, `retryable`, `retry_budget_left` | Verifier 失败 |

### 5.7.2 Stage 模板事件
对于 verifier stages，统一使用模板事件：

- `<stage>_started`
- `<stage>_completed`
- `<stage>_failed`

其中 `<stage>` 当前取值为：

- `patch_apply`
- `compile`
- `lint`
- `test`
- `security_rescan`

### Stage payload 统一结构
```json
{
  "source": "python-engine",
  "stage": "verifier",
  "attempt_no": 1,
  "target_stage": "compile",
  "status": "passed",
  "exit_code": 0,
  "stdout_summary": "",
  "stderr_summary": "",
  "reason": null,
  "retryable": false
}
```

### 规则
- `passed` -> 发 `<stage>_completed`
- `skipped` -> 也发 `<stage>_completed`，但 `payload.status="skipped"`
- `failed` -> 发 `<stage>_failed`

---

## 5.8 Retry 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `review_retry_scheduled` | `RUNNING` | `source`, `stage=review`, `attempt_no`, `next_attempt_no`, `failed_stage`, `failure_reason`, `retry_budget_left` | 决定重试 |
| `review_retry_started` | `RUNNING` | `source`, `stage=review`, `attempt_no`, `retry_count`, `max_retries` | 新一轮重试开始 |

---

## 5.9 Terminal 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `review_completed` | `COMPLETED` | `source`, `stage=finalize_result`, `engine`, `result`, `summary` | 任务成功收口 |
| `review_failed` | `FAILED` | 见上文不同来源 payload | 任务失败收口 |

---

## 6. Day6 新增事件（增量，不破坏现有事件）

Day6 重点是让 LangGraph / Memory / Context / MCP 可观测。  
因此新增事件必须遵循以下原则：

1. **只新增，不替换旧事件**
2. 旧前端看不懂也不影响主链
3. 新前端可用这些事件渲染 debug 与平台能力面板

---

## 6.1 LangGraph 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `langgraph_compiled` | `RUNNING` | `source`, `stage=langgraph`, `graph_name`, `nodes`, `entry_point` | 图编译完成 |
| `langgraph_node_started` | `RUNNING` | `source`, `stage=langgraph`, `node_name`, `attempt_no` | 节点开始 |
| `langgraph_node_completed` | `RUNNING` | `source`, `stage=langgraph`, `node_name`, `attempt_no`, `state_delta_keys` | 节点结束 |

### 约束
- 这些事件仅用于 debug / observability
- 不替代现有业务事件（如 `planner_started`）

---

## 6.2 Memory 增强事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `repo_memory_loaded` | `RUNNING` | `source`, `stage=memory`, `repo_profile_id`, `summary` | 仓库级记忆已加载 |
| `short_term_memory_updated` | `RUNNING` | `source`, `stage=memory`, `snapshot_type`, `summary` | 短期记忆快照更新 |
| `case_store_promoted` | `RUNNING` | `source`, `stage=memory`, `case_id`, `patch_id`, `verified_level` | verified patch 被沉淀为案例 |

### `snapshot_type` 推荐值
- `analyzer_evidence`
- `patch`
- `verifier_failure`
- `retry_context`
- `token_usage`

---

## 6.3 Context Budget 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `context_budget_initialized` | `RUNNING` | `source`, `stage=context_budget`, `context_budget` | 初始化预算 |
| `context_resource_loaded` | `RUNNING` | `source`, `stage=context_budget`, `source_item`, `context_budget` | 某个上下文资源已纳入预算 |
| `context_budget_updated` | `RUNNING` | `source`, `stage=context_budget`, `context_budget` | 预算快照更新 |
| `context_budget_exhausted` | `RUNNING` | `source`, `stage=context_budget`, `context_budget`, `reason` | 预算耗尽，后续停止扩上下文 |

### `source_item` 推荐结构
```json
{
  "source_id": "ctx-1",
  "kind": "snippet_window",
  "path": "snippet.java",
  "symbol": null,
  "token_count": 620,
  "reason": "issue vicinity"
}
```

---

## 6.4 MCP 事件

| eventType | status | payload 最少字段 | 说明 |
|---|---|---|---|
| `mcp_resource_requested` | `RUNNING` | `source=backend-mcp`, `stage=mcp`, `resource_name`, `request_id` | 请求资源 |
| `mcp_resource_completed` | `RUNNING` | `source=backend-mcp`, `stage=mcp`, `resource_name`, `request_id`, `ok`, `latency_ms` | 资源请求完成 |
| `mcp_tool_started` | `RUNNING` | `source=backend-mcp`, `stage=mcp`, `tool_name`, `request_id`, `selected_by` | 工具调用开始 |
| `mcp_tool_completed` | `RUNNING` | `source=backend-mcp`, `stage=mcp`, `tool_name`, `request_id`, `selected_by`, `ok`, `latency_ms` | 工具调用完成 |

### `selected_by` 推荐值
- `planner`
- `fixer`
- `verifier`
- `context_budget`

---

## 7. 关键 payload 片段定义

## 7.1 Patch payload
```json
{
  "patch_id": "patch_001",
  "attempt_no": 1,
  "status": "generated",
  "format": "unified_diff",
  "content": "diff --git ...",
  "explanation": "Applied null guard",
  "risk_level": "low",
  "target_files": ["snippet.java"],
  "strategy_used": "null_guard",
  "memory_case_ids": ["case-null-001"]
}
```

---

## 7.2 Attempt summary
```json
{
  "attempt_no": 1,
  "patch_id": "patch_001",
  "status": "generated",
  "verified_level": "L2",
  "failure_stage": null,
  "failed_stage": null,
  "failure_reason": null,
  "failure_detail": null,
  "memory_case_ids": ["case-null-001"]
}
```

---

## 7.3 Verification summary
```json
{
  "status": "passed",
  "verified_level": "L2",
  "passed_stages": ["patch_apply", "compile", "lint"],
  "failed_stage": null,
  "stages": [],
  "summary": "Verifier passed at L2"
}
```

---

## 7.4 review_completed payload
```json
{
  "source": "python-engine",
  "stage": "finalize_result",
  "engine": "python",
  "result": {},
  "summary": {},
  "analyzer": {},
  "analyzer_evidence": {},
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
- `review_completed` 必须继续包含当前 Day5 的 `result / summary / patch / verification` 块
- Day6 新增的 `context_budget / tool_trace / memory.short_term / memory.repo_profile` 均为 optional

---

## 8. 事件排序约束

## 8.1 通用顺序
同一任务内，外部 SSE 事件必须满足：

- `sequence` 严格递增
- terminal event 只能出现一次
- terminal event 之后必须关闭任务流

---

## 8.2 正常成功路径（示意）
```text
task_created
analysis_started
ast_parsing_started
ast_parsing_completed
symbol_graph_started
symbol_graph_completed
semgrep_scan_started
semgrep_scan_completed
analyzer_completed
planner_started
issue_graph_built
repair_plan_created
planner_completed
case_memory_search_started
case_memory_matched
case_memory_completed
fixer_started
patch_generated
fixer_completed
verifier_started
patch_apply_started
patch_apply_completed
compile_started
compile_completed
lint_started
lint_completed
verifier_completed
review_completed
```

---

## 8.3 零问题路径（示意）
```text
task_created
analysis_started
...
analyzer_completed
review_completed
```

### 说明
- 若 analyzer 后 `issues=[]`，允许直接收口
- 不需要强制经过 planner / fixer / verifier

---

## 8.4 重试路径（示意）
```text
...
fixer_started
patch_generated
fixer_completed
verifier_started
patch_apply_started
patch_apply_completed
compile_started
compile_failed
verifier_failed
review_retry_scheduled
review_retry_started
fixer_started
...
review_completed
```

---

## 9. 终止条件

## 9.1 成功终止
当出现：

- `review_completed` 且 `status=COMPLETED`

任务流结束。

## 9.2 失败终止
当出现：

- `review_failed` 且 `status=FAILED`

任务流结束。

## 9.3 禁止状态
以下情况不允许存在：

- 两个 terminal event
- terminal event 之后仍继续推 RUNNING 事件
- sequence 倒序
- 同一事件缺失 `payload`

---

## 10. 前端消费建议

## 10.1 用户态
优先展示：

- `message`
- `eventType`
- `summary`
- `patch`
- `verification`

## 10.2 Debug 态
额外展示：

- `payload` 原文
- `context_budget`
- `tool_trace`
- `langgraph_node_*`
- `repo_memory_loaded`
- `short_term_memory_updated`

## 10.3 聚合规则
- Issue Graph：取最新 `issue_graph_built` 或最终 `review_completed.result.issue_graph`
- Context Budget：取最新 `context_budget_updated`
- Verification：取最终 `review_completed.result.verification`
- Raw 诊断：取 `diagnostics`

---

## 11. Day6 实现要求摘要

实现 Day6 时必须保证：

1. 旧事件名不被替换  
2. 新事件只做 additive 扩展  
3. backend 继续负责 `timestamp / sequence`  
4. verifier stage 继续使用模板事件命名  
5. `review_completed` 继续作为最终权威结果 payload  
6. 旧前端即使不认识新事件，也不影响主链展示
