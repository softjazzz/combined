<template>
  <section class="batch-table-panel">
    <div class="batch-table-panel__header px-5 py-4">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div class="min-w-0">
          <div class="batch-table-panel__eyebrow">
            Batch Workspace
          </div>
          <div class="mt-2 flex flex-wrap items-end gap-3">
            <div class="batch-table-panel__title">
              批量工作台
            </div>
            <span class="batch-table-panel__summary-pill"> 当前 {{ rows.length }} 条候选病历 </span>
            <span class="batch-table-panel__summary-pill batch-table-panel__summary-pill--selected">
              已选 {{ selectedRowKeys.length }} 条
            </span>
          </div>
          <div class="batch-table-panel__summary mt-2">
            {{ summaryText }}
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <a-button
            size="small"
            type="primary"
            class="batch-table-panel__action batch-table-panel__action--primary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-extract', selectedRowKeys)"
          >
            批量进入抽取
          </a-button>
          <a-button
            size="small"
            class="batch-table-panel__action batch-table-panel__action--secondary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-defer', selectedRowKeys)"
          >
            批量标记稍后
          </a-button>
          <a-button
            size="small"
            class="batch-table-panel__action batch-table-panel__action--secondary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-assign', selectedRowKeys)"
          >
            批量分派
          </a-button>
          <a-button
            size="small"
            class="batch-table-panel__action batch-table-panel__action--ghost"
            @click="emit('clear-filters')"
          >
            清空筛选
          </a-button>
        </div>
      </div>
    </div>

    <a-table
      class="batch-table-panel__table"
      :columns="columns"
      :data-source="rows"
      :loading="loading"
      row-key="id"
      :pagination="false"
      :row-selection="rowSelection"
      :scroll="{ x: 980 }"
      :locale="tableLocale"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'patient'">
          <div class="batch-table-panel__patient-cell">
            <span class="batch-table-panel__patient-name">
              {{ record.patientName }}
            </span>
            <span
              class="batch-table-panel__visit-id inline-flex items-center px-2.5 py-1 font-mono text-[11px]"
            >
              {{ record.visitId }}
            </span>
            <span
              v-if="record.isDemo"
              class="batch-table-panel__tag batch-table-panel__tag--demo inline-flex items-center px-2.5 py-1 text-[11px] font-semibold"
            >
              Demo
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'department'">
          <span class="batch-table-panel__department">{{ record.department }}</span>
        </template>
        <template v-else-if="column.key === 'stageStatus'">
          <span
            class="batch-table-panel__tag inline-flex items-center px-2.5 py-1 text-[11px] font-semibold"
            :class="stageTagClass(record.stageStatus)"
          >
            {{ record.stageStatus }}
          </span>
        </template>
        <template v-else-if="column.key === 'risk'">
          <span class="batch-table-panel__risk">{{ record.riskReason }}</span>
        </template>
        <template v-else-if="column.key === 'updatedAt'">
          <span class="batch-table-panel__updated-at">{{ record.updatedAt }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="default"
            size="small"
            class="batch-table-panel__detail-button"
            @click="emit('open-record', record.id)"
          >
            查看详情
          </a-button>
        </template>
      </template>
    </a-table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface WorkbenchRow {
  id: string
  patientName: string
  visitId: string
  department: string
  stageStatus: string
  riskReason: string
  updatedAt: string
  isDemo: boolean
}

const props = defineProps<{
  rows: WorkbenchRow[]
  selectedRowKeys: string[]
  summaryText: string
  loading?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  'update:selectedRowKeys': [keys: string[]]
  'open-record': [id: string]
  'batch-extract': [keys: string[]]
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
}>()

const rowSelection = computed(() => ({
  selectedRowKeys: props.selectedRowKeys,
  onChange: (keys: (string | number)[]) =>
    emit(
      'update:selectedRowKeys',
      keys.map((k) => String(k)),
    ),
}))

const tableLocale = {
  emptyText: '当前筛选条件下暂无候选病历',
}

function stageTagClass(stageStatus: string) {
  if (/终末|完成|已完成/.test(stageStatus)) return 'batch-table-panel__tag--success'
  if (/待复核|质控|待审核/.test(stageStatus)) return 'batch-table-panel__tag--review'
  if (/资料不全|缺失/.test(stageStatus)) return 'batch-table-panel__tag--danger'
  if (/待处理|处理中|抽取/.test(stageStatus)) return 'batch-table-panel__tag--brand'
  return 'batch-table-panel__tag--neutral'
}

const columns = [
  { title: '患者信息', key: 'patient', dataIndex: 'patient', width: 340 },
  { title: '科室', key: 'department', dataIndex: 'department', width: 160 },
  { title: '阶段状态', key: 'stageStatus', dataIndex: 'stageStatus', width: 120 },
  { title: '风险原因', key: 'risk', dataIndex: 'riskReason', width: 340 },
  { title: '更新时间', key: 'updatedAt', dataIndex: 'updatedAt', width: 100 },
  { title: '操作', key: 'action', dataIndex: 'action', width: 120 },
]
</script>

<style scoped>
.batch-table-panel {
  overflow: hidden;
  border-radius: var(--workstation-radius-panel, 28px);
  border: 1px solid var(--workstation-border-light, rgba(255, 255, 255, 0.92));
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(246, 249, 252, 0.96));
  box-shadow: var(--workstation-shadow-panel, 0 24px 60px rgba(148, 163, 184, 0.12));
}

.batch-table-panel__header {
  border-bottom: 1px solid var(--workstation-divider, rgba(226, 232, 240, 0.88));
}

.batch-table-panel__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--workstation-text-muted, #94a3b8);
}

.batch-table-panel__title {
  font-size: 24px;
  font-weight: 900;
  letter-spacing: -0.04em;
  color: var(--workstation-text-primary, #0f172a);
}

.batch-table-panel__summary-pill {
  display: inline-flex;
  align-items: center;
  border-radius: var(--workstation-radius-pill, 999px);
  border: 1px solid var(--workstation-border-light, rgba(255, 255, 255, 0.92));
  background: rgba(255, 255, 255, 0.88);
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 700;
  color: var(--workstation-text-secondary, #5b6b84);
}

.batch-table-panel__summary-pill--selected {
  border-color: var(--workstation-brand-border, rgba(191, 219, 254, 0.96));
  background: var(--workstation-brand-100, rgba(239, 246, 255, 0.96));
  color: var(--workstation-brand-600, #1e5ae0);
}

.batch-table-panel__summary {
  font-size: 13px;
  line-height: 1.6;
  color: var(--workstation-text-secondary, #5b6b84);
}

.batch-table-panel__action {
  height: 36px !important;
  border-radius: var(--workstation-radius-pill, 999px) !important;
  padding: 0 16px !important;
  font-weight: 700 !important;
  transition:
    box-shadow 160ms ease,
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.batch-table-panel__action--primary {
  border: 0 !important;
  background: var(--workstation-brand-500, #2f6fed) !important;
  color: #fff !important;
  box-shadow: var(--workstation-shadow-brand, 0 12px 22px rgba(47, 111, 237, 0.24)) !important;
}

.batch-table-panel__action--primary:hover {
  background: var(--workstation-brand-600, #1e5ae0) !important;
  box-shadow: var(--workstation-shadow-brand-hover, 0 14px 28px rgba(47, 111, 237, 0.3)) !important;
}

.batch-table-panel__action--secondary,
.batch-table-panel__action--ghost,
.batch-table-panel__detail-button {
  border-color: var(--workstation-brand-border, #c9d9f7) !important;
  background: rgba(255, 255, 255, 0.92) !important;
  color: var(--workstation-text-secondary, #5b6b84) !important;
  box-shadow: 0 8px 16px rgba(148, 163, 184, 0.08) !important;
}

.batch-table-panel__action--secondary:hover,
.batch-table-panel__action--ghost:hover,
.batch-table-panel__detail-button:hover {
  border-color: rgba(191, 219, 254, 0.95) !important;
  color: var(--workstation-brand-600, #1e5ae0) !important;
}

.batch-table-panel__patient-name {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--workstation-text-primary, #0f172a);
}

.batch-table-panel__patient-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  white-space: nowrap;
}

.batch-table-panel__visit-id,
.batch-table-panel__tag,
.batch-table-panel__detail-button {
  border-radius: var(--workstation-radius-pill, 999px);
}

.batch-table-panel__visit-id {
  border: 1px solid var(--workstation-border-soft, rgba(15, 23, 42, 0.06));
  background: var(--workstation-bg-card-soft, rgba(248, 250, 252, 0.92));
  color: var(--workstation-text-secondary, #5b6b84);
  flex-shrink: 0;
}

.batch-table-panel__department,
.batch-table-panel__risk {
  font-size: 13px;
  color: var(--workstation-text-secondary, #5b6b84);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.batch-table-panel__updated-at {
  font-size: 12px;
  font-weight: 600;
  color: var(--workstation-text-muted, #94a3b8);
}

.batch-table-panel__tag {
  border: 1px solid transparent;
  flex-shrink: 0;
}

.batch-table-panel__tag--demo {
  background: var(--workstation-state-demo-bg, #eaf5ff);
  color: var(--workstation-state-demo-text, #0f6cbd);
  border-color: rgba(191, 219, 254, 0.9);
}

.batch-table-panel__tag--brand {
  background: var(--workstation-brand-050, rgba(234, 242, 255, 0.98));
  color: var(--workstation-brand-600, #1e5ae0);
  border-color: var(--workstation-brand-border, rgba(191, 219, 254, 0.96));
}

.batch-table-panel__tag--review {
  background: var(--workstation-state-review-bg, #f3eeff);
  color: var(--workstation-state-review-text, #6e56cf);
  border-color: rgba(216, 180, 254, 0.9);
}

.batch-table-panel__tag--danger {
  background: var(--workstation-state-danger-bg, #fdeded);
  color: var(--workstation-state-danger-text, #b94a48);
  border-color: rgba(252, 165, 165, 0.9);
}

.batch-table-panel__tag--success {
  background: rgba(236, 253, 245, 0.96);
  color: #0f766e;
  border-color: rgba(167, 243, 208, 0.92);
}

.batch-table-panel__tag--neutral {
  background: var(--workstation-bg-card-soft, rgba(248, 250, 252, 0.92));
  color: var(--workstation-text-secondary, #5b6b84);
  border-color: var(--workstation-border-soft, rgba(15, 23, 42, 0.06));
}

.batch-table-panel :deep(.ant-table) {
  background: transparent;
}

.batch-table-panel :deep(.ant-table-container) {
  border-top: 1px solid var(--workstation-divider, rgba(226, 232, 240, 0.88));
}

.batch-table-panel :deep(.ant-table-thead > tr > th) {
  background: var(--workstation-bg-table-header, rgba(248, 250, 252, 0.92));
  color: var(--workstation-text-muted, #94a3b8);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--workstation-divider, rgba(226, 232, 240, 0.88));
}

.batch-table-panel :deep(.ant-table-tbody > tr > td) {
  background: transparent;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  padding-top: 12px;
  padding-bottom: 12px;
}

.batch-table-panel :deep(.ant-table-tbody > tr:hover > td) {
  background: var(--workstation-bg-table-row-hover, rgba(248, 250, 252, 0.88));
}

.batch-table-panel :deep(.ant-table-tbody > tr.ant-table-row-selected > td) {
  background: var(--workstation-bg-table-row-selected, rgba(239, 246, 255, 0.92));
}

.batch-table-panel :deep(.ant-checkbox-wrapper) {
  color: var(--workstation-text-secondary, #5b6b84);
}

.batch-table-panel :deep(.ant-checkbox-inner) {
  border-radius: 6px;
  border-color: rgba(191, 219, 254, 0.96);
}

.batch-table-panel :deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background: var(--workstation-brand-500, #2f6fed);
  border-color: var(--workstation-brand-500, #2f6fed);
}

.batch-table-panel :deep(.ant-empty) {
  margin-block: 48px;
}

.batch-table-panel :deep(.ant-empty-description) {
  color: var(--workstation-text-muted, #94a3b8);
  font-size: 13px;
}

.batch-table-panel__detail-button {
  height: 32px !important;
  padding: 0 14px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
}
</style>
