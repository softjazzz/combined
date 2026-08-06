import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import type { UploadFile, UploadProps } from 'ant-design-vue'
import { InboxOutlined } from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { Compass, FilePlus2, History, Settings2, Trash2 } from 'lucide-vue-next'
import type {
  ManualSamplePool,
  ManualSamplePoolRecord,
  ManualSampleValidationMode,
  ManualSampleValidationRuleSet,
  ManualSamplePoolRunResult,
  ManualLuxian0609RuleCatalogItem,
  ManualSamplePoolSyncJob,
  SyncPhase,
} from './types'
import {
  exportLuxian0609EvaluationReport,
  getLatestManualSamplePoolSyncJob,
  getManualSamplePoolSyncJob,
  getManualSamplePoolRecords,
  importManualSamplePoolByUpload,
  listLuxian0609CustomerRules,
  listManualSampleValidationRuleSets,
  listManualSamplePools,
  matchManualSamplePool,
  runManualSamplePool,
  syncManualSamplePoolRecords,
} from '@/services/manual-case-sample-service'
import { syntheticCaseRuleFamilies } from './syntheticCaseTemplates'
import { testRecordDocumentTypeOptions } from './syntheticCaseBuilder'
import { downloadBlob, normalizeBatchExportBlob } from './batchExport'
import {
  cancelSichuanWorkspaceBatchJob,
  exportSichuanWorkspaceBatchJob,
  getSichuanWorkspaceBatchJob,
  reviewSichuanWorkspaceBatchJob,
} from '@/services/sichuan-rule-workspace-service'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'
import SemanticRulesBatchResultDrawer from '@/views/workstation-v4/semantic-rules/components/SemanticRulesBatchResultDrawer.vue'
import CustomerSampleQcTaskStatusBar from './CustomerSampleQcTaskStatusBar.vue'
import LuxianRuleScopePanel from './LuxianRuleScopePanel.vue'
import QCRecordResultComparisonDrawer from './QCRecordResultComparisonDrawer.vue'
import ReadonlyMedicalDocumentContent from './ReadonlyMedicalDocumentContent.vue'
import {
  CUSTOMER_TEST_POOL_ID,
  isFocusedRecord,
  resolveRecordCreatedDate,
  resolveRecordDisplayCode,
  resolveRecordIdentifier,
  resolveRecordPatientAvatarSrc,
  resolveRecordPatientName,
  resolveRecordPatientTitle,
  sortManualSampleRecordsForDisplay,
} from './recordPresentation'
import {
  formatEditableCopyDocumentMeta,
  formatEditableCopyOrderGroupMeta,
  isEditableOrderDocument,
  resolveEditableOrderTypeLabel,
} from './editableCopyPresentation'
import { buildBatchJobPresentation } from './batchJobPresentation'
import { useCustomerSampleEditableCopyController } from './useCustomerSampleEditableCopyController'
import { useCustomerSampleSyncPresentation } from './useCustomerSampleSyncPresentation'
import { useCustomerSampleGuide } from './useCustomerSampleGuide'
import { useCustomerSampleHospitalizationSync } from './useCustomerSampleHospitalizationSync'
import { useCustomerSamplePoolManagement } from './useCustomerSamplePoolManagement'
import { useCustomerSampleExactReview } from './useCustomerSampleExactReview'
import {
  bundleStatusHint,
  bundleStatusLabel,
  coverageLabel,
  coverageStatusText,
  formatDateTime,
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
  matchStatusHint,
  matchStatusLabel,
  resolveRecordHospitalizationBadge,
  ruleSetScopeLabel,
  summarizeRuleScopes,
  syncJobStatusColor,
  syncJobStatusText,
  validationModeLabel,
} from './customerSampleValidationPresentation'
import {
  LUXIAN_0609_RULE_SET_KEY,
  FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
  SC_SAMPLE_RULE_SET_KEY,
  PROGRAMMATIC_RULE_SET_KEY,
  LEGACY_CUSTOMER_RULE_SET_KEY,
  SAMPLE_RULE_SET_RUN_TIMEOUT_MS,
  RUN_DUPLICATE_GUARD_MS,
  LUXIAN_0609_RULE_FAMILY_DEFINITIONS,
  fallbackRuleSets,
  type LuxianRuleOption,
  type LuxianRuleFamilyView,
  type SamplePoolRunPayload,
  type LuxianFamilyRunScope,
  type LuxianAggregateJob,
  type ImportWorkflowState,
} from './customerSampleValidationConfig'
import type {
  SichuanBatchJob,
  SichuanBatchJobStatus,
} from '@/views/workstation-v4/semantic-rules/types'
import { isBatchJobCancelable } from '@/views/workstation-v4/semantic-rules/utils/batchJobStatus'

export function useCustomerSampleValidationController() {
  const {
    customerSampleGuideOpen,
    customerSampleGuideStepIndex,
    customerSampleTourCardStyle,
    customerSampleGuideSteps,
    currentCustomerSampleGuideStep,
    isLastCustomerSampleGuideStep,
    customerSampleGuideTargetClass,
    updateCustomerSampleTourCardPosition,
    openCustomerSampleGuide,
    closeCustomerSampleGuide,
    startSyntheticCaseFromGuide,
    goToCustomerSampleGuideStep,
    goToPreviousCustomerSampleGuideStep,
    goToNextCustomerSampleGuideStep,
    openInitialCustomerSampleGuide,
    stopCustomerSampleGuidePositionTimer,
  } = useCustomerSampleGuide({ openTestRecordDrawer })

  const poolLoading = ref(false)
  const route = useRoute()
  const router = useRouter()
  const itemLoading = ref(false)
  const matchLoading = ref(false)
  const runLoading = ref(false)
  const syncLoading = ref(false)
  const importingPool = ref(false)
  const selectedRowKeys = ref<string[]>([])
  const initialQueryJobHandled = ref(false)
  const initialFocusedRecordSearchHandled = ref(false)
  const importModalOpen = ref(false)
  const importFileList = ref<UploadFile[]>([])
  const pools = ref<ManualSamplePool[]>([])
  const selectedPoolId = ref<string>()
  const selectedPool = ref<ManualSamplePool>()
  const records = ref<ManualSamplePoolRecord[]>([])
  const {
    hospitalizationSyncModalOpen,
    hospitalizationSyncSubmitting,
    hospitalizationSyncPreviewLoading,
    hospitalizationSyncPreviewError,
    hospitalizationSyncPreview,
    hospitalizationSyncForm,
    hospitalizationScopeOptions,
    hospitalizationScopeNeedsDischargeRange,
    hospitalizationSyncDepartmentOptions,
    hospitalizationPreviewMetrics,
    hospitalizationSyncCanSubmit,
    hospitalizationSyncOkText,
    refreshHospitalizationScopePreview,
    openHospitalizationSyncModal,
    handleHospitalizationSync,
  } = useCustomerSampleHospitalizationSync({ selectedPoolId, openSyncJob })

  const ruleSets = ref<ManualSampleValidationRuleSet[]>(fallbackRuleSets)
  const selectedRuleSetKey = ref<string>(LUXIAN_0609_RULE_SET_KEY)
  const ruleSetDirectoryFallbackActive = ref(false)
  const internalDiagnosticKeys = ref<string[]>([])
  const selectedLuxianCustomerRuleIds = ref<string[]>([])
  const luxian0609RuleCatalog = ref<ManualLuxian0609RuleCatalogItem[]>([])
  const expandedLuxianRuleFamilyKeys = ref<string[]>([])
  const importWorkflow = ref<ImportWorkflowState | null>(null)

  const detailOpen = ref(false)
  const activeRecord = ref<ManualSamplePoolRecord>()
  const reviewDrawerVisible = ref(false)
  const reviewDrawerRecord = ref<{
    id: string
    record_id: string
    patient_name?: string
    department?: string
    discharge_date?: string
    score?: number
    defect_count?: number
    status?: string
  } | null>(null)
  const batchResultOpen = ref(false)
  const batchJobDetail = ref<SichuanBatchJob | null>(null)
  const batchJobLoading = ref(false)
  const cancelBatchJobLoading = ref(false)
  const reviewBatchJobLoadingId = ref('')
  const currentQcTask = ref<SichuanBatchJob | null>(null)
  const currentQcTaskLoading = ref(false)
  const luxianAggregateOpen = ref(false)
  const luxianAggregateLoading = ref(false)
  const luxianAggregateJobs = ref<LuxianAggregateJob[]>([])
  const luxianAggregateParentJobId = ref('')
  const luxianAggregateSummary = computed(() => {
    const total = luxianAggregateJobs.value.length
    const completed = luxianAggregateJobs.value.filter((item) => item.status === 'completed').length
    const failed = luxianAggregateJobs.value.filter((item) =>
      ['failed', 'canceled'].includes(item.status),
    ).length
    const running = luxianAggregateJobs.value.filter((item) =>
      isBatchJobRunning(item.status),
    ).length
    return {
      total,
      completed,
      failed,
      running,
    }
  })
  const luxianAggregateResultOverview = computed(() => {
    const overview = {
      nonCompliant: 0,
      review: 0,
      dataGap: 0,
      notApplicable: 0,
    }

    luxianAggregateJobs.value.forEach((item) => {
      const counts = luxianAggregateDisplayCounts(item)
      overview.nonCompliant += Number(counts.non_compliant || 0)
      overview.review +=
        Number(counts.ai_suggested_non_compliant || 0) + Number(counts.uncertain || 0)
      overview.dataGap += Number(counts.data_gap || 0)
      overview.notApplicable += Number(counts.not_applicable || 0)
    })

    return overview
  })
  const luxianAggregateHeadline = computed(() => {
    const summary = luxianAggregateSummary.value
    const overview = luxianAggregateResultOverview.value
    const completedText = `已完成 ${summary.completed} / ${summary.total} 个质控族`
    if (summary.running > 0) return `${completedText}，其余结果正在汇总。`
    if (summary.failed > 0) return `${completedText}，${summary.failed} 个质控族需查看异常。`
    const attentionCount = overview.nonCompliant + overview.review
    if (attentionCount > 0) return `${completedText}，发现 ${attentionCount} 项需要优先关注。`
    if (overview.dataGap > 0) return `${completedText}，其中 ${overview.dataGap} 项待补充资料。`
    return `${completedText}，暂未发现需要优先处理的结果。`
  })
  const luxianAggregateSortedJobs = computed(() =>
    [...luxianAggregateJobs.value].sort((left, right) => {
      const priorityDifference =
        luxianAggregateItemPriority(right) - luxianAggregateItemPriority(left)
      if (priorityDifference !== 0) return priorityDifference
      return left.family.name.localeCompare(right.family.name, 'zh-CN')
    }),
  )
  const recordResultComparisonOpen = ref(false)
  const recordResultComparisonFocus = ref<{
    visitId: string
    instituteId: string
    patientId: string
    recordId: string
    recordRef?: string
    label: string
  } | null>(null)
  let batchJobPollTimer: ReturnType<typeof setInterval> | null = null
  let currentQcTaskPollTimer: ReturnType<typeof setInterval> | null = null
  let luxianAggregatePollTimer: ReturnType<typeof setInterval> | null = null
  let syncJobPollTimer: ReturnType<typeof setInterval> | null = null
  const primaryVisibleRefreshedSyncJobs = new Set<string>()
  const syncJobDetail = ref<ManualSamplePoolSyncJob>()
  const syncDetailDrawerOpen = ref(false)
  const dismissedSyncJobId = ref('')
  const {
    exactReviewAcceptance,
    exactReviewLoading,
    exactReviewError,
    exactReviewStatusCards,
    exactReviewReasonTags,
    exactReviewBacklogBuckets,
    backlogBucketCardClass,
    backlogBucketTagClass,
    ensureExactReviewAcceptanceLoaded,
  } = useCustomerSampleExactReview()

  const pagination = ref({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  const {
    poolManagementOpen,
    poolManagementLoading,
    poolManagementQuery,
    managedPools,
    deletingPoolIds,
    poolManagementPagination,
    loadManagedPools,
    openPoolManagement,
    handlePoolManagementSearch,
    poolJobStatusLabel,
    poolDeletionDisabled,
    confirmDeletePool,
  } = useCustomerSamplePoolManagement({
    selectedPoolId,
    selectedPool,
    records,
    pagination,
    selectedRowKeys,
    loadPools,
  })

  const filters = ref({
    query: '',
    coverageType: undefined as string | undefined,
    matchStatus: undefined as string | undefined,
    includeInBatch: true,
  })
  const importForm = ref({
    poolName: '',
    description: '',
  })
  const runOptions = ref({
    maxParallelRecords: 2,
  })
  const selectedValidationMode = ref<ManualSampleValidationMode>('customer')
  const isFormalFastScreenMode = computed(
    () => selectedValidationMode.value === 'formal_fast_screen_full',
  )
  const isSyncedOnlyValidationMode = computed(
    () => selectedValidationMode.value === 'programmatic' || isFormalFastScreenMode.value,
  )
  const lastRunSubmission = ref<{
    key: string
    startedAt: number
    jobId?: string
    jobIds?: string[]
  }>()

  function formatSamplePoolOptionLabel(pool: ManualSamplePool): string {
    const name = String(pool.name || '未命名样本池').trim() || '未命名样本池'
    const total = Number(pool.total_items || 0)
    const countText = `（${total}）`
    return name.endsWith(countText) ? name : `${name}${countText}`
  }

  const poolOptions = computed(() =>
    pools.value.map((item) => ({
      label: formatSamplePoolOptionLabel(item),
      value: item.id,
    })),
  )

  const coverageOptions = [
    { label: '内涵验证', value: 'llm_intrinsic' },
    { label: '程序规则', value: 'programmatic' },
    { label: '未纳入', value: 'unsupported' },
  ]

  const matchStatusOptions = [
    { label: '已关联病历', value: 'matched' },
    { label: '待人工确认', value: 'ambiguous' },
    { label: '未找到病历', value: 'unmatched' },
  ]
  const parallelOptions = [
    { label: '1', value: 1 },
    { label: '2', value: 2 },
    { label: '4', value: 4 },
  ]
  const selectedRuleSet = computed(() => {
    return (
      ruleSets.value.find((item) => item.rule_set_key === selectedRuleSetKey.value) ||
      fallbackRuleSets.find((item) => item.rule_set_key === selectedRuleSetKey.value) ||
      fallbackRuleSets[0]
    )
  })
  const selectedRuleSetPayloadKey = computed(() =>
    selectedValidationMode.value === 'sc' ? '' : selectedRuleSet.value?.rule_set_key || '',
  )
  const isLuxian0609Mode = computed(
    () => selectedRuleSet.value?.rule_set_key === LUXIAN_0609_RULE_SET_KEY,
  )
  const luxianRuleFamilies = computed<LuxianRuleFamilyView[]>(() => {
    if (luxian0609RuleCatalog.value.length) {
      return buildLuxian0609RuleFamilies(luxian0609RuleCatalog.value)
    }
    return syntheticCaseRuleFamilies.map((family) => ({
      key: family.key,
      name: family.name,
      description: family.description,
      rules: family.rules.map((rule) => ({
        ruleId: rule.ruleId,
        name: rule.name,
        description: rule.name,
        requiredDocumentsLabel: rule.requiredDocumentsLabel,
      })),
      ruleIds: family.rules.map((rule) => rule.ruleId),
    }))
  })
  const allLuxianRuleIds = computed(() =>
    normalizeLuxianRuleIds(luxianRuleFamilies.value.flatMap((family) => family.ruleIds)),
  )
  const isAllLuxianRulesSelected = computed(() => {
    if (!allLuxianRuleIds.value.length) return false
    const selected = new Set(selectedLuxianCustomerRuleIds.value)
    return allLuxianRuleIds.value.every((ruleId) => selected.has(ruleId))
  })
  const selectedLuxianFamilyCount = computed(
    () =>
      luxianRuleFamilies.value.filter((family) => luxianRuleFamilySelectedCount(family) > 0).length,
  )
  const luxianDefaultRuleCount = computed(() => Number(selectedRuleSet.value?.rule_count || 75))
  const luxianScopeModeText = computed(() =>
    selectedLuxianCustomerRuleIds.value.length
      ? isAllLuxianRulesSelected.value
        ? `当前将运行：全部 ${selectedLuxianCustomerRuleIds.value.length} 个质控点`
        : `当前将运行：${selectedLuxianFamilyCount.value} 个质控族 · ${selectedLuxianCustomerRuleIds.value.length} 个质控点`
      : `当前将运行：全部 ${luxianDefaultRuleCount.value} 个0609质控点`,
  )
  const luxianScopeHelperText = computed(() =>
    selectedLuxianCustomerRuleIds.value.length
      ? '已限定本次质控范围；只会验证勾选的 LX0609 质控点。'
      : `未选择时默认运行全部 ${luxianDefaultRuleCount.value} 个 0609 质控点；也可按质控族快速限定范围。`,
  )
  const mainRuleSets = computed(() =>
    ruleSets.value.filter((item) => !item.advanced && (item.display_group || 'main') === 'main'),
  )
  const selectedRuleSetRuleCountText = computed(() => {
    const count = Number(selectedRuleSet.value?.rule_count || 0)
    return count > 0 ? `${count} 条` : '动态规则数'
  })
  const selectedRuleSetCoverageChips = computed(() => {
    const summary = selectedRuleSet.value?.coverage_summary || {}
    const entries = Object.entries(summary)
    const gate = selectedRuleSet.value?.release_gate_summary
    const evaluation = selectedRuleSet.value?.evaluation_summary
    const freshness = selectedRuleSet.value?.artifact_freshness
    const extraChips: Array<{ label: string; value: string | number; className: string }> = []
    if (selectedRuleSet.value?.rule_set_key === LUXIAN_0609_RULE_SET_KEY) {
      if (freshness?.status && freshness.status !== 'fresh') {
        extraChips.push({
          label: '验收工件',
          value: '需刷新',
          className: 'border-amber-200 bg-amber-50 text-amber-700',
        })
      }
      if (gate) {
        extraChips.push({
          label: gate.release_ready ? '发布闸门' : '闸门未过',
          value: gate.release_ready
            ? '通过'
            : `${Number(gate.passed_checks || 0)}/${Number(gate.passed_checks || 0) + Number(gate.failed_checks || 0) + Number(gate.unverified_checks || 0)}`,
          className: gate.release_ready
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : 'border-rose-200 bg-rose-50 text-rose-700',
        })
      }
      if (evaluation) {
        extraChips.push(
          {
            label: '三类样本齐备',
            value: Number(evaluation.rules_with_all_case_types || 0),
            className:
              Number(evaluation.rules_with_all_case_types || 0) > 0
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-amber-200 bg-amber-50 text-amber-700',
          },
          {
            label: '命中',
            value: Number(evaluation.hit_count || 0),
            className: 'border-sky-200 bg-sky-50 text-sky-700',
          },
          {
            label: '误报',
            value: Number(evaluation.false_positive_count || 0),
            className:
              Number(evaluation.false_positive_count || 0) > 0
                ? 'border-rose-200 bg-rose-50 text-rose-700'
                : 'border-slate-200 bg-slate-50 text-slate-600',
          },
          {
            label: '漏报',
            value: Number(evaluation.false_negative_count || 0),
            className:
              Number(evaluation.false_negative_count || 0) > 0
                ? 'border-rose-200 bg-rose-50 text-rose-700'
                : 'border-slate-200 bg-slate-50 text-slate-600',
          },
          {
            label: '不可判定',
            value: Number(evaluation.unknown_count || 0),
            className:
              Number(evaluation.unknown_count || 0) > 0
                ? 'border-amber-200 bg-amber-50 text-amber-700'
                : 'border-slate-200 bg-slate-50 text-slate-600',
          },
        )
      }
      const pageClosure = selectedRuleSet.value?.page_closure_summary
      if (pageClosure) {
        const capabilityCount = Number(pageClosure.capability_count || 0)
        const passedCapabilities = Number(pageClosure.passed_capabilities || 0)
        extraChips.push({
          label: pageClosure.page_verified ? '页面闭环' : '页面待闭环',
          value: capabilityCount > 0 ? `${passedCapabilities}/${capabilityCount}` : '-',
          className: pageClosure.page_verified
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : 'border-amber-200 bg-amber-50 text-amber-700',
        })
      }
    }
    if (!entries.length) {
      return [
        {
          label: '覆盖状态',
          value: coverageStatusText(selectedRuleSet.value),
          className: 'border-sky-200 bg-sky-50 text-sky-700',
        },
        ...extraChips,
      ]
    }
    return [
      ...extraChips,
      ...entries.map(([label, value]) => ({
        label,
        value,
        className:
          label.includes('待补') || label.includes('联查')
            ? 'border-amber-200 bg-amber-50 text-amber-700'
            : label.includes('近似')
              ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700',
      })),
    ]
  })

  const workflowSteps = computed(() => {
    const pool = selectedPool.value
    const runnableValue = isLuxian0609Mode.value
      ? (pool?.matched_items ?? 0)
      : isSyncedOnlyValidationMode.value
        ? (pool?.matched_items ?? 0)
        : (pool?.ready_items ?? 0)
    return [
      {
        label: '匹配',
        value: pool?.matched_items ?? 0,
        className: (pool?.matched_items ?? 0) > 0 ? 'is-ready' : '',
      },
      {
        label: isSyncedOnlyValidationMode.value ? '同步' : '就绪',
        value: runnableValue,
        className: runnableValue > 0 ? 'is-ready' : '',
      },
      {
        label: '已选',
        value: selectedRecordStats.value.selectedCount,
        className: selectedRecordStats.value.selectedCount > 0 ? 'is-active' : '',
      },
    ]
  })

  const summaryCards = computed(() => {
    const pool = selectedPool.value
    const runnableValue = isLuxian0609Mode.value
      ? (pool?.matched_items ?? 0)
      : isSyncedOnlyValidationMode.value
        ? (pool?.matched_items ?? 0)
        : (pool?.ready_items ?? 0)
    let runnableHelp = '文书已就绪，可直接开始当前模式质控'
    if (isLuxian0609Mode.value) {
      runnableHelp = '已关联真实病历即可开始0609质控；可再限定 LX0609 质控点范围'
    } else if (isFormalFastScreenMode.value) {
      runnableHelp = '已匹配且已同步，可开始正式 84 条质控'
    } else if (selectedValidationMode.value === 'programmatic') {
      runnableHelp = '已匹配且已同步，可直接开始程序规则验证'
    }
    const latestStatus = pool?.latest_job_status
    return [
      { label: '样本总数', value: pool?.total_items ?? 0, help: '当前样本池导入的记录数' },
      {
        label: '已匹配病历',
        value: pool?.matched_items ?? 0,
        help: '已映射到系统病历主键的样本数',
      },
      {
        label: '可质控病历',
        value: runnableValue,
        help: runnableHelp,
      },
      {
        label: '最近任务状态',
        value: latestStatus ? getBatchJobStatusText(latestStatus) : '暂无',
        help: '可在“更多”中查看最近任务详情',
      },
    ]
  })

  const {
    syncProgress,
    syncCustomerStepText,
    syncHospitalizationSummary,
    syncRecordProgress,
    syncResolvedStats,
    customerFacingSyncError,
    syncResultNotice,
    showSyncStatusBar,
    syncStatusBar,
    stopSyncStatusAutoHideTimer,
  } = useCustomerSampleSyncPresentation({
    syncJobDetail,
    dismissedSyncJobId,
    selectedPool,
    records,
    isRecordSyncedForValidation,
    isSyncJobRunning,
  })

  const importWorkflowSteps = computed(() => {
    const workflow = importWorkflow.value
    if (!workflow) return []
    const isImported = workflow.importedRows > 0
    const isMatched =
      workflow.status === 'matched' ||
      workflow.status === 'syncing' ||
      workflow.status === 'synced' ||
      workflow.status === 'sync_failed'
    const hasNoMatch = workflow.status === 'no_match'
    return [
      {
        label: '1. 导入样本 ID',
        description: isImported ? `已读取 ${workflow.importedRows} 条 ID。` : '等待上传模板。',
        className: isImported
          ? 'border-sky-200 bg-sky-50 text-sky-800'
          : 'border-slate-200 bg-slate-50 text-slate-500',
      },
      {
        label: '2. 匹配源库病历',
        description: workflow.matching
          ? '正在按就诊ID、住院号、病案号匹配源库。'
          : hasNoMatch
            ? '未匹配到病历，请检查 ID 类型或医院数据源配置。'
            : `匹配 ${workflow.matched} 份，待确认 ${workflow.ambiguous} 份，未找到 ${workflow.unmatched} 份。`,
        className: workflow.matching
          ? 'border-blue-200 bg-blue-50 text-blue-800'
          : hasNoMatch
            ? 'border-amber-200 bg-amber-50 text-amber-800'
            : isMatched
              ? 'border-sky-200 bg-sky-50 text-sky-800'
              : 'border-slate-200 bg-slate-50 text-slate-500',
      },
      {
        label: '3. 同步病历文书',
        description:
          workflow.status === 'syncing'
            ? '同步任务已创建，请在下方查看进度。'
            : workflow.status === 'synced'
              ? workflow.message
              : workflow.status === 'sync_failed'
                ? workflow.message
                : workflow.matched > 0
                  ? '可开始同步匹配到的病历文书。'
                  : '匹配到病历后才能同步文书。',
        className:
          workflow.status === 'syncing'
            ? 'border-blue-200 bg-blue-50 text-blue-800'
            : workflow.status === 'sync_failed'
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : workflow.status === 'synced' || workflow.matched > 0
                ? 'border-sky-200 bg-sky-50 text-sky-800'
                : 'border-slate-200 bg-slate-50 text-slate-500',
      },
    ]
  })

  const currentScopeDescription = computed(() => {
    const total = pagination.value.total || 0
    const matched = records.value.filter((record) => record.match_status === 'matched').length
    const ready = records.value.filter((record) => record.bundle_status === 'ready').length
    const synced = records.value.filter((record) => isRecordSyncedForValidation(record)).length
    const filterLabels = [
      `验证规则集：${selectedRuleSet.value?.rule_set_name || validationModeLabel(selectedValidationMode.value)}`,
      filters.value.coverageType ? `样本范围：${coverageLabel(filters.value.coverageType)}` : '',
      filters.value.matchStatus ? `病历关联：${matchStatusLabel(filters.value.matchStatus)}` : '',
      !isSyncedOnlyValidationMode.value && filters.value.includeInBatch ? '仅看首批样本' : '',
    ].filter(Boolean)
    const base = isLuxian0609Mode.value
      ? `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份，可按全量或选定 LX0609 质控点发起验证。`
      : isSyncedOnlyValidationMode.value
        ? `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份、已同步 ${synced} 份。`
        : `当前列表展示的是去重后的真实病历池，共 ${total} 份病历；其中已关联 ${matched} 份，文书已就绪 ${ready} 份。`
    if (!filterLabels.length) {
      return `${base} ${runnableRequirementHint()}`
    }
    return `${base} 当前筛选：${filterLabels.join('，')}。${runnableRequirementHint()}`
  })

  const selectedRecordStats = computed(() => {
    const selectedRecords = records.value.filter((record) =>
      selectedRowKeys.value.includes(record.id),
    )
    const runnableRecords = selectedRecords.filter((record) => isRunnableRecord(record))
    const blockerCounts = selectedRecords.reduce(
      (counts, record) => {
        if (record.match_status === 'ambiguous') {
          counts.ambiguous += 1
        } else if (record.match_status !== 'matched' || !record.matched_visit_id) {
          counts.unmatched += 1
        } else if (!isRecordSyncedForValidation(record)) {
          counts.notSynced += 1
        } else if (
          (isLuxian0609Mode.value ||
            selectedValidationMode.value === 'customer' ||
            selectedValidationMode.value === 'sc') &&
          record.bundle_status !== 'ready'
        ) {
          counts.bundleNotReady += 1
        }
        return counts
      },
      {
        ambiguous: 0,
        unmatched: 0,
        notSynced: 0,
        bundleNotReady: 0,
      },
    )
    return {
      selectedCount: selectedRecords.length,
      runnableCount: runnableRecords.length,
      blockedCount: Math.max(0, selectedRecords.length - runnableRecords.length),
      blockerCounts,
      runnableRecordIds: runnableRecords
        .map((record) => String(record.matched_visit_id || '').trim())
        .filter((recordId) => Boolean(recordId)),
    }
  })

  const requiresSelectedRecords = computed(
    () => isFormalFastScreenMode.value || isLuxian0609Mode.value,
  )

  const runButtonDisabled = computed(
    () => runLoading.value || !selectedPoolId.value || !selectedPool.value?.total_items,
  )

  const runButtonActionText = computed(() =>
    isFormalFastScreenMode.value
      ? '开始SC质控'
      : isLuxian0609Mode.value
        ? '开始0609质控'
        : '开始样本验证',
  )

  const runButtonText = computed(() =>
    isFormalFastScreenMode.value
      ? selectedRecordStats.value.selectedCount > 0
        ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
        : '请先选择病历'
      : isLuxian0609Mode.value
        ? selectedRecordStats.value.selectedCount > 0
          ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
          : '请先选择病历'
        : selectedRecordStats.value.selectedCount > 0
          ? `${runButtonActionText.value}（已选 ${selectedRecordStats.value.selectedCount} 份）`
          : runButtonActionText.value,
  )

  const selectedRunScopeSummary = computed(() => {
    if (!isLuxian0609Mode.value) return validationModeLabel(selectedValidationMode.value)
    if (!selectedLuxianCustomerRuleIds.value.length) return '全量0609'
    const selected = new Set(selectedLuxianCustomerRuleIds.value)
    const fullFamilies = luxianRuleFamilies.value.filter(
      (family) =>
        family.ruleIds.length > 0 && family.ruleIds.every((ruleId) => selected.has(ruleId)),
    )
    if (fullFamilies.length > 0) {
      const allSelectedRuleIds = new Set(fullFamilies.flatMap((family) => family.ruleIds))
      const hasOnlyFullFamilies = selectedLuxianCustomerRuleIds.value.every((ruleId) =>
        allSelectedRuleIds.has(ruleId),
      )
      if (hasOnlyFullFamilies) return `已选${fullFamilies.length}个规则族`
    }
    return `已选${selectedLuxianCustomerRuleIds.value.length}个质控点`
  })

  const paginationConfig = computed(() => ({
    current: pagination.value.page,
    pageSize: pagination.value.pageSize,
    total: pagination.value.total,
    showSizeChanger: true,
    showTotal: (total: number) => `共 ${total} 条`,
    onChange: (page: number, pageSize: number) => {
      pagination.value.page = page
      pagination.value.pageSize = pageSize
      loadRecords()
    },
  }))

  const tableEmptyText = computed(() => `${emptyTitle.value}。${emptyDescription.value}`)

  const emptyTitle = computed(() => {
    if (!selectedPoolId.value) return '请先选择样本池'
    if (!selectedPool.value?.matched_items) return '当前还没有匹配成功的病历'
    if (!pagination.value.total) return '当前筛选条件下没有样本'
    return '暂无样本数据'
  })

  const emptyDescription = computed(() => {
    if (!selectedPoolId.value) {
      return '先选择一个客户样本池，再查看问题样本和匹配状态。'
    }
    if (!selectedPool.value?.matched_items) {
      return '请先执行病历匹配，并确认当前环境已经同步到客户真实病历数据。'
    }
    if (!pagination.value.total) {
      return '可以放宽覆盖类型、匹配状态或关闭“仅首批”后重新查询。'
    }
    return '当前没有可展示的样本。'
  })

  const itemColumns: TableColumnsType<ManualSamplePoolRecord> = [
    {
      title: '编号',
      key: 'record_code',
      width: 150,
      customRender: ({ record }) =>
        h(
          'span',
          {
            class: 'customer-sample-record-code',
            title: resolveRecordIdentifier(record),
          },
          resolveRecordDisplayCode(record),
        ),
    },
    {
      title: '病历',
      key: 'patient',
      width: 300,
      customRender: ({ record }) => {
        const hospitalizationBadge = resolveRecordHospitalizationBadge(record)
        const hospitalizationBadgeStyle = {
          display: 'inline-flex',
          minHeight: '22px',
          flex: '0 0 auto',
          alignItems: 'center',
          border: '1px solid transparent',
          borderRadius: '999px',
          padding: '1px 8px',
          fontSize: '11px',
          fontWeight: '650',
          lineHeight: '18px',
          whiteSpace: 'nowrap',
          ...(hospitalizationBadge.status === 'active'
            ? {
                borderColor: 'rgba(0, 102, 204, 0.14)',
                background: 'rgba(0, 102, 204, 0.075)',
                color: '#0057b8',
              }
            : hospitalizationBadge.status === 'discharged'
              ? {
                  borderColor: 'rgba(71, 85, 105, 0.14)',
                  background: 'rgba(71, 85, 105, 0.07)',
                  color: '#475569',
                }
              : {
                  borderColor: 'rgba(217, 119, 6, 0.14)',
                  background: 'rgba(245, 158, 11, 0.08)',
                  color: '#a16207',
                }),
        }
        return h(
          'div',
          {
            class: 'customer-sample-patient-cell',
            style: {
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              minWidth: '0',
            },
          },
          [
            h('img', {
              class: 'customer-sample-patient-avatar',
              src: resolveRecordPatientAvatarSrc(record),
              alt: `${resolveRecordPatientName(record) === '-' ? '患者' : resolveRecordPatientName(record)}头像`,
              style: {
                width: '24px',
                height: '24px',
                flex: '0 0 24px',
                borderRadius: '999px',
                objectFit: 'cover',
              },
            }),
            h(
              'div',
              {
                class: 'customer-sample-patient-summary',
                title: resolveRecordPatientTitle(record),
                style: {
                  display: 'flex',
                  minWidth: '0',
                  alignItems: 'center',
                  gap: '8px',
                },
              },
              [
                h(
                  'span',
                  {
                    class: 'customer-sample-patient-name',
                    style: {
                      overflow: 'hidden',
                      maxWidth: '174px',
                      color: 'var(--customer-sample-text)',
                      fontSize: '14px',
                      fontWeight: '700',
                      lineHeight: '20px',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    },
                  },
                  resolveRecordPatientTitle(record),
                ),
                h(
                  'span',
                  {
                    class: [
                      'customer-sample-hospitalization-badge',
                      `is-${hospitalizationBadge.status}`,
                    ],
                    title: hospitalizationBadge.title,
                    style: hospitalizationBadgeStyle,
                  },
                  hospitalizationBadge.label,
                ),
              ],
            ),
          ],
        )
      },
    },
    {
      title: '创建日期',
      key: 'created_time',
      width: 120,
      customRender: ({ record }) =>
        h(
          'span',
          { class: 'customer-sample-created-time' },
          resolveRecordCreatedDate(record) || '-',
        ),
    },
    {
      title: '科室',
      dataIndex: 'department',
      width: 120,
      customRender: ({ value }) =>
        h('span', { class: 'customer-sample-department' }, String(value || '-')),
    },
    {
      title: '操作',
      key: 'actions',
      width: 310,
      customRender: ({ record }) =>
        h('div', { class: 'customer-sample-action-cell' }, buildRecordActions(record)),
    },
  ]

  const rowSelection = computed(() => ({
    selectedRowKeys: selectedRowKeys.value,
    onChange: (keys) => {
      selectedRowKeys.value = keys.map((key) => String(key))
    },
  }))

  const {
    editableCopyOpen,
    editableCopyLoading,
    editableCopySaving,
    editableCopySaveAndRunLoading,
    editableCopyReadonly,
    editableCopySourceRecord,
    editableCopyDraft,
    editableCopyNewDocumentType,
    editableCopyDocumentQuery,
    editableCopyDocumentFilter,
    editableCopyOrderTypeFilter,
    editableCopyEnabledDocumentCount,
    editableCopyVisibleOrderRows,
    editableCopyFilteredDocuments,
    editableCopyDocumentGroups,
    editableCopyActiveDocument,
    openMedicalRecordViewer,
    selectEditableCopyDocument,
    selectEditableCopyOrderGroup,
    isEditableCopyDocumentGroupExpanded,
    toggleEditableCopyDocumentGroup,
    addEditableCopyDocument,
    addEditableCopyOrderDocument,
    removeEditableCopyDocument,
    openEditableCopyDrawer,
    closeEditableCopyDrawer,
    saveEditableCopy,
  } = useCustomerSampleEditableCopyController({
    selectedPool,
    selectedPoolId,
    pools,
    selectedValidationMode,
    selectedRuleSetPayloadKey,
    isLuxian0609Mode,
    selectedLuxianCustomerRuleIds,
    normalizeLuxianRuleIds,
    loadPools,
    loadRecords,
    openBatchJob,
  })

  function ruleSetCardClass(ruleSet: ManualSampleValidationRuleSet): string {
    return ruleSet.rule_set_key === selectedRuleSetKey.value ? 'is-selected' : ''
  }

  function summarizeRecordScope(record: ManualSamplePoolRecord): string {
    const labels = (record.document_scope_labels || []).filter(Boolean)
    if (labels.length) {
      return labels.join(' / ')
    }
    if (selectedValidationMode.value === 'formal_fast_screen_full') {
      return '正式终末全量内涵 84 条'
    }
    if (selectedValidationMode.value === 'programmatic') {
      return '样本硬门槛程序规则包 v1'
    }
    if (selectedValidationMode.value === 'customer') {
      return selectedRuleSet.value?.rule_set_name || '客户专项规则包'
    }
    return summarizeRuleScopes(record.candidate_rule_ids || [])
  }

  function recordScopeHint(record: ManualSamplePoolRecord): string {
    if (selectedValidationMode.value === 'formal_fast_screen_full') {
      return '当前按正式终末全量内涵 84 条执行，不依赖单条样本候选规则。'
    }
    if ((record.document_scope_labels || []).length > 0) {
      return '已按当前病历实际同步到的文书类型识别验证范围。'
    }
    if (selectedValidationMode.value === 'programmatic') {
      return '当前按固定硬门槛程序规则包执行，不再依赖单条样本候选规则。'
    }
    if (selectedValidationMode.value === 'customer') {
      return '当前按选中的客户验证规则集执行，原始 Excel 问题仅作为对照上下文保留。'
    }
    if ((record.candidate_rule_ids || []).length > 0) {
      return '当前仍按样本问题推断范围，待同步后会自动刷新。'
    }
    return '当前还没有可识别的文书范围。'
  }

  function buildRecordActions(record: ManualSamplePoolRecord) {
    const actions = []
    if (record.matched_visit_id) {
      actions.push(
        h(
          'button',
          {
            type: 'button',
            class: 'customer-sample-secondary-link',
            onClick: () => openMedicalRecordViewer(record),
          },
          '查看病历',
        ),
      )
    }
    if (record.matched_visit_id) {
      actions.push(
        h(
          'button',
          {
            type: 'button',
            class: 'customer-sample-secondary-link',
            onClick: () => openRecordLatestBatchJob(record),
          },
          '查看结果',
        ),
      )
    }
    if (record.matched_visit_id && record.bundle_status === 'ready') {
      actions.push(
        h(
          'button',
          {
            type: 'button',
            class: 'customer-sample-secondary-link',
            onClick: () => openEditableCopyDrawer(record),
          },
          '创建副本',
        ),
      )
    }
    return actions
  }

  function isRecordSyncedForValidation(record: ManualSamplePoolRecord): boolean {
    return record.sync_status === 'synced' || record.sync_status === 'synthetic_seeded'
  }

  function isRunnableRecord(record: ManualSamplePoolRecord): boolean {
    if (isLuxian0609Mode.value) {
      return (
        record.match_status === 'matched' &&
        isRecordSyncedForValidation(record) &&
        record.bundle_status === 'ready' &&
        !!record.matched_visit_id
      )
    }
    if (isSyncedOnlyValidationMode.value) {
      return (
        record.match_status === 'matched' &&
        isRecordSyncedForValidation(record) &&
        !!record.matched_visit_id
      )
    }
    return (
      record.match_status === 'matched' &&
      isRecordSyncedForValidation(record) &&
      record.bundle_status === 'ready' &&
      !!record.matched_visit_id
    )
  }

  function runnableRequirementHint(): string {
    if (isLuxian0609Mode.value) {
      return '泸县0609支持从已关联真实病历直接发起验证；选择质控族/质控点只限定规则范围，不会限制样本池或病历选择。'
    }
    if (selectedValidationMode.value === 'formal_fast_screen_full') {
      return '未关联真实病历或尚未同步到本地 PG 的病历不会进入正式质控；若后台 final scope 收集不到，会返回终末病历未同步错误。'
    }
    if (selectedValidationMode.value === 'programmatic') {
      return '未关联到真实病历或尚未同步的病历不会进入程序规则批量验证。'
    }
    return '未关联到真实病历或文书未就绪的病历不会进入当前规则集验证。'
  }

  function selectedRecordNotRunnableMessage(): string {
    if (isLuxian0609Mode.value) {
      return '当前选中的病历还未完成病历关联，暂时无法开始0609质控'
    }
    if (selectedValidationMode.value === 'formal_fast_screen_full') {
      return '当前选中的病历还未完成匹配或同步，暂时无法发起正式质控 84 条'
    }
    if (selectedValidationMode.value === 'programmatic') {
      return '当前选中的病历还未完成匹配或同步，暂时无法发起程序规则验证'
    }
    return '当前选中的病历还未完成匹配、同步或 bundle 准备，暂时无法发起验证'
  }

  function selectedRecordBlockerMessage(): string {
    const { selectedCount, blockerCounts } = selectedRecordStats.value
    const reasons = [
      blockerCounts.ambiguous > 0 ? `匹配有歧义 ${blockerCounts.ambiguous} 份` : '',
      blockerCounts.unmatched > 0 ? `未关联病历 ${blockerCounts.unmatched} 份` : '',
      blockerCounts.notSynced > 0 ? `尚未同步 ${blockerCounts.notSynced} 份` : '',
      blockerCounts.bundleNotReady > 0 ? `病历包未就绪 ${blockerCounts.bundleNotReady} 份` : '',
    ].filter(Boolean)
    return `已选 ${selectedCount} 份病历，完整范围未提交：${reasons.join('，')}。请处理后重试`
  }

  function clearSelectedRecords() {
    selectedRowKeys.value = []
  }

  function scrollToLuxianScope() {
    const target = document.getElementById('customer-sample-luxian-scope')
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function normalizeRuleSetKey(
    ruleSetKey: unknown,
    validationMode: ManualSampleValidationMode,
  ): string {
    const normalizedKey = String(ruleSetKey || '').trim()
    if (normalizedKey) return normalizedKey
    if (validationMode === 'sc') return SC_SAMPLE_RULE_SET_KEY
    return normalizedKey
  }

  function normalizeRuleSetItem(raw: ManualSampleValidationRuleSet): ManualSampleValidationRuleSet {
    const validationMode = normalizeValidationMode(raw.validation_mode || 'customer')
    const ruleIds = Array.isArray(raw.rule_ids)
      ? raw.rule_ids.map((item) => String(item))
      : undefined
    const ruleCount = Number(raw.rule_count ?? ruleIds?.length ?? 0)
    const ruleSetKey = normalizeRuleSetKey(raw.rule_set_key, validationMode)
    return {
      ...raw,
      rule_set_key: ruleSetKey,
      rule_set_name: String(raw.rule_set_name || ruleSetKey || validationModeLabel(validationMode)),
      rule_set_version: String(raw.rule_set_version || 'v1'),
      scope: String(
        raw.scope || (validationMode === 'formal_fast_screen_full' ? 'final' : 'running'),
      ),
      rule_ids: ruleIds,
      rule_count: Number.isFinite(ruleCount) ? ruleCount : 0,
      validation_mode: validationMode,
      advanced: Boolean(raw.advanced),
      display_group: raw.display_group || (raw.advanced ? 'advanced' : 'main'),
    }
  }

  function buildRuleSetDirectory(
    items: ManualSampleValidationRuleSet[],
  ): ManualSampleValidationRuleSet[] {
    const fallbackByKey = new Map(fallbackRuleSets.map((item) => [item.rule_set_key, item]))
    const mergedByKey = new Map<string, ManualSampleValidationRuleSet>()
    for (const item of fallbackRuleSets) {
      mergedByKey.set(item.rule_set_key, item)
    }
    for (const raw of items) {
      const normalized = normalizeRuleSetItem(raw)
      if (!normalized.rule_set_key) continue
      const fallback = fallbackByKey.get(normalized.rule_set_key)
      mergedByKey.set(normalized.rule_set_key, {
        ...(fallback || {}),
        ...normalized,
        advanced: normalized.advanced ?? fallback?.advanced ?? false,
        display_group: normalized.display_group || fallback?.display_group || 'main',
      })
    }
    const priority = [
      LUXIAN_0609_RULE_SET_KEY,
      FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
      SC_SAMPLE_RULE_SET_KEY,
      PROGRAMMATIC_RULE_SET_KEY,
      LEGACY_CUSTOMER_RULE_SET_KEY,
    ]
    return Array.from(mergedByKey.values()).sort((left, right) => {
      const leftIndex = priority.indexOf(left.rule_set_key)
      const rightIndex = priority.indexOf(right.rule_set_key)
      const leftRank = leftIndex >= 0 ? leftIndex : priority.length
      const rightRank = rightIndex >= 0 ? rightIndex : priority.length
      if (leftRank !== rightRank) return leftRank - rightRank
      if (Boolean(left.advanced) !== Boolean(right.advanced)) return left.advanced ? 1 : -1
      return left.rule_set_name.localeCompare(right.rule_set_name, 'zh-CN')
    })
  }

  function normalizeLuxianCatalogRule(
    rule: ManualLuxian0609RuleCatalogItem,
  ): LuxianRuleOption | null {
    const ruleId = normalizeLuxianRuleIds([rule.rule_id || rule.rule_code || ''])[0]
    if (!ruleId) return null
    const requiredDocumentsLabel =
      rule.required_documents_label ||
      (Array.isArray(rule.applicable_document_labels)
        ? rule.applicable_document_labels.join('、')
        : '')
    return {
      ruleId,
      name: String(rule.name || rule.description || ruleId).trim() || ruleId,
      description: String(rule.description || rule.name || '').trim(),
      requiredDocumentsLabel: String(requiredDocumentsLabel || '').trim(),
    }
  }

  function buildLuxian0609RuleFamilies(
    rules: ManualLuxian0609RuleCatalogItem[],
  ): LuxianRuleFamilyView[] {
    const ruleById = new Map<string, LuxianRuleOption>()
    rules.forEach((rule) => {
      const normalized = normalizeLuxianCatalogRule(rule)
      if (normalized) {
        ruleById.set(normalized.ruleId, normalized)
      }
    })
    const usedRuleIds = new Set<string>()
    const families: LuxianRuleFamilyView[] = LUXIAN_0609_RULE_FAMILY_DEFINITIONS.map((family) => {
      const familyRules = family.ruleIds
        .map((ruleId) => ruleById.get(ruleId))
        .filter((rule): rule is LuxianRuleOption => Boolean(rule))
      familyRules.forEach((rule) => usedRuleIds.add(rule.ruleId))
      return {
        key: family.key,
        name: family.name,
        description: family.description,
        rules: familyRules,
        ruleIds: familyRules.map((rule) => rule.ruleId),
      }
    }).filter((family) => family.rules.length > 0)

    const uncategorizedRules = Array.from(ruleById.values())
      .filter((rule) => !usedRuleIds.has(rule.ruleId))
      .sort((left, right) => left.ruleId.localeCompare(right.ruleId))
    if (uncategorizedRules.length) {
      families.push({
        key: 'other',
        name: '其他',
        description: '后端目录中未归入固定业务族的 LX0609 质控点。',
        rules: uncategorizedRules,
        ruleIds: uncategorizedRules.map((rule) => rule.ruleId),
      })
    }
    return families
  }

  function openTestRecordDrawer() {
    const selectedRuleIds = isLuxian0609Mode.value
      ? normalizeLuxianRuleIds(selectedLuxianCustomerRuleIds.value)
      : []
    const routeTarget: { name: string; query?: Record<string, string> } = {
      name: 'WorkstationV4SyntheticCaseNew',
    }
    if (selectedRuleIds.length) {
      routeTarget.query = {
        ruleIds: selectedRuleIds.join(','),
        ruleFamily: resolveLuxianRuleFamilyKey(selectedRuleIds),
      }
    }
    router.push(routeTarget)
  }

  function toggleInternalDiagnostic() {
    const shouldOpen = !internalDiagnosticKeys.value.includes('sheet2')
    internalDiagnosticKeys.value = shouldOpen ? ['sheet2'] : []
    if (shouldOpen) {
      void ensureExactReviewAcceptanceLoaded()
    }
  }

  function isSheet2DiagnosticOpen(keys: string | string[]) {
    return Array.isArray(keys) ? keys.includes('sheet2') : keys === 'sheet2'
  }

  function handleInternalDiagnosticChange(keys: string | string[]) {
    if (isSheet2DiagnosticOpen(keys)) {
      void ensureExactReviewAcceptanceLoaded()
    }
  }

  async function loadRuleSets() {
    const result = await listManualSampleValidationRuleSets()
    if (!result.success || !result.data) {
      ruleSets.value = fallbackRuleSets
      ruleSetDirectoryFallbackActive.value = true
      applyValidationModeEffects(
        normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
      )
      return
    }
    const mergedRuleSets = buildRuleSetDirectory(result.data.items || [])
    ruleSets.value = mergedRuleSets.length > 0 ? mergedRuleSets : fallbackRuleSets
    ruleSetDirectoryFallbackActive.value = mergedRuleSets.length === 0
    if (!ruleSets.value.some((item) => item.rule_set_key === selectedRuleSetKey.value)) {
      selectedRuleSetKey.value = LUXIAN_0609_RULE_SET_KEY
    }
    applyValidationModeEffects(
      normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
    )
  }

  async function loadLuxian0609RuleCatalog() {
    const result = await listLuxian0609CustomerRules()
    if (!result.success || !result.data) {
      luxian0609RuleCatalog.value = []
      return
    }
    luxian0609RuleCatalog.value = Array.isArray(result.data.rules) ? result.data.rules : []
  }

  async function loadPools(options: { refreshSyncJob?: boolean; loadRecords?: boolean } = {}) {
    const { refreshSyncJob = true, loadRecords: shouldLoadRecords = true } = options
    poolLoading.value = true
    const result = await listManualSamplePools({ page: 1, page_size: 100 })
    poolLoading.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '获取样本池失败')
      return
    }
    pools.value = result.data.items
    const queryPoolId = String(route?.query?.poolId || '').trim()
    if (queryPoolId && pools.value.some((item) => item.id === queryPoolId)) {
      selectedPoolId.value = queryPoolId
    }
    if (selectedPoolId.value && !pools.value.some((item) => item.id === selectedPoolId.value)) {
      selectedPoolId.value = undefined
    }
    if (!selectedPoolId.value && pools.value.length > 0) {
      selectedPoolId.value = pools.value[0].id
    }
    selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
    if (selectedPoolId.value) {
      if (refreshSyncJob) {
        await loadLatestSyncJob()
      }
      if (shouldLoadRecords) {
        await loadRecords()
      }
      await openInitialQueryJob()
    }
  }

  async function loadRecords() {
    if (!selectedPoolId.value) {
      records.value = []
      pagination.value.total = 0
      return
    }
    itemLoading.value = true
    const result = await getManualSamplePoolRecords(selectedPoolId.value, {
      coverage_type: filters.value.coverageType,
      match_status: filters.value.matchStatus,
      include_in_batch_1: isSyncedOnlyValidationMode.value
        ? undefined
        : filters.value.includeInBatch,
      q: filters.value.query || undefined,
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    })
    itemLoading.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '获取样本明细失败')
      return
    }
    selectedPool.value = result.data.pool
    const focusedRecordId = String(route?.query?.recordId || '').trim()
    records.value = sortManualSampleRecordsForDisplay(
      result.data.items,
      selectedPoolId.value,
      focusedRecordId,
    )
    pagination.value.total = result.data.total
    if (
      focusedRecordId &&
      !initialFocusedRecordSearchHandled.value &&
      !records.value.some((record) => isFocusedRecord(record, focusedRecordId))
    ) {
      initialFocusedRecordSearchHandled.value = true
      filters.value.query = focusedRecordId
      pagination.value.page = 1
      await loadRecords()
      return
    }
    selectedRowKeys.value = selectedRowKeys.value.filter((key) =>
      records.value.some((item) => item.id === key),
    )
  }

  async function openInitialQueryJob() {
    if (initialQueryJobHandled.value) return
    const jobId = String(route?.query?.jobId || '').trim()
    if (!jobId) return
    initialQueryJobHandled.value = true
    message.info('验证任务已创建，正在打开任务进度')
    await openBatchJob(jobId)
  }

  async function handlePoolChange() {
    pagination.value.page = 1
    selectedRowKeys.value = []
    selectedPool.value = pools.value.find((item) => item.id === selectedPoolId.value)
    if (importWorkflow.value && importWorkflow.value.poolId !== selectedPoolId.value) {
      importWorkflow.value = null
    }
    await loadLatestSyncJob()
    await loadRecords()
    await restoreCurrentQcTaskForSelectedPool()
  }

  function normalizeValidationMode(mode: string | number): ManualSampleValidationMode {
    const value = String(mode)
    if (value === 'formal_fast_screen_full') return 'formal_fast_screen_full'
    if (value === 'programmatic') return 'programmatic'
    if (value === 'sc') return 'sc'
    return 'customer'
  }

  function applyValidationModeEffects(normalizedMode: ManualSampleValidationMode) {
    selectedValidationMode.value = normalizedMode
    if (normalizedMode === 'programmatic') {
      filters.value.coverageType = 'programmatic'
      filters.value.includeInBatch = false
    } else if (normalizedMode === 'formal_fast_screen_full') {
      filters.value.coverageType = undefined
      filters.value.includeInBatch = false
    } else if (normalizedMode === 'sc' && filters.value.coverageType === 'programmatic') {
      filters.value.coverageType = 'llm_intrinsic'
      filters.value.includeInBatch = true
    } else {
      filters.value.includeInBatch = true
    }
  }

  function normalizeLuxianRuleIds(ruleIds: string[]): string[] {
    return Array.from(
      new Set(
        ruleIds
          .map((ruleId) =>
            String(ruleId || '')
              .trim()
              .toUpperCase(),
          )
          .filter((ruleId) => /^LX0609-\d{3}$/u.test(ruleId)),
      ),
    ).sort()
  }

  function resolveLuxianRuleFamilyKey(ruleIds: string[]): string {
    const normalizedRuleIds = normalizeLuxianRuleIds(ruleIds)
    if (!normalizedRuleIds.length) return ''
    const normalizedSet = new Set(normalizedRuleIds)
    const exactFamily = luxianRuleFamilies.value.find(
      (family) =>
        family.ruleIds.length > 0 && family.ruleIds.every((ruleId) => normalizedSet.has(ruleId)),
    )
    if (exactFamily) return exactFamily.key
    return (
      luxianRuleFamilies.value.find((family) =>
        family.ruleIds.some((ruleId) => normalizedSet.has(ruleId)),
      )?.key || ''
    )
  }

  function toggleLuxianRule(ruleId: string) {
    const normalizedRuleId = normalizeLuxianRuleIds([ruleId])[0]
    if (!normalizedRuleId) return
    const current = new Set(selectedLuxianCustomerRuleIds.value)
    if (current.has(normalizedRuleId)) {
      current.delete(normalizedRuleId)
    } else {
      current.add(normalizedRuleId)
    }
    selectedLuxianCustomerRuleIds.value = normalizeLuxianRuleIds([...current])
  }

  function luxianRuleFamilySelectedCount(family: LuxianRuleFamilyView): number {
    const current = new Set(selectedLuxianCustomerRuleIds.value)
    return normalizeLuxianRuleIds(family.ruleIds).filter((ruleId) => current.has(ruleId)).length
  }

  function isLuxianRuleFamilyExpanded(familyKey: string): boolean {
    return expandedLuxianRuleFamilyKeys.value.includes(familyKey)
  }

  function toggleLuxianRuleFamilyExpanded(familyKey: string) {
    if (isLuxianRuleFamilyExpanded(familyKey)) {
      expandedLuxianRuleFamilyKeys.value = expandedLuxianRuleFamilyKeys.value.filter(
        (key) => key !== familyKey,
      )
      return
    }
    expandedLuxianRuleFamilyKeys.value = [...expandedLuxianRuleFamilyKeys.value, familyKey]
  }

  function selectLuxianRuleFamily(ruleIds: string[]) {
    const normalizedRuleIds = normalizeLuxianRuleIds(ruleIds)
    const current = new Set(selectedLuxianCustomerRuleIds.value)
    if (normalizedRuleIds.every((ruleId) => current.has(ruleId))) {
      normalizedRuleIds.forEach((ruleId) => current.delete(ruleId))
    } else {
      normalizedRuleIds.forEach((ruleId) => current.add(ruleId))
    }
    selectedLuxianCustomerRuleIds.value = normalizeLuxianRuleIds([...current])
  }

  function toggleAllLuxianRuleFamilies() {
    selectedLuxianCustomerRuleIds.value = isAllLuxianRulesSelected.value
      ? []
      : normalizeLuxianRuleIds(allLuxianRuleIds.value)
  }

  function clearLuxianRuleScope() {
    selectedLuxianCustomerRuleIds.value = []
  }

  function buildLuxianFamilyRunScopes(ruleIds: string[]): LuxianFamilyRunScope[] {
    const selectedRuleIds = normalizeLuxianRuleIds(ruleIds)
    if (!selectedRuleIds.length) return []
    const selectedSet = new Set(selectedRuleIds)
    const coveredRuleIds = new Set<string>()
    const scopes = luxianRuleFamilies.value
      .map((family) => {
        const familyRuleIds = normalizeLuxianRuleIds(family.ruleIds).filter((ruleId) =>
          selectedSet.has(ruleId),
        )
        familyRuleIds.forEach((ruleId) => coveredRuleIds.add(ruleId))
        return {
          key: family.key,
          name: family.name,
          ruleIds: familyRuleIds,
        }
      })
      .filter((scope) => scope.ruleIds.length > 0)

    const orphanRuleIds = selectedRuleIds.filter((ruleId) => !coveredRuleIds.has(ruleId))
    if (orphanRuleIds.length) {
      scopes.push({
        key: 'other',
        name: '其他质控点',
        ruleIds: orphanRuleIds,
      })
    }
    return scopes
  }

  function shouldRunLuxianFamiliesInParallel(ruleIds: string[]): boolean {
    return isLuxian0609Mode.value && buildLuxianFamilyRunScopes(ruleIds).length > 1
  }

  async function handleRuleSetChange(ruleSetKey: string | number) {
    const nextKey = String(ruleSetKey || '').trim() || LUXIAN_0609_RULE_SET_KEY
    selectedRuleSetKey.value = nextKey
    applyValidationModeEffects(
      normalizeValidationMode(selectedRuleSet.value?.validation_mode || 'customer'),
    )
    if (!isLuxian0609Mode.value) {
      clearLuxianRuleScope()
    }
    pagination.value.page = 1
    selectedRowKeys.value = []
    await loadRecords()
  }

  async function handleValidationModeChange(mode: ManualSampleValidationMode | string | number) {
    const normalizedMode = normalizeValidationMode(mode)
    const matchedRuleSet =
      ruleSets.value.find(
        (item) => item.advanced && normalizeValidationMode(item.validation_mode) === normalizedMode,
      ) ||
      fallbackRuleSets.find(
        (item) => item.advanced && normalizeValidationMode(item.validation_mode) === normalizedMode,
      ) ||
      ruleSets.value.find(
        (item) => normalizeValidationMode(item.validation_mode) === normalizedMode,
      ) ||
      fallbackRuleSets.find(
        (item) => normalizeValidationMode(item.validation_mode) === normalizedMode,
      )
    selectedRuleSetKey.value = matchedRuleSet?.rule_set_key || LUXIAN_0609_RULE_SET_KEY
    await handleRuleSetChange(selectedRuleSetKey.value)
  }

  async function handleMoreActionKey(key: string) {
    if (key === 'import') {
      importModalOpen.value = true
      return
    }
    if (key === 'create-test-record') {
      openTestRecordDrawer()
      return
    }
    if (key === 'refresh') {
      await loadPools()
      return
    }
    if (key === 'sync') {
      await handleSyncPoolRecords()
      return
    }
    if (key === 'sync-by-hospitalization') {
      await openHospitalizationSyncModal()
      return
    }
    if (key === 'match') {
      await handleMatchPool()
      return
    }
    if (key === 'latest') {
      await openLatestJob()
      return
    }
    if (key === 'surgery-catalog') {
      await router.push({ name: 'WorkstationV4SurgeryProcedureCatalog' })
      return
    }
    if (key === 'export-luxian-md') {
      await handleExportLuxianReport('md')
      return
    }
    if (key === 'export-luxian-csv') {
      await handleExportLuxianReport('csv')
      return
    }
    if (key === 'export-luxian-json') {
      await handleExportLuxianReport('json')
      return
    }
    if (key === 'mode-sc') {
      await handleValidationModeChange('sc')
      return
    }
    if (key === 'mode-programmatic') {
      await handleValidationModeChange('programmatic')
      return
    }
    if (key === 'mode-legacy-customer') {
      selectedRuleSetKey.value = LEGACY_CUSTOMER_RULE_SET_KEY
      await handleRuleSetChange(selectedRuleSetKey.value)
    }
  }

  async function handleExportLuxianReport(format: 'md' | 'csv' | 'json') {
    const result = await exportLuxian0609EvaluationReport(format)
    if (!result.success || !result.data) {
      message.error(result.message || '导出泸县0609质控点评估报告失败')
      return
    }
    const blob = new Blob([result.data], {
      type:
        format === 'json'
          ? 'application/json;charset=utf-8'
          : format === 'csv'
            ? 'text/csv;charset=utf-8'
            : 'text/markdown;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `泸县0609质控点评估报告.${format}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    message.success('泸县0609质控点评估报告已导出')
  }

  function resetFilters() {
    filters.value = {
      query: '',
      coverageType: undefined,
      matchStatus: undefined,
      includeInBatch: !isSyncedOnlyValidationMode.value,
    }
    pagination.value.page = 1
    selectedRowKeys.value = []
    loadRecords()
  }

  function resetImportForm() {
    importModalOpen.value = false
    importForm.value = {
      poolName: '',
      description: '',
    }
    importFileList.value = []
  }

  const handleImportFileSelect: UploadProps['beforeUpload'] = (file) => {
    importFileList.value = [
      {
        uid: file.uid,
        name: file.name,
        status: 'done',
        size: file.size,
        type: file.type,
        originFileObj: file,
      },
    ]
    return false
  }

  async function handleImportPool() {
    const poolName = importForm.value.poolName.trim()
    const file = importFileList.value[0]?.originFileObj
    if (!poolName) {
      message.warning('请先填写样本池名称')
      return
    }
    if (!file) {
      message.warning('请先上传 Excel 模板')
      return
    }
    importingPool.value = true
    const result = await importManualSamplePoolByUpload({
      pool_name: poolName,
      description: importForm.value.description.trim(),
      scene: 'running',
      file,
    })
    importingPool.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '导入客户样本模板失败')
      return
    }
    selectedPoolId.value = result.data.id
    importWorkflow.value = {
      poolId: result.data.id,
      poolName: result.data.name || poolName,
      importedRows: Number(result.data.imported_rows || 0),
      matching: true,
      matched: 0,
      ambiguous: 0,
      unmatched: 0,
      status: 'matching',
      message: '已导入样本 ID，正在自动匹配源库病历...',
    }
    resetImportForm()
    message.success(`导入成功，共写入 ${result.data.imported_rows} 条样本，正在匹配源库病历`)
    await loadPools()
    await runPoolMatch({ source: 'import' })
  }

  async function handleDownloadTemplate() {
    const XLSX = await import('xlsx')
    const workbook = XLSX.utils.book_new()
    const worksheet = XLSX.utils.aoa_to_sheet([
      ['就诊ID', '住院流水号', '病案号', '患者姓名', '备注'],
      ['1870471', 'IP0000135258', '362948', '蒲云鹏', '示例：优先填写就诊ID'],
      ['1430048', '', '', '', '没有住院流水号/病案号时，可只填就诊ID'],
    ])
    worksheet['!cols'] = [{ wch: 18 }, { wch: 20 }, { wch: 16 }, { wch: 14 }, { wch: 34 }]
    XLSX.utils.book_append_sheet(workbook, worksheet, '样本ID')

    const instructionSheet = XLSX.utils.aoa_to_sheet([
      ['字段', '是否必填', '说明'],
      ['就诊ID', '推荐必填', '最可靠的匹配字段，对应源库 visit_id。'],
      ['住院流水号', '可选', '对应源库 inpat_no，例如 IP0000135258。'],
      ['病案号', '可选', '对应源库 mr_no，例如 362948。'],
      ['患者姓名', '可选', '只用于辅助确认，不作为唯一匹配键。'],
      ['备注', '可选', '客户自定义来源或批次说明。'],
    ])
    instructionSheet['!cols'] = [{ wch: 16 }, { wch: 12 }, { wch: 48 }]
    XLSX.utils.book_append_sheet(workbook, instructionSheet, '填写说明')
    XLSX.writeFile(workbook, '客户样本导入模板.xlsx')
  }

  function formatMatchSummary(matched: number, ambiguous: number, unmatched: number) {
    return `匹配 ${matched} 份，待人工确认 ${ambiguous} 份，未找到 ${unmatched} 份`
  }

  async function runPoolMatch(options: { source: 'import' | 'manual' | 'workflow' }) {
    void options
    if (!selectedPoolId.value) return
    matchLoading.value = true
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        matching: true,
        status: 'matching',
        message: '正在按就诊ID、住院号、病案号匹配源库病历...',
      }
    }
    const result = await matchManualSamplePool(selectedPoolId.value)
    matchLoading.value = false
    if (!result.success) {
      if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
        importWorkflow.value = {
          ...importWorkflow.value,
          matching: false,
          status: 'match_failed',
          message: result.message || '病历匹配失败，请检查源库连接或稍后重试。',
        }
      }
      message.error(result.message || '执行病历匹配失败')
      return
    }
    const matched = Number(result.data?.matched ?? 0)
    const ambiguous = Number(result.data?.ambiguous ?? 0)
    const unmatched = Number(result.data?.unmatched ?? 0)
    const summary = formatMatchSummary(matched, ambiguous, unmatched)
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        matching: false,
        matched,
        ambiguous,
        unmatched,
        status: matched > 0 ? 'matched' : 'no_match',
        message:
          matched > 0
            ? '已匹配到源库病历，可以开始同步病历文书。'
            : '未匹配到病历，请检查 ID 类型或医院数据源配置。',
      }
    }
    if (matched > 0) {
      message.success(summary)
    } else {
      message.warning(`${summary}。未匹配到病历，请检查 ID 类型或医院数据源配置。`)
    }
    await loadPools()
  }

  async function handleMatchPool() {
    await runPoolMatch({ source: 'manual' })
  }

  async function handleSyncPoolRecords() {
    if (!selectedPoolId.value) return
    syncLoading.value = true
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        status: 'syncing',
        message: '同步任务已创建后会在下方展示进度。',
      }
    }
    const limitToIntrinsic = !isSyncedOnlyValidationMode.value
    const result = await syncManualSamplePoolRecords(selectedPoolId.value, {
      only_intrinsic: limitToIntrinsic,
      include_in_batch_1: limitToIntrinsic,
    })
    syncLoading.value = false
    if (!result.success || !result.data) {
      if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
        importWorkflow.value = {
          ...importWorkflow.value,
          status: importWorkflow.value.matched > 0 ? 'matched' : 'no_match',
          message: result.message || '同步任务创建失败，请检查源库连接或稍后重试。',
        }
      }
      message.error(result.message || '同步样本病历失败')
      return
    }
    if (importWorkflow.value && importWorkflow.value.poolId === selectedPoolId.value) {
      importWorkflow.value = {
        ...importWorkflow.value,
        status: 'syncing',
        message: '同步任务已创建，请在下方查看进度。',
      }
    }
    message.success('样本病历同步任务已创建')
    await openSyncJob(result.data.job_id)
  }

  function openSyncDetailDrawer() {
    if (!syncJobDetail.value) return
    syncDetailDrawerOpen.value = true
  }

  function dismissSyncStatusBar() {
    const jobId = String(syncJobDetail.value?.id || '')
    if (!jobId || isSyncJobRunning(syncJobDetail.value?.status)) return
    dismissedSyncJobId.value = jobId
  }

  async function handleRetrySync() {
    if (!syncJobDetail.value || syncLoading.value) return
    syncDetailDrawerOpen.value = false
    const summary = syncJobDetail.value.summary || {}
    if (summary.hospitalization_scope || summary.admission_filter) {
      await openHospitalizationSyncModal()
      return
    }
    await handleSyncPoolRecords()
  }

  async function handleRunPool() {
    if (runLoading.value) return
    if (!selectedPoolId.value) return
    const { selectedCount, runnableCount, blockedCount, runnableRecordIds } =
      selectedRecordStats.value
    if (requiresSelectedRecords.value && selectedCount === 0) {
      message.warning('请先选择要质控的病历')
      return
    }
    if (selectedCount > 0 && blockedCount > 0) {
      message.warning(selectedRecordBlockerMessage())
      return
    }
    if (selectedCount > 0 && runnableCount === 0) {
      message.warning(selectedRecordNotRunnableMessage())
      return
    }
    const runKey = buildRunSubmissionKey(
      selectedPoolId.value,
      selectedRuleSetPayloadKey.value,
      selectedValidationMode.value,
      runnableRecordIds,
      isLuxian0609Mode.value ? selectedLuxianCustomerRuleIds.value : [],
    )
    const now = Date.now()
    if (
      lastRunSubmission.value?.key === runKey &&
      now - lastRunSubmission.value.startedAt < RUN_DUPLICATE_GUARD_MS
    ) {
      const reusableJobId = lastRunSubmission.value.jobId || lastRunSubmission.value.jobIds?.[0]
      if (reusableJobId) {
        message.info('任务已创建，正在执行质控')
        await trackCurrentQcTask(reusableJobId)
      } else {
        message.info('正式84条质控任务已提交，正在准备执行')
      }
      return
    }
    runLoading.value = true
    lastRunSubmission.value = {
      key: runKey,
      startedAt: now,
    }
    const creatingMessage = isLuxian0609Mode.value
      ? '正在创建泸县0609验证任务...'
      : isFormalFastScreenMode.value
        ? '正式84条质控任务已提交，正在准备执行'
        : '正在创建样本验证任务...'
    message.loading({
      content: creatingMessage,
      key: runKey,
      duration: 0,
    })
    const runPayload: SamplePoolRunPayload = {
      record_ids: runnableRecordIds,
      max_parallel_records: runOptions.value.maxParallelRecords,
      validation_mode: selectedValidationMode.value,
      rule_set_key: selectedRuleSetPayloadKey.value,
    }
    if (isLuxian0609Mode.value && selectedLuxianCustomerRuleIds.value.length) {
      runPayload.selected_rule_ids = selectedLuxianCustomerRuleIds.value
    }
    if (shouldRunLuxianFamiliesInParallel(selectedLuxianCustomerRuleIds.value)) {
      await runLuxianFamilyScopedJobs({
        runKey,
        startedAt: now,
        basePayload: runPayload,
      })
      return
    }
    const result = await runManualSamplePool(
      selectedPoolId.value,
      runPayload,
      requiresSelectedRecords.value ? { timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS } : undefined,
    )
    if (!result.success || !result.data) {
      if (
        requiresSelectedRecords.value &&
        (result.errorType === 'timeout' || result.errorType === 'network')
      ) {
        message.info('请求等待较久，正在确认后台任务状态')
        const recovered = await recoverRunAfterSlowRequest({
          poolId: selectedPoolId.value,
          recordIds: runnableRecordIds,
          startedAt: now,
          previousJobId: selectedPool.value?.latest_job_id,
          runKey,
          ruleSetKey: selectedRuleSetPayloadKey.value,
          selectedRuleIds: isLuxian0609Mode.value ? selectedLuxianCustomerRuleIds.value : [],
        })
        runLoading.value = false
        if (recovered) {
          return
        }
      } else {
        runLoading.value = false
      }
      message.destroy(runKey)
      if (lastRunSubmission.value?.key === runKey && !lastRunSubmission.value.jobId) {
        lastRunSubmission.value = undefined
      }
      message.error(result.message || '创建样本验证任务失败')
      return
    }
    runLoading.value = false
    lastRunSubmission.value = {
      key: runKey,
      startedAt: now,
      jobId: result.data.job_id,
    }
    const ruleSetName = String(
      result.data.rule_set_name || validationModeLabel(selectedValidationMode.value),
    ).trim()
    const ruleSetKey = String(result.data.rule_set_key || '').trim()
    const ruleSetDisplay = ruleSetKey ? `${ruleSetKey} / ${ruleSetName}` : ruleSetName
    message.success({
      content: `任务已创建，正在打开进度。${ruleSetDisplay}，覆盖 ${result.data.sample_item_count} 条样本 / ${result.data.record_count} 份病历 / ${result.data.rule_count} 条规则，并发 ${runOptions.value.maxParallelRecords} 份病历`,
      key: runKey,
      duration: 3,
    })
    selectedRowKeys.value = []
    await trackCurrentQcTask(result.data.job_id)
    void loadPools()
  }

  async function runLuxianFamilyScopedJobs(options: {
    runKey: string
    startedAt: number
    basePayload: SamplePoolRunPayload
  }) {
    const familyScopes = buildLuxianFamilyRunScopes(selectedLuxianCustomerRuleIds.value)
    const scopedPayload: SamplePoolRunPayload = {
      ...options.basePayload,
      group_by_luxian_family: true,
      selected_rule_ids: selectedLuxianCustomerRuleIds.value,
    }
    const result = await runManualSamplePool(
      selectedPoolId.value,
      scopedPayload,
      requiresSelectedRecords.value ? { timeout: SAMPLE_RULE_SET_RUN_TIMEOUT_MS } : undefined,
    )
    if (!result.success || !result.data) {
      runLoading.value = false
      message.destroy(options.runKey)
      lastRunSubmission.value = undefined
      message.error(result.message || '创建泸县0609总任务失败')
      return
    }

    runLoading.value = false
    const jobId = String(result.data.job_id || '').trim()
    const childJobIds = Array.isArray(result.data.child_job_ids)
      ? result.data.child_job_ids.map((item) => String(item)).filter(Boolean)
      : []
    lastRunSubmission.value = {
      key: options.runKey,
      startedAt: options.startedAt,
      jobId,
      jobIds: [jobId, ...childJobIds],
    }
    message.success({
      content: `已创建泸县0609总任务，${familyScopes.length} 个质控族已并发入队`,
      key: options.runKey,
      duration: 4,
    })
    selectedRowKeys.value = []
    await trackCurrentQcTask(jobId)
    void loadPools()
  }

  function buildRunSubmissionKey(
    poolId: string,
    ruleSetKey: string,
    validationMode: ManualSampleValidationMode,
    recordIds: string[],
    selectedRuleIds: string[] = [],
  ): string {
    const normalizedRecordIds = recordIds.map((item) => String(item)).sort()
    const normalizedRuleIds = normalizeLuxianRuleIds(selectedRuleIds)
    return [
      poolId,
      ruleSetKey || '-',
      validationMode,
      normalizedRecordIds.join(',') || 'all',
      normalizedRuleIds.join(',') || 'full',
    ].join('|')
  }

  function isCloseToRunStart(createdAt: string | undefined, startedAt: number): boolean {
    if (!createdAt) return true
    const createdTime = new Date(createdAt).getTime()
    if (Number.isNaN(createdTime)) return false
    return Math.abs(createdTime - startedAt) <= 5 * 60 * 1000
  }

  function isSameRecordScope(job: SichuanBatchJob, recordIds: string[]): boolean {
    if (!recordIds.length || !Array.isArray(job.record_ids) || !job.record_ids.length) {
      return true
    }
    const expected = recordIds
      .map((item) => String(item))
      .sort()
      .join('|')
    const actual = job.record_ids
      .map((item) => String(item))
      .sort()
      .join('|')
    return expected === actual
  }

  function resolveRecordResultFocus(record: ManualSamplePoolRecord) {
    return {
      visitId: String(record.matched_visit_id || '').trim(),
      instituteId: String(record.matched_institute_id || '').trim(),
      patientId: String(record.matched_patient_id || '').trim(),
      recordId: resolveRecordIdentifier(record),
      label: [
        resolveRecordPatientName(record) === '-' ? '' : resolveRecordPatientName(record),
        record.department || '',
        resolveRecordIdentifier(record),
      ]
        .filter(Boolean)
        .join(' · '),
    }
  }

  async function openRecordLatestBatchJob(record: ManualSamplePoolRecord) {
    const focus = resolveRecordResultFocus(record)
    if (!focus.visitId) {
      message.warning('这份病历尚未匹配源库，暂无可查看的质控结果')
      return
    }
    openRecordResultComparison(focus)
  }

  function openRecordResultComparison(
    focus: NonNullable<typeof recordResultComparisonFocus.value>,
  ) {
    recordResultComparisonFocus.value = focus
    recordResultComparisonOpen.value = true
  }

  function closeRecordResultComparison() {
    recordResultComparisonOpen.value = false
    recordResultComparisonFocus.value = null
  }

  function isSameLuxianRuleScope(job: SichuanBatchJob, selectedRuleIds: string[]): boolean {
    const expected = normalizeLuxianRuleIds(selectedRuleIds)
    const filters = job.filters && typeof job.filters === 'object' ? job.filters : {}
    const actual = normalizeLuxianRuleIds(
      Array.isArray(filters.selected_rule_ids)
        ? filters.selected_rule_ids.map((item) => String(item))
        : [],
    )
    if (!expected.length) {
      return actual.length === 0
    }
    return expected.join('|') === actual.join('|')
  }

  function isRecoverableRunJob(
    job: SichuanBatchJob,
    recordIds: string[],
    startedAt: number,
    ruleSetKey = FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
    selectedRuleIds: string[] = [],
  ): boolean {
    return (
      job.rule_set_key === ruleSetKey &&
      isSameRecordScope(job, recordIds) &&
      isSameLuxianRuleScope(job, selectedRuleIds) &&
      isCloseToRunStart(job.created_at, startedAt)
    )
  }

  async function recoverRunAfterSlowRequest(options: {
    poolId: string
    recordIds: string[]
    startedAt: number
    previousJobId?: string
    runKey: string
    ruleSetKey: string
    selectedRuleIds?: string[]
  }): Promise<boolean> {
    await loadPools()
    const refreshedPool = pools.value.find((item) => item.id === options.poolId)
    const latestJobId = refreshedPool?.latest_job_id
    if (!latestJobId || latestJobId === options.previousJobId) {
      return false
    }
    const jobResult = await getSichuanWorkspaceBatchJob(latestJobId)
    if (!jobResult.success || !jobResult.data) {
      return false
    }
    if (
      !isRecoverableRunJob(
        jobResult.data,
        options.recordIds,
        options.startedAt,
        options.ruleSetKey,
        options.selectedRuleIds || [],
      )
    ) {
      return false
    }
    lastRunSubmission.value = {
      key: options.runKey,
      startedAt: options.startedAt,
      jobId: latestJobId,
    }
    message.success({
      content: '任务已创建，正在执行质控',
      key: options.runKey,
      duration: 3,
    })
    await trackCurrentQcTask(latestJobId)
    return true
  }

  async function openLatestJob() {
    if (!selectedPool.value?.latest_job_id) return
    await openBatchJob(selectedPool.value.latest_job_id)
  }

  function updateCurrentQcTask(job: SichuanBatchJob) {
    if (!currentQcTask.value || currentQcTask.value.id === job.id) {
      currentQcTask.value = job
    }
  }

  async function trackCurrentQcTask(jobId: string, options: { showError?: boolean } = {}) {
    const normalizedJobId = String(jobId || '').trim()
    stopCurrentQcTaskPolling()
    if (!normalizedJobId) {
      currentQcTask.value = null
      return
    }
    if (currentQcTask.value?.id !== normalizedJobId) {
      currentQcTask.value = null
    }
    currentQcTaskLoading.value = true
    try {
      const result = await getSichuanWorkspaceBatchJob(normalizedJobId)
      if (!result.success || !result.data) {
        currentQcTask.value = null
        if (options.showError) {
          message.error(result.message || '获取当前质控任务失败')
        }
        return
      }
      currentQcTask.value = result.data
      if (
        isBatchJobRunning(result.data.status) &&
        !batchResultOpen.value &&
        !luxianAggregateOpen.value
      ) {
        startCurrentQcTaskPolling(normalizedJobId)
      }
    } finally {
      currentQcTaskLoading.value = false
    }
  }

  async function restoreCurrentQcTaskForSelectedPool() {
    await trackCurrentQcTask(String(selectedPool.value?.latest_job_id || ''))
  }

  function openTaskHistoryPage() {
    void router.push({ name: 'WorkstationV4CustomerSampleValidationTasks' })
  }

  async function handleReviewCurrentTask(jobId: string) {
    const job = currentQcTask.value
    if (!job || job.id !== jobId) return
    await handleReviewTaskHistoryJob(job)
  }

  function handleExportCurrentTask(jobId: string) {
    const job = currentQcTask.value
    if (!job || job.id !== jobId) return
    handleExportTaskHistoryJob(job)
  }

  function resolveLuxianFamilyFromChildJob(
    job: SichuanBatchJob,
    fallbackIndex = 0,
  ): LuxianFamilyRunScope {
    const filters = job.filters && typeof job.filters === 'object' ? job.filters : {}
    const ruleIds = normalizeLuxianRuleIds(
      Array.isArray(filters.scoped_customer_rule_ids)
        ? filters.scoped_customer_rule_ids.map((item) => String(item))
        : Array.isArray(filters.selected_rule_ids)
          ? filters.selected_rule_ids.map((item) => String(item))
          : [],
    )
    const familyKey = String(
      job.family_key || filters.family_key || `family-${fallbackIndex + 1}`,
    ).trim()
    const familyName = String(
      job.family_name || filters.family_name || `质控族 ${fallbackIndex + 1}`,
    ).trim()
    return {
      key: familyKey,
      name: familyName,
      ruleIds,
    }
  }

  function buildLuxianAggregateJobsFromParentJob(parentJob: SichuanBatchJob): LuxianAggregateJob[] {
    const childJobs = Array.isArray(parentJob.child_jobs)
      ? parentJob.child_jobs
      : Array.isArray(parentJob.children)
        ? parentJob.children
        : []
    if (childJobs.length > 0) {
      return childJobs
        .map((childJob, index) => ({
          family: resolveLuxianFamilyFromChildJob(childJob, index),
          jobId: String(childJob.id || '').trim(),
          status: childJob.status,
          detail: childJob,
          errorMessage: '',
        }))
        .filter((item) => item.jobId)
    }
    const filters =
      parentJob.filters && typeof parentJob.filters === 'object' ? parentJob.filters : {}
    const familyScopes = Array.isArray(filters.family_scopes)
      ? (filters.family_scopes as Array<Record<string, unknown>>)
      : []
    const childJobIds = Array.isArray(parentJob.child_job_ids)
      ? parentJob.child_job_ids.map((item) => String(item)).filter(Boolean)
      : []
    return childJobIds.map((jobId, index) => {
      const familyScope = familyScopes[index] || {}
      return {
        family: {
          key: String(familyScope.key || `family-${index + 1}`),
          name: String(familyScope.name || `质控族 ${index + 1}`),
          ruleIds: normalizeLuxianRuleIds(
            Array.isArray(familyScope.rule_ids)
              ? familyScope.rule_ids.map((item) => String(item))
              : [],
          ),
        },
        jobId,
        status: 'queued' as SichuanBatchJobStatus,
      }
    })
  }

  async function openLuxianAggregateParentJob(
    parentJobId: string,
    initialRunResult?: ManualSamplePoolRunResult,
  ) {
    stopCurrentQcTaskPolling()
    stopLuxianAggregatePolling()
    luxianAggregateParentJobId.value = parentJobId
    if (Array.isArray(initialRunResult?.child_jobs) && initialRunResult.child_jobs.length > 0) {
      luxianAggregateJobs.value = buildLuxianAggregateJobsFromParentJob({
        id: parentJobId,
        status: 'queued',
        scope: 'all',
        rule_code: '',
        rule_name: '',
        filters: {
          family_scopes: initialRunResult.family_scopes || [],
        },
        child_job_ids: initialRunResult.child_job_ids || [],
        child_jobs: initialRunResult.child_jobs,
      })
    } else {
      luxianAggregateJobs.value = (initialRunResult?.child_job_ids || []).map((jobId, index) => {
        const familyScope = Array.isArray(initialRunResult?.family_scopes)
          ? initialRunResult.family_scopes[index]
          : undefined
        return {
          family: {
            key: String(familyScope?.key || `family-${index + 1}`),
            name: String(familyScope?.name || `质控族 ${index + 1}`),
            ruleIds: normalizeLuxianRuleIds(
              Array.isArray(familyScope?.rule_ids)
                ? familyScope.rule_ids.map((item) => String(item))
                : [],
            ),
          },
          jobId: String(jobId),
          status: 'queued' as SichuanBatchJobStatus,
        }
      })
    }
    luxianAggregateOpen.value = true
    void refreshLuxianAggregateJobs(parentJobId)
    startLuxianAggregatePolling()
  }

  async function refreshLuxianAggregateJobs(parentJobId?: string) {
    const effectiveParentJobId = parentJobId || luxianAggregateParentJobId.value
    if (!luxianAggregateJobs.value.length && !effectiveParentJobId) return
    luxianAggregateLoading.value = true
    try {
      if (effectiveParentJobId) {
        const parentResult = await getSichuanWorkspaceBatchJob(effectiveParentJobId)
        if (parentResult.success && parentResult.data) {
          updateCurrentQcTask(parentResult.data)
          const aggregateJobs = buildLuxianAggregateJobsFromParentJob(parentResult.data)
          if (aggregateJobs.length > 0) {
            luxianAggregateJobs.value = aggregateJobs
          }
        }
      }
      const nextJobs = await Promise.all(
        luxianAggregateJobs.value.map(async (item) => {
          if (!item.jobId) return item
          const result = await getSichuanWorkspaceBatchJob(item.jobId)
          if (!result.success || !result.data) {
            return {
              ...item,
              errorMessage: result.message || '获取子任务状态失败',
            }
          }
          return {
            ...item,
            status: result.data.status,
            detail: result.data,
            errorMessage: '',
          }
        }),
      )
      luxianAggregateJobs.value = nextJobs
      if (nextJobs.every((item) => !isBatchJobRunning(item.status))) {
        stopLuxianAggregatePolling()
        await loadPools()
        await loadRecords()
      }
    } finally {
      luxianAggregateLoading.value = false
    }
  }

  function startLuxianAggregatePolling() {
    stopLuxianAggregatePolling()
    luxianAggregatePollTimer = setInterval(() => {
      if (!luxianAggregateOpen.value) {
        stopLuxianAggregatePolling()
        return
      }
      void refreshLuxianAggregateJobs()
    }, 3000)
  }

  function stopLuxianAggregatePolling() {
    if (luxianAggregatePollTimer) {
      clearInterval(luxianAggregatePollTimer)
      luxianAggregatePollTimer = null
    }
  }

  function closeLuxianAggregateDrawer() {
    stopLuxianAggregatePolling()
    luxianAggregateOpen.value = false
    luxianAggregateParentJobId.value = ''
    if (currentQcTask.value && isBatchJobRunning(currentQcTask.value.status)) {
      startCurrentQcTaskPolling(currentQcTask.value.id)
    }
  }

  async function openLuxianAggregateChildJob(item: LuxianAggregateJob) {
    const jobId = String(item.jobId || '').trim()
    if (!jobId) return
    luxianAggregateOpen.value = false
    stopLuxianAggregatePolling()
    await openBatchJob(jobId)
  }

  function luxianAggregateDisplayCounts(item: LuxianAggregateJob): Record<string, number> {
    return item.detail ? buildBatchJobPresentation(item.detail).statusCounts : {}
  }

  function luxianAggregateStatusChips(item: LuxianAggregateJob) {
    return item.detail ? buildBatchJobPresentation(item.detail).statusChips : []
  }

  function luxianAggregateAttentionCount(item: LuxianAggregateJob): number {
    const counts = luxianAggregateDisplayCounts(item)
    return (
      Number(counts.non_compliant || 0) +
      Number(counts.ai_suggested_non_compliant || 0) +
      Number(counts.uncertain || 0) +
      Number(counts.technical_error || 0)
    )
  }

  function luxianAggregateItemPriority(item: LuxianAggregateJob): number {
    if (['failed', 'canceled'].includes(item.status)) return 6
    const counts = luxianAggregateDisplayCounts(item)
    if (Number(counts.technical_error || 0) > 0 || Number(counts.non_compliant || 0) > 0) {
      return 5
    }
    if (
      Number(counts.ai_suggested_non_compliant || 0) > 0 ||
      Number(counts.uncertain || 0) > 0 ||
      Number(counts.data_gap || 0) > 0
    ) {
      return 4
    }
    if (isBatchJobRunning(item.status)) return 3
    if (Number(counts.compliant || 0) > 0 || Number(counts.ai_suggested_compliant || 0) > 0) {
      return 2
    }
    return 1
  }

  function luxianAggregateItemPriorityClass(item: LuxianAggregateJob): string {
    const priority = luxianAggregateItemPriority(item)
    if (priority >= 5) return 'is-danger'
    if (priority === 4) return 'is-warning'
    if (priority === 3) return 'is-running'
    return 'is-calm'
  }

  function luxianAggregateActionText(item: LuxianAggregateJob): string {
    if (['failed', 'canceled'].includes(item.status)) return '查看异常'
    const attentionCount = luxianAggregateAttentionCount(item)
    if (attentionCount > 0) return `查看 ${attentionCount} 项关注结果`
    const counts = luxianAggregateDisplayCounts(item)
    if (Number(counts.data_gap || 0) > 0) return '查看缺失原因'
    return '查看详情'
  }

  function luxianAggregateResultSummary(item: LuxianAggregateJob): string {
    if (item.detail) return buildBatchJobPresentation(item.detail).overviewText
    if (item.status === 'queued') return '任务已创建，等待后台执行。'
    if (item.status === 'running') return '任务执行中，等待结果回写。'
    return item.errorMessage || '暂无结果摘要。'
  }

  async function loadLatestSyncJob() {
    if (!selectedPoolId.value) {
      syncJobDetail.value = undefined
      stopSyncJobPolling()
      return
    }
    const result = await getLatestManualSamplePoolSyncJob(selectedPoolId.value)
    if (!result.success) return
    syncJobDetail.value = result.data || undefined
    if (syncJobDetail.value && isSyncJobRunning(syncJobDetail.value.status)) {
      startSyncJobPolling(syncJobDetail.value.id)
    } else {
      stopSyncJobPolling()
    }
  }

  async function openSyncJob(jobId: string) {
    stopSyncJobPolling()
    const result = await getManualSamplePoolSyncJob(jobId)
    if (!result.success || !result.data) {
      message.error(result.message || '获取样本同步任务失败')
      return
    }
    syncJobDetail.value = result.data
    if (isSyncJobRunning(result.data.status)) {
      startSyncJobPolling(jobId)
    } else {
      updateImportWorkflowFromSyncJob(result.data)
      await loadPools()
      await loadRecords()
    }
  }

  async function openBatchJob(jobId: string) {
    stopBatchJobPolling()
    if (currentQcTask.value?.id === jobId) {
      stopCurrentQcTaskPolling()
    }
    batchJobLoading.value = true
    batchResultOpen.value = true
    const result = await getSichuanWorkspaceBatchJob(jobId)
    batchJobLoading.value = false
    if (!result.success || !result.data) {
      message.error(result.message || '获取任务详情失败')
      return
    }
    updateCurrentQcTask(result.data)
    if (String(result.data.job_kind || '').toLowerCase() === 'parent') {
      batchResultOpen.value = false
      batchJobDetail.value = null
      await openLuxianAggregateParentJob(jobId)
      return
    }
    batchJobDetail.value = result.data
    if (isBatchJobRunning(result.data.status)) {
      startBatchJobPolling(jobId)
    }
  }

  function closeBatchDrawer() {
    stopBatchJobPolling()
    batchResultOpen.value = false
    batchJobDetail.value = null
    if (currentQcTask.value && isBatchJobRunning(currentQcTask.value.status)) {
      startCurrentQcTaskPolling(currentQcTask.value.id)
    }
  }

  function isBatchJobRunning(status?: string) {
    return isBatchJobCancelable(status)
  }

  function stopBatchJobPolling() {
    if (batchJobPollTimer) {
      clearInterval(batchJobPollTimer)
      batchJobPollTimer = null
    }
  }

  function startCurrentQcTaskPolling(jobId: string) {
    const normalizedJobId = String(jobId || '').trim()
    if (!normalizedJobId || currentQcTaskPollTimer) return
    currentQcTaskPollTimer = setInterval(async () => {
      if (batchResultOpen.value || luxianAggregateOpen.value) {
        stopCurrentQcTaskPolling()
        return
      }
      const result = await getSichuanWorkspaceBatchJob(normalizedJobId)
      if (!result.success || !result.data) return
      currentQcTask.value = result.data
      if (!isBatchJobRunning(result.data.status)) {
        stopCurrentQcTaskPolling()
        await Promise.all([loadPools({ refreshSyncJob: false, loadRecords: false }), loadRecords()])
      }
    }, 5000)
  }

  function stopCurrentQcTaskPolling() {
    if (currentQcTaskPollTimer) {
      clearInterval(currentQcTaskPollTimer)
      currentQcTaskPollTimer = null
    }
  }

  function isSyncJobRunning(status?: string) {
    const normalized = String(status || '').toLowerCase()
    return normalized === 'queued' || normalized === 'running'
  }

  function stopSyncJobPolling() {
    if (syncJobPollTimer) {
      clearInterval(syncJobPollTimer)
      syncJobPollTimer = null
    }
  }

  function hasSyncJobReachedPrimaryVisible(job: ManualSamplePoolSyncJob): boolean {
    const progress = job.summary?.progress || {}
    const phase = String(progress.phase || '') as SyncPhase | ''
    return (
      progress.primary_visible === true ||
      ['primary_visible', 'detail_sync', 'bundle_refresh'].includes(phase)
    )
  }

  function startSyncJobPolling(jobId: string) {
    stopSyncJobPolling()
    syncJobPollTimer = setInterval(async () => {
      const result = await getManualSamplePoolSyncJob(jobId)
      if (!result.success || !result.data) return
      syncJobDetail.value = result.data
      if (
        isSyncJobRunning(result.data.status) &&
        hasSyncJobReachedPrimaryVisible(result.data) &&
        !primaryVisibleRefreshedSyncJobs.has(jobId)
      ) {
        primaryVisibleRefreshedSyncJobs.add(jobId)
        await Promise.all([loadPools({ refreshSyncJob: false, loadRecords: false }), loadRecords()])
      }
      if (!isSyncJobRunning(result.data.status)) {
        stopSyncJobPolling()
        updateImportWorkflowFromSyncJob(result.data)
        const failed = String(result.data.status || '').toLowerCase() === 'failed'
        await loadPools({ refreshSyncJob: false, loadRecords: !failed })
      }
    }, 3000)
  }

  function updateImportWorkflowFromSyncJob(job: ManualSamplePoolSyncJob) {
    if (!importWorkflow.value || importWorkflow.value.poolId !== job.pool_id) return
    const status = String(job.status || '').toLowerCase()
    if (status === 'failed') {
      importWorkflow.value = {
        ...importWorkflow.value,
        status: 'sync_failed',
        message: customerFacingSyncError(job.error_message),
      }
      return
    }
    if (status !== 'completed') return
    const progress = syncRecordProgress.value
    importWorkflow.value = {
      ...importWorkflow.value,
      status: 'synced',
      message: `已同步 ${progress.completed}/${progress.total} 份病历，文书就绪 ${progress.ready} 份。`,
    }
  }

  function startBatchJobPolling(jobId: string) {
    stopBatchJobPolling()
    batchJobPollTimer = setInterval(async () => {
      if (!batchResultOpen.value) {
        stopBatchJobPolling()
        return
      }
      const result = await getSichuanWorkspaceBatchJob(jobId)
      if (!result.success || !result.data) return
      batchJobDetail.value = result.data
      updateCurrentQcTask(result.data)
      if (!isBatchJobRunning(result.data.status)) {
        stopBatchJobPolling()
        await loadPools()
        await loadRecords()
      }
    }, 3000)
  }

  async function handleCancelBatchJob(jobId: string) {
    const normalizedJobId = String(jobId || '').trim()
    if (!normalizedJobId) return
    cancelBatchJobLoading.value = true
    try {
      const result = await cancelSichuanWorkspaceBatchJob(normalizedJobId)
      if (!result.success || !result.data) {
        message.error(result.message || '停止质控任务失败')
        return
      }
      stopBatchJobPolling()
      batchJobDetail.value = result.data
      updateCurrentQcTask(result.data)
      message.success('已停止本次质控任务，已返回结果仍可查看')
      await loadPools()
      await loadRecords()
    } finally {
      cancelBatchJobLoading.value = false
    }
  }

  function confirmCancelBatchJob(jobId: string) {
    const normalizedJobId = String(jobId || '').trim()
    if (!normalizedJobId || cancelBatchJobLoading.value) return
    Modal.confirm({
      title: '停止当前质控任务？',
      content: '停止后将保留已返回结果，后续未执行的病历和质控点不再继续。',
      okText: '停止质控',
      cancelText: '继续等待',
      okButtonProps: { danger: true },
      async onOk() {
        await handleCancelBatchJob(normalizedJobId)
      },
    })
  }

  async function downloadBatchReport(jobId: string, format: 'xlsx' | 'csv' | 'html') {
    if (!jobId) {
      message.warning('当前任务详情未加载完成，暂时无法导出报告')
      return
    }
    const result = await exportSichuanWorkspaceBatchJob({ job_id: jobId, format })
    if (!result.success || !result.data) {
      message.error(result.message || '导出验证任务失败')
      return
    }
    let blob: Blob
    try {
      blob = await normalizeBatchExportBlob(result.data, format)
    } catch (error: any) {
      message.error(error?.message || '导出验证任务失败')
      return
    }
    downloadBlob(blob, `manual-sample-validation-${jobId}.${format}`)
    message.success(format === 'html' ? 'HTML 质控明细已开始下载' : '质控报告已开始下载')
  }

  async function handleExportBatchReport(format: 'xlsx' | 'csv' | 'html' = 'html') {
    const jobId = String(batchJobDetail.value?.id || '').trim()
    await downloadBatchReport(jobId, format)
  }

  async function handleExportTaskHistoryJob(job: SichuanBatchJob) {
    const jobId = String(job?.id || '').trim()
    await downloadBatchReport(jobId, 'html')
  }

  async function reviewBatchJob(jobId: string): Promise<SichuanBatchJob | null> {
    const normalizedJobId = String(jobId || '').trim()
    if (!normalizedJobId) {
      message.warning('当前任务未加载完成，暂时无法复核')
      return null
    }
    reviewBatchJobLoadingId.value = normalizedJobId
    try {
      const result = await reviewSichuanWorkspaceBatchJob(normalizedJobId)
      if (!result.success || !result.data?.job) {
        message.error(result.message || '复核本次结果失败')
        return null
      }
      const updatedJob = result.data.job
      updateCurrentQcTask(updatedJob)
      if (batchJobDetail.value?.id === updatedJob.id) {
        batchJobDetail.value = updatedJob
      }
      const findingCount = Number(result.data.review_report?.summary?.total_findings || 0)
      message.success(
        findingCount > 0 ? `复核完成，发现 ${findingCount} 条复核建议` : '复核完成，暂无高风险建议',
      )
      return updatedJob
    } finally {
      reviewBatchJobLoadingId.value = ''
    }
  }

  async function handleReviewTaskHistoryJob(job: SichuanBatchJob) {
    await reviewBatchJob(job.id)
  }

  async function handleReviewBatchResult() {
    await reviewBatchJob(String(batchJobDetail.value?.id || ''))
  }

  onMounted(async () => {
    window.addEventListener('resize', updateCustomerSampleTourCardPosition)
    window.addEventListener('scroll', updateCustomerSampleTourCardPosition, true)
    await loadRuleSets()
    await loadLuxian0609RuleCatalog()
    await loadPools()
    await restoreCurrentQcTaskForSelectedPool()
    openInitialCustomerSampleGuide()
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateCustomerSampleTourCardPosition)
    window.removeEventListener('scroll', updateCustomerSampleTourCardPosition, true)
    stopCustomerSampleGuidePositionTimer()
    stopBatchJobPolling()
    stopCurrentQcTaskPolling()
    stopLuxianAggregatePolling()
    stopSyncJobPolling()
    stopSyncStatusAutoHideTimer()
  })

  return {
    activeRecord,
    addEditableCopyDocument,
    addEditableCopyOrderDocument,
    allLuxianRuleIds,
    backlogBucketCardClass,
    backlogBucketTagClass,
    batchJobDetail,
    batchJobLoading,
    batchResultOpen,
    bundleStatusHint,
    bundleStatusLabel,
    cancelBatchJobLoading,
    clearLuxianRuleScope,
    clearSelectedRecords,
    closeBatchDrawer,
    closeCustomerSampleGuide,
    closeEditableCopyDrawer,
    closeLuxianAggregateDrawer,
    closeRecordResultComparison,
    Compass,
    confirmCancelBatchJob,
    confirmDeletePool,
    coverageLabel,
    coverageOptions,
    currentCustomerSampleGuideStep,
    currentQcTask,
    currentQcTaskLoading,
    currentScopeDescription,
    CUSTOMER_TEST_POOL_ID,
    customerSampleGuideOpen,
    customerSampleGuideStepIndex,
    customerSampleGuideSteps,
    customerSampleGuideTargetClass,
    CustomerSampleQcTaskStatusBar,
    customerSampleTourCardStyle,
    deletingPoolIds,
    detailOpen,
    dismissSyncStatusBar,
    editableCopyActiveDocument,
    editableCopyDocumentFilter,
    editableCopyDocumentGroups,
    editableCopyDocumentQuery,
    editableCopyDraft,
    editableCopyEnabledDocumentCount,
    editableCopyFilteredDocuments,
    editableCopyLoading,
    editableCopyNewDocumentType,
    editableCopyOpen,
    editableCopyOrderTypeFilter,
    editableCopyReadonly,
    editableCopySaveAndRunLoading,
    editableCopySaving,
    editableCopySourceRecord,
    editableCopyVisibleOrderRows,
    exactReviewAcceptance,
    exactReviewBacklogBuckets,
    exactReviewError,
    exactReviewLoading,
    exactReviewReasonTags,
    exactReviewStatusCards,
    expandedLuxianRuleFamilyKeys,
    FilePlus2,
    filters,
    formatDateTime,
    formatEditableCopyDocumentMeta,
    formatEditableCopyOrderGroupMeta,
    getBatchJobStatusTagClass,
    getBatchJobStatusText,
    goToCustomerSampleGuideStep,
    goToNextCustomerSampleGuideStep,
    goToPreviousCustomerSampleGuideStep,
    handleCancelBatchJob,
    handleDownloadTemplate,
    handleExportBatchReport,
    handleExportCurrentTask,
    handleHospitalizationSync,
    handleImportFileSelect,
    handleImportPool,
    handleInternalDiagnosticChange,
    handleMoreActionKey,
    handlePoolChange,
    handlePoolManagementSearch,
    handleRetrySync,
    handleReviewBatchResult,
    handleReviewCurrentTask,
    handleRuleSetChange,
    handleRunPool,
    handleSyncPoolRecords,
    History,
    hospitalizationPreviewMetrics,
    hospitalizationScopeNeedsDischargeRange,
    hospitalizationScopeOptions,
    hospitalizationSyncCanSubmit,
    hospitalizationSyncDepartmentOptions,
    hospitalizationSyncForm,
    hospitalizationSyncModalOpen,
    hospitalizationSyncOkText,
    hospitalizationSyncPreview,
    hospitalizationSyncPreviewError,
    hospitalizationSyncPreviewLoading,
    hospitalizationSyncSubmitting,
    importFileList,
    importForm,
    importingPool,
    importModalOpen,
    importWorkflow,
    importWorkflowSteps,
    InboxOutlined,
    internalDiagnosticKeys,
    isAllLuxianRulesSelected,
    isEditableCopyDocumentGroupExpanded,
    isEditableOrderDocument,
    isLastCustomerSampleGuideStep,
    isLuxian0609Mode,
    isSyncedOnlyValidationMode,
    itemColumns,
    itemLoading,
    loadManagedPools,
    loadRecords,
    luxianAggregateActionText,
    luxianAggregateHeadline,
    luxianAggregateItemPriorityClass,
    luxianAggregateLoading,
    luxianAggregateOpen,
    luxianAggregateResultOverview,
    luxianAggregateResultSummary,
    luxianAggregateSortedJobs,
    luxianAggregateStatusChips,
    luxianRuleFamilies,
    LuxianRuleScopePanel,
    luxianScopeHelperText,
    luxianScopeModeText,
    mainRuleSets,
    managedPools,
    matchLoading,
    matchStatusHint,
    matchStatusLabel,
    matchStatusOptions,
    openBatchJob,
    openCustomerSampleGuide,
    openLuxianAggregateChildJob,
    openPoolManagement,
    openSyncDetailDrawer,
    openTaskHistoryPage,
    openTestRecordDrawer,
    paginationConfig,
    parallelOptions,
    poolDeletionDisabled,
    poolJobStatusLabel,
    poolLoading,
    poolManagementLoading,
    poolManagementOpen,
    poolManagementPagination,
    poolManagementQuery,
    poolOptions,
    QCRecordResultComparisonDrawer,
    QCReviewDrawer,
    ReadonlyMedicalDocumentContent,
    recordResultComparisonFocus,
    recordResultComparisonOpen,
    records,
    recordScopeHint,
    refreshHospitalizationScopePreview,
    refreshLuxianAggregateJobs,
    removeEditableCopyDocument,
    resetFilters,
    resetImportForm,
    resolveEditableOrderTypeLabel,
    reviewBatchJobLoadingId,
    reviewDrawerRecord,
    reviewDrawerVisible,
    rowSelection,
    ruleSetCardClass,
    ruleSetDirectoryFallbackActive,
    ruleSetScopeLabel,
    runButtonDisabled,
    runButtonText,
    runLoading,
    runOptions,
    runPoolMatch,
    saveEditableCopy,
    scrollToLuxianScope,
    selectEditableCopyDocument,
    selectEditableCopyOrderGroup,
    selectedLuxianCustomerRuleIds,
    selectedLuxianFamilyCount,
    selectedPool,
    selectedPoolId,
    selectedRecordStats,
    selectedRuleSet,
    selectedRuleSetCoverageChips,
    selectedRuleSetRuleCountText,
    selectedRunScopeSummary,
    selectLuxianRuleFamily,
    SemanticRulesBatchResultDrawer,
    Settings2,
    showSyncStatusBar,
    startSyntheticCaseFromGuide,
    summarizeRecordScope,
    summaryCards,
    syncCustomerStepText,
    syncDetailDrawerOpen,
    syncHospitalizationSummary,
    syncJobDetail,
    syncJobStatusColor,
    syncJobStatusText,
    syncLoading,
    syncProgress,
    syncRecordProgress,
    syncResolvedStats,
    syncResultNotice,
    syncStatusBar,
    tableEmptyText,
    testRecordDocumentTypeOptions,
    toggleAllLuxianRuleFamilies,
    toggleEditableCopyDocumentGroup,
    toggleInternalDiagnostic,
    toggleLuxianRule,
    toggleLuxianRuleFamilyExpanded,
    Trash2,
    workflowSteps,
  }
}
