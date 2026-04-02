# Sentinel-CR Day 2 API Contract

## 1. 文档目标

本文定义 Sentinel-CR 在 **Day 2 Analyzer 阶段** 的契约边界，覆盖：

- 前端 -> Java Backend 的公开接口
- Java Backend -> Python Engine 的内部接口
- Python Engine 内部 Analyzer 模块之间的输入输出格式
- 事件流与最终 `task.result` 的结构约束

目标不是重新设计 Day 1 已经跑通的链路，而是在 **不破坏现有 `/api/reviews` + SSE 主链路** 的前提下，把 Day 2 的 Tree-sitter、Symbol Graph、Semgrep 能力接进去。

---

## 2. 设计原则

1. **向后兼容 Day 1**
   - 不修改前端当前使用的 URL：
     - `POST /api/reviews`
     - `GET /api/reviews/{taskId}`
     - `GET /api/reviews/{taskId}/events`
   - 不修改 Python 内部入口：
     - `POST /internal/reviews/run`

2. **Analyzer 输出必须结构化**
   - Day 2 不允许只返回一段自然语言总结。
   - 必须返回 `issues`、`symbols`、`context_summary` 等可消费数据。

3. **事件流优先展示结构化状态，不直接暴露 CoT**
   - 前端消费的是事件和摘要。
   - 每个事件 `payload` 必须稳定、短小、可解析。

4. **LLM 暂不介入 Day 2 的核心结果生成**
   - Day 2 的主目标是构建“确定性证据层”。
   - 允许保留 Fixer/Verifier 字段占位，但不要求在 Day 2 产出 patch。

---

## 3. 当前公开接口（保留不变）

## 3.1 创建评审任务

### Request

`POST /api/reviews`

```json
{
  "codeText": "public class Demo { ... }",
  "language": "java",
  "sourceType": "snippet"
}
```

### Response

```json
{
  "taskId": "rev_20260402103000_ab12cd",
  "status": "CREATED",
  "message": "review task created"
}
```

### 约束

- `language`：Day 2 仍固定为 `java`
- `sourceType`：Day 2 仍固定为 `snippet`
- 非法值由 Java Backend 拒绝，返回 `400`

---

## 3.2 查询任务详情

### Request

`GET /api/reviews/{taskId}`

### Response

```json
{
  "taskId": "rev_20260402103000_ab12cd",
  "status": "COMPLETED",
  "createdAt": "2026-04-02T10:30:00Z",
  "updatedAt": "2026-04-02T10:30:02Z",
  "result": {
    "summary": "day2 analyzer completed",
    "engine": "python",
    "analyzer": {
      "language": "java",
      "issues_count": 2,
      "symbols_count": 6,
      "classes_count": 1,
      "methods_count": 3
    },
    "issues": [],
    "symbols": [],
    "contextSummary": {}
  },
  "errorMessage": null
}
```

### 约束

- `result` 必须是可序列化 JSON 对象
- Day 2 产物应至少包含：
  - `summary`
  - `engine`
  - `analyzer`
  - `issues`
  - `symbols`
  - `contextSummary`

---

## 3.3 SSE 事件流

### Request

`GET /api/reviews/{taskId}/events`

### SSE data payload

每条事件的数据体都是一个 JSON 对象：

```json
{
  "taskId": "rev_20260402103000_ab12cd",
  "eventType": "semgrep_scan_completed",
  "message": "semgrep scan completed",
  "timestamp": "2026-04-02T10:30:01.322Z",
  "sequence": 5,
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "semgrep",
    "issuesCount": 2,
    "ruleset": "auto"
  }
}
```

### 约束

- `taskId`：字符串，必填
- `eventType`：字符串，必填，使用 snake_case
- `message`：用户可读短句，必填
- `timestamp`：ISO-8601 UTC 时间戳
- `sequence`：同一个 task 内严格单调递增
- `status`：枚举 `CREATED | RUNNING | COMPLETED | FAILED`
- `payload`：对象，可为空对象，禁止为 `null`

---

## 4. Java -> Python 内部接口（保留 URL，不扩协议方向）

## 4.1 Internal Review Run

`POST /internal/reviews/run`

### Request

```json
{
  "taskId": "rev_20260402103000_ab12cd",
  "codeText": "public class Demo { ... }",
  "language": "java",
  "sourceType": "snippet",
  "metadata": {
    "engineMode": "python"
  }
}
```

### Response

- `Content-Type: application/x-ndjson`
- 每一行是一条 JSON 事件

```json
{"taskId":"rev_20260402103000_ab12cd","eventType":"analysis_started","message":"python engine started state graph","status":"RUNNING","payload":{"source":"python-engine","stage":"bootstrap_state"}}
{"taskId":"rev_20260402103000_ab12cd","eventType":"ast_parsing_completed","message":"ast parsing completed","status":"RUNNING","payload":{"source":"python-engine","stage":"ast","classesCount":1,"methodsCount":3}}
{"taskId":"rev_20260402103000_ab12cd","eventType":"review_completed","message":"review completed","status":"COMPLETED","payload":{"source":"python-engine","stage":"finalize_result","result":{"summary":"day2 analyzer completed"}}}
```

---

## 5. Python Engine 内部状态契约

## 5.1 `InternalReviewRunRequest`

```python
class InternalReviewRunRequest(BaseModel):
    task_id: str           # alias taskId
    code_text: str         # alias codeText
    language: str
    source_type: str       # alias sourceType
    metadata: dict[str, Any] = {}
```

---

## 5.2 `EngineState` Day 2 扩展版

Day 1 已有字段保留，Day 2 增加 `symbols`、`context_summary`、`analyzer_summary`、`diagnostics`：

```python
class EngineState(BaseModel):
    task_id: str
    code_text: str
    language: str

    issues: list[Issue] = []
    symbols: list[SymbolNode] = []
    context_summary: dict[str, Any] = {}
    analyzer_summary: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []

    issue_graph: list[dict[str, Any]] = []
    patch: dict[str, Any] | None = None
    verification_result: dict[str, Any] | None = None
    events: list[dict[str, Any]] = []
    retry_count: int = 0
```

### 说明

- `issues`：Semgrep 标准化问题列表
- `symbols`：AST + Symbol Graph 的统一摘要
- `context_summary`：对代码结构的统计摘要
- `analyzer_summary`：Analyzer 聚合指标，用于 UI 和 `task.result`
- `diagnostics`：非致命告警，如 parser recover、semgrep 不可用等
- `issue_graph` / `patch` / `verification_result`：Day 2 允许为空，为 Day 3+ 预留

---

## 6. Analyzer 模块契约

## 6.1 `ast_parser.py`

### 目标
输入 Java 代码字符串，输出 AST 结构摘要，不返回 Tree-sitter 原始节点对象。

### Function

```python
def parse_java_code(code_text: str) -> AstParseResult: ...
```

### 输出结构

```json
{
  "language": "java",
  "classes": [
    {
      "name": "UserService",
      "modifiers": ["public"],
      "startLine": 1,
      "endLine": 40,
      "fields": [
        {
          "name": "userRepo",
          "type": "UserRepository",
          "modifiers": ["private", "final"],
          "line": 3
        }
      ],
      "methods": [
        {
          "name": "findUser",
          "signature": "User findUser(String id)",
          "returnType": "User",
          "parameters": [
            {"name": "id", "type": "String"}
          ],
          "modifiers": ["public"],
          "startLine": 6,
          "endLine": 12,
          "bodyStartLine": 7,
          "bodyEndLine": 11
        }
      ]
    }
  ],
  "imports": [
    "java.util.Optional"
  ],
  "errors": []
}
```

### 约束

- 行号从 `1` 开始
- 必须能提取：
  - 类名
  - 方法签名
  - 字段
  - imports
  - 代码块边界
- `errors` 为 parser 恢复信息，禁止抛弃

---

## 6.2 `symbol_graph.py`

### 目标
基于 AST 结果和源码文本，抽取最小可用 Symbol Graph，支撑 Day 3 Planner 的影响范围判断。

### Function

```python
def build_symbol_graph(code_text: str, ast_result: AstParseResult) -> SymbolGraphResult: ...
```

### 输出结构

```json
{
  "symbols": [
    {
      "symbolId": "class:UserService",
      "kind": "class",
      "name": "UserService",
      "owner": null,
      "line": 1,
      "signature": null
    },
    {
      "symbolId": "method:UserService.findUser(String)",
      "kind": "method",
      "name": "findUser",
      "owner": "UserService",
      "line": 6,
      "signature": "User findUser(String id)"
    }
  ],
  "relations": [
    {
      "type": "class_has_method",
      "from": "class:UserService",
      "to": "method:UserService.findUser(String)"
    },
    {
      "type": "method_calls",
      "from": "method:UserService.findUser(String)",
      "to": "method:UserRepository.findById(String)",
      "line": 8,
      "confidence": "medium"
    }
  ],
  "summary": {
    "classesCount": 1,
    "methodsCount": 1,
    "fieldsCount": 1,
    "callEdgesCount": 1,
    "variableRefsCount": 0
  }
}
```

### 约束

- 第一版必须覆盖：
  - `class -> methods`
  - `method -> called methods`
  - `variable -> usage`（可用简化版）
- 允许外部调用目标只有名称，没有完整签名
- `relations[].type` 固定使用枚举字符串，不要写自然语言

---

## 6.3 `semgrep_runner.py`

### 目标
运行 Semgrep，对 Java 代码片段输出标准化 issue 列表。

### Function

```python
def run_semgrep(code_text: str, language: str = "java") -> SemgrepResult: ...
```

### 输出结构

```json
{
  "issues": [
    {
      "issueId": "SG-1",
      "issueType": "java.lang.security.audit.sql-injection",
      "severity": "HIGH",
      "ruleId": "java.lang.security.audit.sql-injection",
      "message": "Detected string concatenation in SQL query",
      "line": 18,
      "startLine": 18,
      "endLine": 18,
      "column": 24,
      "engine": "semgrep",
      "category": "security",
      "snippet": "String sql = \"select ...\" + userInput;"
    }
  ],
  "summary": {
    "issuesCount": 1,
    "ruleset": "auto",
    "engine": "semgrep"
  },
  "errors": []
}
```

### 约束

- Day 2 的 `severity` 统一归一为：`LOW | MEDIUM | HIGH | CRITICAL`
- 统一字段名：
  - `issueType`
  - `severity`
  - `line`
  - `message`
  - `ruleId`
- 如果 Semgrep 在本地不可用：
  - 不直接让整个任务失败
  - 返回 `issues=[]`
  - 同时把错误写入 `errors` 和 `diagnostics`

---

## 6.4 `analyzer_pipeline.py`（建议新增）

### Function

```python
def run_day2_analyzer(code_text: str, language: str = "java") -> Day2AnalyzerResult: ...
```

### 输出结构

```json
{
  "issues": [],
  "symbols": [],
  "contextSummary": {
    "imports": [],
    "classes": [],
    "methods": [],
    "fields": []
  },
  "analyzerSummary": {
    "language": "java",
    "classesCount": 1,
    "methodsCount": 3,
    "fieldsCount": 1,
    "symbolsCount": 6,
    "issuesCount": 2,
    "callEdgesCount": 2,
    "engines": ["tree-sitter", "semgrep"]
  },
  "diagnostics": []
}
```

### 说明

这是 Day 2 最推荐的聚合边界：

- `ast_parser.py`：只管 AST
- `symbol_graph.py`：只管图关系
- `semgrep_runner.py`：只管规则问题
- `analyzer_pipeline.py`：统一归一输出，供 `state_graph.py` 调用

---

## 7. `task.result` 最终结构契约

当 Python Engine 发出 `review_completed` 时，`payload.result` 和 Java 持久化到 `ReviewTask.result` 的对象必须一致。

### 目标结构

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

### 约束

- `summary` 必填
- `engine` 必填，固定为 `python`
- `issues` 必填，始终为数组
- `symbols` 必填，始终为数组
- `contextSummary` 必填，始终为对象
- `diagnostics` 必填，始终为数组
- 不把完整源码重复塞进 `result`

---

## 8. 失败契约

## 8.1 可恢复失败

例如：

- Semgrep 未安装
- 某条规则执行失败
- AST 存在 recoverable parse error

处理规则：

- 任务整体仍可 `COMPLETED`
- 在 `diagnostics` 写入详情
- 事件流中发送对应失败/告警事件
- `result.summary` 仍可为 analyzer completed，但需体现降级运行

### 诊断项示例

```json
{
  "source": "semgrep",
  "level": "warning",
  "code": "SEMGREP_UNAVAILABLE",
  "message": "semgrep executable not found, fallback to empty issues"
}
```

---

## 8.2 不可恢复失败

例如：

- 输入为空
- Python Engine 内部异常导致流水线中断
- 结果无法序列化

处理规则：

- 发送 `review_failed`
- Java 任务状态变为 `FAILED`
- `errorMessage` 写入简短错误说明

---

## 9. 向 Day 3 的兼容点

Day 2 文档必须给 Day 3 预留接口，不要把结构写死成“只有 analyzer 才会使用”。

### 已预留字段

- `issue_graph`
- `patch`
- `verification_result`
- `retry_count`
- `relatedSymbols` / `relations`
- `contextSummary`

### 兼容建议

- `issueId` 在 Day 2 就生成，避免 Day 3 再做二次编号
- `symbolId` 在 Day 2 就稳定生成，避免 Planner 重建映射
- `issues` 中尽量保留 `snippet`、`category`、`engine`

---

## 10. Day 2 验收标准

满足以下条件，可认为契约实现完成：

1. 前端发起 `POST /api/reviews` 后，链路仍可跑通
2. SSE 中能看到细粒度 Analyzer 事件
3. `GET /api/reviews/{taskId}` 的 `result` 含有：
   - `issues`
   - `symbols`
   - `contextSummary`
   - `analyzer`
4. 输入一段 Java 代码后：
   - 能提取类/方法/import 摘要
   - 能提取至少一个 call edge 或 class->method 关系
   - 对典型危险代码能得到至少 1 条规则问题
5. 失败时能返回可诊断信息，而不是无结构异常文本
