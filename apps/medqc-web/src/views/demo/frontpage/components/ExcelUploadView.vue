<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <button @click="$emit('back')" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors">
          <ArrowLeftOutlined class="text-lg" />
        </button>
        <div>
          <h2 class="text-xl font-semibold text-slate-800 dark:text-white">DRG 批量数据上传</h2>
          <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">上传 Excel/CSV 文件进行批量 DRG 分组分析</p>
        </div>
      </div>
      <a 
        :href="templateUrl" 
        class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm flex items-center gap-2"
      >
        <DownloadOutlined />
        下载模板
      </a>
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
            accept=".xlsx,.xls,.csv"
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
              支持 .xlsx, .xls, .csv 格式
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
                @click.stop="uploadFile"
                class="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm flex items-center gap-2"
              >
                <UploadOutlined />
                开始上传
              </button>
            </div>
          </div>
          
          <!-- Uploading State -->
          <div v-else class="text-center p-8">
            <div class="w-20 h-20 mx-auto mb-4 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
              <LoadingOutlined class="text-4xl text-blue-500 animate-spin" />
            </div>
            <h3 class="text-lg font-medium text-slate-700 dark:text-white mb-2">
              正在处理...
            </h3>
            <p class="text-sm text-slate-500 dark:text-slate-400">
              请稍候，正在进行 DRG 分组
            </p>
          </div>
        </div>
        
        <!-- Result Area -->
        <div v-if="uploadResult" class="mt-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-slate-800 dark:text-white">上传结果</h3>
            <span class="text-xs text-slate-500">批次: {{ uploadResult.batch_id }}</span>
          </div>
          
          <div class="grid grid-cols-3 gap-4 mb-4">
            <div class="bg-slate-50 dark:bg-slate-900 rounded-lg p-3 text-center">
              <div class="text-2xl font-bold text-slate-800 dark:text-white">{{ uploadResult.total_records }}</div>
              <div class="text-xs text-slate-500">总记录</div>
            </div>
            <div class="bg-green-50 dark:bg-green-900/20 rounded-lg p-3 text-center">
              <div class="text-2xl font-bold text-green-600">{{ uploadResult.success_count }}</div>
              <div class="text-xs text-green-600">成功</div>
            </div>
            <div class="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 text-center">
              <div class="text-2xl font-bold text-red-500">{{ uploadResult.failed_count }}</div>
              <div class="text-xs text-red-500">失败</div>
            </div>
          </div>
          
          <button 
            @click="goToAnalysis"
            class="w-full py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors text-sm"
          >
            查看分析结果 →
          </button>
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
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  DownloadOutlined,
  CloudUploadOutlined,
  FileExcelOutlined,
  UploadOutlined,
  LoadingOutlined,
  SyncOutlined,
} from '@ant-design/icons-vue'

interface BatchInfo {
  batch_id: string
  count: number
  created_at: string
  total_cost: number
}

interface UploadResult {
  session_id: string  // 新增：session_id
  batch_id: string
  total_records: number
  success_count: number
  failed_count: number
  results: Array<any>
}

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'goAnalysis', sessionId: string, batchId: string): void  // 更新：传递 sessionId
}>()

// State
const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const isDragging = ref(false)
const uploading = ref(false)
const uploadResult = ref<UploadResult | null>(null)
const batches = ref<BatchInfo[]>([])
const loadingBatches = ref(false)
const selectedBatchId = ref<string | null>(null)
const currentSessionId = ref<string | null>(null)  // 新增：当前 session_id

// API base URL
const API_BASE = '/api/v1/drg'
const templateUrl = computed(() => `${API_BASE}/template`)

// Methods
const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
    uploadResult.value = null
  }
}

const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files[0]) {
    const file = files[0]
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (['xlsx', 'xls', 'csv'].includes(ext || '')) {
      selectedFile.value = file
      uploadResult.value = null
    } else {
      message.error('不支持的文件格式，请上传 Excel 或 CSV 文件')
    }
  }
}

const clearFile = () => {
  selectedFile.value = null
  uploadResult.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const uploadFile = async () => {
  if (!selectedFile.value) return
  
  uploading.value = true
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    
    const response = await fetch(`${API_BASE}/batch-upload`, {
      method: 'POST',
      body: formData
    })
    
    const data = await response.json()
    
    if (data.success) {
      uploadResult.value = data
      currentSessionId.value = data.session_id  // 保存 session_id
      message.success(`上传成功！共处理 ${data.total_records} 条记录`)
      loadBatches(data.session_id)  // 传递 session_id
    } else {
      throw new Error(data.detail || '上传失败')
    }
  } catch (err: any) {
    message.error(err.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

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
  emit('goAnalysis', currentSessionId.value, batch.batch_id)
}

const goToAnalysis = () => {
  if (uploadResult.value && currentSessionId.value) {
    emit('goAnalysis', currentSessionId.value, uploadResult.value.batch_id)
  }
}

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

// Lifecycle
onMounted(() => {
  // 不在 mount 时加载批次，因为还没有 session
})
</script>
