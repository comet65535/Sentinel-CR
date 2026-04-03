<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ReviewEvent } from '../types/review'
import type { ReadableStageTimelineItem } from '../utils/reviewEventView'
import BenchmarkPanel from './BenchmarkPanel.vue'
import IssueGraphPanel from './IssueGraphPanel.vue'
import PatchDiffViewer from './PatchDiffViewer.vue'
import TokenContextPanel from './TokenContextPanel.vue'
import ToolTracePanel from './ToolTracePanel.vue'

const props = defineProps<{
  open: boolean
  timeline: ReadableStageTimelineItem[]
  debugMode: boolean
  reviewResult: Record<string, unknown> | null
  events: ReviewEvent[]
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

const tab = ref<'overview' | 'patch' | 'issue' | 'verification' | 'memory' | 'trace' | 'benchmark' | 'raw'>(
  'overview'
)

const latestIssueGraph = computed(() => {
  const fromResult = props.reviewResult?.issue_graph
  if (fromResult && typeof fromResult === 'object') return fromResult as Record<string, unknown>
  for (let i = props.events.length - 1; i >= 0; i -= 1) {
    const event = props.events[i]
    if (event.eventType === 'issue_graph_built' && event.payload.issue_graph) {
      return event.payload.issue_graph as Record<string, unknown>
    }
  }
  return null
})

const latestContextBudget = computed(() => {
  const fromResult = props.reviewResult?.context_budget
  if (fromResult && typeof fromResult === 'object') return fromResult as Record<string, unknown>
  for (let i = props.events.length - 1; i >= 0; i -= 1) {
    const event = props.events[i]
    if (event.payload && typeof event.payload.context_budget === 'object') {
      return event.payload.context_budget as Record<string, unknown>
    }
  }
  return null
})

const patchContent = computed(() => {
  const patch = props.reviewResult?.patch
  if (!patch || typeof patch !== 'object') return ''
  const patchRecord = patch as Record<string, unknown>
  if (typeof patchRecord.unified_diff === 'string' && patchRecord.unified_diff.trim()) {
    return patchRecord.unified_diff
  }
  if (typeof patchRecord.content === 'string' && patchRecord.content.trim()) {
    return patchRecord.content
  }
  return ''
})

const toolTrace = computed(() => {
  const resultTrace = props.reviewResult?.tool_trace
  if (Array.isArray(resultTrace)) return resultTrace
  return []
})

const llmTrace = computed(() => {
  const resultTrace = props.reviewResult?.llm_trace
  if (Array.isArray(resultTrace)) return resultTrace
  return []
})

const benchmarkSummary = computed(() => {
  const candidate = props.reviewResult?.benchmark
  if (candidate && typeof candidate === 'object') return candidate as Record<string, unknown>
  return null
})

function closePanel() {
  emit('close')
}

function statusText(status: ReadableStageTimelineItem['status']): string {
  if (status === 'completed') return '已完成'
  if (status === 'running') return '进行中'
  if (status === 'failed') return '失败'
  if (status === 'skipped') return '已跳过'
  return '未开始'
}

function stringify(value: unknown): string {
  try {
    return JSON.stringify(value ?? {}, null, 2)
  } catch {
    return '{}'
  }
}
</script>

<template>
  <aside v-if="open" class="detail-panel">
    <header class="header">
      <div>
        <p class="eyebrow">过程详情</p>
        <h2>系统处理过程</h2>
      </div>
      <button type="button" class="close-btn" @click="closePanel">关闭</button>
    </header>

    <nav class="tabs">
      <button type="button" :class="{ active: tab === 'overview' }" @click="tab = 'overview'">Overview</button>
      <button type="button" :class="{ active: tab === 'patch' }" @click="tab = 'patch'">Patch Diff</button>
      <button type="button" :class="{ active: tab === 'issue' }" @click="tab = 'issue'">Issue Graph</button>
      <button type="button" :class="{ active: tab === 'verification' }" @click="tab = 'verification'">
        Verification
      </button>
      <button type="button" :class="{ active: tab === 'memory' }" @click="tab = 'memory'">Memory</button>
      <button type="button" :class="{ active: tab === 'trace' }" @click="tab = 'trace'">Tool Trace</button>
      <button type="button" :class="{ active: tab === 'benchmark' }" @click="tab = 'benchmark'">Benchmark</button>
      <button type="button" :class="{ active: tab === 'raw' }" @click="tab = 'raw'">Raw Payload</button>
    </nav>

    <section v-if="tab === 'overview'" class="panel">
      <ul class="timeline-list">
        <li v-for="stage in timeline" :key="stage.key" class="timeline-item" :class="`state-${stage.status}`">
          <div class="item-head">
            <h3>{{ stage.title }}</h3>
            <span>{{ statusText(stage.status) }}</span>
          </div>
          <p class="description">{{ stage.description }}</p>
          <p class="summary">{{ stage.summary }}</p>
          <p v-if="stage.failureReason" class="failure">失败原因：{{ stage.failureReason }}</p>
          <details v-if="stage.detailLog" class="trace">
            <summary>查看详细日志</summary>
            <pre>{{ stage.detailLog }}</pre>
          </details>
        </li>
      </ul>
    </section>

    <section v-if="tab === 'patch'" class="panel">
      <PatchDiffViewer :patch-content="patchContent" />
    </section>

    <section v-if="tab === 'issue'" class="panel">
      <IssueGraphPanel :issue-graph="latestIssueGraph" />
    </section>

    <section v-if="tab === 'verification'" class="panel">
      <TokenContextPanel :context-budget="latestContextBudget" />
      <pre>{{ stringify(reviewResult?.verification ?? {}) }}</pre>
    </section>

    <section v-if="tab === 'memory'" class="panel">
      <pre>{{ stringify(reviewResult?.memory ?? {}) }}</pre>
    </section>

    <section v-if="tab === 'trace'" class="panel">
      <ToolTracePanel :tool-trace="toolTrace" :llm-trace="llmTrace" />
    </section>

    <section v-if="tab === 'benchmark'" class="panel">
      <BenchmarkPanel :benchmark="benchmarkSummary" />
    </section>

    <section v-if="tab === 'raw'" class="panel">
      <pre>{{ stringify(reviewResult ?? {}) }}</pre>
      <template v-if="debugMode">
        <div class="debug-block" v-for="event in events" :key="event.sequence">
          <p><strong>{{ event.eventType }}</strong> · #{{ event.sequence }}</p>
          <p>{{ event.message }}</p>
          <pre>{{ stringify(event.payload) }}</pre>
        </div>
      </template>
    </section>
  </aside>
</template>

<style scoped>
.detail-panel {
  width: 420px;
  border: 1px solid #dbe3ee;
  background: #fff;
  border-radius: 16px;
  padding: 0.9rem;
  display: grid;
  gap: 0.8rem;
  align-content: start;
  max-height: calc(100vh - 2.4rem);
  overflow: auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 0.6rem;
}

.eyebrow {
  margin: 0;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #708597;
  font-weight: 700;
}

.header h2 {
  margin: 0.12rem 0 0;
  color: #183d52;
  font-size: 1.04rem;
}

.close-btn {
  border: 1px solid #cfd9e8;
  background: #f8fbff;
  border-radius: 999px;
  color: #264a60;
  padding: 0.32rem 0.7rem;
  cursor: pointer;
}

.tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.4rem;
}

.tabs button {
  border: 1px solid #d1dced;
  background: #f8fbff;
  color: #2f5268;
  border-radius: 8px;
  padding: 0.32rem 0.42rem;
  font-size: 0.78rem;
  cursor: pointer;
}

.tabs button.active {
  background: #e8f4ff;
  border-color: #8fb7de;
}

.panel {
  display: grid;
  gap: 0.55rem;
}

.panel pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid #d9e2f0;
  background: #f5f9fd;
  border-radius: 8px;
  padding: 0.45rem;
  color: #2f4f63;
  font-size: 0.76rem;
}

.timeline-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.6rem;
}

.timeline-item {
  border: 1px solid #e0e8f2;
  border-radius: 12px;
  background: #fbfdff;
  padding: 0.62rem;
  display: grid;
  gap: 0.32rem;
}

.item-head {
  display: flex;
  justify-content: space-between;
  gap: 0.4rem;
  align-items: center;
}

.item-head h3 {
  margin: 0;
  color: #1f455a;
  font-size: 0.95rem;
}

.item-head span {
  font-size: 0.8rem;
  color: #446379;
}

.description,
.summary,
.failure {
  margin: 0;
  font-size: 0.88rem;
}

.description {
  color: #5f7688;
}

.summary {
  color: #274e63;
}

.failure {
  color: #a24444;
}

.trace summary {
  color: #3f5f74;
  cursor: pointer;
  font-size: 0.82rem;
}

.state-running {
  border-color: #8fb7de;
  background: #f1f8ff;
}

.state-completed {
  border-color: #a1cfb0;
  background: #edf9f1;
}

.state-failed {
  border-color: #d9a0a0;
  background: #fff4f4;
}

.state-skipped {
  border-color: #d9dee8;
  background: #f7f9fc;
}

.debug-block {
  border-top: 1px dashed #cfd9e8;
  padding-top: 0.4rem;
  margin-top: 0.35rem;
}

.debug-block p {
  margin: 0.2rem 0;
  color: #3f5f74;
  font-size: 0.82rem;
}

@media (max-width: 1100px) {
  .detail-panel {
    width: 100%;
    max-height: none;
  }
}
</style>
