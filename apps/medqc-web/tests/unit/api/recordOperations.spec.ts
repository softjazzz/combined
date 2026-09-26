import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCaseOperations, isKnownCaseOperation } from '@/api/recordOperations'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T, status = 200): AxiosResponse<T> {
  return { data, status, statusText: 'OK', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } }
}

function httpError(status: number, data: unknown) {
  return new AxiosError('failed', 'ERR_BAD_RESPONSE', undefined, undefined, response(data, status))
}

describe('病历操作记录 API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('以三坐标与默认 limit=100 查询，成功时解包 data', async () => {
    const data = { items: [], total: 0, limit: 100 }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data }))
    await expect(getCaseOperations({ institute_id: 'H', patient_id: 'P', visit_id: 'V/1' }))
      .resolves.toMatchObject({ success: true, data, status: 200 })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/record-operations/case',
      params: { institute_id: 'H', patient_id: 'P', visit_id: 'V/1', limit: 100 },
    })
  })

  it('显式 limit 原样透传', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: { items: [], total: 0, limit: 20 } }))
    await getCaseOperations({ institute_id: 'H', patient_id: 'P', visit_id: 'V', limit: 20 })
    expect(vi.mocked(ApiService.requestRaw).mock.calls[0][0]).toMatchObject({ params: { limit: 20 } })
  })

  it('403 保留状态码；503 返回失败文案且不抛错', async () => {
    vi.mocked(ApiService.requestRaw)
      .mockRejectedValueOnce(httpError(403, { detail: '没有权限' }))
      .mockRejectedValueOnce(httpError(503, { success: false, error: '操作记录暂不可用' }))
    const query = { institute_id: 'H', patient_id: 'P', visit_id: 'V' }
    await expect(getCaseOperations(query)).resolves.toMatchObject({ success: false, status: 403 })
    const failed = await getCaseOperations(query)
    expect(failed).toMatchObject({ success: false, status: 503 })
    expect(failed.message).toBeTruthy()
  })

  it('isKnownCaseOperation 区分已知与未知类型', () => {
    const base = { id: 'x', occurred_at: null, actor_id: null, actor_name: null }
    expect(isKnownCaseOperation({ ...base, type: 'record_review', summary: {} })).toBe(true)
    expect(isKnownCaseOperation({ ...base, type: 'future_event', summary: null })).toBe(false)
  })
})
