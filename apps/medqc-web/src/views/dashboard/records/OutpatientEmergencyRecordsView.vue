<template>
  <div class="outpatient-emergency-page min-h-screen p-5 lg:p-6">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          当前筛选病历
        </div>
        <div
          data-testid="outpatient-current-total"
          class="apple-metric-value apple-primary"
        >
          {{ currentRecordTotal }}
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          待处理
        </div>
        <div class="apple-metric-value apple-warning">
          暂不可用
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          缺陷总数
        </div>
        <div class="apple-metric-value apple-danger">
          暂不可用
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          通过率
        </div>
        <div class="apple-metric-value apple-success">
          暂不可用
        </div>
      </div>
    </div>

    <div class="apple-workbench flex flex-col h-[calc(100vh-180px)]">
      <div
        class="px-6 py-4 border-b border-slate-100 flex flex-col gap-4"
      >
        <div class="outpatient-toolbar-row flex items-center gap-3">
          <div class="relative">
            <a-input
              v-model:value="searchKeyword"
              placeholder="搜索病案号/姓名/医生..."
              class="w-64 apple-input !pl-10"
              @press-enter="handleSearch"
            />
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>
          <a-button
            type="primary"
            class="!rounded-xl"
            @click="handleSearch"
          >
            查询
          </a-button>

          <a-select
            v-model:value="selectedDepartment"
            class="w-36 custom-select"
            placeholder="选择科室"
            :bordered="false"
            allow-clear
          >
            <a-select-option
              v-for="dept in departmentOptions"
              :key="dept.value"
              :value="dept.value"
            >
              {{ dept.label }}
            </a-select-option>
          </a-select>

          <a-input
            v-model:value="scoringStandard"
            data-testid="outpatient-scoring-standard-filter"
            aria-label="病历源评分标准"
            placeholder="病历源评分标准（精确匹配）"
            class="w-64 apple-input"
            allow-clear
            @press-enter="handleSearch"
          />

          <a-range-picker
            v-model:value="dateRange"
            class="apple-picker !rounded-xl"
            :bordered="false"
          />

          <a-button
            class="!rounded-xl !border-slate-200"
            @click="resetFilters"
          >
            清空条件
          </a-button>
        </div>

        <OutpatientFilterTemplateBar
          :current-filters="currentTemplateFilters"
          :disabled="loading"
          @apply="applyTemplateFilters"
        />

        <div class="outpatient-toolbar-row flex items-center gap-2">
          <a-button
            :disabled="!selectedRowKeys.length"
            class="!rounded-xl"
            @click="openFirstSelectedDetail"
          >
            批量查看详情
          </a-button>
          <a-button
            disabled
            class="!rounded-xl"
          >
            批量催办
          </a-button>
          <a-button
            disabled
            class="!rounded-xl"
          >
            批量通过
          </a-button>
          <a-button
            :disabled="!selectedRowKeys.length || !remediationAssignmentEnabled"
            class="!rounded-xl"
            @click="handleBatchAssignRemediation"
          >
            批量派发整改
          </a-button>
          <a-button
            data-testid="export-outpatient-records"
            :disabled="!appliedExportFilters || loading || exportLoading"
            :loading="exportLoading"
            class="!rounded-xl"
            @click="handleExportRecords"
          >
            <template #icon>
              <Download :size="15" aria-hidden="true" />
            </template>
            导出病历
          </a-button>
          <a-tooltip title="刷新数据">
            <a-button
              class="apple-icon-button !h-9 !w-9 !p-0 flex items-center justify-center"
              @click="handleRefresh"
            >
              <ReloadOutlined :spin="loading" />
            </a-button>
          </a-tooltip>
        </div>
      </div>

      <div
        role="status"
        class="px-6 py-2 text-xs text-slate-600 bg-slate-50 border-b border-slate-100"
      >
        门急诊质控关联待核实，状态、得分、缺陷及其审核、催办、导出暂不可用；病历文书仍可查看。
      </div>

      <div
        v-if="!remediationAssignmentEnabled"
        class="px-6 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100"
      >
        {{ remediationAssignmentHint }}
      </div>

      <div
        v-if="selectedRowKeys.length"
        class="px-6 py-2 bg-[rgba(43,108,246,0.06)] border-b border-[rgba(43,108,246,0.12)] text-sm text-slate-700 flex items-center justify-between"
      >
        <span>已选择
          <span class="font-semibold text-[#2b6cf6]">{{ selectedRowKeys.length }}</span>
          条门急诊病历</span>
        <a-button
          type="link"
          class="!px-0"
          @click="selectedRowKeys = []"
        >
          清空选择
        </a-button>
      </div>

      <div class="flex-1 overflow-hidden px-6 py-2">
        <div
          v-if="listError && !loading"
          data-testid="outpatient-list-error"
          role="alert"
          class="h-full flex flex-col items-center justify-center gap-3 text-center text-slate-600"
        >
          <div class="font-medium text-slate-800">
            门急诊病历暂时无法加载
          </div>
          <div class="text-sm">
            {{ listError }}
          </div>
          <a-button
            data-testid="retry-outpatient-list"
            type="primary"
            @click="fetchRecords"
          >
            重试
          </a-button>
        </div>
        <a-table
          v-else
          :columns="columns"
          :data-source="records"
          :loading="loading"
          :pagination="pagination"
          :row-selection="rowSelection"
          row-key="id"
          class="modern-table h-full"
          :scroll="{ y: 'calc(100vh - 320px)' }"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'recordNumber'">
              <a
                class="font-mono font-semibold text-slate-700 hover:text-[#2b6cf6]"
                @click="openDetail(record as AdminRecordItem)"
              >
                {{ record.record_id || record.id }}
              </a>
            </template>
            <template v-if="column.key === 'status'">
              <span class="text-slate-500">质控关联待核实</span>
            </template>
            <template v-if="column.key === 'score' || column.key === 'defect_count'">
              <span class="text-slate-500">暂不可用</span>
            </template>
            <template v-if="column.key === 'actions'">
              <div class="flex items-center gap-2">
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  @click="openDetail(record as AdminRecordItem)"
                >
                  查看病历文书
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  disabled
                >
                  催办
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  disabled
                >
                  通过
                </a-button>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </div>

    <OutpatientEmergencyDetailDrawer
      :visible="detailVisible"
      :loading="detailLoading"
      :record="detailRecord"
      :detail-data="detailData"
      :error="detailError"
      :remediation-enabled="remediationAssignmentEnabled"
      :has-prev="detailIndex > 0"
      :has-next="detailIndex >= 0 && detailIndex < records.length - 1"
      :current-index="detailIndex + 1"
      :total-count="records.length"
      @close="closeDetail"
      @retry="retryDetail"
      @navigate-prev="navigateDetail(-1)"
      @navigate-next="navigateDetail(1)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import { Download } from 'lucide-vue-next'
import {
  exportOutpatientEmergencyRecords,
  getDepartmentList,
  getRecordDetail,
  getOutpatientEmergencyRecordList,
  type AdminRecordItem,
  type OutpatientEmergencyRecordFilters,
} from '@/api/qcAdmin'
import { useAuthStore } from '@/stores/auth'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import OutpatientEmergencyDetailDrawer from './OutpatientEmergencyDetailDrawer.vue'
import OutpatientFilterTemplateBar, {
  type OutpatientFilterSnapshot,
} from './OutpatientFilterTemplateBar.vue'

const loading = ref(false)
const listError = ref('')
let recordListRequestSequence = 0
let exportRequestSequence = 0
const exportLoading = ref(false)
const appliedExportFilters = ref<OutpatientEmergencyRecordFilters | null>(null)
const searchKeyword = ref('')
const selectedDepartment = ref<string | undefined>(undefined)
const scoringStandard = ref('')
type DateRange = [Dayjs, Dayjs] | null
const dateRange = ref<DateRange>(null)
let suppressAutomaticFetch = false
let mounted = false
const records = ref<AdminRecordItem[]>([])
const departmentOptions = ref<Array<{ value: string; label: string }>>([])
const selectedRowKeys = ref<string[]>([])
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailRecord = ref<AdminRecordItem | null>(null)
const detailData = ref<Record<string, unknown> | null>(null)
const detailError = ref('')
let detailRequestSequence = 0
const detailIndex = computed(() =>
  records.value.findIndex((record) => record.id === detailRecord.value?.id),
)
const authStore = useAuthStore()
const actorKey = computed(() => (
  `${authStore.user?.id || ''}|${[...authStore.userRoles].sort().join(',')}`
))

const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
})

const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

const remediationAssignmentEnabled = false
const remediationAssignmentHint = '整改责任人策略待确认，当前暂不开放派发整改'

const selectedRecords = computed(() => {
  const keySet = new Set(selectedRowKeys.value)
  return records.value.filter((record) => keySet.has(String(record.id)))
})

const currentRecordTotal = computed(() => {
  if (loading.value) return '加载中'
  if (listError.value) return '不可用'
  return pagination.value.total.toLocaleString()
})

const currentTemplateFilters = computed<OutpatientFilterSnapshot>(() => ({
  keyword: searchKeyword.value || undefined,
  department: selectedDepartment.value,
  start_date: dateRange.value?.[0]?.format('YYYY-MM-DD'),
  end_date: dateRange.value?.[1]?.format('YYYY-MM-DD'),
}))

const columns: TableColumnsType<AdminRecordItem> = [
  { title: '病历号', dataIndex: 'record_id', key: 'recordNumber', width: 140 },
  { title: '患者姓名', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '就诊类型', dataIndex: 'visit_type', key: 'visit_type', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 120 },
  { title: '就诊时间', dataIndex: 'visit_date', key: 'visit_date', width: 160 },
  { title: '质控状态', key: 'status', width: 150 },
  { title: '得分', dataIndex: 'score', key: 'score', width: 100 },
  { title: '缺陷数', dataIndex: 'defect_count', key: 'defect_count', width: 100 },
  { title: '操作', key: 'actions', width: 220, fixed: 'right' as const },
]

const loadDepartments = async () => {
  const res = await getDepartmentList()
  if (res.success && res.data) {
    departmentOptions.value = res.data.map((d) => ({ value: d.code || d.name, label: d.name }))
  }
}

const currentListFilters = (): OutpatientEmergencyRecordFilters => ({
  keyword: searchKeyword.value || undefined,
  department: selectedDepartment.value,
  scoring_standard: scoringStandard.value.trim() || undefined,
  start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
  end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
  sort_field: 'visit_date',
  sort_order: 'desc',
})

const isValidRecordList = (value: unknown): value is { items: AdminRecordItem[]; total: number } => {
  if (!value || typeof value !== 'object') return false
  const payload = value as Record<string, unknown>
  return Array.isArray(payload.items)
    && payload.items.every((item) => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    && typeof payload.total === 'number'
    && Number.isInteger(payload.total)
    && payload.total >= 0
}

const fetchRecords = async () => {
  const requestSequence = ++recordListRequestSequence
  const requestActorKey = actorKey.value
  const listFilters = currentListFilters()
  loading.value = true
  listError.value = ''
  try {
    const res = await getOutpatientEmergencyRecordList({
      ...listFilters,
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    if (requestSequence !== recordListRequestSequence || requestActorKey !== actorKey.value) {
      return
    }
    if (res.success && isValidRecordList(res.data)) {
      records.value = res.data.items
      pagination.value.total = res.data.total
      appliedExportFilters.value = { ...listFilters }
      return
    }
    records.value = []
    selectedRowKeys.value = []
    pagination.value.total = 0
    appliedExportFilters.value = null
    listError.value = res.success
      ? '门急诊病历列表返回格式异常，请稍后重试'
      : res.message || '获取门急诊病历失败，请稍后重试'
  } catch {
    if (requestSequence !== recordListRequestSequence || requestActorKey !== actorKey.value) {
      return
    }
    records.value = []
    selectedRowKeys.value = []
    pagination.value.total = 0
    appliedExportFilters.value = null
    listError.value = '获取门急诊病历失败，请稍后重试'
    message.error(listError.value)
  } finally {
    if (requestSequence === recordListRequestSequence && requestActorKey === actorKey.value) {
      loading.value = false
    }
  }
}

const invalidatePendingExport = () => {
  exportRequestSequence += 1
  exportLoading.value = false
}

const handleExportRecords = async () => {
  if (!appliedExportFilters.value || exportLoading.value || loading.value) return
  const requestSequence = ++exportRequestSequence
  const filters = { ...appliedExportFilters.value }
  exportLoading.value = true
  const result = await exportOutpatientEmergencyRecords(filters)
  if (requestSequence !== exportRequestSequence) return
  exportLoading.value = false
  if (result.success === false) {
    message.error(result.message)
    return
  }
  downloadBlob(result.blob, result.filename)
}

const handleSearch = () => {
  pagination.value.current = 1
  fetchRecords()
}

const applyTemplateFilters = async (filters: OutpatientFilterSnapshot) => {
  suppressAutomaticFetch = true
  searchKeyword.value = filters.keyword || ''
  selectedDepartment.value = filters.department || undefined
  scoringStandard.value = ''
  dateRange.value =
    filters.start_date && filters.end_date
      ? [dayjs(filters.start_date), dayjs(filters.end_date)]
      : null
  pagination.value.current = 1
  selectedRowKeys.value = []
  await nextTick()
  suppressAutomaticFetch = false
  fetchRecords()
}

const resetFilters = () => {
  void applyTemplateFilters({})
}

const handleRefresh = () => {
  fetchRecords()
}

const resolveRecordId = (record: AdminRecordItem): string => {
  return String(record.id || '').trim()
}

const openDetail = async (record: AdminRecordItem) => {
  const recordId = resolveRecordId(record)
  if (!recordId) {
    message.warning('病历ID缺失，无法打开详情')
    return
  }

  const requestSequence = ++detailRequestSequence
  detailRecord.value = record
  detailData.value = null
  detailError.value = ''
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await getRecordDetail(recordId, 'legacy_medical_records')
    if (requestSequence !== detailRequestSequence) return
    if (res.success && res.data && typeof res.data === 'object') {
      detailData.value = res.data as Record<string, unknown>
      return
    }
    detailError.value = res.message || '加载质控详情失败，请重试'
  } catch {
    if (requestSequence === detailRequestSequence) {
      detailError.value = '加载质控详情失败，请重试'
    }
  } finally {
    if (requestSequence === detailRequestSequence) detailLoading.value = false
  }
}

const retryDetail = () => {
  if (detailRecord.value) void openDetail(detailRecord.value)
}

const closeDetail = () => {
  detailRequestSequence += 1
  detailVisible.value = false
  detailLoading.value = false
  detailData.value = null
  detailError.value = ''
}

const navigateDetail = (offset: number) => {
  const nextRecord = records.value[detailIndex.value + offset]
  if (nextRecord) void openDetail(nextRecord)
}

const openFirstSelectedDetail = async () => {
  if (!selectedRecords.value.length) {
    return
  }
  await openDetail(selectedRecords.value[0])
}

const handleBatchAssignRemediation = async () => {
  message.warning(remediationAssignmentHint)
}

const handleTableChange = (pag: { current?: number; pageSize?: number }) => {
  pagination.value.current = pag.current || pagination.value.current
  pagination.value.pageSize = pag.pageSize || pagination.value.pageSize
  fetchRecords()
}

watch([selectedDepartment, dateRange], () => {
  if (suppressAutomaticFetch) return
  pagination.value.current = 1
  fetchRecords()
})

watch([searchKeyword, selectedDepartment, dateRange, scoringStandard], invalidatePendingExport)

watch(actorKey, () => {
  recordListRequestSequence += 1
  detailRequestSequence += 1
  loading.value = false
  records.value = []
  selectedRowKeys.value = []
  pagination.value.total = 0
  appliedExportFilters.value = null
  listError.value = ''
  invalidatePendingExport()
  if (mounted && authStore.user?.id) {
    void fetchRecords()
    return
  }
  listError.value = '当前未登录，门急诊病历不可用'
})

onMounted(() => {
  mounted = true
  loadDepartments()
  fetchRecords()
})

onBeforeUnmount(() => {
  mounted = false
  recordListRequestSequence += 1
  detailRequestSequence += 1
  invalidatePendingExport()
})
</script>

<style scoped>
.outpatient-emergency-page {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.apple-metric-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  padding: 16px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.045);
  backdrop-filter: blur(18px);
}

.outpatient-toolbar-row {
  min-width: 0;
  flex-wrap: wrap;
}

.outpatient-toolbar-row > * {
  max-width: 100%;
}

.apple-metric-value {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 24px;
  font-weight: 700;
  line-height: 31px;
}

.apple-primary {
  color: #2b6cf6;
}

.apple-warning {
  color: #b7791f;
}

.apple-danger {
  color: #d92d20;
}

.apple-success {
  color: #0f8f67;
}

.apple-workbench {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.06),
    0 10px 30px rgba(0, 0, 0, 0.045);
  backdrop-filter: blur(18px);
}

.apple-input {
  border-color: rgba(0, 0, 0, 0.08) !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.72) !important;
}

.apple-picker {
  border-color: rgba(0, 0, 0, 0.08) !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.72) !important;
}

.apple-icon-button {
  border-color: rgba(0, 0, 0, 0.08) !important;
  border-radius: 8px !important;
  color: rgba(29, 29, 31, 0.6) !important;
}

.apple-icon-button:hover {
  border-color: rgba(43, 108, 246, 0.24) !important;
  color: #2b6cf6 !important;
}

:deep(.ant-btn-primary) {
  border-color: #2b6cf6 !important;
  background: #2b6cf6 !important;
  box-shadow: 0 2px 8px rgba(43, 108, 246, 0.18) !important;
}

:deep(.ant-btn-link) {
  color: #2b6cf6;
}

:deep(.ant-input:hover),
:deep(.ant-input:focus),
:deep(.ant-picker:hover),
:deep(.ant-picker-focused) {
  border-color: rgba(43, 108, 246, 0.32) !important;
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08) !important;
}

:deep(.custom-select .ant-select-selector) {
  background-color: rgba(255, 255, 255, 0.72) !important;
  border-radius: 8px !important;
  border: 1px solid rgba(0, 0, 0, 0.08) !important;
  height: 36px !important;
  display: flex;
  align-items: center;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: rgba(43, 108, 246, 0.32) !important;
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08) !important;
}

:deep(.modern-table .ant-table-thead > tr > th) {
  background: rgba(245, 245, 247, 0.76);
  color: rgba(29, 29, 31, 0.6);
  font-weight: 600;
  font-size: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

:deep(.modern-table .ant-table-tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  font-size: 13px;
}

:deep(.modern-table .ant-table-tbody > tr:hover > td) {
  background: rgba(0, 0, 0, 0.035);
}

:deep(.ant-tag-blue) {
  color: #2b6cf6;
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.08);
}

:deep(.ant-pagination-item-active) {
  border-color: #2b6cf6;
}

:deep(.ant-pagination-item-active a) {
  color: #2b6cf6;
}
</style>
