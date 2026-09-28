import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import { exportTasksCsv } from '@/api/taskExports'

function blobResponse(
  data: Blob,
  options: { status?: number; contentType?: string; disposition?: string } = {},
): AxiosResponse<Blob> {
  return {
    status: options.status ?? 200,
    statusText: '',
    config: { headers: new AxiosHeaders() },
    data,
    headers: {
      'content-type': options.contentType ?? 'text/csv; charset=utf-8',
      ...(options.disposition ? { 'content-disposition': options.disposition } : {}),
    },
  }
}

function blobHttpError(status: number, body: Blob) {
  const response: AxiosResponse<Blob> = {
    status,
    data: body,
    statusText: '',
    headers: { 'content-type': body.type || 'application/json' },
    config: { headers: new AxiosHeaders() },
  }
  return new AxiosError('failed', String(status), undefined, undefined, response)
}

describe('task exports API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('只发送当前三个真实筛选并返回RFC5987文件名，不触发下载副作用', async () => {
    const csv = new Blob(['\uFEFF任务编号,任务名称\r\nT-1,运行质控'], { type: 'text/csv;charset=utf-8' })
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(blobResponse(csv, {
      disposition: "attachment; filename=task-list.csv; filename*=UTF-8''%E4%BB%BB%E5%8A%A1%E6%B8%85%E5%8D%95.csv",
    }))
    const createElement = vi.spyOn(document, 'createElement')

    const result = await exportTasksCsv({
      scene: 'running',
      status: 'in_progress',
      keyword: ' 任务 A ',
    })

    expect(result).toEqual({ success: true, blob: csv, filename: '任务清单.csv' })
    expect(request).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/task-exports',
      params: { scene: 'running', status: 'in_progress', keyword: ' 任务 A ' },
      responseType: 'blob',
      timeout: 60000,
    })
    expect(createElement).not.toHaveBeenCalled()
  })

  it('省略未生效筛选并支持普通filename回退', async () => {
    const csv = new Blob(['\uFEFF任务编号\r\nT-1'], { type: 'text/csv' })
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(blobResponse(csv, {
      disposition: 'attachment; filename="task-list-20260927.csv"',
    }))

    expect(await exportTasksCsv({ keyword: '' })).toEqual({
      success: true,
      blob: csv,
      filename: 'task-list-20260927.csv',
    })
    expect(request.mock.calls[0]?.[0].params).toEqual({})
  })

  it('200 JSON Blob按错误解析，绝不误当CSV', async () => {
    const body = new Blob([
      JSON.stringify({ detail: { code: 'task_export_failed', message: '导出条件无效' } }),
    ], { type: 'application/json' })
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(blobResponse(body, {
      contentType: 'application/json; charset=utf-8',
      disposition: "attachment; filename*=UTF-8''not-a-csv.csv",
    }))

    expect(await exportTasksCsv()).toEqual({
      success: false,
      message: '导出条件无效',
      status: 200,
    })
  })

  it('拒绝错误状态、错误Content-Type、空文件和非Blob成功体', async () => {
    const csv = new Blob(['\uFEFF任务编号'], { type: 'text/csv' })
    vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(blobResponse(csv, { status: 206 }))
      .mockResolvedValueOnce(blobResponse(csv, { contentType: 'application/octet-stream' }))
      .mockResolvedValueOnce(blobResponse(new Blob([], { type: 'text/csv' })))
      .mockResolvedValueOnce({
        status: 200,
        data: { success: true },
        headers: { 'content-type': 'text/csv; charset=utf-8' },
      } as unknown as AxiosResponse<Blob>)

    for (let index = 0; index < 4; index += 1) {
      expect(await exportTasksCsv()).toMatchObject({
        success: false,
        message: '服务端未返回有效的任务CSV文件',
      })
    }
  })

  it('解析413 JSON Blob的明确超限错误', async () => {
    const body = new Blob([
      JSON.stringify({
        detail: {
          code: 'task_export_too_large',
          message: '匹配任务超过 5000 条，请缩小筛选范围',
          matched_at_least: 5001,
          limit: 5000,
        },
      }),
    ], { type: 'application/json' })
    vi.spyOn(ApiService, 'requestRaw').mockRejectedValue(blobHttpError(413, body))

    expect(await exportTasksCsv({ scene: 'unclassified' })).toEqual({
      success: false,
      message: '匹配任务超过 5000 条，请缩小筛选范围',
      status: 413,
    })
  })

  it('解析对象错误并为网络异常提供稳定消息', async () => {
    const forbiddenResponse = {
      status: 403,
      data: { detail: '仅管理员和质控主管可导出全部任务' },
      statusText: '',
      headers: {},
      config: { headers: new AxiosHeaders() },
    } as AxiosResponse
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(new AxiosError('failed', '403', undefined, undefined, forbiddenResponse))
      .mockRejectedValueOnce(new Error('Network Error'))

    expect(await exportTasksCsv()).toEqual({
      success: false,
      message: '仅管理员和质控主管可导出全部任务',
      status: 403,
    })
    expect(await exportTasksCsv()).toEqual({
      success: false,
      message: '导出任务列表失败，请稍后重试',
    })
  })

  it('RFC5987编码损坏或路径型文件名时回退到安全文件名', async () => {
    const csv = new Blob(['\uFEFF任务编号'], { type: 'text/csv' })
    vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(blobResponse(csv, {
        disposition: "attachment; filename*=UTF-8''%E4%ZZ.csv",
      }))
      .mockResolvedValueOnce(blobResponse(csv, {
        disposition: "attachment; filename*=UTF-8''..%2Fprivate%2Ftask-list.csv",
      }))

    expect(await exportTasksCsv()).toMatchObject({ success: true, filename: 'task-list.csv' })
    expect(await exportTasksCsv()).toMatchObject({ success: true, filename: 'task-list.csv' })
  })
})
