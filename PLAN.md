# 📅 Sentinel-CR 最终版 7 天开发计划（细化增强版）

这份计划的目标不是“7 天堆出一个看起来很炫的 AI 项目”，而是用最短时间做出一条 **真正能跑通的工程主链路**：

> **Analyzer → Issue Graph Planner → Fixer → Multi-stage Verifier → Event Stream → Benchmark**

同时，这份计划已经把前面提出的所有关键升级点全部落地进开发路径中，包括：
- Issue Graph Planner
- Multi-stage Verifier
- Structured Case-based Memory
- Lazy Context System
- Event Stream + Debug Mode
- Failure Taxonomy
- Self-healing Loop
- Repo-level Memory
- PR 级分析入口

---

## 🎯 7 天最终目标

在第 7 天结束时，系统至少要做到：

1. 输入一段 Java 代码，能够先用 Tree-sitter + Semgrep 找出问题
2. 基于扫描结果和结构化经验库生成 Unified Diff
3. 在沙箱中完成 patch apply、compile、lint 或最小测试
4. 在失败时能自动反思并最多重试 2~3 次
5. 前端以事件流 + Diff 视图形式展示过程与结果
6. 能跑通一套 Golden Dataset，并输出失败分类统计

换句话说，这 7 天的重点不是“多智能体写得多复杂”，而是把 **修复闭环** 打穿。

---

## 📂 推荐目录结构（与开发任务强绑定）

```text
Sentinel-CR/
├── frontend-ui/                     # 事件流 UI + Diff + Debug 模式
├── backend-java/                    # Spring Boot + MCP Server + SSE EventBus
├── ai-engine-python/
│   ├── core/
│   │   ├── state_graph.py           # LangGraph 状态机
│   │   ├── issue_graph.py           # 问题依赖图模型
│   │   ├── context_budget.py        # Lazy Context 管理
│   │   └── mcp_client.py            # MCP 客户端
│   ├── analyzers/
│   │   ├── ast_parser.py            # Tree-sitter AST 解析
│   │   ├── symbol_graph.py          # 类/方法/调用关系提取
│   │   ├── semgrep_runner.py        # Semgrep 封装
│   │   └── codeql_runner.py         # CodeQL 封装（可选增强）
│   ├── agents/
│   │   ├── planner_agent.py         # Issue Graph Planner
│   │   ├── fixer_agent.py           # Patch 生成
│   │   ├── verifier_agent.py        # 多阶段验证
│   │   └── reporter_agent.py        # 事件与结果组装
│   ├── memory/
│   │   ├── short_term.py            # 当前线程上下文
│   │   ├── case_memory.py           # 结构化案例经验库
│   │   └── repo_memory.py           # 仓库级经验记忆
│   ├── tools/
│   │   ├── sandbox_env.py           # 沙箱环境
│   │   ├── patch_apply.py           # 应用 diff
│   │   ├── test_runner.py           # 测试执行
│   │   └── repo_tools.py            # 仓库与 PR 上下文工具
│   ├── prompts/
│   │   ├── planner_prompt.py
│   │   ├── fixer_prompt.py
│   │   └── verifier_prompt.py
│   └── benchmark/
│       ├── golden_cases/
│       ├── run_eval.py
│       └── failure_taxonomy.py
└── README.md
```

---

## ✅ Day 1：基础架构打通 + Event Stream 主链路跑通

### 当天目标
先别急着做“很聪明的 Agent”，第一天最重要的是把 **系统骨架和通信链路** 打通。  
到今天结束时，要做到：前端提交一段代码，Python 引擎收到任务，能把状态事件通过 Java SSE 推给前端。

### 要做的事情

#### 1. Java 后端搭建
- Spring Boot 3 初始化工程
- 提供一个 `POST /review` 接口用于接收任务
- 提供一个 `GET /events/{taskId}` 的 SSE 事件流接口
- 建立基础任务对象：`taskId / codeText / status / createdAt`

#### 2. Python AI 引擎骨架
- 建立 `LangGraph` 最小状态图
- 定义全局 `State`：
  - `code_text`
  - `issues`
  - `issue_graph`
  - `patch`
  - `verification_result`
  - `events`
  - `retry_count`

#### 3. 事件格式统一
先统一事件 JSON 协议，例如：

```json
{
  "task_id": "123",
  "event_type": "planning_started",
  "message": "开始进行结构化分析",
  "timestamp": "2026-04-01T10:00:00"
}
```

后面所有模块都严格按这个协议发事件，避免 UI 层后续重构成本。

### 今天结束时的交付物
- 前端能看到“任务已提交”“分析开始”“任务结束”三类基本事件
- Java 与 Python 通信链路打通
- 状态机骨架建立完成

---

## ✅ Day 2：Analyzer 层落地 —— Tree-sitter + Semgrep + Symbol Graph

### 当天目标
构建系统第一层“确定性证据来源”。  
今天结束后，系统至少要能：
- 解析 Java 代码 AST
- 提取方法名、类名、调用点
- 使用 Semgrep 扫出一批基础问题

### 要做的事情

#### 1. `ast_parser.py`
- 接入 `tree-sitter-java`
- 能提取：
  - 类名
  - 方法签名
  - 字段
  - import
  - 代码块边界
- 结果先以 JSON 输出

#### 2. `symbol_graph.py`
- 在 AST 基础上提取 symbol graph：
  - method -> called methods
  - class -> methods
  - variable -> usage
- 不要求第一版非常完整，但要能支撑后续 Planner 判断影响范围

#### 3. `semgrep_runner.py`
- 安装并调用 Semgrep
- 先接官方 Java 规则或自定义规则
- 输出标准化 issue 结构：
  - issue_type
  - severity
  - line
  - message
  - rule_id

#### 4. Analyzer 输出规范化
把 AST / Symbol / Semgrep 的结果统一进状态：

```json
{
  "issues": [...],
  "symbols": [...],
  "context_summary": {...}
}
```

### 今天结束时的交付物
- 输入一段 Java 代码，系统可以返回：
  - 类 / 方法摘要
  - 调用关系摘要
  - 至少 1 个可检出的规则问题

---

## ✅ Day 3：Issue Graph Planner 落地 —— 从“问题列表”升级为“修复图”

### 当天目标
今天是整个项目非常关键的一天：  
把“发现了一堆问题”升级成“知道先修哪个、怎么修、会不会冲突”。

### 要做的事情

#### 1. `issue_graph.py`
设计问题图数据结构，例如：

```json
{
  "issue_id": "ISSUE-1",
  "type": "null_pointer",
  "severity": "medium",
  "location": "UserService.java:42",
  "related_symbols": ["getUser", "userRepo.findById"],
  "depends_on": [],
  "conflicts_with": [],
  "fix_scope": "single_file"
}
```

#### 2. `planner_agent.py`
让 Planner 根据：
- Semgrep issue
- Symbol graph
- 当前代码上下文
组织成有顺序、有边界的 issue plan。

Planner 不只是排序，还要决定：
- 哪些问题应该合并成同一个 patch
- 哪些问题需要跨文件修复
- 哪些问题必须补上下文
- 哪些问题需要测试覆盖验证

#### 3. 输出修复计划
例如：

```json
{
  "repair_plan": [
    {"issue_id": "ISSUE-2", "priority": 1, "strategy": "parameterized_query"},
    {"issue_id": "ISSUE-1", "priority": 2, "strategy": "null_guard"}
  ]
}
```

### 今天结束时的交付物
- 系统不再只是输出 issue list
- 而是能输出一份结构化 repair plan
- 前端事件轴中新增：
  - `issue_graph_built`
  - `repair_plan_created`

---

## ✅ Day 4：Fixer Agent + Case-based Memory —— 从“现编”到“经验适配”

### 当天目标
让系统开始真正生成 **Unified Diff Patch**，并且不是凭空乱写，而是结合结构化经验库进行修复。

### 要做的事情

#### 1. `case_memory.py`
建立最小版本结构化案例库，至少先手动录入 5~10 条典型模式：
- 空指针修复
- SQL 参数化
- N+1 查询改批量查询
- try-with-resources
- 异常日志补全

每条案例包含：
- pattern
- trigger_signals
- before_code
- after_code
- diff
- risk_note
- success_rate

#### 2. Fixer Prompt 设计
Fixer 的 Prompt 不再泛泛地说“请修代码”，而是明确要求：
- 输入 issue plan
- 输入 analyzer 证据
- 输入命中的历史案例
- 输出 unified diff
- 输出修改说明
- 输出潜在风险

#### 3. Patch 格式强约束
要求模型输出 JSON 包裹 patch，例如：

```json
{
  "patch": "diff --git ...",
  "explanation": "...",
  "risk_level": "medium"
}
```

这样后面更容易喂给 verifier、前端、benchmark。

#### 4. 引入 Patch Adaptation 思维
如果命中了高相似案例，优先做“适配”，而不是完全重新生成补丁。

### 今天结束时的交付物
- Fixer Agent 能产出至少一种常见问题的 Unified Diff
- Memory 命中情况可通过事件流展示
- Patch 结构化输出可被后续模块消费

---

## ✅ Day 5：Multi-stage Verifier + Self-healing Loop —— 项目最硬核的一天

### 当天目标
今天要把项目真正和普通 demo 拉开差距：  
让补丁经过验证，不通过就回去改，而不是“建议到此为止”。

### 要做的事情

#### 1. `patch_apply.py`
- 把原代码和 patch 写入临时目录
- 调用 `patch` 命令打补丁
- 处理 patch apply 失败情况

#### 2. `sandbox_env.py`
- 创建隔离临时工作目录
- 执行：
  - `javac`
  - 或 `mvn -q -DskipTests compile`
- 返回 stderr / stdout

#### 3. `test_runner.py`
- 第一版可先做最小测试执行器
- 支持运行指定测试类或简单回归命令

#### 4. `verifier_agent.py`
Verifier 要按阶段执行：
1. patch apply
2. compile
3. lint
4. test
5. security re-scan（第一版可选）

并输出：

```json
{
  "verified_level": "L2",
  "passed_stages": ["patch_apply", "compile", "lint"],
  "failed_stage": "unit_test"
}
```

#### 5. Reflection / Self-healing Loop
如果失败：
- 总结失败原因
- 回填到 Fixer
- 最多重试 2~3 次
- 每次重试都发事件

### 今天结束时的交付物
- 一条真正可闭环的：
  - patch generation
  - patch apply
  - compile / lint
  - fail -> retry
- 这是整个项目最重要的可演示能力



---

# 新 Day 6：平台能力日

## 主题：LangGraph + Memory + MCP/Lazy Context + Issue Graph 可视化 + L2/L3/L4 骨架

### Day 6 的总目标

把目前“Day5 最小闭环”升级成 **真正的 Agent 平台骨架**。
这一天结束时，项目必须从“会修一个 snippet”进化为：

* **真实使用 LangGraph**
* 有 **短期记忆 / 长期结构化记忆 / 仓库级记忆**
* 有 **MCP 风格的 Resources + Tools 双通道**
* 有 **Lazy Context / token 预算**
* 前端能展示 **Issue Graph** 和 **token / context 使用**
* Verifier 不再只有 L1，而是补齐 **L2/L3/L4 的真实阶段骨架**

README 里这些能力本来就是目标：短期/长期/Repo-level Memory、MCP Server + Lazy Context、Issue Graph Planner、L1-L4 多阶段验证、Benchmark 和结构化评测，这一天就是把这些“写在 README 里的理想态”开始变成真实代码。([GitHub][2])

---

## 6.1 彻底把 `state_graph.py` 改造成 **LangGraph**

### 目标

当前代码虽然叫 `state_graph.py`，但仓库检索不到 `langgraph / StateGraph` 的实际使用；README 又明确把 LangGraph 写进了 Python AI Engine 技术栈。Day6 必须把这个“名不副实”的状态扭正。([GitHub][2])

### 要做的事

* 新增真正的 `LangGraph` 工作流定义：

  * `bootstrap`
  * `analyzer`
  * `planner`
  * `memory_retrieval`
  * `fixer`
  * `verifier`
  * `retry_router`
  * `reporter`
* 把当前 async generator 事件发射逻辑包进 LangGraph 节点内部
* 节点之间显式路由：

  * `no_fix_needed -> reporter`
  * `fixer_failed -> reporter`
  * `verifier_passed -> reporter`
  * `verifier_failed + retryable -> retry_router -> fixer`
  * `verifier_failed + retry_exhausted -> reporter`
* 给每个节点补统一输入/输出 contract

### 交付物

* `ai-engine-python/core/langgraph_flow.py`
* `ai-engine-python/core/state_graph.py` 改成 wrapper / adapter，而不是再手写流程
* `tests/test_langgraph_flow.py`

### 验收

* 可以打印出 LangGraph 节点图
* 一次正常请求能走完整图
* 一次失败请求能走 retry 分支
* 零问题样本能直接 `reporter`

---

## 6.2 记忆系统一次补齐：短期 / 长期 / 仓库级

### 目标

README 已经把记忆分成三层：短期记忆、长期结构化案例、Repo-level Memory；当前 main 里你已经有静态 `case_memory.py`，但 `short_term.py / repo_memory.py` 还没有真正进入主链路。Day6 要把这三层都落下去。([GitHub][2])

### 要做的事

#### A. 短期记忆 `memory/short_term.py`

存当前线程上下文：

* 最近一次 analyzer evidence
* 最近一次 patch
* 最近一次 verifier failure
* 最近一次 retry context
* 用户显式约束
* 当前 token 预算消耗

#### B. 长期记忆 `memory/case_memory.py`

把现有静态案例库升级为：

* `cases.jsonl` 或 `sqlite`/`duckdb`
* 结构字段固定：

  * `case_id`
  * `pattern`
  * `trigger_signals`
  * `before_code`
  * `after_code`
  * `diff`
  * `risk_note`
  * `success_rate`
  * `verified_level`
  * `accepted_by_human`
  * `tool_trace`
* 新增 `promote_verified_patch_to_case(...)`

  * 通过验证且人工确认的 patch，可回写为案例单元

#### C. 仓库级记忆 `memory/repo_memory.py`

记录：

* repo 风格偏好
* 常见 issue 类型
* 常见失败阶段
* 常见测试命令
* 常见被拒 patch pattern
* 关键 symbol / 模块风险区

### 交付物

* `memory/short_term.py`
* `memory/repo_memory.py`
* `memory/case_store.py`
* `data/cases/*.jsonl`
* `data/repo_profiles/*.json`

### 验收

* 新请求可读 repo profile
* retry 时能读到上一轮失败信息
* 通过验证的 patch 可以沉淀回 case store

---

## 6.3 MCP Server + Lazy Context System

### 目标

README 对 MCP 的要求非常明确：Resources + Tools 双通道，解决上下文过长，并且按 token budget 渐进加载。当前仓库没看到 `context_budget` 和前端 token 展示，所以 Day6 必须把这块从“README 理想”变成“真实接口”。([GitHub][2])

### 要做的事

#### A. Java Backend 做 MCP 风格资源接口

新增 `/internal/mcp/resources/*`

* `GET /repo-tree`
* `GET /file?path=...`
* `GET /schema`
* `GET /build-log-summary`
* `GET /test-summary`
* `POST /pr-diff/parse`

#### B. Java Backend 做 MCP 风格工具接口

新增 `/internal/mcp/tools/*`

* `POST /resolve-symbol`
* `POST /find-references`
* `POST /run-analyzer`
* `POST /run-sandbox`
* `POST /query-tests`

#### C. Python 侧 `core/context_budget.py`

实现：

* token 预算对象
* 先摘要再扩展
* 先 diff 周边，再 symbol graph，再全文件
* 预算不足时触发 `context_budget_exhausted`

#### D. `core/mcp_client.py`

让 Planner / Fixer / Verifier 可以按需拉：

* 文件片段
* impacted symbols
* build/test summary

### 前端必须新增

* 当前 token 使用量
* 当前 context source 列表
* 当前 context load stage
* Debug 下可看：

  * 拉了哪些资源
  * why this file / why this symbol

### 交付物

* `backend-java/.../mcp/*`
* `ai-engine-python/core/context_budget.py`
* `ai-engine-python/core/mcp_client.py`
* 前端 token/context 面板

### 验收

* 处理超长上下文时不再把整文件直接塞进模型
* 前端能实时看到 token / context 消耗
* Planner/Fixer/Verifier 至少有一次真实走 MCP 拉资源

---

## 6.4 Issue Graph 升级到“可视化 + 可交互”

### 目标

你明确要求不仅要有 Issue Graph，还要“甚至做到可视化”。现在主链路里已经会发 `issue_graph_built`，但前端当前没有 Issue Graph 展示。Day6 必须补齐。([GitHub][3])

### 要做的事

* 标准化 `issue_graph` 结构：

  * nodes
  * edges
  * node_type
  * severity
  * file_path
  * symbol_refs
  * depends_on
  * conflicts_with
  * fix_scope
* 前端新增 `IssueGraphPanel.vue`

  * 用 `vis-network` / `cytoscape.js`
* 点击节点后联动：

  * 右侧详情
  * repair plan item
  * patch diff
  * verifier result
* 支持两种视图：

  * 问题依赖图
  * 文件 / symbol 影响图

### 验收

* 页面里能看到图
* 点击某个 issue 节点能看：

  * 关联 symbol
  * 修复策略
  * patch 目标
  * verifier 结果

---

## 6.5 Verifier 升级到真实 L2 / L3 / L4 骨架

### 目标

你要求的是完整 L1-L4，而不是 compile-only。Day5 已经有 L1 基线，Day6 必须把 L2/L3/L4 的真实阶段接上。README 也把 L1-L4 定义得很清楚。([GitHub][2])

### 要做的事

* `tools/lint_runner.py`

  * Java 优先接 `checkstyle` 或 `spotbugs` 最小版本
* `tools/test_runner.py`

  * 先支持：

    * snippet 回归测试
    * Maven/Gradle test 命令
    * 指定测试类
* `tools/security_rescan.py`

  * 先走 Semgrep rescan
* `agents/verifier_agent.py`

  * 真正产出：

    * L1 = patch_apply + compile
    * L2 = + lint
    * L3 = + test
    * L4 = + security_rescan
* `summary.verified_level` 和前端结果卡要与 L1-L4 严格对齐

### 验收

* 至少一条样本能到 L2
* 至少一条样本能到 L3
* 至少一条样本能跑 L4 rescan
* 失败时明确知道停在哪个 stage

---

## 6.6 Day 6 验收标准

Day 6 结束时，必须满足：

* 真的用了 LangGraph
* 有短期 / 长期 / 仓库级记忆三层
* 有 MCP 资源/工具接口
* 有 Lazy Context 和 token 展示
* 有 Issue Graph 可视化
* Verifier 至少能真实跑到 L2 / L3 / L4 骨架
* 零问题样本、正常修复样本、重试样本都还能稳定收口

---

# 新 Day 7：能力量化与训练日

## 主题：LLM 接入 + Benchmark + Failure Taxonomy + Skills/Tool Calling + SWIFT/VERL + 最终前端打磨

### Day 7 的总目标

Day7 不再是“补点 UI + 录视频”。
要改成：**把这个 Agent 变成可训练、可评测、可展示、可持续迭代的系统。**

README 里对 Benchmark / Failure Taxonomy / 混合扫描引擎 / SWIFT/LoRA 已经给了方向；你额外要求的 VERL、tool calling 召回率、训练集/验证集/测试集评测，就统一放在 Day7。([GitHub][2])

---

## 7.1 真正把 LLM 接进主链路

### 目标

README 明确要求“AST + 确定性分析器 + LLM 协同”，但当前主链路更像规则 + case memory + fallback，还不够“LLM 中枢化”。Day7 必须补真模型接入。([GitHub][2])

### 要做的事

* 新增 `llm/clients.py`

  * OpenAI / Qwen / DeepSeek adapter
* 新增 `prompts/planner_prompt.py / fixer_prompt.py / verifier_reflect_prompt.py`
* Planner 支持两种模式：

  * deterministic only
  * deterministic + llm_assist
* Fixer 支持三层：

  * case adapt
  * template
  * llm generation
* Retry 时必须带上：

  * failed_stage
  * stderr_summary
  * previous_patch
  * selected_context
* 所有 LLM 调用必须产出：

  * token_in
  * token_out
  * latency_ms
  * prompt_name
  * model_name

### 验收

* 可切换开启/关闭 LLM
* 至少一条 case 在开启 LLM 后 patch 更优
* 前端能显示每轮模型调用 token

---

## 7.2 训练与微调：SWIFT + VERL 双轨

### 目标

你要的不是“调用 API”，而是要能做迁移学习微调。README 已经写了 SWIFT/LoRA；你额外要求 VERL，那 Day7 必须补成训练平台。([GitHub][2])

### 要做的事

#### A. SWIFT/SFT 训练轨

* 训练数据来源：

  * 历史结构化案例
  * verified patch
  * replay 的 planner/fixer trace
* 数据格式：

  * `instruction`
  * `input_context`
  * `expected_patch`
  * `expected_verification`
* 目录：

  * `training/swift/data/train.jsonl`
  * `training/swift/data/val.jsonl`
  * `training/swift/data/test.jsonl`
* 提供：

  * `train_swift.sh`
  * `eval_swift.sh`

#### B. VERL / tool-aware 训练轨

* 把 tool trace 变成训练样本：

  * 哪一步调用了 analyzer
  * 哪一步拉了 file fragment
  * 哪一步运行 verifier
* 指标：

  * tool choice accuracy
  * tool argument accuracy
  * tool calling recall
* 提供：

  * `training/verl/config/*.yaml`
  * `training/verl/run_verl.sh`

### 验收

* 至少跑通一次 smoke finetune
* 至少产出一份 eval 报告
* 即使不要求当日训出强模型，也必须把“能训、能评、能复现实验”的平台搭起来

---

## 7.3 Benchmark + Failure Taxonomy + 训练/验证/测试评测

### 目标

这块要直接对应你的第 6 条和第 8 条：量化模型能力、量化 tool calling 召回率，而不是只看“通不通”。README 也明确要求 Golden Dataset、Failure Taxonomy 和分阶段指标。([GitHub][2])

### 要做的事

* 新增：

  * `benchmark/golden_cases/`
  * `benchmark/splits/train.json`
  * `benchmark/splits/val.json`
  * `benchmark/splits/test.json`

* `run_eval.py` 输出：

  * detection precision / recall
  * issue_graph quality
  * repair_plan quality
  * patch generation rate
  * patch apply rate
  * L1/L2/L3/L4 pass rate
  * final verified patch rate
  * retry avg
  * latency avg
  * token cost
  * tool calling recall / precision

* `failure_taxonomy.py`

  * F1 detection miss
  * F2 wrong patch
  * F3 compile error
  * F4 lint fail
  * F5 test fail
  * F6 security rescan fail
  * F7 context insufficient
  * F8 wrong tool selection

* 指标额外补：

  * F2 score
  * per-bug-type confusion
  * per-stage success funnel

### 验收

* 能一键跑评测
* 能输出 train / val / test 三份报告
* 能区分模型问题、工具问题、上下文问题、验证问题

---

## 7.4 Skills / Tooling 能力与召回率

### 目标

你明确要求要有 skills 能力，并量化 tool calling 召回率。Day7 必须把这一层从“散落的工具函数”变成“可观测工具系统”。

### 要做的事

* 统一工具注册表：

  * `sandbox_run`
  * `file_read`
  * `symbol_lookup`
  * `patch_apply`
  * `compile_java`
  * `lint_java`
  * `run_tests`
  * `security_rescan`
* 每次 tool call 记录：

  * tool_name
  * args
  * success
  * latency
  * selected_by
  * expected_tool
* 新增 `tool_eval.py`

  * tool recall
  * tool precision
  * wrong-tool rate
  * arg error rate

### 验收

* 任一 patch 修复样本都能导出 tool trace
* Benchmark 报告里必须出现 tool calling recall

---

## 7.5 前端最终态

### 目标

你第 10 条说得很明确：前端要“完美展现数据，实现交互，左侧能展示历史记录”。现在你愿意先不继续纠结 UI，但 Day7 必须收成真正的产品态。

### 要做的事

* 左栏：

  * 真实历史任务列表
  * 支持回看
* 中栏：

  * 聊天式交互保留
  * 可切换 snippet / repo / PR 模式
* 右栏：

  * 可读阶段过程
  * Debug 下看 payload
* 新增标签页：

  * `Patch Diff`
  * `Issue Graph`
  * `Verification`
  * `Memory`
  * `Tool Trace`
  * `Benchmark`
* 实时展示：

  * token 使用
  * 模型名称
  * 当前 context 来源
  * verified level
  * failure taxonomy bucket

### 验收

* 左栏历史可回看
* 中栏可做聊天式提交
* 右栏能切不同详情
* 至少能在 UI 看到：

  * Issue Graph 图
  * Patch Diff
  * L1-L4
  * token
  * tool trace

---

## 7.6 新的 Day 7 验收标准

Day 7 结束时，必须满足你 11 条诉求里的“未实现部分”：

* 有真实 LLM 接入，不再只是规则/模板
* 有 SWIFT + VERL 训练/eval 脚本
* 有 train/val/test 评测
* 有 tool calling recall
* 有 failure taxonomy 和 F2 等指标
* 有真实的 repo-aware / PR-aware / MCP + Lazy Context
* 有 token 与 context 可视化
* 有 Issue Graph 可视化
* 有历史任务 UI
* 有 LangGraph

---
