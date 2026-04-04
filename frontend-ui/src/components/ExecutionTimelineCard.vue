<script setup lang="ts">
import type { ReadableStageTimelineItem } from '../utils/reviewEventView'

const props = defineProps<{
  timeline: ReadableStageTimelineItem[]
}>()

const emit = defineEmits<{
  (event: 'open-stage', stageKey: string): void
}>()

function statusClass(status: ReadableStageTimelineItem['status']): string {
  return `state-${status}`
}
</script>

<template>
  <section class="timeline-card">
    <header>
      <h3>Execution Timeline</h3>
    </header>
    <ul>
      <li
        v-for="item in props.timeline"
        :key="item.key"
        :class="statusClass(item.status)"
        @click="emit('open-stage', item.key)"
      >
        <div class="row">
          <strong>{{ item.title }}</strong>
          <span>{{ item.status }}</span>
        </div>
        <p>{{ item.summary }}</p>
        <p v-if="item.durationMs !== null" class="duration">{{ item.durationMs }} ms</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.timeline-card {
  border: 1px solid #d9e3f0;
  border-radius: 12px;
  background: #fff;
  padding: 0.7rem;
  display: grid;
  gap: 0.45rem;
}

.timeline-card h3 {
  margin: 0;
  color: #1f455a;
  font-size: 0.95rem;
}

.timeline-card ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.35rem;
}

.timeline-card li {
  border: 1px solid #dfe8f4;
  border-radius: 10px;
  background: #f9fbfe;
  padding: 0.45rem;
  cursor: pointer;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.row strong {
  color: #284f64;
}

.row span,
.timeline-card p {
  margin: 0;
  color: #4e697d;
  font-size: 0.82rem;
}

.duration {
  color: #68859a;
}

.state-running {
  border-color: #7ca9d2;
  background: #eef6ff;
}

.state-passed {
  border-color: #9cc6a9;
  background: #edf8f1;
}

.state-failed {
  border-color: #d6a0a0;
  background: #fff4f4;
}

.state-skipped,
.state-blocked {
  border-color: #d8dee8;
  background: #f7f9fc;
}
</style>
