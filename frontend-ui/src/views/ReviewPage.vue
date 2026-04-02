<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { createReviewEventSource, createReviewTask, fetchReviewTask } from '../api/review'
import EventTimeline from '../components/EventTimeline.vue'
import ReviewForm from '../components/ReviewForm.vue'
import type { ReviewEvent, ReviewTaskStatus } from '../types/review'

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

let eventSource: EventSource | null = null

const sortedEvents = computed(() =>
  [...events.value].sort((left, right) => left.sequence - right.sequence)
)

const SSE_EVENT_TYPES = [
  'task_created',
  'analysis_started',
  'ast_parsing_started',
  'ast_parsing_completed',
  'symbol_graph_started',
  'symbol_graph_completed',
  'semgrep_scan_started',
  'semgrep_scan_completed',
  'semgrep_scan_warning',
  'analyzer_completed',
  'review_completed',
  'review_failed',
  'heartbeat',
] as const

const AGGREGATED_EVENT_TYPES = new Set<string>([
  'task_created',
  'analysis_started',
  'ast_parsing_completed',
  'symbol_graph_completed',
  'semgrep_scan_completed',
  'semgrep_scan_warning',
  'analyzer_completed',
  'review_completed',
  'review_failed',
  'heartbeat',
])

const displayEvents = computed(() =>
  sortedEvents.value.filter((event) => AGGREGATED_EVENT_TYPES.has(event.eventType))
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
      errorMessage.value = 'Failed to parse server event payload.'
    }
  }

  source.onmessage = handleEventMessage
  SSE_EVENT_TYPES.forEach((eventType) => {
    source.addEventListener(eventType, (event) => {
      handleEventMessage(event as MessageEvent<string>)
    })
  })

  source.onopen = () => {
    if (errorMessage.value === 'Event stream was interrupted.') {
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
        errorMessage.value = 'Event stream was interrupted.'
      }
    } catch {
      errorMessage.value = 'Event stream error and task status check failed.'
    }
  }
}

async function submitReview() {
  if (!code.value.trim()) {
    errorMessage.value = 'Code input cannot be empty.'
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
      errorMessage.value = 'Request failed.'
    }
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(() => {
  closeEventSource()
})
</script>

<template>
  <main class="page">
    <section class="headline">
      <p class="eyebrow">Sentinel-CR Day0</p>
      <h1>Frontend -> Backend -> Mock AI -> SSE</h1>
      <p class="hint">
        Submit a Java snippet and watch the event stream move to completion.
      </p>
    </section>

    <ReviewForm v-model:code="code" :submitting="submitting" @submit="submitReview" />

    <section class="panel meta">
      <p><strong>Task ID:</strong> {{ taskId || '-' }}</p>
      <p><strong>Status:</strong> {{ taskStatus }}</p>
    </section>

    <section v-if="errorMessage" class="panel error-box">
      {{ errorMessage }}
    </section>

    <EventTimeline :events="displayEvents" />
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
  font-size: clamp(1.4rem, 4vw, 2rem);
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
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.meta p {
  margin: 0;
  color: #214455;
}

.error-box {
  border-color: #d78989;
  background: #fff3f3;
  color: #9f3333;
}
</style>
