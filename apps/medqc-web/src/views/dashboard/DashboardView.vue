<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import { getTodoStats, getPerformanceRanking } from '@/api/dashboard'
import type { TodoStats, PerformanceData, DashboardScene } from '@/api/dashboard'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import { getAccessToken } from '@/utils/auth-token'
import QCTrendChart from '@/components/charts/QCTrendChart.vue'
import TodoBoard from '@/components/dashboard/TodoBoard.vue'
import PerformanceBoard from '@/components/dashboard/PerformanceBoard.vue'
import {
  ReloadOutlined,
  PlusOutlined,
  ArrowUpOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  UploadOutlined,
  FileSearchOutlined,
  SettingOutlined,
  CalendarOutlined,
  UserOutlined,
  MoreOutlined,
  TrophyOutlined,
  RightOutlined,
} from '@ant-design/icons-vue'

// 状态管理
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

// 页面状态
const loading = ref(true)
const refreshing = ref(false)
const selectedPeriod = ref('month')
const VALID_SCENES: DashboardScene[] = ['all', 'outpatient_emergency', 'running', 'final']
const currentScene = computed<DashboardScene>(() => {
  const q = String(route.query.scene || '').trim()
  if (VALID_SCENES.includes(q as DashboardScene)) {
    return q as DashboardScene
  }
  return 'all'
})

// 统计数据（初始为 0，由 API 填充）
const stats = ref({
  totalRecords: 0,
  pendingRecords: 0,
  analyzingRecords: 0,
  completedRecords: 0,
  averageScore: 0,
  passRate: 0,
  todayUploads: 0,
  weeklyTrend: '--',
})

interface WorkflowEntryCard {
  key: WorkflowStageKey
  title: string
  subtitle: string
  count: number
  action: WorkstationLaunchAction
  continueRecordId: string
  continueTaskId: string
}

const workflowLoading = ref(false)
const workflowCards = ref<WorkflowEntryCard[]>([
  {
    key: 'frontpage_generate',
    title: '待生成首页',
    subtitle: '已出院且首页未生成',
    count: 0,
    action: 'generate_frontpage',
    continueRecordId: '',
    continueTaskId: '',
  },
  {
    key: 'frontpage_qc',
    title: '待首页质控',
    subtitle: '首页已生成，待核对规则',
    count: 0,
    action: 'qc_frontpage',
    continueRecordId: '',
    continueTaskId: '',
  },
  {
    key: 'settlement_qc',
    title: '待结算清单质控',
    subtitle: '结算前关键质控队列',
    count: 0,
    action: 'qc_settlement',
    continueRecordId: '',
    continueTaskId: '',
  },
])

// 排名数据
const performanceData = ref<PerformanceData | null>(null)

// TodoBoard 原始数据
const todoStatsRaw = ref<Record<string, any>>({})

// 最新活动数据
const recentActivities = ref([
  {
    id: 1,
    type: 'upload',
    title: '新增病案 - 张三',
    description: '内科住院病案，等待质控分析',
    time: '2分钟前',
    icon: 'FileAddOutlined',
    color: '#3b82f6',
    bg: 'bg-blue-50 text-blue-600',
  },
  {
    id: 2,
    type: 'analysis',
    title: '质控分析完成 - 李四',
    description: '外科手术病案，评分92分',
    time: '15分钟前',
    icon: 'CheckCircleOutlined',
    color: '#10b981',
    bg: 'bg-emerald-50 text-emerald-600',
  },
  {
    id: 3,
    type: 'review',
    title: '病案审核 - 王五',
    description: '妇产科病案需要进一步确认',
    time: '1小时前',
    icon: 'ExclamationCircleOutlined',
    color: '#f59e0b',
    bg: 'bg-amber-50 text-amber-600',
  },
  {
    id: 4,
    type: 'system',
    title: '系统更新',
    description: '质控规则已更新，新增3条检查规则',
    time: '2小时前',
    icon: 'ToolOutlined',
    color: '#8b5cf6',
    bg: 'bg-purple-50 text-purple-600',
  },
])

// 快捷操作
const quickActions = [
  {
    title: '上传病案',
    icon: UploadOutlined,
    color: 'text-blue-600',
    bg: 'bg-blue-50 group-hover:bg-blue-600 group-hover:text-white',
    action: 'upload',
    desc: '批量导入病案数据',
  },
  {
    title: '智能质控',
    icon: ThunderboltOutlined,
    color: 'text-indigo-600',
    bg: 'bg-indigo-50 group-hover:bg-indigo-600 group-hover:text-white',
    action: 'analyze',
    desc: 'AI 辅助病案分析',
  },
  {
    title: '生成报告',
    icon: FileSearchOutlined,
    color: 'text-emerald-600',
    bg: 'bg-emerald-50 group-hover:bg-emerald-600 group-hover:text-white',
    action: 'report',
    desc: '导出质控统计报表',
  },
  {
    title: '规则配置',
    icon: SettingOutlined,
    color: 'text-slate-600',
    bg: 'bg-slate-100 group-hover:bg-slate-600 group-hover:text-white',
    action: 'rules',
    desc: '自定义质控规则',
  },
]

const stageQueueRoute: Record<WorkflowStageKey, string> = {
  frontpage_generate: '/dashboard/records/running',
  frontpage_qc: '/dashboard/records/running',
  settlement_qc: '/dashboard/records/final',
}

function getAuthHeaders(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function pickRecordId(record: Record<string, any>): string {
  return String(record?.id || record?.record_id || record?.visit_id || record?.visitId || '').trim()
}

function pickTaskId(record: Record<string, any>): string {
  return String(record?.task_id || record?.taskId || '').trim()
}

function isDischargedRecord(record: Record<string, any>): boolean {
  const dischargeDate = String(record?.dischargeDate || record?.discharge_date || '').trim()
  return dischargeDate.length > 0
}

function hasEmptyFrontpage(record: Record<string, any>): boolean {
  return Boolean(record?.cdmFrontpageEmpty ?? record?.cdm_frontpage_empty)
}

function normalizeStatus(record: Record<string, any>): string {
  return String(record?.status || record?.auditStatus || record?.audit_status || '').toLowerCase()
}

function openWorkstationAction(
  recordId: string,
  action: WorkstationLaunchAction,
  stage: WorkflowStageKey,
  taskId = '',
) {
  if (!recordId) {
    message.warning('当前队列暂无可联动病历')
    return
  }
  const query: Record<string, string> = {
    record_id: recordId,
    action,
    source: 'dashboard',
    from_stage: stage,
  }
  if (taskId) query.task_id = taskId
  router.push({ path: '/workstation-v4', query })
}

function openStageQueue(stage: WorkflowStageKey) {
  router.push({
    path: stageQueueRoute[stage],
    query: { stage },
  })
}

function continueStage(card: WorkflowEntryCard) {
  openWorkstationAction(card.continueRecordId, card.action, card.key, card.continueTaskId)
}

// 获取问候语
const getGreeting = () => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 17) return '下午好'
  if (hour < 19) return '傍晚好'
  if (hour < 22) return '晚上好'
  return '深夜好'
}

// 处理快捷操作
const handleQuickAction = (action: string) => {
  const routeMap: Record<string, string> = {
    upload: '/workstation-v4/upload',
    analyze: '/dashboard/records/running',
    report: '/dashboard/records/final',
    rules: '/workstation-v4/rules?tab=coding',
  }
  const target = routeMap[action]
  if (!target) return
  router.push(target)
}

// 刷新数据
const refreshData = async () => {
  refreshing.value = true
  try {
    await fetchDashboardData()
  } finally {
    refreshing.value = false
  }
}

// 排名周期切换
const handlePeriodChange = async (period: string) => {
  try {
    const res = await getPerformanceRanking(
      period as 'this_week' | 'last_week' | 'this_month',
      currentScene.value,
    )
    if (res.success && res.data) {
      performanceData.value = res.data
    }
  } catch (err) {
    console.error('切换排名周期失败:', err)
  }
}

// 从 API 获取 Dashboard 数据
const fetchDashboardData = async () => {
  try {
    // 并行请求待办统计和排名
    const [todoRes, perfRes] = await Promise.all([
      getTodoStats(currentScene.value),
      getPerformanceRanking('this_week', currentScene.value),
    ])

    if (todoRes.success && todoRes.data) {
      const data = todoRes.data
      const overview = data.overview || ({} as any)
      stats.value = {
        totalRecords: data.record_stats?.total || overview.total_records || 0,
        pendingRecords: data.record_stats?.pending_review || overview.total_defects || 0,
        analyzingRecords: data.task_stats?.in_progress || 0,
        completedRecords:
          (data.record_stats?.total || 0) - (data.record_stats?.pending_review || 0),
        averageScore: overview.avg_score || 0,
        passRate: overview.pass_rate || 0,
        todayUploads: data.task_stats?.not_started || 0,
        weeklyTrend: '--',
      }

      // 保存原始数据给 TodoBoard
      todoStatsRaw.value = data
    }

    if (perfRes.success && perfRes.data) {
      performanceData.value = perfRes.data
    }

    await fetchWorkflowCards()
  } catch (err) {
    console.error('获取 Dashboard 数据失败:', err)
  }
}

const fetchWorkflowCards = async () => {
  workflowLoading.value = true
  try {
    const response = await fetch('/api/medical-records/workstation?page=1&page_size=200', {
      headers: getAuthHeaders(),
    })
    const data = await response.json()
    const records = Array.isArray(data?.records) ? data.records : []

    const generateQueue = records.filter(
      (record: Record<string, any>) => isDischargedRecord(record) && hasEmptyFrontpage(record),
    )

    const frontpageQcQueue = records.filter((record: Record<string, any>) => {
      const status = normalizeStatus(record)
      return (
        isDischargedRecord(record) &&
        !hasEmptyFrontpage(record) &&
        ['pending', 'processing', 'in_progress', 'reviewing', 'running'].includes(status)
      )
    })

    const settlementQcQueue = records.filter((record: Record<string, any>) => {
      const status = normalizeStatus(record)
      return (
        isDischargedRecord(record) &&
        !hasEmptyFrontpage(record) &&
        ['completed', 'warning', 'has_defects', 'approved'].includes(status)
      )
    })

    workflowCards.value = workflowCards.value.map((card) => {
      const queue =
        card.key === 'frontpage_generate'
          ? generateQueue
          : card.key === 'frontpage_qc'
            ? frontpageQcQueue
            : settlementQcQueue
      const first = queue[0] || {}
      return {
        ...card,
        count: queue.length,
        continueRecordId: pickRecordId(first),
        continueTaskId: pickTaskId(first),
      }
    })
  } catch (error) {
    console.error('加载病案处理入口失败:', error)
  } finally {
    workflowLoading.value = false
  }
}

// 获取当前日期
const currentDate = computed(() => {
  const now = new Date()
  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }
  return now.toLocaleDateString('zh-CN', options)
})

onMounted(async () => {
  await fetchDashboardData()
  loading.value = false
})

watch(
  () => route.query.scene,
  async () => {
    if (!loading.value) {
      await fetchDashboardData()
    }
  },
)
</script>

<template>
  <div class="w-full bg-slate-50/50 p-6 lg:p-8 font-sans relative overflow-x-hidden">
    <!-- 顶部装饰背景 -->
    <div
      class="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-blue-100/40 via-indigo-50/20 to-transparent pointer-events-none z-0"
    />
    <div
      class="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-gradient-to-br from-blue-200/30 to-purple-200/30 rounded-full blur-3xl pointer-events-none z-0"
    />

    <div class="relative z-10 max-w-7xl mx-auto">
      <!-- 1. Hero Section: 欢迎区 -->
      <div class="mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div class="flex items-center gap-5">
          <div class="relative group cursor-pointer">
            <div
              class="absolute inset-0 bg-blue-600 rounded-2xl blur opacity-20 group-hover:opacity-30 transition-opacity"
            />
            <div
              class="relative w-16 h-16 rounded-2xl bg-white flex items-center justify-center text-blue-600 shadow-sm border border-blue-50 group-hover:scale-105 transition-transform duration-300"
            >
              <UserOutlined class="text-3xl" />
            </div>
            <div
              class="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 border-2 border-white rounded-full"
            />
          </div>

          <div>
            <div
              class="text-slate-500 text-xs font-medium mb-1.5 flex items-center gap-2 bg-white/60 backdrop-blur-sm px-2 py-0.5 rounded-full w-fit border border-slate-200/50"
            >
              <CalendarOutlined /> {{ currentDate }}
            </div>
            <h1 class="text-2xl md:text-3xl font-bold text-slate-800 tracking-tight mb-1">
              {{ getGreeting() }}，{{ authStore.userName }}
            </h1>
            <p class="text-slate-500 text-sm">
              今天系统运行平稳，有
              <span class="text-blue-600 font-bold px-1">{{ stats.pendingRecords }}</span>
              份待分析病案。
            </p>
          </div>
        </div>

        <div class="flex items-center gap-3 w-full md:w-auto">
          <button
            class="flex-1 md:flex-none px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-blue-600 hover:border-blue-200 transition-all font-medium text-sm flex items-center justify-center gap-2 shadow-sm"
            @click="refreshData"
          >
            <ReloadOutlined :class="{ 'animate-spin': refreshing }" />
            <span class="hidden sm:inline">刷新</span>
          </button>
          <button
            class="flex-1 md:flex-none px-6 py-2.5 rounded-xl bg-slate-900 text-white hover:bg-blue-600 transition-all font-medium text-sm flex items-center justify-center gap-2 shadow-lg shadow-slate-200 hover:shadow-blue-500/30"
          >
            <ThunderboltOutlined />
            开始质控
          </button>
        </div>
      </div>

      <!-- 2. 病案处理入口区（Dashboard -> Workstation 深链） -->
      <div class="mb-8">
        <div class="mb-4 flex items-center justify-between">
          <div>
            <h2 class="text-lg font-bold text-slate-800">病案处理入口</h2>
            <p class="text-xs text-slate-400 mt-1">从任务队列分发病历，进入工作台执行单病历处理</p>
          </div>
          <span class="text-xs text-slate-400">
            {{ workflowLoading ? '更新中...' : '实时联动' }}
          </span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            v-for="card in workflowCards"
            :key="card.key"
            class="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 hover:shadow-md transition-all"
          >
            <div class="flex items-start justify-between mb-3">
              <div>
                <div class="text-slate-500 text-xs font-medium">
                  {{ card.title }}
                </div>
                <div class="text-[11px] text-slate-400 mt-1">
                  {{ card.subtitle }}
                </div>
              </div>
              <div class="text-2xl font-bold text-blue-600 font-mono">
                {{ card.count }}
              </div>
            </div>
            <div class="flex gap-2">
              <button
                type="button"
                class="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:border-blue-200 hover:text-blue-600"
                @click="openStageQueue(card.key)"
              >
                批量查看队列
              </button>
              <button
                type="button"
                class="flex-1 rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-500 disabled:bg-slate-300 disabled:cursor-not-allowed"
                :disabled="!card.continueRecordId"
                @click="continueStage(card)"
              >
                继续处理
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. Key Metrics Section: Bento Grid 布局 -->
      <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-5 mb-8">
        <!-- 核心指标 1: 平均评分 -->
        <div
          class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md hover:border-blue-100 transition-all relative overflow-hidden group"
        >
          <div
            class="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity group-hover:scale-110 duration-500"
          >
            <TrophyOutlined class="text-6xl text-blue-600" />
          </div>
          <div class="flex justify-between items-start mb-3">
            <div
              class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center"
            >
              <TrophyOutlined class="text-xl" />
            </div>
            <span
              class="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-lg flex items-center gap-1 border border-emerald-100"
            >
              <ArrowUpOutlined /> 3.2%
            </span>
          </div>
          <div class="relative z-10">
            <div class="text-slate-500 text-sm font-medium mb-1">平均评分</div>
            <div class="flex items-baseline gap-1.5">
              <span class="text-3xl font-bold text-slate-800 tracking-tight">{{
                stats.averageScore
              }}</span>
              <span class="text-sm text-slate-400 font-medium">分</span>
            </div>
            <div class="w-full h-1.5 bg-slate-100 rounded-full mt-3 overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-blue-400 to-blue-600 rounded-full"
                style="width: 87.5%"
              />
            </div>
          </div>
        </div>

        <!-- 核心指标 2: 质控通过率 -->
        <div
          class="bg-white rounded-2xl p-5 shadow-sm border border-slate-100 hover:shadow-md hover:border-indigo-100 transition-all relative overflow-hidden group"
        >
          <div
            class="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity group-hover:scale-110 duration-500"
          >
            <CheckCircleOutlined class="text-6xl text-indigo-600" />
          </div>
          <div class="flex justify-between items-start mb-3">
            <div
              class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center"
            >
              <CheckCircleOutlined class="text-xl" />
            </div>
            <span
              class="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-lg flex items-center gap-1 border border-emerald-100"
            >
              <ArrowUpOutlined /> 1.5%
            </span>
          </div>
          <div class="relative z-10">
            <div class="text-slate-500 text-sm font-medium mb-1">通过率</div>
            <div class="flex items-baseline gap-1.5">
              <span class="text-3xl font-bold text-slate-800 tracking-tight">{{
                stats.passRate
              }}</span>
              <span class="text-sm text-slate-400 font-medium">%</span>
            </div>
            <div class="w-full h-1.5 bg-slate-100 rounded-full mt-3 overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-indigo-400 to-indigo-600 rounded-full"
                style="width: 94.2%"
              />
            </div>
          </div>
        </div>

        <!-- 工作量概览 (合并列) -->
        <div
          class="bg-white rounded-2xl p-0 shadow-sm border border-slate-100 lg:col-span-2 flex flex-col sm:flex-row divide-y sm:divide-y-0 sm:divide-x divide-slate-100 overflow-hidden"
        >
          <div class="flex-1 p-5 hover:bg-slate-50/50 transition-colors group cursor-pointer">
            <div class="flex items-center gap-2 mb-3">
              <div
                class="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center group-hover:bg-slate-200 transition-colors"
              >
                <FileTextOutlined />
              </div>
              <span class="text-sm font-medium text-slate-500">总病案数</span>
            </div>
            <div class="text-2xl font-bold text-slate-800 mb-1">
              {{ stats.totalRecords }}
            </div>
            <div class="text-xs text-emerald-600 flex items-center gap-1">
              <span class="bg-emerald-50 px-1.5 py-0.5 rounded text-emerald-600 font-medium"
                >+12.5%</span
              >
              <span class="text-slate-400">较上周</span>
            </div>
          </div>

          <div class="flex-1 p-5 hover:bg-slate-50/50 transition-colors group cursor-pointer">
            <div class="flex items-center gap-2 mb-3">
              <div
                class="w-8 h-8 rounded-lg bg-orange-50 text-orange-500 flex items-center justify-center group-hover:bg-orange-100 transition-colors"
              >
                <ClockCircleOutlined />
              </div>
              <span class="text-sm font-medium text-slate-500">待分析</span>
            </div>
            <div class="text-2xl font-bold text-slate-800 mb-1">
              {{ stats.pendingRecords }}
            </div>
            <div class="text-xs text-orange-600 flex items-center gap-1">
              <span class="bg-orange-50 px-1.5 py-0.5 rounded text-orange-600 font-medium"
                >需关注</span
              >
              <span class="text-slate-400">处理积压</span>
            </div>
          </div>

          <div class="flex-1 p-5 hover:bg-slate-50/50 transition-colors group cursor-pointer">
            <div class="flex items-center gap-2 mb-3">
              <div
                class="w-8 h-8 rounded-lg bg-cyan-50 text-cyan-500 flex items-center justify-center group-hover:bg-cyan-100 transition-colors"
              >
                <PlusOutlined />
              </div>
              <span class="text-sm font-medium text-slate-500">今日新增</span>
            </div>
            <div class="text-2xl font-bold text-slate-800 mb-1">
              {{ stats.todayUploads }}
            </div>
            <div class="text-xs text-cyan-600 flex items-center gap-1">
              <span class="bg-cyan-50 px-1.5 py-0.5 rounded text-cyan-600 font-medium">Live</span>
              <span class="text-slate-400">实时同步</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 2.5 待办看板 + 工作表现 -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-5">
        <div class="lg:col-span-8">
          <TodoBoard :todo-data="todoStatsRaw" />
        </div>
        <div class="lg:col-span-4">
          <PerformanceBoard
            :ranking-data="performanceData || {}"
            @period-change="handlePeriodChange"
          />
        </div>
      </div>

      <!-- 3. Main Content: 图表与功能区 -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <!-- 左侧: 质控趋势图表 (8 cols) -->
        <div
          class="lg:col-span-8 bg-white rounded-2xl border border-slate-100 shadow-sm p-6 h-full hover:shadow-md transition-shadow"
        >
          <div class="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
            <div>
              <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2">质控趋势分析</h3>
              <p class="text-slate-400 text-xs mt-1">可视化展示近期的质控评分波动与病案处理量</p>
            </div>

            <div class="flex bg-slate-50 rounded-lg p-1 border border-slate-100">
              <button
                v-for="period in ['week', 'month', 'quarter']"
                :key="period"
                :class="[
                  'px-4 py-1.5 text-xs font-medium rounded-md transition-all',
                  selectedPeriod === period
                    ? 'bg-white text-blue-600 shadow-sm ring-1 ring-black/5'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100',
                ]"
                @click="selectedPeriod = period"
              >
                {{ period === 'week' ? '周视图' : period === 'month' ? '月视图' : '季视图' }}
              </button>
            </div>
          </div>

          <div class="h-[350px] w-full relative">
            <!-- 图表容器 -->
            <QCTrendChart :period="selectedPeriod" :height="350" :auto-refresh="true" />
          </div>
        </div>

        <!-- 右侧: 侧边栏 (4 cols) -->
        <div class="lg:col-span-4 flex flex-col gap-5">
          <!-- 快捷操作 Grid -->
          <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h3 class="text-base font-bold text-slate-800 mb-4 flex items-center justify-between">
              <span>快捷入口</span>
            </h3>
            <div class="grid grid-cols-1 gap-3">
              <button
                v-for="action in quickActions"
                :key="action.action"
                class="flex items-center p-3 rounded-xl border border-slate-100 hover:border-blue-100 hover:shadow-sm transition-all duration-200 group text-left"
                @click="handleQuickAction(action.action)"
              >
                <div
                  :class="`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${action.bg}`"
                >
                  <component
                    :is="action.icon"
                    :class="`text-lg transition-colors ${action.color} group-hover:text-white`"
                  />
                </div>
                <div class="ml-3 flex-1">
                  <div
                    class="text-sm font-bold text-slate-700 group-hover:text-blue-600 transition-colors"
                  >
                    {{ action.title }}
                  </div>
                  <div class="text-xs text-slate-400">
                    {{ action.desc }}
                  </div>
                </div>
                <RightOutlined
                  class="text-slate-300 text-xs opacity-0 group-hover:opacity-100 transition-opacity -translate-x-2 group-hover:translate-x-0"
                />
              </button>
            </div>
          </div>

          <!-- 最新动态 Timeline -->
          <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-5 flex-1">
            <div class="flex items-center justify-between mb-5">
              <h3 class="text-base font-bold text-slate-800">最新动态</h3>
              <button class="text-xs text-blue-600 hover:underline">查看全部</button>
            </div>

            <div class="relative">
              <div class="absolute left-[19px] top-2 bottom-2 w-[2px] bg-slate-100" />

              <div
                v-for="(activity, index) in recentActivities"
                :key="activity.id"
                class="relative pl-10 pb-6 last:pb-0 group"
              >
                <div class="absolute left-0 top-0 w-10 h-10 flex items-center justify-center z-10">
                  <div
                    :class="`w-2.5 h-2.5 rounded-full border-2 border-white shadow-sm ring-1 ring-slate-100 ${index === 0 ? 'bg-blue-500 animate-pulse' : 'bg-slate-300 group-hover:bg-blue-400'}`"
                    class="transition-colors"
                  />
                </div>

                <div class="group-hover:bg-slate-50/80 rounded-xl p-2.5 -ml-2.5 transition-colors">
                  <div class="flex justify-between items-start mb-0.5">
                    <span class="text-xs font-bold text-slate-700">{{ activity.title }}</span>
                    <span class="text-[10px] text-slate-400 font-mono">{{ activity.time }}</span>
                  </div>
                  <p class="text-xs text-slate-500 leading-relaxed line-clamp-2">
                    {{ activity.description }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.font-sans {
  font-family:
    'Inter',
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    Oxygen,
    Ubuntu,
    Cantarell,
    'Open Sans',
    'Helvetica Neue',
    sans-serif;
}
</style>
