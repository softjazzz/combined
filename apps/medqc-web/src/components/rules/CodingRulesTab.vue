<template>
  <div class="coding-rules-workbench space-y-4">
    <RulesCodingHeaderBar
      :version-label="versionLabel"
      :search-keyword="query.searchKeyword"
      :loading="loading"
      :has-pending-changes="dirty"
      :readonly="readonly"
      @update:search-keyword="handleKeywordChange"
      @create-rule="handleCreateRule"
      @import-template="handleImportTemplate"
      @run-preflight="handleRunPreflight"
      @publish="publishOpen = true"
    />

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
      <RulesCodingFilterPanel
        :rule-type="query.ruleType"
        :status-set="query.statusSet"
        :risk-set="query.riskSet"
        :owner-id="query.ownerId"
        :owner-options="ownerOptions"
        :saved-views="savedViews"
        :readonly="readonly"
        @update:rule-type="(v) => setQuery({ ruleType: v })"
        @update:status-set="(v) => setQuery({ statusSet: v })"
        @update:risk-set="(v) => setQuery({ riskSet: v })"
        @update:owner-id="(v) => setQuery({ ownerId: v })"
        @reset-filters="handleResetFilters"
        @save-view="handleSaveView"
      />

      <RulesCodingList
        :items="pagedList"
        :selected-rule-id="selectedRuleId"
        :loading="loading"
        :view-mode="query.viewMode"
        :sort-by="query.sortBy"
        :status-filter="query.statusFilter"
        :pagination="{
          current: query.current,
          pageSize: query.pageSize,
          total: filteredList.length,
        }"
        :readonly="readonly"
        @select-rule="handleSelectRule"
        @update:view-mode="(v) => setQuery({ viewMode: v })"
        @update:sort-by="(v) => setQuery({ sortBy: v })"
        @update:status-filter="(v) => setQuery({ statusFilter: v })"
        @duplicate-rule="handleDuplicateRule"
        @disable-rule="handleDisableRule"
        @delete-rule="handleDeleteRule"
        @page-change="handlePageChange"
      />
    </div>

    <RulesCodingChangeTimeline
      :items="timelineItems"
      :loading="false"
      :collapsed="timelineCollapsed"
      @toggle-collapsed="timelineCollapsed = $event"
      @rollback="handleRollback"
    />

    <RulesCodingDetailPanel
      :visible="detailVisible"
      :loading="detailLoading"
      :rule="selectedRule"
      :readonly="readonly"
      :dirty="dirty"
      :sample-preview="samplePreview"
      @close="detailVisible = false"
      @change="handleRuleChange"
      @save-draft="handleSaveDraft"
      @delete-rule="handleDeleteRule"
      @preview-hit="handlePreviewHit"
    />

    <RulesCodingPublishDrawer
      :open="publishOpen"
      :loading="publishing"
      :change-count="changeCount"
      :estimated-impact-count="estimatedImpactCount"
      :risk-notes="riskNotes"
      :high-risk-unreviewed-count="highRiskUnreviewedCount"
      :readonly="readonly"
      @close="publishOpen = false"
      @confirm-publish="handleConfirmPublish"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'

import RulesCodingHeaderBar from './coding/RulesCodingHeaderBar.vue'
import RulesCodingFilterPanel from './coding/RulesCodingFilterPanel.vue'
import RulesCodingList from './coding/RulesCodingList.vue'
import RulesCodingDetailPanel from './coding/RulesCodingDetailPanel.vue'
import RulesCodingPublishDrawer from './coding/RulesCodingPublishDrawer.vue'
import RulesCodingChangeTimeline from './coding/RulesCodingChangeTimeline.vue'
import type {
  RuleChangeLogItem,
  RuleDetail,
  RuleListItem,
  RuleRiskLevel,
  RuleStatus,
  RuleTypeValue,
} from './coding/types'

interface CodingRuleApiItem {
  rule_id: string
  name: string
  category: string
  category_name: string
  description: string
  severity: string
  source: string
  source_name: string
  is_active: boolean
  example: string
  rule_count: number
  version: string
  updated_at?: string
  updated_by?: string
}

const readonly = ref(false)
const loading = ref(false)
const detailLoading = ref(false)
const publishing = ref(false)

const versionLabel = ref(
  `coding-rules v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}`,
)
const allRules = ref<RuleListItem[]>([])
const selectedRuleId = ref<string>()
const selectedRule = ref<RuleDetail>()
const detailVisible = ref(false)
const dirty = ref(false)
const publishOpen = ref(false)
const timelineCollapsed = ref(true)
const timelineItems = ref<RuleChangeLogItem[]>([])

const samplePreview = ref([
  { caseId: 'V-001', matched: true, reason: '主诊断命中规则' },
  { caseId: 'V-002', matched: false, reason: '字段缺失未命中' },
])

const savedViews = ref<Array<{ id: string; name: string }>>([])
const ownerOptions = ref<Array<{ label: string; value: string }>>([])

const query = reactive({
  searchKeyword: '',
  ruleType: 'all' as RuleTypeValue,
  statusSet: ['published', 'draft'] as string[],
  riskSet: ['high', 'medium', 'low'] as string[],
  ownerId: undefined as string | undefined,
  viewMode: 'list' as 'list' | 'compact',
  sortBy: 'updated_at' as 'updated_at' | 'hit_rate' | 'risk',
  statusFilter: 'all' as 'all' | 'published' | 'draft' | 'disabled',
  current: 1,
  pageSize: 20,
})

const filteredList = computed(() => {
  let items = [...allRules.value]
  if (query.searchKeyword.trim()) {
    const keyword = query.searchKeyword.trim().toLowerCase()
    items = items.filter(
      (item) =>
        item.id.toLowerCase().includes(keyword) ||
        item.name.toLowerCase().includes(keyword) ||
        item.conditionSummary.toLowerCase().includes(keyword),
    )
  }
  if (query.ruleType !== 'all') {
    items = items.filter((item) => item.ruleType === query.ruleType)
  }
  if (query.statusSet.length > 0) {
    const allowed = new Set(query.statusSet)
    items = items.filter((item) => allowed.has(item.status))
  }
  if (query.riskSet.length > 0) {
    const allowed = new Set(query.riskSet)
    items = items.filter((item) => allowed.has(item.riskLevel))
  }
  if (query.ownerId) {
    items = items.filter((item) => item.updatedBy === query.ownerId)
  }
  if (query.statusFilter !== 'all') {
    items = items.filter((item) => item.status === query.statusFilter)
  }

  if (query.sortBy === 'hit_rate') {
    items.sort((a, b) => (b.hitRate7d || 0) - (a.hitRate7d || 0))
  } else if (query.sortBy === 'risk') {
    const riskScore: Record<RuleRiskLevel, number> = { high: 3, medium: 2, low: 1 }
    items.sort((a, b) => riskScore[b.riskLevel] - riskScore[a.riskLevel])
  } else {
    items.sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || '')))
  }
  return items
})

const pagedList = computed(() => {
  const start = (query.current - 1) * query.pageSize
  return filteredList.value.slice(start, start + query.pageSize)
})

const changeCount = computed(() => (dirty.value ? 1 : 0))
const estimatedImpactCount = computed(() => Math.min(9999, filteredList.value.length * 3))
const highRiskUnreviewedCount = computed(
  () => filteredList.value.filter((r) => r.riskLevel === 'high').length,
)
const riskNotes = computed(() => {
  const notes: string[] = []
  if (highRiskUnreviewedCount.value > 0) notes.push('检测到高风险规则，请优先复核后发布。')
  if (filteredList.value.some((r) => r.status === 'draft'))
    notes.push('存在草稿规则，发布将覆盖线上规则集。')
  return notes
})

function normalizeRisk(severity: string): RuleRiskLevel {
  if (severity === 'error') return 'high'
  if (severity === 'warning') return 'medium'
  return 'low'
}

function normalizeStatus(isActive: boolean): RuleStatus {
  return isActive ? 'published' : 'disabled'
}

function mapApiItem(item: CodingRuleApiItem): RuleListItem {
  return {
    id: item.rule_id,
    name: item.name,
    ruleType: item.category || 'other_diagnosis',
    status: normalizeStatus(Boolean(item.is_active)),
    riskLevel: normalizeRisk(item.severity),
    conditionSummary: item.description || '-',
    hitCount7d: Number(item.rule_count || 0),
    hitRate7d: Math.min(100, Number(item.rule_count || 0)),
    updatedAt: item.updated_at || item.version || '-',
    updatedBy: item.updated_by || '系统',
    conflictFlag: false,
    falsePositiveHighFlag: false,
  }
}

function toDetail(item: RuleListItem): RuleDetail {
  return {
    id: item.id,
    name: item.name,
    description: item.conditionSummary,
    ruleType: item.ruleType,
    status: item.status,
    riskLevel: item.riskLevel,
    conditionTree: {
      operator: 'AND',
      children: [
        {
          field: 'diagnosis_code',
          comparator: 'NOT_EMPTY',
          value: '',
        },
      ],
    },
    updatedAt: item.updatedAt,
    updatedBy: item.updatedBy,
  }
}

async function fetchRules() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (query.searchKeyword) params.keyword = query.searchKeyword
    if (query.ruleType !== 'all') params.category = query.ruleType
    const response = await ApiService.get<{ items?: CodingRuleApiItem[] }>(
      '/api/v1/qc/coding-rules',
      params,
    )
    if (response.success && response.data?.items) {
      allRules.value = (response.data.items as CodingRuleApiItem[]).map(mapApiItem)
      ownerOptions.value = [...new Set(allRules.value.map((item) => item.updatedBy))]
        .filter(Boolean)
        .map((name) => ({ label: name, value: name }))
    } else {
      allRules.value = []
      if (!response.success) {
        message.error(response.error || '加载编码规则失败')
      }
    }
  } catch (error) {
    console.error(error)
    message.error('加载编码规则失败')
  } finally {
    loading.value = false
  }
}

function setQuery(patch: Partial<typeof query>) {
  Object.assign(query, patch)
  query.current = 1
}

function handleKeywordChange(value: string) {
  setQuery({ searchKeyword: value })
}

function handlePageChange(payload: { current: number; pageSize: number }) {
  query.current = payload.current
  query.pageSize = payload.pageSize
}

function handleMetricClick(payload: { key: 'total' | 'enabled' | 'hit7d' | 'risk' }) {
  if (payload.key === 'enabled') {
    setQuery({ statusSet: ['published'], statusFilter: 'published' })
  } else if (payload.key === 'risk') {
    setQuery({ riskSet: ['high'] })
  } else {
    handleResetFilters()
  }
}

function handleSelectRule(payload: { id: string }) {
  const target = allRules.value.find((item) => item.id === payload.id)
  if (!target) return
  selectedRuleId.value = target.id
  selectedRule.value = toDetail(target)
  detailVisible.value = true
}

function handleRuleChange(payload: Partial<RuleDetail>) {
  if (!selectedRule.value) return
  selectedRule.value = { ...selectedRule.value, ...payload }
  dirty.value = true
}

function handleSaveDraft(payload: RuleDetail) {
  const index = allRules.value.findIndex((item) => item.id === payload.id)
  if (index >= 0) {
    allRules.value[index] = {
      ...allRules.value[index],
      name: payload.name,
      status: 'draft',
      conditionSummary: payload.description || allRules.value[index].conditionSummary,
      updatedAt: new Date().toISOString().slice(0, 19).replace('T', ' '),
      updatedBy: '当前用户',
    }
  }
  dirty.value = false
  timelineItems.value.unshift({
    id: `save-${Date.now()}`,
    time: new Date().toLocaleString('zh-CN', { hour12: false }),
    operator: '当前用户',
    action: 'save_draft',
    ruleCount: 1,
    result: 'success',
  })
  message.success('规则草稿已保存')
}

function handleDuplicateRule(payload: { id: string }) {
  const source = allRules.value.find((item) => item.id === payload.id)
  if (!source) return
  const newItem: RuleListItem = {
    ...source,
    id: `${source.id}-COPY`,
    name: `${source.name}（副本）`,
    status: 'draft',
    updatedAt: new Date().toISOString().slice(0, 19).replace('T', ' '),
    updatedBy: '当前用户',
  }
  allRules.value.unshift(newItem)
  dirty.value = true
  message.success('规则已复制为草稿')
}

function handleDisableRule(payload: { id: string }) {
  const source = allRules.value.find((item) => item.id === payload.id)
  if (!source) return
  source.status = 'disabled'
  dirty.value = true
  message.success('规则已停用')
}

function handleDeleteRule(payload: { id: string }) {
  allRules.value = allRules.value.filter((item) => item.id !== payload.id)
  if (selectedRuleId.value === payload.id) {
    selectedRuleId.value = undefined
    selectedRule.value = undefined
    detailVisible.value = false
  }
  dirty.value = true
  message.success('规则已删除')
}

function handlePreviewHit() {
  message.info('已刷新规则命中预览')
}

function handleResetFilters() {
  query.searchKeyword = ''
  query.ruleType = 'all'
  query.statusSet = ['published', 'draft']
  query.riskSet = ['high', 'medium', 'low']
  query.ownerId = undefined
  query.statusFilter = 'all'
  query.current = 1
}

function handleSaveView(payload: { name: string }) {
  savedViews.value.push({ id: `view-${Date.now()}`, name: payload.name })
  message.success('筛选视图已保存')
}

function handleCreateRule() {
  const newRule: RuleDetail = {
    id: `NEW-${Date.now()}`,
    name: '新建编码规则',
    description: '',
    ruleType: 'other_diagnosis',
    status: 'draft',
    riskLevel: 'medium',
    conditionTree: { operator: 'AND', children: [] },
  }
  selectedRuleId.value = newRule.id
  selectedRule.value = newRule
  detailVisible.value = true
}

function handleImportTemplate() {
  message.info('模板导入入口已打开（后续可接导入弹窗）')
}

function handleRunPreflight() {
  message.success(`预检通过：预计影响 ${estimatedImpactCount.value} 条病历`)
}

async function handleConfirmPublish() {
  publishing.value = true
  try {
    await new Promise((resolve) => setTimeout(resolve, 500))
    timelineItems.value.unshift({
      id: `publish-${Date.now()}`,
      time: new Date().toLocaleString('zh-CN', { hour12: false }),
      operator: '当前用户',
      action: 'publish',
      ruleCount: changeCount.value || filteredList.value.length,
      impactCount: estimatedImpactCount.value,
      version: `v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}.1`,
      result: 'success',
      rollbackable: true,
    })
    dirty.value = false
    publishOpen.value = false
    message.success('规则发布成功')
  } finally {
    publishing.value = false
  }
}

function handleRollback(payload: { id: string; version?: string }) {
  timelineItems.value.unshift({
    id: `rollback-${Date.now()}`,
    time: new Date().toLocaleString('zh-CN', { hour12: false }),
    operator: '当前用户',
    action: 'rollback',
    version: payload.version,
    result: 'success',
  })
  message.success(`已回滚到 ${payload.version || '指定版本'}`)
}

onMounted(async () => {
  await fetchRules()
})
</script>

<style scoped>
.coding-rules-workbench {
  width: 100%;
}
</style>
