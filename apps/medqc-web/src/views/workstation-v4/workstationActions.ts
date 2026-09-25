import ApiService, { apiClient } from '@/services/apiService'

import type { PatientRecord } from './types'

export async function requestFrontpageDraft(visitId: string) {
  const { data } = await apiClient.post(
    '/api/v1/frontpage/auto-generate-draft',
    { visit_id: visitId },
    { timeout: 120000 },
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
    institute_id: record.instituteId || null,
    patient_id: record.patientId,
    visit_id: record.visitId || record.id,
    draft_json: JSON.stringify(draft),
  })
}

export async function requestCodingQc(record: PatientRecord) {
  if (!record.patientId) {
    throw new Error('缺少 patient_id，无法执行编码质控')
  }
  const { data } = await apiClient.post('/api/v1/qc/coding-qc/check', {
    visit_id: record.visitId || record.id,
    patient_id: record.patientId,
    institute_id: record.instituteId || null,
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
  const { data: frontpage } = await apiClient.get(
    `/api/medical-records/frontpage-sheet/${record.patientId}/${record.visitId || record.id}`,
  )
  if (!frontpage) {
    throw new Error('未找到正式首页数据，无法执行首页质控')
  }
  const { data } = await apiClient.post('/api/v1/qc/formal-qc/validate', {
    patient_id: record.patientId,
    visit_id: record.visitId || record.id,
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
  const { data } = await apiClient.post(
    `/api/medical-records/settlement/${record.patientId}/${record.visitId || record.id}/qc`,
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
