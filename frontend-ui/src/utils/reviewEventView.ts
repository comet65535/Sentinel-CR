import type { ReviewEvent, ReviewTaskStatus } from '../types/review'

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
  review_completed: '分析完成',
  review_failed: '分析失败',
  heartbeat: '连接保活',
}

export const AGGREGATED_EVENT_TYPES = new Set<string>([
  'task_created',
  'analysis_started',
  'ast_parsing_completed',
  'symbol_graph_completed',
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
  'review_completed',
  'review_failed',
  'heartbeat',
])

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
  'review_completed',
  'review_failed',
  'heartbeat',
] as const

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
      return `AST 解析完成（${toCount(payload.classesCount)} 个类，${toCount(payload.methodsCount)} 个方法，${toCount(payload.fieldsCount)} 个字段）`
    }
    case 'symbol_graph_started':
      return '正在构建符号图。'
    case 'symbol_graph_completed':
      return `符号图构建完成（${toCount(payload.symbolsCount)} 个符号，${toCount(payload.callEdgesCount)} 条调用边）`
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
      const syntaxCount = toCount(summary.syntaxErrorsCount)
      if (syntaxCount > 0) {
        return `分析器处理完成（问题 ${toCount(summary.issuesCount)}，其中 ${syntaxCount} 个为语法错误）`
      }
      return `分析器处理完成（问题 ${toCount(summary.issuesCount)}，符号 ${toCount(summary.symbolsCount)}）`
    }
    case 'planner_started':
      return `开始构建 Issue Graph 与 Repair Plan（输入问题 ${toCount(payload.inputIssueCount)}，符号 ${toCount(payload.inputSymbolCount)}）`
    case 'issue_graph_built':
      return `问题图构建完成（${toCount(payload.issueCount)} 个节点，${toCount(payload.edgeCount)} 条边）`
    case 'repair_plan_created':
      return `修复计划已生成（${toCount(payload.planCount)} 个计划项）`
    case 'planner_completed':
      return `规划器处理完成（问题 ${toCount(payload.issueCount)}，计划 ${toCount(payload.planCount)}）`
    case 'case_memory_search_started':
      return `开始检索案例库（问题 ${toCount(payload.issue_count)}）`
    case 'case_memory_matched':
      return `命中案例 ${toCount(payload.match_count)} 条`
    case 'case_memory_completed':
      return `案例检索完成（命中 ${toCount(payload.match_count)}）`
    case 'fixer_started':
      return `开始生成补丁（计划 ${toCount(payload.plan_count)}，案例 ${toCount(payload.memory_match_count)}）`
    case 'patch_generated':
      return 'Unified Diff 补丁生成完成'
    case 'fixer_completed':
      return 'Fixer 阶段完成'
    case 'fixer_failed':
      return `Fixer 失败：${typeof payload.reason === 'string' ? payload.reason : '无有效补丁'}`
    case 'review_completed': {
      const result = (payload.result ?? payload) as Record<string, unknown>
      const summary = (result.summary ?? payload.summary ?? {}) as Record<string, unknown>
      const finalOutcome = typeof summary.final_outcome === 'string' ? summary.final_outcome : ''
      if (finalOutcome) {
        return `任务完成：${finalOutcome}（attempt=${toCount(summary.attempt_count)}）`
      }
      const syntaxCount = countSyntaxIssues(result.issues)
      if (syntaxCount > 0) {
        return `分析完成：${toArrayCount(result.issues)} 个问题，其中 ${syntaxCount} 个为语法错误`
      }
      return `分析完成：${toArrayCount(result.issues)} 个问题，${toArrayCount(result.symbols)} 个符号，${toArrayCount(result.diagnostics)} 条诊断`
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
    pair('classes', maybeCount(payload.classesCount)),
    pair('methods', maybeCount(payload.methodsCount)),
    pair('symbols', maybeCount(payload.symbolsCount)),
    pair('issues', maybeCount(payload.issuesCount)),
    pair('parseErrors', maybeCount(payload.syntaxIssuesCount ?? payload.parseErrorsCount)),
    pair('plans', maybeCount(payload.planCount)),
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
