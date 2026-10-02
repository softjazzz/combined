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

async function flushPromises() {
  await Promise.resolve()
  await Promise.resolve()
}

describe('usePatientRecords workstation filters', () => {
  it('账号失效立即清除旧汇总与评分标准，迟到响应不能恢复', async () => {
    const records = usePatientRecords('inpatient')
    records.qcSummary.value = { ...records.qcSummary.value, totalRecords: 88, readyRecords: 77 }
    records.scoreStandards.value = {
      running: { status: 'configured', standardId: 'old', standardName: '旧账号标准', standardUpdatedAt: null },
    }
    let resolveOld!: (value: unknown) => void
    mocks.getRaw.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve }))
    const pending = records.fetchData()
    records.invalidateData()
    expect(records.qcSummary.value.totalRecords).toBe(0)
    expect(records.qcSummary.value.readyRecords).toBe(0)
    expect(records.scoreStandards.value).toEqual({})
    resolveOld({ data: { records: [], total: 88, qc_summary: { total_records: 88 }, score_standards: { running: { status: 'configured', standard_id: 'old' } } } })
    await pending
    expect(records.qcSummary.value.totalRecords).toBe(0)
    expect(records.scoreStandards.value).toEqual({})
  })
  it('列查询交给服务端分页前处理，清除排序恢复默认请求', async () => {
    const records = usePatientRecords('inpatient')
    records.columnFilters.value = { patient: '患者甲', score: '0' }
    records.columnSort.value = 'score'
    records.columnDirection.value = 'desc'
    await records.fetchData(2)
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      page: 2,
      column_filters: '{"patient":"患者甲","score":"0"}',
      column_sort: 'score',
      column_direction: 'desc',
    })
    records.columnSort.value = ''
    records.columnFilters.value = {}
    await records.fetchData(1)
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('column_sort')
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('column_filters')
  })

  it('服务端拒绝超量列查询时保留错误，不能展示为成功的空列表', async () => {
    mocks.getRaw.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: '列查询超过5000，请缩小范围' } },
    })
    const records = usePatientRecords('inpatient')
    await records.fetchData()
    expect(records.loadError.value).toBe(true)
    expect(records.loadErrorMessage.value).toContain('5000')
  })
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
      page: 1,
      page_size: 15,
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
      page: 2,
      page_size: 10,
      date_field: 'admission',
      dept: '中医科',
      doctor: '陈医师',
      keyword: '张三',
      start_date: '2026-05-01',
      end_date: '2026-05-31',
      hospital_status: 'inpatient',
    })
  })

  it('审核状态多选以逗号分隔传给服务端，空数组不带参数，重置清空', async () => {
    const records = usePatientRecords('inpatient')
    records.reviewStateFilter.value = ['pending_review', 'pending_recheck']
    await records.fetchData(1)
    expect(mocks.getRaw).toHaveBeenLastCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
      date_field: 'visit',
      hospital_status: 'inpatient',
      review_state: 'pending_review,pending_recheck',
    })

    records.resetFilters()
    expect(records.reviewStateFilter.value).toEqual([])
    await records.fetchData(1)
    expect(mocks.getRaw.mock.lastCall?.[1]).not.toHaveProperty('review_state')
  })

  it('评分标准、状态、等级与分数区间传给服务端，重置全部清空', async () => {
    const records = usePatientRecords('inpatient')
    records.standardIdFilter.value = '11111111-1111-4111-8111-111111111111'
    records.scoreStatusFilter.value = 'scored'
    records.gradeFilter.value = '甲'
    records.scoreMinFilter.value = 80
    records.scoreMaxFilter.value = 99.5
    await records.fetchData(1)
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      standard_id: '11111111-1111-4111-8111-111111111111',
      score_status: 'scored',
      grade: '甲',
      score_min: 80,
      score_max: 99.5,
    })

    records.resetFilters()
    expect(records.standardIdFilter.value).toBe('')
    expect(records.scoreStatusFilter.value).toBe('')
    expect(records.gradeFilter.value).toBe('')
    expect(records.scoreMinFilter.value).toBeNull()
    expect(records.scoreMaxFilter.value).toBeNull()
  })

  it('缺陷视图请求真实来源并规范化缺陷明细，重置回病历视图', async () => {
    mocks.getRaw.mockResolvedValueOnce({
      data: {
        records: [],
        defects: [
          {
            institute_id: 'H1',
            patient_id: 'P1',
            visit_id: 'V1',
            patient_name: '患者甲',
            source: 'manual',
            defect_id: 'D1',
            rule_id: 'M1',
            rule_name: '人工缺陷',
            document: '病程记录',
            description: '描述',
            status: 'approved',
            occurred_at: '2026-09-30',
          },
        ],
        total: 1,
      },
    })
    const records = usePatientRecords('inpatient')
    records.resultView.value = 'defects'
    records.defectSourceFilter.value = 'manual'
    await records.fetchData(1)
    expect(mocks.getRaw.mock.lastCall?.[1]).toMatchObject({
      result_view: 'defects',
      defect_source: 'manual',
      hospital_status: 'inpatient',
    })
    expect(records.defects.value[0]).toMatchObject({
      source: 'manual',
      defect_id: 'D1',
      visit_id: 'V1',
    })

    records.resetFilters()
    expect(records.resultView.value).toBe('records')
    expect(records.defectSourceFilter.value).toBe('all')
    expect(records.hasDefectFilter.value).toBeNull()
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

  it('sends the explicit today-synced inpatient scope to the backend', async () => {
    const records = usePatientRecords()
    records.syncScope.value = 'today_inpatient'

    await records.fetchData()

    expect(mocks.getRaw).toHaveBeenCalledWith('/api/medical-records/workstation', {
      page: 1,
      page_size: 15,
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
      page: 1,
      page_size: 15,
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
      page: 1,
      page_size: 15,
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
      page: 1,
      page_size: 15,
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
