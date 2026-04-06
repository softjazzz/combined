<template>
  <div class="running-records-page min-h-screen bg-slate-50/50 p-6">
    <!-- 任务进度条（创建任务后显示） -->
    <transition name="slide-down">
      <div
        v-if="taskProgress"
        class="bg-white rounded-2xl p-4 border border-blue-100 shadow-sm mb-4"
      >
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <ThunderboltOutlined class="text-blue-500" />
            <span class="text-sm font-medium text-slate-700">{{
              taskProgress.task_name || '质控任务执行中'
            }}</span>
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
        <div
          v-if="taskProgress.progress_pct >= 100"
          class="flex items-center gap-4 mt-2 text-xs text-slate-500"
        >
          <span>平均分:
            <b class="text-slate-700">{{ taskProgress.avg_score?.toFixed(1) || '-' }}</b></span>
          <span>缺陷数: <b class="text-slate-700">{{ taskProgress.total_defects || 0 }}</b></span>
          <a-button
            size="small"
            type="link"
            @click="handleCloseProgress"
          >
            关闭
          </a-button>
        </div>
      </div>
    </transition>
    <!-- 1. 顶部 Pro 风格信息头 -->
    <div
      class="mb-6 overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-blue-900 to-slate-800 p-6 shadow-xl shadow-slate-900/20"
    >
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div
            class="mb-2 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium text-blue-100"
          >
            <ThunderboltOutlined />
            运行病历 · Pro 控台
          </div>
          <h2 class="text-2xl font-bold tracking-tight text-white">
            运行病历质控中心
          </h2>
          <p class="mt-1 text-sm text-blue-100/90">
            统一管理质控任务、缺陷处理与整改闭环
          </p>
        </div>
        <div class="flex items-center gap-2">
          <a-button
            class="!h-9 !rounded-xl !border-white/40 !bg-white/10 !text-white hover:!border-white hover:!bg-white/20"
            @click="handleRefresh"
          >
            <ReloadOutlined :spin="loading" />
            刷新
          </a-button>
          <a-button
            type="primary"
            class="!h-9 !rounded-xl !border-0 !bg-emerald-500 !text-white hover:!bg-emerald-400"
            @click="showCreateTaskModal = true"
          >
            <PlusOutlined />
            新建任务
          </a-button>
        </div>
      </div>

      <div class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
        <div class="rounded-xl border border-white/15 bg-white/10 p-3 backdrop-blur-sm">
          <div class="text-xs text-blue-100/80">
            今日待审核
          </div>
          <div class="mt-1 flex items-end justify-between">
            <div class="text-2xl font-bold text-white">
              {{ overviewStats.pending_count || 0 }}
            </div>
            <ClockCircleOutlined class="text-base text-blue-200" />
          </div>
        </div>
        <button
          class="rounded-xl border border-rose-200/30 bg-rose-500/15 p-3 text-left backdrop-blur-sm transition hover:bg-rose-500/20"
          @click="handleQuickFilter('critical')"
        >
          <div class="text-xs text-rose-100/90">
            高风险病历
          </div>
          <div class="mt-1 flex items-end justify-between">
            <div class="text-2xl font-bold text-rose-50">
              {{ overviewStats.defects_by_severity?.critical || 0 }}
            </div>
            <AlertOutlined class="text-base text-rose-100" />
          </div>
        </button>
        <div class="rounded-xl border border-emerald-200/30 bg-emerald-500/15 p-3 backdrop-blur-sm">
          <div class="text-xs text-emerald-100/90">
            审核通过率
          </div>
          <div class="mt-1 flex items-end justify-between">
            <div class="text-2xl font-bold text-emerald-50">
              {{ overviewStats.pass_rate?.toFixed?.(1) || '0.0' }}%
            </div>
            <CheckCircleOutlined class="text-base text-emerald-100" />
          </div>
        </div>
        <div class="rounded-xl border border-indigo-200/30 bg-indigo-500/15 p-3 backdrop-blur-sm">
          <div class="text-xs text-indigo-100/90">
            总缺陷数
          </div>
          <div class="mt-1 flex items-end justify-between">
            <div class="text-2xl font-bold text-indigo-50">
              {{ overviewStats.total_defects || 0 }}
            </div>
            <ThunderboltOutlined class="text-base text-indigo-100" />
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 主内容区：工具栏 + 表格 -->
    <div
      class="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[calc(100vh-180px)]"
    >
      <ProQueryBar>
        <template #filters>
          <div class="relative">
            <a-input
              v-model:value="queryConditions.searchValue"
              placeholder="搜索病案号/姓名/医生..."
              class="w-64 !rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400 focus:!border-blue-500 !pl-10"
              @press-enter="handleQuery"
            />
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          <a-select
            v-model:value="queryConditions.timeRange"
            class="w-32 custom-select"
            placeholder="时间周期"
            :bordered="false"
          >
            <a-select-option value="all">
              全部时间
            </a-select-option>
            <a-select-option value="recent7">
              近7日
            </a-select-option>
            <a-select-option value="month">
              本月
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="queryConditions.status"
            class="w-32 custom-select"
            placeholder="审核状态"
            :bordered="false"
          >
            <a-select-option value="all">
              全部状态
            </a-select-option>
            <a-select-option value="pending">
              待审核
            </a-select-option>
            <a-select-option value="reviewing">
              审核中
            </a-select-option>
          </a-select>

          <div class="h-6 w-px bg-slate-200 mx-1" />

          <a-button
            type="text"
            class="text-slate-500 hover:text-blue-600 !flex items-center gap-1"
            @click="showFilterModal = true"
          >
            <FilterOutlined /> 筛选
          </a-button>
        </template>

        <template #actions>
          <ProTableToolbar>
            <a-button
              type="primary"
              class="!h-9 !rounded-xl"
              @click="handleQuery"
            >
              查询
            </a-button>
            <a-button
              class="!h-9 !rounded-xl !border-slate-200"
              @click="handleResetQuery"
            >
              重置
            </a-button>

            <div class="flex bg-slate-100 p-1 rounded-lg">
              <button
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="
                  currentView === 'records'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                "
                @click="currentView = 'records'"
              >
                <FileTextOutlined class="mr-1" />列表
              </button>
              <button
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="
                  currentView === 'defects'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                "
                @click="currentView = 'defects'"
              >
                <ExclamationCircleOutlined class="mr-1" />缺陷
              </button>
              <button
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="
                  currentView === 'remediation'
                    ? 'bg-white text-blue-600 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                "
                @click="currentView = 'remediation'"
              >
                <CheckCircleOutlined class="mr-1" />整改
              </button>
            </div>

            <a-button
              class="!rounded-xl !border-slate-200 text-slate-600 hover:text-blue-600 !h-9"
              @click="openCustomQCExperience()"
            >
              自定义质控体验
            </a-button>
          </ProTableToolbar>
        </template>

        <template
          v-if="stageHint"
          #hint
        >
          {{ stageHint }}
        </template>
      </ProQueryBar>

      <div
        v-if="currentView !== 'remediation'"
        class="flex items-center justify-between border-b border-slate-100 bg-slate-50/70 px-6 py-2.5"
      >
        <div class="text-xs text-slate-500">
          共 <span class="font-semibold text-slate-700">{{ pagination.total }}</span> 条记录
        </div>
        <div class="flex items-center gap-2">
          <button
            class="rounded-full border px-3 py-1 text-xs transition"
            :class="
              activeStatusFilter === 'all'
                ? 'border-blue-200 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
            "
            @click="applyStatusFilter('all')"
          >
            全部状态
          </button>
          <button
            class="rounded-full border px-3 py-1 text-xs transition"
            :class="
              activeStatusFilter === 'pending'
                ? 'border-amber-200 bg-amber-50 text-amber-700'
                : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
            "
            @click="applyStatusFilter('pending')"
          >
            待处理
          </button>
          <button
            class="rounded-full border px-3 py-1 text-xs transition"
            :class="
              activeStatusFilter === 'reviewing'
                ? 'border-blue-200 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
            "
            @click="applyStatusFilter('reviewing')"
          >
            审核中
          </button>
        </div>
      </div>

      <!-- 表格区域（仅在病历/缺陷视图时显示） -->
      <div
        v-if="currentView !== 'remediation'"
        class="flex-1 overflow-hidden px-6 py-2"
      >
        <ProStandardTable
          :columns="currentColumns"
          :data-source="tableDataSource"
          :loading="loading"
          :pagination="pagination"
          :row-selection="rowSelection"
          row-key="id"
          class="modern-table h-full"
          :scroll="{ y: 'calc(100vh - 320px)' }"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'caseInfo'">
              <div class="flex flex-col">
                <div class="flex items-center gap-2">
                  <span
                    class="font-mono font-bold text-slate-700 text-sm cursor-pointer hover:text-blue-600 transition-colors"
                    @click="handleViewDetail(record)"
                  >{{ record.task_number || record.task_name || record.id }}</span>
                  <a-tag
                    v-if="record.status === 'completed'"
                    color="success"
                    class="!rounded-md !text-[10px] !px-1 !mr-0"
                  >
                    完成
                  </a-tag>
                </div>
                <div class="text-xs text-slate-400 mt-0.5">
                  {{ record.task_name || '' }}
                </div>
              </div>
            </template>

            <template v-if="column.key === 'sampling_method'">
              <a-tag
                :color="record.sampling_method === 'all' ? 'blue' : 'green'"
                class="!rounded-md"
              >
                {{
                  record.sampling_method === 'all'
                    ? '全量'
                    : record.sampling_method === 'count'
                      ? '按数量'
                      : record.sampling_method || '-'
                }}
              </a-tag>
            </template>

            <template v-if="column.key === 'auditStatus'">
              <span
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-amber-50 text-amber-600 border-amber-100':
                    getStatusField(record) === 'pending' || getStatusField(record) === 'assigned',
                  'bg-blue-50 text-blue-600 border-blue-100':
                    getStatusField(record) === 'in_progress' ||
                    getStatusField(record) === 'reviewing',
                  'bg-emerald-50 text-emerald-600 border-emerald-100':
                    getStatusField(record) === 'completed' || getStatusField(record) === 'approved',
                  'bg-rose-50 text-rose-600 border-rose-100':
                    getStatusField(record) === 'rejected' || getStatusField(record) === 'failed',
                  'bg-slate-100 text-slate-600 border-slate-200': !getStatusField(record),
                }"
              >
                <span
                  class="w-1.5 h-1.5 rounded-full"
                  :class="{
                    'bg-amber-500':
                      getStatusField(record) === 'pending' || getStatusField(record) === 'assigned',
                    'bg-blue-500':
                      getStatusField(record) === 'in_progress' ||
                      getStatusField(record) === 'reviewing',
                    'bg-emerald-500':
                      getStatusField(record) === 'completed' ||
                      getStatusField(record) === 'approved',
                    'bg-rose-500':
                      getStatusField(record) === 'rejected' || getStatusField(record) === 'failed',
                    'bg-slate-400': !getStatusField(record),
                  }"
                />
                {{ getAuditStatusText(getStatusField(record)) }}
              </span>
            </template>

            <template v-if="column.key === 'createdAt'">
              <span class="text-xs text-slate-500">{{
                record.created_at?.slice(0, 16)?.replace('T', ' ') || '-'
              }}</span>
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
                  class="!h-7 !rounded-full !border-violet-200/90 !text-violet-700 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="jumpToWorkstation(record, 'qc_coding')"
                >
                  编码质控
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
                <a-button
                  size="small"
                  class="!h-7 !rounded-full !border-amber-200/90 !text-amber-700 !px-2.5 !text-xs"
                  :disabled="!getRecordIdForJump(record)"
                  @click="openCustomQCExperience(record)"
                >
                  自定义质控
                </a-button>
              </div>
            </template>

            <template v-if="column.key === 'action'">
              <div class="flex items-center gap-1">
                <a-tooltip title="查看详情">
                  <button
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-blue-600 transition-all"
                    @click="handleViewDetail(record)"
                  >
                    <EyeOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip
                  v-if="getStatusField(record) === 'pending'"
                  title="催办"
                >
                  <button
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-amber-50 hover:text-amber-600 transition-all"
                    @click="handleUrgeRecord(record)"
                  >
                    <SendOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="更多操作">
                  <a-dropdown>
                    <button
                      class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-all"
                    >
                      <MoreOutlined />
                    </button>
                    <template #overlay>
                      <a-menu @click="({ key }: any) => handleMenuAction(key, record)">
                        <a-menu-item
                          v-if="currentView === 'records'"
                          key="reanalyze"
                        >
                          <ThunderboltOutlined /> 重新质控
                        </a-menu-item>
                        <a-menu-item key="export">
                          <FilePdfOutlined /> 导出报告
                        </a-menu-item>
                        <a-menu-item
                          key="delete"
                          class="!text-rose-500"
                        >
                          <DeleteOutlined /> 删除记录
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-tooltip>
              </div>
            </template>
          </template>
        </ProStandardTable>
      </div>

      <!-- 整改闭环视图 -->
      <div
        v-if="currentView === 'remediation'"
        class="flex-1 overflow-hidden px-6 py-2"
      >
        <RemediationPanel />
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
              class="px-3 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-xs font-medium transition-colors flex items-center gap-2"
              @click="handleBatchUrge"
            >
              <SendOutlined /> 批量催办
            </button>
            <button
              class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium transition-colors flex items-center gap-2"
              @click="handleBatchPass"
            >
              <CheckOutlined /> 批量通过
            </button>
            <button
              class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-medium transition-colors flex items-center gap-2"
              @click="handleBatchAssign"
            >
              <SendOutlined /> 派发整改
            </button>

            <button
              class="px-3 py-1.5 rounded-lg bg-slate-600 hover:bg-slate-500 text-xs font-medium transition-colors flex items-center gap-2"
              @click="handleExportDefects"
            >
              <FilePdfOutlined /> 导出
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
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
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
  CloseOutlined,
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
import ProQueryBar from '@/components/pro/ProQueryBar.vue'
import ProTableToolbar from '@/components/pro/ProTableToolbar.vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'
import {
  fetchTaskProgress,
  batchCreateRemediation,
  exportDefectsDownload,
  reAnalyzeQCTask,
  type TaskProgressData,
} from '@/api/qcAdmin'

const route = useRoute()
const router = useRouter()

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
  severity: undefined as string | undefined,
  searchValue: '',
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

// 表格列配置 — 病历/任务视图（后端返回任务级数据）
const recordColumns = [
  { title: '任务信息', key: 'caseInfo', width: 200 },
  { title: '抽样方式', dataIndex: 'sampling_method', key: 'sampling_method', width: 120 },
  { title: '状态', key: 'auditStatus', width: 120 },
  { title: '创建时间', key: 'createdAt', width: 160 },
  { title: '阶段动作', key: 'stageActions', width: 300 },
  { title: '操作', key: 'action', width: 140, align: 'right' as const },
]

// 表格列配置 — 缺陷视图
const defectColumns = [
  { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name', width: 200 },
  { title: '病案号', dataIndex: 'record_id', key: 'record_id', width: 140 },
  { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
  { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
  { title: '状态', key: 'auditStatus', width: 120 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '操作', key: 'action', width: 140, align: 'right' as const },
]

// 根据当前 Tab 返回列配置
const currentColumns = computed(() =>
  currentView.value === 'defects' ? defectColumns : recordColumns,
)

// 根据当前 Tab 返回数据源
const tableDataSource = computed(() =>
  currentView.value === 'defects' ? defects.value : records.value,
)

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
})

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
}))

const activeStatusFilter = computed(() => queryConditions.status || 'all')

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
        severity: queryConditions.severity || undefined,
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
          {
            id: '1',
            record_id: 'C2024001',
            registrationNo: 'R2024001',
            patient_name: '张三',
            patientAge: 45,
            patientGender: '男',
            doctorName: '李医生',
            department: '心内科',
            auditStatus: 'pending',
            score: 85,
            isUrgent: true,
          },
          {
            id: '2',
            record_id: 'C2024002',
            registrationNo: 'R2024002',
            patient_name: '李四',
            patientAge: 32,
            patientGender: '女',
            doctorName: '王医生',
            department: '消化内科',
            auditStatus: 'reviewing',
            score: 92,
            isUrgent: false,
          },
          {
            id: '3',
            record_id: 'C2024003',
            registrationNo: 'R2024003',
            patient_name: '王五',
            patientAge: 67,
            patientGender: '男',
            doctorName: '赵医生',
            department: '呼吸内科',
            auditStatus: 'approved',
            score: 98,
            isUrgent: false,
          },
          {
            id: '4',
            record_id: 'C2024004',
            registrationNo: 'R2024004',
            patient_name: '赵六',
            patientAge: 28,
            patientGender: '女',
            doctorName: '钱医生',
            department: '妇产科',
            auditStatus: 'rejected',
            score: 55,
            isUrgent: false,
          },
          {
            id: '5',
            record_id: 'C2024005',
            registrationNo: 'R2024005',
            patient_name: '孙七',
            patientAge: 55,
            patientGender: '男',
            doctorName: '孙医生',
            department: '骨科',
            auditStatus: 'pending',
            score: 78,
            isUrgent: false,
          },
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

const handleResetQuery = () => {
  queryConditions.searchValue = ''
  queryConditions.timeRange = 'recent7'
  queryConditions.status = 'all'
  queryConditions.severity = undefined
  pagination.current = 1
  fetchRecords()
}

const handleRefresh = () => {
  fetchRecords()
  loadOverview()
}

const applyStatusFilter = (status: 'all' | 'pending' | 'reviewing') => {
  queryConditions.status = status
  pagination.current = 1
  fetchRecords()
}

/** P2: KPI 卡片快速筛选 */
const handleQuickFilter = (filter: string) => {
  if (filter === 'critical') {
    // 切换到缺陷视图，筛选 severity=critical|error
    currentView.value = 'defects'
    queryConditions.status = undefined
    queryConditions.severity = 'critical'
    message.info('已筛选高风险缺陷')
    fetchRecords()
  }
}

/** P2: 操作菜单分发 */
const handleMenuAction = async (key: string, record: any) => {
  if (key === 'reanalyze') {
    // 仅病历视图可用，缺陷视图已在模板中隐藏菜单项
    const taskId = record.task_id
    if (!taskId) {
      message.warning('此记录无关联任务，无法重新质控')
      return
    }
    message.loading('正在重新质控...', 1)
    const res = await reAnalyzeQCTask(taskId)
    if (res.success) {
      message.success('重新质控已触发')
      fetchRecords()
    } else {
      message.error(res.message || '重新质控失败')
    }
  } else if (key === 'export') {
    handleExportDefects()
  } else if (key === 'delete') {
    message.warning('删除功能待后端接入')
  }
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
    const data = res.data as any
    if (data?.failed > 0) {
      message.warning(`派发部分成功：${data.success}/${data.total} 成功，${data.failed} 失败`)
    } else {
      message.success(res.message)
    }
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

const getRecordIdForJump = (record: any): string => {
  return String(record?.record_id || record?.visit_id || record?.visitId || record?.id || '').trim()
}

const resolveStageByAction = (action: WorkstationLaunchAction): WorkflowStageKey => {
  if (action === 'generate_frontpage') return 'frontpage_generate'
  if (action === 'qc_coding') return 'coding_qc'
  if (action === 'qc_frontpage') return 'frontpage_qc'
  if (action === 'qc_settlement') return 'settlement_qc'
  const stageFromQuery = String(route.query.stage || '').trim()
  if (
    stageFromQuery === 'frontpage_generate' ||
    stageFromQuery === 'coding_qc' ||
    stageFromQuery === 'frontpage_qc' ||
    stageFromQuery === 'settlement_qc'
  ) {
    return stageFromQuery
  }
  return 'frontpage_generate'
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

const openCustomQCExperience = (record?: any) => {
  const recordId = record ? getRecordIdForJump(record) : ''
  const query: Record<string, string> = { scene: 'running' }
  if (recordId) {
    query.record_ids = recordId
    const taskId = String(record?.task_id || '').trim()
    if (taskId) query.visit_id = taskId
  }
  router.push({ path: '/workstation-v4/custom-qc-experience', query })
}

const stageHint = computed(() => {
  const stage = String(route.query.stage || '').trim()
  if (stage === 'frontpage_generate') return '当前队列：待生成首页'
  if (stage === 'coding_qc') return '当前队列：待编码质控'
  if (stage === 'frontpage_qc') return '当前队列：待首页质控'
  if (stage === 'settlement_qc') return '当前队列：待结算清单质控'
  return ''
})

const applyStagePreset = (stage: string) => {
  pagination.current = 1
  if (!stage) return
  if (stage === 'frontpage_generate') {
    currentView.value = 'records'
    queryConditions.status = 'pending'
    queryConditions.severity = undefined
  } else if (stage === 'coding_qc') {
    currentView.value = 'records'
    queryConditions.status = 'pending'
    queryConditions.severity = undefined
  } else if (stage === 'frontpage_qc') {
    currentView.value = 'defects'
    queryConditions.status = 'pending'
    queryConditions.severity = undefined
  } else if (stage === 'settlement_qc') {
    currentView.value = 'records'
    queryConditions.status = 'reviewing'
    queryConditions.severity = undefined
  }
  fetchRecords()
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
    pending: '待处理',
    assigned: '已分配',
    in_progress: '进行中',
    completed: '已完成',
    approved: '已通过',
    rejected: '已驳回',
    reviewing: '审核中',
    urged: '已催办',
    remediated: '已整改',
    failed: '失败',
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

watch(
  () => route.query.stage,
  (value) => {
    applyStagePreset(String(value || '').trim())
  },
  { immediate: true },
)

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
