<template>
  <div class="outpatient-emergency-page min-h-screen bg-slate-50/50 p-6">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm">
        <div class="text-slate-500 text-xs font-medium mb-1">
          门急诊病历总量
        </div>
        <div class="text-2xl font-bold text-blue-600 font-mono">
          {{ formatInteger(overviewStats.total_records) }}
        </div>
      </div>
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm">
        <div class="text-slate-500 text-xs font-medium mb-1">
          待处理
        </div>
        <div class="text-2xl font-bold text-amber-600 font-mono">
          {{ formatInteger(overviewStats.pending_count) }}
        </div>
      </div>
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm">
        <div class="text-slate-500 text-xs font-medium mb-1">
          缺陷总数
        </div>
        <div class="text-2xl font-bold text-rose-600 font-mono">
          {{ formatInteger(overviewStats.total_defects) }}
        </div>
      </div>
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm">
        <div class="text-slate-500 text-xs font-medium mb-1">
          通过率
        </div>
        <div class="text-2xl font-bold text-emerald-600 font-mono">
          {{ formatRate(overviewStats.pass_rate) }}%
        </div>
      </div>
    </div>

    <div class="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[calc(100vh-180px)]">
      <div class="px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div class="flex items-center gap-3 flex-1">
          <div class="relative">
            <a-input
              v-model:value="searchKeyword"
              placeholder="搜索病案号/姓名/医生..."
              class="w-64 !rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400 focus:!border-blue-500 !pl-10"
              @press-enter="handleSearch"
            />
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

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
            class="!rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400"
            :bordered="false"
          />
        </div>

        <a-tooltip title="刷新数据">
          <a-button
            class="!rounded-xl !border-slate-200 text-slate-500 hover:text-blue-600 !h-9 !w-9 !p-0 flex items-center justify-center"
            @click="handleRefresh"
          >
            <ReloadOutlined :spin="loading" />
          </a-button>
        </a-tooltip>
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
                class="font-mono font-bold text-slate-700 hover:text-blue-600"
                @click="openDetail(record)"
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
              <a-button
                type="link"
                size="small"
                class="!px-0"
                @click="openDetail(record)"
              >
                质控详情
              </a-button>
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
      @close="detailVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons-vue'
import {
  getAdminOverview,
  getDepartmentList,
  getRecordDetail,
  getOutpatientEmergencyRecordList,
  type AdminOverviewStats,
  type AdminRecordItem,
} from '@/api/qcAdmin'
import OutpatientEmergencyDetailDrawer from './OutpatientEmergencyDetailDrawer.vue'

const loading = ref(false)
const searchKeyword = ref('')
const selectedDepartment = ref<string | undefined>(undefined)
const selectedStatus = ref<string | undefined>(undefined)
const dateRange = ref<[Dayjs, Dayjs] | []>([])
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

const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
}))

const columns = [
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
:deep(.custom-select .ant-select-selector) {
  background-color: #f8fafc !important;
  border-radius: 0.75rem !important;
  border: 1px solid #e2e8f0 !important;
  height: 36px !important;
  display: flex;
  align-items: center;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: #60a5fa !important;
}

:deep(.modern-table .ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
}

:deep(.modern-table .ant-table-tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid #f8fafc;
  font-size: 13px;
}

:deep(.modern-table .ant-table-tbody > tr:hover > td) {
  background: #f8fafc;
}
</style>
