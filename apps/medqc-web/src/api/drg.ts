/**
 * DRG 模块 API 服务
 * 支持 Mock 模式和真实 API 模式切换
 */

import type {
  CaseFrontPage,
  CaseFrontPageDiagnosis,
  CaseFrontPageProcedure
} from '../data/drg/mock-case-front-page'
import type { DRGGrouping, CodingSuggestion, DRGAlert } from '../data/drg/mock-drg-grouping'
import type { ICDCode } from '../data/drg/mock-icd-codes'

// Mock 数据导入（开发阶段使用）
import {
  mockCaseFrontPages,
  getCaseFrontPageByAdmissionId,
  getDiagnosesByFrontPageId,
  getProceduresByFrontPageId
} from '../data/drg/mock-case-front-page'

import {
  mockDRGGroupings,
  getLatestGroupingByAdmissionId,
  getSuggestionsByAdmissionId,
  getAlertsByAdmissionId
} from '../data/drg/mock-drg-grouping'

import {
  suggestICDCodes,
  searchICD10Codes,
  searchICD9Procedures
} from '../data/drg/mock-icd-codes'

// 配置：是否使用 Mock 数据
const USE_MOCK_DATA = import.meta.env.VITE_USE_DRG_MOCK === 'true' || true // 默认使用 Mock

// ==================== 类型定义 ====================

export interface ICDSuggestion {
  code: string
  name: string
  confidence: number
  note: string | null
}

export interface ValidationResult {
  is_valid: boolean
  warnings: Array<{
    type: string
    message: string
    evidence?: string
    severity: 'info' | 'warning' | 'error'
  }>
  conflicts: Array<{
    type: string
    message: string
  }>
}

export interface DRGPredictionResult {
  adrg_code: string
  adrg_name: string
  drg_code: string
  drg_name: string
  weight: number
  baseline_payment: number
  expected_los: { min: number; max: number }
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  grouping_logic: string
}

// ==================== 病案首页相关 API ====================

/**
 * 获取病案首页列表
 */
export async function getCaseFrontPages(): Promise<CaseFrontPage[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(mockCaseFrontPages)
  }

  // TODO: 调用真实 API
  const response = await fetch('/api/v1/case-front-page')
  return response.json()
}

/**
 * 根据 admission_id 获取病案首页详情
 */
export async function getCaseFrontPageDetail(admissionId: string) {
  if (USE_MOCK_DATA) {
    return Promise.resolve(getCaseFrontPageByAdmissionId(admissionId))
  }

  // TODO: 调用真实 API
  const response = await fetch(`/api/v1/case-front-page/${admissionId}`)
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

  // TODO: 调用真实 API
  const response = await fetch('/api/v1/case-front-page', {
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
}): Promise<ICDSuggestion[]> {
  if (USE_MOCK_DATA) {
    // Mock: 使用本地模拟函数
    const suggestions = suggestICDCodes(params.diagnosis_name)
    return Promise.resolve(
      suggestions.map(s => ({
        code: s.code,
        name: s.name,
        confidence: s.confidence,
        note: s.notes
      }))
    )
  }

  // TODO: 调用真实 FastAPI
  const response = await fetch('/api/v1/coding/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const data = await response.json()
  return data.candidates
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

  // TODO: 调用真实 FastAPI
  const response = await fetch('/api/v1/coding/validate', {
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
  query: string
  type: 'diagnosis' | 'procedure'
}): Promise<ICDCode[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(
      params.type === 'diagnosis'
        ? searchICD10Codes(params.query)
        : searchICD9Procedures(params.query)
    )
  }

  // TODO: 调用真实 API
  const response = await fetch(`/api/v1/icd/search?query=${params.query}&type=${params.type}`)
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
}): Promise<DRGPredictionResult> {
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
    })
  }

  // TODO: 调用真实 FastAPI（调用 OpenDRG）
  const response = await fetch('/api/v1/drg/predict', {
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
export async function getGroupingHistory(admissionId: string): Promise<DRGGrouping[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(
      mockDRGGroupings.filter(g => g.admission_id === admissionId)
    )
  }

  // TODO: 调用真实 API
  const response = await fetch(`/api/v1/drg/grouping/${admissionId}/history`)
  return response.json()
}

// ==================== 编码建议相关 API ====================

/**
 * 获取编码优化建议
 */
export async function getCodingSuggestions(admissionId: string): Promise<CodingSuggestion[]> {
  if (USE_MOCK_DATA) {
    return Promise.resolve(getSuggestionsByAdmissionId(admissionId))
  }

  // TODO: 调用真实 API
  const response = await fetch(`/api/v1/coding/suggestions/${admissionId}`)
  return response.json()
}

/**
 * 处理编码建议（接受/拒绝）
 */
export async function handleCodingSuggestion(params: {
  suggestion_id: number
  action: 'accept' | 'reject'
}): Promise<void> {
  if (USE_MOCK_DATA) {
    console.log('[Mock] 处理编码建议:', params)
    return Promise.resolve()
  }

  // TODO: 调用真实 API
  await fetch(`/api/v1/coding/suggestions/${params.suggestion_id}/${params.action}`, {
    method: 'POST'
  })
}

// ==================== 监控预警相关 API ====================

/**
 * 获取预警列表
 */
export async function getDRGAlerts(params?: {
  status?: 'pending' | 'acknowledged' | 'resolved'
}): Promise<DRGAlert[]> {
  if (USE_MOCK_DATA) {
    let alerts = [...mockDRGAlerts]
    if (params?.status) {
      alerts = alerts.filter(a => a.status === params.status)
    }
    return Promise.resolve(alerts)
  }

  // TODO: 调用真实 API
  const queryString = params?.status ? `?status=${params.status}` : ''
  const response = await fetch(`/api/v1/drg/alerts${queryString}`)
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
  predictDRGGrouping,
  getGroupingHistory,

  // 编码建议
  getCodingSuggestions,
  handleCodingSuggestion,

  // 监控预警
  getDRGAlerts
}

export default drgApi
