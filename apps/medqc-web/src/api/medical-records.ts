/**
 * 医疗记录API服务
 * 处理病案记录的增删改查操作
 */
import { supabase, TABLES, STORAGE_BUCKETS } from '../lib/backend-store'
import type { Database } from '../types/database'
import type {
  MedicalRecord,
  CreateMedicalRecordRequest,
  MedicalRecordStatus,
} from '../types/medical-records'
import { ApiWrapper } from '../utils/api-wrapper'
import type { ApiResponse } from '../utils/api-wrapper'

type MedicalRecordRow = Database['public']['Tables']['medical_records']['Row']
type MedicalRecordInsert = Database['public']['Tables']['medical_records']['Insert']
type MedicalRecordUpdate = Database['public']['Tables']['medical_records']['Update']

/**
 * 获取医疗记录列表
 */
export async function getMedicalRecords(options?: {
  status?: MedicalRecordStatus
  department?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<MedicalRecord[]>> {
  const baseQuery = supabase
    .from(TABLES.MEDICAL_RECORDS)
    .select('*', { count: 'exact' })
    .order('created_at', { ascending: false })

  const queryOptions = {
    page:
      options?.offset && options?.limit
        ? Math.floor(options.offset / options.limit) + 1
        : undefined,
    pageSize: options?.limit,
    filters: {
      status: options?.status,
      department: options?.department,
    },
  }

  const query = ApiWrapper.buildQuery(baseQuery, queryOptions)

  return ApiWrapper.query(async () => {
    const result = await query
    return {
      data: result.data?.map(convertRowToMedicalRecord) || [],
      error: result.error,
      count: result.count,
    }
  })
}

/**
 * 根据ID获取医疗记录
 */
export async function getMedicalRecordById(id: string): Promise<ApiResponse<MedicalRecord>> {
  return ApiWrapper.query(async () => {
    const result = await supabase.from(TABLES.MEDICAL_RECORDS).select('*').eq('id', id).single()

    return {
      data: result.data ? convertRowToMedicalRecord(result.data) : null,
      error: result.error,
      count: null,
    }
  })
}

/**
 * 创建医疗记录
 */
export async function createMedicalRecord(
  request: CreateMedicalRecordRequest,
): Promise<ApiResponse<MedicalRecord>> {
  try {
    // 处理文件上传
    let fileUrl: string | null = null
    let fileName: string | null = null
    let fileSize: number | null = null

    if (request.file) {
      const file = request.file
      const filePath = `${Date.now()}-${file.name}`

      const uploadResult = await ApiWrapper.uploadFile(
        file,
        STORAGE_BUCKETS.MEDICAL_FILES,
        filePath,
      )

      if (!uploadResult.success) {
        throw new Error(`文件上传失败: ${uploadResult.error?.message}`)
      }

      fileUrl = uploadResult.data?.url || null
      fileName = file.name
      fileSize = file.size
    }

    // 创建数据库记录
    const insertData: MedicalRecordInsert = {
      patient_name: request.patient_name,
      patient_age: request.patient_age,
      patient_gender: request.patient_gender,
      department: request.department,
      admission_date: request.admission_date,
      record_type: request.record_type,
      content: request.content,
      file_url: fileUrl,
      file_name: fileName,
      file_size: fileSize,
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    return ApiWrapper.insert(async () => {
      const result = await supabase
        .from(TABLES.MEDICAL_RECORDS)
        .insert(insertData)
        .select()
        .single()

      return {
        data: result.data ? convertRowToMedicalRecord(result.data) : null,
        error: result.error,
      }
    })
  } catch (error) {
    return {
      success: false,
      error: {
        message: error instanceof Error ? error.message : '创建医疗记录失败',
      },
    }
  }
}

/**
 * 更新医疗记录
 */
export async function updateMedicalRecord(
  id: string,
  updates: Partial<MedicalRecordUpdate>,
): Promise<ApiResponse<MedicalRecord>> {
  const updateData: MedicalRecordUpdate = {
    ...updates,
    updated_at: new Date().toISOString(),
  }

  return ApiWrapper.update(async () => {
    const result = await supabase
      .from(TABLES.MEDICAL_RECORDS)
      .update(updateData)
      .eq('id', id)
      .select()
      .single()

    return {
      data: result.data ? convertRowToMedicalRecord(result.data) : null,
      error: result.error,
    }
  })
}

/**
 * 删除医疗记录
 */
export async function deleteMedicalRecord(id: string): Promise<ApiResponse<boolean>> {
  return ApiWrapper.delete(async () => {
    const result = await supabase.from(TABLES.MEDICAL_RECORDS).delete().eq('id', id)

    return {
      data: !result.error,
      error: result.error,
    }
  })
}

/**
 * 批量删除医疗记录
 */
export async function batchDeleteMedicalRecords(ids: string[]): Promise<
  ApiResponse<{
    deleted: number
    failed: number
    errors: string[]
  }>
> {
  const operations = ids.map((id) => () => deleteMedicalRecord(id))

  const result = await ApiWrapper.batchOperation(operations, {
    continueOnError: true,
    maxConcurrency: 3,
  })

  return {
    success: result.success,
    data: {
      deleted: result.summary.successful,
      failed: result.summary.failed,
      errors: result.results.filter((r) => !r.success).map((r) => r.error?.message || '未知错误'),
    },
  }
}

/**
 * 搜索医疗记录
 */
export async function searchMedicalRecords(
  query: string,
  options?: {
    limit?: number
    offset?: number
  },
): Promise<ApiResponse<MedicalRecord[]>> {
  const searchQuery = supabase
    .from(TABLES.MEDICAL_RECORDS)
    .select('*', { count: 'exact' })
    .or(`patient_name.ilike.%${query}%,content.ilike.%${query}%,department.ilike.%${query}%`)
    .order('created_at', { ascending: false })

  const queryOptions = {
    page:
      options?.offset && options?.limit
        ? Math.floor(options.offset / options.limit) + 1
        : undefined,
    pageSize: options?.limit,
  }

  const finalQuery = ApiWrapper.buildQuery(searchQuery, queryOptions)

  return ApiWrapper.query(async () => {
    const result = await finalQuery
    return {
      data: result.data?.map(convertRowToMedicalRecord) || [],
      error: result.error,
      count: result.count,
    }
  })
}

/**
 * 获取医疗记录统计
 */
export async function getMedicalRecordStats(): Promise<
  ApiResponse<{
    total: number
    byStatus: Record<MedicalRecordStatus, number>
    byDepartment: Record<string, number>
  }>
> {
  return ApiWrapper.query(async () => {
    const result = await supabase.from(TABLES.MEDICAL_RECORDS).select('status, department')

    if (result.error) {
      return { data: null, error: result.error, count: null }
    }

    const records = result.data || []
    const total = records.length

    const byStatus = records.reduce(
      (acc, record) => {
        acc[record.status as MedicalRecordStatus] =
          (acc[record.status as MedicalRecordStatus] || 0) + 1
        return acc
      },
      {} as Record<MedicalRecordStatus, number>,
    )

    const byDepartment = records.reduce(
      (acc, record) => {
        acc[record.department] = (acc[record.department] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )

    return {
      data: { total, byStatus, byDepartment },
      error: null,
      count: null,
    }
  })
}

/**
 * 转换数据库行为医疗记录对象
 */
function convertRowToMedicalRecord(row: MedicalRecordRow): MedicalRecord {
  return {
    id: row.id,
    patient_name: row.patient_name,
    patient_age: row.patient_age,
    patient_gender: row.patient_gender as 'M' | 'F' | 'U',
    department: row.department,
    admission_date: row.admission_date,
    record_type: row.record_type as 'inpatient' | 'outpatient' | 'emergency',
    content: row.content,
    file_url: row.file_url || undefined,
    file_name: row.file_name || undefined,
    file_size: row.file_size || undefined,
    status: row.status as MedicalRecordStatus,
    qc_score: row.qc_score || undefined,
    qc_grade: row.qc_grade as 'A' | 'B' | 'C' | undefined,
    created_at: row.created_at,
    updated_at: row.updated_at,
  }
}

// ===== Compatibility exports for legacy doctor workstation =====
export type { MedicalRecord }

export interface MedicalRecordTemplate {
  id: string
  name: string
  content: string
}

export interface QCAnalysisResult {
  score?: number
  issues?: Array<{ description?: string; severity?: string }>
  suggestions?: string[]
}

export async function getDemoMedicalRecords(
  _scenario?: string,
): Promise<ApiResponse<MedicalRecord[]>> {
  return getMedicalRecords({ limit: 20, offset: 0 })
}

export async function getDoctorWorkstationTemplates(): Promise<
  ApiResponse<MedicalRecordTemplate[]>
> {
  return {
    success: true,
    data: [],
  }
}

export async function saveMedicalRecordDraft(
  id: string,
  updates: Partial<MedicalRecordUpdate>,
): Promise<ApiResponse<MedicalRecord>> {
  return updateMedicalRecord(id, updates)
}

export async function submitRecordForQCAnalysis(
  _recordId: string,
  _content: string,
): Promise<ApiResponse<QCAnalysisResult>> {
  return {
    success: true,
    data: {
      score: 0,
      issues: [],
      suggestions: [],
    },
  }
}
