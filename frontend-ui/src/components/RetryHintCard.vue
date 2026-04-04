<script setup lang="ts">
defineProps<{
  nextContextHint: string
  nextConstraintHint: string
  nextRetryStrategy: string
}>()
</script>

<template>
  <section class="card">
    <h3>Retry Hints</h3>
    <p><strong>context:</strong> {{ nextContextHint }}</p>
    <p><strong>constraint:</strong> {{ nextConstraintHint }}</p>
    <p><strong>strategy:</strong> {{ nextRetryStrategy }}</p>
  </section>
</template>

<style scoped>
.card { border: 1px solid #d9e2ee; border-radius: 10px; padding: 0.6rem; background: #fff; display: grid; gap: 0.35rem; }
h3 { margin: 0; color: #1d4357; font-size: 0.9rem; }
p { margin: 0; color: #4f687a; font-size: 0.82rem; }
</style>
