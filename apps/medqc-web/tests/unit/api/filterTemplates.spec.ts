import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createFilterTemplate,
  listFilterTemplates,
  removeFilterTemplate,
  updateFilterTemplate,
} from '@/api/filterTemplates'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T, status = 200): AxiosResponse<T> {
  return {
    data,
    status,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

function rejectWith(status: number, body: unknown) {
  vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(
    new AxiosError('failed', 'ERR_BAD_RESPONSE', undefined, undefined, response(body, status)),
  )
}

const template = {
  id: 't/1',
  page_key: 'v5_records_inpatient' as const,
  name: '待审核',
  filters: { review_state: ['pending_review' as const] },
  is_default: false,
  version: 3,
  created_at: '2026-09-27T00:00:00Z',
  updated_at: '2026-09-27T00:00:00Z',
}

describe('筛选模板 API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response([template]))
  })

  it('GET 按 page_key 读取本人模板，兼容数组与 {items} 两种外层', async () => {
    await expect(listFilterTemplates('v5_records_inpatient')).resolves.toMatchObject({
      success: true,
      data: [template],
    })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/filter-templates',
      params: { page_key: 'v5_records_inpatient' },
    })
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ items: [template] }))
    await expect(listFilterTemplates('v5_records_discharged')).resolves.toMatchObject({
      success: true,
      data: [template],
    })
  })

  it('GET 返回无法识别的形状或 503 时视为失败，不伪造空列表', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ foo: 1 }))
    const unknownShape = await listFilterTemplates('v5_records_inpatient')
    expect(unknownShape.success).toBe(false)
    expect(unknownShape.data).toBeUndefined()

    rejectWith(503, { detail: '筛选模板服务暂不可用' })
    await expect(listFilterTemplates('v5_records_inpatient')).resolves.toMatchObject({
      success: false,
      status: 503,
      code: undefined,
    })
  })

  it('POST/PUT/DELETE 使用合同路径、编码 id，并携带 version', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response(template))
    await createFilterTemplate({
      page_key: 'v5_records_inpatient',
      name: '待审核',
      filters: { review_state: ['pending_review'] },
      is_default: true,
    })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST',
      url: '/api/v1/filter-templates',
      data: {
        page_key: 'v5_records_inpatient',
        name: '待审核',
        filters: { review_state: ['pending_review'] },
        is_default: true,
      },
    })

    await updateFilterTemplate('t/1', { version: 3, is_default: true })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'PUT',
      url: '/api/v1/filter-templates/t%2F1',
      data: { version: 3, is_default: true },
    })

    await removeFilterTemplate('t/1', 3)
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'DELETE',
      url: '/api/v1/filter-templates/t%2F1',
      params: { version: 3 },
    })
  })

  it.each([
    ['name_conflict', { detail: { code: 'name_conflict', message: '模板名称已存在' } }],
    ['limit_reached', { error: { code: 'limit_reached', message: '模板数量已达上限' } }],
    ['version_conflict', { detail: { code: 'version_conflict', message: '版本已变化' } }],
  ] as const)('409 %s 从 detail 或 error 解析业务码', async (code, body) => {
    rejectWith(409, body)
    await expect(updateFilterTemplate('t1', { version: 1, name: 'x' })).resolves.toMatchObject({
      success: false,
      status: 409,
      code,
    })
  })

  it('未知 409 业务码不冒充已知冲突，网络异常保持 success=false', async () => {
    rejectWith(409, { detail: { code: 'something_else', message: '其他冲突' } })
    await expect(createFilterTemplate({ page_key: 'v5_records_inpatient', name: 'a', filters: {} }))
      .resolves.toMatchObject({ success: false, status: 409, code: undefined })

    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(new Error('timeout'))
    await expect(removeFilterTemplate('t1', 1)).resolves.toMatchObject({ success: false })
  })
})
