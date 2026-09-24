<template>
  <div class="running-records-page min-h-screen p-5 lg:p-6">
    <!-- 任务进度条（创建任务后显示） -->
    <transition name="slide-down">
      <div
        v-if="taskProgress"
        class="apple-progress-panel mb-4 rounded-2xl p-4"
      >
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <ThunderboltOutlined class="text-[#2b6cf6]" />
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
          :stroke-color="{ from: '#2b6cf6', to: '#10b981' }"
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
    <!-- 1. 顶部业务标题与 KPI -->
    <div class="apple-hero-panel mb-5 p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div class="text-[11px] font-semibold tracking-normal text-slate-500">
            运行队列
          </div>
          <h1 class="mt-1 text-[28px] font-bold leading-8 tracking-normal text-slate-900">
            运行病历质控
          </h1>
          <p class="mt-1 text-sm font-medium text-slate-500">
            聚合在院病历、质控任务与整改闭环，优先处理高风险和待审核记录。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <a-button
            class="apple-secondary-button !h-9 !rounded-lg"
            @click="handleRefresh"
          >
            <ReloadOutlined :spin="loading" />
            刷新
          </a-button>
          <a-button
            type="primary"
            class="apple-primary-button !h-9 !rounded-lg"
            @click="showCreateTaskModal = true"
          >
            <PlusOutlined />
            新建任务
          </a-button>
        </div>
      </div>

      <div class="mt-5 grid grid-cols-1 gap-3 md:grid-cols-4">
        <div class="queue-kpi-card">
          <div class="queue-kpi-icon queue-kpi-icon-primary">
            <ClockCircleOutlined />
          </div>
          <div>
            <div class="queue-kpi-label">
              今日待审核
            </div>
            <div class="queue-kpi-value">
              {{ overviewStats.pending_count || 0 }}
            </div>
            <div class="queue-kpi-desc">
              等待质控处理
            </div>
          </div>
        </div>
        <button
          class="queue-kpi-card text-left transition hover:border-red-200 hover:bg-red-50/30"
          @click="handleQuickFilter('critical')"
        >
          <div class="queue-kpi-icon bg-red-50 text-red-500">
            <AlertOutlined />
          </div>
          <div>
            <div class="queue-kpi-label">
              高风险病历
            </div>
            <div class="queue-kpi-value">
              {{ overviewStats.defects_by_severity?.critical || 0 }}
            </div>
            <div class="queue-kpi-desc">
              建议优先复核
            </div>
          </div>
        </button>
        <div class="queue-kpi-card">
          <div class="queue-kpi-icon bg-emerald-50 text-emerald-600">
            <CheckCircleOutlined />
          </div>
          <div>
            <div class="queue-kpi-label">
              审核通过率
            </div>
            <div class="queue-kpi-value">
              {{ overviewStats.pass_rate?.toFixed?.(1) || '0.0' }}%
            </div>
            <div class="queue-kpi-desc">
              当前筛选范围
            </div>
          </div>
        </div>
        <div class="queue-kpi-card">
          <div class="queue-kpi-icon bg-orange-50 text-orange-500">
            <ThunderboltOutlined />
          </div>
          <div>
            <div class="queue-kpi-label">
              总缺陷数
            </div>
            <div class="queue-kpi-value">
              {{ overviewStats.total_defects || 0 }}
            </div>
            <div class="queue-kpi-desc">
              已发现问题
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 主内容区：工具栏 + 表格 -->
    <div class="apple-workbench flex h-[calc(100vh-198px)] flex-col">
      <ProQueryBar>
        <template #filters>
          <div class="relative">
            <a-input
              v-model:value="queryConditions.searchValue"
              placeholder="搜索病案号、姓名、医生"
              class="w-64 apple-input !pl-10"
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
            class="text-slate-500 hover:text-[#2b6cf6] !flex items-center gap-1"
            @click="showFilterModal = true"
          >
            <FilterOutlined /> 筛选
          </a-button>
        </template>

        <template #actions>
          <ProTableToolbar>
            <a-button
              type="primary"
              class="!h-9 !rounded-lg"
              @click="handleQuery"
            >
              查询
            </a-button>
            <a-button
              class="!h-9 !rounded-lg !border-slate-200"
              @click="handleResetQuery"
            >
              重置
            </a-button>

            <div class="flex bg-slate-100 p-1 rounded-lg">
              <button
                class="px-3 py-1 rounded-md text-xs font-medium transition-all"
                :class="
                  currentView === 'records'
                    ? 'bg-white text-[#2b6cf6] shadow-sm'
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
                    ? 'bg-white text-[#2b6cf6] shadow-sm'
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
                    ? 'bg-white text-[#2b6cf6] shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                "
                @click="currentView = 'remediation'"
              >
                <CheckCircleOutlined class="mr-1" />整改
              </button>
            </div>

            <a-button
              class="!h-9 !rounded-lg !border-slate-200 text-slate-600 hover:text-[#2b6cf6]"
              @click="openCustomQCExperience()"
            >
              自定义质控点
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
                ? 'border-[rgba(43,108,246,0.18)] bg-[rgba(43,108,246,0.08)] text-[#2b6cf6]'
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
                ? 'border-[rgba(43,108,246,0.18)] bg-[rgba(43,108,246,0.08)] text-[#2b6cf6]'
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
              <div class="flex items-center gap-3">
                <img
                  v-if="hasPatientIdentity(record)"
                  :src="patientAvatarSrc(record)"
                  alt=""
                  class="record-patient-avatar"
                >
                <div
                  v-else
                  class="flex h-9 w-9 items-center justify-center rounded-full border border-[rgba(43,108,246,0.14)] bg-[rgba(43,108,246,0.08)] text-[#2b6cf6]"
                >
                  <FileTextOutlined />
                </div>
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <span
                      class="cursor-pointer truncate text-sm font-semibold text-slate-800 transition-colors hover:text-[#2b6cf6]"
                      @click="handleViewDetail(record)"
                    >{{ getPrimaryRecordTitle(record) }}</span>
                    <a-tag
                      v-if="record.status === 'completed'"
                      color="success"
                      class="!mr-0 !rounded-md !px-1 !text-[10px]"
                    >
                      完成
                    </a-tag>
                  </div>
                  <div class="mt-0.5 truncate text-xs font-medium text-slate-400">
                    {{ getSecondaryRecordTitle(record) }}
                  </div>
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
                  'bg-[rgba(43,108,246,0.08)] text-[#2b6cf6] border-[rgba(43,108,246,0.14)]':
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
                    'bg-[#2b6cf6]':
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
                  class="!h-7 !rounded-full !border-[rgba(43,108,246,0.2)] !text-[#2b6cf6] !px-2.5 !text-xs"
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
                    class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-[#2b6cf6] transition-all"
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
          class="absolute bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-5 rounded-[14px] border border-slate-200 bg-white px-5 py-3 text-slate-700 shadow-[0_16px_36px_rgba(15,23,42,0.12)]"
        >
          <span class="text-sm font-semibold">已选择
            <span class="mx-1 font-bold text-[#2b6cf6]">{{ selectedRowKeys.length }}</span> 项</span>
          <div class="h-4 w-px bg-slate-200" />
          <div class="flex items-center gap-2">
            <button
              class="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-amber-200 hover:bg-amber-50 hover:text-amber-700"
              @click="handleBatchUrge"
            >
              <SendOutlined /> 批量催办
            </button>
            <button
              class="apple-primary-action flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition-colors"
              @click="handleBatchPass"
            >
              <CheckOutlined /> 批量通过
            </button>
            <button
              class="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 transition-colors hover:bg-emerald-100"
              @click="handleBatchAssign"
            >
              <SendOutlined /> 派发整改
            </button>

            <button
              class="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-[rgba(43,108,246,0.22)] hover:text-[#2b6cf6]"
              @click="handleExportDefects"
            >
              <FilePdfOutlined /> 导出
            </button>

            <button
              class="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
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
      scene="running"
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
import avatarBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import avatarElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import avatarElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import avatarGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import avatarMan from '@/assets/avatar-icons/patient-icon-man.png'
import avatarWoman from '@/assets/avatar-icons/patient-icon-woman.png'
import {
  fetchTaskProgress,
  batchCreateRemediation,
  exportDefectsDownload,
  reAnalyzeQCTask,
  type CreateTaskAndSampleData,
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

type QueueRecord = Record<string, unknown>

// 表格列配置 — 病历/任务视图（后端返回任务级数据）
const recordColumns = [
  { title: '病历/任务信息', key: 'caseInfo', width: 240 },
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
const clearRecords = () => {
  records.value = []
  pagination.current = 1
  pagination.total = 0
  selectedRowKeys.value = []
}

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
        clearRecords()
        message.error('获取病历列表失败')
      }
    }
  } catch (error) {
    if (currentView.value !== 'defects') clearRecords()
    message.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

// ============= 事件处理 =============

/** 任务创建成功后：启动进度轮询 */
const handleTaskCreated = (data: CreateTaskAndSampleData) => {
  if (data.sampled) {
    startProgressPolling(data.task_id)
  }
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
      message.success(res.message || '重新质控已触发')
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
  router.push({ path: '/workstation-v5', query })
}

const openCustomQCExperience = (record?: any) => {
  const recordId = record ? getRecordIdForJump(record) : ''
  const query: Record<string, string> = { scene: 'running' }
  if (recordId) {
    query.record_ids = recordId
    const taskId = String(record?.task_id || '').trim()
    if (taskId) query.visit_id = taskId
  }
  router.push({ path: '/workstation-v5/custom-qc-experience', query })
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
  if (score >= 80) return '#2b6cf6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

const pickText = (record: QueueRecord, keys: string[]): string => {
  for (const key of keys) {
    const value = record[key]
    if (value !== null && value !== undefined && String(value).trim()) {
      return String(value).trim()
    }
  }
  return ''
}

const getPrimaryRecordTitle = (record: QueueRecord): string => {
  return (
    pickText(record, ['patient_name', 'patientName', 'patient']) ||
    pickText(record, ['task_number', 'task_name', 'record_id', 'visit_id', 'id']) ||
    '-'
  )
}

const getSecondaryRecordTitle = (record: QueueRecord): string => {
  const recordId = pickText(record, ['record_id', 'visit_id', 'visitId', 'registrationNo'])
  const taskName = pickText(record, ['task_name', 'task_number'])
  const department = pickText(record, ['department', 'dept_name', 'deptName'])
  return [recordId || taskName, department].filter(Boolean).join(' · ') || taskName || '-'
}

const hasPatientIdentity = (record: QueueRecord): boolean => {
  return Boolean(pickText(record, ['patient_name', 'patientName', 'patient']))
}

const isFemale = (value: unknown): boolean => {
  const raw = String(value || '')
    .trim()
    .toLowerCase()
  return ['女', 'female', 'f', '2'].includes(raw)
}

const patientAvatarSrc = (record: QueueRecord): string => {
  const age = Number(
    record.patient_age ?? record.patientAge ?? record.age ?? record.patient_age_years ?? 0,
  )
  const female = isFemale(
    record.patient_sex ?? record.patient_gender ?? record.patientGender ?? record.sex,
  )
  if (Number.isFinite(age) && age > 0 && age < 14) return female ? avatarGirl : avatarBoy
  if (Number.isFinite(age) && age >= 55) return female ? avatarElderWoman : avatarElderMan
  return female ? avatarWoman : avatarMan
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
.running-records-page {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.apple-progress-panel,
.apple-hero-panel,
.apple-workbench {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.06),
    0 10px 30px rgba(0, 0, 0, 0.045);
  backdrop-filter: blur(18px);
}

.apple-hero-panel {
  border-radius: 20px;
}

.apple-workbench {
  border-radius: 20px;
}

.apple-primary-button,
.apple-primary-action {
  border: 0 !important;
  background: #2b6cf6 !important;
  color: #ffffff !important;
  box-shadow: 0 2px 8px rgba(43, 108, 246, 0.18) !important;
}

.apple-primary-button:hover,
.apple-primary-action:hover {
  background: #005bb8 !important;
}

.apple-secondary-button {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.78) !important;
  color: rgba(29, 29, 31, 0.78) !important;
}

.apple-secondary-button:hover {
  border-color: rgba(43, 108, 246, 0.24) !important;
  color: #2b6cf6 !important;
}

.apple-input {
  border-color: rgba(0, 0, 0, 0.08) !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.72) !important;
}

.queue-kpi-card {
  display: flex;
  min-height: 92px;
  align-items: center;
  gap: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  padding: 16px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.04);
}

.queue-kpi-card:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.queue-kpi-icon {
  display: flex;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  font-size: 18px;
}

.queue-kpi-icon-primary {
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
}

.queue-kpi-label {
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
}

.queue-kpi-value {
  margin-top: 2px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
}

.queue-kpi-desc {
  margin-top: 2px;
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.record-patient-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  border: 1px solid rgba(43, 108, 246, 0.14);
  border-radius: 999px;
  background: rgba(43, 108, 246, 0.08);
  object-fit: cover;
  box-shadow: 0 8px 18px rgba(43, 108, 246, 0.1);
}

/* 胶囊选择器样式覆盖 */
:deep(.custom-select .ant-select-selector) {
  background-color: rgba(255, 255, 255, 0.72) !important;
  border-radius: 10px !important;
  border: 1px solid rgba(0, 0, 0, 0.08) !important;
  height: 34px !important;
  display: flex;
  align-items: center;
  transition: all 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: rgba(43, 108, 246, 0.32) !important;
  background-color: #ffffff !important;
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08) !important;
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
  background: rgba(245, 245, 247, 0.76);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.6);
  font-weight: 600;
  font-size: 13px;
  padding: 12px 16px;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 16px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  transition: background-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.modern-table :deep(.ant-table-tbody > tr:hover > td) {
  background-color: rgba(0, 0, 0, 0.035) !important;
}

:deep(.ant-btn-primary) {
  border-color: #2b6cf6 !important;
  background: #2b6cf6 !important;
}

:deep(.ant-input:hover),
:deep(.ant-input:focus) {
  border-color: rgba(43, 108, 246, 0.32) !important;
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08) !important;
}

:deep(.ant-pagination-item-active) {
  border-color: #2b6cf6;
}

:deep(.ant-pagination-item-active a),
:deep(.ant-btn-link) {
  color: #2b6cf6;
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
