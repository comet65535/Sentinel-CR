<script setup lang="ts">
const props = defineProps<{
  hasResult: boolean
  stats: {
    issueCount: number
    repairPlanCount: number
    memoryMatchCount: number
    attemptCount: number
    retryCount: number
    patchStatus: string
    finalOutcome: string
    verifiedLevel: string
    failedStage: string
    failureReason: string
    userMessage: string
    retryExhausted: boolean
  }
}>()

const emit = defineEmits<{
  (event: 'open-process'): void
}>()
</script>

<template>
  <section class="result-card" @click="emit('open-process')">
    <header class="result-header">
      <h3>系统结果摘要</h3>
      <button type="button" class="detail-btn" @click.stop="emit('open-process')">查看过程</button>
    </header>

    <p v-if="!hasResult" class="placeholder">结果尚未收口，正在继续处理。</p>

    <template v-else>
      <p class="outcome">最终状态：{{ props.stats.finalOutcome }} · {{ props.stats.verifiedLevel }}</p>
      <div class="stat-grid">
        <p>问题数：{{ props.stats.issueCount }}</p>
        <p>计划数：{{ props.stats.repairPlanCount }}</p>
        <p>经验命中：{{ props.stats.memoryMatchCount }}</p>
        <p>补丁尝试：{{ props.stats.attemptCount }}</p>
        <p>重试次数：{{ props.stats.retryCount }}</p>
        <p>补丁状态：{{ props.stats.patchStatus }}</p>
      </div>
      <p v-if="props.stats.userMessage && props.stats.userMessage !== '-'" class="message">
        {{ props.stats.userMessage }}
      </p>
      <p v-if="props.stats.failedStage !== '-'" class="failure">
        失败阶段：{{ props.stats.failedStage }}
        <span v-if="props.stats.failureReason && props.stats.failureReason !== '-'">（{{ props.stats.failureReason }}）</span>
        <span v-if="props.stats.retryExhausted">，重试预算已耗尽</span>
      </p>
    </template>
  </section>
</template>

<style scoped>
.result-card {
  border: 1px solid #dbe3ef;
  background: #fff;
  border-radius: 14px;
  padding: 0.8rem;
  display: grid;
  gap: 0.55rem;
  cursor: pointer;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
}

.result-header h3 {
  margin: 0;
  color: #1a4055;
  font-size: 0.98rem;
}

.detail-btn {
  border: 1px solid #d0dbeb;
  background: #f8fbff;
  color: #264e64;
  border-radius: 999px;
  padding: 0.28rem 0.65rem;
  cursor: pointer;
}

.placeholder {
  margin: 0;
  color: #667f92;
}

.outcome {
  margin: 0;
  color: #214a5f;
  font-weight: 600;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.25rem 0.8rem;
}

.stat-grid p {
  margin: 0;
  color: #34586b;
  font-size: 0.88rem;
}

.message {
  margin: 0;
  color: #2e4f61;
}

.failure {
  margin: 0;
  color: #9a3f3f;
}

@media (max-width: 760px) {
  .stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
