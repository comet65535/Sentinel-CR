<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { createReviewEventSource, createReviewTask, fetchReviewTask } from '../api/review'
import ProgressHeader from '../components/ProgressHeader.vue'
import ResultSummaryCard from '../components/ResultSummaryCard.vue'
import ReviewForm from '../components/ReviewForm.vue'
import ReviewSidebar from '../components/ReviewSidebar.vue'
import StageDetailPanel from '../components/StageDetailPanel.vue'
import type { ReviewEvent, ReviewTaskStatus } from '../types/review'
import {
  SSE_EVENT_TYPES,
  buildEventSummary,
  buildStageProgress,
  eventsForStage,
  getEventTitle,
  summarizePayload,
  toStatusText,
  type StageKey,
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
const taskId = ref('')
const taskStatus = ref<'IDLE' | ReviewTaskStatus>('IDLE')
const events = ref<ReviewEvent[]>([])
const submitting = ref(false)
const errorMessage = ref('')
const debugMode = ref(false)
const detailPanelOpen = ref(false)
const selectedStageKey = ref<StageKey | null>(null)

let eventSource: EventSource | null = null

const sortedEvents = computed(() => [...events.value].sort((left, right) => left.sequence - right.sequence))

const stageItems = computed(() => buildStageProgress(sortedEvents.value, taskStatus.value))

const currentStage = computed(() => {
  return (
    stageItems.value.find((item) => item.status === 'active') ||
    stageItems.value.find((item) => item.status === 'failed') ||
    [...stageItems.value].reverse().find((item) => item.status === 'completed') ||
    stageItems.value[0] ||
    null
  )
})

const selectedStage = computed(
  () => stageItems.value.find((item) => item.key === selectedStageKey.value) || currentStage.value
)

const selectedStageEvents = computed(() => {
  const stageKey = selectedStage.value?.key
  if (!stageKey) return []
  return eventsForStage(stageKey, sortedEvents.value)
})

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

const resultStats = computed(() => {
  const result = reviewResult.value ?? {}
  const summary = isObject(result.summary) ? (result.summary as Record<string, unknown>) : {}
  const memory = isObject(result.memory) ? (result.memory as Record<string, unknown>) : {}
  const patch = isObject(result.patch) ? (result.patch as Record<string, unknown>) : {}

  return {
    issueCount: toArrayCount(result.issues),
    repairPlanCount: toArrayCount(result.repair_plan),
    memoryMatchCount: toArrayCount(memory.matches),
    attemptCount: toArrayCount(result.attempts),
    patchStatus: typeof patch.status === 'string' ? patch.status : '-',
    finalOutcome: typeof summary.final_outcome === 'string' ? summary.final_outcome : '-',
    verifiedLevel: typeof summary.verified_level === 'string' ? summary.verified_level : 'L0',
  }
})

watch(
  stageItems,
  (nextItems) => {
    if (nextItems.length === 0) {
      selectedStageKey.value = null
      return
    }

    if (selectedStageKey.value && nextItems.some((item) => item.key === selectedStageKey.value)) {
      return
    }

    selectedStageKey.value =
      nextItems.find((item) => item.status === 'active')?.key ||
      nextItems.find((item) => item.status === 'failed')?.key ||
      nextItems[0].key
  },
  { immediate: true }
)

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
  selectedStageKey.value = null
  detailPanelOpen.value = false
  closeEventSource()

  try {
    const response = await createReviewTask({
      codeText: code.value,
      language: 'java',
      sourceType: 'snippet',
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

function openStageDetail(stageKey: string) {
  selectedStageKey.value = stageKey as StageKey
  detailPanelOpen.value = true
}

function openCurrentStageDetail() {
  if (currentStage.value) {
    openStageDetail(currentStage.value.key)
  }
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
  selectedStageKey.value = null
}

onBeforeUnmount(() => {
  closeEventSource()
})

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function toArrayCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}
</script>

<template>
  <main class="page-layout">
    <ReviewSidebar :task-id="taskId" :task-status="taskStatus" @new-analysis="startNewAnalysis" />

    <section class="workspace">
      <section class="workspace-header panel">
        <p class="eyebrow">Sentinel-CR Day4.5 + Day5</p>
        <h1>Patch 验证工作台</h1>
        <p class="hint">默认展示当前阶段与结果摘要，完整事件细节在右侧详情面板按需展开。</p>
        <p class="status-line">
          <strong>任务状态：</strong>{{ toStatusText(taskStatus) }}
          <span class="task-id"><strong>任务 ID：</strong>{{ taskId || '-' }}</span>
        </p>
      </section>

      <ProgressHeader :stages="stageItems" :selected-key="selectedStageKey" @select-stage="openStageDetail" />

      <section class="panel current-stage-card">
        <header>
          <h2>当前阶段</h2>
          <button type="button" class="detail-btn" @click="openCurrentStageDetail">查看详情</button>
        </header>
        <p class="current-title">{{ currentStage?.title ?? '等待任务启动' }}</p>
        <p class="current-hint">{{ currentStage?.hint ?? '暂无阶段信息' }}</p>
      </section>

      <ResultSummaryCard :has-result="Boolean(reviewResult)" :stats="resultStats" />

      <section class="panel form-panel">
        <ReviewForm v-model:code="code" :submitting="submitting" @submit="submitReview" />
      </section>

      <section class="panel meta-panel">
        <label class="debug-toggle">
          <input v-model="debugMode" type="checkbox" />
          <span>Debug 模式（仅影响右侧详情粒度）</span>
        </label>
      </section>

      <section v-if="errorMessage" class="panel error-box">
        {{ errorMessage }}
      </section>
    </section>

    <StageDetailPanel
      :open="detailPanelOpen"
      :selected-stage="selectedStage"
      :stage-events="selectedStageEvents"
      :debug-mode="debugMode"
      :get-title="getEventTitle"
      :get-summary="buildEventSummary"
      :summarize-payload="summarizePayload"
      @close="closeDetailPanel"
    />
  </main>
</template>

<style scoped>
.page-layout {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: start;
}

.workspace {
  display: grid;
  gap: 0.9rem;
  min-width: 0;
}

.panel {
  background: #fff;
  border: 1px solid #d7e1eb;
  border-radius: 14px;
  padding: 0.9rem;
}

.workspace-header h1 {
  margin: 0.1rem 0;
  font-size: clamp(1.3rem, 3vw, 1.85rem);
  color: #153243;
}

.eyebrow {
  margin: 0;
  color: #176891;
  letter-spacing: 0.08em;
  font-size: 0.78rem;
  text-transform: uppercase;
  font-weight: 700;
}

.hint {
  margin: 0;
  color: #4e687c;
}

.status-line {
  margin: 0.35rem 0 0;
  color: #214557;
  display: flex;
  gap: 0.9rem;
  flex-wrap: wrap;
}

.current-stage-card {
  display: grid;
  gap: 0.45rem;
}

.current-stage-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
}

.current-stage-card h2 {
  margin: 0;
  color: #17384b;
  font-size: 1rem;
}

.current-title {
  margin: 0;
  color: #1d4860;
  font-weight: 700;
}

.current-hint {
  margin: 0;
  color: #546f82;
}

.detail-btn {
  border: 1px solid #c9d7e5;
  border-radius: 999px;
  background: #f8fbff;
  color: #1f4a61;
  padding: 0.35rem 0.75rem;
  cursor: pointer;
}

.form-panel {
  padding: 0;
  overflow: hidden;
}

.meta-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.debug-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: #1e4d63;
  font-size: 0.92rem;
}

.error-box {
  border-color: #d78989;
  background: #fff3f3;
  color: #9f3333;
}

@media (max-width: 1100px) {
  .page-layout {
    grid-template-columns: 1fr;
  }
}
</style>

