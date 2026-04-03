# 给 Codex 的提示词：Sentinel-CR Day 4（Fixer Agent + Case-based Memory）

你正在 Sentinel-CR 仓库中继续 Day 4 开发。

## 一、任务背景

这个项目不是普通 AI Code Review Demo，而是要打通一条工程主链路：

- Analyzer
- Issue Graph Planner
- Fixer
- Multi-stage Verifier
- Event Stream
- Benchmark

当前 Day 3 数据通路已经完成，系统已经能输出：

- `issues`
- `symbols`
- `context_summary`
- `issue_graph`
- `repair_plan`
- Day 3 planner 事件

现在进入 Day 4。

Day 4 的目标不是继续扩 analyzer/planner，而是把系统从“知道先修什么”推进到“能生成结构化补丁”。

也就是说，要把当前主链路升级为：

```text
issues + symbols + context_summary
-> issue_graph
-> repair_plan
-> memory_matches
-> patch_artifact
-> review_completed aggregate
```

## 二、你必须先阅读的文件

请先完整阅读以下文件，再开始改代码：

1. `README.md`
2. `PLAN.md`
3. `docs/api-contract.md`
4. `docs/architecture.md`
5. `docs/event-schema.md`
6. `completed-log/` 目录下已有提示词，尤其是 `completed-log/day3/`

你必须重点理解：

- Day 4 不是写“建议文本”，而是输出 **Unified Diff Patch**
- 必须引入 **Case-based Memory**，而不是只靠模型现编
- 事件流需要新增 memory / fixer 相关事件
- `review_completed.payload.result` 必须继续保留

## 三、当前硬约束（不要破坏）

1. 保持 Python 内部入口路由不变：
   - `/internal/reviews/run`
2. 不要破坏 Day 3 已有数据通路
3. `review_completed.payload.result` 必须继续保留
4. 新增字段优先做兼容扩展，不要做破坏性重构
5. 事件名必须稳定，前端和测试会依赖这些新增事件：
   - `case_memory_search_started`
   - `case_memory_matched`
   - `case_memory_completed`
   - `fixer_started`
   - `patch_generated`
   - `fixer_completed`
   - `fixer_failed`
6. Day 4 可以不做真正 verifier 闭环，但要给 Day 5 留好状态位和字段接口

如果你发现现有代码和文档略有出入，遵循以下优先级：

> 现有可运行主链路 > Day 3 兼容性 > Day 4 文档契约 > 代码风格优化

## 四、本次开发目标

请你完成 Day 4 的最小可用实现，使系统从：

```text
Analyzer -> Planner
```

升级为：

```text
Analyzer -> Planner -> Case Memory -> Fixer -> Patch Artifact -> Aggregated Result
```

注意：

- Day 4 的“完成”标准不是 UI 更炫，而是至少一种常见问题能生成结构化 unified diff
- `memory_matches` 和 `patch_artifact` 必须能被最终结果对象和事件流消费
- 输出必须可被 Day 5 Verifier 继续接上

## 五、建议优先修改的文件

请优先检查并按需修改这些文件（文件名可能存在或部分存在）：

### Python AI Engine

- `ai-engine-python/memory/case_memory.py`
- `ai-engine-python/agents/fixer_agent.py`
- `ai-engine-python/prompts/fixer_prompt.py`
- `ai-engine-python/core/state_graph.py`
- `ai-engine-python/core/schemas.py`
- `ai-engine-python/core/events.py`
- `ai-engine-python/agents/reporter_agent.py`
- `ai-engine-python/main.py`

### 测试

- `ai-engine-python/tests/`
- 新增或补充 `test_acceptance_day4.py`

### 前端（仅在确实需要时）

- 与新增事件展示相关的类型映射
- 不要做大规模 UI 重构

## 六、Day 4 必须实现的能力

### 1. 实现最小 Case-based Memory

请在 `memory/case_memory.py` 中实现最小版本结构化案例库，至少包含 5 条左右典型案例，优先这些模式：

- 空指针修复
- SQL 参数化
- try-with-resources
- 异常日志补全
- N+1 查询改批量查询（可先占位）

每条案例至少包含：

- `case_id`
- `pattern`
- `trigger_signals`
- `before_code`
- `after_code`
- `diff`
- `risk_note`
- `success_rate`
- `strategy`

可以先使用内存静态列表，不要求完整向量库。

### 2. 实现案例检索函数

至少提供一个稳定的检索接口，例如：

```python
def retrieve_case_matches(issues, repair_plan, symbols, context_summary, top_k=3) -> list[dict]:
    ...
```

要求：

- 根据 `issue.type` / `strategy_hint` / `related_symbols` 做简单匹配
- 返回稳定的结构化 `memory_matches`
- 如果没有命中，也返回空数组，不要抛异常

### 3. 实现 Fixer Agent

请在 `agents/fixer_agent.py` 中实现 Day 4 的最小 Fixer，输入至少包括：

- `repair_plan`
- analyzer evidence
- `memory_matches`
- `attempt_no`

输出必须是结构化 `patch_artifact`，至少包括：

- `patch_id`
- `attempt_no`
- `format`
- `content`
- `explanation`
- `risk_level`
- `target_files`
- `strategy_used`
- `memory_case_ids`

要求：

- `format` 固定为 `unified_diff`
- `content` 必须真的是 diff 文本，不要只返回自然语言建议
- 若无有效 patch，必须进入 `fixer_failed` 路径

### 4. 实现 Fixer Prompt 约束

在 `prompts/fixer_prompt.py` 中明确提示模型：

- 输入是 `repair_plan + analyzer evidence + memory_matches`
- 输出必须是统一 JSON 对象
- JSON 中必须包含 `patch`、`explanation`、`risk_level`
- `patch` 必须是 unified diff
- 不允许只输出 markdown 建议或散文式说明

建议输出格式：

```json
{
  "patch": "diff --git a/... b/...\n...",
  "explanation": "...",
  "risk_level": "medium"
}
```

### 5. 将 memory / patch 接入状态机

请在 `core/state_graph.py` 中把 Day 4 新增状态接上，最少补齐：

- `memory_matches`
- `patch_artifact`
- `attempts`

建议顺序：

```text
analyzer -> planner -> case_memory -> fixer -> reporter
```

### 6. 新增 Day 4 事件

通过 `core/events.py` 或现有事件构造逻辑，新增这些事件：

- `case_memory_search_started`
- `case_memory_matched`
- `case_memory_completed`
- `fixer_started`
- `patch_generated`
- `fixer_completed`
- `fixer_failed`

要求：

- 事件必须符合 `docs/event-schema.md`
- `payload` 必须结构化
- `message` 只做简短描述，不能承载唯一业务语义

### 7. 扩展最终聚合结果

请在 `reporter_agent.py` 或最终聚合逻辑中，使 `review_completed.payload.result` 至少新增：

- `memory.matches`
- `patch`
- `attempts`

并在顶层镜像字段中同步：

- `memory`
- `patch`
- `attempts`
- `summary.memory_match_count`
- `summary.final_outcome`

其中：

- Day 4 没有 verifier 时，`summary.final_outcome` 可为 `patch_generated`
- `verification` 可暂为 `null`

## 七、实现细节建议

### Patch 生成策略

第一版不要过度追求全能。

建议优先做：

- 单文件 patch
- 单 issue / 少量 issue 合并 patch
- 常见 Java 问题模式

### Memory 使用策略

若命中高相似案例：

- 优先做 patch adaptation
- 尽量复用案例策略名和风险提示

若未命中：

- 允许降级到纯 LLM 生成
- 但结果结构必须一致

### Attempt 记录

即使 Day 4 尚未做 retry，也建议先产出最小 attempt 记录：

```json
{
  "attempt_no": 1,
  "patch_id": "patch_attempt_1",
  "status": "generated",
  "failed_stage": null,
  "verified_level": "L0"
}
```

这样 Day 5 直接复用。

## 八、测试要求

至少补充一个 Day 4 验收测试，断言：

1. 主链路运行后能拿到 `memory_matches`
2. 能产生 `patch_artifact`
3. 能发出 `patch_generated` 事件
4. `review_completed.payload.result.patch` 存在
5. `review_completed.payload.result.memory.matches` 存在
6. 兼容字段 `review_completed.payload.result` 仍保留

如果仓库已有 Day 3 验收测试风格，请尽量沿用。

## 九、不要做的事情

1. 不要改掉 `/internal/reviews/run`
2. 不要删除 Day 3 的字段或事件
3. 不要把 patch 只写在 `message`
4. 不要把关键结果只放在 `debug`
5. 不要为了“优雅重构”大改整个状态图
6. 不要引入沉重基础设施（如必须依赖数据库/向量库）才让 Day 4 可运行

## 十、你完成后需要给出的交付说明

请在完成代码后，按下面格式回复：

### 1. Changed files

列出所有修改文件。

### 2. What was implemented

说明你完成了哪些 Day 4 能力。

### 3. Contract check

逐项说明是否满足：

- `memory_matches` 已接入
- `patch_artifact` 已接入
- 新事件已发出
- `review_completed.payload.result` 保留
- 顶层镜像字段已扩展

### 4. Acceptance notes

说明你建议如何验证 Day 4 是否跑通。

### 5. Risks / follow-ups

说明遗留风险与 Day 5 接口预留情况。

## 十一、一句话要求

请你实现 **最小但真实可跑的 Day 4 Fixer 闭环**：

> 在不破坏 Day 3 的前提下，把 repair plan 变成结构化 patch artifact，并把 case memory、patch、事件、最终结果全部接通。
