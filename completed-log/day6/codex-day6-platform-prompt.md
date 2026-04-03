# Codex Prompt — Sentinel-CR Day6「平台能力日」实现任务

你正在 `Sentinel-CR` 仓库中继续开发 Day6。

你的目标不是“重写一个全新项目”，而是**在当前已经跑通的 Day5 主链路上，增量实现 Day6 平台能力**。

请务必先完整阅读以下文件，再开始编码：

## 必读文件（先读，再改）
### 根目录文档
- `README.md`
- `PLAN.md`
- `docs/api-contract.md`
- `docs/architecture.md`
- `docs/event-schema.md`

### Python 主链
- `ai-engine-python/main.py`
- `ai-engine-python/core/state_graph.py`
- `ai-engine-python/core/schemas.py`
- `ai-engine-python/core/issue_graph.py`
- `ai-engine-python/agents/planner_agent.py`
- `ai-engine-python/agents/fixer_agent.py`
- `ai-engine-python/agents/verifier_agent.py`
- `ai-engine-python/agents/reporter_agent.py`
- `ai-engine-python/memory/case_memory.py`
- `ai-engine-python/tools/patch_apply.py`
- `ai-engine-python/tools/sandbox_env.py`
- `ai-engine-python/tools/test_runner.py`

### Java Backend
- `backend-java/src/main/java/com/backendjava/api/ReviewController.java`
- `backend-java/src/main/java/com/backendjava/service/ReviewService.java`
- `backend-java/src/main/java/com/backendjava/api/dto/CreateReviewRequest.java`
- `backend-java/src/main/java/com/backendjava/engine/PythonAiEngineAdapter.java`
- `backend-java/src/main/java/com/backendjava/engine/PythonReviewRunRequest.java`
- `backend-java/src/main/java/com/backendjava/event/ReviewEvent.java`

### Frontend
- `frontend-ui/src/views/ReviewPage.vue`
- `frontend-ui/src/components/EventTimeline.vue`
- `frontend-ui/src/components/StageDetailPanel.vue`
- `frontend-ui/src/components/ResultSummaryCard.vue`
- `frontend-ui/src/components/PatchDiffViewer.vue`
- `frontend-ui/src/components/ReviewSidebar.vue`
- `frontend-ui/src/types/review.ts`
- `frontend-ui/src/api/review.ts`

---

## 一、先认清当前真实基线，不要按 README 理想态误判

当前真实情况是：

1. **public API 已经存在并且在用**
   - `POST /api/reviews`
   - `GET /api/reviews/{taskId}`
   - `GET /api/reviews/{taskId}/events`

2. **Python 引擎主入口还不是 LangGraph**
   - `ai-engine-python/main.py` 目前直接调用 `run_day3_state_graph`
   - `core/state_graph.py` 目前是手写 orchestrator，不是真正 LangGraph

3. **memory 目前只有静态 case memory**
   - 只有 `memory/case_memory.py`
   - 还没有 `short_term.py / repo_memory.py / case_store.py`

4. **verifier 只有 L1 真正可用**
   - compile / patch_apply 真实存在
   - lint / test / security_rescan 目前还是 skipped placeholder

5. **前端已有基础展示**
   - timeline
   - summary
   - diff
   - detail panel
   但还没有：
   - Issue Graph 可视化
   - token/context panel

6. **public CreateReviewRequest 还没有 metadata**
   - 但 backend 到 python 的 internal request 已经有 `metadata`

你的实现必须建立在这条现实基线之上，而不是凭空假设仓库已经实现了 LangGraph / MCP / Repo Memory。

---

## 二、你的 Day6 总任务

你要实现以下 6 个模块，并保证 **现有 Day5 snippet 闭环不被破坏**：

1. **把 Python 工作流升级为真实 LangGraph**
2. **补齐三层记忆：短期 / 长期 / 仓库级**
3. **新增 MCP 资源 / 工具接口 + Python MCP Client**
4. **新增 Lazy Context / token budget**
5. **前端新增 Issue Graph + Context Budget 面板**
6. **Verifier 升级到真实 L2/L3/L4 骨架**

---

## 三、硬性约束（必须遵守）

### 1. 不能破坏现有 public API
这些接口必须继续可用，字段名不能乱改：

- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/events`

### 2. 不能重命名现有关键字段
禁止改名：

- `taskId`
- `eventType`
- `payload`
- `summary`
- `issue_graph`
- `repair_plan`
- `patch`
- `verification`

### 3. 不能替换掉现有稳定事件名
以下事件名必须继续存在：

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

你可以新增事件，但不能替换旧事件。

### 4. Day6 必须是 additive 改造
- 新字段尽量 optional
- 新 endpoint 走 internal namespace
- 老前端不认识新字段也不应崩

### 5. 保持 snippet-only 路径可用
Day6 先做平台骨架，不强制把 public repo/PR 模式产品化。  
所以就算 MCP / repo memory 暂时拿不到真实仓库，也必须保证 snippet 场景继续跑通。

---

## 四、你要具体完成的代码任务

# 任务 A：真实接入 LangGraph

## 必做
新增：
- `ai-engine-python/core/langgraph_flow.py`

重构：
- `ai-engine-python/core/state_graph.py`

新增测试：
- `ai-engine-python/tests/test_langgraph_flow.py`

## 要求
1. 使用真实 `langgraph` / `StateGraph`
2. 节点至少包括：
   - `bootstrap`
   - `analyzer`
   - `planner`
   - `memory_retrieval`
   - `fixer`
   - `verifier`
   - `retry_router`
   - `reporter`

3. 路由规则：
   - 零问题样本：`analyzer -> reporter`
   - 无 patch：`fixer -> reporter`
   - verifier pass：`verifier -> reporter`
   - verifier fail 且可重试：`verifier -> retry_router -> fixer`
   - verifier fail 且重试耗尽：`retry_router -> reporter`

4. `state_graph.py` 不再手写整个流程，而是作为 adapter / wrapper 调用 `langgraph_flow.py`
5. 保留 `run_day3_state_graph(request)` 这个外部调用入口，避免 `main.py` 与现有代码断裂

## 建议实现方式
- 用 `StateGraph` 编译 graph
- 用 async node
- 每个 node 返回 `state delta`
- 事件继续通过 helper 追加到 `state.events`
- wrapper 负责把新增事件逐步 yield 出去

## 需要新增的 debug 事件
- `langgraph_compiled`
- `langgraph_node_started`
- `langgraph_node_completed`

但注意：这些只是新增 debug 事件，不能代替现有业务事件。

---

# 任务 B：补齐三层记忆

## 必做文件
新增：
- `ai-engine-python/memory/short_term.py`
- `ai-engine-python/memory/repo_memory.py`
- `ai-engine-python/memory/case_store.py`

新增数据目录：
- `ai-engine-python/data/cases/`
- `ai-engine-python/data/repo_profiles/`

必要时调整：
- `ai-engine-python/memory/__init__.py`
- `ai-engine-python/memory/case_memory.py`

## 具体要求

### B1. short_term.py
实现短期记忆，至少保存：
- 最近一次 analyzer evidence
- 最近一次 patch
- 最近一次 verifier failure
- retry context
- 用户约束
- token 使用摘要

建议接口：
- `build_short_term_snapshot(...)`
- `update_short_term_memory(state, snapshot_type, payload)`
- `get_latest_verifier_failure(...)`

并新增事件：
- `short_term_memory_updated`

### B2. case_store.py
把当前静态案例库升级为可持久化 case store。

最少支持 JSONL 方案，字段固定：
- `case_id`
- `pattern`
- `trigger_signals`
- `before_code`
- `after_code`
- `diff`
- `risk_note`
- `success_rate`
- `verified_level`
- `accepted_by_human`
- `tool_trace`

建议接口：
- `load_cases(...)`
- `search_cases(...)`
- `append_case(...)`
- `promote_verified_patch_to_case(...)`

### B3. case_memory.py
保留现有 `retrieve_case_matches(...)` 对外行为，但底层可接入 case store。
要求：
- 当前静态 `CASE_LIBRARY` 可以保留为 fallback
- 优先从 `data/cases/*.jsonl` 读取
- snippet-only 场景没数据时也不能报错

### B4. repo_memory.py
实现 repo-level memory，至少保存：
- `repo_id`
- `style_preferences`
- `common_issue_types`
- `common_failed_stages`
- `preferred_build_command`
- `preferred_test_command`
- `rejected_patch_patterns`
- `hotspots`

建议接口：
- `load_repo_profile(repo_profile_id | repo_id)`
- `resolve_repo_profile(metadata, options)`
- `summarize_repo_profile(...)`

新增事件：
- `repo_memory_loaded`

---

# 任务 C：MCP Server + Python MCP Client + Lazy Context

## C1. backend-java 新增 internal MCP endpoints

新增 backend 包（命名可按你代码风格调整，但建议在 `mcp/` 下）：
- `McpResourceController`
- `McpToolController`
- `McpResourceService`
- `McpToolService`

新增接口：

### Resources
- `GET /internal/mcp/resources/repo-tree`
- `GET /internal/mcp/resources/file`
- `GET /internal/mcp/resources/schema`
- `GET /internal/mcp/resources/build-log-summary`
- `GET /internal/mcp/resources/test-summary`
- `POST /internal/mcp/resources/pr-diff/parse`

### Tools
- `POST /internal/mcp/tools/resolve-symbol`
- `POST /internal/mcp/tools/find-references`
- `POST /internal/mcp/tools/run-analyzer`
- `POST /internal/mcp/tools/run-sandbox`
- `POST /internal/mcp/tools/query-tests`

### 返回格式
统一按 `docs/api-contract.md` 的 envelope：
- `ok`
- `kind`
- `name`
- `request_id`
- `data`
- `meta`
- `error`

## C2. Python 新增 MCP Client
新增：
- `ai-engine-python/core/mcp_client.py`

要求：
- 对 backend internal MCP 接口做统一 client 封装
- Planner / Fixer / Verifier 都能复用
- 所有调用写入 `tool_trace`
- 失败时返回结构化错误，不抛裸异常把主链打断

## C3. 新增 Context Budget
新增：
- `ai-engine-python/core/context_budget.py`

要求：
- 支持 policy：`none` / `lazy`
- 管理：
  - `budget_tokens`
  - `used_tokens`
  - `remaining_tokens`
  - `load_stage`
  - `sources`
- 支持逐步加载：
  1. issue 周边 snippet
  2. symbol summary
  3. impacted file fragment
  4. build/test summary
  5. full file（最后手段）

新增事件：
- `context_budget_initialized`
- `context_resource_loaded`
- `context_budget_updated`
- `context_budget_exhausted`

### 重要
没有真实 tiktoken 也可以先用安全近似估算（例如 char/4），但代码结构必须能后续替换成真实 tokenizer。

---

# 任务 D：补齐 verifier 的真实 L2/L3/L4 骨架

## 必做文件
新增：
- `ai-engine-python/tools/lint_runner.py`
- `ai-engine-python/tools/security_rescan.py`

改造：
- `ai-engine-python/tools/test_runner.py`
- `ai-engine-python/tools/__init__.py`
- `ai-engine-python/agents/verifier_agent.py`

## 要求

### D1. 统一 stage 结果结构
每个 stage 返回：
```json
{
  "stage": "compile",
  "status": "passed|failed|skipped",
  "exit_code": 0,
  "stdout_summary": "",
  "stderr_summary": "",
  "reason": null,
  "retryable": false
}
```

### D2. L1-L4 规则
- `L1 = patch_apply + compile`
- `L2 = + lint`
- `L3 = + test`
- `L4 = + security_rescan`

### D3. 行为要求
- 没有命令配置时可以 `skipped`
- 但不允许直接 TODO 或抛裸异常
- `run_test_stage(...)` 至少支持：
  - 通过 repo profile / options 提供命令
  - 或 snippet 默认 skipped
- `run_lint_stage(...)` 至少支持：
  - 外部命令配置
  - 默认 skipped
- `run_security_rescan_stage(...)` 至少支持：
  - `enable_security_rescan=false` -> skipped
  - `enable_security_rescan=true` 且有 semgrep 命令 -> 尝试执行
  - 否则结构化 skipped

### D4. 事件
继续沿用现有 stage 模板事件：
- `<stage>_started`
- `<stage>_completed`
- `<stage>_failed`

不能另起一套命名系统。

---

# 任务 E：补 frontend Issue Graph / Context 面板

## 必做文件
新增：
- `frontend-ui/src/components/IssueGraphPanel.vue`
- `frontend-ui/src/components/TokenContextPanel.vue`

修改：
- `frontend-ui/src/views/ReviewPage.vue`
- `frontend-ui/src/components/StageDetailPanel.vue`
- `frontend-ui/src/types/review.ts`
- `frontend-ui/src/utils/reviewEventView.ts`（如果没有就新增）

## 要求

### E1. IssueGraphPanel
- 读取：
  - `review_completed.payload.result.issue_graph`
  - 或最新 `issue_graph_built.payload.issue_graph`
- 支持节点点击
- 支持显示：
  - issue type
  - severity
  - file path
  - related symbols
  - strategy hint
  - fix scope
- 允许先用简单 SVG / div 布局 / 轻量图实现
- 不要求 Day6 就做非常复杂的交互，但必须真能显示图，不是纯 JSON dump

### E2. TokenContextPanel
- 读取：
  - `result.context_budget`
  - 或最新 `context_budget_updated` / `context_resource_loaded`
- 展示：
  - budget_tokens
  - used_tokens
  - remaining_tokens
  - load_stage
  - sources 列表

### E3. StageDetailPanel
保留现有面板逻辑，新增 tab / section 即可：
- Overview
- Issue Graph
- Context
- Verification
- Memory
- Raw Payload

### E4. Sidebar
`ReviewSidebar.vue` 当前历史记录是 placeholder，这不是 Day6 强制清理项。  
如无必要，不要为了 Day6 把整个历史系统重写。  
可以保留 placeholder，或只做最小提升，但不要因此拖垮主任务。

---

# 任务 F：把 public request 的 metadata 断层补齐

当前：
- frontend request type 没有 `metadata`
- backend public DTO 没有 `metadata`
- backend internal to python 已经有 `metadata`

Day6 必须补齐：

## 必改
- `frontend-ui/src/types/review.ts`
- `backend-java/api/dto/CreateReviewRequest.java`
- `backend-java/service/ReviewService.java`
- `backend-java/engine/PythonAiEngineAdapter.java`

## 要求
- `metadata` 为 optional
- 未提供时默认 `{}` 或 `Map.of()`
- 透传到 Python internal request
- 不影响现有调用

---

## 五、你必须遵循的 contract

你实现时，必须与以下文档保持一致：

- `docs/api-contract.md`
- `docs/architecture.md`
- `docs/event-schema.md`

如果代码现状与文档存在冲突，请按以下优先级处理：

1. **兼容现有可运行代码**
2. **遵循 docs 中的 Day6 增量 contract**
3. **不要直接按 README 理想态大改 public API**

---

## 六、建议的落地顺序（强烈建议按这个顺序做）

1. 先补类型与 contract 对齐：
   - request / result / event payload / metadata
2. 再接 LangGraph：
   - `langgraph_flow.py`
   - `state_graph.py` adapter
3. 再补 memory：
   - short term / repo / case store
4. 再补 context budget 与 MCP client
5. 再补 backend MCP endpoints
6. 再补 verifier 的 lint/test/security runners
7. 最后补 frontend graph/context 面板

这样做可以避免把当前可跑主链一下打断。

---

## 七、你修改完成后，必须达到的验收标准

### A. 主链稳定性
1. snippet 提交仍能跑通
2. `/api/reviews/{taskId}/events` 仍能持续推送事件
3. `review_completed` payload 仍能被当前前端 summary/diff 读取

### B. LangGraph
4. 存在真实 `langgraph_flow.py`
5. `state_graph.py` 不再是主流程真身，而是 adapter
6. 有至少一个针对正常流的测试
7. 有至少一个针对 retry 分支的测试
8. 有至少一个针对 zero issue 直接 reporter 的测试

### C. Memory
9. 有短期记忆
10. 有 repo profile 读取
11. verified patch 可以被 promote 到 case store（至少代码路径存在，且可运行）

### D. MCP / Context
12. backend 有 internal MCP endpoints
13. python 有 `mcp_client.py`
14. context budget 能输出结构化信息
15. 前端能看到 token/context 面板

### E. Verifier
16. verifier 能输出真实 L2/L3/L4 stage 结果骨架
17. stage 结果统一为 `passed / failed / skipped`
18. 失败时仍能正确出 `verifier_failed -> review_retry_*`

### F. UI
19. 前端能显示 Issue Graph
20. 前端能显示 Context Budget
21. 旧 timeline / summary / diff 不被破坏

---

## 八、不要做的事

不要做以下错误操作：

1. 不要删掉现有 event name，重新发一套新命名
2. 不要把 public API 改成完全不同的路径或字段
3. 不要把 `ReviewSidebar` 历史系统当成 Day6 主任务
4. 不要把 repo/PR public 输入强行做成 Day6 必须完成的工作
5. 不要只写 TODO / pass / placeholder 交差
6. 不要为了“看起来高级”把现有主链拆得跑不起来

---

## 九、交付要求

请直接修改仓库代码，并尽量补上必要测试。

完成后，请确保：

- backend 能编译
- python 代码能运行
- frontend 类型不报错
- 关键路径有 smoke 测试 / 单测
- 事件 schema 与 docs 保持一致

重点不是“代码行数很多”，而是：

> **在真实 Day5 基线之上，把 Day6 平台骨架落到代码里，而且不把现有闭环弄坏。**
