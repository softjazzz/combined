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
      pageSize: 20,
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
    mockWorkstationResponse()
  })

  it('fetchData sends department, keyword and date filters to backend', async () => {
    const records = usePatientRecords()
    records.activeDept.value = '中医科'
    records.searchText.value = '张三'
    records.dateRange.value = ['2026-05-01', '2026-05-31']
    records.dateField.value = 'admission'

    await records.fetchData(2, 10)

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      params: {
        page: 2,
        page_size: 10,
        date_field: 'admission',
        dept: '中医科',
        keyword: '张三',
        start_date: '2026-05-01',
        end_date: '2026-05-31',
      },
    })
  })

  it('keeps backend sort time metadata for displaying newest synced records first', async () => {
    const records = usePatientRecords()

    await records.fetchData()

    expect(records.allRecords.value[0].updateTime).toBe('2026-05-30 09:10:11')
    expect(records.allRecords.value[0].sortTime).toBe('2026-05-30 09:10:11')
  })

  it('selectDept resets page and triggers backend query', async () => {
    const records = usePatientRecords()
    records.currentPage.value = 3

    records.selectDept('普通外科')
    await flushPromises()

    expect(records.currentPage.value).toBe(1)
    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      params: {
        page: 1,
        page_size: 20,
        date_field: 'visit',
        dept: '普通外科',
      },
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
})
