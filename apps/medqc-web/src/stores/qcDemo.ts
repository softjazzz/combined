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

// ==================== 工具函数 ====================

/**
 * 生成唯一ID
 */
const generateId = () => {
  return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

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

  /**
   * 执行质控分析演示
   */
  const runQCAnalysis = async () => {
    if (!testRecord.value || selectedDocumentList.value.length === 0 || selectedRules.value.length === 0) {
      throw new Error('缺少测试对象（病历或文书）或质控规则')
    }

    try {
      currentStep.value = 'run'

      // 模拟分析步骤
      const steps: AnalysisStep[] = [
        { id: '1', name: '数据预处理', description: '清理和标准化病历数据', status: 'pending' },
        { id: '2', name: '规则匹配', description: '匹配适用的质控规则', status: 'pending' },
        { id: '3', name: 'LLM分析', description: '使用大语言模型进行质控分析', status: 'pending' },
        { id: '4', name: '结果生成', description: '生成质控报告和建议', status: 'pending' }
      ]

      analysisSteps.value = steps

      // 逐步执行分析
      for (const step of steps) {
        step.status = 'running'
        step.startTime = new Date()

        // 模拟处理时间
        await new Promise(resolve => setTimeout(resolve, demoConfig.value.stepDelay))

        step.status = 'completed'
        step.endTime = new Date()
      }

      // 生成模拟结果
      analysisResult.value = await generateMockQCResult()

      console.log('质控分析完成', analysisResult.value)
    } catch (err) {
      error.value = `分析失败: ${err instanceof Error ? err.message : '未知错误'}`
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
      severity: result.overallScore < 60 ? 'critical' : result.overallScore < 80 ? 'high' : 'low'
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
  const createAppeal = async (appealData: any) => {
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
  const loadTestData = async () => {
    isLoadingData.value = true
    try {
      // 检查数据库连接
      isDatabaseConnected.value = await demoDataService.checkConnection()

      // 加载可用的医疗记录
      availableRecords.value = await demoDataService.getMedicalRecords({
        limit: 20,
        ...recordFilters.value
      })

      // 加载可用的质控规则
      availableRules.value = await demoDataService.getQCRules({
        limit: 50,
        ...ruleFilters.value
      })

      // 加载科室列表
      availableDepartments.value = await demoDataService.getDepartments()

      // 如果没有选择测试记录，选择第一个
      if (!testRecord.value && availableRecords.value.length > 0) {
        testRecord.value = availableRecords.value[0]
      }

      // 如果没有选择规则，选择前3个活跃规则
      if (selectedRules.value.length === 0 && availableRules.value.length > 0) {
        selectedRules.value = availableRules.value
          .filter(rule => rule.isActive)
          .slice(0, 3)
      }

      console.log(`[DemoDataService] 数据加载完成:`, {
        records: availableRecords.value.length,
        rules: availableRules.value.length,
        departments: availableDepartments.value.length,
        connected: isDatabaseConnected.value
      })
    } catch (err) {
      console.error('[DemoDataService] 数据加载失败:', err)
      error.value = `数据加载失败: ${err instanceof Error ? err.message : '未知错误'}`
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
  const handleAppealAction = (action: string, data?: any) => {
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
    refreshData: loadTestData,
    selectTestRecord: (record: MedicalRecord) => { testRecord.value = record },
    setSelectedDocument: (doc: DocInfo | DocInfo[] | null) => {
      selectedDocument.value = doc
    },
    clearSelectedDocument: () => { selectedDocument.value = null },
    updateRecordFilters: (filters: Partial<typeof recordFilters.value>) => {
      Object.assign(recordFilters.value, filters)
      loadTestData() // 重新加载数据
    },
    updateRuleFilters: (filters: Partial<typeof ruleFilters.value>) => {
      Object.assign(ruleFilters.value, filters)
      loadTestData() // 重新加载数据
    },

    // 状态持久化
    saveDemoState,
    restoreDemoState,
    clearSavedState,
    exportDemoData,
    importDemoData
  }
})
