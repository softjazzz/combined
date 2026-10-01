import { ref, watch, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { RecordLatestReviewState } from '../types'
import type {
  RecordDefectSource,
  RecordResultView,
  RecordScoreFilterStatus,
} from '@/api/filterTemplates'
import type { WorkstationDateRange } from './usePatientRecords'
import {
  hasExplicitRecordQuery,
  mergeRecordFilterQuery,
  normalizeRecordFilter,
  parseRecordFilterQuery,
  recordFilterSignature,
  type RecordFilterSnapshot,
  type ReviewScopeAllIntent,
} from './recordFilterQuery'

const ALL_DEPARTMENTS = '全部科室'
const ALL_DOCTORS = '全部主管医师'

export interface RecordFilterState {
  activeDept: Ref<string>
  activeDoctor: Ref<string>
  searchText: Ref<string>
  startDate: Ref<string>
  endDate: Ref<string>
  dateRange: Ref<WorkstationDateRange>
  reviewStateFilter: Ref<RecordLatestReviewState[]>
  standardIdFilter: Ref<string>
  scoreStatusFilter: Ref<RecordScoreFilterStatus | ''>
  gradeFilter: Ref<string>
  scoreMinFilter: Ref<number | null>
  scoreMaxFilter: Ref<number | null>
  resultView: Ref<RecordResultView>
  defectSourceFilter: Ref<RecordDefectSource>
  hasDefectFilter: Ref<boolean | null>
  currentPage: Ref<number>
}

/**
 * V5 病历列表筛选与 URL query 的双向同步（合同第 4 节：query 是当前筛选唯一来源）。
 *
 * - 手动查询、快捷筛选、应用模板、重置都经 `commitFilters`：写状态、请求第一页、再写 query；
 * - 浏览器前进/后退等外部改写 query 时，以 URL 为准重新请求；自身写入的 query 不重复请求；
 * - 请求参数仍由 usePatientRecords 按既有语义组装。
 */
export function useRecordFilterUrlSync(options: {
  state: RecordFilterState
  fetchData: (page: number) => Promise<void>
  /** 每次筛选生效前的清理（如清空勾选）。 */
  onBeforeLoad?: () => void
}) {
  const { state, fetchData, onBeforeLoad } = options
  const route = useRoute()
  const router = useRouter()
  /** 进入时 URL 已显式给出筛选/定位/下钻：以 URL 为准，不再套用默认。 */
  const urlHadExplicitFilters = hasExplicitRecordQuery(route.query)
  /** 最近一次生效（已请求）的筛选。 */
  const activeFilters = ref<RecordFilterSnapshot>({})
  /** 是否已有筛选生效；模板栏仅在未生效时决定初始筛选，切回列表视图不会覆盖当前筛选。 */
  const filtersInitialized = ref(false)

  function currentFilterSnapshot(): RecordFilterSnapshot {
    return normalizeRecordFilter({
      dept: state.activeDept.value !== ALL_DEPARTMENTS ? state.activeDept.value : undefined,
      doctor: state.activeDoctor.value !== ALL_DOCTORS ? state.activeDoctor.value : undefined,
      keyword: state.searchText.value,
      start_date: state.startDate.value,
      end_date: state.endDate.value,
      review_state: state.reviewStateFilter.value,
      standard_id: state.standardIdFilter.value,
      score_status: state.scoreStatusFilter.value || undefined,
      grade: state.gradeFilter.value,
      score_min: state.scoreMinFilter.value ?? undefined,
      score_max: state.scoreMaxFilter.value ?? undefined,
      result_view: state.resultView.value === 'defects' ? 'defects' : undefined,
      defect_source:
        state.resultView.value === 'defects' || state.hasDefectFilter.value !== null
          ? state.defectSourceFilter.value
          : undefined,
      has_defect: state.hasDefectFilter.value ?? undefined,
    })
  }

  function loadFilters(snapshot: RecordFilterSnapshot): Promise<void> {
    const normalized = normalizeRecordFilter(snapshot)
    onBeforeLoad?.()
    activeFilters.value = normalized
    filtersInitialized.value = true
    state.activeDept.value = normalized.dept ?? ALL_DEPARTMENTS
    state.activeDoctor.value = normalized.doctor ?? ALL_DOCTORS
    state.searchText.value = normalized.keyword ?? ''
    state.startDate.value = normalized.start_date ?? ''
    state.endDate.value = normalized.end_date ?? ''
    state.dateRange.value =
      state.startDate.value || state.endDate.value
        ? [state.startDate.value, state.endDate.value]
        : null
    state.reviewStateFilter.value = [...(normalized.review_state ?? [])]
    state.standardIdFilter.value = normalized.standard_id ?? ''
    state.scoreStatusFilter.value = normalized.score_status ?? ''
    state.gradeFilter.value = normalized.grade ?? ''
    state.scoreMinFilter.value = normalized.score_min ?? null
    state.scoreMaxFilter.value = normalized.score_max ?? null
    state.resultView.value = normalized.result_view ?? 'records'
    state.defectSourceFilter.value = normalized.defect_source ?? 'all'
    state.hasDefectFilter.value = normalized.has_defect ?? null
    state.currentPage.value = 1
    return fetchData(1)
  }

  /** reviewScopeAll：true 写入“显式全部”标记，false 移除，未传则沿用当前 URL（手动查询）。 */
  function commitFilters(snapshot: RecordFilterSnapshot, reviewScopeAll?: ReviewScopeAllIntent) {
    void loadFilters(snapshot)
    void router
      .replace({
        query: mergeRecordFilterQuery(route.query, activeFilters.value, reviewScopeAll),
      })
      .catch(() => undefined)
  }

  const listRoutePath = route.path
  watch(
    () => route.query,
    (query) => {
      // 离开本页的导航不触发重新请求。
      if (route.path !== listRoutePath) return
      const fromUrl = parseRecordFilterQuery(query)
      if (recordFilterSignature(fromUrl) === recordFilterSignature(activeFilters.value)) return
      void loadFilters(fromUrl)
    },
  )

  return {
    activeFilters,
    urlHadExplicitFilters,
    filtersInitialized,
    currentFilterSnapshot,
    loadFilters,
    commitFilters,
  }
}
