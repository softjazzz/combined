import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getAdminRecordList } from '@/api/qcAdmin'
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
})
