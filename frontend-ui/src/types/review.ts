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

export interface ReviewMemory {
  matches: Record<string, unknown>[]
  short_term?: Record<string, unknown>
  repo_profile?: Record<string, unknown>
  case_store?: Record<string, unknown>
  case_store_summary?: Record<string, unknown>
}

export interface ReviewResult {
  engine: string
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
  context_budget: ContextBudget
  selected_context: Record<string, unknown>[]
  tool_trace: ToolTraceItem[]
  llm_trace: LlmTraceItem[]
  repo_profile?: Record<string, unknown>
  patch: Record<string, unknown>
  attempts: Record<string, unknown>[]
  verification: Record<string, unknown> | null
}

export interface CreateReviewRequest {
  codeText: string
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
  }
  metadata?: Record<string, unknown>
}

export interface CreateReviewResponse {
  taskId: string
  status: ReviewTaskStatus
  message: string
}

export interface ReviewTask {
  taskId: string
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
