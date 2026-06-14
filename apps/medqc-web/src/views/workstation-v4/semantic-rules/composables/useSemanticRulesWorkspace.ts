import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiService } from '@/services/apiService'
import { UserRole } from '@/types/auth'
import type { User } from '@/types/auth'
import type { WorkspaceScope } from '@/types/custom-rule-workspace'
import { createSichuanWorkspaceBatchJob } from '@/services/sichuan-rule-workspace-service'
import { useCustomQcBatchLaunchFilters } from '@/views/rules/composables/useCustomQcBatchLaunchFilters'
import { useSichuanBatchJobs } from './useSichuanBatchJobs'
import type {
  SemanticRuleItem,
  SemanticRuleStats,
  SemanticRuleTestResult,
  SemanticRuleWorkspaceQueryState,
  SichuanRuleSetOption,
} from '../types'
import {
  buildSemanticKpiCards,
  buildSemanticWorkspaceQuery,
  executeSemanticRuleTest,
  fetchRulePrompt,
  fetchSemanticRulesFromBackend,
  fetchSichuanRuleSetsFromBackend,
  filterSemanticRules,
  parseSemanticWorkspaceQuery,
  saveRulePrompt,
  SemanticRuleTestError,
  toSemanticRulePage,
} from '../service'

type BuildCaseText = (example: any, options?: Record<string, unknown>) => string

const LUXIAN_0609_RULE_SET_KEY = 'luxian_0609_qc_v1'
const DEFAULT_RULE_PAGE_SIZE = 10
const DEFAULT_RULE_SET_OPTION: SichuanRuleSetOption = {
  rule_set_key: '',
  rule_set_name: 'SC 全病历质控规则',
  rule_set_version: '当前版本',
  scope: 'all',
  rule_ids: [],
  rule_count: 0,
  description: '默认展示当前 SC 全病历质控规则列表。',
}

function toErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof Error)) return fallback
  const messageText = String(error.message || '').trim()
  if (!messageText) return fallback
  return messageText.length > 120 ? `${messageText.slice(0, 120)}...` : messageText
}

function renderSemanticRuleExample(example: SemanticRuleItem['positive_example']): string {
  if (!example) return '暂无示例文本，请手动输入。'
  if (example.raw_text?.trim()) return example.raw_text.trim()
  const lines: string[] = []
  if (example.title) lines.push(example.title)
  if (example.summary) lines.push(example.summary)
  ;(example.sections || []).forEach((section) => {
    if (section.heading) lines.push(`【${section.heading}】`)
    if (section.content) lines.push(section.content)
  })
  if (example.focusPoints?.length) {
    lines.push('【质控关注点】')
    example.focusPoints.forEach((item) => lines.push(`- ${item}`))
  }
  return lines.join('\n')
}

export function useSemanticRulesWorkspace() {
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const rules = ref<SemanticRuleItem[]>([])
  const stats = ref<SemanticRuleStats>({
    total_rules: 0,
    rule_categories: [],
    complexity_distribution: {},
    defect_level_distribution: {},
  })
  const lastRefreshedAt = ref<Date | null>(null)

  const queryState = reactive<SemanticRuleWorkspaceQueryState>({
    ruleSetKey: '',
    keyword: '',
    complexity: '',
    defectLevel: '',
    documentType: '',
    page: 1,
    pageSize: DEFAULT_RULE_PAGE_SIZE,
  })
  const keywordInput = ref('')
  const ruleSetOptions = ref<SichuanRuleSetOption[]>([DEFAULT_RULE_SET_OPTION])

  const currentUser = ref<User | null>(null)
  const isAdmin = computed(() => currentUser.value?.roles?.includes(UserRole.ADMIN) || false)

  const showRuleDetail = ref(false)
  const selectedRule = ref<SemanticRuleItem | null>(null)
  const promptLoading = ref(false)
  const isEditingPrompt = ref(false)
  const currentPrompt = ref('')
  const editingPrompt = ref('')
  const isDefaultPrompt = ref(true)

  const showRuleTest = ref(false)
  const testingRule = ref<SemanticRuleItem | null>(null)
  const testMedicalText = ref('')
  const testLoading = ref(false)
  const testExampleType = ref<'positive' | 'negative'>('negative')
  const testResult = ref<SemanticRuleTestResult | null>(null)

  const showQCEvaluation = ref(false)

  const recordFilters = reactive<{
    scope: WorkspaceScope
    department?: string
    doctor?: string
    dateRange: [any, any] | null
    keyword: string
  }>({
    scope: 'final',
    department: undefined,
    doctor: undefined,
    dateRange: null,
    keyword: '',
  })

  const {
    batchLaunchModalOpen,
    batchLaunchFiltersLoading,
    batchLaunchDepartmentOptions,
    batchLaunchDoctorOptions,
    batchLaunchFilters,
    resetBatchLaunchFiltersFromCurrent,
    loadBatchLaunchFilterOptions,
    handleBatchLaunchScopeChange,
    handleBatchLaunchDepartmentChange,
  } = useCustomQcBatchLaunchFilters(recordFilters)

  const testingBatch = ref(false)
  const resultDrawerOpen = ref(false)

  const {
    batchJobLoading,
    batchJobDetailLoading,
    batchJobDebugLoading,
    cancellingBatchJobId,
    retryingBatchJobId,
    batchJobs,
    batchJobDetail,
    batchJobDebugSnapshot,
    activeBatchJob,
    batchJobPagination,
    batchJobQuery,
    batchJobStatusOptions,
    batchJobScopeOptions,
    loadBatchJobs,
    handleBatchJobTableChange,
    searchBatchJobs,
    startBatchJobPolling,
    stopBatchJobPolling,
    fetchBatchJobDetail,
    fetchBatchJobDebugSnapshot,
    executeCancelBatchJob,
    executeRetryBatchJob,
    exportBatchJobReport,
    resetBatchJobs,
  } = useSichuanBatchJobs()

  const qcRuleCaseMapRef = ref<Record<string, any>>({})
  const buildCaseTextRef = ref<BuildCaseText | null>(null)

  let keywordTimer: ReturnType<typeof setTimeout> | null = null
  let isApplyingRouteQuery = false
  let rulesRefreshSeq = 0

  const complexityBreakdown = computed(() => {
    const distribution = stats.value.complexity_distribution || {}
    return {
      high: Number(distribution['高复杂度'] || 0),
      medium: Number(distribution['中复杂度'] || 0),
      low: Number(distribution['低复杂度'] || 0),
    }
  })

  const criticalDefectCount = computed(() =>
    Number(stats.value.defect_level_distribution?.['严重缺陷'] || 0),
  )
  const majorDefectCount = computed(() =>
    Number(stats.value.defect_level_distribution?.['一般缺陷'] || 0),
  )
  const minorDefectCount = computed(() =>
    Number(stats.value.defect_level_distribution?.['轻微缺陷'] || 0),
  )
  const defectTotal = computed(
    () => criticalDefectCount.value + majorDefectCount.value + minorDefectCount.value,
  )
  const riskDensity = computed(() => {
    if (!stats.value.total_rules) return '0%'
    return `${Math.round((criticalDefectCount.value / stats.value.total_rules) * 100)}%`
  })
  const lastRefreshedLabel = computed(() => {
    if (!lastRefreshedAt.value) return '未同步'
    return lastRefreshedAt.value.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  })

  const filteredRules = computed(() =>
    filterSemanticRules(rules.value, {
      keyword: queryState.keyword,
      complexity: queryState.complexity,
      defectLevel: queryState.defectLevel,
      documentType: queryState.documentType,
    }),
  )

  const tableRules = computed(() =>
    toSemanticRulePage(filteredRules.value, queryState.page, queryState.pageSize),
  )

  const tablePagination = computed<TablePaginationConfig>(() => ({
    current: queryState.page,
    pageSize: queryState.pageSize,
    total: filteredRules.value.length,
    showSizeChanger: true,
    showQuickJumper: true,
    pageSizeOptions: ['10', '20', '50', '100'],
    showTotal: (total) => `共 ${total} 条`,
    size: 'small',
  }))

  const complexityOptions = computed(() =>
    [...new Set(rules.value.map((item) => item.complexity).filter(Boolean))].sort(),
  )
  const defectOptions = computed(() =>
    [...new Set(rules.value.map((item) => item.defect_level).filter(Boolean))].sort(),
  )
  const documentOptions = computed(() => {
    const docSet = new Set<string>()
    rules.value.forEach((rule) => {
      ;(rule.applicable_documents || []).forEach((docType) => {
        if (docType) docSet.add(docType)
      })
    })
    return [...docSet].sort()
  })

  const topCategories = computed(() => {
    const categoryCounter: Record<string, number> = {}
    rules.value.forEach((rule) => {
      categoryCounter[rule.category] = (categoryCounter[rule.category] || 0) + 1
    })
    return Object.entries(categoryCounter)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, count]) => ({ name, count }))
  })

  const heroKpiCards = computed(() =>
    buildSemanticKpiCards({
      stats: stats.value,
      criticalDefectCount: criticalDefectCount.value,
      riskDensity: riskDensity.value,
      lastRefreshedLabel: lastRefreshedLabel.value,
    }),
  )

  const selectedRuleSetOption = computed(
    () =>
      ruleSetOptions.value.find((item) => item.rule_set_key === queryState.ruleSetKey) ||
      DEFAULT_RULE_SET_OPTION,
  )

  function normalizeQueryValue(value: unknown): string {
    if (Array.isArray(value)) return value.length > 0 ? String(value[0]) : ''
    if (value === null || value === undefined) return ''
    return String(value)
  }

  function hasSameManagedQuery(nextQuery: Record<string, unknown>): boolean {
    return (
      normalizeQueryValue(route.query.keyword) === normalizeQueryValue(nextQuery.keyword) &&
      normalizeQueryValue(route.query.ruleSetKey) === normalizeQueryValue(nextQuery.ruleSetKey) &&
      normalizeQueryValue(route.query.complexity) === normalizeQueryValue(nextQuery.complexity) &&
      normalizeQueryValue(route.query.defectLevel) === normalizeQueryValue(nextQuery.defectLevel) &&
      normalizeQueryValue(route.query.documentType) ===
        normalizeQueryValue(nextQuery.documentType) &&
      normalizeQueryValue(route.query.page) === normalizeQueryValue(nextQuery.page) &&
      normalizeQueryValue(route.query.pageSize) === normalizeQueryValue(nextQuery.pageSize)
    )
  }

  function applyRouteQuery() {
    isApplyingRouteQuery = true
    const parsed = parseSemanticWorkspaceQuery(route.query)
    queryState.ruleSetKey = parsed.ruleSetKey
    queryState.keyword = parsed.keyword
    queryState.complexity = parsed.complexity
    queryState.defectLevel = parsed.defectLevel
    queryState.documentType = parsed.documentType
    queryState.page = parsed.page
    queryState.pageSize = parsed.pageSize
    keywordInput.value = parsed.keyword
    isApplyingRouteQuery = false
  }

  function syncStateToRoute() {
    if (isApplyingRouteQuery) return
    const nextQuery = buildSemanticWorkspaceQuery(route.query, queryState)
    if (hasSameManagedQuery(nextQuery as Record<string, unknown>)) return
    router.replace({ query: nextQuery })
  }

  watch(
    () => route.query,
    () => {
      const previousRuleSetKey = queryState.ruleSetKey
      applyRouteQuery()
      if (previousRuleSetKey !== queryState.ruleSetKey && lastRefreshedAt.value) {
        void refreshRules(false)
      }
    },
    { immediate: true },
  )

  watch(
    () => [
      queryState.ruleSetKey,
      queryState.complexity,
      queryState.defectLevel,
      queryState.documentType,
      queryState.keyword,
    ],
    () => {
      if (queryState.page !== 1) queryState.page = 1
      syncStateToRoute()
    },
  )

  watch(
    () => [queryState.page, queryState.pageSize],
    () => {
      syncStateToRoute()
    },
  )

  watch(keywordInput, (value) => {
    if (keywordTimer) clearTimeout(keywordTimer)
    keywordTimer = setTimeout(() => {
      queryState.keyword = value.trim()
    }, 300)
  })

  watch(filteredRules, (items) => {
    const maxPage = Math.max(1, Math.ceil(items.length / queryState.pageSize))
    if (queryState.page > maxPage) {
      queryState.page = maxPage
    }
  })

  function getDefectRate(count: number | undefined): number {
    if (!count || defectTotal.value === 0) return 0
    return Math.round((count / defectTotal.value) * 100)
  }

  function getCategoryRatio(count: number): string {
    if (!stats.value.total_rules) return '0%'
    return `${Math.round((count / stats.value.total_rules) * 100)}%`
  }

  async function refreshRules(
    showSuccessMessage: boolean = true,
    requestedRuleSetKey: string = queryState.ruleSetKey,
  ) {
    const currentSeq = ++rulesRefreshSeq
    loading.value = true
    try {
      const payload = await fetchSemanticRulesFromBackend(requestedRuleSetKey)
      if (currentSeq !== rulesRefreshSeq || requestedRuleSetKey !== queryState.ruleSetKey) {
        return
      }
      rules.value = payload.rules
      stats.value = payload.stats
      lastRefreshedAt.value = new Date()
      if (showSuccessMessage) message.success('规则库已刷新')
    } catch (error) {
      if (currentSeq !== rulesRefreshSeq) {
        return
      }
      message.error('规则库加载失败')
      console.error('[SemanticRulesWorkspace] refresh failed', error)
    } finally {
      if (currentSeq === rulesRefreshSeq) {
        loading.value = false
      }
    }
  }

  function resetFilters() {
    keywordInput.value = ''
    queryState.keyword = ''
    queryState.complexity = ''
    queryState.defectLevel = ''
    queryState.documentType = ''
    queryState.page = 1
    queryState.pageSize = DEFAULT_RULE_PAGE_SIZE
  }

  async function loadRuleSetOptions() {
    try {
      const items = await fetchSichuanRuleSetsFromBackend()
      const luxianRuleSet = items.find((item) => item.rule_set_key === LUXIAN_0609_RULE_SET_KEY)
      ruleSetOptions.value = [
        DEFAULT_RULE_SET_OPTION,
        luxianRuleSet || {
          rule_set_key: LUXIAN_0609_RULE_SET_KEY,
          rule_set_name: '泸县0609质控点验证 v1',
          rule_set_version: '2026-06-09',
          scope: 'running',
          rule_ids: [],
          rule_count: 49,
          description: '客户专项规则包，按 49 条质控点展示。',
        },
      ]
    } catch (error) {
      ruleSetOptions.value = [DEFAULT_RULE_SET_OPTION]
      console.error('[SemanticRulesWorkspace] load rule set options failed', error)
    }
  }

  function handleRuleSetChange(ruleSetKey: string) {
    queryState.ruleSetKey = ruleSetKey
    queryState.page = 1
    syncStateToRoute()
    void refreshRules(false, ruleSetKey)
  }

  function applyFilterQuery() {
    queryState.keyword = keywordInput.value.trim()
    queryState.page = 1
  }

  function handleTableChange(pagination: TablePaginationConfig) {
    queryState.page = Number(pagination.current || 1)
    queryState.pageSize = Number(pagination.pageSize || DEFAULT_RULE_PAGE_SIZE)
  }

  async function openRuleDetail(rule: SemanticRuleItem) {
    selectedRule.value = rule
    showRuleDetail.value = true
    isEditingPrompt.value = false
    testResult.value = null
    currentPrompt.value = ''
    editingPrompt.value = ''
    if (rule.rule_id.startsWith('LX0609-')) {
      currentPrompt.value = rule.custom_prompt || '// 暂无检查模板'
      editingPrompt.value = rule.custom_prompt || ''
      isDefaultPrompt.value = false
      return
    }
    if (!isAdmin.value) return
    await loadPrompt(rule.rule_id)
  }

  function closeRuleDetail() {
    showRuleDetail.value = false
  }

  async function loadPrompt(ruleId: string) {
    promptLoading.value = true
    try {
      const payload = await fetchRulePrompt(ruleId)
      currentPrompt.value = payload.prompt || '// 暂无提示词'
      editingPrompt.value = payload.prompt || ''
      isDefaultPrompt.value = payload.isDefaultPrompt
    } catch (error) {
      const reason = toErrorMessage(error, '请稍后重试')
      currentPrompt.value = `// 获取提示词失败：${reason}`
      message.error(`提示词加载失败：${reason}`)
      console.error('[SemanticRulesWorkspace] load prompt failed', error)
    } finally {
      promptLoading.value = false
    }
  }

  function startEditPrompt() {
    editingPrompt.value = currentPrompt.value || ''
    isEditingPrompt.value = true
  }

  function cancelEditPrompt() {
    editingPrompt.value = currentPrompt.value || ''
    isEditingPrompt.value = false
  }

  async function savePromptChanges() {
    if (!selectedRule.value) return
    promptLoading.value = true
    try {
      await saveRulePrompt(selectedRule.value.rule_id, editingPrompt.value)
      currentPrompt.value = editingPrompt.value.trim() || '// 暂无提示词'
      isDefaultPrompt.value = !editingPrompt.value.trim()
      isEditingPrompt.value = false
      message.success('提示词已保存')
    } catch (error) {
      message.error(`保存提示词失败：${toErrorMessage(error, '请稍后重试')}`)
      console.error('[SemanticRulesWorkspace] save prompt failed', error)
    } finally {
      promptLoading.value = false
    }
  }

  function switchExampleType(type: 'positive' | 'negative') {
    testExampleType.value = type
    if (!testingRule.value) return
    const wrapperExample =
      type === 'positive' ? testingRule.value.positive_example : testingRule.value.negative_example
    if (wrapperExample) {
      testMedicalText.value = renderSemanticRuleExample(wrapperExample)
      return
    }
    const ruleCase =
      qcRuleCaseMapRef.value[testingRule.value.rule_id] ||
      qcRuleCaseMapRef.value[testingRule.value.primary_execution_rule_id || '']
    const buildCaseText = buildCaseTextRef.value
    if (!ruleCase || !buildCaseText) {
      testMedicalText.value = '暂无示例文本，请手动输入。'
      return
    }
    const example = (type === 'positive' ? ruleCase.positive : ruleCase.negative) || {}
    testMedicalText.value = buildCaseText(example, {
      includeHints: false,
      includeTitle: false,
      includeAnalysis: false,
      includeFocusPoints: false,
    })
  }

  function startRuleTest(rule: SemanticRuleItem) {
    testingRule.value = rule
    showRuleTest.value = true
    testResult.value = null
    switchExampleType('negative')
  }

  function closeRuleTest() {
    showRuleTest.value = false
    testLoading.value = false
  }

  async function executeRuleTestAction() {
    if (!testingRule.value || !testMedicalText.value.trim()) {
      message.warning('请输入病历文本')
      return
    }
    testLoading.value = true
    testResult.value = null
    try {
      const ruleId = testingRule.value.rule_id.startsWith('LX0609-')
        ? testingRule.value.rule_id
        : testingRule.value.primary_execution_rule_id || testingRule.value.rule_id
      testResult.value = await executeSemanticRuleTest(ruleId, testMedicalText.value)
    } catch (error) {
      message.error('规则测试失败')
      if (error instanceof SemanticRuleTestError) {
        testResult.value = {
          is_compliant: false,
          confidence: 0,
          findings: error.message || '规则测试失败',
          evidence: '',
          suggestion: '',
          status: 'failed',
          trace_id: error.traceId,
          error_message: error.message,
          error_detail: error.detail,
          status_code: error.statusCode,
          error_category: error.errorCategory || 'unknown',
        }
      }
      console.error('[SemanticRulesWorkspace] rule test failed', error)
    } finally {
      testLoading.value = false
    }
  }

  function openBatchLaunchModal() {
    resetBatchLaunchFiltersFromCurrent()
    batchLaunchModalOpen.value = true
    void loadBatchLaunchFilterOptions({ silent: true }).catch(() => {
      message.warning('批量筛选项加载较慢，请稍后重试')
    })
  }

  function closeBatchLaunchModal() {
    batchLaunchModalOpen.value = false
  }

  async function confirmBatchLaunch() {
    if (testingBatch.value) return
    const isLuxianRuleSet = queryState.ruleSetKey === LUXIAN_0609_RULE_SET_KEY
    const ruleIds = isLuxianRuleSet
      ? []
      : filteredRules.value.map((rule) => rule.rule_id).filter(Boolean)
    if (!isLuxianRuleSet && !ruleIds.length) {
      message.info('当前没有可执行的规则')
      return
    }
    testingBatch.value = true
    try {
      const payload = {
        ...(isLuxianRuleSet ? { rule_set_key: LUXIAN_0609_RULE_SET_KEY } : { rule_ids: ruleIds }),
        scope: batchLaunchFilters.scope,
        department: batchLaunchFilters.department,
        doctor: batchLaunchFilters.doctor,
        date_field: batchLaunchFilters.date_field,
        start_date: batchLaunchFilters.dateRange?.[0]?.format('YYYY-MM-DD'),
        end_date: batchLaunchFilters.dateRange?.[1]?.format('YYYY-MM-DD'),
        keyword: batchLaunchFilters.keyword || undefined,
      }
      const response = await createSichuanWorkspaceBatchJob(payload)
      if (!response.success || !response.data) {
        throw new Error(response.message || '创建批量任务失败')
      }
      message.success('批量任务已创建')
      batchLaunchModalOpen.value = false
      await loadBatchJobs()
      await openBatchJobDrawer(response.data)
    } catch (error: any) {
      message.error(error?.message || '创建批量任务失败')
    } finally {
      testingBatch.value = false
    }
  }

  async function openBatchJobDrawer(job: { id: string }) {
    resultDrawerOpen.value = true
    await fetchBatchJobDetail(job.id, { includeDebugSnapshot: true })
    startBatchJobPolling(job.id)
  }

  function closeBatchJobDrawer() {
    resultDrawerOpen.value = false
    stopBatchJobPolling()
  }

  function formatDateTime(value?: string | Date | null) {
    if (!value) return '-'
    try {
      let date: Date
      if (typeof value === 'string') {
        const text = value.trim()
        const normalized = /z$/i.test(text) || /[+-]\d{2}:\d{2}$/.test(text) ? text : `${text}Z`
        date = new Date(normalized)
      } else {
        date = value
      }
      if (Number.isNaN(date.getTime())) return String(value)
      return date.toLocaleString('zh-CN', { hour12: false })
    } catch {
      return String(value)
    }
  }

  function openQCEvaluation() {
    showQCEvaluation.value = true
  }

  function closeQCEvaluation() {
    showQCEvaluation.value = false
  }

  async function goCustomWorkspace() {
    await router.push('/workstation-v4/rules/custom-workspace')
  }

  async function initialize() {
    try {
      const [qcRuleCasesModule, userResp] = await Promise.all([
        import('@/data/qcRuleCases'),
        ApiService.getCurrentUser(),
      ])

      qcRuleCaseMapRef.value = qcRuleCasesModule.qcRuleCaseMap || {}
      buildCaseTextRef.value = qcRuleCasesModule.buildCaseText || null

      if (userResp.success) {
        currentUser.value = userResp.data ?? null
      }
    } catch (error) {
      console.error('[SemanticRulesWorkspace] initialize failed', error)
    }
    await loadRuleSetOptions()
    await refreshRules(false)
    await loadBatchJobs()
  }

  onMounted(() => {
    initialize()
  })

  onBeforeUnmount(() => {
    if (keywordTimer) {
      clearTimeout(keywordTimer)
      keywordTimer = null
    }
    resetBatchJobs()
  })

  return {
    loading,
    rules,
    stats,
    lastRefreshedLabel,
    complexityBreakdown,
    criticalDefectCount,
    majorDefectCount,
    minorDefectCount,
    riskDensity,
    topCategories,
    heroKpiCards,
    getDefectRate,
    getCategoryRatio,
    queryState,
    ruleSetOptions,
    selectedRuleSetOption,
    handleRuleSetChange,
    keywordInput,
    filteredRules,
    tableRules,
    tablePagination,
    complexityOptions,
    defectOptions,
    documentOptions,
    refreshRules,
    resetFilters,
    applyFilterQuery,
    handleTableChange,
    showRuleDetail,
    selectedRule,
    openRuleDetail,
    closeRuleDetail,
    isAdmin,
    promptLoading,
    isEditingPrompt,
    currentPrompt,
    editingPrompt,
    isDefaultPrompt,
    startEditPrompt,
    cancelEditPrompt,
    savePromptChanges,
    showRuleTest,
    testingRule,
    testMedicalText,
    testLoading,
    testExampleType,
    testResult,
    startRuleTest,
    switchExampleType,
    closeRuleTest,
    executeRuleTestAction,
    showQCEvaluation,
    openQCEvaluation,
    closeQCEvaluation,
    goCustomWorkspace,
    batchLaunchModalOpen,
    batchLaunchFiltersLoading,
    batchLaunchDepartmentOptions,
    batchLaunchDoctorOptions,
    batchLaunchFilters,
    handleBatchLaunchScopeChange,
    handleBatchLaunchDepartmentChange,
    openBatchLaunchModal,
    closeBatchLaunchModal,
    confirmBatchLaunch,
    testingBatch,
    batchJobLoading,
    batchJobDetailLoading,
    batchJobDebugLoading,
    cancellingBatchJobId,
    retryingBatchJobId,
    batchJobs,
    batchJobDetail,
    batchJobDebugSnapshot,
    activeBatchJob,
    batchJobPagination,
    batchJobQuery,
    batchJobStatusOptions,
    batchJobScopeOptions,
    handleBatchJobTableChange,
    searchBatchJobs,
    openBatchJobDrawer,
    closeBatchJobDrawer,
    fetchBatchJobDebugSnapshot,
    executeCancelBatchJob,
    executeRetryBatchJob,
    exportBatchJobReport,
    resultDrawerOpen,
    formatDateTime,
  }
}
