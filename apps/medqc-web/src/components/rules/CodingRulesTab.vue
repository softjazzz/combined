<template>
  <div class="coding-rules-workbench space-y-4">
    <a-alert
      type="info"
      show-icon
      data-testid="readonly-catalog-notice"
      message="只读规则目录"
      description="编码质控规则目录当前为只读视图，不支持在线新建、编辑、保存草稿、发布或回滚；如需自定义质控点，请前往「自定义质控点」工作台。"
    />

    <RulesCodingHeaderBar
      title="编码质控规则目录（只读）"
      subtitle="展示当前在线生效的编码质控规则目录，仅支持检索、筛选与只读详情查看。"
      :version-label="versionLabel"
      :search-keyword="query.searchKeyword"
      :loading="loading"
      :has-pending-changes="false"
      :readonly="readonly"
      @update:search-keyword="handleKeywordChange"
      @create-rule="notifyReadonly"
      @import-template="notifyReadonly"
      @run-preflight="notifyReadonly"
      @publish="notifyReadonly"
    />

    <div class="grid grid-cols-1 gap-4 xl:grid-cols-[260px_minmax(0,1fr)]">
      <RulesCodingFilterPanel
        :rule-type="query.ruleType"
        :status-set="query.statusSet"
        :risk-set="query.riskSet"
        :owner-id="query.ownerId"
        :owner-options="ownerOptions"
        :saved-views="[]"
        :readonly="readonly"
        @update:rule-type="(v) => setQuery({ ruleType: v })"
        @update:status-set="(v) => setQuery({ statusSet: v })"
        @update:risk-set="(v) => setQuery({ riskSet: v })"
        @update:owner-id="(v) => setQuery({ ownerId: v })"
        @reset-filters="handleResetFilters"
        @save-view="notifyReadonly"
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
        @duplicate-rule="notifyReadonly"
        @disable-rule="notifyReadonly"
        @delete-rule="notifyReadonly"
        @page-change="handlePageChange"
      />
    </div>

    <RulesCodingDetailPanel
      :visible="detailVisible"
      :loading="detailLoading"
      :rule="selectedRule"
      :readonly="readonly"
      :dirty="false"
      :sample-preview="samplePreview"
      @close="detailVisible = false"
      @change="notifyReadonly"
      @save-draft="notifyReadonly"
      @delete-rule="notifyReadonly"
      @preview-hit="notifyReadonly"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'

import RulesCodingHeaderBar from './coding/RulesCodingHeaderBar.vue'
import RulesCodingFilterPanel from './coding/RulesCodingFilterPanel.vue'
import RulesCodingList from './coding/RulesCodingList.vue'
import RulesCodingDetailPanel from './coding/RulesCodingDetailPanel.vue'
import type {
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

const readonly = true
const loading = ref(false)
const detailLoading = ref(false)

const versionLabel = ref(
  `coding-rules v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}`,
)
const allRules = ref<RuleListItem[]>([])
const selectedRuleId = ref<string>()
const selectedRule = ref<RuleDetail>()
const detailVisible = ref(false)

const samplePreview = ref([
  { caseId: 'V-001', matched: true, reason: '主诊断命中规则' },
  { caseId: 'V-002', matched: false, reason: '字段缺失未命中' },
])

const ownerOptions = ref<Array<{ label: string; value: string }>>([])
let abortController: AbortController | null = null

const query = reactive({
  searchKeyword: '',
  ruleType: 'all' as RuleTypeValue,
  statusSet: ['published', 'disabled'] as string[],
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

function notifyReadonly() {
  message.info('当前为只读规则目录，暂不支持在线编辑、保存或发布')
}

async function fetchRules() {
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (query.searchKeyword) params.keyword = query.searchKeyword
    if (query.ruleType !== 'all') params.category = query.ruleType
    const response = await ApiService.get<{ items?: CodingRuleApiItem[] }>(
      '/api/v1/qc/coding-rules',
      params,
      { signal: controller.signal, skipErrorToast: true },
    )
    if (controller.signal.aborted) return
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
  } catch (error: any) {
    if (controller.signal.aborted || error?.code === 'ERR_CANCELED') return
    console.error(error)
    message.error('加载编码规则失败')
  } finally {
    if (abortController === controller) {
      abortController = null
      loading.value = false
    }
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

function handleSelectRule(payload: { id: string }) {
  const target = allRules.value.find((item) => item.id === payload.id)
  if (!target) return
  selectedRuleId.value = target.id
  selectedRule.value = toDetail(target)
  detailVisible.value = true
}

function handleResetFilters() {
  query.searchKeyword = ''
  query.ruleType = 'all'
  query.statusSet = ['published', 'disabled']
  query.riskSet = ['high', 'medium', 'low']
  query.ownerId = undefined
  query.statusFilter = 'all'
  query.current = 1
}

onMounted(async () => {
  await fetchRules()
})

onBeforeUnmount(() => {
  abortController?.abort()
})
</script>

<style scoped>
.coding-rules-workbench {
  width: 100%;
}
</style>
