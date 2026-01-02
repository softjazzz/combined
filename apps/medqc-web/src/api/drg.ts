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
  ValidationResult
} from '@/types/drg'
import type { AnalysisDimension, AnalysisDataResponse } from '@/types/drg-analysis'

// Mock 数据导入（开发阶段使用）
import {
  mockCaseFrontPages,
  getCaseFrontPageByAdmissionId,
  getDiagnosesByFrontPageId,
  getProceduresByFrontPageId
} from '../data/drg/mock-case-front-page'

import {
  mockDRGGroupings,
  mockCodingSuggestions,
  mockDRGAlerts,
  getLatestGroupingByAdmissionId,
} from '../data/drg/mock-drg-grouping'

import {
  suggestICDCodes,
  searchICD10Codes,
  searchICD9Procedures
} from '../data/drg/mock-icd-codes'

import { mockAnalysisData } from '../data/drg/mock-analysis'

// 配置：是否使用 Mock 数据
const USE_MOCK_DATA = (import.meta as any).env?.VITE_USE_DRG_MOCK !== 'false' // 默认使用 Mock；设置为 "false" 可切到真实 API

const API_V1_PREFIX = '/api/v1'

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

    const diagnoses = getDiagnosesByFrontPageId(frontPage.front_page_id).map(d => ({
      code: d.diagnosis_code,
      name: d.diagnosis_name,
      sequence: d.sequence,
      is_complication: d.is_complication
    }))

    const procedures = getProceduresByFrontPageId(frontPage.front_page_id).map(p => ({
      code: p.procedure_code,
      name: p.procedure_name,
      sequence: p.sequence,
      procedure_date: p.procedure_date
    }))

    return Promise.resolve({
      ...frontPage,
      secondary_diagnoses: diagnoses,
      procedures
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
      ...data
    } as CaseFrontPage)
  }

  const response = await fetch(`${API_V1_PREFIX}/case-front-page`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
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
    const candidates = suggestions.map(s => ({
      code: s.code,
      name: s.name,
      confidence: s.confidence,
      note: s.notes
    }))
    return Promise.resolve({ candidates, total: candidates.length })
  }

  const response = await fetch(`${API_V1_PREFIX}/coding/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
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
          message: '病程记录中提到\'心力衰竭\'，建议补充次诊断：I50.001（心力衰竭）',
          evidence: '病程记录第3天：患者出现呼吸困难，双肺底湿啰音，考虑心力衰竭...',
          severity: 'info'
        }
      ],
      conflicts: []
    })
  }

  const response = await fetch(`${API_V1_PREFIX}/coding/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
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
    `${API_V1_PREFIX}/coding/search?keyword=${encodeURIComponent(params.keyword)}&category=${params.category}&limit=${params.limit ?? 20}`
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
      grouping_logic: `主诊断${grouping.adrg_code} + 合并症`
    } as any)
  }

  const response = await fetch(`${API_V1_PREFIX}/drg/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const data = await response.json()
  return data.data
}

/**
 * DIP 入组预测
 */
export async function predictDIPGrouping(params: import('@/types/drg').DIPPredictRequest): Promise<import('@/types/drg').DIPGroupingResult> {
  if (USE_MOCK_DATA) {
    // Mock logic if needed, or throw error saying Mock not supported for DIP yet
    throw new Error('DIP Mock mode not implemented in frontend, please use real API')
    // Or return a mock object
  }

  const response = await fetch(`${API_V1_PREFIX}/dip/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
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
        .filter(g => g.admission_id === admissionId)
        .map(g => ({
          grouping_id: g.grouping_id,
          drg_code: g.drg_code,
          drg_name: g.drg_name,
          weight: g.weight,
          baseline_payment: g.baseline_payment,
          actual_cost: g.actual_cost,
          profit_margin: g.profit_margin,
          version: g.version,
          is_latest: g.is_latest,
          grouped_at: g.grouped_at
        })) as any
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
      suggestions = suggestions.filter(s => s.admission_id === params.admission_id)
    }
    if (params?.status) {
      suggestions = suggestions.filter(s => s.status === params.status)
    }
    const limited = typeof params?.limit === 'number' ? suggestions.slice(0, params.limit) : suggestions
    return Promise.resolve({ suggestions: limited as any, total: limited.length })
  }

  const qs = new URLSearchParams()
  if (params?.admission_id) qs.set('admission_id', params.admission_id)
  if (params?.status) qs.set('status', params.status)
  if (typeof params?.limit === 'number') qs.set('limit', String(params.limit))

  const response = await fetch(`${API_V1_PREFIX}/drg/suggestions${qs.toString() ? `?${qs.toString()}` : ''}`)
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
      handled_by: params.handled_by || 'current_user'
    })
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
      alerts = alerts.filter(a => a.admission_id === params.admission_id)
    }
    if (params?.alert_level) {
      alerts = alerts.filter(a => a.alert_level === params.alert_level)
    }
    if (params?.status) {
      alerts = alerts.filter(a => a.status === params.status)
    }
    const limited = typeof params?.limit === 'number' ? alerts.slice(0, params.limit) : alerts
    return Promise.resolve({ alerts: limited as any, total: limited.length })
  }

  const qs = new URLSearchParams()
  if (params?.admission_id) qs.set('admission_id', params.admission_id)
  if (params?.alert_level) qs.set('alert_level', params.alert_level)
  if (params?.status) qs.set('status', params.status)
  if (typeof params?.limit === 'number') qs.set('limit', String(params.limit))

  const response = await fetch(`${API_V1_PREFIX}/drg/alerts${qs.toString() ? `?${qs.toString()}` : ''}`)
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
      handled_by: params.handled_by || 'current_user'
    })
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
}): Promise<AnalysisDataResponse> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockAnalysisData(params.dimension))
  }

  const qs = new URLSearchParams({
    dimension: params.dimension,
    start_date: params.startDate,
    end_date: params.endDate
  })
  if (params.filterId) qs.set('filter_id', params.filterId)

  const response = await fetch(`${API_V1_PREFIX}/drg/analysis?${qs.toString()}`)
  return response.json()
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
  getAnalysisData
}

export default drgApi
