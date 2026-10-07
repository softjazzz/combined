<template>
  <div class="upload-workstation">
    <!-- Step 1: 上传 -->
    <div v-if="currentStep === 'upload'" class="upload-page">
      <header class="upload-header mq-page-head">
        <div class="upload-title-block">
          <button class="upload-back-btn" type="button" @click="$emit('back')">
            <MqIcon name="back" class="upload-back-icon" />
          </button>
          <div>
            <span class="upload-eyebrow mq-page-eyebrow">数据与配置 · 数据导入</span>
            <h2 class="mq-page-title">DRG/DIP 数据分析</h2>
            <p>上传任意格式的 Excel 文件，AI 自动识别字段并生成分析报表</p>
          </div>
        </div>
        <div class="upload-header-meta">
          <span>只读分析</span>
          <span>Excel / CSV / ZIP</span>
        </div>
      </header>

      <div class="upload-content-grid">
        <!-- Upload Area -->
        <div class="upload-main-card mq-card">
          <!-- Drag & Drop Zone -->
          <div
            :class="['upload-dropzone', { 'upload-dropzone--dragging': isDragging }]"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".xlsx,.xls,.csv,.zip"
              class="hidden"
              @change="handleFileSelect"
            />

            <div v-if="!selectedFile && !uploading" class="upload-empty">
              <div class="upload-icon-orb">
                <MqIcon name="upload" class="upload-state-icon" />
              </div>
              <h3>拖拽文件到此处或点击上传</h3>
              <p>支持 .xlsx, .xls, .csv, .zip（多文件压缩包）格式</p>
              <div class="upload-format-row">
                <span>无需固定模板</span>
                <span>字段自动识别</span>
                <span>可生成分析报表</span>
              </div>
            </div>

            <!-- Selected File Preview -->
            <div v-else-if="selectedFile && !uploading" class="upload-selected">
              <div class="upload-icon-orb upload-icon-orb--success">
                <MqIcon name="data" class="upload-state-icon" />
              </div>
              <h3>
                {{ selectedFile.name }}
              </h3>
              <p>
                {{ formatFileSize(selectedFile.size) }}
              </p>
              <div class="upload-action-row">
                <button class="upload-secondary-btn" type="button" @click.stop="clearFile">
                  重新选择
                </button>
                <button class="upload-primary-btn" type="button" @click.stop="smartUploadFile">
                  <MqIcon name="upload" class="upload-button-icon" />
                  开始上传分析
                </button>
              </div>
            </div>

            <!-- Uploading State -->
            <div v-else class="upload-loading">
              <div class="upload-icon-orb">
                <MqIcon name="sync" class="upload-state-icon upload-spin" />
              </div>
              <h3>正在上传...</h3>
              <p>请稍候，正在解析文件结构</p>
            </div>
          </div>
        </div>

        <!-- Batch History -->
        <aside class="upload-history-card">
          <div class="upload-history-head">
            <h3>历史批次</h3>
            <button class="upload-refresh-btn" type="button" @click="() => loadBatches()">
              <MqIcon
                name="sync"
                :class="['upload-refresh-icon', { 'upload-spin': loadingBatches }]"
              />
            </button>
          </div>

          <div class="upload-history-list">
            <div v-if="batches.length === 0" class="upload-history-empty">
              <MqIcon name="pool" class="upload-history-empty-icon" />
              暂无上传记录
            </div>
            <div
              v-for="batch in batches"
              v-else
              :key="batch.batch_id"
              :class="[
                'upload-history-item',
                { 'upload-history-item--selected': selectedBatchId === batch.batch_id },
              ]"
              @click="selectBatch(batch)"
            >
              <div class="upload-history-item-top">
                <span>{{ batch.batch_id.substring(6, 21) }}</span>
                <em>{{ batch.count }} 条</em>
              </div>
              <div class="upload-history-cost">费用: ¥{{ formatNumber(batch.total_cost) }}</div>
              <div class="upload-history-time">
                {{ formatDate(batch.created_at) }}
              </div>
            </div>
          </div>
        </aside>
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
    <div v-else-if="currentStep === 'complete'" class="upload-complete">
      <div class="upload-complete-icon">
        <MqIcon name="success" class="upload-complete-symbol" />
      </div>
      <h2>分析完成！</h2>
      <p>
        已处理 {{ analysisResult?.row_count || 0 }} 条病例数据，生成 {{ chartCount }} 个分析图表
      </p>
      <div class="upload-complete-actions">
        <a-button class="upload-complete-secondary" @click="currentStep = 'upload'">
          继续上传
        </a-button>
        <a-button type="primary" size="large" class="upload-complete-primary" @click="goToAnalysis">
          查看分析报表 →
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'

import { getAccessToken } from '@/utils/auth-token'
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
  (
    e: 'analysisReady',
    data: {
      charts: any
      aiInsights: string[]
      analysisResults: any
    },
  ): void
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
    const token = getAccessToken()
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const response = await fetch(`${API_BASE}/smart-upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: formData,
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
    const token = getAccessToken()
    const response = await fetch(`${API_BASE}/batches?session_id=${sid}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
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
    minute: '2-digit',
  })
}

// 生命周期
onMounted(() => {
  // 无需在 mount 时加载批次，因为没有 session
})
</script>

<style scoped src="../../styles/data-upload.css"></style>
