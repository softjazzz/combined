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
