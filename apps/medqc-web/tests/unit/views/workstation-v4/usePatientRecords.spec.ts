import { describe, expect, it, beforeEach, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getRaw: vi.fn(),
}))

vi.mock('@/services/apiService', () => ({
  ApiService: {
    getRaw: mocks.getRaw,
  },
}))

import { usePatientRecords } from '@/views/workstation-v4/composables/usePatientRecords'

function mockWorkstationResponse() {
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
          updateTime: '2026-05-30 09:10:11',
          sortTime: '2026-05-30 09:10:11',
        },
      ],
      departments: [
        { name: '全部科室', total: 1 },
        { name: '中医科', total: 1 },
      ],
      total: 1,
      page: 1,
      pageSize: 15,
      totalPages: 1,
    },
  })
}

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('usePatientRecords workstation filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.history.replaceState({}, '', '/')
    mockWorkstationResponse()
  })

  it('uses the analytics drill-down department from the URL for the server query', async () => {
    window.history.replaceState({}, '', '/workstation-v4?department=ICU&analytics_scope=final')
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.activeDept.value).toBe('ICU')
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'visit',
      dept: 'ICU',
      analytics_scope: 'final',
    })
  })

  it('fetchData sends department, keyword and date filters to backend', async () => {
    const records = usePatientRecords()
    records.activeDept.value = '中医科'
    records.searchText.value = '张三'
    records.dateRange.value = ['2026-05-01', '2026-05-31']
    records.dateField.value = 'admission'
    records.hospFilter.value = 'inpatient'

    await records.fetchData(2, 10)

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      page: 2,
      page_size: 10,
      date_field: 'admission',
      dept: '中医科',
      keyword: '张三',
      start_date: '2026-05-01',
      end_date: '2026-05-31',
      hospital_status: 'inpatient',
    })
  })

  it('允许运行和终末页面以显式初始住院状态固定服务端范围', async () => {
    const runningRecords = usePatientRecords('inpatient')
    await runningRecords.fetchData()

    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'visit',
      hospital_status: 'inpatient',
    })

    const finalRecords = usePatientRecords('discharged')
    await finalRecords.fetchData()

    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
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
      page: 1,
      page_size: 15,
      date_field: 'visit',
      hospital_status: 'discharged',
    })
  })

  it('keeps backend sort time metadata for displaying newest synced records first', async () => {
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.allRecords.value[0].updateTime).toBe('2026-05-30 09:10:11')
    expect(records.allRecords.value[0].sortTime).toBe('2026-05-30 09:10:11')
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

    records.selectDept('普通外科')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'visit',
      dept: '普通外科',
    })
  })

  it('resetFilters clears department, search and date filters', () => {
    const records = usePatientRecords()
    records.activeDept.value = '普通外科'
    records.searchText.value = '李四'
    records.dateRange.value = ['2026-05-01', '2026-05-31']
    records.dateField.value = 'discharge'
    records.hospFilter.value = 'inpatient'
    records.currentPage.value = 5

    records.resetFilters()

    expect(records.activeDept.value).toBe('全部科室')
    expect(records.searchText.value).toBe('')
    expect(records.dateRange.value).toBeNull()
    expect(records.dateField.value).toBe('visit')
    expect(records.hospFilter.value).toBe('all')
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
        qc_summary: { total_records: 1, ready_records: 1 },
      },
    })
    const records = usePatientRecords('inpatient')
    records.searchText.value = '旧条件'
    const firstRequest = records.fetchData()
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
})
