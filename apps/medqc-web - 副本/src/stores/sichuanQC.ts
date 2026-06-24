import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import ApiService from '@/services/apiService'

interface MedicalRecordInfo {
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

interface QCEvaluationSummary {
  total_rules: number
  compliant_rules: number
  compliance_rate: number
  overall_grade: string
  critical_violations: number
}

interface QCPerformanceMetrics {
  processing_time: number
  token_usage: number
  estimated_cost: number
}

interface QCOptimizationMetrics {
  token_savings_rate: number
  estimated_original_tokens: number
  actual_tokens_saved: number
  cost_savings: number
}

interface QCResult {
  document_id: string
  evaluation_summary: QCEvaluationSummary
  performance_metrics: QCPerformanceMetrics
  optimization_metrics: QCOptimizationMetrics
  evaluation_results: unknown[]
  timestamp: string
  status: string
  mode: string
}

interface CategoryCompliance {
  category: string
  compliant_count: number
  total_count: number
  compliance_rate: number
}

interface Violation {
  id: string
  title: string
  severity: 'high' | 'medium' | 'low'
  description: string
  suggestion: string
}

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
  details?: unknown
}

const PRESET_FIRST_COURSE_RECORD = `首次病程记录\n\n主诉：反复胸闷、胸痛3天，加重伴气促1天。\n\n初步诊断：\n1. 急性冠脉综合征\n2. 高血压病3级（极高危）\n3. 2型糖尿病\n\n诊疗计划：心电监护、抗血小板、抗凝、完善冠脉评估。`

export const useSichuanQCStore = defineStore('sichuanQC', () => {
  const documentContent = ref<string>('')
  const documentType = ref<string>('首次病程记录')
  const documentId = ref<string>('')

  const medicalRecordInfo = ref<MedicalRecordInfo>({
    patientName: '示例患者',
    age: 58,
    gender: '男',
    department: '心内科',
    admissionNumber: '2025001234',
    bedNumber: '15床',
    admissionTime: '2025-10-11 09:30',
    recordTime: '2025-10-11 15:00',
    diagnosis: '急性冠脉综合征',
  })

  const qcResult = ref<QCResult | null>(null)
  const isAnalyzing = ref(false)
  const analysisStartTime = ref<Date | null>(null)
  const analysisEndTime = ref<Date | null>(null)
  const logs = ref<LogEntry[]>([])

  const totalRules = computed(() => qcResult.value?.evaluation_summary.total_rules || 0)
  const complianceRate = computed(() => qcResult.value?.evaluation_summary.compliance_rate || 0)
  const criticalViolations = computed(() => qcResult.value?.evaluation_summary.critical_violations || 0)
  const processingTime = computed(() => qcResult.value?.performance_metrics.processing_time || 0)
  const tokenUsage = computed(() => qcResult.value?.performance_metrics.token_usage || 0)
  const tokenSavingsRate = computed(() => qcResult.value?.optimization_metrics.token_savings_rate || 0)

  const categoryCompliance = computed<CategoryCompliance[]>(() => {
    if (!qcResult.value) return []
    return [
      { category: '完整性', compliant_count: 18, total_count: 20, compliance_rate: 90 },
      { category: '规范性', compliant_count: 15, total_count: 18, compliance_rate: 83.3 },
      { category: '准确性', compliant_count: 12, total_count: 15, compliance_rate: 80 },
      { category: '逻辑性', compliant_count: 12, total_count: 15, compliance_rate: 80 },
    ]
  })

  const violations = computed<Violation[]>(() => {
    if (!qcResult.value) return []
    return [
      {
        id: 'v1',
        title: '缺少病情分析',
        severity: 'high',
        description: '病程中未见完整的病情分析段落。',
        suggestion: '补充诊断依据、风险评估及鉴别诊断。',
      },
      {
        id: 'v2',
        title: '医嘱格式不规范',
        severity: 'medium',
        description: '部分医嘱缺少执行频次和时点。',
        suggestion: '规范医嘱书写并补齐频次/时点。',
      },
    ]
  })

  const addLog = (level: 'info' | 'warning' | 'error', msg: string, details?: unknown) => {
    logs.value.push({
      timestamp: new Date().toISOString(),
      level,
      message: msg,
      details,
    })
  }

  const loadPresetExample = () => {
    documentContent.value = PRESET_FIRST_COURSE_RECORD
    documentType.value = '首次病程记录'
    documentId.value = 'preset-first-course-record'
    addLog('info', '已加载预置病历示例')
    message.success('已加载预置病历示例')
  }

  const setCustomDocument = (content: string, type = '首次病程记录') => {
    documentContent.value = content
    documentType.value = type
    documentId.value = `custom-${Date.now()}`
    addLog('info', '已设置自定义病历', { type, length: content.length })
    message.success('已设置自定义病历')
  }

  const startQCAnalysis = async () => {
    if (!documentContent.value) {
      message.error('请先输入病历内容')
      return
    }

    isAnalyzing.value = true
    analysisStartTime.value = new Date()
    qcResult.value = null
    addLog('info', '开始调用四川质控引擎')

    try {
      const response = await ApiService.post<QCResult>('/api/v1/qc/sichuan/evaluate', {
        document_id: documentId.value || `doc-${Date.now()}`,
        document_content: documentContent.value,
        document_type: documentType.value,
        persist: false,
      }, { timeout: 120000 })

      const data = response.data as QCResult | null
      analysisEndTime.value = new Date()

      if (!response.success || !data) {
        throw new Error(response.error || '四川质控接口返回为空')
      }

      qcResult.value = data
      addLog('info', '质控分析完成', {
        totalRules: data.evaluation_summary?.total_rules,
        complianceRate: data.evaluation_summary?.compliance_rate,
        processingTime: data.performance_metrics?.processing_time,
      })
      message.success(`质控分析完成，合规率 ${data.evaluation_summary?.compliance_rate ?? '-'}%`)
    } catch (error: any) {
      analysisEndTime.value = new Date()
      addLog('error', '质控分析失败', { message: error?.message })
      message.error(`质控分析失败：${error?.message || '未知错误'}`)
    } finally {
      isAnalyzing.value = false
    }
  }

  const exportReport = (format: 'json' | 'markdown' | 'pdf' = 'json') => {
    if (!qcResult.value) {
      message.error('暂无报告可导出')
      return
    }
    if (format !== 'json') {
      message.info('该导出格式暂未实现')
      return
    }

    const blob = new Blob([JSON.stringify(qcResult.value, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `qc-report-${documentId.value || 'report'}.json`
    a.click()
    URL.revokeObjectURL(url)
    message.success('JSON 报告已导出')
  }

  const clearLogs = () => {
    logs.value = []
    addLog('info', '日志已清空')
  }

  const reset = () => {
    documentContent.value = ''
    documentType.value = '首次病程记录'
    documentId.value = ''
    qcResult.value = null
    isAnalyzing.value = false
    analysisStartTime.value = null
    analysisEndTime.value = null
    logs.value = []
    message.info('已重置状态')
  }

  return {
    documentContent,
    documentType,
    documentId,
    medicalRecordInfo,
    qcResult,
    isAnalyzing,
    analysisStartTime,
    analysisEndTime,
    logs,
    totalRules,
    complianceRate,
    criticalViolations,
    processingTime,
    tokenUsage,
    tokenSavingsRate,
    categoryCompliance,
    violations,
    addLog,
    loadPresetExample,
    setCustomDocument,
    startQCAnalysis,
    exportReport,
    clearLogs,
    reset,
  }
})
