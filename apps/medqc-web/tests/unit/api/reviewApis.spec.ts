import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getRecordReviewTodos, getTaskRecordReview, submitTaskRecordReview } from '@/api/recordReviews'
import { getManualDefects, reviewManualDefect } from '@/api/manualDefectReviews'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T, status = 200): AxiosResponse<T> {
  return { data, status, statusText: 'OK', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } }
}

function httpError(status: number, data: unknown) {
  return new AxiosError('failed', 'ERR_BAD_RESPONSE', undefined, undefined, response(data, status))
}

describe('病历审核 API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('GET 编码路径并携带 run_number，成功返回服务端视图', async () => {
    const view = { task_id: 't/1', state: 'pending_review' }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: view }))
    await expect(getTaskRecordReview('t/1', 'r 1', 2)).resolves.toMatchObject({ success: true, data: view, status: 200 })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET', url: '/api/v1/tasks/t%2F1/records/r%201/review', params: { run_number: 2 },
    })
  })

  it('POST 原样提交载荷；统一错误包装下的 409 detail 解出 code 与 message', async () => {
    const payload = { run_number: 1, decision: 'doubtful' as const, reason: '原因', request_id: 'rid', envelope_id: 'env' }
    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(httpError(409, {
      success: false, error: { code: 'result_changed', message: '质控结果已被替换' }, code: 'HTTP_409',
    }))
    await expect(submitTaskRecordReview('t', 'r', payload)).resolves.toEqual({
      success: false, status: 409, code: 'result_changed', message: '质控结果已被替换',
    })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({ method: 'POST', url: '/api/v1/tasks/t/records/r/review', data: payload })
  })

  it('直连 FastAPI 的 detail 对象同样解出 code；503 字符串 detail 与网络异常无 code', async () => {
    vi.mocked(ApiService.requestRaw)
      .mockRejectedValueOnce(httpError(409, { detail: { code: 'already_decided', message: '已决定' } }))
      .mockRejectedValueOnce(httpError(503, { detail: '病历审核服务暂不可用，请稍后重试' }))
      .mockRejectedValueOnce(new Error('Network Error'))
    const payload = { run_number: 1, decision: 'approved' as const, request_id: 'rid', envelope_id: 'env' }
    await expect(submitTaskRecordReview('t', 'r', payload)).resolves.toMatchObject({ status: 409, code: 'already_decided' })
    await expect(submitTaskRecordReview('t', 'r', payload)).resolves.toEqual({
      success: false, status: 503, code: undefined, message: '病历审核服务暂不可用，请稍后重试',
    })
    await expect(submitTaskRecordReview('t', 'r', payload)).resolves.toMatchObject({ success: false, status: undefined, code: undefined })
  })

  it('待办只传入已给定的筛选参数', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response({ success: true, data: { items: [], total: 0 } }))
    await getRecordReviewTodos({ stage: 'recheck', scene: 'running', page: 2, page_size: 20 })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET', url: '/api/v1/record-reviews/todo', params: { stage: 'recheck', scene: 'running', page: 2, page_size: 20 },
    })
    await getRecordReviewTodos()
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({ method: 'GET', url: '/api/v1/record-reviews/todo', params: {} })
  })
})

describe('人工缺陷审核 API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('列表按 review_status 与分页请求', async () => {
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response({ success: true, data: { items: [], total: 0, page: 1, page_size: 20 } }))
    await expect(getManualDefects('approved', 3, 20)).resolves.toMatchObject({ success: true, status: 200 })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET', url: '/api/v1/manual-defects', params: { review_status: 'approved', page: 3, page_size: 20 },
    })
  })

  it('审核提交携带 expected_status，409 not_pending 与 403 可区分', async () => {
    vi.mocked(ApiService.requestRaw)
      .mockRejectedValueOnce(httpError(409, { success: false, error: { code: 'not_pending', message: '已不是待审核状态' } }))
      .mockRejectedValueOnce(httpError(403, { success: false, error: '审核人不能审核本人创建的人工缺陷' }))
    const payload = { decision: 'rejected' as const, reason: '证据不足', expected_status: 'pending' as const }
    await expect(reviewManualDefect('d/1', payload)).resolves.toMatchObject({ status: 409, code: 'not_pending' })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({ method: 'POST', url: '/api/v1/manual-defects/d%2F1/review', data: payload })
    await expect(reviewManualDefect('d/1', payload)).resolves.toEqual({
      success: false, status: 403, code: undefined, message: '审核人不能审核本人创建的人工缺陷',
    })
  })
})
