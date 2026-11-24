import {
  clinicalSourcesApi,
  type ClinicalSourceId,
  type ClinicalSourceMode,
  type ClinicalSourceOption,
} from '@/api/clinicalSources'
import {
  resetClinicalSourceMode,
  setClinicalSourceMode,
  setPageClinicalSource,
} from '@/utils/clinical-source'
import { computed, getCurrentScope, onScopeDispose, ref } from 'vue'
import { ApiService } from '@/services/apiService'
import type { DeptInfo, DoctorInfo, PatientRecord, QcSummaryLoadState, RecordPoolQcSummary } from '../types'
import { normalizeRecord, normalizeRecordLatestQcSummary, normalizeRecordPoolQcSummary } from '../normalize'
import { WORKSTATION_LIST_PAGE_SIZE } from '../utils/workstationListPagination'

const WORKSTATION_URL = '/api/medical-records/workstation'
const ALL_DEPARTMENTS = '全部科室'
const ALL_DOCTORS = '全部主管医师'
const CLINICAL_SOURCE_OPTIONS_TTL_MS = 60_000
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
export type HospitalStatusScope = 'all' | 'inpatient' | 'discharged' | 'unknown'
export type RecordPoolSyncScope = 'all' | 'today_inpatient'
export type InpatientSort = 'default' | 'longest' | 'recent'

type ClinicalSourceOptionsResult = Awaited<ReturnType<typeof clinicalSourcesApi.options>>
type ClinicalSourceOptionsLoader = typeof clinicalSourcesApi.options

interface CachedClinicalSourceOptions {
  value: ClinicalSourceOptionsResult
  expiresAt: number
  loader: ClinicalSourceOptionsLoader
  mockImpl: unknown
}

interface InFlightClinicalSourceOptions {
  promise: Promise<ClinicalSourceOptionsResult>
  loader: ClinicalSourceOptionsLoader
  mockImpl: unknown
}

let cachedClinicalSourceOptions: CachedClinicalSourceOptions | null = null
let inFlightClinicalSourceOptions: InFlightClinicalSourceOptions | null = null

function getMockImplementationIdentity(loader: unknown): unknown {
  if (typeof loader !== 'function') return undefined
  const maybeMock = loader as { getMockImplementation?: () => unknown }
  return typeof maybeMock.getMockImplementation === 'function'
    ? maybeMock.getMockImplementation()
    : undefined
}

export function resetClinicalSourceOptionsCache() {
  cachedClinicalSourceOptions = null
  inFlightClinicalSourceOptions = null
  resetClinicalSourceMode()
}

if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
  window.addEventListener('medqc:clinical-sources-saved', resetClinicalSourceOptionsCache)
}

function resolveRequestedClinicalSource(
  options: ClinicalSourceOptionsResult,
  urlSourceId?: string | null,
): ClinicalSourceId {
  if (options.mode !== 'legacy_compat') return 'independent_cdm'
  if (
    (urlSourceId === 'legacy_pg' || urlSourceId === 'independent_cdm') &&
    options.sources.some((option) => option.id === urlSourceId && option.enabled)
  ) {
    return urlSourceId
  }
  return options.default_source
}

function isCacheableClinicalSourceOptions(result: unknown): result is ClinicalSourceOptionsResult {
  const candidate = result as Partial<ClinicalSourceOptionsResult> | null | undefined
  const sources = candidate?.sources
  if (!Array.isArray(sources)) return false
  const targetId: unknown =
    candidate?.mode === 'legacy_compat' ? candidate.default_source : 'independent_cdm'
  return sources.some(
    (option) =>
      Boolean(option) &&
      typeof option === 'object' &&
      (option as { id?: unknown }).id === targetId &&
      (option as { enabled?: unknown }).enabled === true,
  )
}

async function loadClinicalSourceOptions(): Promise<ClinicalSourceOptionsResult> {
  const loader = clinicalSourcesApi.options
  const mockImpl = getMockImplementationIdentity(loader)
  if (
    cachedClinicalSourceOptions &&
    cachedClinicalSourceOptions.loader === loader &&
    cachedClinicalSourceOptions.mockImpl === mockImpl &&
    Date.now() < cachedClinicalSourceOptions.expiresAt
  ) {
    return cachedClinicalSourceOptions.value
  }
  if (
    inFlightClinicalSourceOptions &&
    inFlightClinicalSourceOptions.loader === loader &&
    inFlightClinicalSourceOptions.mockImpl === mockImpl
  ) {
    return inFlightClinicalSourceOptions.promise
  }

  let tracked!: InFlightClinicalSourceOptions
  const promise = (async () => {
    const result = await loader()
    if (inFlightClinicalSourceOptions === tracked) {
      if (isCacheableClinicalSourceOptions(result)) {
        cachedClinicalSourceOptions = {
          value: result,
          expiresAt: Date.now() + CLINICAL_SOURCE_OPTIONS_TTL_MS,
          loader,
          mockImpl,
        }
      } else {
        cachedClinicalSourceOptions = null
      }
    }
    return result
  })()
  tracked = { promise, loader, mockImpl }
  inFlightClinicalSourceOptions = tracked
  try {
    return await promise
  } finally {
    if (inFlightClinicalSourceOptions === tracked) {
      inFlightClinicalSourceOptions = null
    }
  }
}

function isAbortError(error: unknown, signal?: AbortSignal): boolean {
  if (signal?.aborted) return true
  if (!error || typeof error !== 'object') return false
  const record = error as { code?: unknown; name?: unknown }
  return (
    record.code === 'ERR_CANCELED' ||
    record.name === 'CanceledError' ||
    record.name === 'AbortError'
  )
}

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

function normalizeDoctor(raw: unknown): DoctorInfo {
  const source = (raw || {}) as Record<string, unknown>
  const name = String(source.name ?? source.doctor ?? ALL_DOCTORS).trim()
  const total = Number(source.total ?? source.count ?? 0)
  return {
    name: name || ALL_DOCTORS,
    total: Number.isFinite(total) ? total : 0,
  }
}

function workstationPayload(raw: unknown): Record<string, unknown> {
  const payload = raw && typeof raw === 'object' && 'data' in raw ? raw.data : raw
  if (!payload || typeof payload !== 'object') throw new Error('工作台响应格式无效')
  return payload as Record<string, unknown>
}

/**
 * 病历池的住院状态必须由调用方显式固定到服务端查询。
 * 默认值保留既有全量病历池的行为，运行/终末质控页不会在当前页做本地过滤。
 */
export function usePatientRecords(initialHospitalStatus: HospitalStatusScope = 'all') {
  const initialRouteQuery = new URLSearchParams(window.location.search)
  const initialDepartment = initialRouteQuery.get('department')?.trim()
  const initialDoctor = initialRouteQuery.get('doctor')?.trim()
  const initialKeyword = initialRouteQuery.get('keyword')?.trim() || ''
  const sourceId = ref<ClinicalSourceId | ''>('')
  const sourceMode = ref<ClinicalSourceMode>('fixed_donghua_cdm')
  const sourceOptions = ref<ClinicalSourceOption[]>([])
  let sourceLoading: Promise<void> | undefined
  async function initializeSource() {
    if (sourceId.value) return
    if (!sourceLoading) sourceLoading = (async () => {
      const options = await loadClinicalSourceOptions()
      const mode: ClinicalSourceMode =
        options.mode === 'legacy_compat' ? 'legacy_compat' : 'fixed_donghua_cdm'
      const requested = resolveRequestedClinicalSource(options, initialRouteQuery.get('source_id'))
      if (!options.sources.some((option) => option.id === requested && option.enabled)) {
        resetClinicalSourceOptionsCache()
        throw new Error('当前数据源已停用或无效，请重新选择')
      }
      sourceMode.value = mode
      sourceOptions.value = options.sources
      sourceId.value = requested
      setClinicalSourceMode(mode, sourceId.value)
      setPageClinicalSource(sourceId.value)
    })().finally(() => { sourceLoading = undefined })
    await sourceLoading
  }
  const allRecords = ref<PatientRecord[]>([])
  const departments = ref<DeptInfo[]>([])
  const doctors = ref<DoctorInfo[]>([])
  const currentPage = ref(1)
  const pageSize = ref(WORKSTATION_LIST_PAGE_SIZE)
  const serverTotal = ref(0)
  const serverTotalPages = ref(1)
  const totalCount = computed(() => serverTotal.value)
  const loading = ref(false)
  const loadError = ref(false)
  const qcSummary = ref<RecordPoolQcSummary>({ ...EMPTY_QC_SUMMARY })
  const qcSummaryState = ref<QcSummaryLoadState>('pending')

  const activeDept = ref(initialDepartment || ALL_DEPARTMENTS)
  const activeDoctor = ref(initialDoctor || ALL_DOCTORS)
  const searchText = ref(initialKeyword)
  const dateRange = ref<WorkstationDateRange>(null)
  const committedSearchText = ref(initialKeyword)
  const committedDateRange = ref<WorkstationDateRange>(null)
  const dateField = ref<WorkstationDateField>('visit')
  const hospFilter = ref<HospitalStatusScope>(initialHospitalStatus)
  const syncScope = ref<RecordPoolSyncScope>('all')
  const inpatientSort = ref<InpatientSort>('default')
  let activeRequestSequence = 0
  let listRequest: AbortController | undefined
  let summaryRequest: AbortController | undefined
  const loadedTotals = ref<{ scope: string; total: number }>()
  const qcTotalsReady = computed(() => loadedTotals.value !== undefined)
  if (getCurrentScope()) onScopeDispose(() => {
    ++activeRequestSequence
    listRequest?.abort()
    summaryRequest?.abort()
  })

  const hospOptions = computed<Array<{ value: HospitalStatusScope; label: string }>>(() => [
    { value: 'all', label: '全部病历' },
    { value: 'inpatient', label: '在院' },
    { value: 'discharged', label: '已出院' },
    ...(sourceId.value === 'independent_cdm' ? [{ value: 'unknown' as const, label: '状态未知' }] : []),
  ])

  // 住院状态由服务端筛选；禁止对当前页病历再次本地过滤造成假统计。
  const scopedRecords = computed(() => allRecords.value)

  const filteredRecords = computed(() => scopedRecords.value)

  async function loadQcSummary(
    params: Record<string, string>,
    records: PatientRecord[],
    requestSequence: number,
    includeTotals: boolean,
    scope: string,
    total: number,
  ) {
    const recordKeys = records.flatMap((record) => record.recordKey ? [record.recordKey] : [])
    if (!includeTotals && recordKeys.length === 0) {
      qcSummaryState.value = 'ready'
      return
    }
    const controller = new AbortController()
    summaryRequest = controller
    try {
      const body = includeTotals ? { record_keys: recordKeys } : { record_keys: recordKeys, include_totals: false }
      const response = await ApiService.postRaw(
        `${WORKSTATION_URL}/qc-summary`, body, { params, signal: controller.signal },
      )
      if (requestSequence !== activeRequestSequence) return
      const data = workstationPayload(response.data)
      if (!Array.isArray(data.records) || (includeTotals && !data.qc_summary)) throw new Error('质控摘要响应格式无效')
      const summaries = new Map<string, ReturnType<typeof normalizeRecordLatestQcSummary>>()
      for (const rawRecord of data.records) {
        if (!rawRecord || typeof rawRecord !== 'object') continue
        const record = rawRecord as Record<string, unknown>
        const key =
          typeof record.recordKey === 'string'
            ? record.recordKey
            : typeof record.record_key === 'string'
              ? record.record_key
              : ''
        const rawSummary = record.latest_qc_summary ?? record.latestQcSummary
        if (key && rawSummary) {
          summaries.set(key, normalizeRecordLatestQcSummary(rawSummary))
        }
      }
      allRecords.value = allRecords.value.map((record) => ({
        ...record,
        latestQcSummary: record.recordKey ? summaries.get(record.recordKey) : undefined,
      }))
      if (includeTotals) {
        qcSummary.value = normalizeRecordPoolQcSummary(data.qc_summary)
        loadedTotals.value = { scope, total }
      }
      qcSummaryState.value = 'ready'
    } catch {
      if (requestSequence === activeRequestSequence) qcSummaryState.value = 'unavailable'
    } finally {
      if (summaryRequest === controller) summaryRequest = undefined
    }
  }

  async function fetchData(
    page = 1,
    targetPageSize = pageSize.value,
    isPagination = false,
    allowEmptyPageFallback = true,
  ) {
    const requestSequence = ++activeRequestSequence
    listRequest?.abort()
    summaryRequest?.abort()
    let listController: AbortController | undefined
    loading.value = true
    loadError.value = false
    if (!isPagination) {
      loadedTotals.value = undefined
      qcSummary.value = { ...EMPTY_QC_SUMMARY }
    }
    qcSummaryState.value = 'pending'
    try {
      await initializeSource()
      if (requestSequence !== activeRequestSequence) return
      const [startDate, endDate] = dateRange.value || []
      const requestedPageSize =
        Number.isFinite(Number(targetPageSize)) && Number(targetPageSize) > 0
          ? Number(targetPageSize)
          : WORKSTATION_LIST_PAGE_SIZE
      const params: Record<string, string> = {
        source_id: sourceId.value,
        date_field: dateField.value,
      }
      if (activeDept.value !== ALL_DEPARTMENTS) {
        params.dept = activeDept.value
      }
      if (activeDoctor.value !== ALL_DOCTORS) {
        params.doctor = activeDoctor.value
      }
      const keyword = searchText.value.trim()
      const nextDateRange: WorkstationDateRange =
        startDate || endDate ? [startDate || '', endDate || ''] : null
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
      if (syncScope.value !== 'all') {
        params.sync_scope = syncScope.value
      }
      if (
        inpatientSort.value !== 'default' &&
        (hospFilter.value === 'inpatient' || syncScope.value === 'today_inpatient')
      ) {
        params.inpatient_sort = inpatientSort.value
      }
      const analyticsKeys = [
        'analytics_job_id',
        'analytics_completed_from',
        'analytics_completed_to',
        'analytics_rule_id',
        'analytics_result_status',
        'analytics_scope',
      ] as const
      const analyticsQuery = new URLSearchParams(window.location.search)
      if (analyticsQuery.get('source')?.trim() === 'analytics') {
        for (const key of analyticsKeys) {
          const value = analyticsQuery.get(key)
          if (value?.trim()) {
            params[key] = value.trim()
          }
        }
      }

      listController = new AbortController()
      listRequest = listController
      const response = await ApiService.getRaw(
        WORKSTATION_URL,
        {
          ...params, page, page_size: requestedPageSize, qc_summary_mode: 'deferred',
        },
        { signal: listController.signal },
      )
      const data = workstationPayload(response.data)

      const normalizedRecords = Array.isArray(data.records)
        ? data.records.map((record: unknown) => normalizeRecord(record))
        : []
      // 过期请求不得覆盖较新的筛选、分页或住院状态响应。
      if (requestSequence !== activeRequestSequence) return

      const total = Number(data.total ?? data.total_count ?? 0)
      const totalPagesComputed = requestedPageSize > 0 ? Math.ceil(total / requestedPageSize) : 1
      const resolvedTotalPages = Math.max(1, totalPagesComputed || 1)
      const resolvedPage = Number(data.page ?? data.current_page ?? page) || 1
      if (
        allowEmptyPageFallback &&
        resolvedPage > 1 &&
        normalizedRecords.length === 0 &&
        total > 0
      ) {
        const fallbackPage = Math.max(1, Math.min(resolvedTotalPages, resolvedPage - 1))
        currentPage.value = fallbackPage
        serverTotal.value = total
        serverTotalPages.value = resolvedTotalPages
        pageSize.value = requestedPageSize
        await fetchData(fallbackPage, requestedPageSize, isPagination, false)
        return
      }

      committedSearchText.value = keyword
      committedDateRange.value = nextDateRange
      allRecords.value = normalizedRecords.map((record) => ({
        ...record,
        sourceId: sourceId.value || undefined,
        latestQcSummary: undefined,
      }))
      departments.value =
        Array.isArray(data.departments) && data.departments.length > 0
          ? data.departments.map((dept: unknown) => normalizeDepartment(dept))
          : buildDepartments(normalizedRecords)
      doctors.value =
        Array.isArray(data.doctors) && data.doctors.length > 0
          ? data.doctors.map((doctor: unknown) => normalizeDoctor(doctor))
          : [{ name: ALL_DOCTORS, total: 0 }]

      const scope = JSON.stringify(params)
      const reuseTotals = isPagination && loadedTotals.value?.scope === scope && loadedTotals.value.total === total
      if (!reuseTotals) {
        loadedTotals.value = undefined
        qcSummary.value = { ...EMPTY_QC_SUMMARY }
      }

      serverTotal.value = total
      serverTotalPages.value = resolvedTotalPages
      currentPage.value = resolvedPage
      pageSize.value = requestedPageSize
      if (total > 0) {
        void loadQcSummary(params, normalizedRecords, requestSequence, !reuseTotals, scope, total)
      } else {
        loadedTotals.value = { scope, total }
        qcSummaryState.value = 'ready'
      }
    } catch (error) {
      if (requestSequence !== activeRequestSequence || isAbortError(error, listController?.signal)) {
        return
      }
      console.error('\u52a0\u8f7d\u5de5\u4f5c\u53f0\u6570\u636e\u5931\u8d25:', error)
      cachedClinicalSourceOptions = null
      loadError.value = true
      allRecords.value = []
      serverTotal.value = 0
      loadedTotals.value = undefined
      qcSummary.value = { ...EMPTY_QC_SUMMARY }
      qcSummaryState.value = 'unavailable'
    } finally {
      if (listController && listRequest === listController) listRequest = undefined
      if (requestSequence === activeRequestSequence) {
        loading.value = false
      }
    }
  }

  function selectSource(value: string) {
    if (!sourceOptions.value.some((option) => option.id === value && option.enabled)) return
    ++activeRequestSequence
    listRequest?.abort()
    summaryRequest?.abort()
    resetClinicalSourceOptionsCache()
    if (sourceMode.value !== 'legacy_compat' && value !== 'independent_cdm') {
      throw new Error('普通病历固定读取东华CDM')
    }
    sourceId.value = value as ClinicalSourceId
    setClinicalSourceMode(sourceMode.value, sourceId.value)
    setPageClinicalSource(sourceId.value)
    allRecords.value = []
    departments.value = []
    doctors.value = []
    qcSummary.value = { ...EMPTY_QC_SUMMARY }
    resetFilters()
    void fetchData(1)
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
    void fetchData(nextPage, normalizedPageSize, true)
    const scrollContainer = document.querySelector('.custom-scrollbar')
    if (scrollContainer && typeof scrollContainer.scrollTo === 'function') {
      scrollContainer.scrollTo({ top: 0, behavior: 'smooth' })
    } else if (typeof window !== 'undefined' && typeof window.scrollTo === 'function') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  function refreshData() {
    return fetchData(currentPage.value)
  }

  function selectDept(deptName: string) {
    activeDept.value = deptName
    activeDoctor.value = ALL_DOCTORS
    currentPage.value = 1
    fetchData(1)
  }

  function selectDoctor(doctorName: string) {
    activeDoctor.value = String(doctorName || ALL_DOCTORS).trim() || ALL_DOCTORS
    currentPage.value = 1
    fetchData(1)
  }

  function selectHospFilter(value: HospitalStatusScope) {
    const nextValue = hospOptions.value.some((option) => option.value === value) ? value : 'all'
    if (nextValue !== 'inpatient') {
      inpatientSort.value = 'default'
    }
    if (hospFilter.value === nextValue) return
    hospFilter.value = nextValue
    currentPage.value = 1
    fetchData(1)
  }

  function selectInpatientSort(value: InpatientSort) {
    const nextValue = ['default', 'longest', 'recent'].includes(value) ? value : 'default'
    if (inpatientSort.value === nextValue) return
    inpatientSort.value = nextValue
    currentPage.value = 1
    fetchData(1)
  }

  function resetFilters() {
    activeDept.value = ALL_DEPARTMENTS
    activeDoctor.value = ALL_DOCTORS
    searchText.value = ''
    dateRange.value = null
    dateField.value = 'visit'
    hospFilter.value = initialHospitalStatus
    syncScope.value = 'all'
    inpatientSort.value = 'default'
    currentPage.value = 1
  }

  return {
    sourceId,
    sourceOptions,
    selectSource,
    allRecords,
    departments,
    doctors,
    currentPage,
    pageSize,
    serverTotal,
    serverTotalPages,
    totalCount,
    loading,
    loadError,
    qcSummary,
    qcSummaryState,
    qcTotalsReady,
    activeDept,
    activeDoctor,
    searchText,
    dateRange,
    committedSearchText,
    committedDateRange,
    dateField,
    hospFilter,
    syncScope,
    inpatientSort,
    hospOptions,
    filteredRecords,
    fetchData,
    handlePageChange,
    refreshData,
    selectDept,
    selectDoctor,
    selectHospFilter,
    selectInpatientSort,
    resetFilters,
  }
}
