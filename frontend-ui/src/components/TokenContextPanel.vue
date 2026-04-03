<script setup lang="ts">
const props = defineProps<{
  contextBudget: Record<string, unknown> | null
}>()

function asNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function asText(value: unknown, fallback = '-'): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}
</script>

<template>
  <section class="ctx-panel">
    <p v-if="!contextBudget" class="placeholder">暂无 Context Budget 数据。</p>
    <template v-else>
      <div class="grid">
        <p>Budget: {{ asNumber(contextBudget.budget_tokens) }}</p>
        <p>Used: {{ asNumber(contextBudget.used_tokens) }}</p>
        <p>Remaining: {{ asNumber(contextBudget.remaining_tokens) }}</p>
        <p>Stage: {{ asText(contextBudget.load_stage) }}</p>
      </div>

      <div class="sources">
        <h4>Sources</h4>
        <p
          v-if="!Array.isArray(contextBudget.sources) || contextBudget.sources.length === 0"
          class="placeholder"
        >
          暂无来源记录。
        </p>
        <ul v-else>
          <li v-for="(item, idx) in contextBudget.sources" :key="idx">
            {{ asText((item as Record<string, unknown>).kind) }} ·
            {{ asText((item as Record<string, unknown>).path) }} ·
            tokens={{ asNumber((item as Record<string, unknown>).token_count) }}
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.ctx-panel {
  border: 1px solid #dce6f1;
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.65rem;
  display: grid;
  gap: 0.55rem;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.25rem 0.7rem;
}

.grid p {
  margin: 0;
  color: #31566b;
  font-size: 0.87rem;
}

.sources h4 {
  margin: 0 0 0.32rem;
  color: #214d63;
  font-size: 0.9rem;
}

.sources ul {
  margin: 0;
  padding-left: 1rem;
  color: #3a6077;
  font-size: 0.82rem;
}

.placeholder {
  margin: 0;
  color: #6b8196;
}

@media (max-width: 720px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
