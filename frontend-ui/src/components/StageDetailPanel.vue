<script setup lang="ts">
import type { ReviewEvent } from '../types/review'
import type { StageProgressItem } from '../utils/reviewEventView'

const props = defineProps<{
  open: boolean
  selectedStage: StageProgressItem | null
  stageEvents: ReviewEvent[]
  debugMode: boolean
  getTitle: (eventType: string) => string
  getSummary: (event: ReviewEvent) => string
  summarizePayload: (payload: Record<string, unknown>) => string
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

function closePanel() {
  emit('close')
}

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleTimeString()
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
    <header class="detail-header">
      <div>
        <p class="detail-eyebrow">阶段详情</p>
        <h2>{{ selectedStage?.title ?? '未选择阶段' }}</h2>
      </div>
      <button class="close-btn" type="button" @click="closePanel">关闭</button>
    </header>

    <p v-if="selectedStage" class="stage-hint">{{ selectedStage.hint }}</p>
    <p v-else class="stage-hint">点击任意进度胶囊可查看该阶段明细。</p>

    <p v-if="stageEvents.length === 0" class="placeholder">当前阶段暂无事件。</p>

    <ul v-else class="event-list">
      <li v-for="event in stageEvents" :key="event.sequence" class="event-item">
        <div class="event-head">
          <strong>{{ getTitle(event.eventType) }}</strong>
          <span>#{{ event.sequence }} · {{ formatTime(event.timestamp) }}</span>
        </div>
        <p class="event-summary">{{ getSummary(event) }}</p>

        <template v-if="debugMode">
          <p class="event-meta"><strong>eventType:</strong> <code>{{ event.eventType }}</code></p>
          <p class="event-meta"><strong>message:</strong> {{ event.message }}</p>
          <pre class="event-payload">{{ stringify(event.payload) }}</pre>
        </template>
        <template v-else>
          <p class="event-meta"><strong>payload:</strong> {{ summarizePayload(event.payload) }}</p>
        </template>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.detail-panel {
  width: 360px;
  border: 1px solid #d7e1eb;
  border-radius: 14px;
  background: #fff;
  padding: 0.9rem;
  display: grid;
  gap: 0.75rem;
  align-content: start;
  max-height: calc(100vh - 2.6rem);
  overflow: auto;
}

.detail-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 0.6rem;
}

.detail-eyebrow {
  margin: 0;
  font-size: 0.74rem;
  color: #648093;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.detail-header h2 {
  margin: 0.15rem 0 0;
  color: #17394c;
  font-size: 1.02rem;
}

.close-btn {
  border: 1px solid #c6d4e2;
  border-radius: 999px;
  background: #f8fbff;
  color: #254b5f;
  padding: 0.35rem 0.7rem;
  cursor: pointer;
}

.stage-hint {
  margin: 0;
  color: #4f697d;
}

.placeholder {
  margin: 0;
  color: #597286;
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.6rem;
}

.event-item {
  border: 1px solid #e1e8f0;
  border-radius: 10px;
  background: #f9fbfe;
  padding: 0.6rem;
}

.event-head {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  color: #1f4b62;
  font-size: 0.85rem;
}

.event-summary {
  margin: 0.35rem 0;
  color: #22485c;
}

.event-meta {
  margin: 0.2rem 0;
  color: #4f697c;
  font-size: 0.83rem;
}

.event-meta code {
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
}

.event-payload {
  margin: 0.35rem 0 0;
  background: #f0f5fb;
  border: 1px solid #d6dfeb;
  border-radius: 8px;
  padding: 0.5rem;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.78rem;
  color: #2b4c5f;
}

@media (max-width: 1100px) {
  .detail-panel {
    width: 100%;
    max-height: none;
  }
}
</style>

