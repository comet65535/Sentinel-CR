# Sentinel-CR Event Schema (Day1)

## 1. 文档目标

本文档定义 Sentinel-CR 在 Day1 阶段的统一事件协议。

这份协议必须同时服务于三方：

- Frontend 时间轴展示
- Java Backend 任务状态管理与 SSE 推送
- Python AI Engine 内部事件输出

Day1 的原则是：

> **保留 Day0 的顶层公开事件 schema，不破坏现有前端；新增的细节优先进入 `payload`。**

---

## 2. 公开 ReviewEvent 结构（Java -> Frontend）

Day1 继续沿用统一公开事件结构：

```json
{
  "taskId": "rev_20260402_001",
  "eventType": "analysis_started",
  "message": "python engine started state graph",
  "timestamp": "2026-04-02T10:00:01",
  "sequence": 2,
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

---

## 3. 顶层字段定义

## 3.1 `taskId`
- 必填
- 任务唯一标识
- 同一个 SSE 流内所有事件必须属于同一个 `taskId`

## 3.2 `eventType`
- 必填
- 事件类型
- 前端使用它决定展示文案或图标

## 3.3 `message`
- 必填
- 给用户和开发者看的简短说明
- 必须短句、可读，不写大段日志

## 3.4 `timestamp`
- 必填
- ISO-8601 时间字符串
- **由 Java Backend 统一生成**
- 前端展示用

## 3.5 `sequence`
- 必填
- 从 1 开始递增
- **由 Java Backend 统一分配**
- 前端必须以它为准排序

## 3.6 `status`
- 必填
- 当前任务状态
- 取值只能是：
  - `CREATED`
  - `RUNNING`
  - `COMPLETED`
  - `FAILED`

## 3.7 `payload`
- 必填
- 必须始终是对象
- Day1 即使没有额外信息也返回 `{}`，不能返回 `null`
- 用于承载扩展字段而不破坏顶层 schema

---

## 4. 顶层字段约束

## 4.1 Java 是公开事件的唯一规范化出口
无论事件最初来自哪里，对前端可见的 `ReviewEvent` 都必须由 Java 统一规范化：

- `sequence` 由 Java 生成
- `timestamp` 由 Java 生成
- `payload` 由 Java 保证为对象
- 任务最终状态由 Java 落库/落内存

## 4.2 前端不能假设事件按网络到达顺序有序
网络环境下事件可能延迟，因此：

- 展示顺序以 `sequence` 为准
- 不依赖浏览器收到的先后顺序

## 4.3 payload 扩展只能“加”，不能破坏兼容
可以增加：

- `payload.source`
- `payload.stage`
- `payload.result`
- `payload.issues`
- `payload.issueGraph`
- `payload.engine`

不能做：

- 删除已有顶层字段
- 修改顶层字段名称
- 把原本顶层字段塞回 payload

---

## 5. Day1 推荐 payload 字段

Day1 推荐但不强制的 payload 字段：

```json
{
  "source": "python-engine",
  "stage": "bootstrap_state",
  "engine": "python",
  "issues": [],
  "issueGraph": [],
  "result": {
    "summary": "day1 python engine skeleton completed"
  }
}
```

### 字段说明
- `source`：事件来源，推荐值：
  - `backend`
  - `python-engine`
  - `mock-engine`
- `stage`：当前细分阶段
- `engine`：当前处理引擎标识
- `issues`：Day1 可为空数组
- `issueGraph`：Day1 可为空数组
- `result`：最终结果摘要

---

## 6. Day1 公开事件类型

Day1 默认公开事件类型如下：

```text
task_created
analysis_started
analysis_completed
review_completed
review_failed
heartbeat
```

### 6.1 `task_created`
含义：任务已创建，且后端已经分配 `taskId`

推荐状态：
```text
CREATED
```

推荐 payload：
```json
{
  "source": "backend",
  "engine": "python"
}
```

### 6.2 `analysis_started`
含义：Python 引擎已接手任务并开始推进最小状态机

推荐状态：
```text
RUNNING
```

推荐 payload：
```json
{
  "source": "python-engine",
  "stage": "bootstrap_state"
}
```

### 6.3 `analysis_completed`
含义：Day1 的最小“分析 stub”已完成

推荐状态：
```text
RUNNING
```

推荐 payload：
```json
{
  "source": "python-engine",
  "stage": "run_analysis_stub",
  "issues": [],
  "issueGraph": []
}
```

### 6.4 `review_completed`
含义：整条 Day1 链路成功结束

推荐状态：
```text
COMPLETED
```

推荐 payload：
```json
{
  "source": "python-engine",
  "stage": "finalize_result",
  "result": {
    "summary": "day1 python engine skeleton completed"
  }
}
```

### 6.5 `review_failed`
含义：任务在任一阶段失败

推荐状态：
```text
FAILED
```

推荐 payload：
```json
{
  "source": "backend",
  "stage": "engine_error",
  "errorType": "python_unreachable"
}
```

### 6.6 `heartbeat`
含义：可选保活事件

推荐状态：
- 保持当前任务状态，不改变状态机最终结论

Day1 如果整体链路很短，可以不发 heartbeat。

---

## 7. Day1 默认成功序列

为了兼容 Day0 已有前端与测试，Day1 **默认成功路径** 建议仍然是 4 个公开事件：

### 1. `task_created`
```json
{
  "eventType": "task_created",
  "status": "CREATED"
}
```

### 2. `analysis_started`
```json
{
  "eventType": "analysis_started",
  "status": "RUNNING"
}
```

### 3. `analysis_completed`
```json
{
  "eventType": "analysis_completed",
  "status": "RUNNING"
}
```

### 4. `review_completed`
```json
{
  "eventType": "review_completed",
  "status": "COMPLETED"
}
```

> 这是 Day1 的“最小成功公开序列”。内部流程可以更细，但默认不要额外膨胀公开事件数量。

---

## 8. Day1 默认失败序列

推荐失败时至少发出：

### 1. `task_created`
### 2. `analysis_started`（如果引擎已经开始处理）
### 3. `review_failed`

如果失败发生在 Python 连接之前，也允许直接：

### 1. `task_created`
### 2. `review_failed`

关键要求只有两个：

- 最终任务状态必须是 `FAILED`
- 前端不能看到“看起来没结束”的卡死状态

---

## 9. Python 内部 EngineEvent 结构（Python -> Java）

Python 返回给 Java 的内部事件建议结构：

```json
{
  "taskId": "rev_20260402_001",
  "eventType": "analysis_started",
  "message": "state graph initialized",
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

### 与公开事件的区别
内部事件可以没有：

- `sequence`
- `timestamp`

因为它们都应该由 Java 统一补齐。

### 内部事件硬约束
- `taskId` 必填
- `eventType` 必填
- `message` 必填
- `status` 必填
- `payload` 必填且为对象

---

## 10. Java 规范化规则

Java 收到 Python 事件后，必须按以下顺序处理：

1. 校验 JSON 可解析
2. 校验 `taskId` 一致
3. 校验 `payload` 为对象
4. 分配新的 `sequence`
5. 生成 `timestamp`
6. 更新 `ReviewTask.status`
7. 写入 `ReviewEventBus`
8. 将事件推给前端

### 非法事件示例
以下情况都应视为非法：

- 缺失 `eventType`
- 缺失 `status`
- `payload` 为 `null`
- `taskId` 与请求不一致
- 事件顺序逻辑明显错误（例如先 `review_completed` 再 `analysis_started`）

Java 对非法事件的处理：

- 终止当前引擎消费
- 发布 `review_failed`
- 将错误信息写入任务详情

---

## 11. Day1 与 Day2+ 的兼容预留

Day1 虽然只公开最小事件集，但要为后续阶段留出兼容空间。

未来允许扩展的 `payload` 字段包括：

- `symbols`
- `contextSummary`
- `repairPlan`
- `caseMemoryHits`
- `patch`
- `verificationResult`
- `retryCount`

未来允许扩展的事件类型包括：

```text
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

### 但 Day1 的原则不变
- 顶层 schema 不变
- 已有事件含义不变
- 新细节优先放入 `payload`

---

## 12. 示例：推荐公开事件

## 12.1 成功时的 `analysis_started`
```json
{
  "taskId": "rev_20260402_001",
  "eventType": "analysis_started",
  "message": "python engine started state graph",
  "timestamp": "2026-04-02T10:00:01",
  "sequence": 2,
  "status": "RUNNING",
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state",
    "engine": "python"
  }
}
```

## 12.2 成功时的 `review_completed`
```json
{
  "taskId": "rev_20260402_001",
  "eventType": "review_completed",
  "message": "day1 python engine skeleton completed",
  "timestamp": "2026-04-02T10:00:03",
  "sequence": 4,
  "status": "COMPLETED",
  "payload": {
    "source": "python-engine",
    "stage": "finalize_result",
    "engine": "python",
    "result": {
      "summary": "day1 python engine skeleton completed"
    }
  }
}
```

## 12.3 失败时的 `review_failed`
```json
{
  "taskId": "rev_20260402_001",
  "eventType": "review_failed",
  "message": "python engine unavailable",
  "timestamp": "2026-04-02T10:00:02",
  "sequence": 3,
  "status": "FAILED",
  "payload": {
    "source": "backend",
    "stage": "engine_error",
    "engine": "python",
    "errorType": "python_unreachable"
  }
}
```

---

## 13. 最终原则

Day1 的事件协议要同时满足三件事：

1. **前端不需要重做**
2. **Java 可以继续稳定管理任务生命周期**
3. **Python 事件可以自然演进到 Day2+ 的 Analyzer / Planner / Fixer / Verifier**

只要这三件事成立，Day1 的事件设计就是成功的。
