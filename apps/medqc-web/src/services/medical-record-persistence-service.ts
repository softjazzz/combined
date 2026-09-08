/**
 * 医疗记录持久化服务（后端 API 版）
 * 项目已停用 Supabase，统一走后端接口。
 */

import type { ExtractedMedicalData } from '@/types/medical'
import { getAccessToken } from '@/utils/auth-token'
import { resolveApiBaseUrl } from '@/utils/api-helpers'

export interface MedicalRecord {
  id: string
  patient_name?: string
  patient_age?: number | null
  patient_gender?: string
  department?: string
  diagnosis_primary?: string
  diagnosis_secondary?: string[]
  major_surgery?: string
  content_sections?: {
    documents?: Array<Record<string, unknown>>
  }
  status?: 'draft' | 'active' | 'archived' | string
  created_at?: string
  updated_at?: string
}

export interface PatientInfo {
  name: string
  age?: number
  gender?: string
}

export interface DocumentInRecord {
  id: string
  type: string
  title: string
  content: string
  ai_classified?: boolean
  ai_confidence?: number
  sort_order?: number
}

export interface AIExtractionResult {
  extraction_time: string
  model_used: string
  fields_extracted: string[]
  confidence_scores: Record<string, number>
  processing_time_ms: number
  tokens_used?: number
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
  documents?: DocumentInRecord[]
}

export interface UpdateMedicalRecordRequest {
  record_name?: string
  patient_info?: Partial<PatientInfo>
  department?: string
  primary_diagnosis?: string
  secondary_diagnosis?: string[]
  major_surgery?: string
  status?: 'draft' | 'active' | 'archived'
  documents?: DocumentInRecord[]
}

export interface MedicalRecordSearchParams {
  search?: string
  department?: string
  status?: string
  page?: number
  page_size?: number
}

export interface MedicalRecordStats {
  total_records: number
  monthly_new: number
  pending_review: number
  smart_imported: number
  ai_processed: number
  avg_confidence: number
}

async function requestApi<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${resolveApiBaseUrl()}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`HTTP ${response.status}: ${response.statusText} - ${text}`)
  }

  return (await response.json()) as T
}

function mapCreateRequestToApiPayload(data: CreateMedicalRecordRequest) {
  const docs = (data.documents || []).map((d, idx) => ({
    id: d.id,
    type: d.type,
    title: d.title,
    content: d.content,
    ai_classified: d.ai_classified ?? true,
    ai_confidence: d.ai_confidence ?? 0,
    sort_order: d.sort_order ?? idx,
  }))

  return {
    patient_name: data.patient_info?.name || data.record_name || '未命名病历',
    patient_age: data.patient_info?.age ?? null,
    patient_gender: data.patient_info?.gender || '',
    department: data.department || '',
    diagnosis_primary: data.primary_diagnosis || '',
    diagnosis_secondary: data.secondary_diagnosis || [],
    major_surgery: data.major_surgery || '',
    status: 'active',
    content_sections: {
      documents: docs,
    },
    content: data.raw_text || '',
  }
}

export class MedicalRecordPersistenceService {
  async createMedicalRecord(data: CreateMedicalRecordRequest): Promise<MedicalRecord> {
    const payload = mapCreateRequestToApiPayload(data)
    return requestApi<MedicalRecord>('/api/medical-records', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async saveAIExtractionResult(
    extractedData: ExtractedMedicalData,
    rawText: string,
    _inputMethod: 'paste' | 'upload' | 'batch',
    processingTime: number,
    tokensUsed?: number,
  ): Promise<MedicalRecord> {
    const aiExtractionResult: AIExtractionResult = {
      extraction_time: new Date().toISOString(),
      model_used: 'medical-llm-v1',
      fields_extracted: Object.keys(extractedData).filter(
        (key) => !!extractedData[key as keyof ExtractedMedicalData],
      ),
      confidence_scores: {
        overall: extractedData.confidence || 0,
      },
      processing_time_ms: processingTime,
      tokens_used: tokensUsed,
    }

    const documents = (extractedData.documents || []).map((doc, index) => ({
      id: doc.id,
      type: doc.type,
      title: doc.title,
      content: doc.content,
      ai_classified: true,
      ai_confidence: doc.confidence || 0,
      sort_order: index,
    }))

    return this.createMedicalRecord({
      record_name: extractedData.patientName ? `${extractedData.patientName}病历` : '智能导入病历',
      patient_info: {
        name: extractedData.patientName || '未识别',
        age: extractedData.patientAge,
        gender: extractedData.patientGender,
      },
      department: extractedData.department || '',
      primary_diagnosis: extractedData.primaryDiagnosis || '',
      secondary_diagnosis: extractedData.secondaryDiagnosis || [],
      major_surgery: extractedData.majorSurgery || '',
      raw_text: rawText,
      ai_extraction_result: aiExtractionResult,
      ai_confidence_score: extractedData.confidence || 0,
      import_method: 'smart_import',
      documents,
    })
  }

  async getMedicalRecords(params: MedicalRecordSearchParams = {}): Promise<{
    data: MedicalRecord[]
    total: number
    page: number
    page_size: number
  }> {
    const q = new URLSearchParams()
    if (params.search) q.set('search', params.search)
    if (params.department) q.set('department', params.department)
    if (params.status) q.set('status', params.status)
    if (params.page) q.set('page', String(params.page))
    if (params.page_size) q.set('page_size', String(params.page_size))

    const suffix = q.toString() ? `?${q.toString()}` : ''
    const result = await requestApi<{
      items?: MedicalRecord[]
      total?: number
      page?: number
      page_size?: number
    }>(`/api/medical-records${suffix}`, { method: 'GET' })

    return {
      data: result.items || [],
      total: result.total || 0,
      page: result.page || params.page || 1,
      page_size: result.page_size || params.page_size || 10,
    }
  }

  async getMedicalRecordById(id: string): Promise<MedicalRecord> {
    return requestApi<MedicalRecord>(`/api/medical-records/${encodeURIComponent(id)}`, {
      method: 'GET',
    })
  }

  async updateMedicalRecord(id: string, data: UpdateMedicalRecordRequest): Promise<MedicalRecord> {
    const payload = {
      patient_name: data.patient_info?.name,
      patient_age: data.patient_info?.age,
      patient_gender: data.patient_info?.gender,
      department: data.department,
      diagnosis_primary: data.primary_diagnosis,
      diagnosis_secondary: data.secondary_diagnosis,
      major_surgery: data.major_surgery,
      status: data.status,
      content_sections: data.documents
        ? {
            documents: data.documents,
          }
        : undefined,
    }

    return requestApi<MedicalRecord>(`/api/medical-records/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
  }

  async deleteMedicalRecord(id: string): Promise<void> {
    await requestApi(`/api/medical-records/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    })
  }

  async getMedicalRecordStats(): Promise<MedicalRecordStats> {
    return requestApi<MedicalRecordStats>('/api/medical-records/statistics', {
      method: 'GET',
    })
  }
}

export const medicalRecordPersistenceService = new MedicalRecordPersistenceService()
