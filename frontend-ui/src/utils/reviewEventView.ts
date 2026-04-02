import type { ReviewEvent, ReviewTaskStatus } from '../types/review'

export type StageKey =
  | 'task_created'
  | 'analyzer'
  | 'planner'
  | 'memory'
  | 'fixer'
  | 'verifier'
  | 'completed'

export type StageUiStatus = 'pending' | 'active' | 'completed' | 'failed'

export interface StageProgressItem {
  key: StageKey
  title: string
  status: StageUiStatus
  hint: string
  eventCount: number
  lastEventType: string | null
}

const EVENT_TYPE_TITLE_MAP: Record<string, string> = {
  task_created: '任务已创建',
  analysis_started: '开始分析',
  ast_parsing_started: '开始解析 AST',
  ast_parsing_completed: 'AST 解析完成',
  symbol_graph_started: '开始构建符号图',
  symbol_graph_completed: '符号图构建完成',
  semgrep_scan_started: '开始规则扫描',
  semgrep_scan_completed: 'Semgrep 扫描完成',
  semgrep_scan_warning: 'Semgrep 扫描降级',
  analyzer_completed: '分析器处理完成',
  planner_started: '开始构建修复计划',
  issue_graph_built: '问题图构建完成',
  repair_plan_created: '修复计划已生成',
  planner_completed: '规划器处理完成',
  case_memory_search_started: '案例检索开始',
  case_memory_matched: '命中历史案例',
  case_memory_completed: '案例检索完成',
  fixer_started: '开始生成补丁',
  patch_generated: '补丁生成完成',
  fixer_completed: '修复阶段完成',
  fixer_failed: '修复阶段失败',
  verifier_started: '验证阶段开始',
  patch_apply_started: '开始应用补丁',
  patch_apply_completed: '补丁应用完成',
  patch_apply_failed: '补丁应用失败',
  compile_started: '开始编译验证',
  compile_completed: '编译验证完成',
  compile_failed: '编译验证失败',
  lint_started: '开始 Lint 验证',
  lint_completed: 'Lint 验证完成',
  lint_failed: 'Lint 验证失败',
  test_started: '开始测试验证',
  test_completed: '测试验证完成',
  test_failed: '测试验证失败',
  security_rescan_started: '开始安全复扫',
  security_rescan_completed: '安全复扫完成',
  security_rescan_failed: '安全复扫失败',
  verifier_completed: '验证阶段完成',
  verifier_failed: '验证阶段失败',
  review_retry_scheduled: '已安排重试',
  review_retry_started: '开始重试',
  review_completed: '分析完成',
  review_failed: '分析失败',
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
  'review_completed',
  'review_failed',
  'heartbeat',
] as const

const STAGE_ORDER: StageKey[] = [
  'task_created',
  'analyzer',
  'planner',
  'memory',
  'fixer',
  'verifier',
  'completed',
]

const STAGE_TITLE_MAP: Record<StageKey, string> = {
  task_created: '任务创建',
  analyzer: 'Analyzer',
  planner: 'Planner',
  memory: 'Memory',
  fixer: 'Fixer',
  verifier: 'Verifier',
  completed: 'Completed',
}

const STAGE_DEFAULT_HINT_MAP: Record<StageKey, string> = {
  task_created: '等待任务创建',
  analyzer: '等待代码分析',
  planner: '等待修复规划',
  memory: '等待案例检索',
  fixer: '等待补丁生成',
  verifier: '等待验证阶段',
  completed: '等待最终收口',
}

const ANALYZER_EVENTS = new Set([
  'analysis_started',
  'ast_parsing_started',
  'ast_parsing_completed',
  'symbol_graph_started',
  'symbol_graph_completed',
  'semgrep_scan_started',
  'semgrep_scan_completed',
  'semgrep_scan_warning',
  'analyzer_completed',
])

const PLANNER_EVENTS = new Set([
  'planner_started',
  'issue_graph_built',
  'repair_plan_created',
  'planner_completed',
])

const MEMORY_EVENTS = new Set([
  'case_memory_search_started',
  'case_memory_matched',
  'case_memory_completed',
])

const FIXER_EVENTS = new Set([
  'fixer_started',
  'patch_generated',
  'fixer_completed',
  'fixer_failed',
])

const VERIFIER_EVENTS = new Set([
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
])

const COMPLETED_EVENTS = new Set(['review_completed', 'review_failed'])

const STAGE_COMPLETED_MARKERS: Record<StageKey, Set<string>> = {
  task_created: new Set(['task_created']),
  analyzer: new Set(['analyzer_completed']),
  planner: new Set(['planner_completed']),
  memory: new Set(['case_memory_completed']),
  fixer: new Set(['fixer_completed', 'fixer_failed']),
  verifier: new Set(['verifier_completed', 'verifier_failed']),
  completed: new Set(['review_completed', 'review_failed']),
}

const STAGE_FAILURE_EVENTS: Record<StageKey, Set<string>> = {
  task_created: new Set([]),
  analyzer: new Set([]),
  planner: new Set([]),
  memory: new Set([]),
  fixer: new Set(['fixer_failed']),
  verifier: new Set([
    'verifier_failed',
    'patch_apply_failed',
    'compile_failed',
    'lint_failed',
    'test_failed',
    'security_rescan_failed',
  ]),
  completed: new Set(['review_failed']),
}

export function getEventTitle(eventType: string): string {
  return EVENT_TYPE_TITLE_MAP[eventType] ?? eventType
}

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

export function resolveStageKey(eventType: string): StageKey | null {
  if (eventType === 'task_created') return 'task_created'
  if (ANALYZER_EVENTS.has(eventType)) return 'analyzer'
  if (PLANNER_EVENTS.has(eventType)) return 'planner'
  if (MEMORY_EVENTS.has(eventType)) return 'memory'
  if (FIXER_EVENTS.has(eventType)) return 'fixer'
  if (VERIFIER_EVENTS.has(eventType)) return 'verifier'
  if (COMPLETED_EVENTS.has(eventType)) return 'completed'
  return null
}

export function eventsForStage(stageKey: StageKey, events: ReviewEvent[]): ReviewEvent[] {
  return [...events]
    .filter((event) => resolveStageKey(event.eventType) === stageKey)
    .sort((left, right) => left.sequence - right.sequence)
}

export function buildStageProgress(
  events: ReviewEvent[],
  taskStatus: 'IDLE' | ReviewTaskStatus
): StageProgressItem[] {
  const sorted = [...events].sort((left, right) => left.sequence - right.sequence)
  const items = STAGE_ORDER.map((stageKey): StageProgressItem => {
    const stageEvents = eventsForStage(stageKey, sorted)
    const lastEvent = stageEvents.at(-1)
    const hint = lastEvent ? buildEventSummary(lastEvent) : STAGE_DEFAULT_HINT_MAP[stageKey]

    const status = resolveStageStatus(stageKey, stageEvents, sorted.length, taskStatus)
    return {
      key: stageKey,
      title: STAGE_TITLE_MAP[stageKey],
      status,
      hint,
      eventCount: stageEvents.length,
      lastEventType: lastEvent?.eventType ?? null,
    }
  })

  const hasActive = items.some((item) => item.status === 'active')
  if (!hasActive && taskStatus === 'RUNNING') {
    for (let i = items.length - 1; i >= 0; i -= 1) {
      const item = items[i]
      if (item.eventCount > 0 && item.status === 'completed' && item.key !== 'completed') {
        item.status = 'active'
        break
      }
    }
  }

  if (taskStatus === 'COMPLETED') {
    const completed = items.find((item) => item.key === 'completed')
    if (completed && completed.status !== 'failed') {
      completed.status = 'completed'
    }
  }

  if (taskStatus === 'FAILED') {
    const completed = items.find((item) => item.key === 'completed')
    if (completed) {
      completed.status = 'failed'
      if (completed.eventCount === 0) {
        completed.hint = '任务失败'
      }
    }
  }

  return items
}

export function buildEventSummary(event: ReviewEvent): string {
  const payload = event.payload ?? {}
  switch (event.eventType) {
    case 'task_created':
      return '任务创建成功，等待分析引擎处理。'
    case 'analysis_started':
      return '分析任务已启动。'
    case 'ast_parsing_started':
      return '正在解析 Java AST。'
    case 'ast_parsing_completed': {
      const parseCount = toCount(payload.syntaxIssuesCount ?? payload.parseErrorsCount)
      if (parseCount > 0) {
        return `AST 解析完成（检测到 ${parseCount} 个解析错误）`
      }
      return `AST 解析完成（${toCount(payload.classesCount)} 个类，${toCount(payload.methodsCount)} 个方法）`
    }
    case 'symbol_graph_started':
      return '正在构建符号图。'
    case 'symbol_graph_completed':
      return `符号图构建完成（${toCount(payload.symbolsCount)} 个符号）`
    case 'semgrep_scan_started':
      return '开始执行 Semgrep 规则扫描。'
    case 'semgrep_scan_completed':
      return `Semgrep 扫描完成（发现 ${toCount(payload.issuesCount)} 个问题）`
    case 'semgrep_scan_warning':
      return `Semgrep 扫描降级：${toWarningMessage(payload)}`
    case 'analyzer_completed': {
      const summary = payload.analyzerSummary as Record<string, unknown> | undefined
      if (!summary) {
        return '分析器处理完成。'
      }
      return `分析器处理完成（问题 ${toCount(summary.issuesCount)}，符号 ${toCount(summary.symbolsCount)}）`
    }
    case 'planner_started':
      return `开始构建 Issue Graph 与 Repair Plan（输入问题 ${toCount(payload.inputIssueCount)}）`
    case 'issue_graph_built':
      return `问题图构建完成（${toCount(payload.issueCount)} 个节点）`
    case 'repair_plan_created':
      return `修复计划已生成（${toCount(payload.planCount)} 项）`
    case 'planner_completed':
      return `规划器处理完成（计划 ${toCount(payload.planCount)} 项）`
    case 'case_memory_search_started':
      return `开始检索案例库（问题 ${toCount(payload.issue_count)}）`
    case 'case_memory_matched':
      return `命中案例 ${toCount(payload.match_count)} 条`
    case 'case_memory_completed':
      return `案例检索完成（命中 ${toCount(payload.match_count)}）`
    case 'fixer_started':
      return `开始生成补丁（计划 ${toCount(payload.plan_count)}）`
    case 'patch_generated':
      return 'Unified Diff 补丁生成完成。'
    case 'fixer_completed':
      return 'Fixer 阶段完成。'
    case 'fixer_failed':
      return `Fixer 失败：${typeof payload.reason === 'string' ? payload.reason : '无有效补丁'}`
    case 'verifier_started':
      return '验证流程已启动。'
    case 'patch_apply_started':
      return '开始应用补丁。'
    case 'patch_apply_completed':
      return `补丁应用完成（status=${String(payload.status ?? 'passed')}）。`
    case 'patch_apply_failed':
      return `补丁应用失败：${String(payload.reason ?? 'unknown')}`
    case 'compile_started':
      return '开始编译验证。'
    case 'compile_completed':
      return `编译阶段完成（status=${String(payload.status ?? 'passed')}）。`
    case 'compile_failed':
      return `编译失败：${String(payload.reason ?? payload.stderr_summary ?? 'unknown')}`
    case 'lint_started':
      return '开始 Lint 验证。'
    case 'lint_completed':
      return `Lint 阶段结束（status=${String(payload.status ?? 'passed')}）。`
    case 'lint_failed':
      return `Lint 失败：${String(payload.reason ?? 'unknown')}`
    case 'test_started':
      return '开始测试验证。'
    case 'test_completed':
      return `测试阶段结束（status=${String(payload.status ?? 'passed')}）。`
    case 'test_failed':
      return `测试失败：${String(payload.reason ?? 'unknown')}`
    case 'security_rescan_started':
      return '开始安全复扫。'
    case 'security_rescan_completed':
      return `安全复扫结束（status=${String(payload.status ?? 'passed')}）。`
    case 'security_rescan_failed':
      return `安全复扫失败：${String(payload.reason ?? 'unknown')}`
    case 'verifier_completed':
      return `验证完成（${String(payload.verification?.verified_level ?? payload.verified_level ?? 'L0')}）。`
    case 'verifier_failed':
      return `验证失败：${String(payload.reason ?? payload.failed_stage ?? 'unknown')}`
    case 'review_retry_scheduled':
      return `已安排重试（下一轮 attempt=${toCount(payload.next_attempt_no)}）。`
    case 'review_retry_started':
      return `重试开始（attempt=${toCount(payload.attempt_no)}）。`
    case 'review_completed': {
      const result = (payload.result ?? payload) as Record<string, unknown>
      const summary = (result.summary ?? payload.summary ?? {}) as Record<string, unknown>
      const finalOutcome = typeof summary.final_outcome === 'string' ? summary.final_outcome : ''
      const verifiedLevel = typeof summary.verified_level === 'string' ? summary.verified_level : 'L0'
      if (finalOutcome) {
        return `任务完成：${finalOutcome}（${verifiedLevel}）`
      }
      return `分析完成：${toArrayCount(result.issues)} 个问题，${toArrayCount(result.symbols)} 个符号。`
    }
    case 'review_failed':
      return `分析失败：${toFailureMessage(payload)}`
    case 'heartbeat':
      return '连接保持中。'
    default:
      return event.message || getEventTitle(event.eventType)
  }
}

export function summarizePayload(payload: Record<string, unknown>): string {
  const stage = typeof payload.stage === 'string' ? payload.stage : undefined
  const code = typeof payload.code === 'string' ? payload.code : undefined

  const compactFields = [
    pair('stage', stage),
    pair('status', typeof payload.status === 'string' ? payload.status : undefined),
    pair('classes', maybeCount(payload.classesCount)),
    pair('methods', maybeCount(payload.methodsCount)),
    pair('symbols', maybeCount(payload.symbolsCount)),
    pair('issues', maybeCount(payload.issuesCount)),
    pair('plans', maybeCount(payload.planCount)),
    pair('attempt', maybeCount(payload.attempt_no)),
    pair('code', code),
  ].filter((item): item is string => Boolean(item))

  if (compactFields.length > 0) return compactFields.join(', ')

  const keys = Object.keys(payload)
  if (keys.length === 0) return '空 payload'
  return `字段：${keys.join(', ')}`
}

export function countSyntaxIssues(value: unknown): number {
  if (!Array.isArray(value)) return 0
  return value.filter((item) => {
    if (typeof item !== 'object' || item === null) return false
    const record = item as Record<string, unknown>
    const issueType = String(record.type ?? record.issueType ?? '').toLowerCase()
    const ruleId = String(record.ruleId ?? record.rule_id ?? '').toUpperCase()
    return issueType === 'syntax_error' || issueType === 'parse_error' || ruleId === 'AST_PARSE_ERROR'
  }).length
}

function resolveStageStatus(
  stageKey: StageKey,
  stageEvents: ReviewEvent[],
  allEventCount: number,
  taskStatus: 'IDLE' | ReviewTaskStatus
): StageUiStatus {
  if (stageKey === 'task_created') {
    if (stageEvents.length > 0 || (allEventCount > 0 && taskStatus !== 'IDLE')) {
      return 'completed'
    }
    return 'pending'
  }

  if (stageEvents.length === 0) {
    return 'pending'
  }

  const failureSet = STAGE_FAILURE_EVENTS[stageKey]
  if (stageEvents.some((event) => failureSet.has(event.eventType))) {
    return 'failed'
  }

  const completedSet = STAGE_COMPLETED_MARKERS[stageKey]
  if (stageEvents.some((event) => completedSet.has(event.eventType))) {
    return 'completed'
  }

  return 'active'
}

function toWarningMessage(payload: Record<string, unknown>): string {
  const code = typeof payload.code === 'string' ? payload.code : ''
  if (code === 'SEMGREP_UNAVAILABLE') {
    return '本机未检测到 semgrep，可继续使用 AST/Symbol 结果'
  }
  if (code === 'SEMGREP_TIMEOUT') {
    return 'semgrep 执行超时，已降级返回空问题列表'
  }
  if (code === 'SEMGREP_EXEC_ERROR') {
    return 'semgrep 执行异常，已降级返回空问题列表'
  }
  return typeof payload.message === 'string' ? payload.message : '扫描阶段发生可恢复告警'
}

function toFailureMessage(payload: Record<string, unknown>): string {
  const diagnostics = payload.diagnostics
  if (Array.isArray(diagnostics)) {
    const codes = diagnostics
      .map((item) => (typeof item === 'object' && item !== null ? (item as Record<string, unknown>).code : ''))
      .filter((item) => typeof item === 'string' && item.length > 0)
    if (codes.includes('EMPTY_INPUT')) {
      return '输入为空'
    }
    if (codes.includes('UNSUPPORTED_LANGUAGE')) {
      return '仅支持 Java 代码'
    }
  }
  if (typeof payload.error === 'string' && payload.error.length > 0) {
    return payload.error
  }
  return '任务执行失败'
}

function toCount(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : 0
  }
  return 0
}

function maybeCount(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined
  return toCount(value)
}

function toArrayCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}

function pair(key: string, value: string | number | undefined): string | undefined {
  if (value === undefined) return undefined
  return `${key}=${value}`
}

