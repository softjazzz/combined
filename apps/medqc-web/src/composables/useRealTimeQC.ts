/**
 * 实时质控监控系统
 * 实现病案录入过程中的实时质控分析和预警
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { supabase, TABLES } from '@/lib/supabase'
import { analyzeWithDeepSeek } from '@/api/deepseek-api'
import { wsManager } from '@/utils/websocket-manager'
import { message } from 'ant-design-vue'

// 质控预警级别
export type QCAlertLevel = 'info' | 'warning' | 'error' | 'critical'

// 实时质控分析结果
export interface RealTimeQCResult {
  id: string
  recordId: string
  content: string
  analysisResult: Record<string, unknown>
  alertLevel: QCAlertLevel
  issues: QCIssue[]
  suggestions: string[]
  confidence: number
  timestamp: string
  processingTime: number
}

// 质控问题
export interface QCIssue {
  type: string
  severity: QCAlertLevel
  message: string
  location?: string
  suggestion?: string
  ruleId?: string
}

// 实时监控状态
export interface RealTimeMonitorStatus {
  isActive: boolean
  connectedUsers: number
  activeAnalyses: number
  totalAnalysesToday: number
  averageResponseTime: number
  systemLoad: number
}

// 质控规则
export interface QCRule {
  id: string
  name: string
  description: string
  type: 'content' | 'format' | 'logic' | 'completeness'
  severity: QCAlertLevel
  pattern?: string
  isActive: boolean
  priority: number
}

export function useRealTimeQC() {
  // 响应式数据
  const isMonitoring = ref(false)
  const monitorStatus = ref<RealTimeMonitorStatus>({
    isActive: false,
    connectedUsers: 0,
    activeAnalyses: 0,
    totalAnalysesToday: 0,
    averageResponseTime: 0,
    systemLoad: 0
  })

  const activeAnalyses = ref<Map<string, RealTimeQCResult>>(new Map())
  const recentResults = ref<RealTimeQCResult[]>([])
  const qcRules = ref<QCRule[]>([])
  const alertQueue = ref<QCIssue[]>([])

  // WebSocket连接
  let wsConnection = null
  let messageUnsubscribe: (() => void) | null = null

  // 计算属性
  const criticalIssues = computed(() => 
    alertQueue.value.filter(issue => issue.severity === 'critical')
  )

  const warningIssues = computed(() => 
    alertQueue.value.filter(issue => issue.severity === 'warning')
  )

  const systemHealth = computed(() => {
    const { averageResponseTime, systemLoad } = monitorStatus.value
    if (averageResponseTime > 5000 || systemLoad > 80) return 'poor'
    if (averageResponseTime > 2000 || systemLoad > 60) return 'fair'
    return 'good'
  })

  /**
   * 启动实时监控
   */
  const startRealTimeMonitoring = async () => {
    try {
      console.log('🚀 启动实时质控监控...')
      
      // 初始化WebSocket连接
      await initializeWebSocket()
      
      // 加载质控规则
      await loadQCRules()

      // 启动系统状态更新
      startSystemStatusUpdate()

      isMonitoring.value = true
      monitorStatus.value.isActive = true
      
      message.success('实时质控监控已启动')
      console.log('✅ 实时质控监控启动成功')
    } catch (error) {
      console.error('❌ 启动实时监控失败:', error)
      message.error('启动实时监控失败')
      throw error
    }
  }

  /**
   * 停止实时监控
   */
  const stopRealTimeMonitoring = async () => {
    try {
      console.log('⏹️ 停止实时质控监控...')

      // 取消消息监听
      if (messageUnsubscribe) {
        messageUnsubscribe()
        messageUnsubscribe = null
      }

      // 关闭WebSocket连接
      if (wsConnection) {
        await wsManager.closeConnection('realtime_qc_monitor')
        wsConnection = null
      }

      isMonitoring.value = false
      monitorStatus.value.isActive = false

      message.info('实时质控监控已停止')
      console.log('✅ 实时质控监控已停止')
    } catch (error) {
      console.error('❌ 停止实时监控失败:', error)
    }
  }

  /**
   * 初始化WebSocket连接
   */
  const initializeWebSocket = async () => {
    try {
      // 使用优化的WebSocket管理器
      wsConnection = await wsManager.createConnection('realtime_qc_monitor', {
        maxRetries: 3,
        retryDelay: 2000,
        heartbeatInterval: 30000,
        reconnectOnError: true,
        bufferSize: 50
      })

      // 监听消息
      messageUnsubscribe = wsManager.onMessage('realtime_qc_monitor', (message) => {
        if (message.type === 'postgres_changes') {
          const { payload } = message
          if (payload.table === TABLES.MEDICAL_RECORDS) {
            handleRecordChange(payload)
          } else if (payload.table === TABLES.QC_RESULTS) {
            handleQCResultChange(payload)
          }
        }
      })

      console.log('✅ 优化的WebSocket连接已建立')
    } catch (error) {
      console.error('❌ WebSocket连接失败:', error)
      throw error
    }
  }

  /**
   * 处理病案记录变化
   */
  const handleRecordChange = async (payload) => {
    const { eventType, new: newRecord, old: oldRecord } = payload

    try {
      if (eventType === 'INSERT' || eventType === 'UPDATE') {
        // 触发实时质控分析
        await performRealTimeAnalysis(newRecord)
      }
    } catch (error) {
      console.error('处理病案记录变化失败:', error)
    }
  }

  /**
   * 处理质控结果变化
   */
  const handleQCResultChange = (payload) => {
    const { eventType, new: newResult } = payload

    if (eventType === 'INSERT' || eventType === 'UPDATE') {
      // 更新实时监控状态
      updateMonitorStatus(newResult)
    }
  }

  /**
   * 执行实时质控分析
   */
  const performRealTimeAnalysis = async (record) => {
    const startTime = Date.now()
    const analysisId = `analysis_${record.id}_${startTime}`

    try {
      console.log(`🔍 开始实时质控分析: ${analysisId}`)

      // 创建分析记录
      const analysis: RealTimeQCResult = { id: analysisId,
        recordId: record.id,
        content: record.content,
        analysisResult: null,
        alertLevel: 'info',
        issues: [],
        suggestions:  [],
        confidence: 0,
        timestamp: new Date().toISOString(),
        processingTime: 0
      }

      // 添加到活跃分析列表
      activeAnalyses.value.set(analysisId, analysis)
      monitorStatus.value.activeAnalyses = activeAnalyses.value.size

      // 应用质控规则
      const ruleResults = await applyQCRules(record.content)
      
      // 执行AI分析
      const aiAnalysis = await analyzeWithDeepSeek(record.content)
      
      // 合并分析结果
      const finalResult = mergeAnalysisResults(ruleResults, aiAnalysis)
      
      // 计算处理时间
      const processingTime = Date.now() - startTime
      
      // 更新分析结果
      analysis.analysisResult = finalResult
      analysis.alertLevel = determineAlertLevel(finalResult)
      analysis.issues = extractIssues(finalResult)
      analysis.suggestions = extractSuggestions(finalResult)
      analysis.confidence = calculateConfidence(finalResult)
      analysis.processingTime = processingTime

      // 移除活跃分析，添加到结果列表
      activeAnalyses.value.delete(analysisId)
      recentResults.value.unshift(analysis)
      
      // 保持最近结果列表大小
      if (recentResults.value.length > 100) {
        recentResults.value = recentResults.value.slice(0, 100)
      }

      // 更新监控状态
      updateAnalysisStats(processingTime)

      // 处理预警
      await handleAlerts(analysis)

      console.log(`✅ 实时质控分析完成: ${analysisId}, 耗时: ${processingTime}ms`)

      return analysis
    } catch (error) {
      console.error(`❌ 实时质控分析失败: ${analysisId}`, error)
      
      // 清理失败的分析
      activeAnalyses.value.delete(analysisId)
      monitorStatus.value.activeAnalyses = activeAnalyses.value.size
      
      throw error
    }
  }

  /**
   * 应用质控规则
   */
  const applyQCRules = async (content: string) => {
    const results = []
    
    for (const rule of qcRules.value.filter(r => r.isActive)) {
      try {
        const result = await applyRule(rule, content)
        if (result) {
          results.push(result)
        }
      } catch (error) {
        console.error(`规则应用失败: ${rule.id}`, error)
      }
    }
    
    return results
  }

  /**
   * 应用单个质控规则
   */
  const applyRule = async (rule: QCRule, content: string) => {
    switch (rule.type) {
      case 'content':
        return applyContentRule(rule, content)
      case 'format':
        return applyFormatRule(rule, content)
      case 'logic':
        return applyLogicRule(rule, content)
      case 'completeness':
        return applyCompletenessRule(rule, content)
      default:
        return null
    }
  }

  /**
   * 应用内容规则
   */
  const applyContentRule = (rule: QCRule, content: string) => {
    if (!rule.pattern) return null
    
    const regex = new RegExp(rule.pattern, 'gi')
    const matches = content.match(regex)
    
    if (matches) {
      return {
        ruleId: rule.id,
        type: rule.type,
        severity: rule.severity,
        message: `发现${matches.length}处内容问题: ${rule.description}`,
        matches: matches
      }
    }
    
    return null
  }

  /**
   * 应用格式规则
   */
  const applyFormatRule = (rule: QCRule, content: string) => {
    // 实现格式检查逻辑
    const issues = []
    
    // 检查必要的格式要素
    const requiredSections = ['主诉', '现病史', '既往史', '体格检查']
    for (const section of requiredSections) {
      if (!content.includes(section)) {
        issues.push({
          type: 'missing_section',
          message: `缺少必要章节: ${section}`,
          severity: 'warning' as QCAlertLevel
        })
      }
    }
    
    return issues.length > 0 ? {
      ruleId: rule.id,
      type: rule.type,
      severity: rule.severity,
      message: `发现${issues.length}个格式问题`,
      issues: issues
    } : null
  }

  /**
   * 应用逻辑规则
   */
  const applyLogicRule = (rule: QCRule, content: string) => {
    // 实现逻辑一致性检查
    const issues = []
    
    // 检查年龄和疾病的逻辑一致性
    const ageMatch = content.match(/年龄[：:]\s*(\d+)/i)
    const age = ageMatch ? parseInt(ageMatch[1]) : null
    
    if (age !== null) {
      if (age < 18 && content.includes('高血压')) {
        issues.push({
          type: 'logic_inconsistency',
          message: '年龄与疾病不符：未成年人患高血压较少见',
          severity: 'warning' as QCAlertLevel
        })
      }
    }
    
    return issues.length > 0 ? {
      ruleId: rule.id,
      type: rule.type,
      severity: rule.severity,
      message: `发现${issues.length}个逻辑问题`,
      issues: issues
    } : null
  }

  /**
   * 应用完整性规则
   */
  const applyCompletenessRule = (rule: QCRule, content: string) => {
    // 实现完整性检查
    const issues = []
    
    // 检查基本信息完整性
    const requiredInfo = ['姓名', '性别', '年龄', '科室']
    for (const info of requiredInfo) {
      if (!content.includes(info)) {
        issues.push({
          type: 'missing_info',
          message: `缺少基本信息: ${info}`,
          severity: 'error' as QCAlertLevel
        })
      }
    }
    
    return issues.length > 0 ? {
      ruleId: rule.id,
      type: rule.type,
      severity: rule.severity,
      message: `发现${issues.length}个完整性问题`,
      issues: issues
    } : null
  }

  /**
   * 合并分析结果
   */
  const mergeAnalysisResults = (ruleResults: unknown[], aiAnalysis: unknown) => {
    return {
      ruleResults,
      aiAnalysis,
      timestamp: new Date().toISOString()
    }
  }

  /**
   * 确定预警级别
   */
  const determineAlertLevel = (analysisResult): QCAlertLevel => {
    const { ruleResults } = analysisResult
    
    if (ruleResults.some((r) => r.severity === 'critical')) return 'critical'
    if (ruleResults.some((r: unknown) => r.severity === 'error')) return 'error'
    if (ruleResults.some((r: unknown) => r.severity === 'warning')) return 'warning'
    return 'info'
  }

  /**
   * 提取问题列表
   */
  const extractIssues = (analysisResult): QCIssue[] => {
    const issues: QCIssue[] = []
    
    // 从规则结果中提取问题
    for (const result of analysisResult.ruleResults) {
      if (result.issues) {
        issues.push(...result.issues)
      } else {
        issues.push({
          type: result.type,
          severity: result.severity,
          message: result.message,
          ruleId: result.ruleId
        })
      }
    }
    
    return issues
  }

  /**
   * 提取建议列表
   */
  const extractSuggestions = (analysisResult): string[] => {
    const suggestions: string[] = []
    
    // 从AI分析结果中提取建议
    if (analysisResult.aiAnalysis?.suggestions) {
      suggestions.push(...analysisResult.aiAnalysis.suggestions)
    }
    
    return suggestions
  }

  /**
   * 计算置信度
   */
  const calculateConfidence = (analysisResult): number => {
    // 基于规则匹配和AI分析结果计算置信度
    const ruleCount = analysisResult.ruleResults.length
    const aiConfidence = analysisResult.aiAnalysis?.confidence || 0.5
    
    // 简单的置信度计算
    return Math.min(0.5 + (ruleCount * 0.1) + (aiConfidence * 0.4), 1.0)
  }

  /**
   * 更新分析统计
   */
  const updateAnalysisStats = (processingTime: number) => {
    monitorStatus.value.totalAnalysesToday++
    
    // 更新平均响应时间
    const currentAvg = monitorStatus.value.averageResponseTime
    const totalCount = monitorStatus.value.totalAnalysesToday
    monitorStatus.value.averageResponseTime = 
      (currentAvg * (totalCount - 1) + processingTime) / totalCount
  }

  /**
   * 处理预警
   */
  const handleAlerts = async (analysis: RealTimeQCResult) => {
    for (const issue of analysis.issues) {
      // 添加到预警队列
      alertQueue.value.unshift(issue)
      
      // 保持预警队列大小
      if (alertQueue.value.length > 50) {
        alertQueue.value = alertQueue.value.slice(0, 50)
      }
      
      // 根据严重程度发送通知
      if (issue.severity === 'critical') {
        message.error(`严重质控问题: ${issue.message}`)
      } else if (issue.severity === 'error') {
        message.warning(`质控错误: ${issue.message}`)
      }
    }
  }

  /**
   * 加载质控规则
   */
  const loadQCRules = async () => {
    try {
      const { data, error } = await supabase
        .from(TABLES.QC_RULES)
        .select('*')
        .eq('is_active', true)
        .order('priority', { ascending: false })

      if (error) {
        throw error
      }

      qcRules.value = data || []
      console.log(`✅ 加载了 ${qcRules.value.length} 条质控规则`)
    } catch (error) {
      console.error('❌ 加载质控规则失败:', error)
      // 使用默认规则
      qcRules.value = getDefaultQCRules()
    }
  }

  /**
   * 获取默认质控规则
   */
  const getDefaultQCRules = (): QCRule[] => {
    return [
      {
        id: 'rule_001',
        name: '基本信息完整性',
        description: '检查患者基本信息是否完整',
        type: 'completeness',
        severity: 'error',
        isActive: true,
        priority: 10
      },
      {
        id: 'rule_002',
        name: '病历格式规范',
        description: '检查病历格式是否符合规范',
        type: 'format',
        severity: 'warning',
        isActive: true,
        priority: 8
      },
      {
        id: 'rule_003',
        name: '逻辑一致性',
        description: '检查病历内容逻辑是否一致',
        type: 'logic',
        severity: 'warning',
        isActive: true,
        priority: 6
      }
    ]
  }

  /**
   * 启动系统状态更新
   */
  const startSystemStatusUpdate = () => {
    setInterval(() => {
      updateSystemStatus()
    }, 5000) // 每5秒更新一次系统状态
  }

  /**
   * 更新系统状态
   */
  const updateSystemStatus = () => {
    // 模拟系统负载计算
    const activeCount = activeAnalyses.value.size
    const recentCount = recentResults.value.length
    
    monitorStatus.value.activeAnalyses = activeCount
    monitorStatus.value.systemLoad = Math.min((activeCount * 10) + (recentCount * 0.5), 100)
  }

  /**
   * 更新监控状态
   */
  const updateMonitorStatus = (result) => {
    // 更新连接用户数等状态信息
    // 这里可以根据实际需求实现
  }

  return {
    // 响应式数据
    isMonitoring,
    monitorStatus,
    activeAnalyses,
    recentResults,
    qcRules,
    alertQueue,
    
    // 计算属性
    criticalIssues,
    warningIssues,
    systemHealth,
    
    // 方法
    startRealTimeMonitoring,
    stopRealTimeMonitoring,
    performRealTimeAnalysis,
    loadQCRules
  }
}
