import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ReviewPage from './ReviewPage.vue'

const api = vi.hoisted(() => {
  const eventSource = {
    onmessage: null as ((ev: MessageEvent<string>) => void) | null,
    onopen: null as (() => void) | null,
    onerror: null as (() => void) | null,
    addEventListener: vi.fn(),
    close: vi.fn(),
  }
  return {
    eventSource,
    createReviewTask: vi.fn(),
    fetchConversations: vi.fn(),
    fetchConversationMessages: vi.fn(),
    fetchReviewTask: vi.fn(),
  }
})

vi.mock('../api/review', () => ({
  createReviewTask: api.createReviewTask,
  fetchConversations: api.fetchConversations,
  fetchConversationMessages: api.fetchConversationMessages,
  fetchReviewTask: api.fetchReviewTask,
  createReviewEventSource: () => api.eventSource,
}))

const stubs = {
  ReviewSidebar: {
    name: 'ReviewSidebar',
    emits: ['new-analysis', 'select-conversation'],
    template: '<div data-test="sidebar"></div>',
  },
  ReviewForm: {
    name: 'ReviewForm',
    props: ['message', 'code'],
    emits: ['update:message', 'update:code', 'submit'],
    template: '<div data-test="form"></div>',
  },
  StageDetailPanel: { template: '<div data-test="panel"></div>' },
  ResultSummaryCard: { template: '<div data-test="result"></div>' },
}

describe('ReviewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.fetchConversations.mockResolvedValue([])
    api.fetchConversationMessages.mockResolvedValue([
      {
        message_id: 'msg_user_1',
        conversation_id: 'conv-1',
        parent_message_id: null,
        role: 'user',
        message_text: '只修语法',
        code_text: 'class snippet {}',
        task_id: 'task-1',
        created_at: new Date().toISOString(),
      },
    ])
    api.fetchReviewTask.mockResolvedValue({
      taskId: 'task-1',
      status: 'COMPLETED',
      createdAt: '',
      updatedAt: '',
      result: {},
      errorMessage: null,
    })
  })

  it('sends llm options and clears composer after submit', async () => {
    api.createReviewTask.mockResolvedValue({
      taskId: 'task-1',
      conversationId: 'conv-1',
      messageId: 'msg-1',
      status: 'CREATED',
      message: 'ok',
    })
    const wrapper = mount(ReviewPage, { global: { stubs } })
    await flushPromises()

    const form = wrapper.findComponent({ name: 'ReviewForm' })
    form.vm.$emit('update:message', '只修语法')
    form.vm.$emit('update:code', 'class snippet {}')
    form.vm.$emit('submit')
    await flushPromises()

    expect(api.createReviewTask).toHaveBeenCalledTimes(1)
    const payload = api.createReviewTask.mock.calls[0][0]
    expect(payload.options.llm_enabled).toBe(true)
    expect(payload.options.llm_provider).toBeTypeOf('string')
    expect(payload.options.llm_model).toBeTypeOf('string')
    expect(payload.options.llm_tool_mode).toBeTypeOf('string')

    const latestFormProps = wrapper.findComponent({ name: 'ReviewForm' }).props()
    expect(latestFormProps.message).toBe('')
    expect(latestFormProps.code).toBe('')
    expect(wrapper.text()).toContain('只修语法')
  })

  it('reuses conversation id on follow-up submit', async () => {
    api.createReviewTask
      .mockResolvedValueOnce({
        taskId: 'task-1',
        conversationId: 'conv-1',
        messageId: 'msg-1',
        status: 'CREATED',
        message: 'ok',
      })
      .mockResolvedValueOnce({
        taskId: 'task-2',
        conversationId: 'conv-1',
        messageId: 'msg-2',
        status: 'CREATED',
        message: 'ok',
      })

    const wrapper = mount(ReviewPage, { global: { stubs } })
    await flushPromises()

    const form = wrapper.findComponent({ name: 'ReviewForm' })
    form.vm.$emit('update:message', '第一轮')
    form.vm.$emit('update:code', 'class snippet {}')
    form.vm.$emit('submit')
    await flushPromises()

    form.vm.$emit('update:message', '第二轮 follow-up')
    form.vm.$emit('update:code', '')
    form.vm.$emit('submit')
    await flushPromises()

    expect(api.createReviewTask).toHaveBeenCalledTimes(2)
    const secondPayload = api.createReviewTask.mock.calls[1][0]
    expect(secondPayload.conversationId).toBe('conv-1')
  })
})
