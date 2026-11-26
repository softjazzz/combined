<template>
  <div class="space-y-4">
    <a-alert
      type="info"
      show-icon
      data-testid="readonly-catalog-notice"
      message="只读规则目录"
      description="结算清单质控规则目录当前为只读视图，不支持在线新建、编辑、保存草稿、发布或回滚；规则内容随系统版本统一维护。"
    />

    <RulesCodingHeaderBar
      title="结算清单质控规则目录（只读）"
      subtitle="聚焦结算字段质量与分组影响的只读规则目录，不复用编码规则语义。"
      :version-label="versionLabel"
      :search-keyword="query.searchKeyword"
      :loading="loading"
      :has-pending-changes="false"
      :readonly="readonly"
      search-placeholder="搜索规则名/字段名/规则编号"
      @update:search-keyword="(v) => setQuery({ searchKeyword: v })"
      @create-rule="notifyReadonly"
      @import-template="notifyReadonly"
      @run-preflight="notifyReadonly"
      @publish="notifyReadonly"
    />

    <RulesCodingMetrics
      :total-rules="metrics.totalRules"
      :enabled-rules="metrics.enabledRules"
      :draft-rules="metrics.draftRules"
      :disabled-rules="metrics.disabledRules"
      :hit7d="metrics.hit7d"
      :hit-rate7d="metrics.hitRate7d"
      :high-risk-rules="metrics.highRiskRules"
      :conflict-rules="metrics.conflictRules"
      :false-positive-high-rules="metrics.falsePositiveHighRules"
      total-label="总规则数"
      enabled-label="影响分组"
      hit-label="分类覆盖"
      risk-label="高风险规则"
      :enabled-subtext="'涉及 DRG 分组结果变更的规则'"
      :hit-subtext="`覆盖分类 ${metrics.hit7d} 类`"
      :risk-subtext="`影响分组 ${metrics.conflictRules} 条`"
      @click-metric="handleMetricClick"
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
        rule-type-title="规则分类"
        :rule-type-options="settlementRuleTypeOptions"
        :show-owner-filter="false"
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
      :loading="false"
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'

import RulesCodingHeaderBar from './coding/RulesCodingHeaderBar.vue'
import RulesCodingMetrics from './coding/RulesCodingMetrics.vue'
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

interface SettlementRuleApi {
  rule_id: string
  field_name: string
  rule_name: string
  description: string
  severity: string
  category: string
  affects_grouping: boolean
}

const readonly = true
const loading = ref(false)
const versionLabel = ref(
  `settlement-rules v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}`,
)

const allRules = ref<RuleListItem[]>([])
const selectedRuleId = ref<string>()
const selectedRule = ref<RuleDetail>()
const detailVisible = ref(false)
const ownerOptions = ref<Array<{ label: string; value: string }>>([
  { label: '系统', value: '系统' },
])
const samplePreview = ref([
  { caseId: 'SET-001', matched: true, reason: '分组规则命中' },
  { caseId: 'SET-002', matched: false, reason: '结算字段校验通过' },
])
const settlementRuleTypeOptions = [
  { label: '全部', value: 'all' },
  { label: '完整性', value: 'required' },
  { label: '规范性', value: 'format' },
  { label: '合理性', value: 'logic' },
  { label: '一致性', value: 'consistency' },
]
let abortController: AbortController | null = null

const query = ref({
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

function setQuery(patch: Partial<typeof query.value>) {
  query.value = { ...query.value, ...patch, current: 1 }
}

function normalizeRisk(severity: string): RuleRiskLevel {
  if (severity === 'error') return 'high'
  if (severity === 'warning') return 'medium'
  return 'low'
}

function mapRuleType(category: string): RuleTypeValue {
  if (['required', 'format', 'logic', 'consistency'].includes(category)) return category
  return 'other'
}

function toListItem(item: SettlementRuleApi): RuleListItem {
  return {
    id: item.rule_id,
    name: item.rule_name,
    ruleType: mapRuleType(item.category),
    status: 'published' as RuleStatus,
    riskLevel: normalizeRisk(item.severity),
    conditionSummary: `${item.field_name}：${item.description || '-'}${item.affects_grouping ? '（影响分组）' : ''}`,
    hitCount7d: 0,
    hitRate7d: 0,
    updatedAt: '-',
    updatedBy: '系统',
    conflictFlag: Boolean(item.affects_grouping),
  }
}

const filteredList = computed(() => {
  let items = [...allRules.value]
  const q = query.value
  if (q.searchKeyword.trim()) {
    const keyword = q.searchKeyword.trim().toLowerCase()
    items = items.filter(
      (item) =>
        item.id.toLowerCase().includes(keyword) ||
        item.name.toLowerCase().includes(keyword) ||
        item.conditionSummary.toLowerCase().includes(keyword),
    )
  }
  if (q.ruleType !== 'all') items = items.filter((item) => item.ruleType === q.ruleType)
  if (q.statusSet.length > 0) items = items.filter((item) => q.statusSet.includes(item.status))
  if (q.riskSet.length > 0) items = items.filter((item) => q.riskSet.includes(item.riskLevel))
  if (q.statusFilter !== 'all') items = items.filter((item) => item.status === q.statusFilter)
  return items
})

const pagedList = computed(() => {
  const { current, pageSize } = query.value
  return filteredList.value.slice((current - 1) * pageSize, current * pageSize)
})

const metrics = computed(() => {
  const totalRules = allRules.value.length
  const groupingRules = allRules.value.filter((r) => r.conflictFlag).length
  const enabledRules = groupingRules
  const draftRules = allRules.value.filter((r) => r.status === 'draft').length
  const disabledRules = allRules.value.filter((r) => r.status === 'disabled').length
  const highRiskRules = allRules.value.filter((r) => r.riskLevel === 'high').length
  const categoryCoverage = new Set(
    allRules.value
      .map((rule) => String(rule.ruleType || ''))
      .filter((category) => ['required', 'format', 'logic', 'consistency'].includes(category)),
  ).size
  return {
    totalRules,
    enabledRules,
    draftRules,
    disabledRules,
    hit7d: categoryCoverage,
    hitRate7d: 0,
    highRiskRules,
    conflictRules: groupingRules,
    falsePositiveHighRules: 0,
  }
})

function notifyReadonly() {
  message.info('当前为只读规则目录，暂不支持在线编辑、保存或发布')
}

function handleMetricClick(payload: { key: 'total' | 'enabled' | 'hit7d' | 'risk' }) {
  if (payload.key === 'enabled') setQuery({ statusSet: ['published'], statusFilter: 'published' })
  else if (payload.key === 'risk') setQuery({ riskSet: ['high'] })
  else handleResetFilters()
}

function handleResetFilters() {
  query.value = {
    searchKeyword: '',
    ruleType: 'all',
    statusSet: ['published', 'disabled'],
    riskSet: ['high', 'medium', 'low'],
    ownerId: undefined,
    viewMode: 'list',
    sortBy: 'updated_at',
    statusFilter: 'all',
    current: 1,
    pageSize: 20,
  }
}

function handleSelectRule(payload: { id: string }) {
  const target = allRules.value.find((item) => item.id === payload.id)
  if (!target) return
  selectedRuleId.value = payload.id
  selectedRule.value = {
    id: target.id,
    name: target.name,
    description: target.conditionSummary,
    ruleType: target.ruleType,
    status: target.status,
    riskLevel: target.riskLevel,
    conditionTree: { operator: 'AND', children: [] },
  }
  detailVisible.value = true
}

function handlePageChange(payload: { current: number; pageSize: number }) {
  query.value.current = payload.current
  query.value.pageSize = payload.pageSize
}

async function fetchRules() {
  abortController?.abort()
  const controller = new AbortController()
  abortController = controller
  loading.value = true
  try {
    const response = await ApiService.get<SettlementRuleApi[] | { items?: SettlementRuleApi[] }>(
      '/api/medical-records/settlement/rules/list',
      undefined,
      { signal: controller.signal, skipErrorToast: true },
    )
    if (controller.signal.aborted) return
    const payload = response.data
    if (response.success && Array.isArray(payload)) {
      allRules.value = payload.map(toListItem)
    } else if (response.success && payload && 'items' in payload && Array.isArray(payload.items)) {
      allRules.value = payload.items.map(toListItem)
    } else {
      allRules.value = []
      if (!response.success) {
        message.error(response.error || '加载结算清单规则失败')
      }
    }
  } catch (error: any) {
    if (controller.signal.aborted || error?.code === 'ERR_CANCELED') return
    console.error(error)
    message.error('加载结算清单规则失败')
  } finally {
    if (abortController === controller) {
      abortController = null
      loading.value = false
    }
  }
}

onMounted(fetchRules)
onBeforeUnmount(() => {
  abortController?.abort()
})
</script>
