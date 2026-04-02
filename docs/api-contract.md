# Sentinel-CR API Contract (Day1)

## 1. 文档目标

本文档定义 Sentinel-CR 在 Day1 阶段的接口契约。

Day1 的接口设计遵守两个原则：

1. **公开接口向后兼容 Day0**
2. **新增 Java 与 Python 之间的内部协议，但不让前端感知内部变化**

Day1 的接口分两类：

- **公开接口**：Frontend <-> Java Backend
- **内部接口**：Java Backend <-> Python AI Engine

---

## 2. 总体兼容性原则

Day1 必须遵守：

- 不重命名现有公开接口
- 不修改现有公开响应的核心字段语义
- 不破坏基于 `taskId` 的查询与 SSE 订阅方式
- 不改变 `ReviewEvent` 的顶层字段结构
- 只允许在 `payload` 中做扩展

> 也就是说，Day1 的前端不应该需要因为 Python 引擎接入而重写 API 层。

---

## 3. 公开 REST API（Frontend <-> Java）

## 3.1 创建 Review 任务

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
- `codeText`：必填，用户提交的代码文本
- `language`：必填，Day1 仍固定支持 `java`
- `sourceType`：必填，Day1 仍固定使用 `snippet`

### Response
```json
{
  "taskId": "rev_20260402_001",
  "status": "CREATED",
  "message": "review task created"
}
```

### 约束
- 必须同步返回 `taskId`
- 不允许在该接口中阻塞等待 Python 分析完成
- 创建成功后，前端应立即去订阅 SSE
- Day1 继续沿用 Day0 路径，不改成 `/review`

### 错误码
- `400`：参数错误
- `500`：服务端异常

---

## 3.2 查询任务详情

### Request
`GET /api/reviews/{taskId}`

### Response
```json
{
  "taskId": "rev_20260402_001",
  "status": "COMPLETED",
  "createdAt": "2026-04-02T10:00:00",
  "updatedAt": "2026-04-02T10:00:03",
  "result": {
    "summary": "day1 python engine skeleton completed",
    "engine": "python"
  },
  "errorMessage": null
}
```

### 说明
用途：

- 页面刷新后的状态恢复
- 排查任务失败原因
- 为后续扩展 `patch`、`verification_result` 留入口

### 约束
- `taskId` 不存在时返回 `404`
- `result` 可为 `null`
- `errorMessage` 在成功时为 `null`
- 如果 Python 失败，必须能在这里看见失败信息

---

## 3.3 订阅任务事件流

### Request
`GET /api/reviews/{taskId}/events`

### Response
`Content-Type: text/event-stream`

SSE `data:` 中承载统一 JSON：

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

### 约束
- 同一个 taskId 的事件必须来自同一条任务流
- `sequence` 必须严格递增
- 前端必须以 `sequence` 为准排序，不依赖网络到达顺序
- Day1 默认成功链路仍然建议保持 4 个公开主事件
- `payload` 必须始终是对象，不能省略、不能为 `null`

### 错误码
- `404`：taskId 不存在
- `500`：事件流初始化失败

---

## 4. 任务状态枚举

公开状态继续保持 Day0 语义：

```text
CREATED
RUNNING
COMPLETED
FAILED
```

### 状态流转规则
- 创建任务后为 `CREATED`
- 开始调用引擎后变为 `RUNNING`
- 正常结束为 `COMPLETED`
- 任一步骤失败为 `FAILED`

禁止：

- 从 `CREATED` 直接跳到 `COMPLETED` 且没有任何中间处理事件
- 失败后还继续发送“成功完成”事件
- 任务最终结束后状态仍长期停留在 `RUNNING`

---

## 5. 统一公开事件类型（Day1）

Day1 公开最小成功事件集：

```text
task_created
analysis_started
analysis_completed
review_completed
review_failed
heartbeat
```

说明：

- `task_created`：任务已创建
- `analysis_started`：Python 引擎已开始处理
- `analysis_completed`：Day1 最小分析阶段已完成
- `review_completed`：整体流程成功结束
- `review_failed`：整体流程失败
- `heartbeat`：可选，用于长连接保活

### Day1 额外建议
如果内部想表达更细的阶段，不要轻易新增公开事件类型；优先将细阶段写入：

```json
{
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

这样可减少对现有前端与测试的破坏。

---

## 6. 内部接口（Java <-> Python）

## 6.1 Python 健康检查

### Request
`GET /health`

### Response
```json
{
  "status": "UP",
  "service": "ai-engine-python"
}
```

### 用途
- Java 启动后可探测 Python 是否可用
- 本地调试更容易定位问题
- 为后续 `start-all.bat` 或 docker-compose 留接口

---

## 6.2 启动一次 Python Review 运行

### Request
`POST /internal/reviews/run`

### Headers
```text
Content-Type: application/json
Accept: application/x-ndjson
```

### Body
```json
{
  "taskId": "rev_20260402_001",
  "codeText": "public class Demo { }",
  "language": "java",
  "sourceType": "snippet",
  "metadata": {
    "requestedBy": "backend-java",
    "debug": false
  }
}
```

### 字段说明
- `taskId`：必填，由 Java 生成并传给 Python
- `codeText`：必填，代码原文
- `language`：必填，Day1 固定 `java`
- `sourceType`：必填，Day1 固定 `snippet`
- `metadata`：可选，保留扩展字段

### Response
`Content-Type: application/x-ndjson`

每一行都是一个 JSON 事件：

```json
{"taskId":"rev_20260402_001","eventType":"analysis_started","message":"state graph initialized","status":"RUNNING","payload":{"source":"python-engine","stage":"bootstrap_state"}}
{"taskId":"rev_20260402_001","eventType":"analysis_completed","message":"state graph finished","status":"RUNNING","payload":{"source":"python-engine","stage":"run_analysis_stub","issues":[],"issueGraph":[]}}
{"taskId":"rev_20260402_001","eventType":"review_completed","message":"day1 skeleton completed","status":"COMPLETED","payload":{"source":"python-engine","stage":"finalize_result","result":{"summary":"day1 python engine skeleton completed"}}}
```

### 约束
- 必须按事件顺序逐行流式返回
- 单个请求只处理一个 `taskId`
- 返回的 `taskId` 必须与请求一致
- Python 不负责分配 `sequence`
- Python 不负责对前端可见的最终 SSE 格式控制
- Java 是公开协议的唯一出口

---

## 7. 内部 EngineEvent 约束

Python 返回的内部事件建议结构：

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

### 字段要求
- `taskId`：必填，便于 Java 校验
- `eventType`：必填，必须可映射到公开事件
- `message`：必填，简短清晰
- `status`：必填，使用公开状态枚举
- `payload`：必填，对象类型

### 不要求的字段
内部事件可以没有：
- `sequence`
- `timestamp`

因为这些字段应该由 Java 统一补齐。

---

## 8. Java 侧映射规则

Java 在收到 Python 内部事件后，必须做以下规范化：

1. 校验 `taskId` 一致
2. 为事件分配下一个 `sequence`
3. 生成统一 `timestamp`
4. 规范化成 `ReviewEvent`
5. 写入 `ReviewEventBus`
6. 更新任务状态与最终结果

### 推荐映射原则
- 内部 `analysis_started` -> 公开 `analysis_started`
- 内部 `analysis_completed` -> 公开 `analysis_completed`
- 内部 `review_completed` -> 公开 `review_completed`
- Python 请求失败 / 解析失败 / 断流 -> 公开 `review_failed`

---

## 9. 错误处理契约

## 9.1 Python 不可达
如果 Java 无法连接 Python：

- 任务状态必须置为 `FAILED`
- 必须发布 `review_failed`
- `errorMessage` 必须可通过 `GET /api/reviews/{taskId}` 查询
- 不能让任务无限等待

## 9.2 Python 返回非法事件
以下情况视为非法：

- JSON 无法解析
- `taskId` 不匹配
- 缺少 `eventType`
- 缺少 `status`
- `payload` 不是对象

处理要求：

- 终止当前任务流
- 发布 `review_failed`
- 将错误原因写入任务详情

## 9.3 Python 中途断流
如果已经开始处理但流异常结束：

- 若尚未收到 `review_completed`
- 且尚未收到 `review_failed`
- Java 必须自动补发一个 `review_failed`

---

## 10. 配置契约

推荐 Java 配置项：

```properties
sentinel.ai.mode=python
sentinel.ai.python-base-url=http://localhost:8000
sentinel.ai.python-connect-timeout-ms=3000
sentinel.ai.python-read-timeout-ms=15000
```

推荐 Python 启动端口：

```text
8000
```

Day1 不让前端直连 Python，因此前端配置不需要新增 Python 地址。

---

## 11. Day1 验收接口样例

## 11.1 成功样例流程
1. `POST /api/reviews`
2. 返回 `taskId`
3. `GET /api/reviews/{taskId}/events`
4. 收到：
   - `task_created`
   - `analysis_started`
   - `analysis_completed`
   - `review_completed`
5. `GET /api/reviews/{taskId}` 显示 `COMPLETED`

## 11.2 失败样例流程
1. `POST /api/reviews`
2. 返回 `taskId`
3. Java 调 Python 失败
4. SSE 收到 `review_failed`
5. `GET /api/reviews/{taskId}` 显示 `FAILED`

---

## 12. 最终原则

Day1 的接口设计不是为了“今天做很多功能”，而是为了：

- 保住 Day0 的稳定接口
- 引入真实 Python 服务
- 为 Day2+ 的 analyzer/planner/fixer/verifier 铺轨

任何会破坏现有公开接口稳定性的改动，哪怕看起来“更优雅”，在 Day1 都不应该做。
