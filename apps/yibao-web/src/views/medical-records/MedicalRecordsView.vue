<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-8">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="bg-gradient-to-r from-emerald-500 via-green-600 to-teal-600 text-white p-8 rounded-2xl shadow-lg">
          <div class="flex justify-between items-start">
            <div>
              <div class="flex items-center gap-4 mb-4">
                <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20">
                  <FileTextOutlined class="text-2xl text-white" />
                </div>
                <div>
                  <h1 class="text-4xl font-bold mb-2">测试病历管理</h1>
                  <p class="text-green-100 text-lg">医保质控测试病历数据管理平台</p>
                  <div class="flex items-center mt-2 text-green-200">
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
              <a-button type="primary" size="large" @click="handleCreateRecord" class="h-12 px-6 bg-white/20 border-white/30 text-white hover:bg-white/30 hover:border-white/50 backdrop-blur-sm">
                <PlusOutlined /> 新建病历
              </a-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-600 text-sm font-medium mb-2">总病历数</p>
              <p class="text-3xl font-bold text-gray-800">{{ stats.total }}</p>
              <p class="text-green-600 text-sm mt-1">
                <ArrowUpOutlined class="mr-1" />
                较上月 +12.5%
              </p>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center">
              <FileTextOutlined class="text-blue-600 text-2xl" />
            </div>
          </div>
        </div>

        <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-600 text-sm font-medium mb-2">本月新增</p>
              <p class="text-3xl font-bold text-gray-800">{{ stats.thisMonth }}</p>
              <p class="text-green-600 text-sm mt-1">
                <ArrowUpOutlined class="mr-1" />
                较上月 +8.3%
              </p>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-green-50 flex items-center justify-center">
              <CalendarOutlined class="text-green-600 text-2xl" />
            </div>
          </div>
        </div>

        <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-600 text-sm font-medium mb-2">待审核</p>
              <p class="text-3xl font-bold text-gray-800">{{ stats.pending }}</p>
              <p class="text-orange-600 text-sm mt-1">
                <ClockCircleOutlined class="mr-1" />
                需要处理
              </p>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-orange-50 flex items-center justify-center">
              <ClockCircleOutlined class="text-orange-600 text-2xl" />
            </div>
          </div>
        </div>

        <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 hover:shadow-xl transition-shadow duration-300">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-gray-600 text-sm font-medium mb-2">已关联规则</p>
              <p class="text-3xl font-bold text-gray-800">{{ stats.withRules }}</p>
              <p class="text-purple-600 text-sm mt-1">
                <SettingOutlined class="mr-1" />
                规则覆盖率 78%
              </p>
            </div>
            <div class="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center">
              <SettingOutlined class="text-purple-600 text-2xl" />
            </div>
          </div>
        </div>
      </div>

      <!-- 主要内容区域 -->
      <div class="grid grid-cols-1 xl:grid-cols-4 gap-8">
        <!-- 病历列表 -->
        <div class="xl:col-span-3">
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
            <div class="flex items-center justify-between mb-6">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500/10 to-green-500/20 flex items-center justify-center">
                  <FolderOpenOutlined class="text-emerald-600 text-xl" />
                </div>
                <div>
                  <h3 class="text-xl font-bold text-gray-800">病历列表</h3>
                  <p class="text-gray-600 text-sm">管理和查看测试病历数据</p>
                </div>
              </div>
              <div class="flex gap-2">
                <a-button @click="handleImportRecords">
                  <UploadOutlined /> 批量导入
                </a-button>
                <a-button @click="handleExportRecords">
                  <DownloadOutlined /> 导出数据
                </a-button>
              </div>
            </div>

            <TestMedicalRecordsList 
              :records="records" 
              :loading="loading"
              @view-record="handleViewRecord"
              @edit-record="handleEditRecord"
              @delete-record="handleDeleteRecord"
              @analyze-record="handleAnalyzeRecord"
            />
          </div>
        </div>

        <!-- 右侧操作面板 -->
        <div class="space-y-6">
          <!-- 快捷操作 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/10 to-indigo-500/20 flex items-center justify-center">
                <ThunderboltOutlined class="text-blue-600 text-xl" />
              </div>
              <div>
                <h3 class="text-lg font-bold text-gray-800">快捷操作</h3>
                <p class="text-gray-600 text-sm">常用功能入口</p>
              </div>
            </div>
            <div class="space-y-3">
              <a-button block size="large" @click="handleCreateRecord">
                <PlusOutlined /> 新建病历
              </a-button>
              <a-button block size="large" @click="handleImportRecords">
                <UploadOutlined /> 批量导入
              </a-button>
              <a-button block size="large" @click="handleBatchAnalyze">
                <ThunderboltOutlined /> 批量分析
              </a-button>
              <a-button block size="large" @click="handleTemplateManage">
                <FileTextOutlined /> 模板管理
              </a-button>
            </div>
          </div>

          <!-- 最近活动 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/10 to-pink-500/20 flex items-center justify-center">
                <HistoryOutlined class="text-purple-600 text-xl" />
              </div>
              <div>
                <h3 class="text-lg font-bold text-gray-800">最近活动</h3>
                <p class="text-gray-600 text-sm">病历操作记录</p>
              </div>
            </div>
            <div class="space-y-4">
              <div v-for="activity in recentActivities" :key="activity.id" class="flex items-start gap-3 p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors duration-200">
                <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0" :style="{ background: `linear-gradient(135deg, ${activity.color}15, ${activity.color}25)` }">
                  <component :is="activity.icon" :style="{ color: activity.color }" class="text-sm" />
                </div>
                <div class="flex-1 min-w-0">
                  <h5 class="text-gray-800 font-medium text-sm mb-1 truncate">{{ activity.title }}</h5>
                  <p class="text-gray-600 text-xs mb-1 line-clamp-2">{{ activity.description }}</p>
                  <span class="text-gray-500 text-xs">{{ activity.time }}</span>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import BasicLayout from '@/layouts/BasicLayout.vue'
import TestMedicalRecordsList from '@/components/medical-records/TestMedicalRecordsList.vue'
import { 
  FileTextOutlined, 
  ClockCircleOutlined, 
  ReloadOutlined, 
  PlusOutlined, 
  ArrowUpOutlined,
  CalendarOutlined,
  SettingOutlined,
  FolderOpenOutlined,
  UploadOutlined,
  DownloadOutlined,
  ThunderboltOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  EyeOutlined
} from '@ant-design/icons-vue'

// 测试病历类型定义
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

const router = useRouter()

// 响应式数据
const loading = ref(false)
const refreshing = ref(false)
const records = ref<TestMedicalRecord[]>([])
const stats = ref({
  total: 156,
  thisMonth: 23,
  pending: 5,
  withRules: 89
})

const recentActivities = ref([
  { id: 1, type: 'create', title: '新建病历 - 张三住院记录', description: '创建了心血管疾病相关的测试病历', time: '5分钟前', icon: PlusOutlined, color: '#1890ff' },
  { id: 2, type: 'analyze', title: '分析完成 - 李四门诊记录', description: '质控分析已完成，评分85分', time: '15分钟前', icon: CheckCircleOutlined, color: '#52c41a' },
  { id: 3, type: 'review', title: '病历审核 - 王五手术记录', description: '外科手术记录通过审核', time: '1小时前', icon: EyeOutlined, color: '#faad14' },
  { id: 4, type: 'import', title: '批量导入病历', description: '成功导入15条测试病历数据', time: '2小时前', icon: UploadOutlined, color: '#722ed1' }
])

const currentDate = computed(() => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekdays[now.getDay()]
  return `${year}年${month}月${day}日 ${weekday}`
})

// 方法
function handleCreateRecord() {
  router.push('/medical-records/create')
}

function handleImportRecords() {
  message.info('批量导入功能开发中...')
}

function handleExportRecords() {
  message.info('导出数据功能开发中...')
}

function handleBatchAnalyze() {
  message.info('批量分析功能开发中...')
}

function handleTemplateManage() {
  message.info('模板管理功能开发中...')
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

async function loadRecords() {
  loading.value = true
  try {
    // 调用真实API获取测试病历数据
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://43.163.116.243:8002'
    const response = await fetch(`${API_BASE_URL}/api/medical-records?page=1&page_size=50`, {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('yibao_access_token')}`,
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      records.value = data.data || []

      // 更新统计数据
      stats.value = {
        total: data.total || 0,
        completed: records.value.filter(r => r.status === 'completed').length,
        pending: records.value.filter(r => r.status === 'pending').length,
        high_risk: records.value.filter(r => r.violation_risk === 'block').length
      }

      message.success(`成功加载 ${records.value.length} 条测试病历`)
    } else if (response.status === 401) {
      message.error('认证失败，请重新登录')
      // 可以在这里触发重新登录
    } else {
      const errorData = await response.json()
      message.error(`加载失败: ${errorData.detail || '未知错误'}`)
    }
  } catch (error) {
    console.error('加载病历数据失败:', error)
    message.error('网络错误，请检查连接')
  } finally {
    loading.value = false
  }
}

async function refreshData() {
  refreshing.value = true
  try {
    await loadRecords()
    message.success('数据刷新成功')
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  loadRecords()
})
</script>

<style scoped>
/* 自定义样式 */
</style>
