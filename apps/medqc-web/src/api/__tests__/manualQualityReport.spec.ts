import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getManualQualityReport } from '../manualQualityReport'
const mock = vi.hoisted(() => vi.fn())
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: mock } }))
const filters = { start_date: '2026-10-01', end_date: '2026-10-01', scene: 'all' as const }
const result = {
  assumption: '待确认',
  as_of: '2026-10-01T00:00:00Z',
  timezone: 'Asia/Shanghai',
  filters,
  summary: {
    entered: 0,
    review: { pending: 0, approved: 0, rejected: 0, unknown: 0 },
    rectification: {
      pending: 0,
      submitted: 0,
      approved: 0,
      rejected: 0,
      unassigned: 0,
      unknown: 0,
    },
  },
  filter_options: { institutes: [], departments: [], creators: [], tasks: [] },
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
}
beforeEach(() => {
  vi.clearAllMocks()
})
describe('人工质控回执边界', () => {
  it.each([{}, { root_job_id: null, envelope_id: null }, { root_job_id: 'J1', envelope_id: 5 }])(
    '可信来源必须携带完整冻结结果引用%j',
    async (anchors) => {
      const row = {
        id: 'D1',
        creator_name: '录入人',
        created_at: '2026-10-24T00:00:00Z',
        institute_id: 'H1',
        patient_id: 'P1',
        visit_id: 'V1',
        department: '内科',
        creator_id: 'U1',
        task_id: 'T1',
        task_name: '任务',
        task_record_id: 'TR1',
        rule_name: '人工缺陷',
        run_number: 1,
        scene: 'running',
        source_verified: true,
        review_status: 'approved',
        rectification_status: 'unassigned',
        ...anchors,
      }
      const payload = {
        ...result,
        items: [row],
        total: 1,
        summary: {
          entered: 1,
          review: { pending: 0, approved: 1, rejected: 0, unknown: 0 },
          rectification: {
            pending: 0,
            submitted: 0,
            approved: 0,
            rejected: 0,
            unassigned: 1,
            unknown: 0,
          },
        },
      }
      mock.mockResolvedValue({ data: { success: true, data: payload } })
      await expect(getManualQualityReport(filters)).rejects.toThrow('回执不完整')
      mock.mockResolvedValue({
        data: {
          success: true,
          data: { ...payload, items: [{ ...row, root_job_id: 'J1', envelope_id: 'E1' }] },
        },
      })
      await expect(getManualQualityReport(filters)).resolves.toMatchObject({
        items: [{ root_job_id: 'J1', envelope_id: 'E1' }],
      })
    },
  )
  it('完整回执保持当前状态桶与冻结筛选', async () => {
    mock.mockResolvedValue({ data: { success: true, data: result } })
    expect(await getManualQualityReport(filters)).toEqual(result)
    expect(mock).toHaveBeenCalledWith(
      expect.objectContaining({ params: { ...filters, page: 1, page_size: 20 } }),
    )
  })
  it.each([
    {},
    { ...result, summary: {} },
    { ...result, filter_options: {} },
    { ...result, summary: { ...result.summary, review: { pending: 0, approved: 0, rejected: 0 } } },
    {
      ...result,
      summary: {
        ...result.summary,
        rectification: { ...result.summary.rectification, unknown: -1 },
      },
    },
    { ...result, items: [{}] },
    { ...result, page: 2 },
    { ...result, as_of: '2026-10-01T00:00:00' },
  ])('坏回执失败进入错误态，不补零', async (bad) => {
    mock.mockResolvedValue({ data: { success: true, data: bad } })
    await expect(getManualQualityReport(filters)).rejects.toThrow('回执不完整')
  })
})
