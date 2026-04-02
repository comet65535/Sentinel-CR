# 给 Codex 的 Day 2 实现提示词

你现在在实现 Sentinel-CR 的 **Day 2 Analyzer 层**。

## 背景

这是一个工程化 AI Code Repair 项目，目标主链路是：

Analyzer -> Issue Graph Planner -> Fixer -> Multi-stage Verifier -> Event Stream -> Benchmark

当前 **Day 1 已完成**，现状如下：

1. 前端已经通过 `frontend-ui/src/api/review.ts` 调用：
   - `POST /api/reviews`
   - `GET /api/reviews/{taskId}`
   - `GET /api/reviews/{taskId}/events`
2. Java 后端已经有 `ReviewController` / `ReviewService` / `ReviewEvent` / `ReviewTask`，能把 Python Engine 事件转成 SSE 并持久化到 `task.result`
3. Python Engine 当前已有：
   - `ai-engine-python/main.py`
   - `ai-engine-python/core/schemas.py`
   - `ai-engine-python/core/events.py`
   - `ai-engine-python/core/state_graph.py`
4. 但是 Python Engine 目前仍是 Day 1 stub：
   - `run_analysis_stub()` 只是占位
   - `analyzers/` 目录基本还没实现
   - `prompts/` 目录也几乎还是空壳
5. Day 2 目标不是做 patch/fixer/verifier，而是做**确定性证据层**：
   - Tree-sitter AST
   - Symbol Graph
   - Semgrep

## 你的任务

请你直接在仓库中完成 Day 2 落地，要求**最小必要改动、保持主链路可运行**。

### 必做项

#### 1. 完成 Python Analyzer 模块
在 `ai-engine-python/analyzers/` 下实现：

- `ast_parser.py`
- `symbol_graph.py`
- `semgrep_runner.py`
- 建议新增 `analyzer_pipeline.py`

#### 2. AST 解析能力
`ast_parser.py` 需要基于 `tree-sitter-java` 提取：

- 类名
- 方法签名
- 字段
- imports
- 代码块边界（起止行）

输出必须是 JSON-friendly 结构，不能返回不可序列化对象。

#### 3. Symbol Graph 能力
`symbol_graph.py` 需要在 AST 基础上提取最小可用 graph：

- `class -> methods`
- `method -> called methods`
- `variable -> usage`（第一版可以简化）

目标不是做全功能静态分析器，而是给 Day 3 Planner 提供足够的影响范围信息。

#### 4. Semgrep 扫描能力
`semgrep_runner.py` 需要：

- 对 Java 代码片段执行扫描
- 输出标准化 issue 结构
- 统一字段：
  - `issueId`
  - `issueType`
  - `severity`
  - `ruleId`
  - `message`
  - `line`
  - `startLine`
  - `endLine`
  - `engine`
  - `category`
  - `snippet`
- `severity` 统一归一到：
  - `LOW | MEDIUM | HIGH | CRITICAL`

如果本地 semgrep 不可用，不要直接让整个任务失败：

- 返回空 issues
- 记录 diagnostics
- 发 warning 事件

#### 5. 扩展 `core/schemas.py`
扩展 `EngineState`，至少新增：

- `symbols`
- `context_summary`
- `analyzer_summary`
- `diagnostics`

要求：

- 与现有字段兼容
- 保留 `issue_graph` / `patch` / `verification_result` / `retry_count` 以兼容后续 Day 3+

#### 6. 改造 `core/state_graph.py`
把 Day 1 的 stub 流程替换为 Day 2 的真实 Analyzer 流程。

推荐顺序：

1. `analysis_started`
2. `ast_parsing_started`
3. `ast_parsing_completed`
4. `symbol_graph_started`
5. `symbol_graph_completed`
6. `semgrep_scan_started`
7. `semgrep_scan_completed` 或 `semgrep_scan_warning`
8. `analyzer_completed`
9. `review_completed`

最终 `review_completed.payload.result` 必须包含：

- `summary`
- `engine`
- `analyzer`
- `issues`
- `symbols`
- `contextSummary`
- `diagnostics`

#### 7. 保持 Java / Frontend 契约不破坏
不要改动这些公开接口的 URL：

- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/events`
- Python `POST /internal/reviews/run`

不要破坏前端当前的 EventSource 使用方式。

#### 8. 补测试
至少补以下测试：

- `ast_parser.py` 的单元测试
- `symbol_graph.py` 的单元测试
- `state_graph.py` 的事件顺序测试
- 对一个危险 Java 片段，Semgrep 至少能产出 1 条 issue（如果环境支持）

如果 semgrep 在 CI/本地环境不稳定，测试要写成**可降级但可诊断**，不要让整个测试套件脆弱。

---

## 设计约束

1. **不要过度设计**
   - Day 2 不做 Planner/Fixer/Verifier
   - 不要把 Day 6 的 repo-aware / PR-aware 逻辑提前做进来

2. **不要让 LLM 参与 Analyzer 核心输出**
   - Day 2 的结果应该来自 Tree-sitter 和 Semgrep
   - 自然语言只用于 summary，不用于替代结构化结果

3. **结构化优先**
   - 所有 Analyzer 输出必须可 JSON 序列化
   - 事件 `payload` 必须是对象，不能是字符串拼接大段文本

4. **保持向后兼容**
   - 可以新增细粒度事件
   - 但不要让现有前端因为字段名变化而挂掉

5. **最小必要改动**
   - 优先改 Python Engine
   - Java Backend 非必要不要大改
   - Frontend 非必要不要改 API 调用逻辑

---

## 目标数据结构（请按这个方向实现）

### `task.result`

```json
{
  "summary": "day2 analyzer completed",
  "engine": "python",
  "analyzer": {
    "language": "java",
    "classesCount": 1,
    "methodsCount": 3,
    "fieldsCount": 1,
    "symbolsCount": 6,
    "issuesCount": 2,
    "callEdgesCount": 2,
    "engines": ["tree-sitter", "semgrep"]
  },
  "issues": [],
  "symbols": [],
  "contextSummary": {},
  "diagnostics": []
}
```

### 单条 issue

```json
{
  "issueId": "SG-1",
  "issueType": "java.lang.security.audit.sql-injection",
  "severity": "HIGH",
  "ruleId": "java.lang.security.audit.sql-injection",
  "message": "Detected string concatenation in SQL query",
  "line": 18,
  "startLine": 18,
  "endLine": 18,
  "engine": "semgrep",
  "category": "security",
  "snippet": "String sql = \"select ...\" + userInput;"
}
```

### 单条 symbol

```json
{
  "symbolId": "method:UserService.findUser(String)",
  "kind": "method",
  "name": "findUser",
  "owner": "UserService",
  "line": 6,
  "signature": "User findUser(String id)"
}
```

---

## 事件要求

至少实现这些事件：

- `analysis_started`
- `ast_parsing_started`
- `ast_parsing_completed`
- `symbol_graph_started`
- `symbol_graph_completed`
- `semgrep_scan_started`
- `semgrep_scan_completed`
- `semgrep_scan_warning`
- `analyzer_completed`
- `review_completed`
- `review_failed`

事件字段继续沿用现有 envelope：

- `taskId`
- `eventType`
- `message`
- `status`
- `payload`

最终 Java 侧会补 `timestamp` 和 `sequence`，所以 Python 侧不要破坏当前事件模型。

---

## 依赖建议

如果需要，请更新 `ai-engine-python/requirements.txt`，引入：

- `tree-sitter`
- `tree-sitter-java`
- `semgrep`

但要注意：

- 依赖增加要克制
- 不要引入不必要的大型框架

---

## 交付要求

完成后，请给出：

1. 你改了哪些文件
2. 关键设计说明
3. 如何运行 / 验证
4. 测试结果
5. 已知风险和后续建议

---

## 验收标准

只有满足以下条件，才算完成：

1. 用一段 Java 代码提交后，主链路仍能跑通
2. SSE 能看到细粒度 Analyzer 事件
3. 最终 `task.result` 包含结构化 `issues/symbols/contextSummary`
4. 至少能提取出类/方法/import 摘要
5. 至少能提取出一部分调用关系
6. 对典型危险代码，若 semgrep 可用，至少能得到 1 条 issue
7. 失败时返回 diagnostics，而不是只有崩溃异常

请直接开始修改，不要只输出方案。
