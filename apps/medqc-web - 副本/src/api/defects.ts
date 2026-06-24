/**
 * 缺陷操作 API 服务
 *
 * 提供缺陷的催办、撤回、标记整改、审核通过、审核存疑等操作
 */

import { ApiService } from '@/services/apiService'
import {
  extractApiErrorMessageFromError,
  normalizeApiSuccess,
} from '@/utils/api-envelope'

const BASE_URL = '/api/v1/qc/defects'

async function request<T = any>(
  config: Parameters<typeof ApiService.requestRaw>[0],
): Promise<{ success: boolean; data?: T; message?: string }> {
  try {
    const response = await ApiService.requestRaw<T>(config)
    const normalized = normalizeApiSuccess<T>(response.data)
    return {
      success: normalized.success,
      data: normalized.data,
      message: normalized.message,
    }
  } catch (error) {
    return {
      success: false,
      message: extractApiErrorMessageFromError(error, '网络异常或服务器不可用'),
    }
  }
}

// ============= 类型定义 =============

export interface DefectItem {
  id: string
  record_id: string
  patient_name?: string
  department?: string
  rule_name: string
  description: string
  severity: 'critical' | 'error' | 'warning' | 'info'
  category: string
  location: string
  suggestion: string
  status: 'pending' | 'urged' | 'remediated' | 'approved' | 'rejected'
  created_at: string
  urged_at?: string
  remediated_at?: string
  approved_at?: string
}

export interface DefectListResponse {
  items: DefectItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DefectStats {
  total: number
  by_severity: Record<string, number>
  by_category: Record<string, number>
  by_status: Record<string, number>
}

// ============= API 函数 =============

/** 获取缺陷列表 */
export async function getDefectList(params?: {
  record_id?: string
  department?: string
  severity?: string
  category?: string
  status?: string
  start_date?: string
  end_date?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${BASE_URL}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<DefectListResponse>({
    method: 'GET',
    url,
  })
}

/** 催办缺陷 */
export async function urgeDefect(defectId: string, data: { message?: string; deadline?: string }) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/${defectId}/urge`,
    data: {
      message: data.message || '请尽快完成整改',
      deadline: data.deadline,
    },
  })
}

/** 撤回催办 */
export async function cancelUrgeDefect(defectId: string, reason?: string) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/${defectId}/cancel-urge`,
    data: { reason },
  })
}

/** 标记已整改 */
export async function markDefectRemediated(
  defectId: string,
  data: { remediation_note: string; evidence?: string[] },
) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/${defectId}/mark-remediated`,
    data,
  })
}

/** 审核通过 */
export async function approveDefect(defectId: string, comment?: string) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/${defectId}/approve`,
    data: { comment },
  })
}

/** 审核存疑（退回） */
export async function rejectDefect(defectId: string, data: { reason: string; suggestion?: string }) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/${defectId}/reject`,
    data,
  })
}

/** 批量操作 */
export async function batchDefectAction(data: {
  defect_ids: string[]
  action: 'approve' | 'reject' | 'urge'
  message?: string
}) {
  return request({
    method: 'POST',
    url: `${BASE_URL}/batch-action`,
    data,
  })
}

/** 导出缺陷列表 */
export function getDefectExportUrl(params?: {
  format?: string
  max_rows?: number
  record_id?: string
  department?: string
  severity?: string
  category?: string
  status?: string
  start_date?: string
  end_date?: string
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  return `${BASE_URL}/export${queryParams.toString() ? '?' + queryParams.toString() : ''}`
}

/** 下载导出文件 */
export async function exportDefects(params?: Parameters<typeof getDefectExportUrl>[0]) {
  const url = getDefectExportUrl(params)
  try {
    const response = await ApiService.getRaw<Blob>(url, undefined, {
      responseType: 'blob',
    })
    const blob = response.data
    const disposition = response.headers['content-disposition']
    const filename =
      disposition?.match(/filename="?(.+?)"?$/)?.[1] || `缺陷列表.${params?.format || 'xlsx'}`
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    return { success: true, message: '导出成功' }
  } catch (error) {
    return { success: false, message: extractApiErrorMessageFromError(error, '导出失败') }
  }
}

/** 获取缺陷统计 */
export async function getDefectStats(params?: {
  record_id?: string
  department?: string
  start_date?: string
  end_date?: string
}) {
  const queryParams = new URLSearchParams()
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value))
      }
    })
  }
  const url = `${BASE_URL}/stats${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  return request<DefectStats>({
    method: 'GET',
    url,
  })
}
