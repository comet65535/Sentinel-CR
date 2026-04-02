<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { createReviewEventSource, createReviewTask, fetchReviewTask } from '../api/review'
import EventTimeline from '../components/EventTimeline.vue'
import ReviewForm from '../components/ReviewForm.vue'
import type { ReviewEvent, ReviewTaskStatus } from '../types/review'
import {
  AGGREGATED_EVENT_TYPES,
  SSE_EVENT_TYPES,
  buildEventSummary,
  getEventTitle,
  summarizePayload,
  toStatusText,
} from '../utils/reviewEventView'

const DEFAULT_SNIPPET = `public class Demo {
    public String greet(String name) {
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

let eventSource: EventSource | null = null

const sortedEvents = computed(() => [...events.value].sort((left, right) => left.sequence - right.sequence))

const displayEvents = computed(() =>
  debugMode.value
    ? sortedEvents.value
    : sortedEvents.value.filter((event) => AGGREGATED_EVENT_TYPES.has(event.eventType))
)

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

const analyzerSummary = computed<Record<string, unknown>>(() => {
  const result = reviewResult.value
  const analyzer = result?.analyzer
  if (typeof analyzer === 'object' && analyzer !== null) {
    return analyzer as Record<string, unknown>
  }
  return {}
})

const resultStats = computed(() => {
  const result = reviewResult.value ?? {}
  const analyzer = analyzerSummary.value
  const symbols = Array.isArray(result.symbols) ? result.symbols : []
  const issues = Array.isArray(result.issues) ? result.issues : []
  const diagnostics = Array.isArray(result.diagnostics) ? result.diagnostics : []
  const repairPlan = Array.isArray(result.repair_plan) ? result.repair_plan : []
  const issueGraph = isObject(result.issue_graph) ? (result.issue_graph as Record<string, unknown>) : {}
  const graphNodes = Array.isArray(issueGraph.nodes) ? issueGraph.nodes : []
  const graphEdges = Array.isArray(issueGraph.edges) ? issueGraph.edges : []

  return {
    issuesCount: issues.length,
    classesCount: toNumber(analyzer.classesCount),
    methodsCount: toNumber(analyzer.methodsCount),
    fieldsCount: toNumber(analyzer.fieldsCount),
    symbolsCount: symbols.length,
    diagnosticsCount: diagnostics.length,
    issueGraphNodesCount: graphNodes.length,
    issueGraphEdgesCount: graphEdges.length,
    repairPlanCount: repairPlan.length,
  }
})

const semgrepStatus = computed(() => {
  const eventTypes = new Set(sortedEvents.value.map((event) => event.eventType))
  if (eventTypes.has('semgrep_scan_warning')) return '降级'
  if (eventTypes.has('semgrep_scan_completed')) return '正常'
  return '未执行'
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

onBeforeUnmount(() => {
  closeEventSource()
})

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}
</script>

<template>
  <main class="page">
    <section class="headline">
      <p class="eyebrow">Sentinel-CR Day 3</p>
      <h1>Day 3 Issue Graph Planner · Analyzer + Planner</h1>
      <p class="hint">
        提交一段 Java 代码，观察 Analyzer 与 Planner 事件流、结构化问题图与修复计划。
      </p>
    </section>

    <ReviewForm v-model:code="code" :submitting="submitting" @submit="submitReview" />

    <section class="panel meta">
      <p><strong>任务 ID：</strong> {{ taskId || '-' }}</p>
      <p><strong>任务状态：</strong> {{ toStatusText(taskStatus) }}</p>
      <label class="debug-toggle">
        <input v-model="debugMode" type="checkbox" />
        <span>Debug 视图（显示全部细粒度事件）</span>
      </label>
    </section>

    <section class="panel result-card">
      <header class="result-header">
        <h2>Day 3 结果摘要</h2>
        <p>{{ reviewResult ? '已生成结构化结果' : '等待 review_completed 事件' }}</p>
      </header>
      <div class="result-grid">
        <p><strong>问题数：</strong>{{ resultStats.issuesCount }}</p>
        <p><strong>类数量：</strong>{{ resultStats.classesCount }}</p>
        <p><strong>方法数量：</strong>{{ resultStats.methodsCount }}</p>
        <p><strong>字段数量：</strong>{{ resultStats.fieldsCount }}</p>
        <p><strong>符号数量：</strong>{{ resultStats.symbolsCount }}</p>
        <p><strong>诊断数量：</strong>{{ resultStats.diagnosticsCount }}</p>
        <p><strong>问题图节点：</strong>{{ resultStats.issueGraphNodesCount }}</p>
        <p><strong>问题图边：</strong>{{ resultStats.issueGraphEdgesCount }}</p>
        <p><strong>修复计划项：</strong>{{ resultStats.repairPlanCount }}</p>
        <p><strong>Semgrep 状态：</strong>{{ semgrepStatus }}</p>
        <p><strong>当前任务状态：</strong>{{ toStatusText(taskStatus) }}</p>
      </div>
    </section>

    <section v-if="errorMessage" class="panel error-box">
      {{ errorMessage }}
    </section>

    <EventTimeline
      :events="displayEvents"
      :debug-mode="debugMode"
      :get-title="getEventTitle"
      :get-summary="buildEventSummary"
      :summarize-payload="summarizePayload"
    />
    <p class="mode-note">
      {{
        debugMode
          ? 'Debug 模式：展示全部细粒度事件（含 *_started）。'
          : '默认模式：仅展示聚合阶段事件。'
      }}
    </p>
  </main>
</template>

<style scoped>
.page {
  width: min(920px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 1rem;
}

.headline h1 {
  margin: 0.1rem 0;
  font-size: clamp(1.35rem, 4vw, 1.9rem);
  color: #153243;
}

.eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #176891;
  font-size: 0.8rem;
  font-weight: 700;
}

.hint {
  margin: 0;
  color: #4d6778;
}

.panel {
  background: #ffffff;
  border: 1px solid #d5dce4;
  border-radius: 14px;
  padding: 1rem;
}

.meta {
  display: grid;
  gap: 0.35rem;
}

.meta p {
  margin: 0;
  color: #214455;
}

.debug-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  color: #1e4d63;
  font-size: 0.92rem;
}

.result-card {
  display: grid;
  gap: 0.75rem;
}

.result-header h2 {
  margin: 0;
  font-size: 1.05rem;
  color: #173647;
}

.result-header p {
  margin: 0.25rem 0 0;
  color: #567488;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.4rem 1rem;
}

.result-grid p {
  margin: 0;
  color: #214455;
}

.error-box {
  border-color: #d78989;
  background: #fff3f3;
  color: #9f3333;
}

.mode-note {
  margin: -0.25rem 0 0;
  color: #597286;
  font-size: 0.88rem;
}

@media (max-width: 720px) {
  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
