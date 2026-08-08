<template>
  <section class="batch-table-panel">
    <div class="batch-table-panel__header px-4 py-2">
      <div
        class="batch-table-panel__toolbar flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
      >
        <div class="batch-table-panel__toolbar-meta min-w-0">
          <div class="flex flex-wrap items-center gap-2.5">
            <div class="batch-table-panel__title">
              {{ title }}
            </div>
            <span class="batch-table-panel__summary-pill">当前 {{ rows.length }} 条</span>
            <span
              v-if="showSelection"
              class="batch-table-panel__summary-pill batch-table-panel__summary-pill--selected"
            >
              已选 {{ selectedRowKeys.length }} 条
            </span>
          </div>
        </div>

        <div
          v-if="showBatchActions"
          class="batch-table-panel__actions flex flex-wrap items-center gap-2"
        >
          <a-button
            v-if="showPrimaryAction"
            size="small"
            type="primary"
            class="batch-table-panel__action batch-table-panel__action--primary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-extract', selectedRowKeys)"
          >
            {{ primaryActionLabel }}
          </a-button>
          <a-button
            v-if="showDeferAction"
            size="small"
            class="batch-table-panel__action batch-table-panel__action--secondary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-defer', selectedRowKeys)"
          >
            标记稍后
          </a-button>
          <a-button
            v-if="showAssignAction"
            size="small"
            class="batch-table-panel__action batch-table-panel__action--secondary"
            :disabled="selectedRowKeys.length === 0 || readonly"
            @click="emit('batch-assign', selectedRowKeys)"
          >
            分派
          </a-button>
          <a-button
            v-if="showClearFiltersAction"
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
      :data-source="displayRows"
      :loading="loading"
      row-key="id"
      :pagination="tablePagination"
      :row-selection="rowSelection"
      :scroll="tableScroll"
      :locale="tableLocale"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'patient'">
          <div class="batch-table-panel__patient-cell">
            <img
              class="batch-table-panel__avatar"
              :src="patientAvatarSrc(record)"
              :alt="`${record.patientName || '患者'}头像`"
            >
            <span class="batch-table-panel__patient-meta">
              <span class="batch-table-panel__patient-name">
                {{ record.patientName }}
              </span>
              <span class="batch-table-panel__visit-line">
                <span class="batch-table-panel__visit-label">住院号：</span>
                <span class="batch-table-panel__visit-id font-mono">
                  {{ record.visitId }}
                </span>
                <span
                  v-if="record.isDemo"
                  class="batch-table-panel__tag batch-table-panel__tag--demo inline-flex items-center px-2 py-0.5 text-[11px] font-semibold"
                >
                  样例
                </span>
              </span>
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
        <template v-else-if="column.key === 'dataState'">
          <div class="batch-table-panel__quality-cell">
            <span class="batch-table-panel__quality-title">{{ sourceStateLabel(record.sourceState) }}</span>
            <span class="batch-table-panel__quality-detail">不以文书数量推断资料完整性</span>
          </div>
        </template>
        <template v-else-if="column.key === 'qcResult'">
          <div class="batch-table-panel__quality-cell">
            <span
              class="batch-table-panel__tag batch-table-panel__quality-title"
              :class="qcSummaryClass(record.latestQcSummary)"
            >{{ latestQcSummaryLabel(record.latestQcSummary) }}</span>
            <span class="batch-table-panel__quality-detail">{{ latestQcSummaryDetail(record.latestQcSummary) }}</span>
          </div>
        </template>
        <template v-else-if="column.key === 'risk'">
          <span class="batch-table-panel__risk">{{ record.riskReason }}</span>
        </template>
        <template v-else-if="column.key === 'admissionDischarge'">
          <span class="batch-table-panel__date-pair">
            <span>{{ record.admissionDate || '-' }}</span>
            <span>{{ record.dischargeDate || '-' }}</span>
          </span>
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
            {{ rowActionLabel }}
          </a-button>
        </template>
      </template>
    </a-table>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RecordLatestQcSummary, RecordSourceState } from '../../types'
import patientIconBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import patientIconElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import patientIconElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import patientIconGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import patientIconMan from '@/assets/avatar-icons/patient-icon-man.png'
import patientIconWoman from '@/assets/avatar-icons/patient-icon-woman.png'

export interface WorkbenchRow {
  id: string
  patientName: string
  patientSex?: string
  patientAge?: number
  visitId: string
  department: string
  stageStatus: string
  riskReason: string
  admissionDate?: string
  dischargeDate?: string
  updatedAt: string
  isDemo: boolean
  sourceState?: RecordSourceState
  latestQcSummary?: RecordLatestQcSummary
}

const props = defineProps<{
  rows: WorkbenchRow[]
  selectedRowKeys: string[]
  summaryText: string
  currentPage?: number
  pageSize?: number
  total?: number
  loading?: boolean
  readonly?: boolean
  title?: string
  primaryActionLabel?: string
  rowActionLabel?: string
  showSelection?: boolean
  showPrimaryAction?: boolean
  showDeferAction?: boolean
  showAssignAction?: boolean
  showClearFiltersAction?: boolean
  showQualityColumns?: boolean
}>()

const emit = defineEmits<{
  'update:selectedRowKeys': [keys: string[]]
  'open-record': [id: string]
  'batch-extract': [keys: string[]]
  'batch-defer': [keys: string[]]
  'batch-assign': [keys: string[]]
  'clear-filters': []
  'page-change': [page: number, pageSize?: number]
}>()

const showSelection = computed(() => props.showSelection !== false)

const rowSelection = computed(() => {
  if (!showSelection.value) return undefined
  return {
    selectedRowKeys: props.selectedRowKeys,
    onChange: (keys: (string | number)[]) =>
      emit(
        'update:selectedRowKeys',
        keys.map((k) => String(k)),
      ),
  }
})

const title = computed(() => props.title || '病历池列表')
const primaryActionLabel = computed(() => props.primaryActionLabel || '批量处理')
const rowActionLabel = computed(() => props.rowActionLabel || '查看详情')
const showPrimaryAction = computed(() => props.showPrimaryAction !== false)
const showDeferAction = computed(() => props.showDeferAction === true)
const showAssignAction = computed(() => props.showAssignAction === true)
const showClearFiltersAction = computed(() => props.showClearFiltersAction === true)
const showQualityColumns = computed(() => props.showQualityColumns === true)
const showBatchActions = computed(
  () =>
    showPrimaryAction.value ||
    showDeferAction.value ||
    showAssignAction.value ||
    showClearFiltersAction.value,
)
const tableScroll = computed(() => ({
  x: showQualityColumns.value ? 1240 : 980,
  y: showSelection.value ? undefined : 440,
}))
const displayRows = computed(() => {
  if (showSelection.value) return props.rows
  const currentPageSize = Number(props.pageSize || 15)
  if (!Number.isFinite(currentPageSize) || currentPageSize <= 0) return props.rows
  return props.rows.slice(0, currentPageSize)
})

const tableLocale = {
  emptyText: '当前筛选条件下暂无候选病历',
}

const tablePagination = computed(() => {
  const pageSize = Number(props.pageSize || 15)
  const totalFromProps = Number(props.total || 0)
  const totalFromRows = Array.isArray(props.rows) ? props.rows.length : 0
  const total = Math.max(totalFromProps, totalFromRows)
  return {
    current: Number(props.currentPage || 1),
    total,
    pageSize,
    size: 'small' as const,
    showQuickJumper: true,
    showSizeChanger: true,
    pageSizeOptions: ['15', '30', '50', '100'],
    hideOnSinglePage: false,
    showTotal: (value: number) => `共 ${value} 例`,
  }
})

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  const nextPage = Number(pagination.current || 1)
  const nextPageSize = Number(pagination.pageSize || props.pageSize || 15)
  const currentPage = Number(props.currentPage || 1)
  const currentPageSize = Number(props.pageSize || 15)
  if (nextPage === currentPage && nextPageSize === currentPageSize) return
  emit('page-change', nextPage, nextPageSize)
}

function isFemale(sex?: string) {
  return /女|female|^f$/i.test(String(sex || '').trim())
}

function patientAvatarSrc(record: { patientSex?: string; patientAge?: number }) {
  const age = Number(record.patientAge || 0)
  const female = isFemale(record.patientSex)
  if (Number.isFinite(age) && age > 0 && age < 14) {
    return female ? patientIconGirl : patientIconBoy
  }
  if (Number.isFinite(age) && age >= 55) {
    return female ? patientIconElderWoman : patientIconElderMan
  }
  return female ? patientIconWoman : patientIconMan
}

function stageTagClass(stageStatus: string) {
  if (/终末|完成|已完成/.test(stageStatus)) return 'batch-table-panel__tag--success'
  if (/待复核|质控|待审核/.test(stageStatus)) return 'batch-table-panel__tag--review'
  if (/资料不全|缺失/.test(stageStatus)) return 'batch-table-panel__tag--danger'
  if (/超时|临期/.test(stageStatus)) return 'batch-table-panel__tag--warning'
  if (/待处理|处理中|抽取/.test(stageStatus)) return 'batch-table-panel__tag--brand'
  return 'batch-table-panel__tag--neutral'
}

const stageColumns = [
  { title: '患者信息', key: 'patient', dataIndex: 'patient', width: 260 },
  { title: '科室', key: 'department', dataIndex: 'department', width: 160 },
  { title: '状态', key: 'stageStatus', dataIndex: 'stageStatus', width: 110 },
  { title: '风险标签', key: 'risk', dataIndex: 'riskReason', width: 220 },
  { title: '入院 / 出院', key: 'admissionDischarge', dataIndex: 'admissionDischarge', width: 140 },
  { title: '更新时间', key: 'updatedAt', dataIndex: 'updatedAt', width: 150 },
  { title: '操作', key: 'action', dataIndex: 'action', width: 120 },
]

const qualityColumns = [
  { title: '患者信息', key: 'patient', dataIndex: 'patient', width: 250 },
  { title: '科室', key: 'department', dataIndex: 'department', width: 140 },
  { title: '数据状态', key: 'dataState', dataIndex: 'dataState', width: 210 },
  { title: '最新质控结果', key: 'qcResult', dataIndex: 'qcResult', width: 240 },
  { title: '入院 / 出院', key: 'admissionDischarge', dataIndex: 'admissionDischarge', width: 150 },
  { title: '更新时间', key: 'updatedAt', dataIndex: 'updatedAt', width: 150 },
  { title: '操作', key: 'action', dataIndex: 'action', width: 100 },
]

const columns = computed(() => (showQualityColumns.value ? qualityColumns : stageColumns))

function sourceStateLabel(sourceState?: RecordSourceState): string {
  if (!sourceState || sourceState.status === 'unknown') return '资料同步状态待核实'
  return '资料同步状态待核实'
}

function latestQcSummaryLabel(summary?: RecordLatestQcSummary): string {
  if (!summary || summary.status === 'not_run') return '尚未运行质控'
  if (summary.status === 'technical_error') return '结果校验异常'
  return `已完成 · ${Number(summary.totalRuleCount || 0)} 条规则`
}

function latestQcSummaryDetail(summary?: RecordLatestQcSummary): string {
  if (!summary || summary.status === 'not_run') return '当前规则版本尚未生成结果'
  if (summary.status === 'technical_error') return qcErrorReasonLabel(summary.reasonCode)
  const statusCounts = summary.statusCounts || {}
  const defects = Number(statusCounts.non_compliant || 0)
  const dataGaps = Number(statusCounts.data_gap || 0)
  if (defects || dataGaps) {
    return `确定问题 ${defects} 项；资料待补 ${dataGaps} 项`
  }
  return '当前规则版本结果已完成'
}

function qcSummaryClass(summary?: RecordLatestQcSummary): string {
  if (!summary || summary.status === 'not_run') return 'batch-table-panel__tag--neutral'
  if (summary.status === 'technical_error') return 'batch-table-panel__tag--danger'
  const defects = Number(summary.statusCounts?.non_compliant || 0)
  const dataGaps = Number(summary.statusCounts?.data_gap || 0)
  if (defects) return 'batch-table-panel__tag--warning'
  if (dataGaps) return 'batch-table-panel__tag--review'
  return 'batch-table-panel__tag--success'
}

function qcErrorReasonLabel(reasonCode?: string | null): string {
  const labels: Record<string, string> = {
    generation_conflict: '同一病历存在冲突的结果代次，请联系管理员复核',
    canonical_envelope_missing: '质控结果未完整交付，请联系管理员复核',
    canonical_envelope_invalid: '质控结果校验未通过，请联系管理员复核',
  }
  return labels[String(reasonCode || '')] || '质控结果暂无法校验，请联系管理员复核'
}
</script>

<style scoped>
.batch-table-panel {
  overflow: hidden;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.96);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 14px 32px rgba(148, 163, 184, 0.12);
}

.batch-table-panel__header {
  border-bottom: 1px solid var(--workstation-divider, rgba(226, 232, 240, 0.88));
}

.batch-table-panel__toolbar {
  gap: 8px;
}

.batch-table-panel__toolbar-meta {
  min-width: 0;
}

.batch-table-panel__title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--workstation-text-primary, #1d1d1f);
}

.batch-table-panel__summary-pill {
  display: inline-flex;
  align-items: center;
  border-radius: var(--workstation-radius-pill, 999px);
  border: 0;
  background: rgba(248, 250, 252, 0.9);
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
  color: var(--workstation-text-secondary, #5b6b84);
}

.batch-table-panel__summary-pill--selected {
  border-color: var(--workstation-brand-border, rgba(191, 219, 254, 0.96));
  background: var(--workstation-brand-100, rgba(239, 246, 255, 0.96));
  color: var(--workstation-brand-600, #1e5ae0);
}

.batch-table-panel__action {
  height: 34px !important;
  border-radius: 9px !important;
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
  background: var(--workstation-brand-500, #0066cc) !important;
  color: #fff !important;
  box-shadow: 0 12px 22px rgba(47, 111, 237, 0.18) !important;
}

.batch-table-panel__action--primary:hover {
  background: var(--workstation-brand-600, #1e5ae0) !important;
  box-shadow: 0 14px 26px rgba(47, 111, 237, 0.22) !important;
}

.batch-table-panel__action--secondary {
  border-color: transparent !important;
  background: transparent !important;
  color: var(--workstation-text-secondary, #5b6b84) !important;
  box-shadow: none !important;
}

.batch-table-panel__action--ghost,
.batch-table-panel__detail-button {
  border-color: transparent !important;
  background: rgba(255, 255, 255, 0.72) !important;
  color: var(--workstation-text-secondary, #5b6b84) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 8px 16px rgba(191, 207, 228, 0.12) !important;
}

.batch-table-panel__action--secondary:hover,
.batch-table-panel__action--ghost:hover,
.batch-table-panel__detail-button:hover {
  border-color: transparent !important;
  color: var(--workstation-brand-600, #1e5ae0) !important;
}

.batch-table-panel :deep(.ant-pagination-options) {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.batch-table-panel :deep(.ant-table-pagination) {
  margin: 8px 12px !important;
}

.batch-table-panel :deep(.ant-table-thead > tr > th) {
  padding-top: 7px !important;
  padding-bottom: 7px !important;
}

.batch-table-panel :deep(.ant-pagination-options-size-changer) {
  min-width: 104px;
}

.batch-table-panel__patient-name {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--workstation-text-primary, #1d1d1f);
}

.batch-table-panel__patient-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.batch-table-panel__avatar {
  display: block;
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  border-radius: 999px;
  background: #eaf2ff;
  object-fit: cover;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.96),
    0 2px 6px rgba(0, 102, 204, 0.08);
}

.batch-table-panel__patient-meta {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.batch-table-panel__visit-line {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 2px;
}

.batch-table-panel__tag,
.batch-table-panel__detail-button {
  border-radius: 8px;
}

.batch-table-panel__visit-label {
  color: var(--workstation-text-muted, #94a3b8);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.batch-table-panel__visit-id {
  color: var(--workstation-text-secondary, #5b6b84);
  font-size: 12px;
}

.batch-table-panel__department,
.batch-table-panel__risk {
  font-size: 12px;
  color: var(--workstation-text-secondary, #5b6b84);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.batch-table-panel__quality-cell {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.batch-table-panel__quality-title {
  width: fit-content;
  max-width: 100%;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.batch-table-panel__quality-detail {
  overflow: hidden;
  color: var(--workstation-text-muted, #94a3b8);
  font-size: 11px;
  font-weight: 500;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-table-panel__date-pair {
  display: flex;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--workstation-text-secondary, #5b6b84);
}

.batch-table-panel__updated-at {
  font-size: 11px;
  font-weight: 600;
  color: var(--workstation-text-muted, #94a3b8);
}

.batch-table-panel__tag {
  border: 0;
  flex-shrink: 0;
  box-shadow: none;
}

.batch-table-panel__tag--demo {
  background: color-mix(in srgb, var(--workstation-state-demo-bg, #eaf5ff) 84%, white);
  color: var(--workstation-state-demo-text, #0f6cbd);
}

.batch-table-panel__tag--brand {
  background: color-mix(
    in srgb,
    var(--workstation-brand-050, rgba(234, 242, 255, 0.98)) 88%,
    white
  );
  color: var(--workstation-brand-600, #1e5ae0);
}

.batch-table-panel__tag--review {
  background: color-mix(in srgb, var(--workstation-state-review-bg, #f3eeff) 84%, white);
  color: var(--workstation-state-review-text, #6e56cf);
}

.batch-table-panel__tag--danger {
  background: color-mix(in srgb, var(--workstation-state-danger-bg, #fdeded) 84%, white);
  color: var(--workstation-state-danger-text, #b94a48);
}

.batch-table-panel__tag--warning {
  background: color-mix(in srgb, var(--workstation-state-warning-bg, #fff6e5) 84%, white);
  color: var(--workstation-state-warning-text, #b85a00);
}

.batch-table-panel__tag--success {
  background: color-mix(in srgb, rgba(236, 253, 245, 0.96) 86%, white);
  color: #0f766e;
}

.batch-table-panel__tag--neutral {
  background: rgba(248, 250, 252, 0.86);
  color: var(--workstation-text-secondary, #5b6b84);
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
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--workstation-divider, rgba(226, 232, 240, 0.88));
}

.batch-table-panel :deep(.ant-table-tbody > tr > td) {
  background: transparent;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  padding-top: 5px;
  padding-bottom: 5px;
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
  height: 26px !important;
  padding: 0 10px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
}
</style>
