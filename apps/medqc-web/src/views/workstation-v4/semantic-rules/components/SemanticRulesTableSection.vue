<template>
  <section class="table-shell">
    <div class="table-shell-head">
      <div>
        <p class="table-shell-eyebrow">
          规则工作区
        </p>
        <h3 class="table-shell-title">
          规则执行工作台
        </h3>
      </div>
      <div class="table-shell-right">
        <div class="table-shell-meta">
          <span class="table-shell-count">{{ total }}</span>
          <span class="table-shell-label">当前结果</span>
        </div>
        <div class="table-shell-actions">
          <a-button
            class="table-secondary-btn"
            @click="emit('openQcEvaluation')"
          >
            开始质控评估
          </a-button>
          <a-button
            class="table-secondary-btn"
            @click="emit('openCustomWorkspace')"
          >
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
            <SearchOutlined class="text-slate-400" />
          </template>
        </a-input>

        <a-select
          :value="defectLevel"
          class="query-select"
          placeholder="缺陷级别"
          allow-clear
          @update:value="emit('update:defectLevel', String($event || ''))"
        >
          <a-select-option
            v-for="item in defectOptions"
            :key="item"
            :value="item"
          >
            {{ item }}
          </a-select-option>
        </a-select>

        <a-select
          :value="complexity"
          class="query-select"
          placeholder="复杂度"
          allow-clear
          @update:value="emit('update:complexity', String($event || ''))"
        >
          <a-select-option
            v-for="item in complexityOptions"
            :key="item"
            :value="item"
          >
            {{ item }}
          </a-select-option>
        </a-select>

        <a-select
          :value="documentType"
          class="query-select"
          placeholder="适用文书"
          allow-clear
          @update:value="emit('update:documentType', String($event || ''))"
        >
          <a-select-option
            v-for="item in documentOptions"
            :key="item"
            :value="item"
          >
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
        :scroll="{ x: 1200, y: tableScrollY }"
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
            <span class="doc-secondary">
              {{ getDocTypeZh((record.applicable_documents || [])[0] || '未知文书') }}
            </span>
          </template>

          <template v-if="column.key === 'name'">
            <div class="rule-main">
              <button
                class="rule-main-title"
                @click="emit('viewDetail', record as SemanticRuleItem)"
              >
                {{ record.name }}
              </button>
              <span
                class="rule-main-desc"
                :title="record.description"
              >
                {{ record.description || '暂无描述' }}
              </span>
            </div>
          </template>

          <template v-if="column.key === 'complexity'">
            <span
              class="status-pill status-secondary"
              :class="getSecondaryStatusClass(record)"
            >
              {{ getSecondaryStatusLabel(record) }}
            </span>
          </template>

          <template v-if="column.key === 'defect_level'">
            <span
              class="status-pill status-primary"
              :class="getPrimaryStatusClass(record)"
            >
              {{ getPrimaryStatusLabel(record) }}
            </span>
          </template>

          <template v-if="column.key === 'actions'">
            <div class="table-actions">
              <a-button
                type="primary"
                size="small"
                class="action-primary"
                @click="emit('viewDetail', record as SemanticRuleItem)"
              >
                {{ rowAction.primaryLabel }}
              </a-button>
              <a-button
                size="small"
                class="action-secondary"
                @click="emit('startTest', record as SemanticRuleItem)"
              >
                {{ rowAction.secondaryLabel }}
              </a-button>
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
import { SearchOutlined } from '@ant-design/icons-vue'
import ProQueryBar from '@/components/pro/ProQueryBar.vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'
import type { SemanticRuleItem } from '../types'
import { getDocTypeZh } from '../types'
import { buildSemanticRuleRowActionModel, buildSemanticRuleRowStatusModel } from '../service'

const props = defineProps<{
  loading: boolean
  rules: SemanticRuleItem[]
  total: number
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
  { title: '规则名称', key: 'name', width: 520 },
  { title: '复杂度', key: 'complexity', width: 116, align: 'center' as const },
  { title: '缺陷级别', key: 'defect_level', width: 124, align: 'center' as const },
  { title: '操作', key: 'actions', width: 210, fixed: 'right' as const, align: 'right' as const },
])

const tableScrollY = computed(() => 'calc((100vh - 440px) * 2)')
const rowAction = buildSemanticRuleRowActionModel()

function getRowNumber(index: number): number {
  const page = Number(props.pagination.current || 1)
  const pageSize = Number(props.pagination.pageSize || 20)
  return (page - 1) * pageSize + index + 1
}

function getRowStatus(rule: Record<string, any>) {
  return buildSemanticRuleRowStatusModel(rule as SemanticRuleItem)
}

function getPrimaryStatusClass(rule: Record<string, any>): string {
  const status = getRowStatus(rule)
  return `status-${status.primaryTone}`
}

function getSecondaryStatusClass(rule: Record<string, any>): string {
  const status = getRowStatus(rule)
  return `status-${status.secondaryTone}`
}

function getPrimaryStatusLabel(rule: Record<string, any>): string {
  return getRowStatus(rule).primaryLabel
}

function getSecondaryStatusLabel(rule: Record<string, any>): string {
  return getRowStatus(rule).secondaryLabel
}

function handleTableChange(pagination: TablePaginationConfig) {
  emit('tableChange', pagination)
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
  margin-top: 16px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  background: #ffffff;
  box-shadow: 0 14px 34px rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.table-shell-head {
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.table-shell-eyebrow {
  margin: 0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.table-shell-title {
  margin: 2px 0 0;
  font-size: 17px;
  font-weight: 600;
  color: #0f2747;
  line-height: 1.2;
}

.table-shell-right {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.table-shell-meta {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid #dbe7f5;
  background: #f8fbff;
  padding: 8px 12px;
}

.table-shell-count {
  font-size: 20px;
  line-height: 1;
  color: #0f2747;
  font-weight: 700;
}

.table-shell-label {
  color: #6b7280;
  font-size: 11px;
}

.table-shell-actions {
  display: inline-flex;
  gap: 8px;
}

.table-secondary-btn {
  height: 28px;
  border-radius: 10px;
  font-size: 12px;
  color: #334155;
  border-color: #cbd5e1;
}

.query-input {
  width: 320px;
  min-width: 240px;
  border-radius: 12px;
  height: 30px;
  font-size: 13px;
}

.query-select {
  width: 150px;
  height: 30px;
  font-size: 13px;
}

.table-shell-body {
  padding: 8px 16px 14px;
  min-height: calc((100vh - 440px) * 2 + 56px);
}

.index-cell {
  color: #475569;
}

.rule-code-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 82px;
  border-radius: 12px;
  border: 1px solid #c9ddf7;
  background: #edf4ff;
  padding: 6px 10px;
  color: #0f3d78;
  font-size: 13px;
  font-weight: 700;
}

.doc-secondary {
  color: #64748b;
  font-size: 12px;
}

.rule-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-main-title {
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: #0f2747;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  padding: 0;
}

.rule-main-title:hover {
  color: #1d4ed8;
}

.rule-main-desc {
  color: #6b7280;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  min-width: 90px;
  height: 24px;
  border-radius: 8px;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
}

.status-primary.status-danger {
  color: #b91c1c;
  background: #fee2e2;
  border-color: #fecaca;
}

.status-primary.status-warning {
  color: #b45309;
  background: #ffedd5;
  border-color: #fed7aa;
}

.status-primary.status-safe {
  color: #047857;
  background: #dcfce7;
  border-color: #bbf7d0;
}

.status-primary.status-neutral {
  color: #475569;
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.status-secondary {
  color: #64748b;
  background: #f8fafc;
  border-color: #cbd5e1;
}

.table-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

.action-primary {
  height: 24px;
  border-radius: 8px;
  font-size: 12px;
}

.action-secondary {
  height: 24px;
  border-radius: 8px;
  font-size: 12px;
}

:deep(.modern-table .ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #475569;
  font-size: 11px;
  font-weight: 600;
  padding: 10px 10px;
}

:deep(.modern-table .ant-table-tbody > tr > td) {
  padding: 12px 10px;
  vertical-align: top;
  font-size: 12px;
  color: #374151;
}

:deep(.modern-table .ant-table-row:hover > td) {
  background: #eff6ff;
}

:deep(.modern-table .semantic-rule-row) {
  cursor: pointer;
}

@media (max-width: 1279px) {
  .table-shell-right {
    flex-direction: column;
    align-items: flex-end;
  }
  .table-shell-body {
    min-height: calc(100vh - 320px);
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
