import { beforeEach, describe, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: mocks.request } }))
import {
  createManualEntry,
  decideManualDefect,
  getEntryContexts,
  getManualPendingCount,
  getManualReviewQueue,
  getOwnManualEntries,
  type EntryContext,
} from '../manualDefectWorkflow'
const item = {
  id: 'd1',
  rule_name: '缺陷',
  description: '说明',
  manual_review_status: 'pending',
  task_id: 't1',
  task_record_id: 'r1',
  run_number: 1,
}
const context: EntryContext = {
  task_id: 't1',
  task_record_id: 'r1',
  task_name: '任务',
  institute_id: 'H1',
  patient_id: 'P1',
  visit_id: 'V1',
  scene: 'running',
  run_number: 1,
  job_id: 'J1',
  available: true,
  reason: null,
}
function reply(data: unknown) {
  mocks.request.mockResolvedValue({ data: { success: true, data } })
}
beforeEach(() => vi.clearAllMocks())
describe('人工缺陷操作回执', () => {
  it('不把错误场景或未知计数变成零', async () => {
    reply({ scene: 'final', total: 0 })
    await expect(getManualPendingCount('running')).rejects.toThrow()
    reply({ scene: 'running', total: null })
    await expect(getManualPendingCount('running')).rejects.toThrow()
    reply({ scene: 'running', total: 3 })
    expect(await getManualPendingCount('running')).toBe(3)
  })
  it('拒绝跨病例和跨状态的列表回执', async () => {
    reply({ items: [{ ...item, task_record_id: 'other' }], total: 1 })
    await expect(getOwnManualEntries(context)).rejects.toThrow()
    reply({
      items: [{ ...item, manual_review_status: 'approved' }],
      total: 1,
      page: 1,
      scene: 'running',
    })
    await expect(getManualReviewQueue('running', 'pending')).rejects.toThrow()
  })
  it('创建复用调用者请求ID，回执必须匹配冻结任务坐标', async () => {
    const payload = {
      defect_id: 'd1',
      task_id: 't1',
      task_record_id: 'r1',
      run_number: 1,
      rule_name: '缺陷',
      description: '说明',
      severity: 'warning' as const,
    }
    reply({ ...item, task_record_id: 'other' })
    await expect(createManualEntry(payload)).rejects.toThrow()
    expect(mocks.request.mock.calls[0][0].data).toEqual(payload)
    reply(item)
    await expect(createManualEntry(payload)).resolves.toMatchObject({ id: 'd1' })
  })
  it('审核固定以pending做CAS，缺历史或错误结论不能报成功', async () => {
    reply({ id: 'd1', manual_review_status: 'approved', previous_status: 'pending' })
    await expect(decideManualDefect('d1', 'approved', '')).rejects.toThrow()
    expect(mocks.request.mock.calls[0][0].data.expected_status).toBe('pending')
    reply({
      id: 'd1',
      manual_review_status: 'rejected',
      previous_status: 'pending',
      history_id: 'h1',
    })
    await expect(decideManualDefect('d1', 'approved', '')).rejects.toThrow()
  })
  it('没有合法运行的任务不能被标记可录入', async () => {
    reply({ items: [{ ...context, run_number: null }], page: 1, has_more: false })
    await expect(getEntryContexts('all')).rejects.toThrow()
    reply({ items: [context], page: 1, has_more: false })
    await expect(getEntryContexts('all')).resolves.toMatchObject({ items: [context] })
  })
})
