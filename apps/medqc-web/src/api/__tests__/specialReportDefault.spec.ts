import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { getSpecialReportDefault, setSpecialReportDefault } from '../scoring'

function envelope(data: unknown) {
  return { data: { success: true, data }, status: 200 } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

beforeEach(() => vi.restoreAllMocks())
describe('专用默认评分标准API', () => {
  it('只在final用途入口读取，绑定未知不造fallback', async () => {
    const data = { purpose: 'special_report', execution_scene: 'final', version_seq: 2, standard_id: 'gone', standard_version_seq: 3, status: 'unavailable', standard: null }
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope(data))
    expect((await getSpecialReportDefault()).data).toEqual(data)
    expect(spy).toHaveBeenCalledWith({ method: 'GET', url: '/api/v1/scoring/defaults/special-report', params: { scene: 'final' } })
  })
  it('保存只传绑定CAS与目标标准CAS，解除绑定保留null', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({}))
    await setSpecialReportDefault({ version_seq: 2, standard_id: 'S', standard_version_seq: 3 })
    await setSpecialReportDefault({ version_seq: 3, standard_id: null, standard_version_seq: null })
    expect(spy.mock.calls[0][0]).toMatchObject({ method: 'PUT', params: { scene: 'final' }, data: { version_seq: 2, standard_id: 'S', standard_version_seq: 3 } })
    expect(spy.mock.calls[1][0].data).toEqual({ version_seq: 3, standard_id: null, standard_version_seq: null })
  })
  it('不完整绑定不能作为已保存成功回执', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({}))
    expect((await getSpecialReportDefault()).success).toBe(false)
    expect(await setSpecialReportDefault({ version_seq: 0, standard_id: 'S', standard_version_seq: 1 }))
      .toMatchObject({ success: false, status: 200 })
  })
})
