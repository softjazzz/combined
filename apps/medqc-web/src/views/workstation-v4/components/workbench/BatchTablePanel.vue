<template>
  <section
    class="batch-table-panel"
    :class="{ 'batch-table-panel--record-pool': recordPoolMode }"
  >
    <div class="batch-table-panel__header px-4 py-2">
      <div
        class="batch-table-panel__toolbar flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"
      >
        <div class="batch-table-panel__toolbar-meta min-w-0">
          <div class="flex flex-wrap items-center gap-2.5">
            <div class="batch-table-panel__title">
              <ListChecks
                v-if="recordPoolMode"
                :size="17"
                aria-hidden="true"
                class="record-pool-list-icon"
              />
              {{ recordPoolMode ? '病历列表' : title }}
            </div>
            <span class="batch-table-panel__summary-pill">{{ recordPoolMode ? '本页' : '当前' }} {{ rows.length }}
              {{ recordPoolMode ? '份' : '条' }}</span>
            <span
              v-if="showSelection && (!recordPoolMode || selectedRowKeys.length > 0)"
              class="batch-table-panel__summary-pill batch-table-panel__summary-pill--selected"
            >
              已选 {{ selectedRowKeys.length }} {{ recordPoolMode ? '份' : '条' }}
            </span>
            <a-button
              v-if="recordPoolMode && showSelection && selectedRowKeys.length > 0"
              type="link"
              size="small"
              class="batch-table-panel__clear-selection"
              data-testid="clear-record-selection"
              @click="emit('update:selectedRowKeys', [])"
            >
              清除选择
            </a-button>
          </div>
        </div>

        <div
          v-if="showBatchActions"
          class="batch-table-panel__actions flex flex-wrap items-center gap-2"
        >
          <slot name="toolbar-actions" />
          <a-button
            v-if="showPrimaryAction"
            size="small"
            type="primary"
            class="batch-table-panel__action batch-table-panel__action--primary"
            :loading="primaryActionLoading"
            :disabled="selectedRowKeys.length === 0 || readonly || primaryActionLoading"
            @click="emit('batch-extract', selectedRowKeys)"
          >
            {{ primaryActionLoading && recordPoolMode ? '创建中…' : primaryActionLabel }}
          </a-button>
          <a-popconfirm
            v-if="showFilterQcAction"
            :title="`将按当前全部筛选条件质控 ${filterQcCount} 份病历，是否继续？`"
            ok-text="开始质控"
            cancel-text="取消"
            :disabled="filterQcDisabled"
            @confirm="emit('filter-qc')"
          >
            <a-button
              size="small"
              class="batch-table-panel__action batch-table-panel__action--secondary"
              data-testid="filter-qc-action"
              :loading="filterQcLoading"
              :disabled="filterQcDisabled"
            >
              {{ filterQcLoading ? '创建中…' : `质控当前筛选（${filterQcCount}）` }}
            </a-button>
          </a-popconfirm>
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

    <div
      v-if="$slots['task-status']"
      class="batch-table-panel__task-status"
      data-testid="batch-table-task-status"
    >
      <slot name="task-status" />
    </div>

    <a-table
      class="batch-table-panel__table"
      :columns="columns"
      :data-source="displayRows"
      :loading="{ spinning: loading === true, tip: '正在加载病历列表…' }"
      :aria-busy="loading"
      :row-key="(record: WorkbenchRow) => record.recordKey || record.id"
      :pagination="tablePagination"
      :row-selection="rowSelection"
      :scroll="tableScroll"
      :custom-row="buildCustomRow"
      :row-class-name="rowClassName"
      @change="handleTableChange"
    >
      <template #emptyText>
        <Empty
          v-if="!loading && !loadError"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          :description="emptyDescription || '当前筛选条件下暂无候选病历'"
        />
      </template>
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'patient'">
          <div class="batch-table-panel__patient-cell">
            <img
              class="batch-table-panel__avatar"
              :src="patientAvatarSrc(record)"
              :alt="`${record.patientName || '患者'}头像`"
            >
            <span class="batch-table-panel__patient-meta">
              <span
                class="batch-table-panel__patient-name"
                :title="record.patientName"
              >
                {{ record.patientName }}
              </span>
              <span class="batch-table-panel__visit-line">
                <span class="batch-table-panel__visit-label">住院号：</span>
                <span
                  class="batch-table-panel__visit-id"
                  :title="record.visitId"
                >
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
          <span
            class="batch-table-panel__department"
            :title="record.department"
          >{{ record.department }}</span>
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
        <template v-else-if="column.key === 'hospitalizationStatus'">
          <span
            class="batch-table-panel__hospitalization-status"
            :class="hospitalizationStatusClass(record)"
          >
            {{ hospitalizationStatusLabel(record) }}
          </span>
        </template>
        <template v-else-if="column.key === 'admissionDate'">
          <span
            class="batch-table-panel__standalone-date"
            :title="displayHospitalDate(record.admissionDate)"
          >
            {{ tableHospitalDate(record.admissionDate) }}
          </span>
        </template>
        <template v-else-if="column.key === 'dischargeDate'">
          <span
            class="batch-table-panel__standalone-date"
            :title="dischargeDateLabel(record)"
          >
            {{ tableHospitalDate(dischargeDateLabel(record)) }}
          </span>
        </template>
        <template v-else-if="column.key === 'admissionDischarge'">
          <div class="batch-table-panel__hospitalization">
            <span
              class="batch-table-panel__hospitalization-status"
              :class="hospitalizationStatusClass(record)"
            >
              {{ hospitalizationStatusLabel(record) }}
            </span>
            <span class="batch-table-panel__date-pair">
              <span class="batch-table-panel__date-line">
                <span class="batch-table-panel__date-label">入院</span>
                <span>{{ displayHospitalDate(record.admissionDate) }}</span>
              </span>
              <span class="batch-table-panel__date-line">
                <span class="batch-table-panel__date-label">出院</span>
                <span :class="{ 'batch-table-panel__date-pending': !isDischargedRecord(record) }">
                  {{ dischargeDateLabel(record) }}
                </span>
              </span>
            </span>
          </div>
        </template>
        <template v-else-if="column.key === 'updatedAt'">
          <span class="batch-table-panel__updated-at">{{ record.updatedAt }}</span>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="default"
            size="small"
            class="batch-table-panel__detail-button"
            :aria-label="
              recordPoolMode ? `查看${record.patientName || ''}病历详情` : rowActionLabel
            "
            @click="emit('open-record', record.recordKey || record.id)"
          >
            <Eye
              v-if="recordPoolMode"
              :size="14"
              aria-hidden="true"
            />
            {{ recordPoolMode ? '查看' : rowActionLabel }}
          </a-button>
        </template>
      </template>
    </a-table>
  </section>
</template>

<script setup lang="ts">
import { Empty } from 'ant-design-vue'
import { computed } from 'vue'
import { Eye, ListChecks } from 'lucide-vue-next'
import type { RecordLatestQcSummary, RecordSourceState } from '../../types'
import {
  WORKSTATION_LIST_PAGE_SIZE,
  WORKSTATION_LIST_PAGE_SIZE_OPTIONS,
  WORKSTATION_LIST_PAGINATION_LOCALE,
} from '../../utils/workstationListPagination'
import {
  dischargeDateLabel,
  displayHospitalDate,
  hospitalizationStatusLabel,
  isDischargedRecord,
  resolvedHospitalizationStatus,
  type HospitalizationRow,
} from './hospitalizationPresentation'
import patientIconBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import patientIconElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import patientIconElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import patientIconGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import patientIconMan from '@/assets/avatar-icons/patient-icon-man.png'
import patientIconWoman from '@/assets/avatar-icons/patient-icon-woman.png'

export interface WorkbenchRow {
  id: string
  recordKey?: string
  patientName: string
  patientSex?: string
  patientAge?: number
  visitId: string
  department: string
  stageStatus: string
  riskReason: string
  admissionDate?: string
  dischargeDate?: string
  hospitalizationStatus?: 'inpatient' | 'discharged' | 'unknown'
  sourceId?: 'legacy_pg' | 'independent_cdm'
  admissionPrecision?: 'date' | 'datetime' | 'unknown'
  dischargePrecision?: 'date' | 'datetime' | 'unknown'
  materialCompleteness?: string
  hospitalizationStatusVerifiedAt?: string
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
  loadError?: boolean
  emptyDescription?: string
  readonly?: boolean
  title?: string
  primaryActionLabel?: string
  primaryActionLoading?: boolean
  filterQcCount?: number
  filterQcLoading?: boolean
  rowActionLabel?: string
  showSelection?: boolean
  showPrimaryAction?: boolean
  showFilterQcAction?: boolean
  showDeferAction?: boolean
  showAssignAction?: boolean
  showClearFiltersAction?: boolean
  /** 病历池预览：当前预览的病历，点击行时切换 */
  activeRowKey?: string
  recordPoolMode?: boolean
}>()

const emit = defineEmits<{
  'update:selectedRowKeys': [keys: string[]]
  'open-record': [id: string]
  'select-row': [id: string]
  'batch-extract': [keys: string[]]
  'filter-qc': []
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
const primaryActionLoading = computed(() => props.primaryActionLoading === true)
const filterQcCount = computed(() => Math.max(0, Math.trunc(Number(props.filterQcCount || 0))))
const filterQcLoading = computed(() => props.filterQcLoading === true)
const filterQcDisabled = computed(
  () => filterQcCount.value === 0 || props.readonly === true || filterQcLoading.value,
)
const rowActionLabel = computed(() => props.rowActionLabel || '查看详情')
const showPrimaryAction = computed(() => props.showPrimaryAction !== false)
const showFilterQcAction = computed(() => props.showFilterQcAction === true)
const showDeferAction = computed(() => props.showDeferAction === true)
const showAssignAction = computed(() => props.showAssignAction === true)
const showClearFiltersAction = computed(() => props.showClearFiltersAction === true)
const recordPoolMode = computed(() => props.recordPoolMode === true)
const showBatchActions = computed(
  () =>
    showPrimaryAction.value ||
    showFilterQcAction.value ||
    showDeferAction.value ||
    showAssignAction.value ||
    showClearFiltersAction.value,
)
const tableScroll = computed(() => ({
  // 保留窄屏横向滚动；宽屏由各列按比例共同分配空间。
  x: recordPoolMode.value ? 672 : 980,
  y: showSelection.value ? undefined : 440,
}))
const displayRows = computed(() => {
  if (showSelection.value) return props.rows
  const currentPageSize = Number(props.pageSize || WORKSTATION_LIST_PAGE_SIZE)
  if (!Number.isFinite(currentPageSize) || currentPageSize <= 0) return props.rows
  return props.rows.slice(0, currentPageSize)
})

const tablePagination = computed(() => {
  const pageSize = Number(props.pageSize || WORKSTATION_LIST_PAGE_SIZE)
  const totalFromProps = Number(props.total || 0)
  const totalFromRows = Array.isArray(props.rows) ? props.rows.length : 0
  const total = Math.max(totalFromProps, totalFromRows)
  if (total === 0) return false
  return {
    current: Number(props.currentPage || 1),
    total,
    pageSize,
    size: 'small' as const,
    showQuickJumper: true,
    showSizeChanger: true,
    pageSizeOptions: WORKSTATION_LIST_PAGE_SIZE_OPTIONS,
    locale: WORKSTATION_LIST_PAGINATION_LOCALE,
    hideOnSinglePage: false,
    showTotal: (value: number) => `共 ${value} 例`,
  }
})

function handleTableChange(pagination: { current?: number; pageSize?: number }) {
  const nextPage = Number(pagination.current || 1)
  const nextPageSize = Number(pagination.pageSize || props.pageSize || WORKSTATION_LIST_PAGE_SIZE)
  const currentPage = Number(props.currentPage || 1)
  const currentPageSize = Number(props.pageSize || WORKSTATION_LIST_PAGE_SIZE)
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

function hospitalizationStatusClass(record: HospitalizationRow) {
  return `batch-table-panel__hospitalization-status--${resolvedHospitalizationStatus(record)}`
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
  {
    title: '住院状态 / 入出院',
    key: 'admissionDischarge',
    dataIndex: 'admissionDischarge',
    width: 230,
  },
  { title: '更新时间', key: 'updatedAt', dataIndex: 'updatedAt', width: 150 },
  { title: '操作', key: 'action', dataIndex: 'action', width: 120 },
]

function tableHospitalDate(value?: string) {
  return displayHospitalDate(value).replace(/^(\d{4}-\d{2}-\d{2}) (?=\d{2}:\d{2})/, '$1\n')
}

// 患者列不再独占剩余空间，日期列保留完整日期与时间的两行宽度。
const recordPoolColumns = [
  { title: '患者 / 住院号', key: 'patient', dataIndex: 'patient', width: '24%' },
  { title: '科室', key: 'department', dataIndex: 'department', width: '21%', ellipsis: true },
  {
    title: '住院状态',
    key: 'hospitalizationStatus',
    dataIndex: 'hospitalizationStatus',
    width: '13%',
  },
  { title: '入院日期', key: 'admissionDate', dataIndex: 'admissionDate', width: '16%' },
  { title: '出院日期', key: 'dischargeDate', dataIndex: 'dischargeDate', width: '16%' },
  { title: '操作', key: 'action', dataIndex: 'action', width: '10%' },
]

const columns = computed(() => (recordPoolMode.value ? recordPoolColumns : stageColumns))

// 病历池模式：点击或键盘 Enter/Space 选中行（非按钮/勾选框）只切换右侧预览，查看详情仍走“查看”按钮
const INTERACTIVE_SELECTOR = 'button, a, input, label, .ant-checkbox-wrapper, [role="button"]'

function buildCustomRow(record: WorkbenchRow) {
  if (!props.recordPoolMode) return {}
  const key = record.recordKey || record.id
  const active = Boolean(props.activeRowKey && props.activeRowKey === key)
  return {
    tabindex: 0,
    'aria-current': active ? ('true' as const) : undefined,
    onClick: (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest(INTERACTIVE_SELECTOR)) return
      emit('select-row', key)
    },
    onKeydown: (event: KeyboardEvent) => {
      if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') return
      const target = event.target as HTMLElement | null
      if (target && target !== event.currentTarget && target.closest(INTERACTIVE_SELECTOR)) return
      if (event.key === ' ' || event.key === 'Spacebar') {
        event.preventDefault()
      }
      emit('select-row', key)
    },
  }
}

function rowClassName(record: WorkbenchRow): string {
  if (!props.recordPoolMode) return ''
  const active = props.activeRowKey && props.activeRowKey === (record.recordKey || record.id)
  return active ? 'batch-table-panel__row--active' : 'batch-table-panel__row--selectable'
}
</script>

<style scoped>
.batch-table-panel__task-status {
  padding: 8px 12px 10px;
}

.batch-table-panel__task-status :deep(.record-pool-qc-status) {
  border-radius: 10px;
  box-shadow: none;
}

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
  border-bottom: 1px solid var(--mq-border);
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
  color: var(--mq-text-primary);
}

.batch-table-panel__summary-pill {
  display: inline-flex;
  align-items: center;
  border-radius: var(--mq-radius-tag);
  border: 0;
  background: rgba(248, 250, 252, 0.9);
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
  color: var(--mq-text-secondary);
}

.batch-table-panel__summary-pill--selected {
  border-color: var(--mq-info-border);
  background: var(--mq-info-bg);
  color: var(--mq-brand-700);
}

.batch-table-panel__action {
  height: 36px !important;
  border-radius: 10px !important;
  padding: 0 14px !important;
  font-weight: 500 !important;
  transition:
    box-shadow 160ms ease,
    border-color 160ms ease,
    background-color 160ms ease,
    color 160ms ease,
    transform 160ms ease;
}

.batch-table-panel__action--primary {
  border: 0 !important;
  background: var(--mq-brand-600) !important;
  color: #fff !important;
  box-shadow: 0 12px 22px rgba(47, 111, 237, 0.18) !important;
}

.batch-table-panel__action--primary:hover {
  background: var(--mq-brand-700) !important;
  box-shadow: 0 14px 26px rgba(47, 111, 237, 0.22) !important;
}

.batch-table-panel__action--secondary {
  border: 1px solid rgba(20, 40, 80, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: var(--mq-text-primary) !important;
  box-shadow: none !important;
}

.batch-table-panel__action--ghost,
.batch-table-panel__detail-button {
  border-color: transparent !important;
  background: rgba(255, 255, 255, 0.72) !important;
  color: var(--mq-text-secondary) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 8px 16px rgba(191, 207, 228, 0.12) !important;
}

.batch-table-panel__action--secondary:hover:not(:disabled) {
  border-color: rgba(10, 108, 255, 0.32) !important;
  background: rgba(10, 108, 255, 0.05) !important;
  color: var(--mq-brand-700) !important;
}

.batch-table-panel__action--ghost:hover,
.batch-table-panel__detail-button:hover {
  border-color: transparent !important;
  color: var(--mq-brand-700) !important;
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
  color: var(--mq-text-primary);
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
    0 2px 6px rgba(10, 108, 255, 0.08);
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
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.batch-table-panel__visit-id {
  color: var(--mq-text-secondary);
  font-size: 12px;
}

.batch-table-panel__department,
.batch-table-panel__risk {
  font-size: 12px;
  color: var(--mq-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.batch-table-panel__hospitalization {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.batch-table-panel__hospitalization-status {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.batch-table-panel__hospitalization-status--inpatient {
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
}

.batch-table-panel__hospitalization-status--discharged {
  background: var(--mq-neutral-bg);
  color: var(--mq-text-secondary);
}

.batch-table-panel__hospitalization-status--unknown {
  background: var(--mq-warning-bg);
  color: var(--mq-warning-text);
}

.batch-table-panel__date-pair {
  display: grid;
  gap: 3px;
  font-size: 12px;
  font-weight: 600;
  color: var(--mq-text-secondary);
}

.batch-table-panel__date-line {
  display: flex;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}

.batch-table-panel__date-label {
  min-width: 24px;
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 600;
}

.batch-table-panel__date-pending {
  color: var(--mq-brand-700);
}

.batch-table-panel__updated-at {
  font-size: 11px;
  font-weight: 600;
  color: var(--mq-text-tertiary);
}

.batch-table-panel__tag {
  border: 0;
  flex-shrink: 0;
  box-shadow: none;
}

.batch-table-panel__tag--demo {
  background: color-mix(in srgb, var(--mq-info-bg) 84%, white);
  color: var(--mq-info-text);
}

.batch-table-panel__tag--brand {
  background: color-mix(
    in srgb,
    var(--mq-brand-tint-6) 88%,
    white
  );
  color: var(--mq-brand-700);
}

.batch-table-panel__tag--review {
  background: color-mix(in srgb, var(--mq-info-bg) 84%, white);
  color: var(--mq-info-text);
}

.batch-table-panel__tag--danger {
  background: color-mix(in srgb, var(--mq-danger-bg) 84%, white);
  color: var(--mq-danger-text);
}

.batch-table-panel__tag--warning {
  background: color-mix(in srgb, var(--mq-warning-bg) 84%, white);
  color: var(--mq-warning-text);
}

.batch-table-panel__tag--success {
  background: color-mix(in srgb, rgba(236, 253, 245, 0.96) 86%, white);
  color: #0f766e;
}

.batch-table-panel__tag--neutral {
  background: rgba(248, 250, 252, 0.86);
  color: var(--mq-text-secondary);
}

.batch-table-panel :deep(.ant-table) {
  background: transparent;
}

.batch-table-panel :deep(.ant-table-container) {
  border-top: 1px solid var(--mq-border);
}

.batch-table-panel :deep(.ant-table-thead > tr > th) {
  background: var(--mq-table-header-bg);
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--mq-border);
}

.batch-table-panel :deep(.ant-table-tbody > tr > td) {
  background: transparent;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  padding-top: 5px;
  padding-bottom: 5px;
}

.batch-table-panel :deep(.ant-table-tbody > tr:hover > td) {
  background: var(--mq-table-row-hover-bg);
}

.batch-table-panel :deep(.ant-table-tbody > tr.ant-table-row-selected > td) {
  background: var(--mq-info-bg);
}

.batch-table-panel :deep(.ant-checkbox-wrapper) {
  color: var(--mq-text-secondary);
}

.batch-table-panel :deep(.ant-checkbox-inner) {
  border-radius: 6px;
  border-color: rgba(191, 219, 254, 0.96);
}

.batch-table-panel :deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background: var(--mq-brand-600);
  border-color: var(--mq-brand-600);
}

.batch-table-panel :deep(.ant-empty) {
  margin-block: 48px;
}

.batch-table-panel :deep(.ant-empty-description) {
  color: var(--mq-text-tertiary);
  font-size: 13px;
}

.batch-table-panel__detail-button {
  height: 26px !important;
  padding: 0 10px !important;
  font-size: 11px !important;
  font-weight: 700 !important;
}

.batch-table-panel--record-pool {
  border-radius: 12px;
  border-color: var(--mq-border);
  background: #fff;
  box-shadow: none;
}

.batch-table-panel--record-pool .batch-table-panel__header {
  padding: 16px 20px;
}

.batch-table-panel--record-pool .batch-table-panel__title {
  font-size: 17px;
  font-weight: 600;
}

.batch-table-panel--record-pool .batch-table-panel__summary-pill {
  background: transparent;
  font-weight: 500;
}

.batch-table-panel--record-pool .batch-table-panel__clear-selection {
  padding-inline: 2px;
  font-size: 12px;
  color: var(--mq-brand-600);
}

.batch-table-panel--record-pool .batch-table-panel__patient-name {
  font-size: 15px;
  line-height: 22px;
  font-weight: 600;
}

.batch-table-panel--record-pool .batch-table-panel__department {
  display: block;
  font-size: 14px;
  color: var(--mq-text-primary);
}

.batch-table-panel--record-pool .batch-table-panel__detail-button {
  height: 30px !important;
  background: transparent !important;
  color: var(--mq-brand-600) !important;
  box-shadow: none !important;
  font-size: 13px !important;
  font-weight: 500 !important;
}

.batch-table-panel--record-pool .batch-table-panel__action--primary {
  box-shadow: none !important;
}

.batch-table-panel--record-pool :deep(.ant-table-container) {
  border-top: 0;
}

.batch-table-panel--record-pool :deep(.ant-table-thead > tr > th) {
  background: #fafbfd;
  color: var(--mq-text-secondary);
  font-size: 14px;
  font-weight: 500;
  letter-spacing: 0;
}

.batch-table-panel--record-pool :deep(.ant-table-tbody > tr > td) {
  padding-top: 12px;
  padding-bottom: 12px;
  border-bottom-color: #edf0f4;
}

.batch-table-panel--record-pool :deep(.ant-table-thead > tr > th),
.batch-table-panel--record-pool :deep(.ant-table-tbody > tr > td) {
  padding-inline: 12px;
}

.batch-table-panel--record-pool .batch-table-panel__detail-button {
  padding-inline: 6px !important;
}

.batch-table-panel__standalone-date {
  display: inline-block;
  white-space: pre;
  overflow-wrap: normal;
  word-break: normal;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}

.batch-table-panel--record-pool :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(10, 108, 255, 0.04);
}

.batch-table-panel--record-pool :deep(.ant-table-tbody > tr.ant-table-row-selected > td) {
  background: rgba(10, 108, 255, 0.085);
}
</style>
