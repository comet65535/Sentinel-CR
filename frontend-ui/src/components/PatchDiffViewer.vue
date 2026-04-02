<script setup lang="ts">
import { computed } from 'vue'

interface DiffRow {
  id: string
  kind: 'context' | 'added' | 'removed'
  leftLineNo: number | null
  rightLineNo: number | null
  leftText: string
  rightText: string
}

const props = defineProps<{
  patchContent: string
}>()

const rows = computed<DiffRow[]>(() => {
  if (!props.patchContent.trim()) {
    return []
  }

  const lines = props.patchContent.split(/\r?\n/)
  const result: DiffRow[] = []
  let leftCursor = 0
  let rightCursor = 0
  let rowId = 0

  for (const rawLine of lines) {
    if (!rawLine) {
      continue
    }
    if (rawLine.startsWith('diff --git') || rawLine.startsWith('--- ') || rawLine.startsWith('+++ ')) {
      continue
    }
    if (rawLine.startsWith('@@')) {
      const match = rawLine.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/)
      if (match) {
        leftCursor = Number(match[1])
        rightCursor = Number(match[2])
      }
      continue
    }
    if (rawLine.startsWith('\\ No newline at end of file')) {
      continue
    }

    const prefix = rawLine[0]
    const text = rawLine.slice(1)
    if (prefix === ' ') {
      result.push({
        id: `row-${rowId++}`,
        kind: 'context',
        leftLineNo: leftCursor++,
        rightLineNo: rightCursor++,
        leftText: text,
        rightText: text,
      })
      continue
    }
    if (prefix === '-') {
      result.push({
        id: `row-${rowId++}`,
        kind: 'removed',
        leftLineNo: leftCursor++,
        rightLineNo: null,
        leftText: text,
        rightText: '',
      })
      continue
    }
    if (prefix === '+') {
      result.push({
        id: `row-${rowId++}`,
        kind: 'added',
        leftLineNo: null,
        rightLineNo: rightCursor++,
        leftText: '',
        rightText: text,
      })
    }
  }

  return result
})
</script>

<template>
  <section class="diff-wrap">
    <header class="diff-header">
      <h4>代码差异对比</h4>
      <p>左侧 Original Code · 右侧 Patched Code</p>
    </header>

    <p v-if="rows.length === 0" class="empty">补丁内容为空，暂无可视化 diff。</p>

    <div v-else class="diff-table-wrap">
      <table class="diff-table">
        <thead>
          <tr>
            <th class="line-col">#</th>
            <th>Original Code</th>
            <th class="line-col">#</th>
            <th>Patched Code</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :class="`row-${row.kind}`">
            <td class="line-col">{{ row.leftLineNo ?? '' }}</td>
            <td><pre>{{ row.leftText }}</pre></td>
            <td class="line-col">{{ row.rightLineNo ?? '' }}</td>
            <td><pre>{{ row.rightText }}</pre></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.diff-wrap {
  border: 1px solid #d9e3ef;
  border-radius: 12px;
  background: #fcfdff;
  padding: 0.65rem;
  display: grid;
  gap: 0.45rem;
}

.diff-header h4 {
  margin: 0;
  color: #24485f;
  font-size: 0.92rem;
}

.diff-header p {
  margin: 0.18rem 0 0;
  color: #60798c;
  font-size: 0.8rem;
}

.empty {
  margin: 0;
  color: #6d8396;
  font-size: 0.84rem;
}

.diff-table-wrap {
  overflow: auto;
}

.diff-table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'JetBrains Mono', 'Cascadia Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 0.76rem;
}

.diff-table th,
.diff-table td {
  border: 1px solid #d7e1ee;
  padding: 0.25rem 0.35rem;
  vertical-align: top;
}

.diff-table th {
  background: #f3f7fc;
  color: #3b5a70;
  text-align: left;
}

.line-col {
  width: 42px;
  color: #7290a4;
  text-align: right;
}

.diff-table pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.row-added td {
  background: #eaf8ee;
}

.row-removed td {
  background: #fff1f1;
}

.row-context td {
  background: #f9fbfe;
}
</style>
