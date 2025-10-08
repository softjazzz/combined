/**
 * LLM质控演示系统状态管理
 * 管理演示流程、数据状态和用户交互
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DemoState,
  DemoConfig,
  QCResult,
  QCNotification,
  Appeal,
  DemoStep,
  QualityControlRule,
  AnalysisStep,
  AppealReason
} from '@/types/quality-control'
import type { MedicalRecord } from '@/types/medical-records'
import { DemoDataService } from '@/services/demoDataService'
import { ApiService } from '@/services/apiService'
import type { QCAnalysisRequest } from '@/types'

// ==================== 工具函数 ====================

/**
 * 生成唯一ID
 */
const generateId = () => {
  return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

export const useQCDemoStore = defineStore('qcDemo', () => {
  // ==================== 数据服务实例 ====================

  const demoDataService = DemoDataService.getInstance()

  // ==================== 状态定义 ====================

  // 演示状态
  const isRunning = ref(false)
  const isPaused = ref(false)
  const currentStep = ref<DemoState['currentStep']>('target')
  const progress = ref(0)
  const error = ref<string | null>(null)

  // 数据库连接状态
  const isDatabaseConnected = ref(false)
  const isLoadingData = ref(false)

  // 数据状态
  const selectedRules = ref<any[]>([])
  const testRecord = ref<MedicalRecord | null>(null)
  // 所选文书（支持单选或多选；为兼容旧逻辑，仍命名为 selectedDocument）
  type DocInfo = { id: string; title?: string; type?: string; created_at?: string }
  const selectedDocument = ref<DocInfo | DocInfo[] | null>(null)
  const analysisResult = ref<QCResult | null>(null)
  const analysisSteps = ref<AnalysisStep[]>([])

  // 可用数据
  const availableRecords = ref<MedicalRecord[]>([])
  const availableRules = ref<any[]>([])
  const availableDepartments = ref<string[]>([])

  // 筛选状态
  const recordFilters = ref({
    search: '',
    department: '',
    status: ''
  })
  const ruleFilters = ref({
    category: '',
    severity: '',
    isActive: true
  })

  // 通知状态
  const notifications = ref<QCNotification[]>([])
  const activeNotification = ref<QCNotification | null>(null)
  const showNotificationModal = ref(false)

  // 申诉状态
  const appeals = ref<Appeal[]>([])
  const currentAppeal = ref<Appeal | null>(null)
  const showAppealModal = ref(false)

  // 演示配置
  const demoConfig = ref<DemoConfig>({
    selectedRules: [],
    testRecordId: '',
    simulateRealTime: true,
    showAnalysisSteps: true,
    enableNotifications: true,
    autoAdvance: false,
    stepDelay: 2000
  })

  // ==================== 计算属性 ====================

  const unreadNotifications = computed(() =>
    notifications.value.filter(n => !n.isRead)
  )

  const pendingAppeals = computed(() =>
    appeals.value.filter(a => a.status === 'pending')
  )

  const canStartDemo = computed(() =>
    selectedRules.value.length > 0 && !!testRecord.value && selectedDocumentList.value.length > 0 && !isRunning.value
  )

  const demoProgress = computed(() => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    const idx = steps.indexOf(currentStep.value)
    return idx < 0 ? 0 : Math.round((idx / (steps.length - 1)) * 100)
  })
  // 统一获取文书列表与主文书（向后兼容使用主文书）
  const selectedDocumentList = computed<DocInfo[]>(() => {
    if (!selectedDocument.value) return []
    return Array.isArray(selectedDocument.value) ? selectedDocument.value : [selectedDocument.value]
  })
  const selectedDocumentPrimary = computed<DocInfo | null>(() => selectedDocumentList.value[0] || null)


  // ==================== Actions ====================

  /**
   * 初始化演示环境
   */
  const initializeDemo = async (config: Partial<DemoConfig> = {}, restoreState = true) => {
    try {
      // 更新配置
      demoConfig.value = { ...demoConfig.value, ...config }

      // 首先加载可用数据（无论是否恢复状态都需要）
      await loadTestData()

      // 尝试恢复保存的状态
      if (restoreState) {
        const restored = await restoreDemoState()
        if (restored) {
          console.log('演示状态已从本地存储恢复，但已重新加载可用数据')
          return
        }
      }

      // 重置状态
      resetDemoState()

      // 保存初始状态
      await saveDemoState()

      console.log('演示环境初始化完成')
    } catch (err) {
      error.value = `初始化失败: ${err instanceof Error ? err.message : '未知错误'}`
      throw err
    }
  }

  /**
   * 开始演示
   */
  const startDemo = async () => {
    if (!canStartDemo.value) {
      throw new Error('演示条件不满足，请检查规则、病历与文书是否选择完整')
    }

    try {
      isRunning.value = true
      currentStep.value = 'run'
      progress.value = demoProgress.value
      error.value = null

      console.log('开始LLM质控演示')

      if (demoConfig.value.autoAdvance) {
        await runAutoDemo()
      } else {
        // 手动模式直接执行分析
        await executeStep('run')
      }
    } catch (err) {
      error.value = `启动演示失败: ${err instanceof Error ? err.message : '未知错误'}`
      isRunning.value = false
      throw err
    }
  }

  /**
   * 暂停/恢复演示
   */
  const togglePause = () => {
    isPaused.value = !isPaused.value
    console.log(isPaused.value ? '演示已暂停' : '演示已恢复')
  }

  /**
   * 停止演示
   */
  const stopDemo = () => {
    isRunning.value = false
    isPaused.value = false
    currentStep.value = 'rules'
    progress.value = 0
    console.log('演示已停止')
  }

  /**
   * 进入下一步
   */
  const nextStep = async () => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    const currentIndex = steps.indexOf(currentStep.value)
    if (currentIndex < steps.length - 1) {
      currentStep.value = steps[currentIndex + 1]
      progress.value = demoProgress.value
      await executeStep(currentStep.value)
    }
  }

  /**
   * 返回上一步
   */
  const previousStep = async () => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    const currentIndex = steps.indexOf(currentStep.value)
    if (currentIndex > 0) {
      currentStep.value = steps[currentIndex - 1]
      progress.value = demoProgress.value
      await saveDemoState()
    }
  }

  /**
   * 跳转到指定步骤
   */
  const jumpToStep = async (step: DemoState['currentStep']) => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    if (steps.includes(step)) {
      currentStep.value = step
      progress.value = demoProgress.value
      if (step === 'run' && canStartDemo.value) {
        await executeStep('run')
      }
      await saveDemoState()
      console.log(`已跳转到步骤: ${step}`)
    }
  }

  /**
   * 重播演示
   */
  const replayDemo = async () => {
    // 保存当前配置
    const currentConfig = { ...demoConfig.value }

    // 重置状态但保持配置
    resetDemoState()
    demoConfig.value = currentConfig

    // 重新加载测试数据
    await loadTestData()

    // 保存重置后的状态
    await saveDemoState()

    console.log('演示已重置，可以重新开始')
  }

  const normalizeSeverity = (severity?: string): 'low' | 'medium' | 'high' | 'critical' => {
    const value = (severity || '').toString().toLowerCase()
    if (['critical', 'fatal', '严重', '紧急'].includes(value)) return 'critical'
    if (['high', 'major', '较重', 'highrisk'].includes(value)) return 'high'
    if (['low', 'minor', '轻', '提醒'].includes(value)) return 'low'
    return 'medium'
  }

  const normalizePriority = (priority?: string): 'low' | 'medium' | 'high' => {
    const value = (priority || '').toString().toLowerCase()
    if (['high', 'urgent', '紧急'].includes(value)) return 'high'
    if (['low', 'minor', '可选'].includes(value)) return 'low'
    return 'medium'
  }

  const adaptQCResultFromBackend = (raw: unknown): QCResult => {
    const issues = Array.isArray(raw?.issues)
      ? raw.issues.map((issue: unknown) => ({
          id: issue.id || generateId(),
          ruleName: issue.rule_name || issue.ruleName || '未命名规则',
          ruleId: issue.rule_id || issue.ruleId || '',
          description: issue.description || '检测到该规则存在待改进项',
          severity: normalizeSeverity(issue.severity),
          category: issue.category || 'general',
          location: issue.location || '病历正文',
          suggestion: issue.suggestion || '请补充相关内容，确保记录规范完整',
          canAppeal: true
        }))
      : []

    const suggestions = Array.isArray(raw?.suggestions)
      ? raw.suggestions.map((item: unknown) => ({
          id: item.id || generateId(),
          category: item.category || '整改建议',
          title: item.title || '完善质控项',
          description: item.description || '根据分析结果更新或补充文书内容。',
          priority: normalizePriority(item.priority),
          actionRequired: item.action_required !== false
        }))
      : []

    const ruleResults = Array.isArray(raw?.rule_results)
      ? raw.rule_results.map((rr: unknown) => ({
          ruleId: rr.rule_id || rr.ruleId || '',
          ruleName: rr.rule_name || rr.ruleName || '质控规则',
          passed: Boolean(rr.passed),
          score: Number(rr.score ?? 0),
          maxScore: Number(rr.max_score ?? 100),
          details: rr.details || '',
          executionTime: Number(rr.execution_time ?? 1000),
          confidence: Number(
            rr.confidence ?? (rr.passed ? 0.9 : 0.7)
          )
        }))
      : []

    const steps = Array.isArray(raw?.analysis_steps)
      ? raw.analysis_steps.map((step: unknown): AnalysisStep => ({
          id: step.id || generateId(),
          name: step.name || '质控步骤',
          description: step.description || '',
          status: (step.status || 'completed') as AnalysisStep['status'],
          startTime: step.started_at ? new Date(step.started_at) : undefined,
          endTime: step.completed_at ? new Date(step.completed_at) : undefined,
          result: step.result,
          error: step.error
        }))
      : []

    const confidenceFallback = ruleResults.length
      ? Number(
          (
            ruleResults.reduce((acc, item) => acc + (item.confidence ?? 0.75), 0) /
            ruleResults.length
          ).toFixed(2)
        )
      : 0.8

    const metadata = raw?.metadata
      ? {
          analysisVersion: raw.metadata.analysisVersion || '1.0.0',
          modelVersion: raw.metadata.modelVersion || 'demo-qc-engine',
          processingTime: raw.metadata.processingTime ?? 0,
          rulesApplied: raw.metadata.rulesApplied ?? ruleResults.length,
          totalTokens: raw.metadata.totalTokens,
          confidence: raw.metadata.confidence ?? confidenceFallback,
          documents: raw.metadata.documents,
          record: raw.metadata.record,
          engine: raw.metadata.engine,
          analysisId: raw.metadata.analysisId || raw.id,
          scoreBaseline: raw.metadata.scoreBaseline
        }
      : {
          analysisVersion: '1.0.0',
          modelVersion: 'demo-qc-engine',
          processingTime: 0,
          rulesApplied: ruleResults.length,
          confidence: confidenceFallback
        }

    return {
      id: raw?.id || raw?.analysis_id || `qc-result-${Date.now()}`,
      recordId: raw?.record_id || raw?.recordId || testRecord.value?.id || 'unknown',
      overallScore: Number(raw?.overall_score ?? raw?.overallScore ?? 0),
      overallGrade: raw?.overall_grade || raw?.overallGrade || 'B',
      analysisDate: raw?.analysis_date || raw?.analysisDate || new Date().toISOString(),
      issues,
      suggestions,
      ruleResults,
      analysisSteps: steps,
      metadata
    }
  }

  /**
   * 执行质控分析演示
   */
  const runQCAnalysis = async () => {
    if (!testRecord.value || selectedDocumentList.value.length === 0 || selectedRules.value.length === 0) {
      throw new Error('缺少测试对象（病历或文书）或质控规则')
    }

    currentStep.value = 'run'

    const baseSteps: AnalysisStep[] = [
      { id: 'prepare', name: '准备数据', description: '整合所选病历、文书与规则', status: 'pending' },
      { id: 'engine', name: '调用质控引擎', description: '将分析任务发送至后端质控引擎', status: 'pending' },
      { id: 'fetch', name: '获取分析结果', description: '等待并解析质控分析结果', status: 'pending' },
      { id: 'notify', name: '生成通知', description: '同步质控结果至演示面板', status: 'pending' }
    ]
    analysisSteps.value = baseSteps.map(step => ({ ...step }))

    const stepDelay = Math.max(0, Number(demoConfig.value.stepDelay) || 0)
    const runStep = async (index: number, handler: () => Promise<void>) => {
      const step = analysisSteps.value[index]
      step.status = 'running'
      step.startTime = new Date()
      try {
        await handler()
        if (stepDelay > 0) {
          await sleep(stepDelay)
        }
        step.status = 'completed'
      } catch (err) {
        step.status = 'error'
        step.error = err instanceof Error ? err.message : String(err)
        throw err
      } finally {
        step.endTime = new Date()
      }
    }

    let analysisId = ''

    try {
      await runStep(0, async () => {
        error.value = null
        analysisResult.value = null
        progress.value = 5
      })

      await runStep(1, async () => {
        const payload: QCAnalysisRequest = {
          recordId: testRecord.value!.id,
          content: testRecord.value?.content || '',
          rules: selectedRules.value.map(rule => ({
            id: rule.id,
            name: rule.name,
            description: rule.description || '',
            weight: Number(rule.weight ?? rule.maxScore ?? 10) || 1,
            category: rule.category,
            severity: rule.severity,
            ruleCode: rule.ruleCode || rule.rule_code
          })),
          documents: selectedDocumentList.value.map(doc => ({
            id: doc.id,
            title: doc.title,
            type: doc.type
          })),
          recordMetadata: {
            patientName: testRecord.value?.patient_name,
            department: testRecord.value?.department,
            qcScore: testRecord.value?.qc_score,
            admissionDate: testRecord.value?.admission_date,
            documentCount: selectedDocumentList.value.length
          },
          options: {
            dataSource: isDatabaseConnected.value ? 'database' : 'mock',
            autoAdvance: demoConfig.value.autoAdvance
          }
        }

        const response = await ApiService.analyzeRecord(testRecord.value!.id, payload)
        if (!response.success || !response.data) {
          throw new Error(response.error || '质控引擎未返回结果')
        }
        analysisId = response.data.analysis_id || response.data.analysisId || ''
        progress.value = 45
      })

      let backendResult: unknown = null
      await runStep(2, async () => {
        const maxAttempts = 5
        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          const resultResponse = await ApiService.getQCResult(testRecord.value!.id)
          if (resultResponse.success && resultResponse.data) {
            backendResult = resultResponse.data
            break
          }
          await sleep(300 + attempt * 200)
        }

        if (!backendResult) {
          throw new Error('质控结果尚未生成，请稍后重试')
        }

        const adapted = adaptQCResultFromBackend(backendResult)
        if (adapted.analysisSteps && adapted.analysisSteps.length > 0) {
          analysisSteps.value = analysisSteps.value.map((step, index) => {
            const backendStep = adapted.analysisSteps?.[index]
            if (backendStep) {
              return {
                ...step,
                ...backendStep,
                status: backendStep.status,
                startTime: backendStep.startTime ?? step.startTime,
                endTime: backendStep.endTime ?? new Date()
              }
            }
            return {
              ...step,
              status: step.status === 'error' ? 'error' : 'completed',
              endTime: step.endTime || new Date()
            }
          })
        } else {
          analysisSteps.value = analysisSteps.value.map(step => ({
            ...step,
            status: step.status === 'error' ? 'error' : 'completed',
            endTime: step.endTime || new Date()
          }))
        }

        analysisResult.value = { ...adapted, analysisSteps: analysisSteps.value }
        if (analysisResult.value) {
          analysisResult.value.metadata = {
            ...(analysisResult.value.metadata || {
              analysisVersion: '1.0.0',
              modelVersion: 'demo-qc-engine',
              processingTime: 0,
              rulesApplied: analysisResult.value.ruleResults.length,
              confidence:
                analysisResult.value.ruleResults.reduce((acc, item) => acc + item.confidence, 0) /
                Math.max(analysisResult.value.ruleResults.length, 1)
            }),
            analysisId: analysisResult.value.metadata?.analysisId || analysisId || analysisResult.value.id
          }
        }
        progress.value = 85
      })

      await runStep(3, async () => {
        if (analysisResult.value) {
          simulateQCNotification(analysisResult.value)
          if (demoConfig.value.enableNotifications) {
            playNotificationSound()
          }
        }
        progress.value = 95
      })

      progress.value = 100
      isRunning.value = false
      await saveDemoState()

      console.log('质控分析完成', {
        analysisId,
        record: testRecord.value?.id,
        rules: selectedRules.value.length
      })
    } catch (err) {
      console.error('[QCDemoStore] runQCAnalysis failed:', err)
      error.value = `分析失败: ${err instanceof Error ? err.message : '未知错误'}`
      isRunning.value = false
      throw err
    }
  }

  /**
   * 模拟质控通知
   */
  const simulateQCNotification = (result: QCResult) => {
    const notification: QCNotification = {
      id: `notification-${Date.now()}`,
      type: result.overallScore < 60 ? 'error' : result.overallScore < 80 ? 'warning' : 'success',
      title: '质控分析完成',
      message: `病历质控评分: ${result.overallScore}分，发现 ${result.issues.length} 个问题`,
      qcResult: result,
      timestamp: new Date(),
      isRead: false,
      canAppeal: result.issues.some(issue => issue.canAppeal),
      severity: result.overallScore < 60 ? 'critical' : result.overallScore < 80 ? 'high' : 'low',
      status: 'pending'
    }

    if (result.metadata?.record) {
      notification.recordInfo = {
        patientName: result.metadata.record.patientName || result.metadata.record.name,
        recordNumber: result.metadata.record.recordNumber || result.recordId,
        department: result.metadata.record.department,
        status: '待处理'
      }
    }

    notifications.value.unshift(notification)

    if (demoConfig.value.enableNotifications) {
      activeNotification.value = notification
      showNotificationModal.value = true
    }

    console.log('质控通知已生成', notification)
  }

  /**
   * 创建申诉
   */
  const createAppeal = async (appealData: unknown) => {
    if (!activeNotification.value && !appealData.notificationId) {
      throw new Error('没有可申诉的通知')
    }

    const targetNotification = activeNotification.value ||
      notifications.value.find(n => n.id === appealData.notificationId)

    if (!targetNotification) {
      throw new Error('找不到相关通知')
    }

    const appeal: Appeal = {
      id: appealData.id || `appeal-${Date.now()}`,
      qcResultId: targetNotification.qcResult?.id || '',
      notificationId: targetNotification.id,
      reason: appealData.reason,
      reasonText: appealData.reasonText || '',
      description: appealData.description,
      attachments: appealData.attachments || [],
      status: 'pending',
      submittedAt: appealData.submittedAt || new Date(),
      submittedBy: appealData.submittedBy || 'demo-user',
      appealType: appealData.appealType || 'quality_dispute',
      priority: appealData.priority || 'medium',
      contact: appealData.contact || '',
      reviewerComment: '',
      reviewedAt: null,
      reviewedBy: '',
      estimatedReviewTime: appealData.estimatedReviewTime || new Date(Date.now() + 3 * 24 * 60 * 60 * 1000)
    }

    appeals.value.unshift(appeal)
    currentAppeal.value = appeal

    // 更新通知状态
    targetNotification.appealId = appeal.id
    targetNotification.status = 'appealed'

    // 启动模拟审核流程
    setTimeout(() => {
      simulateAppealReview(appeal.id)
    }, 5000) // 5秒后开始审核

    console.log('申诉已创建', appeal)
    return appeal
  }

  /**
   * 模拟申诉审核流程
   */
  const simulateAppealReview = (appealId: string) => {
    const appeal = appeals.value.find(a => a.id === appealId)
    if (!appeal) return

    // 更新状态为审核中
    appeal.status = 'reviewing'

    // 模拟审核过程
    setTimeout(() => {
      // 随机决定审核结果 (70% 通过率)
      const isApproved = Math.random() > 0.3

      appeal.status = isApproved ? 'approved' : 'rejected'
      appeal.reviewedAt = new Date()
      appeal.reviewedBy = '质控审核员'
      appeal.reviewerComment = isApproved
        ? '经审核，您的申诉理由充分，质控结果已更新。感谢您的反馈，这有助于我们改进质控规则。'
        : '经审核，原质控结果准确，申诉不予通过。如有异议，可提供更多证据重新申诉。'

      // 如果申诉通过，更新相关通知的质控结果
      if (isApproved && appeal.notificationId) {
        const notification = notifications.value.find(n => n.id === appeal.notificationId)
        if (notification && notification.qcResult) {
          // 提高评分
          notification.qcResult.overallScore = Math.min(100, notification.qcResult.overallScore + 15)
          // 移除部分问题
          if (notification.qcResult.issues && notification.qcResult.issues.length > 0) {
            notification.qcResult.issues.splice(0, 1)
          }
          // 更新等级
          if (notification.qcResult.overallScore >= 95) {
            notification.qcResult.overallGrade = 'A+'
          } else if (notification.qcResult.overallScore >= 90) {
            notification.qcResult.overallGrade = 'A'
          } else if (notification.qcResult.overallScore >= 80) {
            notification.qcResult.overallGrade = 'B'
          }
        }
      }

      // 发送审核结果通知
      const resultNotification: QCNotification = {
        id: generateId(),
        type: isApproved ? 'success' : 'info',
        severity: isApproved ? 'low' : 'medium',
        title: `申诉审核结果通知`,
        message: `您提交的申诉 ${appeal.id} 已${isApproved ? '通过' : '被驳回'}审核`,
        timestamp: new Date(),
        isRead: false,
        status: 'pending',
        canAppeal: !isApproved,
        recordInfo: {
          patientName: '相关患者',
          recordNumber: 'MR' + Date.now(),
          department: '相关科室',
          doctor: appeal.submittedBy,
          admissionDate: new Date().toISOString().split('T')[0],
          status: '已处理'
        },
        qcResult: {
          overallScore: isApproved ? 95 : 75,
          overallGrade: isApproved ? 'A' : 'B',
          analysisDate: new Date().toISOString(),
          issues: [],
          suggestions: [],
          ruleResults: [],
          analysisSteps: [],
          metadata: {
            analysisVersion: '1.0.0',
            modelVersion: 'gpt-4',
            processingTime: 2000,
            rulesApplied: 3,
            confidence: 0.9
          }
        }
      }

      notifications.value.unshift(resultNotification)

    }, 8000) // 8秒后完成审核
  }

  /**
   * 重置演示状态
   */
  const resetDemoState = () => {
    isRunning.value = false
    isPaused.value = false
    currentStep.value = 'target'
    progress.value = 0
    error.value = null
    analysisResult.value = null
    analysisSteps.value = []
    notifications.value = []
    activeNotification.value = null
    appeals.value = []
    currentAppeal.value = null
    showNotificationModal.value = false
    showAppealModal.value = false
    // 清空所选文书
    selectedDocument.value = null
  }

  // ==================== 私有方法 ====================

  /**
   * 加载测试数据
   */
  const loadTestData = async (forceRefresh = false) => {
    isLoadingData.value = true
    error.value = null // 清除之前的错误

    try {
      console.log('[QCDemoStore] 开始加载测试数据...')

      // 检查数据库连接（支持强制刷新）
      isDatabaseConnected.value = await demoDataService.checkConnection({
        timeoutMs: 1500,
        forceRefresh
      })

      // 并行加载所有数据以提高性能
      // 优先尝试使用本地API，失败时回退到Supabase
      let records: unknown[] = []
      let rules: unknown[] = []
      let departments: string[] = []

      try {
        console.log('[QCDemoStore] 尝试使用本地API加载数据...')
        // 尝试使用本地API
        const [apiRecords, apiRules] = await Promise.all([
          ApiService.getMedicalRecords({ page: 1, page_size: 20 }),
          ApiService.getQCRules()
        ])

        if (apiRecords.success && apiRecords.data?.data) {
          records = apiRecords.data.data.map((record: unknown) => ({
            ...record,
            // 数据结构适配：将 patient_info.name 映射到 patient_name
            patient_name: record.patient_info?.name || record.patient_name || '未知患者',
            // 添加其他可能需要的字段映射
            admission_date: record.admission_date || record.created_at?.split('T')[0] || '未知',
            qc_score: record.qc_score || record.ai_confidence_score || 0
          }))
          console.log('[QCDemoStore] ✅ 本地API医疗记录加载成功:', records.length)
        }

        if (apiRules.success && apiRules.data?.data) {
          rules = apiRules.data.data
          console.log('[QCDemoStore] ✅ 本地API质控规则加载成功:', rules.length)
        }

        // 从记录中提取科室信息
        departments = [...new Set(records.map(r => r.department).filter(Boolean))]

        // 如果本地API成功，标记数据库已连接
        if (records.length > 0 && rules.length > 0) {
          isDatabaseConnected.value = true
          console.log('[QCDemoStore] ✅ 本地API连接成功')
        } else {
          throw new Error('本地API返回数据为空')
        }
      } catch (apiError) {
        console.warn('[QCDemoStore] 本地API失败，回退到Supabase:', apiError)

        // 回退到原有的Supabase逻辑
        const [supabaseRecords, supabaseRules, supabaseDepartments] = await Promise.all([
          demoDataService.getMedicalRecords({
            limit: 20,
            ...recordFilters.value
          }),
          demoDataService.getQCRules({
            limit: 50,
            ...ruleFilters.value
          }),
          demoDataService.getDepartments()
        ])

        // 对Supabase数据也进行相同的数据结构适配
        records = supabaseRecords.map((record: unknown) => ({
          ...record,
          // 数据结构适配：确保 patient_name 字段存在
          patient_name: record.patient_info?.name || record.patient_name || '未知患者',
          admission_date: record.admission_date || record.created_at?.split('T')[0] || '未知',
          qc_score: record.qc_score || record.ai_confidence_score || 0
        }))
        rules = supabaseRules
        departments = supabaseDepartments
      }

      availableRecords.value = records
      availableRules.value = rules
      availableDepartments.value = departments

      // 智能选择默认测试记录
      if (!testRecord.value && availableRecords.value.length > 0) {
        // 优先选择有完整信息的记录
        const preferredRecord = availableRecords.value.find(r =>
          r.patient_info && r.primary_diagnosis
        ) || availableRecords.value[0]
        testRecord.value = preferredRecord
      }

      // 智能选择默认规则
      if (selectedRules.value.length === 0 && availableRules.value.length > 0) {
        // 优先选择不同类别的活跃规则
        const categories = new Set<string>()
        const selectedRulesList: unknown[] = []

        for (const rule of availableRules.value.filter(r => r.isActive)) {
          if (selectedRulesList.length >= 3) break
          if (!categories.has(rule.category) || selectedRulesList.length < 2) {
            selectedRulesList.push(rule)
            categories.add(rule.category)
          }
        }

        selectedRules.value = selectedRulesList
      }

      const dataSource = isDatabaseConnected.value ? '数据库' : '模拟数据'
      console.log(`[QCDemoStore] 数据加载完成 (${dataSource}):`, {
        records: availableRecords.value.length,
        rules: availableRules.value.length,
        departments: availableDepartments.value.length,
        connected: isDatabaseConnected.value,
        selectedRecord: testRecord.value?.id,
        selectedRules: selectedRules.value.length
      })

    } catch (err) {
      console.error('[QCDemoStore] 数据加载失败:', err)
      const errorMessage = err instanceof Error ? err.message : '未知错误'
      error.value = `数据加载失败: ${errorMessage}`

      // 即使出错也要确保有基本的模拟数据可用
      if (availableRecords.value.length === 0 || availableRules.value.length === 0) {
        console.log('[QCDemoStore] 尝试加载备用模拟数据...')
        try {
          // 强制使用模拟数据
          isDatabaseConnected.value = false
          availableRecords.value = await demoDataService.getMedicalRecords({ limit: 10 })
          availableRules.value = await demoDataService.getQCRules({ limit: 20 })
          availableDepartments.value = await demoDataService.getDepartments()

          if (!testRecord.value && availableRecords.value.length > 0) {
            testRecord.value = availableRecords.value[0]
          }
          if (selectedRules.value.length === 0 && availableRules.value.length > 0) {
            selectedRules.value = availableRules.value.filter(r => r.isActive).slice(0, 3)
          }

          console.log('[QCDemoStore] 备用模拟数据加载成功')
        } catch (fallbackError) {
          console.error('[QCDemoStore] 备用数据加载也失败:', fallbackError)
        }
      }
    } finally {
      isLoadingData.value = false
    }
  }

  /**
   * 自动演示流程
   */
  const runAutoDemo = async () => {
    //

    if (!isRunning.value) isRunning.value = true
    currentStep.value = 'run'
    await executeStep('run')
    isRunning.value = false
  }

  /**
   * 执行特定步骤
   */
  const executeStep = async (step: DemoState['currentStep']) => {
    switch (step) {
      case 'run':
        if (canStartDemo.value) {
          await runQCAnalysis()
        }
        break
      default:
        // target / rules 步骤无需自动执行
        break
    }
  }

  /**
   * 生成模拟质控结果
   */
  const generateMockQCResult = async (): Promise<QCResult> => {
    return {
      id: `qc-result-${Date.now()}`,
      recordId: testRecord.value?.id || 'unknown',
      overallScore: Math.floor(Math.random() * 40) + 60, // 60-100分
      overallGrade: 'B',
      analysisDate: new Date().toISOString(),
      issues: [
        {
          id: 'issue-001',
          ruleName: '主诉完整性检查',
          ruleId: 'rule-001',
          description: '主诉描述不够详细，缺少症状持续时间',
          severity: 'medium',
          category: '完整性',
          location: '主诉部分',
          suggestion: '建议补充症状的具体持续时间和严重程度',
          canAppeal: true
        }
      ],
      suggestions: [
        {
          id: 'suggestion-001',
          category: '完整性改进',
          title: '完善主诉描述',
          description: '建议在主诉中添加更详细的症状描述',
          priority: 'medium',
          actionRequired: true
        }
      ],
      ruleResults: selectedRules.value.map(rule => ({
        ruleId: rule.id,
        ruleName: `规则-${rule.id}`,
        passed: Math.random() > 0.3,
        score: Math.floor(Math.random() * 20) + 80,
        maxScore: 100,
        details: '规则执行详情...',
        executionTime: Math.floor(Math.random() * 1000) + 500,
        confidence: Math.random() * 0.3 + 0.7
      })),
      analysisSteps: analysisSteps.value,
      metadata: {
        analysisVersion: '1.0.0',
        modelVersion: 'gpt-4',
        processingTime: 5000,
        rulesApplied: selectedRules.value.length,
        confidence: 0.85
      }
    }
  }

  // ==================== 通知处理方法 ====================

  // 通知相关方法
  const handleNotificationAction = (action: string, notification?: QCNotification) => {
    if (!notification && !['simulate', 'clear-all', 'mark-all-read'].includes(action)) return

    switch (action) {
      case 'view':
      case 'select':
        // 查看通知详情，设置为活动通知
        activeNotification.value = notification!
        if (!notification!.isRead) {
          notification!.isRead = true
        }
        break
      case 'confirm':
      case 'markRead':
        notification!.status = 'confirmed'
        notification!.isRead = true
        activeNotification.value = null
        break
      case 'ignore':
        notification!.status = 'ignored'
        notification!.isRead = true
        activeNotification.value = null
        break
      case 'appeal':
        notification!.status = 'appealed'
        // 触发申诉流程
        showAppealModal.value = true
        currentAppeal.value = {
          id: generateId(),
          notificationId: notification!.id,
          reason: '',
          description: '',
          evidence: [],
          status: 'pending',
          submittedAt: new Date(),
          submittedBy: 'Dr. Zhang'
        }
        break
      case 'mark-read':
        notification!.isRead = true
        break
      case 'mark-unread':
        notification!.isRead = false
        break
      case 'delete':
        {
          const index = notifications.value.findIndex(n => n.id === notification!.id)
          if (index > -1) {
            notifications.value.splice(index, 1)
          }
          if (activeNotification.value?.id === notification!.id) {
            activeNotification.value = null
          }
        }
        break
      case 'mark-all-read':
        notifications.value.forEach(n => (n.isRead = true))
        break
      case 'clear-all':
        notifications.value = []
        activeNotification.value = null
        break
      case 'simulate':
        simulateRandomNotification()
        break
    }
  }

  // 模拟随机质控通知
  const simulateRandomNotification = () => {
    const notificationTypes = ['error', 'warning', 'info']
    const severities = ['critical', 'high', 'medium', 'low']
    const departments = ['内科', '外科', '儿科', '妇产科', '急诊科']
    const doctors = ['张医生', '李医生', '王医生', '刘医生', '陈医生']

    const type = notificationTypes[Math.floor(Math.random() * notificationTypes.length)]
    const severity = severities[Math.floor(Math.random() * severities.length)]
    const department = departments[Math.floor(Math.random() * departments.length)]
    const doctor = doctors[Math.floor(Math.random() * doctors.length)]

    const notification: QCNotification = {
      id: generateId(),
      type: type as 'error' | 'warning' | 'info' | 'success',
      severity: severity as 'critical' | 'high' | 'medium' | 'low',
      title: `${department}质控提醒`,
      message: `发现病历质量问题，请及时处理`,
      timestamp: new Date(),
      isRead: false,
      status: 'pending',
      canAppeal: true,
      recordInfo: {
        patientName: `患者${Math.floor(Math.random() * 1000)}`,
        recordNumber: `MR${Date.now()}`,
        department,
        doctor,
        admissionDate: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        status: '待审核'
      },
      qcResult: {
        overallScore: Math.floor(Math.random() * 40) + 60, // 60-100分
        overallGrade: 'B',
        analysisDate: new Date().toISOString(),
        issues: [
          {
            id: generateId(),
            ruleName: '病历完整性检查',
            ruleId: 'rule-' + generateId(),
            description: '缺少必要的检查项目记录',
            severity: severity as 'critical' | 'high' | 'medium' | 'low',
            category: '完整性',
            location: '检查记录',
            suggestion: '请补充相关检查项目的详细记录',
            canAppeal: true
          }
        ],
        suggestions: [
          {
            id: generateId(),
            category: '完整性改进',
            title: '完善病历记录',
            description: '建议在病历中补充详细的检查记录和诊断依据',
            priority: 'high',
            actionRequired: true
          }
        ],
        ruleResults: [],
        analysisSteps: [],
        metadata: {
          analysisVersion: '1.0.0',
          modelVersion: 'gpt-4',
          processingTime: Math.floor(Math.random() * 3000) + 1000,
          rulesApplied: Math.floor(Math.random() * 5) + 1,
          confidence: Math.random() * 0.3 + 0.7
        }
      }
    }

    // 添加到通知列表开头
    notifications.value.unshift(notification)

    // 如果开启了声音提醒，播放提示音
    if (demoConfig.value.enableNotifications) {
      playNotificationSound()
    }

    return notification
  }

  // 播放通知提示音
  const playNotificationSound = () => {
    try {
      // 创建一个简单的提示音
      const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)()
      const oscillator = audioContext.createOscillator()
      const gainNode = audioContext.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(audioContext.destination)

      oscillator.frequency.setValueAtTime(800, audioContext.currentTime)
      oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1)

      gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)

      oscillator.start(audioContext.currentTime)
      oscillator.stop(audioContext.currentTime + 0.3)
    } catch (error) {
      console.warn('无法播放通知提示音:', error)
    }
  }

  // ==================== 状态持久化方法 ====================

  /**
   * 保存演示状态到本地存储
   */
  const saveDemoState = async () => {
    try {
      const stateToSave = {
        currentStep: currentStep.value,
        selectedRules: selectedRules.value,
        testRecord: testRecord.value,
        selectedDocument: selectedDocument.value,
        analysisResult: analysisResult.value,
        notifications: notifications.value,
        appeals: appeals.value,
        config: demoConfig.value,
        progress: progress.value,
        isRunning: isRunning.value,
        isPaused: isPaused.value,
        timestamp: new Date().toISOString(),
        version: '1.0.1'
      }

      localStorage.setItem('qc-demo-state', JSON.stringify(stateToSave))
      console.log('演示状态已保存')
    } catch (error) {
      console.warn('保存演示状态失败:', error)
    }
  }

  /**
   * 从本地存储恢复演示状态
   */
  const restoreDemoState = async () => {
    try {
      const saved = localStorage.getItem('qc-demo-state')
      if (!saved) return false

      const parsedState = JSON.parse(saved)

      // 检查版本兼容性
      if (!['1.0.0','1.0.1'].includes(parsedState.version)) {
        console.warn('演示状态版本不兼容，将重新初始化')
        localStorage.removeItem('qc-demo-state')
        return false
      }

      // 检查状态是否过期（24小时）
      const timestamp = new Date(parsedState.timestamp)
      const now = new Date()
      const hoursDiff = (now.getTime() - timestamp.getTime()) / (1000 * 60 * 60)

      if (hoursDiff > 24) {
        console.log('演示状态已过期，将重新初始化')
        localStorage.removeItem('qc-demo-state')
        return false
      }

      // 恢复状态
      {
        const restoredStep = parsedState.currentStep as string | undefined
        if (restoredStep === 'target' || restoredStep === 'rules' || restoredStep === 'run') {
          currentStep.value = restoredStep
        } else if (['analysis','notification','appeal','completed'].includes(restoredStep || '')) {
          currentStep.value = 'run'
        } else {
          currentStep.value = 'target'
        }
      }
      selectedRules.value = parsedState.selectedRules || []
      testRecord.value = parsedState.testRecord
      selectedDocument.value = parsedState.selectedDocument || null
      analysisResult.value = parsedState.analysisResult
      notifications.value = parsedState.notifications || []
      appeals.value = parsedState.appeals || []
      demoConfig.value = { ...demoConfig.value, ...parsedState.config }
      progress.value = parsedState.progress || 0
      isRunning.value = parsedState.isRunning || false
      isPaused.value = parsedState.isPaused || false

      return true
    } catch (error) {
      console.warn('恢复演示状态失败:', error)
      localStorage.removeItem('qc-demo-state')
      return false
    }
  }

  /**
   * 清除保存的演示状态
   */
  const clearSavedState = () => {
    localStorage.removeItem('qc-demo-state')
    console.log('已清除保存的演示状态')
  }

  /**
   * 导出演示数据
   */
  const exportDemoData = () => {
    const exportData = {
      metadata: {
        exportTime: new Date().toISOString(),
        version: '1.0.1',
        description: 'LLM质控演示系统数据导出'
      },
      demoState: {
        currentStep: currentStep.value,
        selectedRules: selectedRules.value,
        testRecord: testRecord.value,
        selectedDocument: selectedDocument.value,
        analysisResult: analysisResult.value,
        notifications: notifications.value,
        appeals: appeals.value,
        config: demoConfig.value,
        progress: progress.value
      },
      statistics: {
        totalNotifications: notifications.value.length,
        unreadNotifications: notifications.value.filter(n => !n.isRead).length,
        totalAppeals: appeals.value.length,
        pendingAppeals: appeals.value.filter(a => a.status === 'pending').length,
        approvedAppeals: appeals.value.filter(a => a.status === 'approved').length,
        rejectedAppeals: appeals.value.filter(a => a.status === 'rejected').length
      }
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `qc-demo-export-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    console.log('演示数据已导出')
  }

  /**
   * 导入演示数据
   */
  const importDemoData = async (file: File) => {
    try {
      const text = await file.text()
      const importData = JSON.parse(text)

      // 验证数据格式
      if (!importData.metadata || !importData.demoState) {
        throw new Error('无效的导入文件格式')
      }

      // 检查版本兼容性
      if (!['1.0.0','1.0.1'].includes(importData.metadata.version)) {
        throw new Error('导入文件版本不兼容')
      }

      // 恢复状态
      const { demoState } = importData
      {
        const restoredStep = demoState.currentStep as string | undefined
        if (restoredStep === 'target' || restoredStep === 'rules' || restoredStep === 'run') {
          currentStep.value = restoredStep
        } else if (['analysis','notification','appeal','completed'].includes(restoredStep || '')) {
          currentStep.value = 'run'
        } else {
          currentStep.value = 'target'
        }
      }
      selectedRules.value = demoState.selectedRules || []
      testRecord.value = demoState.testRecord
      selectedDocument.value = demoState.selectedDocument || null
      analysisResult.value = demoState.analysisResult
      notifications.value = demoState.notifications || []
      appeals.value = demoState.appeals || []
      demoConfig.value = { ...demoConfig.value, ...demoState.config }
      progress.value = demoState.progress || 0

      // 保存导入的状态
      await saveDemoState()

      console.log('演示数据导入成功')
      return true
    } catch (error) {
      console.error('导入演示数据失败:', error)
      throw error
    }
  }

  // ==================== 申诉处理方法 ====================

  /**
   * 处理申诉相关操作
   */
  const handleAppealAction = (action: string, data?: unknown) => {
    switch (action) {
      case 'create':
        showAppealModal.value = true
        break
      case 'refresh':
        // 刷新申诉列表
        break
      case 'export':
        // 导出申诉数据
        exportAppealData()
        break
      case 'batch-approve':
        batchUpdateAppealStatus(data, 'approved')
        break
      case 'batch-reject':
        batchUpdateAppealStatus(data, 'rejected')
        break
      case 'batch-delete':
        batchDeleteAppeals(data)
        break
      case 'view':
        if (data) {
          currentAppeal.value = appeals.value.find(a => a.id === data.id) || null
        }
        break
      case 'edit':
        if (data && data.status === 'pending') {
          currentAppeal.value = data
          showAppealModal.value = true
        }
        break
      case 'cancel':
        if (data) {
          const appeal = appeals.value.find(a => a.id === data.id)
          if (appeal && appeal.status === 'pending') {
            appeal.status = 'cancelled'
          }
        }
        break
    }
  }

  /**
   * 批量更新申诉状态
   */
  const batchUpdateAppealStatus = (appealIds: string[], status: 'approved' | 'rejected') => {
    appealIds.forEach(id => {
      const appeal = appeals.value.find(a => a.id === id)
      if (appeal && appeal.status === 'pending') {
        appeal.status = status
        appeal.reviewedAt = new Date()
        appeal.reviewedBy = '批量审核员'
        appeal.reviewerComment = status === 'approved'
          ? '批量审核通过'
          : '批量审核驳回'
      }
    })
  }

  /**
   * 批量删除申诉
   */
  const batchDeleteAppeals = (appealIds: string[]) => {
    appealIds.forEach(id => {
      const index = appeals.value.findIndex(a => a.id === id)
      if (index > -1) {
        appeals.value.splice(index, 1)
      }
    })

    // 如果当前申诉被删除，清空当前申诉
    if (currentAppeal.value && appealIds.includes(currentAppeal.value.id)) {
      currentAppeal.value = null
    }
  }

  /**
   * 导出申诉数据
   */
  const exportAppealData = () => {
    const data = appeals.value.map(appeal => ({
      申诉编号: appeal.id,
      申诉类型: appeal.appealType,
      申诉理由: appeal.reason,
      申诉描述: appeal.description,
      优先级: appeal.priority,
      状态: appeal.status,
      提交时间: appeal.submittedAt.toLocaleString('zh-CN'),
      提交人: appeal.submittedBy,
      审核时间: appeal.reviewedAt?.toLocaleString('zh-CN') || '',
      审核人: appeal.reviewedBy || '',
      审核意见: appeal.reviewerComment || ''
    }))

    // 这里可以实现实际的导出逻辑
    console.log('导出申诉数据:', data)
  }

  // ==================== 返回接口 ====================

  return {
    // 状态
    isRunning,
    isPaused,
    currentStep,
    progress,
    error,
    selectedRules,
    testRecord,
    selectedDocument,
    analysisResult,
    analysisSteps,
    notifications,
    activeNotification,
    showNotificationModal,
    appeals,
    currentAppeal,
    showAppealModal,
    demoConfig,

    // 数据状态
    isDatabaseConnected,
    isLoadingData,
    availableRecords,
    availableRules,
    availableDepartments,
    recordFilters,
    ruleFilters,

    // 计算属性
    unreadNotifications,
    pendingAppeals,
    canStartDemo,
    demoProgress,
    selectedDocumentList,
    selectedDocumentPrimary,


    // 方法
    initializeDemo,
    startDemo,
    togglePause,
    stopDemo,
    nextStep,
    previousStep,
    jumpToStep,
    replayDemo,
    runQCAnalysis,
    simulateQCNotification,
    createAppeal,
    resetDemoState,
    handleNotificationAction,
    simulateRandomNotification,
    playNotificationSound,
    handleAppealAction,
    simulateAppealReview,

    // 数据管理方法
    loadTestData,
    refreshData: (forceRefresh = true) => loadTestData(forceRefresh),
    selectTestRecord: (record: MedicalRecord) => { testRecord.value = record },
    setSelectedDocument: (doc: DocInfo | DocInfo[] | null) => {
      selectedDocument.value = doc
    },
    clearSelectedDocument: () => { selectedDocument.value = null },
    updateRecordFilters: (filters: Partial<typeof recordFilters.value>) => {
      Object.assign(recordFilters.value, filters)
      loadTestData(true) // 重新加载数据，强制刷新连接状态
    },
    updateRuleFilters: (filters: Partial<typeof ruleFilters.value>) => {
      Object.assign(ruleFilters.value, filters)
      loadTestData(true) // 重新加载数据，强制刷新连接状态
    },
    // 重置连接状态并重新加载数据
    resetConnection: async () => {
      demoDataService.resetConnectionState()
      await loadTestData(true)
    },

    // 状态持久化
    saveDemoState,
    restoreDemoState,
    clearSavedState,
    exportDemoData,
    importDemoData
  }
})
