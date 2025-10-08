// 审核任务管理服务
// 基于LLM集成质控系统的审核任务管理功能

import type {
  QCAuditTask,
  QCAuditTaskItem,
  CreateAuditTaskRequest,
  AuditTaskFilter,
  SamplingConfig,
  AuditScope,
  RiskLevel,
  AssignedReviewer
} from '@/types/audit-module'

import { unifiedAPIClient } from './unified-api-client'

// 智能抽样算法服务
class IntelligentSamplingService {
  constructor(private qcEngine: typeof integratedQCEngine) {}

  async executeSampling(
    scope: AuditScope,
    config: SamplingConfig
  ): Promise<QCAuditTaskItem[]> {
    
    console.log('开始执行智能抽样算法...')
    
    // 1. 获取候选病历数据
    const candidateRecords = await this.getCandidateRecords(scope)
    console.log(`获取到 ${candidateRecords.length} 条候选病历`)
    
    // 2. 风险等级评估
    const riskAssessedRecords = await this.assessRiskLevels(candidateRecords)
    
    // 3. 执行抽样算法
    const sampledRecords = await this.applySamplingAlgorithm(riskAssessedRecords, config)
    
    console.log(`抽样完成，选中 ${sampledRecords.length} 条病历`)
    return sampledRecords
  }

  private async getCandidateRecords(scope: AuditScope): Promise<any[]> {
    let query = supabase
      .from('medical_records')
      .select(`
        *,
        patients(id, name, gender, age, admission_date, discharge_date),
        departments(id, name)
      `)

    // 应用科室范围过滤
    if (scope.departments && scope.departments.length > 0) {
      query = query.in('department_id', scope.departments)
    }

    // 应用文书类型过滤
    if (scope.document_types && scope.document_types.length > 0) {
      query = query.in('document_type', scope.document_types)
    }

    // 应用时间范围过滤
    if (scope.date_range) {
      query = query
        .gte('created_at', scope.date_range.start)
        .lte('created_at', scope.date_range.end)
    }

    // 是否包含已出院患者
    if (!scope.include_discharged) {
      query = query.is('discharge_date', null)
    }

    const { data, error } = await query.order('created_at', { ascending: false })

    if (error) {
      throw new Error(`获取候选病历失败: ${error.message}`)
    }

    return data || []
  }

  private async assessRiskLevels(records: unknown[]): Promise<any[]> {
    const assessedRecords = []

    for (const record of records) {
      try {
        // 使用LLM引擎进行风险评估
        const riskAssessment = await this.qcEngine.executeQualityControl({
          patientId: record.patient_id,
          documents: [record],
          departmentId: record.department_id
        }, undefined, { category: 'risk_assessment' })

        const riskLevel = this.calculateRiskLevel(riskAssessment)
        const complexityScore = this.calculateComplexityScore(record, riskAssessment)

        assessedRecords.push({
          ...record,
          risk_level: riskLevel,
          complexity_score: complexityScore,
          risk_assessment: riskAssessment
        })

      } catch (error) {
        console.warn(`风险评估失败 (记录 ${record.id}):`, error)
        // 使用默认风险等级
        assessedRecords.push({
          ...record,
          risk_level: 'B' as RiskLevel,
          complexity_score: 50
        })
      }
    }

    return assessedRecords
  }

  private calculateRiskLevel(assessment: unknown): RiskLevel {
    const overallScore = assessment.overallScore || 0
    const riskLevel = assessment.riskLevel

    if (riskLevel === 'critical' || overallScore < 60) {
      return 'A' // 高风险
    } else if (riskLevel === 'high' || overallScore < 80) {
      return 'B' // 中风险
    } else {
      return 'C' // 低风险
    }
  }

  private calculateComplexityScore(record, assessment): number {
    let score = 0

    // 基于文书数量
    score += Math.min((record.document_count || 1) * 10, 30)

    // 基于住院天数
    const admissionDate = new Date(record.admission_date)
    const dischargeDate = record.discharge_date ? new Date(record.discharge_date) : new Date()
    const stayDays = Math.ceil((dischargeDate.getTime() - admissionDate.getTime()) / (1000 * 60 * 60 * 24))
    score += Math.min(stayDays * 2, 20)

    // 基于质控发现的问题数量
    const issueCount = assessment.ruleResults?.reduce((sum: number, result: unknown) => 
      sum + (result.findings?.length || 0), 0) || 0
    score += Math.min(issueCount * 5, 30)

    // 基于科室复杂度
    const departmentComplexity = this.getDepartmentComplexity(record.department_name)
    score += departmentComplexity

    return Math.min(score, 100)
  }

  private getDepartmentComplexity(departmentName: string): number {
    const complexityMap: Record<string, number> = {
      'ICU': 20,
      '急诊科': 18,
      '心外科': 16,
      '神经外科': 16,
      '肿瘤科': 14,
      '内科': 10,
      '外科': 12,
      '妇产科': 10,
      '儿科': 12
    }

    return complexityMap[departmentName] || 8
  }

  private async applySamplingAlgorithm(
    records[],
    config: SamplingConfig
  ): Promise<QCAuditTaskItem[]> {
    
    switch (config.sampling_method) {
      case 'stratified':
        return this.stratifiedSampling(records, config)
      case 'risk_based':
        return this.riskBasedSampling(records, config)
      case 'systematic':
        return this.systematicSampling(records, config)
      default: return this.randomSampling(records, config)
    }
  }

  private async stratifiedSampling(
    records[],
    config: SamplingConfig
  ): Promise<QCAuditTaskItem[]> {
    
    const sampledRecords: QCAuditTaskItem[] = []
    
    // 按风险等级分层
    const strata = {
      A: records.filter(r => r.risk_level === 'A'),
      B: records.filter(r => r.risk_level === 'B'),
      C: records.filter(r => r.risk_level === 'C')
    }

    // 应用分层抽样规则
    for (const rule of config.stratification_rules || : unknown[]) {
      const stratumRecords = strata[rule.stratum_name as keyof typeof strata] || []
      const sampleSize = Math.min(
        Math.max(
          Math.ceil(stratumRecords.length * rule.sample_ratio),
          rule.min_sample_size || 1
        ),
        rule.max_sample_size || stratumRecords.length
      )

      const stratumSample = this.randomSelectFromArray(stratumRecords, sampleSize)
      sampledRecords.push(...stratumSample.map(record => this.convertToTaskItem(record)))
    }

    return sampledRecords
  }

  private async riskBasedSampling(
    records: unknown[],
    config: SamplingConfig
  ): Promise<QCAuditTaskItem[]> {
    
    const weights = config.risk_based_weights || {
      risk_A_weight: 0.6,
      risk_B_weight: 0.3,
      risk_C_weight: 0.1
    }

    const totalSampleSize = config.total_sample_size || 
                           Math.ceil(records.length * (config.sampling_ratio || 0.1))

    const sampleSizes = {
      A: Math.ceil(totalSampleSize * weights.risk_A_weight),
      B: Math.ceil(totalSampleSize * weights.risk_B_weight),
      C: Math.ceil(totalSampleSize * weights.risk_C_weight)
    }

    const sampledRecords: QCAuditTaskItem[] = []

    // 按风险等级抽样
    for (const [riskLevel, sampleSize] of Object.entries(sampleSizes)) {
      const riskRecords = records.filter(r => r.risk_level === riskLevel)
      const sample = this.randomSelectFromArray(riskRecords, Math.min(sampleSize, riskRecords.length))
      sampledRecords.push(...sample.map(record => this.convertToTaskItem(record)))
    }

    return sampledRecords
  }

  private randomSampling(records: unknown[], config: SamplingConfig): QCAuditTaskItem[] {
    const sampleSize = config.total_sample_size || 
                      Math.ceil(records.length * (config.sampling_ratio || 0.1))
    
    const sample = this.randomSelectFromArray(records, Math.min(sampleSize, records.length))
    return sample.map(record => this.convertToTaskItem(record))
  }

  private systematicSampling(records[], config: SamplingConfig): QCAuditTaskItem[] {
    const sampleSize = config.total_sample_size || 
                      Math.ceil(records.length * (config.sampling_ratio || 0.1))
    
    if (sampleSize >= records.length) {
      return records.map(record => this.convertToTaskItem(record))
    }

    const interval = Math.floor(records.length / sampleSize)
    const startIndex = Math.floor(Math.random() * interval)
    const sampledRecords: QCAuditTaskItem[] = []

    for (let i = startIndex; i < records.length && sampledRecords.length < sampleSize; i += interval) {
      sampledRecords.push(this.convertToTaskItem(records[i]))
    }

    return sampledRecords
  }

  private randomSelectFromArray<T>(array: T[], count: number): T[] {
    const shuffled = [...array].sort(() => 0.5 - Math.random())
    return shuffled.slice(0, count)
  }

  private convertToTaskItem(record): QCAuditTaskItem {
    return {
      id: '', // 将在创建时生成
      task_id: '', // 将在创建时设置
      patient_id: record.patient_id,
      medical_record_id: record.id,
      patient_name: record.patients?.name || '',
      admission_date: record.patients?.admission_date || '',
      discharge_date: record.patients?.discharge_date,
      department_id: record.department_id,
      department_name: record.departments?.name || '',
      risk_level: record.risk_level,
      complexity_score: record.complexity_score,
      audit_status: 'pending',
      defect_count: 0,
      has_critical_defects: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
  }
}

// 主要的审核任务服务
export class AuditTaskService {
  private samplingService: IntelligentSamplingService

  constructor() {
    this.samplingService = new IntelligentSamplingService(integratedQCEngine)
  }

  async createAuditTask(request: CreateAuditTaskRequest): Promise<QCAuditTask> {
    console.log('创建审核任务:', request.task_name)

    try {
      // 1. 创建任务记录
      const task = await this.createTaskRecord(request)
      
      // 2. 执行智能抽样
      const taskItems = await this.samplingService.executeSampling(
        request.audit_scope,
        request.sampling_config
      )
      
      // 3. 创建任务明细
      await this.createTaskItems(task.id, taskItems)
      
      // 4. 分配审核员
      await this.assignReviewers(task.id, request.assigned_reviewers)
      
      // 5. 更新任务统计
      await this.updateTaskStatistics(task.id)
      
      console.log(`审核任务创建完成: ${task.task_code}`)
      return task

    } catch (error) {
      console.error('创建审核任务失败:', error)
      throw error
    }
  }

  private async createTaskRecord(request: CreateAuditTaskRequest): Promise<QCAuditTask> {
    const taskCode = this.generateTaskCode(request.task_type, request.audit_level)
    
    const { data, error } = await supabase
      .from('qc_audit_tasks')
      .insert({
        task_code: taskCode,
        task_name: request.task_name,
        task_type: request.task_type,
        audit_level: request.audit_level,
        audit_scope: request.audit_scope,
        sampling_config: request.sampling_config,
        planned_start_date: request.planned_start_date,
        planned_end_date: request.planned_end_date,
        description: request.description,
        priority: request.priority || 5,
        status: 'pending'
      })
      .select()
      .single()

    if (error) {
      throw new Error(`创建任务记录失败: ${error.message}`)
    }

    return data
  }

  private async createTaskItems(taskId: string, items: QCAuditTaskItem: unknown[]): Promise<void> {
    const itemsWithTaskId = items.map(item => ({
      ...item,
      task_id: taskId
    }))

    const { error } = await supabase
      .from('qc_audit_task_items')
      .insert(itemsWithTaskId)

    if (error) {
      throw new Error(`创建任务明细失败: ${error.message}`)
    }
  }

  private async assignReviewers(taskId: string, reviewerIds: string: unknown[]): Promise<void> {
    // 获取任务明细
    const { data: taskItems, error } = await supabase
      .from('qc_audit_task_items')
      .select('id')
      .eq('task_id', taskId)

    if (error) {
      throw new Error(`获取任务明细失败: ${error.message}`)
    }

    // 负载均衡分配
    const assignments = this.distributeTaskItems(taskItems || [], reviewerIds)
    
    // 批量更新分配
    for (const [reviewerId, itemIds] of assignments) {
      await supabase
        .from('qc_audit_task_items')
        .update({
          assigned_reviewer_id: reviewerId,
          assigned_at: new Date().toISOString()
        })
        .in('id', itemIds)
    }
  }

  private distributeTaskItems(items[], reviewerIds: string: unknown[]): Map<string, string[]> {
    const assignments = new Map<string, string[]>()
    
    // 初始化分配映射
    reviewerIds.forEach(id => assignments.set(id, : unknown[]))
    
    // 轮询分配
    items.forEach((item, index: unknown) => {
      const reviewerId = reviewerIds[index % reviewerIds.length]
      assignments.get(reviewerId)!.push(item.id)
    })
    
    return assignments
  }

  private generateTaskCode(taskType: string, auditLevel: string): string {
    const prefix = `${taskType.toUpperCase()}_${auditLevel.toUpperCase()}`
    const timestamp = new Date().toISOString().replace(/[-:]/g, '').substring(0, 15)
    const random = Math.random().toString(36).substring(2, 5).toUpperCase()
    
    return `${prefix}_${timestamp}_${random}`
  }

  async getAuditTasks(filter?: AuditTaskFilter): Promise<QCAuditTask[]> {
    // 尝试从缓存获取
    const cacheKey = `audit_tasks_${JSON.stringify(filter || {})}`
    const cached = await intelligentQCCache.getCachedResult(cacheKey)
    
    if (cached) {
      return cached
    }

    let query = supabase
      .from('qc_audit_tasks')
      .select('*')

    // 应用过滤条件
    if (filter?.task_type) {
      query = query.eq('task_type', filter.task_type)
    }
    
    if (filter?.audit_level) {
      query = query.eq('audit_level', filter.audit_level)
    }
    
    if (filter?.status) {
      query = query.eq('status', filter.status)
    }

    if (filter?.search) {
      query = query.or(`task_name.ilike.%${filter.search}%,task_code.ilike.%${filter.search}%`)
    }

    const { data, error } = await query.order('created_at', { ascending: false })

    if (error) {
      throw new Error(`获取审核任务失败: ${error.message}`)
    }

    // 缓存结果
    await intelligentQCCache.cacheResult(cacheKey, data || [], 300) // 5分钟缓存

    return data || []
  }

  private async updateTaskStatistics(taskId: string): Promise<void> {
    const { data, error } = await supabase.rpc('update_audit_task_statistics', {
      task_id: taskId
    })

    if (error) {
      console.warn('更新任务统计失败:', error)
    }
  }
}

// 导出单例实例
export const auditTaskService = new AuditTaskService()
