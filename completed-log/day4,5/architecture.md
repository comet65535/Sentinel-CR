# Sentinel-CR Architecture（Day 4 / Day 5）

## 1. 文档目标

本文件描述 Sentinel-CR 在 Day 4（Fixer Agent + Case-based Memory）与 Day 5（Multi-stage Verifier + Self-healing Loop）阶段的目标架构、组件职责、数据流与实现边界。

Day 4/5 的核心不是再引入更多智能体，而是把 Day 3 已有的：

> Analyzer Evidence → Issue Graph → Repair Plan

继续推进为：

> Analyzer → Issue Graph Planner → Case Memory → Patch Fixer → Multi-stage Verifier → Retry Loop → Event Stream Result

这一步会决定项目是否真正具备“可修、可验、可解释失败”的工程闭环。

***

## 2. 架构定位

Sentinel-CR 的工程主链路不是“让大模型给建议”，而是：

> 发现问题 → 规划修复 → 生成补丁 → 验证补丁 → 失败回路 → 输出可分级结果

根据 README 与 7 天计划，系统的最终目标一直围绕：

> Analyzer → Issue Graph Planner → Fixer → Multi-stage Verifier → Event Stream → Benchmark

其中：

- Day 4 的关键增量是让系统第一次产出结构化 Unified Diff Patch。
- Day 5 的关键增量是让补丁不直接暴露给用户，而先经过 patch apply / compile / lint / test 的验证链路。

因此 Day 4/5 的架构目标不是做“大而全”，而是打穿一条最小可演示闭环：

1. 有问题输入
2. 有结构化 repair plan
3. 有案例命中
4. 有补丁输出
5. 有验证结论
6. 失败时能自动重试
7. 前端能看见全过程事件

***

## 3. Day 4 / Day 5 目标拆分

## 3.1 Day 4：从 Repair Plan 到 Patch Artifact

Day 4 解决的问题是：

- Day 3 已经知道“先修什么”
- 但系统还不会稳定地产出“怎么改”的结构化结果

因此 Day 4 要引入：

- `case_memory.py`
- `fixer_agent.py`
- `prompts/fixer_prompt.py`
- `patch_artifact` 结构
- memory / fixer 相关事件

Day 4 的输出不再是泛泛建议，而是：

- 命中的案例
- 使用的策略
- 目标文件
- Unified Diff 内容
- 风险等级
- 修改说明

## 3.2 Day 5：从 Patch Artifact 到 Verified Patch

Day 5 解决的问题是：

- 仅有 patch 还不够
- 必须证明 patch 能打上、能编译、最好还能通过 lint / test

因此 Day 5 要引入：

- `patch_apply.py`
- `sandbox_env.py`
- `test_runner.py`
- `verifier_agent.py`
- reflection / retry 机制
- verifier / retry 相关事件

Day 5 的关键产物是：

- `verification_result`
- `attempts`
- `retry_history`
- `verified_level`

***

## 4. 系统总览

```mermaid
graph TD
    subgraph Frontend
        UI[ReviewPage / Code Input]
        Timeline[Event Timeline]
        DiffView[Diff Viewer]
        DebugPanel[Debug Panel]
    end

    subgraph JavaBackend[Java Backend / SSE Gateway]
        ReviewAPI[POST /api/reviews]
        ReviewResult[GET /api/reviews/{id}]
        EventSSE[GET /api/reviews/{id}/events]
        InternalProxy[POST /internal/reviews/run Proxy]
        EventHub[SSE Event Hub]
    end

    subgraph PythonEngine[Python AI Engine]
        StateGraph[core/state_graph.py]
        Analyzer[analyzers/*]
        Planner[agents/planner_agent.py]
        CaseMemory[memory/case_memory.py]
        Fixer[agents/fixer_agent.py]
        Verifier[agents/verifier_agent.py]
        Reporter[agents/reporter_agent.py]
    end

    subgraph Sandbox[Execution Tools]
        PatchApply[tools/patch_apply.py]
        SandboxEnv[tools/sandbox_env.py]
        TestRunner[tools/test_runner.py]
    end

    UI --> ReviewAPI
    ReviewAPI --> InternalProxy
    InternalProxy --> StateGraph
    StateGraph --> Analyzer
    StateGraph --> Planner
    StateGraph --> CaseMemory
    StateGraph --> Fixer
    Fixer --> Verifier
    Verifier --> PatchApply
    Verifier --> SandboxEnv
    Verifier --> TestRunner
    Verifier -->|fail and retry| Fixer
    StateGraph --> Reporter
    Reporter --> EventHub
    EventHub --> EventSSE
    EventSSE --> Timeline
    EventSSE --> DiffView
    EventSSE --> DebugPanel
    Reporter --> ReviewResult
```

***

## 5. 分层职责

## 5.1 Frontend UI

职责：

- 提交代码修复任务
- 订阅 SSE 事件流
- 展示 Timeline / Diff / Debug 信息
- 展示最终结果与验证等级

注意：

- 前端不推导业务语义
- 前端不从 `message` 中解析 patch / verification
- 一切以结构化 `payload` 与最终结果对象为准

## 5.2 Java Backend

职责：

- 作为统一外部入口
- 生成 `review_id` / `task_id`
- 把前端请求转发给 Python 引擎
- 把 NDJSON 转换为 SSE
- 聚合任务结果并提供查询接口

注意：

- Java 负责传输与编排，不负责重写 AI 结果语义
- Java 可以缓存最终结果，但不能篡改字段名

## 5.3 Python AI Engine

职责：

- 承载实际审查/修复主流程
- 维护 LangGraph / 状态机
- 发出全链路结构化事件
- 聚合最终结果

它是 Day 4/5 的核心执行层。

***

## 6. Python 侧组件拆解

## 6.1 Analyzer 层（已完成基础能力）

输入：

- `code_text`
- `language`

输出：

- `issues`
- `symbols`
- `context_summary`

责任边界：

- 只负责提供证据
- 不负责决定修复顺序
- 不负责生成 patch

## 6.2 Planner 层（Day 3 已完成基础能力）

输入：

- analyzer 输出

输出：

- `issue_graph`
- `repair_plan`

责任边界：

- 决定修复顺序
- 决定修复边界与策略提示
- 不直接生成 patch

## 6.3 Case Memory（Day 4 新增）

输入：

- `repair_plan`
- analyzer 证据
- 受影响 symbol / issue 类型

输出：

- `memory_matches`

责任：

- 检索结构化案例
- 返回命中模式、风险提示、历史成功率
- 为 Fixer 提供 patch adaptation 依据

第一版可以是本地静态案例库，不要求完整向量检索。

## 6.4 Fixer Agent（Day 4 新增）

输入：

- `repair_plan`
- analyzer 证据
- `memory_matches`
- 当前尝试号 `attempt_no`

输出：

- `patch_artifact`

职责：

- 把修复计划转换为 Unified Diff
- 输出结构化 explanation / risk_level / target_files
- 记录使用了哪些 memory case

边界：

- Fixer 负责“生成补丁”
- 不负责自己判定补丁是否可信
- 验证必须交给 Verifier

## 6.5 Verifier Agent（Day 5 新增）

输入：

- `patch_artifact`
- 原始代码 / 临时工作目录
- verifier 配置

输出：

- `verification_result`
- `attempt_record`

执行顺序：

1. patch apply
2. compile
3. lint
4. test
5. security re-scan（可选）

边界：

- Verifier 只做证据性验证
- 不负责生成补丁
- 失败时只返回结构化失败原因，重生成由 Fixer 执行

## 6.6 Reporter Agent

职责：

- 聚合 analyzer / planner / memory / fixer / verifier 结果
- 生成 `review_completed` 事件
- 生成最终 `result` 对象
- 做兼容镜像字段填充

***

## 7. 状态机视角

Day 4/5 的状态图建议最少包含以下状态字段：

```python
state = {
    "task_id": str,
    "code_text": str,
    "issues": list,
    "symbols": list,
    "context_summary": dict,
    "issue_graph": dict,
    "repair_plan": list,
    "memory_matches": list,
    "patch_artifact": dict | None,
    "verification_result": dict | None,
    "attempts": list,
    "retry_count": int,
    "max_retries": int,
    "events": list,
    "final_status": str,
}
```

### 关键设计要点

- `attempts` 必须是历史累积数组，而不是只保留最后一轮
- `patch_artifact` 只表示当前轮次最新补丁
- `verification_result` 只表示当前轮次最新验证结论
- 最终结果应由 `attempts` + 当前结果共同聚合

***

## 8. 数据流

## 8.1 主成功路径

```text
提交代码
  -> Analyzer 生成 issues / symbols / context_summary
  -> Planner 生成 issue_graph / repair_plan
  -> Case Memory 检索匹配案例
  -> Fixer 生成 patch_artifact
  -> Verifier 执行 patch_apply / compile / lint / test
  -> Reporter 聚合 verified result
  -> Java 通过 SSE 推送事件，前端展示
```

## 8.2 失败重试路径

```text
Fixer 生成 patch_artifact
  -> Verifier 在 compile 或 test 阶段失败
  -> 生成结构化 failure summary
  -> retry budget > 0
  -> 发出 retry_scheduled 事件
  -> Fixer 基于 failure summary 再生成 patch
  -> 再次进入 Verifier
  -> 成功或耗尽重试次数
```

## 8.3 失败信息回填原则

Verifier 返回给 Fixer 的失败信息应尽量结构化，包括：

- `failed_stage`
- `stderr_summary`
- `likely_reason`
- `retry_budget_left`
- `last_patch_id`

不要只返回一整段 stderr 原文，否则下一轮难以稳定利用。

***

## 9. 多阶段验证设计

## 9.1 Patch Apply

目标：

- 判断 patch 是否能正确打到目标文件

输出：

- `passed` / `failed`
- reject 原因摘要

## 9.2 Compile

目标：

- 判断补丁后代码是否语法正确、依赖可解析

第一版建议：

- 单文件场景优先 `javac`
- 项目化场景可预留 `mvn -q -DskipTests compile`

## 9.3 Lint

目标：

- 过滤明显坏味道或规范问题

第一版可允许为轻量占位，但事件和结果结构必须预留。

## 9.4 Test

目标：

- 判断补丁是否引入行为回归

第一版可从最小测试执行器起步：

- 指定测试类
- 简单回归命令
- 或无测试场景的跳过状态

## 9.5 Security Re-scan

目标：

- 检查补丁是否引入新的安全问题

Day 5 第一版为可选增强项，不应阻塞最小闭环。

***

## 10. Verified Level 设计

推荐采用如下等级：

- `L0`: patch 已生成，但未验证
- `L1`: patch apply + compile 通过
- `L2`: patch apply + compile + lint 通过
- `L3`: patch apply + compile + lint + test 通过
- `L4`: 上述全部通过且 security re-scan 通过

这个等级既能直接给前端展示，也能成为 benchmark 指标。

***

## 11. 自愈式重试回路

## 11.1 为什么需要重试回路

真实补丁失败常见原因：

- 上下文理解不完整
- import / type 细节错误
- 方法名或变量名拼错
- patch 逻辑对但语法不完整

如果第一次失败就终止，系统很难体现工程价值。

## 11.2 重试策略

建议最小策略：

- 默认 `max_retries = 2`
- 只在可重试失败时进入下一轮
- 不可重试错误直接终止

### 可重试示例

- compile error
- test fail
- patch apply conflict（可重构 patch 时）

### 不可重试示例

- 输入为空
- 内部状态损坏
- Sandbox 初始化失败且无法恢复

## 11.3 Attempt 记录

每轮都应记录：

- `attempt_no`
- `patch_id`
- `memory_case_ids`
- `failed_stage`
- `failure_reason`
- `verified_level`
- `status`

***

## 12. 事件驱动设计

Day 4/5 仍坚持“事件优先”的系统可观测性设计。

### 前端普通模式关心

- 当前阶段
- 当前状态
- 是否已生成补丁
- 验证通过到什么等级
- 是否正在重试

### Debug 模式关心

- 命中了哪些案例
- 当前 patch 用了什么策略
- 哪个阶段失败
- 失败 stderr 摘要
- 已经重试了几次

因此：

- 事件名必须稳定
- payload 必须结构化
- 最终结果必须可由事件序列回放验证

***

## 13. 目录映射建议

```text
ai-engine-python/
├── core/
│   ├── state_graph.py
│   ├── issue_graph.py
│   ├── schemas.py
│   └── events.py
├── agents/
│   ├── planner_agent.py
│   ├── fixer_agent.py
│   ├── verifier_agent.py
│   └── reporter_agent.py
├── memory/
│   ├── short_term.py
│   └── case_memory.py
├── tools/
│   ├── patch_apply.py
│   ├── sandbox_env.py
│   └── test_runner.py
└── prompts/
    └── fixer_prompt.py
```

### Day 4 重点文件

- `memory/case_memory.py`
- `agents/fixer_agent.py`
- `prompts/fixer_prompt.py`
- `core/state_graph.py`
- `core/events.py`
- `agents/reporter_agent.py`

### Day 5 重点文件

- `tools/patch_apply.py`
- `tools/sandbox_env.py`
- `tools/test_runner.py`
- `agents/verifier_agent.py`
- `core/state_graph.py`
- `agents/reporter_agent.py`
- `tests/test_acceptance_day5.py`

***

## 14. 实现边界与非目标

Day 4/5 的非目标：

- 不追求完整仓库级上下文系统
- 不追求复杂向量检索基础设施
- 不追求全量 PR 修复
- 不追求一次支持所有语言
- 不追求大型多文件补丁智能合并

Day 4/5 的成功标准是：

1. 至少一种常见问题能生成 Unified Diff
2. 补丁对象是结构化 JSON
3. 至少支持 patch apply + compile 的最小验证闭环
4. 失败后能自动再尝试 1~2 次
5. 前端能展示新增事件与最终等级

***

## 15. 一句话总结

Day 4 把 Sentinel-CR 从“会规划”推进到“会改”，Day 5 再把它从“会改”推进到“会证明自己改得至少部分正确”。

这两天完成后，项目就不再只是 Analyzer + Planner demo，而是第一次真正具备：

> Patch-first + Verification-first + Retry-aware

的工程化代码修复闭环。
