import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  activateScoringStandard,
  archiveScoringStandard,
  copyScoringStandard,
  createScoringStandard,
  deleteScoringStandard,
  exportScoringStandard,
  getCaseScore,
  getScoringStandard,
  listScoringScenes,
  listScoringStandards,
  importScoringStandard,
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

  it('导出请求读取 Blob；导入使用 multipart 并确认草稿响应', async () => {
    const detail = {
      id: 'new-1', name: '导入草稿', scene: 'running', rule_set_key: 'luxian_0609_qc_v1',
      status: 'draft', is_default: false, base_score: 100, grade_bands: bands, veto_grade: '乙',
      version_seq: 1, created_by: 'u1', created_at: null, updated_by: 'u1', updated_at: null,
      activated_by: null, activated_at: null, groups: [], items: [], group_count: 0, item_count: 0,
    }
    const blob = new Blob(['xlsx'])
    const spy = vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce({ status: 200, data: blob } as Awaited<ReturnType<typeof ApiService.requestRaw>>)
      .mockResolvedValueOnce(envelope(detail))

    expect(await exportScoringStandard('id/1')).toMatchObject({ success: true, data: blob })
    const imported = await importScoringStandard(new File(['xlsx'], 'standard.xlsx'))
    expect(imported).toMatchObject({ success: true, data: detail, resultUnknown: false })
    expect(spy.mock.calls[0]?.[0]).toMatchObject({
      method: 'GET', url: '/api/v1/scoring/standards/id%2F1/export', responseType: 'blob',
    })
    expect(spy.mock.calls[1]?.[0]).toMatchObject({ method: 'POST', url: '/api/v1/scoring/standards/import' })
    expect(spy.mock.calls[1]?.[0].data).toBeInstanceOf(FormData)
  })

  it('导入422返回逐行问题；5xx与异常200均锁定为结果未知', async () => {
    const problems = [{ sheet: '评分条目', row: 3, field: '规则ID', code: 'rule_duplicate', message: '规则重复' }]
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(422, {
        detail: { code: 'excel_validation_failed', message: '校验未通过', problems },
      }))
      .mockRejectedValueOnce(httpError(503, { detail: '暂不可用' }))
      .mockResolvedValueOnce(envelope({ status: 'draft' }))
    const file = new File(['xlsx'], 'standard.xlsx')

    expect(await importScoringStandard(file)).toMatchObject({
      success: false, status: 422, code: 'excel_validation_failed', problems, resultUnknown: false,
    })
    const unavailable = await importScoringStandard(file)
    expect(unavailable.resultUnknown).toBe(true)
    expect(unavailable.message).toContain('可能已写入')
    const malformed = await importScoringStandard(file)
    expect(malformed.resultUnknown).toBe(true)
    expect(malformed.message).toContain('无法确认新草稿')
  })

  it('导入在客户端拒绝扩展名和超限文件，不发请求', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw')
    expect((await importScoringStandard(new File(['x'], 'standard.csv'))).resultUnknown).toBe(false)
    expect((await importScoringStandard(new File([new Uint8Array(2 * 1024 * 1024 + 1)], 'standard.xlsx'))).message)
      .toContain('2 MiB')
    expect(spy).not.toHaveBeenCalled()
  })
})
