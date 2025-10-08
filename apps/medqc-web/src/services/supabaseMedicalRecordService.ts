/**
 * Supabase医疗记录服务
 * 处理医疗记录的CRUD操作和非结构化数据存储
 */

import { supabase } from '@/lib/supabase'
import type { ExtractedMedicalData, ExtractedDocument } from '@/types/medical'


// 测试表数据库类型定义
export interface MedicalRecordTest {
  id: string
  record_number: string
  record_name: string
  patient_info: PatientInfo
  department: string
  primary_diagnosis: string
  secondary_diagnosis: string[]
  major_surgery: string
  raw_text?: string
  ai_extraction_result: AIExtractionResult
  ai_confidence_score: number
  documents: DocumentInRecord[] // 直接存储在JSONB字段中
  status: 'draft' | 'active' | 'archived'
  import_method: 'manual' | 'smart_import' | 'batch_import'
  created_at: string
  updated_at: string
}

// 兼容原有接口
export interface MedicalRecord extends MedicalRecordTest {
  created_by?: string
  last_modified_by?: string
}

export interface PatientInfo {
  name: string
  age?: number
  gender?: string
  id_number?: string
  phone?: string
  address?: string
  emergency_contact?: {
    name: string
    phone: string
    relationship: string
  }
}

// 存储在JSONB中的文书数据结构
export interface DocumentInRecord {
  id: string
  type: string
  title: string
  content: string
  ai_classified: boolean
  ai_confidence: number
  sort_order?: number
}

// 保持原有接口兼容性
export interface MedicalDocument extends DocumentInRecord {
  record_id: string
  document_type: string
  ai_confidence_score: number
  ai_extraction_metadata: Record<string, unknown>
  document_metadata: Record<string, unknown>
  status: 'active' | 'archived'
  created_by: string
  created_at: string
  updated_at: string
}

export interface AIExtractionResult {
  extraction_time: string
  model_used: string
  model_version?: string
  fields_extracted: string[]
  confidence_scores: Record<string, number>
  processing_time_ms: number
  tokens_used?: number
  raw_response?: Record<string, unknown>
}

export interface AIParsingHistory {
  id: string
  record_id: string
  input_text: string
  input_method: 'paste' | 'upload' | 'batch'
  extraction_result: Record<string, unknown>
  confidence_scores: Record<string, number>
  processing_time_ms: number
  tokens_used?: number
  model_name: string
  model_version?: string
  user_corrections?: Record<string, unknown>
  user_rating?: number
  user_feedback?: string
  created_by: string
  created_at: string
}

export interface CreateMedicalRecordRequest {
  record_name: string
  patient_info: PatientInfo
  department: string
  primary_diagnosis: string
  secondary_diagnosis?: string[]
  major_surgery?: string
  raw_text?: string
  ai_extraction_result?: AIExtractionResult
  ai_confidence_score?: number
  import_method?: 'manual' | 'smart_import' | 'batch_import'
  documents?: DocumentInRecord[] // 使用简化的文书结构
}

export interface UpdateMedicalRecordRequest {
  record_name?: string
  patient_info?: Partial<PatientInfo>
  department?: string
  primary_diagnosis?: string
  secondary_diagnosis?: string[]
  major_surgery?: string
  status?: 'draft' | 'active' | 'archived'
  documents?: DocumentInRecord[] // 支持更新文书
}

export interface MedicalRecordSearchParams {
  search?: string
  department?: string
  diagnosis?: string
  creator?: string
  status?: string
  import_method?: string
  date_range?: [string, string]
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface MedicalRecordStats {
  total_records: number
  monthly_new: number
  pending_review: number
  smart_imported: number
  ai_processed: number
  avg_confidence: number
}

/**
 * Supabase医疗记录服务类 - 使用测试表
 */
export class SupabaseMedicalRecordService { private readonly TABLE_NAME = 'medical_records_test'
  private readonly STATS_VIEW = 'medical_records_test_stats'

  /**
   * 创建医疗记录 - 简化版本，直接存储到测试表
   */
  async createMedicalRecord(data: CreateMedicalRecordRequest): Promise<MedicalRecord> {
    // 生成病历编号
    const recordNumber = await this.generateRecordNumber()

    // 准备记录数据 - 文书直接存储在documents字段中
    const recordData = {
      record_number: recordNumber,
      record_name: data.record_name,
      patient_info: data.patient_info,
      department: data.department,
      primary_diagnosis: data.primary_diagnosis,
      secondary_diagnosis: data.secondary_diagnosis || [],
      major_surgery: data.major_surgery || '',
      raw_text: data.raw_text,
      ai_extraction_result: data.ai_extraction_result || {},
      ai_confidence_score: data.ai_confidence_score || 0,
      documents: data.documents || [], // 直接存储文书数组
      import_method: data.import_method || 'manual',
      status: 'active'
    }

    // 插入记录到测试表
    const { data: record, error: recordError } = await supabase
      .from(this.TABLE_NAME)
      .insert(recordData)
      .select()
      .single()

    if (recordError) {
      console.error('创建医疗记录失败:', recordError)
      throw new Error(`创建医疗记录失败: ${recordError.message}`)
    }

    return record as MedicalRecord
  }

  /**
   * 保存AI解析结果 - 简化版本
   */
  async saveAIExtractionResult(
    extractedData: ExtractedMedicalData,
    rawText: string,
    inputMethod: 'paste' | 'upload' | 'batch',
    processingTime: number,
    tokensUsed?: number
  ): Promise<MedicalRecord> {
    // 准备患者信息
    const patientInfo: PatientInfo = {
      name: extractedData.patientName,
      age: extractedData.patientAge,
      gender: extractedData.patientGender
    }

    // 准备AI解析结果
    const aiExtractionResult: AIExtractionResult = {
      extraction_time: new Date().toISOString(),
      model_used: 'medical-llm-v1',
      fields_extracted: Object.keys(extractedData).filter(key => extractedData[key as keyof ExtractedMedicalData]),
      confidence_scores: {
        overall: extractedData.confidence,
        patient_name: 95,
        department: 88,
        diagnosis: 92
      },
      processing_time_ms: processingTime,
      tokens_used: tokensUsed
    }

    // 转换文书数据格式
    const documents: DocumentInRecord[] = extractedData.documents?.map((doc, index) => ({
      id: doc.id,
      type: doc.type,
      title: doc.title,
      content: doc.content,
      ai_classified: true,
      ai_confidence: doc.confidence,
      sort_order: index
    })) || []

    // 创建医疗记录
    const createRequest: CreateMedicalRecordRequest = {
      record_name: extractedData.patientName ? `${extractedData.patientName}病历` : '智能导入病历',
      patient_info: patientInfo,
      department: extractedData.department,
      primary_diagnosis: extractedData.primaryDiagnosis,
      secondary_diagnosis: extractedData.secondaryDiagnosis,
      major_surgery: extractedData.majorSurgery,
      raw_text: rawText,
      ai_extraction_result: aiExtractionResult,
      ai_confidence_score: extractedData.confidence,
      import_method: 'smart_import',
      documents: documents
    }

    const record = await this.createMedicalRecord(createRequest)

    // 保存解析历史（如果需要的话）
    // await this.saveParsingHistory(...)

    return record
  }

  /**
   * 获取医疗记录列表 - 从测试表查询
   */
  async getMedicalRecords(params: MedicalRecordSearchParams = {}): Promise<{
    data: MedicalRecord[]
    total: number
    page: number
    page_size: number
  }> {
    // 直连 Supabase
    let query = supabase
      .from(this.TABLE_NAME)
      .select('*', { count: 'exact' })

    if (params.search) {
      query = query.or(`record_name.ilike.%${params.search}%,primary_diagnosis.ilike.%${params.search}%`)
    }
    if (params.department) {
      query = query.eq('department', params.department)
    }
    if (params.status) {
      query = query.eq('status', params.status)
    }
    if (params.import_method) {
      query = query.eq('import_method', params.import_method)
    }
    if (params.date_range) {
      query = query.gte('created_at', params.date_range[0])
                   .lte('created_at', params.date_range[1])
    }

    const sortBy = params.sort_by || 'created_at'
    const sortOrder = params.sort_order || 'desc'
    query = query.order(sortBy, { ascending: sortOrder === 'asc' })

    const page = params.page || 1
    const pageSize = params.page_size || 10
    const from = (page - 1) * pageSize
    const to = from + pageSize - 1
    query = query.range(from, to)

    const { data, error, count } = await query
    if (error) {
      console.error('获取医疗记录列表失败:', error)
      throw new Error(`获取医疗记录列表失败: ${error.message}`)
    }
    return { data: data || [], total: count || 0, page, page_size: pageSize }
  }

  /**
   * 根据ID获取医疗记录 - 从测试表查询
   */
  async getMedicalRecordById(id: string): Promise<MedicalRecord> {
    const { data, error } = await supabase
      .from(this.TABLE_NAME)
      .select('*')
      .eq('id', id)
      .single()

    if (error) {
      console.error('获取医疗记录失败:', error)
      throw new Error(`获取医疗记录失败: ${error.message}`)
    }

    return data as MedicalRecord
  }

  /**
   * 更新医疗记录 - 测试表版本
   */
  async updateMedicalRecord(id: string, data: UpdateMedicalRecordRequest): Promise<MedicalRecord> {
    const updateData = {
      ...data,
      updated_at: new Date().toISOString()
    }

    const { error } = await supabase
      .from(this.TABLE_NAME)
      .update(updateData)
      .eq('id', id)

    if (error) {
      console.error('更新医疗记录失败:', error)
      throw new Error(`更新医疗记录失败: ${error.message}`)
    }

    return await this.getMedicalRecordById(id)
  }

  /**
   * 删除医疗记录 - 测试表版本
   */
  async deleteMedicalRecord(id: string): Promise<void> {
    const { error } = await supabase
      .from(this.TABLE_NAME)
      .delete()
      .eq('id', id)

    if (error) {
      console.error('删除医疗记录失败:', error)
      throw new Error(`删除医疗记录失败: ${error.message}`)
    }
  }

  /**
   * 获取统计数据 - 测试表版本
   */
  async getMedicalRecordStats(): Promise<MedicalRecordStats> {
    const { data, error } = await supabase
      .from(this.STATS_VIEW)
      .select('*')
      .single()

    if (error) {
      console.error('获取统计数据失败:', error)
      throw new Error(`获取统计数据失败: ${error.message}`)
    }

    return data
  }

  /**
   * 保存解析历史
   */
  async saveParsingHistory(historyData: Omit<AIParsingHistory, 'id' | 'created_by' | 'created_at'>): Promise<void> {
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error('用户未登录')

    const { error } = await supabase
      .from('ai_parsing_history')
      .insert({
        ...historyData,
        created_by: user.id
      })

    if (error) {
      console.error('保存解析历史失败:', error)
      throw new Error(`保存解析历史失败: ${error.message}`)
    }
  }

  /**
   * 生成病历编号 - 测试表版本
   */
  private async generateRecordNumber(): Promise<string> {
    const now = new Date()
    const year = now.getFullYear()
    const month = String(now.getMonth() + 1).padStart(2, '0')
    const day = String(now.getDate()).padStart(2, '0')

    // 查询当天已有的记录数量
    const { count } = await supabase
      .from(this.TABLE_NAME)
      .select('*', { count: 'exact', head: true })
      .gte('created_at', `${year}-${month}-${day}T00:00:00Z`)
      .lt('created_at', `${year}-${month}-${day}T23:59:59Z`)

    const sequence = String((count || 0) + 1).padStart(3, '0')
    return `TEST${year}${month}${day}${sequence}` // 测试表使用TEST前缀
  }

  /**
   * 批量导入医疗记录
   */
  async batchImportMedicalRecords(records: CreateMedicalRecordRequest[]): Promise<{
    success: number
    failed: number
    errors: string[]
  }> {
    const results = {
      success: 0,
      failed: 0,
      errors: [] as string[]
    }

    for (const record of records) {
      try {
        await this.createMedicalRecord(record)
        results.success++
      } catch (error) {
        results.failed++
        results.errors.push(error instanceof Error ? error.message : '未知错误')
      }
    }

    return results
  }
}

// 创建默认实例
export const supabaseMedicalRecordService = new SupabaseMedicalRecordService()
