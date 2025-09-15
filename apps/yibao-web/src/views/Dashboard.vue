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
                    <p class="text-blue-100 text-lg">智慧医保质控系统 · {{ userDepartment }}审核概览</p>
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
                  <PlusOutlined /> 新增审核
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
            <!-- 测试病历管理模块 -->
            <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8 hover:shadow-xl transition-shadow duration-300">
              <div class="flex items-center justify-between mb-6">
                <div class="flex items-center gap-4">
                  <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500/10 to-green-500/20 flex items-center justify-center">
                    <FileTextOutlined class="text-emerald-600 text-xl" />
                  </div>
                  <div>
                    <h3 class="text-xl font-bold text-gray-800">测试病历管理</h3>
                    <p class="text-gray-600 text-sm">医保质控测试病历数据管理</p>
                  </div>
                </div>
                <div class="flex gap-2">
                  <a-button type="primary" size="small" @click="handleCreateRecord">
                    <PlusOutlined /> 新建病历
                  </a-button>
                  <a-button size="small" @click="handleImportRecords">
                    <UploadOutlined /> 批量导入
                  </a-button>
                </div>
              </div>

              <!-- 病历统计卡片 -->
              <div class="grid grid-cols-4 gap-4 mb-6">
                <div class="bg-blue-50 rounded-lg p-4 border border-blue-100">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-blue-600 text-sm font-medium">总病历数</p>
                      <p class="text-2xl font-bold text-blue-700">{{ medicalRecordsStats.total }}</p>
                    </div>
                    <FileTextOutlined class="text-blue-500 text-xl" />
                  </div>
                </div>
                <div class="bg-amber-50 rounded-lg p-4 border border-amber-100">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-amber-600 text-sm font-medium">本月新增</p>
                      <p class="text-2xl font-bold text-amber-700">{{ medicalRecordsStats.thisMonth }}</p>
                    </div>
                    <CalendarOutlined class="text-amber-500 text-xl" />
                  </div>
                </div>
                <div class="bg-green-50 rounded-lg p-4 border border-green-100">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-green-600 text-sm font-medium">待审核</p>
                      <p class="text-2xl font-bold text-green-700">{{ medicalRecordsStats.pending }}</p>
                    </div>
                    <ClockCircleOutlined class="text-green-500 text-xl" />
                  </div>
                </div>
                <div class="bg-purple-50 rounded-lg p-4 border border-purple-100">
                  <div class="flex items-center justify-between">
                    <div>
                      <p class="text-purple-600 text-sm font-medium">已关联规则</p>
                      <p class="text-2xl font-bold text-purple-700">{{ medicalRecordsStats.withRules }}</p>
                    </div>
                    <SettingOutlined class="text-purple-500 text-xl" />
                  </div>
                </div>
              </div>

              <!-- 病历列表 -->
              <TestMedicalRecordsList
                :records="medicalRecords"
                :loading="recordsLoading"
                @view-record="handleViewRecord"
                @edit-record="handleEditRecord"
                @delete-record="handleDeleteRecord"
                @analyze-record="handleAnalyzeRecord"
              />
            </div>

            <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-8 hover:shadow-xl transition-shadow duration-300">
              <div class="flex items-center justify-between mb-6">
                <div class="flex items-center gap-4">
                  <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/20 flex items-center justify-center">
                    <BarChartOutlined class="text-blue-600 text-xl" />
                  </div>
                  <div>
                    <h3 class="text-xl font-bold text-gray-800">医保违规趋势分析</h3>
                    <p class="text-gray-600 text-sm">AI驱动的医保审核数据分析</p>
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
                  <h3 class="text-xl font-bold text-gray-800">AI医保审核洞察</h3>
                  <p class="text-gray-600 text-sm">智能医保违规分析与建议</p>
                </div>
              </div>
              <div class="space-y-4">
                <div class="bg-green-50 border border-green-200 rounded-xl p-4">
                  <div class="flex items-start gap-3">
                    <div class="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
                      <CheckCircleOutlined class="text-green-600 text-lg" />
                    </div>
                    <div>
                      <h4 class="text-gray-800 font-semibold mb-2">医保审核通过率提升</h4>
                      <p class="text-gray-600 text-sm">本周医保审核通过率较上周提升3.2%，主要改善在费用合理性审核方面</p>
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
                      <p class="text-gray-600 text-sm">药品费用超标问题较为突出，建议加强合理用药审核培训</p>
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
                      <p class="text-gray-600 text-sm">建议启用智能医保规则引擎，预计可提升违规识别准确率15%</p>
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

import ViolationTrendsChart from '@/components/charts/ViolationTrendsChart.vue'
import TestMedicalRecordsList from '@/components/medical-records/TestMedicalRecordsList.vue'
import { fetchDashboardStats, fetchViolationTrends, fetchTopRules } from '@/services/supabaseSdk'
import { getMedicalRecordStats } from '@/api/medical-records'
import { useAuthStore } from '@/stores/auth'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined, PlusOutlined, ArrowUpOutlined, ArrowDownOutlined, FileTextOutlined, ClockCircleOutlined, SyncOutlined, TrophyOutlined, CheckCircleOutlined, ThunderboltOutlined, SafetyCertificateOutlined, EyeOutlined, StarOutlined, RobotOutlined, BarChartOutlined, UploadOutlined, FileSearchOutlined, SettingOutlined, CalendarOutlined, DownloadOutlined, WarningOutlined } from '@ant-design/icons-vue'

// 测试病历相关类型定义
interface TestMedicalRecord {
  id: string
  name: string
  patient_name: string
  patient_id: string
  department: string
  record_type: string
  disease_type: string
  complexity_level: string
  status: 'draft' | 'pending' | 'analyzing' | 'completed' | 'failed'
  qc_score?: number
  expected_grade?: string
  expected_score?: number
  content: string
  created_at: string
  updated_at: string
  created_by: string
  tags?: string[]
  medical_insurance_type?: string
  cost_amount?: number
  violation_risk?: 'low' | 'medium' | 'high'
}

const authStore = useAuthStore()
const router = useRouter()
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

const stats = ref({ totalRecords: 1247, pendingRecords: 23, analyzingRecords: 8, completedRecords: 1216, averageScore: 12.8, passRate: 94.2, todayUploads: 15 })
const serverStats = ref({ totalViolations: 0 })
const trends = ref<any[]>([])
const topRules = ref<any[]>([])

// 测试病历管理相关数据
const recordsLoading = ref(false)
const medicalRecords = ref<TestMedicalRecord[]>([])
const medicalRecordsStats = ref({
  total: 156,
  thisMonth: 23,
  pending: 5,
  withRules: 89
})

// 医保病历统计数据
const medicalRecordStats = ref({
  totalRecords: 0,
  pendingReview: 0,
  approvedRecords: 0,
  violationCount: 0
})

interface DashboardCard { title: string; value: string | number; change?: { value: number; type: 'increase' | 'decrease' }; icon: any; color: string }

const dashboardCards = computed<DashboardCard[]>(() => [
  { title: '医保案例数', value: stats.value.totalRecords.toLocaleString(), change: { value: 12.5, type: 'increase' }, icon: FileTextOutlined, color: '#1890ff' },
  { title: '待审核', value: stats.value.pendingRecords, change: { value: 2.1, type: 'decrease' }, icon: ClockCircleOutlined, color: '#faad14' },
  { title: '审核中', value: stats.value.analyzingRecords, change: { value: 1.8, type: 'increase' }, icon: SyncOutlined, color: '#13c2c2' },
  { title: '审核通过率', value: `${stats.value.passRate}%`, change: { value: 3.2, type: 'increase' }, icon: CheckCircleOutlined, color: '#52c41a' },
  { title: '费用核减率', value: `${stats.value.averageScore}%`, change: { value: 1.5, type: 'increase' }, icon: TrophyOutlined, color: '#722ed1' },
  { title: '今日违规', value: serverStats.value.totalViolations, icon: WarningOutlined, color: '#f5222d' }
])

const recentActivities = ref([
  { id: 1, type: 'upload', title: '新增医保案例 - 张三', description: '内科住院费用，等待医保审核', time: '2分钟前', icon: UploadOutlined, color: '#1890ff' },
  { id: 2, type: 'analysis', title: '医保审核完成 - 李四', description: '外科手术费用，审核通过', time: '15分钟前', icon: CheckCircleOutlined, color: '#52c41a' },
  { id: 3, type: 'review', title: '违规案例审核 - 王五', description: '药品费用超标，需要进一步确认', time: '1小时前', icon: EyeOutlined, color: '#faad14' },
  { id: 4, type: 'system', title: '医保规则更新', description: '医保审核规则已更新，新增3条检查规则', time: '2小时前', icon: SettingOutlined, color: '#722ed1' },
  { id: 5, type: 'export', title: '医保报告导出完成', description: '本月医保审核报告已生成', time: '3小时前', icon: DownloadOutlined, color: '#13c2c2' }
])

const quickActions = [
  { title: '上传费用', description: '批量上传医保费用数据', icon: UploadOutlined, color: '#06b6d4', action: 'upload' },
  { title: '医保审核', description: '执行AI智能医保审核', icon: ThunderboltOutlined, color: '#10b981', action: 'analyze' },
  { title: '生成报告', description: '导出医保审核报告', icon: FileSearchOutlined, color: '#f59e0b', action: 'report' },
  { title: '规则管理', description: '配置医保审核规则', icon: SettingOutlined, color: '#8b5cf6', action: 'rules' }
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

function handleQuickAction(action: string) {
  console.log('Quick action:', action)
  // TODO: 实现快捷操作功能
}
function getTrendClass(type: 'increase' | 'decrease') { return type === 'increase' ? 'text-green-500' : 'text-red-500' }
function getTrendIcon(type: 'increase' | 'decrease') { return type === 'increase' ? ArrowUpOutlined : ArrowDownOutlined }

// 测试病历管理方法
function handleCreateRecord() {
  router.push('/medical-records/create')
}

function handleImportRecords() {
  message.info('批量导入功能开发中...')
}

function handleViewRecord(record: TestMedicalRecord) {
  router.push(`/medical-records/${record.id}`)
}

function handleEditRecord(record: TestMedicalRecord) {
  router.push(`/medical-records/${record.id}/edit`)
}

function handleDeleteRecord(record: TestMedicalRecord) {
  message.info(`删除病历: ${record.name}`)
}

function handleAnalyzeRecord(record: TestMedicalRecord) {
  message.info(`分析病历: ${record.name}`)
}

// 加载测试病历数据
async function loadMedicalRecords() {
  recordsLoading.value = true
  try {
    // 模拟API调用，实际应该调用后端接口
    await new Promise(resolve => setTimeout(resolve, 1000))

    // 模拟数据
    medicalRecords.value = [
      {
        id: 'LLM_1756801551524',
        name: '张伟住院病历',
        patient_name: '张伟',
        patient_id: 'P001',
        department: '外二科',
        record_type: '住院记录',
        disease_type: '心血管疾病',
        complexity_level: '中等',
        status: 'completed',
        qc_score: 85,
        expected_grade: 'A',
        expected_score: 90,
        content: '患者张伟，男，45岁，因胸痛3天入院...',
        created_at: '2025-05-02 16:25',
        updated_at: '2025-05-02 18:30',
        created_by: '质控医师',
        tags: ['心血管', '住院'],
        medical_insurance_type: '职工医保',
        cost_amount: 15680.50,
        violation_risk: 'low'
      },
      {
        id: 'TEST001',
        name: '测试病历001',
        patient_name: '测试患者',
        patient_id: 'P002',
        department: '内科',
        record_type: '门诊记录',
        disease_type: '呼吸系统',
        complexity_level: '简单',
        status: 'pending',
        content: '测试病历内容...',
        created_at: '2025-05-05 00:28',
        updated_at: '2025-05-05 00:28',
        created_by: '测试医师',
        tags: ['测试', '门诊'],
        medical_insurance_type: '居民医保',
        cost_amount: 580.00,
        violation_risk: 'medium'
      },
      {
        id: 'MRTEST123',
        name: '自动化检测病历',
        patient_name: '自动化测试',
        patient_id: 'P003',
        department: '外科',
        record_type: '手术记录',
        disease_type: '外科疾病',
        complexity_level: '复杂',
        status: 'analyzing',
        qc_score: 92,
        content: '手术记录详细内容...',
        created_at: '2025-05-05 00:49',
        updated_at: '2025-05-05 01:15',
        created_by: '肝胆外科',
        tags: ['手术', '外科'],
        medical_insurance_type: '职工医保',
        cost_amount: 28900.00,
        violation_risk: 'high'
      }
    ]
  } catch (error) {
    message.error('加载病历数据失败')
  } finally {
    recordsLoading.value = false
  }
}

// 加载医保病历统计数据
async function loadMedicalRecordStats() {
  try {
    const stats = await getMedicalRecordStats()
    medicalRecordStats.value = {
      totalRecords: stats.totalRecords,
      pendingReview: stats.pendingReview,
      approvedRecords: stats.approvedRecords,
      violationCount: stats.violationCount
    }
  } catch (error) {
    console.error('加载医保病历统计数据失败:', error)
  }
}

async function refreshData() {
  refreshing.value = true
  try {
    const s = await fetchDashboardStats()
    serverStats.value.totalViolations = s.totalViolations || 0
    trends.value = await fetchViolationTrends(30)
    topRules.value = await fetchTopRules(10)
    stats.value.todayUploads += Math.floor(Math.random() * 5)
    await loadMedicalRecordStats()
  } finally {
    refreshing.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([refreshData(), loadMedicalRecords(), loadMedicalRecordStats()])
  } finally {
    loading.value = false
  }
})
</script>



