# Sentinel-CR API Contract (Day0)

## 1. 目标

本文档定义 Day0 阶段前后端、后端与 AI Engine 之间的最小接口契约。

目标：
- 保证前端、后端、Python 引擎未来可以独立演进
- 保证 Day0 用 mock 实现，Day1 可平滑切换真实引擎
- 保证所有协议围绕 taskId 和 event stream 展开

---

## 2. REST API

## 2.1 创建 Review 任务

### Request
`POST /api/reviews`

### Body
```json
{
  "codeText": "public class Demo { }",
  "language": "java",
  "sourceType": "snippet"
}
```

### 字段说明

- `codeText`: 必填，用户提交的代码文本
- `language`: 必填，Day0 固定只支持 `java`
- `sourceType`: 必填，Day0 固定使用 `snippet`

### Response

```
{
  "taskId": "rev_20260401_001",
  "status": "CREATED",
  "message": "review task created"
}
```

### 约束

- 后端必须同步返回 taskId
- 不在这个接口中阻塞等待分析完成
- 创建成功后，前端应立即去订阅 SSE

------

## 2.2 订阅任务事件流

### Request

```
GET /api/reviews/{taskId}/events
```

### Response

```
Content-Type: text/event-stream
```

SSE event data 示例：

```
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

### 约束

- SSE 必须支持同一个 taskId 的连续事件推送
- 事件顺序必须按 `sequence` 单调递增
- 任务结束后可发送 completed 事件并关闭流，或保留短时间连接

------

## 2.3 查询任务详情（可选但建议 Day0 一并实现）

### Request

```
GET /api/reviews/{taskId}
```

### Response

```
{
  "taskId": "rev_20260401_001",
  "status": "COMPLETED",
  "createdAt": "2026-04-01T20:09:58",
  "updatedAt": "2026-04-01T20:10:06",
  "result": {
    "summary": "mock review completed"
  },
  "errorMessage": null
}
```

用途：

- 页面刷新后的状态恢复
- 调试接口
- 后续扩展结果详情

------

## 3. 任务状态枚举

```
CREATED
RUNNING
COMPLETED
FAILED
```

状态流转规则：

- 创建任务后为 `CREATED`
- 开始处理后变为 `RUNNING`
- 成功结束为 `COMPLETED`
- 任一步骤失败为 `FAILED`

禁止跳过状态直接乱写。

------

## 4. 事件类型枚举（Day0）

Day0 最小事件集：

```
task_created
analysis_started
analysis_completed
review_completed
review_failed
heartbeat
```

说明：

- `task_created`: 任务已创建
- `analysis_started`: 开始处理
- `analysis_completed`: Mock 分析完成
- `review_completed`: 整体流程完成
- `review_failed`: 流程失败
- `heartbeat`: 可选，用于保持连接活性

------

## 5. AI Engine Adapter Contract

Java 后端通过统一接口调用 AI Engine。

建议接口语义：

```
public interface AiEngineAdapter {
    void startReview(ReviewTask task, Consumer<ReviewEvent> eventConsumer);
}
```

约束：

- 由引擎逐步回调事件
- Day0 可由 MockAiEngineAdapter 定时推送固定事件
- 后续真实 Python 引擎接入时，不得改变事件协议

------

## 6. 错误处理约束

### 创建任务失败

返回：

- HTTP 400：参数错误
- HTTP 500：服务端异常

### SSE 订阅失败

返回：

- HTTP 404：taskId 不存在
- HTTP 500：事件流初始化失败

### 引擎执行失败

必须至少发出：

- `review_failed` 事件
- 任务状态改为 `FAILED`
- `errorMessage` 写入任务详情

------

## 7. 兼容性约束

Day0 所有接口一旦实现，Day1 不允许随意破坏：

- URL 路径
- 基本字段名
- taskId 机制
- SSE 协议基本结构

后续扩展只能：

- 增加 payload 字段内容
- 增加新的 eventType
- 增加结果详情字段

