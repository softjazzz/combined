import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCoreSystemReport, exportCoreSystemReport } from '../coreSystemReports'

const mock = vi.hoisted(() => vi.fn())
vi.mock('@/services/apiService', () => ({ ApiService: { requestRaw: mock } }))
const systems = Array.from({ length: 18 }, (_, index) => ({
  id: `CORE-${String(index + 1).padStart(2, '0')}`,
  name: '合成制度',
  record_count: null,
  problem_records: null,
  problem_rate: null,
  points: [],
}))
const result = {
  as_of: '2026-10-01T00:00:00Z',
  scene: 'running',
  contract: '已配置质控点范围的问题率',
  scope: {
    scope_label: '当前在院病历',
    scope_basis: 'inpatient_with_qc_result',
    archive_status: null,
  },
  summary: { candidate_records: 0, unknown_records: 0, unavailable_records: 0, unknown_points: 0 },
  systems,
  reference: {
    title: '医疗质量安全核心制度要点',
    reference_date: '2018-04-18',
    source_url: 'https://www.nhc.gov.cn/reference',
    reference_note: '2018版参考',
    systems: systems.map((s) => ({ ...s, text: '定义与基本要求' })),
  },
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
}
beforeEach(() => vi.clearAllMocks())
describe('核心制度报表API边界', () => {
  it('空选项不传到最小长度约束接口，false仍保留', async () => {
    mock.mockResolvedValue({ data: { success: true, data: result } })
    await getCoreSystemReport({
      scene: 'running',
      institute_id: '',
      system_id: '',
      problems_only: false,
    })
    expect(mock).toHaveBeenCalledWith(
      expect.objectContaining({
        params: { scene: 'running', problems_only: false, page: 1, page_size: 20 },
      }),
    )
  })
  it('完整18项及无配置null保持原样', async () => {
    mock.mockResolvedValue({ data: { success: true, data: result } })
    expect(await getCoreSystemReport({ scene: 'running' })).toEqual(result)
  })
  it.each([
    {},
    { ...result, summary: {} },
    { ...result, systems: systems.slice(1) },
    { ...result, reference: { ...result.reference, systems: [] } },
    { ...result, systems: [{ ...systems[0], problem_records: 0 }, ...systems.slice(1)] },
    { ...result, summary: { ...result.summary, unknown_points: -1 } },
    { ...result, items: [{}] },
    { ...result, top_systems: [{ id: 'CORE-99', name: '未知制度', defect_total: 1 }] },
    { ...result, top_systems: [{ id: 'CORE-01', name: '合成制度', defect_total: -1 }] },
    { ...result, summary: { ...result.summary, unknown_defects: -1 } },
    { ...result, systems: [{ ...systems[0], defect_total: -1 }, ...systems.slice(1)] },
  ])('坏回执不进入渲染或补零', async (value) => {
    mock.mockResolvedValue({ data: { success: true, data: value } })
    await expect(getCoreSystemReport({ scene: 'running' })).rejects.toThrow('回执不完整')
  })
  it('导出保持应用的三坐标机构/制度过滤', async () => {
    const blob = new Blob(['synthetic'])
    mock.mockResolvedValue({ data: blob })
    expect(
      await exportCoreSystemReport({ scene: 'final', institute_id: 'H1', system_id: 'CORE-01' }),
    ).toBe(blob)
    expect(mock).toHaveBeenCalledWith(
      expect.objectContaining({
        params: { scene: 'final', institute_id: 'H1', system_id: 'CORE-01' },
        responseType: 'blob',
      }),
    )
  })
})
