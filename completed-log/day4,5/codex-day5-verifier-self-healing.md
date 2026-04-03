# 给 Codex 的提示词：Sentinel-CR Day 5（Multi-stage Verifier + Self-healing Loop）

你正在 Sentinel-CR 仓库中继续 Day 5 开发。

## 一、任务背景

这个项目的目标不是停留在“发现问题”和“生成 patch”，而是要打通：

- Analyzer
- Issue Graph Planner
- Fixer
- Multi-stage Verifier
- Event Stream
- Benchmark

当前 Day 4 已经具备：

- `issues`
- `symbols`
- `context_summary`
- `issue_graph`
- `repair_plan`
- `memory_matches`
- `patch_artifact`
- Day 4 memory / fixer 事件

现在进入 Day 5。

Day 5 的目标不是继续优化 prompt 文案，而是把系统第一次真正做成“补丁必须先验证再交付”的样子。

也就是说，要把当前主链路升级为：

```text
Analyzer
-> Planner
-> Case Memory
-> Fixer
-> Patch Artifact
-> Verifier
-> Retry Loop
-> review_completed aggregate
```

## 二、你必须先阅读的文件

请先完整阅读以下文件，再开始改代码：

1. `README.md`
2. `PLAN.md`
3. `docs/api-contract.md`
4. `docs/architecture.md`
5. `docs/event-schema.md`
6. `completed-log/day4/` 与 `completed-log/day3/` 中的提示词和文档

你必须重点理解：

- Day 5 的核心是 **patch apply / compile / lint / test** 分阶段验证
- 失败后要进入 **reflection / retry loop**
- `review_completed.payload.result` 必须继续保留
- 最终结果必须包含 `verification`、`attempts`、`retry_count`、`verified_level`

## 三、当前硬约束（不要破坏）

1. 保持 Python 内部入口路由不变：
   - `/internal/reviews/run`
2. 不要破坏 Day 4 已有 patch 生成通路
3. `review_completed.payload.result` 必须继续保留
4. 新增字段优先做兼容扩展，不要做破坏性重构
5. 前端和测试会依赖这些新增事件：
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
   - `verifier_completed`
   - `verifier_failed`
   - `review_retry_scheduled`
   - `review_retry_started`
6. Day 5 第一版允许 `security_rescan` 为可选或 `skipped`，但接口要预留

如果你发现现有代码和文档略有出入，遵循以下优先级：

> 现有可运行主链路 > Day 4 兼容性 > Day 5 文档契约 > 代码风格优化

## 四、本次开发目标

请你完成 Day 5 的最小可用实现，使系统从：

```text
Analyzer -> Planner -> Case Memory -> Fixer -> Patch Artifact
```

升级为：

```text
Analyzer -> Planner -> Case Memory -> Fixer -> Verifier -> Retry Loop -> Verified Result
```

注意：

- Day 5 的“完成”标准不是所有验证工具都很完整，而是至少打通：
  - patch apply
  - compile
  - fail -> retry
- 最终必须能够回答：
  - 第几轮成功/失败
  - 失败在哪个阶段
  - 当前补丁的 verified level 是多少

## 五、建议优先修改的文件

请优先检查并按需修改这些文件（文件名可能存在或部分存在）：

### Python AI Engine

- `ai-engine-python/tools/patch_apply.py`
- `ai-engine-python/tools/sandbox_env.py`
- `ai-engine-python/tools/test_runner.py`
- `ai-engine-python/agents/verifier_agent.py`
- `ai-engine-python/core/state_graph.py`
- `ai-engine-python/core/schemas.py`
- `ai-engine-python/core/events.py`
- `ai-engine-python/agents/reporter_agent.py`
- `ai-engine-python/main.py`

### 测试

- `ai-engine-python/tests/`
- 新增或补充 `test_acceptance_day5.py`

### 前端（仅在确实需要时）

- 与 verifier / retry 事件展示相关的类型映射
- 不要做大规模 UI 重构

## 六、Day 5 必须实现的能力

### 1. 实现 patch apply 工具

请在 `tools/patch_apply.py` 中实现最小 patch apply 能力，要求：

- 能把原代码与 patch 写入临时目录
- 能尝试应用 unified diff
- 能结构化返回结果，例如：

```json
{
  "stage": "patch_apply",
  "status": "passed",
  "exit_code": 0,
  "stdout_summary": "patch applied",
  "stderr_summary": ""
}
```

失败时至少返回：

- `stage`
- `status = failed`
- `reason` 或 `stderr_summary`
- `retryable`

优先保证行为稳定，不要求一开始支持复杂多文件大 patch。

### 2. 实现 sandbox 执行能力

请在 `tools/sandbox_env.py` 中实现最小隔离执行能力，至少支持：

- 创建临时工作目录
- 在目录中写入补丁后代码
- 执行 `javac` 或其他最小编译命令
- 返回 `stdout_summary` / `stderr_summary` / `exit_code`

要求：

- 不要把整个原始长日志直接塞进 message
- 结构化返回阶段结果

### 3. 实现最小 test runner

请在 `tools/test_runner.py` 中实现最小测试执行器：

- 可以先支持占位命令或简化测试执行
- 若当前场景没有测试，也应显式返回 `skipped`
- 结果结构应和 compile/lint 阶段统一

例如：

```json
{
  "stage": "test",
  "status": "skipped",
  "reason": "no test command configured"
}
```

### 4. 实现 Verifier Agent

请在 `agents/verifier_agent.py` 中实现多阶段验证流程，顺序至少为：

1. `patch_apply`
2. `compile`
3. `lint`（可占位或跳过）
4. `test`（可占位或跳过）
5. `security_rescan`（可选预留）

输出必须是结构化 `verification_result`，至少包括：

- `status`
- `verified_level`
- `passed_stages`
- `failed_stage`
- `stages`
- `summary`

推荐等级：

- `L0`: patch 已生成但未通过验证
- `L1`: patch apply + compile 通过
- `L2`: patch apply + compile + lint 通过
- `L3`: patch apply + compile + lint + test 通过
- `L4`: 再加 security rescan 通过

### 5. 把 verifier 接入状态机

请在 `core/state_graph.py` 中把 Day 5 新增状态接上，至少补齐：

- `verification_result`
- `attempts`
- `retry_count`
- `max_retries`
- `final_status`

建议顺序：

```text
analyzer -> planner -> case_memory -> fixer -> verifier
    -> success => reporter
    -> failed and retryable => fixer
    -> failed and not retryable => reporter
```

### 6. 实现 Self-healing / Retry Loop

请实现最小自愈重试机制：

- 读取 `options.max_retries`
- verifier 失败后若 `retryable = true` 且预算未耗尽，则进入下一轮
- 下一轮 Fixer 至少能拿到上一轮失败摘要
- 每轮都要记录 `attempt_record`

失败摘要至少应包含：

- `failed_stage`
- `reason` 或 `stderr_summary`
- `retry_budget_left`
- `last_patch_id`

### 7. 新增 Day 5 事件

通过 `core/events.py` 或现有事件构造逻辑，新增 verifier / retry 事件，要求：

- 事件必须符合 `docs/event-schema.md`
- `payload` 必须结构化
- 每轮失败必须能从事件序列里看出来

最少要支持：

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
- `verifier_completed`
- `verifier_failed`
- `review_retry_scheduled`
- `review_retry_started`

### 8. 扩展最终聚合结果

请在 `reporter_agent.py` 或最终聚合逻辑中，使 `review_completed.payload.result` 至少新增：

- `verification`
- `attempts`
- `summary.retry_count`
- `summary.attempt_count`
- `summary.verified_level`
- `summary.final_outcome`

并在顶层镜像字段中同步：

- `verification`
- `attempts`
- `summary`

推荐 `summary.final_outcome`：

- `verified_patch`
- `patch_generated_unverified`
- `failed_after_retries`
- `failed_no_patch`

## 七、实现细节建议

### Verification 阶段策略

第一版不要过度追求完整工具链，优先保证：

- 阶段拆分清楚
- 结构化结果清楚
- 事件发得清楚
- retry 能跑起来

### Lint / Test 的第一版要求

- `lint` 和 `test` 可以先轻量实现
- 如果暂时无法执行，也要显式返回 `skipped`
- 不要因为暂时没有完整 lint/test 环境就阻塞整个 Day 5

### Retry 策略

建议：

- 默认最多重试 2 次
- 只有 verifier 失败且 `retryable` 才重试
- patch 生成失败是否重试，可根据你现有代码决定，但必须结构化记录

### Attempt 记录

每轮 attempt 至少记录：

```json
{
  "attempt_no": 1,
  "patch_id": "patch_attempt_1",
  "status": "failed",
  "memory_case_ids": ["case-null-guard-001"],
  "failed_stage": "compile",
  "failure_reason": "cannot find symbol UserDTO",
  "verified_level": "L0"
}
```

## 八、测试要求

至少补充一个 Day 5 验收测试，断言：

1. 主链路运行后能拿到 `verification_result`
2. 成功场景至少能到 `L1`（patch apply + compile）
3. 失败场景能发出 `compile_failed` 或其他 verifier 失败事件
4. 可重试失败场景能发出 `review_retry_scheduled`
5. `review_completed.payload.result.verification` 存在
6. `review_completed.payload.result.attempts` 存在
7. 兼容字段 `review_completed.payload.result` 仍保留

如果你能方便构造一个 compile fail 再 retry 成功的小样例，会更好。

## 九、不要做的事情

1. 不要改掉 `/internal/reviews/run`
2. 不要删除 Day 4 的 `memory` / `patch` 字段
3. 不要把验证结论只写在 `message`
4. 不要把 stderr 原文整段塞进最终 summary
5. 不要为了“更优雅”大改整个状态图
6. 不要把 Day 5 依赖建立在重型外部基础设施上

## 十、你完成后需要给出的交付说明

请在完成代码后，按下面格式回复：

### 1. Changed files

列出所有修改文件。

### 2. What was implemented

说明你完成了哪些 Day 5 能力。

### 3. Contract check

逐项说明是否满足：

- `verification_result` 已接入
- `attempts` / `retry_count` 已接入
- verifier / retry 事件已发出
- `review_completed.payload.result` 保留
- 顶层镜像字段已扩展

### 4. Acceptance notes

说明你建议如何验证 Day 5 是否跑通。

### 5. Risks / follow-ups

说明遗留风险与 Day 6 接口预留情况。

## 十一、一句话要求

请你实现 **最小但真实可跑的 Day 5 Verification 闭环**：

> 在不破坏 Day 4 的前提下，把 patch artifact 送入多阶段 verifier，并能在失败时进行结构化重试，最终输出带 verified level 和 attempts 的结果。
