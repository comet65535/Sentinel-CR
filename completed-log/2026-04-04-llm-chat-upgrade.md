# Sentinel-CR Upgrade Status (2026-04-04)

## 已实现（默认主路径）
- Conversation/thread 语义：`/api/reviews` 兼容保留，并支持 `conversationId/messageId/parentMessageId/messageText`。
- 前端改为聊天式主界面：左侧会话、中心聊天流、右侧过程抽屉；提交后 composer 清空但消息留在会话流。
- 默认请求携带 `llm_enabled/llm_provider/llm_model/llm_tool_mode`。
- Python 主链路改为 LLM-centric action loop（含工具执行回灌），Verifier 仍是硬门禁，支持失败反思重试。
- 移除 whitespace/manual_review/no-op fallback patch 行为；LLM 不可用时结构化失败。
- short-term memory 改为 conversation-keyed（SQLite `thread_state`），follow-up 可复用最新 verifier failure。
- Debug Mode 与 User Mode 分离：Debug 才展示 tool/memory/raw 等追踪细节。

## 默认启用策略
- 当请求未显式设置 `llm_enabled` 时：若存在可用凭证（`SENTINEL_LLM_API_KEY` / `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`）则自动启用 LLM。
- 当显式 `llm_enabled=true` 但凭证缺失时：任务返回结构化失败，不生成伪补丁。

## Roadmap（明确未完成）
- 多 provider 的完整 native tool-calling 统一编排与更细粒度权限控制。
- MCP 资源的更丰富策略化调度与跨仓库缓存优化。
- 分布式 conversation store（当前为单机 SQLite）。
