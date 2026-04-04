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
}

export interface ConversationItem {
  id: string
  role: 'user' | 'assistant'
  type: 'code' | 'status' | 'result'
  title: string
  text: string
  code?: string
}

export interface ReadableStageTimelineItem {
  key: string
  title: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  summary: string
  failureReason: string | null
  detailLog: string | null
  events: ReviewEvent[]
}

const EVENT_TITLES: Record<string, string> = {
  task_created: '任务创建',
  analysis_started: '初始化分析',
  ast_parsing_started: '语法分析',
  ast_parsing_completed: '语法分析完成',
  symbol_graph_started: '符号关系构建',
  symbol_graph_completed: '符号关系完成',
  semgrep_scan_started: '规则扫描',
  semgrep_scan_completed: '规则扫描完成',
  semgrep_scan_warning: '规则扫描降级',
  analyzer_completed: '分析完成',
  planner_started: '修复规划',
  issue_graph_built: '问题图构建',
  repair_plan_created: '修复计划生成',
  planner_completed: '规划完成',
  case_memory_search_started: '经验检索',
  case_memory_matched: '经验命中',
  case_memory_completed: '经验检索完成',
  fixer_started: '补丁生成',
  patch_generated: '补丁已生成',
  fixer_completed: '补丁生成完成',
  fixer_failed: '补丁生成失败',
  verifier_started: '验证启动',
  patch_apply_started: '补丁应用',
  patch_apply_completed: '补丁应用完成',
  patch_apply_failed: '补丁应用失败',
  compile_started: '编译验证',
  compile_completed: '编译验证完成',
  compile_failed: '编译验证失败',
  lint_started: 'Lint 验证',
  lint_completed: 'Lint 验证完成',
  lint_failed: 'Lint 验证失败',
  test_started: '测试验证',
  test_completed: '测试验证完成',
  test_failed: '测试验证失败',
  security_rescan_started: '安全复扫',
  security_rescan_completed: '安全复扫完成',
  security_rescan_failed: '安全复扫失败',
  verifier_completed: '验证完成',
  verifier_failed: '验证失败',
  review_retry_scheduled: '重试已调度',
  review_retry_started: '重试开始',
  langgraph_compiled: 'LangGraph 已编译',
  langgraph_node_started: 'LangGraph 节点开始',
  langgraph_node_completed: 'LangGraph 节点完成',
  context_budget_initialized: '上下文预算初始化',
  context_resource_loaded: '上下文资源已加载',
  context_budget_updated: '上下文预算更新',
  context_budget_exhausted: '上下文预算耗尽',
  repo_memory_loaded: '仓库记忆已加载',
  short_term_memory_updated: '短期记忆已更新',
  case_store_promoted: '案例已沉淀',
  mcp_resource_requested: 'MCP 资源请求',
  mcp_resource_completed: 'MCP 资源完成',
  mcp_tool_started: 'MCP 工具开始',
  mcp_tool_completed: 'MCP 工具完成',
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
  'review_completed',
  'review_failed',
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

export function buildReadableCurrentStatus(
  events: ReviewEvent[],
  reviewResult: Record<string, unknown> | null
): string {
  const latest = [...events]
    .sort((a, b) => b.sequence - a.sequence)
    .find((event) => event.eventType !== 'heartbeat')

  if (latest === undefined) {
    return '等待提交代码。'
  }

  const map: Record<string, string> = {
    analysis_started: '正在读取并初始化分析任务…',
    ast_parsing_started: '正在做语法分析…',
    symbol_graph_started: '正在构建符号关系…',
    semgrep_scan_started: '正在执行规则扫描…',
    planner_started: '正在规划修复顺序…',
    case_memory_search_started: '正在查询历史修复经验…',
    fixer_started: '正在生成补丁…',
    patch_apply_started: '正在应用补丁…',
    compile_started: '正在进行编译验证…',
    review_retry_started: '上一轮编译失败，正在重试…',
    review_completed: '已完成，正在汇总结果…',
    review_failed: '处理失败。',
  }

  if (map[latest.eventType]) {
    return map[latest.eventType]
  }

  if (latest.eventType === 'verifier_started') {
    return '正在应用补丁并编译验证…'
  }
  if (latest.eventType === 'compile_failed') {
    return '编译失败，正在评估是否进入重试…'
  }
  if (latest.eventType === 'verifier_failed') {
    return '验证失败，正在整理失败原因…'
  }
  if (latest.eventType === 'patch_generated') {
    return '补丁已生成，准备进入验证…'
  }

  if (reviewResult) {
    return '处理完成，正在展示结果。'
  }
  return '系统正在处理中…'
}

export function buildReadableSuccessMessage(reviewResult: Record<string, unknown> | null): string {
  if (!reviewResult) {
    return '处理完成。'
  }
  const stats = extractResultStats(reviewResult)
  if (stats.noFixNeeded) {
    return '代码健康，无需修复。已完成基础分析并直接收口。'
  }
  return `已完成。共识别 ${stats.issueCount} 个问题，生成 ${stats.attemptCount} 次补丁尝试，最终结果 ${stats.finalOutcome}（${stats.verifiedLevel}）。`
}

export function buildReadableFailureMessage(
  reviewResult: Record<string, unknown> | null,
  fallbackStatus: string
): string {
  if (!reviewResult) {
    return fallbackStatus
  }
  const stats = extractResultStats(reviewResult)
  if (stats.userMessage && stats.userMessage !== '-') {
    return stats.userMessage
  }

  const stage = stats.failedStage === '-' ? '未知阶段' : stats.failedStage
  const reason = stats.failureReason === '-' ? '原因暂不可用' : stats.failureReason
  if (reason.includes('llm_not_enabled_or_missing_credentials')) {
    return 'LLM disabled / missing credentials。请配置凭证后重试。'
  }
  const retryPart = `已重试 ${stats.retryCount} 次${stats.retryExhausted ? '，重试预算已耗尽' : ''}`
  return `处理在 ${stage} 阶段失败，${reason}。${retryPart}。`
}

export function buildConversationItems(
  events: ReviewEvent[],
  reviewResult: Record<string, unknown> | null,
  submittedCode: string,
  currentStatusLine: string
): ConversationItem[] {
  const items: ConversationItem[] = []
  if (submittedCode.trim()) {
    items.push({
      id: 'user-code',
      role: 'user',
      type: 'code',
      title: '你',
      text: '请根据我的约束修复这段代码。',
      code: submittedCode,
    })
  }

  const hasCompleted = events.some((event) => event.eventType === 'review_completed')
  if (!hasCompleted) {
    items.push({
      id: 'assistant-status',
      role: 'assistant',
      type: 'status',
      title: 'Sentinel-CR',
      text: currentStatusLine,
    })
    return items
  }

  const stats = reviewResult ? extractResultStats(reviewResult) : null
  const isSuccess = stats !== null && (stats.finalOutcome === 'verified_patch' || stats.noFixNeeded)
  items.push({
    id: 'assistant-result',
    role: 'assistant',
    type: 'result',
    title: 'Sentinel-CR',
    text: isSuccess
      ? buildReadableSuccessMessage(reviewResult)
      : buildReadableFailureMessage(reviewResult, currentStatusLine),
  })
  return items
}

export function buildReadableStageTimeline(
  events: ReviewEvent[],
  reviewResult: Record<string, unknown> | null
): ReadableStageTimelineItem[] {
  const sorted = [...events].sort((a, b) => a.sequence - b.sequence)
  const resultStats = reviewResult ? extractResultStats(reviewResult) : null

  const stages: Array<{ key: string; title: string; description: string; eventTypes: string[] }> = [
    {
      key: 'analyzer',
      title: '语法分析',
      description: '正在检查类、方法、语法错误和静态规则命中。',
      eventTypes: [
        'analysis_started',
        'ast_parsing_started',
        'ast_parsing_completed',
        'symbol_graph_started',
        'symbol_graph_completed',
        'semgrep_scan_started',
        'semgrep_scan_completed',
        'semgrep_scan_warning',
        'analyzer_completed',
      ],
    },
    {
      key: 'planner',
      title: '修复规划',
      description: '正在判断先修哪些问题以及是否会产生冲突。',
      eventTypes: ['planner_started', 'issue_graph_built', 'repair_plan_created', 'planner_completed'],
    },
    {
      key: 'memory',
      title: '经验检索',
      description: '正在查找相似历史修复案例并给出策略提示。',
      eventTypes: ['case_memory_search_started', 'case_memory_matched', 'case_memory_completed'],
    },
    {
      key: 'fixer',
      title: '生成补丁',
      description: '正在生成统一 diff 补丁。',
      eventTypes: ['fixer_started', 'patch_generated', 'fixer_completed', 'fixer_failed'],
    },
    {
      key: 'patch_apply',
      title: '补丁应用',
      description: '正在把补丁应用到临时代码副本。',
      eventTypes: ['patch_apply_started', 'patch_apply_completed', 'patch_apply_failed'],
    },
    {
      key: 'compile',
      title: '编译验证',
      description: '正在使用 javac 验证补丁是否能编译通过。',
      eventTypes: ['compile_started', 'compile_completed', 'compile_failed'],
    },
    {
      key: 'retry',
      title: '重试',
      description: '上一轮失败后，正在根据失败原因重新生成补丁。',
      eventTypes: ['review_retry_scheduled', 'review_retry_started'],
    },
    {
      key: 'completed',
      title: '最终收口',
      description: '正在汇总最终结果并返回给页面。',
      eventTypes: ['review_completed', 'review_failed'],
    },
  ]

  return stages.map((stage) => {
    const stageEvents = sorted.filter((event) => stage.eventTypes.includes(event.eventType))
    const lastEvent = stageEvents[stageEvents.length - 1]
    const failureEvent = stageEvents.find((event) => event.eventType.endsWith('_failed'))

    let status: ReadableStageTimelineItem['status'] = 'pending'
    if (stageEvents.length > 0) {
      status = 'running'
    }

    if (failureEvent) {
      status = 'failed'
    } else if (lastEvent) {
      const eventType = lastEvent.eventType
      if (eventType.endsWith('_completed') || eventType === 'fixer_completed' || eventType === 'review_completed') {
        status = 'completed'
      }
      if (
        stageEvents.some(
          (event) =>
            event.payload &&
            typeof event.payload.status === 'string' &&
            String(event.payload.status).toLowerCase() === 'skipped'
        )
      ) {
        status = 'skipped'
      }
    }

    let summary = '等待开始。'
    if (lastEvent) {
      summary = buildReadableEventLine(lastEvent)
    }

    let failureReason: string | null = null
    if (failureEvent) {
      const reason = extractFailureReason(failureEvent.payload)
      failureReason = reason || '该阶段失败，未提供更多原因。'
    }
    let detailLog: string | null = failureEvent ? extractFailureDetail(failureEvent.payload) : null

    if (stage.key === 'retry' && resultStats !== null) {
      if (resultStats.retryCount > 0 && status === 'pending') {
        status = 'running'
        summary = `已触发 ${resultStats.retryCount} 次重试。`
      }
      if (resultStats.finalOutcome === 'failed_after_retries') {
        status = 'failed'
        summary = `已重试 ${resultStats.retryCount} 次，达到最大重试次数。`
        failureReason = resultStats.failureReason !== '-' ? resultStats.failureReason : failureReason
        detailLog = resultStats.failureDetail !== '-' ? resultStats.failureDetail : detailLog
      } else if (
        (resultStats.finalOutcome === 'verified_patch' || resultStats.noFixNeeded) &&
        resultStats.retryCount > 0
      ) {
        status = 'completed'
        summary = `重试结束，最终在第 ${resultStats.retryCount + 1} 轮收口。`
      }
    }

    if (
      resultStats?.noFixNeeded &&
      ['planner', 'memory', 'fixer', 'patch_apply', 'compile', 'retry'].includes(stage.key)
    ) {
      status = 'skipped'
      summary = '未发现可修复问题，已短路跳过该阶段。'
      failureReason = null
      detailLog = null
    }

    if (stage.key === 'completed' && reviewResult) {
      const stats = resultStats ?? extractResultStats(reviewResult)
      if (stats.finalOutcome === 'verified_patch' || stats.noFixNeeded) {
        summary = buildReadableSuccessMessage(reviewResult)
        status = 'completed'
      } else {
        summary = buildReadableFailureMessage(reviewResult, summary)
        status = 'failed'
        failureReason = stats.failureReason === '-' ? failureReason : stats.failureReason
        detailLog = stats.failureDetail === '-' ? detailLog : stats.failureDetail
      }
    }

    return {
      key: stage.key,
      title: stage.title,
      description: stage.description,
      status,
      summary,
      failureReason,
      detailLog,
      events: stageEvents,
    }
  })
}

export function extractResultStats(reviewResult: Record<string, unknown>): ResultStats {
  const summary = asRecord(reviewResult.summary)
  const memory = asRecord(reviewResult.memory)
  const patch = asRecord(reviewResult.patch)

  return {
    issueCount: toArrayCount(reviewResult.issues),
    repairPlanCount: toArrayCount(reviewResult.repair_plan),
    memoryMatchCount: toArrayCount(memory.matches),
    attemptCount: toArrayCount(reviewResult.attempts),
    patchStatus: toText(patch.status, '-'),
    verifiedLevel: toText(summary.verified_level, 'L0'),
    finalOutcome: toText(summary.final_outcome, '-'),
    retryCount: toNumber(summary.retry_count),
    failedStage: toText(summary.failed_stage, '-'),
    failureReason: toText(summary.failure_reason, '-'),
    failureDetail: toText(summary.failure_detail, '-'),
    retryExhausted: Boolean(summary.retry_exhausted),
    noFixNeeded: Boolean(summary.no_fix_needed),
    userMessage: toText(summary.user_message, '-'),
  }
}

export function summarizePayload(payload: Record<string, unknown>): string {
  const fields = [
    pair('status', typeof payload.status === 'string' ? payload.status : undefined),
    pair('attempt', toNumberOrUndefined(payload.attempt_no)),
    pair('reason', typeof payload.reason === 'string' ? payload.reason : undefined),
    pair('failed_stage', typeof payload.failed_stage === 'string' ? payload.failed_stage : undefined),
  ].filter((item): item is string => Boolean(item))

  if (fields.length > 0) {
    return fields.join('，')
  }
  const keys = Object.keys(payload)
  if (keys.length === 0) return '空 payload'
  return `字段：${keys.join(', ')}`
}

function buildReadableEventLine(event: ReviewEvent): string {
  const payload = event.payload ?? {}
  switch (event.eventType) {
    case 'analysis_started':
      return '分析任务已启动。'
    case 'ast_parsing_started':
      return '正在进行语法分析。'
    case 'ast_parsing_completed': {
      const count = toNumber(payload.syntaxIssuesCount ?? payload.parseErrorsCount)
      if (count > 0) {
        return `语法分析完成，检测到 ${count} 个语法问题。`
      }
      return '语法分析完成，未发现明显语法错误。'
    }
    case 'symbol_graph_started':
      return '正在构建符号关系。'
    case 'symbol_graph_completed':
      return `符号关系构建完成，共 ${toNumber(payload.symbolsCount)} 个符号。`
    case 'semgrep_scan_started':
      return '正在执行规则扫描。'
    case 'semgrep_scan_completed':
      return `规则扫描完成，发现 ${toNumber(payload.issuesCount)} 个问题。`
    case 'semgrep_scan_warning':
      return `规则扫描降级：${toText(payload.message, '已自动降级执行。')}`
    case 'planner_started':
      return '正在规划修复顺序。'
    case 'issue_graph_built':
      return `问题图构建完成，共 ${toNumber(payload.issueCount)} 个节点。`
    case 'repair_plan_created':
      return `修复计划已生成，共 ${toNumber(payload.planCount)} 项。`
    case 'planner_completed':
      return '修复规划阶段完成。'
    case 'case_memory_search_started':
      return '正在查询历史修复经验。'
    case 'case_memory_matched':
      return `命中 ${toNumber(payload.match_count)} 条历史案例。`
    case 'case_memory_completed':
      return '经验检索阶段完成。'
    case 'fixer_started':
      return '正在生成统一 diff 补丁。'
    case 'patch_generated':
      return '补丁生成完成。'
    case 'fixer_completed':
      return '补丁生成阶段结束。'
    case 'fixer_failed':
      return `补丁生成失败：${toText(payload.reason, '无有效补丁。')}`
    case 'patch_apply_started':
      return '正在把补丁应用到临时代码副本。'
    case 'patch_apply_completed':
      return '补丁应用完成。'
    case 'patch_apply_failed':
      return `补丁应用失败：${extractFailureReason(payload) || '无法应用补丁。'}`
    case 'compile_started':
      return '正在使用 javac 进行编译验证。'
    case 'compile_completed': {
      const status = toText(payload.status, 'passed')
      if (status === 'skipped') {
        return '编译验证已跳过。'
      }
      return '编译验证通过。'
    }
    case 'compile_failed':
      return `编译验证失败：${extractFailureReason(payload) || '编译未通过。'}`
    case 'review_retry_scheduled':
      return '上一轮失败，系统已安排重试。'
    case 'review_retry_started':
      return '上一轮失败，正在重试。'
    case 'verifier_completed':
      return `验证完成，当前等级 ${toText((payload.verification as Record<string, unknown> | undefined)?.verified_level ?? payload.verified_level, 'L0')}。`
    case 'verifier_failed':
      return `验证失败：${extractFailureReason(payload) || '验证未通过。'}`
    case 'review_completed':
      return '结果收口完成。'
    case 'review_failed':
      return `处理失败：${extractFailureReason(payload) || '任务失败。'}`
    default:
      return event.message || getEventTitle(event.eventType)
  }
}

function extractFailureReason(payload: Record<string, unknown>): string | null {
  const reason = typeof payload.reason === 'string' ? payload.reason.trim() : ''
  const candidates = [payload.stderr_summary, payload.failure_detail, payload.failure_reason, payload.reason, payload.error]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      if (candidate === reason && ['compile_failed', 'patch_apply_failed', 'verifier_failed'].includes(reason)) {
        continue
      }
      return candidate.trim()
    }
  }
  return null
}

function extractFailureDetail(payload: Record<string, unknown>): string | null {
  const candidates = [payload.failure_detail, payload.stderr_summary, payload.stdout_summary]
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) {
      return candidate.trim()
    }
  }
  return null
}

function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {}
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

function toNumberOrUndefined(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined
  return toNumber(value)
}

function toArrayCount(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}

function pair(key: string, value: string | number | undefined): string | undefined {
  if (value === undefined) return undefined
  return `${key}=${value}`
}
