<script setup lang="ts">
import type { ReviewEvent } from '../types/review'

defineProps<{
  events: ReviewEvent[]
  debugMode: boolean
  getTitle: (eventType: string) => string
  getSummary: (event: ReviewEvent) => string
  summarizePayload: (payload: Record<string, unknown>) => string
}>()

function formatTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleTimeString()
}
</script>

<template>
  <section class="panel">
    <header class="section-header">
      <h2>事件流</h2>
    </header>

    <p v-if="events.length === 0" class="placeholder">
      暂无事件，等待任务启动...
    </p>

    <ul v-else class="event-list">
      <li v-for="event in events" :key="event.sequence" class="event-item">
        <div class="event-head">
          <span class="event-sequence">#{{ event.sequence }}</span>
          <span class="event-title">{{ getTitle(event.eventType) }}</span>
          <time class="event-time">{{ formatTime(event.timestamp) }}</time>
        </div>
        <p class="event-summary">{{ getSummary(event) }}</p>
        <div v-if="debugMode" class="event-debug">
          <p><strong>eventType:</strong> <code>{{ event.eventType }}</code></p>
          <p><strong>message:</strong> {{ event.message }}</p>
          <p><strong>payload:</strong> {{ summarizePayload(event.payload) }}</p>
        </div>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.panel {
  background: #ffffff;
  border: 1px solid #d5dce4;
  border-radius: 14px;
  padding: 1rem;
}

.section-header h2 {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
  color: #173647;
}

.placeholder {
  margin: 0;
  color: #5e7385;
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.55rem;
}

.event-item {
  border: 1px solid #e1e8ee;
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: #f9fbfd;
}

.event-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.6rem;
  align-items: center;
}

.event-sequence {
  color: #165f80;
  font-weight: 600;
}

.event-title {
  color: #1f5069;
  font-weight: 600;
}

.event-time {
  color: #658092;
  font-size: 0.82rem;
}

.event-summary {
  margin: 0.35rem 0 0;
  color: #254252;
}

.event-debug {
  margin-top: 0.5rem;
  border-top: 1px dashed #cfdae4;
  padding-top: 0.45rem;
  color: #365668;
  font-size: 0.86rem;
}

.event-debug p {
  margin: 0.2rem 0;
}

.event-debug code {
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 0.82rem;
  color: #1f5069;
}

@media (max-width: 720px) {
  .event-head {
    grid-template-columns: auto 1fr;
  }
}
</style>
