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
                @update:value="(value) => patchFilters({ date_field: value })"
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
                @update:value="(value) => patchFilters({ doctor: value })"
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
                @update:value="(value) => patchFilters({ dateRange: value })"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="关键词">
              <a-input
                :value="batchLaunchFilters.keyword"
                allow-clear
                placeholder="姓名/住院号/visit"
                @update:value="(value) => patchFilters({ keyword: String(value || '') })"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import type { Dayjs } from 'dayjs'
import type { WorkspaceScope } from '@/types/custom-rule-workspace'

type DateRangeValue = [Dayjs, Dayjs] | null

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

async function handleScopeUpdate(value: WorkspaceScope) {
  patchFilters({
    scope: value,
    department: undefined,
    doctor: undefined,
  })
  await props.handleBatchLaunchScopeChange(value)
}

async function handleDepartmentUpdate(value?: string) {
  patchFilters({
    department: value || undefined,
    doctor: undefined,
  })
  await props.handleBatchLaunchDepartmentChange(value || undefined)
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
}

.summary-card {
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 12px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  padding: 12px;
}

.summary-label {
  color: #64748b;
  font-size: 12px;
}

.summary-value {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
  margin-top: 4px;
}
</style>
