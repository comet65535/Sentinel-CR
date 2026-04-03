import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import IssueGraphPanel from './IssueGraphPanel.vue'

describe('IssueGraphPanel', () => {
  it('renders placeholder when graph data is missing', () => {
    const wrapper = mount(IssueGraphPanel, {
      props: {
        issueGraph: null,
      },
    })
    expect(wrapper.text()).toContain('暂无 Issue Graph 数据')
  })

  it('renders svg nodes and supports node click', async () => {
    const wrapper = mount(IssueGraphPanel, {
      props: {
        issueGraph: {
          nodes: [
            { issue_id: 'ISSUE-1', type: 'null_pointer', severity: 'high' },
            { issue_id: 'ISSUE-2', type: 'sql_injection', severity: 'medium' },
          ],
          edges: [{ from_issue_id: 'ISSUE-1', to_issue_id: 'ISSUE-2', edge_type: 'depends_on' }],
        },
      },
    })

    expect(wrapper.find('svg.graph-svg').exists()).toBe(true)
    const nodes = wrapper.findAll('g.node')
    expect(nodes.length).toBe(2)
    await nodes[0].trigger('click')
    expect(wrapper.text()).toContain('ISSUE-1')
  })
})
