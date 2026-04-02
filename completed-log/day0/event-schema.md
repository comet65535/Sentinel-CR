```
# Sentinel-CR Event Schema (Day0)

## 1. 目标

本文档定义 Sentinel-CR 的统一事件协议。

统一事件协议是后续：
- 前端时间轴展示
- Debug Mode
- 多阶段验证
- Benchmark
- 重试闭环

的基础。

Day0 即使只做 mock，也必须严格遵守这份协议。

---

## 2. 统一事件 JSON 结构

```json
{
  "taskId": "rev_20260401_001",
  "eventType": "analysis_started",
  "message": "analysis started",
  "timestamp": "2026-04-01T20:10:00",
  "sequence": 2,
  "status": "RUNNING",
  "payload": {}
}
```

------

## 3. 字段定义

- `taskId`: 任务唯一标识
- `eventType`: 事件类型
- `message`: 给用户看的简短说明
- `timestamp`: ISO-8601 时间字符串
- `sequence`: 递增序号，从 1 开始
- `status`: 当前任务状态
- `payload`: 扩展字段，Day0 可为空对象

------

## 4. 字段约束

## 4.1 taskId

- 必填
- 同一个事件流中的所有事件必须属于同一个 taskId

## 4.2 eventType

- 必填
- 必须来自已定义枚举或未来扩展枚举
- 前端应基于它做不同展示

## 4.3 message

- 必填
- 面向用户与调试人员
- 必须简短清晰，不写大段废话

## 4.4 timestamp

- 必填
- 使用 ISO-8601 格式
- 由后端统一生成

## 4.5 sequence

- 必填
- 从 1 开始递增
- 前端以此排序，不依赖到达顺序

## 4.6 status

- 必填
- 取值必须属于任务状态枚举

## 4.7 payload

- 必填
- Day0 即使没有额外信息，也返回空对象 `{}``
- 后续用于承载 analyzer / patch / verifier 详情

------

## 5. Day0 事件序列标准

正常完成时推荐顺序：

### 1

```
{
  "eventType": "task_created",
  "message": "task created"
}
```

### 2

```
{
  "eventType": "analysis_started",
  "message": "analysis started"
}
```

### 3

```
{
  "eventType": "analysis_completed",
  "message": "analysis completed"
}
```

### 4

```
{
  "eventType": "review_completed",
  "message": "review completed"
}
```

失败时推荐顺序：

### 1

```
task_created
```

### 2

```
analysis_started
```

### 3

```
review_failed
```

------

## 6. Day1+ 扩展事件预留

后续允许新增但不破坏 Day0：

```
issue_graph_built
repair_plan_created
case_memory_hit
patch_generated
patch_apply_started
patch_apply_passed
compile_started
compile_passed
lint_started
lint_passed
test_started
test_passed
retry_started
retry_finished
verification_completed
```

------

## 7. payload 扩展约定

Day0:

```
{}
```

未来 analyzer 阶段：

```
{
  "issuesCount": 2,
  "symbolsCount": 5
}
```

未来 patch 阶段：

```
{
  "patchId": "patch_001",
  "riskLevel": "medium"
}
```

未来 verifier 阶段：

```
{
  "verifiedLevel": "L2",
  "passedStages": ["patch_apply", "compile", "lint"]
}
```

------

## 8. 前端展示规则

- 使用 `sequence` 排序
- 使用 `timestamp` 展示时间
- 使用 `eventType` 映射图标和颜色
- 使用 `message` 作为主文案
- 暂不依赖 `payload` 做复杂展示
- `review_completed` 与 `review_failed` 必须高亮

------

## 9. 后端实现规则

- 后端统一构造事件对象
- 禁止前端自己拼事件
- 禁止 AI Engine 直接决定最终前端展示格式
- 事件必须先标准化，再通过 SSE 输出

------

## 10. 样例

```
[
  {
    "taskId": "rev_001",
    "eventType": "task_created",
    "message": "task created",
    "timestamp": "2026-04-01T20:10:00",
    "sequence": 1,
    "status": "CREATED",
    "payload": {}
  },
  {
    "taskId": "rev_001",
    "eventType": "analysis_started",
    "message": "analysis started",
    "timestamp": "2026-04-01T20:10:01",
    "sequence": 2,
    "status": "RUNNING",
    "payload": {}
  },
  {
    "taskId": "rev_001",
    "eventType": "analysis_completed",
    "message": "analysis completed",
    "timestamp": "2026-04-01T20:10:03",
    "sequence": 3,
    "status": "RUNNING",
    "payload": {
      "issuesCount": 0
    }
  },
  {
    "taskId": "rev_001",
    "eventType": "review_completed",
    "message": "review completed",
    "timestamp": "2026-04-01T20:10:04",
    "sequence": 4,
    "status": "COMPLETED",
    "payload": {
      "summary": "mock pipeline completed"
    }
  }
]
```