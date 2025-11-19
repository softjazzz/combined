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
  CalendarOutlined,
  AppstoreOutlined,
  BulbOutlined
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
  <div class="min-h-screen bg-[#F8FAFC] p-4 lg:p-8 font-sans">
    <!-- 顶部欢迎 Banner -->
    <div class="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 to-indigo-700 text-white shadow-lg mb-8">
      <div class="absolute top-0 right-0 w-full h-full overflow-hidden pointer-events-none">
        <div class="absolute -top-24 -right-24 w-96 h-96 bg-white/10 rounded-full blur-3xl"></div>
        <div class="absolute top-1/2 right-10 w-64 h-64 bg-blue-400/20 rounded-full blur-2xl"></div>
      </div>
      
      <div class="relative z-10 px-8 py-10 flex flex-col md:flex-row justify-between items-center gap-6">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <span class="px-3 py-1 rounded-full bg-white/20 backdrop-blur-sm text-xs font-medium border border-white/10">
              {{ getCurrentDateTime() }}
            </span>
            <span class="px-3 py-1 rounded-full bg-green-400/20 text-green-100 text-xs font-medium border border-green-400/20 flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span>
              系统运行正常
            </span>
          </div>
          <h1 class="text-3xl font-bold tracking-tight mb-2">
            {{ getGreeting() }}，{{ authStore.userName }}
          </h1>
          <p class="text-blue-100 text-base max-w-xl">
            欢迎回到医疗质控平台。今日共有 <span class="text-white font-bold">{{ stats.todayUploads }}</span> 份新病历等待处理，系统已自动完成 <span class="text-white font-bold">{{ stats.completedRecords }}</span> 份病历的质控分析。
          </p>
        </div>
        
        <div class="flex items-center gap-4">
          <button 
            @click="refreshData"
            class="px-5 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 backdrop-blur-md text-white font-medium transition-all duration-200 border border-white/10 flex items-center gap-2"
          >
            <ReloadOutlined :class="{ 'animate-spin': refreshing }" />
            <span>刷新数据</span>
          </button>
          <button 
            @click="handleQuickAction('analyze')"
            class="px-6 py-2.5 rounded-xl bg-white text-blue-600 hover:bg-blue-50 font-bold shadow-lg shadow-blue-900/20 transition-all duration-200 flex items-center gap-2 transform hover:scale-105 active:scale-95"
          >
            <ThunderboltOutlined />
            <span>开始质控</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 核心指标卡片 (Bento Grid) -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div v-for="(card, index) in dashboardCards.slice(0, 4)" :key="card.title" 
        class="group bg-white rounded-2xl p-6 border border-slate-100 shadow-sm hover:shadow-md transition-all duration-300 relative overflow-hidden"
      >
        <div class="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-transparent to-slate-50 rounded-bl-full -mr-4 -mt-4 transition-transform group-hover:scale-110"></div>
        
        <div class="relative z-10">
          <div class="flex justify-between items-start mb-4">
            <div class="w-12 h-12 rounded-xl flex items-center justify-center" :style="{ backgroundColor: `${card.color}15` }">
              <component :is="card.icon" :style="{ color: card.color, fontSize: '24px' }" />
            </div>
            <div v-if="card.change" class="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-lg bg-slate-50">
              <component :is="getTrendIcon(card.change.type)" :class="getTrendClass(card.change.type)" />
              <span :class="getTrendClass(card.change.type)">{{ card.change.value }}%</span>
            </div>
          </div>
          
          <div class="space-y-1">
            <div class="text-slate-500 text-sm font-medium">{{ card.title }}</div>
            <div class="text-2xl font-bold text-slate-800 tracking-tight">{{ card.value }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 (Grid Layout) -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8">
      
      <!-- 左侧主栏 (8 cols) -->
      <div class="lg:col-span-8 space-y-8">
        
        <!-- 趋势图表 -->
        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2">
                <BarChartOutlined class="text-blue-500" />
                质控趋势分析
              </h3>
              <p class="text-slate-400 text-xs mt-1">过去一段时间的质控评分与病历数量趋势</p>
            </div>
            <div class="flex bg-slate-100 rounded-lg p-1">
              <button 
                v-for="period in ['week', 'month', 'quarter']" 
                :key="period"
                @click="selectedPeriod = period"
                :class="[
                  'px-3 py-1 text-xs font-medium rounded-md transition-all',
                  selectedPeriod === period ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
                ]"
              >
                {{ period === 'week' ? '周' : period === 'month' ? '月' : '季' }}
              </button>
            </div>
          </div>
          <div class="h-80">
            <QCTrendChart :period="selectedPeriod" :height="320" :auto-refresh="true" />
          </div>
        </div>

        <!-- 最新活动列表 -->
        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="text-lg font-bold text-slate-800 flex items-center gap-2">
              <ClockCircleOutlined class="text-blue-500" />
              最近动态
            </h3>
            <button class="text-blue-600 text-sm font-medium hover:text-blue-700 transition-colors">查看全部</button>
          </div>
          <div class="space-y-4">
            <div v-for="(activity, index) in recentActivities" :key="activity.id" class="flex items-start gap-4 group">
              <div class="relative">
                <div class="w-10 h-10 rounded-full flex items-center justify-center z-10 relative" :style="{ backgroundColor: `${activity.color}15` }">
                  <component :is="activity.icon" :style="{ color: activity.color }" />
                </div>
                <div v-if="index !== recentActivities.length - 1" class="absolute top-10 left-1/2 -translate-x-1/2 w-0.5 h-full bg-slate-100 -z-0"></div>
              </div>
              <div class="flex-1 pb-4 border-b border-slate-50 group-last:border-0">
                <div class="flex justify-between items-start">
                  <div>
                    <h4 class="text-sm font-bold text-slate-800">{{ activity.title }}</h4>
                    <p class="text-slate-500 text-xs mt-1">{{ activity.description }}</p>
                  </div>
                  <span class="text-xs text-slate-400 whitespace-nowrap">{{ activity.time }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- 右侧边栏 (4 cols) -->
      <div class="lg:col-span-4 space-y-8">
        
        <!-- AI 智能洞察 -->
        <div class="bg-gradient-to-br from-indigo-50 to-white rounded-2xl border border-indigo-100 shadow-sm p-6">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <RobotOutlined class="text-xl" />
            </div>
            <div>
              <h3 class="text-lg font-bold text-slate-800">AI 智能洞察</h3>
              <p class="text-xs text-indigo-600 font-medium">基于大模型的实时分析</p>
            </div>
          </div>
          
          <div class="space-y-3">
            <div class="bg-white p-4 rounded-xl border border-indigo-50 shadow-sm">
              <div class="flex items-start gap-3">
                <CheckCircleOutlined class="text-green-500 mt-1" />
                <div>
                  <h4 class="text-sm font-bold text-slate-700">质控通过率提升</h4>
                  <p class="text-xs text-slate-500 mt-1 leading-relaxed">本周质控通过率较上周提升 3.2%，主要改善在病程记录完整性方面。</p>
                </div>
              </div>
            </div>
            
            <div class="bg-white p-4 rounded-xl border border-indigo-50 shadow-sm">
              <div class="flex items-start gap-3">
                <ExclamationCircleOutlined class="text-amber-500 mt-1" />
                <div>
                  <h4 class="text-sm font-bold text-slate-700">关注重点</h4>
                  <p class="text-xs text-slate-500 mt-1 leading-relaxed">内科病案中诊断一致性问题较为突出，建议加强相关培训。</p>
                </div>
              </div>
            </div>

            <div class="bg-white p-4 rounded-xl border border-indigo-50 shadow-sm">
              <div class="flex items-start gap-3">
                <BulbOutlined class="text-blue-500 mt-1" />
                <div>
                  <h4 class="text-sm font-bold text-slate-700">优化建议</h4>
                  <p class="text-xs text-slate-500 mt-1 leading-relaxed">建议启用新的AI辅助诊断模块，预计可提升诊断准确率15%。</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 快捷入口 -->
        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
            <AppstoreOutlined class="text-blue-500" />
            快捷功能
          </h3>
          <div class="grid grid-cols-2 gap-4">
            <button 
              v-for="action in quickActions" 
              :key="action.action"
              @click="handleQuickAction(action.action)"
              class="flex flex-col items-center justify-center p-4 rounded-xl bg-slate-50 hover:bg-blue-50 border border-transparent hover:border-blue-100 transition-all duration-200 group"
            >
              <div class="w-10 h-10 rounded-full flex items-center justify-center mb-3 transition-transform group-hover:scale-110 bg-white shadow-sm">
                <component :is="action.icon" :style="{ color: action.color }" class="text-lg" />
              </div>
              <span class="text-xs font-medium text-slate-600 group-hover:text-blue-600">{{ action.title }}</span>
            </button>
          </div>
        </div>

        <!-- 部门分布 (Optional) -->
        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6">
          <h3 class="text-lg font-bold text-slate-800 mb-4">病案来源分布</h3>
          <div class="space-y-3">
            <div v-for="dept in departmentData" :key="dept.name" class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: dept.color }"></div>
                <span class="text-xs text-slate-600">{{ dept.name }}</span>
              </div>
              <div class="flex items-center gap-2 w-1/2">
                <div class="h-1.5 rounded-full bg-slate-100 flex-1 overflow-hidden">
                  <div class="h-full rounded-full" :style="{ width: `${dept.value}%`, backgroundColor: dept.color }"></div>
                </div>
                <span class="text-xs font-bold text-slate-700 w-6 text-right">{{ dept.value }}%</span>
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