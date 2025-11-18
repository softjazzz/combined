/**
 * 四川质控引擎 Pinia Store
 * 管理四川质控演示的状态和逻辑
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import ApiService from '@/services/apiService'

// 预置的首次病程记录示例
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

腹部：腹部平软，无压痛、反跳痛，肝脾肋下未触及，Murphy征阴性，移动性浊音阴性，肠鸣音正常。

脊柱四肢：脊柱无畸形，四肢活动正常，双下肢无水肿。

神经系统：生理反射存在，病理反射未引出。

七、辅助检查
1. 心电图（2025-10-11 急诊）：V1-V4导联ST段压低0.1-0.2mV，T波倒置。
2. 心肌酶谱（2025-10-11 急诊）：
   - 肌钙蛋白I：0.8 ng/mL（正常值<0.04 ng/mL）↑
   - 肌酸激酶同工酶（CK-MB）：45 U/L（正常值<25 U/L）↑
3. 血常规（2025-10-11）：WBC 8.5×10^9/L，RBC 4.8×10^12/L，Hb 145 g/L，PLT 220×10^9/L。
4. 生化全套（2025-10-11）：
   - 空腹血糖：8.2 mmol/L（正常值3.9-6.1 mmol/L）↑
   - 总胆固醇：6.5 mmol/L（正常值<5.2 mmol/L）↑
   - 低密度脂蛋白：4.2 mmol/L（正常值<3.4 mmol/L）↑
   - 肝肾功能正常。

八、初步诊断
1. 急性冠脉综合征（ACS）
   - 不稳定型心绞痛？
   - 非ST段抬高型心肌梗死（NSTEMI）？
2. 高血压病 3级 很高危
3. 2型糖尿病
4. 血脂异常

九、诊疗计划
1. 完善检查：
   - 急查心肌标志物动态变化
   - 心脏彩超
   - 冠脉CTA或冠脉造影
   - 动态心电图监测
   
2. 治疗方案：
   - 一级护理，心电监护，吸氧
   - 绝对卧床休息，低盐低脂糖尿病饮食
   - 抗血小板聚集：阿司匹林 100mg qd + 氯吡格雷 75mg qd
   - 抗凝治疗：低分子肝素 4000U q12h 皮下注射
   - 扩冠治疗：硝酸甘油 10mg 静脉泵入
   - 调脂稳定斑块：阿托伐他汀 20mg qn
   - 控制血压：继续硝苯地平缓释片 30mg qd
   - 控制血糖：胰岛素降糖治疗，监测血糖
   - 改善心肌代谢：曲美他嗪 20mg tid
   
3. 病情观察：
   - 密切观察胸痛、胸闷症状变化
   - 监测生命体征、心电图变化
   - 监测心肌标志物动态变化
   - 注意有无心律失常、心力衰竭等并发症

十、医师签名
主治医师：张医生
记录时间：2025年10月11日 15:00`

// 病历信息接口
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

// 质控结果接口
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
  evaluation_results: any[]
  timestamp: string
  status: string
  mode: string
}

// 分类合规率接口
interface CategoryCompliance {
  category: string
  compliant_count: number
  total_count: number
  compliance_rate: number
}

// 违规项接口
interface Violation {
  id: string
  title: string
  severity: 'high' | 'medium' | 'low'
  description: string
  suggestion: string
}

// 日志条目接口
interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error'
  message: string
  details?: any
}

export const useSichuanQCStore = defineStore('sichuanQC', () => {
  // ========== 状态 ==========
  
  // 病历内容
  const documentContent = ref<string>('')
  const documentType = ref<string>('首次病程记录')
  const documentId = ref<string>('')
  
  // 病历信息
  const medicalRecordInfo = ref<MedicalRecordInfo>({
    patientName: '李明',
    age: 58,
    gender: '男',
    department: '心内科',
    admissionNumber: '2025001234',
    bedNumber: '15床',
    admissionTime: '2025年10月11日 09:30',
    recordTime: '2025年10月11日 15:00',
    diagnosis: '急性冠脉综合征（ACS）'
  })
  
  // 质控结果
  const qcResult = ref<QCResult | null>(null)
  
  // 分析状态
  const isAnalyzing = ref(false)
  const analysisStartTime = ref<Date | null>(null)
  const analysisEndTime = ref<Date | null>(null)
  
  // 日志
  const logs = ref<LogEntry[]>([])
  
  // ========== 计算属性 ==========
  
  // 统计数据
  const totalRules = computed(() => qcResult.value?.evaluation_summary.total_rules || 0)
  const complianceRate = computed(() => qcResult.value?.evaluation_summary.compliance_rate || 0)
  const criticalViolations = computed(() => qcResult.value?.evaluation_summary.critical_violations || 0)
  const processingTime = computed(() => qcResult.value?.performance_metrics.processing_time || 0)
  const tokenUsage = computed(() => qcResult.value?.performance_metrics.token_usage || 0)
  const tokenSavingsRate = computed(() => qcResult.value?.optimization_metrics.token_savings_rate || 0)
  
  // 分类合规率（模拟数据，实际应从 evaluation_results 中解析）
  const categoryCompliance = computed<CategoryCompliance[]>(() => {
    if (!qcResult.value) return []
    
    return [
      { category: '完整性', compliant_count: 18, total_count: 20, compliance_rate: 90.0 },
      { category: '规范性', compliant_count: 15, total_count: 18, compliance_rate: 83.3 },
      { category: '准确性', compliant_count: 12, total_count: 15, compliance_rate: 80.0 },
      { category: '逻辑性', compliant_count: 12, total_count: 15, compliance_rate: 80.0 }
    ]
  })
  
  // 严重违规项（模拟数据）
  const violations = computed<Violation[]>(() => {
    if (!qcResult.value) return []
    
    return [
      {
        id: 'v1',
        title: '缺少病情分析和诊断依据',
        severity: 'high',
        description: '首次病程记录中未包含病情分析和诊断依据部分',
        suggestion: '补充病情分析，明确诊断依据，添加风险评估（GRACE评分或TIMI评分）'
      },
      {
        id: 'v2',
        title: '缺少鉴别诊断',
        severity: 'high',
        description: '未列出需要鉴别的疾病',
        suggestion: '补充鉴别诊断，如肺栓塞、主动脉夹层、急性心包炎等'
      },
      {
        id: 'v3',
        title: '医嘱格式不规范',
        severity: 'medium',
        description: '医嘱格式不符合标准，缺少具体时间和护理级别',
        suggestion: '规范医嘱格式，补充医嘱时间，明确护理级别和饮食医嘱'
      }
    ]
  })
  
  // ========== 方法 ==========
  
  // 添加日志
  const addLog = (level: 'info' | 'warning' | 'error', message: string, details?: any) => {
    logs.value.push({
      timestamp: new Date().toISOString(),
      level,
      message,
      details
    })
  }
  
  // 加载预置示例
  const loadPresetExample = () => {
    documentContent.value = PRESET_FIRST_COURSE_RECORD
    documentType.value = '首次病程记录'
    documentId.value = 'preset-first-course-record'
    
    addLog('info', '已加载预置示例：首次病程记录（李明，58岁男性）')
    message.success('已加载预置示例病历')
  }
  
  // 设置自定义病历
  const setCustomDocument = (content: string, type: string = '首次病程记录') => {
    documentContent.value = content
    documentType.value = type
    documentId.value = `custom-${Date.now()}`
    
    addLog('info', `已设置自定义病历，类型：${type}，长度：${content.length}字符`)
    message.success('已设置自定义病历')
  }
  
  // 开始质控分析
  const startQCAnalysis = async () => {
    if (!documentContent.value) {
      message.error('请先选择或输入病历内容')
      return
    }
    
    isAnalyzing.value = true
    analysisStartTime.value = new Date()
    qcResult.value = null
    
    addLog('info', '开始质控分析...', {
      documentType: documentType.value,
      contentLength: documentContent.value.length
    })
    
    try {
      // 调用后端 API
      addLog('info', '正在调用四川质控引擎 API...')

      const response = await ApiService.post('/api/v1/qc/sichuan/evaluate', {
        document_id: documentId.value,
        document_content: documentContent.value,
        document_type: documentType.value,
        persist: false
      }, { timeout: 120000 })
      
      analysisEndTime.value = new Date()
      qcResult.value = response.data
      
      addLog('info', '质控分析完成', {
        totalRules: response.data.evaluation_summary.total_rules,
        complianceRate: response.data.evaluation_summary.compliance_rate,
        processingTime: response.data.performance_metrics.processing_time
      })
      
      message.success(`质控分析完成！合规率：${response.data.evaluation_summary.compliance_rate}%`)
      
    } catch (error: any) {
      analysisEndTime.value = new Date()
      
      addLog('error', '质控分析失败', {
        error: error.message,
        response: error.response?.data
      })
      
      message.error(`质控分析失败：${error.message}`)
      
    } finally {
      isAnalyzing.value = false
    }
  }
  
  // 导出报告
  const exportReport = (format: 'json' | 'markdown' | 'pdf' = 'json') => {
    if (!qcResult.value) {
      message.error('暂无质控报告可导出')
      return
    }
    
    addLog('info', `导出质控报告，格式：${format}`)
    
    if (format === 'json') {
      const blob = new Blob([JSON.stringify(qcResult.value, null, 2)], {
        type: 'application/json'
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `qc-report-${documentId.value}.json`
      a.click()
      URL.revokeObjectURL(url)
      
      message.success('JSON 报告已导出')
    } else if (format === 'markdown') {
      // TODO: 生成 Markdown 格式报告
      message.info('Markdown 导出功能开发中...')
    } else if (format === 'pdf') {
      // TODO: 生成 PDF 格式报告
      message.info('PDF 导出功能开发中...')
    }
  }
  
  // 清空日志
  const clearLogs = () => {
    logs.value = []
    addLog('info', '日志已清空')
  }
  
  // 重置状态
  const reset = () => {
    documentContent.value = ''
    documentType.value = '首次病程记录'
    documentId.value = ''
    qcResult.value = null
    isAnalyzing.value = false
    analysisStartTime.value = null
    analysisEndTime.value = null
    logs.value = []
    
    message.info('已重置所有状态')
  }
  
  return {
    // 状态
    documentContent,
    documentType,
    documentId,
    medicalRecordInfo,
    qcResult,
    isAnalyzing,
    analysisStartTime,
    analysisEndTime,
    logs,
    
    // 计算属性
    totalRules,
    complianceRate,
    criticalViolations,
    processingTime,
    tokenUsage,
    tokenSavingsRate,
    categoryCompliance,
    violations,
    
    // 方法
    addLog,
    loadPresetExample,
    setCustomDocument,
    startQCAnalysis,
    exportReport,
    clearLogs,
    reset
  }
})

