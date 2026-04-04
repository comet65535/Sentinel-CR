import { describe, expect, it } from 'vitest'
import { buildReadableFailureMessage } from './reviewEventView'

describe('reviewEventView llm failure message', () => {
  it('renders explicit llm disabled message', () => {
    const message = buildReadableFailureMessage(
      {
        summary: {
          failed_stage: 'fixer',
          failure_reason: 'llm_not_enabled_or_missing_credentials',
          failure_detail: 'missing key',
          retry_count: 0,
          retry_exhausted: false,
          no_fix_needed: false,
          user_message: '-',
        },
      },
      'fallback'
    )
    expect(message).toContain('LLM disabled / missing credentials')
  })
})
