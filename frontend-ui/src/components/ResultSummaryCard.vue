<script setup lang="ts">
const props = defineProps<{
  hasResult: boolean
  stats: {
    issueCount: number
    repairPlanCount: number
    memoryMatchCount: number
    attemptCount: number
    patchStatus: string
    finalOutcome: string
    verifiedLevel: string
  }
}>()
</script>

<template>
  <section class="summary-card">
    <header class="summary-header">
      <h2>结果摘要</h2>
      <p>{{ hasResult ? '已收到 review_completed 收口结果' : '等待 review_completed' }}</p>
    </header>

    <div class="summary-grid">
      <p><strong>issue_count:</strong> {{ props.stats.issueCount }}</p>
      <p><strong>repair_plan_count:</strong> {{ props.stats.repairPlanCount }}</p>
      <p><strong>memory_match_count:</strong> {{ props.stats.memoryMatchCount }}</p>
      <p><strong>attempt_count:</strong> {{ props.stats.attemptCount }}</p>
      <p><strong>patch.status:</strong> {{ props.stats.patchStatus }}</p>
      <p><strong>final_outcome:</strong> {{ props.stats.finalOutcome }}</p>
      <p><strong>verified_level:</strong> {{ props.stats.verifiedLevel }}</p>
    </div>
  </section>
</template>

<style scoped>
.summary-card {
  border: 1px solid #d7e1eb;
  border-radius: 14px;
  background: #fff;
  padding: 0.9rem;
  display: grid;
  gap: 0.75rem;
}

.summary-header h2 {
  margin: 0;
  color: #17394c;
  font-size: 1rem;
}

.summary-header p {
  margin: 0.25rem 0 0;
  color: #587286;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.4rem 0.9rem;
}

.summary-grid p {
  margin: 0;
  color: #214557;
}

@media (max-width: 760px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>

