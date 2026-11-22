/**
 * 临床质控演示平台 Pinia Store
 * 管理病例、文书、质控结果等状态
 */
import { LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import ApiService from '@/services/apiService'
import { DEMO_CASES, getCaseById } from '@/data/demo-cases'
import type {
  Case,
  Document,
  QCResult,
  QCRuleSet,
  WholeCaseQCResult,
  FrontPageDraft,
  CaseFilter,
  Violation,
  SichuanQCEvaluateResponse,
  FrontPageGenerateResponse
} from '@/types/clinical-workstation'
import { DocumentTypeLabels } from '@/types/clinical-workstation'

// LocalStorage keys
const CUSTOM_CASES_KEY = 'clinical_workstation_custom_cases'
const MAX_CUSTOM_CASES = 10 // 最多保存10个自定义病例

export const useClinicalWorkstationStore = defineStore('clinicalWorkstation', () => {
  // ========== State ==========

  // 所有病例（预置+自定义）
  const cases = ref<Case[]>([])

  // 当前选中的病例ID和文书ID
  const currentCaseId = ref<string | null>(null)
  const currentDocumentId = ref<string | null>(null)

  // 质控结果缓存（key: documentId_ruleSet）
  const qcResults = ref<Map<string, QCResult>>(new Map())

  // 整病例质控结果
  const wholeCaseQCResult = ref<WholeCaseQCResult | null>(null)

  // 病案首页草稿
  const frontpageDraft = ref<FrontPageDraft | null>(null)

  // 分析状态
  const isQCAnalyzing = ref(false)
  const isFrontpageGenerating = ref(false)
  const isWholeCaseQCAnalyzing = ref(false)

  // 选中的规则集
  const selectedRuleSet = ref<QCRuleSet>('sichuan_146' as QCRuleSet)

  // 筛选条件
  const filter = ref<CaseFilter>({
    department: '全部',
    complexity: undefined,
    isCustom: undefined,
    keyword: ''
  })

  // 右侧CDSS面板激活的Tab
  const activeCdssTab = ref<'qc' | 'frontpage'>('qc')

  // ========== Getters ==========

  /**
   * 当前病例
   */
  const currentCase = computed<Case | null>(() => {
    if (!currentCaseId.value) return null
    return cases.value.find((c) => c.caseId === currentCaseId.value) || null
  })

  /**
   * 当前文书
   */
  const currentDocument = computed<Document | null>(() => {
    if (!currentCase.value || !currentDocumentId.value) return null
    return (
      currentCase.value.documents.find((d) => d.documentId === currentDocumentId.value) || null
    )
  })

  /**
   * 当前病例的所有文书
   */
  const documentsOfCurrentCase = computed<Document[]>(() => {
    return currentCase.value?.documents || []
  })

  /**
   * 当前文书的质控结果
   */
  const currentQCResult = computed<QCResult | null>(() => {
    if (!currentDocumentId.value) return null
    const key = `${currentDocumentId.value}_${selectedRuleSet.value}`
    return qcResults.value.get(key) || null
  })

  /**
   * 当前文书的违规项列表
   */
  const currentViolations = computed<Violation[]>(() => {
    return currentQCResult.value?.violations || []
  })

  /**
   * 筛选后的病例列表
   */
  const filteredCases = computed<Case[]>(() => {
    let result = cases.value

    // 按科室筛选
    if (filter.value.department && filter.value.department !== '全部') {
      result = result.filter((c) => c.visitInfo.department === filter.value.department)
    }

    // 按复杂度筛选
    if (filter.value.complexity) {
      result = result.filter((c) => c.diagnosisInfo.complexity === filter.value.complexity)
    }

    // 按是否自定义筛选
    if (filter.value.isCustom !== undefined) {
      result = result.filter((c) => c.metadata.isCustom === filter.value.isCustom)
    }

    // 关键字搜索
    if (filter.value.keyword) {
      const keyword = filter.value.keyword.toLowerCase()
      result = result.filter(
        (c) =>
          c.caseName.toLowerCase().includes(keyword) ||
          c.diagnosisInfo.diseaseType.toLowerCase().includes(keyword) ||
          c.visitInfo.department.toLowerCase().includes(keyword) ||
          c.patientInfo.name.toLowerCase().includes(keyword)
      )
    }

    return result
  })

  /**
   * 预置病例列表
   */
  const presetCases = computed<Case[]>(() => {
    return cases.value.filter((c) => !c.metadata.isCustom)
  })

  /**
   * 自定义病例列表
   */
  const customCases = computed<Case[]>(() => {
    return cases.value.filter((c) => c.metadata.isCustom)
  })

  // ========== Actions ==========

  /**
   * 初始化：加载预置病例和自定义病例
   */
  function initialize() {
    // 加载预置病例
    cases.value = [...DEMO_CASES]

    // 从localStorage加载自定义病例
    loadCustomCasesFromStorage()

    // 默认选中第一个病例的第一份文书
    if (cases.value.length > 0) {
      selectCase(cases.value[0].caseId)
    }
  }

  /**
   * 选择病例
   */
  function selectCase(caseId: string) {
    const targetCase = cases.value.find((c) => c.caseId === caseId)
    if (!targetCase) {
      message.error('病例不存在')
      return
    }

    currentCaseId.value = caseId

    // 自动选中该病例的第一份文书
    if (targetCase.documents.length > 0) {
      selectDocument(targetCase.documents[0].documentId)
    } else {
      currentDocumentId.value = null
    }

    // 清空病案首页草稿（切换病例时）
    frontpageDraft.value = null
  }

  /**
   * 选择文书
   */
  function selectDocument(documentId: string) {
    if (!currentCase.value) return

    const targetDocument = currentCase.value.documents.find((d) => d.documentId === documentId)
    if (!targetDocument) {
      message.error('文书不存在')
      return
    }

    currentDocumentId.value = documentId

    // 切换到质控Tab
    activeCdssTab.value = 'qc'
  }

  /**
   * 文书级质控分析
   */
  async function analyzeDocument(documentId?: string, ruleSet?: QCRuleSet) {
    const docId = documentId || currentDocumentId.value
    const rules = ruleSet || selectedRuleSet.value

    if (!docId) {
      message.error('请先选择文书')
      return
    }

    const document = currentCase.value?.documents.find((d) => d.documentId === docId)
    if (!document) {
      message.error('文书不存在')
      return
    }

    // 检查是否已有缓存结果
    const cacheKey = `${docId}_${rules}`
    if (qcResults.value.has(cacheKey)) {
      message.info('已有质控结果，直接显示')
      return
    }

    isQCAnalyzing.value = true

    try {
      // 调用四川质控API
      const response = await ApiService.post<SichuanQCEvaluateResponse>(
        '/api/v1/qc/sichuan/evaluate',
        {
          document_id: docId,
          document_content: document.content,
          document_type: DocumentTypeLabels[document.documentType] || '病程记录',
          persist: false,
          prompt_mode: 'plan_a' // 使用精简版提示词
        },
        { timeout: LONG_REQUEST_TIMEOUT_MS }
      )

      if (response.data && response.data.data) {
        const apiData = response.data.data

        // 转换为QCResult格式
        const qcResult: QCResult = {
          documentId: docId,
          caseId: currentCase.value?.caseId || '',
          ruleSet: rules,
          evaluationSummary: {
            totalRules: apiData.evaluation_summary.total_rules || 0,
            compliantRules: apiData.evaluation_summary.compliant_rules || 0,
            complianceRate: apiData.evaluation_summary.compliance_rate || 0,
            overallGrade: apiData.evaluation_summary.overall_grade || 'C',
            criticalViolations: apiData.evaluation_summary.critical_violations || 0
          },
          violations: transformViolations(apiData.evaluation_results || []),
          performanceMetrics: {
            processingTime: apiData.performance_metrics?.processing_time || 0,
            tokenUsage: apiData.performance_metrics?.token_usage || 0,
            estimatedCost: apiData.performance_metrics?.estimated_cost || 0
          },
          optimizationMetrics: apiData.optimization_metrics
            ? {
                tokenSavingsRate: apiData.optimization_metrics.token_savings_rate || 0,
                costSavings: apiData.optimization_metrics.cost_savings || 0
              }
            : undefined,
          timestamp: new Date().toISOString(),
          status: 'completed',
          mode: apiData.evaluation_summary.model,
          llmInfo: apiData.llm_info
        }

        // 缓存结果
        qcResults.value.set(cacheKey, qcResult)

        message.success(
          `质控分析完成！合规率：${qcResult.evaluationSummary.complianceRate.toFixed(1)}%`
        )
      } else {
        throw new Error('API返回数据格式错误')
      }
    } catch (error: any) {
      message.error(`质控分析失败：${error.message}`)
      console.error('质控分析失败：', error)
    } finally {
      isQCAnalyzing.value = false
    }
  }

  /**
   * 整病例质控分析
   */
  async function analyzeWholeCase(caseId?: string, ruleSet?: QCRuleSet) {
    const targetCaseId = caseId || currentCaseId.value
    const rules = ruleSet || selectedRuleSet.value

    if (!targetCaseId) {
      message.error('请先选择病例')
      return
    }

    const targetCase = cases.value.find((c) => c.caseId === targetCaseId)
    if (!targetCase) {
      message.error('病例不存在')
      return
    }

    if (targetCase.documents.length === 0) {
      message.error('该病例没有文书')
      return
    }

    isWholeCaseQCAnalyzing.value = true
    wholeCaseQCResult.value = null

    try {
      const documentResults: WholeCaseQCResult['documentResults'] = []

      // 顺序分析每份文书
      for (const document of targetCase.documents) {
        try {
          // 调用API
          const response = await ApiService.post<SichuanQCEvaluateResponse>(
            '/api/v1/qc/sichuan/evaluate',
            {
              document_id: document.documentId,
              document_content: document.content,
              document_type: DocumentTypeLabels[document.documentType] || '病程记录',
              persist: false,
              prompt_mode: 'plan_a'
            },
            { timeout: LONG_REQUEST_TIMEOUT_MS }
          )

          if (response.data && response.data.data) {
            const apiData = response.data.data

            documentResults.push({
              documentId: document.documentId,
              documentTitle: document.title,
              documentType: document.documentType,
              summary: {
                totalRules: apiData.evaluation_summary.total_rules || 0,
                compliantRules: apiData.evaluation_summary.compliant_rules || 0,
                complianceRate: apiData.evaluation_summary.compliance_rate || 0,
                overallGrade: apiData.evaluation_summary.overall_grade || 'C',
                criticalViolations: apiData.evaluation_summary.critical_violations || 0
              },
              violationsCount: apiData.evaluation_summary.issues_found || 0,
              status: 'completed'
            })

            // 同时缓存单文书结果
            const cacheKey = `${document.documentId}_${rules}`
            if (!qcResults.value.has(cacheKey)) {
              const qcResult: QCResult = {
                documentId: document.documentId,
                caseId: targetCaseId,
                ruleSet: rules,
                evaluationSummary: {
                  totalRules: apiData.evaluation_summary.total_rules || 0,
                  compliantRules: apiData.evaluation_summary.compliant_rules || 0,
                  complianceRate: apiData.evaluation_summary.compliance_rate || 0,
                  overallGrade: apiData.evaluation_summary.overall_grade || 'C',
                  criticalViolations: apiData.evaluation_summary.critical_violations || 0
                },
                violations: transformViolations(apiData.evaluation_results || []),
                performanceMetrics: {
                  processingTime: apiData.performance_metrics?.processing_time || 0,
                  tokenUsage: apiData.performance_metrics?.token_usage || 0,
                  estimatedCost: apiData.performance_metrics?.estimated_cost || 0
                },
                timestamp: new Date().toISOString(),
                status: 'completed'
              }
              qcResults.value.set(cacheKey, qcResult)
            }
          }
        } catch (error: any) {
          documentResults.push({
            documentId: document.documentId,
            documentTitle: document.title,
            documentType: document.documentType,
            summary: {
              totalRules: 0,
              compliantRules: 0,
              complianceRate: 0,
              overallGrade: 'F',
              criticalViolations: 0
            },
            violationsCount: 0,
            status: 'failed'
          })
          console.error(`文书 ${document.title} 质控失败：`, error)
        }
      }

      // 计算整病例汇总
      const totalDocuments = documentResults.length
      const analyzedDocuments = documentResults.filter((r) => r.status === 'completed').length
      const totalViolations = documentResults.reduce((sum, r) => sum + r.violationsCount, 0)
      const averageComplianceRate =
        analyzedDocuments > 0
          ? documentResults
              .filter((r) => r.status === 'completed')
              .reduce((sum, r) => sum + r.summary.complianceRate, 0) / analyzedDocuments
          : 0

      let overallGrade = 'F'
      if (averageComplianceRate >= 90) overallGrade = 'A'
      else if (averageComplianceRate >= 80) overallGrade = 'B'
      else if (averageComplianceRate >= 70) overallGrade = 'C'
      else if (averageComplianceRate >= 60) overallGrade = 'D'

      wholeCaseQCResult.value = {
        caseId: targetCaseId,
        caseName: targetCase.caseName,
        ruleSet: rules,
        documentResults,
        overallSummary: {
          totalDocuments,
          analyzedDocuments,
          averageComplianceRate,
          totalViolations,
          overallGrade
        },
        timestamp: new Date().toISOString()
      }

      message.success(
        `整病例质控完成！平均合规率：${averageComplianceRate.toFixed(1)}%，总违规数：${totalViolations}`
      )
    } catch (error: any) {
      message.error(`整病例质控失败：${error.message}`)
      console.error('整病例质控失败：', error)
    } finally {
      isWholeCaseQCAnalyzing.value = false
    }
  }

  /**
   * 生成病案首页草稿
   */
  async function generateFrontpage(caseId?: string) {
    const targetCaseId = caseId || currentCaseId.value

    if (!targetCaseId) {
      message.error('请先选择病例')
      return
    }

    const targetCase = cases.value.find((c) => c.caseId === targetCaseId)
    if (!targetCase) {
      message.error('病例不存在')
      return
    }

    isFrontpageGenerating.value = true
    frontpageDraft.value = null

    try {
      // 调用病案首页生成API
      const response = await ApiService.post<FrontPageGenerateResponse>(
        '/api/v1/frontpage/auto-generate-draft',
        {
          visit_id: targetCase.visitInfo.visitId,
          documents: targetCase.documents.map((doc) => ({
            type: DocumentTypeLabels[doc.documentType] || '其他',
            content: doc.content,
            meta: doc.metadata
          }))
        },
        { timeout: LONG_REQUEST_TIMEOUT_MS }
      )

      if (response.data && response.data.data && response.data.data.frontpage) {
        frontpageDraft.value = response.data.data.frontpage
        activeCdssTab.value = 'frontpage' // 切换到病案首页Tab
        message.success('病案首页草稿生成完成')
      } else {
        throw new Error('API返回数据格式错误')
      }
    } catch (error: any) {
      message.error(`病案首页生成失败：${error.message}`)
      console.error('病案首页生成失败：', error)
    } finally {
      isFrontpageGenerating.value = false
    }
  }

  /**
   * 添加自定义病例
   */
  function addCustomCase(customCase: Case) {
    // 验证必填字段
    if (!customCase.caseName || !customCase.patientInfo.name) {
      message.error('请填写病例名称和患者姓名')
      return
    }

    if (customCase.documents.length === 0) {
      message.error('请至少添加一份文书')
      return
    }

    // 标记为自定义
    customCase.metadata.isCustom = true
    customCase.metadata.createdAt = new Date().toISOString()

    // 添加到病例列表
    cases.value.push(customCase)

    // 保存到localStorage
    saveCustomCasesToStorage()

    message.success('自定义病例已添加')

    // 自动选中该病例
    selectCase(customCase.caseId)
  }

  /**
   * 删除自定义病例
   */
  function deleteCustomCase(caseId: string) {
    const index = cases.value.findIndex((c) => c.caseId === caseId && c.metadata.isCustom)
    if (index === -1) {
      message.error('病例不存在或非自定义病例')
      return
    }

    cases.value.splice(index, 1)
    saveCustomCasesToStorage()

    // 如果删除的是当前病例，切换到第一个病例
    if (currentCaseId.value === caseId) {
      if (cases.value.length > 0) {
        selectCase(cases.value[0].caseId)
      } else {
        currentCaseId.value = null
        currentDocumentId.value = null
      }
    }

    message.success('自定义病例已删除')
  }

  /**
   * 更新筛选条件
   */
  function updateFilter(newFilter: Partial<CaseFilter>) {
    filter.value = { ...filter.value, ...newFilter }
  }

  /**
   * 重置筛选条件
   */
  function resetFilter() {
    filter.value = {
      department: '全部',
      complexity: undefined,
      isCustom: undefined,
      keyword: ''
    }
  }

  /**
   * 切换规则集
   */
  function switchRuleSet(ruleSet: QCRuleSet) {
    selectedRuleSet.value = ruleSet
    message.info(`已切换到规则集：${ruleSet}`)
  }

  /**
   * 从localStorage加载自定义病例
   */
  function loadCustomCasesFromStorage() {
    try {
      const stored = localStorage.getItem(CUSTOM_CASES_KEY)
      if (stored) {
        const customCases: Case[] = JSON.parse(stored)
        cases.value.push(...customCases)
      }
    } catch (error) {
      console.error('加载自定义病例失败：', error)
    }
  }

  /**
   * 保存自定义病例到localStorage
   */
  function saveCustomCasesToStorage() {
    try {
      const customCasesList = cases.value.filter((c) => c.metadata.isCustom)
      // 只保留最近的MAX_CUSTOM_CASES个
      const toSave = customCasesList.slice(-MAX_CUSTOM_CASES)
      localStorage.setItem(CUSTOM_CASES_KEY, JSON.stringify(toSave))
    } catch (error) {
      console.error('保存自定义病例失败：', error)
      message.warning('自定义病例保存失败，请检查浏览器存储空间')
    }
  }

  /**
   * 清空所有自定义病例
   */
  function clearAllCustomCases() {
    cases.value = cases.value.filter((c) => !c.metadata.isCustom)
    localStorage.removeItem(CUSTOM_CASES_KEY)
    message.success('所有自定义病例已清空')

    // 如果当前病例被删除，切换到第一个预置病例
    if (currentCaseId.value && !cases.value.find((c) => c.caseId === currentCaseId.value)) {
      if (cases.value.length > 0) {
        selectCase(cases.value[0].caseId)
      } else {
        currentCaseId.value = null
        currentDocumentId.value = null
      }
    }
  }

  /**
   * 转换违规项数据格式
   */
  function transformViolations(evaluationResults: any[]): Violation[] {
    return evaluationResults
      .filter((result) => !result.is_compliant && result.status === 'non_compliant')
      .map((result) => ({
        ruleId: result.rule_id || '',
        ruleName: result.rule_name || '未知规则',
        severity: determineSeverity(result),
        description: result.findings || result.description || '无描述',
        evidence: result.evidence ? [result.evidence] : [],
        location: result.location || '',
        suggestion: result.suggestion || '无改进建议',
        confidence: result.confidence || 0
      }))
  }

  /**
   * 判断违规严重程度
   */
  function determineSeverity(result: any): 'critical' | 'major' | 'minor' {
    // 根据规则ID前缀或其他字段判断
    const ruleId = result.rule_id || ''
    if (ruleId.startsWith('C-') || result.critical) {
      return 'critical'
    } else if (ruleId.startsWith('M-') || result.major) {
      return 'major'
    } else {
      return 'minor'
    }
  }

  return {
    // State
    cases,
    currentCaseId,
    currentDocumentId,
    qcResults,
    wholeCaseQCResult,
    frontpageDraft,
    isQCAnalyzing,
    isFrontpageGenerating,
    isWholeCaseQCAnalyzing,
    selectedRuleSet,
    filter,
    activeCdssTab,

    // Getters
    currentCase,
    currentDocument,
    documentsOfCurrentCase,
    currentQCResult,
    currentViolations,
    filteredCases,
    presetCases,
    customCases,

    // Actions
    initialize,
    selectCase,
    selectDocument,
    analyzeDocument,
    analyzeWholeCase,
    generateFrontpage,
    addCustomCase,
    deleteCustomCase,
    updateFilter,
    resetFilter,
    switchRuleSet,
    clearAllCustomCases
  }
})
