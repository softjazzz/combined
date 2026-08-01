<template>
  <div class="outpatient-emergency-page min-h-screen p-5 lg:p-6">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          门急诊病历总量
        </div>
        <div class="apple-metric-value apple-primary">
          {{ formatInteger(overviewStats.total_records) }}
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          待处理
        </div>
        <div class="apple-metric-value apple-warning">
          {{ formatInteger(overviewStats.pending_count) }}
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          缺陷总数
        </div>
        <div class="apple-metric-value apple-danger">
          {{ formatInteger(overviewStats.total_defects) }}
        </div>
      </div>
      <div class="apple-metric-card">
        <div class="text-slate-500 text-xs font-medium mb-1">
          通过率
        </div>
        <div class="apple-metric-value apple-success">
          {{ formatRate(overviewStats.pass_rate) }}%
        </div>
      </div>
    </div>

    <div class="apple-workbench flex flex-col h-[calc(100vh-180px)]">
      <div
        class="px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4"
      >
        <div class="flex items-center gap-3 flex-1">
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

          <a-select
            v-model:value="selectedStatus"
            class="w-36 custom-select"
            placeholder="处理状态"
            :bordered="false"
            allow-clear
          >
            <a-select-option value="pending">
              待处理
            </a-select-option>
            <a-select-option value="reviewing">
              审核中
            </a-select-option>
            <a-select-option value="approved">
              已通过
            </a-select-option>
            <a-select-option value="rejected">
              已驳回
            </a-select-option>
          </a-select>

          <a-range-picker
            v-model:value="dateRange"
            class="apple-picker !rounded-xl"
            :bordered="false"
          />

          <a-button
            class="!rounded-xl !border-slate-200"
            @click="resetFilters"
          >
            重置
          </a-button>
        </div>

        <div class="flex items-center gap-2">
          <a-button
            :disabled="!selectedRowKeys.length"
            class="!rounded-xl"
            @click="openFirstSelectedDetail"
          >
            批量查看详情
          </a-button>
          <a-button
            :disabled="!selectedRowKeys.length"
            class="!rounded-xl"
            @click="handleBatchUrge"
          >
            批量催办
          </a-button>
          <a-button
            :disabled="!selectedRowKeys.length"
            class="!rounded-xl"
            @click="handleBatchApprove"
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
            class="!rounded-xl"
            @click="handleExportDefects"
          >
            导出缺陷
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
        v-if="!remediationAssignmentEnabled"
        class="px-6 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100"
      >
        {{ remediationAssignmentHint }}
      </div>

      <div
        v-if="selectedRowKeys.length"
        class="px-6 py-2 bg-[rgba(0,102,204,0.06)] border-b border-[rgba(0,102,204,0.12)] text-sm text-slate-700 flex items-center justify-between"
      >
        <span>已选择
          <span class="font-semibold text-[#0066cc]">{{ selectedRowKeys.length }}</span>
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
        <a-table
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
                class="font-mono font-semibold text-slate-700 hover:text-[#0066cc]"
                @click="openDetail(record as AdminRecordItem)"
              >
                {{ record.record_id || record.id }}
              </a>
            </template>
            <template v-if="column.key === 'status'">
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusText(record.status) }}
              </a-tag>
            </template>
            <template v-if="column.key === 'actions'">
              <div class="flex items-center gap-2">
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  @click="openDetail(record as AdminRecordItem)"
                >
                  质控详情
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  @click="handleRecordUrge(record as AdminRecordItem)"
                >
                  催办
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="!px-0"
                  @click="handleRecordApprove(record as AdminRecordItem)"
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
      :remediation-enabled="remediationAssignmentEnabled"
      @close="detailVisible = false"
      @urge-defect="handleUrgeDefect"
      @approve-defect="handleApproveDefect"
      @reject-defect="handleRejectDefect"
      @assign-remediation="handleAssignRemediationForDefect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import {
  approveDefect,
  batchDefectAction,
  exportDefects,
  getDefectList,
  getAdminOverview,
  getDepartmentList,
  getRecordDetail,
  getOutpatientEmergencyRecordList,
  rejectDefect,
  urgeDefect,
  type AdminOverviewStats,
  type AdminRecordItem,
} from '@/api/qcAdmin'
import OutpatientEmergencyDetailDrawer from './OutpatientEmergencyDetailDrawer.vue'

const loading = ref(false)
const searchKeyword = ref('')
const selectedDepartment = ref<string | undefined>(undefined)
const selectedStatus = ref<string | undefined>(undefined)
type DateRange = [Dayjs, Dayjs] | null
const dateRange = ref<DateRange>(null)
const records = ref<AdminRecordItem[]>([])
const departmentOptions = ref<Array<{ value: string; label: string }>>([])
const selectedRowKeys = ref<string[]>([])
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailRecord = ref<AdminRecordItem | null>(null)
const detailData = ref<Record<string, unknown> | null>(null)

const overviewStats = ref<AdminOverviewStats>({
  total_records: 0,
  archived_count: 0,
  pending_count: 0,
  pass_rate: 0,
  total_defects: 0,
  defects_by_severity: {},
})

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

const columns: TableColumnsType<AdminRecordItem> = [
  { title: '病历号', dataIndex: 'record_id', key: 'recordNumber', width: 140 },
  { title: '患者姓名', dataIndex: 'patient_name', key: 'patient_name', width: 120 },
  { title: '就诊类型', dataIndex: 'visit_type', key: 'visit_type', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 120 },
  { title: '就诊时间', dataIndex: 'visit_date', key: 'visit_date', width: 160 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '得分', dataIndex: 'score', key: 'score', width: 100 },
  { title: '缺陷数', dataIndex: 'defect_count', key: 'defect_count', width: 100 },
  { title: '操作', key: 'actions', width: 120, fixed: 'right' as const },
]

const toNumber = (value: unknown): number => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const formatInteger = (value: unknown): string => Math.trunc(toNumber(value)).toLocaleString()
const formatRate = (value: unknown): string => toNumber(value).toFixed(1)

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    reviewing: '审核中',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || status || '-'
}

const getStatusColor = (status: string) => {
  const map: Record<string, string> = {
    pending: 'orange',
    reviewing: 'blue',
    approved: 'green',
    rejected: 'red',
  }
  return map[status] || 'default'
}

const loadOverview = async () => {
  const res = await getAdminOverview({
    department: selectedDepartment.value,
    start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
    end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
  })
  if (res.success && res.data) {
    overviewStats.value = {
      ...overviewStats.value,
      ...res.data,
      total_records: toNumber(res.data.total_records),
      archived_count: toNumber(res.data.archived_count),
      pending_count: toNumber(res.data.pending_count),
      pass_rate: toNumber(res.data.pass_rate),
      total_defects: toNumber(res.data.total_defects),
      defects_by_severity: res.data.defects_by_severity || {},
    }
  }
}

const loadDepartments = async () => {
  const res = await getDepartmentList()
  if (res.success && res.data) {
    departmentOptions.value = res.data.map((d) => ({ value: d.code || d.name, label: d.name }))
  }
}

const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await getOutpatientEmergencyRecordList({
      keyword: searchKeyword.value || undefined,
      department: selectedDepartment.value,
      status: selectedStatus.value,
      start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
      end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    if (res.success && res.data) {
      records.value = res.data.items || []
      pagination.value.total = res.data.total || 0
      return
    }
    records.value = []
    pagination.value.total = 0
  } catch {
    message.error('获取门急诊病历失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.current = 1
  fetchRecords()
}

const resetFilters = () => {
  searchKeyword.value = ''
  selectedDepartment.value = undefined
  selectedStatus.value = undefined
  dateRange.value = null
  pagination.value.current = 1
  selectedRowKeys.value = []
  fetchRecords()
  loadOverview()
}

const handleRefresh = () => {
  fetchRecords()
  loadOverview()
}

const resolveRecordId = (record: AdminRecordItem): string => {
  const candidate = record.id || record.record_id
  return String(candidate || '').trim()
}

const openDetail = async (record: AdminRecordItem) => {
  const recordId = resolveRecordId(record)
  if (!recordId) {
    message.warning('病历ID缺失，无法打开详情')
    return
  }

  detailRecord.value = record
  detailData.value = null
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await getRecordDetail(recordId)
    if (res.success) {
      detailData.value = (res.data as Record<string, unknown>) || {}
      return
    }
    message.warning(res.message || '加载质控详情失败')
  } catch {
    message.error('加载质控详情失败')
  } finally {
    detailLoading.value = false
  }
}

const queryDefectIdsForRecord = async (record: AdminRecordItem): Promise<string[]> => {
  const recordId = String(record.record_id || '').trim()
  if (!recordId) {
    return []
  }
  const res = await getDefectList({ record_id: recordId, page: 1, page_size: 200 })
  if (!res.success || !res.data) {
    return []
  }
  return (res.data.items || []).map((item) => String(item.id || '').trim()).filter(Boolean)
}

const queryDefectIdsForSelectedRecords = async (): Promise<string[]> => {
  const all = await Promise.all(
    selectedRecords.value.map((record) => queryDefectIdsForRecord(record)),
  )
  return Array.from(new Set(all.flat()))
}

const handleUrgeDefect = async (defectId: string) => {
  const res = await urgeDefect(defectId, { message: '请尽快完成门急诊病历整改' })
  if (res.success) {
    message.success('催办成功')
    return
  }
  message.error(res.message || '催办失败')
}

const handleApproveDefect = async (defectId: string) => {
  const res = await approveDefect(defectId, '门急诊质控审核通过')
  if (res.success) {
    message.success('审核通过')
    handleRefresh()
    return
  }
  message.error(res.message || '审核通过失败')
}

const handleRejectDefect = async (defectId: string) => {
  const res = await rejectDefect(defectId, {
    reason: '门急诊病历证据不足，需补充说明',
    suggestion: '请补充缺陷定位证据后重新提交',
  })
  if (res.success) {
    message.success('已标记审核存疑')
    handleRefresh()
    return
  }
  message.error(res.message || '操作失败')
}

const handleAssignRemediationForDefect = async (defectId: string) => {
  void defectId
  message.warning(remediationAssignmentHint)
}

const handleRecordUrge = async (record: AdminRecordItem) => {
  const defectIds = await queryDefectIdsForRecord(record)
  if (!defectIds.length) {
    message.warning('该病历暂无可催办缺陷')
    return
  }
  const res = await batchDefectAction({
    defect_ids: defectIds,
    action: 'urge',
    message: '请尽快完成门急诊病历整改',
  })
  if (res.success) {
    message.success(`已催办 ${defectIds.length} 条缺陷`)
    handleRefresh()
    return
  }
  message.error(res.message || '催办失败')
}

const handleRecordApprove = async (record: AdminRecordItem) => {
  const defectIds = await queryDefectIdsForRecord(record)
  if (!defectIds.length) {
    message.warning('该病历暂无可审核缺陷')
    return
  }
  const res = await batchDefectAction({
    defect_ids: defectIds,
    action: 'approve',
    message: '门急诊病历批量审核通过',
  })
  if (res.success) {
    message.success(`已通过 ${defectIds.length} 条缺陷`)
    handleRefresh()
    return
  }
  message.error(res.message || '批量通过失败')
}

const openFirstSelectedDetail = async () => {
  if (!selectedRecords.value.length) {
    return
  }
  await openDetail(selectedRecords.value[0])
}

const handleBatchUrge = async () => {
  const defectIds = await queryDefectIdsForSelectedRecords()
  if (!defectIds.length) {
    message.warning('所选病历暂无可催办缺陷')
    return
  }
  const res = await batchDefectAction({
    defect_ids: defectIds,
    action: 'urge',
    message: '请尽快完成门急诊病历整改',
  })
  if (res.success) {
    message.success(`批量催办成功，共 ${defectIds.length} 条缺陷`)
    selectedRowKeys.value = []
    handleRefresh()
    return
  }
  message.error(res.message || '批量催办失败')
}

const handleBatchApprove = async () => {
  const defectIds = await queryDefectIdsForSelectedRecords()
  if (!defectIds.length) {
    message.warning('所选病历暂无可审核缺陷')
    return
  }
  const res = await batchDefectAction({
    defect_ids: defectIds,
    action: 'approve',
    message: '门急诊病历批量审核通过',
  })
  if (res.success) {
    message.success(`批量通过成功，共 ${defectIds.length} 条缺陷`)
    selectedRowKeys.value = []
    handleRefresh()
    return
  }
  message.error(res.message || '批量通过失败')
}

const handleBatchAssignRemediation = async () => {
  message.warning(remediationAssignmentHint)
}

const handleExportDefects = async () => {
  const res = await exportDefects({
    department: selectedDepartment.value,
    status: selectedStatus.value,
    start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
    end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
  })
  if (res.success) {
    message.success('缺陷导出成功')
    return
  }
  message.error(res.message || '缺陷导出失败')
}

const handleTableChange = (pag: { current?: number; pageSize?: number }) => {
  pagination.value.current = pag.current || pagination.value.current
  pagination.value.pageSize = pag.pageSize || pagination.value.pageSize
  fetchRecords()
}

watch([selectedDepartment, selectedStatus, dateRange], () => {
  pagination.value.current = 1
  fetchRecords()
  loadOverview()
})

onMounted(() => {
  loadDepartments()
  loadOverview()
  fetchRecords()
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

.apple-metric-value {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 24px;
  font-weight: 700;
  line-height: 31px;
}

.apple-primary {
  color: #0066cc;
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
  border-color: rgba(0, 102, 204, 0.24) !important;
  color: #0066cc !important;
}

:deep(.ant-btn-primary) {
  border-color: #0066cc !important;
  background: #0066cc !important;
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.18) !important;
}

:deep(.ant-btn-link) {
  color: #0066cc;
}

:deep(.ant-input:hover),
:deep(.ant-input:focus),
:deep(.ant-picker:hover),
:deep(.ant-picker-focused) {
  border-color: rgba(0, 102, 204, 0.32) !important;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08) !important;
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
  border-color: rgba(0, 102, 204, 0.32) !important;
  box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.08) !important;
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
  color: #0066cc;
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.08);
}

:deep(.ant-pagination-item-active) {
  border-color: #0066cc;
}

:deep(.ant-pagination-item-active a) {
  color: #0066cc;
}
</style>
