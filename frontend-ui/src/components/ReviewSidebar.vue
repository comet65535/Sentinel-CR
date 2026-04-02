<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewTaskStatus } from '../types/review'
import { toStatusText } from '../utils/reviewEventView'

const props = defineProps<{
  taskId: string
  taskStatus: 'IDLE' | ReviewTaskStatus
}>()

const emit = defineEmits<{
  (event: 'new-analysis'): void
}>()

const historyItems = [
  { id: 'hist-1', title: 'Null Guard Patch', time: 'Today' },
  { id: 'hist-2', title: 'SQL Injection Fix', time: 'Yesterday' },
  { id: 'hist-3', title: 'Resource Leak Check', time: 'Earlier' },
]

const taskSummary = computed(() => {
  if (!props.taskId) return '当前无任务'
  return `${props.taskId} · ${toStatusText(props.taskStatus)}`
})

function onNewAnalysis() {
  emit('new-analysis')
}
</script>

<template>
  <aside class="sidebar">
    <button class="new-btn" type="button" @click="onNewAnalysis">新建分析</button>

    <section class="group">
      <p class="group-title">历史任务</p>
      <ul class="history-list">
        <li v-for="item in historyItems" :key="item.id" class="history-item">
          <p class="history-title">{{ item.title }}</p>
          <p class="history-time">{{ item.time }}</p>
        </li>
      </ul>
    </section>

    <section class="group current-task">
      <p class="group-title">当前任务</p>
      <p class="task-text">{{ taskSummary }}</p>
    </section>
  </aside>
</template>

<style scoped>
.sidebar {
  background: #f5f7fb;
  border: 1px solid #d9e0ea;
  border-radius: 14px;
  padding: 0.9rem;
  display: grid;
  gap: 1rem;
  min-height: calc(100vh - 2.6rem);
  align-content: start;
}

.new-btn {
  border: 1px solid #176891;
  background: #176891;
  color: #fff;
  border-radius: 999px;
  padding: 0.5rem 0.85rem;
  font-weight: 700;
  cursor: pointer;
}

.group {
  display: grid;
  gap: 0.5rem;
}

.group-title {
  margin: 0;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #547084;
  font-weight: 700;
}

.history-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.45rem;
}

.history-item {
  border: 1px solid #d9e3ee;
  border-radius: 10px;
  background: #fff;
  padding: 0.5rem 0.6rem;
}

.history-title {
  margin: 0;
  color: #1b3e51;
  font-size: 0.9rem;
}

.history-time {
  margin: 0.2rem 0 0;
  color: #688397;
  font-size: 0.78rem;
}

.current-task {
  border-top: 1px dashed #c7d3df;
  padding-top: 0.7rem;
}

.task-text {
  margin: 0;
  color: #2f5064;
  font-size: 0.88rem;
  line-break: anywhere;
}

@media (max-width: 1100px) {
  .sidebar {
    min-height: auto;
  }
}
</style>

