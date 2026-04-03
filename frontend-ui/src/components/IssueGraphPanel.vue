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

interface PositionedNode extends GraphNode {
  id: string
  x: number
  y: number
}

const props = defineProps<{
  issueGraph: Record<string, unknown> | null
}>()

const selectedIssueId = ref<string | null>(null)

const nodes = computed(() => {
  const raw = props.issueGraph?.nodes
  if (!Array.isArray(raw)) return []
  return raw as GraphNode[]
})

const edges = computed(() => {
  const raw = props.issueGraph?.edges
  return Array.isArray(raw) ? (raw as GraphEdge[]) : []
})

const positionedNodes = computed<PositionedNode[]>(() => {
  const size = nodes.value.length
  if (size === 0) return []
  const centerX = 240
  const centerY = 140
  const radius = Math.max(70, Math.min(120, 28 * size))
  return nodes.value.map((node, index) => {
    const angle = (2 * Math.PI * index) / size
    const id = String(node.issue_id || `node-${index}`)
    return {
      ...node,
      id,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  })
})

const nodeMap = computed(() =>
  Object.fromEntries(positionedNodes.value.map((node) => [node.id, node]))
)

const selectedNode = computed(() => {
  if (!selectedIssueId.value) return null
  return nodeMap.value[selectedIssueId.value] ?? null
})

function pickIssue(issueId: string | undefined) {
  if (!issueId) return
  selectedIssueId.value = issueId
}

function edgeKey(edge: GraphEdge, idx: number): string {
  return `${edge.from_issue_id || 'from'}-${edge.to_issue_id || 'to'}-${idx}`
}
</script>

<template>
  <section class="graph-panel">
    <p v-if="positionedNodes.length === 0" class="placeholder">暂无 Issue Graph 数据。</p>

    <div v-else class="graph-layout">
      <div class="graph-canvas">
        <svg class="graph-svg" viewBox="0 0 480 280" role="img" aria-label="Issue Graph">
          <line
            v-for="(edge, idx) in edges"
            :key="edgeKey(edge, idx)"
            :x1="nodeMap[String(edge.from_issue_id)]?.x ?? 0"
            :y1="nodeMap[String(edge.from_issue_id)]?.y ?? 0"
            :x2="nodeMap[String(edge.to_issue_id)]?.x ?? 0"
            :y2="nodeMap[String(edge.to_issue_id)]?.y ?? 0"
            class="edge"
          />

          <g
            v-for="node in positionedNodes"
            :key="node.id"
            class="node"
            :class="{ active: selectedIssueId === node.id }"
            @click="pickIssue(node.id)"
          >
            <circle :cx="node.x" :cy="node.y" r="20" />
            <text :x="node.x" :y="node.y + 4" text-anchor="middle">{{ node.id }}</text>
          </g>
        </svg>
      </div>

      <div class="detail">
        <p v-if="!selectedNode" class="placeholder">点击图中的节点查看 Issue 详情。</p>
        <template v-else>
          <h4>{{ selectedNode.id }}</h4>
          <p>Type: {{ selectedNode.type || '-' }}</p>
          <p>Severity: {{ selectedNode.severity || '-' }}</p>
          <p>File: {{ selectedNode.file_path || selectedNode.location?.file_path || '-' }}</p>
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
  grid-template-columns: 1.2fr 1fr;
  gap: 0.7rem;
}

.graph-canvas,
.detail {
  border: 1px solid #dce5ef;
  border-radius: 10px;
  background: #fbfdff;
  padding: 0.6rem;
}

.graph-svg {
  width: 100%;
  height: 280px;
  display: block;
}

.edge {
  stroke: #9cb8d3;
  stroke-width: 1.5;
}

.node {
  cursor: pointer;
}

.node circle {
  fill: #dfeeff;
  stroke: #6f9ec3;
  stroke-width: 1.4;
}

.node.active circle {
  fill: #b6dbff;
  stroke: #1f6799;
  stroke-width: 2;
}

.node text {
  font-size: 9px;
  fill: #1f4259;
  pointer-events: none;
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

  .graph-svg {
    height: 240px;
  }
}
</style>
