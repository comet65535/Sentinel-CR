<script setup lang="ts">
import PatchDiffViewer from './PatchDiffViewer.vue'

const props = defineProps<{
  hasResult: boolean
  debugMode: boolean
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
    failureDetail: string
    userMessage: string
    retryExhausted: boolean
    noFixNeeded: boolean
  }
  patchContent: string
}>()

const emit = defineEmits<{
  (event: 'open-process'): void
}>()
</script>

<template>
  <section class="result-card" @click="props.debugMode && emit('open-process')">
    <header class="result-header">
      <h3>Verified Patch</h3>
      <button
        v-if="props.debugMode"
        type="button"
        class="detail-btn"
        @click.stop="emit('open-process')"
      >
        View Debug
      </button>
    </header>

    <p v-if="!hasResult" class="placeholder">Waiting for final delivery…</p>

    <template v-else>
      <p class="outcome">{{ props.stats.verifiedLevel }} · {{ props.stats.finalOutcome }}</p>

      <PatchDiffViewer
        v-if="props.patchContent"
        :patch-content="props.patchContent"
        @click.stop
      />

      <p v-if="props.stats.userMessage && props.stats.userMessage !== '-'" class="message">
        {{ props.stats.userMessage }}
      </p>

      <p v-if="props.stats.failedStage !== '-'" class="failure">
        failed_stage: {{ props.stats.failedStage }}
        <span v-if="props.stats.failureReason && props.stats.failureReason !== '-'">
          ({{ props.stats.failureReason }})
        </span>
      </p>

      <details
        v-if="props.stats.failureDetail && props.stats.failureDetail !== '-'"
        class="trace-details"
        @click.stop
      >
        <summary>stderr excerpt</summary>
        <pre>{{ props.stats.failureDetail }}</pre>
      </details>
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
  cursor: default;
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

.message {
  margin: 0;
  color: #2e4f61;
}

.failure {
  margin: 0;
  color: #9a3f3f;
}

.trace-details summary {
  color: #37566a;
  cursor: pointer;
  font-size: 0.84rem;
}

.trace-details pre {
  margin: 0.4rem 0 0;
  border: 1px solid #d6e0ed;
  background: #f6f9fd;
  border-radius: 8px;
  padding: 0.5rem;
  white-space: pre-wrap;
  word-break: break-word;
  color: #2d4b60;
  font-size: 0.78rem;
}
</style>
