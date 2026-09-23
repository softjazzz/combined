import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosHeaders, type AxiosResponse } from 'axios'
import { ApiService } from '@/services/apiService'
import { getTaskDetail, getTaskList, getTaskRuleSets, getTaskStats, getTaskTodoStats } from '@/api/tasks'

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

const stats = {
  total: 6,
  by_status: { assigned: 2, in_progress: 1, completed: 3 },
  draft: 0,
  in_progress: 1,
  completed: 3,
  cancelled: 0,
}

describe('任务统计 API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(ApiService.requestRaw).mockResolvedValue(response(stats))
  })

  it('按 received 范围请求我的任务统计', async () => {
    await expect(getTaskStats({ tab: 'received' })).resolves.toEqual({
      success: true,
      data: stats,
      message: undefined,
    })

    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/stats?tab=received',
    })
  })

  it('保留无参调用的兼容地址', async () => {
    await getTaskStats()

    expect(ApiService.requestRaw).toHaveBeenCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/stats',
    })
  })

  it('通过工作区目录读取已发布规则集并保留请求失败语义', async () => {
    const catalog = { items: [{ rule_set_key: 'running-rules', rule_set_name: '运行规则', rule_set_version: 'v1', scope: 'running' }] }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response(catalog))
    await expect(getTaskRuleSets()).resolves.toMatchObject({ success: true, data: catalog })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/qc/sichuan/workspace/rule-sets',
    })

    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(new Error('目录不可用'))
    await expect(getTaskRuleSets()).resolves.toMatchObject({ success: false })
  })

  it('任务详情编码路径并显式传递清单范围', async () => {
    await getTaskDetail('task/含空格', { tab: 'received' })

    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/task%2F%E5%90%AB%E7%A9%BA%E6%A0%BC?tab=received',
    })

    await getTaskDetail('legacy-task')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/legacy-task',
    })
  })

  it('列表、统计和待办统计使用同一场景筛选合同', async () => {
    await getTaskList({ tab: 'received', scene: 'unclassified' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks?tab=received&scene=unclassified',
    })

    await getTaskStats({ tab: 'received', scene: 'running' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/stats?tab=received&scene=running',
    })

    await getTaskTodoStats({ scene: 'outpatient' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/todo-stats?scene=outpatient',
    })
  })

  it('获取个人待办统计并按服务端时点编码下钻条件', async () => {
    const todoStats = {
      as_of: '2026-09-22T07:30:00+00:00',
      assigned: 2,
      in_progress: 1,
      due_soon: 3,
    }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response(todoStats))

    await expect(getTaskTodoStats()).resolves.toEqual({
      success: true,
      data: todoStats,
      message: undefined,
    })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url: '/api/v1/tasks/todo-stats',
    })

    await getTaskList({
      tab: 'received',
      todo: 'due_soon',
      as_of: todoStats.as_of,
      page: 2,
    })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET',
      url:
        '/api/v1/tasks?tab=received&todo=due_soon&as_of=2026-09-22T07%3A30%3A00%2B00%3A00&page=2',
    })
  })
})
