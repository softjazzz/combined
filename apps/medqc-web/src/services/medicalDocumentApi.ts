export interface MedicalDocumentPayload {
  id?: string
  record_id?: string | null
  document_type: string
  title: string
  content: string
  summary?: string
  ai_classified?: boolean
  ai_confidence_score?: number
  ai_extraction_metadata?: Record<string, unknown>
  document_metadata?: Record<string, unknown>
  position?: Record<string, unknown>
  sort_order?: number
  status?: 'active' | 'archived'
}

export async function createDocumentsBatch(items: MedicalDocumentPayload[]): Promise<{ success: boolean; count: number }>{
  const apiUrl = typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? 'http://localhost:8001/api/medical-documents/batch'
    : '/api/medical-documents/batch'

  const resp = await fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items)
  })

  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}))
    throw new Error(data.detail || `创建医疗文书失败: ${resp.status}`)
  }

  const data = await resp.json()
  return { success: true, count: data.count || (data.data ? data.data.length : 0) }
}

export async function listDocuments(record_id?: string) {
  const apiUrl = typeof window !== 'undefined' && window.location.hostname === 'localhost'
    ? `http://localhost:8001/api/medical-documents${record_id ? `?record_id=${record_id}` : ''}`
    : `/api/medical-documents${record_id ? `?record_id=${record_id}` : ''}`
  const resp = await fetch(apiUrl)
  if (!resp.ok) throw new Error('获取医疗文书失败')
  return resp.json()
}

