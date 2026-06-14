<template>
  <section class="table-shell">
    <div class="table-shell-head">
      <div>
        <h3 class="table-shell-title">规则执行工作台</h3>
      </div>
      <div class="table-shell-right">
        <label class="rule-set-picker">
          <Layers class="rule-set-icon" />
          <span class="rule-set-label">规则集：</span>
          <a-select
            :value="selectedRuleSetValue"
            class="rule-set-select"
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
        <div class="table-shell-meta">
          <List class="workbench-icon" />
          <span class="table-shell-count">{{ total }}</span>
          <span class="table-shell-label">当前结果</span>
        </div>
        <div class="table-shell-actions">
          <a-button type="primary" class="table-primary-btn" @click="emit('openQcEvaluation')">
            <Play class="button-icon" />
            开始质控评估
          </a-button>
          <a-button class="table-secondary-btn" @click="emit('openCustomWorkspace')">
            <SlidersHorizontal class="button-icon" />
            自定义规则工作台
          </a-button>
        </div>
      </div>
    </div>

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
          :value="defectLevel"
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
          :value="complexity"
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
          :value="documentType"
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
        :scroll="{ x: 980 }"
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

          <template v-if="column.key === 'applicable_documents'">
            <span class="doc-type-pill">
              {{ getDocTypeZh((record.applicable_documents || [])[0] || '未知文书') }}
            </span>
          </template>

          <template v-if="column.key === 'name'">
            <div class="rule-main">
              <div class="rule-main-content">
                <button
                  class="rule-main-title"
                  @click="emit('viewDetail', record as SemanticRuleItem)"
                >
                  {{ record.name }}
                </button>
                <div v-if="isLuxianWrapper(record as SemanticRuleItem)" class="rule-main-tags">
                  <span class="mini-tag mini-tag-blue">
                    {{ formatImplementationStatus(record.implementation_status) }}
                  </span>
                  <span class="mini-tag">
                    {{ formatDependencyType(record.dependency_type) }}
                  </span>
                  <span v-if="record.data_status" class="mini-tag mini-tag-amber">
                    {{ formatDataStatus(record.data_status) }}
                  </span>
                  <span v-if="record.primary_execution_rule_id" class="mini-tag mini-tag-green">
                    主执行 {{ record.primary_execution_rule_id }}
                  </span>
                </div>
                <div v-if="record.mapped_rule_ids?.length" class="mapped-rules">
                  映射规则：{{ record.mapped_rule_ids.join('、') }}
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
                  size="small"
                  class="action-secondary"
                  @click="emit('startTest', record as SemanticRuleItem)"
                >
                  <ClipboardCheck class="button-icon" />
                  {{ rowAction.secondaryLabel }}
                </a-button>
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
import {
  ClipboardCheck,
  FileSearch,
  Layers,
  List,
  Play,
  Search,
  SlidersHorizontal,
} from 'lucide-vue-next'
import ProQueryBar from '@/components/pro/ProQueryBar.vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'
import type { SemanticRuleItem, SichuanRuleSetOption } from '../types'
import {
  getDataStatusZh,
  getDependencyTypeZh,
  getDocTypeZh,
  getImplementationStatusZh,
} from '../types'
import { buildSemanticRuleRowActionModel } from '../service'

const DEFAULT_RULE_SET_SELECT_VALUE = '__default_sc_rules__'

const props = defineProps<{
  loading: boolean
  rules: SemanticRuleItem[]
  total: number
  ruleSetKey: string
  ruleSetOptions: SichuanRuleSetOption[]
  keywordInput: string
  complexity: string
  defectLevel: string
  documentType: string
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
  openQcEvaluation: []
  openCustomWorkspace: []
  tableChange: [pagination: TablePaginationConfig]
  viewDetail: [rule: SemanticRuleItem]
  startTest: [rule: SemanticRuleItem]
}>()

const columns = computed(() => [
  { title: '序号', key: 'index', width: 64, fixed: 'left' as const, align: 'center' as const },
  { title: '编号', key: 'rule_id', width: 110, fixed: 'left' as const },
  { title: '适用文书', key: 'applicable_documents', width: 150 },
  { title: '规则名称', key: 'name', width: 760 },
])

const rowAction = buildSemanticRuleRowActionModel()
const normalizedRuleSetOptions = computed(() =>
  props.ruleSetOptions.map((item) => ({
    value: item.rule_set_key || DEFAULT_RULE_SET_SELECT_VALUE,
    label: item.rule_set_name,
  })),
)
const selectedRuleSetValue = computed(() => props.ruleSetKey || DEFAULT_RULE_SET_SELECT_VALUE)

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

function isLuxianWrapper(rule: SemanticRuleItem): boolean {
  return rule.rule_id.startsWith('LX0609-')
}

function formatImplementationStatus(value?: string): string {
  return getImplementationStatusZh(value)
}

function formatDependencyType(value?: string): string {
  return getDependencyTypeZh(value)
}

function formatDataStatus(value?: string): string {
  return getDataStatusZh(value)
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
.table-shell {
  --semantic-font-sans:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  --semantic-font-display:
    'Source Han Sans SC', 'SF Pro Display', 'San Francisco', 'PingFang SC', Inter,
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  --semantic-table-bg: rgba(255, 255, 255, 0.82);
  --semantic-table-hover-bg: rgba(0, 0, 0, 0.025);

  margin-top: 0;
  border-radius: 20px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  font-family: var(--semantic-font-sans);
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  overflow: hidden;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.table-shell :deep(.ant-btn),
.table-shell :deep(.ant-input),
.table-shell :deep(.ant-input-affix-wrapper),
.table-shell :deep(.ant-select),
.table-shell :deep(.ant-select-dropdown),
.table-shell :deep(.ant-select-item),
.table-shell :deep(.ant-tag),
.table-shell :deep(.ant-table),
.table-shell :deep(.ant-pagination) {
  font-family: var(--semantic-font-sans);
}

.table-shell:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.table-shell-head {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 18px 22px 15px;
  background: rgba(255, 255, 255, 0.9);
}

.table-shell-title {
  margin: 0;
  font-family: var(--semantic-font-display);
  font-size: 17px;
  font-weight: 600;
  color: #1d1d1f;
  line-height: 1.2;
  letter-spacing: 0;
}

.table-shell-right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
  min-width: 0;
  flex-wrap: wrap;
}

.rule-set-picker {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: linear-gradient(180deg, rgba(249, 250, 252, 0.98), rgba(239, 241, 246, 0.94));
  border: 1px solid rgba(29, 29, 31, 0.12);
  border-radius: 10px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 0, 0, 0.035);
  color: #1d1d1f;
  cursor: pointer;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 600;
  font-synthesis-weight: none;
  height: 36px;
  min-height: 36px;
  letter-spacing: 0;
  line-height: 20px;
  padding: 0 11px 0 10px;
  text-rendering: geometricprecision;
  white-space: nowrap;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.rule-set-select {
  width: 170px;
}

.rule-set-icon {
  color: rgba(29, 29, 31, 0.68);
  flex: none;
  height: 16px;
  stroke-width: 2.1;
  width: 16px;
}

.rule-set-label {
  color: rgba(29, 29, 31, 0.66);
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 20px;
}

.workbench-icon,
.button-icon,
.query-icon {
  flex: none;
  height: 15px;
  stroke-width: 2;
  width: 15px;
}

.query-icon {
  color: rgba(29, 29, 31, 0.38);
}

.table-shell-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(0, 102, 204, 0.16);
  background: linear-gradient(180deg, rgba(241, 248, 255, 0.96), rgba(230, 243, 255, 0.88));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 102, 204, 0.04);
  padding: 0 12px;
  white-space: nowrap;
}

.table-shell-count {
  font-family: var(--semantic-font-display);
  font-size: 13px;
  line-height: 1;
  color: #0066cc;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.table-shell-label {
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
}

.table-shell-actions {
  display: inline-flex;
  gap: 8px;
}

.table-primary-btn,
.table-secondary-btn {
  align-items: center;
  display: inline-flex;
  gap: 6px;
  height: 36px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  padding: 0 14px;
}

.table-primary-btn {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 4px 10px rgba(0, 102, 204, 0.16);
}

.table-secondary-btn {
  background: rgba(255, 255, 255, 0.94);
  color: rgba(29, 29, 31, 0.68);
  border-color: rgba(29, 29, 31, 0.1);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 1px rgba(0, 0, 0, 0.035);
}

.rule-set-picker:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(242, 244, 248, 0.96));
  border-color: rgba(29, 29, 31, 0.16);
  color: #1d1d1f;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 2px 5px rgba(0, 0, 0, 0.055);
}

.table-shell-meta:hover {
  border-color: rgba(0, 102, 204, 0.22);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 2px 5px rgba(0, 102, 204, 0.07);
}

.table-secondary-btn:hover {
  background: rgba(255, 255, 255, 0.98);
  border-color: rgba(29, 29, 31, 0.15);
  color: #1d1d1f;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 2px 5px rgba(0, 0, 0, 0.055);
}

.table-primary-btn:hover,
.table-primary-btn:focus {
  background: #0057b8;
  border-color: #0057b8;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 12px rgba(0, 102, 204, 0.18);
}

:deep(.rule-set-select .ant-select-selector) {
  height: 32px !important;
  padding: 0 !important;
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
}

:deep(.rule-set-select.ant-select-focused .ant-select-selector),
:deep(.rule-set-select .ant-select-selector:focus),
:deep(.rule-set-select .ant-select-selector:active) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.rule-set-select .ant-select-selection-item) {
  padding-inline-end: 20px !important;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 13px;
  font-weight: 600;
  font-synthesis-weight: none;
  letter-spacing: 0;
  line-height: 32px !important;
  overflow: hidden;
  text-rendering: geometricprecision;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.rule-set-select .ant-select-selection-search-input),
:deep(.rule-set-select .ant-select-selection-placeholder) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  letter-spacing: 0 !important;
}

:deep(.rule-set-select .ant-select-arrow) {
  color: rgba(29, 29, 31, 0.72);
  right: 0;
}

.query-input {
  width: 320px;
  min-width: 240px;
  border-radius: 8px;
  height: 34px;
  font-size: 13px;
}

.query-select {
  width: 152px;
  height: 34px;
  font-size: 13px;
}

.table-shell-body {
  padding: 0;
  min-height: calc(100vh - 360px);
  background: rgba(255, 255, 255, 0.72);
}

.index-cell {
  color: rgba(29, 29, 31, 0.42);
  font-size: 12px;
  font-weight: 600;
}

.rule-code-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 84px;
  border-radius: 8px;
  border: 1px solid rgba(60, 111, 170, 0.2);
  background: rgba(226, 237, 248, 0.72);
  padding: 5px 10px;
  color: #1f6fb2;
  font-family: 'SF Pro Text', 'Cascadia Code', 'Roboto Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0;
}

.doc-type-pill {
  align-items: center;
  background: transparent;
  border: none;
  border-radius: 0;
  color: rgba(29, 29, 31, 0.62);
  display: inline-flex;
  font-size: 12px;
  font-weight: 500;
  min-height: 20px;
  padding: 0;
}

.rule-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  width: 100%;
}

.rule-main-content {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 8px;
}

.rule-main-title {
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  padding: 0;
}

.rule-main-title:hover {
  color: #0066cc;
}

.rule-main-tags,
.mapped-rules,
.rule-inline-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.mapped-rules {
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  font-weight: 500;
}

.rule-inline-actions {
  flex: none;
  justify-content: flex-end;
  align-items: center;
  align-self: flex-start;
  min-width: 180px;
  padding-top: 2px;
}

.mini-tag {
  display: inline-flex;
  align-items: center;
  height: 21px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  padding: 0 8px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 11px;
  font-weight: 600;
}

.mini-tag-blue {
  border-color: rgba(60, 111, 170, 0.2);
  background: rgba(226, 237, 248, 0.72);
  color: #1f6fb2;
}

.mini-tag-green {
  border-color: rgba(60, 111, 170, 0.2);
  background: rgba(226, 237, 248, 0.72);
  color: #1f6fb2;
}

.mini-tag-amber {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}

.status-pill {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 78px;
  height: 24px;
  border-radius: 999px;
  padding: 0 8px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid transparent;
}

.status-primary.status-danger {
  color: #dc3545;
  background: rgba(220, 53, 69, 0.1);
  border-color: rgba(220, 53, 69, 0.2);
}

.status-primary.status-warning {
  color: #9a6200;
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.18);
}

.status-primary.status-safe {
  color: #247a3d;
  background: rgba(40, 167, 69, 0.1);
  border-color: rgba(40, 167, 69, 0.18);
}

.status-primary.status-neutral {
  color: rgba(29, 29, 31, 0.62);
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.08);
}

.status-secondary {
  color: rgba(29, 29, 31, 0.6);
  background: rgba(0, 0, 0, 0.04);
  border-color: rgba(0, 0, 0, 0.08);
}

.action-primary {
  align-items: center;
  display: inline-flex;
  gap: 5px;
  height: 28px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  background: transparent;
  border-color: rgba(0, 102, 204, 0.4);
  color: #0066cc;
  box-shadow: none;
}

.action-secondary {
  align-items: center;
  display: inline-flex;
  gap: 5px;
  height: 28px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(29, 29, 31, 0.62);
  border-color: rgba(0, 0, 0, 0.08);
}

:deep(.modern-table),
:deep(.modern-table .ant-table),
:deep(.modern-table .ant-table-container),
:deep(.modern-table .ant-table-content),
:deep(.modern-table .ant-table-body) {
  background: rgba(255, 255, 255, 0.72);
}

:deep(.modern-table .ant-table-cell),
:deep(.modern-table .ant-table-cell-fix-left),
:deep(.modern-table .ant-table-cell-fix-right) {
  background: var(--semantic-table-bg);
}

:deep(.modern-table .ant-table-thead > tr > th) {
  background: rgba(255, 255, 255, 0.92);
  color: rgba(29, 29, 31, 0.42);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 11px 16px;
}

:deep(.modern-table .ant-table-tbody > tr > td) {
  background: var(--semantic-table-bg);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 14px 16px;
  vertical-align: top;
  font-size: 13px;
  color: rgba(29, 29, 31, 0.74);
}

:deep(.modern-table .ant-table-row:hover > td) {
  background: var(--semantic-table-hover-bg) !important;
}

:deep(.modern-table .ant-table-row:hover > .ant-table-cell-fix-left),
:deep(.modern-table .ant-table-row:hover > .ant-table-cell-fix-right) {
  background: var(--semantic-table-hover-bg) !important;
}

:deep(.modern-table .ant-table-tbody > tr:hover > td),
:deep(.modern-table .ant-table-tbody > tr:hover > td.ant-table-cell-fix-left),
:deep(.modern-table .ant-table-tbody > tr:hover > td.ant-table-cell-fix-right) {
  background: var(--semantic-table-hover-bg) !important;
}

:deep(.modern-table .ant-table-tbody > tr:hover .action-primary),
:deep(.modern-table .ant-table-tbody > tr:hover .action-secondary) {
  background: rgba(255, 255, 255, 0.66);
}

:deep(.modern-table .ant-table-cell-fix-right-first::after),
:deep(.modern-table .ant-table-cell-fix-right-last::after) {
  box-shadow: inset -10px 0 8px -8px rgba(0, 0, 0, 0.1);
}

:deep(.modern-table .ant-table-tbody > tr:hover > .ant-table-cell-fix-right-first::after),
:deep(.modern-table .ant-table-tbody > tr:hover > .ant-table-cell-fix-right-last::after) {
  box-shadow: inset -10px 0 8px -8px rgba(0, 0, 0, 0.08);
}

:deep(.modern-table .ant-table-tbody > tr:hover .action-primary:hover),
:deep(.modern-table .ant-table-tbody > tr:hover .action-secondary:hover) {
  background: rgba(255, 255, 255, 0.88);
}

:deep(.modern-table .ant-table-body::-webkit-scrollbar-track) {
  background: rgba(0, 0, 0, 0.04);
}

:deep(.modern-table .ant-table-body::-webkit-scrollbar-thumb) {
  background: rgba(0, 0, 0, 0.28);
  border-radius: 999px;
}

:deep(.modern-table .semantic-rule-row) {
  cursor: pointer;
}

@media (max-width: 1279px) {
  .table-shell-right {
    flex-direction: column;
    align-items: flex-end;
  }
  .rule-set-picker {
    justify-content: flex-end;
  }
  .table-shell-body {
    min-height: calc(100vh - 300px);
  }
}

@media (max-width: 1023px) {
  .table-shell-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .table-shell-right {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
  }
  .rule-set-picker,
  .rule-set-select {
    width: 100%;
  }
  .query-input {
    width: 100%;
  }
  .query-select {
    width: 100%;
  }
  .table-shell-body {
    min-height: calc(100vh - 260px);
  }
}
</style>

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
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
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
