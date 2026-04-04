import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import StageDetailPanel from './StageDetailPanel.vue'

const baseProps = {
  open: true,
  timeline: [],
  reviewResult: {},
  events: [],
}

describe('StageDetailPanel', () => {
  it('hides debug tabs in user mode', () => {
    const wrapper = mount(StageDetailPanel, {
      props: { ...baseProps, debugMode: false },
      global: {
        stubs: {
          IssueGraphPanel: true,
          PatchDiffViewer: true,
          TokenContextPanel: true,
          ToolTracePanel: true,
          BenchmarkPanel: true,
        },
      },
    })
    expect(wrapper.text()).not.toContain('Issue Graph')
    expect(wrapper.text()).not.toContain('Memory')
    expect(wrapper.text()).not.toContain('Tool Trace')
    expect(wrapper.text()).not.toContain('Raw Payload')
  })

  it('shows debug tabs in debug mode', () => {
    const wrapper = mount(StageDetailPanel, {
      props: { ...baseProps, debugMode: true },
      global: {
        stubs: {
          IssueGraphPanel: true,
          PatchDiffViewer: true,
          TokenContextPanel: true,
          ToolTracePanel: true,
          BenchmarkPanel: true,
        },
      },
    })
    expect(wrapper.text()).toContain('Issue Graph')
    expect(wrapper.text()).toContain('Memory')
    expect(wrapper.text()).toContain('Tool Trace')
    expect(wrapper.text()).toContain('Raw Payload')
  })
})
