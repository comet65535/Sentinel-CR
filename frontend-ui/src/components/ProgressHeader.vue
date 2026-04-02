<script setup lang="ts">
import { computed } from 'vue'
import type { StageProgressItem, StageUiStatus } from '../utils/reviewEventView'

const props = defineProps<{
  stages: StageProgressItem[]
  selectedKey: string | null
}>()

const emit = defineEmits<{
  (event: 'select-stage', stageKey: string): void
}>()

const activeStage = computed(
  () =>
    props.stages.find((item) => item.status === 'active') ||
    props.stages.find((item) => item.status === 'failed') ||
    props.stages[props.stages.length - 1]
)

function onSelect(stageKey: string) {
  emit('select-stage', stageKey)
}

function statusText(status: StageUiStatus): string {
  if (status === 'completed') return 'Completed'
  if (status === 'active') return 'Active'
  if (status === 'failed') return 'Failed'
  return 'Pending'
}
</script>

<template>
  <section class="progress-card">
    <header class="progress-header">
      <h2>当前进度</h2>
      <p>{{ activeStage?.hint ?? '等待任务启动' }}</p>
    </header>

    <div class="progress-rail">
      <button
        v-for="stage in stages"
        :key="stage.key"
        type="button"
        class="stage-pill"
        :class="[
          `stage-${stage.status}`,
          { selected: selectedKey === stage.key },
        ]"
        @click="onSelect(stage.key)"
      >
        <span class="stage-title">{{ stage.title }}</span>
        <span class="stage-meta">{{ statusText(stage.status) }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.progress-card {
  border: 1px solid #d6dfe9;
  border-radius: 14px;
  padding: 0.9rem;
  background: #fff;
  display: grid;
  gap: 0.8rem;
}

.progress-header h2 {
  margin: 0;
  color: #153243;
  font-size: 1rem;
}

.progress-header p {
  margin: 0.25rem 0 0;
  color: #587286;
  font-size: 0.9rem;
}

.progress-rail {
  display: flex;
  gap: 0.55rem;
  overflow-x: auto;
  padding-bottom: 0.2rem;
}

.stage-pill {
  border: 1px solid #d6e0eb;
  background: #f8fbff;
  color: #295267;
  border-radius: 999px;
  padding: 0.45rem 0.75rem;
  min-width: 126px;
  display: grid;
  justify-items: start;
  gap: 0.1rem;
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.stage-title {
  font-weight: 700;
  font-size: 0.86rem;
}

.stage-meta {
  font-size: 0.76rem;
}

.stage-pill.selected {
  border-color: #135f86;
  box-shadow: 0 0 0 1px #135f86 inset;
}

.stage-pill.stage-completed {
  background: #eaf7f0;
  border-color: #8abda0;
  color: #1f5933;
}

.stage-pill.stage-active {
  background: #ebf5ff;
  border-color: #77a6d8;
  color: #1a4e7e;
}

.stage-pill.stage-failed {
  background: #fff1f1;
  border-color: #d58f8f;
  color: #873a3a;
}

.stage-pill.stage-pending {
  opacity: 0.8;
}
</style>

