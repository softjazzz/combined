import { LONG_REQUEST_TIMEOUT_MS } from '@/config/requestTimeouts'
import ApiService, { apiClient } from '@/services/apiService'

import type { PatientRecord } from './types'

export interface RecordActionIdentity {
  instituteId?: string | null
  patientId?: string | null
}

function normalizeOptionalId(value?: string | null): string | undefined {
  const trimmed = String(value ?? '').trim()
  return trimmed ? trimmed : undefined
}

export async function requestFrontpageDraft(
  visitIdOrRecord: string | PatientRecord,
  identity?: RecordActionIdentity,
) {
  const visitId =
    typeof visitIdOrRecord === 'string'
      ? visitIdOrRecord
      : visitIdOrRecord.visitId || visitIdOrRecord.id
  const patientId = normalizeOptionalId(
    identity?.patientId ??
      (typeof visitIdOrRecord === 'string' ? undefined : visitIdOrRecord.patientId),
  )
  const instituteId = normalizeOptionalId(
    identity?.instituteId ??
      (typeof visitIdOrRecord === 'string' ? undefined : visitIdOrRecord.instituteId),
  )
  const payload: Record<string, string> = { visit_id: visitId }
  if (patientId) payload.patient_id = patientId
  if (instituteId) payload.institute_id = instituteId

  const { data } = await apiClient.post(
    '/api/v1/frontpage/auto-generate-draft',
    payload,
    { timeout: LONG_REQUEST_TIMEOUT_MS },
  )
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '首页抽取提交失败'))
  }
  const draft = data?.data?.frontpage || data?.frontpage || null
  if (!draft) {
    throw new Error('首页抽取未返回草稿结果')
  }
  return {
    draft,
    totalIssues: 0,
    highRiskCount: 0,
    persistence: null,
  }
}

export async function persistBatchFrontpageDraft(
  record: PatientRecord,
  draft: Record<string, any>,
) {
  if (!record.patientId) {
    throw new Error('缺少 patient_id，无法保存参考首页草稿')
  }
  await apiClient.post('/api/medical-records/ai-frontpage-draft', {
    institute_id: normalizeOptionalId(record.instituteId) ?? null,
    patient_id: record.patientId,
    visit_id: record.visitId || record.id,
    draft_json: JSON.stringify(draft),
  })
}

export async function requestCodingQc(record: PatientRecord) {
  if (!record.patientId) {
    throw new Error('缺少 patient_id，无法执行编码质控')
  }
  const instituteId = normalizeOptionalId(record.instituteId)
  const { data } = await apiClient.post('/api/v1/qc/coding-qc/check', {
    ...(instituteId ? { institute_id: instituteId } : {}),
    visit_id: record.visitId || record.id,
    patient_id: record.patientId,
  })
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '编码质控执行失败'))
  }
  const payload = data?.data || {}
  return {
    persistence: payload?.persistence || data?.persistence || null,
    totalIssues: Number(payload?.total_issues || 0),
    highRiskCount: Number(payload?.errors || 0),
  }
}

export async function requestFrontpageQc(record: PatientRecord) {
  if (!record.patientId) {
    throw new Error('缺少 patient_id，无法执行首页质控')
  }
  const visitId = record.visitId || record.id
  const instituteId = normalizeOptionalId(record.instituteId)
  const { data: frontpage } = await apiClient.get(
    `/api/medical-records/frontpage-sheet/${encodeURIComponent(record.patientId)}/${encodeURIComponent(visitId)}`,
    instituteId ? { params: { institute_id: instituteId } } : undefined,
  )
  if (!frontpage) {
    throw new Error('未找到正式首页数据，无法执行首页质控')
  }
  const { data } = await apiClient.post('/api/v1/qc/formal-qc/validate', {
    ...(instituteId ? { institute_id: instituteId } : {}),
    patient_id: record.patientId,
    visit_id: visitId,
    frontpage,
  })
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '首页质控执行失败'))
  }
  const payload = data?.data || {}
  const failedResults = Array.isArray(payload?.results) ? payload.results : []
  const highRiskCount = failedResults.filter(
    (item: any) => String(item?.severity || '').toLowerCase() === 'error',
  ).length
  return {
    persistence: payload?.persistence || data?.persistence || null,
    totalIssues: Number(payload?.failed || failedResults.length || 0),
    highRiskCount,
  }
}

export async function requestSettlementQc(record: PatientRecord) {
  if (!record.patientId) {
    throw new Error('缺少 patient_id，无法执行结算质控')
  }
  const visitId = record.visitId || record.id
  const instituteId = normalizeOptionalId(record.instituteId)
  const { data } = await apiClient.post(
    `/api/medical-records/settlement/${encodeURIComponent(record.patientId)}/${encodeURIComponent(visitId)}/qc`,
    undefined,
    instituteId ? { params: { institute_id: instituteId } } : undefined,
  )
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '结算质控执行失败'))
  }
  const payload = data?.data || data || {}
  const results = Array.isArray(payload?.results) ? payload.results : []
  const failedResults = results.filter((item: any) => !item?.passed)
  const highRiskCount = failedResults.filter((item: any) =>
    ['critical', 'high', 'error'].includes(String(item?.severity || '').toLowerCase()),
  ).length
  return {
    persistence: payload?.persistence || data?.persistence || null,
    totalIssues: failedResults.length,
    highRiskCount,
  }
}

export async function createBatchSummaryNotification(params: {
  workflowType: 'frontpage_generate' | 'coding_qc' | 'frontpage_qc' | 'settlement_qc'
  totalCount: number
  successCount: number
  failedCount: number
  highRiskCount: number
}) {
  if (!ApiService.isAuthenticated()) return
  await apiClient.post('/api/v1/notifications/qc-batch-summary', {
    workflow_type: params.workflowType,
    total_count: params.totalCount,
    success_count: params.successCount,
    failed_count: params.failedCount,
    high_risk_count: params.highRiskCount,
  })
}
