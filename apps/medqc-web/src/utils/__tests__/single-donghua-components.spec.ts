import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { AxiosHeaders } from 'axios'
import Panel from '@/views/workstation-v4/components/system-config/ClinicalSourceSettingsPanel.vue'
import { clinicalSourcesApi } from '@/api/clinicalSources'
import { ApiService } from '@/services/apiService'
import { usePatientRecords, resetClinicalSourceOptionsCache } from '@/views/workstation-v4/composables/usePatientRecords'
import type { ClinicalSourceSettings } from '@/api/clinicalSources'

vi.mock('@/api/clinicalSources', () => ({ clinicalSourcesApi: { configuration: vi.fn(), save: vi.fn(), check: vi.fn(), options: vi.fn() } }))
vi.mock('@/services/apiService', () => ({ ApiService: { getRaw: vi.fn(), postRaw: vi.fn() } }))
const settings: ClinicalSourceSettings = {
  version: 1, default_source: 'legacy_pg', legacy_name: '原来源', legacy_enabled: true,
  cdm: { name: '东华CDM', enabled: true, host: 'localhost', port: 62997, database: 'synthetic', username: 'readonly' },
}

function response(data: unknown) {
  return { data, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } }
}

beforeEach(() => {
  vi.resetAllMocks()
  resetClinicalSourceOptionsCache()
  window.history.replaceState({}, '', '/workstation-v5/running-records?source_id=legacy_pg')
  vi.mocked(clinicalSourcesApi.configuration).mockResolvedValue(structuredClone(settings))
  vi.mocked(clinicalSourcesApi.save).mockResolvedValue(structuredClone(settings))
})
describe('真实面板及病历池单源行为', () => {
  it('没有切源控件，保存强制东华，不自动连接源库', async () => {
    const panel = mount(Panel)
    await flushPromises()
    expect(panel.text()).toContain('普通临床来源：东华CDM')
    expect(panel.find('select').exists()).toBe(false)
    expect(panel.findAll('input[type=checkbox]')).toHaveLength(1)
    expect(clinicalSourcesApi.check).not.toHaveBeenCalled()
    await panel.get('form').trigger('submit')
    await flushPromises()
    expect(clinicalSourcesApi.save).toHaveBeenCalledWith(expect.objectContaining({ default_source: 'independent_cdm', legacy_enabled: false }))
    panel.unmount()
  })
  it('过期默认配置及URL不能改变列表请求，行身份继续传给详情与任务', async () => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({ default_source: 'legacy_pg', sources: [{ id: 'legacy_pg', name: 'old', enabled: true }, { id: 'independent_cdm', name: '东华CDM', enabled: true }] })
    vi.mocked(ApiService.getRaw).mockResolvedValue({ data: { records: [{ id: 'R', institute_id: 'I', patient_id: 'P', visit_id: 'V' }], total: 1 }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config: { headers: new AxiosHeaders() } })
    const records = usePatientRecords()
    await records.fetchData()
    expect(ApiService.getRaw).toHaveBeenCalledWith(
      '/api/medical-records/workstation',
      expect.objectContaining({ source_id: 'independent_cdm' }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(records.allRecords.value[0].sourceId).toBe('independent_cdm')
    expect(new URL(window.location.href).searchParams.get('source_id')).toBe('independent_cdm')
  })
  it('停用东华时显示失败，不请求或回退legacy', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({ default_source: 'legacy_pg', sources: [{ id: 'legacy_pg', name: 'old', enabled: true }, { id: 'independent_cdm', name: '东华CDM', enabled: false }] })
    const records = usePatientRecords()
    await records.fetchData()
    expect(records.loadError.value).toBe(true)
    expect(ApiService.getRaw).not.toHaveBeenCalled()
    expect(records.allRecords.value).toEqual([])
    vi.restoreAllMocks()
  })

  it('后端显式返回 legacy_compat 时使用本地 legacy_pg 数据源并保持 URL 一致', async () => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({
      mode: 'legacy_compat',
      default_source: 'legacy_pg',
      sources: [
        { id: 'legacy_pg', name: '原有数据源', enabled: true },
        { id: 'independent_cdm', name: '服务器CDM', enabled: false },
      ],
    })
    vi.mocked(ApiService.getRaw).mockResolvedValue(
      response({ records: [{ id: 'R1', institute_id: 'I', patient_id: 'P1', visit_id: 'V1' }], total: 1 }),
    )
    const records = usePatientRecords('inpatient')
    await records.fetchData()
    expect(records.loadError.value).toBe(false)
    expect(records.sourceId.value).toBe('legacy_pg')
    expect(ApiService.getRaw).toHaveBeenCalledWith(
      '/api/medical-records/workstation',
      expect.objectContaining({ source_id: 'legacy_pg', hospital_status: 'inpatient' }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(records.allRecords.value[0]?.sourceId).toBe('legacy_pg')
    expect(new URL(window.location.href).searchParams.get('source_id')).toBe('legacy_pg')
  })

  it('同筛选翻页只读取本页摘要，主动刷新重新统计全集', async () => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({
      default_source: 'independent_cdm', sources: [{ id: 'independent_cdm', name: '东华CDM', enabled: true }],
    })
    const first = { id: 'V1', recordKey: '["I","P1","V1"]', institute_id: 'I', patient_id: 'P1', visit_id: 'V1' }
    const second = { id: 'V2', recordKey: '["I","P2","V2"]', institute_id: 'I', patient_id: 'P2', visit_id: 'V2' }
    const pageTwo = response({ records: [second], total: 80, page: 2 })
    const totals = { total_records: 80, ready_records: 1, status_counts: { data_gap: 1 } }
    vi.mocked(ApiService.getRaw)
      .mockResolvedValueOnce(response({ records: [first], total: 80, page: 1 }))
      .mockResolvedValue(pageTwo)
    vi.mocked(ApiService.postRaw)
      .mockResolvedValueOnce(response({ qc_summary: totals, records: [] }))
      .mockResolvedValueOnce(response({ records: [{ recordKey: second.recordKey, latest_qc_summary: { status: 'not_run' } }] }))
      .mockResolvedValueOnce(response({ qc_summary: { ...totals, ready_records: 2 }, records: [] }))

    const records = usePatientRecords('discharged')
    await records.fetchData()
    await flushPromises()
    expect(records.qcSummary.value.readyRecords).toBe(1)
    records.handlePageChange(2)
    await flushPromises()
    expect(ApiService.postRaw).toHaveBeenNthCalledWith(2, '/api/medical-records/workstation/qc-summary',
      { record_keys: [second.recordKey], include_totals: false }, expect.anything())
    expect(records.qcSummary.value.readyRecords).toBe(1)
    expect(records.allRecords.value[0].latestQcSummary?.status).toBe('not_run')
    records.refreshData()
    await flushPromises()
    expect(ApiService.postRaw).toHaveBeenNthCalledWith(3, '/api/medical-records/workstation/qc-summary',
      { record_keys: [second.recordKey] }, expect.anything())
    expect(records.qcSummary.value.readyRecords).toBe(2)
  })

  it('已有总计在翻页等待和失败时可用，越界空页不请求行摘要', async () => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({
      default_source: 'independent_cdm', sources: [{ id: 'independent_cdm', name: '东华CDM', enabled: true }],
    })
    const record = { id: 'V', recordKey: '["I","P","V"]', institute_id: 'I', patient_id: 'P', visit_id: 'V' }
    vi.mocked(ApiService.getRaw)
      .mockResolvedValueOnce(response({ records: [record], total: 80, page: 1 }))
      .mockResolvedValueOnce(response({ records: [record], total: 80, page: 2 }))
      .mockResolvedValueOnce(response({ records: [], total: 80, page: 3 }))
    let rejectRows: (error: Error) => void = () => { throw new Error('未发起行摘要请求') }
    vi.mocked(ApiService.postRaw)
      .mockResolvedValueOnce(response({ qc_summary: { total_records: 80, ready_records: 9 }, records: [] }))
      .mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectRows = reject }))

    const records = usePatientRecords('discharged')
    await records.fetchData()
    await flushPromises()
    records.handlePageChange(2)
    await flushPromises()
    expect(records.qcSummaryState.value).toBe('pending')
    expect(records.qcTotalsReady.value).toBe(true)
    expect(records.qcSummary.value.readyRecords).toBe(9)
    rejectRows(new Error('本页摘要超时'))
    await flushPromises()
    expect(records.qcSummaryState.value).toBe('unavailable')
    expect(records.qcTotalsReady.value).toBe(true)
    expect(records.qcSummary.value.readyRecords).toBe(9)

    records.handlePageChange(3)
    await flushPromises()
    expect(records.allRecords.value).toEqual([])
    expect(records.qcSummaryState.value).toBe('ready')
    expect(records.qcTotalsReady.value).toBe(true)
    expect(ApiService.postRaw).toHaveBeenCalledTimes(2)
  })

  it.each([false, true])('终末列表先显示，摘要独立返回或失败（失败=%s）', async (failed) => {
    vi.mocked(clinicalSourcesApi.options).mockResolvedValue({
      default_source: 'independent_cdm', sources: [{ id: 'independent_cdm', name: '东华CDM', enabled: true }],
    })
    const recordKey = '["I","P","V"]'
    const summary = response({
      qc_summary: { total_records: 2, ready_records: 1, status_counts: { data_gap: 1 } },
      records: [
        { recordKey: '["I","other","V"]', latest_qc_summary: { status: 'not_run' } },
        { recordKey, latest_qc_summary: { status: 'ready', status_counts: { data_gap: 1 } } },
      ],
    })
    let settleSummary: () => void = () => { throw new Error('未发起摘要请求') }
    vi.mocked(ApiService.getRaw)
      .mockResolvedValueOnce(response({ records: [{ id: 'V', recordKey, institute_id: 'I', patient_id: 'P', visit_id: 'V' }], total: 2 }))
    vi.mocked(ApiService.postRaw)
      .mockImplementationOnce(() => new Promise((resolve, reject) => {
        settleSummary = () => failed ? reject(new Error('摘要超时')) : resolve(summary)
      }))
    const records = usePatientRecords('discharged')
    records.dateField.value = 'discharge'
    records.searchText.value = '合成'
    await records.fetchData(1, 15)
    expect(records.loading.value).toBe(false)
    expect(records.allRecords.value[0].recordKey).toBe(recordKey)
    expect(records.allRecords.value[0].latestQcSummary).toBeUndefined()
    const params = { page: 1, page_size: 15, hospital_status: 'discharged', date_field: 'discharge', source_id: 'independent_cdm', keyword: '合成' }
    expect(ApiService.getRaw).toHaveBeenNthCalledWith(
      1,
      '/api/medical-records/workstation',
      { ...params, qc_summary_mode: 'deferred' },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(ApiService.postRaw).toHaveBeenCalledWith(
      '/api/medical-records/workstation/qc-summary', { record_keys: [recordKey] },
      expect.objectContaining({
        params: { hospital_status: 'discharged', date_field: 'discharge', source_id: 'independent_cdm', keyword: '合成' },
        signal: expect.any(AbortSignal),
      }),
    )
    settleSummary()
    await flushPromises()
    expect(records.loadError.value).toBe(false)
    expect(records.allRecords.value[0].recordKey).toBe(recordKey)
    if (failed) {
      expect(records.qcSummaryState.value).toBe('unavailable')
      expect(records.allRecords.value[0].latestQcSummary).toBeUndefined()
    } else {
      expect(records.qcSummaryState.value).toBe('ready')
      expect(records.qcSummary.value.totalRecords).toBe(2)
      expect(records.allRecords.value[0].latestQcSummary?.status).toBe('ready')
    }
  })
})
