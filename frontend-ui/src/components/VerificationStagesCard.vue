<script setup lang="ts">
import type { VerificationStageFact } from '../types/review'

defineProps<{
  stages: VerificationStageFact[]
}>()
</script>

<template>
  <section class="card">
    <h3>Verification Stages</h3>
    <ul>
      <li v-for="stage in stages" :key="stage.stage" :class="`state-${stage.status}`">
        <div class="head">
          <strong>{{ stage.stage }}</strong>
          <span>{{ stage.status }}</span>
        </div>
        <p>{{ stage.summary }}</p>
        <p v-if="stage.skip_reason">reason: {{ stage.skip_reason }}</p>
        <p v-if="stage.failure_code">failure_code: {{ stage.failure_code }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.card { border: 1px solid #d9e2ee; border-radius: 10px; padding: 0.6rem; background: #fff; display: grid; gap: 0.5rem; }
h3 { margin: 0; color: #1d4357; font-size: 0.9rem; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.35rem; }
li { border: 1px solid #e1e8f2; border-radius: 8px; background: #f9fbfe; padding: 0.4rem; }
.head { display: flex; justify-content: space-between; gap: 0.4rem; }
.head strong { color: #2f566b; }
.head span, p { margin: 0; color: #4f687a; font-size: 0.8rem; }
.state-failed { border-color: #d9a4a4; background: #fff4f4; }
.state-passed { border-color: #a5ceaf; background: #eef9f1; }
</style>
