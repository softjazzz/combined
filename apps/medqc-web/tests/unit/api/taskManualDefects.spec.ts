import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createTaskManualDefect, getTaskManualDefects } from '@/api/tasks'
import { ApiService } from '@/services/apiService'

vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: vi.fn() } }))

function response<T>(data: T, status = 200): AxiosResponse<T> {
  return {
    data, status, statusText: 'OK', headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  }
}

describe('任务病历人工缺陷 API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response({ items: [], total: 0, limit: 50, offset: 0 }))
  })

  it('POST 编码两个关联 ID，原样提交客户端编号与核实运行编号', async () => {
    const payload = {
      defect_id: 'stable-id', run_number: 2, rule_name: '现病史缺项',
      description: '未记载起病时间', severity: 'warning' as const,
      suggestion: null, evidence: null,
    }
    await expect(createTaskManualDefect('task/甲', 'association/乙', payload)).resolves.toMatchObject({ success: true })
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/tasks/task%2F%E7%94%B2/records/association%2F%E4%B9%99/manual-defects',
      data: payload,
    })
  })

  it('GET 始终指定精确任务病历路径及分页参数', async () => {
    await getTaskManualDefects('task/甲', 'association/乙', 20, 40)
    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/task%2F%E7%94%B2/records/association%2F%E4%B9%99/manual-defects',
      params: { limit: 20, offset: 40 },
    })
  })

  it('服务端拒绝和网络异常保持 success=false，不伪造已保存结果', async () => {
    const rejected = response({ detail: '无权处理该任务病历' }, 403)
    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(
      new AxiosError('Forbidden', 'ERR_BAD_RESPONSE', undefined, undefined, rejected),
    )
    const payload = {
      defect_id: 'stable-id', run_number: 2, rule_name: '现病史缺项',
      description: '未记载起病时间', severity: 'warning' as const,
    }
    await expect(createTaskManualDefect('task-a', 'association-a', payload)).resolves.toMatchObject({
      success: false, status: 403,
    })

    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(new Error('timeout'))
    await expect(getTaskManualDefects('task-a', 'association-a')).resolves.toMatchObject({ success: false })
  })
})
