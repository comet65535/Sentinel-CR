import type { ReviewEvent, ReviewTaskStatus } from '../types/review'

export interface ResultStats {
  issueCount: number
  repairPlanCount: number
  memoryMatchCount: number
  attemptCount: number
  patchStatus: string
  verifiedLevel: string
  finalOutcome: string
  retryCount: number
  failedStage: string
  failureReason: string
  failureDetail: string
  retryExhausted: boolean
  noFixNeeded: boolean
  userMessage: string
  patchApplyStatus: string
  compileStatus: string
  lintStatus: string
  testStatus: string
  securityStatus: string
  regressionRisk: string
  failureTaxonomy: string
  nextContextHint: string
  nextConstraintHint: string
  nextRetryStrategy: string
}

export interface ReadableStageTimelineItem {
  key: string
  title: string
  description: string
  status: 'pending' | 'running' | 'passed' | 'failed' | 'skipped' | 'blocked'
  summary: string
  durationMs: number | null
  startedAt: string | null
  finishedAt: string | null
  details: unknown
  events: ReviewEvent[]
}

export type StageUiStatus = 'pending' | 'active' | 'completed' | 'failed'

export interface StageProgressItem {
  key: string
  title: string
  status: StageUiStatus
  hint: string
}

const EXECUTION_STAGE_LABELS: Array<{ key: string; title: string; description: string }> = [
  { key: 'intake_received', title: 'Intake', description: '接收输入与初始化状态。' },
  { key: 'analyzer_running', title: 'Analyzer', description: '语法、符号和规则扫描。' },
  { key: 'issue_graph_building', title: 'Issue Graph', description: '构建修复批次与依赖关系。' },
  { key: 'context_loading', title: 'Context', description: '按预算加载修复上下文。' },
  { key: 'memory_matching', title: 'Memory', description: '匹配历史修复案例。' },
  { key: 'standards_retrieving', title: 'Standards', description: '检索规范知识命中。' },
  { key: 'fixer_generating_patch', title: 'Fixer', description: '生成 unified diff 补丁。' },
  { key: 'patch_apply_running', title: 'Patch Apply', description: '应用补丁到临时代码。' },
  { key: 'compile_running', title: 'Compile', description: '编译验证。' },
  { key: 'lint_running', title: 'Lint', description: '静态规范验证。' },
  { key: 'test_running', title: 'Test', description: '回归测试验证。' },
  { key: 'security_rescan_running', title: 'Security', description: '安全复扫。' },
  { key: 'retry_reflection', title: 'Reflection', description: '失败反思并生成下一轮提示。' },
  { key: 'final_answer_writing', title: 'Reporter', description: '整理最终交付与解释。' },
  { key: 'completed', title: 'Completed', description: '流程完成。' },
]

const EVENT_TITLES: Record<string, string> = {
  task_created: '任务创建',
  analysis_started: '分析启动',
  analyzer_completed: '分析完成',
  planner_started: '规划启动',
  planner_completed: '规划完成',
  fixer_started: '补丁生成启动',
  patch_generated: '补丁生成完成',
  fixer_completed: '补丁阶段完成',
  verifier_started: '验证启动',
  verifier_completed: '验证完成',
  verifier_failed: '验证失败',
  review_retry_scheduled: '重试调度',
  review_retry_started: '重试开始',
  retry_reflection_completed: '反思完成',
  execution_stage_update: '执行阶段更新',
  standards_hits_updated: '规范命中更新',
  review_completed: '任务完成',
  review_failed: '任务失败',
  heartbeat: '连接保活',
}

export const SSE_EVENT_TYPES = [
  'task_created',
  'analysis_started',
  'ast_parsing_started',
  'ast_parsing_completed',
  'symbol_graph_started',
  'symbol_graph_completed',
  'semgrep_scan_started',
  'semgrep_scan_completed',
  'semgrep_scan_warning',
  'analyzer_completed',
  'planner_started',
  'issue_graph_built',
  'repair_plan_created',
  'planner_completed',
  'case_memory_search_started',
  'case_memory_matched',
  'case_memory_completed',
  'standards_hits_updated',
  'fixer_started',
  'patch_generated',
  'fixer_completed',
  'fixer_failed',
  'verifier_started',
  'patch_apply_started',
  'patch_apply_completed',
  'patch_apply_failed',
  'compile_started',
  'compile_completed',
  'compile_failed',
  'lint_started',
  'lint_completed',
  'lint_failed',
  'test_started',
  'test_completed',
  'test_failed',
  'security_rescan_started',
  'security_rescan_completed',
  'security_rescan_failed',
  'verifier_completed',
  'verifier_failed',
  'review_retry_scheduled',
  'review_retry_started',
  'retry_reflection_completed',
  'execution_stage_update',
  'review_completed',
  'review_failed',
  'langgraph_compiled',
  'langgraph_node_started',
  'langgraph_node_completed',
  'context_budget_initialized',
  'context_resource_loaded',
  'context_budget_updated',
  'context_budget_exhausted',
  'repo_memory_loaded',
  'short_term_memory_updated',
  'case_store_promoted',
  'mcp_resource_requested',
  'mcp_resource_completed',
  'mcp_tool_started',
  'mcp_tool_completed',
  'heartbeat',
] as const

export function toStatusText(status: 'IDLE' | ReviewTaskStatus): string {
  const map: Record<'IDLE' | ReviewTaskStatus, string> = {
    IDLE: '空闲',
    CREATED: '已创建',
    RUNNING: '运行中',
    COMPLETED: '已完成',
    FAILED: '失败',
  }
  return map[status]
}

export function getEventTitle(eventType: string): string {
  return EVENT_TITLES[eventType] ?? eventType
}

export function buildReadableCurrentStatus(events: ReviewEvent[], reviewResult: Record<string, unknown> | null): string {
  const stage = latestRunningStage(events, reviewResult)
  if (stage) {
    return `正在 ${stage.title}：${stage.summary}`
  }
  const latest = [...events]
    .sort((a, b) => b.sequence - a.sequence)
    .find((event) => event.eventType !== 'heartbeat')
  if (!latest) return '等待提交代码。'
  if (latest.eventType === 'review_completed') return '处理完成，正在展示结果。'
  if (latest.eventType === 'review_failed') return '处理失败，正在整理失败原因。'
  return latest.message || getEventTitle(latest.eventType)
}

export function buildReadableFailureMessage(reviewResult: Record<string, unknown> | null, fallbackStatus: string): string {
  if (!reviewResult) return fallbackStatus
  const stats = extractResultStats(reviewResult)
  return `失败阶段=${stats.failedStage}；taxonomy=${stats.failureTaxonomy}；建议上下文=${stats.nextContextHint}`
}

export function buildReadableStageTimeline(
  events: ReviewEvent[],
  reviewResult: Record<string, unknown> | null
): ReadableStageTimelineItem[] {
  const map = stageStateMap(events, reviewResult)
  return EXECUTION_STAGE_LABELS.map((item) => {
    const payload = map[item.key]
    const related = events.filter((event) => {
      if (event.eventType !== 'execution_stage_update') return false
      const stageId = String((event.payload.stage_id ?? '') as string)
      return stageId === item.key
    })
    return {
      key: item.key,
      title: item.title,
      description: item.description,
      status: (payload?.status ?? 'pending') as ReadableStageTimelineItem['status'],
      summary: payload?.summary ?? '等待执行。',
      durationMs: toNumberOrNull(payload?.duration_ms),
      startedAt: asText(payload?.started_at, null),
      finishedAt: asText(payload?.finished_at, null),
      details: payload?.details,
      events: related,
    }
  })
}

export function extractResultStats(reviewResult: Record<string, unknown>): ResultStats {
  const summary = asRecord(reviewResult.summary)
  const delivery = asRecord(reviewResult.delivery)
  const memory = asRecord(reviewResult.memory)
  const patch = asRecord(reviewResult.patch)
  const executionTruth = asRecord(reviewResult.execution_truth)
  const taxonomy = asRecord(executionTruth.failure_taxonomy ?? summary.failure_taxonomy)

  return {
    issueCount: toArrayCount(reviewResult.issues),
    repairPlanCount: toArrayCount(reviewResult.repair_plan),
    memoryMatchCount: toArrayCount(memory.matches),
    attemptCount: toArrayCount(reviewResult.attempts),
    patchStatus: toText(patch.status, delivery.unified_diff ? 'generated' : '-'),
    verifiedLevel: toText(delivery.verified_level ?? summary.verified_level, 'L0'),
    finalOutcome: toText(delivery.final_outcome ?? summary.final_outcome, '-'),
    retryCount: toNumber(summary.retry_count),
    failedStage: toText(delivery.failed_stage ?? summary.failed_stage, '-'),
    failureReason: toText(delivery.failure_reason ?? summary.failure_reason, '-'),
    failureDetail: toText(summary.failure_detail, '-'),
    retryExhausted: Boolean(summary.retry_exhausted),
    noFixNeeded: Boolean(summary.no_fix_needed),
    userMessage: toText(summary.user_message, '-'),
    patchApplyStatus: toText(executionTruth.patch_apply_status, 'pending'),
    compileStatus: toText(executionTruth.compile_status, 'pending'),
    lintStatus: toText(executionTruth.lint_status, 'pending'),
    testStatus: toText(executionTruth.test_status, 'pending'),
    securityStatus: toText(executionTruth.security_rescan_status, 'pending'),
    regressionRisk: toText(executionTruth.regression_risk, 'unknown'),
    failureTaxonomy: toText(taxonomy.bucket, 'none'),
    nextContextHint: toText(executionTruth.next_context_hint, '-'),
    nextConstraintHint: toText(executionTruth.next_constraint_hint, '-'),
    nextRetryStrategy: toText(executionTruth.next_retry_strategy, '-'),
  }
}

function latestRunningStage(events: ReviewEvent[], reviewResult: Record<string, unknown> | null): ReadableStageTimelineItem | null {
  const stages = buildReadableStageTimeline(events, reviewResult)
  const running = stages.find((item) => item.status === 'running')
  return running ?? null
}

function stageStateMap(events: ReviewEvent[], reviewResult: Record<string, unknown> | null): Record<string, Record<string, unknown>> {
  const result: Record<string, Record<string, unknown>> = {}
  const executionFromResult = asRecord(reviewResult?.execution_stages)
  for (const [key, value] of Object.entries(executionFromResult)) {
    if (typeof value === 'object' && value !== null) {
      result[key] = value as Record<string, unknown>
    }
  }
  const sorted = [...events].sort((a, b) => a.sequence - b.sequence)
  for (const event of sorted) {
    if (event.eventType !== 'execution_stage_update') continue
    const stageId = String(event.payload.stage_id ?? '')
    if (!stageId) continue
    result[stageId] = event.payload
  }
  return result
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {}
}

function asText(value: unknown, fallback: string | null): string | null {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function toText(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function toNumberOrNull(value: unknown): number | null {
  const n = toNumber(value)
  return Number.isFinite(n) && n > 0 ? n : null
}

function toArrayCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}
