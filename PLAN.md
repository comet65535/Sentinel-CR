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

## ✅ Day 6：Lazy Context System + Repo-level Memory + PR 分析入口

### 当天目标
今天要做的是把系统从“修一段代码”提升到“开始像真实工程工具”。

### 要做的事情

#### 1. `context_budget.py`
实现最小版本的 Lazy Context：
- 默认只取问题附近上下文
- 如果修复失败，再扩展更多代码
- 优先返回 AST summary / symbol summary，而不是整段全文

#### 2. MCP Resource 获取策略
Java MCP Server 提供：
- 文件树
- 单文件内容
- schema / test summary
- PR diff

Python 侧按需请求，而不是一次性拉全量内容。

#### 3. `repo_memory.py`
加入最小仓库级记忆：
- 某个 repo 习惯的命名风格
- 常见的风险区域
- 历史被拒绝 patch 模式

#### 4. PR 级入口
支持输入：
- Git 仓库链接
- PR 链接
- diff 文本

然后：
- 先解析 diff
- 再分析 impacted symbols
- 最后只在受影响区域做 repair planning

### 今天结束时的交付物
- 项目不再局限于“单代码框输入”
- 能讲出自己支持 repo-aware / PR-aware workflow
- 上下文获取策略从“全量灌输”升级为“按需取证”

---

## ✅ Day 7：Benchmark + Failure Taxonomy + UI 打磨 + 录屏

### 当天目标
把项目从“能跑”打磨到“能展示、能量化、能说服别人”。

### 要做的事情

#### 1. `benchmark/golden_cases/`
构造 10 个最有代表性的 Java 样本：
- NullPointer
- SQL Injection
- N+1 Query
- Concurrency Race
- Bad Exception Handling
- Missing Resource Close
- Wrong API Usage
- Missing Validation
- Improper Logging
- Regression-prone Refactor

#### 2. `run_eval.py`
一键跑批评估，输出：
- detection rate
- patch generation rate
- apply pass rate
- compile pass rate
- lint pass rate
- test pass rate
- verified patch rate
- avg retries
- avg latency

#### 3. `failure_taxonomy.py`
给失败结果做分类：
- F1 detection miss
- F2 wrong patch
- F3 compile error
- F4 test fail
- F5 regression introduced
- F6 insufficient context

#### 4. 前端 UI 打磨
至少完成：
- 事件时间轴
- 红绿 Diff
- Verified Level 标签
- Debug Mode 开关
- 失败原因展示

#### 5. 演示视频
准备一个 3 分钟稳定 Demo：
1. 输入有问题的 Java 代码
2. 展示系统事件流
3. 展示 patch 和验证等级
4. 展示 benchmark 结果图

### 今天结束时的交付物
- 一套可展示的完整系统
- 一组可量化的评估结果
- 一段足够稳的演示链路

---

## 📌 每天都要注意的工程原则

### 1. 不要让 LLM 做它不擅长的事情
- 能用分析器确定的，就不要让 LLM 猜
- 能用规则检出的，就不要用 Prompt 试探

### 2. 不要让 patch 直接出现在用户面前
- 一定要先验证
- 最少也要 compile
- 最好给出 Verified Level

### 3. 不要把上下文一股脑塞进模型
- 先摘要
- 再按需扩展
- 要有 budget 意识

### 4. 不要只统计成功率
- 要知道失败发生在哪一步
- 要能用 failure taxonomy 指导优化

### 5. 不要过早把架构做得过于花哨
这 7 天里，最重要的不是“多智能体数量”，而是：
- Analyzer 可靠
- Planner 清晰
- Fixer 可控
- Verifier 真能跑
- Benchmark 能量化

---

## 🌟 这份计划相较旧版本的关键提升总结

这次计划相较之前，做了这些本质升级：

### 升级 1：补上了 Issue Graph Planner
旧版本里只有“有问题 -> 生成 patch”，缺乏修复依赖关系和冲突管理。  
现在增加了问题图建模，系统不再盲修。

### 升级 2：Verifier 从单阶段变成多阶段
旧版本主要强调 compile。  
现在明确拆成 patch apply / compile / lint / test / rescan，输出可量化验证等级。

### 升级 3：RAG 从文档检索升级为案例经验库
旧版本里经验更像“规范文本”。  
现在变成带 before/after/diff/success_rate 的结构化修复经验。

### 升级 4：引入 Lazy Context
旧版本默认假设上下文可以直接拿全。  
现在加入上下文预算和按需加载，更接近真实仓库场景。

### 升级 5：UI 从展示结果升级为展示系统状态
旧版本偏“最后给报告”。  
现在强调事件流、验证等级、调试面板，产品感更强。

### 升级 6：评测从打分升级为失败分类
旧版本有 benchmark 思路，但不够可诊断。  
现在加入 failure taxonomy，后续优化方向会非常清晰。

---

## 🏁 最后一句

这 7 天计划真正要做成的，不是一个“看起来很像 AI 的项目”，而是一个：

> **能发现问题、能生成补丁、能验证补丁、能解释失败、能持续迭代的工程化 Code Repair Agent**
