<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { createReviewEventSource, createReviewTask, fetchReviewTask } from '../api/review'
import ResultSummaryCard from '../components/ResultSummaryCard.vue'
import ReviewForm from '../components/ReviewForm.vue'
import ReviewSidebar from '../components/ReviewSidebar.vue'
import StageDetailPanel from '../components/StageDetailPanel.vue'
import type { ReviewEvent, ReviewTaskStatus } from '../types/review'
import {
  SSE_EVENT_TYPES,
  buildConversationItems,
  buildReadableCurrentStatus,
  buildReadableStageTimeline,
  extractResultStats,
  toStatusText,
} from '../utils/reviewEventView'

const DEFAULT_SNIPPET = `class snippet {
    String greet(String name) {
        if (name == null) {
            return "hello";
        }
        return "hello " + name;
    }
}`

const code = ref(DEFAULT_SNIPPET)
const submittedCode = ref('')
const taskId = ref('')
const taskStatus = ref<'IDLE' | ReviewTaskStatus>('IDLE')
const events = ref<ReviewEvent[]>([])
const submitting = ref(false)
const errorMessage = ref('')
const debugMode = ref(false)
const detailPanelOpen = ref(false)

let eventSource: EventSource | null = null

const sortedEvents = computed(() => [...events.value].sort((left, right) => left.sequence - right.sequence))

const reviewResult = computed<Record<string, unknown> | null>(() => {
  const completed = [...sortedEvents.value]
    .reverse()
    .find((event) => event.eventType === 'review_completed')
  if (!completed) return null
  if (completed.payload && typeof completed.payload.result === 'object' && completed.payload.result !== null) {
    return completed.payload.result as Record<string, unknown>
  }
  return completed.payload as Record<string, unknown>
})

const currentStatusLine = computed(() =>
  buildReadableCurrentStatus(sortedEvents.value, reviewResult.value)
)

const conversationItems = computed(() =>
  buildConversationItems(
    sortedEvents.value,
    reviewResult.value,
    submittedCode.value,
    currentStatusLine.value
  )
)

const stageTimeline = computed(() =>
  buildReadableStageTimeline(sortedEvents.value, reviewResult.value)
)

const resultStats = computed(() => {
  if (!reviewResult.value) {
    return {
      issueCount: 0,
      repairPlanCount: 0,
      memoryMatchCount: 0,
      attemptCount: 0,
      retryCount: 0,
      patchStatus: '-',
      finalOutcome: '-',
      verifiedLevel: 'L0',
      failedStage: '-',
      failureReason: '-',
      failureDetail: '-',
      userMessage: '-',
      retryExhausted: false,
      noFixNeeded: false,
    }
  }
  return extractResultStats(reviewResult.value)
})

const patchContent = computed(() => {
  if (!reviewResult.value) {
    return ''
  }
  const patch = reviewResult.value.patch
  if (typeof patch === 'object' && patch !== null && typeof (patch as Record<string, unknown>).content === 'string') {
    return String((patch as Record<string, unknown>).content)
  }
  return ''
})

const isProcessing = computed(() => {
  if (taskStatus.value === 'RUNNING' || taskStatus.value === 'CREATED') return true
  if (submitting.value) return true
  return reviewResult.value === null && events.value.length > 0
})

function isTaskFinished(status: string): boolean {
  return status === 'COMPLETED' || status === 'FAILED'
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
}

function upsertEvent(event: ReviewEvent) {
  const index = events.value.findIndex((item) => item.sequence === event.sequence)
  if (index >= 0) {
    events.value.splice(index, 1, event)
  } else {
    events.value.push(event)
  }

  taskStatus.value = event.status

  if (isTaskFinished(event.status)) {
    closeEventSource()
  }
}

function subscribeEventStream(nextTaskId: string) {
  closeEventSource()
  const source = createReviewEventSource(nextTaskId)
  eventSource = source

  const handleEventMessage = (messageEvent: MessageEvent<string>) => {
    try {
      const event = JSON.parse(messageEvent.data) as ReviewEvent
      upsertEvent(event)
    } catch {
      errorMessage.value = '服务端事件解析失败。'
    }
  }

  source.onmessage = handleEventMessage
  SSE_EVENT_TYPES.forEach((eventType) => {
    source.addEventListener(eventType, (event) => {
      handleEventMessage(event as MessageEvent<string>)
    })
  })

  source.onopen = () => {
    if (errorMessage.value === '事件流连接中断。') {
      errorMessage.value = ''
    }
  }

  source.onerror = async () => {
    if (isTaskFinished(taskStatus.value)) {
      closeEventSource()
      return
    }

    try {
      const latestTask = await fetchReviewTask(nextTaskId)
      taskStatus.value = latestTask.status
      if (isTaskFinished(latestTask.status)) {
        closeEventSource()
      } else {
        errorMessage.value = '事件流连接中断。'
      }
    } catch {
      errorMessage.value = '事件流出错，且任务状态查询失败。'
    }
  }
}

async function submitReview() {
  if (!code.value.trim()) {
    errorMessage.value = '代码输入不能为空。'
    return
  }

  submitting.value = true
  errorMessage.value = ''
  events.value = []
  taskId.value = ''
  taskStatus.value = 'IDLE'
  detailPanelOpen.value = false
  submittedCode.value = code.value
  closeEventSource()

  try {
    const response = await createReviewTask({
      codeText: code.value,
      language: 'java',
      sourceType: 'snippet',
      options: {
        enable_verifier: true,
        max_retries: 2,
        enable_security_rescan: false,
      },
    })
    taskId.value = response.taskId
    taskStatus.value = response.status
    subscribeEventStream(response.taskId)
  } catch (error) {
    if (error instanceof Error) {
      errorMessage.value = error.message
    } else {
      errorMessage.value = '请求失败。'
    }
  } finally {
    submitting.value = false
  }
}

function openDetailPanel() {
  detailPanelOpen.value = true
}

function closeDetailPanel() {
  detailPanelOpen.value = false
}

function startNewAnalysis() {
  closeEventSource()
  events.value = []
  taskId.value = ''
  taskStatus.value = 'IDLE'
  errorMessage.value = ''
  detailPanelOpen.value = false
  submittedCode.value = ''
}

onBeforeUnmount(() => {
  closeEventSource()
})
</script>

<template>
  <main class="layout">
    <ReviewSidebar :task-id="taskId" :task-status="taskStatus" @new-analysis="startNewAnalysis" />

    <section class="chat-column">
      <header class="chat-header">
        <div class="header-actions">
          <span class="line-label">当前进度：</span>
          <button class="status-line" type="button" @click="openDetailPanel">
            <span v-if="isProcessing" class="pulse-dot" />
            <span>{{ currentStatusLine }}</span>
          </button>
        </div>

        <div class="header-actions secondary">
          <span class="task-text">任务：{{ taskId || '-' }} · {{ toStatusText(taskStatus) }}</span>
          <button class="process-btn" type="button" @click="openDetailPanel">查看过程</button>
          <label class="debug-toggle">
            <input v-model="debugMode" type="checkbox" />
            <span>Debug</span>
          </label>
        </div>
      </header>

      <section class="chat-thread">
        <div v-if="conversationItems.length === 0" class="empty">
          <p>把 Java 代码发给我，我会先分析，再给出补丁与验证结果。</p>
        </div>

        <article
          v-for="item in conversationItems"
          :key="item.id"
          class="message"
          :class="item.role === 'user' ? 'message-user' : 'message-assistant'"
        >
          <p class="sender">{{ item.title }}</p>
          <p v-if="item.type !== 'status'" class="text">{{ item.text }}</p>

          <pre v-if="item.code" class="code-block">{{ item.code }}</pre>

          <button v-if="item.type === 'status'" class="status-bubble" type="button" @click="openDetailPanel">
            <span class="pulse-dot" />
            <span>{{ item.text }}</span>
          </button>

          <ResultSummaryCard
            v-if="item.type === 'result'"
            :has-result="Boolean(reviewResult)"
            :stats="resultStats"
            :patch-content="patchContent"
            @open-process="openDetailPanel"
          />
        </article>

        <article v-if="errorMessage" class="message message-assistant message-error">
          <p class="sender">Sentinel-CR</p>
          <p class="text">{{ errorMessage }}</p>
        </article>
      </section>

      <footer class="composer-wrap">
        <ReviewForm v-model:code="code" :submitting="submitting" @submit="submitReview" />
      </footer>
    </section>

    <StageDetailPanel
      :open="detailPanelOpen"
      :timeline="stageTimeline"
      :debug-mode="debugMode"
      @close="closeDetailPanel"
    />
  </main>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: start;
}

.chat-column {
  min-width: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 0.75rem;
  min-height: calc(100vh - 2.4rem);
}

.chat-header {
  border: 1px solid #dfe6f1;
  background: #fff;
  border-radius: 14px;
  padding: 0.65rem 0.75rem;
  display: grid;
  gap: 0.5rem;
}

.status-line {
  border: 1px solid #d1deee;
  background: #f3f8ff;
  color: #1f4c67;
  border-radius: 999px;
  padding: 0.45rem 0.72rem;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-weight: 600;
  cursor: pointer;
  justify-self: start;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.header-actions.secondary {
  justify-content: space-between;
}

.line-label {
  color: #5d7488;
  font-size: 0.84rem;
}

.task-text {
  color: #5d7488;
  font-size: 0.84rem;
}

.process-btn {
  border: 1px solid #d1dcec;
  background: #f8fbff;
  color: #2b5167;
  border-radius: 999px;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
}

.debug-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #4e677b;
  font-size: 0.84rem;
}

.chat-thread {
  border: 1px solid #dfe6f1;
  background: #fff;
  border-radius: 14px;
  padding: 0.9rem;
  overflow: auto;
  display: grid;
  gap: 0.75rem;
  align-content: start;
}

.empty {
  color: #5f788a;
}

.empty p {
  margin: 0;
}

.message {
  max-width: 92%;
  border-radius: 14px;
  padding: 0.7rem 0.75rem;
  display: grid;
  gap: 0.4rem;
}

.message-user {
  justify-self: end;
  background: #edf4ff;
  border: 1px solid #cfdef4;
}

.message-assistant {
  justify-self: start;
  background: #f8fafd;
  border: 1px solid #dee6f0;
}

.message-error {
  border-color: #d8a1a1;
  background: #fff3f3;
}

.sender {
  margin: 0;
  color: #5e7587;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 700;
}

.text {
  margin: 0;
  color: #234b61;
}

.code-block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid #d2deee;
  background: #f4f8ff;
  border-radius: 10px;
  padding: 0.6rem;
  color: #1c3a4f;
  font-size: 0.82rem;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
}

.status-bubble {
  border: 1px dashed #bcd2e8;
  background: #f2f8ff;
  border-radius: 10px;
  padding: 0.45rem 0.55rem;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #31566b;
  cursor: pointer;
  text-align: left;
}

.composer-wrap {
  position: sticky;
  bottom: 0;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2f88bc;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.35;
    transform: scale(0.95);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
  100% {
    opacity: 0.35;
    transform: scale(0.95);
  }
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .chat-column {
    min-height: auto;
  }

  .message {
    max-width: 100%;
  }
}
</style>
