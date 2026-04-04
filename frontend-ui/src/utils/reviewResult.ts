import type { ReviewEvent } from '../types/review'

export function extractCompletedResult(events: ReviewEvent[]): Record<string, unknown> | null {
  const completed = [...events].reverse().find((event) => event.eventType === 'review_completed')
  if (!completed) return null
  if (completed.payload && typeof completed.payload.result === 'object' && completed.payload.result !== null) {
    return completed.payload.result as Record<string, unknown>
  }
  if (completed.payload && typeof completed.payload === 'object') {
    return completed.payload as Record<string, unknown>
  }
  return null
}

export function buildAccumulatedResult(events: ReviewEvent[]): Record<string, unknown> | null {
  const result: Record<string, unknown> = {}
  for (const event of events) {
    const payload = event.payload
    if (payload && typeof payload.result === 'object' && payload.result !== null) {
      Object.assign(result, payload.result as Record<string, unknown>)
    }
    if (payload.issue_graph && typeof payload.issue_graph === 'object') result.issue_graph = payload.issue_graph
    if (payload.delivery && typeof payload.delivery === 'object') result.delivery = payload.delivery
    if (payload.context_budget && typeof payload.context_budget === 'object') result.context_budget = payload.context_budget
    if (payload.verification && typeof payload.verification === 'object') result.verification = payload.verification
    if (payload.patch && typeof payload.patch === 'object') result.patch = payload.patch
    if (Array.isArray(payload.tool_trace)) result.tool_trace = payload.tool_trace
    if (Array.isArray(payload.llm_trace)) result.llm_trace = payload.llm_trace
  }
  return Object.keys(result).length > 0 ? result : null
}

export function resolveResultByPriority(events: ReviewEvent[]): Record<string, unknown> | null {
  const completed = extractCompletedResult(events)
  if (completed) return completed
  return buildAccumulatedResult(events)
}
