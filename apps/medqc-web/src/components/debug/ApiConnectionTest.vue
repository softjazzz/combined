<template>
  <div class="api-connection-test">
    <div class="p-6 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50">
      <div class="flex items-center justify-between mb-6">
        <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <ApiOutlined class="text-cyan-400" />
          API连接测试
        </h3>
        <div class="flex items-center gap-2">
          <div 
            class="w-3 h-3 rounded-full"
            :class="connectionStatus === 'connected' ? 'bg-emerald-400' : connectionStatus === 'connecting' ? 'bg-amber-400' : 'bg-red-400'"
          ></div>
          <span 
            class="text-sm font-medium"
            :class="connectionStatus === 'connected' ? 'text-emerald-400' : connectionStatus === 'connecting' ? 'text-amber-400' : 'text-red-400'"
          >
            {{ getStatusText(connectionStatus) }}
          </span>
        </div>
      </div>

      <!-- API基础信息 -->
      <div class="mb-6 p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
        <h4 class="text-sm font-medium text-slate-200 mb-3">API配置信息</h4>
        <div class="space-y-2 text-sm">
          <div class="flex justify-between">
            <span class="text-slate-400">基础URL:</span>
            <span class="text-slate-200 font-mono">{{ apiBaseUrl }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">超时时间:</span>
            <span class="text-slate-200">30秒</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-400">认证状态:</span>
            <span :class="isAuthenticated ? 'text-emerald-400' : 'text-red-400'">
              {{ isAuthenticated ? '已认证' : '未认证' }}
            </span>
          </div>
        </div>
      </div>

      <!-- 测试按钮 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <a-button 
          @click="testConnection"
          :loading="testing.connection"
          class="h-12 bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30"
        >
          <ApiOutlined />
          连接测试
        </a-button>
        
        <a-button 
          @click="testAuth"
          :loading="testing.auth"
          class="h-12 bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"
        >
          <UserOutlined />
          认证测试
        </a-button>
        
        <a-button 
          @click="testAllApis"
          :loading="testing.all"
          class="h-12 bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30"
        >
          <ThunderboltOutlined />
          全面测试
        </a-button>
      </div>

      <!-- 测试结果 -->
      <div class="space-y-4">
        <div
          v-for="result in testResults"
          :key="result.id"
          class="p-4 rounded-lg border transition-all duration-200"
          :class="getResultCardClass(result.status)"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <component 
                :is="getResultIcon(result.status)" 
                :class="getResultIconClass(result.status)"
              />
              <span class="font-medium text-slate-100">{{ result.name }}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="text-xs text-slate-400">{{ result.duration }}ms</span>
              <a-tag 
                :color="getResultTagColor(result.status)" 
                size="small"
              >
                {{ getResultStatusText(result.status) }}
              </a-tag>
            </div>
          </div>
          
          <div class="text-sm text-slate-300 mb-2">{{ result.description }}</div>
          
          <div v-if="result.details" class="text-xs text-slate-400 font-mono bg-slate-900/50 p-2 rounded border border-slate-600/20">
            {{ result.details }}
          </div>
          
          <div v-if="result.error" class="text-xs text-red-300 bg-red-500/10 p-2 rounded border border-red-500/20 mt-2">
            错误: {{ result.error }}
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="testResults.length === 0" class="text-center py-8">
        <div class="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3">
          <ApiOutlined class="text-slate-400 text-2xl" />
        </div>
        <div class="text-slate-400">点击上方按钮开始API测试</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  UserOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons-vue'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'

// 状态
const connectionStatus = ref<'connected' | 'connecting' | 'disconnected'>('disconnected')
const apiBaseUrl = ref(ApiService.getBaseURL())
const authStore = useAuthStore()

// 测试状态
const testing = ref({
  connection: false,
  auth: false,
  all: false
})

// 测试结果
interface TestResult {
  id: string
  name: string
  description: string
  status: 'success' | 'error' | 'warning' | 'loading'
  duration: number
  details?: string
  error?: string
}

const testResults = ref<TestResult[]>([])

// 计算属性
const isAuthenticated = computed(() => ApiService.isAuthenticated())

// 方法
const getStatusText = (status: string) => {
  const texts = {
    connected: '已连接',
    connecting: '连接中',
    disconnected: '未连接'
  }
  return texts[status as keyof typeof texts] || '未知'
}

const addTestResult = (result: Omit<TestResult, 'id'>) => {
  testResults.value.unshift({
    ...result,
    id: Date.now().toString()
  })
  
  // 限制结果数量
  if (testResults.value.length > 10) {
    testResults.value = testResults.value.slice(0, 10)
  }
}

const testConnection = async () => {
  testing.value.connection = true
  connectionStatus.value = 'connecting'
  
  const startTime = Date.now()
  
  try {
    const isConnected = await ApiService.checkConnection()
    const duration = Date.now() - startTime
    
    if (isConnected) {
      connectionStatus.value = 'connected'
      addTestResult({
        name: 'API连接测试',
        description: '成功连接到后端API服务',
        status: 'success',
        duration,
        details: `GET ${apiBaseUrl.value}/api/health`
      })
      message.success('API连接正常')
    } else {
      connectionStatus.value = 'disconnected'
      addTestResult({
        name: 'API连接测试',
        description: '无法连接到后端API服务',
        status: 'error',
        duration,
        error: '连接失败，请检查后端服务是否启动'
      })
      message.error('API连接失败')
    }
  } catch (error: any) {
    connectionStatus.value = 'disconnected'
    const duration = Date.now() - startTime
    
    addTestResult({
      name: 'API连接测试',
      description: '连接测试过程中发生错误',
      status: 'error',
      duration,
      error: error.message || '未知错误'
    })
    message.error('连接测试失败')
  } finally {
    testing.value.connection = false
  }
}

const testAuth = async () => {
  testing.value.auth = true
  const startTime = Date.now()
  
  try {
    if (!isAuthenticated.value) {
      // 尝试使用演示账户登录
      const response = await ApiService.login({
        email: 'admin@medqc.com',
        password: 'admin123'
      })
      
      const duration = Date.now() - startTime
      
      if (response.success) {
        addTestResult({
          name: '认证测试',
          description: '使用演示账户登录成功',
          status: 'success',
          duration,
          details: 'POST /api/auth/login'
        })
        message.success('认证测试成功')
      } else {
        addTestResult({
          name: '认证测试',
          description: '登录失败',
          status: 'error',
          duration,
          error: response.error || '登录失败'
        })
        message.error('认证测试失败')
      }
    } else {
      // 测试获取用户信息
      const response = await ApiService.getCurrentUser()
      const duration = Date.now() - startTime
      
      if (response.success) {
        addTestResult({
          name: '认证测试',
          description: '成功获取当前用户信息',
          status: 'success',
          duration,
          details: `GET /api/auth/me - 用户: ${response.data?.display_name}`
        })
        message.success('认证测试成功')
      } else {
        addTestResult({
          name: '认证测试',
          description: '获取用户信息失败',
          status: 'error',
          duration,
          error: response.error || '获取用户信息失败'
        })
        message.error('认证测试失败')
      }
    }
  } catch (error: any) {
    const duration = Date.now() - startTime
    addTestResult({
      name: '认证测试',
      description: '认证测试过程中发生错误',
      status: 'error',
      duration,
      error: error.message || '未知错误'
    })
    message.error('认证测试失败')
  } finally {
    testing.value.auth = false
  }
}

const testAllApis = async () => {
  testing.value.all = true
  testResults.value = []
  
  // 依次测试各个API模块
  await testConnection()
  await new Promise(resolve => setTimeout(resolve, 500))
  
  await testAuth()
  await new Promise(resolve => setTimeout(resolve, 500))
  
  // 测试其他API接口
  await testMedicalRecordsApi()
  await new Promise(resolve => setTimeout(resolve, 500))
  
  await testQCApi()
  
  testing.value.all = false
  message.info('全面API测试完成')
}

const testMedicalRecordsApi = async () => {
  const startTime = Date.now()
  
  try {
    const response = await ApiService.getMedicalRecords({ pagination: { page: 1, pageSize: 5 } })
    const duration = Date.now() - startTime
    
    if (response.success) {
      addTestResult({
        name: '医疗记录API测试',
        description: '成功获取医疗记录列表',
        status: 'success',
        duration,
        details: `GET /api/records - 返回 ${response.data?.data?.length || 0} 条记录`
      })
    } else {
      addTestResult({
        name: '医疗记录API测试',
        description: '获取医疗记录失败',
        status: 'error',
        duration,
        error: response.error || '获取记录失败'
      })
    }
  } catch (error: any) {
    const duration = Date.now() - startTime
    addTestResult({
      name: '医疗记录API测试',
      description: '医疗记录API测试失败',
      status: 'error',
      duration,
      error: error.message || '未知错误'
    })
  }
}

const testQCApi = async () => {
  const startTime = Date.now()
  
  try {
    const response = await ApiService.getQCRules()
    const duration = Date.now() - startTime
    
    if (response.success) {
      addTestResult({
        name: '质控API测试',
        description: '成功获取质控规则列表',
        status: 'success',
        duration,
        details: `GET /api/qc/rules - 返回 ${response.data?.length || 0} 条规则`
      })
    } else {
      addTestResult({
        name: '质控API测试',
        description: '获取质控规则失败',
        status: 'error',
        duration,
        error: response.error || '获取规则失败'
      })
    }
  } catch (error: any) {
    const duration = Date.now() - startTime
    addTestResult({
      name: '质控API测试',
      description: '质控API测试失败',
      status: 'error',
      duration,
      error: error.message || '未知错误'
    })
  }
}

// 样式相关方法
const getResultCardClass = (status: string) => {
  const classes = {
    success: 'border-emerald-500/30 bg-emerald-500/5',
    error: 'border-red-500/30 bg-red-500/5',
    warning: 'border-amber-500/30 bg-amber-500/5',
    loading: 'border-blue-500/30 bg-blue-500/5'
  }
  return classes[status as keyof typeof classes] || 'border-slate-600/30 bg-slate-700/5'
}

const getResultIcon = (status: string) => {
  const icons = {
    success: CheckCircleOutlined,
    error: CloseCircleOutlined,
    warning: ExclamationCircleOutlined,
    loading: LoadingOutlined
  }
  return icons[status as keyof typeof icons] || ExclamationCircleOutlined
}

const getResultIconClass = (status: string) => {
  const classes = {
    success: 'text-emerald-400',
    error: 'text-red-400',
    warning: 'text-amber-400',
    loading: 'text-blue-400'
  }
  return classes[status as keyof typeof classes] || 'text-slate-400'
}

const getResultTagColor = (status: string) => {
  const colors = {
    success: 'green',
    error: 'red',
    warning: 'orange',
    loading: 'blue'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getResultStatusText = (status: string) => {
  const texts = {
    success: '成功',
    error: '失败',
    warning: '警告',
    loading: '进行中'
  }
  return texts[status as keyof typeof texts] || '未知'
}

// 生命周期
onMounted(() => {
  // 初始连接测试
  testConnection()
})
</script>

<style scoped>
.api-connection-test {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 结果卡片动画 */
.space-y-4 > div {
  animation: slideInUp 0.3s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .grid-cols-1.md\\:grid-cols-3 {
    grid-template-columns: 1fr;
  }
}
</style>
