import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  cancelTaskSchedule,
  createTaskSchedule,
  getTaskSchedule,
  listTaskScheduleRuns,
  listTaskSchedules,
  pauseTaskSchedule,
  retryTaskScheduleRun,
  resumeTaskSchedule,
  runTaskScheduleNow,
  type TaskScheduleCreateRequest,
  type TaskScheduleResponse,
  type TaskScheduleRunResponse,
} from '@/api/taskSchedules'

function response(data: unknown, success = true) {
  return {
    status: 200,
    data: { success, data, message: success ? 'ok' : 'failed' },
  } as Awaited<ReturnType<typeof ApiService.requestRaw>>
}

function error(status: number, data: unknown) {
  const axiosResponse = {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
  } as AxiosResponse
  return new AxiosError('failed', String(status), undefined, undefined, axiosResponse)
}

const schedule: TaskScheduleResponse = {
  id: 'schedule/1',
  source_task_id: 'task-1',
  owner_id: 'user-1',
  name: '运行病历每日抽查',
  scene: 'running',
  rule_set_key: 'luxian-0609',
  rule_set_version: 'v1',
  task_config: {
    date_range: null,
    department_filter: ['内科'],
    sampling_method: 'count',
    sampling_config: { case_scope: 'active', total: 20 },
    assign_method: 'by_ratio',
    assignee_config: {},
  },
  timing_config: {
    kind: 'daily',
    timezone: 'Asia/Shanghai',
    time: '09:00',
    start_date: '2026-10-01',
    end_date: null,
  },
  state: 'active',
  next_fire_at: '2026-10-01T09:00:00+08:00',
  last_fire_at: null,
  version: 1,
  created_at: '2026-09-28T10:00:00+08:00',
  updated_at: '2026-09-28T10:00:00+08:00',
}

const run: TaskScheduleRunResponse = {
  id: 'run-1',
  schedule_id: 'schedule/1',
  trigger_type: 'scheduled',
  scheduled_fire_at: '2026-10-01T09:00:00+08:00',
  idempotency_key: 'schedule/1:2026-10-01',
  status: 'succeeded',
  generated_task_id: 'task-child-1',
  async_job_id: null,
  attempt_count: 1,
  heartbeat_at: null,
  started_at: '2026-10-01T09:00:01+08:00',
  finished_at: '2026-10-01T09:00:03+08:00',
  error_code: null,
  error_message: null,
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:03+08:00',
}

describe('task schedules API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it.each(['record_type_count', 'record_type_ratio'] as const)(
    '类型计划%s回执保留完整类型配置与分配方式',
    async (method) => {
      const config = {
        institutes: [
          {
            institute_id: 'SYN-H',
            critical: { positive_codes: ['C+'], negative_codes: ['C-'] },
            difficult: { positive_codes: ['D+'], negative_codes: ['D-'] },
          },
        ],
        overlap_policy: 'priority',
        priority: ['difficult', 'critical'],
        selected_buckets: ['difficult'],
      }
      const typed = {
        ...schedule,
        task_config: {
          ...schedule.task_config,
          sampling_method: method,
          sampling_config: { record_type_config: config },
          assign_method: 'by_record_type',
        },
      }
      vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(typed))
      const result = await getTaskSchedule(schedule.id)
      expect(result.success).toBe(true)
      expect(result.data?.task_config).toEqual(typed.task_config)
    },
  )

  it('创建只发送源草稿、配置版本和严格时间配置', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(schedule))
    const payload: TaskScheduleCreateRequest = {
      source_task_id: 'task-1',
      source_configuration_version: 3,
      timing_config: {
        kind: 'weekly',
        timezone: 'Asia/Shanghai',
        time: '09:00',
        start_date: '2026-10-01',
        end_date: null,
        weekdays: [1, 3, 5],
      },
    }
    expect(await createTaskSchedule(payload, 'create-request-1')).toMatchObject({
      success: true,
      data: schedule,
    })
    expect(request).toHaveBeenCalledWith({
      method: 'POST',
      url: '/api/v1/task-schedules',
      headers: { 'Idempotency-Key': 'create-request-1' },
      data: payload,
    })
    const sent = request.mock.calls[0][0].data as Record<string, unknown>
    expect(sent).not.toHaveProperty('task_config')
    expect(sent).not.toHaveProperty('sampling_config')
    expect(sent).not.toHaveProperty('rule_set_key')
  })

  it('列表、详情与历史均核对分页和对象身份', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response({ items: [schedule], total: 1, page: 2, page_size: 10 }))
      .mockResolvedValueOnce(response(schedule))
      .mockResolvedValueOnce(response({ items: [run], total: 1, page: 1, page_size: 20 }))
    expect(await listTaskSchedules({ state: 'active', page: 2, page_size: 10 })).toMatchObject({
      success: true,
      data: { total: 1 },
    })
    expect(await getTaskSchedule('schedule/1')).toMatchObject({ success: true, data: schedule })
    expect(await listTaskScheduleRuns('schedule/1', { status: 'succeeded' })).toMatchObject({
      success: true,
      data: { items: [run] },
    })
    expect(request.mock.calls.map(([config]) => config.url)).toEqual([
      '/api/v1/task-schedules?state=active&page=2&page_size=10',
      '/api/v1/task-schedules/schedule%2F1',
      '/api/v1/task-schedules/schedule%2F1/runs?status=succeeded',
    ])
  })

  it('接受终末月计划合同并拒绝越界执行日', async () => {
    const finalMonthly = {
      ...schedule,
      scene: 'final' as const,
      task_config: {
        ...schedule.task_config,
        sampling_config: { case_scope: 'discharged', total: 20 },
      },
      timing_config: {
        kind: 'monthly' as const,
        timezone: 'Asia/Shanghai' as const,
        time: '09:00',
        start_date: '2026-10-01',
        end_date: null,
        day: 1,
      },
    }
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response(finalMonthly))
      .mockResolvedValueOnce(
        response({
          ...finalMonthly,
          timing_config: { ...finalMonthly.timing_config, day: 32 },
        }),
      )
    expect(await getTaskSchedule('schedule/1')).toMatchObject({
      success: true,
      data: { scene: 'final', timing_config: { kind: 'monthly', day: 1 } },
    })
    expect(await getTaskSchedule('schedule/1')).toMatchObject({ success: false, uncertain: false })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it.each([
    { ...schedule, id: '' },
    { ...schedule, version: 0 },
    { ...schedule, state: 'unknown' },
    { ...schedule, timing_config: { ...schedule.timing_config, timezone: 'UTC' } },
    { ...schedule, task_config: { ...schedule.task_config, sampling_config: [] } },
  ])('坏 200 写回失败关闭并标为结果未知', async (payload) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response(payload))
    expect(
      await createTaskSchedule(
        {
          source_task_id: 'task-1',
          source_configuration_version: 3,
          timing_config: {
            kind: 'once',
            timezone: 'Asia/Shanghai',
            run_at: '2026-10-01T09:00:00+08:00',
          },
        },
        'create-request-1',
      ),
    ).toMatchObject({ success: false, uncertain: true })
  })

  it('暂停、恢复和取消均携带 CAS 版本且严格核对回执 ID', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response({ ...schedule, state: 'paused', version: 2 }))
      .mockResolvedValueOnce(response({ ...schedule, state: 'active', version: 3 }))
      .mockResolvedValueOnce(response({ ...schedule, state: 'cancelled', version: 4 }))
    await pauseTaskSchedule('schedule/1', { version: 1 })
    await resumeTaskSchedule('schedule/1', { version: 2 })
    await cancelTaskSchedule('schedule/1', { version: 3 })
    expect(request.mock.calls.map(([config]) => [config.method, config.url, config.data])).toEqual([
      ['PATCH', '/api/v1/task-schedules/schedule%2F1/pause', { version: 1 }],
      ['PATCH', '/api/v1/task-schedules/schedule%2F1/resume', { version: 2 }],
      ['PATCH', '/api/v1/task-schedules/schedule%2F1/cancel', { version: 3 }],
    ])
  })

  it('业务冲突保留结构化错误，网络与 5xx 写入标为未知', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw')
    request.mockRejectedValueOnce(
      error(409, {
        detail: { code: 'version_conflict', message: '计划版本已变化' },
      }),
    )
    expect(await pauseTaskSchedule('schedule/1', { version: 1 })).toMatchObject({
      success: false,
      uncertain: false,
      code: 'version_conflict',
      message: '计划版本已变化',
    })
    request.mockRejectedValueOnce(error(503, { detail: '服务暂不可用' }))
    expect(await resumeTaskSchedule('schedule/1', { version: 1 })).toMatchObject({
      success: false,
      uncertain: true,
      status: 503,
    })
    request.mockRejectedValueOnce(new Error('network'))
    expect(await cancelTaskSchedule('schedule/1', { version: 1 })).toMatchObject({
      success: false,
      uncertain: true,
    })
  })

  it('立即运行携带调用方稳定幂等键，失败重试不发送猜测载荷', async () => {
    const request = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response({ ...run, trigger_type: 'manual' }))
      .mockResolvedValueOnce(response({ ...run, status: 'queued', attempt_count: 2 }))
    expect(await runTaskScheduleNow('schedule/1', 'request-123')).toMatchObject({ success: true })
    expect(await retryTaskScheduleRun('run/1')).toMatchObject({ success: true })
    expect(request.mock.calls).toEqual([
      [
        {
          method: 'POST',
          url: '/api/v1/task-schedules/schedule%2F1/run-now',
          headers: { 'Idempotency-Key': 'request-123' },
        },
      ],
      [{ method: 'POST', url: '/api/v1/task-schedules/runs/run%2F1/retry' }],
    ])
  })
})
