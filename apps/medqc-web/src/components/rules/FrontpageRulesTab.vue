<template>
  <div class="space-y-4">
    <RulesCodingHeaderBar
      title="首页质控规则管理"
      subtitle="面向首页资料完整性与规范性，不涉及编码主诊断/主手术。"
      :version-label="versionLabel"
      :search-keyword="query.searchKeyword"
      :loading="loading"
      :has-pending-changes="dirty"
      :readonly="readonly"
      search-placeholder="搜索规则名/字段名/规则编号"
      @update:search-keyword="(v) => setQuery({ searchKeyword: v })"
      @create-rule="handleCreateRule"
      @import-template="() => message.info('模板导入入口预留')"
      @run-preflight="() => message.success(`预检通过：预计影响 ${estimatedImpactCount} 条病历`)"
      @publish="publishOpen = true"
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
      enabled-label="已启用"
      hit-label="覆盖字段"
      risk-label="高风险规则"
      :enabled-subtext="'首页抽取规则均为在线生效'"
      :hit-subtext="`覆盖字段 ${metrics.hit7d} 项`"
      :risk-subtext="`分类覆盖 ${metrics.conflictRules} 类`"
      @click-metric="handleMetricClick"
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
        rule-type-title="规则分类"
        :rule-type-options="frontpageRuleTypeOptions"
        :show-owner-filter="false"
        @update:rule-type="(v) => setQuery({ ruleType: v })"
        @update:status-set="(v) => setQuery({ statusSet: v })"
        @update:risk-set="(v) => setQuery({ riskSet: v })"
        @update:owner-id="(v) => setQuery({ ownerId: v })"
        @reset-filters="handleResetFilters"
        @save-view="({ name }) => savedViews.push({ id: `view-${Date.now()}`, name })"
      />

      <RulesCodingList
        :items="pagedList"
        :selected-rule-id="selectedRuleId"
        :loading="loading"
        :view-mode="query.viewMode"
        :sort-by="query.sortBy"
        :status-filter="query.statusFilter"
        :document-type-options="documentTypeOptions"
        :document-type-set="query.documentTypeSet"
        document-type-placeholder="病历文书类型"
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
        @update:document-type-set="(v) => setQuery({ documentTypeSet: v })"
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
      @rollback="({ version }) => message.success(`已回滚到 ${version || '指定版本'}`)"
    />

    <RulesCodingDetailPanel
      :visible="detailVisible"
      :loading="false"
      :rule="selectedRule"
      :readonly="readonly"
      :dirty="dirty"
      :sample-preview="samplePreview"
      @close="detailVisible = false"
      @change="handleRuleChange"
      @save-draft="handleSaveDraft"
      @delete-rule="handleDeleteRule"
      @preview-hit="() => message.info('已刷新命中预览')"
    />

    <RulesCodingPublishDrawer
      :open="publishOpen"
      :loading="publishing"
      :change-count="dirty ? 1 : 0"
      :estimated-impact-count="estimatedImpactCount"
      :risk-notes="riskNotes"
      :high-risk-unreviewed-count="metrics.highRiskRules"
      :readonly="readonly"
      @close="publishOpen = false"
      @confirm-publish="handlePublish"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import { ApiService } from '@/services/apiService'

import RulesCodingHeaderBar from './coding/RulesCodingHeaderBar.vue'
import RulesCodingMetrics from './coding/RulesCodingMetrics.vue'
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

interface FrontpageRuleApi {
  rule_id: string
  field_name: string
  rule_name: string
  description: string
  severity: string
  category: string
  applicable_documents?: string[]
  document_types?: string[]
  document_type?: string
}

interface FrontpageRuleListItem extends RuleListItem {
  documentTypes: string[]
}

const readonly = ref(false)
const loading = ref(false)
const dirty = ref(false)
const publishing = ref(false)
const versionLabel = ref(
  `frontpage-rules v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}`,
)

const allRules = ref<FrontpageRuleListItem[]>([])
const selectedRuleId = ref<string>()
const selectedRule = ref<RuleDetail>()
const detailVisible = ref(false)
const publishOpen = ref(false)
const timelineCollapsed = ref(true)
const timelineItems = ref<RuleChangeLogItem[]>([])
const savedViews = ref<Array<{ id: string; name: string }>>([])
const ownerOptions = ref<Array<{ label: string; value: string }>>([
  { label: '系统', value: '系统' },
])
const samplePreview = ref([
  { caseId: 'FP-001', matched: true, reason: '首页字段命中' },
  { caseId: 'FP-002', matched: false, reason: '字段值为空' },
])
const frontpageRuleTypeOptions = [
  { label: '全部', value: 'all' },
  { label: '完整性', value: 'required' },
  { label: '规范性', value: 'format' },
  { label: '合理性', value: 'logic' },
  { label: '一致性', value: 'consistency' },
]
const documentTypeOptions = [
  { label: '入院记录', value: 'admission_record' },
  { label: '首次病程记录', value: 'first_course_record' },
  { label: '手术记录', value: 'operation_record' },
  { label: '会诊记录', value: 'consultation_record' },
  { label: '出院记录', value: 'discharge_record' },
  { label: '通用文书', value: 'general_record' },
]
const documentTypeLabelMap: Record<string, string> = {
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  operation_record: '手术记录',
  consultation_record: '会诊记录',
  discharge_record: '出院记录',
  general_record: '通用文书',
}

const query = ref({
  searchKeyword: '',
  ruleType: 'all' as RuleTypeValue,
  statusSet: ['published', 'draft'] as string[],
  riskSet: ['high', 'medium', 'low'] as string[],
  documentTypeSet: [] as string[],
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

function normalizeDocumentTypes(input: string[]): string[] {
  const mapping: Record<string, string> = {
    入院记录: 'admission_record',
    admission: 'admission_record',
    admission_record: 'admission_record',
    首次病程记录: 'first_course_record',
    first_course_record: 'first_course_record',
    手术记录: 'operation_record',
    operation_record: 'operation_record',
    会诊记录: 'consultation_record',
    consultation_record: 'consultation_record',
    出院记录: 'discharge_record',
    discharge_record: 'discharge_record',
    通用文书: 'general_record',
    general: 'general_record',
    general_record: 'general_record',
  }
  const normalized = input.map((code) => mapping[String(code)] || String(code)).filter(Boolean)
  return normalized.length > 0 ? Array.from(new Set(normalized)) : ['general_record']
}

function inferDocumentTypes(item: FrontpageRuleApi): string[] {
  const fromPayload = [
    ...(item.applicable_documents || []),
    ...(item.document_types || []),
    ...(item.document_type ? [item.document_type] : []),
  ]
    .map((v) => String(v || '').trim())
    .filter(Boolean)
  if (fromPayload.length > 0) return normalizeDocumentTypes(fromPayload)

  const token =
    `${item.rule_name || ''} ${item.field_name || ''} ${item.description || ''}`.toLowerCase()
  const matched: string[] = []
  if (/(入院|admission|主诉|现病史|既往史|体格检查)/.test(token)) matched.push('admission_record')
  if (/(首次病程|first_course|病程)/.test(token)) matched.push('first_course_record')
  if (/(手术|术前|术后|麻醉|operation|surgery)/.test(token)) matched.push('operation_record')
  if (/(会诊|consultation|consult)/.test(token)) matched.push('consultation_record')
  if (/(出院|discharge)/.test(token)) matched.push('discharge_record')
  if (matched.length === 0) matched.push('general_record')
  return Array.from(new Set(matched))
}

function toListItem(item: FrontpageRuleApi): FrontpageRuleListItem {
  const documentTypes = inferDocumentTypes(item)
  const docLabel = documentTypes.map((code) => documentTypeLabelMap[code] || code).join('、')
  return {
    id: item.rule_id,
    name: item.rule_name,
    ruleType: mapRuleType(item.category),
    status: 'published' as RuleStatus,
    riskLevel: normalizeRisk(item.severity),
    conditionSummary: `${item.field_name}：${item.description || '-'}（${docLabel}）`,
    hitCount7d: 0,
    hitRate7d: 0,
    updatedAt: '-',
    updatedBy: '系统',
    documentTypes,
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
  if (q.documentTypeSet.length > 0) {
    items = items.filter((item) =>
      item.documentTypes.some((doc) => q.documentTypeSet.includes(doc)),
    )
  }
  if (q.statusFilter !== 'all') items = items.filter((item) => item.status === q.statusFilter)
  return items
})

const pagedList = computed(() => {
  const { current, pageSize } = query.value
  return filteredList.value.slice((current - 1) * pageSize, current * pageSize)
})

const metrics = computed(() => {
  const totalRules = allRules.value.length
  const enabledRules = allRules.value.filter((r) => r.status === 'published').length
  const draftRules = allRules.value.filter((r) => r.status === 'draft').length
  const disabledRules = allRules.value.filter((r) => r.status === 'disabled').length
  const highRiskRules = allRules.value.filter((r) => r.riskLevel === 'high').length
  const categoryCoverage = new Set(
    allRules.value
      .map((rule) => String(rule.ruleType || ''))
      .filter((category) => ['required', 'format', 'logic', 'consistency'].includes(category)),
  ).size
  const fieldCoverage = new Set(
    allRules.value
      .map((rule) => rule.conditionSummary.split('：')[0]?.trim())
      .filter((field) => Boolean(field)),
  ).size
  return {
    totalRules,
    enabledRules,
    draftRules,
    disabledRules,
    hit7d: fieldCoverage,
    hitRate7d: 0,
    highRiskRules,
    conflictRules: categoryCoverage,
    falsePositiveHighRules: 0,
  }
})

const estimatedImpactCount = computed(() => Math.min(9999, filteredList.value.length * 2))
const riskNotes = computed(() =>
  metrics.value.highRiskRules > 0 ? ['存在高风险规则，建议发布前复核。'] : [],
)

function handleMetricClick(payload: { key: 'total' | 'enabled' | 'hit7d' | 'risk' }) {
  if (payload.key === 'enabled') setQuery({ statusSet: ['published'], statusFilter: 'published' })
  else if (payload.key === 'risk') setQuery({ riskSet: ['high'] })
  else handleResetFilters()
}

function handleResetFilters() {
  query.value = {
    searchKeyword: '',
    ruleType: 'all',
    statusSet: ['published', 'draft'],
    riskSet: ['high', 'medium', 'low'],
    documentTypeSet: [],
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

function handleRuleChange(payload: Partial<RuleDetail>) {
  if (!selectedRule.value) return
  selectedRule.value = { ...selectedRule.value, ...payload }
  dirty.value = true
}

function handleSaveDraft(payload: RuleDetail) {
  const idx = allRules.value.findIndex((item) => item.id === payload.id)
  if (idx >= 0) {
    allRules.value[idx] = {
      ...allRules.value[idx],
      name: payload.name,
      status: 'draft',
      conditionSummary: payload.description || allRules.value[idx].conditionSummary,
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
  allRules.value.unshift({
    ...source,
    id: `${source.id}-COPY`,
    name: `${source.name}（副本）`,
    status: 'draft',
  })
  dirty.value = true
  message.success('规则已复制')
}

function handleDisableRule(payload: { id: string }) {
  const target = allRules.value.find((item) => item.id === payload.id)
  if (!target) return
  target.status = 'disabled'
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

function handlePageChange(payload: { current: number; pageSize: number }) {
  query.value.current = payload.current
  query.value.pageSize = payload.pageSize
}

function handleCreateRule() {
  selectedRule.value = {
    id: `NEW-${Date.now()}`,
    name: '新建首页规则',
    description: '',
    ruleType: 'required',
    status: 'draft',
    riskLevel: 'medium',
    conditionTree: { operator: 'AND', children: [] },
  }
  selectedRuleId.value = selectedRule.value.id
  detailVisible.value = true
}

async function handlePublish() {
  publishing.value = true
  try {
    await new Promise((resolve) => setTimeout(resolve, 400))
    timelineItems.value.unshift({
      id: `publish-${Date.now()}`,
      time: new Date().toLocaleString('zh-CN', { hour12: false }),
      operator: '当前用户',
      action: 'publish',
      ruleCount: filteredList.value.length,
      impactCount: estimatedImpactCount.value,
      version: `v${new Date().toISOString().slice(0, 10).replace(/-/g, '.')}.1`,
      result: 'success',
      rollbackable: true,
    })
    dirty.value = false
    publishOpen.value = false
    message.success('首页规则发布成功')
  } finally {
    publishing.value = false
  }
}

async function fetchRules() {
  loading.value = true
  try {
    const response = await ApiService.get<FrontpageRuleApi[] | { items?: FrontpageRuleApi[] }>(
      '/api/v1/qc/formal-qc/rules',
    )
    const payload = response.data
    if (response.success && Array.isArray(payload)) {
      allRules.value = payload.map(toListItem)
    } else if (response.success && payload && 'items' in payload && Array.isArray(payload.items)) {
      allRules.value = payload.items.map(toListItem)
    } else {
      allRules.value = []
      if (!response.success) {
        message.error(response.error || '加载首页质控规则失败')
      }
    }
  } catch (error) {
    console.error(error)
    message.error('加载首页质控规则失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchRules)
</script>
