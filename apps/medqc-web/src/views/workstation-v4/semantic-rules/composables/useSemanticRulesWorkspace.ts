import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiService } from '@/services/apiService'
import { toWsPath } from '@/router/workstation-v4/registry'
import { UserRole } from '@/types/auth'
import type { User } from '@/types/auth'
import type {
  SemanticRuleItem,
  SemanticRuleStats,
  SemanticRuleTestResult,
  SemanticRuleWorkspaceQueryState,
} from '../types'
import {
  buildSemanticKpiCards,
  buildSemanticWorkspaceQuery,
  executeSemanticRuleTest,
  fetchRulePrompt,
  fetchSemanticRulesFromBackend,
  filterSemanticRules,
  parseSemanticWorkspaceQuery,
  saveRulePrompt,
  toSemanticRulePage,
} from '../service'

type BuildCaseText = (example: any, options?: Record<string, unknown>) => string

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
    keyword: '',
    complexity: '',
    defectLevel: '',
    documentType: '',
    page: 1,
    pageSize: 20,
  })
  const keywordInput = ref('')

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

  const qcRuleCaseMapRef = ref<Record<string, any>>({})
  const buildCaseTextRef = ref<BuildCaseText | null>(null)

  let keywordTimer: ReturnType<typeof setTimeout> | null = null
  let isApplyingRouteQuery = false

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
    pageSizeOptions: ['20', '50', '100'],
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

  function normalizeQueryValue(value: unknown): string {
    if (Array.isArray(value)) return value.length > 0 ? String(value[0]) : ''
    if (value === null || value === undefined) return ''
    return String(value)
  }

  function hasSameManagedQuery(nextQuery: Record<string, unknown>): boolean {
    return (
      normalizeQueryValue(route.query.keyword) === normalizeQueryValue(nextQuery.keyword) &&
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
      applyRouteQuery()
    },
    { immediate: true },
  )

  watch(
    () => [
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

  async function refreshRules(showSuccessMessage: boolean = true) {
    loading.value = true
    try {
      const payload = await fetchSemanticRulesFromBackend()
      rules.value = payload.rules
      stats.value = payload.stats
      lastRefreshedAt.value = new Date()
      if (showSuccessMessage) message.success('规则库已刷新')
    } catch (error) {
      message.error('规则库加载失败')
      console.error('[SemanticRulesWorkspace] refresh failed', error)
    } finally {
      loading.value = false
    }
  }

  function resetFilters() {
    keywordInput.value = ''
    queryState.keyword = ''
    queryState.complexity = ''
    queryState.defectLevel = ''
    queryState.documentType = ''
    queryState.page = 1
    queryState.pageSize = 20
  }

  function applyFilterQuery() {
    queryState.keyword = keywordInput.value.trim()
    queryState.page = 1
  }

  function handleTableChange(pagination: TablePaginationConfig) {
    queryState.page = Number(pagination.current || 1)
    queryState.pageSize = Number(pagination.pageSize || 20)
  }

  async function openRuleDetail(rule: SemanticRuleItem) {
    selectedRule.value = rule
    showRuleDetail.value = true
    isEditingPrompt.value = false
    testResult.value = null
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
      currentPrompt.value = '// 获取提示词失败'
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
      message.error('保存提示词失败')
      console.error('[SemanticRulesWorkspace] save prompt failed', error)
    } finally {
      promptLoading.value = false
    }
  }

  function switchExampleType(type: 'positive' | 'negative') {
    testExampleType.value = type
    if (!testingRule.value) return
    const ruleCase = qcRuleCaseMapRef.value[testingRule.value.rule_id]
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
      testResult.value = await executeSemanticRuleTest(
        testingRule.value.rule_id,
        testMedicalText.value,
      )
    } catch (error) {
      message.error('规则测试失败')
      console.error('[SemanticRulesWorkspace] rule test failed', error)
    } finally {
      testLoading.value = false
    }
  }

  function openQCEvaluation() {
    showQCEvaluation.value = true
  }

  function closeQCEvaluation() {
    showQCEvaluation.value = false
  }

  async function goCustomWorkspace() {
    await router.push(toWsPath('customRulesExecute'))
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
    await refreshRules(false)
  }

  onMounted(() => {
    initialize()
  })

  onBeforeUnmount(() => {
    if (keywordTimer) {
      clearTimeout(keywordTimer)
      keywordTimer = null
    }
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
  }
}
