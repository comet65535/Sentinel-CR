<script setup lang="ts">
import { computed, ref } from 'vue'

interface GraphNode {
  issue_id?: string
  type?: string
  severity?: string
  file_path?: string
  location?: { file_path?: string; line?: number }
  related_symbols?: string[]
  strategy_hint?: string
  fix_scope?: string
}

interface GraphEdge {
  from_issue_id?: string
  to_issue_id?: string
  edge_type?: string
}

const props = defineProps<{
  issueGraph: Record<string, unknown> | null
}>()

const selectedIssueId = ref<string | null>(null)

const nodes = computed(() => {
  const raw = props.issueGraph?.nodes
  return Array.isArray(raw) ? (raw as GraphNode[]) : []
})

const edges = computed(() => {
  const raw = props.issueGraph?.edges
  return Array.isArray(raw) ? (raw as GraphEdge[]) : []
})

const selectedNode = computed(() => {
  if (!selectedIssueId.value) return null
  return nodes.value.find((node) => String(node.issue_id) === selectedIssueId.value) ?? null
})

function pickIssue(issueId: string | undefined) {
  if (!issueId) return
  selectedIssueId.value = issueId
}
</script>

<template>
  <section class="graph-panel">
    <p v-if="nodes.length === 0" class="placeholder">暂无 Issue Graph 数据。</p>

    <div v-else class="graph-layout">
      <div class="graph-canvas">
        <button
          v-for="node in nodes"
          :key="String(node.issue_id)"
          type="button"
          class="node-chip"
          :class="{ active: selectedIssueId === String(node.issue_id) }"
          @click="pickIssue(String(node.issue_id))"
        >
          <strong>{{ node.issue_id }}</strong>
          <span>{{ node.type }} · {{ node.severity }}</span>
        </button>

        <ul class="edge-list">
          <li v-for="(edge, idx) in edges" :key="idx">
            {{ edge.from_issue_id }} → {{ edge.to_issue_id }} ({{ edge.edge_type }})
          </li>
        </ul>
      </div>

      <div class="detail">
        <p v-if="!selectedNode" class="placeholder">点击左侧节点查看详情。</p>
        <template v-else>
          <h4>{{ selectedNode.issue_id }}</h4>
          <p>Type: {{ selectedNode.type }}</p>
          <p>Severity: {{ selectedNode.severity }}</p>
          <p>
            File:
            {{ selectedNode.file_path || selectedNode.location?.file_path || '-' }}
          </p>
          <p>Strategy: {{ selectedNode.strategy_hint || '-' }}</p>
          <p>Fix Scope: {{ selectedNode.fix_scope || '-' }}</p>
          <p>Symbols: {{ (selectedNode.related_symbols || []).join(', ') || '-' }}</p>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.graph-panel {
  display: grid;
  gap: 0.6rem;
}

.graph-layout {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 0.7rem;
}

.graph-canvas,
.detail {
  border: 1px solid #dce5ef;
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.6rem;
}

.node-chip {
  border: 1px solid #cdd9ea;
  border-radius: 999px;
  background: #f2f7ff;
  color: #204960;
  display: inline-grid;
  gap: 0.12rem;
  padding: 0.36rem 0.6rem;
  margin: 0 0.45rem 0.45rem 0;
  cursor: pointer;
  text-align: left;
}

.node-chip.active {
  border-color: #6d9fc4;
  background: #deefff;
}

.node-chip span {
  font-size: 0.76rem;
}

.edge-list {
  margin: 0.2rem 0 0;
  padding-left: 1rem;
  color: #3b5e74;
  font-size: 0.82rem;
}

.detail h4 {
  margin: 0 0 0.35rem;
  color: #22495f;
}

.detail p {
  margin: 0.18rem 0;
  color: #34586d;
  font-size: 0.86rem;
}

.placeholder {
  margin: 0;
  color: #698095;
}

@media (max-width: 900px) {
  .graph-layout {
    grid-template-columns: 1fr;
  }
}
</style>
