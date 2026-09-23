import { AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getRecordDetail } from '@/api/qcAdmin'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

describe('getRecordDetail 质控详情合同', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('成功时仅请求质控详情', async () => {
    const detail = { record_id: 'record-1', defects: [{ id: 'defect-1' }] }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: detail }))

    await expect(getRecordDetail('record-1')).resolves.toEqual({
      success: true,
      data: detail,
      message: undefined,
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record-1/qc-detail',
    })
  })

  it('服务返回失败信封时原样传递失败，不降级到内存单记录', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(
      response({ success: false, message: '质控详情暂不可用' }),
    )

    await expect(getRecordDetail('record-1')).resolves.toEqual({
      success: false,
      data: undefined,
      message: '质控详情暂不可用',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record-1/qc-detail',
    })
  })

  it('503 时保留错误提示，不把内存单记录伪装成完整质控详情', async () => {
    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce({
      response: { status: 503, data: { detail: '质控详情数据源不可用' } },
    })

    await expect(getRecordDetail('record-1')).resolves.toEqual({
      success: false,
      message: '质控详情数据源不可用',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledTimes(1)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/records/record-1/qc-detail',
    })
  })
})
