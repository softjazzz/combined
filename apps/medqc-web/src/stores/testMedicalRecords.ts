/**
 * 测试病历列表管理 Store
 * 负责列表数据、筛选、分页、选择和模板管理
 */
import { defineStore } from 'pinia'
import { computed, reactive, ref } from 'vue'
import { TestMedicalRecordService } from '@/services/test-medical-records'
import type {
  BatchActionPayload,
  FilterTemplate,
  PaginationState,
  QuickFilterTag,
  RecordSearchConditions,
  TestMedicalRecordDetail,
  TestMedicalRecordSummary
} from '@/types/test-medical-records'

const defaultPagination: PaginationState = {
  current: 1,
  pageSize: 10,
  total: 0
}

const defaultConditions: RecordSearchConditions = {
  keywordType: 'name',
  recordType: [],
  departments: [],
  diseaseCategories: [],
  complexity: [],
  status: [],
  tags: []
}

const mergeConditions = (
  base: RecordSearchConditions,
  overlay: Partial<RecordSearchConditions>
): RecordSearchConditions => {
  const result: RecordSearchConditions = { ...base }

  Object.entries(overlay).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      result[key as keyof RecordSearchConditions] = [...value]
    } else if (value === undefined) {
      delete result[key as keyof RecordSearchConditions]
    } else {
      result[key as keyof RecordSearchConditions] = value
    }
  })

  return result
}

export const useTestMedicalRecordsStore = defineStore('testMedicalRecords', () => {
  const loading = ref(false)
  const records = ref<TestMedicalRecordSummary[]>([])
  const pagination = reactive<PaginationState>({ ...defaultPagination })
  const conditions = ref<RecordSearchConditions>({ ...defaultConditions })
  const appliedConditions = ref<RecordSearchConditions>({ ...defaultConditions })
  const selectedRowKeys = ref<string[]>([])
  const detailCache = ref<Map<string, TestMedicalRecordDetail>>(new Map())

  const quickFilters = ref<QuickFilterTag[]>(TestMedicalRecordService.getQuickFilters())
  const activeQuickFilters = ref<Set<string>>(new Set())

  const filterTemplates = ref<FilterTemplate[]>([])
  const templatesLoading = ref(false)

  const hasActiveFilters = computed(() => {
    const current = appliedConditions.value
    const base = defaultConditions
    return JSON.stringify(current) !== JSON.stringify(base)
  })

  const selectedCount = computed(() => selectedRowKeys.value.length)

  const currentConditions = computed(() => appliedConditions.value)

  const refreshQuickFilters = () => {
    quickFilters.value = TestMedicalRecordService.getQuickFilters()
  }

  const loadRecords = async (
    override?: Partial<RecordSearchConditions>,
    paginationOverride?: Partial<PaginationState>
  ) => {
    loading.value = true
    try {
      if (paginationOverride) {
        Object.assign(pagination, { ...pagination, ...paginationOverride })
      }

      const mergedConditions = override
        ? mergeConditions(appliedConditions.value, override)
        : appliedConditions.value

      const response = await TestMedicalRecordService.fetchList(mergedConditions, pagination)
      records.value = response.data.items
      Object.assign(pagination, response.data.pagination)
      appliedConditions.value = mergedConditions
    } finally {
      loading.value = false
    }
  }

  const updateConditions = (partial: Partial<RecordSearchConditions>) => {
    conditions.value = mergeConditions(conditions.value, partial)
  }

  const applyFilters = async () => {
    pagination.current = 1
    await loadRecords(conditions.value)
  }

  const resetFilters = async () => {
    conditions.value = { ...defaultConditions }
    appliedConditions.value = { ...defaultConditions }
    activeQuickFilters.value.clear()
    pagination.current = 1
    await loadRecords()
  }

  const toggleQuickFilter = async (tag: QuickFilterTag) => {
    if (activeQuickFilters.value.has(tag.key)) {
      activeQuickFilters.value.delete(tag.key)
    } else {
      activeQuickFilters.value.add(tag.key)
    }

    let merged = { ...defaultConditions }
    activeQuickFilters.value.forEach(key => {
      const quick = quickFilters.value.find(item => item.key === key)
      if (!quick) return
      merged = mergeConditions(merged, quick.conditions)
    })

    conditions.value = mergeConditions(merged, conditions.value)
    pagination.current = 1
    await loadRecords(conditions.value)
  }

  const changePage = async (page: number, pageSize?: number) => {
    pagination.current = page
    if (pageSize && pageSize !== pagination.pageSize) {
      pagination.pageSize = pageSize
    }
    await loadRecords()
  }

  const fetchDetail = async (id: string) => {
    if (detailCache.value.has(id)) {
      return detailCache.value.get(id)!
    }
    const response = await TestMedicalRecordService.fetchDetail(id)
    if (response.success && response.data) {
      detailCache.value.set(id, response.data)
      return response.data
    }
    throw new Error(response.message || '获取病历详情失败')
  }

  const performBatchAction = async (payload: BatchActionPayload) => {
    if (!payload.recordIds.length) {
      return {
        succeeded: [] as string[],
        failed: [] as string[]
      }
    }
    const result = await TestMedicalRecordService.performBatchAction(payload)
    await loadRecords()
    selectedRowKeys.value = []
    return result.data
  }

  const loadTemplates = async () => {
    templatesLoading.value = true
    try {
      const response = await TestMedicalRecordService.fetchFilterTemplates()
      filterTemplates.value = response.data
    } finally {
      templatesLoading.value = false
    }
  }

  const saveTemplate = async (template: Omit<FilterTemplate, 'id' | 'createdAt' | 'updatedAt'> & { id?: string }) => {
    const response = await TestMedicalRecordService.saveFilterTemplate(template)
    await loadTemplates()
    return response.data
  }

  const deleteTemplate = async (id: string) => {
    await TestMedicalRecordService.deleteFilterTemplate(id)
    await loadTemplates()
  }

  const initialize = async () => {
    refreshQuickFilters()
    await loadTemplates()
    await loadRecords()
  }

  return {
    // state
    loading,
    templatesLoading,
    records,
    pagination,
    conditions,
    appliedConditions,
    quickFilters,
    activeQuickFilters,
    filterTemplates,
    selectedRowKeys,
    // getters
    hasActiveFilters,
    selectedCount,
    currentConditions,
    // actions
    initialize,
    loadRecords,
    updateConditions,
    applyFilters,
    resetFilters,
    toggleQuickFilter,
    changePage,
    fetchDetail,
    performBatchAction,
    loadTemplates,
    saveTemplate,
    deleteTemplate
  }
})
