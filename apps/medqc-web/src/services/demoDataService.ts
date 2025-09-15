/**
 * LLM质控演示数据服务
 * 负责从Supabase数据库获取真实的测试病历和质控规则数据
 */

import { supabase, TABLES, checkSupabaseConnection } from '@/lib/supabase'
import type { MedicalRecord } from '@/types/medical-records'
import type { QualityControlRule } from '@/types/quality-control'

// 数据库医疗记录类型
export interface DatabaseMedicalRecord {
  id: string
  record_number: string
  record_name: string
  patient_info: {
    name: string
    age: number
    gender: string
    phone?: string
  }
  department: string
  primary_diagnosis: string
  secondary_diagnosis: string[]
  major_surgery: string
  raw_text?: string
  ai_extraction_result: any
  ai_confidence_score: number
  documents: any[]
  status: 'draft' | 'active' | 'archived'
  import_method: 'manual' | 'smart_import' | 'batch_import'
  created_at: string
  updated_at: string
}

// 数据库质控规则类型
export interface DatabaseQCRule {
  id: string
  rule_code: string
  name: string
  description: string
  category: 'completeness' | 'consistency' | 'rationality' | 'timeliness' | 'similarity' | 'compliance'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  is_active: boolean
  check_logic: any
  prompt_template?: string
  version: string
  created_at: string
  updated_at: string
}

// 演示数据服务类
export class DemoDataService {
  private static instance: DemoDataService
  private isConnected: boolean = false
  private connectionChecked: boolean = false

  private constructor() {}

  static getInstance(): DemoDataService {
    if (!DemoDataService.instance) {
      DemoDataService.instance = new DemoDataService()
    }
    return DemoDataService.instance
  }

  /**
   * 检查数据库连接状态
   */
  async checkConnection(): Promise<boolean> {
    if (this.connectionChecked) {
      console.log(`[DemoDataService] 使用缓存的连接状态: ${this.isConnected ? '已连接' : '未连接'}`)
      return this.isConnected
    }

    try {
      console.log('[DemoDataService] 正在检查数据库连接...')
      this.isConnected = await checkSupabaseConnection()
      this.connectionChecked = true
      console.log(`[DemoDataService] 数据库连接状态: ${this.isConnected ? '已连接' : '未连接'}`)
      return this.isConnected
    } catch (error) {
      console.error('[DemoDataService] 连接检查失败:', error)
      this.isConnected = false
      this.connectionChecked = true
      return false
    }
  }

  /**
   * 获取测试病历列表
   */
  async getMedicalRecords(params: {
    limit?: number
    search?: string
    department?: string
    status?: string
  } = {}): Promise<MedicalRecord[]> {
    console.log('[DemoDataService] 开始获取医疗记录，参数:', params)
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      console.warn('[DemoDataService] 数据库未连接，返回模拟数据')
      return this.getMockMedicalRecords()
    }

    try {
      console.log('[DemoDataService] 正在从数据库查询医疗记录...')
      let query = supabase
        .from(TABLES.MEDICAL_RECORDS_TEST)
        .select('*')
        .eq('status', 'active')

      // 应用筛选条件
      if (params.search) {
        query = query.or(`record_name.ilike.%${params.search}%,primary_diagnosis.ilike.%${params.search}%`)
      }
      if (params.department) {
        query = query.eq('department', params.department)
      }
      if (params.status) {
        query = query.eq('status', params.status)
      }

      // 排序和限制
      query = query.order('created_at', { ascending: false })
      if (params.limit) {
        query = query.limit(params.limit)
      }

      const { data, error } = await query
      console.log('[DemoDataService] 数据库查询结果:', { data: data?.length, error })

      if (error) {
        console.error('[DemoDataService] 获取医疗记录失败:', error)
        return this.getMockMedicalRecords()
      }

      // 转换数据格式
      const transformedData = this.transformDatabaseRecords(data || [])
      console.log('[DemoDataService] 转换后的医疗记录数量:', transformedData.length)
      return transformedData
    } catch (error) {
      console.error('[DemoDataService] 获取医疗记录异常:', error)
      return this.getMockMedicalRecords()
    }
  }

  /**
   * 根据ID获取单个医疗记录
   */
  async getMedicalRecordById(id: string): Promise<MedicalRecord | null> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      console.warn('[DemoDataService] 数据库未连接，返回模拟数据')
      const mockRecords = this.getMockMedicalRecords()
      return mockRecords.find(record => record.id === id) || null
    }

    try {
      const { data, error } = await supabase
        .from(TABLES.MEDICAL_RECORDS_TEST)
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        console.error('[DemoDataService] 获取医疗记录失败:', error)
        return null
      }

      const transformed = this.transformDatabaseRecords([data])
      return transformed[0] || null
    } catch (error) {
      console.error('[DemoDataService] 获取医疗记录异常:', error)
      return null
    }
  }

  /**
   * 获取质控规则列表
   */
  async getQCRules(params: {
    limit?: number
    category?: string
    severity?: string
    isActive?: boolean
  } = {}): Promise<QualityControlRule[]> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      console.warn('[DemoDataService] 数据库未连接，返回模拟数据')
      return this.getMockQCRules()
    }

    try {
      let query = supabase
        .from(TABLES.QC_RULES)
        .select('*')

      // 应用筛选条件
      if (params.category) {
        query = query.eq('category', params.category)
      }
      if (params.severity) {
        query = query.eq('severity', params.severity)
      }
      if (params.isActive !== undefined) {
        query = query.eq('is_active', params.isActive)
      }

      // 排序和限制
      query = query.order('rule_code', { ascending: true })
      if (params.limit) {
        query = query.limit(params.limit)
      }

      const { data, error } = await query

      if (error) {
        console.error('[DemoDataService] 获取质控规则失败:', error)
        return this.getMockQCRules()
      }

      // 转换数据格式
      return this.transformDatabaseRules(data || [])
    } catch (error) {
      console.error('[DemoDataService] 获取质控规则异常:', error)
      return this.getMockQCRules()
    }
  }

  /**
   * 获取可用的科室列表
   */
  async getDepartments(): Promise<string[]> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      return ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
    }

    try {
      const { data, error } = await supabase
        .from(TABLES.MEDICAL_RECORDS_TEST)
        .select('department')
        .not('department', 'is', null)

      if (error) {
        console.error('[DemoDataService] 获取科室列表失败:', error)
        return ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
      }

      // 去重并排序
      const departments = [...new Set(data.map(item => item.department).filter(Boolean))]
      return departments.sort()
    } catch (error) {
      console.error('[DemoDataService] 获取科室列表异常:', error)
      return ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
    }
  }
  /**
   * 获取指定病历的文书列表
   */
  async getDocumentsForRecord(recordId: string): Promise<Array<{ id: string; title: string; type: string; created_at?: string }>> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      return this.getMockDocuments(recordId)
    }
    try {
      const { data, error } = await supabase
        .from(TABLES.MEDICAL_RECORDS_TEST)
        .select('id, updated_at, documents')
        .eq('id', recordId)
        .single()
      if (error) {
        console.warn('[DemoDataService] 获取文书失败，使用模拟数据:', error)
        return this.getMockDocuments(recordId)
      }
      const docs = (data as any)?.documents
      if (Array.isArray(docs) && docs.length > 0) {
        return docs.map((d: any, i: number) => ({
          id: d.id || `${recordId}-doc-${i + 1}`,
          title: d.title || d.type || '未命名文书',
          type: d.type || 'unknown',
          created_at: d.created_at || data.updated_at
        }))
      }
      // 数据库无文书字段，回退
      return this.getMockDocuments(recordId)
    } catch (e) {
      console.error('[DemoDataService] 获取文书异常，使用模拟数据:', e)
      return this.getMockDocuments(recordId)
    }
  }



  /**
   * 转换数据库医疗记录格式
   */
  private transformDatabaseRecords(records: DatabaseMedicalRecord[]): MedicalRecord[] {
    return records.map(record => ({
      id: record.id,
      patient_name: record.patient_info?.name || '未知患者',
      patient_age: record.patient_info?.age || 0,
      patient_gender: (record.patient_info?.gender === '男' ? 'M' :
                      record.patient_info?.gender === '女' ? 'F' : 'U') as 'M' | 'F' | 'U',
      department: record.department || '未知科室',
      admission_date: record.created_at,
      record_type: 'inpatient' as const,
      content: record.raw_text || this.generateContentFromRecord(record),
      status: record.status === 'active' ? 'completed' as const : 'pending' as const,
      created_at: record.created_at,
      updated_at: record.updated_at,
      qc_score: record.ai_confidence_score,
      qc_grade: this.calculateGrade(record.ai_confidence_score)
    }))
  }

  /**
   * 转换数据库质控规则格式
   */
  private transformDatabaseRules(rules: DatabaseQCRule[]): QualityControlRule[] {
    return rules.map(rule => ({
      id: rule.id,
      pointId: rule.id, // 使用相同ID
      conditions: [], // 简化处理
      logicOperator: 'AND' as const,
      createTime: rule.created_at,
      updateTime: rule.updated_at,
      // 扩展属性
      name: rule.name,
      description: rule.description,
      category: rule.category,
      ruleType: rule.rule_type,
      severity: rule.severity,
      maxScore: rule.max_score,
      weight: rule.weight,
      isActive: rule.is_active,
      checkLogic: rule.check_logic,
      promptTemplate: rule.prompt_template,
      version: rule.version,
      ruleCode: rule.rule_code
    }))
  }

  /**
   * 从记录生成内容文本
   */
  private generateContentFromRecord(record: DatabaseMedicalRecord): string {
    const patientInfo = record.patient_info || {}
    return `
患者姓名：${patientInfo.name || '未知'}
年龄：${patientInfo.age || '未知'}岁
性别：${patientInfo.gender || '未知'}
科室：${record.department || '未知'}
主诊断：${record.primary_diagnosis || '未知'}
主要手术：${record.major_surgery || '无'}

${record.raw_text || '病历内容暂无'}
    `.trim()
  }

  /**
   * 计算质控等级
   */
  private calculateGrade(score: number): 'A' | 'B' | 'C' {
    if (score >= 90) return 'A'
    if (score >= 80) return 'B'
    return 'C'
  }

  /**
   * 获取模拟医疗记录数据（当数据库不可用时使用）
   */
  private getMockMedicalRecords(): MedicalRecord[] {
    return [
      {
        id: 'mock-record-001',
        patient_name: '张三',
        patient_age: 65,
        patient_gender: 'M',
        department: '心内科',
        admission_date: '2024-01-15T08:30:00Z',
        record_type: 'inpatient',
        content: `
患者姓名：张三
年龄：65岁
性别：男
科室：心内科
主诉：胸痛3小时
现病史：患者3小时前无明显诱因出现胸痛，呈压榨性，伴出汗，无发热，无咳嗽咳痰。
既往史：既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。
主诊断：急性心肌梗死
治疗：给予阿司匹林、氯吡格雷抗血小板，阿托伐他汀调脂，美托洛尔控制心率。
        `.trim(),
        status: 'completed',
        created_at: '2024-01-15T08:30:00Z',
        updated_at: '2024-01-15T10:30:00Z',
        qc_score: 92,
        qc_grade: 'A'
      },
      {
        id: 'mock-record-002',
        patient_name: '李四',
        patient_age: 45,
        patient_gender: 'F',
        department: '呼吸内科',
        admission_date: '2024-01-16T09:15:00Z',
        record_type: 'inpatient',
        content: `
患者姓名：李四
年龄：45岁
性别：女
科室：呼吸内科
主诉：发热、咳嗽2天
现病史：患者2天前开始发热，体温最高38.5℃，伴咳嗽，咳少量白痰，无胸痛。
既往史：既往体健，无特殊病史。

   * 获取模拟文书列表










主诊断：肺炎
治疗：给予头孢曲松抗感染，对症支持治疗。
        `.trim(),
        status: 'completed',
        created_at: '2024-01-16T09:15:00Z',
        updated_at: '2024-01-16T11:15:00Z',
        qc_score: 88,
        qc_grade: 'B'
      },
      {
        id: 'mock-record-003',
        patient_name: '王五',
        patient_age: 32,
        patient_gender: 'M',
        department: '消化内科',
        admission_date: '2024-01-17T14:20:00Z',
        record_type: 'inpatient',
        content: `
患者姓名：王五
年龄：32岁
性别：男
科室：消化内科
主诉：腹痛、腹泻1天
现病史：患者1天前进食不洁食物后出现腹痛、腹泻，大便呈水样，无发热。
既往史：既往体健，无特殊病史。
主诊断：急性胃肠炎
治疗：给予补液、止泻、调节肠道菌群治疗。
        `.trim(),
        status: 'completed',
        created_at: '2024-01-17T14:20:00Z',
        updated_at: '2024-01-17T16:20:00Z',
        qc_score: 85,
        qc_grade: 'B'
      }
    ]
  }


  /** 获取模拟文书列表（当数据库不可用时使用） */
  private getMockDocuments(recordId: string) {
    const now = new Date().toISOString()
    return [
      { id: `${recordId}-doc-1`, title: '入院记录', type: 'admission', created_at: now },
      { id: `${recordId}-doc-2`, title: '首次病程', type: 'first_course', created_at: now },
      { id: `${recordId}-doc-3`, title: '出院记录', type: 'discharge', created_at: now },
      { id: `${recordId}-doc-4`, title: '手术记录', type: 'surgery', created_at: now }
    ]
  }

/**
   * 获取模拟质控规则数据（当数据库不可用时使用）
   */
  private getMockQCRules(): QualityControlRule[] {
    return [
      {
        id: 'mock-rule-001',
        pointId: 'mock-rule-001',
        conditions: [],
        logicOperator: 'AND',
        createTime: '2024-01-01T00:00:00Z',
        updateTime: '2024-01-01T00:00:00Z',
        name: '主诉完整性检查',
        description: '检查病历中主诉部分是否完整记录，主诉应简明扼要地描述患者的主要症状',
        category: 'completeness',
        ruleType: 'objective',
        severity: 'major',
        maxScore: 10,
        weight: 1.0,
        isActive: true,
        checkLogic: {
          type: 'content_check',
          required_sections: ['主诉'],
          min_length: 5
        },
        promptTemplate: '请检查以下病历的主诉部分是否完整：\n\n{content}\n\n评估标准：\n1. 主诉是否存在\n2. 主诉是否简明扼要\n3. 主诉是否描述了主要症状',
        version: '1.0',
        ruleCode: 'COMP-001'
      },
      {
        id: 'mock-rule-002',
        pointId: 'mock-rule-002',
        conditions: [],
        logicOperator: 'AND',
        createTime: '2024-01-01T00:00:00Z',
        updateTime: '2024-01-01T00:00:00Z',
        name: '现病史逻辑性检查',
        description: '检查现病史的描述是否逻辑清晰，时间顺序是否合理',
        category: 'consistency',
        ruleType: 'subjective',
        severity: 'major',
        maxScore: 15,
        weight: 1.2,
        isActive: true,
        checkLogic: {
          type: 'llm_analysis',
          criteria: ['时间逻辑', '症状关联', '病程发展']
        },
        promptTemplate: '请分析以下现病史的逻辑性：\n\n{content}\n\n评估要点：\n1. 时间顺序是否合理\n2. 症状发展是否符合逻辑\n3. 病程描述是否完整',
        version: '1.0',
        ruleCode: 'CONS-001'
      },
      {
        id: 'mock-rule-003',
        pointId: 'mock-rule-003',
        conditions: [],
        logicOperator: 'AND',
        createTime: '2024-01-01T00:00:00Z',
        updateTime: '2024-01-01T00:00:00Z',
        name: '诊断合理性检查',
        description: '检查诊断是否与症状、检查结果相符',
        category: 'rationality',
        ruleType: 'hybrid',
        severity: 'critical',
        maxScore: 20,
        weight: 1.5,
        isActive: true,
        checkLogic: {
          type: 'hybrid',
          patterns: ['诊断', '症状', '检查'],
          criteria: ['症状匹配', '检查支持', '诊断准确']
        },
        promptTemplate: '请评估诊断的合理性：\n\n{content}\n\n评估标准：\n1. 诊断是否与症状相符\n2. 是否有检查结果支持\n3. 诊断是否准确完整',
        version: '1.0',
        ruleCode: 'RATI-001'
      }
    ]
  }
}
