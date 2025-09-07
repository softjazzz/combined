<template>
  <div class="analysis-progress">
    <div class="space-y-6">
      <!-- 总体进度 -->
      <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <ThunderboltOutlined class="text-amber-400" />
            质控分析进度
          </h3>
          <div class="flex items-center gap-3">
            <div class="text-sm text-slate-400">
              {{ currentStep }}/{{ totalSteps }} 步骤
            </div>
            <div class="text-sm font-medium" :class="getStatusColor(status)">
              {{ getStatusLabel(status) }}
            </div>
          </div>
        </div>

        <!-- 总进度条 -->
        <div class="mb-6">
          <div class="flex items-center justify-between mb-2">
            <span class="text-sm text-slate-300">总体进度</span>
            <span class="text-sm font-medium text-slate-200">{{ overallProgress }}%</span>
          </div>
          <a-progress 
            :percent="overallProgress" 
            :show-info="false"
            :stroke-color="getProgressColor(status)"
            stroke-width="8"
            class="overall-progress"
          />
        </div>

        <!-- 状态指示器 -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="text-center p-3 rounded-lg bg-slate-700/30">
            <div class="text-lg font-bold text-blue-400">{{ processedRecords }}</div>
            <div class="text-xs text-slate-400">已处理记录</div>
          </div>
          <div class="text-center p-3 rounded-lg bg-slate-700/30">
            <div class="text-lg font-bold text-amber-400">{{ totalRecords }}</div>
            <div class="text-xs text-slate-400">总记录数</div>
          </div>
          <div class="text-center p-3 rounded-lg bg-slate-700/30">
            <div class="text-lg font-bold text-emerald-400">{{ completedAnalyses }}</div>
            <div class="text-xs text-slate-400">完成分析</div>
          </div>
          <div class="text-center p-3 rounded-lg bg-slate-700/30">
            <div class="text-lg font-bold text-red-400">{{ foundIssues }}</div>
            <div class="text-xs text-slate-400">发现问题</div>
          </div>
        </div>
      </div>

      <!-- 详细步骤进度 -->
      <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
        <h4 class="text-base font-semibold text-slate-100 flex items-center gap-2 mb-4">
          <OrderedListOutlined class="text-cyan-400" />
          分析步骤详情
        </h4>

        <div class="space-y-4">
          <div
            v-for="(step, index) in analysisSteps"
            :key="step.id"
            class="step-item p-4 rounded-lg border transition-all duration-300"
            :class="getStepCardClass(step.status, index)"
          >
            <div class="flex items-center gap-4">
              <!-- 步骤图标 -->
              <div 
                class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                :class="getStepIconClass(step.status, index)"
              >
                <component 
                  :is="getStepIcon(step.status)" 
                  class="text-sm"
                  :class="{ 'animate-spin': step.status === 'running' }"
                />
              </div>

              <div class="flex-1 min-w-0">
                <!-- 步骤标题和状态 -->
                <div class="flex items-center justify-between mb-2">
                  <h5 class="font-medium text-slate-100">{{ step.name }}</h5>
                  <div class="flex items-center gap-2">
                    <a-tag 
                      :color="getStepStatusColor(step.status)" 
                      size="small"
                      class="step-status-tag"
                    >
                      {{ getStepStatusLabel(step.status) }}
                    </a-tag>
                    <span v-if="step.duration" class="text-xs text-slate-400">
                      {{ formatDuration(step.duration) }}
                    </span>
                  </div>
                </div>

                <!-- 步骤描述 -->
                <p class="text-sm text-slate-300 mb-3">{{ step.description }}</p>

                <!-- 步骤进度条 -->
                <div v-if="step.status === 'running' || step.status === 'completed'" class="mb-3">
                  <div class="flex items-center justify-between mb-1">
                    <span class="text-xs text-slate-400">{{ step.current_task || '处理中...' }}</span>
                    <span class="text-xs text-slate-400">{{ step.progress }}%</span>
                  </div>
                  <a-progress 
                    :percent="step.progress" 
                    :show-info="false"
                    :stroke-color="getStepProgressColor(step.status)"
                    size="small"
                  />
                </div>

                <!-- 步骤详细信息 -->
                <div v-if="step.details" class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <div v-if="step.details.processed" class="flex items-center gap-1">
                    <CheckCircleOutlined class="text-emerald-400" />
                    <span class="text-slate-400">已处理: {{ step.details.processed }}</span>
                  </div>
                  <div v-if="step.details.errors" class="flex items-center gap-1">
                    <ExclamationCircleOutlined class="text-red-400" />
                    <span class="text-slate-400">错误: {{ step.details.errors }}</span>
                  </div>
                  <div v-if="step.details.warnings" class="flex items-center gap-1">
                    <WarningOutlined class="text-amber-400" />
                    <span class="text-slate-400">警告: {{ step.details.warnings }}</span>
                  </div>
                  <div v-if="step.details.time_remaining" class="flex items-center gap-1">
                    <ClockCircleOutlined class="text-blue-400" />
                    <span class="text-slate-400">剩余: {{ step.details.time_remaining }}</span>
                  </div>
                </div>

                <!-- 错误信息 -->
                <div v-if="step.status === 'failed' && step.error" class="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div class="flex items-start gap-2">
                    <ExclamationCircleOutlined class="text-red-400 text-sm mt-0.5" />
                    <div>
                      <div class="text-sm font-medium text-red-300 mb-1">执行失败</div>
                      <div class="text-xs text-red-200">{{ step.error }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 实时日志 -->
      <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
        <div class="flex items-center justify-between mb-4">
          <h4 class="text-base font-semibold text-slate-100 flex items-center gap-2">
            <FileTextOutlined class="text-green-400" />
            实时日志
          </h4>
          <div class="flex items-center gap-2">
            <a-switch 
              v-model:checked="autoScroll" 
              size="small"
            />
            <span class="text-xs text-slate-400">自动滚动</span>
            <a-button 
              size="small"
              @click="clearLogs"
              class="bg-slate-700/50 border-slate-600/50 text-slate-300"
            >
              <ClearOutlined />
              清空
            </a-button>
          </div>
        </div>

        <div 
          ref="logContainer"
          class="log-container h-64 overflow-y-auto p-4 rounded-lg bg-slate-900/50 border border-slate-600/30 font-mono text-sm"
        >
          <div
            v-for="(log, index) in logs"
            :key="index"
            class="log-entry mb-1 flex items-start gap-2"
            :class="getLogLevelClass(log.level)"
          >
            <span class="text-xs text-slate-500 flex-shrink-0 w-20">
              {{ formatTime(log.timestamp) }}
            </span>
            <span 
              class="text-xs flex-shrink-0 w-12"
              :class="getLogLevelColor(log.level)"
            >
              [{{ log.level.toUpperCase() }}]
            </span>
            <span class="text-slate-300 flex-1">{{ log.message }}</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex items-center justify-center gap-4">
        <a-button 
          v-if="status === 'running'"
          @click="pauseAnalysis"
          class="bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30"
        >
          <PauseCircleOutlined />
          暂停分析
        </a-button>
        <a-button 
          v-if="status === 'paused'"
          @click="resumeAnalysis"
          class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"
        >
          <PlayCircleOutlined />
          继续分析
        </a-button>
        <a-button 
          v-if="status === 'running' || status === 'paused'"
          @click="stopAnalysis"
          danger
          class="bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30"
        >
          <StopOutlined />
          停止分析
        </a-button>
        <a-button 
          v-if="status === 'completed' || status === 'failed'"
          @click="restartAnalysis"
          type="primary"
          class="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none"
        >
          <ReloadOutlined />
          重新分析
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  OrderedListOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  ClearOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  LoadingOutlined,
  CheckOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  recordId?: string
  autoStart?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoStart: false
})

// Emits
const emit = defineEmits<{
  'analysis-completed': [result: any]
  'analysis-failed': [error: string]
  'analysis-paused': []
  'analysis-resumed': []
  'analysis-stopped': []
}>()

// 状态
const status = ref<'idle' | 'running' | 'paused' | 'completed' | 'failed'>('idle')
const currentStep = ref(0)
const totalSteps = ref(5)
const overallProgress = ref(0)
const processedRecords = ref(0)
const totalRecords = ref(100)
const completedAnalyses = ref(0)
const foundIssues = ref(0)
const autoScroll = ref(true)
const logContainer = ref<HTMLElement>()

// 分析步骤
const analysisSteps = ref([
  {
    id: '1',
    name: '数据预处理',
    description: '清理和标准化病案数据，准备分析环境',
    status: 'pending' as 'pending' | 'running' | 'completed' | 'failed',
    progress: 0,
    current_task: '',
    duration: 0,
    details: null as any,
    error: ''
  },
  {
    id: '2',
    name: '规则引擎初始化',
    description: '加载质控规则，初始化分析引擎',
    status: 'pending' as 'pending' | 'running' | 'completed' | 'failed',
    progress: 0,
    current_task: '',
    duration: 0,
    details: null as any,
    error: ''
  },
  {
    id: '3',
    name: 'AI模型分析',
    description: '使用大语言模型进行深度质控分析',
    status: 'pending' as 'pending' | 'running' | 'completed' | 'failed',
    progress: 0,
    current_task: '',
    duration: 0,
    details: null as any,
    error: ''
  },
  {
    id: '4',
    name: '问题识别与分类',
    description: '识别质控问题并进行严重程度分类',
    status: 'pending' as 'pending' | 'running' | 'completed' | 'failed',
    progress: 0,
    current_task: '',
    duration: 0,
    details: null as any,
    error: ''
  },
  {
    id: '5',
    name: '生成分析报告',
    description: '生成详细的质控分析报告和改进建议',
    status: 'pending' as 'pending' | 'running' | 'completed' | 'failed',
    progress: 0,
    current_task: '',
    duration: 0,
    details: null as any,
    error: ''
  }
])

// 日志
const logs = ref<Array<{
  timestamp: Date
  level: 'info' | 'warn' | 'error' | 'debug'
  message: string
}>>([])

// 定时器
let progressTimer: NodeJS.Timeout | null = null
let logTimer: NodeJS.Timeout | null = null

// 计算属性
const isAnalyzing = computed(() => status.value === 'running')

// 方法
const startAnalysis = () => {
  status.value = 'running'
  currentStep.value = 1
  overallProgress.value = 0
  
  // 重置步骤状态
  analysisSteps.value.forEach(step => {
    step.status = 'pending'
    step.progress = 0
    step.current_task = ''
    step.duration = 0
    step.details = null
    step.error = ''
  })
  
  addLog('info', '开始质控分析...')
  simulateAnalysis()
}

const simulateAnalysis = () => {
  let stepIndex = 0
  
  const processStep = () => {
    if (stepIndex >= analysisSteps.value.length) {
      // 分析完成
      status.value = 'completed'
      overallProgress.value = 100
      addLog('info', '质控分析完成')
      emit('analysis-completed', { /* 分析结果 */ })
      return
    }
    
    const step = analysisSteps.value[stepIndex]
    step.status = 'running'
    currentStep.value = stepIndex + 1
    
    addLog('info', `开始执行: ${step.name}`)
    
    // 模拟步骤进度
    let progress = 0
    const stepTimer = setInterval(() => {
      if (status.value !== 'running') {
        clearInterval(stepTimer)
        return
      }
      
      progress += Math.random() * 15
      if (progress > 100) progress = 100
      
      step.progress = Math.floor(progress)
      step.current_task = getRandomTask(step.name)
      
      // 更新总体进度
      const completedSteps = stepIndex
      const currentStepProgress = progress / 100
      overallProgress.value = Math.floor(((completedSteps + currentStepProgress) / totalSteps.value) * 100)
      
      // 更新统计数据
      processedRecords.value = Math.floor((overallProgress.value / 100) * totalRecords.value)
      completedAnalyses.value = Math.floor(processedRecords.value * 0.8)
      foundIssues.value = Math.floor(processedRecords.value * 0.15)
      
      // 添加随机日志
      if (Math.random() < 0.3) {
        addLog('debug', `${step.name}: ${step.current_task}`)
      }
      
      if (progress >= 100) {
        clearInterval(stepTimer)
        step.status = 'completed'
        step.duration = Math.floor(Math.random() * 30) + 10
        step.details = {
          processed: Math.floor(Math.random() * 50) + 20,
          errors: Math.floor(Math.random() * 3),
          warnings: Math.floor(Math.random() * 8),
          time_remaining: `${Math.floor(Math.random() * 5) + 1}分钟`
        }
        
        addLog('info', `完成: ${step.name} (${step.duration}秒)`)
        
        stepIndex++
        setTimeout(processStep, 1000)
      }
    }, 500)
  }
  
  processStep()
}

const getRandomTask = (stepName: string) => {
  const tasks = {
    '数据预处理': [
      '清理文本格式...',
      '标准化医学术语...',
      '验证数据完整性...',
      '构建分析索引...'
    ],
    '规则引擎初始化': [
      '加载质控规则库...',
      '编译规则表达式...',
      '初始化评分权重...',
      '验证规则完整性...'
    ],
    'AI模型分析': [
      '调用大语言模型...',
      '分析病案语义...',
      '识别关键信息...',
      '计算相似度得分...'
    ],
    '问题识别与分类': [
      '检测质控问题...',
      '分析问题严重程度...',
      '归类问题类型...',
      '生成问题报告...'
    ],
    '生成分析报告': [
      '汇总分析结果...',
      '生成改进建议...',
      '格式化报告内容...',
      '保存分析数据...'
    ]
  }
  
  const stepTasks = tasks[stepName as keyof typeof tasks] || ['处理中...']
  return stepTasks[Math.floor(Math.random() * stepTasks.length)]
}

const addLog = (level: 'info' | 'warn' | 'error' | 'debug', message: string) => {
  logs.value.push({
    timestamp: new Date(),
    level,
    message
  })
  
  // 限制日志数量
  if (logs.value.length > 100) {
    logs.value.shift()
  }
  
  // 自动滚动到底部
  if (autoScroll.value) {
    nextTick(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    })
  }
}

const pauseAnalysis = () => {
  status.value = 'paused'
  addLog('warn', '分析已暂停')
  emit('analysis-paused')
}

const resumeAnalysis = () => {
  status.value = 'running'
  addLog('info', '分析已恢复')
  emit('analysis-resumed')
}

const stopAnalysis = () => {
  status.value = 'idle'
  addLog('warn', '分析已停止')
  emit('analysis-stopped')
}

const restartAnalysis = () => {
  logs.value = []
  startAnalysis()
}

const clearLogs = () => {
  logs.value = []
}

// 样式相关方法
const getStatusColor = (status: string) => {
  const colors = {
    idle: 'text-slate-400',
    running: 'text-blue-400',
    paused: 'text-amber-400',
    completed: 'text-emerald-400',
    failed: 'text-red-400'
  }
  return colors[status as keyof typeof colors] || 'text-slate-400'
}

const getStatusLabel = (status: string) => {
  const labels = {
    idle: '待开始',
    running: '分析中',
    paused: '已暂停',
    completed: '已完成',
    failed: '分析失败'
  }
  return labels[status as keyof typeof labels] || status
}

const getProgressColor = (status: string) => {
  const colors = {
    idle: '#64748b',
    running: '#3b82f6',
    paused: '#f59e0b',
    completed: '#10b981',
    failed: '#ef4444'
  }
  return colors[status as keyof typeof colors] || '#64748b'
}

const getStepCardClass = (stepStatus: string, index: number) => {
  if (stepStatus === 'running') {
    return 'border-blue-500/50 bg-blue-500/10'
  } else if (stepStatus === 'completed') {
    return 'border-emerald-500/30 bg-emerald-500/5'
  } else if (stepStatus === 'failed') {
    return 'border-red-500/30 bg-red-500/5'
  } else if (index < currentStep.value - 1) {
    return 'border-slate-600/30 bg-slate-700/20'
  }
  return 'border-slate-600/20 bg-slate-700/10'
}

const getStepIconClass = (stepStatus: string, index: number) => {
  if (stepStatus === 'running') {
    return 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
  } else if (stepStatus === 'completed') {
    return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
  } else if (stepStatus === 'failed') {
    return 'bg-red-500/20 text-red-400 border border-red-500/30'
  }
  return 'bg-slate-600/20 text-slate-400 border border-slate-600/30'
}

const getStepIcon = (stepStatus: string) => {
  const icons = {
    pending: ClockCircleOutlined,
    running: LoadingOutlined,
    completed: CheckOutlined,
    failed: CloseOutlined
  }
  return icons[stepStatus as keyof typeof icons] || ClockCircleOutlined
}

const getStepStatusColor = (stepStatus: string) => {
  const colors = {
    pending: 'default',
    running: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[stepStatus as keyof typeof colors] || 'default'
}

const getStepStatusLabel = (stepStatus: string) => {
  const labels = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[stepStatus as keyof typeof labels] || stepStatus
}

const getStepProgressColor = (stepStatus: string) => {
  return stepStatus === 'completed' ? '#10b981' : '#3b82f6'
}

const getLogLevelClass = (level: string) => {
  const classes = {
    info: 'text-slate-300',
    warn: 'text-amber-300',
    error: 'text-red-300',
    debug: 'text-slate-400'
  }
  return classes[level as keyof typeof classes] || 'text-slate-300'
}

const getLogLevelColor = (level: string) => {
  const colors = {
    info: 'text-blue-400',
    warn: 'text-amber-400',
    error: 'text-red-400',
    debug: 'text-slate-500'
  }
  return colors[level as keyof typeof colors] || 'text-slate-400'
}

const formatDuration = (seconds: number) => {
  if (seconds < 60) {
    return `${seconds}秒`
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}分${remainingSeconds}秒`
}

const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 生命周期
onMounted(() => {
  if (props.autoStart) {
    startAnalysis()
  }
})

onUnmounted(() => {
  if (progressTimer) {
    clearInterval(progressTimer)
  }
  if (logTimer) {
    clearInterval(logTimer)
  }
})

// 暴露方法
defineExpose({ startAnalysis,
  pauseAnalysis,
  resumeAnalysis,
  stopAnalysis,
  restartAnalysis
  })
</script>

<style scoped>
.overall-progress :deep(.ant-progress-bg) {
  transition: all 0.3s ease;
}

.step-status-tag {
  border: none !important;
  border-radius: 0.5rem !important;
  font-weight: 600 !important;
  font-size: 10px !important;
}

.log-container {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
}

.log-container::-webkit-scrollbar {
  width: 6px;
}

.log-container::-webkit-scrollbar-track {
  background: rgba(71, 85, 105, 0.2);
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 3px;
}

.log-container::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}

.log-entry {
  animation: slideInLeft 0.3s ease-out;
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.step-item {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.step-item:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .grid-cols-2.md\\:grid-cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .grid-cols-2.md\\:grid-cols-4.gap-3 {
    grid-template-columns: 1fr;
  }
  
  .step-item {
    padding: 1rem;
  }
  
  .log-container {
    height: 12rem;
  }
}
</style>
