<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import QCTrendChart from '@/components/charts/QCTrendChart.vue'
import type { DashboardCard } from '@/types'
import {
  ReloadOutlined,
  PlusOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  FileTextOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  EyeOutlined,
  StarOutlined,
  RobotOutlined,
  BarChartOutlined,
  UploadOutlined,
  FileSearchOutlined,
  SettingOutlined,
  CalendarOutlined
} from '@ant-design/icons-vue'

// 状态管理
const authStore = useAuthStore()

// 页面状态
const loading = ref(true)
const refreshing = ref(false)
const selectedPeriod = ref('month')

// 统计数据
const stats = ref({
  totalRecords: 1247,
  pendingRecords: 23,
  analyzingRecords: 8,
  completedRecords: 1216,
  averageScore: 87.5,
  passRate: 94.2,
  todayUploads: 15,
  weeklyTrend: '+12.5%'
})

// 卡片数据
const dashboardCards = computed<DashboardCard[]>(() => [
  {
    title: '总病案数',
    value: stats.value.totalRecords.toLocaleString(),
    change: {
      value: 12.5,
      type: 'increase'
    },
    icon: FileTextOutlined,
    color: '#1890ff'
  },
  {
    title: '待分析',
    value: stats.value.pendingRecords,
    change: {
      value: 2.1,
      type: 'decrease'
    },
    icon: ClockCircleOutlined,
    color: '#faad14'
  },
  {
    title: '分析中',
    value: stats.value.analyzingRecords,
    change: {
      value: 1.8,
      type: 'increase'
    },
    icon: SyncOutlined,
    color: '#13c2c2'
  },
  {
    title: '平均评分',
    value: `${stats.value.averageScore}分`,
    change: {
      value: 3.2,
      type: 'increase'
    },
    icon: TrophyOutlined,
    color: '#52c41a'
  },
  {
    title: '通过率',
    value: `${stats.value.passRate}%`,
    change: {
      value: 1.5,
      type: 'increase'
    },
    icon: CheckCircleOutlined,
    color: '#722ed1'
  },
  {
    title: '今日新增',
    value: stats.value.todayUploads,
    change: {
      value: 8.3,
      type: 'increase'
    },
    icon: PlusOutlined,
    color: '#f5222d'
  }
])

// 质控趋势图表数据
const qcTrendData = ref({
  labels: ['1月', '2月', '3月', '4月', '5月', '6月'],
  datasets: [
    {
      label: '病案数量',
      data: [120, 190, 300, 500, 200, 300],
      borderColor: '#1890ff',
      backgroundColor: 'rgba(24, 144, 255, 0.1)',
      tension: 0.4
    },
    {
      label: '平均评分',
      data: [85, 87, 89, 88, 90, 88],
      borderColor: '#52c41a',
      backgroundColor: 'rgba(82, 196, 26, 0.1)',
      tension: 0.4,
      yAxisID: 'y1'
    }
  ]
})

// 部门分布数据
const departmentData = ref([
  { name: '内科', value: 35, color: '#1890ff' },
  { name: '外科', value: 28, color: '#52c41a' },
  { name: '妇产科', value: 18, color: '#faad14' },
  { name: '儿科', value: 12, color: '#f5222d' },
  { name: '其他', value: 7, color: '#722ed1' }
])

// 最新活动数据
const recentActivities = ref([
  {
    id: 1,
    type: 'upload',
    title: '新增病案 - 张三',
    description: '内科住院病案，等待质控分析',
    time: '2分钟前',
    icon: 'FileAddOutlined',
    color: '#1890ff'
  },
  {
    id: 2,
    type: 'analysis',
    title: '质控分析完成 - 李四',
    description: '外科手术病案，评分92分',
    time: '15分钟前',
    icon: 'CheckCircleOutlined',
    color: '#52c41a'
  },
  {
    id: 3,
    type: 'review',
    title: '病案审核 - 王五',
    description: '妇产科病案需要进一步确认',
    time: '1小时前',
    icon: 'ExclamationCircleOutlined',
    color: '#faad14'
  },
  {
    id: 4,
    type: 'system',
    title: '系统更新',
    description: '质控规则已更新，新增3条检查规则',
    time: '2小时前',
    icon: 'ToolOutlined',
    color: '#722ed1'
  },
  {
    id: 5,
    type: 'export',
    title: '数据导出完成',
    description: '本月质控报告已生成',
    time: '3小时前',
    icon: 'DownloadOutlined',
    color: '#13c2c2'
  }
])

// 快捷操作
const quickActions = [
  {
    title: '上传病案',
    description: '批量上传医疗病案文件',
    icon: UploadOutlined,
    color: '#06b6d4',
    action: 'upload'
  },
  {
    title: '质控分析',
    description: '执行AI智能质控分析',
    icon: ThunderboltOutlined,
    color: '#10b981',
    action: 'analyze'
  },
  {
    title: '生成报告',
    description: '导出质控统计报告',
    icon: FileSearchOutlined,
    color: '#f59e0b',
    action: 'report'
  },
  {
    title: '规则管理',
    description: '配置质控检查规则',
    icon: SettingOutlined,
    color: '#8b5cf6',
    action: 'rules'
  }
]

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
  switch (action) {
    case 'upload':
      // TODO: 跳转到上传页面
      break
    case 'analyze':
      // TODO: 跳转到分析页面
      break
    case 'report':
      // TODO: 跳转到报告页面
      break
    case 'rules':
      // TODO: 跳转到规则管理页面
      break
  }
}

// 刷新数据
const refreshData = async () => {
  refreshing.value = true
  try {
    // TODO: 调用API刷新数据
    await new Promise(resolve => setTimeout(resolve, 1000))
    // 模拟数据更新
    stats.value.todayUploads += Math.floor(Math.random() * 5)
  } finally {
    refreshing.value = false
  }
}

// 获取卡片样式
const getCardClass = (color: string) => {
  return `border-l-4 hover:shadow-lg transition-all duration-300 cursor-pointer`
}

// 获取变化趋势样式
const getTrendClass = (type: 'increase' | 'decrease') => {
  return type === 'increase' ? 'text-green-500' : 'text-red-500'
}

// 获取变化趋势图标
const getTrendIcon = (type: 'increase' | 'decrease') => {
  return type === 'increase' ? ArrowUpOutlined : ArrowDownOutlined
}

// 获取当前日期时间
const getCurrentDateTime = () => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]

  return `${year}年${month}月${day}日 ${weekday}`
}

// 组件挂载时获取数据
onMounted(async () => {
  try {
    // TODO: 获取真实数据
    await new Promise(resolve => setTimeout(resolve, 800))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div data-testid="dashboard-container" class="min-h-screen bg-gray-50 relative">
    <!-- 医疗主题背景装饰 -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <!-- 医疗蓝色渐变背景 -->
      <div class="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-gradient-to-br from-blue-100/40 via-cyan-50/30 to-green-50/20 blur-3xl"></div>
      <div class="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-gradient-to-tr from-green-100/30 via-blue-50/20 to-indigo-50/30 blur-3xl"></div>

      <!-- 医疗十字图案 -->
      <div class="absolute top-20 right-20 w-8 h-8 opacity-5">
        <div class="absolute inset-0 bg-blue-500 rounded-sm transform rotate-45"></div>
        <div class="absolute top-2 left-2 w-4 h-4 bg-white rounded-sm"></div>
      </div>
      <div class="absolute bottom-32 left-32 w-6 h-6 opacity-5">
        <div class="absolute inset-0 bg-green-500 rounded-sm transform rotate-45"></div>
        <div class="absolute top-1.5 left-1.5 w-3 h-3 bg-white rounded-sm"></div>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="relative z-10 p-8">
      <!-- 顶部欢迎区域 -->
      <div class="mb-8">
        <div class="bg-gradient-to-r from-blue-500 via-blue-600 to-indigo-600 text-white p-8 rounded-2xl shadow-lg mb-8">
          <div class="flex justify-between items-start">
            <div>
              <div class="flex items-center gap-4 mb-4">
                <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20">
                  <RobotOutlined class="text-2xl text-white" />
                </div>
                <div>
                  <h1 class="text-4xl font-bold mb-2">
                    {{ getGreeting() }}，{{ authStore.userName }}！
                  </h1>
                  <p class="text-blue-100 text-lg">
                    医疗AI质控系统 · {{ authStore.userDepartment || '全院' }}数据概览
                  </p>
                  <div class="flex items-center mt-2 text-blue-200">
                    <ClockCircleOutlined class="mr-2" />
                    <span>{{ getCurrentDateTime() }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="flex space-x-4">
              <a-button
                @click="refreshData"
                :loading="refreshing"
                data-testid="refresh-button"
                size="large"
                class="h-12 px-6 bg-white/10 border-white/30 text-white hover:bg-white/20 hover:border-white/50 backdrop-blur-sm"
              >
                <ReloadOutlined />
                刷新数据
              </a-button>
              <a-button
                type="primary"
                size="large"
                class="h-12 px-6 bg-white/20 border-white/30 text-white hover:bg-white/30 hover:border-white/50 backdrop-blur-sm"
              >
                <PlusOutlined />
                新增病案
              </a-button>
            </div>
        </div>
      </div>

      <!-- 统计卡片网格 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 mb-8">
        <div
          v-for="card in dashboardCards"
          :key="card.title"
          data-testid="stat-card"
          class="group relative"
        >
          <!-- 卡片主体 -->
          <div class="relative rounded-2xl bg-white shadow-lg hover:shadow-xl border border-gray-100 p-6 hover:border-blue-200 transition-all duration-300 cursor-pointer group-hover:scale-105">
            <div class="flex items-start justify-between mb-4">
              <div
                class="w-14 h-14 rounded-2xl flex items-center justify-center shadow-sm"
                :style="{ background: `linear-gradient(135deg, ${card.color}15, ${card.color}25)` }"
              >
                <component
                  :is="card.icon"
                  :style="{ color: card.color }"
                  class="text-2xl"
                />
              </div>
              <div v-if="card.change" class="flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-lg">
                <component
                  :is="getTrendIcon(card.change.type)"
                  :class="getTrendClass(card.change.type)"
                  data-testid="trend-icon"
                  class="text-xs"
                />
                <span :class="getTrendClass(card.change.type)" class="text-xs font-semibold">
                  {{ card.change.value }}%
                </span>
              </div>
            </div>

            <div>
              <p class="text-gray-600 text-sm mb-2 font-medium">{{ card.title }}</p>
              <p class="text-3xl font-bold text-gray-800 mb-1">{{ card.value }}</p>
              <p class="text-gray-500 text-xs">较上周</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 主要内容区域 -->
      <div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <!-- 左侧：质控趋势分析 -->
        <div class="xl:col-span-2">
          <!-- 质控趋势图表卡片 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8 hover:shadow-xl transition-shadow duration-300">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/20 flex items-center justify-center">
                  <BarChartOutlined class="text-blue-600 text-xl" />
                </div>
                <div>
                  <h3 class="text-xl font-bold text-gray-800">质控趋势分析</h3>
                  <p class="text-gray-600 text-sm">AI驱动的实时质控数据分析</p>
                </div>
              </div>
              <a-select
                v-model:value="selectedPeriod"
                style="width: 140px"
                data-testid="period-select"
                size="large"
                class="custom-select"
                :options="[
                  { value: 'week', label: '近一周' },
                  { value: 'month', label: '近一月' },
                  { value: 'quarter', label: '近三月' },
                  { value: 'year', label: '近一年' }
                ]"
              />
            </div>

            <div class="bg-gray-50 rounded-xl p-6 border border-gray-100">
              <QCTrendChart
                :period="selectedPeriod"
                :height="320"
                :auto-refresh="true"
              />
            </div>
          </div>

          <!-- AI质控洞察 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 hover:shadow-xl transition-shadow duration-300">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500/10 to-emerald-500/20 flex items-center justify-center">
                <ThunderboltOutlined class="text-green-600 text-xl" />
              </div>
              <div>
                <h3 class="text-xl font-bold text-gray-800">AI质控洞察</h3>
                <p class="text-gray-600 text-sm">智能分析与建议</p>
              </div>
            </div>

            <div class="space-y-4">
              <div class="bg-green-50 border border-green-200 rounded-xl p-4">
                <div class="flex items-start gap-3">
                  <div class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                    <CheckCircleOutlined class="text-green-600 text-lg" />
                  </div>
                  <div>
                    <h4 class="text-gray-800 font-semibold mb-2">质控通过率提升</h4>
                    <p class="text-gray-600 text-sm">本周质控通过率较上周提升3.2%，主要改善在病程记录完整性方面</p>
                  </div>
                </div>
              </div>

              <div class="bg-amber-50 border border-amber-200 rounded-xl p-4">
                <div class="flex items-start gap-3">
                  <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                    <EyeOutlined class="text-amber-600 text-lg" />
                  </div>
                  <div>
                    <h4 class="text-gray-800 font-semibold mb-2">关注重点</h4>
                    <p class="text-gray-600 text-sm">内科病案中诊断一致性问题较为突出，建议加强相关培训</p>
                  </div>
                </div>
              </div>

              <div class="bg-blue-50 border border-blue-200 rounded-xl p-4">
                <div class="flex items-start gap-3">
                  <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                    <StarOutlined class="text-blue-600 text-lg" />
                  </div>
                  <div>
                    <h4 class="text-gray-800 font-semibold mb-2">优化建议</h4>
                    <p class="text-gray-600 text-sm">建议启用新的AI辅助诊断模块，预计可提升诊断准确率15%</p>
                  </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：快捷操作和活动 -->
        <div class="space-y-8">
          <!-- 快捷操作 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/10 to-purple-500/20 flex items-center justify-center">
                <ThunderboltOutlined class="text-indigo-600 text-xl" />
              </div>
              <div>
                <h3 class="text-xl font-bold text-gray-800">快捷操作</h3>
                <p class="text-gray-600 text-sm">常用功能快速入口</p>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4">
              <button
                v-for="action in quickActions"
                :key="action.action"
                :data-testid="`quick-action-${action.action}`"
                data-testid="quick-action"
                @click="handleQuickAction(action.action)"
                class="group/btn relative p-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-blue-300 transition-all duration-300 hover:shadow-md"
              >
                <div class="flex flex-col items-center gap-3">
                  <div
                    class="w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 group-hover/btn:scale-110"
                    :style="{ background: `linear-gradient(135deg, ${action.color}15, ${action.color}25)` }"
                  >
                    <component
                      :is="action.icon"
                      :style="{ color: action.color }"
                      class="text-xl"
                    />
                  </div>
                  <span class="text-sm text-gray-700 group-hover/btn:text-gray-900 font-medium transition-colors duration-300">
                    {{ action.title }}
                  </span>
                </div>
              </button>
            </div>
          </div>

          <!-- 最新活动 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/10 to-pink-500/20 flex items-center justify-center">
                  <SafetyCertificateOutlined class="text-purple-600 text-xl" />
                </div>
                <div>
                  <h3 class="text-xl font-bold text-gray-800">最新活动</h3>
                  <p class="text-gray-600 text-sm">系统动态与通知</p>
                </div>
              </div>
              <button class="text-blue-600 hover:text-blue-700 text-sm font-medium transition-colors duration-300">
                查看全部
              </button>
            </div>

            <div class="space-y-4">
              <div
                v-for="activity in recentActivities"
                :key="activity.id"
                class="flex items-start gap-4 p-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-100 hover:border-gray-200 transition-all duration-300"
              >
                <div
                  class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                  :style="{ background: `linear-gradient(135deg, ${activity.color}15, ${activity.color}25)` }"
                >
                  <component
                    :is="activity.icon"
                    :style="{ color: activity.color }"
                    class="text-lg"
                  />
                </div>
                <div class="flex-1 min-w-0">
                  <h5 class="text-gray-800 font-semibold mb-1 truncate">{{ activity.title }}</h5>
                  <p class="text-gray-600 text-sm mb-2 line-clamp-2">{{ activity.description }}</p>
                  <span class="text-gray-500 text-xs">{{ activity.time }}</span>
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
/* 现代化医疗AI系统样式 - 明亮主题 */

/* 动画效果 */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.4;
  }
  50% {
    opacity: 0.8;
  }
}

/* 自定义选择器样式 */
:deep(.custom-select .ant-select-selector) {
  background: white !important;
  border: 1px solid #e5e7eb !important;
  color: #374151 !important;
  border-radius: 0.75rem !important;
}

:deep(.custom-select .ant-select-arrow) {
  color: #6b7280 !important;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
}

:deep(.custom-select.ant-select-focused .ant-select-selector) {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
}

/* 按钮样式覆盖 */
:deep(.ant-btn) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border-radius: 0.75rem;
  font-weight: 500;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .xl\\:col-span-2 {
    grid-column: span 1;
  }
}

/* 文本截断 */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f3f4f6;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}

/* 医疗主题装饰元素 */
.medical-cross {
  position: relative;
}

.medical-cross::before,
.medical-cross::after {
  content: '';
  position: absolute;
  background: currentColor;
}

.medical-cross::before {
  width: 100%;
  height: 20%;
  top: 40%;
}

.medical-cross::after {
  height: 100%;
  width: 20%;
  left: 40%;
}
</style>