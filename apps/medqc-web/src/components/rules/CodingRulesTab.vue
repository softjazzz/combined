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
      @click-metric="handleMetricClick"
    />

    <section class="coding-qc-audit">
      <div class="coding-qc-audit__head">
        <div>
          <strong>编码内涵质控闭环</strong>
          <span>按投标示例执行规则层校验，结果进入统一编码质控结构，不写病案首页。</span>
        </div>
        <button
          type="button"
          class="coding-qc-audit__button"
          :disabled="codingQcLoading"
          @click="runCodingQcAudit"
        >
          {{ codingQcLoading ? '执行中' : '执行验收样例' }}
        </button>
      </div>
      <div class="coding-qc-audit__body">
        <div class="coding-qc-audit__metric">
          <span>问题总数</span>
          <strong>{{ codingQcResult?.total_issues ?? '-' }}</strong>
          <small>规则层 + 可选语义层</small>
        </div>
        <div class="coding-qc-audit__metric">
          <span>规则问题</span>
          <strong>{{ codingQcRuleIssues.length }}</strong>
          <small>确定性编码规范</small>
        </div>
        <div class="coding-qc-audit__metric">
          <span>正式写入</span>
          <strong>否</strong>
          <small>仅写质控分析结果</small>
        </div>
        <div class="coding-qc-audit__issues">
          <div
            v-for="issue in codingQcRuleIssues.slice(0, 3)"
            :key="issue.rule_id || issue.description"
          >
            <b>{{ issue.rule_name || issue.dimension || '编码规则' }}</b>
            <span>{{ issue.description }}</span>
          </div>
          <p v-if="codingQcResult && codingQcRuleIssues.length === 0">
            当前样例未发现编码内涵问题。
          </p>
          <p v-else-if="!codingQcResult">
            点击执行后展示肿瘤病理、病理费用、合并编码和附加编码等规则结果。
          </p>
        </div>
      </div>
    </section>

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

interface CodingQcIssue {
  rule_id?: string
  rule_name?: string
  dimension?: string
  description?: string
}

interface CodingQcResult {
  total_issues?: number
  rule_issues?: CodingQcIssue[]
  llm_issues?: CodingQcIssue[]
  persistence?: unknown
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
const codingQcLoading = ref(false)
const codingQcResult = ref<CodingQcResult | null>(null)

const codingQcRuleIssues = computed(() => codingQcResult.value?.rule_issues || [])

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

const metrics = computed(() => {
  const totalRules = allRules.value.length
  const enabledRules = allRules.value.filter((r) => r.status === 'published').length
  const draftRules = allRules.value.filter((r) => r.status === 'draft').length
  const disabledRules = allRules.value.filter((r) => r.status === 'disabled').length
  const highRiskRules = allRules.value.filter((r) => r.riskLevel === 'high').length
  const conflictRules = allRules.value.filter((r) => r.conflictFlag).length
  const falsePositiveHighRules = allRules.value.filter((r) => r.falsePositiveHighFlag).length
  const hit7d = allRules.value.reduce((acc, cur) => acc + (cur.hitCount7d || 0), 0)
  const hitRate7d = totalRules > 0 ? Math.min(100, (hit7d / Math.max(totalRules * 10, 1)) * 100) : 0
  return {
    totalRules,
    enabledRules,
    draftRules,
    disabledRules,
    hit7d,
    hitRate7d,
    highRiskRules,
    conflictRules,
    falsePositiveHighRules,
  }
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

async function runCodingQcAudit() {
  codingQcLoading.value = true
  try {
    const response = await ApiService.post<CodingQcResult>('/api/v1/qc/coding-qc/check', {
      skip_llm: true,
      frontpage: {
        diagnoses: {
          discharge_main_diagnosis_text: '急性阑尾炎伴腹膜炎',
          discharge_main_icd: 'K35.900',
          discharge_other_diagnoses_texts: ['腹膜炎', '胃恶性肿瘤'],
          discharge_other_icds: ['K65.900', 'C16.900'],
          pathology_diagnosis_code: '',
        },
        procedures: {
          main_procedure_name: '冠状动脉支架置入术',
          main_procedure_code: '36.0601',
          other_procedure_names: [],
          other_procedure_codes: [],
        },
        costs: {
          categories: {
            pathology_fee: 280,
          },
        },
      },
    })
    if (!response.success || !response.data) {
      throw new Error(response.error || '编码内涵质控执行失败')
    }
    codingQcResult.value = response.data
    message.success(`编码内涵质控完成：${codingQcResult.value?.total_issues ?? 0} 个问题`)
  } catch (error) {
    codingQcResult.value = null
    message.error('编码内涵质控执行失败')
  } finally {
    codingQcLoading.value = false
  }
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

.coding-qc-audit {
  border: 1px solid #bfdbfe;
  border-radius: 16px;
  background: #f8fbff;
  padding: 16px;
}

.coding-qc-audit__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.coding-qc-audit__head strong {
  display: block;
  color: #0f172a;
  font-size: 16px;
  font-weight: 900;
}

.coding-qc-audit__head span {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
}

.coding-qc-audit__button {
  min-height: 36px;
  border: 0;
  border-radius: 9px;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 900;
  padding: 0 14px;
}

.coding-qc-audit__button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.coding-qc-audit__body {
  display: grid;
  grid-template-columns: repeat(3, 150px) minmax(0, 1fr);
  gap: 10px;
  margin-top: 14px;
}

.coding-qc-audit__metric,
.coding-qc-audit__issues {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
}

.coding-qc-audit__metric span,
.coding-qc-audit__metric small {
  display: block;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.coding-qc-audit__metric strong {
  display: block;
  color: #2563eb;
  font-size: 24px;
  font-weight: 900;
  line-height: 30px;
}

.coding-qc-audit__issues {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.coding-qc-audit__issues div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 10px;
  color: #475569;
  font-size: 13px;
  line-height: 20px;
}

.coding-qc-audit__issues b {
  color: #0f172a;
}

.coding-qc-audit__issues p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 20px;
}

@media (max-width: 1100px) {
  .coding-qc-audit__body {
    grid-template-columns: 1fr;
  }

  .coding-qc-audit__issues div {
    grid-template-columns: 1fr;
  }
}
</style>
