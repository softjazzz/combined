// @ts-nocheck
/**
 * LLM质控演示数据服务
 * 负责从Supabase数据库获取真实的测试病历和质控规则数据
 */

import { supabase, TABLES, checkSupabaseConnection } from '@/lib/backend-store'
import { DOCUMENT_TYPE_LABELS } from '@/utils/documentTypeUtils'
import { getDocumentTypeCode, getDocumentBaseCode } from '@/constants/documentTypes'
import type { MedicalRecord } from '@/types/medical-records'
import type { QualityControlRule, RecordDocumentInfo } from '@/types/quality-control'
import { ApiService } from '@/services/apiService'

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
  ai_extraction_result: Record<string, unknown>
  ai_confidence_score: number
  documents: unknown[]
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
  category:
    | 'completeness'
    | 'consistency'
    | 'rationality'
    | 'timeliness'
    | 'similarity'
    | 'compliance'
  rule_type: 'objective' | 'subjective' | 'hybrid'
  severity: 'critical' | 'major' | 'minor'
  max_score: number
  weight: number
  is_active: boolean
  check_logic: Record<string, unknown>
  prompt_template?: string
  version: string
  created_at: string
  updated_at: string
  applicable_documents?: string[] // 适用的文书类型列表
}

interface DepartmentRow {
  department?: string
}

interface RawDocumentRow {
  id?: string
  type?: string
  type_code?: string
  title?: string
  created_at?: string
}

// 演示数据服务类
export class DemoDataService {
  private static instance: DemoDataService
  private isConnected: boolean = false
  private connectionChecked: boolean = false
  private recordsCache: { data: MedicalRecord[]; ts: number } | null = null
  private departmentsCache: { data: string[]; ts: number } | null = null
  private readonly CACHE_TTL_MS = 60000

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
  async checkConnection(
    opts: { timeoutMs?: number; forceRefresh?: boolean } = {},
  ): Promise<boolean> {
    const timeoutMs = opts.timeoutMs ?? 5000 // 增加超时时间到5秒，适应跨国网络延迟
    const forceRefresh = opts.forceRefresh ?? false

    // 如果不强制刷新且已检查过连接，返回缓存结果
    if (!forceRefresh && this.connectionChecked) {
      console.log(`[DemoDataService] 使用缓存的连接状态: ${this.isConnected ? '已连接' : '未连接'}`)
      return this.isConnected
    }

    console.log('[DemoDataService] 开始数据库连接检查...')

    // 重试机制：最多尝试2次
    const maxRetries = 2
    let lastError: unknown = null

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      console.log(`[DemoDataService] 连接尝试 ${attempt}/${maxRetries}...`)

      // 快速返回策略：超过 timeoutMs 立即降级为未连接，同时在后台继续真实检测
      const timeoutPromise = new Promise<boolean>((resolve) => {
        setTimeout(() => {
          console.log(
            `[DemoDataService] 连接检查超时 (${timeoutMs}ms)，尝试 ${attempt}/${maxRetries}`,
          )
          resolve(false)
        }, timeoutMs)
      })

      const probe = checkSupabaseConnection()

      try {
        const result = await Promise.race([probe, timeoutPromise])

        if (result) {
          this.isConnected = true
          this.connectionChecked = true
          console.log(`[DemoDataService] ✅ 数据库连接成功 (尝试 ${attempt}/${maxRetries})`)
          return true
        } else if (attempt < maxRetries) {
          console.log(
            `[DemoDataService] ⚠️ 连接超时，可能是网络延迟导致，等待重试... (尝试 ${attempt}/${maxRetries})`,
          )
          await new Promise((resolve) => setTimeout(resolve, 1000)) // 等待1秒后重试
          continue
        } else {
          console.log('[DemoDataService] ⚠️ 网络连接超时，可能是跨国网络延迟，将使用模拟数据')
          this.isConnected = false
          this.connectionChecked = true
          return false
        }
      } catch (error) {
        lastError = error
        if (attempt < maxRetries) {
          console.log(`[DemoDataService] 连接异常，准备重试: ${error}`)
          await new Promise((resolve) => setTimeout(resolve, 1000))
          continue
        }
      }
    }

    // 如果所有尝试都失败了
    console.error('[DemoDataService] 所有连接尝试失败:', lastError)
    this.isConnected = false
    this.connectionChecked = true
    return false
  }

  /**
   * 重置连接状态，强制重新检查
   */
  resetConnectionState(): void {
    this.connectionChecked = false
    this.isConnected = false
    console.log('[DemoDataService] 连接状态已重置')
  }

  /**
   * 获取测试病历列表
   */
  async getMedicalRecords(
    params: {
      limit?: number
      search?: string
      department?: string
      status?: string
    } = {},
  ): Promise<MedicalRecord[]> {
    console.log('[DemoDataService] 开始获取医疗记录，参数:', params)
    // 先用缓存提升首次打开速度
    const now = Date.now()
    if (this.recordsCache && now - this.recordsCache.ts < this.CACHE_TTL_MS) {
      // 后台刷新但不阻塞 UI
      this.refreshMedicalRecords(params).catch(() => {})
      return this.recordsCache.data
    }
    // 无缓存则刷新
    return this.refreshMedicalRecords(params)
  }

  private async refreshMedicalRecords(
    params: {
      limit?: number
      search?: string
      department?: string
      status?: string
    } = {},
  ): Promise<MedicalRecord[]> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      const mock = this.getMockMedicalRecords()
      this.recordsCache = { data: mock, ts: Date.now() }
      return mock
    }
    try {
      let query = supabase.from(TABLES.MEDICAL_RECORDS_TEST).select('*').eq('status', 'active')

      if (params.search) {
        query = query.or(
          `record_name.ilike.%${params.search}%,primary_diagnosis.ilike.%${params.search}%`,
        )
      }
      if (params.department) query = query.eq('department', params.department)
      if (params.status) query = query.eq('status', params.status)

      query = query.order('created_at', { ascending: false })
      if (params.limit) query = query.limit(params.limit)

      const { data, error } = await query
      if (error || !data) {
        const mock = this.getMockMedicalRecords()
        this.recordsCache = { data: mock, ts: Date.now() }
        return mock
      }
      const transformed = this.transformDatabaseRecords(data)
      this.recordsCache = { data: transformed, ts: Date.now() }
      return transformed
    } catch (e) {
      const mock = this.getMockMedicalRecords()
      this.recordsCache = { data: mock, ts: Date.now() }
      return mock
    }
  }

  /**
   * 根据ID获取单个医疗记录
   */
  async getMedicalRecordById(id: string): Promise<MedicalRecord | null> {
    const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    const isUuid = uuidRe.test(id)
    const isConnected = await this.checkConnection()
    // 若ID不是UUID（如 mock-record-001），直接走本地数据，避免无效的远端查询
    if (!isUuid || !isConnected) {
      if (!isConnected) console.warn('[DemoDataService] 数据库未连接，返回模拟数据')
      const mockRecords = this.getMockMedicalRecords()
      return mockRecords.find((record) => record.id === id) || null
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
  async getQCRules(
    params: {
      limit?: number
      category?: string
      severity?: string
      isActive?: boolean
    } = {},
  ): Promise<QualityControlRule[]> {
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      console.warn('[DemoDataService] 数据库未连接，返回模拟数据')
      return this.getMockQCRules()
    }

    try {
      let query = supabase.from(TABLES.QC_RULES).select('*')

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
   * 获取四川省质控规则列表
   * @param params 查询参数
   * @returns 四川省质控规则列表
   */
  async getSichuanQCRules(
    params: {
      document_type?: string
      document_types?: string
      grouped?: boolean
    } = {},
  ): Promise<QualityControlRule[]> {
    console.log('[DemoDataService] 开始获取四川省质控规则，参数:', params)

    try {
      // 构建查询参数
      const queryParams = new URLSearchParams()
      if (params.document_type) {
        queryParams.append('document_type', params.document_type)
      }
      if (params.document_types) {
        queryParams.append('document_types', params.document_types)
      }
      if (params.grouped !== undefined) {
        queryParams.append('grouped', String(params.grouped))
      }

      // 调用四川质控规则API
      const url = `/api/v1/qc/sichuan/rules${queryParams.toString() ? '?' + queryParams.toString() : ''}`
      const response = await fetch(url)

      if (!response.ok) {
        throw new Error(`获取四川规则失败: ${response.status} ${response.statusText}`)
      }

      const data = await response.json()

      // 处理分组返回格式
      if (params.grouped && data.rules_by_document_type) {
        console.log('[DemoDataService] 收到分组格式的四川规则')
        // 展开所有分组规则
        const allRules: any[] = []
        Object.values(data.rules_by_document_type).forEach((rules: any) => {
          if (Array.isArray(rules)) {
            allRules.push(...rules)
          }
        })
        return this.transformSichuanRules(allRules)
      }

      // 处理普通列表格式
      if (data.rules && Array.isArray(data.rules)) {
        console.log(`[DemoDataService] ✅ 成功加载 ${data.rules.length} 条四川省质控规则`)
        return this.transformSichuanRules(data.rules)
      }

      console.warn('[DemoDataService] 四川规则API返回格式异常，使用空数组')
      return []
    } catch (error) {
      console.error('[DemoDataService] 获取四川省质控规则失败:', error)
      // 降级处理：返回空数组，让上层决定是否使用Mock数据
      return []
    }
  }

  /**
   * 转换四川规则格式为演示系统使用的格式
   */
  private transformSichuanRules(rules: any[]): QualityControlRule[] {
    return rules.map((rule) => ({
      id: rule.rule_id || rule.id,
      pointId: rule.rule_id || rule.id,
      conditions: [],
      logicOperator: 'AND' as const,
      createTime: new Date().toISOString(),
      updateTime: new Date().toISOString(),
      // 四川规则核心字段
      name: rule.name || '未命名规则',
      description: rule.description || '',
      category: rule.category || '基础',
      ruleType: this.mapRuleType(rule.complexity),
      severity: this.mapSeverity(rule.defect_level),
      maxScore: rule.score_deduction || 0,
      weight: 1.0,
      isActive: true,
      checkLogic: {},
      promptTemplate: rule.prompt_template || rule.description,
      version: '1.0',
      ruleCode: rule.rule_id || '',
      // 四川规则特有字段
      applicable_documents: rule.applicable_documents || [],
      complexity: rule.complexity,
      defect_level: rule.defect_level,
      requires_rag: rule.requires_rag || false,
      requires_cot: rule.requires_cot || false,
      medical_domain: rule.medical_domain || '通用',
      score_deduction: rule.score_deduction || 0,
    }))
  }

  /**
   * 映射复杂度到规则类型
   */
  private mapRuleType(complexity?: string): 'objective' | 'subjective' | 'hybrid' {
    if (!complexity) return 'hybrid'
    const lower = complexity.toLowerCase()
    if (lower.includes('低') || lower === 'low') return 'objective'
    if (lower.includes('高') || lower === 'high') return 'subjective'
    return 'hybrid'
  }

  /**
   * 映射缺陷级别到严重程度
   */
  private mapSeverity(defectLevel?: string): 'critical' | 'major' | 'minor' {
    if (!defectLevel) return 'major'
    const lower = defectLevel.toLowerCase()
    if (lower.includes('严重') || lower === 'critical') return 'critical'
    if (lower.includes('轻微') || lower === 'minor') return 'minor'
    return 'major'
  }

  /**
   * 获取可用的科室列表
   */
  async getDepartments(): Promise<string[]> {
    const now = Date.now()
    if (this.departmentsCache && now - this.departmentsCache.ts < this.CACHE_TTL_MS) {
      return this.departmentsCache.data
    }
    const isConnected = await this.checkConnection()
    if (!isConnected) {
      const fallback = ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
      this.departmentsCache = { data: fallback, ts: Date.now() }
      return fallback
    }
    try {
      const { data, error } = await supabase
        .from(TABLES.MEDICAL_RECORDS_TEST)
        .select('department')
        .not('department', 'is', null)
      if (error) {
        const fallback = ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
        this.departmentsCache = { data: fallback, ts: Date.now() }
        return fallback
      }
      const departments = [
        ...new Set((data || []).map((item: DepartmentRow) => item.department).filter(Boolean)),
      ].sort()
      this.departmentsCache = { data: departments, ts: Date.now() }
      return departments
    } catch (error) {
      const fallback = ['内科', '外科', '妇产科', '儿科', '急诊科', '骨科', '神经内科', '心内科']
      this.departmentsCache = { data: fallback, ts: Date.now() }
      return fallback
    }
  }
  /**
   * 获取指定病历的文书列表
   */
  async getDocumentsForRecord(recordId: string): Promise<RecordDocumentInfo[]> {
    const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    const isUuid = uuidRe.test(recordId)

    // 非UUID（mock记录）直接返回模拟文书
    if (!isUuid) {
      return this.getMockDocuments(recordId)
    }

    // 优先尝试后端API（FastAPI服务）
    try {
      const apiResult = await (ApiService as any).getMedicalRecordDocuments(recordId)
      if (apiResult.success && Array.isArray(apiResult.data)) {
        console.log(`[DemoDataService] ✅ 使用后端API获取文书: ${apiResult.data.length} 条`)
        // 统一文书结构，补齐/标准化 type 字段，避免出现 "unknown"
        const normalized: RecordDocumentInfo[] = apiResult.data.map((doc, i) => {
          // 1) 优先使用现有 doc.type
          let type = (doc.type || '').toString()
          // 2) 空或 unknown 时，尝试用标题/名称推断
          if (!type || type === 'unknown') {
            type = getDocumentTypeCode(doc.title || '')
          }
          // 3) 仍然无效则使用常见基础类型兜底（按业务默认：病程记录）
          if (!type || type === 'unknown') {
            type = getDocumentBaseCode('progress_note')
          }
          return {
            id: doc.id || `${recordId}-doc-${i + 1}`,
            title: doc.title || '未命名文书',
            type,
            created_at: doc.created_at,
            content: doc.content,
          }
        })
        return normalized
      }
    } catch (apiError) {
      console.warn(
        '[DemoDataService] ⚠️ 后端API获取文书失败，准备回退到Supabase/Mock数据',
        apiError,
      )
    }

    const isConnected = await this.checkConnection()
    // 数据库不可用时使用模拟文书，避免远端报错
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
        return docs.map((d: RawDocumentRow, i: number) => {
          const typeCode = (d.type || d.type_code || '').toString()
          const chineseLabel = (DOCUMENT_TYPE_LABELS as any)[typeCode] || ''
          return {
            id: d.id || `${recordId}-doc-${i + 1}`,
            // 标题优先：已有标题 -> 中文类型名 -> 英文代码 -> 兜底
            title: d.title || chineseLabel || typeCode || '未命名文书',
            type: typeCode || 'unknown',
            created_at: d.created_at || data.updated_at,
          }
        })
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
    return records.map((record) => ({
      id: record.id,
      patient_name: record.patient_info?.name || '未知患者',
      patient_age: record.patient_info?.age || 0,
      patient_gender: (record.patient_info?.gender === '男'
        ? 'M'
        : record.patient_info?.gender === '女'
          ? 'F'
          : 'U') as 'M' | 'F' | 'U',
      department: record.department || '未知科室',
      admission_date: record.created_at,
      record_type: 'inpatient' as const,
      content: record.raw_text || this.generateContentFromRecord(record),
      status: record.status === 'active' ? ('completed' as const) : ('pending' as const),
      created_at: record.created_at,
      updated_at: record.updated_at,
      qc_score: record.ai_confidence_score,
      qc_grade: this.calculateGrade(record.ai_confidence_score),
    }))
  }

  /**
   * 转换数据库质控规则格式
   */
  private transformDatabaseRules(rules: DatabaseQCRule[]): QualityControlRule[] {
    return rules.map((rule) => ({
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
      ruleCode: rule.rule_code,
      // 添加 applicable_documents 字段映射
      applicable_documents: rule.applicable_documents || [],
    }))
  }

  /**
   * 从记录生成内容文本
   */
  private generateContentFromRecord(record: DatabaseMedicalRecord): string {
    const patientInfo: Partial<DatabaseMedicalRecord['patient_info']> = record.patient_info || {}
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
        qc_grade: 'A',
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
        qc_grade: 'B',
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
        qc_grade: 'B',
      },
    ]
  }

  /** 获取模拟文书列表（当数据库不可用时使用） */
  private getMockDocuments(recordId: string): RecordDocumentInfo[] {
    const now = new Date().toISOString()
    return [
      { id: `${recordId}-doc-1`, title: '入院记录', type: 'admission', created_at: now },
      { id: `${recordId}-doc-2`, title: '首次病程', type: 'first_course', created_at: now },
      { id: `${recordId}-doc-3`, title: '出院记录', type: 'discharge', created_at: now },
      { id: `${recordId}-doc-4`, title: '手术记录', type: 'surgery', created_at: now },
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
          min_length: 5,
        },
        promptTemplate:
          '请检查以下病历的主诉部分是否完整：\n\n{content}\n\n评估标准：\n1. 主诉是否存在\n2. 主诉是否简明扼要\n3. 主诉是否描述了主要症状',
        version: '1.0',
        ruleCode: 'COMP-001',
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
          criteria: ['时间逻辑', '症状关联', '病程发展'],
        },
        promptTemplate:
          '请分析以下现病史的逻辑性：\n\n{content}\n\n评估要点：\n1. 时间顺序是否合理\n2. 症状发展是否符合逻辑\n3. 病程描述是否完整',
        version: '1.0',
        ruleCode: 'CONS-001',
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
          criteria: ['症状匹配', '检查支持', '诊断准确'],
        },
        promptTemplate:
          '请评估诊断的合理性：\n\n{content}\n\n评估标准：\n1. 诊断是否与症状相符\n2. 是否有检查结果支持\n3. 诊断是否准确完整',
        version: '1.0',
        ruleCode: 'RATI-001',
      },
    ]
  }
}
