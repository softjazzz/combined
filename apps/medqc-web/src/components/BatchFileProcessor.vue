<template>
  <div class="batch-file-processor">
    <!-- 文件上传区域 -->
    <div class="upload-section">
      <a-upload-dragger
        :file-list="fileList"
        :before-upload="beforeUpload"
        :custom-request="handleFileUpload"
        accept=".pdf,.doc,.docx,.txt"
        :multiple="true"
        :show-upload-list="false"
        class="enhanced-upload-dragger"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p class="ant-upload-hint">
          支持 PDF、Word、文本文件格式，可批量上传多个文件
        </p>
      </a-upload-dragger>
    </div>

    <!-- 文件列表和统计信息 -->
    <div v-if="uploadedFiles.length > 0" class="file-management-section">
      <!-- 统计信息 -->
      <div class="file-stats">
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic title="总文件数" :value="uploadedFiles.length" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="总大小" :value="totalSize" suffix="MB" :precision="2" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="已解析" :value="parsedCount" :suffix="`/ ${uploadedFiles.length}`" />
          </a-col>
          <a-col :span="6">
            <a-statistic title="成功率" :value="successRate" suffix="%" :precision="1" />
          </a-col>
        </a-row>
      </div>

      <!-- 批量操作按钮 -->
      <div class="batch-actions">
        <a-space size="large">
          <a-button 
            type="primary" 
            size="large"
            :loading="batchProcessing" 
            :disabled="uploadedFiles.length === 0"
            @click="startBatchProcessing"
          >
            <template #icon><ThunderboltOutlined /></template>
            {{ batchProcessing ? '解析中...' : '一键解析所有文件' }}
          </a-button>
          
          <a-button 
            v-if="batchProcessing"
            @click="pauseProcessing"
            :disabled="!canPause"
          >
            <template #icon><PauseCircleOutlined /></template>
            {{ isPaused ? '继续' : '暂停' }}
          </a-button>
          
          <a-button 
            v-if="batchProcessing"
            @click="cancelProcessing"
            danger
          >
            <template #icon><StopOutlined /></template>
            取消
          </a-button>
          
          <a-button @click="clearAllFiles" danger>
            <template #icon><DeleteOutlined /></template>
            清空所有
          </a-button>
        </a-space>
      </div>

      <!-- 整体进度条 -->
      <div v-if="batchProcessing || completedFiles > 0" class="overall-progress">
        <div class="progress-header">
          <span class="progress-title">整体进度</span>
          <span class="progress-info">
            {{ completedFiles }} / {{ uploadedFiles.length }} 
            ({{ currentProcessingFile ? `正在处理: ${currentProcessingFile}` : '等待中' }})
          </span>
        </div>
        <a-progress 
          :percent="overallProgress" 
          :status="batchProcessing ? 'active' : (hasErrors ? 'exception' : 'success')"
          :show-info="false"
        />
      </div>

      <!-- 文件列表 -->
      <div class="file-list">
        <a-list
          :data-source="uploadedFiles"
          :pagination="{ pageSize: 10, showSizeChanger: true }"
        >
          <template #renderItem="{ item, index }">
            <a-list-item 
              :class="['file-item', { 'selected': selectedFileIndex === index }]"
              @click="selectFile(index)"
            >
              <template #actions>
                <a-space>
                  <a-button 
                    v-if="!item.processing && !item.parsed"
                    size="small" 
                    @click.stop="processSingleFile(index)"
                    :loading="item.processing"
                  >
                    解析
                  </a-button>
                  <a-button 
                    size="small" 
                    @click.stop="removeFile(index)"
                    danger
                  >
                    删除
                  </a-button>
                </a-space>
              </template>
              
              <a-list-item-meta>
                <template #title>
                  <div class="file-title">
                    <component :is="getFileIcon(item.type)" class="file-icon" />
                    <span class="file-name">{{ item.name }}</span>
                    <a-tag :color="getStatusColor(item.status)" size="small">
                      {{ getStatusText(item.status) }}
                    </a-tag>
                  </div>
                </template>
                <template #description>
                  <div class="file-details">
                    <span>大小: {{ formatFileSize(item.size) }}</span>
                    <span v-if="item.processing">
                      <a-spin size="small" />
                      解析中...
                    </span>
                    <span v-else-if="item.parsed && item.confidence">
                      置信度: {{ Math.round(item.confidence) }}%
                    </span>
                    <span v-else-if="item.error" class="error-text">
                      错误: {{ item.error }}
                    </span>
                  </div>
                </template>
              </a-list-item-meta>
              
              <!-- 单个文件进度条 -->
              <div v-if="item.processing" class="file-progress">
                <a-progress 
                  :percent="item.progress || 0" 
                  size="small" 
                  status="active"
                  :show-info="false"
                />
              </div>
            </a-list-item>
          </template>
        </a-list>
      </div>

      <!-- 批量操作结果 -->
      <div v-if="batchResults.length > 0" class="batch-results">
        <a-divider>批量处理结果</a-divider>
        <div class="results-actions">
          <a-space>
            <a-button 
              type="primary" 
              @click="showBatchResultsModal"
              :disabled="batchResults.length === 0"
            >
              <template #icon><EyeOutlined /></template>
              查看所有结果
            </a-button>
            <a-button @click="exportBatchResults">
              <template #icon><DownloadOutlined /></template>
              导出结果
            </a-button>
            <a-button @click="saveBatchToDatabase" :loading="saving">
              <template #icon><DatabaseOutlined /></template>
              批量保存到数据库
            </a-button>
          </a-space>
        </div>
      </div>
    </div>

    <!-- 批量结果Modal -->
    <a-modal
      v-model:open="batchResultsModalVisible"
      title="批量解析结果"
      width="1200px"
      :footer="null"
      class="batch-results-modal"
    >
      <div class="batch-results-content">
        <a-tabs v-model:activeKey="activeResultTab">
          <a-tab-pane 
            v-for="(result, index) in batchResults" 
            :key="index" 
            :tab="result.fileName"
          >
            <LLMResultModal
              :visible="true"
              :data="result.data"
              :result="result"
              :original-text="result.originalText"
              @update:visible="() => {}"
              @save-and-redirect="() => handleSingleSave(result)"
              @save-only="() => handleSingleSave(result)"
              @export-result="() => handleSingleExport(result)"
              @export-pdf="() => handleSingleExportPDF(result)"
              @go-to-import="() => {}"
            />
          </a-tab-pane>
        </a-tabs>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  InboxOutlined,
  ThunderboltOutlined,
  PauseCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  EyeOutlined,
  DownloadOutlined,
  DatabaseOutlined,
  FileOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import LLMResultModal from './LLMResultModal.vue'

// 文件状态枚举
enum FileStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

// 文件接口
interface ProcessingFile {
  id: string
  name: string
  size: number
  type: string
  file: File
  status: FileStatus
  processing: boolean
  parsed: boolean
  progress: number
  confidence?: number
  error?: string
  result?: any
  originalText?: string
}

// Props和Emits
interface Props {
  maxFileSize?: number // MB
  maxFileCount?: number
  allowedTypes?: string[]
}

interface Emits {
  (e: 'files-processed', results: any[]): void
  (e: 'single-file-processed', result: any): void
  (e: 'batch-completed', results: any[]): void
}

const props = withDefaults(defineProps<Props>(), {
  maxFileSize: 50,
  maxFileCount: 20,
  allowedTypes: () => ['.pdf', '.doc', '.docx', '.txt']
})

const emit = defineEmits<Emits>()

// 响应式数据
const fileList = ref<any[]>([])
const uploadedFiles = ref<ProcessingFile[]>([])
const selectedFileIndex = ref(-1)
const batchProcessing = ref(false)
const isPaused = ref(false)
const canPause = ref(true)
const completedFiles = ref(0)
const currentProcessingFile = ref('')
const batchResults = ref<any[]>([])
const batchResultsModalVisible = ref(false)
const activeResultTab = ref(0)
const saving = ref(false)

// 计算属性
const totalSize = computed(() => {
  return uploadedFiles.value.reduce((total, file) => total + file.size, 0) / (1024 * 1024)
})

const parsedCount = computed(() => {
  return uploadedFiles.value.filter(file => file.parsed).length
})

const successRate = computed(() => {
  if (uploadedFiles.value.length === 0) return 0
  const successCount = uploadedFiles.value.filter(file => file.status === FileStatus.COMPLETED).length
  return (successCount / uploadedFiles.value.length) * 100
})

const overallProgress = computed(() => {
  if (uploadedFiles.value.length === 0) return 0
  return (completedFiles.value / uploadedFiles.value.length) * 100
})

const hasErrors = computed(() => {
  return uploadedFiles.value.some(file => file.status === FileStatus.FAILED)
})

// 方法
const beforeUpload = (file: File) => {
  // 检查文件大小
  if (file.size > props.maxFileSize * 1024 * 1024) {
    message.error(`文件 ${file.name} 超过 ${props.maxFileSize}MB 限制`)
    return false
  }
  
  // 检查文件数量
  if (uploadedFiles.value.length >= props.maxFileCount) {
    message.error(`最多只能上传 ${props.maxFileCount} 个文件`)
    return false
  }
  
  // 检查文件类型
  const fileExt = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!props.allowedTypes.includes(fileExt)) {
    message.error(`不支持的文件类型: ${fileExt}`)
    return false
  }
  
  return false // 阻止自动上传
}

const handleFileUpload = (options: any) => {
  const { file } = options
  
  const processingFile: ProcessingFile = {
    id: Date.now() + Math.random().toString(),
    name: file.name,
    size: file.size,
    type: file.type,
    file: file,
    status: FileStatus.PENDING,
    processing: false,
    parsed: false,
    progress: 0
  }
  
  uploadedFiles.value.push(processingFile)
  message.success(`文件 ${file.name} 添加成功`)
}

const getFileIcon = (type: string) => {
  if (type.includes('pdf')) return FilePdfOutlined
  if (type.includes('word') || type.includes('document')) return FileWordOutlined
  if (type.includes('text')) return FileTextOutlined
  return FileOutlined
}

const getStatusColor = (status: FileStatus) => {
  const colorMap = {
    [FileStatus.PENDING]: 'default',
    [FileStatus.PROCESSING]: 'processing',
    [FileStatus.COMPLETED]: 'success',
    [FileStatus.FAILED]: 'error'
  }
  return colorMap[status]
}

const getStatusText = (status: FileStatus) => {
  const textMap = {
    [FileStatus.PENDING]: '等待中',
    [FileStatus.PROCESSING]: '解析中',
    [FileStatus.COMPLETED]: '已完成',
    [FileStatus.FAILED]: '失败'
  }
  return textMap[status]
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const selectFile = (index: number) => {
  selectedFileIndex.value = index
}

const removeFile = (index: number) => {
  uploadedFiles.value.splice(index, 1)
  if (selectedFileIndex.value === index) {
    selectedFileIndex.value = -1
  } else if (selectedFileIndex.value > index) {
    selectedFileIndex.value--
  }
}

const clearAllFiles = () => {
  uploadedFiles.value = []
  selectedFileIndex.value = -1
  batchResults.value = []
  completedFiles.value = 0
}

// 单个文件处理
const processSingleFile = async (index: number) => {
  const file = uploadedFiles.value[index]
  if (!file || file.processing) return
  
  try {
    file.processing = true
    file.status = FileStatus.PROCESSING
    file.progress = 0
    
    // 模拟处理进度
    const progressInterval = setInterval(() => {
      if (file.progress < 90) {
        file.progress += Math.random() * 20
      }
    }, 500)
    
    // 这里调用实际的LLM解析API
    const result = await callLLMParseAPI(file.file)
    
    clearInterval(progressInterval)
    file.progress = 100
    file.processing = false
    file.parsed = true
    file.status = FileStatus.COMPLETED
    file.result = result
    file.confidence = result.data?.confidence || 0
    
    emit('single-file-processed', result)
    message.success(`文件 ${file.name} 解析完成`)
    
  } catch (error: any) {
    file.processing = false
    file.status = FileStatus.FAILED
    file.error = error.message
    message.error(`文件 ${file.name} 解析失败: ${error.message}`)
  }
}

// 批量处理
const startBatchProcessing = async () => {
  if (uploadedFiles.value.length === 0) return
  
  batchProcessing.value = true
  isPaused.value = false
  completedFiles.value = 0
  batchResults.value = []
  
  try {
    for (let i = 0; i < uploadedFiles.value.length; i++) {
      if (!batchProcessing.value) break // 用户取消
      
      while (isPaused.value) {
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      const file = uploadedFiles.value[i]
      if (file.parsed) {
        completedFiles.value++
        continue
      }
      
      currentProcessingFile.value = file.name
      await processSingleFile(i)
      
      if (file.result) {
        batchResults.value.push({
          fileName: file.name,
          ...file.result,
          originalText: file.result.data?.content
        })
      }
      
      completedFiles.value++
    }
    
    message.success('批量解析完成!')
    emit('batch-completed', batchResults.value)
    
  } catch (error: any) {
    message.error(`批量处理失败: ${error.message}`)
  } finally {
    batchProcessing.value = false
    currentProcessingFile.value = ''
  }
}

const pauseProcessing = () => {
  isPaused.value = !isPaused.value
}

const cancelProcessing = () => {
  batchProcessing.value = false
  isPaused.value = false
  currentProcessingFile.value = ''
}

// 结果处理
const showBatchResultsModal = () => {
  batchResultsModalVisible.value = true
}

const exportBatchResults = () => {
  if (batchResults.value.length === 0) return
  
  const dataStr = JSON.stringify(batchResults.value, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `batch_results_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const saveBatchToDatabase = async () => {
  saving.value = true
  try {
    // 这里实现批量保存逻辑
    await new Promise(resolve => setTimeout(resolve, 2000)) // 模拟保存
    message.success('批量保存成功!')
  } catch (error: any) {
    message.error(`批量保存失败: ${error.message}`)
  } finally {
    saving.value = false
  }
}

const handleSingleSave = (result: any) => {
  message.success(`保存文件 ${result.fileName} 成功`)
}

const handleSingleExport = (result: any) => {
  const dataStr = JSON.stringify(result, null, 2)
  const blob = new Blob([dataStr], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${result.fileName}_result.json`
  a.click()
  URL.revokeObjectURL(url)
}

const handleSingleExportPDF = (result: any) => {
  message.info('PDF导出功能开发中...')
}

// 模拟LLM解析API调用
const callLLMParseAPI = async (file: File): Promise<any> => {
  // 这里应该调用实际的LLM解析API
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() > 0.1) { // 90%成功率
        resolve({
          success: true,
          data: {
            patientName: '测试患者',
            content: '模拟解析内容...',
            confidence: Math.random() * 40 + 60, // 60-100%
            documents: []
          }
        })
      } else {
        reject(new Error('模拟解析失败'))
      }
    }, 2000 + Math.random() * 3000) // 2-5秒
  })
}
</script>

<style scoped>
.batch-file-processor {
  padding: 16px;
}

.upload-section {
  margin-bottom: 24px;
}

.enhanced-upload-dragger {
  background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
  border: 2px dashed #91d5ff;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.enhanced-upload-dragger:hover {
  border-color: #40a9ff;
  background: linear-gradient(135deg, #e6f3ff 0%, #d6ebff 100%);
}

.file-management-section {
  background: #fafafa;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #e8e8e8;
}

.file-stats {
  background: white;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.batch-actions {
  text-align: center;
  margin-bottom: 20px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.overall-progress {
  margin-bottom: 20px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-title {
  font-weight: 600;
  color: #262626;
}

.progress-info {
  font-size: 12px;
  color: #8c8c8c;
}

.file-list {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.file-item {
  cursor: pointer;
  transition: all 0.2s ease;
  border-radius: 6px;
  margin: 4px 8px;
  padding: 8px;
}

.file-item:hover {
  background-color: #f5f5f5;
}

.file-item.selected {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
}

.file-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #1890ff;
  font-size: 16px;
}

.file-name {
  flex: 1;
  font-weight: 500;
}

.file-details {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #8c8c8c;
}

.file-progress {
  margin-top: 8px;
}

.error-text {
  color: #ff4d4f;
}

.batch-results {
  margin-top: 24px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.results-actions {
  text-align: center;
  margin-top: 16px;
}

.batch-results-modal :deep(.ant-modal-body) {
  padding: 0;
}

.batch-results-content {
  max-height: 70vh;
  overflow-y: auto;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .batch-file-processor {
    padding: 8px;
  }

  .file-management-section {
    padding: 12px;
  }

  .batch-actions {
    padding: 12px;
  }

  .batch-actions :deep(.ant-space) {
    flex-wrap: wrap;
  }

  .file-details {
    flex-direction: column;
    gap: 4px;
  }
}

/* 动画效果 */
.file-item {
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 进度条样式优化 */
.overall-progress :deep(.ant-progress-bg) {
  background: linear-gradient(90deg, #1890ff, #52c41a);
}

.file-progress :deep(.ant-progress-bg) {
  background: linear-gradient(90deg, #40a9ff, #73d13d);
}
</style>
