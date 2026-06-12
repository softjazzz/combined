<template>
  <a-modal
    :open="open"
    title="发起批量质控"
    width="760px"
    ok-text="开始执行"
    cancel-text="取消"
    :confirm-loading="testingBatch"
    @ok="handleConfirm"
    @cancel="emit('update:open', false)"
  >
    <div class="space-y-4">
      <div class="summary-grid">
        <div class="summary-card">
          <div class="summary-label">
            规则数量
          </div>
          <div class="summary-value">
            {{ selectedRunDraftCount }}
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">
            病历范围
          </div>
          <div class="summary-value">
            {{ selectedRunSceneLabel }}
          </div>
        </div>
        <div class="summary-card">
          <div class="summary-label">
            已选病历
          </div>
          <div class="summary-value">
            {{ selectedRecordCount }}
          </div>
        </div>
      </div>

      <a-form layout="vertical">
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="病历范围">
              <a-select
                :value="batchLaunchFilters.scope"
                :options="scopeOptions"
                :loading="batchLaunchFiltersLoading"
                @update:value="handleScopeUpdate"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="日期字段">
              <a-select
                :value="batchLaunchFilters.date_field"
                :options="dateFieldOptions"
                @update:value="handleDateFieldUpdate"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="科室">
              <a-select
                :value="batchLaunchFilters.department"
                allow-clear
                :loading="batchLaunchFiltersLoading"
                :options="batchLaunchDepartmentOptions"
                placeholder="全部科室"
                @update:value="handleDepartmentUpdate"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="医生">
              <a-select
                :value="batchLaunchFilters.doctor"
                allow-clear
                :loading="batchLaunchFiltersLoading"
                :options="batchLaunchDoctorOptions"
                placeholder="全部医生"
                @update:value="handleDoctorUpdate"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="batchLaunchDateFieldLabel">
              <a-range-picker
                :value="batchLaunchFilters.dateRange"
                class="w-full"
                @update:value="handleDateRangeUpdate"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="关键词">
              <a-input
                :value="batchLaunchFilters.keyword"
                allow-clear
                placeholder="姓名/住院号/visit"
                @update:value="handleKeywordUpdate"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import dayjs, { type Dayjs } from 'dayjs'
import type { WorkspaceScope } from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null
type DateRangeInput = [Dayjs, Dayjs] | [string, string] | null
type SelectInputValue = string | number | undefined

type BatchLaunchFilters = {
  scope: WorkspaceScope
  department?: string
  doctor?: string
  date_field: 'admission' | 'discharge'
  dateRange: DateRangeValue
  keyword: string
}

const props = defineProps<{
  open: boolean
  testingBatch: boolean
  confirmBatchLaunch: () => void | Promise<void>
  selectedRunDraftCount: number
  selectedRunSceneLabel: string
  selectedRecordCount: number
  batchLaunchFilters: BatchLaunchFilters
  scopeOptions: Array<{ label: string; value: string }>
  batchLaunchFiltersLoading: boolean
  batchLaunchDepartmentOptions: Array<{ label: string; value: string }>
  batchLaunchDoctorOptions: Array<{ label: string; value: string }>
  handleBatchLaunchScopeChange: (scope: WorkspaceScope) => void | Promise<void>
  handleBatchLaunchDepartmentChange: (department?: string) => void | Promise<void>
  batchLaunchDateFieldLabel: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update:batch-launch-filters': [value: BatchLaunchFilters]
}>()

const dateFieldOptions = [
  { label: '按入院日期', value: 'admission' },
  { label: '按出院日期', value: 'discharge' },
]

function patchFilters(partial: Partial<BatchLaunchFilters>) {
  emit('update:batch-launch-filters', {
    ...props.batchLaunchFilters,
    ...partial,
  })
}

function normalizeScope(value: SelectInputValue): WorkspaceScope {
  return value === 'running' || value === 'final' ? value : 'all'
}

function normalizeTextValue(value: SelectInputValue): string | undefined {
  if (value === undefined || value === null || value === '') return undefined
  return String(value)
}

function normalizeDateRange(value: DateRangeInput): [Dayjs, Dayjs] | null {
  if (!value) return null
  const [start, end] = value
  if (typeof start === 'string' || typeof end === 'string') {
    return [dayjs(start), dayjs(end)]
  }
  return value as [Dayjs, Dayjs]
}

async function handleScopeUpdate(value: SelectInputValue) {
  const scope = normalizeScope(value)
  patchFilters({
    scope,
    department: undefined,
    doctor: undefined,
  })
  await props.handleBatchLaunchScopeChange(scope)
}

async function handleDepartmentUpdate(value: SelectInputValue) {
  patchFilters({
    department: normalizeTextValue(value),
    doctor: undefined,
  })
  await props.handleBatchLaunchDepartmentChange(normalizeTextValue(value))
}

function handleDoctorUpdate(value: SelectInputValue) {
  patchFilters({
    doctor: normalizeTextValue(value),
  })
}

function handleDateFieldUpdate(value: SelectInputValue) {
  patchFilters({
    date_field: value === 'discharge' ? 'discharge' : 'admission',
  })
}

function handleDateRangeUpdate(value: DateRangeInput) {
  patchFilters({
    dateRange: normalizeDateRange(value),
  })
}

function handleKeywordUpdate(value: SelectInputValue) {
  patchFilters({
    keyword: String(value || ''),
  })
}

async function handleConfirm() {
  await props.confirmBatchLaunch()
}
</script>

<style scoped>
.summary-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  font-family: 'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter,
    'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.summary-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  padding: 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.summary-label {
  color: rgba(29, 29, 31, 0.60);
  font-size: 12px;
  font-weight: 500;
}

.summary-value {
  color: #0066cc;
  font-size: 18px;
  font-weight: 700;
  margin-top: 4px;
}

:deep(.ant-modal-content),
:deep(.ant-modal-header) {
  font-family: 'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter,
    'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:deep(.ant-modal-content) {
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

:deep(.ant-modal-title) {
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
}

:deep(.ant-btn) {
  border-radius: 8px;
  font-family: 'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter,
    'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-weight: 600;
}

:deep(.ant-btn-primary) {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.18);
}

:deep(.ant-btn-primary:not(:disabled):hover) {
  background: #0057b8;
  border-color: #0057b8;
}

:deep(.ant-input),
:deep(.ant-picker),
:deep(.ant-select-selector) {
  border-radius: 8px !important;
  border-color: rgba(0, 0, 0, 0.08) !important;
  font-family: 'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter,
    'PingFang SC', 'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:deep(.ant-input:hover),
:deep(.ant-picker:hover),
:deep(.ant-select:not(.ant-select-disabled):hover .ant-select-selector) {
  border-color: rgba(0, 102, 204, 0.22) !important;
}
</style>
