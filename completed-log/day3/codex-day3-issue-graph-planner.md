# 给 Codex 的提示词：Sentinel-CR Day 3（Issue Graph Planner）

你正在 Sentinel-CR 仓库中继续 Day 3 开发。

## 一、任务背景

这个项目不是普通 AI Code Review Demo，而是要走一条工程主链路：

- Analyzer
- Issue Graph Planner
- Fixer
- Multi-stage Verifier
- Event Stream
- Benchmark

当前 **Day 2 数据通路已经完成**。现在要进入 **Day 3：Issue Graph Planner**。

Day 3 的目标不是加花哨功能，而是把 Day 2 的 analyzer 输出升级为：

- `issue_graph`
- `repair_plan`
- 新增 planner 事件
- 最终 `review_completed` 聚合结果扩展

## 二、你必须先阅读的文件

请先完整阅读以下文件，再开始改代码：

1. `README.md`
2. `PLAN.md`
3. `docs/api-contract.md`
4. `docs/architecture.md`
5. `docs/event-schema.md`
6. `completed-log/` 目录下已有提示词（如果存在）

其中你要特别理解：
- Day 2 analyzer 已经输出什么
- Day 3 planner 要新增什么
- 事件流 contract 怎么定义
- 最终结果对象如何兼容旧结构

## 三、当前硬约束（不要破坏）

1. **保持 Python 内部入口路由不变：**
   - `/internal/reviews/run`
2. **不要破坏 Day 2 已有数据通路**
3. **`review_completed.payload.result` 必须继续保留**
4. **新增字段时优先做“兼容扩展”，不要做破坏性重构**
5. 前端和测试都将依赖新增事件：
   - `issue_graph_built`
   - `repair_plan_created`

如果你发现现有代码和文档略有出入，遵循以下优先级：

> **现有可运行主链路 > Day 2 兼容性 > Day 3 文档契约 > 代码风格优化**

也就是说：
- 先保证链路不坏
- 再补齐 Day 3 能力
- 不要为了“更优雅”去打断现有入口或前端读取方式

## 四、本次开发目标

请你完成 Day 3 的最小可用实现，使系统从：

```text
issues + symbols + context_summary
```

升级为：

```text
issues + symbols + context_summary
-> issue_graph
-> repair_plan
-> planner events
-> review_completed aggregate
```

## 五、建议优先修改的文件

请优先检查并按需修改这些文件（文件名可能存在或部分存在）：

### Python AI Engine
- `ai-engine-python/core/issue_graph.py`
- `ai-engine-python/agents/planner_agent.py`
- `ai-engine-python/core/state_graph.py`
- `ai-engine-python/core/schemas.py`
- `ai-engine-python/core/events.py`
- `ai-engine-python/agents/reporter_agent.py`
- `ai-engine-python/main.py`

### 测试
- `ai-engine-python/tests/`
- 新增或补充 `test_acceptance_day3.py`

### 前端（仅在确实需要时）
- 与事件展示相关的类型或映射
- 但不要做大规模 UI 重构

## 六、Day 3 必须实现的能力

### 1. 统一 Issue Graph 数据结构

请在 `issue_graph.py` 中实现或补齐：

- `IssueNode`
- `IssueEdge`
- `IssueGraph`
- `RepairPlanItem`

至少支持以下字段：

#### IssueNode
- `issue_id`
- `type`
- `severity`
- `location`
- `related_symbols`
- `depends_on`
- `conflicts_with`
- `fix_scope`
- `requires_context`
- `requires_test`
- `strategy_hint`

#### RepairPlanItem
- `issue_id`
- `priority`
- `strategy`
- `patch_group`
- `fix_scope`
- `requires_context`
- `requires_test`
- `blocked_by`

### 2. 从 Day 2 analyzer 输出构建 issue_graph

输入至少来自：
- `issues`
- `symbols`
- `context_summary`

第一版允许启发式实现，但必须稳定，不要写成“随机感觉式”逻辑。

建议规则：

#### 规则 A：每个 issue 至少转成一个 node

#### 规则 B：根据 symbol / line / file_path 补全 `related_symbols`

#### 规则 C：根据以下启发式补 `fix_scope`
- 同文件 -> `single_file`
- 明显跨文件引用或缺少足够信息 -> `multi_file` 或 `unknown`

#### 规则 D：根据 issue_type 给出 `strategy_hint`
比如：
- `null_pointer` -> `null_guard`
- `sql_injection` -> `parameterized_query`
- `resource_leak` -> `try_with_resources`
- `missing_validation` -> `input_validation`
- `bad_exception_handling` -> `exception_logging`

#### 规则 E：根据风险或类型判断 `requires_test`
如：
- SQL 注入
- 查询逻辑变更
- 资源管理
- 跨方法调用链影响

### 3. 生成 repair_plan

请基于 `issue_graph` 生成有顺序的 `repair_plan`。

要求：
- `priority` 为数字，越小越先修
- 支持 `patch_group`
- 支持 `blocked_by`
- 若两个问题明显冲突，不要放到同一 patch_group
- 若两个问题修改点重叠，可进入 `conflicts_with`

第一版可按以下顺序排序：
1. 高严重度优先
2. 有依赖约束的先满足依赖
3. 单文件优先于未知范围
4. 明确策略优先于未知策略

### 4. 在状态机中插入 planner 阶段

请在 Day 2 状态图基础上，新增 planner 阶段节点。

推荐事件顺序：
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

### 5. 发出新增事件

请严格按文档事件契约发送：

#### 必须新增
- `issue_graph_built`
- `repair_plan_created`

#### payload 要求
- `issue_graph_built.payload.issue_graph` 必须是结构化对象
- `repair_plan_created.payload.repair_plan` 必须是数组
- 不要只在 `message` 里写“已生成问题图”这种自然语言

### 6. 扩展 review_completed 最终收口

`review_completed.payload` 中必须同时保留：

#### 兼容字段
- `result`

#### 新结构建议镜像
- `summary`
- `analyzer`
- `issue_graph`
- `repair_plan`

也就是说，以下两条读取路径都应成立：

```python
payload["result"]["issue_graph"]
payload["issue_graph"]
```

以及：

```python
payload["result"]["repair_plan"]
payload["repair_plan"]
```

## 七、实现风格要求

1. **优先小步扩展，不要大重构**
2. **优先纯函数/可测试函数**，把 issue graph 构建逻辑抽到独立函数
3. **不要把复杂业务逻辑塞进 route handler**
4. **不要让前端依赖 message 做逻辑判断**
5. **不要引入与 Day 3 无关的大范围改动**
6. 如果已有 dataclass / pydantic / typed dict 风格，请保持现有风格一致

## 八、建议验收测试

请补充测试，至少覆盖以下断言：

### Case 1：输入含 1~2 个 issue 的 Java 代码
断言：
- `analyzer_completed` 存在
- `issue_graph_built` 存在
- `repair_plan_created` 存在
- `review_completed` 存在

### Case 2：检查 issue_graph 结构
断言：
- `nodes` 是 list
- 每个 node 至少有 `issue_id`、`type`、`fix_scope`

### Case 3：检查 repair_plan 结构
断言：
- `repair_plan` 是 list
- 每个 item 至少有 `issue_id`、`priority`、`strategy`

### Case 4：检查 review_completed 兼容性
断言：
- `payload.result` 存在
- `payload.result.issue_graph` 存在
- `payload.result.repair_plan` 存在
- 顶层 `payload.issue_graph` 存在
- 顶层 `payload.repair_plan` 存在

## 九、输出要求

完成修改后，请给出：

1. **变更文件列表**
2. **每个文件做了什么**
3. **关键设计说明**
4. **如何运行测试 / 启动服务**
5. **一段最小示例输出**（展示事件流中新增的 Planner 事件）

## 十、你不要做的事情

1. 不要改掉 `/internal/reviews/run`
2. 不要把 Day 3 做成 Fixer/Verifier 大开发
3. 不要删除旧字段
4. 不要引入无法解释的抽象层
5. 不要只写“伪结构”，必须让事件和最终 payload 真正能输出 `issue_graph` / `repair_plan`

## 十一、完成标准

你完成后，系统应该能做到：

- 输入一段 Java 代码
- Day 2 analyzer 正常输出
- Day 3 planner 正常构建 issue graph
- Day 3 planner 正常生成 repair plan
- 事件流中可看到：
  - `issue_graph_built`
  - `repair_plan_created`
- `review_completed` 中能读到：
  - `payload.result.issue_graph`
  - `payload.result.repair_plan`
  - 顶层镜像 `payload.issue_graph`
  - 顶层镜像 `payload.repair_plan`

请直接开始改代码，不要只给方案。
