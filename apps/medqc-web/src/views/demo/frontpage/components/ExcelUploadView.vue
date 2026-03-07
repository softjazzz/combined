<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 overflow-hidden">
    <!-- Step 1: 上传 -->
    <div v-if="currentStep === 'upload'" class="flex-1 flex flex-col p-6 overflow-hidden">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <button @click="$emit('back')" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
            <ArrowLeftOutlined class="text-lg" />
          </button>
          <div>
            <h2 class="text-xl font-semibold text-slate-800 dark:text-white">DRG/DIP 数据分析</h2>
            <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">上传任意格式的 Excel 文件，AI 自动识别字段并生成分析报表</p>
          </div>
        </div>
      </div>

      <div class="flex-1 flex gap-6 overflow-hidden">
        <!-- Upload Area -->
        <div class="flex-1 flex flex-col">
          <!-- Drag & Drop Zone -->
          <div
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="handleDrop"
            :class="[
              'flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center transition-all cursor-pointer',
              isDragging 
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' 
                : 'border-slate-300 dark:border-slate-600 hover:border-blue-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            ]"
            @click="triggerFileInput"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".xlsx,.xls,.csv,.zip"
              class="hidden"
              @change="handleFileSelect"
            />
            
            <div v-if="!selectedFile && !uploading" class="text-center p-8">
              <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <CloudUploadOutlined class="text-4xl text-blue-500" />
              </div>
              <h3 class="text-lg font-medium text-slate-700 dark:text-white mb-2">
                拖拽文件到此处或点击上传
              </h3>
              <p class="text-sm text-slate-500 dark:text-slate-400">
                支持 .xlsx, .xls, .csv, .zip（多文件压缩包）格式
              </p>
              <p class="text-xs text-slate-400 mt-2">
                ✨ 无需固定模板，AI 自动识别字段
              </p>
            </div>
            
            <!-- Selected File Preview -->
            <div v-else-if="selectedFile && !uploading" class="text-center p-8">
              <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <FileExcelOutlined class="text-4xl text-green-500" />
              </div>
              <h3 class="text-lg font-medium text-slate-700 dark:text-white mb-2">
                {{ selectedFile.name }}
              </h3>
              <p class="text-sm text-slate-500 dark:text-slate-400 mb-4">
                {{ formatFileSize(selectedFile.size) }}
              </p>
              <div class="flex gap-3 justify-center">
                <button
                  @click.stop="clearFile"
                  class="px-4 py-2 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors text-sm"
                >
                  重新选择
                </button>
                <button
                  @click.stop="smartUploadFile"
                  class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm flex items-center gap-2"
                >
                  <UploadOutlined />
                  开始上传分析
                </button>
              </div>
            </div>
            
            <!-- Uploading State -->
            <div v-else class="text-center p-8">
              <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                <LoadingOutlined class="text-4xl text-blue-500 animate-spin" />
              </div>
              <h3 class="text-lg font-medium text-slate-700 dark:text-white mb-2">
                正在上传...
              </h3>
              <p class="text-sm text-slate-500 dark:text-slate-400">
                请稍候，正在解析文件结构
              </p>
            </div>
          </div>
        </div>
        
        <!-- Batch History -->
        <div class="w-80 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 flex flex-col overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200">历史批次</h3>
            <button @click="loadBatches" class="text-blue-500 hover:text-blue-600">
              <SyncOutlined :class="{ 'animate-spin': loadingBatches }" />
            </button>
          </div>
          
          <div class="flex-1 overflow-y-auto">
            <div v-if="batches.length === 0" class="p-8 text-center text-slate-400">
              暂无上传记录
            </div>
            <div
              v-else
              v-for="batch in batches"
              :key="batch.batch_id"
              @click="selectBatch(batch)"
              :class="[
                'p-4 border-b border-slate-100 dark:border-slate-700 cursor-pointer transition-colors',
                selectedBatchId === batch.batch_id 
                  ? 'bg-blue-50 dark:bg-blue-900/20 border-l-4 border-l-blue-500' 
                  : 'hover:bg-slate-50 dark:hover:bg-slate-700/30'
              ]"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium text-slate-700 dark:text-white">{{ batch.batch_id.substring(6, 21) }}</span>
                <span class="text-xs text-blue-500">{{ batch.count }} 条</span>
              </div>
              <div class="text-xs text-slate-500">
                费用: ¥{{ formatNumber(batch.total_cost) }}
              </div>
              <div class="text-xs text-slate-400 mt-1">
                {{ formatDate(batch.created_at) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 2: 字段映射 -->
    <FieldMappingStep
      v-else-if="currentStep === 'mapping'"
      :file-id="uploadedFileId"
      :file-name="uploadedFileName"
      :row-count="uploadedRowCount"
      :columns="uploadedColumns"
      :sample-data="uploadedSampleData"
      @back="currentStep = 'upload'"
      @confirmed="handleMappingConfirmed"
    />

    <!-- Step 3: 报表生成完成 → 跳转事后分析 -->
    <div v-else-if="currentStep === 'complete'" class="flex-1 flex flex-col items-center justify-center p-8">
      <div class="w-24 h-24 rounded-full bg-green-100 flex items-center justify-center mb-6">
        <CheckCircleOutlined class="text-5xl text-green-500" />
      </div>
      <h2 class="text-2xl font-semibold text-slate-800 mb-2">分析完成！</h2>
      <p class="text-slate-500 mb-6">
        已处理 {{ analysisResult?.row_count || 0 }} 条病例数据，生成 {{ chartCount }} 个分析图表
      </p>
      <div class="flex gap-4">
        <a-button @click="currentStep = 'upload'">继续上传</a-button>
        <a-button type="primary" size="large" @click="goToAnalysis">
          查看分析报表 →
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  CloudUploadOutlined,
  FileExcelOutlined,
  UploadOutlined,
  LoadingOutlined,
  SyncOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import FieldMappingStep from './FieldMappingStep.vue'

interface BatchInfo {
  batch_id: string
  count: number
  created_at: string
  total_cost: number
}

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'goAnalysis', sessionId: string, batchId: string): void
  (e: 'go-analysis', sessionId: string, batchId: string): void
  (e: 'analysisReady', data: {
    charts: any
    aiInsights: string[]
    analysisResults: any
  }): void
}>()

// 步骤控制
const currentStep = ref<'upload' | 'mapping' | 'complete'>('upload')

// 上传状态
const apiBaseUrl = ((import.meta as any)?.env?.VITE_API_BASE_URL || '').trim().replace(/\/$/, '')
const API_BASE = apiBaseUrl ? `${apiBaseUrl}/api/v1/drg` : '/api/v1/drg'
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const isDragging = ref(false)
const uploading = ref(false)

// 上传结果（传给字段映射步骤）
const uploadedFileId = ref('')
const uploadedFileName = ref('')
const uploadedRowCount = ref(0)
const uploadedColumns = ref<string[]>([])
const uploadedSampleData = ref<Record<string, any>[]>([])

// 分析结果
const analysisResult = ref<any>(null)
const chartCount = computed(() => Object.keys(analysisResult.value?.charts || {}).length)

// 历史批次
const batches = ref<BatchInfo[]>([])
const loadingBatches = ref(false)
const selectedBatchId = ref<string | null>(null)
const currentSessionId = ref<string | null>(null)

// 方法
const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files[0]) {
    const file = files[0]
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (['xlsx', 'xls', 'csv', 'zip'].includes(ext || '')) {
      selectedFile.value = file
    } else {
      message.error('不支持的文件格式，请上传 Excel/CSV/ZIP 文件')
    }
  }
}

const clearFile = () => {
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const smartUploadFile = async () => {
  if (!selectedFile.value) return
  
  uploading.value = true
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    const response = await fetch(`${API_BASE}/smart-upload`, {
      method: 'POST',
      body: formData
    })
    
    let data
    try {
      data = await response.json()
    } catch {
      throw new Error(`服务器响应异常: ${response.status} ${response.statusText}`)
    }
    
    if (response.ok && data.success) {
      uploadedFileId.value = data.file_id
      uploadedFileName.value = data.filename
      uploadedRowCount.value = data.row_count
      uploadedColumns.value = data.columns || []
      uploadedSampleData.value = data.sample_data || []
      
      message.success(`文件上传成功！共 ${data.row_count} 行数据，${data.file_count} 个文件`)
      
      // 跳转到字段映射步骤
      currentStep.value = 'mapping'
    } else {
      throw new Error(data.detail || data.error || '上传失败')
    }
  } catch (err: any) {
    console.error('Smart upload error:', err)
    message.error(err.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

const handleMappingConfirmed = (data: {
  fileId: string
  mappings: Record<string, string>
  analysisResults: any
  charts: any
  aiInsights: string[]
}) => {
  analysisResult.value = {
    charts: data.charts,
    aiInsights: data.aiInsights,
    analysisResults: data.analysisResults,
    row_count: data.analysisResults?.overview?.total_cases || 0,
  }
  
  // 通知父组件分析结果已就绪
  emit('analysisReady', {
    charts: data.charts,
    aiInsights: data.aiInsights,
    analysisResults: data.analysisResults,
  })
  
  currentStep.value = 'complete'
}

const goToAnalysis = () => {
  if (currentSessionId.value) {
    emit('go-analysis', currentSessionId.value, '')
  }
  // 如果没有 sessionId，直接通知父组件切换到分析视图
  emit('analysisReady', {
    charts: analysisResult.value?.charts || {},
    aiInsights: analysisResult.value?.aiInsights || [],
    analysisResults: analysisResult.value?.analysisResults || {},
  })
}

// 历史批次
const loadBatches = async (sessionId?: string) => {
  const sid = sessionId || currentSessionId.value
  if (!sid) {
    batches.value = []
    return
  }
  loadingBatches.value = true
  try {
    const response = await fetch(`${API_BASE}/batches?session_id=${sid}`)
    const data = await response.json()
    if (data.success) {
      batches.value = data.data
    }
  } catch (err) {
    console.error('加载批次列表失败:', err)
  } finally {
    loadingBatches.value = false
  }
}

const selectBatch = (batch: BatchInfo) => {
  if (!currentSessionId.value) return
  selectedBatchId.value = batch.batch_id
  emit('go-analysis', currentSessionId.value, batch.batch_id)
}

// 工具函数
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const formatNumber = (num: number): string => {
  return num?.toLocaleString('zh-CN') || '0'
}

const formatDate = (dateStr: string): string => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  })
}

// 生命周期
onMounted(() => {
  // 无需在 mount 时加载批次，因为没有 session
})
</script>
