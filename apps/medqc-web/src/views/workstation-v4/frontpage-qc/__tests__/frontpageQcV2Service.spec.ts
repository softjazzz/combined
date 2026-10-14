import { beforeEach, describe, expect, it, vi } from 'vitest'

// 脚本化客户端：只记录请求、返回固定结果，不连接后端
const getRaw = vi.fn()
const postRaw = vi.fn()
vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: (...args: unknown[]) => getRaw(...args),
    postRaw: (...args: unknown[]) => postRaw(...args),
  },
}))

import {
  createFrontpageQcRun,
  exportFrontpageQcRecords,
  FrontpageQcRequestError,
  isFrontpageQcRunActive,
  listFrontpageQcRecords,
  reviewFrontpageQcFinding,
} from '@/services/frontpage-qc-v2-service'

function httpError(status: number, data: unknown) {
  return Object.assign(new Error(`Request failed with status code ${status}`), {
    response: { status, data },
  })
}

describe('frontpage-qc-v2-service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('列表查询去掉空参数并解出 data', async () => {
    getRaw.mockResolvedValueOnce({ data: { success: true, data: { items: [], total: 0, page: 1, page_size: 15 } } })

    const result = await listFrontpageQcRecords({ department: '', grade: 'qualified', issue: '', page: 1, page_size: 15 })

    expect(getRaw).toHaveBeenCalledWith('/api/v1/frontpage-qc/records', {
      grade: 'qualified',
      page: 1,
      page_size: 15,
    })
    expect(result.total).toBe(0)
  })

  it('409 冲突时保留后端返回的进行中任务', async () => {
    const run = { id: 'run-1', status: 'running' }
    postRaw.mockRejectedValueOnce(
      httpError(409, { success: false, error: { message: '已有进行中的首页质控任务', run } }),
    )

    const error = await createFrontpageQcRun({ record_refs: [] }).catch((err: unknown) => err)

    expect(error).toBeInstanceOf(FrontpageQcRequestError)
    expect((error as FrontpageQcRequestError).status).toBe(409)
    expect((error as FrontpageQcRequestError).message).toBe('已有进行中的首页质控任务')
    expect((error as FrontpageQcRequestError).payload).toEqual({ message: '已有进行中的首页质控任务', run })
  })

  it('字符串错误原样展示，缺失时用兜底文案', async () => {
    postRaw.mockRejectedValueOnce(httpError(422, { success: false, error: '标记误报必须填写原因' }))
    await expect(reviewFrontpageQcFinding('f-1', { status: 'false_alarm', note: '' })).rejects.toThrow(
      '标记误报必须填写原因',
    )

    postRaw.mockRejectedValueOnce(new Error('Network Error'))
    await expect(reviewFrontpageQcFinding('f-1', { status: 'confirmed', note: '' })).rejects.toThrow('保存复核失败')
  })

  it('导出失败时从 Blob 响应体读出原因', async () => {
    const body = new Blob([JSON.stringify({ success: false, error: '导出范围超出上限' })], {
      type: 'application/json',
    })
    postRaw.mockRejectedValueOnce(httpError(422, body))

    await expect(exportFrontpageQcRecords({ department: '内科' })).rejects.toThrow('导出范围超出上限')
    expect(postRaw).toHaveBeenCalledWith(
      '/api/v1/frontpage-qc/records/export',
      { department: '内科' },
      { responseType: 'blob' },
    )
  })

  it('只有排队中和质控中算进行中', () => {
    expect(isFrontpageQcRunActive({ status: 'queued' })).toBe(true)
    expect(isFrontpageQcRunActive({ status: 'running' })).toBe(true)
    expect(isFrontpageQcRunActive({ status: 'completed_with_errors' })).toBe(false)
    expect(isFrontpageQcRunActive(null)).toBe(false)
  })
})
