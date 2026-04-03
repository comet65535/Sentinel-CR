# Sentinel-CR API Contract（Day 4 / Day 5）

## 1. 文档目的

本文件定义 Sentinel-CR 在 Day 4（Fixer Agent + Case-based Memory）与 Day 5（Multi-stage Verifier + Self-healing Loop）阶段的统一接口约定，覆盖：

1. 前端 ↔ Java Backend 的外部 API
2. Java Backend ↔ Python AI Engine 的内部 API
3. Day 4 新增的 `memory_matches`、`patch_artifact` 数据契约
4. Day 5 新增的 `verification`、`attempts`、`retry_history` 数据契约
5. `review_completed` 聚合结果的兼容性规则

本文件的目标不是一次性定义未来全部能力，而是把 Day 3 已经固定下来的 Analyzer / Planner 契约继续向后扩展到：

> Analyzer → Issue Graph → Repair Plan → Case Memory → Patch Artifact → Verification Result → Retry Loop → Final Result

这样 Day 4/5 的实现就不会出现“补丁是字符串、验证结果是自然语言、前端靠 message 猜状态”的失控情况。

***

## 2. 设计原则

### 2.1 兼容优先

- Python 内部入口 `/internal/reviews/run` 保持不变。
- Day 4/5 只做向后兼容扩展，不做破坏性改名。
- `review_completed.payload.result` 必须继续保留。

### 2.2 契约先行

- Patch、Memory、Verification、Retry 都必须是结构化 JSON。
- 不允许把关键结果只放在 `message` 中。
- 事件流与最终结果对象必须共享同一套字段语义。

### 2.3 分层明确

- Analyzer：发现问题与结构化证据
- Planner：组织问题图与修复计划
- Memory：检索结构化经验案例
- Fixer：生成 Unified Diff Patch
- Verifier：执行 patch apply / compile / lint / test / rescan
- Reporter：聚合最终结果并输出兼容对象

### 2.4 状态可恢复

- 每一轮尝试都必须有独立 attempt 记录。
- 每次失败都必须记录失败阶段、失败摘要、是否进入重试。
- 最终结果必须能回答“第几轮成功/失败、失败在哪一步、通过了哪些阶段”。

***

## 3. 名词约定

### 3.1 Review

一次完整的代码审查/修复任务。

### 3.2 Attempt

一次从 Fixer 开始、到 Verifier 结束的独立补丁尝试。

### 3.3 Memory Match

从 `case_memory` 命中的结构化修复案例。

### 3.4 Patch Artifact

Fixer 产出的结构化补丁对象，而不只是单纯 patch 字符串。

### 3.5 Verification Result

Verifier 对补丁执行多阶段验证后得到的结构化结论。

***

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
    "max_retries": 2,
    "enable_verifier": true,
    "enable_security_rescan": false
  },
  "metadata": {
    "client_request_id": "req-001",
    "repo_name": null,
    "pr_url": null,
    "branch": null
  }
}
```

#### 字段说明

- `source_type`: Day 4/5 主路径仍固定为 `inline_code`
  - 预留值：`pr_diff`、`repo_file`
- `language`: 当前建议固定为 `java`
- `code_text`: 待分析代码
- `options.debug`: 是否填充调试字段
- `options.max_retries`: Day 5 默认建议 `2`
- `options.enable_verifier`: 是否执行验证链路
- `options.enable_security_rescan`: 第一版可选，默认 `false`
- `metadata`: 透传扩展信息，不影响主链路契约

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

***

## 4.2 订阅事件流

### `GET /api/reviews/{reviewId}/events`

#### Response

- `Content-Type: text/event-stream`
- 每条 SSE `data:` 对应一条标准 Event Envelope

#### 说明

- Java Backend 负责把 Python 返回的 NDJSON 转为 SSE 推送给前端。
- Java 不得改写事件的字段语义，只允许做传输层封装。
- 前端 Timeline 与 Debug Panel 必须消费同一条事件对象。

***

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
    "memory_match_count": 1,
    "attempt_count": 1,
    "retry_count": 0,
    "verified_level": "L2",
    "final_outcome": "verified_patch"
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
  "memory": {
    "matches": []
  },
  "patch": {
    "patch_id": "patch_attempt_1",
    "format": "unified_diff",
    "content": "diff --git a/... b/...",
    "explanation": "使用 null guard 避免空指针",
    "risk_level": "medium",
    "target_files": ["src/main/java/UserService.java"]
  },
  "verification": {
    "verified_level": "L2",
    "passed_stages": ["patch_apply", "compile", "lint"],
    "failed_stage": null,
    "status": "passed"
  },
  "attempts": [
    {
      "attempt_no": 1,
      "patch_id": "patch_attempt_1",
      "status": "passed",
      "failed_stage": null,
      "verified_level": "L2"
    }
  ],
  "result": {
    "summary": {},
    "analyzer": {},
    "issue_graph": {},
    "repair_plan": [],
    "memory": {},
    "patch": {},
    "verification": {},
    "attempts": []
  },
  "created_at": "2026-04-02T15:00:00Z",
  "completed_at": "2026-04-02T15:00:06Z"
}
```

#### 说明

- 顶层字段用于新前端 / 新测试直接消费。
- `result` 作为兼容镜像字段继续保留。
- 若 Day 4 仅完成 Patch 生成而未启用 Verifier，则 `verification` 可为 `null`。
- 若 Day 5 失败耗尽重试次数，则 `status` 可为 `failed`，但 `attempts` 仍必须完整返回。

***

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
    "max_retries": 2,
    "enable_verifier": true,
    "enable_security_rescan": false
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
- `code_text`：当前 Day 4/5 主路径必填
- `options.max_retries`：Python 侧负责消费并决定是否进入自愈重试
- `metadata`：仅透传，不影响主逻辑契约

***

## 5.2 内部流式响应

### Response

- `Content-Type: application/x-ndjson`
- 每行一条 JSON Event Envelope

#### 示例

```json
{"task_id":"rev_20260402_001","event_type":"patch_generated","stage":"fixer","status":"completed","message":"补丁生成完成","timestamp":"2026-04-02T15:00:03Z","payload":{"patch_id":"patch_attempt_1","risk_level":"medium"}}
```

***

## 6. 标准 Event Envelope

所有事件必须遵循统一包裹结构：

```json
{
  "task_id": "rev_20260402_001",
  "event_id": "evt_0011",
  "seq": 11,
  "event_type": "compile_completed",
  "stage": "verifier",
  "status": "completed",
  "message": "编译验证通过",
  "timestamp": "2026-04-02T15:00:04Z",
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
- `debug`

### 字段约定

- `event_type`: 稳定枚举，供前端与测试判断
- `stage`: `review` / `analyzer` / `planner` / `memory` / `fixer` / `verifier` / `reporter`
- `status`: `started` / `completed` / `failed` / `retrying`
- `payload`: 机器消费字段
- `debug`: 仅在 debug 模式下补充上下文，不可承载关键业务字段

***

## 7. Day 4 / Day 5 新增核心数据契约

## 7.1 MemoryMatch

```json
{
  "case_id": "case-null-guard-001",
  "pattern": "null_pointer_guard",
  "score": 0.91,
  "trigger_signals": ["nullable repository result", "method return dereference"],
  "strategy": "null_guard",
  "risk_note": "may change returned empty behavior",
  "success_rate": 0.87
}
```

### 字段说明

- `case_id`: 案例唯一 ID
- `pattern`: 结构化案例模式名
- `score`: 当前命中分数，范围建议 `0 ~ 1`
- `trigger_signals`: 命中信号
- `strategy`: 建议补丁策略
- `risk_note`: 风险提示
- `success_rate`: 历史成功率

## 7.2 PatchArtifact

```json
{
  "patch_id": "patch_attempt_1",
  "attempt_no": 1,
  "format": "unified_diff",
  "content": "diff --git a/src/... b/src/...\n...",
  "explanation": "在 findById 结果上增加 Optional 判空保护",
  "risk_level": "medium",
  "target_files": ["src/main/java/UserService.java"],
  "strategy_used": "null_guard",
  "memory_case_ids": ["case-null-guard-001"]
}
```

### 约束

- `format` 当前固定为 `unified_diff`
- `content` 必须为可应用的 patch 文本
- `target_files` 不能为空
- `memory_case_ids` 可以为空，但字段建议始终保留

## 7.3 VerificationStageResult

```json
{
  "stage": "compile",
  "status": "passed",
  "exit_code": 0,
  "stdout_summary": "mvn compile succeeded",
  "stderr_summary": "",
  "started_at": "2026-04-02T15:00:04Z",
  "completed_at": "2026-04-02T15:00:05Z"
}
```

## 7.4 VerificationResult

```json
{
  "status": "passed",
  "verified_level": "L3",
  "passed_stages": ["patch_apply", "compile", "lint", "test"],
  "failed_stage": null,
  "stages": [],
  "summary": "补丁应用、编译、lint、测试均通过"
}
```

### 约束

- `verified_level` 推荐枚举：`L0` / `L1` / `L2` / `L3` / `L4`
- `L0`: patch 生成但未验证
- `L1`: patch apply + compile 通过
- `L2`: patch apply + compile + lint 通过
- `L3`: patch apply + compile + lint + test 通过
- `L4`: 上述全部通过且 security rescan 通过

## 7.5 AttemptRecord

```json
{
  "attempt_no": 2,
  "patch_id": "patch_attempt_2",
  "status": "failed",
  "memory_case_ids": ["case-sql-parameterized-002"],
  "failed_stage": "compile",
  "failure_reason": "cannot find symbol queryBuilder",
  "verified_level": "L0",
  "started_at": "2026-04-02T15:00:03Z",
  "completed_at": "2026-04-02T15:00:05Z"
}
```

***

## 8. 最终聚合结果规则

## 8.1 Day 4 最低要求

若只完成 Fixer + Case Memory，则 `review_completed.payload.result` 至少包含：

- `summary`
- `analyzer`
- `issue_graph`
- `repair_plan`
- `memory.matches`
- `patch`

此时：

- `verification` 可为 `null`
- `attempts` 至少包含一轮 patch 生成记录
- `summary.final_outcome` 可为 `patch_generated`

## 8.2 Day 5 最低要求

若启用 Verifier + Retry Loop，则 `review_completed.payload.result` 还必须包含：

- `verification`
- `attempts`
- `retry_count`
- `summary.final_outcome`

`summary.final_outcome` 推荐值：

- `verified_patch`
- `patch_generated_unverified`
- `failed_after_retries`
- `failed_no_patch`

***

## 9. 失败与重试契约

## 9.1 失败事件最小字段

任一失败事件的 `payload` 至少应包含：

```json
{
  "attempt_no": 1,
  "failed_stage": "compile",
  "reason": "cannot find symbol UserDTO",
  "retryable": true,
  "retry_budget_left": 1
}
```

## 9.2 重试调度事件

进入下一轮之前，必须发送 `review_retry_scheduled` 事件：

```json
{
  "attempt_no": 1,
  "next_attempt_no": 2,
  "failed_stage": "compile",
  "failure_reason": "cannot find symbol UserDTO",
  "retry_budget_left": 1
}
```

## 9.3 终止条件

满足任一条件时，Review 结束：

1. 达到最大验证等级目标并通过
2. `max_retries` 用尽
3. 补丁无法生成且不可恢复
4. 发生不可重试基础设施错误

***

## 10. 兼容性要求

### 10.1 必须保留

- `POST /internal/reviews/run`
- NDJSON 内部流式返回
- `review_completed.payload.result`
- Day 3 的 `issue_graph` 与 `repair_plan` 字段命名

### 10.2 可新增但不可替代

- 可在顶层新增 `memory` / `patch` / `verification` / `attempts`
- 不能删除旧字段后只保留新字段
- 不能要求前端从 `message` 里解析 patch/验证结论

### 10.3 空值策略

- 未执行的阶段应返回 `null` 或空数组，而不是缺失关键字段
- 推荐始终保留对象骨架，降低前端分支判断复杂度

***

## 11. 非目标

以下能力不在 Day 4/5 契约强制范围内：

- PR 级输入主链路
- Repo-level Memory
- Lazy Context 扩展策略
- 多文件大型 patch 合并策略
- CodeQL 强制集成

这些能力会在 Day 6 及之后再扩展，不应阻塞当前 Day 4/5 的最小闭环。
