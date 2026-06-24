import { reactive, ref } from 'vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { message } from 'ant-design-vue'
import { getWorkspaceRecordFilters } from '@/services/custom-rule-workspace-service'
import type { WorkspaceScope } from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null

type RecordFiltersState = {
  scope: WorkspaceScope
  department?: string
  doctor?: string
  dateRange: DateRangeValue
  keyword: string
}

type BatchLaunchFiltersState = {
  scope: WorkspaceScope
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  dateRange: DateRangeValue
  keyword: string
}

type LoadOptions = {
  silent?: boolean
}

function buildRangeFromBounds(bounds: { min: string; max: string } | undefined): DateRangeValue {
  if (!bounds?.min || !bounds?.max) return null
  const start = dayjs(bounds.min)
  const end = dayjs(bounds.max)
  if (!start.isValid() || !end.isValid()) return null
  return [start, end]
}

export function useCustomQcBatchLaunchFilters(recordFilters: RecordFiltersState) {
  const batchLaunchModalOpen = ref(false)
  const batchLaunchFiltersLoading = ref(false)
  const batchLaunchDepartmentOptions = ref<Array<{ label: string; value: string }>>([])
  const batchLaunchDoctorOptions = ref<Array<{ label: string; value: string }>>([])

  const batchLaunchFilters = reactive<BatchLaunchFiltersState>({
    scope: recordFilters.scope || 'final',
    department: recordFilters.department,
    doctor: recordFilters.doctor,
    date_field: 'admission',
    dateRange: recordFilters.dateRange,
    keyword: recordFilters.keyword || '',
  })

  function resetBatchLaunchFiltersFromCurrent() {
    batchLaunchFilters.scope = recordFilters.scope || 'final'
    batchLaunchFilters.department = recordFilters.department
    batchLaunchFilters.doctor = recordFilters.doctor
    batchLaunchFilters.keyword = recordFilters.keyword || ''
    batchLaunchFilters.dateRange = recordFilters.dateRange
  }

  async function loadBatchLaunchFilterOptions(options: LoadOptions = {}) {
    batchLaunchFiltersLoading.value = true
    try {
      const response = await getWorkspaceRecordFilters({
        scope: batchLaunchFilters.scope,
        department: batchLaunchFilters.department,
      })
      if (!response.success || !response.data) {
        throw new Error(response.message || '获取批量筛选项失败')
      }

      const departments = response.data.departments || []
      const doctors = response.data.doctors || []
      batchLaunchDepartmentOptions.value = departments.map((item) => ({
        label: item,
        value: item,
      }))
      batchLaunchDoctorOptions.value = doctors.map((item) => ({
        label: item,
        value: item,
      }))

      if (batchLaunchFilters.department && !departments.includes(batchLaunchFilters.department)) {
        batchLaunchFilters.department = undefined
      }
      if (batchLaunchFilters.doctor && !doctors.includes(batchLaunchFilters.doctor)) {
        batchLaunchFilters.doctor = undefined
      }

      const dateFieldKey = batchLaunchFilters.date_field === 'discharge' ? 'discharge' : 'admission'
      const bounds = response.data.date_bounds?.[dateFieldKey]
      if (!batchLaunchFilters.dateRange) {
        batchLaunchFilters.dateRange = buildRangeFromBounds(bounds)
      }
    } catch (error: any) {
      if (!options.silent) {
        message.error(error?.message || '获取批量筛选项失败')
      }
      throw error
    } finally {
      batchLaunchFiltersLoading.value = false
    }
  }

  async function handleBatchLaunchScopeChange(scope: WorkspaceScope) {
    batchLaunchFilters.scope = scope
    batchLaunchFilters.department = undefined
    batchLaunchFilters.doctor = undefined
    await loadBatchLaunchFilterOptions({ silent: true })
  }

  async function handleBatchLaunchDepartmentChange(department?: string) {
    batchLaunchFilters.department = department || undefined
    batchLaunchFilters.doctor = undefined
    await loadBatchLaunchFilterOptions({ silent: true })
  }

  return {
    batchLaunchModalOpen,
    batchLaunchFiltersLoading,
    batchLaunchDepartmentOptions,
    batchLaunchDoctorOptions,
    batchLaunchFilters,
    resetBatchLaunchFiltersFromCurrent,
    loadBatchLaunchFilterOptions,
    handleBatchLaunchScopeChange,
    handleBatchLaunchDepartmentChange,
  }
}
