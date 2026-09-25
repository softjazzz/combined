import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { ApiService } from '@/services/apiService'
import { assignTask, completeTaskRecord, createTaskQcRun, getLatestTaskRecordSyncJob, getTaskAssigneeOptions, getTaskDetail, getTaskList, getTaskQcRuns, getTaskRecordSyncJob, getTaskRuleSets, getTaskStats, getTaskTodoStats, startTaskRecord, syncTaskRecords, updateTask } from '@/api/tasks'

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

  it('运行历史与新运行使用任务专属端点且编码任务 ID', async () => {
    await getTaskQcRuns('task/1')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET', url: '/api/v1/tasks/task%2F1/qc-runs',
    })
    await createTaskQcRun('task/1')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/qc-runs',
    })
    await getTaskQcRuns('task/1', 'assigned')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET', url: '/api/v1/tasks/task%2F1/qc-runs?scope=assigned',
    })
    await createTaskQcRun('task/1', 'all')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/qc-runs?scope=all',
    })
  })

  it('单病历开始处理编码任务和关联 ID，并保留服务端确认字段', async () => {
    const started = { task_id: 'task/1', task_record_id: 'record/甲', status: 'in_progress', idempotent: true }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response(started))
    await expect(startTaskRecord('task/1', 'record/甲')).resolves.toMatchObject({ success: true, data: started })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/records/record%2F%E7%94%B2/start',
    })
  })

  it('单病历显式完成只提交所选运行编号并编码任务与关联 ID', async () => {
    const completed = { task_id: 'task/1', task_record_id: 'record/甲', status: 'completed', run_number: 2,
      idempotent: false, score: null, defect_count: null }
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response(completed))
    await expect(completeTaskRecord('task/1', 'record/甲', 2)).resolves.toMatchObject({ success: true, data: completed })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/records/record%2F%E7%94%B2/complete',
      data: { run_number: 2 },
    })
  })

  it('显式同步任务病历只调用本地任务端点且不附带请求体', async () => {
    await syncTaskRecords('task/1')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/sync-records',
    })
    await getTaskRecordSyncJob('task/1', 'job/甲')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET', url: '/api/v1/tasks/task%2F1/sync-records/job%2F%E7%94%B2',
    })
    await getLatestTaskRecordSyncJob('task/1')
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith(expect.objectContaining({
      method: 'GET', url: '/api/v1/tasks/task%2F1/sync-records/latest',
    }))
  })

  it('latest 404 保留 HTTP 状态，供首次同步区分无作业与网络故障', async () => {
    const notFound = { ...response({ detail: '同步作业不存在' }), status: 404 }
    vi.mocked(ApiService.requestRaw).mockRejectedValueOnce(new AxiosError('Not Found', 'ERR_BAD_RESPONSE', undefined, undefined, notFound))
    await expect(getLatestTaskRecordSyncJob('task-1')).resolves.toMatchObject({ success: false, status: 404 })
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce({ ...notFound, data: { detail: '同步作业不存在' } })
    await expect(getLatestTaskRecordSyncJob('task-1')).resolves.toMatchObject({ status: 404 })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith(expect.objectContaining({
      validateStatus: expect.any(Function),
    }))
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

  it('从真实目录读取候选并以编码任务路径提交比例分配', async () => {
    const options = [{ user_id: 'qc-1', user_name: '质控员甲', department: '质控科' }]
    vi.mocked(ApiService.requestRaw).mockResolvedValueOnce(response(options))
    await expect(getTaskAssigneeOptions()).resolves.toMatchObject({ success: true, data: options })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'GET', url: '/api/v1/tasks/assignee-options',
    })

    await assignTask('task/1', { method: 'by_ratio', assignees: options })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'POST', url: '/api/v1/tasks/task%2F1/assign',
      data: { method: 'by_ratio', assignees: options },
    })
  })

  it('开始受领任务沿用 PUT 状态接口', async () => {
    await updateTask('task-1', { status: 'in_progress' })
    expect(ApiService.requestRaw).toHaveBeenLastCalledWith({
      method: 'PUT', url: '/api/v1/tasks/task-1', data: { status: 'in_progress' },
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
