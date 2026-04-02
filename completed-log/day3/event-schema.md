# Sentinel-CR Event Schema（Day 3）

## 1. 文档目标

本文件定义 Sentinel-CR 在 Day 3 阶段的统一事件协议，解决以下问题：

1. Python 发出的事件格式必须固定
2. Java 转发为 SSE 时不能改 payload 语义
3. 前端事件轴与 Debug Panel 必须消费同一份结构化数据
4. 自动化测试必须能根据 `event_type` 和 `payload` 做断言

计划中明确要求从 Day 1 起就统一事件 JSON 协议，后续所有模块都按这个协议发事件，以避免 UI 层反复重构。Day 3 只是把 Planner 相关事件补充进来。fileciteturn0file0

---

## 2. 传输层与对象层分离

### 2.1 内部传输层
- Python → Java：`application/x-ndjson`
- 一行一条 JSON Event

### 2.2 前端传输层
- Java → Frontend：`text/event-stream`
- 每条 SSE `data:` 包含一条 JSON Event

### 2.3 对象层
无论走 NDJSON 还是 SSE，**事件 JSON 本体完全一致**。

---

## 3. 标准 Event Envelope

```json
{
  "task_id": "rev_20260402_001",
  "event_id": "evt_0003",
  "seq": 3,
  "event_type": "ast_parsed",
  "stage": "analyzer",
  "status": "completed",
  "message": "AST 解析完成",
  "timestamp": "2026-04-02T15:00:01Z",
  "payload": {},
  "debug": {}
}
```

---

## 4. 字段定义

| 字段 | 是否必填 | 类型 | 说明 |
|---|---|---:|---|
| `task_id` | 是 | string | 当前 review 任务 ID |
| `event_id` | 否但推荐 | string | 事件唯一 ID |
| `seq` | 否但推荐 | integer | 单任务内递增序号 |
| `event_type` | 是 | string | 稳定事件类型枚举 |
| `stage` | 否但推荐 | string | 所属阶段 |
| `status` | 否但推荐 | string | started/completed/failed |
| `message` | 是 | string | 面向用户的简短描述 |
| `timestamp` | 是 | string | ISO-8601 UTC 时间 |
| `payload` | 否但推荐 | object | 机器消费的结构化数据 |
| `debug` | 否 | object | 调试附加信息 |

---

## 5. 字段约束

## 5.1 `task_id`
- 全链路一致
- Java Backend 创建，Python 透传

## 5.2 `event_type`
- 必须稳定、可枚举、可被测试断言
- 不允许把业务语义只写在 `message`

## 5.3 `message`
- 给用户看的短句
- 不能替代结构化 payload

## 5.4 `payload`
- 优先放给前端、测试、后续 Agent 消费的数据
- 必须是对象，不要混用字符串与数组顶层

## 5.5 `debug`
- 只在 debug 模式下填充额外信息
- 不能依赖 debug 才能拿到关键业务字段

---

## 6. Stage 枚举

### 当前推荐值
- `review`
- `analyzer`
- `planner`
- `fixer`
- `verifier`
- `reporter`

### Day 3 实际会用到
- `review`
- `analyzer`
- `planner`

---

## 7. Status 枚举

- `started`
- `completed`
- `failed`

说明：
- 如果某事件只表示结果，也可以固定使用 `completed`
- 建议所有主阶段同时发送 started 和 completed 事件

---

## 8. Event Type 总表（Day 3）

| event_type | stage | status | 含义 |
|---|---|---|---|
| `review_started` | review | started | 任务开始执行 |
| `analyzer_started` | analyzer | started | 分析阶段开始 |
| `ast_parsed` | analyzer | completed | AST 解析完成 |
| `symbols_extracted` | analyzer | completed | 符号提取完成 |
| `semgrep_completed` | analyzer | completed | Semgrep 扫描完成 |
| `analyzer_completed` | analyzer | completed | Day 2 分析结果汇总完成 |
| `planner_started` | planner | started | Day 3 问题图构建开始 |
| `issue_graph_built` | planner | completed | 问题图构建完成 |
| `repair_plan_created` | planner | completed | 修复计划已生成 |
| `planner_completed` | planner | completed | Planner 阶段完成 |
| `review_completed` | review | completed | 任务完成 |
| `review_failed` | review | failed | 任务失败 |

根据 Day 3 计划，前端事件轴必须至少新增 `issue_graph_built` 和 `repair_plan_created`。fileciteturn0file0

---

## 9. 各事件 payload 规范

## 9.1 `review_started`

```json
{
  "source_type": "inline_code",
  "language": "java"
}
```

---

## 9.2 `ast_parsed`

```json
{
  "class_count": 1,
  "method_count": 3,
  "classes": ["UserService"],
  "methods": ["getUser", "saveUser", "deleteUser"]
}
```

### 说明
- 给前端 timeline 做简要展示
- 详细 AST 不强制出现在此事件中

---

## 9.3 `symbols_extracted`

```json
{
  "symbol_count": 4,
  "symbols": [
    {
      "symbol_id": "SYM-1",
      "symbol_type": "method",
      "name": "getUser",
      "class_name": "UserService",
      "line_start": 30,
      "line_end": 58,
      "called_symbols": ["userRepo.findById"]
    }
  ]
}
```

---

## 9.4 `semgrep_completed`

```json
{
  "issue_count": 2,
  "issues": [
    {
      "issue_id": "ISSUE-1",
      "issue_type": "null_pointer",
      "severity": "medium",
      "line": 42,
      "message": "Potential null dereference",
      "rule_id": "java.lang.null-deref",
      "file_path": "UserService.java"
    }
  ]
}
```

---

## 9.5 `analyzer_completed`

```json
{
  "issues": [],
  "symbols": [],
  "context_summary": {
    "classes": ["UserService"],
    "methods": ["getUser"],
    "imports": ["java.util.Optional"],
    "language": "java"
  }
}
```

### 说明
- 这是 Day 2 的标准汇总事件
- Day 3 Planner 必须以它作为主输入之一

---

## 9.6 `planner_started`

```json
{
  "input_issue_count": 2,
  "input_symbol_count": 4
}
```

---

## 9.7 `issue_graph_built`

```json
{
  "issue_graph": {
    "nodes": [
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
    ],
    "edges": []
  },
  "issue_count": 1,
  "edge_count": 0
}
```

### 说明
- `issue_graph` 必须是完整结构化对象
- `issue_count` 和 `edge_count` 用于 timeline 与测试快速断言

---

## 9.8 `repair_plan_created`

```json
{
  "repair_plan": [
    {
      "issue_id": "ISSUE-1",
      "priority": 1,
      "strategy": "null_guard",
      "patch_group": "PATCH-1",
      "fix_scope": "single_file",
      "requires_context": false,
      "requires_test": false,
      "blocked_by": []
    }
  ],
  "plan_count": 1
}
```

### 说明
- 这是给 Day 4 Fixer 的直接输入
- `plan_count` 便于前端直接展示“已生成 N 条修复计划”

---

## 9.9 `planner_completed`

```json
{
  "issue_count": 2,
  "plan_count": 2,
  "has_blocked_items": false
}
```

---

## 9.10 `review_completed`

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

### 兼容规则（非常重要）
- `payload.result` 必须保留，兼容旧前端/旧测试
- 顶层镜像字段也必须有，方便新前端直接读取
- `review_completed` 是 Day 2 / Day 3 的统一收口事件

---

## 9.11 `review_failed`

```json
{
  "error_code": "PLANNER_BUILD_FAILED",
  "error_message": "issue id missing",
  "failed_stage": "planner",
  "retryable": false
}
```

---

## 10. Debug 字段建议

### 可选结构

```json
{
  "raw_issue_ids": ["ISSUE-1", "ISSUE-2"],
  "grouping_reason": [
    "ISSUE-1 and ISSUE-2 touch same symbol getUser",
    "ISSUE-2 requires_test because severity=high and strategy=parameterized_query"
  ]
}
```

### 原则
- Debug 信息用于解释 Planner 行为
- 不能替代正式 payload
- 前端 Debug Panel 可以完整展示，但普通时间轴不应依赖它

README 也明确区分了用户模式与调试模式：普通用户看关键状态，调试模式看分析器结果、上下文选择、重试与失败原因。fileciteturn0file1

---

## 11. 事件顺序约束

单个任务内推荐顺序如下：

1. `review_started`
2. `analyzer_started`
3. `ast_parsed`
4. `symbols_extracted`
5. `semgrep_completed`
6. `analyzer_completed`
7. `planner_started`
8. `issue_graph_built`
9. `repair_plan_created`
10. `planner_completed`
11. `review_completed`

### 约束
- `issue_graph_built` 不得早于 `analyzer_completed`
- `repair_plan_created` 不得早于 `issue_graph_built`
- `review_completed` 必须是成功路径的最后一条业务事件
- 失败时允许 `review_failed` 取代 `review_completed`

---

## 12. 幂等与重复事件处理

### 12.1 `seq`
- 同一 `task_id` 内严格递增
- 前端可用它做排序

### 12.2 重复消费
如果 Java 或前端重复收到同一事件，可按以下 key 去重：
- `(task_id, event_id)` 优先
- 若无 `event_id`，则回退 `(task_id, seq)`

---

## 13. 前端消费建议

## 13.1 Timeline
取字段：
- `event_type`
- `message`
- `timestamp`
- `status`

## 13.2 Debug Panel
重点展示：
- `analyzer_completed.payload`
- `issue_graph_built.payload.issue_graph`
- `repair_plan_created.payload.repair_plan`
- `review_failed.payload`

## 13.3 最终结果页
优先读取：
- `review_completed.payload.summary`
- `review_completed.payload.analyzer`
- `review_completed.payload.issue_graph`
- `review_completed.payload.repair_plan`

若前端仍依赖旧结构，则回退读取 `review_completed.payload.result`

---

## 14. Day 3 验收断言建议

自动化测试至少应断言：

1. 事件流中存在 `issue_graph_built`
2. 事件流中存在 `repair_plan_created`
3. `issue_graph_built.payload.issue_graph.nodes` 为数组
4. `repair_plan_created.payload.repair_plan` 为数组
5. `review_completed.payload.result.issue_graph` 存在
6. `review_completed.payload.result.repair_plan` 存在
7. `review_completed.payload.issue_graph` 顶层镜像存在
8. `review_completed.payload.repair_plan` 顶层镜像存在

---

## 15. 一句话总结

Day 3 的事件协议核心不是“多发两条消息”，而是：

> **让 Planner 的输入、过程、结果都能被前端、测试和后续 Agent 稳定消费。**
