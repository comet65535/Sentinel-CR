export type ReviewTaskStatus = 'CREATED' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface CreateReviewRequest {
  codeText: string
  language: 'java'
  sourceType: 'snippet'
  options?: {
    enable_verifier?: boolean
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
  result: Record<string, unknown>
  errorMessage: string | null
}

export interface ReviewEvent {
  taskId: string
  eventType: string
  message: string
  timestamp: string
  sequence: number
  status: ReviewTaskStatus
  payload: Record<string, unknown>
}
