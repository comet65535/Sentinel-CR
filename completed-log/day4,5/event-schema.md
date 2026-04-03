# Sentinel-CR Event Schema（Day 4 / Day 5）

## 1. 文档目标

本文件定义 Sentinel-CR 在 Day 4（Fixer Agent + Case-based Memory）与 Day 5（Multi-stage Verifier + Self-healing Loop）阶段的统一事件协议，解决以下问题：

1. Python 发出的事件格式必须固定
2. Java 转发为 SSE 时不能改 payload 语义
3. Timeline、Diff Viewer、Debug Panel 必须消费同一份结构化数据
4. 自动化测试必须能根据 `event_type`、`stage`、`payload` 做断言
5. Day 5 的 retry 与 verification 过程必须能被事件完整回放

Day 4/5 的新增重点不是重新发明事件系统，而是在 Day 3 事件框架上继续补充：

- memory 相关事件
- fixer 相关事件
- verifier 相关事件
- retry 相关事件
- 最终聚合事件中的 patch / verification / attempts 数据

***

## 2. 传输层与对象层分离

### 2.1 内部传输层

- Python → Java：`application/x-ndjson`
- 一行一条 JSON Event

### 2.2 前端传输层

- Java → Frontend：`text/event-stream`
- 每条 SSE `data:` 包含一条 JSON Event

### 2.3 对象层

无论走 NDJSON 还是 SSE，事件 JSON 本体必须完全一致。

***

## 3. 标准 Event Envelope

```json
{
  "task_id": "rev_20260402_001",
  "event_id": "evt_0009",
  "seq": 9,
  "event_type": "patch_generated",
  "stage": "fixer",
  "status": "completed",
  "message": "补丁生成完成",
  "timestamp": "2026-04-02T15:00:03Z",
  "payload": {},
  "debug": {}
}
```

***

## 4. 字段定义

| 字段 | 是否必填 | 类型 | 说明 |
|---|---|---|---|
| `task_id` | 是 | string | 当前 review 任务 ID |
| `event_id` | 否但推荐 | string | 事件唯一 ID |
| `seq` | 否但推荐 | integer | 单任务内递增序号 |
| `event_type` | 是 | string | 稳定事件类型枚举 |
| `stage` | 否但推荐 | string | 所属阶段 |
| `status` | 否但推荐 | string | `started/completed/failed/retrying/skipped` |
| `message` | 是 | string | 面向用户的简短描述 |
| `timestamp` | 是 | string | ISO-8601 UTC 时间 |
| `payload` | 否但推荐 | object | 机器消费的结构化数据 |
| `debug` | 否 | object | 调试附加信息 |

***

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

- 必须为对象
- 优先放给前端、测试、后续 Agent 消费的数据
- 不要混用字符串、数组作为顶层 payload

## 5.5 `debug`

- 只在 debug 模式下填充额外信息
- 不能依赖 debug 才能拿到关键业务字段

***

## 6. Stage 枚举

### 当前推荐值

- `review`
- `analyzer`
- `planner`
- `memory`
- `fixer`
- `verifier`
- `reporter`

### Day 4/5 实际会用到

- `review`
- `analyzer`
- `planner`
- `memory`
- `fixer`
- `verifier`
- `reporter`

***

## 7. Status 枚举

推荐值：

- `started`
- `completed`
- `failed`
- `retrying`
- `skipped`

说明：

- `started`: 当前阶段开始
- `completed`: 当前阶段完成
- `failed`: 当前阶段失败
- `retrying`: 当前 review 进入下一轮尝试
- `skipped`: 当前阶段被显式跳过（如未启用 test / security rescan）

***

## 8. 事件分组总览

## 8.1 Review 级事件

- `review_accepted`
- `review_started`
- `review_retry_scheduled`
- `review_retry_started`
- `review_completed`
- `review_failed`

## 8.2 Analyzer 级事件

- `analyzer_started`
- `ast_parsed`
- `symbol_graph_built`
- `semgrep_completed`
- `analyzer_completed`

## 8.3 Planner 级事件

- `planner_started`
- `issue_graph_built`
- `repair_plan_created`
- `planner_completed`

## 8.4 Memory 级事件（Day 4 新增）

- `case_memory_search_started`
- `case_memory_matched`
- `case_memory_completed`

## 8.5 Fixer 级事件（Day 4 新增）

- `fixer_started`
- `patch_generated`
- `fixer_completed`
- `fixer_failed`

## 8.6 Verifier 级事件（Day 5 新增）

- `verifier_started`
- `patch_apply_started`
- `patch_apply_completed`
- `patch_apply_failed`
- `compile_started`
- `compile_completed`
- `compile_failed`
- `lint_started`
- `lint_completed`
- `lint_failed`
- `test_started`
- `test_completed`
- `test_failed`
- `security_rescan_started`
- `security_rescan_completed`
- `security_rescan_failed`
- `verifier_completed`
- `verifier_failed`

***

## 9. 标准 payload 片段

## 9.1 review_accepted

```json
{
  "review_id": "rev_20260402_001",
  "source_type": "inline_code",
  "language": "java"
}
```

## 9.2 issue_graph_built

```json
{
  "node_count": 2,
  "edge_count": 1,
  "issue_ids": ["ISSUE-1", "ISSUE-2"]
}
```

## 9.3 repair_plan_created

```json
{
  "plan_count": 2,
  "strategies": ["parameterized_query", "null_guard"]
}
```

## 9.4 case_memory_matched

```json
{
  "match_count": 2,
  "matches": [
    {
      "case_id": "case-null-guard-001",
      "pattern": "null_pointer_guard",
      "score": 0.91,
      "strategy": "null_guard"
    }
  ]
}
```

## 9.5 patch_generated

```json
{
  "attempt_no": 1,
  "patch_id": "patch_attempt_1",
  "format": "unified_diff",
  "target_files": ["src/main/java/UserService.java"],
  "risk_level": "medium",
  "strategy_used": "null_guard",
  "memory_case_ids": ["case-null-guard-001"]
}
```

## 9.6 compile_completed

```json
{
  "attempt_no": 1,
  "stage": "compile",
  "exit_code": 0,
  "verified_level_after_stage": "L1",
  "stdout_summary": "javac succeeded",
  "stderr_summary": ""
}
```

## 9.7 compile_failed

```json
{
  "attempt_no": 1,
  "stage": "compile",
  "exit_code": 1,
  "reason": "cannot find symbol UserDTO",
  "retryable": true,
  "retry_budget_left": 1
}
```

## 9.8 review_retry_scheduled

```json
{
  "attempt_no": 1,
  "next_attempt_no": 2,
  "failed_stage": "compile",
  "failure_reason": "cannot find symbol UserDTO",
  "retry_budget_left": 1
}
```

## 9.9 review_completed

```json
{
  "summary": {
    "issue_count": 2,
    "repair_plan_count": 2,
    "memory_match_count": 1,
    "attempt_count": 1,
    "retry_count": 0,
    "verified_level": "L2",
    "final_outcome": "verified_patch"
  },
  "result": {
    "analyzer": {},
    "issue_graph": {},
    "repair_plan": [],
    "memory": {},
    "patch": {},
    "verification": {},
    "attempts": []
  }
}
```

***

## 10. 逐类事件定义

## 10.1 Review 级事件

### `review_accepted`

- `stage`: `review`
- `status`: `completed`
- 语义：任务已被系统接收

### `review_started`

- `stage`: `review`
- `status`: `started`
- 语义：Python 主流程正式开始执行

### `review_retry_scheduled`

- `stage`: `review`
- `status`: `retrying`
- 语义：上一轮失败后，系统决定进入下一轮

### `review_retry_started`

- `stage`: `review`
- `status`: `started`
- 语义：新一轮 attempt 已开始

### `review_completed`

- `stage`: `reporter`
- `status`: `completed`
- 语义：任务成功结束，可能是 patch_generated 或 verified_patch

### `review_failed`

- `stage`: `reporter`
- `status`: `failed`
- 语义：任务失败结束，通常是耗尽重试或不可恢复错误

***

## 10.2 Memory 级事件

### `case_memory_search_started`

- `stage`: `memory`
- `status`: `started`
- 语义：开始在案例库中检索匹配项

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "issue_count": 2,
  "strategy_hints": ["null_guard", "parameterized_query"]
}
```

### `case_memory_matched`

- `stage`: `memory`
- `status`: `completed`
- 语义：找到一批候选案例

### `case_memory_completed`

- `stage`: `memory`
- `status`: `completed`
- 语义：案例检索阶段结束，可进入 Fixer

***

## 10.3 Fixer 级事件

### `fixer_started`

- `stage`: `fixer`
- `status`: `started`
- 语义：开始生成 patch

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "plan_count": 2,
  "memory_match_count": 1
}
```

### `patch_generated`

- `stage`: `fixer`
- `status`: `completed`
- 语义：成功生成结构化补丁

### `fixer_completed`

- `stage`: `fixer`
- `status`: `completed`
- 语义：Fixer 阶段结束

### `fixer_failed`

- `stage`: `fixer`
- `status`: `failed`
- 语义：无法生成有效补丁

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "reason": "model output missing unified diff",
  "retryable": false
}
```

***

## 10.4 Verifier 级事件

### `verifier_started`

- `stage`: `verifier`
- `status`: `started`
- 语义：开始执行验证链路

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "enabled_stages": ["patch_apply", "compile", "lint", "test"]
}
```

### `patch_apply_started` / `patch_apply_completed` / `patch_apply_failed`

- 语义：补丁应用阶段
- 成功时应给出 `target_files`
- 失败时应给出 `reason` / `retryable`

### `compile_started` / `compile_completed` / `compile_failed`

- 语义：编译阶段
- 成功时应给出 `verified_level_after_stage`
- 失败时应给出 `reason` / `exit_code`

### `lint_started` / `lint_completed` / `lint_failed`

- 语义：lint 阶段
- 若未启用，可使用 `skipped`

### `test_started` / `test_completed` / `test_failed`

- 语义：测试阶段
- 若无测试场景，可使用 `skipped`

### `security_rescan_started` / `security_rescan_completed` / `security_rescan_failed`

- 语义：安全复扫阶段
- Day 5 第一版允许缺省或 `skipped`

### `verifier_completed`

- `stage`: `verifier`
- `status`: `completed`
- 语义：当前轮次验证阶段结束

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "verified_level": "L2",
  "passed_stages": ["patch_apply", "compile", "lint"],
  "failed_stage": null,
  "status": "passed"
}
```

### `verifier_failed`

- `stage`: `verifier`
- `status`: `failed`
- 语义：当前轮次在验证阶段结束且未通过

#### payload 最小字段

```json
{
  "attempt_no": 1,
  "verified_level": "L0",
  "failed_stage": "compile",
  "reason": "cannot find symbol UserDTO",
  "retryable": true,
  "retry_budget_left": 1
}
```

***

## 11. Debug 字段建议

`debug` 只在 `options.debug = true` 时填充，推荐内容：

### 11.1 Memory 阶段

```json
{
  "retrieval_keywords": ["null pointer", "Optional", "repository result"],
  "top_case_ids": ["case-null-guard-001", "case-null-check-004"]
}
```

### 11.2 Fixer 阶段

```json
{
  "issue_ids": ["ISSUE-1"],
  "strategy_hint": "null_guard",
  "prompt_mode": "patch_adaptation"
}
```

### 11.3 Verifier 阶段

```json
{
  "workdir": "/tmp/sentinel/rev_001/attempt_1",
  "command": "javac UserService.java"
}
```

注意：

- `debug` 不能成为唯一业务真相来源
- 不要把完整大段日志直接塞进 `message`
- 若日志较长，应提供 `stdout_summary` / `stderr_summary`

***

## 12. 最小成功事件序列

一个最小成功闭环建议出现如下事件序列：

1. `review_accepted`
2. `review_started`
3. `analyzer_started`
4. `ast_parsed`
5. `symbol_graph_built`
6. `semgrep_completed`
7. `analyzer_completed`
8. `planner_started`
9. `issue_graph_built`
10. `repair_plan_created`
11. `planner_completed`
12. `case_memory_search_started`
13. `case_memory_matched`
14. `case_memory_completed`
15. `fixer_started`
16. `patch_generated`
17. `fixer_completed`
18. `verifier_started`
19. `patch_apply_completed`
20. `compile_completed`
21. `lint_completed`（可选）
22. `test_completed`（可选）
23. `verifier_completed`
24. `review_completed`

***

## 13. 最小失败重试事件序列

一个典型失败重试链路建议出现：

1. `fixer_started`
2. `patch_generated`
3. `verifier_started`
4. `patch_apply_completed`
5. `compile_failed`
6. `verifier_failed`
7. `review_retry_scheduled`
8. `review_retry_started`
9. `fixer_started`
10. `patch_generated`
11. `verifier_started`
12. `compile_completed`
13. `verifier_completed`
14. `review_completed`

***

## 14. 测试断言建议

自动化测试至少应断言：

- `event_type` 是否出现
- `seq` 是否递增
- `task_id` 是否一致
- `patch_generated.payload.patch_id` 是否存在
- `verifier_completed.payload.verified_level` 是否存在
- 失败场景下是否出现 `review_retry_scheduled`
- `review_completed.payload.result` 是否包含 `patch` / `verification` / `attempts`

***

## 15. 兼容性要求

### 必须保留

- Day 3 的 Event Envelope 结构
- Day 3 的 planner 事件名：
  - `issue_graph_built`
  - `repair_plan_created`
- `review_completed` 作为最终结束事件

### 可新增但不可破坏

- 新增 memory / fixer / verifier / retry 事件
- 新增 payload 字段
- 新增 `stage = memory`

### 不允许的做法

- 把 Day 5 的验证结果只写进 `message`
- 把 patch 文本只写进 debug
- 为了前端方便临时重命名旧事件

***

## 16. 一句话总结

Day 4/5 的事件协议必须让系统做到两件事：

1. 前端能清楚看到“现在做到哪一步了”
2. 测试和开发者能准确回答“哪一轮、哪一阶段、为什么失败/成功”

只有这样，Sentinel-CR 的 Patch-first 和 Verification-first 才是可观测、可迭代、可工程化的。
