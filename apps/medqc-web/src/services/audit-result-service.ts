// 审核结果管理服务
// 支持多级审核、批量操作和LLM辅助缺陷识别

import type {
  QCAuditResult,
  QCDefect,
  QCAuditTaskItem,
  AuditLevel,
  DefectSeverity,
  BatchAuditRequest,
  BatchAuditResult,
  AIDefectSuggestion,
  DefectAnalysisContext
} from '@/types/audit-module'

import { supabase } from '@/lib/supabase'
import { integratedQCEngine } from './integrated-qc-engine'
import { notificationService } from './notification-service'
import { intelligentQCCache } from './intelligent-cache'

// AI辅助缺陷识别服务
class AIDefectAssistantService {
  constructor(private qcEngine: typeof integratedQCEngine) {}

  async suggestDefects(
    taskItem: QCAuditTaskItem,
    context: DefectAnalysisContext
  ): Promise<AIDefectSuggestion[]> {
    
    console.log(`AI辅助缺陷识别: 患者 ${taskItem.patient_name}`)

    try { // 使用现有的LLM引擎进行缺陷分析
      const analysisResult = await this.qcEngine.executeQualityControl({
        patientId: taskItem.patient_id,
        documents: context.medical_record ? [context.medical_record] :  [],
        departmentId: taskItem.department_id
      }, taskItem.department_id, {
        category: 'defect_detection',
        implementation_type: 'semantic_llm'
      })

      // 转换为缺陷建议
      return this.convertToDefectSuggestions(analysisResult, context)

    } catch (error) {
      console.error('AI缺陷识别失败:', error)
      return []
    }
  }

  private convertToDefectSuggestions(
    analysisResult: unknown,
    context: DefectAnalysisContext
  ): AIDefectSuggestion[] {
    
    const suggestions: AIDefectSuggestion[] = []

    if (analysisResult.ruleResults) {
      for (const ruleResult of analysisResult.ruleResults) {
        if (ruleResult.findings && ruleResult.findings.length > 0) {
          for (const finding of ruleResult.findings) {
            suggestions.push({
              suggested_type: this.mapFindingToDefectType(finding.type),
              suggested_category: this.mapRuleCategoryToDefectCategory(ruleResult.ruleCode),
              suggested_severity: this.mapSeverityToDefectSeverity(finding.severity),
              suggested_title: finding.description,
              suggested_description: this.enhanceDefectDescription(finding, ruleResult),
              suggested_location: finding.location || '未指定位置',
              confidence: ruleResult.confidence || 70,
              supporting_evidence: [finding.evidence || ''],
              rectification_suggestions: [finding.recommendation || '请根据质控标准进行整改']
            })
          }
        }
      }
    }

    return suggestions
  }

  private mapFindingToDefectType(findingType: string): string {
    const typeMap: Record<string, string> = {
      'missing_section': '缺失章节',
      'missing_content': '内容缺失',
      'format_error': '格式错误',
      'logical_inconsistency': '逻辑不一致',
      'duplication': '内容重复',
      'timeliness_issue': '时效性问题'
    }
    return typeMap[findingType] || '其他问题'
  }

  private mapRuleCategoryToDefectCategory(ruleCode: string): string {
    if (ruleCode.includes('COMP')) return '完整性'
    if (ruleCode.includes('DUP')) return '重复性'
    if (ruleCode.includes('CONS')) return '一致性'
    if (ruleCode.includes('TIME')) return '时效性'
    return '质量问题'
  }

  private mapSeverityToDefectSeverity(severity: string): DefectSeverity {
    const severityMap: Record<string, DefectSeverity> = {
      'critical': 'critical',
      'major': 'major',
      'minor': 'minor'
    }
    return severityMap[severity] || 'minor'
  }

  private enhanceDefectDescription(finding: unknown,  ruleResult: unknown): string {
    let description = finding.description || ''
    
    if (finding.evidence) {
      description += `\n\n支持证据：${finding.evidence}`
    }
    
    if (ruleResult.medicalReasoning) {
      description += `\n\n医学推理：${ruleResult.medicalReasoning}`
    }
    
    return description
  }
}

// 权限控制服务
class AuditPermissionService {
  async checkModificationPermission(
    userId: string,
    targetLevel: AuditLevel,
    currentLevel: AuditLevel
  ): Promise<{ allowed: boolean; reason?: string }> {
    
    // 获取用户角色
    const { data: userProfile, error } = await supabase
      .from('user_profiles')
      .select('roles')
      .eq('user_id', userId)
      .single()

    if (error) {
      return { allowed: false, reason: '无法验证用户权限' }
    }

    const roles = userProfile.roles || []
    
    // 权限矩阵
    const permissionMatrix = {
      'qc_reviewer_expert': ['department', 'hospital'], // 专家可以修改院级和科室级
      'qc_reviewer_hospital': ['department'], // 院级可以修改科室级
      'qc_reviewer_dept': [] // 科室级不能修改其他级别
    }

    for (const role of roles) {
      const allowedLevels = permissionMatrix[role] || []
      if (allowedLevels.includes(targetLevel)) {
        return { allowed: true }
      }
    }

    return { 
      allowed: false, 
      reason: `当前用户权限不足，无法修改${targetLevel}级别的审核结果` 
    }
  }
}

// 主要的审核结果服务
export class AuditResultService {
  private aiAssistant: AIDefectAssistantService
  private permissionService: AuditPermissionService

  constructor() {
    this.aiAssistant = new AIDefectAssistantService(integratedQCEngine)
    this.permissionService = new AuditPermissionService()
  }

  async createAuditResult(
    taskItemId: string,
    auditLevel: AuditLevel,
    reviewerId: string,
    resultData: {
      audit_score: number
      audit_conclusion?: string
      defects: Partial<QCDefect>[]
      review_duration?: number
    }
  ): Promise<QCAuditResult> {
    
    console.log(`创建审核结果: ${taskItemId} - ${auditLevel}`)

    try {
      // 1. 获取审核员信息
      const { data: reviewer } = await supabase
        .from('user_profiles')
        .select('full_name')
        .eq('user_id', reviewerId)
        .single()

      // 2. 创建审核结果记录
      const { data: auditResult, error: resultError } = await supabase
        .from('qc_audit_results')
        .insert({
          task_item_id: taskItemId,
          audit_level: auditLevel,
          reviewer_id: reviewerId,
          reviewer_name: reviewer?.full_name || '',
          audit_score: resultData.audit_score,
          audit_conclusion: resultData.audit_conclusion,
          review_duration: resultData.review_duration,
          status: 'draft'
        })
        .select()
        .single()

      if (resultError) {
        throw new Error(`创建审核结果失败: ${resultError.message}`)
      }

      // 3. 创建缺陷记录
      if (resultData.defects.length > 0) {
        await this.createDefects(auditResult.id, taskItemId, resultData.defects)
      }

      // 4. 更新任务项状态
      await this.updateTaskItemStatus(taskItemId, 'in_review')

      return auditResult

    } catch (error) {
      console.error('创建审核结果失败:', error)
      throw error
    }
  }

  async submitAuditResult(auditResultId: string): Promise<void> {
    console.log(`提交审核结果: ${auditResultId}`)

    try {
      // 1. 更新审核结果状态
      const { data: auditResult, error } = await supabase
        .from('qc_audit_results')
        .update({
          status: 'submitted',
          submitted_at: new Date().toISOString(),
          is_final: true
        })
        .eq('id', auditResultId)
        .select(`
          *,
          qc_audit_task_items(
            patient_id,
            patient_name,
            medical_record_id,
            qc_audit_tasks(task_name)
          )
        `)
        .single()

      if (error) {
        throw new Error(`提交审核结果失败: ${error.message}`)
      }

      // 2. 更新任务项状态
      await this.updateTaskItemStatus(auditResult.task_item_id, 'completed')

      // 3. 发送通知
      await this.sendAuditCompletionNotification(auditResult)

    } catch (error) {
      console.error('提交审核结果失败:', error)
      throw error
    }
  }

  async batchAudit(request: BatchAuditRequest): Promise<BatchAuditResult> {
    console.log(`批量审核: ${request.task_item_ids.length} 个项目`)

    const result: BatchAuditResult = { total_processed: request.task_item_ids.length,
      successful_count: 0,
      failed_count: 0,
      errors:  [],
      processed_items: []
    }

    // 并发处理，但限制并发数
    const concurrencyLimit = 5
    const chunks = this.chunkArray(request.task_item_ids, concurrencyLimit)

    for (const chunk of chunks) {
      const promises = chunk.map(async (taskItemId) => {
        try {
          const processedItem = await this.processSingleBatchItem(
            taskItemId,
            request.audit_template
          )
          
          result.successful_count++
          result.processed_items.push(processedItem)

        } catch (error) {
          result.failed_count++
          result.errors.push({
            task_item_id: taskItemId,
            error_message: error.message
          })
        }
      })

      await Promise.all(promises)
    }

    return result
  }

  private async processSingleBatchItem(
    taskItemId: string,
    template?: Record<string, unknown>
  ): Promise<unknown> {
    
    const startTime = Date.now()

    // 1. 获取任务项信息
    const { data: taskItem } = await supabase
      .from('qc_audit_task_items')
      .select('*')
      .eq('id', taskItemId)
      .single()

    if (!taskItem) {
      throw new Error('任务项不存在')
    }

    // 2. AI辅助缺陷识别
    const aiSuggestions = await this.aiAssistant.suggestDefects(taskItem, {
      medical_record: null, // 需要从实际数据源获取
      audit_level: 'department',
      reviewer_expertise: []
    })

    // 3. 应用审核模板
    const score = template?.default_score || this.calculateDefaultScore(aiSuggestions)
    const defects = this.mergeTemplateDefects(aiSuggestions, (template?.common_defects || []) as unknown[])

    // 4. 创建审核结果
    const auditResult = await this.createAuditResult(
      taskItemId,
      'department',
      'batch_processor', // 批量处理标识
      {
        audit_score: score,
        audit_conclusion: '批量审核完成',
        defects: defects.map(d => ({
          defect_type: d.suggested_type,
          defect_category: d.suggested_category,
          severity: d.suggested_severity,
          title: d.suggested_title,
          description: d.suggested_description,
          score_deduction: this.calculateScoreDeduction(d.suggested_severity),
          ai_assisted: true,
          ai_confidence: d.confidence
        })),
        review_duration: Math.floor((Date.now() - startTime) / 1000 / 60)
      }
    )

    return {
      task_item_id: taskItemId,
      audit_result_id: auditResult.id,
      score,
      defect_count: defects.length,
      has_critical_defects: defects.some(d => d.suggested_severity === 'critical'),
      processing_time: Date.now() - startTime
    }
  }

  async modifyLowerLevelResult(
    auditResultId: string,
    modifierId: string,
    modifications: {
      new_score?: number
      new_conclusion?: string
      reason: string
    }
  ): Promise<void> {
    
    console.log(`修改下级审核结果: ${auditResultId}`)

    try {
      // 1. 获取原始审核结果
      const { data: originalResult } = await supabase
        .from('qc_audit_results')
        .select('*')
        .eq('id', auditResultId)
        .single()

      if (!originalResult) {
        throw new Error('审核结果不存在')
      }

      // 2. 权限检查
      const permission = await this.permissionService.checkModificationPermission(
        modifierId,
        originalResult.audit_level,
        'expert' // 假设修改者是专家级别
      )

      if (!permission.allowed) {
        throw new Error(permission.reason || '权限不足')
      }

      // 3. 更新审核结果
      await supabase
        .from('qc_audit_results')
        .update({
          audit_score: modifications.new_score || originalResult.audit_score,
          audit_conclusion: modifications.new_conclusion || originalResult.audit_conclusion,
          modified_by: modifierId,
          modification_reason: modifications.reason,
          original_score: originalResult.audit_score,
          status: 'modified',
          updated_at: new Date().toISOString()
        })
        .eq('id', auditResultId)

      // 4. 记录修改日志
      await this.logResultModification(auditResultId, modifierId, modifications)

    } catch (error) {
      console.error('修改审核结果失败:', error)
      throw error
    }
  }

  async getAuditResults(
    taskItemId: string,
    includeDefects: boolean = true
  ): Promise<QCAuditResult[]> {
    
    // 尝试从缓存获取
    const cacheKey = `audit_results_${taskItemId}_${includeDefects}`
    const cached = await intelligentQCCache.getCachedResult(cacheKey)
    
    if (cached) {
      return cached
    }

    let query = supabase
      .from('qc_audit_results')
      .select('*')
      .eq('task_item_id', taskItemId)

    if (includeDefects) {
      query = query.select(`
        *,
        qc_defects(*)
      `)
    }

    const { data, error } = await query.order('created_at', { ascending: true })

    if (error) {
      throw new Error(`获取审核结果失败: ${error.message}`)
    }

    // 缓存结果
    await intelligentQCCache.cacheResult(cacheKey, data || [], 300) // 5分钟缓存

    return data || []
  }

  private async createDefects(
    auditResultId: string,
    taskItemId: string,
    defects: Partial<QCDefect>[]
  ): Promise<void> {
    
    const defectRecords = defects.map(defect => ({
      audit_result_id: auditResultId,
      task_item_id: taskItemId,
      defect_type: defect.defect_type || '未分类',
      defect_category: defect.defect_category || '质量问题',
      severity: defect.severity || 'minor',
      title: defect.title || '质控问题',
      description: defect.description || '',
      score_deduction: defect.score_deduction || 0,
      ai_assisted: defect.ai_assisted || false,
      ai_confidence: defect.ai_confidence,
      status: 'identified'
    }))

    const { error } = await supabase
      .from('qc_defects')
      .insert(defectRecords)

    if (error) {
      throw new Error(`创建缺陷记录失败: ${error.message}`)
    }
  }

  private async updateTaskItemStatus(taskItemId: string, status: string): Promise<void> {
    await supabase
      .from('qc_audit_task_items')
      .update({ 
        audit_status: status,
        updated_at: new Date().toISOString()
      })
      .eq('id', taskItemId)
  }

  private async sendAuditCompletionNotification(auditResult: unknown): Promise<void> {
    // 发送给临床医生的通知
    await notificationService.sendNotification(
      auditResult.qc_audit_task_items.patient_id, // 假设患者ID就是医生ID
      'clinician',
      'audit_result',
      {
        patient_id: auditResult.qc_audit_task_items.patient_id,
        medical_record_id: auditResult.qc_audit_task_items.medical_record_id,
        audit_result_id: auditResult.id
      }
    )
  }

  private calculateDefaultScore(suggestions: AIDefectSuggestion[]): number {
    let score = 100
    
    for (const suggestion of suggestions) {
      const deduction = this.calculateScoreDeduction(suggestion.suggested_severity)
      score -= deduction
    }
    
    return Math.max(score, 0)
  }

  private calculateScoreDeduction(severity: DefectSeverity): number {
    const deductionMap: Record<DefectSeverity, number> = {
      'critical': 20,
      'major': 10,
      'minor': 5
    }
    return deductionMap[severity]
  }

  private mergeTemplateDefects(
    aiSuggestions: AIDefectSuggestion[],
    templateDefects: Partial<QCDefect>[]
  ): AIDefectSuggestion[] {
    // 简单合并逻辑，实际应用中可能需要更复杂的去重和合并策略
    return [...aiSuggestions]
  }

  private chunkArray<T>(array: T[], size: number): T[][] {
    const chunks: T[][] = []
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size))
    }
    return chunks
  }

  private async logResultModification(
    auditResultId: string,
    modifierId: string,
    modifications: Record<string, unknown>
  ): Promise<void> {
    // 记录修改日志的逻辑
    console.log('记录审核结果修改:', { auditResultId, modifierId, modifications })
  }
}

// 导出单例实例
export const auditResultService = new AuditResultService()
