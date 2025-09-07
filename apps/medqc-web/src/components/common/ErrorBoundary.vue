<template>
  <div class="error-boundary">
    <!-- 正常内容 -->
    <slot v-if="!hasError" />
    
    <!-- 错误状态 -->
    <div v-else class="error-content">
      <div class="error-container" :class="`error-${errorSeverity}`">
        <!-- 错误图标 -->
        <div class="error-icon">
          <component :is="errorIcon" />
        </div>
        
        <!-- 错误信息 -->
        <div class="error-info">
          <h3 class="error-title">{{ errorTitle }}</h3>
          <p class="error-message">{{ errorMessage }}</p>
          
          <!-- 错误详情（开发模式） -->
          <div v-if="showDetails && errorDetails" class="error-details">
            <a-collapse ghost>
              <a-collapse-panel key="details" header="错误详情">
                <pre class="error-stack">{{ errorDetails }}</pre>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </div>
        
        <!-- 操作按钮 -->
        <div class="error-actions">
          <a-space :direction="isMobile ? 'vertical' : 'horizontal'" :size="12">
            <a-button 
              type="primary" 
              @click="handleRetry"
              :loading="retrying"
            >
              <template #icon><ReloadOutlined /></template>
              重试
            </a-button>
            
            <a-button 
              v-if="canGoBack"
              @click="handleGoBack"
            >
              <template #icon><ArrowLeftOutlined /></template>
              返回
            </a-button>
            
            <a-button 
              v-if="showReportButton"
              @click="handleReport"
            >
              <template #icon><BugOutlined /></template>
              报告问题
            </a-button>
            
            <a-button 
              v-if="showRefreshButton"
              @click="handleRefresh"
            >
              <template #icon><SyncOutlined /></template>
              刷新页面
            </a-button>
          </a-space>
        </div>
        
        <!-- 建议操作 -->
        <div v-if="suggestions.length > 0" class="error-suggestions">
          <h4>建议操作：</h4>
          <ul>
            <li v-for="(suggestion, index) in suggestions" :key="index">
              {{ suggestion }}
            </li>
          </ul>
        </div>
        
        <!-- 联系信息 -->
        <div v-if="showContactInfo" class="error-contact">
          <a-divider />
          <p class="contact-text">
            如果问题持续存在，请联系技术支持：
            <a href="mailto:support@example.com">support@example.com</a>
            或拨打 400-123-4567
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onErrorCaptured, watch } from 'vue'
import { useRouter } from 'vue-router'
import { 
  ReloadOutlined, 
  ArrowLeftOutlined, 
  BugOutlined, 
  SyncOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { globalErrorHandler, ErrorType, ErrorSeverity } from '@/lib/error-handler'
import { useBreakpoints } from '@/composables/useBreakpoints'

// Props 定义
interface Props {
  fallback?: boolean
  showDetails?: boolean
  showReportButton?: boolean
  showRefreshButton?: boolean
  showContactInfo?: boolean
  canGoBack?: boolean
  maxRetries?: number
  autoRetry?: boolean
  autoRetryDelay?: number
}

const props = withDefaults(defineProps<Props>(), {
  fallback: true,
  showDetails: process.env.NODE_ENV === 'development',
  showReportButton: true,
  showRefreshButton: true,
  showContactInfo: true,
  canGoBack: true,
  maxRetries: 3,
  autoRetry: false,
  autoRetryDelay: 3000
})

// Emits 定义
const emit = defineEmits<{
  error: [error: Error]
  retry: []
  recover: []
}>()

// 响应式数据
const router = useRouter()
const { isMobile } = useBreakpoints()

const hasError = ref(false)
const currentError = ref<Error | null>(null)
const retrying = ref(false)
const retryCount = ref(0)
const errorType = ref<ErrorType>(ErrorType.UNKNOWN)
const errorSeverity = ref<ErrorSeverity>(ErrorSeverity.MEDIUM)

// 计算属性
const errorIcon = computed(() => {
  switch (errorSeverity.value) {
    case ErrorSeverity.CRITICAL:
      return CloseCircleOutlined
    case ErrorSeverity.HIGH:
      return ExclamationCircleOutlined
    case ErrorSeverity.MEDIUM:
      return WarningOutlined
    default:
      return InfoCircleOutlined
  }
})

const errorTitle = computed(() => {
  if (!currentError.value) return '发生错误'
  
  const titleMap: Record<ErrorType, string> = {
    [ErrorType.NETWORK]: '网络连接错误',
    [ErrorType.API]: '服务请求失败',
    [ErrorType.VALIDATION]: '数据验证错误',
    [ErrorType.PERMISSION]: '权限不足',
    [ErrorType.BUSINESS]: '业务逻辑错误',
    [ErrorType.SYSTEM]: '系统错误',
    [ErrorType.TIMEOUT]: '请求超时',
    [ErrorType.UNKNOWN]: '未知错误'
  }
  
  return titleMap[errorType.value] || '发生错误'
})

const errorMessage = computed(() => {
  if (!currentError.value) return '系统遇到了一个问题'
  
  // 用户友好的错误消息
  const messageMap: Record<ErrorType, string> = {
    [ErrorType.NETWORK]: '网络连接异常，请检查网络设置后重试',
    [ErrorType.API]: '服务暂时不可用，请稍后重试',
    [ErrorType.VALIDATION]: '输入的数据格式不正确，请检查后重新提交',
    [ErrorType.PERMISSION]: '您没有执行此操作的权限，请联系管理员',
    [ErrorType.BUSINESS]: '操作无法完成，请检查输入信息',
    [ErrorType.SYSTEM]: '系统内部错误，我们正在处理这个问题',
    [ErrorType.TIMEOUT]: '操作超时，请重试或检查网络连接',
    [ErrorType.UNKNOWN]: '系统遇到了未知问题，请重试或联系技术支持'
  }
  
  return messageMap[errorType.value] || currentError.value.message || '系统遇到了一个问题'
})

const errorDetails = computed(() => {
  if (!currentError.value || !props.showDetails) return null
  
  return {
    message: currentError.value.message,
    stack: currentError.value.stack,
    type: errorType.value,
    severity: errorSeverity.value,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href
  }
})

const suggestions = computed(() => {
  const baseSuggestions: Record<ErrorType, string[]> = {
    [ErrorType.NETWORK]: [
      '检查网络连接是否正常',
      '尝试刷新页面',
      '如果使用VPN，请尝试断开后重试'
    ],
    [ErrorType.API]: [
      '稍后重试',
      '检查输入的数据是否正确',
      '如果问题持续，请联系技术支持'
    ],
    [ErrorType.VALIDATION]: [
      '检查输入格式是否正确',
      '确保必填字段已填写',
      '参考提示信息修正输入'
    ],
    [ErrorType.PERMISSION]: [
      '联系管理员获取相应权限',
      '确认您的账户状态正常',
      '尝试重新登录'
    ],
    [ErrorType.BUSINESS]: [
      '检查操作步骤是否正确',
      '确认数据状态符合要求',
      '参考帮助文档'
    ],
    [ErrorType.SYSTEM]: [
      '稍后重试',
      '刷新页面',
      '联系技术支持'
    ],
    [ErrorType.TIMEOUT]: [
      '检查网络连接速度',
      '重试操作',
      '如果文件较大，请耐心等待'
    ],
    [ErrorType.UNKNOWN]: [
      '刷新页面重试',
      '清除浏览器缓存',
      '联系技术支持并提供错误详情'
    ]
  }
  
  return baseSuggestions[errorType.value] || baseSuggestions[ErrorType.UNKNOWN]
})

// 方法
const handleError = (error: Error) => {
  console.error('ErrorBoundary捕获错误:', error)
  
  hasError.value = true
  currentError.value = error
  retryCount.value = 0
  
  // 分析错误类型和严重程度
  analyzeError(error)
  
  // 上报错误
  globalErrorHandler.handleError(error, {
    component: 'ErrorBoundary',
    props: props
  })
  
  emit('error', error)
  
  // 自动重试
  if (props.autoRetry && retryCount.value < props.maxRetries) {
    setTimeout(() => {
      handleRetry()
    }, props.autoRetryDelay)
  }
}

const analyzeError = (error: Error) => {
  const message = error.message?.toLowerCase() || ''
  
  // 分析错误类型
  if (message.includes('network') || message.includes('fetch')) {
    errorType.value = ErrorType.NETWORK
    errorSeverity.value = ErrorSeverity.HIGH
  } else if (message.includes('timeout')) {
    errorType.value = ErrorType.TIMEOUT
    errorSeverity.value = ErrorSeverity.MEDIUM
  } else if (message.includes('permission') || message.includes('unauthorized')) {
    errorType.value = ErrorType.PERMISSION
    errorSeverity.value = ErrorSeverity.MEDIUM
  } else if (message.includes('validation') || message.includes('invalid')) {
    errorType.value = ErrorType.VALIDATION
    errorSeverity.value = ErrorSeverity.LOW
  } else if (message.includes('api') || message.includes('server')) {
    errorType.value = ErrorType.API
    errorSeverity.value = ErrorSeverity.HIGH
  } else {
    errorType.value = ErrorType.UNKNOWN
    errorSeverity.value = ErrorSeverity.MEDIUM
  }
}

const handleRetry = async () => {
  if (retryCount.value >= props.maxRetries) {
    message.warning(`已达到最大重试次数 (${props.maxRetries})`)
    return
  }
  
  retrying.value = true
  retryCount.value++
  
  try {
    // 等待一段时间后重试
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 重置错误状态
    hasError.value = false
    currentError.value = null
    
    emit('retry')
    emit('recover')
    
    message.success('重试成功')
  } catch (error) {
    console.error('重试失败:', error)
    message.error('重试失败，请稍后再试')
  } finally {
    retrying.value = false
  }
}

const handleGoBack = () => {
  if (window.history.length > 1) {
    router.go(-1)
  } else {
    router.push('/')
  }
}

const handleReport = () => {
  // 实现错误报告功能
  const errorReport = {
    error: currentError.value?.message,
    stack: currentError.value?.stack,
    url: window.location.href,
    userAgent: navigator.userAgent,
    timestamp: new Date().toISOString()
  }
  
  console.log('错误报告:', errorReport)
  message.success('错误报告已提交，感谢您的反馈')
}

const handleRefresh = () => {
  window.location.reload()
}

// 错误捕获
onErrorCaptured((error: Error) => {
  handleError(error)
  return false // 阻止错误继续传播
})

// 监听全局错误
window.addEventListener('error',  (event: any) => {
  if (event.error) {
    handleError(event.error)
  }
})

window.addEventListener('unhandledrejection',  (event: any) => {
  handleError(new Error(event.reason))
})

// 暴露方法给父组件
defineExpose({
  handleError: any, reset: () => {
    hasError.value = false
    currentError.value = null
    retryCount.value = 0
  }
})
</script>

<style scoped>
.error-boundary {
  width: 100%;
  height: 100%;
}

.error-content {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 24px;
}

.error-container {
  max-width: 600px;
  width: 100%;
  text-align: center;
  padding: 40px 32px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

.error-critical {
  border-left: 4px solid #ff4d4f;
}

.error-high {
  border-left: 4px solid #fa8c16;
}

.error-medium {
  border-left: 4px solid #faad14;
}

.error-low {
  border-left: 4px solid #1890ff;
}

.error-icon {
  font-size: 64px;
  margin-bottom: 24px;
}

.error-critical .error-icon {
  color: #ff4d4f;
}

.error-high .error-icon {
  color: #fa8c16;
}

.error-medium .error-icon {
  color: #faad14;
}

.error-low .error-icon {
  color: #1890ff;
}

.error-info {
  margin-bottom: 32px;
}

.error-title {
  font-size: 24px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 16px 0;
}

.error-message {
  font-size: 16px;
  color: #666;
  line-height: 1.6;
  margin: 0 0 16px 0;
}

.error-details {
  margin-top: 16px;
  text-align: left;
}

.error-stack {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #666;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-actions {
  margin-bottom: 24px;
}

.error-suggestions {
  text-align: left;
  margin-bottom: 24px;
}

.error-suggestions h4 {
  font-size: 16px;
  font-weight: 500;
  color: #1a1a1a;
  margin: 0 0 12px 0;
}

.error-suggestions ul {
  margin: 0;
  padding-left: 20px;
}

.error-suggestions li {
  color: #666;
  line-height: 1.6;
  margin-bottom: 8px;
}

.error-contact {
  text-align: center;
}

.contact-text {
  color: #666;
  font-size: 14px;
  margin: 0;
}

.contact-text a {
  color: #1890ff;
  text-decoration: none;
}

.contact-text a:hover {
  text-decoration: underline;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .error-content {
    padding: 16px;
    min-height: 300px;
  }
  
  .error-container {
    padding: 24px 20px;
  }
  
  .error-icon {
    font-size: 48px;
    margin-bottom: 16px;
  }
  
  .error-title {
    font-size: 20px;
  }
  
  .error-message {
    font-size: 14px;
  }
  
  .error-actions {
    margin-bottom: 16px;
  }
}

@media (max-width: 480px) {
  .error-container {
    padding: 20px 16px;
  }
  
  .error-icon {
    font-size: 40px;
    margin-bottom: 12px;
  }
  
  .error-title {
    font-size: 18px;
  }
  
  .error-message {
    font-size: 13px;
  }
}
</style>
