# Sentinel-CR Event Schema

## 1. 文档目标

本文定义 Sentinel-CR 事件流的统一标准，适用于：

- Java Backend 对前端输出的 SSE 事件
- Python Engine 对 Java Backend 输出的 NDJSON 事件
- Day 2 及后续阶段新增事件类型

所有事件都必须遵守同一套 envelope 结构和命名规则。

---

## 2. 统一事件 Envelope

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
    "issuesCount": 2
  }
}
```

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `taskId` | string | 是 | 任务 ID |
| `eventType` | string | 是 | 事件类型，snake_case |
| `message` | string | 是 | 用户可读短信息 |
| `timestamp` | string | 是 | ISO-8601 UTC 时间戳 |
| `sequence` | number | 是 | task 内递增序号 |
| `status` | string | 是 | `CREATED \| RUNNING \| COMPLETED \| FAILED` |
| `payload` | object | 是 | 事件附加数据，空对象也要传 |

---

## 3. 基本规则

### 3.1 命名规则

- 统一使用 `snake_case`
- 推荐后缀：
  - `_started`
  - `_completed`
  - `_failed`
  - `_warning`

### 3.2 状态规则

- `CREATED`：任务刚创建
- `RUNNING`：中间阶段事件
- `COMPLETED`：任务最终完成
- `FAILED`：任务最终失败

### 3.3 终态规则

单个 task 只允许一个终态事件：

- `review_completed`
- `review_failed`

### 3.4 事件顺序规则

同一 task 中：

- `sequence` 必须严格递增
- `timestamp` 应与事件真实生成时间一致
- 前端展示顺序以 `sequence` 为准

---

## 4. Day 1 保留事件

这些事件已经存在，Day 2 必须兼容。

## 4.1 `task_created`

### 触发方
Java Backend

### status
`CREATED`

### payload
```json
{
  "source": "backend",
  "engine": "python"
}
```

---

## 4.2 `analysis_started`

### 触发方
Python Engine

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "bootstrap_state"
}
```

---

## 4.3 `review_completed`

### 触发方
Python Engine

### status
`COMPLETED`

### payload
```json
{
  "source": "python-engine",
  "stage": "finalize_result",
  "result": {
    "summary": "day2 analyzer completed"
  }
}
```

---

## 4.4 `review_failed`

### 触发方
Java Backend 或 Python Engine

### status
`FAILED`

### payload
```json
{
  "source": "backend",
  "stage": "engine_error",
  "errorType": "python_unreachable",
  "error": "connection refused"
}
```

---

## 5. Day 2 新增事件目录

## 5.1 `ast_parsing_started`

### 目的
标记 Tree-sitter AST 解析开始。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "ast",
  "language": "java"
}
```

---

## 5.2 `ast_parsing_completed`

### 目的
输出 AST 摘要统计。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "ast",
  "language": "java",
  "classesCount": 1,
  "methodsCount": 3,
  "fieldsCount": 1,
  "importsCount": 2,
  "hasParseErrors": false
}
```

### 可选字段

- `parseErrorsCount`
- `diagnostics`

---

## 5.3 `symbol_graph_started`

### 目的
标记 Symbol Graph 构建开始。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "symbol_graph"
}
```

---

## 5.4 `symbol_graph_completed`

### 目的
输出图关系摘要。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "symbol_graph",
  "symbolsCount": 6,
  "callEdgesCount": 2,
  "variableRefsCount": 4
}
```

---

## 5.5 `semgrep_scan_started`

### 目的
标记 Semgrep 扫描开始。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "semgrep",
  "ruleset": "auto"
}
```

---

## 5.6 `semgrep_scan_completed`

### 目的
输出规则扫描摘要。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "semgrep",
  "ruleset": "auto",
  "issuesCount": 2,
  "severityBreakdown": {
    "LOW": 0,
    "MEDIUM": 1,
    "HIGH": 1,
    "CRITICAL": 0
  }
}
```

---

## 5.7 `semgrep_scan_warning`

### 目的
Semgrep 可恢复失败或降级运行。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "semgrep",
  "code": "SEMGREP_UNAVAILABLE",
  "message": "semgrep executable not found, fallback to empty issues"
}
```

---

## 5.8 `analyzer_completed`

### 目的
标记 Day 2 Analyzer 聚合结束。

### status
`RUNNING`

### payload
```json
{
  "source": "python-engine",
  "stage": "analyzer_pipeline",
  "analyzerSummary": {
    "language": "java",
    "classesCount": 1,
    "methodsCount": 3,
    "fieldsCount": 1,
    "symbolsCount": 6,
    "issuesCount": 2,
    "callEdgesCount": 2,
    "engines": ["tree-sitter", "semgrep"]
  }
}
```

### 说明

- `analyzer_completed` 不是终态事件
- 后面仍必须发送 `review_completed` 或 `review_failed`

---

## 6. 失败事件建议

## 6.1 `analysis_failed`

### 用途
Python Engine 内部阶段失败，但尚未回到 Java 统一封装前。

### status
`FAILED`

### payload
```json
{
  "source": "python-engine",
  "stage": "ast",
  "errorType": "parser_exception",
  "error": "unexpected node type"
}
```

### 建议

Day 2 可以不单独实现该事件，只要最终会转成 `review_failed`。

---

## 7. `payload` 字段约束

### 7.1 必须包含的最小上下文

Day 2 中间事件的 `payload` 推荐至少包含：

- `source`
- `stage`

### 7.2 不应直接放入的内容

为了防止事件过大，不应在中间事件里放：

- 完整源码全文
- 全量 AST 原始树
- 超长 diff
- 不可序列化对象

### 7.3 适合放在 payload 的内容

- 计数信息
- 简短摘要
- 小型 diagnostics
- 最终 result（只在 `review_completed` 中）

---

## 8. 前端消费规则

前端按以下原则消费事件：

1. 用 `sequence` 排序
2. 用 `eventType` 决定 UI 文案和图标
3. 用 `status` 决定颜色态：
   - `CREATED` -> 中性
   - `RUNNING` -> 蓝色/进行中
   - `COMPLETED` -> 绿色
   - `FAILED` -> 红色
4. 用 `payload` 做补充展示

### 推荐展示文案映射

| eventType | UI 文案 |
|---|---|
| `task_created` | 任务已创建 |
| `analysis_started` | 分析已开始 |
| `ast_parsing_started` | 正在解析 AST |
| `ast_parsing_completed` | AST 解析完成 |
| `symbol_graph_started` | 正在构建符号图 |
| `symbol_graph_completed` | 符号图构建完成 |
| `semgrep_scan_started` | 正在运行 Semgrep |
| `semgrep_scan_completed` | Semgrep 扫描完成 |
| `semgrep_scan_warning` | Semgrep 降级运行 |
| `analyzer_completed` | Analyzer 聚合完成 |
| `review_completed` | 任务完成 |
| `review_failed` | 任务失败 |

---

## 9. 示例事件流

```text
task_created
analysis_started
ast_parsing_started
ast_parsing_completed
symbol_graph_started
symbol_graph_completed
semgrep_scan_started
semgrep_scan_completed
analyzer_completed
review_completed
```

### 失败场景示例

```text
task_created
analysis_started
ast_parsing_started
ast_parsing_completed
semgrep_scan_started
semgrep_scan_warning
analyzer_completed
review_completed
```

或

```text
task_created
analysis_started
ast_parsing_started
review_failed
```

---

## 10. 版本兼容策略

### v0.1（Day 1）
- `task_created`
- `analysis_started`
- `analysis_completed`
- `review_completed`
- `review_failed`

### v0.2（Day 2）
- 保留 Day 1 事件
- 新增细粒度 Analyzer 事件
- 推荐以 `analyzer_completed` 替代 Day 1 的粗粒度 `analysis_completed`

### 兼容建议

Day 2 过渡期可以同时发送：

- `analysis_started`
- `analyzer_completed`
- `review_completed`

这样前端旧逻辑不会断，新 UI 也能消费更多信息。

---

## 11. 验收标准

满足以下条件，可认为事件标准落地完成：

1. 所有事件都符合统一 envelope
2. 中间阶段事件都使用 `RUNNING`
3. 终态事件只出现一次
4. `payload` 始终是对象，不是 `null`
5. 前端可以仅依赖 `eventType + status + payload` 做展示
