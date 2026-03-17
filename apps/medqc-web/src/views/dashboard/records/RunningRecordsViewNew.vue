<template>
  <div class="running-records-page min-h-screen bg-slate-50/50 p-6">
    <!-- 任务进度条（创建任务后显示） -->
    <transition name="slide-down">
      <div v-if="taskProgress" class="bg-white rounded-2xl p-4 border border-blue-100 shadow-sm mb-4">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <ThunderboltOutlined class="text-blue-500" />
            <span class="text-sm font-medium text-slate-700">{{ taskProgress.task_name || '质控任务执行中' }}</span>
          </div>
          <span class="text-xs text-slate-400">
            {{ taskProgress.completed_records }}/{{ taskProgress.total_records }} 条
          </span>
        </div>
        <a-progress
          :percent="Math.round(taskProgress.progress_pct || 0)"
          :status="taskProgress.progress_pct >= 100 ? 'success' : 'active'"
          :stroke-color="{ from: '#3b82f6', to: '#10b981' }"
        />
        <div v-if="taskProgress.progress_pct >= 100" class="flex items-center gap-4 mt-2 text-xs text-slate-500">
          <span>平均分: <b class="text-slate-700">{{ taskProgress.avg_score?.toFixed(1) || '-' }}</b></span>
          <span>缺陷数: <b class="text-slate-700">{{ taskProgress.total_defects || 0 }}</b></span>
          <a-button size="small" type="link" @click="handleCloseProgress">关闭</a-button>
        </div>
      </div>
    </transition>
    <!-- 1. 顶部 KPI 概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">今日待审核</div>
          <div class="text-2xl font-bold text-slate-800 font-mono">{{ overviewStats.pending_count || 0 }}</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <ClockCircleOutlined class="text-lg" />
        </div>
      </div>
      
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">高风险病历</div>
          <div class="text-2xl font-bold text-rose-600 font-mono">{{ overviewStats.defects_by_severity?.critical || 0 }}</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <AlertOutlined class="text-lg" />
        </div>
      </div>

      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">审核通过率</div>
          <div class="text-2xl font-bold text-emerald-600 font-mono">{{ overviewStats.pass_rate?.toFixed?.(1) || '0.0' }}%</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <CheckCircleOutlined class="text-lg" />
        </div>
      </div>

      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">总缺陷数</div>
          <div class="text-2xl font-bold text-indigo-600 font-mono">{{ overviewStats.total_defects || 0 }}</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <ThunderboltOutlined class="text-lg" />
        </div>
      </div>
    </div>

    <!-- 2. 主内容区：工具栏 + 表格 -->
    <div class="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[calc(100vh-180px)]">
      
      <!-- 工具栏 Header -->
      <div class="px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <!-- 左侧：搜索与筛选 -->
        <div class="flex items-center gap-3 flex-1">
          <div class="relative">
             <a-input
              v-model:value="queryConditions.searchValue"
              placeholder="搜索病案号/姓名/医生..."
              class="w-64 !rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400 focus:!border-blue-500 !pl-10"
              @press-enter="handleQuery"
            >
            </a-input>
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>
          
          <a-select
            v-model:value="queryConditions.timeRange"
            class="w-32 custom-select"
            placeholder="时间周期"
            :bordered="false"
          >
             <a-select-option value="all">全部时间</a-select-option>
             <a-select-option value="recent7">近7日</a-select-option>
             <a-select-option value="month">本月</a-select-option>
          </a-select>

          <a-select
            v-model:value="queryConditions.status"
            class="w-32 custom-select"
            placeholder="审核状态"
            :bordered="false"
          >
             <a-select-option value="all">全部状态</a-select-option>
             <a-select-option value="pending">待审核</a-select-option>
             <a-select-option value="reviewing">审核中</a-select-option>
          </a-select>
          
          <div class="h-6 w-px bg-slate-200 mx-1"></div>

          <a-button type="text" class="text-slate-500 hover:text-blue-600 !flex items-center gap-1" @click="showFilterModal = true">
            <FilterOutlined /> 筛选
          </a-button>
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="flex items-center gap-3">
           <div class="flex bg-slate-100 p-1 rounded-lg">
              <button 
                @click="currentView = 'records'"
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="currentView === 'records' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              >
                <FileTextOutlined class="mr-1" />列表
              </button>
              <button 
                @click="currentView = 'defects'"
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="currentView === 'defects' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              >
                <ExclamationCircleOutlined class="mr-1" />缺陷
              </button>
              <button 
                @click="currentView = 'remediation'"
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="currentView === 'remediation' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              >
                <CheckCircleOutlined class="mr-1" />整改
              </button>
           </div>

           <a-button type="primary" class="bg-blue-600 hover:bg-blue-500 border-none shadow-md shadow-blue-500/20 !rounded-xl !flex items-center gap-1 !h-9" @click="showCreateTaskModal = true">
             <PlusOutlined /> 新建任务
           </a-button>
           
           <a-tooltip title="刷新数据">
             <a-button class="!rounded-xl !border-slate-200 text-slate-500 hover:text-blue-600 !h-9 !w-9 !p-0 flex items-center justify-center" @click="handleRefresh">
               <ReloadOutlined :spin="loading" />
             </a-button>
           </a-tooltip>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="flex-1 overflow-hidden px-6 py-2">
        <a-table
          :columns="currentColumns"
          :data-source="tableDataSource"
          :loading="loading"
          :pagination="pagination"
          :row-selection="rowSelection"
          @change="handleTableChange"
          row-key="id"
          class="modern-table h-full"
          :scroll="{ y: 'calc(100vh - 320px)' }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'caseInfo'">
              <div class="flex flex-col">
                <div class="flex items-center gap-2">
                   <span class="font-mono font-bold text-slate-700 text-sm group-hover:text-blue-600 transition-colors cursor-pointer" @click="handleViewDetail(record)">{{ record.record_id || record.caseNo }}</span>
                   <a-tag v-if="record.isUrgent" color="error" class="!rounded-md !text-[10px] !px-1 !mr-0">急</a-tag>
                </div>
                <div class="text-xs text-slate-400 mt-0.5">{{ record.registrationNo }}</div>
              </div>
            </template>
            
            <template v-if="column.key === 'patientInfo'">
               <div class="flex items-center gap-2">
                 <div class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600 border border-slate-200">
                   {{ (record.patient_name || record.patientName || '').charAt(0) }}
                 </div>
                 <div>
                   <div class="text-sm font-medium text-slate-700">{{ record.patient_name || record.patientName }}</div>
                   <div class="text-xs text-slate-400">{{ record.patientAge }}岁 / {{ record.patientGender }}</div>
                 </div>
               </div>
            </template>

            <template v-if="column.key === 'doctorInfo'">
              <div class="text-sm text-slate-700">{{ record.doctorName }}</div>
              <div class="text-xs text-slate-400">{{ record.department }}</div>
            </template>

            <template v-if="column.key === 'auditStatus'">
              <span 
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-amber-50 text-amber-600 border-amber-100': getStatusField(record) === 'pending',
                  'bg-blue-50 text-blue-600 border-blue-100': getStatusField(record) === 'reviewing' || getStatusField(record) === 'urged',
                  'bg-emerald-50 text-emerald-600 border-emerald-100': getStatusField(record) === 'approved',
                  'bg-rose-50 text-rose-600 border-rose-100': getStatusField(record) === 'rejected',
                  'bg-slate-100 text-slate-600 border-slate-200': getStatusField(record) === 'remediated'
                }"
              >
                <span class="w-1.5 h-1.5 rounded-full" :class="{
                  'bg-amber-500': getStatusField(record) === 'pending',
                  'bg-blue-500': getStatusField(record) === 'reviewing' || getStatusField(record) === 'urged',
                  'bg-emerald-500': getStatusField(record) === 'approved',
                  'bg-rose-500': getStatusField(record) === 'rejected',
                  'bg-slate-400': getStatusField(record) === 'remediated'
                }"></span>
                {{ getAuditStatusText(getStatusField(record)) }}
              </span>
            </template>
            
            <template v-if="column.key === 'score'">
               <div class="flex items-center gap-2">
                 <span class="font-mono font-bold text-slate-700">{{ record.score || '-' }}</span>
                 <a-progress 
                   :percent="record.score" 
                   :show-info="false" 
                   :stroke-color="getScoreColor(record.score)" 
                   size="small" 
                   class="w-16"
                 />
               </div>
            </template>

            <template v-if="column.key === 'action'">
              <div class="flex items-center gap-1">
                <a-tooltip title="查看详情">
                  <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-blue-600 transition-all" @click="handleViewDetail(record)">
                    <EyeOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="催办" v-if="getStatusField(record) === 'pending'">
                  <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-amber-50 hover:text-amber-600 transition-all" @click="handleUrgeRecord(record)">
                    <SendOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="更多操作">
                   <a-dropdown>
                      <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-all">
                        <MoreOutlined />
                      </button>
                      <template #overlay>
                        <a-menu>
                          <a-menu-item key="1"><FilePdfOutlined /> 导出报告</a-menu-item>
                          <a-menu-item key="2" class="!text-rose-500"><DeleteOutlined /> 删除记录</a-menu-item>
                        </a-menu>
                      </template>
                   </a-dropdown>
                </a-tooltip>
              </div>
            </template>
          </template>
        </a-table>
      </div>

      <!-- 整改闭环视图 -->
      <div v-if="currentView === 'remediation'" class="flex-1 overflow-hidden px-6 py-2">
        <RemediationPanel />
      </div>
      
      <!-- 底部批量操作栏 (有选中时显示) -->
      <transition name="slide-up">
        <div v-if="selectedRowKeys.length > 0" class="absolute bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-6 py-3 rounded-full shadow-xl flex items-center gap-6 z-50">
           <span class="text-sm font-medium">已选择 <span class="text-blue-400 font-bold mx-1">{{ selectedRowKeys.length }}</span> 项</span>
           <div class="h-4 w-px bg-slate-600"></div>
           <div class="flex items-center gap-2">
             <button class="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium transition-colors flex items-center gap-2" @click="handleBatchUrge">
               <SendOutlined /> 批量催办
             </button>
             <button class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium transition-colors flex items-center gap-2" @click="handleBatchPass">
               <CheckOutlined /> 批量通过
             </button>
             <button class="w-8 h-8 rounded-full bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors ml-2" @click="selectedRowKeys = []">
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

    <!-- 新建质控任务弹窗 -->
    <CreateTaskModal
      :visible="showCreateTaskModal"
      @update:visible="showCreateTaskModal = $event"
      @created="handleTaskCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  ReloadOutlined,
  FilterOutlined,
  PlusOutlined,
  ClockCircleOutlined,
  AlertOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  ExclamationCircleOutlined,
  EyeOutlined,
  SendOutlined,
  MoreOutlined,
  FilePdfOutlined,
  DeleteOutlined,
  CheckOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'
import {
  getAdminRecordList,
  getAdminOverview,
  getDefectList,
  batchDefectAction,
  urgeDefect,
  approveDefect,
  batchCreateQCTask,
  type AdminRecordItem,
  type AdminOverviewStats,
  type DefectItem,
} from '@/api/qcAdmin'
import QCReviewDrawer from '@/components/qc/QCReviewDrawer.vue'
import CreateTaskModal from '@/components/qc/CreateTaskModal.vue'
import RemediationPanel from '@/components/qc/RemediationPanel.vue'
import {
  fetchTaskProgress,
  batchCreateRemediation,
  exportDefectsDownload,
  type TaskProgressData,
} from '@/api/qcAdmin'

// ============= 响应式数据 =============
const loading = ref(false)
const showFilterModal = ref(false)
const showCreateTaskModal = ref(false)
const currentView = ref('records')
const drawerVisible = ref(false)
const drawerRecord = ref<any>(null)
const taskProgress = ref<TaskProgressData | null>(null)
let progressTimer: ReturnType<typeof setInterval> | null = null
let pollFailCount = 0
const MAX_POLL_FAILURES = 5
const selectedRowKeys = ref<string[]>([])

// 查询条件
const queryConditions = reactive({
  timeRange: 'recent7',
  status: undefined as string | undefined,
  searchValue: ''
})

// KPI 统计
const overviewStats = ref<AdminOverviewStats>({
  total_records: 0,
  archived_count: 0,
  pending_count: 0,
  pass_rate: 0,
  total_defects: 0,
  defects_by_severity: {},
})

// 表格数据
const records = ref<any[]>([])

// 缺陷列表数据（缺陷 Tab 用）
const defects = ref<DefectItem[]>([])

// 表格列配置 — 病历视图
const recordColumns = [
  { title: '病案信息', key: 'caseInfo', width: 140 },
  { title: '患者', key: 'patientInfo', width: 180 },
  { title: '科室/医生', key: 'doctorInfo', width: 160 },
  { title: '状态', key: 'auditStatus', width: 120 },
  { title: '质控评分', key: 'score', width: 160 },
  { title: '操作', key: 'action', width: 140, align: 'right' as const }
]

// 表格列配置 — 缺陷视图
const defectColumns = [
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 200 },
  { title: '病案号', dataIndex: 'record_id', key: 'record_id', width: 140 },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
  { title: '状态', key: 'auditStatus', width: 120 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: 140, align: 'right' as const }
]

// 根据当前 Tab 返回列配置
const currentColumns = computed(() =>
  currentView.value === 'defects' ? defectColumns : recordColumns
)

// 根据当前 Tab 返回数据源
const tableDataSource = computed(() =>
  currentView.value === 'defects' ? defects.value : records.value
)

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`
})

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}))

// ============= 数据加载 =============

/** 加载 KPI 概览 */
const loadOverview = async () => {
  const res = await getAdminOverview()
  if (res.success && res.data) {
    overviewStats.value = res.data
  }
}

/** 加载病历列表 */
const fetchRecords = async () => {
  loading.value = true
  try {
    if (currentView.value === 'defects') {
      // 缺陷视图 — 调用缺陷列表 API
      const res = await getDefectList({
        status: queryConditions.status !== 'all' ? queryConditions.status : undefined,
        keyword: queryConditions.searchValue || undefined,
        page: pagination.current,
        page_size: pagination.pageSize,
      })
      if (res.success && res.data) {
        defects.value = (res.data as any).items || []
        pagination.total = (res.data as any).total || 0
      }
    } else {
      // 病历列表视图
      const res = await getAdminRecordList({
        status: queryConditions.status !== 'all' ? queryConditions.status : undefined,
        keyword: queryConditions.searchValue || undefined,
        page: pagination.current,
        page_size: pagination.pageSize,
      })
      if (res.success && res.data) {
        records.value = res.data.items || []
        pagination.total = res.data.total || 0
      } else {
        // API 未就绪时 mock 兜底
        records.value = [
          { id: '1', record_id: 'C2024001', registrationNo: 'R2024001', patient_name: '张三', patientAge: 45, patientGender: '男', doctorName: '李医生', department: '心内科', auditStatus: 'pending', score: 85, isUrgent: true },
          { id: '2', record_id: 'C2024002', registrationNo: 'R2024002', patient_name: '李四', patientAge: 32, patientGender: '女', doctorName: '王医生', department: '消化内科', auditStatus: 'reviewing', score: 92, isUrgent: false },
          { id: '3', record_id: 'C2024003', registrationNo: 'R2024003', patient_name: '王五', patientAge: 67, patientGender: '男', doctorName: '赵医生', department: '呼吸内科', auditStatus: 'approved', score: 98, isUrgent: false },
          { id: '4', record_id: 'C2024004', registrationNo: 'R2024004', patient_name: '赵六', patientAge: 28, patientGender: '女', doctorName: '钱医生', department: '妇产科', auditStatus: 'rejected', score: 55, isUrgent: false },
          { id: '5', record_id: 'C2024005', registrationNo: 'R2024005', patient_name: '孙七', patientAge: 55, patientGender: '男', doctorName: '孙医生', department: '骨科', auditStatus: 'pending', score: 78, isUrgent: false },
        ] as any[]
        pagination.total = 5
      }
    }
  } catch (error) {
    message.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// ============= 事件处理 =============

/** 任务创建成功后：启动进度轮询 */
const handleTaskCreated = (data: { task_id: string; task_number: string }) => {
  startProgressPolling(data.task_id)
}

/** 启动进度轮询（3 秒一次） */
const startProgressPolling = (taskId: string) => {
  stopProgressPolling()
  // 立即查询一次
  pollProgress(taskId)
  progressTimer = setInterval(() => pollProgress(taskId), 3000)
}

const pollProgress = async (taskId: string) => {
  const res = await fetchTaskProgress(taskId)
  if (res.success && res.data) {
    pollFailCount = 0
    taskProgress.value = res.data
    // 进度完成时停止轮询 + 刷新列表
    if (res.data.progress_pct >= 100) {
      stopProgressPolling()
      fetchRecords()
      loadOverview()
    }
  } else {
    // 失败计数 + 退避
    pollFailCount++
    if (pollFailCount >= MAX_POLL_FAILURES) {
      stopProgressPolling()
      message.warning('进度查询失败次数过多，已停止轮询。请手动刷新。')
    }
  }
}

/** 关闭进度条（同时停止轮询） */
const handleCloseProgress = () => {
  stopProgressPolling()
  taskProgress.value = null
}

const stopProgressPolling = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

const handleQuery = () => {
  pagination.current = 1
  fetchRecords()
}

const handleRefresh = () => {
  fetchRecords()
  loadOverview()
}

/** P1: 批量派发整改 */
const handleBatchAssign = async () => {
  if (currentView.value !== 'defects') {
    message.warning('批量派发仅在缺陷视图下可用')
    return
  }
  // 简化版：使用默认整改要求派发
  const res = await batchCreateRemediation({
    defect_ids: selectedRowKeys.value,
    assignee_id: 'default',
    assignee_name: '责任科室',
    remediation_requirement: '请尽快完成整改',
  })
  if (res.success) {
    message.success(res.message)
  } else {
    message.error(res.message || '派发失败')
  }
  selectedRowKeys.value = []
  fetchRecords()
}

/** P1: 导出缺陷报告 */
const handleExportDefects = async () => {
  message.loading('正在导出...', 1)
  const res = await exportDefectsDownload({
    status: queryConditions.status,
  })
  if (res.success) {
    message.success('导出成功')
  } else {
    message.error(res.message || '导出失败')
  }
}

const handleTableChange = (pag: any) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  fetchRecords()
}

const handleViewDetail = (record: any) => {
  drawerRecord.value = record
  drawerVisible.value = true
}

const handleUrgeRecord = async (record: any) => {
  if (currentView.value !== 'defects') {
    // 病历视图下 record.id 不是 defect_id，引导用户通过 Drawer 操作
    drawerRecord.value = record
    drawerVisible.value = true
    return
  }
  const res = await urgeDefect(record.id, { message: '请尽快完成审核' })
  if (res.success) {
    message.success(`已发送催办提醒: ${record.rule_name || record.id}`)
    fetchRecords()
  } else {
    message.error(res.message || '催办失败')
  }
}

const handleBatchUrge = async () => {
  if (currentView.value !== 'defects') {
    message.warning('批量催办仅在缺陷视图下可用')
    return
  }
  const res = await batchDefectAction({
    defect_ids: selectedRowKeys.value,
    action: 'urge',
    message: '请尽快完成审核',
  })
  if (res.success) {
    message.success(`批量催办 ${selectedRowKeys.value.length} 条记录`)
  } else {
    message.error(res.message || '批量催办失败')
  }
  selectedRowKeys.value = []
  fetchRecords()
}

const handleBatchPass = async () => {
  if (currentView.value !== 'defects') {
    message.warning('批量通过仅在缺陷视图下可用')
    return
  }
  const res = await batchDefectAction({
    defect_ids: selectedRowKeys.value,
    action: 'approve',
  })
  if (res.success) {
    message.success(`批量通过 ${selectedRowKeys.value.length} 条记录`)
  } else {
    message.error(res.message || '批量通过失败')
  }
  selectedRowKeys.value = []
  fetchRecords()
}

/** 兼容病历(auditStatus)和缺陷(status)两种数据模型的状态字段取值 */
const getStatusField = (record: any): string => {
  return record.status || record.auditStatus || 'pending'
}

const getAuditStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已驳回',
    reviewing: '审核中',
    urged: '已催办',
    remediated: '已整改',
  }
  return textMap[status] || status
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

// 视图切换时重新加载数据
watch(currentView, () => {
  pagination.current = 1
  fetchRecords()
})

onMounted(() => {
  loadOverview()
  fetchRecords()
})

onUnmounted(() => {
  stopProgressPolling()
})
</script>

<style scoped>
/* 胶囊选择器样式覆盖 */
:deep(.custom-select .ant-select-selector) {
  background-color: #f8fafc !important;
  border-radius: 10px !important;
  border: 1px solid #e2e8f0 !important;
  height: 34px !important;
  display: flex;
  align-items: center;
  transition: all 0.2s;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: #60a5fa !important; /* blue-400 */
  background-color: #ffffff !important;
}

:deep(.custom-select .ant-select-selection-placeholder) {
  color: #94a3b8;
  font-size: 13px;
}

:deep(.custom-select .ant-select-selection-item) {
  color: #475569;
  font-size: 13px;
  font-weight: 500;
}

/* 现代表格样式 */
.modern-table :deep(.ant-table-thead > tr > th) {
  background: transparent;
  border-bottom: 1px solid #f1f5f9;
  color: #64748b;
  font-weight: 600;
  font-size: 13px;
  padding: 12px 16px;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 16px 16px;
  border-bottom: 1px solid #f8fafc;
  transition: background-color 0.2s;
}

.modern-table :deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc !important;
}

/* 分页样式微调 */
.modern-table :deep(.ant-pagination) {
  margin: 16px 0;
}

/* 动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 20px);
}
</style>
