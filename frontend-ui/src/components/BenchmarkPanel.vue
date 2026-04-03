<script setup lang="ts">
const props = defineProps<{
  benchmark: Record<string, unknown> | null
}>()

function text(value: unknown, fallback = '-'): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function num(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) return value.toFixed(4)
  if (typeof value === 'string' && value.trim()) return value
  return '-'
}

const metrics = () =>
  (props.benchmark?.metrics as Record<string, unknown> | undefined) ?? {}
</script>

<template>
  <section class="benchmark-panel">
    <p v-if="!benchmark" class="placeholder">
      暂无 Benchmark 结果。可先运行 `python benchmark/run_eval.py` 生成最近一次评测。
    </p>
    <template v-else>
      <p>mode: {{ text(benchmark.mode) }} · schema: {{ text(benchmark.schema_version) }}</p>
      <div class="metric-grid">
        <p>detection precision: {{ num(metrics().detection_precision) }}</p>
        <p>detection recall: {{ num(metrics().detection_recall) }}</p>
        <p>final verified patch rate: {{ num(metrics().final_verified_patch_rate) }}</p>
        <p>L4 pass rate: {{ num(metrics().l4_pass_rate) }}</p>
        <p>tool recall: {{ num(metrics().tool_calling_recall) }}</p>
        <p>tool precision: {{ num(metrics().tool_calling_precision) }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.benchmark-panel {
  border: 1px solid #dce5ef;
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.7rem;
  display: grid;
  gap: 0.45rem;
}

.benchmark-panel p {
  margin: 0;
  color: #2f4e62;
  font-size: 0.84rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.3rem 0.8rem;
}

.placeholder {
  color: #698095;
}

@media (max-width: 780px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
