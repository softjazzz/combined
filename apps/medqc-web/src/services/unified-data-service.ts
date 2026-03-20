/**
 * 统一数据访问服务
 * 基于Supabase直连的数据访问层，为后期迁移做准备
 * 
 * 架构说明：
 * - 第一阶段：直连Supabase（当前）
 * - 第二阶段：后端API代理（计划中）
 * 
 * 设计原则：
 * 1. 统一接口：为后期迁移提供一致的API
 * 2. 安全优先：实现必要的安全措施
 * 3. 性能考虑：添加缓存和优化机制
 * 4. 错误处理：完善的错误处理和日志
 */

import { supabase } from '@/lib/supabase'
import type { Database } from '@/types/database'
import type { 
  MedicalRecord, 
  CreateMedicalRecordRequest,
  UpdateMedicalRecordRequest,
  QCResult,
  User,
  SearchParams
} from '@/types'

// 数据库表类型
type MedicalRecordRow = Database['public']['Tables']['medical_records']['Row']
type MedicalRecordInsert = Database['public']['Tables']['medical_records']['Insert']
type MedicalRecordUpdate = Database['public']['Tables']['medical_records']['Update']

interface ExtendedSearchParams extends SearchParams {
  status?: string
  department?: string
  page?: number
  pageSize?: number
}

interface CachedMedicalRecords {
  data: MedicalRecord[]
  count: number
}

// 统一响应格式
export interface UnifiedApiResponse<T = any> {
  success: boolean
  data?: T
  error?: {
    message: string
    code?: string
    details?: Record<string, unknown>
  }
  count?: number
  message?: string
}

// 缓存管理
class SimpleCache {
  private cache = new Map<string, { data: unknown; timestamp: number; ttl: number }>()
  
  set(key: string, data: unknown, ttl: number = 5 * 60 * 1000) { // 默认5分钟
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    })
  }
  
  get(key: string): unknown | null {
    const item = this.cache.get(key)
    if (!item) return null
    
    if (Date.now() - item.timestamp > item.ttl) {
      this.cache.delete(key)
      return null
    }
    
    return item.data
  }
  
  clear() {
    this.cache.clear()
  }
}

// 安全工具
class SecurityUtils {
  // 数据脱敏
  static sanitizePatientData(record: unknown, userRole: string): unknown {
    if (typeof record !== 'object' || record === null) return record
    const sanitized = { ...(record as Record<string, unknown>) }
    
    // 非管理员用户脱敏处理
    if (userRole !== 'admin') {
      if (sanitized.patient_name) {
        sanitized.patient_name = this.maskName(sanitized.patient_name)
      }
      if (sanitized.patient_id) {
        sanitized.patient_id = this.maskId(sanitized.patient_id)
      }
    }
    
    return sanitized
  }
  
  private static maskName(name: string): string {
    if (name.length <= 2) return name
    return name.charAt(0) + '*'.repeat(name.length - 2) + name.charAt(name.length - 1)
  }
  
  private static maskId(id: string): string {
    if (id.length <= 6) return '***'
    return id.substring(0, 3) + '***' + id.substring(id.length - 3)
  }
}

// 审计日志
class AuditLogger {
  static async log(operation: string, details: unknown) {
    try {
      const logEntry = {
        operation,
        details: JSON.stringify(details),
        timestamp: new Date().toISOString(),
        user_id: (await supabase.auth.getUser()).data.user?.id,
        ip_address: 'client', // 客户端无法获取真实IP
        user_agent: navigator.userAgent
      }
      
      // 记录到Supabase audit_logs表
      await supabase.from('audit_logs').insert(logEntry)
    } catch (error) {
      console.warn('审计日志记录失败:', error)
    }
  }
}

/**
 * 统一数据访问服务类
 */
export class UnifiedDataService {
  private cache = new SimpleCache()
  
  // ==================== 医疗记录管理 ====================
  
  /**
   * 获取医疗记录列表
   */
  async getMedicalRecords(params?: ExtendedSearchParams): Promise<UnifiedApiResponse<MedicalRecord[]>> {
    try {
      // 缓存键
      const cacheKey = `medical_records_${JSON.stringify(params || {})}`
      const cached = this.cache.get(cacheKey)
      if (cached) {
        const cachedRecords = cached as CachedMedicalRecords
        return { success: true, data: cachedRecords.data, count: cachedRecords.count }
      }
      
      // 构建查询
      let query = supabase
        .from('medical_records')
        .select('*', { count: 'exact' })
        .order('created_at', { ascending: false })
      
      // 应用筛选条件
      if (params?.status) {
        query = query.eq('status', params.status)
      }
      if (params?.department) {
        query = query.eq('department_id', params.department)
      }
      if (params?.keyword) {
        query = query.or(`patient_name.ilike.%${params.keyword}%,content.ilike.%${params.keyword}%`)
      }
      
      // 分页
      if (params?.page && params?.pageSize) {
        const from = (params.page - 1) * params.pageSize
        const to = from + params.pageSize - 1
        query = query.range(from, to)
      }
      
      const { data, error, count } = await query
      
      if (error) {
        await AuditLogger.log('get_medical_records_error', { error: error.message, params })
        return {
          success: false,
          error: {
            message: '获取医疗记录失败',
            code: error.code,
            details: error.details
          }
        }
      }
      
      // 数据脱敏
      const user = await supabase.auth.getUser()
      const userRole = 'doctor' // TODO: 从用户信息中获取实际角色
      const sanitizedData = data?.map(record => 
        SecurityUtils.sanitizePatientData(record, userRole)
      ) || []
      
      // 缓存结果
      this.cache.set(cacheKey, { data: sanitizedData, count })
      
      await AuditLogger.log('get_medical_records', { count: data?.length, params })
      
      return {
        success: true,
        data: sanitizedData,
        count: count || 0
      }
      
    } catch (error) {
      console.error('获取医疗记录失败:', error)
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '未知错误'
        }
      }
    }
  }
  
  /**
   * 根据ID获取医疗记录
   */
  async getMedicalRecordById(id: string): Promise<UnifiedApiResponse<MedicalRecord>> {
    try {
      const { data, error } = await supabase
        .from('medical_records')
        .select('*')
        .eq('id', id)
        .single()
      
      if (error) {
        return {
          success: false,
          error: {
            message: '获取医疗记录失败',
            code: error.code
          }
        }
      }
      
      // 数据脱敏
      const userRole = 'doctor' // TODO: 获取实际用户角色
      const sanitizedData = SecurityUtils.sanitizePatientData(data, userRole)
      
      await AuditLogger.log('get_medical_record_by_id', { record_id: id })
      
      return {
        success: true,
        data: sanitizedData
      }
      
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '未知错误'
        }
      }
    }
  }
  
  /**
   * 创建医疗记录
   */
  async createMedicalRecord(request: CreateMedicalRecordRequest): Promise<UnifiedApiResponse<MedicalRecord>> {
    try {
      // 数据验证
      if (!request.patient_name || !request.content) {
        return {
          success: false,
          error: {
            message: '患者姓名和病历内容不能为空'
          }
        }
      }
      
      // 构建插入数据
      const insertData: MedicalRecordInsert = {
        record_number: `REC-${Date.now()}`,
        patient_name: request.patient_name,
        patient_age: request.patient_age,
        patient_gender: request.patient_gender,
        content: request.content,
        status: 'pending',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      
      const { data, error } = await supabase
        .from('medical_records')
        .insert(insertData)
        .select()
        .single()
      
      if (error) {
        await AuditLogger.log('create_medical_record_error', { error: error.message, request })
        return {
          success: false,
          error: {
            message: '创建医疗记录失败',
            code: error.code
          }
        }
      }
      
      // 清除相关缓存
      this.cache.clear()
      
      await AuditLogger.log('create_medical_record', { record_id: data.id })
      
      return {
        success: true,
        data: data as MedicalRecord,
        message: '医疗记录创建成功'
      }
      
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '未知错误'
        }
      }
    }
  }
  
  /**
   * 更新医疗记录
   */
  async updateMedicalRecord(id: string, request: UpdateMedicalRecordRequest): Promise<UnifiedApiResponse<MedicalRecord>> {
    try {
      const updateData: MedicalRecordUpdate = {
        ...request,
        updated_at: new Date().toISOString()
      }
      
      const { data, error } = await supabase
        .from('medical_records')
        .update(updateData)
        .eq('id', id)
        .select()
        .single()
      
      if (error) {
        return {
          success: false,
          error: {
            message: '更新医疗记录失败',
            code: error.code
          }
        }
      }
      
      // 清除相关缓存
      this.cache.clear()
      
      await AuditLogger.log('update_medical_record', { record_id: id, changes: request })
      
      return {
        success: true,
        data: data as MedicalRecord,
        message: '医疗记录更新成功'
      }
      
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '未知错误'
        }
      }
    }
  }
  
  /**
   * 删除医疗记录
   */
  async deleteMedicalRecord(id: string): Promise<UnifiedApiResponse<void>> {
    try {
      const { error } = await supabase
        .from('medical_records')
        .delete()
        .eq('id', id)
      
      if (error) {
        return {
          success: false,
          error: {
            message: '删除医疗记录失败',
            code: error.code
          }
        }
      }
      
      // 清除相关缓存
      this.cache.clear()
      
      await AuditLogger.log('delete_medical_record', { record_id: id })
      
      return {
        success: true,
        message: '医疗记录删除成功'
      }
      
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '未知错误'
        }
      }
    }
  }
  
  // ==================== 质控分析 ====================
  
  /**
   * 开始质控分析
   */
  async startQCAnalysis(recordId: string): Promise<UnifiedApiResponse<{ analysisId: string }>> {
    try {
      // 获取记录内容
      const recordResponse = await this.getMedicalRecordById(recordId)
      if (!recordResponse.success || !recordResponse.data) {
        return {
          success: false,
          error: { message: '医疗记录不存在' }
        }
      }
      
      // 调用后端分析API
      const response = await fetch('/api/qc/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${(await supabase.auth.getSession()).data.session?.access_token}`
        },
        body: JSON.stringify({
          record_id: recordId,
          content: recordResponse.data.content
        })
      })
      
      const result = await response.json()
      
      if (!result.success) {
        return {
          success: false,
          error: { message: result.error || '分析失败' }
        }
      }
      
      // 保存分析结果到Supabase
      await supabase.from('qc_analysis_results').insert({
        record_id: recordId,
        analysis_result: result.data,
        created_at: new Date().toISOString()
      })
      
      await AuditLogger.log('start_qc_analysis', { record_id: recordId })
      
      return {
        success: true,
        data: { analysisId: `analysis-${recordId}` },
        message: '质控分析已开始'
      }
      
    } catch (error) {
      return {
        success: false,
        error: {
          message: error instanceof Error ? error.message : '分析失败'
        }
      }
    }
  }
}

// 导出单例实例
export const unifiedDataService = new UnifiedDataService()
