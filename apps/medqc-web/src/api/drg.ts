// @ts-nocheck
/**
 * DRG 模块 API 服务
 * 支持 Mock 模式和真实 API 模式切换
 */

import type {
  CaseFrontPage,
  CodingSuggestResponse,
  CodingSuggestionsResponse,
  DRGAlertsResponse,
  DRGGroupingHistoryItem,
  DRGGroupingResult,
  ICDSearchResponse,
  ValidationResult,
} from '@/types/drg'
import type { AnalysisDimension, AnalysisDataResponse } from '@/types/drg-analysis'

// Mock 数据导入（开发阶段使用）
import {
  mockCaseFrontPages,
  getCaseFrontPageByAdmissionId,
  getDiagnosesByFrontPageId,
  getProceduresByFrontPageId,
} from '../data/drg/mock-case-front-page'

import {
  mockDRGGroupings,
  mockCodingSuggestions,
  mockDRGAlerts,
  getLatestGroupingByAdmissionId,
} from '../data/drg/mock-drg-grouping'

import { suggestICDCodes, searchICD10Codes, searchICD9Procedures } from '../data/drg/mock-icd-codes'

import { mockAnalysisData } from '../data/drg/mock-analysis'

// 配置：是否使用 Mock 数据
const USE_MOCK_DATA = (import.meta as any).env?.VITE_USE_DRG_MOCK !== 'false' // 默认使用 Mock；设置为 "false" 可切到真实 API

const API_V1_PREFIX = '/api/v1'

type GrouperConfigPayload = {
  region: string
  engine: string
  baseRate: number
  hospitalCoefficient: number
  regionCoefficient: number
  effectiveDate: string
  lowRateThreshold: number
  highRateThreshold: number
  enableCCMCC: boolean
  enableAutoSuggestion: boolean
}

type GrouperVersionItem = {
  version_id: string
  operator: string
  operated_at: string
  change_summary: string
  published_at?: string
  is_published?: boolean
}

type GrouperConsistencySample = {
  case_key?: string
  admission_id?: string
  hospital_group: string
  insurance_group: string
}

const mockGrouperStore: {
  draft: GrouperConfigPayload
  published_version_id: string | null
  versions: Array<GrouperVersionItem & { config: GrouperConfigPayload }>
} = {
  draft: {
    region: 'sichuan',
    engine: 'OpenDRG',
    baseRate: 10000,
    hospitalCoefficient: 1.2,
    regionCoefficient: 1.05,
    effectiveDate: '2024-01-01',
    lowRateThreshold: 3,
    highRateThreshold: 30,
    enableCCMCC: true,
    enableAutoSuggestion: true,
  },
  published_version_id: null,
  versions: [],
}

// ==================== 病案首页相关 API ====================

/**
 * 获取病案首页列表
 */
export async function getCaseFrontPages(): Promise<CaseFrontPage[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockCaseFrontPages)
  }

  const response = await fetch(`${API_V1_PREFIX}/case-front-page`)
  return response.json()
}

/**
 * 根据 admission_id 获取病案首页详情
 */
export async function getCaseFrontPageDetail(admissionId: string) {
  if (USE_MOCK_DATA) {
    const frontPage = getCaseFrontPageByAdmissionId(admissionId)
    if (!frontPage) return Promise.resolve(null)

    const diagnoses = getDiagnosesByFrontPageId(frontPage.front_page_id).map((d) => ({
      code: d.diagnosis_code,
      name: d.diagnosis_name,
      sequence: d.sequence,
      is_complication: d.is_complication,
    }))

    const procedures = getProceduresByFrontPageId(frontPage.front_page_id).map((p) => ({
      code: p.procedure_code,
      name: p.procedure_name,
      sequence: p.sequence,
      procedure_date: p.procedure_date,
    }))

    return Promise.resolve({
      ...frontPage,
      secondary_diagnoses: diagnoses,
      procedures,
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/case-front-page/${admissionId}`)
  return response.json()
}

/**
 * 创建或更新病案首页
 */
export async function saveCaseFrontPage(data: Partial<CaseFrontPage>): Promise<CaseFrontPage> {
  if (USE_MOCK_DATA) {
    // Mock: 模拟保存成功
    console.log('[Mock] 保存病案首页:', data)
    return Promise.resolve({
      ...mockCaseFrontPages[0],
      ...data,
    } as CaseFrontPage)
  }

  const response = await fetch(`${API_V1_PREFIX}/case-front-page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return response.json()
}

// ==================== 编码辅助相关 API ====================

/**
 * ICD 编码推荐
 * PRD 3.2.1 API接口1
 */
export async function suggestCoding(params: {
  diagnosis_name: string
  context?: string
  category: 'diagnosis' | 'procedure'
}): Promise<CodingSuggestResponse> {
  if (USE_MOCK_DATA) {
    // Mock: 使用本地模拟函数
    const suggestions = suggestICDCodes(params.diagnosis_name)
    const candidates = suggestions.map((s) => ({
      code: s.code,
      name: s.name,
      confidence: s.confidence,
      note: s.notes,
    }))
    return Promise.resolve({ candidates, total: candidates.length })
  }

  const response = await fetch(`${API_V1_PREFIX}/coding/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data
}

/**
 * 编码校验
 * PRD 3.2.1 API接口2
 */
export async function validateCoding(params: {
  admission_id: string
  primary_diagnosis: { code: string; name: string }
  secondary_diagnoses: Array<{ code: string; name: string }>
  procedures: Array<{ code: string; name: string }>
}): Promise<ValidationResult> {
  if (USE_MOCK_DATA) {
    // Mock: 模拟校验结果
    return Promise.resolve({
      is_valid: true,
      warnings: [
        {
          type: 'missing_diagnosis',
          message: "病程记录中提到'心力衰竭'，建议补充次诊断：I50.001（心力衰竭）",
          evidence: '病程记录第3天：患者出现呼吸困难，双肺底湿啰音，考虑心力衰竭...',
          severity: 'info',
        },
      ],
      conflicts: [],
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/coding/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return response.json()
}

/**
 * 搜索 ICD 编码库
 */
export async function searchICDCodes(params: {
  keyword: string
  category: 'diagnosis' | 'procedure'
  limit?: number
}): Promise<ICDSearchResponse> {
  if (USE_MOCK_DATA) {
    const results =
      params.category === 'diagnosis'
        ? searchICD10Codes(params.keyword)
        : searchICD9Procedures(params.keyword)
    const limited = typeof params.limit === 'number' ? results.slice(0, params.limit) : results
    return Promise.resolve({ results: limited, total: limited.length })
  }

  const response = await fetch(
    `${API_V1_PREFIX}/coding/search?keyword=${encodeURIComponent(params.keyword)}&category=${params.category}&limit=${params.limit ?? 20}`,
  )
  return response.json()
}

// ==================== DRG 分组相关 API ====================

/**
 * DRG 入组预测
 * PRD 3.2.2 核心 API
 */
export async function predictDRGGrouping(params: {
  admission_id: string
  region?: string
}): Promise<DRGGroupingResult> {
  if (USE_MOCK_DATA) {
    // Mock: 返回模拟的分组结果
    const grouping = getLatestGroupingByAdmissionId(params.admission_id)
    if (!grouping) {
      throw new Error('未找到分组数据')
    }

    return Promise.resolve({
      adrg_code: grouping.adrg_code,
      adrg_name: grouping.adrg_name,
      drg_code: grouping.drg_code,
      drg_name: grouping.drg_name,
      weight: grouping.weight,
      baseline_payment: grouping.baseline_payment,
      expected_los: { min: 10, max: 15 },
      confidence: 0.89,
      risk_level: 'high',
      grouping_logic: `主诊断${grouping.adrg_code} + 合并症`,
    } as any)
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

/**
 * DIP 入组预测
 */
export async function predictDIPGrouping(
  params: import('@/types/drg').DIPPredictRequest,
): Promise<import('@/types/drg').DIPGroupingResult> {
  if (USE_MOCK_DATA) {
    // Mock logic if needed, or throw error saying Mock not supported for DIP yet
    throw new Error('DIP Mock mode not implemented in frontend, please use real API')
    // Or return a mock object
  }

  const response = await fetch(`${API_V1_PREFIX}/dip/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

/**
 * 获取分组历史记录
 */
export async function getGroupingHistory(admissionId: string): Promise<DRGGroupingHistoryItem[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(
      mockDRGGroupings
        .filter((g) => g.admission_id === admissionId)
        .map((g) => ({
          grouping_id: g.grouping_id,
          drg_code: g.drg_code,
          drg_name: g.drg_name,
          weight: g.weight,
          baseline_payment: g.baseline_payment,
          actual_cost: g.actual_cost,
          profit_margin: g.profit_margin,
          version: g.version,
          is_latest: g.is_latest,
          grouped_at: g.grouped_at,
        })) as any,
    )
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/grouping/${admissionId}/history`)
  const data = await response.json()
  return data.history
}

// ==================== 编码建议相关 API ====================

/**
 * 获取编码优化建议
 */
export async function getCodingSuggestions(params?: {
  admission_id?: string
  status?: 'pending' | 'accepted' | 'rejected'
  limit?: number
}): Promise<CodingSuggestionsResponse> {
  if (USE_MOCK_DATA) {
    let suggestions = [...mockCodingSuggestions]
    if (params?.admission_id) {
      suggestions = suggestions.filter((s) => s.admission_id === params.admission_id)
    }
    if (params?.status) {
      suggestions = suggestions.filter((s) => s.status === params.status)
    }
    const limited =
      typeof params?.limit === 'number' ? suggestions.slice(0, params.limit) : suggestions
    return Promise.resolve({ suggestions: limited as any, total: limited.length })
  }

  const qs = new URLSearchParams()
  if (params?.admission_id) qs.set('admission_id', params.admission_id)
  if (params?.status) qs.set('status', params.status)
  if (typeof params?.limit === 'number') qs.set('limit', String(params.limit))

  const response = await fetch(
    `${API_V1_PREFIX}/drg/suggestions${qs.toString() ? `?${qs.toString()}` : ''}`,
  )
  return response.json()
}

/**
 * 处理编码建议（接受/拒绝）
 */
export async function handleCodingSuggestion(params: {
  suggestion_id: number
  action: 'accept' | 'reject'
  handled_by?: string
}): Promise<void> {
  if (USE_MOCK_DATA) {
    console.log('[Mock] 处理编码建议:', params)
    return Promise.resolve()
  }

  await fetch(`${API_V1_PREFIX}/drg/suggestions/handle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      suggestion_id: params.suggestion_id,
      action: params.action,
      handled_by: params.handled_by || 'current_user',
    }),
  })
}

// ==================== 监控预警相关 API ====================

/**
 * 获取预警列表
 */
export async function getDRGAlerts(params?: {
  admission_id?: string
  alert_level?: 'info' | 'warning' | 'critical'
  status?: 'pending' | 'acknowledged' | 'resolved'
  limit?: number
}): Promise<DRGAlertsResponse> {
  if (USE_MOCK_DATA) {
    let alerts = [...mockDRGAlerts]
    if (params?.admission_id) {
      alerts = alerts.filter((a) => a.admission_id === params.admission_id)
    }
    if (params?.alert_level) {
      alerts = alerts.filter((a) => a.alert_level === params.alert_level)
    }
    if (params?.status) {
      alerts = alerts.filter((a) => a.status === params.status)
    }
    const limited = typeof params?.limit === 'number' ? alerts.slice(0, params.limit) : alerts
    return Promise.resolve({ alerts: limited as any, total: limited.length })
  }

  const qs = new URLSearchParams()
  if (params?.admission_id) qs.set('admission_id', params.admission_id)
  if (params?.alert_level) qs.set('alert_level', params.alert_level)
  if (params?.status) qs.set('status', params.status)
  if (typeof params?.limit === 'number') qs.set('limit', String(params.limit))

  const response = await fetch(
    `${API_V1_PREFIX}/drg/alerts${qs.toString() ? `?${qs.toString()}` : ''}`,
  )
  return response.json()
}

export async function handleDRGAlert(params: {
  alert_id: number
  action: 'acknowledge' | 'resolve'
  handled_by?: string
}): Promise<void> {
  if (USE_MOCK_DATA) {
    console.log('[Mock] 处理预警:', params)
    return Promise.resolve()
  }

  const res = await fetch(`${API_V1_PREFIX}/drg/alerts/handle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      alert_id: params.alert_id,
      action: params.action,
      handled_by: params.handled_by || 'current_user',
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `handleDRGAlert failed: ${res.status}`)
  }
}

// ==================== 统计分析 API ====================

export async function getAnalysisData(params: {
  dimension: AnalysisDimension
  startDate: string
  endDate: string
  filterId?: string // 科室ID/医生ID等
  sessionId?: string
  batchId?: string
  department?: string
  doctor?: string
}): Promise<AnalysisDataResponse> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockAnalysisData(params.dimension))
  }

  const qs = new URLSearchParams({
    dimension: params.dimension,
    start_date: params.startDate,
    end_date: params.endDate,
  })
  if (params.filterId) qs.set('filter_id', params.filterId)
  if (params.sessionId) qs.set('session_id', params.sessionId)
  if (params.batchId) qs.set('batch_id', params.batchId)
  if (params.department) qs.set('department', params.department)
  if (params.doctor) qs.set('doctor', params.doctor)

  const response = await fetch(`${API_V1_PREFIX}/drg/analysis?${qs.toString()}`)
  const data = await response.json()
  return data.data ?? data
}

export async function exportAnalysisData(params: {
  format: 'excel' | 'pdf' | 'docx'
  dimension: AnalysisDimension
  startDate: string
  endDate: string
  filterId?: string
  sessionId?: string
  batchId?: string
  department?: string
  doctor?: string
  versionId?: string
}): Promise<{ blob: Blob; fileName: string }> {
  if (USE_MOCK_DATA && params.format === 'docx') {
    throw new Error('Mock 模式暂不支持 DOCX 导出，请切换真实 API')
  }

  if (USE_MOCK_DATA) {
    return Promise.reject(new Error('Mock 模式请使用前端本地导出'))
  }

  const qs = new URLSearchParams({
    dimension: params.dimension,
    start_date: params.startDate,
    end_date: params.endDate,
  })
  if (params.filterId) qs.set('filter_id', params.filterId)
  if (params.sessionId) qs.set('session_id', params.sessionId)
  if (params.batchId) qs.set('batch_id', params.batchId)
  if (params.department) qs.set('department', params.department)
  if (params.doctor) qs.set('doctor', params.doctor)
  if (params.versionId) qs.set('version_id', params.versionId)

  const response = await fetch(
    `${API_V1_PREFIX}/drg/analysis/export/${params.format}?${qs.toString()}`,
  )
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(text || `导出失败: ${response.status}`)
  }

  const disposition = response.headers.get('content-disposition') || ''
  const matched = disposition.match(/filename=([^;]+)/i)
  const fileName = matched?.[1]?.replace(/["']/g, '') || `drg-analysis.${params.format}`
  const blob = await response.blob()
  return { blob, fileName }
}

// ==================== 分组器配置中心 API（6.2.2） ====================

export async function getGrouperConfigCurrent(): Promise<{
  draft: GrouperConfigPayload
  published_version_id: string | null
  published_config: GrouperConfigPayload | null
  latest_version_id: string | null
  latest_consistency_report?: any
}> {
  if (USE_MOCK_DATA) {
    const latest = mockGrouperStore.versions[0]
    return Promise.resolve({
      draft: { ...mockGrouperStore.draft },
      published_version_id: mockGrouperStore.published_version_id,
      published_config: latest ? { ...latest.config } : null,
      latest_version_id: latest?.version_id || null,
      latest_consistency_report: null,
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/current`)
  const data = await response.json()
  return data.data
}

export async function saveGrouperConfigDraft(params: {
  config: GrouperConfigPayload
  operator: string
  change_summary: string
}) {
  if (USE_MOCK_DATA) {
    mockGrouperStore.draft = { ...params.config }
    return Promise.resolve({
      draft: { ...mockGrouperStore.draft },
      audit: {
        version_id: mockGrouperStore.published_version_id,
        operator: params.operator,
        operated_at: new Date().toISOString(),
        change_summary: params.change_summary,
      },
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

export async function publishGrouperConfig(params: { operator: string; change_summary: string }) {
  if (USE_MOCK_DATA) {
    const versionId = `mock-${Date.now()}`
    const now = new Date().toISOString()
    const version = {
      version_id: versionId,
      operator: params.operator,
      operated_at: now,
      change_summary: params.change_summary,
      published_at: now,
      is_published: true,
      config: { ...mockGrouperStore.draft },
    }
    mockGrouperStore.versions.unshift(version)
    mockGrouperStore.published_version_id = versionId
    return Promise.resolve(version)
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

export async function listGrouperConfigVersions(): Promise<{
  items: GrouperVersionItem[]
  total: number
}> {
  if (USE_MOCK_DATA) {
    return Promise.resolve({
      items: mockGrouperStore.versions.map(({ config, ...item }) => item),
      total: mockGrouperStore.versions.length,
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/versions`)
  const data = await response.json()
  return data.data
}

export async function getGrouperConfigVersionDetail(versionId: string) {
  if (USE_MOCK_DATA) {
    const item = mockGrouperStore.versions.find((v) => v.version_id === versionId)
    if (!item) {
      throw new Error('版本不存在')
    }
    return item
  }

  const response = await fetch(
    `${API_V1_PREFIX}/drg/config/versions/${encodeURIComponent(versionId)}`,
  )
  const data = await response.json()
  return data.data
}

export async function rollbackGrouperConfig(params: {
  version_id: string
  operator: string
  change_summary: string
}) {
  if (USE_MOCK_DATA) {
    const version = mockGrouperStore.versions.find((item) => item.version_id === params.version_id)
    if (!version) {
      throw new Error('版本不存在')
    }
    mockGrouperStore.published_version_id = version.version_id
    mockGrouperStore.draft = { ...version.config }
    return Promise.resolve({
      version_id: version.version_id,
      operator: params.operator,
      operated_at: new Date().toISOString(),
      change_summary: params.change_summary,
      config: { ...version.config },
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

export async function runGrouperConsistencyCheck(params: {
  operator: string
  version_id?: string
  samples: GrouperConsistencySample[]
}) {
  if (USE_MOCK_DATA) {
    const validSamples = params.samples.filter(
      (item) => item.hospital_group && item.insurance_group,
    )
    const matched = validSamples.filter((item) => item.hospital_group === item.insurance_group)
    const differences = validSamples.filter((item) => item.hospital_group !== item.insurance_group)
    const consistencyRate =
      validSamples.length > 0
        ? Number(((matched.length / validSamples.length) * 100).toFixed(2))
        : 0
    return Promise.resolve({
      version_id: params.version_id || mockGrouperStore.published_version_id,
      operator: params.operator,
      operated_at: new Date().toISOString(),
      formula: '一致率 = 匹配成功样本数 / 有效对照样本数',
      summary: {
        matched_count: matched.length,
        valid_count: validSamples.length,
        consistency_rate: consistencyRate,
        difference_count: differences.length,
      },
      differences,
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/consistency-check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  const data = await response.json()
  return data.data
}

export async function listGrouperConfigAuditLogs(
  limit = 100,
): Promise<{ items: any[]; total: number }> {
  if (USE_MOCK_DATA) {
    const items = mockGrouperStore.versions.map((version) => ({
      action: 'publish',
      version_id: version.version_id,
      operator: version.operator,
      operated_at: version.operated_at,
      change_summary: version.change_summary,
    }))
    return Promise.resolve({ items, total: items.length })
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/config/audit-logs?limit=${limit}`)
  const data = await response.json()
  return data.data
}

// ==================== 医保结算清单 API ====================

import type { SettlementForm, SettlementBasicInfo } from '@/types/settlement'

/**
 * 根据病案号获取结算清单数据
 * 如果不存在则从病案首页自动转换
 */
export async function getSettlementForm(caseNumber: string): Promise<SettlementForm | null> {
  if (USE_MOCK_DATA) {
    // Mock: 从病案首页数据转换
    const caseFrontPage = getCaseFrontPageByAdmissionId(caseNumber)
    if (!caseFrontPage) return null

    return convertCaseFrontPageToSettlement(caseFrontPage)
  }

  const response = await fetch(`${API_V1_PREFIX}/settlement/${caseNumber}`)
  if (!response.ok) {
    if (response.status === 404) return null
    throw new Error(`获取结算清单失败: ${response.status}`)
  }
  return response.json()
}

/**
 * 保存结算清单
 */
export async function saveSettlementForm(
  data: SettlementForm,
): Promise<{ success: boolean; message: string }> {
  if (USE_MOCK_DATA) {
    console.log('[Mock] 保存结算清单:', data)
    return Promise.resolve({ success: true, message: '保存成功' })
  }

  const response = await fetch(`${API_V1_PREFIX}/settlement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  return response.json()
}

/**
 * 从病案首页自动生成结算清单草稿
 */
export async function generateSettlementFromCase(admissionId: string): Promise<SettlementForm> {
  if (USE_MOCK_DATA) {
    const caseFrontPage = getCaseFrontPageByAdmissionId(admissionId)
    if (!caseFrontPage) {
      throw new Error('病案首页不存在')
    }
    return convertCaseFrontPageToSettlement(caseFrontPage)
  }

  const response = await fetch(`${API_V1_PREFIX}/settlement/generate/${admissionId}`, {
    method: 'POST',
  })
  return response.json()
}

/**
 * 将病案首页数据转换为结算清单格式
 * 兼容 CaseFrontPage 类型和 mock 数据
 */
function convertCaseFrontPageToSettlement(caseFrontPage: any): SettlementForm {
  const diagnoses = getDiagnosesByFrontPageId(caseFrontPage.front_page_id)
  const procedures = getProceduresByFrontPageId(caseFrontPage.front_page_id)

  // 兼容两种数据结构
  const patientName = caseFrontPage.patient_name || ''
  const patientGender = caseFrontPage.patient_gender || caseFrontPage.gender
  const patientAge = caseFrontPage.patient_age ?? caseFrontPage.age ?? null
  const admissionDate = caseFrontPage.admission_date || ''
  const dischargeDate = caseFrontPage.discharge_date || ''
  const admissionDept = caseFrontPage.admission_department || ''
  const dischargeDept = caseFrontPage.discharge_department || ''
  const los = caseFrontPage.total_hospital_days ?? caseFrontPage.los ?? null
  const primaryDxName = caseFrontPage.primary_diagnosis_name || ''
  const primaryDxCode =
    caseFrontPage.primary_diagnosis_code || caseFrontPage.primary_diagnosis || ''
  const attendingDoc = caseFrontPage.attending_physician || ''
  const totalFee = caseFrontPage.total_cost ?? null

  return {
    basicInfo: {
      institutionName: '泸州市人民医院',
      institutionCode: 'H51050100001',
      serialNumber: `SN${Date.now()}`,
      insuranceNumber: caseFrontPage.patient_id || '',
      caseNumber: caseFrontPage.admission_id,
      settlementLevel: '三级甲等',
      reportDate: new Date().toISOString().slice(0, 10),
      patientName,
      gender:
        patientGender === 'M' || patientGender === '男'
          ? 1
          : patientGender === 'F' || patientGender === '女'
            ? 2
            : null,
      birthDate: '',
      age: patientAge,
      ageInDays: null,
      nationality: '中国',
      ethnicity: '汉族',
      idCardType: '01',
      idCardNumber: '',
      occupation: '',
      currentAddress: { province: '四川省', city: '泸州市', county: '', detail: '' },
      workUnit: '',
      workAddress: '',
      workPhone: '',
      workPostcode: '',
      contactName: '',
      contactRelation: '',
      contactAddress: { province: '', city: '', county: '', detail: '' },
      contactPhone: '',
      insuranceType: '310', // 城镇职工
      specialPersonType: '',
      insuredArea: '泸州市',
      newbornAdmissionType: '',
      newbornBirthWeight: null,
      newbornAdmissionWeight: null,
    },
    outpatientInfo: {
      department: admissionDept,
      visitDate: '',
      diagnosisRows: Array.from({ length: 3 }, (_, i) => ({
        id: i + 1,
        diagnosisName: '',
        diagnosisCode: '',
        procedureName: '',
        procedureCode: '',
      })),
    },
    inpatientInfo: {
      hospitalizationType: 1,
      admissionRoute: 2,
      treatmentCategory: 1,
      admissionTime: admissionDate,
      admissionDepartment: admissionDept,
      transferDepartment: '',
      dischargeTime: dischargeDate,
      dischargeDepartment: dischargeDept,
      actualLOS: los,
      emergencyWestDiagnosis: primaryDxName,
      emergencyWestCode: primaryDxCode,
      emergencyTCMDiagnosis: '',
      emergencyTCMCode: '',
      diagnosisRows: diagnoses.slice(0, 10).map((d: any, i: number) => ({
        id: i + 1,
        westDiagnosis: d.diagnosis_name,
        westCode: d.diagnosis_code,
        admissionCondition: '',
        tcmDiagnosis: '',
        tcmCode: '',
        tcmAdmissionCondition: '',
      })),
      diagnosisCount: diagnoses.length,
      surgeryRows: procedures.slice(0, 5).map((p: any, i: number) => ({
        id: i + 1,
        name: p.procedure_name,
        code: p.procedure_code,
        date: p.procedure_date || '',
        startTime: '',
        endTime: '',
        anesthesiaStartTime: '',
        anesthesiaEndTime: '',
        anesthesiaMethod: '',
        surgeonName: '',
        surgeonCode: '',
        anesthesiologistName: '',
        anesthesiologistCode: '',
      })),
      surgeryCount: procedures.length,
      ventilatorDays: null,
      ventilatorHours: null,
      ventilatorMinutes: null,
      ventilatorDuration: null,
      comaBeforeAdmission: { days: null, hours: null, minutes: null },
      comaAfterAdmission: { days: null, hours: null, minutes: null },
      icuRows: [],
      icuRecords: [],
      transfusionRecords: [],
      bloodType: '',
      bloodVolume: '',
      bloodUnit: '',
      specialNursingDays: null,
      level1NursingDays: null,
      level2NursingDays: null,
      level3NursingDays: null,
      dischargeMethod: 1,
      transferInstitutionName: '',
      transferInstitutionCode: '',
      hasReadmissionPlan: 1,
      readmissionPurpose: '',
      primaryNurseName: '',
      primaryNurseCode: '',
      attendingPhysicianName: attendingDoc,
      attendingPhysicianCode: '',
    },
    feeInfo: {
      businessSerialNumber: '',
      invoiceCode: '',
      invoiceNumber: '',
      settlementPeriod: {
        start: admissionDate,
        end: dischargeDate,
      },
      feeItems: [],
      totalAmount: {
        itemName: '合计',
        amount: totalFee,
        classA: null,
        classB: null,
        selfPay: null,
        other: null,
      },
      fundPayments: [],
      personalSelfPay: null,
      personalSelfExpense: null,
      personalAccountPay: null,
      personalCashPay: null,
      paymentMethod: [4], // 默认 DRG
    },
    reportingDepartment: '病案室',
    reportingPerson: '',
    insuranceAgency: '泸州市医疗保障局',
    insuranceAgent: '',
  }
}

// ==================== 导出配置 ====================

export const drgApi = {
  // 病案首页
  getCaseFrontPages,
  getCaseFrontPageDetail,
  saveCaseFrontPage,

  // 编码辅助
  suggestCoding,
  validateCoding,
  searchICDCodes,

  // DRG 分组
  // DRG/DIP 分组
  predictDRGGrouping,
  predictDIPGrouping,
  getGroupingHistory,

  // 编码建议
  getCodingSuggestions,
  handleCodingSuggestion,

  // 监控预警
  getDRGAlerts,
  handleDRGAlert,

  // 统计分析
  getAnalysisData,
  exportAnalysisData,

  // 6.2.2 分组器本地化配置
  getGrouperConfigCurrent,
  saveGrouperConfigDraft,
  publishGrouperConfig,
  listGrouperConfigVersions,
  getGrouperConfigVersionDetail,
  rollbackGrouperConfig,
  runGrouperConsistencyCheck,
  listGrouperConfigAuditLogs,

  // 医保结算清单
  getSettlementForm,
  saveSettlementForm,
  generateSettlementFromCase,
}

export default drgApi
