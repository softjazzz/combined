import { computed, h, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type {
  QCRecordCompareIssue,
  SichuanBatchIssueItem,
  SichuanBatchJobDebugSnapshot,
  SichuanBatchJobResultTrace,
  SichuanBatchJob,
  SichuanBatchResultAggregation,
  Luxian0609ReviewFinding,
  Luxian0609ReviewReport,
} from '@/views/workstation-v4/semantic-rules/types'
import {
  evaluateSichuanRuleForVisit,
  getSichuanWorkspaceBatchJobResultTrace,
} from '@/services/sichuan-rule-workspace-service'
import type {
  StructuredQCFilterState,
  StructuredQCIssue,
  StructuredQCStatus,
} from '@/views/workstation-v4/types'
import {
  createDefaultStructuredQCFilter,
  filterStructuredQCIssues,
  mapBatchJobToStructuredQC,
} from '@/views/workstation-v4/utils/structuredQc'
import { isBatchJobCancelable } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'
import BatchResultOverview from '@/views/workstation-v4/semantic-rules/components/BatchResultOverview.vue'
import BatchResultTraceModal from '@/views/workstation-v4/semantic-rules/components/BatchResultTraceModal.vue'
import CustomerQcResultDetailCard from '@/views/workstation-v4/semantic-rules/components/CustomerQcResultDetailCard.vue'
import QCRecordCompareWorkbench from '@/views/workstation-v4/semantic-rules/components/QCRecordCompareWorkbench.vue'
import { buildCustomerQcDisplayModel } from '@/views/workstation-v4/semantic-rules/customer-qc-display-model'
import { normalizeCustomerQcResult } from '@/domain/customer-qc/result-normalizer'
import { resolveIssueCanonicalStatus } from '@/views/workstation-v4/semantic-rules/batchResultStatus'
import { createIssueEvidencePresentation } from '@/views/workstation-v4/semantic-rules/issueEvidencePresentation'
import { buildRecommendationEvidence } from '@/views/workstation-v4/semantic-rules/record-comparison-model'

export type SemanticRulesBatchResultDrawerProps = {
  open: boolean
  batchJobDetail: SichuanBatchJob | null
  batchJobDebugSnapshot?: SichuanBatchJobDebugSnapshot | null
  batchJobDebugLoading?: boolean
  fetchBatchJobDebugSnapshot?: (
    jobId: string,
    options?: { ruleJobId?: string; itemLimit?: number },
  ) => Promise<SichuanBatchJobDebugSnapshot | null>
  batchJobDetailLoading: boolean
  close: () => void
  exportBatchJobReport: (format?: 'xlsx' | 'csv' | 'html') => void
  reviewBatchJobResult?: () => Promise<void> | void
  reviewBatchJobLoading?: boolean
  cancelBatchJob?: (jobId: string) => Promise<void> | void
  cancelBatchJobLoading?: boolean
  getBatchJobStatusTagClass: (status?: string) => string
  getBatchJobStatusText: (status?: string) => string
  formatDateTime: (value?: string | Date | null) => string
  focusVisitId?: string
  focusInstituteId?: string
  focusPatientId?: string
  focusRecordId?: string
  focusRecordRef?: string
  focusRecordLabel?: string
  enableRecordComparison?: boolean
  defaultRecordComparison?: boolean
}

export function useSemanticRulesBatchResultDrawerController(
  props: Readonly<SemanticRulesBatchResultDrawerProps>,
) {
  type BatchJobExportFormat = 'xlsx' | 'csv' | 'html'

  function handleExportMenuClick(event: { key?: unknown }) {
    const format = String(event?.key || 'html') as BatchJobExportFormat
    props.exportBatchJobReport(['xlsx', 'csv', 'html'].includes(format) ? format : 'html')
  }

  async function handleReviewBatchJobResult() {
    if (!props.reviewBatchJobResult) {
      message.warning('当前页面暂未接入复核功能')
      return
    }
    await props.reviewBatchJobResult()
  }

  const PROGRESS_STEP_LABEL_MAP: Record<string, string> = {
    queued: '排队中',
    prepare: '收集病历与装配证据',
    filter: '病历筛选完成，准备执行规则',
    run: '正在执行质控规则',
    aggregate: '正在汇总结果',
    completed: '已完成',
    failed: '执行失败',
    canceled: '已取消',
  }

  const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
  const LUXIAN_0609_NATIVE_RULE_IDS = new Set(['LX0609-029', 'LX0609-030', 'LX0609-032'])
  const LUXIAN_0609_FOCUS_STATUSES: StructuredQCStatus[] = [
    'non_compliant',
    'ai_suggested_non_compliant',
    'uncertain',
    'data_gap',
    'not_executed',
    'technical_error',
    'failed',
  ]
  const LUXIAN_0609_STATUS_ORDER = [
    'non_compliant',
    'ai_suggested_non_compliant',
    'compliant',
    'ai_suggested_compliant',
    'not_applicable',
    'data_gap',
    'uncertain',
    'not_executed',
    'technical_error',
  ]
  const ISSUE_RESULT_DISPLAY_STATUS_ORDER = [
    'non_compliant',
    'ai_suggested_non_compliant',
    'technical_error',
    'data_gap',
    'uncertain',
    'not_executed',
    'not_applicable',
    'ai_suggested_compliant',
    'compliant',
  ]
  const ALL_RECORDS_KEY = '__all_records__'

  interface IssueRecordGroup<T extends SichuanBatchIssueItem = SichuanBatchIssueItem> {
    key: string
    label: string
    meta: string
    total: number
    nonCompliant: number
    dataGap: number
    uncertain: number
    technicalError: number
    items: T[]
  }

  function normalizeStringList(value: unknown): string[] {
    if (!Array.isArray(value)) return []
    const seen = new Set<string>()
    const result: string[] = []
    value.forEach((item) => {
      const normalized = String(item || '').trim()
      if (!normalized || seen.has(normalized)) return
      seen.add(normalized)
      result.push(normalized)
    })
    return result
  }

  function optionalNumber(value: unknown): number | null {
    if (value === null || value === undefined || value === '') return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }

  function formatTokenNumber(value: unknown): string {
    const parsed = optionalNumber(value)
    if (parsed === null) return '-'
    return Math.round(parsed).toLocaleString('zh-CN')
  }

  function parseBackendDateTimeMs(value?: string | Date | null): number {
    if (!value) return 0
    if (value instanceof Date) {
      const timestamp = value.getTime()
      return Number.isFinite(timestamp) ? timestamp : 0
    }
    const text = String(value).trim()
    if (!text) return 0
    const normalized = text.includes('T') ? text : text.replace(' ', 'T')
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
    const timestamp = Date.parse(hasTimezone ? normalized : `${normalized}Z`)
    return Number.isFinite(timestamp) ? timestamp : 0
  }

  const liveNow = ref(Date.now())
  let liveTicker: ReturnType<typeof setInterval> | null = null

  const issueViewMode = ref<'business' | 'advanced' | 'compare'>('business')
  const showAllStatuses = ref(false)
  const issueFilter = ref<StructuredQCFilterState>(createDefaultStructuredQCFilter())
  const advancedSectionKeys = ref<string[]>([])
  const normalizedFocusVisitId = computed(() => String(props.focusVisitId || '').trim())
  const normalizedFocusRecordId = computed(() => String(props.focusRecordId || '').trim())
  const normalizedFocusRecordRef = computed(() => String(props.focusRecordRef || '').trim())
  const cancelBatchJobLoading = computed(() => props.cancelBatchJobLoading === true)
  const canCancelBatchJob = computed(
    () =>
      Boolean(props.cancelBatchJob) &&
      Boolean(props.batchJobDetail?.id) &&
      isBatchJobCancelable(props.batchJobDetail?.status),
  )
  const batchJobFilters = computed<Record<string, unknown>>(() => {
    const filters = props.batchJobDetail?.filters
    return filters && typeof filters === 'object' ? filters : {}
  })
  const isLuxian0609BatchJob = computed(() => {
    const detail = props.batchJobDetail
    const summary = detail?.summary
    const filters = batchJobFilters.value
    return (
      String(detail?.rule_set_key || summary?.rule_set_key || filters.rule_set_key || '')
        .trim()
        .toLowerCase() === LUXIAN_0609_RULE_SET_KEY
    )
  })
  const isFocusedRecordMode = computed(
    () =>
      !!(
        normalizedFocusVisitId.value ||
        normalizedFocusRecordId.value ||
        normalizedFocusRecordRef.value
      ),
  )

  function confirmCancelBatchJob() {
    const jobId = String(props.batchJobDetail?.id || '').trim()
    if (!jobId || !props.cancelBatchJob) return
    Modal.confirm({
      title: '停止质控任务',
      content: '确定停止当前质控任务？已完成结果将保留，未完成规则不再继续执行。',
      okText: '停止任务',
      okType: 'danger',
      cancelText: '继续等待',
      async onOk() {
        try {
          await props.cancelBatchJob?.(jobId)
        } catch (error) {
          const text = error instanceof Error ? error.message : ''
          message.error(text || '停止任务失败')
          throw error
        }
      },
    })
  }

  function matchesFocusedRecord(
    item: Pick<SichuanBatchIssueItem, 'visit_id' | 'record_id' | 'record_ref'> | StructuredQCIssue,
  ) {
    if (!isFocusedRecordMode.value) return true
    const candidateVisitId =
      'visitId' in item ? String(item.visitId || '').trim() : String(item.visit_id || '').trim()
    const candidateRecordId =
      'recordId' in item ? String(item.recordId || '').trim() : String(item.record_id || '').trim()
    const candidateRecordRef =
      'recordRef' in item
        ? String(item.recordRef || '').trim()
        : 'record_ref' in item
          ? String(item.record_ref || '').trim()
          : ''
    if (normalizedFocusRecordRef.value && candidateRecordRef === normalizedFocusRecordRef.value)
      return true
    if (
      !normalizedFocusRecordRef.value &&
      candidateRecordRef &&
      !candidateVisitId &&
      !candidateRecordId
    ) {
      return true
    }
    if (normalizedFocusVisitId.value && candidateVisitId === normalizedFocusVisitId.value)
      return true
    if (normalizedFocusVisitId.value && candidateRecordId === normalizedFocusVisitId.value)
      return true
    if (normalizedFocusRecordId.value && candidateRecordId === normalizedFocusRecordId.value)
      return true
    return false
  }

  const ruleColumns = computed(() => [
    { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 120 },
    { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 220 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 110 },
    { title: '命中问题', dataIndex: 'issue_records', key: 'issue_records', width: 100 },
    { title: '成功', dataIndex: 'success_count', key: 'success_count', width: 90 },
    { title: '失败', dataIndex: 'failed_count', key: 'failed_count', width: 90 },
  ])

  const issueColumns = computed(() => {
    const columns: Array<Record<string, any>> = [
      { title: '规则编码', dataIndex: 'rule_code', key: 'rule_code', width: 96 },
      {
        title: isLuxian0609BatchJob.value ? '病历引用' : '病历号',
        dataIndex: isLuxian0609BatchJob.value ? 'record_ref' : 'record_id',
        key: isLuxian0609BatchJob.value ? 'record_ref' : 'record_id',
        width: 120,
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 92,
        customRender: ({ text, record }: { text?: string; record: SichuanBatchIssueItem }) =>
          resolveDisplayStatusText(record) || resolveStatusText(text),
      },
      {
        title: '质控结论',
        dataIndex: 'findings',
        key: 'findings',
        width: 320,
        customRender: ({ text }: { text?: string }) =>
          h(
            'span',
            { title: sanitizeCustomerVisibleText(text) },
            truncateText(sanitizeCustomerVisibleText(text), 80),
          ),
      },
      {
        title: '证据摘要',
        dataIndex: 'evidence',
        key: 'evidence',
        width: 280,
        customRender: ({ text }: { text?: string }) =>
          h(
            'span',
            { title: resolveCustomerEvidenceText(text) },
            truncateText(resolveCustomerEvidenceText(text), 72),
          ),
      },
      {
        title: '整改建议',
        dataIndex: 'suggestion',
        key: 'suggestion',
        width: 260,
        customRender: ({ text }: { text?: string }) =>
          h(
            'span',
            { title: sanitizeCustomerVisibleText(text) },
            truncateText(sanitizeCustomerVisibleText(text), 68),
          ),
      },
      {
        title: '文书域',
        dataIndex: 'target_document_type',
        key: 'target_document_type',
        width: 108,
        customRender: ({ record }: { record: SichuanBatchIssueItem }) =>
          record.target_document_type || record.document_type || '-',
      },
      { title: '规则域', dataIndex: 'execution_domain', key: 'execution_domain', width: 112 },
      { title: '规则族', dataIndex: 'rule_family', key: 'rule_family', width: 128 },
      { title: '缺陷等级', dataIndex: 'defect_level', key: 'defect_level', width: 110 },
      {
        title: '精审',
        dataIndex: 'refined',
        key: 'refined',
        width: 72,
        customRender: ({ text }: { text?: boolean }) => (text ? '是' : '否'),
      },
      {
        title: '置信度',
        dataIndex: 'confidence',
        key: 'confidence',
        width: 88,
        customRender: ({ text }: { text?: number }) => Number(text || 0).toFixed(2),
      },
    ]
    if (issueViewMode.value === 'advanced') {
      columns.push(
        { title: '执行器', dataIndex: 'executor_type', key: 'executor_type', width: 84 },
        { title: '规则版本', dataIndex: 'rule_version', key: 'rule_version', width: 112 },
      )
      if (!isLuxianNativeSliceBatchJob.value) {
        columns.push(
          { title: 'Prompt版本', dataIndex: 'prompt_version', key: 'prompt_version', width: 120 },
          { title: '模型版本', dataIndex: 'model_version', key: 'model_version', width: 120 },
        )
      }
      columns.push(
        { title: '证据来源', dataIndex: 'evidence_source', key: 'evidence_source', width: 110 },
        { title: 'trace_id', dataIndex: 'trace_id', key: 'trace_id', width: 140 },
        {
          title: 'cache_hit',
          dataIndex: 'cache_hit',
          key: 'cache_hit',
          width: 90,
          customRender: ({ text }: { text?: boolean | null }) =>
            text === null || text === undefined ? '-' : text ? 'true' : 'false',
        },
      )
    }
    return columns
  })

  const resolvedRuleResults = computed(() => {
    const ruleResults = props.batchJobDetail?.rule_results
    if (Array.isArray(ruleResults) && ruleResults.length > 0) {
      if (!isFocusedRecordMode.value) return ruleResults
      return ruleResults
        .map((ruleResult) => ({
          ...ruleResult,
          items: (ruleResult.items || []).filter((item) => matchesFocusedRecord(item)),
        }))
        .filter((ruleResult) => (ruleResult.items || []).length > 0)
    }
    return []
  })

  const canonicalLuxianIssueSourceItems = computed<SichuanBatchIssueItem[]>(() => {
    const topLevelItems = props.batchJobDetail?.items || []
    if (topLevelItems.length > 0) {
      if (!isFocusedRecordMode.value) return topLevelItems
      return topLevelItems.filter((item) => matchesFocusedRecord(item))
    }
    const seen = new Set<string>()
    return resolvedRuleResults.value
      .flatMap((ruleResult) => ruleResult.items || [])
      .filter((item) => {
        const key = [
          item.record_ref || item.record_id || item.visit_id || '',
          item.rule_id || item.rule_code || '',
          resolveIssueCanonicalStatus(item),
          item.reason_code || '',
        ].join('|')
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
  })

  const transfusionDocumentationSummary = computed(() => {
    if (!isLuxian0609BatchJob.value || !isFocusedRecordMode.value) return null

    const definitions = [
      { ruleId: 'LX0609-044', label: '输血前评估' },
      { ruleId: 'LX0609-045', label: '输血病程' },
      { ruleId: 'LX0609-047', label: '输血后评价' },
    ]
    const sourceItems = canonicalLuxianIssueSourceItems.value
    const entries = definitions.map((definition) => {
      const item = sourceItems.find(
        (candidate) =>
          String(candidate.rule_id || candidate.rule_code || '').trim() === definition.ruleId,
      )
      const status = item ? resolveIssueCanonicalStatus(item) : ''
      return {
        ...definition,
        status,
        statusText: item
          ? resolveDisplayStatusText(item) || resolveStatusText(status)
          : '未返回结果',
      }
    })
    if (!entries.some((entry) => entry.status)) return null

    const incompleteEntries = entries.filter((entry) => entry.status !== 'compliant')
    return {
      complete: incompleteEntries.length === 0,
      entries,
      summaryText:
        incompleteEntries.length === 0
          ? '输血前评估、输血病程、输血后评价已齐备'
          : '尚未齐备：' +
            incompleteEntries.map((entry) => entry.label + '：' + entry.statusText).join('；'),
    }
  })

  const selectedClusterKey = ref('')
  const selectedDebugRuleJobId = ref('')
  const selectedIssueRecordKey = ref(ALL_RECORDS_KEY)
  const selectedBusinessIssueKey = ref('')
  const issuePagination = reactive({
    current: 1,
    pageSize: 8,
    showSizeChanger: false,
  })
  const expandedIssueKeys = ref<string[]>([])
  const deepReviewModalOpen = ref(false)
  const selectedDeepReviewIssue = ref<SichuanBatchIssueItem | null>(null)
  const deepReviewLoading = ref(false)
  const deepReviewError = ref('')
  const deepReviewResult = ref<Record<string, unknown> | null>(null)
  const resultTraceModalOpen = ref(false)
  const resultTraceLoading = ref(false)
  const resultTraceError = ref('')
  const resultTraceData = ref<SichuanBatchJobResultTrace | null>(null)

  const batchJobDebugSnapshot = computed(() => props.batchJobDebugSnapshot || null)
  const canShowResultTrace = computed(() => issueViewMode.value === 'advanced')

  type ResultTraceRow = {
    key: string
    label: string
    value: string
  }

  type ResultTraceSection = {
    key: string
    title: string
    description: string
    badge?: string
    rows: ResultTraceRow[]
  }

  const resultTraceSections = computed<ResultTraceSection[]>(() => {
    const trace = resultTraceData.value
    if (!trace) return []
    return [
      {
        key: 'final_result',
        title: '最终客户点结果',
        description: '页面最终展示给客户的质控点结论和状态。',
        badge: stringifyTraceValue(
          trace.final_result?.status || trace.final_result?.display_status || '',
        ),
        rows: traceObjectRows(trace.final_result),
      },
      {
        key: 'aggregation_trace',
        title: '聚合与后处理',
        description: '用于判断状态是否被客户点聚合、规则保护或后处理改写。',
        rows: traceObjectRows(trace.aggregation_trace),
      },
      {
        key: 'decision',
        title: '门控、依赖与判定',
        description: '规则触发、依赖字段和判定过程的可展示诊断信息。',
        rows: [
          ...traceObjectRows(trace.trigger, '触发'),
          ...traceObjectRows(trace.dependencies, '依赖'),
          ...traceObjectRows(trace.decision, '判定'),
        ],
      },
      {
        key: 'source_execution_results',
        title: '底层执行线索',
        description: '底层规则或映射结果的脱敏摘要；如果为空，说明该任务未保存可展示的底层明细。',
        rows: traceListRows(trace.source_execution_results),
      },
      {
        key: 'safety',
        title: '安全过滤',
        description: '确认诊断追踪没有返回模型原始输出、完整病历正文或向量等敏感字段。',
        rows: traceObjectRows(trace.safety),
      },
    ]
  })

  const structuredResult = computed(() =>
    mapBatchJobToStructuredQC(props.batchJobDetail, batchJobDebugSnapshot.value),
  )

  const scopedStructuredIssues = computed<StructuredQCIssue[]>(() => {
    const issues = structuredResult.value.issues || []
    if (!isFocusedRecordMode.value) return issues
    return issues.filter((item) => matchesFocusedRecord(item))
  })

  const structuredIssues = computed<StructuredQCIssue[]>(() => {
    const defaultStatusList = isLuxian0609BatchJob.value
      ? LUXIAN_0609_FOCUS_STATUSES
      : (['non_compliant', 'uncertain'] satisfies StructuredQCStatus[])
    const baseFilter: StructuredQCFilterState = {
      ...issueFilter.value,
      statusList: showAllStatuses.value ? [] : defaultStatusList,
    }
    let list = filterStructuredQCIssues(scopedStructuredIssues.value, baseFilter)
    if (!showAllStatuses.value) {
      list = list.filter((item) => !item.internalOnly)
    }
    if (selectedDebugRuleJobId.value) {
      list = list.filter((item) => item.ruleJobId === selectedDebugRuleJobId.value)
    }
    return list
  })

  function resolveIssueSourceKey(
    issue: Pick<
      SichuanBatchIssueItem,
      'rule_job_id' | 'rule_id' | 'rule_code' | 'record_id' | 'visit_id'
    >,
  ) {
    return [
      issue.rule_job_id || '',
      issue.rule_id || issue.rule_code || '',
      issue.record_id || '',
      issue.visit_id || '',
    ].join('|')
  }

  const sourceIssueMap = computed(() => {
    const map = new Map<string, SichuanBatchIssueItem>()
    const nestedItems = resolvedRuleResults.value.flatMap((ruleResult) => ruleResult.items || [])
    ;[...(props.batchJobDetail?.items || []), ...nestedItems].forEach((item) => {
      map.set(resolveIssueSourceKey(item), item)
    })
    return map
  })

  function mapStructuredIssueToBatchIssueItem(item: StructuredQCIssue): SichuanBatchIssueItem {
    const sourceIssue =
      sourceIssueMap.value.get(
        resolveIssueSourceKey({
          rule_job_id: item.ruleJobId || undefined,
          rule_id: item.ruleId || item.ruleCode,
          rule_code: item.ruleCode || item.ruleId,
          record_id: item.recordId || '',
          visit_id: item.visitId || '',
        }),
      ) || ({} as Partial<SichuanBatchIssueItem>)
    return {
      ...sourceIssue,
      rule_job_id: item.ruleJobId || undefined,
      rule_id: item.ruleId || item.ruleCode,
      rule_code: item.ruleCode || item.ruleId,
      rule_name: item.ruleName,
      record_ref: sourceIssue.record_ref,
      reason_code: sourceIssue.reason_code,
      canonical_status: sourceIssue.canonical_status,
      record_id: item.recordId || '',
      visit_id: item.visitId || '',
      patient_name: item.patientName || '',
      department: item.department || '',
      status: item.status,
      is_compliant: item.status === 'compliant' || item.status === 'not_applicable',
      display_status: item.displayStatus || sourceIssue.display_status,
      display_bucket: item.displayBucket || sourceIssue.display_bucket,
      postprocess_label: item.postprocessLabel || sourceIssue.postprocess_label,
      postprocess_reason: item.postprocessReason || sourceIssue.postprocess_reason,
      evidence_problem_type: item.evidenceProblemType || sourceIssue.evidence_problem_type,
      can_show_as_defect: item.canShowAsDefect,
      can_show_to_doctor: item.canShowToDoctor,
      internal_only: item.internalOnly,
      postprocess_mode: item.postprocessMode || sourceIssue.postprocess_mode,
      first_pass_status: item.firstPassStatus || sourceIssue.first_pass_status,
      first_pass_display_status:
        item.firstPassDisplayStatus || sourceIssue.first_pass_display_status,
      adjudicated_display_status:
        item.adjudicatedDisplayStatus || sourceIssue.adjudicated_display_status,
      adjudicator_reason: item.adjudicatorReason || sourceIssue.adjudicator_reason,
      adjudicator_supporting_quote:
        item.adjudicatorSupportingQuote || sourceIssue.adjudicator_supporting_quote,
      adjudicator_confidence: item.adjudicatorConfidence || sourceIssue.adjudicator_confidence,
      rule_requirement_match: item.ruleRequirementMatch || sourceIssue.rule_requirement_match,
      findings: item.findings,
      evidence: item.evidence,
      suggestion: item.suggestion,
      confidence: item.confidence,
      executor_type: item.executorType,
      rule_version: item.metadata.ruleVersion,
      prompt_version: item.metadata.promptVersion,
      model_version: item.metadata.modelVersion,
      evidence_source: item.metadata.evidenceSource,
      cache_hit: item.metadata.cacheHit === null ? undefined : item.metadata.cacheHit,
      trace_id: item.metadata.traceId,
      cache_key: item.metadata.cacheKey,
      execution_domain: item.executionDomain,
      rule_family: item.ruleFamily,
      doc_scope: item.metadata.docScope,
      cost_class: item.metadata.costClass,
      document_type: item.documentType,
      defect_level: item.defectLevel,
      qc_point_id: item.qcPointId || sourceIssue.qc_point_id,
      rule_set_key: item.ruleSetKey || sourceIssue.rule_set_key,
      rule_set_version: item.ruleSetVersion || sourceIssue.rule_set_version,
      schema_version: item.schemaVersion || sourceIssue.schema_version,
      result_status: item.resultStatus || sourceIssue.result_status,
      trigger: item.trigger || sourceIssue.trigger,
      dependencies: item.dependencies || sourceIssue.dependencies,
      evidence_items:
        item.evidenceItems && item.evidenceItems.length > 0
          ? item.evidenceItems
          : sourceIssue.evidence_items,
      decision: item.decision || sourceIssue.decision,
      review: item.review || sourceIssue.review,
      audit: item.audit || sourceIssue.audit,
      llm_fallback: item.metadata.llmFallback === null ? undefined : item.metadata.llmFallback,
      refined: item.metadata.refined === null ? undefined : item.metadata.refined,
      refine_reason: item.metadata.refineReason,
      screening_status: item.metadata.screeningStatus,
      final_decision_source: item.metadata.finalDecisionSource,
    }
  }

  const issueItems = computed<SichuanBatchIssueItem[]>(() => {
    if (isLuxian0609BatchJob.value) {
      const keyword = String(issueFilter.value.keyword || '')
        .trim()
        .toLowerCase()
      return canonicalLuxianIssueSourceItems.value
        .filter((item) => showAllStatuses.value || item.internal_only !== true)
        .filter(
          (item) =>
            showAllStatuses.value ||
            LUXIAN_0609_FOCUS_STATUSES.includes(
              resolveIssueCanonicalStatus(item) as StructuredQCStatus,
            ),
        )
        .filter(
          (item) =>
            !issueFilter.value.documentType ||
            String(item.document_type || item.target_document_type || '') ===
              issueFilter.value.documentType,
        )
        .filter(
          (item) =>
            !issueFilter.value.executionDomain ||
            String(item.execution_domain || '') === issueFilter.value.executionDomain,
        )
        .filter(
          (item) =>
            !issueFilter.value.defectLevel ||
            String(item.defect_level || '') === issueFilter.value.defectLevel,
        )
        .filter((item) => {
          if (!keyword) return true
          return [
            item.rule_id,
            item.rule_code,
            item.rule_name,
            item.record_ref,
            item.findings,
            item.suggestion,
          ]
            .map((value) => String(value || '').toLowerCase())
            .some((value) => value.includes(keyword))
        })
    }
    const mapped = structuredIssues.value.map(mapStructuredIssueToBatchIssueItem)
    return mapped
  })

  const resolvedDeepReviewResult = computed(() => {
    if (!deepReviewResult.value) return null
    const evaluationResults = Array.isArray(deepReviewResult.value.evaluation_results)
      ? (deepReviewResult.value.evaluation_results as Array<Record<string, unknown>>)
      : []
    return evaluationResults[0] || deepReviewResult.value
  })

  const issueDocumentTypeOptions = computed(() => {
    const set = new Set<string>()
    scopedStructuredIssues.value.forEach((item) => {
      const value = String(item.documentType || '').trim()
      if (value) set.add(value)
    })
    return Array.from(set).map((value) => ({ label: value, value }))
  })

  const issueExecutionDomainOptions = computed(() => {
    const set = new Set<string>()
    scopedStructuredIssues.value.forEach((item) => {
      const value = String(item.executionDomain || '').trim()
      if (value) set.add(value)
    })
    return Array.from(set).map((value) => ({ label: value, value }))
  })

  const issueDefectLevelOptions = computed(() => {
    const set = new Set<string>()
    scopedStructuredIssues.value.forEach((item) => {
      const value = String(item.defectLevel || '').trim()
      if (value) set.add(value)
    })
    return Array.from(set).map((value) => ({ label: value, value }))
  })

  watch(
    () => props.batchJobDetail?.id,
    () => {
      selectedClusterKey.value = ''
      selectedDebugRuleJobId.value = ''
      selectedIssueRecordKey.value = ALL_RECORDS_KEY
      selectedBusinessIssueKey.value = ''
      issueViewMode.value = 'business'
      advancedSectionKeys.value = []
      expandedIssueKeys.value = []
      closeDeepReviewModal()
      resetIssueFilters()
    },
  )

  watch(
    () => [
      issueFilter.value.keyword,
      issueFilter.value.documentType,
      issueFilter.value.executionDomain,
      issueFilter.value.defectLevel,
      showAllStatuses.value,
      selectedDebugRuleJobId.value,
      selectedClusterKey.value,
      selectedIssueRecordKey.value,
      selectedBusinessIssueKey.value,
    ],
    () => {
      issuePagination.current = 1
    },
  )

  const resultAggregation = computed<SichuanBatchResultAggregation | null>(() => {
    return props.batchJobDetail?.summary?.result_aggregation || null
  })

  const topAggregationClusters = computed(() => {
    return (resultAggregation.value?.clusters || []).slice(0, 8)
  })

  const aggregationBreakdownSections = computed(() => {
    const aggregation = resultAggregation.value
    if (!aggregation) return []
    return [
      {
        key: 'rule',
        title: '按规则',
        total:
          aggregation.rule_breakdown?.reduce((sum, item) => sum + Number(item.hits || 0), 0) || 0,
        items: normalizeBreakdownItems(
          (aggregation.rule_breakdown || []).map((item) => ({
            label: item.rule_name || item.rule_id,
            count: Number(item.hits || 0),
          })),
        ),
      },
      {
        key: 'executor',
        title: '按执行器',
        total:
          aggregation.executor_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
          0,
        items: normalizeBreakdownItems(
          (aggregation.executor_breakdown || []).map((item) => ({
            label: resolveBreakdownLabel('executor', item.key),
            count: Number(item.count || 0),
          })),
        ),
      },
      {
        key: 'document',
        title: '按文书',
        total:
          aggregation.document_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
          0,
        items: normalizeBreakdownItems(
          (aggregation.document_breakdown || []).map((item) => ({
            label: resolveBreakdownLabel('document', item.key),
            count: Number(item.count || 0),
          })),
        ),
      },
      {
        key: 'status',
        title: '按状态',
        total:
          aggregation.status_breakdown?.reduce((sum, item) => sum + Number(item.count || 0), 0) ||
          0,
        items: normalizeBreakdownItems(
          (aggregation.status_breakdown || []).map((item) => ({
            label: resolveBreakdownLabel('status', item.key),
            count: Number(item.count || 0),
          })),
        ),
      },
      {
        key: 'defect',
        title: '按缺陷级别',
        total:
          aggregation.defect_level_breakdown?.reduce(
            (sum, item) => sum + Number(item.count || 0),
            0,
          ) || 0,
        items: normalizeBreakdownItems(
          (aggregation.defect_level_breakdown || []).map((item) => ({
            label: resolveBreakdownLabel('defect', item.key),
            count: Number(item.count || 0),
          })),
        ),
      },
    ]
  })

  const debugRuleOptions = computed(() => {
    return (batchJobDebugSnapshot.value?.rules || []).map((rule) => ({
      label: `${rule.rule_code} · ${rule.rule_name}`,
      value: rule.rule_job_id,
    }))
  })

  const currentDebugRule = computed(() => {
    const snapshot = batchJobDebugSnapshot.value
    if (!snapshot) return null
    if (selectedDebugRuleJobId.value) {
      return (
        (snapshot.rules || []).find((rule) => rule.rule_job_id === selectedDebugRuleJobId.value) ||
        null
      )
    }
    const currentRuleJobId = String(snapshot.current_rule?.rule_job_id || '').trim()
    if (currentRuleJobId) {
      const matched = (snapshot.rules || []).find((rule) => rule.rule_job_id === currentRuleJobId)
      if (matched) return matched
    }
    return (
      (snapshot.rules || []).find(
        (rule) => String(rule.status || '').toLowerCase() === 'running',
      ) ||
      snapshot.rules?.[0] ||
      null
    )
  })

  const debugProgressEntries = computed(() => {
    const progress =
      batchJobDebugSnapshot.value?.current_rule?.progress || currentDebugRule.value?.progress || {}
    return objectEntriesToCompactList(progress)
  })

  const debugDetailEntries = computed(() => {
    return objectEntriesToCompactList(currentDebugRule.value?.debug || {})
  })

  const activeRuleFilterLabel = computed(() => {
    if (!selectedDebugRuleJobId.value) return ''
    const matched = (batchJobDebugSnapshot.value?.rules || []).find(
      (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
    )
    if (!matched) return ''
    return `${matched.rule_code} · ${matched.rule_name}`
  })

  const selectedCluster = computed(() => {
    if (!selectedClusterKey.value) return null
    return (
      (resultAggregation.value?.clusters || []).find(
        (cluster) => cluster.cluster_key === selectedClusterKey.value,
      ) || null
    )
  })

  function resolveIssueDisplayRecordRef(
    item: Pick<SichuanBatchIssueItem, 'record_ref' | 'record_id' | 'visit_id'>,
  ) {
    if (isLuxian0609BatchJob.value) {
      return String(item.record_ref || '').trim() || '当前验收病历'
    }
    return String(item.record_id || item.visit_id || '').trim() || '-'
  }

  function resolveLegacySafeRecordGroupKey(
    item: Pick<SichuanBatchIssueItem, 'visit_id' | 'record_id'>,
  ) {
    const source = `${String(item.visit_id || '').trim()}|${String(item.record_id || '').trim()}`
    if (source === '|') return 'unknown-safe-record'
    let hash = 2166136261
    for (let index = 0; index < source.length; index += 1) {
      hash ^= source.charCodeAt(index)
      hash = Math.imul(hash, 16777619)
    }
    return `legacy-safe-${(hash >>> 0).toString(16).padStart(8, '0')}`
  }

  function resolveIssueRecordKey(
    item: Pick<SichuanBatchIssueItem, 'record_ref' | 'visit_id' | 'record_id'>,
  ) {
    if (isLuxian0609BatchJob.value) {
      return String(item.record_ref || '').trim() || resolveLegacySafeRecordGroupKey(item)
    }
    const visitId = String(item.visit_id || '').trim()
    const recordId = String(item.record_id || '').trim()
    return visitId || recordId || 'unknown-record'
  }

  function resolveIssueRecordLabel(item: SichuanBatchIssueItem) {
    if (isLuxian0609BatchJob.value) {
      const recordRef = String(item.record_ref || '').trim()
      return recordRef ? `验收病历 ${recordRef}` : '当前验收病历'
    }
    const patientName = String(item.patient_name || '').trim()
    const recordId = String(item.record_id || '').trim()
    const visitId = String(item.visit_id || '').trim()
    if (patientName && recordId && patientName !== recordId) return `${patientName} · ${recordId}`
    if (patientName) return patientName
    if (recordId) return `病历 ${recordId}`
    if (visitId) return `病历 ${visitId}`
    return '未返回病历标识'
  }

  function resolveIssueRecordMeta(item: SichuanBatchIssueItem) {
    if (isLuxian0609BatchJob.value) {
      return String(item.record_ref || '').trim()
    }
    const values = [
      String(item.department || '').trim(),
      String(item.visit_id || '').trim() ? `visit_id ${String(item.visit_id).trim()}` : '',
      String(item.record_id || '').trim() ? `记录 ${String(item.record_id).trim()}` : '',
    ].filter(Boolean)
    return Array.from(new Set(values)).join(' · ')
  }

  function createIssueRecordGroup<T extends SichuanBatchIssueItem>(
    key: string,
    item: T,
  ): IssueRecordGroup<T> {
    return {
      key,
      label: resolveIssueRecordLabel(item),
      meta: resolveIssueRecordMeta(item),
      total: 0,
      nonCompliant: 0,
      dataGap: 0,
      uncertain: 0,
      technicalError: 0,
      items: [],
    }
  }

  function buildIssueRecordGroups<T extends SichuanBatchIssueItem>(
    items: T[],
  ): Array<IssueRecordGroup<T>> {
    const map = new Map<string, IssueRecordGroup<T>>()
    const safeItems = Array.isArray(items) ? items : []
    safeItems.forEach((item) => {
      const key = resolveIssueRecordKey(item)
      if (!map.has(key)) {
        map.set(key, createIssueRecordGroup(key, item))
      }
      const group = map.get(key)
      if (!group) return
      group.items.push(item)
      group.total += 1
      const status = resolveIssueCanonicalStatus(item)
      if (status === 'non_compliant') {
        group.nonCompliant += 1
      }
      if (status === 'data_gap') group.dataGap += 1
      if (status === 'uncertain' || status === 'ai_suggested_non_compliant') group.uncertain += 1
      if (status === 'technical_error') group.technicalError += 1
    })
    return Array.from(map.values())
  }

  function resolveIssueResultSortRank(item: Partial<SichuanBatchIssueItem>): number {
    const status = resolveIssueCanonicalStatus(item)
    const index = ISSUE_RESULT_DISPLAY_STATUS_ORDER.indexOf(status)
    return index >= 0 ? index : ISSUE_RESULT_DISPLAY_STATUS_ORDER.length
  }

  function sortIssueItemsForBusinessDisplay<T extends SichuanBatchIssueItem>(items: T[]): T[] {
    return [...items].sort((left, right) => {
      const statusRank = resolveIssueResultSortRank(left) - resolveIssueResultSortRank(right)
      if (statusRank !== 0) return statusRank
      const leftRule = String(left.rule_code || left.rule_id || '').trim()
      const rightRule = String(right.rule_code || right.rule_id || '').trim()
      if (leftRule !== rightRule) return leftRule.localeCompare(rightRule, 'zh-Hans-CN')
      return resolveIssueDisplayRecordRef(left).localeCompare(
        resolveIssueDisplayRecordRef(right),
        'zh-Hans-CN',
      )
    })
  }

  const displayIssueItemsBeforeRecordFilter = computed<SichuanBatchIssueItem[]>(() => {
    const items = issueItems.value.filter((item) => {
      if (!selectedDebugRuleJobId.value) return true
      const itemRuleJobId = String(item.rule_job_id || '').trim()
      return itemRuleJobId === selectedDebugRuleJobId.value
    })
    const cluster = selectedCluster.value
    if (!cluster) return items
    return items.filter((item) => matchIssueItemWithCluster(item, cluster))
  })

  const issueRecordGroups = computed(() =>
    buildIssueRecordGroups(displayIssueItemsBeforeRecordFilter.value),
  )

  const focusedLuxianRecordLabel = computed(
    () => issueRecordGroups.value[0]?.label || '当前验收病历',
  )

  const issueRecordTotalCount = computed(() =>
    issueRecordGroups.value.reduce((sum, group) => sum + group.total, 0),
  )

  const isMultiRecordIssueMode = computed(() => issueRecordGroups.value.length > 1)
  const isSingleRecordIssueMode = computed(
    () => issueViewMode.value === 'business' && issueRecordGroups.value.length <= 1,
  )
  const isFocusedSingleRecordScope = computed(
    () => isFocusedRecordMode.value && issueRecordGroups.value.length <= 1,
  )

  const displayIssueItems = computed<SichuanBatchIssueItem[]>(() => {
    let items = displayIssueItemsBeforeRecordFilter.value
    if (selectedIssueRecordKey.value === ALL_RECORDS_KEY) {
      return sortIssueItemsForBusinessDisplay(items)
    }
    const exists = issueRecordGroups.value.some(
      (group) => group.key === selectedIssueRecordKey.value,
    )
    if (exists) {
      items = items.filter((item) => resolveIssueRecordKey(item) === selectedIssueRecordKey.value)
    } else if (issueRecordGroups.value.length > 1) {
      const fallbackKey = issueRecordGroups.value[0]?.key
      if (fallbackKey) {
        items = items.filter((item) => resolveIssueRecordKey(item) === fallbackKey)
      }
    }
    return sortIssueItemsForBusinessDisplay(items)
  })

  const noIssueEvidenceSourceItems = computed<SichuanBatchIssueItem[]>(() => {
    if (isLuxian0609BatchJob.value) {
      let items = canonicalLuxianIssueSourceItems.value.filter((item) =>
        ['compliant', 'not_applicable', 'ai_suggested_compliant'].includes(
          resolveIssueCanonicalStatus(item),
        ),
      )
      if (selectedDebugRuleJobId.value) {
        items = items.filter(
          (item) => String(item.rule_job_id || '').trim() === selectedDebugRuleJobId.value,
        )
      }
      if (
        selectedIssueRecordKey.value &&
        selectedIssueRecordKey.value !== ALL_RECORDS_KEY &&
        issueRecordGroups.value.some((group) => group.key === selectedIssueRecordKey.value)
      ) {
        items = items.filter((item) => resolveIssueRecordKey(item) === selectedIssueRecordKey.value)
      }
      return sortIssueItemsForBusinessDisplay(items)
    }
    const baseFilter: StructuredQCFilterState = {
      ...issueFilter.value,
      statusList: ['compliant', 'not_applicable'] satisfies StructuredQCStatus[],
    }
    let items = filterStructuredQCIssues(scopedStructuredIssues.value, baseFilter)
    if (!showAllStatuses.value) {
      items = items.filter((item) => !item.internalOnly)
    }
    let mappedItems = items.map(mapStructuredIssueToBatchIssueItem)
    if (selectedDebugRuleJobId.value) {
      mappedItems = mappedItems.filter((item) => {
        const itemRuleJobId = String(item.rule_job_id || '').trim()
        return itemRuleJobId === selectedDebugRuleJobId.value
      })
    }
    const cluster = selectedCluster.value
    if (cluster) {
      mappedItems = mappedItems.filter((item) => matchIssueItemWithCluster(item, cluster))
    }
    if (
      selectedIssueRecordKey.value &&
      selectedIssueRecordKey.value !== ALL_RECORDS_KEY &&
      issueRecordGroups.value.some((group) => group.key === selectedIssueRecordKey.value)
    ) {
      mappedItems = mappedItems.filter(
        (item) => resolveIssueRecordKey(item) === selectedIssueRecordKey.value,
      )
    }
    return sortIssueItemsForBusinessDisplay(mappedItems)
  })

  const noIssueEvidenceTotalCount = computed(() => noIssueEvidenceSourceItems.value.length)

  const noIssueEvidenceItems = computed(() =>
    noIssueEvidenceSourceItems.value.slice(0, 8).map(enrichNoIssueEvidenceItem),
  )

  function enrichBusinessIssueCard(item: SichuanBatchIssueItem) {
    const customerEvidenceText =
      resolveLuxianSafeEvidenceText(item) ||
      resolveCustomerEvidenceText(resolveLegacyEvidenceText(item.evidence))
    return {
      ...item,
      customer_display: isLuxian0609BatchJob.value ? buildCustomerQcDisplayModel(item) : null,
      customer_findings_text: sanitizeCustomerVisibleText(
        isLuxian0609BatchJob.value ? item.conclusion || item.findings : item.findings,
      ),
      customer_reason_code_text: isLuxian0609BatchJob.value
        ? resolveLuxianReasonCodeText(item.reason_code)
        : '',
      customer_suggestion_text: sanitizeCustomerVisibleText(item.suggestion),
      customer_evidence_text: customerEvidenceText,
      customer_evidence_structured: resolveStructuredText(customerEvidenceText),
      evidence_summary: resolveIssueEvidenceSummary(item),
      evidence_summary_parts: resolveIssueEvidenceSummaryParts(item),
      issue_card_class: resolveIssueCardClass(item),
    }
  }

  function resolveNoIssueEvidenceBasisLabel(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    if (status === 'not_applicable') return '不适用依据'
    if (status === 'compliant') return '未发现问题依据'
    return '判定依据'
  }

  function resolveNoIssueEvidenceBasisText(item: Partial<SichuanBatchIssueItem>) {
    const status = resolveIssueCanonicalStatus(item)
    const structuredEvidence = resolveEvidenceChainItems(item, 320)
      .slice(0, 2)
      .map(formatEvidenceSummaryItem)
      .join('；')
    const evidenceText =
      structuredEvidence ||
      resolveIssueEvidenceSummary(item) ||
      sanitizeCustomerVisibleText(item.findings) ||
      sanitizeCustomerVisibleText(resolveLegacyEvidenceText(item.evidence))
    if (evidenceText && !isGenericCustomerEvidenceText(evidenceText)) {
      return truncateText(evidenceText, 220)
    }
    if (status === 'not_applicable') {
      return '本次未发现该质控点适用的强触发事实，因此未列为问题项。'
    }
    return '本次已完成该质控点检查，未发现需要整改、补资料或质控确认的结果。'
  }

  function enrichNoIssueEvidenceItem(item: SichuanBatchIssueItem) {
    return {
      ...item,
      no_issue_status_text:
        resolveDisplayStatusText(item) || resolveStatusText(resolveIssueCanonicalStatus(item)),
      no_issue_basis_label: resolveNoIssueEvidenceBasisLabel(item),
      no_issue_basis_text: resolveNoIssueEvidenceBasisText(item),
    }
  }

  const allBusinessIssueCards = computed(() => displayIssueItems.value.map(enrichBusinessIssueCard))

  const recordCompareCoordinates = computed(() => {
    const candidates = [
      allBusinessIssueCards.value.find(
        (item) => resolveIssueStableKey(item) === selectedBusinessIssueKey.value,
      ),
      ...allBusinessIssueCards.value,
    ].filter(Boolean)
    const visitId =
      normalizedFocusVisitId.value ||
      candidates.map((item) => String(item?.visit_id || '').trim()).find(Boolean) ||
      ''
    const instituteId =
      String(props.focusInstituteId || '').trim() ||
      candidates.map((item) => String(item?.institute_id || '').trim()).find(Boolean) ||
      ''
    const patientId =
      String(props.focusPatientId || '').trim() ||
      candidates.map((item) => String(item?.patient_id || '').trim()).find(Boolean) ||
      ''
    return { visitId, instituteId, patientId }
  })

  function buildRecordCompareEvidence(
    item: SichuanBatchIssueItem,
    itemKey: string,
  ): QCRecordCompareIssue['evidences'] {
    const recommendationEvidence = buildRecommendationEvidence(item, itemKey)
    const evidenceRefs = Array.isArray(item.evidence) ? item.evidence.filter(isSafeEvidenceRef) : []
    if (recommendationEvidence.length || evidenceRefs.length) {
      const recommendationRefs = new Set(
        recommendationEvidence.map((evidence) => evidence.source_ref || ''),
      )
      const regularEvidence = evidenceRefs
        .filter((evidence) => !recommendationRefs.has(evidence.source_ref.trim()))
        .map((evidence, index) => ({
          key: `${itemKey}-evidence-${index}`,
          source_document_type: evidence.source_type,
          source_table: evidence.source_type,
          source_document_name: resolveLuxianEvidenceSourceLabel(evidence.source_type),
          quote: evidence.source_ref.trim(),
        }))
      return [...recommendationEvidence, ...regularEvidence].slice(0, 6)
    }
    const evidenceText = resolveIssueEvidenceSummary(item)
    if (!evidenceText) return []
    return [
      {
        key: `${itemKey}-evidence-summary`,
        source_document_type: String(item.target_document_type || item.document_type || ''),
        source_document_name: String(item.target_document_type || item.document_type || '来源文书'),
        quote: evidenceText,
      },
    ]
  }

  const recordCompareIssues = computed<QCRecordCompareIssue[]>(() =>
    allBusinessIssueCards.value.map((item) => {
      const key = resolveIssueStableKey(item)
      const status = resolveIssueCanonicalStatus(item)
      const normalized = normalizeCustomerQcResult(item)
      const existingEvidences = buildRecordCompareEvidence(item, key)
      const controlledEvidences = normalized.display.evidenceSources.map((source, index) => ({
        key: `${key}-controlled-evidence-${index}`,
        source_document_type: source.kind,
        source_document_name: source.label,
        section_field_path: source.fieldPath,
        quote: source.label,
      }))
      return {
        key,
        rule_code: String(item.rule_code || item.rule_id || '未知规则'),
        rule_name: String(item.rule_name || '未知质控点'),
        status,
        status_text: resolveDisplayStatusText(item) || resolveStatusText(status),
        result_kind_text: resolveIssueResultKindText(item),
        conclusion: item.customer_findings_text || item.findings || item.conclusion || '未返回结论',
        summary: normalized.display.summary,
        detail: normalized.display.detail,
        requirement: normalized.display.requirement,
        actual_value: normalized.display.actualValue,
        suggestion: normalized.display.suggestion,
        target_document_type: String(item.target_document_type || item.document_type || ''),
        evidences: existingEvidences.length ? existingEvidences : controlledEvidences,
      }
    }),
  )

  function selectRecordCompareIssue(issueKey: string) {
    selectedBusinessIssueKey.value = issueKey
  }

  const businessIssueCards = computed(() => {
    if (isSingleRecordIssueMode.value) {
      const selected =
        allBusinessIssueCards.value.find(
          (item) => resolveIssueStableKey(item) === selectedBusinessIssueKey.value,
        ) || allBusinessIssueCards.value[0]
      return selected ? [selected] : []
    }
    const startIndex = (issuePagination.current - 1) * issuePagination.pageSize
    return displayIssueItems.value
      .slice(startIndex, startIndex + issuePagination.pageSize)
      .map(enrichBusinessIssueCard)
  })

  const selectedBusinessIssueCard = computed(() => businessIssueCards.value[0] || null)

  const selectedIssuePatientContext = computed(() => {
    const item = selectedBusinessIssueCard.value
    if (!item) return null
    if (isLuxian0609BatchJob.value) {
      return {
        recordId: resolveIssueDisplayRecordRef(item),
        patientName: '验收病历',
        department: '',
        documentType:
          String(item.target_document_type || item.document_type || '').trim() || '未知文书域',
        initial: '病',
      }
    }
    const recordId = String(item.record_id || item.visit_id || item.patient_id || '-').trim() || '-'
    const patientName = String(item.patient_name || '').trim() || '未返回患者'
    const department = String(item.department || '').trim() || '未返回科室'
    const documentType =
      String(item.target_document_type || item.document_type || '').trim() || '未知文书域'
    const initial = patientName && patientName !== '未返回患者' ? patientName.slice(0, 1) : '病'
    return {
      recordId,
      patientName,
      department,
      documentType,
      initial,
    }
  })

  const businessIssueCardGroups = computed(() => buildIssueRecordGroups(businessIssueCards.value))

  const shouldShowIssueRecordGroupHeader = computed(
    () =>
      isMultiRecordIssueMode.value ||
      (selectedIssueRecordKey.value !== ALL_RECORDS_KEY && !isSingleRecordIssueMode.value),
  )

  const singleIssueNavGroups = computed(() => {
    const groups = [
      {
        key: 'non_compliant',
        title: '优先处理：确定问题',
        className: 'issue-review-nav-group--danger',
        items: [] as SichuanBatchIssueItem[],
      },
      {
        key: 'data_gap',
        title: '需补资料：数据不足',
        className: 'issue-review-nav-group--warning',
        items: [] as SichuanBatchIssueItem[],
      },
      {
        key: 'uncertain',
        title: 'AI判断：建议确认',
        className: 'issue-review-nav-group--review',
        items: [] as SichuanBatchIssueItem[],
      },
      {
        key: 'technical_error',
        title: '执行异常：技术错误',
        className: 'issue-review-nav-group--warning',
        items: [] as SichuanBatchIssueItem[],
      },
      {
        key: 'not_applicable',
        title: '无需处理：不适用',
        className: 'issue-review-nav-group--muted',
        items: [] as SichuanBatchIssueItem[],
      },
      {
        key: 'other',
        title: '其他结果',
        className: 'issue-review-nav-group--muted',
        items: [] as SichuanBatchIssueItem[],
      },
    ]
    const groupMap = new Map(groups.map((group) => [group.key, group]))
    displayIssueItems.value.forEach((item) => {
      const status = resolveIssueCanonicalStatus(item)
      const group =
        groupMap.get(
          status === 'ai_suggested_non_compliant'
            ? 'uncertain'
            : status === 'ai_suggested_compliant'
              ? 'not_applicable'
              : status === 'not_executed'
                ? 'uncertain'
                : status,
        ) || groupMap.get('other')
      group?.items.push(item)
    })
    return groups.filter((group) => group.items.length > 0)
  })

  function selectBusinessIssue(item: SichuanBatchIssueItem) {
    selectedBusinessIssueKey.value = resolveIssueStableKey(item)
  }

  function resolveIssueReviewNavClass(item: SichuanBatchIssueItem) {
    const status = resolveIssueCanonicalStatus(item)
    if (status === 'non_compliant') return 'issue-review-nav-item--danger'
    if (status === 'technical_error') return 'issue-review-nav-item--error'
    if (status === 'data_gap' || status === 'uncertain' || status === 'ai_suggested_non_compliant')
      return 'issue-review-nav-item--warning'
    if (status === 'not_executed' || status === 'not_applicable')
      return 'issue-review-nav-item--muted'
    if (status === 'compliant' || status === 'ai_suggested_compliant')
      return 'issue-review-nav-item--ok'
    return ''
  }

  function syncSelectedIssueRecord(groups = issueRecordGroups.value) {
    if (groups.length > 1) {
      const hasSelected = groups.some((group) => group.key === selectedIssueRecordKey.value)
      if (!hasSelected || selectedIssueRecordKey.value === ALL_RECORDS_KEY) {
        selectedIssueRecordKey.value = groups[0]?.key || ALL_RECORDS_KEY
      }
      return
    }
    if (selectedIssueRecordKey.value !== ALL_RECORDS_KEY) {
      selectedIssueRecordKey.value = ALL_RECORDS_KEY
    }
  }

  function syncSelectedBusinessIssue(items = displayIssueItems.value) {
    if (!items.length) {
      selectedBusinessIssueKey.value = ''
      return
    }
    const hasSelected = items.some(
      (item) => resolveIssueStableKey(item) === selectedBusinessIssueKey.value,
    )
    if (!hasSelected) {
      selectedBusinessIssueKey.value = resolveIssueStableKey(items[0])
    }
  }

  const linkedIssueRowKey = computed(() => {
    if (!selectedCluster.value) return ''
    return resolveIssueStableKey(displayIssueItems.value[0])
  })

  const displayRuleResults = computed(() => {
    const items = resolvedRuleResults.value
    if (!selectedDebugRuleJobId.value) return items
    return items.filter((item) => String(item.id || '').trim() === selectedDebugRuleJobId.value)
  })

  const progressSummary = computed(() => {
    const progressCandidate =
      props.batchJobDetail?.progress || props.batchJobDetail?.summary?.progress || {}
    const progress =
      progressCandidate && typeof progressCandidate === 'object'
        ? (progressCandidate as Record<string, unknown>)
        : {}
    const totalRecords = Number(progress.total_records || props.batchJobDetail?.total_records || 0)
    const processedRecords = Number(
      progress.processed_records ||
        (props.batchJobDetail?.status === 'completed' ? totalRecords : 0),
    )
    const rawRuleCount = Number(progress.rule_count || props.batchJobDetail?.rule_count || 0)
    const ruleCount = Math.max(1, rawRuleCount || resolvedRuleResults.value.length || 1)
    const ruleIndex = Math.min(
      ruleCount,
      Math.max(
        0,
        Number(
          progress.rule_index || (props.batchJobDetail?.status === 'completed' ? ruleCount : 0),
        ),
      ),
    )
    const status = String(props.batchJobDetail?.status || '')
    const stepKey = String(progress.step_key || status || 'queued').toLowerCase()
    let percent = 0
    if (totalRecords > 0) {
      percent = Math.min(100, Math.round((processedRecords / totalRecords) * 100))
    } else if (status === 'completed') {
      percent = 100
    }
    const progressStatus =
      status === 'failed' ? 'exception' : status === 'completed' ? 'success' : 'active'
    return {
      percent,
      processedRecords,
      totalRecords,
      ruleIndex,
      ruleCount,
      stepLabel: PROGRESS_STEP_LABEL_MAP[stepKey] || stepKey || '执行中',
      status: progressStatus as 'active' | 'success' | 'exception',
    }
  })

  const streamState = computed(() => {
    const state = props.batchJobDetail?.summary?.stream_state
    return state && typeof state === 'object' ? state : null
  })

  const isRunningBatchJob = computed(() => {
    const status = String(props.batchJobDetail?.status || '')
      .trim()
      .toLowerCase()
    return status === 'queued' || status === 'running'
  })

  const isWaitingFirstResult = computed(
    () =>
      isRunningBatchJob.value &&
      issueItems.value.length === 0 &&
      (progressSummary.value?.processedRecords || 0) === 0,
  )

  const currentStreamRecordLabel = computed(() => {
    const state = streamState.value
    const latestVisitId = String(state?.latest_visit_id || '').trim()
    const latestRecordId = String(state?.latest_record_id || '').trim()
    return latestVisitId || latestRecordId || ''
  })

  const streamUpdatedAtText = computed(() => {
    const updatedAt = streamState.value?.updated_at || props.batchJobDetail?.updated_at
    if (!updatedAt) return ''
    return props.formatDateTime(updatedAt)
  })

  const liveStartedAtMs = computed(() => {
    const startValue = props.batchJobDetail?.started_at || streamState.value?.started_at
    return parseBackendDateTimeMs(startValue)
  })

  const liveElapsedSeconds = computed(() => {
    const detail = props.batchJobDetail
    if (!detail) return 0
    const finalSeconds = Number(
      detail.summary?.wall_clock_time ??
        detail.wall_clock_time ??
        detail.total_processing_time ??
        0,
    )
    if (!isRunningBatchJob.value) return finalSeconds
    if (!liveStartedAtMs.value) return finalSeconds
    return Math.max(finalSeconds, (liveNow.value - liveStartedAtMs.value) / 1000)
  })

  const liveElapsedText = computed(() => formatProcessingTime(liveElapsedSeconds.value))
  const liveElapsedLabel = computed(() => {
    if (isRunningBatchJob.value && !liveStartedAtMs.value && liveElapsedSeconds.value <= 0) {
      return '运行中'
    }
    return `运行 ${liveElapsedText.value}`
  })

  const incrementalResultTip = computed(() => {
    if (!isRunningBatchJob.value) return ''
    if (issueItems.value.length > 0) {
      return `已返回 ${issueItems.value.length} 条结果，任务仍在继续，后续病历完成后会自动追加。`
    }
    if ((progressSummary.value?.processedRecords || 0) > 0) {
      return '已完成部分病历，当前暂无需要展示的问题项，系统仍在继续质控。'
    }
    return isLuxianNativeSliceBatchJob.value
      ? '正在等待首份病历结果，系统正在执行质控，结果会自动出现。'
      : '正在等待首份病历结果，模型仍在处理，结果会自动出现。'
  })

  const waitingFirstResultDescription = computed(() =>
    isLuxianNativeSliceBatchJob.value
      ? '系统正在执行首份病历质控，结果会自动出现在这里。'
      : '模型仍在处理首份病历，结果会自动出现在这里。',
  )

  const executionSummary = computed(() => {
    const summary = props.batchJobDetail?.summary
    const fromSummary = summary?.executor_breakdown
    const cacheFromSummary = summary?.cache_breakdown
    if (fromSummary || cacheFromSummary) {
      return {
        programCount: Number(fromSummary?.program || 0),
        llmCount: Number(fromSummary?.llm || 0),
        cacheHit: Number(cacheFromSummary?.hit || 0),
        cacheMiss: Number(cacheFromSummary?.miss || 0),
      }
    }
    const items = issueItems.value
    if (!items.length) return null
    const programCount = items.filter(
      (item) => String(item.executor_type || '').toLowerCase() === 'program',
    ).length
    const llmCount = items.filter(
      (item) => String(item.executor_type || '').toLowerCase() !== 'program',
    ).length
    const cacheHit = items.filter((item) => item.cache_hit === true).length
    const cacheMiss = items.length - cacheHit
    return { programCount, llmCount, cacheHit, cacheMiss }
  })

  const isPostprocessedFormalResult = computed(() => {
    const detail = props.batchJobDetail
    const summary = detail?.summary
    const filters = (detail?.filters || {}) as Record<string, unknown>
    return Boolean(
      summary?.postprocess_summary ||
      summary?.display_status_counts ||
      filters.validation_mode === 'formal_fast_screen_full' ||
      filters.rule_set_key === 'sc_content_full_v1' ||
      summary?.rule_set_key === 'sc_content_full_v1',
    )
  })

  const luxianSelectedRuleIds = computed(() => {
    const filters = batchJobFilters.value
    return normalizeStringList(filters.selected_rule_ids).length
      ? normalizeStringList(filters.selected_rule_ids)
      : normalizeStringList(filters.scoped_customer_rule_ids)
  })

  const luxianRecordRuleMapEntries = computed(() => {
    const rawMap = batchJobFilters.value.record_rule_map
    if (!rawMap || typeof rawMap !== 'object' || Array.isArray(rawMap)) return []
    return Object.entries(rawMap as Record<string, unknown>)
  })

  const isLuxianScopedRun = computed(
    () => luxianSelectedRuleIds.value.length > 0 || luxianRecordRuleMapEntries.value.length > 0,
  )

  const luxianExecutionRuleIds = computed(() => {
    const filters = batchJobFilters.value
    return normalizeStringList(filters.rule_ids).length
      ? normalizeStringList(filters.rule_ids)
      : normalizeStringList(props.batchJobDetail?.draft_ids)
  })

  const isLuxianNativeSliceBatchJob = computed(() => {
    const executionRuleIds = luxianExecutionRuleIds.value.map((ruleId) => ruleId.toUpperCase())
    return (
      isLuxian0609BatchJob.value &&
      executionRuleIds.length > 0 &&
      executionRuleIds.every((ruleId) => LUXIAN_0609_NATIVE_RULE_IDS.has(ruleId))
    )
  })

  const {
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
  } = createIssueEvidencePresentation({
    isLuxian0609BatchJob: () => isLuxian0609BatchJob.value,
    isLuxianNativeSliceBatchJob: () => isLuxianNativeSliceBatchJob.value,
    resolveStatusText,
  })

  watch(
    () => [
      props.open,
      props.defaultRecordComparison,
      isFocusedSingleRecordScope.value,
      recordCompareCoordinates.value.visitId,
      props.batchJobDetail?.id,
    ],
    (values) => {
      const [open, defaultEnabled, singleRecordScope, visitId] = Array.isArray(values) ? values : []
      if (
        !open ||
        defaultEnabled !== true ||
        singleRecordScope !== true ||
        !String(visitId || '')
      ) {
        return
      }
      issueViewMode.value = 'compare'
    },
    { immediate: true },
  )

  const luxianCustomerRuleCount = computed(() => {
    const detail = props.batchJobDetail
    const summary = detail?.summary
    const filters = batchJobFilters.value
    return (
      optionalNumber(detail?.customer_rule_count) ??
      optionalNumber(summary?.customer_rule_count) ??
      optionalNumber(filters.customer_rule_count) ??
      luxianSelectedRuleIds.value.length
    )
  })

  watch(
    issueRecordGroups,
    (groups) => {
      syncSelectedIssueRecord(groups)
    },
    { immediate: true },
  )

  watch(
    displayIssueItems,
    (items) => {
      syncSelectedBusinessIssue(items)
    },
    { immediate: true },
  )

  const luxianRecordRuleMapSummary = computed(() => {
    const entries = luxianRecordRuleMapEntries.value
    if (!entries.length)
      return isLuxianScopedRun.value
        ? '未返回'
        : isLuxianNativeSliceBatchJob.value
          ? '全量运行，不按单病历限定质控点'
          : '全量运行，不按单病历限定执行规则'
    const uniqueRules = new Set<string>()
    entries.forEach(([, ruleIds]) => {
      normalizeStringList(ruleIds).forEach((ruleId) => uniqueRules.add(ruleId))
    })
    const sample = entries
      .slice(0, 2)
      .map(
        ([recordId, ruleIds]) =>
          `${recordId}: ${normalizeStringList(ruleIds).length || 0} 条${isLuxianNativeSliceBatchJob.value ? '质控点' : '执行规则'}`,
      )
      .join('；')
    const suffix = entries.length > 2 ? `；另有 ${entries.length - 2} 份病历` : ''
    return isLuxianNativeSliceBatchJob.value
      ? `${entries.length} 份病历执行 ${uniqueRules.size} 个质控点。${sample}${suffix}`
      : `${entries.length} 份病历映射到 ${uniqueRules.size} 条底层执行规则。${sample}${suffix}`
  })

  const luxianStatusDistribution = computed(() => {
    const counts = new Map<string, number>()
    const sourceItems = canonicalLuxianIssueSourceItems.value
    sourceItems.forEach((item) => {
      const key = resolveIssueCanonicalStatus(item)
      if (!key) return
      counts.set(key, Number(counts.get(key) || 0) + 1)
    })
    return LUXIAN_0609_STATUS_ORDER.map((key) => ({
      key,
      label: resolveEvidenceStatusText(key),
      value: Number(counts.get(key) || 0),
      className:
        key === 'non_compliant' || key === 'technical_error'
          ? 'is-danger'
          : key === 'data_gap' ||
              key === 'uncertain' ||
              key === 'ai_suggested_non_compliant' ||
              key === 'not_executed'
            ? 'is-warning'
            : key === 'compliant' || key === 'ai_suggested_compliant'
              ? 'is-success'
              : 'is-muted',
    }))
  })

  const showResultReviewOverview = computed(
    () => isLuxian0609BatchJob.value && issueViewMode.value === 'business',
  )

  const resultReviewOverviewTitle = computed(() => {
    const name = String(props.batchJobDetail?.rule_name || '').trim()
    if (name) return name
    const code = String(props.batchJobDetail?.rule_code || '').trim()
    return code || '泸县0609质控点验证任务'
  })

  const resultReviewOutcomeText = computed(() => {
    const heroTitle = String(statusHero.value?.title || '').trim()
    if (heroTitle) return heroTitle
    return '当前展示泸县0609质控点验证结果。'
  })

  const resultReviewScopeText = computed(() => {
    if (isLuxianScopedRun.value) {
      const countText = luxianSelectedRuleIds.value.length
        ? `已限定 ${luxianSelectedRuleIds.value.length} 个 LX0609 质控点`
        : '已限定质控点，具体 ID 未返回'
      return `${countText}；${luxianRecordRuleMapSummary.value}`
    }
    return `未限定，执行全量 0609 质控点；${luxianRecordRuleMapSummary.value}`
  })

  const resultReviewRecordCount = computed(() => {
    const summary = props.batchJobDetail?.summary
    const filters = batchJobFilters.value
    const authoritativeCount =
      optionalNumber(summary?.total_records) ??
      optionalNumber(filters.dedup_record_count) ??
      optionalNumber(props.batchJobDetail?.total_records)
    if (authoritativeCount !== null) return authoritativeCount
    if (issueRecordGroups.value.length > 0) return issueRecordGroups.value.length
    const selectedRecordIds = Array.isArray(filters.selected_record_ids)
      ? filters.selected_record_ids
      : []
    return selectedRecordIds.length
  })

  const resultReviewResultCount = computed(() => {
    if (displayIssueItemsBeforeRecordFilter.value.length > 0) {
      return displayIssueItemsBeforeRecordFilter.value.length
    }
    return Number(
      props.batchJobDetail?.summary?.processed_rule_count ??
        props.batchJobDetail?.summary?.rule_count ??
        props.batchJobDetail?.rule_count ??
        0,
    )
  })

  const resultReviewCustomerRuleCount = computed(() => {
    if (luxianCustomerRuleCount.value > 0) return luxianCustomerRuleCount.value
    if (luxianSelectedRuleIds.value.length > 0) return luxianSelectedRuleIds.value.length
    return resultReviewResultCount.value
  })

  const resultReviewStatusPills = computed(() =>
    luxianStatusDistribution.value.filter(
      (item) =>
        item.value > 0 ||
        [
          'non_compliant',
          'ai_suggested_non_compliant',
          'data_gap',
          'uncertain',
          'not_applicable',
        ].includes(item.key),
    ),
  )

  const resultReviewOverviewModel = computed(() => {
    if (!showResultReviewOverview.value) return null
    const status = props.batchJobDetail?.status || 'queued'
    return {
      title: resultReviewOverviewTitle.value,
      statusClass: props.getBatchJobStatusTagClass(status),
      statusText: props.getBatchJobStatusText(status),
      createdAtText: props.batchJobDetail?.created_at
        ? props.formatDateTime(props.batchJobDetail.created_at)
        : '',
      finishedAtText: props.batchJobDetail?.finished_at
        ? props.formatDateTime(props.batchJobDetail.finished_at)
        : '',
      recordCount: resultReviewRecordCount.value,
      customerRuleCount: resultReviewCustomerRuleCount.value,
      resultCount: resultReviewResultCount.value,
      outcomeText: resultReviewOutcomeText.value,
      scopeText: resultReviewScopeText.value,
      statusPills: resultReviewStatusPills.value,
    }
  })

  const luxianReviewReport = computed<Luxian0609ReviewReport | null>(() => {
    const report = props.batchJobDetail?.summary?.review_report
    return report && typeof report === 'object' ? report : null
  })

  const luxianReviewFindings = computed<Luxian0609ReviewFinding[]>(
    () => luxianReviewReport.value?.findings?.slice(0, 8) || [],
  )

  const luxianReviewSummaryText = computed(() => {
    const summary = luxianReviewReport.value?.summary
    const total = Number(summary?.total_findings || 0)
    if (!total) return '暂无高风险建议'
    return `共 ${total} 条建议：P0 ${Number(summary?.p0 || 0)} · P1 ${Number(summary?.p1 || 0)} · P2 ${Number(summary?.p2 || 0)}`
  })

  function mapStructuredStatusLabel(status?: string): string {
    const normalized = String(status || '')
      .trim()
      .toLowerCase()
    if (normalized === 'non_compliant') return '不合规'
    if (normalized === 'ai_suggested_non_compliant') return 'AI判断：疑似问题'
    if (normalized === 'ai_suggested_compliant') return 'AI判断：未见问题'
    if (normalized === 'compliant') return '合规'
    if (normalized === 'not_applicable') return '不适用'
    if (normalized === 'data_gap') return '数据不足'
    if (normalized === 'uncertain') return 'AI判断'
    if (normalized === 'not_executed') return '未执行'
    if (normalized === 'technical_error') return '技术异常'
    return status || 'AI判断'
  }

  function isConfirmedDefectItem(item: SichuanBatchIssueItem): boolean {
    if (isLuxian0609BatchJob.value) {
      return resolveIssueCanonicalStatus(item) === 'non_compliant'
    }
    if (isPostprocessedFormalResult.value) {
      return item.can_show_as_defect === true || item.display_status === 'confirmed_defect'
    }
    return item.status === 'non_compliant'
  }

  function isNeedsReviewItem(item: SichuanBatchIssueItem): boolean {
    if (isLuxian0609BatchJob.value) {
      const status = resolveIssueCanonicalStatus(item)
      return status === 'uncertain' || status === 'ai_suggested_non_compliant'
    }
    if (isPostprocessedFormalResult.value) {
      return false
    }
    return item.status === 'uncertain'
  }

  function isDataQualityGapItem(item: SichuanBatchIssueItem): boolean {
    if (isLuxian0609BatchJob.value) {
      return resolveIssueCanonicalStatus(item) === 'data_gap'
    }
    return isPostprocessedFormalResult.value && item.display_status === 'data_quality_gap'
  }

  function isRejectedBySystemItem(item: SichuanBatchIssueItem): boolean {
    return isPostprocessedFormalResult.value && item.display_status === 'rejected_by_system'
  }

  const ruleLevelSummary = computed(() => {
    const totalRules = Math.max(
      0,
      Number(props.batchJobDetail?.summary?.rule_count ?? props.batchJobDetail?.rule_count ?? 0) ||
        resolvedRuleResults.value.length,
    )
    const issueItemsList = issueItems.value
    const summary = props.batchJobDetail?.summary
    const nonCompliantCount = issueItemsList.filter((item) => isConfirmedDefectItem(item)).length
    const uncertainCount = issueItemsList.filter((item) => isNeedsReviewItem(item)).length
    const dataQualityGapCount = issueItemsList.filter((item) => isDataQualityGapItem(item)).length
    const technicalErrorCount = isPostprocessedFormalResult.value
      ? Number(
          summary?.technical_error_internal_count ??
            summary?.postprocess_summary?.technical_error_internal_count ??
            issueItemsList.filter((item) => item.display_status === 'technical_error_internal')
              .length,
        )
      : issueItemsList.filter((item) => resolveIssueCanonicalStatus(item) === 'technical_error')
          .length
    const rejectedBySystemCount = isPostprocessedFormalResult.value
      ? Number(
          summary?.rejected_by_system_count ??
            summary?.postprocess_summary?.rejected_by_system_count ??
            0,
        )
      : issueItemsList.filter((item) => isRejectedBySystemItem(item)).length
    const focusCount = nonCompliantCount + uncertainCount + dataQualityGapCount
    const docIssueCount = new Set(
      issueItemsList
        .filter((item) => isConfirmedDefectItem(item))
        .map((item) => resolveIssueDisplayRecordRef(item))
        .filter(Boolean),
    ).size
    const docUncertainCount = new Set(
      issueItemsList
        .filter((item) => isNeedsReviewItem(item))
        .map((item) => resolveIssueDisplayRecordRef(item))
        .filter(Boolean),
    ).size
    const processingTimeSeconds = Number(
      props.batchJobDetail?.summary?.wall_clock_time ??
        props.batchJobDetail?.wall_clock_time ??
        props.batchJobDetail?.total_processing_time ??
        0,
    )
    const modelProcessingTimeSeconds = Number(
      props.batchJobDetail?.summary?.total_processing_time ??
        props.batchJobDetail?.total_processing_time ??
        0,
    )
    return {
      totalRules,
      nonCompliantCount,
      uncertainCount,
      dataQualityGapCount,
      rejectedBySystemCount,
      technicalErrorCount,
      focusCount,
      docIssueCount,
      docUncertainCount,
      processingTimeSeconds,
      modelProcessingTimeSeconds,
    }
  })

  const statusHero = computed(() => {
    const detail = props.batchJobDetail
    if (!detail) return null
    const status = String(detail.status || '')
      .trim()
      .toLowerCase()
    const processedRecords = progressSummary.value?.processedRecords ?? 0
    const totalRecords = progressSummary.value?.totalRecords ?? Number(detail.total_records || 0)
    const issueRecords = ruleLevelSummary.value.nonCompliantCount
    const uncertainRecords = ruleLevelSummary.value.uncertainCount
    const dataQualityGapRecords = ruleLevelSummary.value.dataQualityGapCount
    const finishedAt = detail.finished_at || detail.updated_at
    const meta: string[] = []
    if (totalRecords > 0) {
      meta.push(`已处理 ${processedRecords}/${totalRecords} 份病历`)
    }
    if ((progressSummary.value?.ruleCount || 0) > 0) {
      meta.push(
        `规则 ${progressSummary.value?.ruleIndex || 0}/${progressSummary.value?.ruleCount || 0}`,
      )
    }
    if (status === 'completed') {
      if (ruleLevelSummary.value.processingTimeSeconds > 0) {
        meta.push(`总耗时 ${formatProcessingTime(ruleLevelSummary.value.processingTimeSeconds)}`)
      }
      if (
        isPostprocessedFormalResult.value &&
        !isLuxianNativeSliceBatchJob.value &&
        ruleLevelSummary.value.modelProcessingTimeSeconds > 0
      ) {
        meta.push(
          `累计模型处理耗时 ${formatProcessingTime(ruleLevelSummary.value.modelProcessingTimeSeconds)}`,
        )
      }
      if (finishedAt) {
        meta.push(`完成于 ${props.formatDateTime(finishedAt)}`)
      }
    }
    if (status === 'failed' && detail.error_message) {
      meta.push('请优先查看下方失败原因与调试快照')
    }
    if (status === 'canceled' && finishedAt) {
      meta.push(`停止于 ${props.formatDateTime(finishedAt)}`)
    }
    if (status === 'queued') {
      return {
        tone: 'queued',
        title: '任务已创建，等待执行',
        description:
          '系统已接收任务，正在分配执行资源。抽屉内容会自动刷新，不需要手动反复关闭再打开。',
        meta,
        pulse: true,
      }
    }
    if (status === 'running') {
      return {
        tone: 'running',
        title: '任务执行中，请直接关注这里的进度',
        description: '结果会随着轮询自动刷新。任务结束后会弹出强提醒，并保留最终结果在当前抽屉中。',
        meta,
        pulse: true,
      }
    }
    if (status === 'completed') {
      const focusCount =
        issueRecords +
        uncertainRecords +
        (isLuxian0609BatchJob.value || isPostprocessedFormalResult.value
          ? dataQualityGapRecords
          : 0)
      if (isLuxian0609BatchJob.value) {
        return {
          tone: 'completed',
          title:
            focusCount > 0
              ? '任务已完成，已发现泸县0609质控点问题'
              : '任务已完成，本次未发现泸县0609质控点问题',
          description:
            focusCount > 0
              ? `请查看下方客户质控点明细：不合规 ${issueRecords} 条，数据不足 ${dataQualityGapRecords} 条，AI判断 ${uncertainRecords} 条。`
              : '当前所选 LX0609 质控点未返回不合规、数据不足或 AI 判断结果。',
          meta,
          pulse: false,
        }
      }
      return {
        tone: 'completed',
        title: focusCount > 0 ? '任务已完成，已产出可处理问题' : '任务已完成，本次未发现问题',
        description:
          focusCount > 0
            ? isPostprocessedFormalResult.value
              ? '请优先查看下方四层准入明细，确认缺陷可直接处理，数据缺口需排查链路。'
              : '请优先查看下方“问题/AI判断明细”，直接判断需要确认或整改的质控点。'
            : '本次批量质控已执行完毕，当前规则集下没有发现需要处理的问题。',
        meta,
        pulse: false,
      }
    }
    if (status === 'failed') {
      return {
        tone: 'failed',
        title: '任务执行失败，需要人工处理',
        description: detail.error_message || '后端在执行中断，请检查失败原因，必要时点击重试。',
        meta,
        pulse: false,
      }
    }
    return {
      tone: 'canceled',
      title: '任务已取消',
      description: '该任务已被手动停止，不会继续产生新的质控结果。',
      meta,
      pulse: false,
    }
  })

  const primarySummaryCards = computed(() => {
    const summary = props.batchJobDetail?.summary
    const totalRecords = Number(
      optionalNumber(summary?.total_records) ??
        optionalNumber(batchJobFilters.value.dedup_record_count) ??
        optionalNumber(props.batchJobDetail?.total_records) ??
        0,
    )
    const successCount = Number(summary?.success_count ?? props.batchJobDetail?.success_count ?? 0)
    const failedRecordCount = Number(
      summary?.failed_record_count ?? props.batchJobDetail?.failed_count ?? 0,
    )
    const failedAttemptCount = Number(
      summary?.failed_count ?? props.batchJobDetail?.failed_count ?? 0,
    )
    const issueRecords = ruleLevelSummary.value.nonCompliantCount
    const uncertainRecords = ruleLevelSummary.value.uncertainCount
    const dataQualityGapRecords = ruleLevelSummary.value.dataQualityGapCount
    const rejectedBySystemRecords = ruleLevelSummary.value.rejectedBySystemCount
    const technicalErrorRecords = ruleLevelSummary.value.technicalErrorCount
    const focusCount = ruleLevelSummary.value.focusCount
    const processingTimeSeconds = isRunningBatchJob.value
      ? liveElapsedSeconds.value
      : ruleLevelSummary.value.processingTimeSeconds
    const cards = [
      { key: 'total', label: '总病历', value: totalRecords, desc: '' },
      { key: 'rules', label: '总规则', value: ruleLevelSummary.value.totalRules, desc: '' },
      {
        key: 'failed-records',
        label: '失败病历',
        value: failedRecordCount,
        desc: '去重后的病历数',
      },
      {
        key: 'failed-attempts',
        label: '失败次数',
        value: failedAttemptCount,
        desc: '规则执行失败总次数',
      },
      {
        key: 'issues',
        label: isPostprocessedFormalResult.value ? '确认缺陷' : '不合规规则',
        value: issueRecords,
        desc: isPostprocessedFormalResult.value ? '后处理准入后可展示为缺陷' : '',
      },
      ...(isPostprocessedFormalResult.value
        ? []
        : [
            {
              key: 'uncertain',
              label: 'AI判断规则',
              value: uncertainRecords,
              desc: '',
            },
          ]),
      ...(isPostprocessedFormalResult.value
        ? [
            { key: 'data-quality-gap', label: '数据缺口', value: dataQualityGapRecords, desc: '' },
            {
              key: 'rejected-by-system',
              label: '系统驳回',
              value: rejectedBySystemRecords,
              desc: '仅内部诊断',
            },
            {
              key: 'technical-error',
              label: '技术异常',
              value: technicalErrorRecords,
              desc: '仅内部诊断',
            },
          ]
        : []),
      { key: 'focus', label: '重点结果', value: focusCount, desc: '' },
      {
        key: 'duration',
        label: '总耗时',
        value: processingTimeSeconds > 0 ? formatProcessingTime(processingTimeSeconds) : '-',
        desc: '',
      },
      ...(isPostprocessedFormalResult.value && !isLuxianNativeSliceBatchJob.value
        ? [
            {
              key: 'model-duration',
              label: '累计模型处理耗时',
              value:
                ruleLevelSummary.value.modelProcessingTimeSeconds > 0
                  ? formatProcessingTime(ruleLevelSummary.value.modelProcessingTimeSeconds)
                  : '-',
              desc: '并发 pack 的模型耗时累计',
            },
          ]
        : []),
      { key: 'success', label: '执行成功', value: successCount, desc: '' },
      {
        key: 'issue-records',
        label: '涉及问题病历',
        value: ruleLevelSummary.value.docIssueCount,
        desc: '病历级去重统计',
      },
      {
        key: 'uncertain-records',
        label: '涉及AI判断病历',
        value: ruleLevelSummary.value.docUncertainCount,
        desc: '病历级去重统计',
      },
    ]
    return isPostprocessedFormalResult.value
      ? cards.filter((item) => item.key !== 'uncertain-records')
      : cards
  })

  const focusedSummaryCards = computed(() => {
    if (isFocusedRecordMode.value) {
      return [
        { key: 'total', label: '总病历', value: 1, desc: '当前仅展示选中病历' },
        {
          key: 'issues',
          label: isPostprocessedFormalResult.value ? '确认缺陷' : '不合规规则',
          value: issueItems.value.filter((item) => isConfirmedDefectItem(item)).length,
          desc: '',
        },
        {
          key: 'uncertain',
          label: 'AI判断规则',
          value: issueItems.value.filter((item) => isNeedsReviewItem(item)).length,
          desc: '',
        },
        ...(isPostprocessedFormalResult.value
          ? [
              {
                key: 'data-quality-gap',
                label: '数据缺口',
                value: issueItems.value.filter((item) => isDataQualityGapItem(item)).length,
                desc: '',
              },
              {
                key: 'rejected-by-system',
                label: '系统驳回',
                value: ruleLevelSummary.value.rejectedBySystemCount,
                desc: '仅内部诊断',
              },
              {
                key: 'technical-error',
                label: '技术异常',
                value: ruleLevelSummary.value.technicalErrorCount,
                desc: '仅内部诊断',
              },
            ]
          : []),
        {
          key: 'duration',
          label: '总耗时',
          value:
            ruleLevelSummary.value.processingTimeSeconds > 0
              ? formatProcessingTime(ruleLevelSummary.value.processingTimeSeconds)
              : '-',
          desc: isPostprocessedFormalResult.value ? '真实任务墙钟耗时' : '任务总耗时',
        },
      ].filter((item) => !(isPostprocessedFormalResult.value && item.key === 'uncertain'))
    }
    return primarySummaryCards.value.filter((item) =>
      [
        'total',
        'issues',
        ...(isPostprocessedFormalResult.value ? [] : ['uncertain']),
        'data-quality-gap',
        'rejected-by-system',
        'technical-error',
        'duration',
        'model-duration',
      ].includes(item.key),
    )
  })

  const isFastScreenResult = computed(() => {
    const detail = props.batchJobDetail
    const summary = detail?.summary
    return (
      String(detail?.execution_strategy || summary?.execution_strategy || '')
        .trim()
        .toLowerCase() === 'fast_screen' ||
      String(detail?.rule_set_key || summary?.rule_set_key || '')
        .trim()
        .toLowerCase() === 'sc_content_fast_v1'
    )
  })

  const executionSummaryCards = computed(() => {
    if (!executionSummary.value) return []
    const summary = props.batchJobDetail?.summary
    const packMetrics = summary?.pack_metrics || {}
    const cards = [
      {
        key: 'program',
        label: 'Program执行',
        value: executionSummary.value.programCount,
        desc: '',
      },
      ...(isLuxianNativeSliceBatchJob.value
        ? []
        : [{ key: 'llm', label: '语义规则', value: executionSummary.value.llmCount, desc: '' }]),
      { key: 'hit', label: '缓存命中', value: executionSummary.value.cacheHit, desc: '' },
      { key: 'miss', label: '缓存未命中', value: executionSummary.value.cacheMiss, desc: '' },
    ]
    if (summary?.refine_summary || summary?.refined_rule_count) {
      cards.push({
        key: 'refined',
        label: '单条精审',
        value: Number(
          summary.refined_rule_count || summary.refine_summary?.refined_rule_count || 0,
        ),
        desc: '',
      })
    }
    if (packMetrics.total_packs !== undefined) {
      cards.push({
        key: 'packs',
        label: '分包数',
        value: Number(packMetrics.total_packs || 0),
        desc: '',
      })
    }
    return cards
  })

  const performanceProfile = computed(
    () => props.batchJobDetail?.summary?.performance_profile || null,
  )

  const performanceProfileCards = computed(() => {
    if (isLuxianNativeSliceBatchJob.value) return []
    const profile = performanceProfile.value
    if (!profile) return []
    const unattributedTokens = optionalNumber(profile.unattributed_tokens)
    const breakdownComplete =
      profile.token_breakdown_complete === true ||
      (unattributedTokens !== null && unattributedTokens === 0)
    return [
      {
        key: 'tokens-total',
        label: '总 Token',
        value: formatTokenNumber(
          profile.tokens_total ?? props.batchJobDetail?.summary?.total_tokens,
        ),
        desc: '本次任务模型服务返回的 token 总量',
      },
      {
        key: 'prompt-tokens',
        label: '输入 Token',
        value: formatTokenNumber(profile.prompt_tokens),
        desc: '可归因到输入上下文的 token',
      },
      {
        key: 'completion-tokens',
        label: '输出 Token',
        value: formatTokenNumber(profile.completion_tokens),
        desc: '可归因到模型输出的 token',
      },
      {
        key: 'unattributed-tokens',
        label: '未归因 Token',
        value: formatTokenNumber(profile.unattributed_tokens),
        desc: '模型服务未拆分到输入/输出的 token',
      },
      {
        key: 'token-breakdown-complete',
        label: 'Token 拆分',
        value: breakdownComplete ? '完整' : '有未归因',
        desc: breakdownComplete ? '输入/输出 token 已覆盖总量' : '需结合未归因 token 评估成本',
      },
    ]
  })

  const advancedSummaryCards = computed(() => {
    const cards = [
      ...primarySummaryCards.value.filter(
        (item) => !['total', 'issues', 'uncertain', 'failed-records'].includes(item.key),
      ),
      ...performanceProfileCards.value,
      ...executionSummaryCards.value,
      {
        key: 'rule-results',
        label: '规则结果条数',
        value: resolvedRuleResults.value.length,
        desc: '',
      },
      {
        key: 'issue-items',
        label: isPostprocessedFormalResult.value ? '四层准入明细' : '问题/AI判断明细',
        value: issueItems.value.length,
        desc: '',
      },
    ]
    return cards.filter((item) => item.value !== undefined && item.value !== null)
  })

  const issueFocusSummary = computed(() => {
    const currentItems = displayIssueItems.value
    const total = currentItems.length
    if (!total) {
      return showAllStatuses.value
        ? '当前没有可展示的规则结果。'
        : '当前没有需要复核或整改的问题项。'
    }
    const selectedRecord = issueRecordGroups.value.find(
      (group) => group.key === selectedIssueRecordKey.value,
    )
    const scopePrefix =
      selectedRecord && selectedIssueRecordKey.value !== ALL_RECORDS_KEY
        ? `${selectedRecord.label}：`
        : ''
    const nonCompliantCount = currentItems.filter((item) => isConfirmedDefectItem(item)).length
    const uncertainCount = currentItems.filter((item) => isNeedsReviewItem(item)).length
    const dataQualityGapCount = currentItems.filter((item) => isDataQualityGapItem(item)).length
    const rejectedBySystemCount = ruleLevelSummary.value.rejectedBySystemCount
    const technicalErrorCount = currentItems.filter(
      (item) => resolveIssueCanonicalStatus(item) === 'technical_error',
    ).length
    if (isLuxian0609BatchJob.value) {
      const modeText = isLuxianScopedRun.value ? '选定质控点验证' : '全量 0609 规则集'
      return `${scopePrefix}当前展示泸县0609${modeText}结果，共 ${total} 条客户质控点结果，其中不合规 ${nonCompliantCount} 条，数据不足 ${dataQualityGapCount} 条，AI判断 ${uncertainCount} 条，技术异常 ${technicalErrorCount} 条。`
    }
    if (isPostprocessedFormalResult.value) {
      return `${scopePrefix}当前为正式质控四层准入结果，共 ${total} 条可查看结果，其中确认缺陷 ${nonCompliantCount} 条，数据缺口 ${dataQualityGapCount} 条，系统驳回 ${rejectedBySystemCount} 条，技术异常 ${technicalErrorCount} 条。原始语义判断不会直接计入确认缺陷。`
    }
    if (issueViewMode.value === 'business') {
      if (isFastScreenResult.value) {
        return `${scopePrefix}当前为快速初筛结果（摘要版），共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。可先展开完整说明，再按需进入深度复核查看全文文书。`
      }
      return `${scopePrefix}当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。默认优先阅读问题卡片，高级表格已折叠到“高级视图”。`
    }
    return `${scopePrefix}当前共 ${total} 条重点结果，其中不合规 ${nonCompliantCount} 条，AI判断 ${uncertainCount} 条。高级视图会展示完整表格和追溯字段。`
  })

  const issueSectionTitle = computed(() =>
    isLuxian0609BatchJob.value
      ? 'LX0609 客户质控点结果'
      : isPostprocessedFormalResult.value
        ? '确认缺陷/数据缺口/系统驳回'
        : '问题/AI判断明细',
  )

  const emptyIssueText = computed(() =>
    isLuxian0609BatchJob.value
      ? '暂无 LX0609 不合规、数据不足或 AI 判断结果'
      : isPostprocessedFormalResult.value
        ? '暂无确认缺陷、数据缺口或系统驳回项'
        : '暂无问题/AI判断明细',
  )

  watch(
    () => [batchJobDebugSnapshot.value?.job_id, batchJobDebugSnapshot.value?.rules?.length],
    () => {
      if (!batchJobDebugSnapshot.value) {
        selectedDebugRuleJobId.value = ''
        return
      }
      if (!selectedDebugRuleJobId.value) return
      const hasSelected = (batchJobDebugSnapshot.value.rules || []).some(
        (rule) => rule.rule_job_id === selectedDebugRuleJobId.value,
      )
      if (!hasSelected) {
        selectedDebugRuleJobId.value = ''
      }
    },
    { immediate: true },
  )

  async function handleDebugRuleChange(value: string | undefined) {
    selectedDebugRuleJobId.value = value || ''
    const jobId = props.batchJobDetail?.id
    if (!jobId || !props.fetchBatchJobDebugSnapshot) return
    await props.fetchBatchJobDebugSnapshot(jobId, {
      ruleJobId: value || undefined,
    })
  }

  function toggleClusterFilter(clusterKey: string) {
    selectedClusterKey.value = selectedClusterKey.value === clusterKey ? '' : clusterKey
    issuePagination.current = 1
    void nextTick(() => scrollToLinkedIssueRow())
  }

  function clearClusterFilter() {
    selectedClusterKey.value = ''
    issuePagination.current = 1
  }

  function handleIssueTableChange(pagination: { current?: number; pageSize?: number }) {
    issuePagination.current = Number(pagination.current || 1)
    issuePagination.pageSize = Number(pagination.pageSize || 8)
  }

  function resetIssueFilters() {
    issueFilter.value = createDefaultStructuredQCFilter()
    showAllStatuses.value = false
    issuePagination.current = 1
  }

  function resolveIssueStableKey(item?: SichuanBatchIssueItem) {
    if (!item) return ''
    return [
      item.rule_job_id || '',
      item.rule_id || item.rule_code || '',
      isLuxian0609BatchJob.value ? resolveIssueRecordKey(item) : item.record_id || '',
      isLuxian0609BatchJob.value ? '' : item.visit_id || '',
      item.trace_id || '',
    ].join('|')
  }

  function isIssueExpanded(item: SichuanBatchIssueItem) {
    const key = resolveIssueStableKey(item)
    return expandedIssueKeys.value.includes(key)
  }

  function toggleIssueExpanded(item: SichuanBatchIssueItem) {
    const key = resolveIssueStableKey(item)
    if (!key) return
    expandedIssueKeys.value = expandedIssueKeys.value.includes(key)
      ? expandedIssueKeys.value.filter((itemKey) => itemKey !== key)
      : [...expandedIssueKeys.value, key]
  }

  function stringifyTraceValue(value: unknown): string {
    if (value === null || value === undefined || value === '') return '-'
    if (Array.isArray(value)) {
      if (value.length === 0) return '-'
      return value
        .map((item) => stringifyTraceValue(item))
        .filter((item) => item && item !== '-')
        .join('；')
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value)
      } catch {
        return String(value)
      }
    }
    return String(value)
  }

  function humanizeTraceKey(key: string): string {
    const keyMap: Record<string, string> = {
      rule_id: '规则ID',
      rule_code: '规则编码',
      qc_point_id: '客户质控点',
      rule_name: '质控点名称',
      record_id: '病历号',
      visit_id: '就诊ID',
      patient_name: '患者',
      department: '科室',
      status: '状态',
      display_status: '展示状态',
      result_status: '结果状态',
      is_compliant: '合规布尔值',
      defect_level: '缺陷等级',
      findings: '质控结论',
      evidence: '证据摘要',
      suggestion: '处理建议',
      target_document_type: '目标文书',
      document_type: '文书类型',
      rule_family: '规则族',
      trace_id: 'Trace ID',
      model_version: '模型版本',
      executor_type: '执行器',
      final_status: '最终状态',
      final_decision_source: '最终状态来源',
      postprocess_label: '后处理标签',
      postprocess_reason: '后处理原因',
      first_pass_status: '初判状态',
      adjudicated_display_status: '裁决后展示状态',
      adjudicator_reason: '裁决原因',
      customer_display_guard: '客户展示保护',
      rule_requirement_match: '规则口径匹配',
      source_execution_count: '底层结果数',
      sensitive_fields_removed: '已移除敏感字段',
      raw_output_returned: '是否返回原始输出',
      note: '说明',
    }
    return keyMap[key] || key.replace(/_/g, ' ')
  }

  function traceObjectRows(value?: Record<string, unknown>, prefix = ''): ResultTraceRow[] {
    if (!value || typeof value !== 'object') return []
    return Object.entries(value)
      .filter(
        ([, item]) => item !== null && item !== undefined && stringifyTraceValue(item) !== '-',
      )
      .map(([key, item]) => ({
        key: prefix ? `${prefix}-${key}` : key,
        label: prefix ? `${prefix} · ${humanizeTraceKey(key)}` : humanizeTraceKey(key),
        value: stringifyTraceValue(item),
      }))
  }

  function traceListRows(value?: Array<Record<string, unknown>>): ResultTraceRow[] {
    if (!Array.isArray(value) || value.length === 0) return []
    return value.flatMap((item, index) =>
      traceObjectRows(item, `底层结果 ${index + 1}`).map((row) => ({
        ...row,
        key: `${index}-${row.key}`,
      })),
    )
  }

  async function openIssueTrace(item: SichuanBatchIssueItem) {
    const jobId = props.batchJobDetail?.id
    if (!jobId) {
      message.warning('当前任务缺少任务 ID，无法查看诊断追踪。')
      return
    }
    resultTraceModalOpen.value = true
    resultTraceLoading.value = true
    resultTraceError.value = ''
    resultTraceData.value = null
    const response = await getSichuanWorkspaceBatchJobResultTrace(jobId, {
      record_id: String(item.record_id || '').trim() || undefined,
      visit_id: String(item.visit_id || '').trim() || undefined,
      rule_id: String(item.qc_point_id || item.rule_id || item.rule_code || '').trim() || undefined,
    })
    resultTraceLoading.value = false
    if (!response.success || !response.data) {
      resultTraceError.value = response.message || '诊断追踪获取失败'
      message.warning(resultTraceError.value)
      return
    }
    resultTraceData.value = response.data
  }

  function closeIssueTrace() {
    resultTraceModalOpen.value = false
    resultTraceLoading.value = false
    resultTraceError.value = ''
    resultTraceData.value = null
  }

  async function openIssueDeepReview(item: SichuanBatchIssueItem) {
    selectedDeepReviewIssue.value = item
    deepReviewModalOpen.value = true
    deepReviewLoading.value = true
    deepReviewError.value = ''
    deepReviewResult.value = null
    const ruleId = String(item.rule_id || item.rule_code || '').trim()
    const instituteId = String(item.institute_id || '').trim()
    const patientId = String(item.patient_id || '').trim()
    const visitId = String(item.visit_id || '').trim()
    if (!ruleId || !instituteId || !patientId || !visitId) {
      deepReviewLoading.value = false
      deepReviewError.value = '当前结果缺少单条复核所需病历主键，无法发起深度复核。'
      return
    }
    const response = await evaluateSichuanRuleForVisit({
      rule_id: ruleId,
      institute_id: instituteId,
      patient_id: patientId,
      visit_id: visitId,
      source_schema: 'cdm',
      bundle_schema: 'public',
      force_refresh_bundle: false,
    })
    deepReviewLoading.value = false
    if (!response.success || !response.data) {
      deepReviewError.value = response.message || '深度复核失败'
      message.warning(deepReviewError.value)
      return
    }
    deepReviewResult.value = response.data
  }

  function closeDeepReviewModal() {
    deepReviewModalOpen.value = false
    selectedDeepReviewIssue.value = null
    deepReviewLoading.value = false
    deepReviewError.value = ''
    deepReviewResult.value = null
  }

  function formatProcessingTime(seconds: number) {
    const safeSeconds = Math.max(0, Number(seconds || 0))
    if (safeSeconds <= 0) return '-'
    if (safeSeconds < 60) return `${safeSeconds.toFixed(1)} 秒`
    const minutes = Math.floor(safeSeconds / 60)
    const remainSeconds = safeSeconds % 60
    return `${minutes}分${remainSeconds.toFixed(1)}秒`
  }

  function scrollToLinkedIssueRow() {
    const linkedKey = linkedIssueRowKey.value
    if (!linkedKey) return
    const row = document.querySelector<HTMLElement>(
      `.batch-issue-table tbody tr[data-row-key="${linkedKey.replace(/"/g, '\\"')}"]`,
    )
    if (row) {
      row.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }

  function normalizeBreakdownItems(items: Array<{ label: string; count: number }>) {
    return items
      .filter((item) => item.label)
      .sort((left, right) => right.count - left.count)
      .slice(0, 4)
  }

  function truncateText(text?: string, limit = 80) {
    const value = String(text || '').trim()
    if (!value) return '-'
    return value.length > limit ? `${value.slice(0, limit)}...` : value
  }

  function resolveDeepReviewText(field: 'findings' | 'evidence' | 'suggestion') {
    const text = String(
      resolvedDeepReviewResult.value?.[field] || selectedDeepReviewIssue.value?.[field] || '',
    )
    if (field === 'evidence') return resolveCustomerEvidenceText(text)
    if (field === 'findings') return sanitizeCustomerVisibleText(text)
    return sanitizeCustomerVisibleText(text)
  }

  function resolveBreakdownLabel(kind: 'executor' | 'document' | 'defect' | 'status', key: string) {
    const normalizedKey = String(key || '').trim()
    if (!normalizedKey) return '未命名'
    if (kind === 'executor') {
      const map: Record<string, string> = {
        program: '程序规则',
        llm: '语义规则',
      }
      return map[normalizedKey.toLowerCase()] || normalizedKey
    }
    if (kind === 'defect') {
      const map: Record<string, string> = {
        critical: '严重缺陷',
        major: '重大缺陷',
        moderate: '中度缺陷',
        minor: '轻微缺陷',
        high: '高风险',
        medium: '中风险',
        low: '低风险',
      }
      return map[normalizedKey.toLowerCase()] || normalizedKey
    }
    if (kind === 'status') {
      const map: Record<string, string> = {
        non_compliant: '不合规',
        ai_suggested_non_compliant: 'AI判断：疑似问题',
        uncertain: 'AI判断',
        compliant: '合规',
        ai_suggested_compliant: 'AI判断：未见问题',
        not_applicable: '不适用',
        failed: '失败',
      }
      return map[normalizedKey.toLowerCase()] || normalizedKey
    }
    return normalizedKey
  }

  function resolveStatusText(status?: string) {
    const normalized = String(status || '')
      .trim()
      .toLowerCase()
    if (normalized === 'non_compliant') return '不合规'
    if (normalized === 'ai_suggested_non_compliant') return 'AI判断：疑似问题'
    if (normalized === 'uncertain') return 'AI判断'
    if (normalized === 'ai_suggested_compliant') return 'AI判断：未见问题'
    if (normalized === 'not_applicable') return '不适用'
    if (normalized === 'data_gap') return '数据不足'
    if (normalized === 'not_executed') return '未执行'
    if (normalized === 'technical_error' || normalized === 'technical_error_internal')
      return '技术异常'
    if (normalized === 'failed') return '失败'
    return '合规'
  }

  function resolveDisplayStatusText(item?: Pick<SichuanBatchIssueItem, 'display_status'> | null) {
    if (!isPostprocessedFormalResult.value || !item?.display_status) return ''
    const normalized = String(item.display_status || '')
      .trim()
      .toLowerCase()
    if (normalized === 'confirmed_defect') return '确认缺陷'
    if (normalized === 'qc_review_candidate' || normalized === 'needs_review') return '系统驳回'
    if (normalized === 'data_quality_gap') return '数据缺口'
    if (normalized === 'rejected_by_system') return '系统驳回'
    if (normalized === 'technical_error_internal') return '内部技术异常'
    if (normalized === 'not_applicable') return '不适用'
    if (normalized === 'compliant') return '合规'
    return ''
  }

  function objectEntriesToCompactList(input: Record<string, unknown> | unknown) {
    if (!input || typeof input !== 'object') return []
    return Object.entries(input)
      .map(([label, value]) => ({
        label,
        value: formatCompactValue(value),
      }))
      .filter((item) => item.label && item.value)
      .slice(0, 8)
  }

  function formatCompactValue(value: unknown) {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string') return value.trim()
    if (typeof value === 'number' || typeof value === 'boolean') return String(value)
    if (Array.isArray(value)) {
      const list = value
        .slice(0, 3)
        .map((item) => formatCompactValue(item))
        .filter(Boolean)
      const suffix = value.length > 3 ? '…' : ''
      return list.join('、') + suffix
    }
    if (value instanceof Date) {
      return value.toISOString()
    }
    try {
      const json = JSON.stringify(value)
      return json.length > 72 ? `${json.slice(0, 72)}…` : json
    } catch {
      return String(value)
    }
  }

  function resolveIssueRowClassName(record: SichuanBatchIssueItem) {
    const linkedKey = linkedIssueRowKey.value
    const currentKey = resolveIssueStableKey(record)
    if (linkedKey && currentKey === linkedKey) return 'issue-row-highlight issue-row-linked'
    if (['uncertain', 'ai_suggested_non_compliant'].includes(resolveIssueCanonicalStatus(record)))
      return 'issue-row-uncertain'
    if (!selectedCluster.value) return ''
    return matchIssueItemWithCluster(record, selectedCluster.value) ? 'issue-row-highlight' : ''
  }

  // 聚合簇命中判定：优先规则ID/编码匹配，其次回退到证据文本匹配。
  function matchIssueItemWithCluster(
    item: SichuanBatchIssueItem,
    cluster: SichuanBatchResultAggregation['clusters'][number],
  ) {
    const clusterRuleIdSet = new Set(
      (cluster.rules || []).map((rule) => String(rule.rule_id || '').toLowerCase()).filter(Boolean),
    )
    const itemRuleCode = String(item.rule_code || '').toLowerCase()
    const itemRuleId = String(item.rule_id || '').toLowerCase()
    const byRule =
      (itemRuleId && clusterRuleIdSet.has(itemRuleId)) ||
      (itemRuleCode && clusterRuleIdSet.has(itemRuleCode))
    if (byRule) return true
    const finding = String(item.findings || '')
    const evidence = String(item.evidence || '')
    const sampleEvidence = String(cluster.sample_evidence || '').trim()
    if (sampleEvidence && (finding.includes(sampleEvidence) || evidence.includes(sampleEvidence))) {
      return true
    }
    const clusterKey = String(cluster.cluster_key || '').trim()
    if (clusterKey && (finding.includes(clusterKey) || evidence.includes(clusterKey))) {
      return true
    }
    return false
  }

  watch(
    () => [selectedClusterKey.value, displayIssueItems.value.length],
    async () => {
      if (!selectedClusterKey.value) return
      issuePagination.current = 1
      await nextTick()
      scrollToLinkedIssueRow()
    },
  )

  onMounted(() => {
    liveTicker = setInterval(() => {
      liveNow.value = Date.now()
    }, 1000)
  })

  onUnmounted(() => {
    if (liveTicker) {
      clearInterval(liveTicker)
      liveTicker = null
    }
  })

  return {
    activeRuleFilterLabel,
    advancedSectionKeys,
    advancedSummaryCards,
    aggregationBreakdownSections,
    ALL_RECORDS_KEY,
    batchJobDebugSnapshot,
    BatchResultOverview,
    BatchResultTraceModal,
    businessIssueCardGroups,
    businessIssueCards,
    canCancelBatchJob,
    cancelBatchJobLoading,
    canShowResultTrace,
    clearClusterFilter,
    closeDeepReviewModal,
    closeIssueTrace,
    confirmCancelBatchJob,
    currentDebugRule,
    currentStreamRecordLabel,
    CustomerQcResultDetailCard,
    debugDetailEntries,
    debugProgressEntries,
    debugRuleOptions,
    deepReviewError,
    deepReviewLoading,
    deepReviewModalOpen,
    displayIssueItems,
    displayRuleResults,
    emptyIssueText,
    focusedLuxianRecordLabel,
    focusedSummaryCards,
    handleDebugRuleChange,
    handleExportMenuClick,
    handleIssueTableChange,
    handleReviewBatchJobResult,
    hasEvidenceChain,
    hasStructuredText,
    incrementalResultTip,
    isFastScreenResult,
    isFocusedRecordMode,
    isFocusedSingleRecordScope,
    isIssueExpanded,
    isLuxian0609BatchJob,
    isMultiRecordIssueMode,
    isRunningBatchJob,
    isSingleRecordIssueMode,
    issueColumns,
    issueDefectLevelOptions,
    issueDocumentTypeOptions,
    issueExecutionDomainOptions,
    issueFilter,
    issueFocusSummary,
    issuePagination,
    issueRecordGroups,
    issueRecordTotalCount,
    issueSectionTitle,
    issueViewMode,
    isWaitingFirstResult,
    liveElapsedLabel,
    luxianReviewFindings,
    luxianReviewReport,
    luxianReviewSummaryText,
    mapStructuredStatusLabel,
    noIssueEvidenceItems,
    noIssueEvidenceTotalCount,
    openIssueDeepReview,
    openIssueTrace,
    progressSummary,
    QCRecordCompareWorkbench,
    recordCompareCoordinates,
    recordCompareIssues,
    resetIssueFilters,
    resolveAuditRows,
    resolveCopyEvidenceCompare,
    resolveCustomerEvidenceText,
    resolveDecisionRows,
    resolveDeepReviewText,
    resolveDependencyRows,
    resolveDisplayStatusText,
    resolveEvidenceChainItems,
    resolveEvidenceStatusText,
    resolveExecutorTypeText,
    resolveIssueCanonicalStatus,
    resolveIssueDisplayRecordRef,
    resolveIssueResultKindClass,
    resolveIssueResultKindText,
    resolveIssueReviewNavClass,
    resolveIssueRowClassName,
    resolveIssueSeverityText,
    resolveIssueStableKey,
    resolveMissingSources,
    resolveReviewRows,
    resolveStatusText,
    resolveStructuredText,
    resolveTriggerFacts,
    resultAggregation,
    resultReviewOverviewModel,
    resultTraceError,
    resultTraceLoading,
    resultTraceModalOpen,
    resultTraceSections,
    ruleColumns,
    sanitizeCustomerVisibleText,
    selectBusinessIssue,
    selectedBusinessIssueCard,
    selectedBusinessIssueKey,
    selectedClusterKey,
    selectedDebugRuleJobId,
    selectedDeepReviewIssue,
    selectedIssuePatientContext,
    selectedIssueRecordKey,
    selectRecordCompareIssue,
    shouldShowIssueRecordGroupHeader,
    showAllStatuses,
    showResultReviewOverview,
    singleIssueNavGroups,
    statusHero,
    streamUpdatedAtText,
    toggleClusterFilter,
    toggleIssueExpanded,
    topAggregationClusters,
    transfusionDocumentationSummary,
    truncateText,
    waitingFirstResultDescription,
  }
}
