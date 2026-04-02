<script setup lang="ts">
import type { ReadableStageTimelineItem } from '../utils/reviewEventView'

const props = defineProps<{
  open: boolean
  timeline: ReadableStageTimelineItem[]
  debugMode: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
}>()

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

        <template v-if="debugMode && stage.events.length > 0">
          <div class="debug-block" v-for="event in stage.events" :key="event.sequence">
            <p><strong>{{ event.eventType }}</strong> · #{{ event.sequence }}</p>
            <p>{{ event.message }}</p>
            <pre>{{ stringify(event.payload) }}</pre>
          </div>
        </template>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.detail-panel {
  width: 380px;
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

.trace pre {
  margin: 0.35rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid #d9e2f0;
  background: #f5f9fd;
  border-radius: 8px;
  padding: 0.45rem;
  color: #2f4f63;
  font-size: 0.76rem;
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
  margin-top: 0.15rem;
}

.debug-block p {
  margin: 0.2rem 0;
  color: #3f5f74;
  font-size: 0.82rem;
}

.debug-block pre {
  margin: 0.2rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  border: 1px solid #d9e2f0;
  background: #f4f8fd;
  border-radius: 8px;
  padding: 0.45rem;
  font-size: 0.76rem;
  color: #2f4f63;
}

@media (max-width: 1100px) {
  .detail-panel {
    width: 100%;
    max-height: none;
  }
}
</style>
