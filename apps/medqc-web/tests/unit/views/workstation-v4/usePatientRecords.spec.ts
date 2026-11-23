import { describe, expect, it, beforeEach, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getRaw: vi.fn(),
  postRaw: vi.fn(),
}))

vi.mock('@/api/clinicalSources', () => ({
  clinicalSourcesApi: { options: vi.fn(async () => ({ default_source: 'legacy_pg', sources: [
    { id: 'legacy_pg', name: '原有数据源', enabled: true },
    { id: 'independent_cdm', name: '服务器CDM', enabled: true },
  ] })) },
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: mocks.getRaw,
    postRaw: mocks.postRaw,
  },
}))

import { usePatientRecords } from '@/views/workstation-v4/composables/usePatientRecords'

function mockWorkstationResponse() {
  mocks.postRaw.mockResolvedValue({ data: { records: [], qc_summary: { total_records: 1 } } })
  mocks.getRaw.mockResolvedValue({
    data: {
      records: [
        {
          id: 'V1',
          visitId: 'V1',
          name: '张三',
          department: '中医科',
          admissionDate: '2026-05-25',
          dischargeDate: '',
          dischargeDatetime: '2026-05-30 08:20:30',
          updateTime: '2026-05-30 09:10:11',
          sortTime: '2026-05-30 09:10:11',
        },
      ],
      departments: [
        { name: '全部科室', total: 1 },
        { name: '中医科', total: 1 },
      ],
      doctors: [
        { name: '全部主管医师', total: 1 },
        { name: '陈医师', total: 1 },
      ],
      total: 1,
      page: 1,
      pageSize: 15,
      totalPages: 1,
    },
  })
}

describe('usePatientRecords workstation filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
    mockWorkstationResponse()
  })

  it('uses the analytics drill-down department from the URL for the server query', async () => {
    window.history.replaceState({}, '', '/workstation-v5?department=ICU&analytics_scope=final')
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.activeDept.value).toBe('ICU')
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      dept: 'ICU',
      analytics_scope: 'final',
    })
  })

  it('fetchData sends department, attending physician, keyword and date filters to backend', async () => {
    const records = usePatientRecords()
    records.activeDept.value = '中医科'
    records.activeDoctor.value = '陈医师'
    records.searchText.value = '张三'
    records.dateRange.value = ['2026-05-01', '2026-05-31']
    records.dateField.value = 'admission'
    records.hospFilter.value = 'inpatient'

    await records.fetchData(2, 10)

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 2,
      page_size: 10,
      source_id: 'independent_cdm',
      date_field: 'admission',
      dept: '中医科',
      doctor: '陈医师',
      keyword: '张三',
      start_date: '2026-05-01',
      end_date: '2026-05-31',
      hospital_status: 'inpatient',
    })
  })

  it('允许运行和终末页面以显式初始住院状态固定服务端范围', async () => {
    const runningRecords = usePatientRecords('inpatient')
    await runningRecords.fetchData()

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      hospital_status: 'inpatient',
    })

    const finalRecords = usePatientRecords('discharged')
    await finalRecords.fetchData()

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      hospital_status: 'discharged',
    })
  })

  it('switches hospital status through the backend from the first page without local filtering', async () => {
    const records = usePatientRecords()
    records.currentPage.value = 3

    records.selectHospFilter('discharged')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      hospital_status: 'discharged',
    })
  })

  it('sends the explicit today-synced inpatient scope to the backend', async () => {
    const records = usePatientRecords()
    records.syncScope.value = 'today_inpatient'

    await records.fetchData()

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      sync_scope: 'today_inpatient',
    })
  })

  it('requests inpatient length-of-stay sorting from the first page', async () => {
    const records = usePatientRecords()
    records.hospFilter.value = 'inpatient'
    records.currentPage.value = 3

    records.selectInpatientSort('longest')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      hospital_status: 'inpatient',
      inpatient_sort: 'longest',
    })
  })

  it('keeps backend sort time metadata for displaying newest synced records first', async () => {
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.allRecords.value[0].updateTime).toBe('2026-05-30 09:10:11')
    expect(records.allRecords.value[0].sortTime).toBe('2026-05-30 09:10:11')
    expect(records.allRecords.value[0].dischargeDatetime).toBe('2026-05-30 08:20:30')
    expect(records.allRecords.value[0].dischargeDate).toBe('2026-05-30')
  })

  it('retains the backend triple record key instead of reducing a record to visit ID', async () => {
    mocks.getRaw.mockResolvedValueOnce({
      data: {
        records: [
          {
            id: 'V1',
            visit_id: 'V1',
            record_key: '["H-2","P-2","V1"]',
            name: '李四',
            department: '外科',
          },
        ],
        total: 1,
        page: 1,
      },
    })
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.allRecords.value[0]).toMatchObject({
      id: 'V1',
      visitId: 'V1',
      recordKey: '["H-2","P-2","V1"]',
    })
  })

  it('selectDept resets page and triggers backend query', async () => {
    const records = usePatientRecords()
    records.currentPage.value = 3
    records.activeDoctor.value = '陈医师'

    records.selectDept('普通外科')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(records.activeDoctor.value).toBe('全部主管医师')
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      dept: '普通外科',
    })
  })

  it('selectDoctor resets page and applies the server-side attending physician filter', async () => {
    const records = usePatientRecords()
    records.currentPage.value = 3

    records.selectDoctor('陈医师')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(records.activeDoctor.value).toBe('陈医师')
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      qc_summary_mode: 'deferred',
      page: 1,
      page_size: 15,
      source_id: 'independent_cdm',
      date_field: 'visit',
      doctor: '陈医师',
    })
    expect(records.doctors.value).toEqual([
      { name: '全部主管医师', total: 1 },
      { name: '陈医师', total: 1 },
    ])
  })

  it('resetFilters clears department, search and date filters', () => {
    const records = usePatientRecords()
    records.activeDept.value = '普通外科'
    records.activeDoctor.value = '陈医师'
    records.searchText.value = '李四'
    records.dateRange.value = ['2026-05-01', '2026-05-31']
    records.dateField.value = 'discharge'
    records.hospFilter.value = 'inpatient'
    records.syncScope.value = 'today_inpatient'
    records.currentPage.value = 5

    records.resetFilters()

    expect(records.activeDept.value).toBe('全部科室')
    expect(records.activeDoctor.value).toBe('全部主管医师')
    expect(records.searchText.value).toBe('')
    expect(records.dateRange.value).toBeNull()
    expect(records.dateField.value).toBe('visit')
    expect(records.hospFilter.value).toBe('all')
    expect(records.syncScope.value).toBe('all')
    expect(records.currentPage.value).toBe(1)
  })

  it('过期请求不会覆盖较新筛选响应或其全量汇总', async () => {
    let resolveFirst: ((value: unknown) => void) | undefined
    const firstResponse = new Promise((resolve) => {
      resolveFirst = resolve
    })
    mocks.getRaw.mockReset()
    mocks.getRaw.mockImplementationOnce(() => firstResponse)
    mocks.getRaw.mockResolvedValueOnce({
      data: {
        records: [
          {
            id: 'newest',
            visit_id: 'newest',
            record_key: '["H","P","newest"]',
            institute_id: 'H',
            patient_id: 'P',
            name: '新筛选结果',
          },
        ],
        total: 1,
        page: 1,
      },
    })
    mocks.postRaw.mockResolvedValueOnce({
      data: { records: [], qc_summary: { total_records: 1, ready_records: 1 } },
    })
    const records = usePatientRecords('inpatient')
    records.searchText.value = '旧条件'
    const firstRequest = records.fetchData()
    await flushPromises()
    records.searchText.value = '新条件'
    const secondRequest = records.fetchData()

    await secondRequest
    resolveFirst?.({
      data: {
        records: [{ id: 'stale', name: '旧筛选结果' }],
        total: 99,
        page: 1,
        qc_summary: { total_records: 99, ready_records: 99 },
      },
    })
    await firstRequest

    expect(records.allRecords.value.map((item) => item.name)).toEqual(['新筛选结果'])
    expect(records.qcSummary.value).toMatchObject({ totalRecords: 1, readyRecords: 1 })
    expect(records.loading.value).toBe(false)
  })

  it.each(['筛选', '分页'])('忽略%s切换后迟到的旧摘要', async (change) => {
    const oldKey = '["H","P","V1"]'
    const nextKey = '["H","P","V2"]'
    const nextPage = change === '分页' ? 2 : 1
    const list = (recordKey: string, id: string, page: number) => ({
      data: { total: 2, page, records: [{ id, recordKey }] },
    })
    const summary = (recordKey: string, count: number) => ({ data: {
      qc_summary: { total_records: 2, status_counts: { data_gap: count } },
      records: [{ recordKey, latest_qc_summary: { status: 'ready', status_counts: { data_gap: count } } }],
    } })
    let resolveOldSummary: (value: ReturnType<typeof summary>) => void = () => {}
    mocks.getRaw
      .mockResolvedValueOnce(list(oldKey, 'V1', 1))
      .mockResolvedValueOnce(list(nextKey, 'V2', nextPage))
    mocks.postRaw
      .mockImplementationOnce(() => new Promise((resolve) => { resolveOldSummary = resolve }))
      .mockResolvedValueOnce(summary(nextKey, 1))
    const records = usePatientRecords()
    await records.fetchData()
    const oldSignal = mocks.postRaw.mock.calls[0][2].signal
    if (change === '筛选') records.searchText.value = '新条件'
    await records.fetchData(nextPage)
    expect(oldSignal.aborted).toBe(true)
    expect(mocks.postRaw.mock.calls[1][1]).toEqual({ record_keys: [nextKey] })
    resolveOldSummary(summary(oldKey, 99))
    await flushPromises()
    expect(records.currentPage.value).toBe(nextPage)
    expect(records.qcSummary.value.statusCounts).toEqual({ data_gap: 1 })
    expect(records.allRecords.value[0].latestQcSummary?.statusCounts).toEqual({ data_gap: 1 })
  })
})


describe('独立CDM状态筛选', () => {
  it('固定CDM保留未知状态且拒绝切回旧源', async () => {
    window.history.replaceState({}, '', '/workstation-v5?source_id=independent_cdm')
    mockWorkstationResponse()
    const records = usePatientRecords()
    await records.fetchData()
    expect(records.hospOptions.value.map((option) => option.value)).toContain('unknown')
    records.selectHospFilter('unknown')
    await flushPromises()
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', expect.objectContaining({
      source_id: 'independent_cdm', hospital_status: 'unknown', qc_summary_mode: 'deferred',
    }))
    expect(() => records.selectSource('legacy_pg')).toThrow('普通病历固定读取东华CDM')
    expect(records.sourceId.value).toBe('independent_cdm')
    expect(records.hospOptions.value.map((option) => option.value)).toContain('unknown')
    expect(records.hospFilter.value).toBe('unknown')
  })
})
