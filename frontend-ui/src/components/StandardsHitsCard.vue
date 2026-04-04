<script setup lang="ts">
import type { StandardsHitsSummary } from '../types/review'

defineProps<{
  standards: StandardsHitsSummary | null
}>()
</script>

<template>
  <section class="card">
    <h3>Standards Hits</h3>
    <p v-if="!standards">No standards hit.</p>
    <template v-else>
      <p>hit_count: {{ standards.hit_count }}</p>
      <p>sources: {{ standards.sources.join(', ') || '-' }}</p>
      <ul>
        <li v-for="item in standards.hits" :key="item.id || item.summary">
          <strong>{{ item.source || 'unknown' }}</strong>
          <p>{{ item.summary }}</p>
        </li>
      </ul>
    </template>
  </section>
</template>

<style scoped>
.card { border: 1px solid #d9e2ee; border-radius: 10px; padding: 0.6rem; background: #fff; display: grid; gap: 0.35rem; }
h3 { margin: 0; color: #1d4357; font-size: 0.9rem; }
p { margin: 0; color: #4f687a; font-size: 0.82rem; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.25rem; }
li { border: 1px solid #e3eaf4; border-radius: 8px; padding: 0.35rem; background: #f9fbff; }
li strong { color: #2f566b; font-size: 0.82rem; }
li p { margin: 0.2rem 0 0; }
</style>
