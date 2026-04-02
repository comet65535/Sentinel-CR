# Sentinel-CR API Contract

## 1. 文档目的

本文件定义 Sentinel-CR 在 **Day 3（Issue Graph Planner）** 阶段的统一接口约定，覆盖：

1. 前端 ↔ Java Backend 的外部 API
2. Java Backend ↔ Python AI Engine 的内部 API
3. Review 结果对象与兼容性规则
4. Day 3 新增的 `issue_graph` 与 `repair_plan` 数据契约

本文档的目标不是补充所有未来能力，而是先把 **Day 2 已打通的数据通路** 与 **Day 3 需要新增的 Planner 数据结构** 固定下来，避免后续实现出现“字段名、事件名、传输格式各写各的”的情况。

---

## 2. 设计原则

### 2.1 稳定优先
- **内部 Python 入口 `/internal/reviews/run` 保持不变**。
- Day 3 只在返回流与最终结果对象上扩展字段，不改变既有调用方式。

### 2.2 契约先行
- 事件流、最终结果、分析器输出、Planner 输出都必须是**结构化 JSON**。
- 不允许把关键结果仅放在自然语言 message 中。

### 2.3 兼容 Day 2
- `review_completed.payload.result` 继续保留，作为兼容字段。
- 同时允许在顶层镜像关键结果字段，便于前端与测试直接消费。

### 2.4 分层清晰
- Analyzer 负责“发现候选问题与结构化证据”。
- Planner 负责“组织问题图与修复计划”。
- Fixer / Verifier 暂可为空壳或占位，但接口名称应预留。

---

## 3. 名词约定

### 3.1 Review
一次完整的代码审查/修复任务。

### 3.2 Event
Review 执行过程中的一条结构化事件。

### 3.3 Analyzer Output
Day 2 已完成的分析结果，至少包括：
- `issues`
- `symbols`
- `context_summary`

### 3.4 Issue Graph
Day 3 新增的数据对象，用于表达问题之间的依赖、冲突、修复范围与测试需求。

### 3.5 Repair Plan
Day 3 新增的有序修复计划，是对 `issue_graph` 的执行视图。

---

## 4. 外部 API（Frontend ↔ Java Backend）

> 外部 API 以 Java Backend 为唯一入口。前端不直接调用 Python AI Engine。

## 4.1 创建 Review

### `POST /api/reviews`

#### Request
```json
{
  "source_type": "inline_code",
  "language": "java",
  "code_text": "public class UserService { ... }",
  "options": {
    "debug": true,
    "max_retries": 0
  },
  "metadata": {
    "client_request_id": "req-001",
    "repo_name": null,
    "pr_url": null
  }
}
```

#### 字段说明
- `source_type`: 当前 Day 3 主路径固定为 `inline_code`。
  - 预留值：`pr_diff`、`repo_file`
- `language`: 当前建议固定为 `java`
- `code_text`: 待分析代码
- `options.debug`: 是否返回调试信息
- `options.max_retries`: Day 3 可先固定 `0`
- `metadata`: 前端透传的扩展信息

#### Response
```json
{
  "review_id": "rev_20260402_001",
  "status": "accepted",
  "events_url": "/api/reviews/rev_20260402_001/events",
  "result_url": "/api/reviews/rev_20260402_001",
  "created_at": "2026-04-02T15:00:00Z"
}
```

---

## 4.2 订阅事件流

### `GET /api/reviews/{reviewId}/events`

#### Response
- `Content-Type: text/event-stream`
- 每条 SSE `data:` 对应一条标准 Event Envelope

#### 说明
- Java Backend 负责把 Python 返回的 NDJSON 转为 SSE 推送给前端
- Event 的 JSON 结构必须保持不变，传输层可以变化

---

## 4.3 查询最终结果

### `GET /api/reviews/{reviewId}`

#### Response
```json
{
  "review_id": "rev_20260402_001",
  "status": "completed",
  "summary": {
    "issue_count": 2,
    "repair_plan_count": 2,
    "verified_level": null,
    "retry_count": 0
  },
  "analyzer": {
    "issues": [],
    "symbols": [],
    "context_summary": {}
  },
  "issue_graph": {
    "nodes": [],
    "edges": []
  },
  "repair_plan": [],
  "result": {
    "summary": {},
    "analyzer": {},
    "issue_graph": {},
    "repair_plan": []
  },
  "created_at": "2026-04-02T15:00:00Z",
  "completed_at": "2026-04-02T15:00:03Z"
}
```

#### 说明
- `result` 用于兼容旧前端 / 旧测试
- 顶层镜像字段用于新前端 / 新测试

---

## 5. 内部 API（Java Backend ↔ Python AI Engine）

## 5.1 启动内部 Review

### `POST /internal/reviews/run`

#### Request
```json
{
  "task_id": "rev_20260402_001",
  "language": "java",
  "code_text": "public class UserService { ... }",
  "options": {
    "debug": true,
    "max_retries": 0
  },
  "metadata": {
    "source_type": "inline_code",
    "repo_name": null,
    "pr_url": null,
    "client_request_id": "req-001"
  }
}
```

#### 字段要求
- `task_id`：由 Java Backend 生成并全链路透传
- `code_text`：当前 Day 3 主路径必填
- `metadata`：只做透传，不应影响主逻辑正确性

---

## 5.2 内部流式响应

### Response
- `Content-Type: application/x-ndjson`
- 每行一条 JSON Event Envelope

#### 示例
```json
{"task_id":"rev_20260402_001","event_type":"planner_started","message":"开始构建问题图","timestamp":"2026-04-02T15:00:01Z","payload":{}}
```

---

## 6. 标准 Event Envelope

所有事件必须遵循统一包裹结构。

```json
{
  "task_id": "rev_20260402_001",
  "event_id": "evt_0007",
  "seq": 7,
  "event_type": "issue_graph_built",
  "stage": "planner",
  "status": "completed",
  "message": "问题图构建完成",
  "timestamp": "2026-04-02T15:00:02Z",
  "payload": {},
  "debug": {}
}
```

### 必填字段
- `task_id`
- `event_type`
- `message`
- `timestamp`

### 强烈建议字段
- `event_id`
- `seq`
- `stage`
- `status`
- `payload`

### 字段约定
- `event_type`: 稳定枚举，供前端与测试判断
- `stage`: 如 `analyzer` / `planner` / `fixer` / `verifier`
- `status`: `started` / `completed` / `failed`
- `payload`: 机器消费字段
- `debug`: 仅在 debug 模式下扩展

---

## 7. Day 2 Analyzer Output Contract

```json
{
  "issues": [
    {
      "issue_id": "ISSUE-1",
      "issue_type": "null_pointer",
      "severity": "medium",
      "line": 42,
      "message": "Potential null dereference",
      "rule_id": "java.lang.null-deref",
      "file_path": "UserService.java",
      "symbol_hints": ["getUser"]
    }
  ],
  "symbols": [
    {
      "symbol_id": "SYM-1",
      "symbol_type": "method",
      "name": "getUser",
      "class_name": "UserService",
      "signature": "User getUser(String id)",
      "line_start": 30,
      "line_end": 58,
      "called_symbols": ["userRepo.findById"]
    }
  ],
  "context_summary": {
    "classes": ["UserService"],
    "methods": ["getUser"],
    "imports": ["java.util.Optional"],
    "language": "java"
  }
}
```

### 要求
- `issues` 是 Planner 的主输入
- `symbols` 用于补充影响范围、关联符号与修复边界
- `context_summary` 用于前端展示与 Prompt 压缩

---

## 8. Day 3 Issue Graph Contract

## 8.1 Issue Graph Node

```json
{
  "issue_id": "ISSUE-1",
  "type": "null_pointer",
  "severity": "medium",
  "location": {
    "file_path": "UserService.java",
    "line": 42
  },
  "related_symbols": ["getUser", "userRepo.findById"],
  "depends_on": [],
  "conflicts_with": [],
  "fix_scope": "single_file",
  "requires_context": false,
  "requires_test": false,
  "strategy_hint": "null_guard"
}
```

### 字段说明
- `depends_on`: 必须先完成的 issue_id 列表
- `conflicts_with`: 不能在同一 patch 中直接合并的 issue_id 列表
- `fix_scope`: `single_file` / `multi_file` / `unknown`
- `requires_context`: 是否需要额外上下文
- `requires_test`: 是否建议进入测试验证
- `strategy_hint`: 给 Fixer 的修复策略提示

---

## 8.2 Issue Graph Edge

```json
{
  "from_issue_id": "ISSUE-2",
  "to_issue_id": "ISSUE-1",
  "relation": "depends_on"
}
```

### `relation` 枚举
- `depends_on`
- `conflicts_with`
- `same_scope`
- `same_symbol`

---

## 8.3 Issue Graph Root Object

```json
{
  "nodes": [
    {
      "issue_id": "ISSUE-1",
      "type": "null_pointer",
      "severity": "medium",
      "location": {"file_path": "UserService.java", "line": 42},
      "related_symbols": ["getUser"],
      "depends_on": [],
      "conflicts_with": [],
      "fix_scope": "single_file",
      "requires_context": false,
      "requires_test": false,
      "strategy_hint": "null_guard"
    }
  ],
  "edges": []
}
```

---

## 9. Day 3 Repair Plan Contract

```json
[
  {
    "issue_id": "ISSUE-2",
    "priority": 1,
    "strategy": "parameterized_query",
    "patch_group": "PATCH-1",
    "fix_scope": "single_file",
    "requires_context": false,
    "requires_test": true,
    "blocked_by": []
  },
  {
    "issue_id": "ISSUE-1",
    "priority": 2,
    "strategy": "null_guard",
    "patch_group": "PATCH-2",
    "fix_scope": "single_file",
    "requires_context": false,
    "requires_test": false,
    "blocked_by": []
  }
]
```

### 字段说明
- `priority`: 数字越小越优先
- `patch_group`: 同组问题可在一个 patch 中处理
- `blocked_by`: 当前计划项的前置 issue_id

---

## 10. 关键事件的 payload 约定

## 10.1 `analyzer_completed`
```json
{
  "issues": [],
  "symbols": [],
  "context_summary": {}
}
```

## 10.2 `issue_graph_built`
```json
{
  "issue_graph": {
    "nodes": [],
    "edges": []
  },
  "issue_count": 2,
  "edge_count": 1
}
```

## 10.3 `repair_plan_created`
```json
{
  "repair_plan": [],
  "plan_count": 2
}
```

## 10.4 `review_completed`
```json
{
  "result": {
    "summary": {
      "issue_count": 2,
      "repair_plan_count": 2,
      "retry_count": 0,
      "verified_level": null
    },
    "analyzer": {
      "issues": [],
      "symbols": [],
      "context_summary": {}
    },
    "issue_graph": {
      "nodes": [],
      "edges": []
    },
    "repair_plan": []
  },
  "summary": {
    "issue_count": 2,
    "repair_plan_count": 2,
    "retry_count": 0,
    "verified_level": null
  },
  "analyzer": {
    "issues": [],
    "symbols": [],
    "context_summary": {}
  },
  "issue_graph": {
    "nodes": [],
    "edges": []
  },
  "repair_plan": []
}
```

### 兼容规则
- `payload.result` **必须保留**
- 顶层镜像字段推荐至少保留：
  - `summary`
  - `analyzer`
  - `issue_graph`
  - `repair_plan`

---

## 11. 状态枚举

### Review Status
- `accepted`
- `running`
- `completed`
- `failed`

### Event Status
- `started`
- `completed`
- `failed`

### Fix Scope
- `single_file`
- `multi_file`
- `unknown`

### Severity
- `low`
- `medium`
- `high`
- `critical`

---

## 12. 错误契约

## 12.1 同步接口错误

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "code_text is required",
    "details": {}
  }
}
```

## 12.2 流式错误事件

```json
{
  "task_id": "rev_20260402_001",
  "event_type": "review_failed",
  "stage": "planner",
  "status": "failed",
  "message": "问题图构建失败",
  "timestamp": "2026-04-02T15:00:02Z",
  "payload": {
    "error_code": "PLANNER_BUILD_FAILED",
    "error_message": "issue id missing",
    "retryable": false
  }
}
```

---

## 13. Day 3 实施要求（必须满足）

1. `/internal/reviews/run` 不改路由名
2. `review_completed.payload.result` 不移除
3. 新增事件：
   - `issue_graph_built`
   - `repair_plan_created`
4. 最终结果必须能同时被：
   - 事件流前端
   - API 结果页
   - 自动化测试
   - 后续 Fixer/Verifier
   直接消费
5. `issue_graph` 与 `repair_plan` 必须是结构化字段，不得只写在 message 中

---

## 14. 非目标

以下内容不是 Day 3 必须完成项：
- 真实 patch 生成
- compile/lint/test 验证
- repo-level memory 持久化
- PR 级入口正式可用

但接口命名与结果对象需要为这些能力预留演进空间。
