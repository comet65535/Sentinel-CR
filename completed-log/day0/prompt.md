:::writing{variant="standard" id="48124"}
你现在是 Sentinel-CR 项目的实现代理。请严格按照仓库现状与 docs 规则完成 Day0 基础数据通路，不要扩展到 Day1 以后。

## 项目背景
Sentinel-CR 是一个 Verified AI Code Repair Agent。长期目标是打通：
Analyzer -> Issue Graph Planner -> Fixer -> Multi-stage Verifier -> Event Stream -> Benchmark

但今天是 Day0，只做最小基础通路：
Frontend -> Spring Boot Backend -> Mock AI Engine -> SSE Event Stream -> Frontend

请先阅读并遵守以下文档：
- README.md
- PLAN.md
- docs/architecture.md
- docs/api-contract.md
- docs/event-schema.md

如果 docs 文件尚不存在，请先按这些文件名创建，并以仓库规则为准继续开发。

## Day0 目标
实现一条本地可演示的最小链路：

1. 前端输入 Java 代码文本
2. 点击提交后调用后端 `POST /api/reviews`
3. 后端创建 task，返回 taskId
4. 前端自动订阅 `GET /api/reviews/{taskId}/events`
5. 后端通过 Mock AI Engine 分阶段推送事件：
   - task_created
   - analysis_started
   - analysis_completed
   - review_completed
6. 前端将事件按顺序渲染为时间轴或列表
7. 最终页面可看到 taskId、任务状态、事件流
8. 整体本地可运行

## 重要边界
严格禁止在 Day0 做以下事情：
- 不接入真实 LangGraph
- 不接入真实 Tree-sitter
- 不接入真实 Semgrep
- 不接入真实 Python 分析逻辑
- 不接数据库、Redis、MQ
- 不做复杂鉴权
- 不做过度抽象
- 不重写整个前端/后端脚手架

允许：
- Java 后端内置 MockAiEngineAdapter
- 使用内存态任务存储
- 使用 SSE 推送事件
- 前端用最简洁方式展示事件

## 后端要求
请优先在 `backend-java` 中完成：

### 1. API
实现：
- `POST /api/reviews`
- `GET /api/reviews/{taskId}/events`
- 建议额外实现 `GET /api/reviews/{taskId}`

### 2. 数据模型
至少包含：
- ReviewTask
- ReviewTaskStatus
- ReviewEvent

### 3. 服务层
至少包含：
- ReviewService
- AiEngineAdapter
- MockAiEngineAdapter
- ReviewEventBus
- InMemoryTaskRepository

### 4. 行为要求
- 创建任务时生成 taskId
- 立即记录 task_created 事件
- 启动 mock review 流程
- mock review 流程应异步推送事件，模拟真实处理过程
- 每个事件都遵循统一 schema：
  - taskId
  - eventType
  - message
  - timestamp
  - sequence
  - status
  - payload
- sequence 必须递增
- 最终任务状态更新为 COMPLETED 或 FAILED

### 5. 推荐技术实现
- Spring Boot 3
- WebFlux SSE 或兼容实现
- Reactor `Sinks.Many` 或同等机制
- 内存态 `ConcurrentHashMap`

如果已有依赖允许，请优先采用最简单稳定方案，不额外引入新基础设施。

## 前端要求
请在 `frontend-ui` 中完成：

### 1. 页面能力
- 一个代码输入区域
- 一个提交按钮
- 一个 taskId 展示区域
- 一个事件列表区域
- 一个任务状态展示区域

### 2. API 调用
- 提交按钮调用 `POST /api/reviews`
- 成功后自动建立 SSE 连接
- 持续接收事件并更新 UI

### 3. 展示要求
- 事件按 sequence 排序显示
- 展示 eventType、message、timestamp
- 最终展示任务状态
- 失败时给出错误提示

### 4. 代码要求
- API 层与页面层分离
- 对事件类型定义 TypeScript 类型
- 正确关闭 EventSource，避免重复连接泄漏

## 文件组织建议
后端建议结构：
- api/
- service/
- engine/
- event/
- task/
- dto/

前端建议结构：
- src/api/
- src/types/
- src/components/
- src/views/ 或 src/pages/

## 联调要求
请确保：
- 前后端接口路径一致
- 前端可直接本地联调
- 如有跨域问题，后端补充最小必要配置
- 不要假设用户会手工改很多配置

## 输出要求
完成后请给出：

1. 你新增/修改了哪些文件
2. 每个文件的作用
3. 本地运行方式
4. 如何手工验证 Day0 是否完成
5. 当前仍然是 mock 的部分有哪些
6. 下一步如何平滑进入 Day1

## 验收标准
必须满足以下验收条件：
- 输入任意 Java 代码后能返回 taskId
- SSE 能连续收到至少 4 个事件
- 前端能显示这些事件
- 最终任务状态为 COMPLETED
- 整体无阻塞长请求
- 代码结构为后续接入真实 AI Engine 预留扩展点

## 开发风格要求
- 以最小改动完成目标
- 保持命名清晰
- 保持接口稳定
- 不做炫技式设计
- 优先可运行、可联调、可演示
- 所有实现围绕“Day0 打通基础数据通路”这一目标服务

现在开始直接修改代码，不要只给方案。优先完成 docs 和可运行链路，再补充说明。
:::

---

# 三、我对你这个 Day0 的一个判断

你现在最该让 Codex做的，不是“AI 修复能力”，而是这 4 个点：

- 后端任务模型
- 后端 SSE 事件总线
- Mock AI Engine
- 前端提交 + 事件流页面

因为这正是你 7 天计划里 Day1 的骨架前置版：先把事件协议和主链路定住，后面 Analyzer、Planner、Fixer、Verifier 才能往上叠。:contentReference[oaicite:3]{index=3}

而且 Codex 本身就适合这类**边界清晰、可验收、能跑测试/联调**的任务；给它这种规则文档 + 明确验收项，成功率会比“帮我随便实现一个 agent”高很多。:contentReference[oaicite:4]{index=4}

如果你愿意，我下一条可以继续直接给你一版 **“更强的 AGENTS.md / CODEX.md”**，专门优化 Codex 在你这个仓库里的执行效果。
::contentReference[oaicite:5]{index=5}