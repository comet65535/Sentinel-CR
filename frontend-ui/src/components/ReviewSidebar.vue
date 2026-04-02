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

const placeholderHistory = [
  { id: 'h1', title: '空指针修复演练', subtitle: '今天' },
  { id: 'h2', title: 'SQL 参数化检查', subtitle: '昨天' },
  { id: 'h3', title: '编译失败重试样例', subtitle: '更早' },
]

const taskLabel = computed(() => {
  if (!props.taskId) return '当前暂无任务'
  return `${props.taskId} · ${toStatusText(props.taskStatus)}`
})
</script>

<template>
  <aside class="sidebar">
    <button class="new-chat" type="button" @click="emit('new-analysis')">+ 新建分析</button>

    <div class="section">
      <p class="section-title">历史会话</p>
      <button v-for="item in placeholderHistory" :key="item.id" class="history-item" type="button">
        <span class="history-title">{{ item.title }}</span>
        <span class="history-subtitle">{{ item.subtitle }}</span>
      </button>
    </div>

    <div class="section current">
      <p class="section-title">当前任务</p>
      <p class="current-text">{{ taskLabel }}</p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  background: #f5f7fb;
  border: 1px solid #e1e7ef;
  border-radius: 16px;
  padding: 0.9rem;
  display: grid;
  gap: 1rem;
  min-height: calc(100vh - 2.4rem);
  align-content: start;
}

.new-chat {
  border: 1px solid #cdd8e7;
  background: #fff;
  color: #21465b;
  border-radius: 12px;
  padding: 0.55rem 0.7rem;
  font-weight: 600;
  cursor: pointer;
  text-align: left;
}

.new-chat:hover {
  background: #eef3fb;
}

.section {
  display: grid;
  gap: 0.45rem;
}

.section-title {
  margin: 0;
  font-size: 0.73rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6f8294;
  font-weight: 700;
}

.history-item {
  border: 1px solid transparent;
  background: transparent;
  border-radius: 10px;
  padding: 0.45rem 0.5rem;
  display: grid;
  gap: 0.1rem;
  cursor: pointer;
  text-align: left;
}

.history-item:hover {
  background: #e9f0fb;
  border-color: #d4e1f1;
}

.history-title {
  color: #213f53;
  font-size: 0.88rem;
}

.history-subtitle {
  color: #72879c;
  font-size: 0.76rem;
}

.current {
  border-top: 1px solid #dde5f0;
  padding-top: 0.75rem;
}

.current-text {
  margin: 0;
  color: #2f4f64;
  line-break: anywhere;
  font-size: 0.84rem;
}

@media (max-width: 1100px) {
  .sidebar {
    min-height: auto;
  }
}
</style>
