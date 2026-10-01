import { computed, ref } from 'vue'
import { ApiService } from '@/services/apiService'
import type {
  DeptInfo,
  DoctorInfo,
  PatientRecord,
  RecordLatestReviewState,
  RecordPoolQcSummary,
  ScoreStandardOverviewMap,
  WorkstationScoreStandardOption,
} from '../types'
import type {
  RecordDefectSource,
  RecordDefectWorkflow,
  RecordResultView,
  RecordScoreFilterStatus,
} from '@/api/filterTemplates'
import {
  normalizeRecord,
  normalizeRecordPoolQcSummary,
  normalizeScoreStandards,
} from '../normalize'
import { ANALYTICS_DRILLDOWN_QUERY_KEYS } from '../analyticsDrilldown'

const WORKSTATION_PAGE_SIZE = 15
const ALL_DEPARTMENTS = '全部科室'
const ALL_DOCTORS = '全部主管医师'
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
export type HospitalStatusScope = 'all' | 'inpatient' | 'discharged'
export type RecordPoolSyncScope = 'all' | 'today_inpatient'
export type InpatientSort = 'default' | 'longest' | 'recent'

export interface WorkstationDefectItem {
  institute_id: string
  patient_id: string
  visit_id: string
  patient_name: string
  department: string
  doctor: string
  source: 'auto' | 'manual'
  defect_id: string | null
  rule_id: string
  rule_name: string
  document: string
  description: string
  status: string
  occurred_at: string | null
  root_job_id?: string | null
  envelope_id?: string | null
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

/**
 * 病历池的住院状态必须由调用方显式固定到服务端查询。
 * 默认值保留既有全量病历池的行为，运行/终末质控页不会在当前页做本地过滤。
 */
export function usePatientRecords(initialHospitalStatus: HospitalStatusScope = 'all') {
  const initialRouteQuery = new URLSearchParams(window.location.search)
  const initialDepartment = initialRouteQuery.get('department')?.trim()
  const initialDoctor = initialRouteQuery.get('doctor')?.trim()
  const allRecords = ref<PatientRecord[]>([])
  const defects = ref<WorkstationDefectItem[]>([])
  const departments = ref<DeptInfo[]>([])
  const doctors = ref<DoctorInfo[]>([])
  const currentPage = ref(1)
  const pageSize = ref(WORKSTATION_PAGE_SIZE)
  const serverTotal = ref(0)
  const serverTotalPages = ref(1)
  const totalCount = computed(() => serverTotal.value)
  const loading = ref(false)
  const loadError = ref(false)
  const qcSummary = ref<RecordPoolQcSummary>({ ...EMPTY_QC_SUMMARY })
  /** 响应顶层 score_standards：本页涉及场景的默认评分标准概况。 */
  const scoreStandards = ref<ScoreStandardOverviewMap>({})
  const scoreStandardOptions = ref<WorkstationScoreStandardOption[]>([])
  const scoreStandardOptionsStatus = ref<'available' | 'unavailable'>('available')

  const activeDept = ref(initialDepartment || ALL_DEPARTMENTS)
  const activeDoctor = ref(initialDoctor || ALL_DOCTORS)
  const searchText = ref('')
  const dateRange = ref<WorkstationDateRange>(null)
  const dateField = ref<WorkstationDateField>('visit')
  const hospFilter = ref<HospitalStatusScope>(initialHospitalStatus)
  const syncScope = ref<RecordPoolSyncScope>('all')
  const inpatientSort = ref<InpatientSort>('default')
  /** 审核状态筛选（多选）；空数组表示不按审核状态过滤。 */
  const reviewStateFilter = ref<RecordLatestReviewState[]>([])
  const standardIdFilter = ref('')
  const scoreStatusFilter = ref<RecordScoreFilterStatus | ''>('')
  const gradeFilter = ref('')
  const scoreMinFilter = ref<number | null>(null)
  const scoreMaxFilter = ref<number | null>(null)
  const resultView = ref<RecordResultView>('records')
  const defectSourceFilter = ref<RecordDefectSource>('all')
  const defectWorkflowFilter = ref<RecordDefectWorkflow | ''>('')
  const hasDefectFilter = ref<boolean | null>(null)
  let activeRequestSequence = 0

  const hospOptions: Array<{ value: HospitalStatusScope; label: string }> = [
    { value: 'all', label: '全部病历' },
    { value: 'inpatient', label: '在院' },
    { value: 'discharged', label: '已出院' },
  ]

  // 住院状态由服务端筛选；禁止对当前页病历再次本地过滤造成假统计。
  const scopedRecords = computed(() => allRecords.value)

  const filteredRecords = computed(() => scopedRecords.value)

  async function fetchData(page = 1, targetPageSize = pageSize.value) {
    const requestSequence = ++activeRequestSequence
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
      if (activeDept.value !== ALL_DEPARTMENTS) {
        params.dept = activeDept.value
      }
      if (activeDoctor.value !== ALL_DOCTORS) {
        params.doctor = activeDoctor.value
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
      if (syncScope.value !== 'all') {
        params.sync_scope = syncScope.value
      }
      if (inpatientSort.value !== 'default') {
        params.inpatient_sort = inpatientSort.value
      }
      if (reviewStateFilter.value.length > 0) {
        // 合同：逗号分隔多值；服务端按列表同源的审核状态过滤后再分页。
        params.review_state = reviewStateFilter.value.join(',')
      }
      if (standardIdFilter.value) params.standard_id = standardIdFilter.value
      if (scoreStatusFilter.value) params.score_status = scoreStatusFilter.value
      if (gradeFilter.value.trim()) params.grade = gradeFilter.value.trim()
      if (scoreMinFilter.value !== null) params.score_min = scoreMinFilter.value
      if (scoreMaxFilter.value !== null) params.score_max = scoreMaxFilter.value
      if (resultView.value === 'defects') params.result_view = resultView.value
      if (resultView.value === 'defects' && defectWorkflowFilter.value) {
        params.defect_workflow = defectWorkflowFilter.value
      }
      if (resultView.value === 'defects' || hasDefectFilter.value !== null) {
        params.defect_source = defectSourceFilter.value
      }
      if (hasDefectFilter.value !== null) params.has_defect = String(hasDefectFilter.value)
      // 下钻上下文只有 analyticsDrilldown 一条资料链，参数名与后端查询项保持一致。
      const analyticsQuery = new URLSearchParams(window.location.search)
      for (const key of ANALYTICS_DRILLDOWN_QUERY_KEYS) {
        if (key === 'source') continue
        const value = analyticsQuery.get(key)
        if (value?.trim()) {
          params[key] = value.trim()
        }
      }

      const response = await ApiService.getRaw('/api/medical-records/workstation', params)
      const raw = response.data as Record<string, unknown>
      const data = (
        raw && typeof raw === 'object' && 'data' in raw
          ? (raw.data as Record<string, unknown>)
          : raw
      ) as Record<string, unknown>

      const normalizedRecords = Array.isArray(data.records)
        ? data.records.map((record: unknown) => normalizeRecord(record))
        : []
      // 过期请求不得覆盖较新的筛选、分页或住院状态响应。
      if (requestSequence !== activeRequestSequence) return

      allRecords.value = normalizedRecords
      defects.value = Array.isArray(data.defects)
        ? data.defects.flatMap((raw): WorkstationDefectItem[] => {
            const item = raw as Record<string, unknown>
            const source = item.source
            const instituteId = String(item.institute_id ?? '').trim()
            const patientId = String(item.patient_id ?? '').trim()
            const visitId = String(item.visit_id ?? '').trim()
            if (
              !instituteId ||
              !patientId ||
              !visitId ||
              (source !== 'auto' && source !== 'manual')
            ) {
              return []
            }
            return [
              {
                institute_id: instituteId,
                patient_id: patientId,
                visit_id: visitId,
                patient_name: String(item.patient_name ?? '').trim(),
                department: String(item.department ?? '').trim(),
                doctor: String(item.doctor ?? '').trim(),
                source,
                defect_id: item.defect_id == null ? null : String(item.defect_id),
                rule_id: String(item.rule_id ?? '').trim(),
                rule_name: String(item.rule_name ?? '').trim(),
                document: String(item.document ?? '').trim(),
                description: String(item.description ?? '').trim(),
                status: String(item.status ?? '').trim(),
                occurred_at: item.occurred_at == null ? null : String(item.occurred_at),
                root_job_id: item.root_job_id == null ? null : String(item.root_job_id),
                envelope_id: item.envelope_id == null ? null : String(item.envelope_id),
              },
            ]
          })
        : []
      departments.value =
        Array.isArray(data.departments) && data.departments.length > 0
          ? data.departments.map((dept: unknown) => normalizeDepartment(dept))
          : buildDepartments(normalizedRecords)
      doctors.value =
        Array.isArray(data.doctors) && data.doctors.length > 0
          ? data.doctors.map((doctor: unknown) => normalizeDoctor(doctor))
          : [{ name: ALL_DOCTORS, total: 0 }]

      const total = Number(data.total ?? data.total_count ?? 0)
      const totalPagesComputed = requestedPageSize > 0 ? Math.ceil(total / requestedPageSize) : 1

      serverTotal.value = total
      serverTotalPages.value = Math.max(1, totalPagesComputed || 1)
      currentPage.value = Number(data.page ?? data.current_page ?? page) || 1
      pageSize.value = requestedPageSize
      qcSummary.value = normalizeRecordPoolQcSummary(data.qc_summary)
      scoreStandards.value = normalizeScoreStandards(data.score_standards)
      scoreStandardOptions.value = Array.isArray(data.score_standard_options)
        ? data.score_standard_options.flatMap((raw): WorkstationScoreStandardOption[] => {
            const item = raw as Record<string, unknown>
            const id = String(item.id ?? '').trim()
            const name = String(item.name ?? '').trim()
            const versionSeq = Number(item.version_seq)
            const grades = Array.isArray(item.grades)
              ? item.grades.map((value) => String(value).trim()).filter(Boolean)
              : []
            return id && name && Number.isInteger(versionSeq) && versionSeq > 0
              ? [{ id, name, versionSeq, isDefault: item.is_default === true, grades }]
              : []
          })
        : []
      scoreStandardOptionsStatus.value =
        data.score_standard_options_status === 'unavailable' ? 'unavailable' : 'available'
    } catch (error) {
      if (requestSequence !== activeRequestSequence) return
      console.error('\u52a0\u8f7d\u5de5\u4f5c\u53f0\u6570\u636e\u5931\u8d25:', error)
      loadError.value = true
      allRecords.value = []
      defects.value = []
      serverTotal.value = 0
      serverTotalPages.value = 1
      qcSummary.value = { ...EMPTY_QC_SUMMARY }
      scoreStandards.value = {}
      scoreStandardOptions.value = []
      scoreStandardOptionsStatus.value = 'unavailable'
    } finally {
      if (requestSequence === activeRequestSequence) {
        loading.value = false
      }
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
    const nextValue = hospOptions.some((option) => option.value === value) ? value : 'all'
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
    reviewStateFilter.value = []
    standardIdFilter.value = ''
    scoreStatusFilter.value = ''
    gradeFilter.value = ''
    scoreMinFilter.value = null
    scoreMaxFilter.value = null
    resultView.value = 'records'
    defectSourceFilter.value = 'all'
    defectWorkflowFilter.value = ''
    hasDefectFilter.value = null
    currentPage.value = 1
  }

  return {
    allRecords,
    defects,
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
    scoreStandards,
    scoreStandardOptions,
    scoreStandardOptionsStatus,
    activeDept,
    activeDoctor,
    searchText,
    dateRange,
    dateField,
    hospFilter,
    syncScope,
    inpatientSort,
    reviewStateFilter,
    standardIdFilter,
    scoreStatusFilter,
    gradeFilter,
    scoreMinFilter,
    scoreMaxFilter,
    resultView,
    defectSourceFilter,
    defectWorkflowFilter,
    hasDefectFilter,
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
