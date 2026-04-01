<script setup lang="ts">
import type { ReviewEvent } from '../types/review'

defineProps<{
  events: ReviewEvent[]
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
      <h2>Event Stream</h2>
    </header>

    <p v-if="events.length === 0" class="placeholder">
      Waiting for events...
    </p>

    <ul v-else class="event-list">
      <li v-for="event in events" :key="event.sequence" class="event-item">
        <span class="event-sequence">#{{ event.sequence }}</span>
        <span class="event-type">{{ event.eventType }}</span>
        <span class="event-message">{{ event.message }}</span>
        <time class="event-time">{{ formatTime(event.timestamp) }}</time>
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
  gap: 0.45rem;
}

.event-item {
  display: grid;
  grid-template-columns: auto auto 1fr auto;
  gap: 0.6rem;
  align-items: center;
  border: 1px solid #e1e8ee;
  border-radius: 10px;
  padding: 0.55rem 0.65rem;
  background: #f9fbfd;
}

.event-sequence {
  color: #165f80;
  font-weight: 600;
}

.event-type {
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
  color: #1f5069;
  font-size: 0.82rem;
}

.event-message {
  color: #254252;
}

.event-time {
  color: #658092;
  font-size: 0.82rem;
}

@media (max-width: 720px) {
  .event-item {
    grid-template-columns: auto 1fr;
  }
}
</style>
