<template>
  <div class="batch-upload-container">
    <!-- 上传区域 -->
    <div
      ref="uploadArea"
      class="upload-area"
      :class="{
        'drag-over': isDragOver,
        'uploading': isUploading
      }"
      @drop="handleDrop"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".pdf,.doc,.docx,.txt"
        @change="handleFileSelect"
        class="hidden"
      />
      
      <div class="upload-content">
        <div v-if="!isUploading" class="upload-prompt">
          <div class="upload-icon">
            <i class="fas fa-cloud-upload-alt text-6xl text-blue-500"></i>
          </div>
          <h3 class="text-xl font-semibold text-gray-700 mb-2">
            拖拽文件到此处或点击上传
          </h3>
          <p class="text-gray-500 mb-4">
            支持 PDF、DOC、DOCX、TXT 格式，单个文件最大10MB
          </p>
          <div class="upload-stats">
            <span class="text-sm text-gray-400">
              已选择 {{ selectedFiles.length }} 个文件
              <span v-if="totalSize > 0">
                ({{ formatFileSize(totalSize) }})
              </span>
            </span>
          </div>
        </div>

        <div v-else class="upload-progress">
          <div class="progress-circle">
            <i class="fas fa-spinner fa-spin text-4xl text-blue-500"></i>
          </div>
          <h3 class="text-xl font-semibold text-gray-700 mb-2">
            正在上传文件...
          </h3>
          <div class="progress-details">
            <div class="progress-bar-container">
              <div class="progress-bar">
                <div 
                  class="progress-fill"
                  :style="{ width: uploadProgress + '%' }"
                ></div>
              </div>
              <span class="progress-text">{{ uploadProgress }}%</span>
            </div>
            <p class="text-sm text-gray-500 mt-2">
              {{ processedFiles }}/{{ totalFiles }} 个文件已处理
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- 文件列表 -->
    <div v-if="selectedFiles.length > 0" class="file-list mt-6">
      <div class="file-list-header">
        <h4 class="text-lg font-semibold text-gray-700">
          待上传文件 ({{ selectedFiles.length }})
        </h4>
        <div class="file-actions">
          <button
            @click="clearFiles"
            class="btn-secondary"
            :disabled="isUploading"
          >
            <i class="fas fa-trash mr-2"></i>
            清空
          </button>
          <button
            @click="startUpload"
            class="btn-primary"
            :disabled="isUploading || selectedFiles.length === 0"
          >
            <i class="fas fa-upload mr-2"></i>
            开始上传
          </button>
        </div>
      </div>

      <div class="file-items">
        <div
          v-for="(file, index) in selectedFiles"
          :key="index"
          class="file-item"
          :class="{
            'file-success': file.status === 'success',
            'file-error': file.status === 'error',
            'file-uploading': file.status === 'uploading'
          }"
        >
          <div class="file-info">
            <div class="file-icon">
              <i :class="getFileIcon(file.type)"></i>
            </div>
            <div class="file-details">
              <div class="file-name">{{ file.name }}</div>
              <div class="file-meta">
                {{ formatFileSize(file.size) }} • {{ getFileType(file.type) }}
              </div>
            </div>
          </div>

          <div class="file-status">
            <div v-if="file.status === 'pending'" class="status-pending">
              <i class="fas fa-clock text-gray-400"></i>
              <span class="text-sm text-gray-500">等待中</span>
            </div>
            <div v-else-if="file.status === 'uploading'" class="status-uploading">
              <i class="fas fa-spinner fa-spin text-blue-500"></i>
              <span class="text-sm text-blue-600">上传中</span>
            </div>
            <div v-else-if="file.status === 'success'" class="status-success">
              <i class="fas fa-check-circle text-green-500"></i>
              <span class="text-sm text-green-600">成功</span>
            </div>
            <div v-else-if="file.status === 'error'" class="status-error">
              <i class="fas fa-exclamation-circle text-red-500"></i>
              <span class="text-sm text-red-600">失败</span>
              <div class="error-message text-xs text-red-500 mt-1">
                {{ file.error }}
              </div>
            </div>
          </div>

          <div class="file-actions">
            <button
              v-if="file.status === 'error'"
              @click="retryFile(index)"
              class="btn-retry"
              :disabled="isUploading"
            >
              <i class="fas fa-redo text-sm"></i>
            </button>
            <button
              @click="removeFile(index)"
              class="btn-remove"
              :disabled="isUploading"
            >
              <i class="fas fa-times text-sm"></i>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 上传结果统计 -->
    <div v-if="uploadComplete" class="upload-summary mt-6">
      <div class="summary-card">
        <div class="summary-header">
          <i class="fas fa-chart-pie text-2xl text-blue-500"></i>
          <h4 class="text-lg font-semibold text-gray-700">上传结果</h4>
        </div>
        <div class="summary-stats">
          <div class="stat-item">
            <span class="stat-label">总文件数</span>
            <span class="stat-value">{{ totalFiles }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">成功上传</span>
            <span class="stat-value text-green-600">{{ successCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">上传失败</span>
            <span class="stat-value text-red-600">{{ errorCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">成功率</span>
            <span class="stat-value">{{ successRate }}%</span>
          </div>
        </div>
        <div class="summary-actions">
          <button
            v-if="errorCount > 0"
            @click="retryFailedFiles"
            class="btn-secondary"
          >
            <i class="fas fa-redo mr-2"></i>
            重试失败文件
          </button>
          <button
            @click="resetUpload"
            class="btn-primary"
          >
            <i class="fas fa-plus mr-2"></i>
            继续上传
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { useBatchUpload } from '@/composables/useBatchUpload'

// 接口定义
interface UploadFile {
  name: string
  size: number
  type: string
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  id?: string
}

// 组件属性
const props = defineProps<{
  maxFileSize?: number // 单个文件最大大小 (MB)
  maxTotalSize?: number // 总文件最大大小 (MB)
  acceptedTypes?: string[] // 接受的文件类型
}>()

// 默认配置
const maxFileSize = props.maxFileSize || 10 // 10MB
const maxTotalSize = props.maxTotalSize || 100 // 100MB
const acceptedTypes = props.acceptedTypes || ['pdf', 'doc', 'docx', 'txt']

// 响应式数据
const uploadArea = ref<HTMLElement>()
const fileInput = ref<HTMLInputElement>()
const selectedFiles = ref<UploadFile[]>([])
const isDragOver = ref(false)
const isUploading = ref(false)
const uploadProgress = ref(0)
const processedFiles = ref(0)
const uploadComplete = ref(false)

// 使用批量上传组合式函数
const { uploadBatch, uploadProgress: batchProgress } = useBatchUpload()

// 导入模拟版本作为备用
import { useBatchUploadMock } from '@/composables/useBatchUploadMock'
const mockUpload = useBatchUploadMock()

// 计算属性
const totalSize = computed(() => 
  selectedFiles.value.reduce((sum, file) => sum + file.size, 0)
)

const totalFiles = computed(() => selectedFiles.value.length)

const successCount = computed(() => 
  selectedFiles.value.filter(file => file.status === 'success').length
)

const errorCount = computed(() => 
  selectedFiles.value.filter(file => file.status === 'error').length
)

const successRate = computed(() => {
  if (totalFiles.value === 0) return 0
  return Math.round((successCount.value / totalFiles.value) * 100)
})

// 文件处理方法
const validateFile = (file: File): string | null => {
  // 检查文件类型
  const fileExtension = file.name.split('.').pop()?.toLowerCase()
  if (!fileExtension || !acceptedTypes.includes(fileExtension)) {
    return `不支持的文件类型: ${fileExtension}`
  }

  // 检查文件大小
  if (file.size > maxFileSize * 1024 * 1024) {
    return `文件大小超过限制: ${formatFileSize(file.size)} > ${maxFileSize}MB`
  }

  return null
}

const addFiles = (files: FileList | File[]) => {
  const fileArray = Array.from(files)
  const newFiles: UploadFile[] = []

  for (const file of fileArray) {
    // 验证文件
    const error = validateFile(file)
    if (error) {
      message.error(`${file.name}: ${error}`)
      continue
    }

    // 检查是否已存在
    const exists = selectedFiles.value.some(f => 
      f.name === file.name && f.size === file.size
    )
    if (exists) {
      message.warning(`文件已存在: ${file.name}`)
      continue
    }

    newFiles.push({
      name: file.name,
      size: file.size,
      type: file.type,
      file,
      status: 'pending'
    })
  }

  // 检查总大小限制
  const newTotalSize = totalSize.value + newFiles.reduce((sum, f) => sum + f.size, 0)
  if (newTotalSize > maxTotalSize * 1024 * 1024) {
    message.error(`总文件大小超过限制: ${formatFileSize(newTotalSize)} > ${maxTotalSize}MB`)
    return
  }

  selectedFiles.value.push(...newFiles)
  message.success(`已添加 ${newFiles.length} 个文件`)
}

// 事件处理
const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = false
  
  const files = e.dataTransfer?.files
  if (files) {
    addFiles(files)
  }
}

const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = true
}

const handleDragLeave = (e: DragEvent) => {
  e.preventDefault()
  isDragOver.value = false
}

const triggerFileInput = () => {
  if (!isUploading.value) {
    fileInput.value?.click()
  }
}

const handleFileSelect = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files) {
    addFiles(target.files)
    target.value = '' // 清空input，允许重复选择同一文件
  }
}

// 文件操作
const removeFile = (index: number) => {
  selectedFiles.value.splice(index, 1)
}

const clearFiles = () => {
  selectedFiles.value = []
  uploadComplete.value = false
}

const retryFile = (index: number) => {
  selectedFiles.value[index].status = 'pending'
  selectedFiles.value[index].error = undefined
}

const retryFailedFiles = () => {
  selectedFiles.value.forEach(file => {
    if (file.status === 'error') {
      file.status = 'pending'
      file.error = undefined
    }
  })
  startUpload()
}

const resetUpload = () => {
  selectedFiles.value = []
  uploadComplete.value = false
  uploadProgress.value = 0
  processedFiles.value = 0
}

// 上传处理
const startUpload = async () => {
  if (selectedFiles.value.length === 0) return

  isUploading.value = true
  uploadComplete.value = false
  uploadProgress.value = 0
  processedFiles.value = 0

  try {
    // 只上传待处理的文件
    const pendingFiles = selectedFiles.value.filter(f => f.status === 'pending')
    
    await uploadBatch(pendingFiles, {
      onProgress: (progress) => {
        uploadProgress.value = progress
      },
      onFileComplete: (index: any,  success: any, error: any) => {
        const file = pendingFiles[index]
        if (file) {
          file.status = success ? 'success' : 'error'
          if (error) file.error = error
          processedFiles.value++
        }
      }
    })

    uploadComplete.value = true
    message.success(`批量上传完成！成功: ${successCount.value}, 失败: ${errorCount.value}`)
  } catch (error) {
    console.error('批量上传失败:', error)
    message.error('批量上传过程中发生错误')
  } finally {
    isUploading.value = false
  }
}

// 工具函数
const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getFileIcon = (type: string): string => {
  if (type.includes('pdf')) return 'fas fa-file-pdf text-red-500'
  if (type.includes('word') || type.includes('doc')) return 'fas fa-file-word text-blue-500'
  if (type.includes('text')) return 'fas fa-file-alt text-gray-500'
  return 'fas fa-file text-gray-400'
}

const getFileType = (type: string): string => {
  if (type.includes('pdf')) return 'PDF'
  if (type.includes('word') || type.includes('doc')) return 'Word'
  if (type.includes('text')) return 'Text'
  return '未知'
}

// 生命周期
onMounted(() => {
  // 防止页面默认的拖拽行为
  document.addEventListener('dragover', (e) => e.preventDefault())
  document.addEventListener('drop', (e) => e.preventDefault())
})

onUnmounted(() => {
  document.removeEventListener('dragover', (e) => e.preventDefault())
  document.removeEventListener('drop', (e) => e.preventDefault())
})
</script>

<style scoped>
.batch-upload-container {
  @apply max-w-4xl mx-auto p-6;
}

.upload-area {
  @apply border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer transition-all duration-300;
  min-height: 200px;
}

.upload-area:hover {
  @apply border-blue-400 bg-blue-50;
}

.upload-area.drag-over {
  @apply border-blue-500 bg-blue-100;
}

.upload-area.uploading {
  @apply cursor-not-allowed bg-gray-50;
}

.upload-content {
  @apply flex flex-col items-center justify-center h-full;
}

.upload-icon {
  @apply mb-4;
}

.upload-stats {
  @apply mt-4 p-3 bg-gray-100 rounded-lg;
}

.progress-circle {
  @apply mb-4;
}

.progress-bar-container {
  @apply flex items-center space-x-3 w-full max-w-md;
}

.progress-bar {
  @apply flex-1 h-2 bg-gray-200 rounded-full overflow-hidden;
}

.progress-fill {
  @apply h-full bg-blue-500 transition-all duration-300;
}

.progress-text {
  @apply text-sm font-medium text-gray-600 min-w-[3rem];
}

.file-list {
  @apply bg-white rounded-xl border border-gray-200 overflow-hidden;
}

.file-list-header {
  @apply flex items-center justify-between p-4 bg-gray-50 border-b border-gray-200;
}

.file-actions {
  @apply flex items-center space-x-2;
}

.file-items {
  @apply divide-y divide-gray-100;
}

.file-item {
  @apply flex items-center justify-between p-4 hover:bg-gray-50 transition-colors duration-200;
}

.file-item.file-success {
  @apply bg-green-50 border-l-4 border-green-500;
}

.file-item.file-error {
  @apply bg-red-50 border-l-4 border-red-500;
}

.file-item.file-uploading {
  @apply bg-blue-50 border-l-4 border-blue-500;
}

.file-info {
  @apply flex items-center space-x-3 flex-1;
}

.file-icon {
  @apply text-2xl;
}

.file-details {
  @apply flex-1;
}

.file-name {
  @apply font-medium text-gray-800 truncate;
}

.file-meta {
  @apply text-sm text-gray-500;
}

.file-status {
  @apply flex items-center space-x-2 min-w-[100px];
}

.file-actions {
  @apply flex items-center space-x-1 ml-4;
}

.upload-summary {
  @apply bg-white rounded-xl border border-gray-200 overflow-hidden;
}

.summary-card {
  @apply p-6;
}

.summary-header {
  @apply flex items-center space-x-3 mb-4;
}

.summary-stats {
  @apply grid grid-cols-2 md:grid-cols-4 gap-4 mb-6;
}

.stat-item {
  @apply text-center p-3 bg-gray-50 rounded-lg;
}

.stat-label {
  @apply block text-sm text-gray-500 mb-1;
}

.stat-value {
  @apply block text-xl font-bold text-gray-800;
}

.summary-actions {
  @apply flex items-center justify-center space-x-3;
}

/* 按钮样式 */
.btn-primary {
  @apply px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-secondary {
  @apply px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-retry {
  @apply p-2 text-orange-600 hover:bg-orange-100 rounded-lg transition-colors duration-200 disabled:opacity-50;
}

.btn-remove {
  @apply p-2 text-red-600 hover:bg-red-100 rounded-lg transition-colors duration-200 disabled:opacity-50;
}

.hidden {
  display: none;
}

.error-message {
  @apply max-w-[200px] truncate;
}

/* 状态指示器 */
.status-pending,
.status-uploading,
.status-success,
.status-error {
  @apply flex items-center space-x-1;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .batch-upload-container {
    @apply p-4;
  }

  .upload-area {
    @apply p-6;
  }

  .file-list-header {
    @apply flex-col space-y-3 items-start;
  }

  .file-actions {
    @apply w-full justify-end;
  }

  .file-item {
    @apply flex-col items-start space-y-2;
  }

  .file-info {
    @apply w-full;
  }

  .file-status {
    @apply w-full justify-between;
  }
}
</style>
