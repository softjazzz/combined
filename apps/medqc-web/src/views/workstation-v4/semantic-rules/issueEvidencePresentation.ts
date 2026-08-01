import { resolveIssueCanonicalStatus } from './batchResultStatus'
import type { SichuanBatchIssueItem, SichuanBatchSafeEvidenceRef } from './types'

export interface IssueEvidencePresentationOptions {
  isLuxian0609BatchJob: () => boolean
  isLuxianNativeSliceBatchJob: () => boolean
  resolveStatusText: (status?: string) => string
}

export function createIssueEvidencePresentation(options: IssueEvidencePresentationOptions) {
  const isLuxian0609BatchJob = {
    get value() {
      return options.isLuxian0609BatchJob()
    },
  }
  const isLuxianNativeSliceBatchJob = {
    get value() {
      return options.isLuxianNativeSliceBatchJob()
    },
  }
  const resolveStatusText = options.resolveStatusText

  function truncateText(text?: string, limit = 80): string {
    const normalized = String(text || '').trim()
    if (!normalized) return '-'
    return normalized.length > limit ? normalized.slice(0, limit) + '…' : normalized
  }

  type EvidenceDisplayRow = {
    key: string
    label: string
    value: string
  }

  type EvidenceDisplayItem = {
    key: string
    source: string
    recordTime: string
    fieldPath: string
    quote: string
  }

  type EvidenceSummaryPart = {
    key: string
    label: string
    value: string
    kind: 'time' | 'source' | 'delta' | 'field' | 'text'
  }

  type CopyEvidenceCompare = {
    left: {
      label: string
      quote: string
    }
    right: {
      label: string
      quote: string
    }
    pairs?: Array<{
      key: string
      index: number
      leftLabel: string
      leftQuote: string
      rightLabel: string
      rightQuote: string
      similarity?: string
    }>
    metric?: string
    differenceGap?: string
    legacyNotice?: string
  }

  function toRecord(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null
    return value as Record<string, unknown>
  }

  function toRecordList(value: unknown): Array<Record<string, unknown>> {
    if (!Array.isArray(value)) return []
    return value.filter(
      (item): item is Record<string, unknown> =>
        !!item && typeof item === 'object' && !Array.isArray(item),
    )
  }

  function normalizeEvidenceText(value: unknown, limit = 120) {
    const text = String(value ?? '')
      .replace(/\s+/g, ' ')
      .trim()
    if (!text) return ''
    return text.length > limit ? `${text.slice(0, limit)}...` : text
  }

  function normalizeEvidencePartValue(value: string, limit = 96) {
    return normalizeEvidenceText(
      value
        .replace(/\s+/g, ' ')
        .replace(/[；;，,。\s]+$/gu, '')
        .trim(),
      limit,
    )
  }

  function normalizeEvidencePartLabel(value: string) {
    const label = value
      .replace(/\s+/g, '')
      .replace(/[；;，,。]+$/gu, '')
      .trim()
    const map: Record<string, string> = {
      authored_at: '记录时间',
      record_time: '记录时间',
      submit_time: '提交时间',
      submitted_at: '提交时间',
      admission_time: '入院时间',
      discharge_time: '出院时间',
      deadline: '截止时间',
      elapsed: '间隔',
      delta: '差值',
    }
    return map[label] || label
  }

  function resolveEvidencePartKind(label: string, value: string): EvidenceSummaryPart['kind'] {
    const text = `${label} ${value}`
    if (/间隔|差值|超时|超过|小时|天/.test(text)) return 'delta'
    if (/时间|日期|入院|出院|记录|提交|截止/.test(label)) return 'time'
    if (/来源|文书|字段/.test(label)) return 'source'
    if (/^[a-z_]+$/i.test(label)) return 'field'
    return 'text'
  }

  function parseEvidenceSummaryParts(text?: string | null): EvidenceSummaryPart[] {
    const raw = sanitizeCustomerVisibleText(text)
    if (!raw) return []
    return raw
      .split(/[；;\n]/u)
      .map((part) => part.trim())
      .filter((part) => part.length >= 4)
      .map((part, index): EvidenceSummaryPart | null => {
        const segments = part
          .split(/：/u)
          .map((segment) => segment.trim())
          .filter(Boolean)
        if (segments.length < 2) return null

        const first = normalizeEvidencePartLabel(segments[0] || '')
        const second = normalizeEvidencePartLabel(segments[1] || '')
        const secondIsTechnicalField = /^[a-z_]+$/i.test(segments[1] || '')
        const label = secondIsTechnicalField ? `${first} · ${second}` : first
        const value = normalizeEvidencePartValue(
          secondIsTechnicalField ? segments.slice(2).join('：') : segments.slice(1).join('：'),
        )
        if (!label || !value) return null
        return {
          key: `evidence-part-${index}-${label}`,
          label,
          value,
          kind: resolveEvidencePartKind(label, value),
        }
      })
      .filter((part): part is EvidenceSummaryPart => Boolean(part))
      .slice(0, 6)
  }

  const INTERNAL_EVIDENCE_LABELS = [
    '证据模板',
    '触发门控',
    '触发状态',
    '触发说明',
    '触发关键词',
    '匹配关键词',
    '来源线索',
    '映射执行规则',
    '应包含证据要素',
    '质控点',
  ]

  const CUSTOMER_EVIDENCE_PRIORITY_LABELS = ['执行证据', '关键证据', '判定依据', '判断依据']

  const EVIDENCE_LABELS = [
    ...INTERNAL_EVIDENCE_LABELS,
    ...CUSTOMER_EVIDENCE_PRIORITY_LABELS,
    '数据缺口',
  ]

  function escapeRegExp(value: string) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  function resolveLabeledEvidenceValue(text: string, label: string) {
    const labelPattern = new RegExp(`${escapeRegExp(label)}[：:]\\s*`, 'u')
    const match = labelPattern.exec(text)
    if (!match) return ''
    const start = match.index + match[0].length
    const nextLabelIndexes = EVIDENCE_LABELS.filter((candidate) => candidate !== label)
      .map((candidate) => {
        const nextPattern = new RegExp(`${escapeRegExp(candidate)}[：:]\\s*`, 'u')
        const nextMatch = nextPattern.exec(text.slice(start))
        return nextMatch ? start + nextMatch.index : -1
      })
      .filter((index) => index >= 0)
    const end = nextLabelIndexes.length ? Math.min(...nextLabelIndexes) : text.length
    return text.slice(start, end).replace(/\s+/g, ' ').trim()
  }

  function removeInternalEvidenceSegments(text: string) {
    let output = text
    output = output
      .replace(/来源未标注\s*[·:：]\s*evidence[：:]?\s*/giu, '')
      .replace(/\bevidence[：:]\s*/giu, '')
      .replace(/\btrigger_status[：:]\s*unknown[。；;]*/giu, '')
      .replace(/\bunknown\b/giu, '')
      .replace(/LLM\s*语义规则/giu, '语义规则')
      .replace(/LLM\s*返回(?:了)?非结构化结果[，,。；;]*/giu, '自动判定未形成可靠结构化结论，')
      .replace(/请查看原始输出[。；;]*/gu, '')
      .replace(/本质控点按现有文书和结构化数据直接复核[。；;]*/gu, '')
      .replace(/判定依据[：:]\s*本质控点按现有文书和结构化数据直接复核[。；;]*/gu, '')
      .replace(/判定依据[：:]\s*已发现相关事件[，,]进入规则复核[。；;]*/gu, '')
      .replace(/已发现相关事件[，,]进入规则复核[。；;]*/gu, '')
    INTERNAL_EVIDENCE_LABELS.forEach((label) => {
      const labelPattern = new RegExp(`${escapeRegExp(label)}[：:]\\s*`, 'u')
      let match = labelPattern.exec(output)
      while (match) {
        const start = match.index
        const contentStart = start + match[0].length
        const nextLabelIndexes = EVIDENCE_LABELS.filter((candidate) => candidate !== label)
          .map((candidate) => {
            const nextPattern = new RegExp(`${escapeRegExp(candidate)}[：:]\\s*`, 'u')
            const nextMatch = nextPattern.exec(output.slice(contentStart))
            return nextMatch ? contentStart + nextMatch.index : -1
          })
          .filter((index) => index >= 0)
        const end = nextLabelIndexes.length ? Math.min(...nextLabelIndexes) : output.length
        output = `${output.slice(0, start)} ${output.slice(end)}`
        match = labelPattern.exec(output)
      }
    })
    return output.replace(/\s+/g, ' ').trim()
  }

  function sanitizeCustomerVisibleText(text?: string | null) {
    const cleaned = removeInternalEvidenceSegments(String(text || ''))
      .replace(/来源未标注\s*[·:：]\s*/gu, '')
      .replace(/待人工复核/gu, 'AI判断后建议确认')
      .replace(/待人工核对/gu, 'AI判断后建议确认')
      .replace(/建议人工复核/gu, '建议结合原文确认')
      .replace(/建议人工核对/gu, '建议结合原文确认')
      .replace(/需人工复核/gu, '需结合原文确认')
      .replace(/需人工核对/gu, '需结合原文确认')
      .replace(/需要人工复核/gu, '需要结合原文确认')
      .replace(/需要人工核对/gu, '需要结合原文确认')
      .replace(/人工复核/gu, '结合原文确认')
      .replace(/人工核对/gu, '结合原文确认')
      .replace(/\s+/g, ' ')
      .trim()
    return cleaned
  }

  function normalizeCustomerDataGapText(text?: string | null) {
    return String(text || '')
      .replace(/^数据缺口[：:]\s*/u, '')
      .replace(/复制病历比对未执行[。.]?/u, '复制病历比对未执行')
      .replace(/[；;]/gu, '，')
      .replace(/[，。、\s]+$/gu, '')
      .trim()
  }

  function normalizeCustomerEvidenceLabel(value: unknown) {
    const normalized = String(value || '').trim()
    if (!normalized || normalized === 'evidence') return ''
    const labelMap: Record<string, string> = {
      source_document: '来源文书',
      source_field: '来源字段',
      field_path: '来源字段',
      quote: '原文片段',
      supporting_evidence: '关键证据',
      text_evidence: '关键证据',
    }
    return labelMap[normalized] || normalized
  }

  function resolveLegacyEvidenceText(value: SichuanBatchIssueItem['evidence']) {
    return typeof value === 'string' ? value : ''
  }

  function isSafeEvidenceRef(value: unknown): value is SichuanBatchSafeEvidenceRef {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return false
    const record = value as Record<string, unknown>
    return (
      typeof record.source_type === 'string' &&
      record.source_type.trim().length > 0 &&
      typeof record.source_ref === 'string' &&
      /^[a-z0-9][a-z0-9:_-]{1,127}$/i.test(record.source_ref.trim())
    )
  }

  function resolveLuxianEvidenceSourceLabel(sourceType: string) {
    const sourceMap: Record<string, string> = {
      consultation_record: '会诊记录',
      daily_course_record: '日常病程记录',
      superior_round_record: '上级医师查房记录',
      surgery_record: '手术记录',
      presurg_summary: '术前小结',
      consent_form: '手术知情同意书',
      surgery_inform_consent: '手术知情同意书',
      inpat_order: '住院医嘱',
      medical_order: '医嘱',
      exam_report: '检查报告',
      lab_report: '检验报告',
    }
    return sourceMap[sourceType.trim().toLowerCase()] || '相关文书'
  }

  function resolveLuxianSafeEvidenceText(item: Partial<SichuanBatchIssueItem>) {
    if (!isLuxian0609BatchJob.value || !Array.isArray(item.evidence)) return ''
    return item.evidence
      .filter(isSafeEvidenceRef)
      .slice(0, 6)
      .map(
        (evidence) =>
          `${resolveLuxianEvidenceSourceLabel(evidence.source_type)} · ${evidence.source_ref.trim()}`,
      )
      .join('；')
  }

  function resolveLuxianReasonCodeText(reasonCode?: string) {
    const reasonMap: Record<string, string> = {
      consultation_application_needs_review: '会诊申请目的需复核',
      source_unavailable: '所需来源暂不可用',
      source_query_failed: '来源读取异常',
      source_incomplete: '来源资料不完整',
      evidence_insufficient: '现有证据不足',
    }
    return (
      reasonMap[
        String(reasonCode || '')
          .trim()
          .toLowerCase()
      ] || '按受控规则完成判定'
    )
  }

  function resolveCustomerEvidenceText(text?: string | null) {
    const raw = String(text || '').trim()
    if (!raw) return ''
    const priorityEvidence = CUSTOMER_EVIDENCE_PRIORITY_LABELS.map((label) =>
      removeInternalEvidenceSegments(resolveLabeledEvidenceValue(raw, label)),
    ).find(Boolean)
    if (priorityEvidence) return priorityEvidence
    return removeInternalEvidenceSegments(raw)
  }

  function isGenericCustomerEvidenceText(text: string) {
    const normalized = text.replace(/\s+/g, '')
    return (
      !normalized ||
      /^判定依据[:：]?未发现与本质控点直接相关的适用事件[。.]?$/.test(text.trim()) ||
      normalized === '未发现与本质控点直接相关的适用事件' ||
      normalized === '本质控点按现有文书和结构化数据直接复核'
    )
  }

  function resolveRichCustomerEvidenceText(item: Partial<SichuanBatchIssueItem>) {
    const evidenceText = resolveCustomerEvidenceText(resolveLegacyEvidenceText(item.evidence))
    if (!evidenceText || isGenericCustomerEvidenceText(evidenceText)) return ''
    return evidenceText
  }

  function resolveEvidenceDataGapText(text?: string | null) {
    const raw = String(text || '').trim()
    if (!raw) return ''
    return normalizeEvidenceText(
      normalizeCustomerDataGapText(resolveLabeledEvidenceValue(raw, '数据缺口')),
      80,
    )
  }

  function hasEvidenceChain(item?: Partial<SichuanBatchIssueItem> | null) {
    if (!item) return false
    return Boolean(
      item.result_status ||
        item.qc_point_id ||
        item.schema_version ||
        item.trigger ||
        item.dependencies ||
        item.decision ||
        item.review ||
        item.audit ||
        (Array.isArray(item.evidence_items) && item.evidence_items.length > 0),
    )
  }

  function resolveEvidenceStatusText(status?: string) {
    const normalized = String(status || '')
      .trim()
      .toLowerCase()
    const map: Record<string, string> = {
      non_compliant: '不合规',
      ai_suggested_non_compliant: 'AI判断：疑似问题',
      compliant: '合规',
      ai_suggested_compliant: 'AI判断：未见问题',
      not_applicable: '不适用',
      data_gap: '数据不足',
      uncertain: 'AI判断',
      not_executed: '未执行',
      technical_error: '技术异常',
      failed: '失败',
      error: '错误',
    }
    return map[normalized] || resolveStatusText(normalized)
  }

  function resolveIssueSeverityText(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    if (status === 'data_gap') return '数据不足，需补充资料'
    if (status === 'ai_suggested_non_compliant' || status === 'uncertain') return 'AI判断'
    if (status === 'ai_suggested_compliant') return 'AI未见问题'
    if (status === 'not_applicable') return '不适用'
    if (status === 'not_executed') return '未执行'
    if (status === 'technical_error') return '技术异常'
    return item.defect_level || '未分级'
  }

  function resolveIssueCardClass(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    return {
      'issue-conclusion-card--danger': status === 'non_compliant' || status === 'technical_error',
      'issue-conclusion-card--warning':
        status === 'data_gap' ||
        status === 'uncertain' ||
        status === 'ai_suggested_non_compliant' ||
        status === 'not_executed',
      'issue-conclusion-card--success':
        status === 'compliant' || status === 'ai_suggested_compliant',
      'issue-conclusion-card--muted': status === 'not_applicable',
    }
  }

  function resolveIssueResultKindText(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    if (status === 'non_compliant') return '确定问题'
    if (status === 'ai_suggested_non_compliant') return 'AI判断'
    if (status === 'ai_suggested_compliant') return 'AI未见问题'
    if (status === 'technical_error') return '技术异常'
    if (status === 'data_gap') return '数据不足'
    if (status === 'uncertain') return 'AI判断'
    if (status === 'not_executed') return '未执行'
    if (status === 'not_applicable') return '不适用'
    if (status === 'compliant') return '合规'
    return '结果项'
  }

  function resolveIssueResultKindClass(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    return {
      'issue-result-kind--danger': status === 'non_compliant',
      'issue-result-kind--error': status === 'technical_error',
      'issue-result-kind--review':
        status === 'data_gap' ||
        status === 'uncertain' ||
        status === 'ai_suggested_non_compliant' ||
        status === 'not_executed',
      'issue-result-kind--muted': status === 'not_applicable',
      'issue-result-kind--ok': status === 'compliant' || status === 'ai_suggested_compliant',
    }
  }

  function resolveExecutorTypeText(value?: string) {
    const normalized = String(value || '')
      .trim()
      .toLowerCase()
    if (normalized === 'program') return '自动规则'
    if (normalized === 'llm') return '语义规则'
    if (normalized === 'hybrid') return '混合执行'
    return value || '执行器未标注'
  }

  function resolveTriggerFacts(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
    const trigger = toRecord(item.trigger)
    const facts = toRecordList(trigger?.trigger_facts)
    const rows = facts
      .map((fact, index) => {
        const label =
          normalizeEvidenceText(fact.fact_label, 30) ||
          normalizeEvidenceText(fact.fact_type, 30) ||
          `触发事实 ${index + 1}`
        const sourceParts = [
          normalizeEvidenceText(fact.source_document_type, 24),
          normalizeEvidenceText(fact.source_document_id, 24),
          normalizeEvidenceText(fact.record_time, 24),
        ].filter(Boolean)
        const value = [
          normalizeEvidenceText(fact.fact_value, 120),
          sourceParts.length ? `来源：${sourceParts.join(' / ')}` : '',
        ]
          .filter(Boolean)
          .join('；')
        return {
          key: `trigger-${index}`,
          label,
          value,
        }
      })
      .filter((row) => row.value)
    const notApplicableReason = normalizeEvidenceText(trigger?.not_applicable_reason, 120)
    if (notApplicableReason) {
      rows.push({
        key: 'not-applicable-reason',
        label: '不适用原因',
        value: notApplicableReason,
      })
    }
    return rows
  }

  function resolveSourceNames(value: unknown) {
    const rows = toRecordList(value)
      .map((item) => {
        return (
          normalizeEvidenceText(item.source_name, 40) ||
          normalizeEvidenceText(item.table, 40) ||
          normalizeEvidenceText(item.source_table, 40)
        )
      })
      .filter(Boolean)
    return rows.length ? rows.join('、') : ''
  }

  function resolveMissingSources(item: Partial<SichuanBatchIssueItem>) {
    const dependencies = toRecord(item.dependencies)
    return toRecordList(dependencies?.missing_sources)
  }

  function resolveDependencyRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
    const dependencies = toRecord(item.dependencies)
    if (!dependencies) {
      return [
        {
          key: 'dependency-empty',
          label: '依赖数据',
          value: '暂无可展示的数据依赖',
        },
      ]
    }
    const rows: EvidenceDisplayRow[] = []
    const requiredSources = resolveSourceNames(dependencies.required_sources)
    if (requiredSources) {
      rows.push({ key: 'required-sources', label: '需要数据', value: requiredSources })
    }
    const missingSources = resolveSourceNames(dependencies.missing_sources)
    if (missingSources) {
      rows.push({ key: 'missing-sources', label: '缺失数据', value: missingSources })
    }
    const gapReason = normalizeEvidenceText(dependencies.data_gap_reason, 120)
    if (gapReason) rows.push({ key: 'data-gap-reason', label: '缺口说明', value: gapReason })
    const coverage = normalizeEvidenceText(dependencies.source_coverage_level, 32)
    if (coverage) {
      const coverageMap: Record<string, string> = {
        full: '数据完整',
        partial: '部分覆盖',
        missing: '缺少关键数据',
        unknown: '未标注',
      }
      rows.push({
        key: 'coverage',
        label: '覆盖程度',
        value: coverageMap[coverage] || coverage,
      })
    }
    return rows.length
      ? rows
      : [
          {
            key: 'dependency-empty',
            label: '依赖数据',
            value: '暂无可展示的数据依赖',
          },
        ]
  }

  function resolveEvidenceChainItems(
    item: Partial<SichuanBatchIssueItem>,
    quoteLimit = 260,
  ): EvidenceDisplayItem[] {
    const evidenceItems = toRecordList(item.evidence_items)
      .map((evidence, index) => {
        const source =
          normalizeEvidenceText(evidence.source_document_name, 40) ||
          normalizeEvidenceText(evidence.source_document_type, 40) ||
          normalizeEvidenceText(evidence.source_table, 40) ||
          '质控依据'
        return {
          key: normalizeEvidenceText(evidence.evidence_id, 24) || `evidence-${index}`,
          source,
          recordTime: normalizeEvidenceText(evidence.record_time, 32),
          fieldPath: normalizeCustomerEvidenceLabel(evidence.field_path),
          quote: normalizeEvidenceText(
            resolveCustomerEvidenceText(String(evidence.quote || '')),
            quoteLimit,
          ),
        }
      })
      .filter((item) => item.quote)
    const richEvidenceText = resolveRichCustomerEvidenceText(item)
    if (richEvidenceText) {
      const currentQuoteText = evidenceItems.map((evidence) => evidence.quote).join(' ')
      const shouldPrepend =
        richEvidenceText.length > 36 &&
        richEvidenceText.length > currentQuoteText.length + 16 &&
        !currentQuoteText.includes(richEvidenceText.slice(0, 24))
      if (shouldPrepend) {
        return [
          {
            key: 'customer-evidence-summary',
            source: '质控结果',
            recordTime: '',
            fieldPath: '关键证据',
            quote: normalizeEvidenceText(richEvidenceText, Math.max(quoteLimit, 320)),
          },
          ...evidenceItems,
        ]
      }
    }
    return evidenceItems
  }

  function formatEvidenceSummaryItem(evidence: EvidenceDisplayItem) {
    if (evidence.source === '质控结果' && evidence.fieldPath === '关键证据') {
      return evidence.quote
    }
    if (evidence.source === '质控结果') {
      return evidence.fieldPath ? `${evidence.fieldPath}：${evidence.quote}` : evidence.quote
    }
    const source = [evidence.source, evidence.fieldPath].filter(Boolean).join(' · ')
    return source ? `${source}：${evidence.quote}` : evidence.quote
  }

  function isCopyRule(item: Partial<SichuanBatchIssueItem>) {
    const ruleText = [item.rule_code, item.rule_id, item.rule_name, item.findings, item.evidence]
      .filter(Boolean)
      .join(' ')
    return /LX0609-0?1[67]|复制|重复|完全相同|相似度/.test(ruleText)
  }

  function evidenceRoleText(evidence: Record<string, unknown>) {
    return [
      evidence.source_document_name,
      evidence.source_document_type,
      evidence.source_field,
      evidence.field_path,
      evidence.evidence_role,
    ]
      .map((value) => String(value || '').trim())
      .filter(Boolean)
      .join(' ')
  }

  function normalizeCopyEvidenceSourceLabel(value: unknown) {
    const text = normalizeEvidenceText(value, 32)
    const mapping: Record<string, string> = {
      daily_course_record: '日常病程记录',
      senior_course_record: '上级医师查房记录',
      first_course_record: '首次病程记录',
      admission_record: '入院记录',
      copy_compare: '复制病历比对',
    }
    return mapping[text] || text
  }

  function resolveCopyEvidenceCompare(
    item: Partial<SichuanBatchIssueItem>,
  ): CopyEvidenceCompare | null {
    if (!isCopyRule(item)) return null
    const evidenceRows = toRecordList(item.evidence_items)
      .map((evidence, index) => {
        const quote = normalizeEvidenceText(evidence.quote, 180)
        if (!quote) return null
        const roleText = evidenceRoleText(evidence)
        const source =
          normalizeCopyEvidenceSourceLabel(evidence.source_document_name) ||
          normalizeCopyEvidenceSourceLabel(evidence.source_document_type) ||
          `文书片段 ${index + 1}`
        return {
          quote,
          roleText,
          source,
          evidenceId: normalizeEvidenceText(evidence.evidence_id, 32),
          actualValue: normalizeEvidenceText(evidence.actual_value, 64),
        }
      })
      .filter(
        (
          row,
        ): row is {
          quote: string
          roleText: string
          source: string
          evidenceId: string
          actualValue: string
        } => Boolean(row),
      )

    const metricEvidence = evidenceRows.find((row) =>
      /COPY-METRIC|复制病历比对指标|重复度判定|相似度|覆盖率/.test(
        [row.evidenceId, row.roleText, row.source, row.quote].join(' '),
      ),
    )
    const metric = metricEvidence?.quote
    const differenceEvidence = evidenceRows.find((row) =>
      /COPY-MISSING-DIFFERENCE|差异不足|缺少差异|新增内容|病情变化/.test(
        [row.evidenceId, row.roleText, row.source, row.quote].join(' '),
      ),
    )
    const differenceGap = differenceEvidence?.quote
    const pairMap = new Map<
      string,
      {
        index: number
        previous?: (typeof evidenceRows)[number]
        current?: (typeof evidenceRows)[number]
      }
    >()
    evidenceRows.forEach((row) => {
      const match = row.evidenceId.match(/^COPY-PAIR-(\d+)-(PREVIOUS|CURRENT)$/)
      if (!match) return
      const key = match[1] || ''
      const existing = pairMap.get(key) || { index: Number(key) || pairMap.size + 1 }
      if (match[2] === 'PREVIOUS') {
        existing.previous = row
      } else {
        existing.current = row
      }
      pairMap.set(key, existing)
    })
    const pairs = Array.from(pairMap.values())
      .filter((pair) => pair.previous?.quote && pair.current?.quote)
      .sort((a, b) => a.index - b.index)
      .map((pair) => ({
        key: `copy-pair-${pair.index}`,
        index: pair.index,
        leftLabel: pair.previous?.source || `前次记录片段 ${pair.index}`,
        leftQuote: pair.previous?.quote || '',
        rightLabel: pair.current?.source || `本次记录片段 ${pair.index}`,
        rightQuote: pair.current?.quote || '',
        similarity: pair.current?.actualValue || pair.previous?.actualValue || '',
      }))
    const legacyNotice = pairs.length
      ? ''
      : '当前任务结果只保存了单组对照片段。请重新发起质控，生成多片段对照、相似度指标和差异不足说明。'
    const admissionEvidence = evidenceRows.find((row) =>
      /入院记录|admission|source|原文/.test(row.roleText),
    )
    const courseEvidence = evidenceRows.find((row) =>
      /首次病程|日常病程|病程记录|course|target|对比/.test(row.roleText),
    )
    if (admissionEvidence && courseEvidence) {
      return {
        left: {
          label: admissionEvidence.source || '入院记录片段',
          quote: admissionEvidence.quote,
        },
        right: {
          label: courseEvidence.source || '病程记录片段',
          quote: courseEvidence.quote,
        },
        pairs,
        metric,
        differenceGap,
        legacyNotice,
      }
    }

    const customerEvidence =
      typeof item.evidence === 'string' ? resolveCustomerEvidenceText(item.evidence) : ''
    const parts = customerEvidence
      .split(/[；;]/)
      .map((part) => part.trim())
      .filter((part) => part.length >= 8)
    if (parts.length >= 3) {
      return {
        left: {
          label: '入院记录/首次病程片段',
          quote: truncateText(parts[1], 180),
        },
        right: {
          label: '病程记录片段',
          quote: truncateText(parts[2], 180),
        },
        pairs,
        metric,
        differenceGap,
        legacyNotice,
      }
    }
    const snippetRows = evidenceRows.filter(
      (row) =>
        row.evidenceId !== 'COPY-METRIC' &&
        row.evidenceId !== 'COPY-MISSING-DIFFERENCE' &&
        !/^COPY-PAIR-\d+-(PREVIOUS|CURRENT)$/.test(row.evidenceId),
    )
    if (snippetRows.length >= 2) {
      return {
        left: {
          label: snippetRows[0].source,
          quote: snippetRows[0].quote,
        },
        right: {
          label: snippetRows[1].source,
          quote: snippetRows[1].quote,
        },
        pairs,
        metric,
        differenceGap,
        legacyNotice,
      }
    }
    if (pairs.length) {
      return {
        left: {
          label: pairs[0].leftLabel,
          quote: pairs[0].leftQuote,
        },
        right: {
          label: pairs[0].rightLabel,
          quote: pairs[0].rightQuote,
        },
        pairs,
        metric,
        differenceGap,
        legacyNotice,
      }
    }
    return null
  }

  function resolveIssueEvidenceSummary(item: Partial<SichuanBatchIssueItem>) {
    const safeEvidenceText = resolveLuxianSafeEvidenceText(item)
    if (safeEvidenceText) return truncateText(safeEvidenceText, 180)
    const status = resolveIssueCanonicalStatus(item)
    if (status === 'data_gap') {
      const missingSources = resolveSourceNames(toRecord(item.dependencies)?.missing_sources)
      if (missingSources) {
        return truncateText(
          `已识别相关触发事实，但缺少${normalizeCustomerDataGapText(missingSources)}，需补齐后再自动判定。`,
          140,
        )
      }
      const dataGapText = resolveEvidenceDataGapText(resolveLegacyEvidenceText(item.evidence))
      if (dataGapText) {
        return truncateText(
          `已识别相关触发事实，但缺少${normalizeCustomerDataGapText(dataGapText)}，需补齐后再自动判定。`,
          140,
        )
      }
    }
    const evidences = resolveEvidenceChainItems(item)
    if (evidences.length) {
      const richEvidenceText = resolveRichCustomerEvidenceText(item)
      const evidenceSummaryText = evidences.slice(0, 2).map(formatEvidenceSummaryItem).join('；')
      if (richEvidenceText && richEvidenceText.length > evidenceSummaryText.length + 16) {
        return truncateText(richEvidenceText, 180)
      }
      return truncateText(evidences.slice(0, 2).map(formatEvidenceSummaryItem).join('；'), 180)
    }
    const triggerFact = resolveTriggerFacts(item)[0]
    if (triggerFact?.value) {
      return truncateText(`${triggerFact.label}：${triggerFact.value}`, 118)
    }
    const decision = resolveDecisionRows(item).find((row) => row.key === 'decision-summary')
    if (decision?.value) {
      return truncateText(decision.value, 118)
    }
    return truncateText(resolveCustomerEvidenceText(resolveLegacyEvidenceText(item.evidence)), 140)
  }

  function resolveIssueEvidenceSummaryParts(item: Partial<SichuanBatchIssueItem>) {
    const evidenceCandidates = [
      resolveLuxianSafeEvidenceText(item),
      resolveRichCustomerEvidenceText(item),
      resolveEvidenceChainItems(item).slice(0, 2).map(formatEvidenceSummaryItem).join('；'),
      resolveCustomerEvidenceText(resolveLegacyEvidenceText(item.evidence)),
      resolveIssueEvidenceSummary(item),
    ].filter(Boolean)
    for (const evidenceText of evidenceCandidates) {
      const parts = parseEvidenceSummaryParts(evidenceText)
      if (parts.length >= 2) return parts
    }
    return []
  }

  function resolveDecisionRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
    const decision = toRecord(item.decision)
    if (!decision) return []
    const rows: EvidenceDisplayRow[] = [
      {
        key: 'decision-summary',
        label: '判断摘要',
        value: normalizeEvidenceText(decision.decision_summary, 160),
      },
      {
        key: 'threshold',
        label: '判断阈值',
        value: normalizeEvidenceText(decision.threshold, 120),
      },
      {
        key: 'expected',
        label: '期望值',
        value: normalizeEvidenceText(decision.expected_value, 120),
      },
      {
        key: 'actual',
        label: '实际值',
        value: normalizeEvidenceText(decision.actual_value, 120),
      },
      {
        key: 'delta',
        label: '差值',
        value: normalizeEvidenceText(decision.delta, 80),
      },
      {
        key: 'suggestion',
        label: '处理建议',
        value: normalizeEvidenceText(decision.suggestion, 160),
      },
    ]
    return rows.filter((row) => row.value)
  }

  function resolveReviewRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
    const review = toRecord(item.review)
    if (!review) return []
    const reviewStatus = normalizeEvidenceText(review.review_status, 32)
    const statusMap: Record<string, string> = {
      pending: '待确认',
      not_required: '无需复核',
      reviewed: '已复核',
    }
    const rows: EvidenceDisplayRow[] = []
    if (reviewStatus) {
      rows.push({
        key: 'review-status',
        label: '复核状态',
        value: statusMap[reviewStatus] || reviewStatus,
      })
    }
    const finalStatus = normalizeEvidenceText(review.final_status, 32)
    if (finalStatus) rows.push({ key: 'final-status', label: '最终状态', value: finalStatus })
    const comment = normalizeEvidenceText(review.review_comment, 140)
    if (comment) rows.push({ key: 'review-comment', label: '复核意见', value: comment })
    return rows
  }

  function resolveAuditRows(item: Partial<SichuanBatchIssueItem>): EvidenceDisplayRow[] {
    const audit = toRecord(item.audit)
    if (!audit) return []
    const rows: EvidenceDisplayRow[] = [
      { key: 'visit-id', label: '住院号', value: normalizeEvidenceText(audit.visit_id, 48) },
      ...(isLuxianNativeSliceBatchJob.value
        ? []
        : [
            {
              key: 'model-name',
              label: '执行方式',
              value: normalizeEvidenceText(audit.model_name, 80),
            },
          ]),
      {
        key: 'executed-at',
        label: '执行时间',
        value: normalizeEvidenceText(audit.executed_at, 48),
      },
      { key: 'elapsed', label: '耗时', value: normalizeEvidenceText(audit.elapsed_ms, 32) },
      {
        key: 'technical-status',
        label: '技术状态',
        value: normalizeEvidenceText(audit.technical_status, 40),
      },
    ]
    return rows.filter((row) => row.value)
  }

  type StructuredTextSection = {
    title: string
    paragraphs: string[]
    points: string[]
  }

  function resolveStructuredText(text?: string | null) {
    const raw = String(text || '')
      .replace(/\r\n/g, '\n')
      .replace(/\u00a0/g, ' ')
      .trim()
    if (!raw) {
      return {
        summary: [] as string[],
        sections: [] as StructuredTextSection[],
        points: [] as string[],
      }
    }

    const prepared = raw
      .replace(/(【[^】]{1,40}】)/g, '\n$1\n')
      .replace(/(\*\*[^*]{1,60}\*\*[：:]?)/g, '\n$1\n')
      .replace(/(^|[。；;：:]\s*)(\d+[.、]\s*)/g, '$1\n$2')

    const lines = prepared
      .split('\n')
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter(Boolean)

    const summary: string[] = []
    const sections: StructuredTextSection[] = []
    const rootPoints: string[] = []
    let currentSection: StructuredTextSection | null = null

    const pushParagraph = (target: StructuredTextSection | null, value: string) => {
      const normalized = value.trim()
      if (!normalized) return
      if (target) {
        target.paragraphs.push(normalized)
      } else {
        summary.push(normalized)
      }
    }

    const createSection = (title: string, trailingContent = '') => {
      currentSection = {
        title: title.replace(/[：:]+$/g, '').trim(),
        paragraphs: [],
        points: [],
      }
      sections.push(currentSection)
      if (trailingContent.trim()) {
        currentSection.paragraphs.push(trailingContent.trim())
      }
    }

    lines.forEach((line) => {
      const markdownHeading = line.match(/^\*\*([^*]{1,80})\*\*[：:]?\s*(.*)$/)
      if (markdownHeading) {
        createSection(markdownHeading[1], markdownHeading[2] || '')
        return
      }

      const bracketHeading = line.match(/^【([^】]{1,80})】\s*(.*)$/)
      if (bracketHeading) {
        createSection(bracketHeading[1], bracketHeading[2] || '')
        return
      }

      const shortHeading = line.match(/^([^，。；;：:\s]{2,24})[：:]\s*(.+)$/)
      if (shortHeading && shortHeading[1].length <= 18) {
        createSection(shortHeading[1], shortHeading[2] || '')
        return
      }

      const numberedPoint = line.match(/^\d+[.、]\s*(.+)$/)
      if (numberedPoint) {
        if (currentSection) {
          currentSection.points.push(numberedPoint[1].trim())
        } else {
          rootPoints.push(numberedPoint[1].trim())
        }
        return
      }

      pushParagraph(currentSection, line)
    })

    return { summary, sections, points: rootPoints }
  }

  function hasStructuredText(text?: string | null) {
    const structured = resolveStructuredText(text)
    return Boolean(
      structured.summary.length || structured.sections.length || structured.points.length,
    )
  }

  return {
    formatEvidenceSummaryItem,
    hasEvidenceChain,
    hasStructuredText,
    isGenericCustomerEvidenceText,
    isSafeEvidenceRef,
    resolveAuditRows,
    resolveCopyEvidenceCompare,
    resolveCustomerEvidenceText,
    resolveDecisionRows,
    resolveDependencyRows,
    resolveEvidenceChainItems,
    resolveEvidenceStatusText,
    resolveExecutorTypeText,
    resolveIssueCardClass,
    resolveIssueEvidenceSummary,
    resolveIssueEvidenceSummaryParts,
    resolveIssueResultKindClass,
    resolveIssueResultKindText,
    resolveIssueSeverityText,
    resolveLegacyEvidenceText,
    resolveLuxianEvidenceSourceLabel,
    resolveLuxianReasonCodeText,
    resolveLuxianSafeEvidenceText,
    resolveMissingSources,
    resolveReviewRows,
    resolveStructuredText,
    resolveTriggerFacts,
    sanitizeCustomerVisibleText,
  }
}
