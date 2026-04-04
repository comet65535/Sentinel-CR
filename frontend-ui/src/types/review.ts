export type ReviewTaskStatus = 'CREATED' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface FailureTaxonomy {
  bucket: string
  code: string | null
  explanation: string | null
}

export interface ContextBudgetSource {
  kind: string
  id: string
  tokens: number
  reason: string
}

export interface ContextBudget {
  enabled?: boolean
  budget_tokens?: number
  used_tokens?: number
  remaining_tokens?: number
  load_stage?: string
  sources?: ContextBudgetSource[]
}

export interface ToolTraceItem {
  tool_name?: string
  args?: Record<string, unknown>
  success?: boolean
  latency_ms?: number
  selected_by?: string
  expected_tool?: string
  phase?: string
  [key: string]: unknown
}

export interface LlmTraceItem {
  phase?: string
  prompt_name?: string
  provider?: string
  model?: string
  token_in?: number
  token_out?: number
  latency_ms?: number
  json_mode?: boolean
  tool_mode?: string
  cache_hit_tokens?: number
  cache_miss_tokens?: number
  [key: string]: unknown
}

export interface ReviewSummary {
  issue_count: number
  repair_plan_count: number
  memory_match_count: number
  attempt_count: number
  retry_count: number
  verified_level: string
  final_outcome: string
  failed_stage: string | null
  failure_reason: string | null
  failure_detail: string | null
  retry_exhausted: boolean
  no_fix_needed: boolean
  user_message: string
  failure_taxonomy: FailureTaxonomy
}

export interface DeliveryResult {
  unified_diff: string
  verified_level: string
  verification_stages: Array<Record<string, unknown>>
  final_outcome: string
  failed_stage?: string | null
  failure_code?: string | null
  failure_reason?: string | null
  retryable?: boolean
}

export interface ReviewMemory {
  matches: Record<string, unknown>[]
  short_term?: Record<string, unknown>
  repo_profile?: Record<string, unknown>
  case_store?: Record<string, unknown>
  case_store_summary?: Record<string, unknown>
}

export interface ReviewResult {
  engine: string
  delivery: DeliveryResult
  summary: ReviewSummary
  analyzer: Record<string, unknown>
  analyzer_evidence: Record<string, unknown>
  issues: Record<string, unknown>[]
  symbols: Record<string, unknown>[]
  contextSummary: Record<string, unknown>
  diagnostics: Record<string, unknown>[]
  issue_graph: Record<string, unknown>
  repair_plan: Record<string, unknown>[]
  planner_summary: Record<string, unknown>
  memory: ReviewMemory
  memory_hits?: Record<string, unknown>
  context_budget: ContextBudget
  selected_context: Record<string, unknown>[]
  tool_trace: ToolTraceItem[]
  llm_trace: LlmTraceItem[]
  repo_profile?: Record<string, unknown>
  patch: Record<string, unknown>
  attempts: Record<string, unknown>[]
  verification: Record<string, unknown> | null
  user_events?: Record<string, unknown>[]
  debug_events?: Record<string, unknown>[]
}

export interface CreateReviewRequest {
  codeText?: string
  messageText?: string
  conversationId?: string
  messageId?: string
  parentMessageId?: string
  language: 'java'
  sourceType: 'snippet'
  options?: {
    enable_verifier?: boolean
    enable_mcp?: boolean
    max_retries?: number
    enable_security_rescan?: boolean
    debug?: boolean
    context_policy?: 'none' | 'lazy'
    context_budget_tokens?: number
    persist_verified_case?: boolean
    llm_enabled?: boolean
    llm_provider?: string
    llm_model?: string
    llm_tool_mode?: string
  }
  metadata?: Record<string, unknown>
}

export interface CreateReviewResponse {
  taskId: string
  conversationId: string
  messageId: string
  status: ReviewTaskStatus
  message: string
}

export interface ReviewTask {
  taskId: string
  conversationId?: string
  messageId?: string
  parentMessageId?: string
  status: ReviewTaskStatus
  createdAt: string
  updatedAt: string
  result: ReviewResult | Record<string, unknown>
  errorMessage: string | null
}

export interface ReviewEvent {
  taskId: string
  eventType: string
  message: string
  timestamp: string
  sequence: number
  status: ReviewTaskStatus
  payload: Record<string, unknown> & { result?: ReviewResult }
}

export interface ReviewHistoryItem {
  task_id: string
  conversation_id?: string
  message_id?: string
  status: ReviewTaskStatus
  created_at: string
  updated_at: string
  title: string
  input_kind: string
  summary: {
    final_status: string
    verified_level: string
    failure_taxonomy: {
      bucket: string
    }
  }
  has_patch: boolean
}

export interface ConversationSummary {
  conversation_id: string
  title: string
  created_at: string
  updated_at: string
  latest_message?: string
  latest_task_id?: string
}

export interface ConversationMessage {
  message_id: string
  conversation_id: string
  parent_message_id?: string
  role: 'user' | 'assistant'
  message_text?: string
  code_text?: string
  task_id?: string
  created_at: string
}
