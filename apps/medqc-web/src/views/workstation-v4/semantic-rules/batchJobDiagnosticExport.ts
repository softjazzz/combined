import type {
  SichuanBatchFailedItem,
  SichuanBatchIssueItem,
  SichuanBatchJob,
  SichuanBatchJobDebugSnapshot,
} from './types'

const PACKAGE_SCHEMA = 'medqc-qc-task-diagnostic-v1'
const SECRET_PATTERN =
  /(?:bearer\s+[a-z0-9._~-]+|sk-[a-z0-9_-]+|(?:api[_-]?key|password|token|authorization)\s*[:=]\s*[^\r\n,;]+)/giu

function text(value: unknown, limit = 500): string {
  return String(value ?? '')
    .replace(SECRET_PATTERN, '[已移除凭证]')
    .trim()
    .slice(0, limit)
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/gu, '\\$&')
}

function collectPatientIdentifiers(
  job: SichuanBatchJob,
  snapshot?: SichuanBatchJobDebugSnapshot | null,
): string[] {
  const rows = [
    ...(job.failed_records || []),
    ...(job.items || []),
    ...(snapshot?.recent_failed_records || []),
    ...(snapshot?.recent_items || []),
  ] as Array<Record<string, unknown>>
  const values = new Set<string>()
  for (const row of rows) {
    for (const field of ['patient_name', 'patient_id', 'visit_id', 'record_id', 'record_ref']) {
      const value = String(row[field] ?? '').trim()
      if (value.length >= 2) values.add(value)
    }
  }
  return [...values].sort((left, right) => right.length - left.length)
}

function createSafeText(patientIdentifiers: string[]) {
  return (value: unknown, limit = 500): string => {
    let result = text(value, limit * 2)
    for (const identifier of patientIdentifiers) {
      result = result.replace(new RegExp(escapeRegExp(identifier), 'gu'), '[已移除身份]')
    }
    return result.slice(0, limit)
  }
}

function number(value: unknown): number | undefined {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function compact<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== undefined && item !== '' && item !== null),
  ) as Partial<T>
}

function pickProgress(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return
  const source = value as Record<string, unknown>
  const result = compact({
    step_key: text(source.step_key, 64),
    processed_records: number(source.processed_records),
    total_records: number(source.total_records),
    progress_percent: number(source.progress_percent),
    rule_index: number(source.rule_index),
    rule_count: number(source.rule_count),
    completed: number(source.completed),
    failed: number(source.failed),
  })
  return Object.keys(result).length ? result : undefined
}

function pickDebug(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return
  const source = value as Record<string, unknown>
  const result = compact({
    trace_id: text(source.trace_id, 128),
    request_id: text(source.request_id, 128),
    executor_type: text(source.executor_type, 64),
    execution_domain: text(source.execution_domain, 64),
    phase: text(source.phase, 64),
    retry_count: number(source.retry_count),
    cache_hit: typeof source.cache_hit === 'boolean' ? source.cache_hit : undefined,
  })
  return Object.keys(result).length ? result : undefined
}

function recordAliasFactory() {
  const aliases = new Map<string, string>()
  return (value: SichuanBatchFailedItem | SichuanBatchIssueItem): string => {
    const key = text(value.record_ref || value.visit_id || value.record_id, 160) || 'unknown'
    if (!aliases.has(key)) aliases.set(key, `病例-${String(aliases.size + 1).padStart(3, '0')}`)
    return aliases.get(key)!
  }
}

function safeFailure(
  value: SichuanBatchFailedItem,
  alias: (value: SichuanBatchFailedItem) => string,
  safeText: (value: unknown, limit?: number) => string,
) {
  return compact({
    record: alias(value),
    rule_id: text(value.rule_id, 64),
    rule_job_id: text(value.rule_job_id, 128),
    status: text(value.failure_status || value.status, 64),
    reason_code: text(value.reason_code, 64),
    error_phase: text(value.error_phase, 64),
    error: safeText(value.error),
    trace_id: text(value.trace_id, 128),
    rule_version: text(value.rule_version, 64),
    prompt_version: text(value.prompt_version, 64),
  })
}

function safeResult(value: SichuanBatchIssueItem, alias: (value: SichuanBatchIssueItem) => string) {
  return compact({
    record: alias(value),
    rule_id: text(value.rule_id || value.rule_code, 64),
    status: text(value.result_status || value.canonical_status || value.status, 64),
    reason_code: text(value.reason_code, 64),
    executor_type: text(value.executor_type, 64),
    model_version: text(value.model_version, 128),
    prompt_version: text(value.prompt_version, 64),
    cache_hit: typeof value.cache_hit === 'boolean' ? value.cache_hit : undefined,
    trace_id: text(value.trace_id, 128),
  })
}

export function buildBatchJobDiagnosticText(
  job: SichuanBatchJob,
  snapshot?: SichuanBatchJobDebugSnapshot | null,
  generatedAt = new Date().toISOString(),
): string {
  const alias = recordAliasFactory()
  const safeText = createSafeText(collectPatientIdentifiers(job, snapshot))
  const summary = job.summary || undefined
  const failures = (job.failed_records || snapshot?.recent_failed_records || []).map((item) =>
    safeFailure(item, alias, safeText),
  )
  const recentResults = (snapshot?.recent_items || job.items || [])
    .slice(-200)
    .map((item) => safeResult(item, alias))
  const payload = {
    schema_version: PACKAGE_SCHEMA,
    generated_at: generatedAt,
    privacy: {
      level: 'redacted_task_diagnostic',
      patient_identity: 'aliased',
      raw_medical_text_included: false,
      model_prompt_or_raw_response_included: false,
      credentials_included: false,
    },
    task: compact({
      job_id: text(job.id, 128),
      status: text(job.status, 64),
      scope: text(job.scope, 64),
      rule_code: text(job.rule_code, 64),
      rule_name: text(job.rule_name, 160),
      rule_set_key: text(job.rule_set_key || summary?.rule_set_key, 128),
      rule_set_version: text(job.rule_set_version || summary?.rule_set_version, 64),
      execution_mode: text(job.execution_mode || snapshot?.execution_mode, 64),
      created_at: text(job.created_at, 64),
      started_at: text(job.started_at, 64),
      finished_at: text(job.finished_at, 64),
      updated_at: text(job.updated_at || snapshot?.updated_at, 64),
      error_message: safeText(job.error_message),
    }),
    counts: compact({
      total_records: number(job.total_records ?? summary?.total_records),
      success_count: number(job.success_count ?? summary?.success_count),
      failed_count: number(job.failed_count ?? summary?.failed_count),
      completed_rule_count: number(summary?.completed_rule_count),
      failed_rule_count: number(summary?.failed_rule_count),
      issue_records: number(job.issue_records ?? summary?.issue_records),
      compliant_records: number(job.compliant_records ?? summary?.compliant_records),
      total_tokens: number(job.total_tokens ?? summary?.total_tokens),
      total_processing_time: number(job.total_processing_time ?? summary?.total_processing_time),
      wall_clock_time: number(job.wall_clock_time ?? summary?.wall_clock_time),
    }),
    retry: summary?.automatic_failed_rule_retry
      ? compact({
          status: text(summary.automatic_failed_rule_retry.status, 64),
          completed_attempts: number(summary.automatic_failed_rule_retry.completed_attempts),
          max_attempts: number(summary.automatic_failed_rule_retry.max_attempts),
          remaining_failure_count: number(
            summary.automatic_failed_rule_retry.remaining_failure_count,
          ),
          should_retry: summary.automatic_failed_rule_retry.should_retry,
        })
      : undefined,
    progress: pickProgress(job.progress),
    failures,
    recent_results: recentResults,
    rule_executions: (snapshot?.rules || []).map((rule) =>
      compact({
        rule_job_id: text(rule.rule_job_id, 128),
        rule_code: text(rule.rule_code, 64),
        rule_name: text(rule.rule_name, 160),
        status: text(rule.status, 64),
        progress: pickProgress(rule.progress),
        debug: pickDebug(rule.debug),
        success_count: number(rule.success_count),
        failed_count: number(rule.failed_count),
        total_tokens: number(rule.total_tokens),
        total_processing_time: number(rule.total_processing_time),
        error_message: safeText(rule.error_message),
        updated_at: text(rule.updated_at, 64),
      }),
    ),
  }
  const lines = [
    '# MedQC 质控任务诊断包',
    `格式版本：${PACKAGE_SCHEMA}`,
    `生成时间：${generatedAt}`,
    '',
    '## 使用说明',
    '本包用于定位批量质控执行、模型输出校验、自动补跑和结果汇总问题。病历身份已替换为包内临时别名，不包含完整病历正文、模型原始提示词或响应、访问凭证。',
    '',
    '## 任务摘要',
    `- 任务：${payload.task.rule_name || payload.task.rule_code || payload.task.job_id}`,
    `- 状态：${payload.task.status || 'unknown'}`,
    `- 病历：${payload.counts.success_count || 0} 成功 / ${payload.counts.failed_count || 0} 失败 / ${payload.counts.total_records || 0} 总数`,
    `- 规则：${payload.counts.completed_rule_count || 0} 完成 / ${payload.counts.failed_rule_count || 0} 失败`,
    '',
    `## 失败定位（${failures.length} 项）`,
    ...(failures.length
      ? failures.map(
          (item) =>
            `- ${item.record || '未知病例'} · ${item.rule_id || '未知规则'} · ${item.reason_code || item.status || '原因待确认'}${item.error_phase ? ` · ${item.error_phase}` : ''}`,
        )
      : ['- 未记录失败项']),
    '',
    '## 机器可读数据',
    '```json',
    JSON.stringify(payload, null, 2).replace(/`/gu, '\\u0060'),
    '```',
  ]
  return lines.join('\n')
}

export function batchJobDiagnosticFilename(job: SichuanBatchJob): string {
  const id = text(job.id, 80).replace(/[^a-z0-9_-]+/giu, '-') || 'unknown'
  return `质控任务诊断包_${id}.md`
}
