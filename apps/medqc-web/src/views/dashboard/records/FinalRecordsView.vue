<template>
  <div class="final-records-page min-h-screen bg-slate-50/50 p-6">
    <!-- 1. 顶部 KPI 概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div
        class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all"
      >
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">
            总病历数
          </div>
          <div class="text-2xl font-bold text-blue-600 font-mono">
            {{ formatInteger(overviewStats.total_records) }}
          </div>
        </div>
        <div
          class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center group-hover:scale-110 transition-transform"
        >
          <FileTextOutlined class="text-lg" />
        </div>
      </div>

      <div
        class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all"
      >
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">
            已归档
          </div>
          <div class="text-2xl font-bold text-emerald-600 font-mono">
            {{ formatInteger(overviewStats.archived_count) }}
          </div>
        </div>
        <div
          class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-110 transition-transform"
        >
          <CheckCircleOutlined class="text-lg" />
        </div>
      </div>

      <div
        class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all"
      >
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">
            待处理
          </div>
          <div class="text-2xl font-bold text-amber-600 font-mono">
            {{ formatInteger(overviewStats.pending_count) }}
          </div>
        </div>
        <div
          class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center group-hover:scale-110 transition-transform"
        >
          <ClockCircleOutlined class="text-lg" />
        </div>
      </div>

      <div
        class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all"
      >
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">
            质控通过率
          </div>
          <div class="text-2xl font-bold text-purple-600 font-mono">
            {{ formatRate(overviewStats.pass_rate) }}%
          </div>
        </div>
        <div
          class="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center group-hover:scale-110 transition-transform"
        >
          <TrophyOutlined class="text-lg" />
        </div>
      </div>
    </div>

    <!-- 2. 主内容区：工具栏 + 表格 -->
    <div
      class="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[calc(100vh-180px)]"
    >
      <!-- 工具栏 Header -->
      <div
        class="px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4"
      >
        <!-- 左侧：搜索与筛选 -->
        <div class="flex items-center gap-3 flex-1">
          <div class="relative">
            <a-input
              v-model:value="searchKeyword"
              placeholder="搜索病历号/姓名..."
              class="w-64 !rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400 focus:!border-blue-500 !pl-10"
              @press-enter="handleSearch"
            />
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          <a-select
            v-model:value="selectedDepartment"
            class="w-32 custom-select"
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
            v-model:value="selectedQCStatus"
            class="w-32 custom-select"
            placeholder="质控状态"
            :bordered="false"
            allow-clear
          >
            <a-select-option
              v-for="status in qcStatusOptions"
              :key="status.value"
              :value="status.value"
            >
              {{ status.label }}
            </a-select-option>
          </a-select>

          <div class="h-6 w-px bg-slate-200 mx-1" />

          <a-range-picker
            v-model:value="dateRange"
            class="!rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400"
            :bordered="false"
          />
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="flex items-center gap-3">
          <a-button
            type="primary"
            class="bg-blue-600 hover:bg-blue-500 border-none shadow-md shadow-blue-500/20 !rounded-xl !flex items-center gap-1 !h-9"
            @click="handleBatchArchive"
          >
            <FolderOutlined /> 批量归档
          </a-button>

          <a-button
            class="!rounded-xl !border-slate-200 text-slate-600 hover:text-blue-600 !h-9 !flex items-center gap-1"
            @click="handleExport"
          >
            <DownloadOutlined /> 导出
          </a-button>

          <a-tooltip title="刷新数据">
            <a-button
              class="!rounded-xl !border-slate-200 text-slate-500 hover:text-blue-600 !h-9 !w-9 !p-0 flex items-center justify-center"
              @click="handleRefresh"
            >
              <ReloadOutlined :spin="loading" />
            </a-button>
          </a-tooltip>
        </div>
      </div>

      <div
        v-if="stageHint"
        class="px-6 py-2 text-xs text-blue-700 bg-blue-50/70 border-b border-blue-100"
      >
        {{ stageHint }}
      </div>

      <!-- 表格区域 -->
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
              <div
                class="font-mono font-bold text-slate-700 text-sm group-hover:text-blue-600 transition-colors cursor-pointer"
                @click="handleView(record as AdminRecordItem)"
              >
                {{ record.record_id }}
              </div>
            </template>

            <template v-if="column.key === 'patientInfo'">
              <div class="flex items-center gap-2">
                <div
                  class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600 border border-slate-200"
                >
                  {{ (record.patient_name || '').charAt(0) }}
                </div>
                <div class="text-sm font-medium text-slate-700">
                  {{ record.patient_name }}
                </div>
              </div>
            </template>

            <template v-if="column.key === 'qcStatus'">
              <span
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-emerald-50 text-emerald-600 border-emerald-100':
                    record.status === 'completed' || record.status === 'passed',
                  'bg-rose-50 text-rose-600 border-rose-100': record.status === 'failed',
                  'bg-amber-50 text-amber-600 border-amber-100': record.status === 'pending',
                }"
              >
                <span
                  class="w-1.5 h-1.5 rounded-full"
                  :class="{
                    'bg-emerald-500': record.status === 'completed' || record.status === 'passed',
                    'bg-rose-500': record.status === 'failed',
                    'bg-amber-500': record.status === 'pending',
                  }"
                />
                {{ getQCStatusText(record.status) }}
              </span>
            </template>

            <template v-if="column.key === 'defectCount'">
              <span
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-slate-100 text-slate-600 border-slate-200': record.defect_count === 0,
                  'bg-amber-50 text-amber-600 border-amber-100':
                    record.defect_count > 0 && record.defect_count <= 3,
                  'bg-rose-50 text-rose-600 border-rose-100': record.defect_count > 3,
                }"
              >
                {{ record.defect_count || 0 }}
              </span>
            </template>

            <template v-if="column.key === 'qcScore'">
              <div class="flex items-center gap-2">
                <span class="font-mono font-bold text-slate-700">{{ record.score || '-' }}</span>
                <a-progress
                  v-if="record.score"
                  :percent="record.score"
                  :show-info="false"
                  :stroke-color="getScoreColor(record.score)"
                  size="small"
                  class="w-16"
                />
              </div>
            </template>

            <template v-if="column.key === 'stageActions'">
              <div class="flex flex-wrap gap-1.5">
                <a-button
                  size="small"
                  class="!h-7 !rounded-full !border-slate-200/90 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="jumpToWorkstation(record, 'open_record')"
                >
                  进入工作台
                </a-button>
                <a-button
                  size="small"
                  class="!h-7 !rounded-full !border-blue-200/90 !text-blue-700 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="jumpToWorkstation(record, 'generate_frontpage')"
                >
                  生成首页
                </a-button>
                <a-button
                  size="small"
                  class="!h-7 !rounded-full !border-emerald-200/90 !text-emerald-700 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="jumpToWorkstation(record, 'qc_frontpage')"
                >
                  首页质控
                </a-button>
                <a-button
                  size="small"
                  class="!h-7 !rounded-full !border-violet-200/90 !text-violet-700 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="jumpToWorkstation(record, 'qc_settlement')"
                >
                  结算质控
                </a-button>
              </div>
            </template>

            <template v-if="column.key === 'action'">
              <div class="flex items-center gap-1">
                <a-tooltip title="查看详情">
                  <button
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-blue-600 transition-all"
                    @click="handleView(record as AdminRecordItem)"
                  >
                    <EyeOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="质控报告">
                  <button
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-blue-50 hover:text-blue-600 transition-all"
                    @click="handleQCReport(record as AdminRecordItem)"
                  >
                    <FileSearchOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip
                  v-if="record.status === 'pending'"
                  title="归档"
                >
                  <button
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-emerald-50 hover:text-emerald-600 transition-all"
                    @click="handleArchive(record as AdminRecordItem)"
                  >
                    <FolderOutlined />
                  </button>
                </a-tooltip>
              </div>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 底部批量操作栏 (有选中时显示) -->
      <transition name="slide-up">
        <div
          v-if="selectedRowKeys.length > 0"
          class="absolute bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-6 py-3 rounded-full shadow-xl flex items-center gap-6 z-50"
        >
          <span class="text-sm font-medium">已选择
            <span class="text-blue-400 font-bold mx-1">{{ selectedRowKeys.length }}</span> 项</span>
          <div class="h-4 w-px bg-slate-600" />
          <div class="flex items-center gap-2">
            <button
              class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium transition-colors flex items-center gap-2"
              @click="handleBatchArchive"
            >
              <FolderOutlined /> 批量归档
            </button>
            <button
              class="w-8 h-8 rounded-full bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors ml-2"
              @click="selectedRowKeys = []"
            >
              <CloseOutlined />
            </button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 联审详情抽屉 -->
    <QCReviewDrawer
      :visible="drawerVisible"
      :record="drawerRecord"
      @update:visible="drawerVisible = $event"
      @close="drawerVisible = false"
      @refresh="fetchRecords"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import {
  SearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileSearchOutlined,
  FolderOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  TrophyOutlined,
  CloseOutlined,
} from '@ant-design/icons-vue'
import {
  getAdminRecordList,
  getAdminOverview,
  getDepartmentList,
  exportDefects,
  batchDefectAction,
  type AdminRecordItem,
  type AdminOverviewStats,
} from '@/api/qcAdmin'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'

const route = useRoute()
const router = useRouter()

// ============= 响应式数据 =============
const loading = ref(false)
const searchKeyword = ref('')
const selectedDepartment = ref<string | undefined>(undefined)
const selectedQCStatus = ref<string | undefined>(undefined)
type DateRange = [Dayjs, Dayjs] | null
const dateRange = ref<DateRange>(null)
const records = ref<AdminRecordItem[]>([])
const selectedRowKeys = ref<string[]>([])
const drawerVisible = ref(false)
const drawerRecord = ref<AdminRecordItem | null>(null)

// KPI 卡片数据
const overviewStats = ref<AdminOverviewStats>({
  total_records: 0,
  archived_count: 0,
  pending_count: 0,
  pass_rate: 0,
  total_defects: 0,
  defects_by_severity: {},
})

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
})

// 行选择配置
const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
}))

// 科室选项 — 动态加载
const departmentOptions = ref<Array<{ value: string; label: string }>>([])

// 质控状态选项
const qcStatusOptions = [
  { value: 'passed', label: '通过' },
  { value: 'failed', label: '未通过' },
  { value: 'pending', label: '待质控' },
]

// 表格列配置 — 增加缺陷数列
const columns: TableColumnsType<AdminRecordItem> = [
  {
    title: '病历号',
    dataIndex: 'record_id',
    key: 'recordNumber',
    width: 120,
  },
  {
    title: '患者信息',
    key: 'patientInfo',
    width: 150,
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 120,
  },
  {
    title: '出院日期',
    dataIndex: 'discharge_date',
    key: 'dischargeDate',
    width: 120,
  },
  {
    title: '质控状态',
    dataIndex: 'status',
    key: 'qcStatus',
    width: 120,
  },
  {
    title: '缺陷数',
    dataIndex: 'defect_count',
    key: 'defectCount',
    width: 100,
    sorter: true,
  },
  {
    title: '质控得分',
    dataIndex: 'score',
    key: 'qcScore',
    width: 150,
    sorter: true,
  },
  {
    title: '阶段动作',
    key: 'stageActions',
    width: 300,
  },
  {
    title: '操作',
    key: 'action',
    width: 140,
    fixed: 'right' as const,
  },
]

const getQCStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    passed: '通过',
    completed: '通过',
    failed: '未通过',
    pending: '待质控',
  }
  return textMap[status] || status
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#10b981' // emerald-500
  if (score >= 80) return '#3b82f6' // blue-500
  if (score >= 60) return '#f59e0b' // amber-500
  return '#f43f5e' // rose-500
}

const toNumber = (value: unknown): number => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const formatInteger = (value: unknown): string => {
  return Math.trunc(toNumber(value)).toLocaleString()
}

const formatRate = (value: unknown): string => {
  return toNumber(value).toFixed(1)
}

// ============= 数据加载 =============

/** 加载科室列表 */
const loadDepartments = async () => {
  const res = await getDepartmentList()
  if (res.success && res.data) {
    departmentOptions.value = res.data.map((d) => ({ value: d.code || d.name, label: d.name }))
  }
}

/** 加载 KPI 概览 */
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

/** 加载病历列表 */
const fetchRecords = async () => {
  loading.value = true
  try {
    const res = await getAdminRecordList({
      department: selectedDepartment.value,
      status: selectedQCStatus.value,
      keyword: searchKeyword.value || undefined,
      start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
      end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
      page: pagination.value.current,
      page_size: pagination.value.pageSize,
    })
    if (res.success && res.data) {
      records.value = res.data.items || []
      pagination.value.total = res.data.total || 0
    } else {
      // API 未就绪时使用 mock 数据兜底
      records.value = [
        {
          id: '1',
          task_id: '',
          record_id: 'F2024001',
          patient_name: '王五',
          department: '内科',
          discharge_date: '2024-01-10',
          status: 'completed',
          defect_count: 2,
          score: 95,
          created_at: '',
        },
        {
          id: '2',
          task_id: '',
          record_id: 'F2024002',
          patient_name: '赵六',
          department: '外科',
          discharge_date: '2024-01-12',
          status: 'failed',
          defect_count: 5,
          score: 72,
          created_at: '',
        },
        {
          id: '3',
          task_id: '',
          record_id: 'F2024003',
          patient_name: '李四',
          department: '儿科',
          discharge_date: '2024-01-15',
          status: 'completed',
          defect_count: 1,
          score: 88,
          created_at: '',
        },
        {
          id: '4',
          task_id: '',
          record_id: 'F2024004',
          patient_name: '张三',
          department: '内科',
          discharge_date: '2024-01-18',
          status: 'pending',
          defect_count: 0,
          score: undefined,
          created_at: '',
        },
      ] as any[]
      pagination.value.total = 4
    }
  } catch (error) {
    message.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// ============= 事件处理 =============

const handleSearch = () => {
  pagination.value.current = 1
  fetchRecords()
}

const handleRefresh = () => {
  fetchRecords()
  loadOverview()
}

const handleBatchArchive = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要操作的病历')
    return
  }
  // TODO: 对接批量归档 API
  message.success(`批量归档 ${selectedRowKeys.value.length} 条病历成功`)
  selectedRowKeys.value = []
}

const handleExport = async () => {
  message.loading('正在导出...', 1)
  const res = await exportDefects({
    department: selectedDepartment.value,
    start_date: dateRange.value?.[0]?.format?.('YYYY-MM-DD'),
    end_date: dateRange.value?.[1]?.format?.('YYYY-MM-DD'),
  })
  if (res.success) {
    message.success('导出成功')
  } else {
    message.error(res.message || '导出失败')
  }
}

const handleView = (record: AdminRecordItem) => {
  drawerRecord.value = record
  drawerVisible.value = true
}

const getRecordIdForJump = (record: any): string => {
  return String(record?.record_id || record?.visit_id || record?.visitId || record?.id || '').trim()
}

const resolveStageByAction = (action: WorkstationLaunchAction): WorkflowStageKey => {
  if (action === 'generate_frontpage') return 'frontpage_generate'
  if (action === 'qc_frontpage') return 'frontpage_qc'
  if (action === 'qc_settlement') return 'settlement_qc'
  const stageFromQuery = String(route.query.stage || '').trim()
  if (
    stageFromQuery === 'frontpage_generate' ||
    stageFromQuery === 'frontpage_qc' ||
    stageFromQuery === 'settlement_qc'
  ) {
    return stageFromQuery
  }
  return 'settlement_qc'
}

const jumpToWorkstation = (record: any, action: WorkstationLaunchAction) => {
  const recordId = getRecordIdForJump(record)
  if (!recordId) {
    message.warning('当前记录缺少病历标识，无法联动工作台')
    return
  }
  const taskId = String(record?.task_id || '').trim()
  const fromStage = resolveStageByAction(action)
  const query: Record<string, string> = {
    record_id: recordId,
    action,
    source: 'dashboard',
    from_stage: fromStage,
  }
  if (taskId) query.task_id = taskId
  router.push({ path: '/workstation-v4', query })
}

const handleQCReport = (record: AdminRecordItem) => {
  // TODO: 导航到质控报告页
  message.info(`查看质控报告: ${record.record_id}`)
}

const handleArchive = (record: AdminRecordItem) => {
  // TODO: 对接单条归档 API
  message.success(`归档成功: ${record.record_id}`)
}

const handleTableChange = (pag: any) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  fetchRecords()
}

const stageHint = computed(() => {
  const stage = String(route.query.stage || '').trim()
  if (stage === 'frontpage_generate') return '当前队列：待生成首页（结算视图）'
  if (stage === 'frontpage_qc') return '当前队列：待首页质控（结算视图）'
  if (stage === 'settlement_qc') return '当前队列：待结算清单质控'
  return ''
})

const applyStagePreset = (stage: string) => {
  if (stage === 'frontpage_generate') {
    selectedQCStatus.value = 'pending'
    return
  }
  if (stage === 'frontpage_qc') {
    selectedQCStatus.value = 'failed'
    return
  }
  if (stage === 'settlement_qc') {
    selectedQCStatus.value = 'pending'
  }
}

// 筛选条件变化时自动刷新
watch([selectedDepartment, selectedQCStatus, dateRange], () => {
  pagination.value.current = 1
  fetchRecords()
  loadOverview()
})

watch(
  () => route.query.stage,
  (value) => {
    applyStagePreset(String(value || '').trim())
  },
  { immediate: true },
)

onMounted(() => {
  loadDepartments()
  loadOverview()
  fetchRecords()
})
</script>

<style scoped>
/* 自定义下拉框样式 */
:deep(.custom-select .ant-select-selector) {
  background-color: #f8fafc !important; /* slate-50 */
  border-radius: 0.75rem !important; /* rounded-xl */
  border: 1px solid #e2e8f0 !important; /* slate-200 */
  height: 36px !important;
  display: flex;
  align-items: center;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: #60a5fa !important; /* blue-400 */
}

:deep(.custom-select .ant-select-selection-placeholder) {
  line-height: 34px !important;
  color: #94a3b8 !important; /* slate-400 */
}

:deep(.custom-select .ant-select-selection-item) {
  line-height: 34px !important;
  color: #334155 !important; /* slate-700 */
  font-weight: 500;
}

/* 表格样式优化 */
:deep(.modern-table .ant-table) {
  background: transparent;
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

/* 分页样式 */
:deep(.ant-pagination-item) {
  border-radius: 8px;
  background: white;
}

:deep(.ant-pagination-item-active) {
  background: #2563eb;
  border-color: #2563eb;
}

:deep(.ant-pagination-item-active a) {
  color: white;
}

/* 底部批量操作栏动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translate(-50%, 100%);
  opacity: 0;
}
</style>
