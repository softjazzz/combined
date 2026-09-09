import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosHeaders, type AxiosResponse } from 'axios'
import { ApiService } from '@/services/apiService'
import {
  startDiagnosticCapture,
  getDiagnosticCapture,
  downloadDiagnosticCapture,
} from '@/services/qc-diagnostics-service'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

describe('排障采集授权 API', () => {
  beforeEach(() => vi.clearAllMocks())
  it('启动传完整身份，查询和下载转义任务 ID，下载明确确认', async () => {
    const selection = {
      job_id: 'old',
      record_ref: 'ref',
      institute_id: 'h',
      patient_id: 'p',
      visit_id: 'v',
    }
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response({ job_id: 'new' }))
    expect(await startDiagnosticCapture(selection)).toEqual({ job_id: 'new' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: 'POST',
        url: '/api/v1/qc/diagnostics/capture/start',
        data: selection,
      }),
    )
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response({ state: 'running' }))
    expect(await getDiagnosticCapture('a/b')).toEqual({ state: 'running' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({ method: 'GET', url: '/api/v1/qc/diagnostics/capture/a%2Fb' }),
    )
    const blob = new Blob(['zip'])
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response(blob))
    expect(await downloadDiagnosticCapture('a/b')).toBe(blob)
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: 'POST',
        url: '/api/v1/qc/diagnostics/capture/a%2Fb/download',
        data: { confirmed: true },
        responseType: 'blob',
      }),
    )
  })
})
