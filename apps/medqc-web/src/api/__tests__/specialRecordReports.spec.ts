import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  SPECIAL_RECORD_TYPES,
  getSpecialRecordReport,
  getSpecialReportRecords,
  getSpecialReportDefects,
  exportSpecialRecordReport,
  getSpecialSourceConfig,
  saveSpecialSourceConfig,
} from '../specialRecordReports'
const filters = {
  institute_id: 'H1',
  discharged_from: '2026-10-01',
  discharged_to: '2026-10-03',
  record_type: 'death' as const,
  record_type_state: 'positive' as const,
}
const report = {
  scope: { ...filters, timezone: 'Asia/Shanghai', classification_version_seq: 1 },
  summary: {
    cohort_total: 0,
    record_total: 0,
    unavailable_result_total: 0,
    unknown_type_total: 0,
    graded_total: 0,
    ungraded_total: 0,
    known_result_total: 0,
    selected_unavailable_result_total: 0,
    grade_ratio_denominator: 'graded_total',
    defect_ratio_denominator: 'confirmed_auto_defect_total',
  },
  types: SPECIAL_RECORD_TYPES.map((key) => ({
    key,
    label: key,
    count: null,
    known_positive_total: 0,
    unknown_total: 0,
    status: 'unknown',
  })),
  top_departments: null,
  grade_distribution: null,
  top_defects: null,
  score_standard: {
    status: 'no_standard',
    standard_id: null,
    standard_version_seq: null,
    binding_version_seq: null,
  },
}
function envelope(data: unknown) {
  return { data: { success: true, data }, status: 200 } as Awaited<
    ReturnType<typeof ApiService.requestRaw>
  >
}
beforeEach(() => vi.restoreAllMocks())
describe('特殊病历报表API边界', () => {
  it('保留未知值并共用筛选，分页与导出传专用kind', async () => {
    const spy = vi
      .spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(envelope(report))
      .mockResolvedValueOnce(
        envelope({
          total: 0,
          page: 2,
          page_size: 20,
          items: [],
          scope: report.scope,
          score_standard: report.score_standard,
        }),
      )
      .mockResolvedValueOnce(
        envelope({
          total: 0,
          page: 1,
          page_size: 20,
          items: [],
          scope: report.scope,
          score_standard: report.score_standard,
        }),
      )
      .mockResolvedValueOnce({ data: new Blob(['synthetic']) } as Awaited<
        ReturnType<typeof ApiService.requestRaw>
      >)
    expect((await getSpecialRecordReport({ ...filters, department: '' })).types[0].count).toBeNull()
    await getSpecialReportRecords(filters, 2)
    await getSpecialReportDefects(filters)
    await exportSpecialRecordReport(filters, 'summary')
    expect(spy.mock.calls[0][0].params).toEqual(filters)
    expect(spy.mock.calls[1][0].params).toEqual({ ...filters, page: 2, page_size: 20 })
    expect(spy.mock.calls[3][0].params).toEqual({ ...filters, kind: 'summary' })
  })
  it.each([{}, { ...report, types: [] }, { ...report, top_defects: [{ name: 'bad', count: -1 }] }])(
    '坏回执拒绝渲染',
    async (value) => {
      vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope(value))
      await expect(getSpecialRecordReport(filters)).rejects.toThrow('回执不完整')
    },
  )
  it('混院身份/缺三坐标病例不进入渲染', async () => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(
      envelope({
        total: 1,
        page: 1,
        page_size: 20,
        items: [{ institute_id: 'H1', patient_id: '', visit_id: 'V' }],
      }),
    )
    await expect(getSpecialReportRecords(filters)).rejects.toThrow('回执不完整')
  })
  it('配置回执绑定机构及版本，空数组保持未知不添默认码', async () => {
    const config = {
      critical: { positive_codes: [], negative_codes: [] },
      difficult: { positive_codes: [], negative_codes: [] },
      surgery_level_codes: { '1': [], '2': [], '3': [], '4': [] },
    }
    const data = { institute_id: 'H1', version_seq: 0, config, sources: [] }
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(envelope(data))
    expect((await getSpecialSourceConfig('H1')).config).toEqual(config)
    await saveSpecialSourceConfig('H1', 0, config)
    expect(spy.mock.calls[1][0]).toMatchObject({
      method: 'PUT',
      params: { institute_id: 'H1' },
      data: { version_seq: 0, config },
    })
    await expect(getSpecialSourceConfig('H2')).rejects.toThrow('回执不完整')
  })
  it('CSV已知版本header漂移拒绝下载，不冒称整体病例快照', async () => {
    const spy = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue({
      ...envelope(null),
      data: new Blob(['synthetic']),
      headers: {
        'x-special-classification-version': '1',
        'x-special-standard-id': '',
        'x-special-standard-version': '',
        'x-special-binding-version': '',
      },
    })
    const expected = report as unknown as import('../specialRecordReports').SpecialRecordReport
    await expect(exportSpecialRecordReport(filters, 'summary', expected)).resolves.toBeInstanceOf(
      Blob,
    )
    spy.mockResolvedValue({
      ...envelope(null),
      data: new Blob(['synthetic']),
      headers: { 'x-special-classification-version': '2' },
    })
    await expect(exportSpecialRecordReport(filters, 'summary', expected)).rejects.toThrow(
      '版本已变化',
    )
  })
  it('已知身份的空姓名科室可以保持未知，不拒绝整个报表', async () => {
    const row = {
      institute_id: 'H1',
      patient_id: 'P1',
      visit_id: 'V1',
      patient_name: null,
      department: null,
      discharged_at: null,
      types: Object.fromEntries(
        SPECIAL_RECORD_TYPES.map((key) => [key, { state: 'unknown', reason_code: 'missing' }]),
      ),
      report_score_status: 'unknown',
      report_score: null,
      report_grade: null,
      standard_id: null,
      standard_version_seq: null,
      binding_version_seq: null,
      reason_code: 'no_standard',
      historical_score: null,
      historical_grade: null,
    }
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(
      envelope({
        total: 1,
        page: 1,
        page_size: 20,
        items: [row],
        scope: report.scope,
        score_standard: report.score_standard,
      }),
    )
    expect((await getSpecialReportRecords(filters)).items[0].patient_name).toBeNull()
  })
})
