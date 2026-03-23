<template>
  <div class="api-test-view min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
    <div class="max-w-6xl mx-auto">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center">
            <ApiOutlined class="text-white text-sm" />
          </div>
          <h1 class="text-2xl font-bold text-slate-100">
            API集成测试
          </h1>
        </div>
        <p class="text-slate-400 text-sm">
          前后端API对接联调测试工具
        </p>
      </div>

      <!-- API连接测试 -->
      <div class="mb-8">
        <ApiConnectionTest />
      </div>

      <!-- 详细API测试 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <!-- 认证API测试 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <UserOutlined class="text-emerald-400" />
            认证API测试 (B1)
          </h3>
          
          <div class="space-y-4">
            <div class="p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
              <h4 class="text-sm font-medium text-slate-200 mb-2">
                测试账户
              </h4>
              <div class="space-y-2 text-xs">
                <div class="flex justify-between">
                  <span class="text-slate-400">管理员:</span>
                  <span class="text-slate-200 font-mono">admin@medqc.com / admin123</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">质控主管:</span>
                  <span class="text-slate-200 font-mono">qc@medqc.com / qc123456</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-400">医务人员:</span>
                  <span class="text-slate-200 font-mono">doctor@medqc.com / doctor123</span>
                </div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <a-button 
                :loading="authTesting.login"
                size="small"
                class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300"
                @click="testLogin"
              >
                登录测试
              </a-button>
              <a-button 
                :loading="authTesting.getUser"
                size="small"
                class="bg-blue-500/20 border-blue-400/30 text-blue-300"
                @click="testGetUser"
              >
                获取用户
              </a-button>
              <a-button 
                :loading="authTesting.updateProfile"
                size="small"
                class="bg-purple-500/20 border-purple-400/30 text-purple-300"
                @click="testUpdateProfile"
              >
                更新资料
              </a-button>
              <a-button 
                :loading="authTesting.logout"
                size="small"
                class="bg-red-500/20 border-red-400/30 text-red-300"
                @click="testLogout"
              >
                登出测试
              </a-button>
            </div>
          </div>
        </div>

        <!-- 医疗记录API测试 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <FileTextOutlined class="text-blue-400" />
            医疗记录API测试 (B2)
          </h3>
          
          <div class="space-y-4">
            <div class="p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
              <h4 class="text-sm font-medium text-slate-200 mb-2">
                API接口
              </h4>
              <div class="space-y-1 text-xs text-slate-400">
                <div>• GET /api/records - 获取记录列表</div>
                <div>• POST /api/records - 创建记录</div>
                <div>• PUT /api/records/:id - 更新记录</div>
                <div>• DELETE /api/records/:id - 删除记录</div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <a-button 
                :loading="recordTesting.getRecords"
                size="small"
                class="bg-blue-500/20 border-blue-400/30 text-blue-300"
                @click="testGetRecords"
              >
                获取列表
              </a-button>
              <a-button 
                :loading="recordTesting.createRecord"
                size="small"
                class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300"
                @click="testCreateRecord"
              >
                创建记录
              </a-button>
              <a-button 
                :loading="recordTesting.uploadFile"
                size="small"
                class="bg-purple-500/20 border-purple-400/30 text-purple-300"
                @click="testUploadFile"
              >
                文件上传
              </a-button>
              <a-button 
                :loading="recordTesting.getStatistics"
                size="small"
                class="bg-amber-500/20 border-amber-400/30 text-amber-300"
                @click="testGetStatistics"
              >
                获取统计
              </a-button>
            </div>
          </div>
        </div>

        <!-- 质控分析API测试 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <ThunderboltOutlined class="text-purple-400" />
            质控分析API测试 (B3)
          </h3>
          
          <div class="space-y-4">
            <div class="p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
              <h4 class="text-sm font-medium text-slate-200 mb-2">
                AI分析功能
              </h4>
              <div class="space-y-1 text-xs text-slate-400">
                <div>• POST /api/qc/analyze - 开始分析</div>
                <div>• GET /api/qc/result/:id - 获取结果</div>
                <div>• GET /api/qc/progress/:id - 获取进度</div>
                <div>• GET /api/qc/rules - 获取规则</div>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <a-button 
                :loading="qcTesting.getRules"
                size="small"
                class="bg-purple-500/20 border-purple-400/30 text-purple-300"
                @click="testGetQCRules"
              >
                获取规则
              </a-button>
              <a-button 
                :loading="qcTesting.startAnalysis"
                size="small"
                class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300"
                @click="testStartAnalysis"
              >
                开始分析
              </a-button>
              <a-button 
                :loading="qcTesting.getResult"
                size="small"
                class="bg-blue-500/20 border-blue-400/30 text-blue-300"
                @click="testGetQCResult"
              >
                获取结果
              </a-button>
              <a-button 
                :loading="qcTesting.getHistory"
                size="small"
                class="bg-amber-500/20 border-amber-400/30 text-amber-300"
                @click="testGetQCHistory"
              >
                获取历史
              </a-button>
            </div>
          </div>
        </div>

        <!-- 测试日志 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <FileTextOutlined class="text-green-400" />
              测试日志
            </h3>
            <a-button 
              size="small"
              class="bg-slate-700/50 border-slate-600/50 text-slate-300"
              @click="clearLogs"
            >
              清空日志
            </a-button>
          </div>
          
          <div class="max-h-64 overflow-y-auto space-y-2">
            <div
              v-for="log in testLogs"
              :key="log.id"
              class="p-2 rounded text-xs font-mono"
              :class="getLogClass(log.type)"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium">{{ log.title }}</span>
                <span class="text-slate-500">{{ formatTime(log.timestamp) }}</span>
              </div>
              <div>{{ log.message }}</div>
              <div
                v-if="log.details"
                class="mt-1 text-slate-400"
              >
                {{ log.details }}
              </div>
            </div>
          </div>

          <div
            v-if="testLogs.length === 0"
            class="text-center py-8"
          >
            <div class="text-slate-400 text-sm">
              暂无测试日志
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApiOutlined,
  UserOutlined,
  FileTextOutlined,
  ThunderboltOutlined
} from '@ant-design/icons-vue'
import ApiConnectionTest from '@/components/debug/ApiConnectionTest.vue'
import { ApiService } from '@/services/apiService'

const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) return error.message
  if (typeof error === 'object' && error && 'message' in error) {
    return String((error as { message?: unknown }).message || '未知错误')
  }
  return '未知错误'
}

// 测试状态
const authTesting = reactive({
  login: false,
  getUser: false,
  updateProfile: false,
  logout: false
})

const recordTesting = reactive({
  getRecords: false,
  createRecord: false,
  uploadFile: false,
  getStatistics: false
})

const qcTesting = reactive({
  getRules: false,
  startAnalysis: false,
  getResult: false,
  getHistory: false
})

// 测试日志
interface TestLog {
  id: string
  title: string
  message: string
  details?: string
  type: 'success' | 'error' | 'info' | 'warning'
  timestamp: Date
}

const testLogs = ref<TestLog[]>([])

// 添加日志
const addLog = (log: Omit<TestLog, 'id' | 'timestamp'>) => {
  testLogs.value.unshift({
    ...log,
    id: Date.now().toString(),
    timestamp: new Date()
  })
  
  // 限制日志数量
  if (testLogs.value.length > 50) {
    testLogs.value = testLogs.value.slice(0, 50)
  }
}

// 认证API测试
const testLogin = async () => {
  authTesting.login = true
  try {
    const response = await ApiService.login({
      email: 'admin@medqc.com',
      password: 'admin123'
    })
    
    if (response.success) {
      addLog({
        title: '登录测试',
        message: '登录成功',
        details: `POST /api/auth/login - Token已获取`,
        type: 'success'
      })
      message.success('登录测试成功')
    } else {
      addLog({
        title: '登录测试',
        message: '登录失败',
        details: response.error,
        type: 'error'
      })
      message.error('登录测试失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '登录测试',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
    message.error('登录测试异常')
  } finally {
    authTesting.login = false
  }
}

const testGetUser = async () => {
  authTesting.getUser = true
  try {
    const response = await ApiService.getCurrentUser()
    
    if (response.success) {
      addLog({
        title: '获取用户信息',
        message: '获取成功',
        details: `GET /api/auth/me - 用户: ${response.data?.display_name}`,
        type: 'success'
      })
      message.success('获取用户信息成功')
    } else {
      addLog({
        title: '获取用户信息',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取用户信息失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取用户信息',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    authTesting.getUser = false
  }
}

const testUpdateProfile = async () => {
  authTesting.updateProfile = true
  try {
    const response = await ApiService.updateProfile({
      display_name: '测试用户 - ' + new Date().toLocaleString()
    })
    
    if (response.success) {
      addLog({
        title: '更新用户资料',
        message: '更新成功',
        details: 'PUT /api/auth/profile',
        type: 'success'
      })
      message.success('更新资料成功')
    } else {
      addLog({
        title: '更新用户资料',
        message: '更新失败',
        details: response.error,
        type: 'error'
      })
      message.error('更新资料失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '更新用户资料',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    authTesting.updateProfile = false
  }
}

const testLogout = async () => {
  authTesting.logout = true
  try {
    const response = await ApiService.logout()
    
    if (response.success) {
      addLog({
        title: '用户登出',
        message: '登出成功',
        details: 'POST /api/auth/logout',
        type: 'success'
      })
      message.success('登出成功')
    } else {
      addLog({
        title: '用户登出',
        message: '登出失败',
        details: response.error,
        type: 'error'
      })
    }
  } catch (error: unknown) {
    addLog({
      title: '用户登出',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    authTesting.logout = false
  }
}

// 医疗记录API测试
const testGetRecords = async () => {
  recordTesting.getRecords = true
  try {
    const response = await ApiService.getMedicalRecords({
      pagination: { page: 1, pageSize: 10 }
    })
    
    if (response.success) {
      addLog({
        title: '获取医疗记录',
        message: '获取成功',
        details: `GET /api/records - 返回 ${response.data?.data?.length || 0} 条记录`,
        type: 'success'
      })
      message.success('获取记录成功')
    } else {
      addLog({
        title: '获取医疗记录',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取记录失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取医疗记录',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    recordTesting.getRecords = false
  }
}

const testCreateRecord = async () => {
  recordTesting.createRecord = true
  try {
    const response = await ApiService.createMedicalRecord({
      record_name: '测试病历',
      patient_info: {
        name: '测试患者',
        age: 30,
        gender: 'M'
      },
      department: '内科',
      primary_diagnosis: '测试诊断',
      raw_text: '这是一个测试病案记录，用于API测试。'
    })
    
    if (response.success) {
      addLog({
        title: '创建医疗记录',
        message: '创建成功',
        details: `POST /api/records - 记录ID: ${response.data?.id}`,
        type: 'success'
      })
      message.success('创建记录成功')
    } else {
      addLog({
        title: '创建医疗记录',
        message: '创建失败',
        details: response.error,
        type: 'error'
      })
      message.error('创建记录失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '创建医疗记录',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    recordTesting.createRecord = false
  }
}

const testUploadFile = async () => {
  recordTesting.uploadFile = true
  try {
    // 创建一个测试文件
    const testContent = '这是一个测试文件内容，用于API测试。'
    const blob = new Blob([testContent], { type: 'text/plain' })
    const file = new File([blob], 'test.txt', { type: 'text/plain' })
    
    const response = await ApiService.uploadRecordFile(file)
    
    if (response.success) {
      addLog({
        title: '文件上传',
        message: '上传成功',
        details: `POST /api/records/upload - 文件: ${response.data?.file_name}`,
        type: 'success'
      })
      message.success('文件上传成功')
    } else {
      addLog({
        title: '文件上传',
        message: '上传失败',
        details: response.error,
        type: 'error'
      })
      message.error('文件上传失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '文件上传',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    recordTesting.uploadFile = false
  }
}

const testGetStatistics = async () => {
  recordTesting.getStatistics = true
  try {
    const response = await ApiService.getMedicalRecordsStatistics()
    
    if (response.success) {
      addLog({
        title: '获取统计信息',
        message: '获取成功',
        details: 'GET /api/records/statistics',
        type: 'success'
      })
      message.success('获取统计成功')
    } else {
      addLog({
        title: '获取统计信息',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取统计失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取统计信息',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    recordTesting.getStatistics = false
  }
}

// 质控API测试
const testGetQCRules = async () => {
  qcTesting.getRules = true
  try {
    const response = await ApiService.getQCRules()
    
    if (response.success) {
      addLog({
        title: '获取质控规则',
        message: '获取成功',
        details: `GET /api/qc/rules - 返回 ${response.data?.length || 0} 条规则`,
        type: 'success'
      })
      message.success('获取规则成功')
    } else {
      addLog({
        title: '获取质控规则',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取规则失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取质控规则',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    qcTesting.getRules = false
  }
}

const testStartAnalysis = async () => {
  qcTesting.startAnalysis = true
  try {
    const response = await ApiService.analyzeRecord('test-record-id')
    
    if (response.success) {
      addLog({
        title: '开始质控分析',
        message: '分析已开始',
        details: `POST /api/qc/analyze - 分析ID: ${response.data?.analysis_id}`,
        type: 'success'
      })
      message.success('开始分析成功')
    } else {
      addLog({
        title: '开始质控分析',
        message: '开始失败',
        details: response.error,
        type: 'error'
      })
      message.error('开始分析失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '开始质控分析',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    qcTesting.startAnalysis = false
  }
}

const testGetQCResult = async () => {
  qcTesting.getResult = true
  try {
    const response = await ApiService.getQCResult('test-record-id')
    
    if (response.success) {
      addLog({
        title: '获取质控结果',
        message: '获取成功',
        details: `GET /api/qc/result - 评分: ${response.data?.score}`,
        type: 'success'
      })
      message.success('获取结果成功')
    } else {
      addLog({
        title: '获取质控结果',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取结果失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取质控结果',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    qcTesting.getResult = false
  }
}

const testGetQCHistory = async () => {
  qcTesting.getHistory = true
  try {
    const response = await ApiService.getQCHistory({ page: 1, pageSize: 10 })
    
    if (response.success) {
      addLog({
        title: '获取质控历史',
        message: '获取成功',
        details: `GET /api/qc/history - 返回 ${response.data?.length || 0} 条记录`,
        type: 'success'
      })
      message.success('获取历史成功')
    } else {
      addLog({
        title: '获取质控历史',
        message: '获取失败',
        details: response.error,
        type: 'error'
      })
      message.error('获取历史失败')
    }
  } catch (error: unknown) {
    addLog({
      title: '获取质控历史',
      message: '测试异常',
      details: getErrorMessage(error),
      type: 'error'
    })
  } finally {
    qcTesting.getHistory = false
  }
}

// 工具方法
const clearLogs = () => {
  testLogs.value = []
  message.info('日志已清空')
}

const getLogClass = (type: string) => {
  const classes = {
    success: 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300',
    error: 'bg-red-500/10 border border-red-500/20 text-red-300',
    warning: 'bg-amber-500/10 border border-amber-500/20 text-amber-300',
    info: 'bg-blue-500/10 border border-blue-500/20 text-blue-300'
  }
  return classes[type as keyof typeof classes] || classes.info
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped>
/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 滚动条样式 */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: rgba(71, 85, 105, 0.2);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .grid-cols-1.lg\\:grid-cols-2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .grid-cols-2 {
    grid-template-columns: 1fr;
  }
}
</style>
