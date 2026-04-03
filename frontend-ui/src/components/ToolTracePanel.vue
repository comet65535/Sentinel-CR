<script setup lang="ts">
import type { LlmTraceItem, ToolTraceItem } from '../types/review'

defineProps<{
  toolTrace: ToolTraceItem[]
  llmTrace: LlmTraceItem[]
}>()
</script>

<template>
  <section class="trace-panel">
    <div class="trace-block">
      <h4>Tool Trace</h4>
      <p v-if="toolTrace.length === 0" class="placeholder">暂无工具调用记录。</p>
      <ul v-else class="trace-list">
        <li v-for="(item, idx) in toolTrace" :key="idx">
          <strong>{{ item.tool_name || '-' }}</strong>
          <span> phase={{ item.phase || '-' }}</span>
          <span> success={{ String(item.success ?? '-') }}</span>
          <span> latency={{ item.latency_ms ?? '-' }}ms</span>
          <span> expected={{ item.expected_tool || '-' }}</span>
        </li>
      </ul>
    </div>

    <div class="trace-block">
      <h4>LLM Trace</h4>
      <p v-if="llmTrace.length === 0" class="placeholder">暂无 LLM 调用记录。</p>
      <ul v-else class="trace-list">
        <li v-for="(item, idx) in llmTrace" :key="idx">
          <strong>{{ item.phase || '-' }}</strong>
          <span> model={{ item.model || '-' }}</span>
          <span> in={{ item.token_in ?? '-' }}</span>
          <span> out={{ item.token_out ?? '-' }}</span>
          <span> latency={{ item.latency_ms ?? '-' }}ms</span>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.trace-panel {
  display: grid;
  gap: 0.7rem;
}

.trace-block {
  border: 1px solid #dce5ef;
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.6rem;
}

.trace-block h4 {
  margin: 0 0 0.35rem;
  color: #244b61;
}

.trace-list {
  margin: 0;
  padding-left: 1rem;
  display: grid;
  gap: 0.22rem;
  color: #2f4e62;
  font-size: 0.82rem;
}

.trace-list li span {
  margin-left: 0.35rem;
}

.placeholder {
  margin: 0;
  color: #698095;
}
</style>
