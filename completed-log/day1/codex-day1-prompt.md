你现在在 Sentinel-CR 仓库中工作，请直接完成 **Day1** 的实现，不要做 Day2+ 功能扩散。

先读这几个文件，并把它们当作本次开发的唯一规范来源：
- README.md
- PLAN.md
- docs/architecture.md
- docs/api-contract.md
- docs/event-schema.md

你必须基于当前仓库的现实状态开发，而不是重新发明一套新路径。当前已知事实：
1. Day0 已经跑通 `Frontend -> Spring Boot Backend -> Mock AI -> SSE -> Frontend`
2. 公开接口已经是：
   - `POST /api/reviews`
   - `GET /api/reviews/{taskId}`
   - `GET /api/reviews/{taskId}/events`
3. 后端已经有：
   - `AiEngineAdapter`
   - `MockAiEngineAdapter`
   - `ReviewEvent`
   - `ReviewEventBus`
   - `ReviewService`
   - `InMemoryTaskRepository`
4. 前端已经能展示至少 4 个事件：
   - `task_created`
   - `analysis_started`
   - `analysis_completed`
   - `review_completed`

你的目标不是推翻 Day0，而是 **在不破坏 Day0 公共 API 和前端行为的前提下，引入真实的 Python 引擎骨架**。

# 本次必须完成的任务

## A. 新增 ai-engine-python 服务
创建 `ai-engine-python/` 最小可运行服务，推荐使用 FastAPI + uvicorn。

至少包含：
- `main.py`
- `requirements.txt`
- `core/state_graph.py`
- `core/schemas.py`
- `core/events.py`

Python 服务必须提供：
1. `GET /health`
2. `POST /internal/reviews/run`

其中 `POST /internal/reviews/run` 必须接收：
```json
{
  "taskId": "rev_xxx",
  "codeText": "...",
  "language": "java",
  "sourceType": "snippet",
  "metadata": {}
}
```

并返回 `application/x-ndjson` 的流式响应，每行一个 JSON 事件。

## B. 在 Python 侧建立 Day1 最小状态机骨架
不要实现真实 Tree-sitter / Semgrep / Patch / Verifier。
只实现最小可扩展 state graph。

状态至少包含这些字段：
- `task_id`
- `code_text`
- `language`
- `issues`
- `issue_graph`
- `patch`
- `verification_result`
- `events`
- `retry_count`

最小阶段：
1. `bootstrap_state`
2. `run_analysis_stub`
3. `finalize_result`

最小成功事件流：
1. `analysis_started`
2. `analysis_completed`
3. `review_completed`

要求：
- `issues` 初始为空数组
- `issue_graph` 初始为空数组
- `patch` 为 `None`
- `verification_result` 为 `None`
- `retry_count` 为 `0`

## C. 在 Java 后端新增 PythonAiEngineAdapter
在保留 `AiEngineAdapter` 接口不变的前提下，新增一个真实 Python 适配器，例如：
- `PythonAiEngineAdapter`
- `PythonEngineProperties`
- `PythonEngineEvent`
- `EngineEventMapper`

要求：
1. Java 后端通过 HTTP 调用 Python 的 `POST /internal/reviews/run`
2. 逐行消费 NDJSON 事件流
3. 将 Python 事件映射成现有 `ReviewEvent` 体系
4. 由 Java 统一分配 `sequence`
5. 由 Java 统一生成面向前端的 `timestamp`
6. 通过现有 `ReviewEventBus` 发布事件
7. 正确更新 `ReviewTask.status`、`result`、`errorMessage`

## D. 保留 Mock 模式作为回退
不要删除 `MockAiEngineAdapter`。
必须支持通过配置切换：
- `sentinel.ai.mode=mock`
- `sentinel.ai.mode=python`

并增加配置项：
- `sentinel.ai.python-base-url=http://localhost:8000`
- 合理的 connect/read timeout

要求：
- Python 未启动时，在 `python` 模式下任务必须进入 `FAILED`
- 必须发出 `review_failed`
- `GET /api/reviews/{taskId}` 能看到错误信息
- Mock 模式仍可继续工作

## E. 公开 API 和前端兼容性要求
这些内容禁止破坏：
- `POST /api/reviews`
- `GET /api/reviews/{taskId}`
- `GET /api/reviews/{taskId}/events`
- `ReviewEvent` 顶层字段：
  - `taskId`
  - `eventType`
  - `message`
  - `timestamp`
  - `sequence`
  - `status`
  - `payload`

注意：
- Day0 已经有前端和集成测试成功链路，默认成功路径不要无节制新增公开事件。
- **默认成功链路继续保持 4 个公开主事件**：
  1. `task_created`
  2. `analysis_started`
  3. `analysis_completed`
  4. `review_completed`
- 更细的内部阶段信息优先放在 `payload.stage`，例如：
```json
{
  "payload": {
    "source": "python-engine",
    "stage": "bootstrap_state"
  }
}
```

## F. 测试与运行脚本
请补齐最小可验证能力，至少做到：

### 后端
- 现有测试继续通过
- 新增一个针对 Python 适配器的测试，至少覆盖：
  - 正常事件映射
  - Python 不可达时报错并进入 `FAILED`

### Python
- 至少有最小单测或可直接运行的 smoke test 逻辑
- `uvicorn main:app --host 0.0.0.0 --port 8000` 可启动

### 前端
- 不要求大改
- 只做必要兼容
- `npm run build` 继续通过

### 启动方式
如果仓库里已有 `start-all.bat`，请一并更新，使其能启动：
- backend-java
- ai-engine-python
- frontend-ui

# 明确禁止的事项
今天不要做这些：
- 不接真实 Tree-sitter
- 不接真实 Semgrep
- 不做真实 patch generation
- 不做真实 compile/lint/test verifier
- 不接数据库/Redis/MQ
- 不改成新的公开 API 路径
- 不让前端直连 Python
- 不为了“架构好看”推翻 Day0 已有代码

# 完成标准
最终你提交的代码必须满足：

1. 本地同时启动 Java / Python / Frontend
2. 页面提交任意 Java 代码
3. 后端立即返回 `taskId`
4. 前端通过 Java SSE 收到事件
5. 成功链路默认仍是：
   - `task_created`
   - `analysis_started`
   - `analysis_completed`
   - `review_completed`
6. 事件 `sequence` 单调递增
7. 最终状态为 `COMPLETED`
8. `payload.source` 能标识 `python-engine`
9. Python 不可用时会产生 `review_failed` 且任务状态为 `FAILED`

# 交付格式要求
请直接修改代码并给出：
1. 你新增/修改的文件列表
2. 每个文件的作用
3. 本地运行命令
4. 如何验证 Day1 已完成
5. 哪些部分仍然是 stub / placeholder
