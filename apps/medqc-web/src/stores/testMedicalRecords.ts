/**
 * 测试病历管理 Store（V3.6 P1-E3）
 * 只保存列表查询状态与接口结果；条目状态、替换关系由后端判定，这里不重判。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  getCurrentRuleSetCatalog,
  listTestRecords,
  removeTestRecord,
  updateTestRecordRules,
} from '@/services/test-medical-records'
import type { CurrentRuleSetCatalog, TestRecordItem } from '@/types/test-medical-records'

export const useTestMedicalRecordsStore = defineStore('testMedicalRecords', () => {
  const items = ref<TestRecordItem[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const keyword = ref('')
  const includeRemoved = ref(false)
  const loading = ref(false)
  const loadError = ref('')
  const selectedIds = ref<string[]>([])
  const ruleCatalog = ref<CurrentRuleSetCatalog | null>(null)
  const ruleCatalogError = ref('')
  const ruleCatalogLoading = ref(false)

  const selectedItems = computed(() =>
    items.value.filter((item) => selectedIds.value.includes(item.id)),
  )

  async function load() {
    loading.value = true
    loadError.value = ''
    const result = await listTestRecords({
      page: page.value,
      page_size: pageSize.value,
      include_removed: includeRemoved.value,
      q: keyword.value,
    })
    loading.value = false
    if (!result.success || !result.data) {
      loadError.value = result.message || '获取测试病历失败'
      items.value = []
      total.value = 0
      return
    }
    items.value = result.data.items
    total.value = result.data.total
    const visibleIds = new Set(items.value.map((item) => item.id))
    selectedIds.value = selectedIds.value.filter((id) => visibleIds.has(id))
  }

  async function changePage(nextPage: number, nextPageSize: number) {
    page.value = nextPage
    pageSize.value = nextPageSize
    await load()
  }

  async function search() {
    page.value = 1
    await load()
  }

  async function ensureRuleCatalog(force = false) {
    if (ruleCatalog.value && !force) return
    ruleCatalogLoading.value = true
    ruleCatalogError.value = ''
    const result = await getCurrentRuleSetCatalog()
    ruleCatalogLoading.value = false
    if (!result.success || !result.data) {
      ruleCatalogError.value = result.message || '读取当前规则集版本失败'
      return
    }
    ruleCatalog.value = result.data
  }

  async function saveRules(item: TestRecordItem, ruleIds: string[]) {
    const result = await updateTestRecordRules(item, ruleIds)
    if (result.success) await load()
    return result
  }

  async function remove(item: TestRecordItem) {
    const result = await removeTestRecord(item)
    if (result.success) await load()
    return result
  }

  return {
    items,
    total,
    page,
    pageSize,
    keyword,
    includeRemoved,
    loading,
    loadError,
    selectedIds,
    selectedItems,
    ruleCatalog,
    ruleCatalogError,
    ruleCatalogLoading,
    load,
    changePage,
    search,
    ensureRuleCatalog,
    saveRules,
    remove,
  }
})
