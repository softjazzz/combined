<template>
  <div class="upload-workstation">
    <!-- Step 1: 上传 -->
    <div
      v-if="currentStep === 'upload'"
      class="upload-page"
    >
      <header class="upload-header">
        <div class="upload-title-block">
          <button
            class="upload-back-btn"
            type="button"
            @click="$emit('back')"
          >
            <ArrowLeft class="upload-back-icon" />
          </button>
          <div>
            <span class="upload-eyebrow">数据与配置 · 数据导入</span>
            <h2>DRG/DIP 数据分析</h2>
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
        <div class="upload-main-card">
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
            >

            <div
              v-if="!selectedFile && !uploading"
              class="upload-empty"
            >
              <div class="upload-icon-orb">
                <UploadCloud class="upload-state-icon" />
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
            <div
              v-else-if="selectedFile && !uploading"
              class="upload-selected"
            >
              <div class="upload-icon-orb upload-icon-orb--success">
                <FileSpreadsheet class="upload-state-icon" />
              </div>
              <h3>
                {{ selectedFile.name }}
              </h3>
              <p>
                {{ formatFileSize(selectedFile.size) }}
              </p>
              <div class="upload-action-row">
                <button
                  class="upload-secondary-btn"
                  type="button"
                  @click.stop="clearFile"
                >
                  重新选择
                </button>
                <button
                  class="upload-primary-btn"
                  type="button"
                  @click.stop="smartUploadFile"
                >
                  <UploadCloud class="upload-button-icon" />
                  开始上传分析
                </button>
              </div>
            </div>

            <!-- Uploading State -->
            <div
              v-else
              class="upload-loading"
            >
              <div class="upload-icon-orb">
                <LoaderCircle class="upload-state-icon upload-spin" />
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
            <button
              class="upload-refresh-btn"
              type="button"
              @click="() => loadBatches()"
            >
              <RefreshCw :class="['upload-refresh-icon', { 'upload-spin': loadingBatches }]" />
            </button>
          </div>

          <div class="upload-history-list">
            <div
              v-if="batches.length === 0"
              class="upload-history-empty"
            >
              <Inbox class="upload-history-empty-icon" />
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
              <div class="upload-history-cost">
                费用: ¥{{ formatNumber(batch.total_cost) }}
              </div>
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
    <div
      v-else-if="currentStep === 'complete'"
      class="upload-complete"
    >
      <div class="upload-complete-icon">
        <CircleCheck class="upload-complete-symbol" />
      </div>
      <h2>分析完成！</h2>
      <p>
        已处理 {{ analysisResult?.row_count || 0 }} 条病例数据，生成 {{ chartCount }} 个分析图表
      </p>
      <div class="upload-complete-actions">
        <a-button
          class="upload-complete-secondary"
          @click="currentStep = 'upload'"
        >
          继续上传
        </a-button>
        <a-button
          type="primary"
          size="large"
          class="upload-complete-primary"
          @click="goToAnalysis"
        >
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
  ArrowLeft,
  CircleCheck,
  FileSpreadsheet,
  Inbox,
  LoaderCircle,
  RefreshCw,
  UploadCloud,
} from 'lucide-vue-next'
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

<style scoped>
.upload-workstation {
  min-height: 100%;
  width: 100%;
  overflow: hidden;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'San Francisco', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.upload-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  padding: 24px;
  overflow: hidden;
}

.upload-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.upload-title-block {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
}

.upload-back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
  color: rgba(29, 29, 31, 0.58);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 3px rgba(0, 0, 0, 0.045);
  transition:
    color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.upload-back-btn:hover {
  color: #2b6cf6;
  border-color: rgba(43, 108, 246, 0.2);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 3px 10px rgba(43, 108, 246, 0.08);
}

.upload-back-icon {
  width: 17px;
  height: 17px;
  stroke-width: 2.1;
}

.upload-eyebrow {
  display: block;
  margin-bottom: 5px;
  color: #2b6cf6;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  line-height: 1;
}

.upload-title-block h2 {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
  letter-spacing: 0;
}

.upload-title-block p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.upload-header-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 6px;
}

.upload-header-meta span {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(43, 108, 246, 0.12);
  border-radius: 999px;
  background: rgba(43, 108, 246, 0.06);
  color: #2b6cf6;
  font-size: 12px;
  font-weight: 600;
}

.upload-content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 18px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.upload-main-card,
.upload-history-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  overflow: hidden;
}

.upload-main-card {
  display: flex;
  min-width: 0;
  min-height: 0;
  padding: 18px;
}

.upload-dropzone {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 420px;
  border: 1.5px dashed rgba(43, 108, 246, 0.24);
  border-radius: 18px;
  background:
    radial-gradient(circle at top, rgba(43, 108, 246, 0.07), transparent 34%),
    rgba(250, 252, 255, 0.7);
  cursor: pointer;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.upload-dropzone:hover,
.upload-dropzone--dragging {
  border-color: rgba(43, 108, 246, 0.42);
  background:
    radial-gradient(circle at top, rgba(43, 108, 246, 0.1), transparent 38%),
    rgba(247, 251, 255, 0.88);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 8px 28px rgba(43, 108, 246, 0.08);
  transform: translateY(-1px);
}

.upload-empty,
.upload-selected,
.upload-loading {
  width: min(520px, 100%);
  padding: 32px;
  text-align: center;
}

.upload-icon-orb {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 76px;
  height: 76px;
  margin-bottom: 18px;
  border: 1px solid rgba(43, 108, 246, 0.16);
  border-radius: 18px;
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 4px 14px rgba(43, 108, 246, 0.08);
}

.upload-icon-orb--success {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.09);
  color: #059669;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.92),
    0 4px 14px rgba(16, 185, 129, 0.08);
}

.upload-state-icon {
  width: 34px;
  height: 34px;
  stroke-width: 1.9;
}

.upload-empty h3,
.upload-selected h3,
.upload-loading h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 18px;
  font-weight: 650;
  line-height: 24px;
}

.upload-empty p,
.upload-selected p,
.upload-loading p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.upload-format-row {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 18px;
}

.upload-format-row span {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(29, 29, 31, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: rgba(29, 29, 31, 0.66);
  font-size: 12px;
  font-weight: 600;
}

.upload-action-row,
.upload-complete-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 20px;
}

.upload-primary-btn,
.upload-secondary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.upload-primary-btn {
  border: 1px solid #2b6cf6;
  background: #2b6cf6;
  color: #fff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 5px 14px rgba(43, 108, 246, 0.18);
}

.upload-primary-btn:hover {
  background: #0057b8;
  border-color: #0057b8;
}

.upload-secondary-btn {
  border: 1px solid rgba(29, 29, 31, 0.1);
  background: rgba(255, 255, 255, 0.94);
  color: rgba(29, 29, 31, 0.7);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 1px 2px rgba(0, 0, 0, 0.04);
}

.upload-secondary-btn:hover {
  color: #1d1d1f;
  border-color: rgba(29, 29, 31, 0.16);
  background: rgba(255, 255, 255, 0.98);
}

.upload-button-icon {
  width: 15px;
  height: 15px;
  stroke-width: 2.1;
}

.upload-history-card {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.upload-history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 16px 13px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.upload-history-head h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 16px;
  font-weight: 650;
  line-height: 22px;
}

.upload-refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid rgba(43, 108, 246, 0.14);
  border-radius: 9px;
  background: rgba(43, 108, 246, 0.06);
  color: #2b6cf6;
}

.upload-refresh-icon {
  width: 15px;
  height: 15px;
  stroke-width: 2.1;
}

.upload-history-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.upload-history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 220px;
  padding: 28px;
  color: rgba(29, 29, 31, 0.38);
  font-size: 13px;
  font-weight: 500;
}

.upload-history-empty-icon {
  width: 28px;
  height: 28px;
  stroke-width: 1.8;
}

.upload-history-item {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.upload-history-item:hover {
  background: rgba(0, 0, 0, 0.025);
}

.upload-history-item--selected {
  background: rgba(43, 108, 246, 0.08);
  box-shadow: inset 3px 0 0 #2b6cf6;
}

.upload-history-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.upload-history-item-top span {
  min-width: 0;
  overflow: hidden;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-history-item-top em {
  flex: none;
  color: #2b6cf6;
  font-size: 12px;
  font-style: normal;
  font-weight: 650;
}

.upload-history-cost,
.upload-history-time {
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
}

.upload-history-time {
  color: rgba(29, 29, 31, 0.38);
}

.upload-complete {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 32px;
  background: #f5f5f7;
  text-align: center;
}

.upload-complete-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 88px;
  height: 88px;
  margin-bottom: 20px;
  border: 1px solid rgba(16, 185, 129, 0.18);
  border-radius: 26px;
  background: rgba(16, 185, 129, 0.09);
  color: #059669;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 10px 28px rgba(16, 185, 129, 0.12);
}

.upload-complete-symbol {
  width: 42px;
  height: 42px;
  stroke-width: 1.9;
}

.upload-complete h2 {
  margin: 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 34px;
}

.upload-complete p {
  margin: 10px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.upload-complete-secondary,
.upload-complete-primary {
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}

.upload-complete-primary {
  background: #2b6cf6;
  border-color: #2b6cf6;
  box-shadow: 0 5px 14px rgba(43, 108, 246, 0.18);
}

.upload-spin {
  animation: upload-spin 0.9s linear infinite;
}

@keyframes upload-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1100px) {
  .upload-content-grid {
    grid-template-columns: 1fr;
    overflow: auto;
  }

  .upload-history-card {
    min-height: 260px;
  }
}

@media (max-width: 720px) {
  .upload-page {
    padding: 16px;
  }

  .upload-header {
    flex-direction: column;
  }

  .upload-title-block h2,
  .upload-complete h2 {
    font-size: 24px;
    line-height: 29px;
  }

  .upload-dropzone {
    min-height: 360px;
  }
}
</style>
