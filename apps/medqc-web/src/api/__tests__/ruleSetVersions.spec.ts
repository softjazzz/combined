import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  createRuleSetDraft,
  deleteRuleSetDraft,
  getRuleSetVersion,
  listRuleSetVersions,
  publishRuleSetDraft,
  retireRuleSetVersion,
  updateRuleSetDraft,
} from '@/api/ruleSetVersions'

const KEY = 'luxian_0609_qc_v1'

function envelope(data: unknown) {
  return { status: 200, data: { success: true, data } } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

function httpError(status: number, body: unknown) {
  const response = { status, data: body, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } } as AxiosResponse
  return new AxiosError('failed', String(status), undefined, undefined, response)
}

describe('ruleSetVersions API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('按合同路径读取列表与详情，版本号做 URL 编码', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({ items: [] }))
    await listRuleSetVersions(KEY)
    await getRuleSetVersion(KEY, 'v1/2')
    expect(spy.mock.calls[0]?.[0]).toMatchObject({ method: 'GET', url: '/api/v1/rule-set-versions', params: { rule_set_key: KEY } })
    expect(spy.mock.calls[1]?.[0]).toMatchObject({ url: `/api/v1/rule-set-versions/${KEY}/v1%2F2` })
  })

  it('写草稿只发送 rule_id/state，去掉只读派生字段', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope({}))
    const entries = [{ rule_id: 'LX0609-001', state: 'active' as const, executable: true, qc_point: '名称', source_document: '入院记录' }]
    await createRuleSetDraft(KEY, { base_version: '2026-06-09' })
    await updateRuleSetDraft(KEY, { version_seq: 3, entries })
    await deleteRuleSetDraft(KEY, 4)
    await publishRuleSetDraft(KEY, { version: 'v2', note: '说明', version_seq: 5 })
    await retireRuleSetVersion(KEY, 'v1')
    expect(spy.mock.calls[0]?.[0]).toMatchObject({ method: 'POST', url: `/api/v1/rule-set-versions/${KEY}/draft`, data: { base_version: '2026-06-09' } })
    expect(spy.mock.calls[1]?.[0]).toMatchObject({ method: 'PUT', data: { version_seq: 3, entries: [{ rule_id: 'LX0609-001', state: 'active' }] } })
    expect((spy.mock.calls[1]?.[0].data as { entries: object[] }).entries[0]).toEqual({ rule_id: 'LX0609-001', state: 'active' })
    expect(spy.mock.calls[2]?.[0]).toMatchObject({ method: 'DELETE', params: { version_seq: 4 } })
    expect(spy.mock.calls[3]?.[0]).toMatchObject({ url: `/api/v1/rule-set-versions/${KEY}/draft/publish`, data: { version: 'v2', note: '说明', version_seq: 5 } })
    expect(spy.mock.calls[4]?.[0]).toMatchObject({ method: 'POST', url: `/api/v1/rule-set-versions/${KEY}/v1/retire` })
  })

  it.each([
    'draft_exists', 'version_conflict', 'version_exists', 'unsupported_rule_set',
    'current_version', 'builtin_version', 'already_retired',
  ])('解析 409 业务 code：%s', async (code) => {
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(httpError(409, { success: false, error: { code, message: `冲突-${code}` } }))
    const result = await retireRuleSetVersion(KEY, 'v1')
    expect(result).toMatchObject({ success: false, status: 409, code, message: `冲突-${code}` })
  })

  it('解析 422 problems（统一包装 error 与直连 detail 两种形态）', async () => {
    const detail = { code: 'publish_validation_failed', message: '规则集版本发布校验未通过', problems: ['至少需要 1 条 active 规则', 'LX0609-020 不可执行'] }
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(422, { success: false, error: detail }))
      .mockRejectedValueOnce(httpError(422, { detail }))
    for (let index = 0; index < 2; index += 1) {
      const result = await publishRuleSetDraft(KEY, { version: 'v1' })
      expect(result).toMatchObject({ success: false, status: 422, code: 'publish_validation_failed', problems: detail.problems })
    }
  })

  it('非结构化错误回退到消息文本，网络异常无状态码', async () => {
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(503, { success: false, error: '规则集版本服务暂不可用，请稍后重试' }))
      .mockRejectedValueOnce(new Error('Network Error'))
    expect(await listRuleSetVersions(KEY)).toMatchObject({ success: false, status: 503, message: '规则集版本服务暂不可用，请稍后重试', code: undefined })
    const network = await listRuleSetVersions(KEY)
    expect(network.success).toBe(false)
    expect(network.status).toBeUndefined()
  })
})
