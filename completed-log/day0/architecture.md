# Sentinel-CR Architecture (Day0 Baseline)

## 1. 文档目标

这份文档用于约束 Codex 在 Sentinel-CR 项目中的 Day0 开发行为。

Day0 的目标不是实现完整的 Code Repair Agent，而是先打通最小基础数据通路：

Frontend -> Spring Boot Backend -> AI Engine Adapter -> Event Stream -> Frontend

要求：
- 先打通链路，再补复杂智能能力
- 先稳定事件协议，再补 analyzer / planner / fixer / verifier
- 所有实现优先服务于 Day1 主链路，而不是过度设计

---

## 2. 当前项目结构

项目根目录：

- `frontend-ui/`：Vue3 前端
- `backend-java/`：Spring Boot 后端
- `ai-engine-python/`：Python AI 引擎

Day0 阶段允许 Python 引擎先采用 mock / stub 模式，只要接口和事件结构稳定即可。

---

## 3. 系统分层

## 3.1 Frontend UI
职责：
- 提交 review 请求
- 按 taskId 订阅 SSE 事件流
- 显示任务状态、事件时间轴、最终结果占位
- Day0 不要求实现 diff 视图，不要求复杂调试面板

必须具备：
- 代码输入框
- 提交按钮
- taskId 展示
- SSE 事件列表展示
- 基本错误提示

---

## 3.2 Java Backend
职责：
- 提供 REST API 接收 review 请求
- 生成 taskId
- 管理任务状态
- 提供 SSE 事件流接口
- 调用 AI Engine Adapter
- 将 AI Engine 产生的事件转发给前端

Day0 阶段后端是系统主协调器。

必须具备：
- `POST /api/reviews`
- `GET /api/reviews/{taskId}/events`
- 内存态任务存储
- 内存态事件总线
- AI Engine Adapter 接口
- Mock AI Engine 实现

---

## 3.3 Python AI Engine
职责：
- 后续承接 analyzer / planner / fixer / verifier
- Day0 阶段只要求提供最小可替代能力

Day0 允许两种方式：
1. 先不真实调用 Python，Java 内部提供 MockEngine 模拟事件
2. 或 Java 调 Python stub 接口，返回固定事件流

优先级：
- 优先保证事件协议稳定
- 优先保证 task 生命周期跑通
- 不要求 Day0 引入 LangGraph、Tree-sitter、Semgrep 真执行

---

## 4. Day0 目标边界

Day0 必须完成：

1. 前端可提交一段代码文本
2. 后端创建任务并返回 taskId
3. 前端可基于 taskId 建立 SSE 连接
4. 后端能持续推送事件：
   - task_created
   - analysis_started
   - analysis_completed
   - review_completed
5. 前端正确显示事件顺序
6. 整体链路在本地可演示

Day0 明确不做：
- 不做真实 AST 分析
- 不做真实 Semgrep 扫描
- 不做真实 patch 生成
- 不做真实 verifier
- 不接数据库、Redis、MQ
- 不做复杂鉴权
- 不做多租户
- 不做生产级持久化

---

## 5. 编码原则

## 5.1 先接口稳定，再实现增强
所有复杂功能都必须建立在稳定协议之上。
禁止为了未来功能提前引入过重抽象。

## 5.2 所有状态围绕 taskId
任何 review 行为都必须可通过 taskId 查询与追踪。

## 5.3 事件优先
Sentinel-CR 是事件驱动体验，不是同步长请求体验。
任何长流程都应该通过事件流体现，而不是阻塞 HTTP 返回。

## 5.4 后端内部先内存实现
Day0 允许使用 ConcurrentHashMap、Sinks、in-memory repository。
只要接口不变，后续可以替换为 Redis / MQ / DB。

## 5.5 前端先可用，再美化
前端优先保证：
- 请求成功
- SSE 正常
- 事件能渲染
- 错误能提示

不要求 Day0 做复杂 UI 视觉优化。

---

## 6. 推荐后端模块划分

建议在 `backend-java` 中按以下包组织：

- `api/`
  - `ReviewController`
  - `dto/`
- `service/`
  - `ReviewService`
- `event/`
  - `ReviewEvent`
  - `ReviewEventBus`
- `task/`
  - `ReviewTask`
  - `ReviewTaskStatus`
  - `TaskRepository`
- `engine/`
  - `AiEngineAdapter`
  - `MockAiEngineAdapter`

要求：
- Controller 只做协议转换
- Service 负责任务创建与流程启动
- EventBus 负责 SSE 推送
- EngineAdapter 负责后续与 Python 引擎对接

---

## 7. 推荐前端模块划分

建议在 `frontend-ui/src/` 中按以下结构组织：

- `api/`
  - `review.ts`
- `types/`
  - `review.ts`
- `components/`
  - `ReviewForm.vue`
  - `EventTimeline.vue`
- `pages/` 或 `views/`
  - `ReviewPage.vue`

要求：
- API 请求与页面逻辑分离
- 事件类型定义统一维护
- EventSource 生命周期明确关闭
- 页面刷新后允许重新提交任务

---

## 8. Day0 验收标准

满足以下条件即算完成：

1. 在前端输入任意 Java 代码并点击提交
2. 后端返回 `taskId`
3. 前端自动连接 `/api/reviews/{taskId}/events`
4. 2~5 秒内持续收到 4 个以上事件
5. 前端按时间顺序展示事件
6. 最终任务状态为 `COMPLETED`
7. 无需手工刷新页面即可看到整个过程
8. 本地开发环境可重复运行

---

## 9. Day0 完成后为 Day1 预留的扩展点

必须预留以下接口，但 Day0 不要求真实实现：

- `AiEngineAdapter.review(...)`
- 事件类型扩展位
- `payload` 字段
- `ReviewTask.result`
- `ReviewTask.errorMessage`
- `analysis_summary`
- `patch_summary`
- `verification_summary`

后续 Day1/Day2 在不破坏协议的前提下逐步替换 Mock 实现。