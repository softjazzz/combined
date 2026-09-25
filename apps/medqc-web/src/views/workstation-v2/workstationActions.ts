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
 * institute_id 只用于消歧：仅当调用方已有可信选中病例的机构号时才追加，空值不编造机构。
 * 省略时由后端按唯一候选兼容，命中多机构由后端返回 409，调用方不得把它降级成空首页或草稿。
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
  // GET 只作只读门槛：先确认该病例确有正式首页。读不到（404/409/503）一律失败关闭，
  // 绝不把 LLM 草稿或空首页当成可质控对象；正文不再作为 POST 判定输入。
  let officialSheet: Record<string, any> | null = null
  try {
    const { data } = await apiClient.get(
      buildFormalFrontpageSheetUrl(
        record.patientId,
        record.visitId || record.id,
        record.instituteId,
      ),
    )
    officialSheet = data ?? null
  } catch (error) {
    // 409/503 等正式源读取失败必须原样失败，不能退化成“无正式首页”再对草稿执行正式质控。
    throw new Error(describeFormalFrontpageSheetError(error, '读取正式首页数据失败'))
  }
  if (!officialSheet) {
    throw new Error('未找到正式首页数据，无法执行首页质控')
  }
  // 正式质控新合同：只传三坐标，服务端自行重读正式首页；机构号有则传、无则省略，不编造机构。
  const postBody: Record<string, string> = {
    patient_id: record.patientId,
    visit_id: record.visitId || record.id,
  }
  const instituteId = typeof record.instituteId === 'string' ? record.instituteId.trim() : ''
  if (instituteId) postBody.institute_id = instituteId
  const { data } = await apiClient.post('/api/v1/qc/formal-qc/validate', postBody)
  if (data?.success === false) {
    throw new Error(String(data?.error || data?.message || '首页质控执行失败'))
  }
  const payload = data?.data
  // 畸形 200（缺统一信封或 results 非数组）必须失败关闭，不能报成“零问题通过”。
  if (!payload || !Array.isArray(payload.results)) {
    throw new Error('首页质控响应异常，无法确认质控结果')
  }
  const failedResults = payload.results
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
