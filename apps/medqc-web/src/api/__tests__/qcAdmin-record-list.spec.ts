import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  exportOutpatientEmergencyRecords,
  getAdminRecordList,
  getFinalRecordList,
  getOutpatientEmergencyRecordList,
} from '@/api/qcAdmin'
import { ApiService } from '@/services/apiService'

describe('getAdminRecordList', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it.each([undefined, 'running', 'final'] as const)(
    '拒绝场景 %s，且不发送病历或任务请求',
    async (scene) => {
      const request = vi.spyOn(ApiService, 'requestRaw')
      const response = await getAdminRecordList(scene ? { scene } : undefined)

      expect(response.success).toBe(false)
      expect(response.message).toContain('此旧试跑入口无法确认')
      expect(request).not.toHaveBeenCalled()
    },
  )

  it('门急诊仍请求病历接口，不请求任务列表', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce({
      data: { success: true, data: { items: [], total: 0, page: 1, page_size: 10 } },
    } as never)

    const response = await getAdminRecordList({ scene: 'outpatient_emergency', page: 1 })

    expect(response.success).toBe(true)
    expect(request).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/outpatient-emergency?scene=outpatient_emergency&page=1',
    })
  })

  it('终末未核实筛选准确序列化到专用列表接口', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce({
      data: { success: true, data: { items: [], total: 0, page: 1, page_size: 10 } },
    } as never)

    const response = await getFinalRecordList({ status: 'unverified', page: 2 })

    expect(response.success).toBe(true)
    expect(request).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/final?status=unverified&page=2',
    })
  })

  it('门急诊列表与导出使用同一组业务筛选，导出不带分页', async () => {
    const csv = new Blob(['\ufeff病历号,姓名\r\nA,张三'], { type: 'text/csv;charset=utf-8' })
    const request = vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce({
        data: { success: true, data: { items: [], total: 0, page: 2, page_size: 20 } },
      } as never)
      .mockResolvedValueOnce({
        status: 200,
        data: csv,
        headers: {
          'content-type': 'text/csv; charset=utf-8',
          'content-disposition': "attachment; filename*=UTF-8''outpatient-records.csv",
        },
      } as never)
    const filters = {
      keyword: '张三', department: '急诊科', status: 'pending',
      start_date: '2026-09-01', end_date: '2026-09-28', scoring_standard: 'standard-v1',
      sort_field: 'visit_date' as const, sort_order: 'desc' as const,
    }

    await getOutpatientEmergencyRecordList({ ...filters, page: 2, page_size: 20 })
    const exported = await exportOutpatientEmergencyRecords(filters)

    expect(request).toHaveBeenNthCalledWith(1, {
      method: 'GET',
      url: '/api/v1/records/outpatient-emergency?keyword=%E5%BC%A0%E4%B8%89&department=%E6%80%A5%E8%AF%8A%E7%A7%91&status=pending&start_date=2026-09-01&end_date=2026-09-28&scoring_standard=standard-v1&sort_field=visit_date&sort_order=desc&page=2&page_size=20',
    })
    expect(request).toHaveBeenNthCalledWith(2, expect.objectContaining({
      method: 'GET',
      url: '/api/v1/records/outpatient-emergency/export',
      params: filters,
      responseType: 'blob',
    }))
    expect(exported).toEqual({ success: true, blob: csv, filename: 'outpatient-records.csv' })
  })

  it('门急诊导出拒绝把JSON错误响应下载成CSV', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValueOnce({
      status: 413,
      data: new Blob([JSON.stringify({ detail: { message: '导出结果超过10000条，请缩小筛选范围' } })], {
        type: 'application/json',
      }),
      headers: { 'content-type': 'application/json' },
    } as never)

    const result = await exportOutpatientEmergencyRecords({})

    expect(result).toEqual({
      success: false,
      message: '导出结果超过10000条，请缩小筛选范围',
      status: 413,
    })
  })
})
