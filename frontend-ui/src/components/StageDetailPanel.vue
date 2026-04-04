<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ReviewEvent, StandardsHitsSummary, VerificationStageFact } from '../types/review'
import type { ReadableStageTimelineItem } from '../utils/reviewEventView'
import BenchmarkPanel from './BenchmarkPanel.vue'
import ExecutionTimelineCard from './ExecutionTimelineCard.vue'
import IssueGraphPanel from './IssueGraphPanel.vue'
import PatchDiffViewer from './PatchDiffViewer.vue'
import RetryHintCard from './RetryHintCard.vue'
import StandardsHitsCard from './StandardsHitsCard.vue'
import TokenContextPanel from './TokenContextPanel.vue'
import ToolTracePanel from './ToolTracePanel.vue'
import VerificationStagesCard from './VerificationStagesCard.vue'

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

const tab = ref<'execution' | 'verification' | 'memory' | 'context' | 'standards' | 'trace' | 'benchmark' | 'raw'>(
  'execution'
)

const patchContent = computed(() => {
  const delivery = props.reviewResult?.delivery
  if (delivery && typeof delivery === 'object') {
    const diff = (delivery as Record<string, unknown>).unified_diff
    if (typeof diff === 'string' && diff.trim()) return diff
  }
  const patch = props.reviewResult?.patch
  if (!patch || typeof patch !== 'object') return ''
  const patchRecord = patch as Record<string, unknown>
  if (typeof patchRecord.unified_diff === 'string' && patchRecord.unified_diff.trim()) return patchRecord.unified_diff
  if (typeof patchRecord.content === 'string' && patchRecord.content.trim()) return patchRecord.content
  return ''
})

const verificationStages = computed<VerificationStageFact[]>(() => {
  const verification = props.reviewResult?.verification
  if (!verification || typeof verification !== 'object') return []
  const stages = (verification as Record<string, unknown>).stages
  if (!Array.isArray(stages)) return []
  return stages as VerificationStageFact[]
})

const executionTruth = computed(() => {
  const value = props.reviewResult?.execution_truth
  if (value && typeof value === 'object') return value as Record<string, unknown>
  return {}
})

const standards = computed<StandardsHitsSummary | null>(() => {
  const value = props.reviewResult?.standards_hits
  if (value && typeof value === 'object') return value as StandardsHitsSummary
  return null
})

const contextBudget = computed(() => {
  const value = props.reviewResult?.context_budget
  if (value && typeof value === 'object') return value as Record<string, unknown>
  return null
})

const selectedContext = computed(() => {
  const value = props.reviewResult?.selected_context
  return Array.isArray(value) ? value : []
})

const memoryBlock = computed(() => {
  const value = props.reviewResult?.memory
  if (value && typeof value === 'object') return value as Record<string, unknown>
  return null
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
        <p class="eyebrow">Debug Panel</p>
        <h2>Execution Details</h2>
      </div>
      <button type="button" class="close-btn" @click="emit('close')">关闭</button>
    </header>

    <nav class="tabs">
      <button type="button" :class="{ active: tab === 'execution' }" @click="tab = 'execution'">Execution</button>
      <button type="button" :class="{ active: tab === 'verification' }" @click="tab = 'verification'">Verification</button>
      <button v-if="debugMode" type="button" :class="{ active: tab === 'memory' }" @click="tab = 'memory'">Memory</button>
      <button v-if="debugMode" type="button" :class="{ active: tab === 'context' }" @click="tab = 'context'">Context</button>
      <button v-if="debugMode" type="button" :class="{ active: tab === 'standards' }" @click="tab = 'standards'">Standards</button>
      <button v-if="debugMode" type="button" :class="{ active: tab === 'trace' }" @click="tab = 'trace'">Tool Trace</button>
      <button v-if="debugMode && benchmarkSummary" type="button" :class="{ active: tab === 'benchmark' }" @click="tab = 'benchmark'">Benchmark Mapping</button>
      <button v-if="debugMode" type="button" :class="{ active: tab === 'raw' }" @click="tab = 'raw'">Raw Payload</button>
    </nav>

    <section v-if="tab === 'execution'" class="panel">
      <ExecutionTimelineCard :timeline="timeline" />
      <RetryHintCard
        :next-context-hint="String(executionTruth.next_context_hint || '-')"
        :next-constraint-hint="String(executionTruth.next_constraint_hint || '-')"
        :next-retry-strategy="String(executionTruth.next_retry_strategy || '-')"
      />
    </section>

    <section v-if="tab === 'verification'" class="panel">
      <VerificationStagesCard :stages="verificationStages" />
      <PatchDiffViewer :patch-content="patchContent" />
    </section>

    <section v-if="debugMode && tab === 'memory'" class="panel">
      <pre>{{ stringify(memoryBlock) }}</pre>
      <pre>{{ stringify(reviewResult?.memory_hits ?? {}) }}</pre>
    </section>

    <section v-if="debugMode && tab === 'context'" class="panel">
      <TokenContextPanel :context-budget="contextBudget" />
      <pre>{{ stringify(selectedContext) }}</pre>
      <IssueGraphPanel :issue-graph="(reviewResult?.issue_graph as Record<string, unknown> | null)" />
    </section>

    <section v-if="debugMode && tab === 'standards'" class="panel">
      <StandardsHitsCard :standards="standards" />
    </section>

    <section v-if="debugMode && tab === 'trace'" class="panel">
      <ToolTracePanel :tool-trace="toolTrace" :llm-trace="llmTrace" />
    </section>

    <section v-if="debugMode && tab === 'benchmark' && benchmarkSummary" class="panel">
      <BenchmarkPanel :benchmark="benchmarkSummary" />
    </section>

    <section v-if="debugMode && tab === 'raw'" class="panel">
      <pre>{{ stringify(reviewResult ?? {}) }}</pre>
      <div class="debug-block" v-for="event in events" :key="event.sequence">
        <p><strong>{{ event.eventType }}</strong> · #{{ event.sequence }}</p>
        <p>{{ event.message }}</p>
        <pre>{{ stringify(event.payload) }}</pre>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.detail-panel {
  width: 440px;
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
