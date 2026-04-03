import { describe, expect, it } from 'vitest'
import type { ReviewEvent } from '../types/review'
import { resolveResultByPriority } from './reviewResult'

function event(input: Partial<ReviewEvent>): ReviewEvent {
  return {
    taskId: 'rev_1',
    eventType: 'analysis_started',
    message: '',
    timestamp: '',
    sequence: 1,
    status: 'RUNNING',
    payload: {},
    ...input,
  }
}

describe('resolveResultByPriority', () => {
  it('prefers review_completed.result over accumulated payload', () => {
    const result = resolveResultByPriority([
      event({
        sequence: 1,
        eventType: 'context_budget_updated',
        payload: { context_budget: { used_tokens: 100 } },
      }),
      event({
        sequence: 2,
        eventType: 'review_completed',
        status: 'COMPLETED',
        payload: { result: { summary: { verified_level: 'L3' } } },
      }),
    ])
    expect(result).toEqual({ summary: { verified_level: 'L3' } })
  })

  it('falls back to accumulated event payload when review_completed is absent', () => {
    const result = resolveResultByPriority([
      event({
        sequence: 1,
        eventType: 'patch_generated',
        payload: { patch: { unified_diff: 'diff --git a b' } },
      }),
    ])
    expect(result).toEqual({ patch: { unified_diff: 'diff --git a b' } })
  })
})
