import ApiService, { apiClient } from '@/services/apiService'

import type { PatientRecord } from './types'

/**
 * 正式病案首页 GET 的路径段必须逐段编码：patient_id / visit_id 来自服务端选中行，
 * 但仍是外部字符串，直接拼接会被 `/`、`?`、`#` 等字符截断成另一条路由。
 */
export function buildFormalFrontpageSheetPath(patientId: string, visitId: string): string {
  return `/api/medical-records/frontpage-sheet/${encodeURIComponent(patientId)}/${encodeURIComponent(visitId)}`
}

/**
 * institute_id 只用于消歧：仅当调用方已有可信选中行 / props 的机构号时才追加，空值不编造机构。
 * 省略时由后端按唯一候选兼容，身份歧义由后端返回 409，调用方不得把它降级成空首页或客户端草稿。
 */
export function buildFormalFrontpageSheetUrl(
  patientId: string,
  visitId: string,
  instituteId?: string | null,
): string {
  const path = buildFormalFrontpageSheetPath(patientId, visitId)
  const normalized = typeof instituteId === 'string' ? instituteId.trim() : ''
  if (!normalized) return path
  return `${path}?${new URLSearchParams({ institute_id: normalized }).toString()}`
}

/**
 * 409 表示正式首页归属不唯一、503 表示首页服务暂不可用：两者都必须原样提示用户，
 * 不得被转换成“没有正式首页”，否则客户端草稿或空首页会被当成可质控对象。
 */
export function describeFormalFrontpageSheetError(
  error: unknown,
  fallback = '正式首页读取失败',
): string {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })
    ?.response
  const detail = response?.data?.detail
  const hasDetail = typeof detail === 'string' && detail.trim() !== ''
  if (response?.status === 409) {
    return hasDetail ? String(detail).trim() : '正式首页归属不唯一，请指定机构号后重试'
  }
  if (response?.status === 503) {
    return hasDetail ? String(detail).trim() : '正式首页服务暂不可用，请稍后重试'
  }
  return fallback
}

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
  // GET 仅作只读门槛：确认存在唯一正式首页。409/503 必须原样失败，
  // 不能退化成“无正式首页”再去质控草稿或空首页。
  let frontpageAvailable = false
  try {
    const { data } = await apiClient.get(
      buildFormalFrontpageSheetUrl(
        record.patientId,
        record.visitId || record.id,
        record.instituteId,
      ),
    )
    frontpageAvailable = Boolean(data)
  } catch (error) {
    throw new Error(describeFormalFrontpageSheetError(error, '读取正式首页数据失败'))
  }
  if (!frontpageAvailable) {
    throw new Error('未找到正式首页数据，无法执行首页质控')
  }
  // POST 新合同：只提交三坐标，服务端自行重新读取首页；
  // 不再把 GET 拿到的 frontpage 正文当作判定输入，机构号有则不编造、无则省略。
  const payload: Record<string, string> = {
    patient_id: record.patientId,
    visit_id: record.visitId || record.id,
  }
  const instituteId = typeof record.instituteId === 'string' ? record.instituteId.trim() : ''
  if (instituteId) payload.institute_id = instituteId
  const { data } = await apiClient.post('/api/v1/qc/formal-qc/validate', payload)
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '首页质控执行失败'))
  }
  // 统一信封缺失或 results 非数组都属服务端异常：必须失败关闭，不能返回零问题结果被当成“已质控”。
  const resultPayload = data?.data
  if (!resultPayload || !Array.isArray(resultPayload.results)) {
    throw new Error('首页质控响应缺少统一数据体')
  }
  const failedResults = resultPayload.results
  const highRiskCount = failedResults.filter(
    (item: any) => String(item?.severity || '').toLowerCase() === 'error',
  ).length
  return {
    persistence: resultPayload.persistence || data?.persistence || null,
    totalIssues: Number(resultPayload.failed || failedResults.length || 0),
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
