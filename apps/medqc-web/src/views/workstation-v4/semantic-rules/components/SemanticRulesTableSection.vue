<template>
  <section class="table-shell">
    <!-- 当前规则集主卡（v7.1 蓝色主卡）：切换规则集、开始评估、进入自定义工作台 -->
    <div class="table-shell-head rule-set-hero">
      <span class="rule-set-hero__mark" aria-hidden="true">
        <MqIcon name="rules" color="#FFFFFF" :size="28" />
      </span>
      <div class="rule-set-hero__copy">
        <span class="rule-set-hero__eyebrow">当前规则集</span>
        <div class="rule-set-hero__title-row">
          <h3 class="table-shell-title">
            {{ selectedRuleSetLabel }}
          </h3>
          <label class="rule-set-picker">
            <span class="rule-set-label">切换规则集</span>
            <a-select
              :value="selectedRuleSetValue"
              class="rule-set-select"
              aria-label="切换规则集"
              popup-class-name="semantic-rule-select-dropdown"
              @change="handleRuleSetSelectChange"
            >
              <a-select-option
                v-for="item in normalizedRuleSetOptions"
                :key="item.value"
                :value="item.value"
              >
                {{ item.label }}
              </a-select-option>
            </a-select>
          </label>
        </div>
        <div class="table-shell-meta">
          <span class="table-shell-count">{{ total }}</span>
          <span class="table-shell-label">条目录规则 · 当前结果可查看</span>
        </div>
      </div>
      <div v-if="!confirmedResultsOnly" class="table-shell-actions">
        <a-button class="table-secondary-btn" @click="emit('openCustomWorkspace')">
          <SlidersHorizontal class="button-icon" />
          自定义规则工作台
        </a-button>
        <a-button class="table-primary-btn" @click="emit('openQcEvaluation')">
          <Play class="button-icon" />
          开始质控评估
        </a-button>
      </div>
    </div>

    <p v-if="ruleSetKey === 'luxian_0609_qc_v1'" class="execution-summary">
      当前筛选范围：{{ executionSummary }}。目录数量不等于实际执行数量。
    </p>

    <ProQueryBar>
      <template #filters>
        <a-input
          :value="keywordInput"
          placeholder="搜索规则编号、名称或文书类型"
          class="query-input"
          allow-clear
          @update:value="emit('update:keywordInput', String($event || ''))"
        >
          <template #prefix>
            <Search class="query-icon" />
          </template>
        </a-input>

        <a-select
          :value="defectLevel || undefined"
          class="query-select"
          placeholder="缺陷级别"
          allow-clear
          popup-class-name="semantic-rule-select-dropdown"
          @update:value="emit('update:defectLevel', String($event || ''))"
        >
          <a-select-option v-for="item in defectOptions" :key="item" :value="item">
            {{ item }}
          </a-select-option>
        </a-select>

        <a-select
          :value="complexity || undefined"
          class="query-select"
          placeholder="复杂度"
          allow-clear
          popup-class-name="semantic-rule-select-dropdown"
          @update:value="emit('update:complexity', String($event || ''))"
        >
          <a-select-option v-for="item in complexityOptions" :key="item" :value="item">
            {{ item }}
          </a-select-option>
        </a-select>

        <a-select
          :value="documentType || undefined"
          class="query-select"
          placeholder="适用文书"
          allow-clear
          popup-class-name="semantic-rule-select-dropdown"
          @update:value="emit('update:documentType', String($event || ''))"
        >
          <a-select-option v-for="item in documentOptions" :key="item" :value="item">
            {{ getDocTypeZh(item) }}
          </a-select-option>
        </a-select>

        <a-select
          v-if="hasReleaseScope"
          :value="releaseScope || undefined"
          class="query-select"
          placeholder="发布范围"
          allow-clear
          aria-label="发布范围"
          popup-class-name="semantic-rule-select-dropdown"
          @update:value="emit('update:releaseScope', String($event || ''))"
        >
          <a-select-option value="acceptance_only"> 待验收 </a-select-option>
          <a-select-option value="default"> 已上线 </a-select-option>
        </a-select>
      </template>
    </ProQueryBar>

    <div class="table-shell-body">
      <ProStandardTable
        :columns="columns"
        :data-source="rules"
        :loading="loading"
        :pagination="pagination"
        row-key="rule_id"
        :custom-row="buildCustomRow"
        :locale="{ emptyText: '暂无匹配规则' }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            <span class="index-cell">{{ getRowNumber(index) }}</span>
          </template>

          <template v-if="column.key === 'rule_id'">
            <span class="rule-code-pill">
              {{ record.rule_code || record.rule_id }}
            </span>
          </template>

          <template v-if="column.key === 'release_scope'">
            <span
              :class="
                record.release_scope === 'acceptance_only'
                  ? 'mq-status mq-status--warning'
                  : 'mq-status mq-status--success'
              "
              data-testid="release-scope"
            >
              {{ record.release_scope === 'acceptance_only' ? '待验收' : '已上线' }}
            </span>
          </template>

          <template v-if="column.key === 'applicable_documents'">
            <span class="doc-type-pill">
              {{ getDocTypeZh((record.applicable_documents || [])[0] || '未知文书') }}
            </span>
          </template>

          <template v-if="column.key === 'execution_status'">
            <span :title="executionStatusHint(record as SemanticRuleItem)">{{
              executionStatus(record as SemanticRuleItem)
            }}</span>
          </template>

          <template v-if="column.key === 'name'">
            <div class="rule-main">
              <div class="rule-main-content">
                <button
                  type="button"
                  class="rule-main-title"
                  @click="emit('viewDetail', record as SemanticRuleItem)"
                >
                  {{ record.name }}
                </button>
                <div class="rule-main-meta">
                  <span
                    v-if="record.release_scope"
                    :class="
                      record.release_scope === 'acceptance_only'
                        ? 'mq-status mq-status--warning'
                        : 'mq-status mq-status--success'
                    "
                  >
                    {{ record.release_scope === 'acceptance_only' ? '待验收' : '已上线' }}
                  </span>
                  <span class="doc-type-pill">
                    {{ getDocTypeZh((record.applicable_documents || [])[0] || '未知文书') }}
                  </span>
                  <span
                    v-if="ruleSetKey === 'luxian_0609_qc_v1'"
                    class="rule-execution-meta"
                    :title="executionStatusHint(record as SemanticRuleItem)"
                  >
                    {{ executionStatus(record as SemanticRuleItem) }}
                  </span>
                </div>
              </div>
              <div class="rule-inline-actions">
                <a-button
                  type="primary"
                  size="small"
                  class="action-primary"
                  @click="emit('viewDetail', record as SemanticRuleItem)"
                >
                  <FileSearch class="button-icon" />
                  {{ rowAction.primaryLabel }}
                </a-button>
                <a-button
                  v-if="!confirmedResultsOnly"
                  size="small"
                  class="action-secondary"
                  data-testid="start-rule-test"
                  :disabled="isLuxianRule(record as SemanticRuleItem)"
                  :title="
                    isLuxianRule(record as SemanticRuleItem)
                      ? 'LX0609 规则不支持纯文本测试，请前往规则验收使用结构化病例验证'
                      : undefined
                  "
                  @click="handleStartTest(record as SemanticRuleItem)"
                >
                  <ClipboardCheck class="button-icon" />
                  {{ rowAction.secondaryLabel }}
                </a-button>
                <router-link
                  v-if="!confirmedResultsOnly && record.release_scope === 'acceptance_only'"
                  class="ant-btn ant-btn-sm action-secondary"
                  data-testid="go-rule-validation"
                  :to="{
                    name: 'WorkstationV4RuleValidationDetail',
                    params: { ruleId: record.rule_id },
                  }"
                >
                  去验收
                </router-link>
              </div>
            </div>
          </template>
        </template>
      </ProStandardTable>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import { ClipboardCheck, FileSearch, Play, Search, SlidersHorizontal } from 'lucide-vue-next'
import MqIcon from '@/components/icons/MqIcon.vue'
import ProQueryBar from '@/components/pro/ProQueryBar.vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import type { SemanticRuleItem, SichuanRuleSetOption } from '../types'
import { getDocTypeZh } from '../types'
import { executionStatus, executionStatusHint } from '../executionStatus'
import { buildSemanticRuleRowActionModel } from '../service'

const DEFAULT_RULE_SET_SELECT_VALUE = '__default_sc_rules__'

const props = defineProps<{
  loading: boolean
  rules: SemanticRuleItem[]
  scopeRules?: SemanticRuleItem[]
  total: number
  ruleSetKey: string
  ruleSetOptions: SichuanRuleSetOption[]
  keywordInput: string
  complexity: string
  defectLevel: string
  documentType: string
  releaseScope?: string
  complexityOptions: string[]
  defectOptions: string[]
  documentOptions: string[]
  pagination: TablePaginationConfig
}>()

const emit = defineEmits<{
  'update:keywordInput': [value: string]
  'update:ruleSetKey': [value: string]
  ruleSetChange: [value: string]
  'update:complexity': [value: string]
  'update:defectLevel': [value: string]
  'update:documentType': [value: string]
  'update:releaseScope': [value: string]
  openQcEvaluation: []
  openCustomWorkspace: []
  tableChange: [pagination: TablePaginationConfig]
  viewDetail: [rule: SemanticRuleItem]
  startTest: [rule: SemanticRuleItem]
}>()

const { confirmedResultsOnly } = useQcResultVisibility()

function isLuxianRule(rule: SemanticRuleItem | undefined): boolean {
  return Boolean(rule?.rule_id && String(rule.rule_id).startsWith('LX0609-'))
}

function handleStartTest(rule: SemanticRuleItem) {
  if (confirmedResultsOnly.value || isLuxianRule(rule)) return
  emit('startTest', rule)
}

/** 只有 LX0609 规则带目录发布范围；其他规则集不显示发布范围列与筛选 */
const hasReleaseScope = computed(
  () => props.rules.some((rule) => Boolean(rule.release_scope)) || Boolean(props.releaseScope),
)
const columns = computed(() => [
  { title: '序号', key: 'index', width: 52, align: 'center' as const, responsive: ['md'] },
  { title: '编号', key: 'rule_id', width: 142 },
  { title: '规则名称', key: 'name' },
  ...(hasReleaseScope.value
    ? [{ title: '发布范围', key: 'release_scope', width: 92, responsive: ['lg'] }]
    : []),
  { title: '适用文书', key: 'applicable_documents', width: 116, responsive: ['lg'] },
  ...(props.ruleSetKey === 'luxian_0609_qc_v1'
    ? [{ title: '执行状态', key: 'execution_status', width: 96, responsive: ['lg'] }]
    : []),
])

const executionSummary = computed(() => {
  const counts = new Map<string, number>()
  for (const rule of props.scopeRules || props.rules) {
    const label = executionStatus(rule)
    counts.set(label, (counts.get(label) || 0) + 1)
  }
  return [...counts].map(([label, count]) => `${label} ${count} 条`).join(' · ')
})

const rowAction = buildSemanticRuleRowActionModel()
const normalizedRuleSetOptions = computed(() =>
  props.ruleSetOptions.map((item) => ({
    value: item.rule_set_key || DEFAULT_RULE_SET_SELECT_VALUE,
    label: item.rule_set_name,
  })),
)
const selectedRuleSetValue = computed(() => props.ruleSetKey || DEFAULT_RULE_SET_SELECT_VALUE)
const selectedRuleSetLabel = computed(
  () =>
    normalizedRuleSetOptions.value.find((item) => item.value === selectedRuleSetValue.value)
      ?.label || '质控规则集',
)

function getRowNumber(index: number): number {
  const page = Number(props.pagination.current || 1)
  const pageSize = Number(props.pagination.pageSize || 10)
  return (page - 1) * pageSize + index + 1
}

function handleTableChange(pagination: TablePaginationConfig) {
  emit('tableChange', pagination)
}

function handleRuleSetSelectChange(value: string | number) {
  const normalized = String(value || '')
  const nextValue = normalized === DEFAULT_RULE_SET_SELECT_VALUE ? '' : normalized
  emit('update:ruleSetKey', nextValue)
  emit('ruleSetChange', nextValue)
}

function buildCustomRow(record: SemanticRuleItem) {
  return {
    class: 'semantic-rule-row',
    onClick: (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      if (
        target.closest('button') ||
        target.closest('a') ||
        target.closest('.ant-btn') ||
        target.closest('.ant-pagination')
      ) {
        return
      }
      emit('viewDetail', record)
    },
  }
}
</script>

<style scoped>
.execution-summary {
  margin: 12px 20px;
  color: var(--mq-text-secondary);
  font-size: 14px;
  line-height: 22px;
}
</style>

<style scoped src="./styles/semantic-rules-table.css"></style>

<style>
.semantic-rule-select-dropdown {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.94);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-synthesis-weight: none;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: geometricprecision;
}

.semantic-rule-select-dropdown .ant-select-item {
  min-height: 34px;
  padding: 7px 12px;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
  letter-spacing: 0;
}

.semantic-rule-select-dropdown
  .ant-select-item-option-active:not(.ant-select-item-option-disabled) {
  background: rgba(0, 0, 0, 0.04);
}

.semantic-rule-select-dropdown
  .ant-select-item-option-selected:not(.ant-select-item-option-disabled) {
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  font-weight: 600;
}

.semantic-rule-select-dropdown .ant-select-item-option-content {
  font-size: inherit;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-weight: inherit;
  line-height: inherit;
}
</style>
