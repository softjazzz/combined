/**
 * LLM质控演示系统状态管理
 * 管理演示流程、数据状态和用户交互
 */
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type {
  DemoState,
  DemoConfig,
  QCResult,
  QCNotification,
  Appeal,
  DemoStep,
  QualityControlRule,
  AnalysisStep,
  AppealReason,
  QCIssue,
  QCSuggestion,
  QCRuleResult,
  QCResultMetadata
} from '@/types/quality-control'
import type { MedicalRecord } from '@/types/medical-records'
import { DemoDataService } from '@/services/demoDataService'
import { ApiService } from '@/services/apiService'
import type { QCAnalysisRequest } from '@/types'
import { getDocumentTypeCode, getDocumentMatchCodes } from '@/constants/documentTypes'

// ==================== 工具函数 ====================

/**
 * 生成唯一ID
 */
const generateId = () => {
  return `id-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const getRuleIdentifier = (rule: any): string => {
  if (!rule) return ''
  return String(rule.id ?? rule.ruleCode ?? rule.name ?? '')
}

// ==================== 预置示例数据 ====================

/**
 * 预置示例数据结构
 */
interface PresetExample {
  id: string
  title: string
  type: string
  content: string
  patientInfo: {
    patientName: string
    age: number
    gender: string
    department: string
    admissionNumber: string
    bedNumber: string
    admissionTime: string
    recordTime: string
    diagnosis: string
  }
}

/**
 * 预置的首次病程记录示例
 */
const PRESET_FIRST_COURSE_RECORD = `首次病程记录

记录时间：2025年10月11日 15:00

一、患者基本信息
姓名：李明
性别：男
年龄：58岁
科室：心内科
住院号：2025001234
床号：15床
入院时间：2025年10月11日 09:30

二、主诉
反复胸闷、胸痛3天，加重伴气促1天。

三、现病史
患者于3天前无明显诱因出现胸闷、胸痛，呈压榨性疼痛，位于胸骨后,持续时间约5-10分钟，休息后可缓解。1天前上述症状加重，伴有气促、出汗，活动后明显，休息时亦有发作。患者自服"速效救心丸"后症状无明显缓解，遂来我院急诊就诊。

急诊查心电图示：V1-V4导联ST段压低0.1-0.2mV，T波倒置。
急诊查心肌酶谱：肌钙蛋白I 0.8 ng/mL（正常值<0.04 ng/mL），肌酸激酶同工酶（CK-MB）45 U/L（正常值<25 U/L）。

急诊诊断为"急性冠脉综合征"，予以阿司匹林、氯吡格雷抗血小板聚集，低分子肝素抗凝，硝酸甘油扩冠等治疗后，症状稍缓解，为进一步诊治收入我科。

发病以来，患者精神欠佳，食欲减退，睡眠欠佳，大小便正常，体重无明显变化。

四、既往史
1. 高血压病史10年，最高血压180/110 mmHg，平时口服"硝苯地平缓释片"控制，血压控制尚可。
2. 2型糖尿病病史5年，口服"二甲双胍"控制，血糖控制一般。
3. 吸烟史30年，每天约20支，已戒烟2年。
4. 否认肝炎、结核等传染病史。
5. 否认手术、外伤史。
6. 否认药物、食物过敏史。
7. 否认输血史。

五、个人史及家族史
1. 个人史：生于本地，长期居住本地，无疫区居住史，无毒物接触史。
2. 家族史：父亲有高血压病史，母亲有糖尿病史，否认家族遗传性疾病史。

六、体格检查
T: 36.8℃  P: 88次/分  R: 20次/分  BP: 145/90 mmHg

一般情况：神志清楚，精神欠佳，体型偏胖，营养中等，自主体位，查体合作。

皮肤黏膜：皮肤无黄染、出血点，浅表淋巴结未触及肿大。

头颈部：头颅无畸形，双侧瞳孔等大等圆，对光反射灵敏，巩膜无黄染，结膜无充血，口唇无发绀，咽部无充血，扁桃体无肿大，颈软，气管居中，甲状腺无肿大，颈静脉无怒张。

胸部：
- 肺部：胸廓对称，呼吸运动正常，双肺叩诊清音，双肺呼吸音清晰，未闻及干湿性啰音。
- 心脏：心前区无隆起，心尖搏动位于左侧第5肋间锁骨中线内0.5cm，心界不大，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。

腹部：腹部平软，无压痛、反跳痛，肝脾未触及，Murphy征阴性，移动性浊音阴性，肠鸣音正常。

四肢：四肢活动自如，双下肢无水肿，足背动脉搏动良好。

神经系统：生理反射存在，病理反射未引出。

七、辅助检查
1. 心电图（2025-10-11 09:45）：窦性心律，V1-V4导联ST段压低0.1-0.2mV，T波倒置。
2. 心肌酶谱（2025-10-11 10:00）：
   - 肌钙蛋白I：0.8 ng/mL ↑（正常值<0.04 ng/mL）
   - CK-MB：45 U/L ↑（正常值<25 U/L）
   - CK：280 U/L（正常值24-195 U/L）
3. 血常规（2025-10-11 10:00）：WBC 8.5×10^9/L，RBC 4.8×10^12/L，Hb 145 g/L，PLT 220×10^9/L。
4. 生化全套（2025-10-11 10:00）：
   - 空腹血糖：8.2 mmol/L ↑
   - 总胆固醇：6.5 mmol/L ↑
   - 甘油三酯：2.8 mmol/L ↑
   - 低密度脂蛋白：4.2 mmol/L ↑
   - 肌酐：85 μmol/L
   - 尿素氮：6.5 mmol/L

八、初步诊断
1. 急性冠脉综合征（ACS）
   - 不稳定型心绞痛？
   - 非ST段抬高型心肌梗死（NSTEMI）？
2. 高血压病3级（极高危）
3. 2型糖尿病
4. 血脂异常

九、诊疗计划
1. 心内科监护病房（CCU）监护治疗
2. 绝对卧床休息，低盐低脂糖尿病饮食
3. 心电监护，吸氧
4. 抗血小板聚集：阿司匹林 100mg qd + 氯吡格雷 75mg qd
5. 抗凝治疗：低分子肝素 5000U q12h 皮下注射
6. 扩冠治疗：硝酸甘油 10mg 静脉泵入
7. 调脂治疗：阿托伐他汀 20mg qn
8. 降压治疗：继续硝苯地平缓释片 30mg qd
9. 降糖治疗：继续二甲双胍 0.5g tid
10. 完善冠脉造影检查，必要时行PCI治疗
11. 密切观察病情变化，定期复查心电图、心肌酶谱

十、注意事项
1. 严密监测生命体征、心电图变化
2. 观察胸痛发作情况，及时处理
3. 注意出血倾向
4. 控制血压、血糖在目标范围
5. 向患者及家属交代病情，签署病危通知书、冠脉造影知情同意书

医师签名：张医生
记录时间：2025年10月11日 15:00`

/**
 * 预置示例集合
 */
const PRESET_EXAMPLES: Record<string, PresetExample> = {
  firstCourseRecord: {
    id: 'preset-first-course-record',
    title: '首次病程记录 - 李明（急性冠脉综合征）',
    type: '首次病程记录',
    content: PRESET_FIRST_COURSE_RECORD,
    patientInfo: {
      patientName: '李明',
      age: 58,
      gender: '男',
      department: '心内科',
      admissionNumber: '2025001234',
      bedNumber: '15床',
      admissionTime: '2025年10月11日 09:30',
      recordTime: '2025年10月11日 15:00',
      diagnosis: '急性冠脉综合征（ACS）、高血压病3级、2型糖尿病、血脂异常'
    }
  }
}

// ==================== 错误处理类型定义 ====================

/**
 * 错误类型枚举
 */
enum ErrorType {
  NETWORK = 'network',           // 网络错误
  TIMEOUT = 'timeout',           // 超时错误
  BUSINESS = 'business',         // 业务逻辑错误
  VALIDATION = 'validation',     // 数据验证错误
  PERMISSION = 'permission',     // 权限错误
  NOT_FOUND = 'not_found',       // 资源不存在
  SERVER = 'server',             // 服务器错误
  UNKNOWN = 'unknown'            // 未知错误
}

/**
 * 错误上下文信息
 */
interface ErrorContext {
  operation: string              // 操作名称（如 "加载病历"、"执行质控分析"）
  component?: string             // 组件名称
  details?: Record<string, any>  // 额外详情
}

/**
 * 处理后的错误信息
 */
interface ProcessedError {
  type: ErrorType
  message: string                // 用户友好的错误消息
  technicalMessage: string       // 技术详情（用于日志）
  context: ErrorContext
  timestamp: string
  canRetry: boolean              // 是否可以重试
  retryDelay?: number            // 建议的重试延迟（毫秒）
}

export const useQCDemoStore = defineStore('qcDemo', () => {
  // ==================== 数据服务实例 ====================

  const demoDataService = DemoDataService.getInstance()

  // ==================== 状态定义 ====================

  // 演示状态
  const isRunning = ref(false)
  const isPaused = ref(false)
  const pauseStartTime = ref<Date | null>(null)
  const currentStep = ref<DemoState['currentStep']>('target')
  const progress = ref(0)
  const error = ref<string | null>(null)

  // 数据库连接状态
  const isDatabaseConnected = ref(false)
  const isLoadingData = ref(false)

  // 数据状态
  const selectedRules = ref<QualityControlRule[]>([])
  const testRecord = ref<MedicalRecord | null>(null)
  // 所选文书（支持单选或多选；为兼容旧逻辑，仍命名为 selectedDocument）
  type DocInfo = { id: string; title?: string; type?: string; created_at?: string }
  const selectedDocument = ref<DocInfo | DocInfo[] | null>(null)
  const analysisResult = ref<QCResult | null>(null)
  const analysisSteps = ref<AnalysisStep[]>([])

  // 可用数据
  const availableRecords = ref<MedicalRecord[]>([])
  const availableRules = ref<QualityControlRule[]>([]) // 所有规则（未过滤）

  const syncSelectedRulesWithAvailable = () => {
    if (selectedRules.value.length === 0 || availableRules.value.length === 0) return
    const map = new Map<string, QualityControlRule>()
    availableRules.value.forEach(rule => {
      const id = getRuleIdentifier(rule)
      if (id) map.set(id, rule)
    })
    const next = selectedRules.value
      .map(rule => {
        const id = getRuleIdentifier(rule)
        return id ? map.get(id) : undefined
      })
      .filter((rule): rule is QualityControlRule => !!rule)
    selectedRules.value = next
  }
  const availableDepartments = ref<string[]>([])

  // 根据当前选中文书类型过滤的适用规则
  const applicableRules = computed<QualityControlRule[]>(() => {
    // 如果没有选择文书，返回所有规则
    if (!selectedDocumentPrimary.value?.type) {
      return availableRules.value
    }

    const documentType = selectedDocumentPrimary.value.type

    // 将文书类型转换为标准英文代码，并生成匹配代码集合（如首次病程记录 -> [first_progress_note, progress_note]）
    const documentTypeCode = getDocumentTypeCode(documentType)
    const matchCodes = getDocumentMatchCodes(documentType)

    // 过滤规则：
    // 1. applicable_documents 为空或 null 的通用规则
    // 2. applicable_documents 包含当前文书类型代码或其基础代码的规则
    const filtered = availableRules.value.filter((rule: any) => {
      const applicableDocs: string[] = rule.applicable_documents || []

      // 通用规则（适用于所有文书类型）
      if (!applicableDocs || applicableDocs.length === 0) {
        return true
      }

      // 匹配任一代码即可
      return matchCodes.some(code => applicableDocs.includes(code))
    })

    console.log(`[QCDemoStore] 规则过滤: 文书类型="${documentType}", 文书代码="${documentTypeCode}", 匹配集合=${JSON.stringify(matchCodes)}, 总规则=${availableRules.value.length}, 适用规则=${filtered.length}`)

    // 调试：打印前3条适用规则的 applicable_documents 字段
    if (filtered.length > 0) {
      console.log('[QCDemoStore] 适用规则示例（前3条）:')
      filtered.slice(0, 3).forEach((rule: any, index: number) => {
        console.log(`  规则${index + 1}: ${rule.name || rule.rule_code}`)
        console.log(`    applicable_documents:`, rule.applicable_documents)
      })
    }

    return filtered
  })

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

  // 错误日志存储（用于调试面板）
  const errorLogs = ref<ProcessedError[]>([])
  const maxErrorLogs = 50 // 最多保存50条错误日志

  // 演示日志存储（用于增强日志面板）
  interface DemoLogEntry {
    timestamp: string
    level: 'info' | 'warning' | 'error'
    message: string
    details?: any
  }
  const demoLogs = ref<DemoLogEntry[]>([])
  const maxDemoLogs = 200 // 最多保存200条演示日志

  // 性能监控数据
  interface StepTiming {
    name: string
    startTime: number
    endTime?: number
    duration: number
  }

  interface ApiCall {
    name: string
    duration: number
    status: 'success' | 'error'
    timestamp: string
  }

  interface MemoryInfo {
    usedJSHeapSize: number
    totalJSHeapSize: number
    jsHeapSizeLimit: number
  }

  const stepTimings = ref<StepTiming[]>([])
  const apiCalls = ref<ApiCall[]>([])
  const memoryInfo = ref<MemoryInfo | null>(null)
  const performanceMonitorEnabled = ref(false)

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

  // ==================== 统计相关计算属性 ====================

  // 已选规则数量
  const selectedRulesCount = computed(() => selectedRules.value.length)

  // 可用规则总数（基于当前文书类型过滤后的规则）
  const totalRulesCount = computed(() => applicableRules.value.length)

  // 所有规则总数（未过滤）
  const allRulesCount = computed(() => availableRules.value.length)

  // 分析完成数量（简化版，实际应该基于分析历史）
  const analysisCompletedCount = computed(() => {
    return analysisResult.value ? 1 : 0
  })

  // 总测试对象数量
  const totalRecordsCount = computed(() => {
    return testRecord.value ? 1 : 0
  })

  // 未读通知数量
  const unreadNotificationsCount = computed(() => unreadNotifications.value.length)

  // 总通知数量
  const totalNotificationsCount = computed(() => notifications.value.length)

  // 待处理申诉数量
  const pendingAppealsCount = computed(() => pendingAppeals.value.length)

  // 总申诉数量
  const totalAppealsCount = computed(() => appeals.value.length)

  // 平均质控得分
  const averageQCScore = computed(() => {
    if (!analysisResult.value || !analysisResult.value.issues) {
      return 0
    }
    // 基于问题数量计算得分（简化版）
    const issuesCount = analysisResult.value.issues.length
    const baseScore = 100
    const deduction = Math.min(issuesCount * 5, 50) // 每个问题扣5分，最多扣50分
    return Math.max(baseScore - deduction, 0)
  })

  // 演示开始时间
  const demoStartTime = ref<Date | null>(null)

  // ==================== 统一获取文书列表与主文书 ====================

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
      handleError(err, {
        operation: '初始化演示环境',
        component: 'QCDemoStore',
        details: { config, restoreState }
      })
      throw err
    }
  }

  // ==================== 错误处理函数 ====================

  /**
   * 分析错误类型
   */
  const analyzeErrorType = (error: any): ErrorType => {
    // 网络错误
    if (error.message?.includes('Network') || error.message?.includes('fetch')) {
      return ErrorType.NETWORK
    }

    // 超时错误
    if (error.message?.includes('timeout') || error.message?.includes('超时')) {
      return ErrorType.TIMEOUT
    }

    // 权限错误
    if (error.status === 401 || error.status === 403) {
      return ErrorType.PERMISSION
    }

    // 资源不存在
    if (error.status === 404) {
      return ErrorType.NOT_FOUND
    }

    // 服务器错误
    if (error.status >= 500) {
      return ErrorType.SERVER
    }

    // 验证错误
    if (error.status === 400 || error.message?.includes('验证') || error.message?.includes('validation')) {
      return ErrorType.VALIDATION
    }

    // 业务错误
    if (error.code || error.businessCode) {
      return ErrorType.BUSINESS
    }

    return ErrorType.UNKNOWN
  }

  /**
   * 生成用户友好的错误消息
   */
  const generateUserMessage = (errorType: ErrorType, context: ErrorContext, originalError: any): string => {
    const operation = context.operation

    switch (errorType) {
      case ErrorType.NETWORK:
        return `${operation}失败：网络连接异常，请检查网络后重试`

      case ErrorType.TIMEOUT:
        return `${operation}超时：服务器响应时间过长，请稍后重试`

      case ErrorType.PERMISSION:
        return `${operation}失败：权限不足，请联系管理员`

      case ErrorType.NOT_FOUND:
        return `${operation}失败：请求的资源不存在`

      case ErrorType.SERVER:
        return `${operation}失败：服务器内部错误，请稍后重试或联系技术支持`

      case ErrorType.VALIDATION:
        return `${operation}失败：${originalError.message || '数据验证失败，请检查输入'}`

      case ErrorType.BUSINESS:
        return `${operation}失败：${originalError.message || '业务处理异常'}`

      case ErrorType.UNKNOWN:
      default:
        return `${operation}失败：${originalError.message || '未知错误，请重试'}`
    }
  }

  /**
   * 统一错误处理函数
   * @param error 原始错误对象
   * @param context 错误上下文信息
   * @returns 处理后的错误信息
   */
  const handleError = (error: any, context: ErrorContext): ProcessedError => {
    const errorType = analyzeErrorType(error)
    const timestamp = new Date().toISOString()

    // 生成用户友好消息
    const userMessage = generateUserMessage(errorType, context, error)

    // 生成技术详情
    const technicalMessage = error.stack || error.message || JSON.stringify(error)

    // 判断是否可以重试
    const canRetry = [
      ErrorType.NETWORK,
      ErrorType.TIMEOUT,
      ErrorType.SERVER
    ].includes(errorType)

    // 建议的重试延迟
    const retryDelay = errorType === ErrorType.TIMEOUT ? 5000 : 2000

    const processedError: ProcessedError = {
      type: errorType,
      message: userMessage,
      technicalMessage,
      context,
      timestamp,
      canRetry,
      retryDelay: canRetry ? retryDelay : undefined
    }

    // 记录到错误日志
    errorLogs.value.unshift(processedError)
    if (errorLogs.value.length > maxErrorLogs) {
      errorLogs.value = errorLogs.value.slice(0, maxErrorLogs)
    }

    // 输出到控制台（开发模式）
    if (import.meta.env.MODE === 'development') {
      console.error(`[QC Demo Error] ${context.operation}:`, {
        type: errorType,
        message: userMessage,
        technical: technicalMessage,
        context,
        originalError: error
      })
    }

    // 设置全局错误状态
    error.value = userMessage

    return processedError
  }

  /**
   * 清除错误状态
   */
  const clearError = () => {
    error.value = null
  }

  /**
   * 获取错误日志
   */
  const getErrorLogs = () => {
    return errorLogs.value
  }

  /**
   * 清除错误日志
   */
  const clearErrorLogs = () => {
    errorLogs.value = []
  }

  // ==================== 演示日志管理函数 ====================

  /**
   * 添加演示日志
   */
  const addDemoLog = (level: 'info' | 'warning' | 'error', message: string, details?: any) => {
    const timestamp = new Date().toISOString()
    const logEntry: DemoLogEntry = {
      timestamp,
      level,
      message,
      details
    }

    demoLogs.value.push(logEntry)

    // 限制日志数量
    if (demoLogs.value.length > maxDemoLogs) {
      demoLogs.value = demoLogs.value.slice(-maxDemoLogs)
    }

    // 开发模式下同时输出到控制台
    if (import.meta.env.MODE === 'development') {
      const consoleMethod = level === 'error' ? console.error : level === 'warning' ? console.warn : console.log
      consoleMethod(`[Demo Log] ${message}`, details || '')
    }
  }

  /**
   * 清除演示日志
   */
  const clearDemoLogs = () => {
    demoLogs.value = []
  }

  /**
   * 获取演示日志
   */
  const getDemoLogs = () => {
    return demoLogs.value
  }

  // ==================== 性能监控函数 ====================

  /**
   * 开始记录步骤性能
   */
  const startStepTiming = (stepName: string) => {
    if (!performanceMonitorEnabled.value) return

    const timing: StepTiming = {
      name: stepName,
      startTime: performance.now(),
      duration: 0
    }
    stepTimings.value.push(timing)
  }

  /**
   * 结束记录步骤性能
   */
  const endStepTiming = (stepName: string) => {
    if (!performanceMonitorEnabled.value) return

    const timing = stepTimings.value.find(t => t.name === stepName && !t.endTime)
    if (timing) {
      timing.endTime = performance.now()
      timing.duration = timing.endTime - timing.startTime
    }
  }

  /**
   * 记录 API 调用性能
   */
  const recordApiCall = (apiName: string, duration: number, status: 'success' | 'error') => {
    if (!performanceMonitorEnabled.value) return

    const call: ApiCall = {
      name: apiName,
      duration,
      status,
      timestamp: new Date().toLocaleTimeString()
    }
    apiCalls.value.push(call)
  }

  /**
   * 更新内存信息
   */
  const updateMemoryInfo = () => {
    if (!performanceMonitorEnabled.value) return

    // @ts-ignore - performance.memory 是非标准 API
    if (performance.memory) {
      // @ts-ignore
      const memory = performance.memory
      memoryInfo.value = {
        usedJSHeapSize: memory.usedJSHeapSize / 1024 / 1024, // 转换为 MB
        totalJSHeapSize: memory.totalJSHeapSize / 1024 / 1024,
        jsHeapSizeLimit: memory.jsHeapSizeLimit / 1024 / 1024
      }
    }
  }

  /**
   * 重置性能数据
   */
  const resetPerformanceData = () => {
    stepTimings.value = []
    apiCalls.value = []
    memoryInfo.value = null
  }

  /**
   * 切换性能监控
   */
  const togglePerformanceMonitor = (enabled: boolean) => {
    performanceMonitorEnabled.value = enabled
    if (enabled) {
      updateMemoryInfo()
    } else {
      resetPerformanceData()
    }
  }

  // ==================== 演示控制函数 ====================

  /**
   * 开始演示
   */
  const startDemo = async () => {
    if (!canStartDemo.value) {
      const error = new Error('演示条件不满足，请检查规则、病历与文书是否选择完整')
      handleError(error, {
        operation: '启动质控演示',
        component: 'QCDemoStore',
        details: {
          hasRecord: !!testRecord.value,
          hasDocument: !!selectedDocument.value,
          hasRules: selectedRules.value.length > 0
        }
      })
      throw error
    }

    try {
      isRunning.value = true
      demoStartTime.value = new Date() // 记录开始时间
      currentStep.value = 'run'
      progress.value = demoProgress.value
      clearError()

      addDemoLog('info', '开始LLM质控演示', {
        record: testRecord.value?.patient_name,
        rulesCount: selectedRules.value.length
      })
      startStepTiming('质控演示')
      console.log('开始LLM质控演示')

      if (demoConfig.value.autoAdvance) {
        await runAutoDemo()
      } else {
        // 手动模式直接执行分析
        await executeStep('run')
      }
    } catch (err) {
      handleError(err, {
        operation: '启动质控演示',
        component: 'QCDemoStore'
      })
      isRunning.value = false
      throw err
    }
  }

  /**
   * 暂停/恢复演示
   */
  const togglePause = () => {
    isPaused.value = !isPaused.value

    if (isPaused.value) {
      // 记录暂停开始时间
      pauseStartTime.value = new Date()
      console.log('演示已暂停')
    } else {
      // 清除暂停时间
      pauseStartTime.value = null
      console.log('演示已恢复')
    }
  }

  /**
   * 停止演示
   */
  const stopDemo = () => {
    isRunning.value = false
    isPaused.value = false
    pauseStartTime.value = null
    demoStartTime.value = null // 清除开始时间
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
    console.log('[QCDemoStore] nextStep - 当前索引:', currentIndex, '当前步骤:', currentStep.value)
    if (currentIndex < steps.length - 1) {
      const newStep = steps[currentIndex + 1]
      console.log('[QCDemoStore] nextStep - 切换到:', newStep)
      currentStep.value = newStep
      progress.value = demoProgress.value
      await executeStep(currentStep.value)
      await saveDemoState()
      console.log('[QCDemoStore] nextStep - 完成，当前步骤:', currentStep.value)
    } else {
      console.log('[QCDemoStore] nextStep - 已是最后一步，无法前进')
    }
  }

  /**
   * 返回上一步
   */
  const previousStep = async () => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    const currentIndex = steps.indexOf(currentStep.value)
    console.log('[QCDemoStore] previousStep - 当前索引:', currentIndex, '当前步骤:', currentStep.value)
    if (currentIndex > 0) {
      const newStep = steps[currentIndex - 1]
      console.log('[QCDemoStore] previousStep - 切换到:', newStep)
      currentStep.value = newStep
      progress.value = demoProgress.value
      await saveDemoState()
      console.log('[QCDemoStore] previousStep - 完成，当前步骤:', currentStep.value)
    } else {
      console.log('[QCDemoStore] previousStep - 已是第一步，无法后退')
    }
  }

  /**
   * 跳转到指定步骤
   */
  const jumpToStep = async (step: DemoState['currentStep']) => {
    const steps: DemoState['currentStep'][] = ['target', 'rules', 'run']
    console.log('[QCDemoStore] jumpToStep - 目标步骤:', step, '当前步骤:', currentStep.value)
    if (steps.includes(step)) {
      currentStep.value = step
      progress.value = demoProgress.value
      console.log('[QCDemoStore] jumpToStep - 步骤已更新为:', currentStep.value)
      if (
        step === 'run' &&
        selectedRules.value.length > 0 &&
        !!testRecord.value &&
        selectedDocumentList.value.length > 0
      ) {
        console.log('[QCDemoStore] jumpToStep - 自动执行运行步骤')
        await executeStep('run')
      }
      await saveDemoState()
      console.log(`[QCDemoStore] jumpToStep - 完成，已跳转到步骤: ${step}`)
    } else {
      console.warn('[QCDemoStore] jumpToStep - 无效的步骤:', step)
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

  /**
   * 将四川质控 API 响应转换为演示页面需要的 QCResult 格式
   */
  const adaptSichuanQCResult = (sichuanResponse: any): QCResult => {
    const evaluationSummary = sichuanResponse.evaluation_summary || {}
    const performanceMetrics = sichuanResponse.performance_metrics || {}
    const evaluationResults = sichuanResponse.evaluation_results || []

    // 调试日志：查看后端返回的原始数据
    console.log('[adaptSichuanQCResult] 后端返回数据:', {
      evaluationSummary,
      evaluationResultsCount: evaluationResults.length,
      evaluationResults: evaluationResults, // 显示所有数据（因为只有1条）
      fullResponse: sichuanResponse
    })

    // 计算总体评分：基于合规率转换为 0-100 分
    const complianceRate = evaluationSummary.compliance_rate || 0
    const overallScore = Math.round(complianceRate)

    // 将评估结果转换为问题列表
    let issues: QCIssue[] = []

    // 方式1: 从 evaluation_results 中提取不合规的项（适用于多次调用模式）
    const issuesFromResults = evaluationResults
      .filter((result: any) => !result.is_compliant)
      .map((result: any) => ({
        id: generateId(),
        ruleName: result.rule_name || '质控规则',
        ruleId: result.rule_id || '',
        description: result.findings || '检测到质控问题',
        severity: result.severity || 'medium',
        category: result.category || 'general',
        location: result.location || '病历正文',
        suggestion: result.suggestion || '请根据规则要求进行整改',
        evidence: result.evidence || '',
        canAppeal: true
      }))

    // 方式2: 如果 evaluation_results 只有1条汇总记录（single_prompt 模式），
    // 则从 evaluation_summary 中生成问题列表
    if (evaluationResults.length === 1 && evaluationSummary.total_rules > 1) {
      const nonCompliantCount = evaluationSummary.total_rules - evaluationSummary.compliant_rules
      const criticalViolations = evaluationSummary.critical_violations || 0

      // 如果有不合规的规则，生成汇总问题
      if (nonCompliantCount > 0) {
        issues = [{
          id: generateId(),
          ruleName: '病历质控综合评估',
          ruleId: 'summary-001',
          description: `经过 ${evaluationSummary.total_rules} 条规则检查，发现 ${nonCompliantCount} 条规则不合规${criticalViolations > 0 ? `，其中 ${criticalViolations} 条为严重违规` : ''}。`,
          severity: criticalViolations > 0 ? 'high' : (nonCompliantCount > 5 ? 'medium' : 'low'),
          category: 'comprehensive',
          location: '病历整体',
          suggestion: `建议重点关注不合规的 ${nonCompliantCount} 条规则，完善病历内容以提高合规率。`,
          evidence: `合规率: ${evaluationSummary.compliance_rate}%, 等级: ${evaluationSummary.overall_grade}`,
          canAppeal: true
        }]

        // 如果第一条 evaluation_results 有详细的 findings，也添加进去
        const firstResult = evaluationResults[0]
        if (firstResult && firstResult.findings && firstResult.findings.length > 10) {
          issues.push({
            id: generateId(),
            ruleName: firstResult.rule_name || '详细评估结果',
            ruleId: firstResult.rule_id || 'detail-001',
            description: firstResult.findings,
            severity: firstResult.severity || 'medium',
            category: firstResult.category || 'general',
            location: firstResult.location || '病历正文',
            suggestion: firstResult.suggestion || '请根据评估结果进行整改',
            evidence: firstResult.evidence || '',
            canAppeal: true
          })
        }
      }
    } else {
      // 使用从 evaluation_results 中提取的问题列表
      issues = issuesFromResults
    }

    console.log('[adaptSichuanQCResult] 转换后的问题列表:', {
      mode: evaluationResults.length === 1 && evaluationSummary.total_rules > 1 ? 'single_prompt' : 'multi_call',
      issuesCount: issues.length,
      issues: issues.slice(0, 3)
    })

    // 生成改进建议
    const suggestions: QCSuggestion[] = issues.length > 0
      ? [{
          id: generateId(),
          category: '质控整改',
          title: '完善病历质控项',
          description: `发现 ${issues.length} 个质控问题，建议根据规则要求进行整改`,
          priority: 'high' as const,
          actionRequired: true
        }]
      : []

    // 将评估结果转换为规则结果列表
    let ruleResults: QCRuleResult[] = evaluationResults.map((result: any) => ({
      ruleId: result.rule_id || '',
      ruleName: result.rule_name || '质控规则',
      passed: result.is_compliant || false,
      score: result.is_compliant ? 100 : 0,
      maxScore: 100,
      details: result.findings || result.description || '',
      executionTime: performanceMetrics.processing_time || 0,
      confidence: result.confidence || 0.85,
      evidence: result.evidence || '',
      location: result.location || '',
      suggestion: result.suggestion || ''
    }))

    // 加强兜底：只有汇总或全部显示通过时，尽量还原出不通过的规则
    if ((ruleResults.length <= 1 || ruleResults.every(r => r.passed)) && (evaluationSummary.total_rules > 1)) {
      const first: any = evaluationResults[0] || {}

      // 1) 优先尝试从后端的 violations/non_compliant_rules/failed_rules 中提取
      const candidates: any[] = []
      ;['violations', 'non_compliant_rules', 'failed_rules'].forEach((k) => {
        const arr = first?.[k]
        if (Array.isArray(arr)) candidates.push(...arr)
      })

      if (candidates.length > 0) {
        const toRuleResult = (v: any): QCRuleResult => {
          const rid = String(v.rule_id || v.ruleId || '')
          const rname = String(v.rule_name || v.ruleName || v.title || '质控规则')
          const matched = (selectedRules.value || []).find((r: any) => String(r.id) === rid || String(r.name || '').toLowerCase() === rname.toLowerCase())
          return {
            ruleId: rid || String(matched?.id || ''),
            ruleName: rname || String(matched?.name || (matched ? `规则-${matched.id}` : '质控规则')),
            passed: false,
            score: Number(v.score ?? 60),
            maxScore: Number(v.max_score ?? 100),
            details: v.description || v.details || v.findings || '该规则存在不合规项',
            executionTime: Number(performanceMetrics.processing_time || 0),
            confidence: Number(v.confidence ?? 0.75),
            evidence: v.evidence || '',
            location: v.location || '',
            suggestion: v.suggestion || '请根据规则要求进行整改'
          }
        }

        const failedResults = candidates.map(toRuleResult)
        const existing = new Map<string, QCRuleResult>()
        ruleResults.forEach(r => existing.set(r.ruleId || r.ruleName, r))
        failedResults.forEach(fr => existing.set(fr.ruleId || fr.ruleName, fr))
        ruleResults = Array.from(existing.values())

        // 同步生成 issues（若还没有逐条）
        if (issues.length <= 1) {
          failedResults.forEach(fr => {
            issues.push({
              id: generateId(),
              ruleName: fr.ruleName,
              ruleId: fr.ruleId,
              description: fr.details,
              severity: 'high',
              category: 'rule',
              location: '病历正文',
              suggestion: '请根据规则要求进行整改',
              canAppeal: true
            })
          })
        }
      } else if ((selectedRules.value?.length || 0) > 0) {
        // 2) 仍无可用详细数据时，根据汇总不合规数量，合成前 N 条为未通过
        const nonCompliantCount = Math.max((evaluationSummary.total_rules || 0) - (evaluationSummary.compliant_rules || 0), 0)
        if (nonCompliantCount > 0) {
          const failing = (selectedRules.value as any[]).slice(0, nonCompliantCount)
          const failingSet = new Set(failing.map(r => String(r.id)))

          ruleResults = (selectedRules.value as any[]).map((rule: any) => {
            const exist = ruleResults.find(r => r.ruleId === String(rule.id))
            if (exist) return exist
            const fail = failingSet.has(String(rule.id))
            const relatedIssue = issues.find(i => i.ruleId === String(rule.id))
            return {
              ruleId: String(rule.id),
              ruleName: String(rule.name || `规则-${rule.id}`),
              passed: !fail,
              score: !fail ? 100 : 60,
              maxScore: 100,
              details: fail ? (relatedIssue?.description || '该规则在汇总结果中判定为不合规') : '该规则未发现明显问题',
              executionTime: Number(performanceMetrics.processing_time || 0),
              confidence: fail ? 0.75 : 0.85,
              evidence: relatedIssue?.evidence || '',
              location: relatedIssue?.location || '',
              suggestion: relatedIssue?.suggestion || (fail ? '请根据规则要求进行整改' : '')
            }
          })

          // 生成对应 issues
          failing.forEach((rule: any) => {
            if (!issues.some(i => i.ruleId === String(rule.id))) {
              issues.push({
                id: generateId(),
                ruleName: String(rule.name || `规则-${rule.id}`),
                ruleId: String(rule.id),
                description: '该规则在汇总结果中被判定为不合规',
                severity: 'high',
                category: 'rule',
                location: '病历正文',
                suggestion: '请根据规则要求进行整改',
                canAppeal: true
              })
            }
          })
        }
      }
    }

    // 构建元数据
    const metadata: QCResultMetadata = {
      analysisVersion: '2.0.0',
      modelVersion: sichuanResponse.mode === 'single_prompt' ? 'Sichuan-QC-Single-Prompt' : 'Sichuan-QC-Multi-Call',
      processingTime: performanceMetrics.processing_time || 0,
      rulesApplied: evaluationSummary.total_rules || 0,
      totalTokens: performanceMetrics.token_usage || 0,
      confidence: ruleResults.length > 0
        ? ruleResults.reduce((acc, r) => acc + r.confidence, 0) / ruleResults.length
        : 0.85,
      documents: selectedDocumentList.value.map(doc => ({
        id: doc.id,
        title: doc.title,
        type: doc.type
      })),
      record: testRecord.value ? {
        id: testRecord.value.id,
        patientName: testRecord.value.patient_name,
        department: testRecord.value.department
      } : undefined,
      engine: 'Sichuan-QC-Engine',
      analysisId: sichuanResponse.document_id || `qc-${Date.now()}`
    }

    return {
      id: sichuanResponse.document_id || `qc-result-${Date.now()}`,
      recordId: testRecord.value?.id || 'unknown',
      overallScore,
      overallGrade: evaluationSummary.overall_grade || 'B',
      analysisDate: sichuanResponse.timestamp || new Date().toISOString(),
      issues,
      suggestions,
      ruleResults,
      // 兼容部分组件使用的 snake_case 字段
      rule_results: ruleResults as any,
      metadata
    }
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
      rule_results: ruleResults as any,
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
        addDemoLog('info', '准备调用四川质控引擎 API...', {
          recordId: testRecord.value!.id,
          documentsCount: selectedDocumentList.value.length,
          rulesCount: selectedRules.value.length
        })
        progress.value = 20
      })

      let backendResult: unknown = null
      await runStep(2, async () => {
        // 调用四川质控 API（同步返回结果，无需轮询）
        addDemoLog('info', '正在调用四川质控引擎进行分析...', {
          engine: 'Sichuan-QC-Engine',
          mode: 'single_prompt'
        })

        // 获取第一个文档的内容作为分析对象
        const primaryDocument = selectedDocumentList.value[0]
        if (!primaryDocument) {
          throw new Error('未选择文档，无法进行质控分析')
        }

        // 获取文档内容（优先级：content > 生成示例内容）
        let documentContent = (primaryDocument as any)?.content || testRecord.value?.content || ''

        // 如果没有内容，生成一个示例病历内容
        if (!documentContent || documentContent.trim().length === 0) {
          addDemoLog('warning', '未找到病历内容，使用示例内容进行演示', {
            recordId: testRecord.value?.id,
            patientName: testRecord.value?.patient_name
          })

          // 从病历记录中提取诊断信息（可能在不同字段中）
          const diagnosis = (testRecord.value as any)?.diagnosis ||
                           (testRecord.value as any)?.primary_diagnosis ||
                           '胸痛3小时'

          documentContent = `患者${testRecord.value?.patient_name || '张三'}，${testRecord.value?.patient_gender === 'M' ? '男' : '女'}，${testRecord.value?.patient_age || 45}岁，因"${diagnosis}"入院。

现病史：患者于3小时前无明显诱因出现胸痛，呈压榨性，伴大汗，持续不缓解，遂来我院急诊。

既往史：高血压病史5年，规律服药。否认糖尿病、冠心病史。

个人史：吸烟20年，每日1包。

查体：T 36.5℃，P 88次/分，R 18次/分，BP 145/90mmHg。神志清，精神可，心肺腹查体未见明显异常。

辅助检查：心电图示：V1-V4导联ST段抬高0.2-0.3mV。

初步诊断：急性心肌梗死。

诊疗计划：
1. 心内科住院治疗
2. 急诊冠脉造影+支架植入术
3. 抗血小板、抗凝、调脂等药物治疗
4. 心电监护、吸氧
5. 完善相关检查

医师签名：${testRecord.value?.doctor_id || '李医生'}
日期：${testRecord.value?.admission_date || new Date().toISOString().split('T')[0]}`
        }

        // 构建四川质控 API 请求
        // 提取用户选择的规则ID列表
        const ruleIds = selectedRules.value
          .map(rule => rule.rule_code || rule.id)
          .filter(id => id) // 过滤掉空值

        const sichuanPayload = {
          document_id: primaryDocument.id,
          document_content: documentContent,
          document_type: primaryDocument.type || '病程记录',
          rule_ids: ruleIds.length > 0 ? ruleIds : undefined, // 只有选择了规则才传递
          persist: false // 演示模式不持久化
        }

        addDemoLog('info', '发送质控请求到后端...', {
          documentId: sichuanPayload.document_id,
          documentType: sichuanPayload.document_type,
          contentLength: sichuanPayload.document_content.length,
          contentSource: ((primaryDocument as any)?.content ? 'document.content' : (testRecord.value?.content ? 'record.content' : 'generated')),
          selectedRulesCount: ruleIds.length,
          ruleIds: ruleIds.slice(0, 5) // 只显示前5个规则ID
        })

        try {
          // 调用四川质控 API
          const response = await ApiService.post('/api/v1/qc/sichuan/evaluate', sichuanPayload, { timeout: 120000 })

          if (!response.success || !response.data) {
            throw new Error(response.error || '四川质控引擎未返回结果')
          }

          backendResult = response.data
          analysisId = response.data.document_id || `qc-${Date.now()}`

          addDemoLog('info', '质控分析完成', {
            analysisId,
            complianceRate: response.data.evaluation_summary?.compliance_rate,
            totalRules: response.data.evaluation_summary?.total_rules,
            processingTime: response.data.performance_metrics?.processing_time
          })

          console.log('✅ [四川质控] 分析完成:', {
            documentId: response.data.document_id,
            complianceRate: response.data.evaluation_summary?.compliance_rate,
            grade: response.data.evaluation_summary?.overall_grade,
            tokenUsage: response.data.performance_metrics?.token_usage
          })

        } catch (err) {
          addDemoLog('error', '质控分析失败', {
            error: err instanceof Error ? err.message : String(err)
          })
          throw err
        }

        if (!backendResult) {
          throw new Error('质控引擎未返回有效结果')
        }

        // 使用四川质控专用的转换函数
        const adapted = adaptSichuanQCResult(backendResult)
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
      handleError(err, {
        operation: '执行质控分析',
        component: 'QCDemoStore',
        details: {
          recordId: testRecord.value?.id,
          rulesCount: selectedRules.value.length,
          documentsCount: selectedDocumentList.value.length,
          analysisId
        }
      })
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
        // 尝试使用本地API（医疗记录）和四川质控规则
        const [apiRecords, sichuanRules] = await Promise.all([
          ApiService.getMedicalRecords({ page: 1, page_size: 20 }),
          demoDataService.getSichuanQCRules()
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

        if (sichuanRules && sichuanRules.length > 0) {
          rules = sichuanRules
          console.log('[QCDemoStore] ✅ 四川省质控规则加载成功:', rules.length, '条')
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

        // 回退到原有的Supabase逻辑（使用四川规则）
        const [supabaseRecords, sichuanRulesBackup, supabaseDepartments] = await Promise.all([
          demoDataService.getMedicalRecords({
            limit: 20,
            ...recordFilters.value
          }),
          demoDataService.getSichuanQCRules(),
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
        rules = sichuanRulesBackup
        departments = supabaseDepartments
        console.log('[QCDemoStore] ✅ Supabase回退成功，加载了', rules.length, '条四川规则')
      }

      availableRecords.value = records
      availableRules.value = rules as QualityControlRule[]
      syncSelectedRulesWithAvailable()
      availableDepartments.value = departments

      // 智能选择默认测试记录
      if (!testRecord.value && availableRecords.value.length > 0) {
        // 优先选择有完整信息的记录
        const preferredRecord = availableRecords.value.find(r =>
          r.patient_info && r.primary_diagnosis
        ) || availableRecords.value[0]
        testRecord.value = preferredRecord
      }

      // 智能选择默认文书（如果测试记录已选择但文书未选择）
      if (testRecord.value && !selectedDocument.value) {
        // 尝试从测试记录中获取文书列表
        const recordDocuments = testRecord.value.documents || []
        if (recordDocuments.length > 0) {
          // 优先选择首次病程记录或入院记录
          const preferredDoc = recordDocuments.find((doc: any) =>
            doc.type === '首次病程记录' || doc.type === '入院记录'
          ) || recordDocuments[0]
          selectedDocument.value = preferredDoc
          console.log('[QCDemoStore] 自动选择文书:', preferredDoc.title || preferredDoc.type)
        } else {
          // 如果记录没有文书列表，创建一个默认文书
          const defaultDoc = {
            id: `doc-${testRecord.value.id}`,
            title: '首次病程记录',
            type: '首次病程记录',
            created_at: testRecord.value.admission_date || new Date().toISOString()
          }
          selectedDocument.value = defaultDoc
          console.log('[QCDemoStore] 创建默认文书:', defaultDoc.title)
        }
      }

      const dataSource = isDatabaseConnected.value ? '数据库' : '模拟数据'
      console.log(`[QCDemoStore] 数据加载完成 (${dataSource}):`, {
        records: availableRecords.value.length,
        rules: availableRules.value.length,
        departments: availableDepartments.value.length,
        connected: isDatabaseConnected.value,
        selectedRecord: testRecord.value?.id,
        selectedDocument: selectedDocument.value ? (Array.isArray(selectedDocument.value) ? selectedDocument.value.length : 1) : 0,
        selectedRules: selectedRules.value.length,
        canStartDemo: canStartDemo.value
      })

    } catch (err) {
      console.error('[QCDemoStore] 数据加载失败:', err)
      handleError(err, {
        operation: '加载测试数据',
        component: 'QCDemoStore',
        details: { forceRefresh }
      })

      // 即使出错也要确保有基本的模拟数据可用
      if (availableRecords.value.length === 0 || availableRules.value.length === 0) {
        console.log('[QCDemoStore] 尝试加载备用模拟数据...')
        try {
          // 强制使用模拟数据
          isDatabaseConnected.value = false
          availableRecords.value = await demoDataService.getMedicalRecords({ limit: 10 })
          availableRules.value = await demoDataService.getQCRules({ limit: 20 })
          syncSelectedRulesWithAvailable()
          availableDepartments.value = await demoDataService.getDepartments()

          if (!testRecord.value && availableRecords.value.length > 0) {
            testRecord.value = availableRecords.value[0]
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
        // 已在 startDemo() 入口校验可运行条件，且 runQCAnalysis() 内也会再次自检
        await runQCAnalysis()
        break
      default:
        // target / rules 步骤无需自动执行
        break
    }
  }

  const setSelectedRules = (rules: QualityControlRule[]) => {
    selectedRules.value = [...rules]
    syncSelectedRulesWithAvailable()
  }

  const toggleRuleSelection = (rule: QualityControlRule, checked?: boolean) => {
    const id = getRuleIdentifier(rule)
    if (!id) return
    const exists = selectedRules.value.some(r => getRuleIdentifier(r) === id)
    const shouldSelect = checked !== undefined ? checked : !exists

    if (shouldSelect && !exists) {
      selectedRules.value = [...selectedRules.value, rule]
    } else if (!shouldSelect && exists) {
      selectedRules.value = selectedRules.value.filter(r => getRuleIdentifier(r) !== id)
    }
  }

  const selectAllRules = (rules: QualityControlRule[]) => {
    const map = new Map<string, QualityControlRule>()
    selectedRules.value.forEach(rule => {
      const id = getRuleIdentifier(rule)
      if (id) map.set(id, rule)
    })
    rules.forEach(rule => {
      const id = getRuleIdentifier(rule)
      if (id) map.set(id, rule)
    })
    selectedRules.value = Array.from(map.values())
    syncSelectedRulesWithAvailable()
  }

  const clearSelectedRules = () => {
    selectedRules.value = []
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

  // ==================== 预置示例加载 ====================

  /**
   * 加载预置示例
   * @param exampleKey 示例键名（如 'firstCourseRecord'）
   */
  const loadPresetExample = (exampleKey: string) => {
    const example = PRESET_EXAMPLES[exampleKey]
    if (!example) {
      addDemoLog('error', `预置示例不存在: ${exampleKey}`)
      return
    }

    // 设置病历内容
    testRecord.value = {
      id: example.id,
      patient_name: example.patientInfo.patientName,
      patient_age: example.patientInfo.age,
      patient_gender: example.patientInfo.gender === '男' ? 'M' : 'F',
      department: example.patientInfo.department,
      admission_date: example.patientInfo.admissionTime,
      record_type: 'inpatient',
      status: 'pending',
      content: example.content,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      // 添加额外字段用于显示
      admission_number: example.patientInfo.admissionNumber,
      bed_number: example.patientInfo.bedNumber,
      diagnosis: example.patientInfo.diagnosis
    } as MedicalRecord & { admission_number?: string; bed_number?: string; diagnosis?: string }

    // 设置文书内容
    selectedDocument.value = {
      id: example.id,
      title: example.title,
      type: example.type,
      created_at: new Date().toISOString()
    }

    addDemoLog('info', `已加载预置示例：${example.title}`)

    // 自动跳转到规则配置步骤
    if (currentStep.value === 'target') {
      nextStep()
    }
  }

  /**
   * 获取所有预置示例列表
   */
  const getPresetExamples = () => {
    return Object.entries(PRESET_EXAMPLES).map(([key, example]) => ({
      key,
      title: example.title,
      type: example.type,
      description: `${example.patientInfo.patientName}，${example.patientInfo.age}岁${example.patientInfo.gender}，${example.patientInfo.diagnosis}`
    }))
  }

  /**
   * 获取当前病历信息（用于病历信息卡片）
   */
  const currentRecordInfo = computed(() => {
    if (!testRecord.value) return null

    const record = testRecord.value as MedicalRecord & {
      admission_number?: string
      bed_number?: string
      diagnosis?: string
    }

    return {
      patientName: record.patient_name,
      age: record.patient_age,
      gender: record.patient_gender === 'M' ? '男' : record.patient_gender === 'F' ? '女' : '未知',
      department: record.department,
      admissionNumber: record.admission_number || '-',
      bedNumber: record.bed_number || '-',
      admissionTime: record.admission_date,
      recordTime: record.created_at,
      diagnosis: record.diagnosis || '-'
    }
  })

  /**
   * 获取当前文书信息
   */
  const currentDocumentInfo = computed(() => {
    if (!selectedDocument.value) return null

    const doc = Array.isArray(selectedDocument.value)
      ? selectedDocument.value[0]
      : selectedDocument.value

    return {
      type: doc.type,
      title: doc.title
    }
  })

  // ==================== 监听器 ====================

  // 监听文书选择变化，自动更新规则选择
  watch(
    () => selectedDocumentPrimary.value?.type,
    (newDocumentType, oldDocumentType) => {
      if (newDocumentType && newDocumentType !== oldDocumentType && availableRules.value.length > 0) {
        console.log(`[QCDemoStore] 文书类型变化: "${oldDocumentType}" → "${newDocumentType}"`)
        const validIds = new Set(applicableRules.value.map(rule => getRuleIdentifier(rule)))
        const before = selectedRules.value.length
        if (before > 0) {
          selectedRules.value = selectedRules.value.filter(rule => validIds.has(getRuleIdentifier(rule)))
          const after = selectedRules.value.length
          if (after !== before) {
            addDemoLog('info', `已根据文书类型调整选中的规则`, {
              before,
              after,
              documentType: newDocumentType
            })
          }
        }
      }
    }
  )

  // ==================== 返回接口 ====================

  return {
    // 状态
    isRunning,
    isPaused,
    pauseStartTime,
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

    // 错误处理状态
    errorLogs,

    // 演示日志状态
    demoLogs,

    // 性能监控状态
    stepTimings,
    apiCalls,
    memoryInfo,
    performanceMonitorEnabled,

    // 数据状态
    isDatabaseConnected,
    isLoadingData,
    availableRecords,
    availableRules,
    applicableRules, // 根据当前文书类型过滤的适用规则
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
    currentRecordInfo,
    currentDocumentInfo,

    // 统计相关计算属性
    selectedRulesCount,
    totalRulesCount, // 适用于当前文书类型的规则总数
    allRulesCount, // 所有规则总数（未过滤）
    analysisCompletedCount,
    totalRecordsCount,
    unreadNotificationsCount,
    totalNotificationsCount,
    pendingAppealsCount,
    totalAppealsCount,
    averageQCScore,
    demoStartTime,


    // 错误处理方法
    handleError,
    clearError,
    getErrorLogs,
    clearErrorLogs,

    // 演示日志方法
    addDemoLog,
    clearDemoLogs,
    getDemoLogs,

    // 性能监控方法
    startStepTiming,
    endStepTiming,
    recordApiCall,
    updateMemoryInfo,
    resetPerformanceData,
    togglePerformanceMonitor,

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

    // 预置示例方法
    loadPresetExample,
    getPresetExamples,

    // 状态持久化
    saveDemoState,
    restoreDemoState,
    clearSavedState,
    exportDemoData,
    importDemoData,

    // 规则管理方法
    setSelectedRules,
    toggleRuleSelection,
    selectAllRules,
    clearSelectedRules
  }
})
