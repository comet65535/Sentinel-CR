import { describe, expect, it } from 'vitest'
import { buildReadableFailureMessage } from './reviewEventView'

describe('reviewEventView failure message', () => {
  it('renders taxonomy and next context hint', () => {
    const message = buildReadableFailureMessage(
      {
        summary: {
          failed_stage: 'fixer',
          failure_reason: 'llm_output_invalid',
          failure_detail: 'missing key',
          retry_count: 0,
          retry_exhausted: false,
          no_fix_needed: false,
          user_message: '-',
        },
        execution_truth: {
          failure_taxonomy: { bucket: 'llm_output_invalid' },
          next_context_hint: 'provide method context',
        },
      },
      'fallback'
    )
    expect(message).toContain('taxonomy=llm_output_invalid')
    expect(message).toContain('provide method context')
  })
})
