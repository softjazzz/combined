import { computed, ref } from 'vue'
import { ApiService } from '@/services/apiService'
import type { DeptInfo, PatientRecord, RecordPoolQcSummary } from '../types'
import { normalizeRecord, normalizeRecordPoolQcSummary } from '../normalize'

const WORKSTATION_PAGE_SIZE = 15
const EMPTY_QC_SUMMARY: RecordPoolQcSummary = {
  totalRecords: 0,
  readyRecords: 0,
  notRunRecords: 0,
  technicalErrorRecords: 0,
  statusCounts: {},
  runningState: 'unknown',
}
export type WorkstationDateField = 'visit' | 'admission' | 'discharge' | 'updated'
export type WorkstationDateRange = [string, string] | null

function normalizeDepartment(raw: unknown): DeptInfo {
  const source = (raw || {}) as Record<string, unknown>
  const name = String(source.name ?? source.department ?? source.dept_name ?? '未分科室').trim()
  const total = Number(source.total ?? source.count ?? 0)
  const warningCount = Number(source.warningCount ?? source.warning_count ?? 0)
  return {
    name: name || '未分科室',
    total: Number.isFinite(total) ? total : 0,
    warningCount: Number.isFinite(warningCount) ? warningCount : 0,
  }
}

function buildDepartments(records: PatientRecord[]): DeptInfo[] {
  const map = new Map<string, DeptInfo>()
  for (const record of records) {
    const name = record.department || '未分科室'
    const current = map.get(name) || { name, total: 0, warningCount: 0 }
    current.total += 1
    if (record.status === 'warning' || record.status === 'has_defects') {
      current.warningCount += 1
    }
    map.set(name, current)
  }
  const values = [...map.values()].sort((a, b) => b.total - a.total)
  return [
    {
      name: '全部科室',
      total: records.length,
      warningCount: values.reduce((sum, item) => sum + item.warningCount, 0),
    },
    ...values,
  ]
}

export function usePatientRecords() {
  const allRecords = ref<PatientRecord[]>([])
  const departments = ref<DeptInfo[]>([])
  const currentPage = ref(1)
  const pageSize = ref(WORKSTATION_PAGE_SIZE)
  const serverTotal = ref(0)
  const serverTotalPages = ref(1)
  const totalCount = computed(() => serverTotal.value)
  const loading = ref(false)
  const loadError = ref(false)
  const qcSummary = ref<RecordPoolQcSummary>({ ...EMPTY_QC_SUMMARY })

  const activeDept = ref('\u5168\u90e8\u79d1\u5ba4')
  const searchText = ref('')
  const dateRange = ref<WorkstationDateRange>(null)
  const dateField = ref<WorkstationDateField>('visit')
  const hospFilter = ref<'all' | 'inpatient' | 'discharged'>('all')

  const hospOptions = [
    { value: 'all', label: '\u5168\u90e8' },
    { value: 'inpatient', label: '\u5728\u9662' },
    { value: 'discharged', label: '\u5df2\u51fa\u9662' },
  ]

  // 在院/已出院尚未接入服务端筛选；禁止对当前页病历做本地筛选造成假统计。
  const scopedRecords = computed(() => allRecords.value)

  const filteredRecords = computed(() => scopedRecords.value)

  async function fetchData(page = 1, targetPageSize = pageSize.value) {
    loading.value = true
    loadError.value = false
    try {
      const [startDate, endDate] = dateRange.value || []
      const requestedPageSize =
        Number.isFinite(Number(targetPageSize)) && Number(targetPageSize) > 0
          ? Number(targetPageSize)
          : WORKSTATION_PAGE_SIZE
      const params: Record<string, string | number> = {
        page,
        page_size: requestedPageSize,
        date_field: dateField.value,
      }
      if (activeDept.value !== '\u5168\u90e8\u79d1\u5ba4') {
        params.dept = activeDept.value
      }
      const keyword = searchText.value.trim()
      if (keyword) {
        params.keyword = keyword
      }
      if (startDate) {
        params.start_date = startDate
      }
      if (endDate) {
        params.end_date = endDate
      }
      if (hospFilter.value !== 'all') {
        params.hospital_status = hospFilter.value
      }
      const analyticsKeys = [
        'analytics_job_id',
        'analytics_completed_from',
        'analytics_completed_to',
        'analytics_rule_id',
        'analytics_result_status',
      ] as const
      const analyticsQuery = new URLSearchParams(window.location.search)
      for (const key of analyticsKeys) {
        const value = analyticsQuery.get(key)
        if (value?.trim()) {
          params[key] = value.trim()
        }
      }

      const response = await ApiService.getRaw('/api/medical-records/workstation', {
        params,
      })
      const raw = response.data as Record<string, unknown>
      const data = (
        raw && typeof raw === 'object' && 'data' in raw
          ? (raw.data as Record<string, unknown>)
          : raw
      ) as Record<string, unknown>

      const normalizedRecords = Array.isArray(data.records)
        ? data.records.map((record: unknown) => normalizeRecord(record))
        : []
      allRecords.value = normalizedRecords
      departments.value =
        Array.isArray(data.departments) && data.departments.length > 0
          ? data.departments.map((dept: unknown) => normalizeDepartment(dept))
          : buildDepartments(normalizedRecords)

      const total = Number(data.total ?? data.total_count ?? 0)
      const totalPagesComputed = requestedPageSize > 0 ? Math.ceil(total / requestedPageSize) : 1

      serverTotal.value = total
      serverTotalPages.value = Math.max(1, totalPagesComputed || 1)
      currentPage.value = Number(data.page ?? data.current_page ?? page) || 1
      pageSize.value = requestedPageSize
      qcSummary.value = normalizeRecordPoolQcSummary(data.qc_summary)
    } catch (error) {
      console.error('\u52a0\u8f7d\u5de5\u4f5c\u53f0\u6570\u636e\u5931\u8d25:', error)
      loadError.value = true
      qcSummary.value = { ...EMPTY_QC_SUMMARY }
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number, nextPageSize?: number) {
    const normalizedPageSize =
      Number.isFinite(Number(nextPageSize)) && Number(nextPageSize) > 0
        ? Number(nextPageSize)
        : pageSize.value
    const pageSizeChanged = normalizedPageSize !== pageSize.value
    pageSize.value = normalizedPageSize
    const nextPage = pageSizeChanged ? 1 : page
    currentPage.value = nextPage
    fetchData(nextPage, normalizedPageSize)
    document.querySelector('.custom-scrollbar')?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function refreshData() {
    fetchData(currentPage.value)
  }

  function selectDept(deptName: string) {
    activeDept.value = deptName
    currentPage.value = 1
    fetchData(1)
  }

  function selectHospFilter(value: typeof hospFilter.value) {
    const nextValue = hospOptions.some((option) => option.value === value) ? value : 'all'
    if (hospFilter.value === nextValue) return
    hospFilter.value = nextValue
    currentPage.value = 1
    fetchData(1)
  }

  function resetFilters() {
    activeDept.value = '\u5168\u90e8\u79d1\u5ba4'
    searchText.value = ''
    dateRange.value = null
    dateField.value = 'visit'
    hospFilter.value = 'all'
    currentPage.value = 1
  }

  return {
    allRecords,
    departments,
    currentPage,
    pageSize,
    serverTotal,
    serverTotalPages,
    totalCount,
    loading,
    loadError,
    qcSummary,
    activeDept,
    searchText,
    dateRange,
    dateField,
    hospFilter,
    hospOptions,
    filteredRecords,
    fetchData,
    handlePageChange,
    refreshData,
    selectDept,
    selectHospFilter,
    resetFilters,
  }
}
