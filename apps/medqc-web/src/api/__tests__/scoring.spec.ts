import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  activateScoringStandard,
  archiveScoringStandard,
  copyScoringStandard,
  createScoringStandard,
  deleteScoringStandard,
  getCaseScore,
  getScoringStandard,
  listScoringScenes,
  listScoringStandards,
  saveScoringItems,
  setDefaultScoringStandard,
  updateScoringStandard,
} from '@/api/scoring'

function envelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

function httpError(status: number, body: unknown) {
  const response = { status, data: body, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } } as AxiosResponse
  return new AxiosError('failed', String(status), undefined, undefined, response)
}

const bands = [
  { name: '甲', min_score: 90, max_score: 100 },
  { name: '乙', min_score: 0, max_score: 90 },
]

describe('scoring API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('按合同路径读取场景、列表、详情与单病历得分', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({ items: [] }))
    await listScoringScenes()
    await listScoringStandards({ scene: 'running', status: 'active' })
    await listScoringStandards()
    await getScoringStandard('id/1')
    await getCaseScore({ institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'final' })
    expect(spy.mock.calls[0]?.[0]).toMatchObject({ method: 'GET', url: '/api/v1/scoring/scenes' })
    expect(spy.mock.calls[1]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards', params: { scene: 'running', status: 'active' } })
    expect(spy.mock.calls[2]?.[0].params).toEqual({})
    expect(spy.mock.calls[3]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards/id%2F1' })
    expect(spy.mock.calls[4]?.[0]).toMatchObject({
      url: '/api/v1/scoring/case',
      params: { institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'final' },
    })
  })

  it('写接口只发送合同字段并带 version_seq', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({}))
    await createScoringStandard({
      name: '标准', scene: 'running', base_score: 100, veto_grade: '乙',
      grade_bands: bands.map((band) => ({ ...band, extra: 1 })) as typeof bands,
    })
    await updateScoringStandard('s1', { version_seq: 2, name: '新名' })
    await saveScoringItems('s1', {
      version_seq: 3,
      groups: [{ group_name: '病程', max_deduction: null, sort_order: 1, key: 'x' } as never],
      items: [{ group_name: '病程', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true, key: 'y' } as never],
    })
    await copyScoringStandard('s1', '副本')
    await activateScoringStandard('s1', { version_seq: 4, replace_mode: 'undefault' })
    await setDefaultScoringStandard('s1', { version_seq: 5, replace_mode: 'archive' })
    await archiveScoringStandard('s1', 6)
    await deleteScoringStandard('s1', 7)
    expect(spy.mock.calls[0]?.[0]).toMatchObject({ method: 'POST', url: '/api/v1/scoring/standards' })
    expect((spy.mock.calls[0]?.[0].data as { grade_bands: object[] }).grade_bands[0]).toEqual(bands[0])
    expect(spy.mock.calls[1]?.[0]).toMatchObject({ method: 'PUT', url: '/api/v1/scoring/standards/s1', data: { version_seq: 2, name: '新名' } })
    expect(spy.mock.calls[2]?.[0]).toMatchObject({ method: 'PUT', url: '/api/v1/scoring/standards/s1/items' })
    expect(spy.mock.calls[2]?.[0].data).toEqual({
      version_seq: 3,
      groups: [{ group_name: '病程', max_deduction: null, sort_order: 1 }],
      items: [{ group_name: '病程', rule_id: 'LX0609-001', deduction: 2, is_veto: false, enabled: true }],
    })
    expect(spy.mock.calls[3]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards/s1/copy', data: { name: '副本' } })
    expect(spy.mock.calls[4]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards/s1/activate', data: { version_seq: 4, replace_mode: 'undefault' } })
    expect(spy.mock.calls[5]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards/s1/set-default', data: { version_seq: 5, replace_mode: 'archive' } })
    expect(spy.mock.calls[6]?.[0]).toMatchObject({ url: '/api/v1/scoring/standards/s1/archive', data: { version_seq: 6 } })
    expect(spy.mock.calls[7]?.[0]).toMatchObject({ method: 'DELETE', params: { version_seq: 7 } })
  })

  it('解析 409 业务 code 与 422 problems（error 与 detail 两种形态）', async () => {
    const detail = { code: 'items_validation_failed', message: '评分条目校验未通过', problems: ['规则重复：LX0609-001'] }
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(409, { success: false, error: { code: 'version_conflict', message: '评分标准已被修改，请刷新后重试' } }))
      .mockRejectedValueOnce(httpError(422, { success: false, error: detail }))
      .mockRejectedValueOnce(httpError(422, { detail }))
    expect(await saveScoringItems('s1', { version_seq: 1, groups: [], items: [] })).toMatchObject({
      success: false, status: 409, code: 'version_conflict', message: '评分标准已被修改，请刷新后重试',
    })
    for (let index = 0; index < 2; index += 1) {
      expect(await saveScoringItems('s1', { version_seq: 1, groups: [], items: [] })).toMatchObject({
        success: false, status: 422, code: 'items_validation_failed', problems: detail.problems,
      })
    }
  })

  it('403/503 与网络异常回退到消息文本', async () => {
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(503, { success: false, error: '评分服务暂不可用，请稍后重试' }))
      .mockRejectedValueOnce(httpError(403, { detail: '权限不足' }))
      .mockRejectedValueOnce(new Error('Network Error'))
    expect(await getCaseScore({ institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'running' }))
      .toMatchObject({ success: false, status: 503, message: '评分服务暂不可用，请稍后重试', code: undefined })
    expect(await getCaseScore({ institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'running' }))
      .toMatchObject({ success: false, status: 403, message: '权限不足' })
    const network = await listScoringStandards()
    expect(network.success).toBe(false)
    expect(network.status).toBeUndefined()
  })
})
