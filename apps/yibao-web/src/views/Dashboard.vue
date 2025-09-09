<template>
  <BasicLayout>
    <div data-testid="dashboard-container" class="min-h-screen bg-gray-50 relative">
      <div class="absolute inset-0 pointer-events-none overflow-hidden">
        <div class="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-gradient-to-br from-blue-100/40 via-cyan-50/30 to-green-50/20 blur-3xl"></div>
        <div class="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-gradient-to-tr from-green-100/30 via-blue-50/20 to-indigo-50/30 blur-3xl"></div>
      </div>

      <div class="relative z-10 p-8">
        <div class="mb-8">
          <div class="bg-gradient-to-r from-blue-500 via-blue-600 to-indigo-600 text-white p-8 rounded-2xl shadow-lg mb-8">
            <div class="flex justify-between items-start">
              <div>
                <div class="flex items-center gap-4 mb-4">
                  <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20">
                    <RobotOutlined class="text-2xl text-white" />
                  </div>
                  <div>
                    <h1 class="text-4xl font-bold mb-2">{{ greeting }}，{{ userName }}！</h1>
                    <p class="text-blue-100 text-lg">医保智能审核系统 · {{ userDepartment }}数据概览</p>
                    <div class="flex items-center mt-2 text-blue-200">
                      <ClockCircleOutlined class="mr-2" />
                      <span>{{ currentDate }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="flex space-x-4">
                <a-button @click="refreshData" :loading="refreshing" size="large" class="h-12 px-6 bg-white/10 border-white/30 text-white hover:bg-white/20 hover:border-white/50 backdrop-blur-sm">
                  <ReloadOutlined /> 刷新数据
                </a-button>
                <a-button type="primary" size="large" class="h-12 px-6 bg-white/20 border-white/30 text-white hover:bg-white/30 hover:border-white/50 backdrop-blur-sm">
                  <PlusOutlined /> 新增病案
                </a-button>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6 mb-8">
          <div v-for="card in dashboardCards" :key="card.title" class="group relative">
            <div class="relative rounded-2xl bg-white shadow-lg hover:shadow-xl border border-gray-100 p-6 hover:border-blue-200 transition-all duration-300 cursor-pointer group-hover:scale-105">
              <div class="flex items-start justify-between mb-4">
                <div class="w-14 h-14 rounded-2xl flex items-center justify-center shadow-sm" :style="{ background: `linear-gradient(135deg, ${card.color}15, ${card.color}25)` }">
                  <component :is="card.icon" :style="{ color: card.color }" class="text-2xl" />
                </div>
                <div v-if="card.change" class="flex items-center gap-1 bg-gray-50 px-2 py-1 rounded-lg">
                  <component :is="getTrendIcon(card.change.type)" :class="getTrendClass(card.change.type)" class="text-xs" />
                  <span :class="getTrendClass(card.change.type)" class="text-xs font-semibold">{{ card.change.value }}%</span>
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

        <div class="grid grid-cols-1 xl:grid-cols-3 gap-8">
          <div class="xl:col-span-2">
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
                <a-select v-model:value="selectedPeriod" style="width: 140px" size="large" class="custom-select" :options="periodOptions" />
              </div>
              <div class="bg-gray-50 rounded-xl p-6 border border-gray-100">
                <ViolationTrendsChart :days="30" :height="320" />
              </div>
            </div>

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

          <div class="space-y-8">
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
                <button v-for="action in quickActions" :key="action.action" @click="handleQuickAction(action.action)" class="group/btn relative p-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-blue-300 transition-all duration-300 hover:shadow-md">
                  <div class="flex flex-col items-center gap-3">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-300 group-hover/btn:scale-110" :style="{ background: `linear-gradient(135deg, ${action.color}15, ${action.color}25)` }">
                      <component :is="action.icon" :style="{ color: action.color }" class="text-xl" />
                    </div>
                    <span class="text-sm text-gray-700 group-hover/btn:text-gray-900 font-medium transition-colors duration-300">{{ action.title }}</span>
                  </div>
                </button>
              </div>
            </div>

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
                <button class="text-blue-600 hover:text-blue-700 text-sm font-medium transition-colors duration-300">查看全部</button>
              </div>
              <div class="space-y-4">
                <div v-for="activity in recentActivities" :key="activity.id" class="flex items-start gap-4 p-4 rounded-xl bg-gray-50 hover:bg-gray-100 border border-gray-100 hover:border-gray-200 transition-all duration-300">
                  <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" :style="{ background: `linear-gradient(135deg, ${activity.color}15, ${activity.color}25)` }">
                    <component :is="activity.icon" :style="{ color: activity.color }" class="text-lg" />
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
  </BasicLayout>
  </template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import QCTrendChart from '@/components/charts/QCTrendChart.vue'
import ViolationTrendsChart from '@/components/charts/ViolationTrendsChart.vue'
import { fetchDashboardStats, fetchViolationTrends, fetchTopRules } from '@/services/supabaseSdk'
import { useAuthStore } from '@/stores/auth'
import { ref, computed, onMounted } from 'vue'
import { ReloadOutlined, PlusOutlined, ArrowUpOutlined, ArrowDownOutlined, FileTextOutlined, ClockCircleOutlined, SyncOutlined, TrophyOutlined, CheckCircleOutlined, ThunderboltOutlined, SafetyCertificateOutlined, EyeOutlined, StarOutlined, RobotOutlined, BarChartOutlined, UploadOutlined, FileSearchOutlined, SettingOutlined, CalendarOutlined, DownloadOutlined, WarningOutlined } from '@ant-design/icons-vue'

const authStore = useAuthStore()
const userName = computed(() => authStore.user?.display_name || '用户')
const userDepartment = computed(() => authStore.user?.department || '全院')

const loading = ref(true)
const refreshing = ref(false)
const selectedPeriod = ref('month')
const periodOptions = [
  { value: 'week', label: '近一周' },
  { value: 'month', label: '近一月' },
  { value: 'quarter', label: '近三月' },
  { value: 'year', label: '近一年' }
]

const stats = ref({ totalRecords: 1247, pendingRecords: 23, analyzingRecords: 8, completedRecords: 1216, averageScore: 87.5, passRate: 94.2, todayUploads: 15 })
const serverStats = ref({ totalViolations: 0 })
const trends = ref<any[]>([])
const topRules = ref<any[]>([])

interface DashboardCard { title: string; value: string | number; change?: { value: number; type: 'increase' | 'decrease' }; icon: any; color: string }

const dashboardCards = computed<DashboardCard[]>(() => [
  { title: '总病案数', value: stats.value.totalRecords.toLocaleString(), change: { value: 12.5, type: 'increase' }, icon: FileTextOutlined, color: '#1890ff' },
  { title: '待分析', value: stats.value.pendingRecords, change: { value: 2.1, type: 'decrease' }, icon: ClockCircleOutlined, color: '#faad14' },
  { title: '分析中', value: stats.value.analyzingRecords, change: { value: 1.8, type: 'increase' }, icon: SyncOutlined, color: '#13c2c2' },
  { title: '平均评分', value: `${stats.value.averageScore}分`, change: { value: 3.2, type: 'increase' }, icon: TrophyOutlined, color: '#52c41a' },
  { title: '通过率', value: `${stats.value.passRate}%`, change: { value: 1.5, type: 'increase' }, icon: CheckCircleOutlined, color: '#722ed1' },
  { title: '今日违规', value: serverStats.value.totalViolations, icon: WarningOutlined, color: '#f5222d' }
])

const recentActivities = ref([
  { id: 1, type: 'upload', title: '新增病案 - 张三', description: '内科住院病案，等待质控分析', time: '2分钟前', icon: UploadOutlined, color: '#1890ff' },
  { id: 2, type: 'analysis', title: '质控分析完成 - 李四', description: '外科手术病案，评分92分', time: '15分钟前', icon: CheckCircleOutlined, color: '#52c41a' },
  { id: 3, type: 'review', title: '病案审核 - 王五', description: '妇产科病案需要进一步确认', time: '1小时前', icon: EyeOutlined, color: '#faad14' },
  { id: 4, type: 'system', title: '系统更新', description: '质控规则已更新，新增3条检查规则', time: '2小时前', icon: SettingOutlined, color: '#722ed1' },
  { id: 5, type: 'export', title: '数据导出完成', description: '本月质控报告已生成', time: '3小时前', icon: DownloadOutlined, color: '#13c2c2' }
])

const quickActions = [
  { title: '上传病案', description: '批量上传医疗病案文件', icon: UploadOutlined, color: '#06b6d4', action: 'upload' },
  { title: '质控分析', description: '执行AI智能质控分析', icon: ThunderboltOutlined, color: '#10b981', action: 'analyze' },
  { title: '生成报告', description: '导出质控统计报告', icon: FileSearchOutlined, color: '#f59e0b', action: 'report' },
  { title: '规则管理', description: '配置质控检查规则', icon: SettingOutlined, color: '#8b5cf6', action: 'rules' }
]

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 17) return '下午好'
  if (hour < 19) return '傍晚好'
  if (hour < 22) return '晚上好'
  return '深夜好'
})

const currentDate = computed(() => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]
  return `${year}年${month}月${day}日 ${weekday}`
})

function handleQuickAction(action: string) {}
function getTrendClass(type: 'increase' | 'decrease') { return type === 'increase' ? 'text-green-500' : 'text-red-500' }
function getTrendIcon(type: 'increase' | 'decrease') { return type === 'increase' ? ArrowUpOutlined : ArrowDownOutlined }

async function refreshData() {
  refreshing.value = true
  try {
    const s = await fetchDashboardStats()
    serverStats.value.totalViolations = s.totalViolations || 0
    trends.value = await fetchViolationTrends(30)
    topRules.value = await fetchTopRules(10)
    stats.value.todayUploads += Math.floor(Math.random() * 5)
  } finally {
    refreshing.value = false
  }
}

onMounted(async () => { try { await refreshData() } finally { loading.value = false } })
</script>



