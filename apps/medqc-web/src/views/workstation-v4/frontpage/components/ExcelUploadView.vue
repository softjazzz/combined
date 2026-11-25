<template>
  <div class="upload-workstation">
    <!-- Step 1: 上传 -->
    <div v-if="currentStep === 'upload'" class="upload-page">
      <header class="upload-header mq-page-head">
        <div class="upload-title-block">
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
            role="button"
            tabindex="0"
            aria-label="拖拽文件到此处或点击上传"
            @dragover.prevent="isDragging = true"
            @dragleave="isDragging = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
            @keydown.enter.self.prevent="triggerFileInput"
            @keydown.space.self.prevent="triggerFileInput"
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
                <button
                  class="upload-secondary-btn"
                  type="button"
                  :disabled="uploading"
                  @click.stop="clearFile"
                >
                  重新选择
                </button>
                <button
                  class="upload-primary-btn"
                  type="button"
                  :disabled="uploading"
                  data-testid="start-upload-btn"
                  @click.stop="smartUploadFile"
                >
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
              <h3>{{ uploadProgress > 0 ? `正在解析 (${uploadProgress}%)...` : '正在上传...' }}</h3>
              <p>{{ uploadStageText }}</p>
              <div class="upload-action-row">
                <button
                  class="upload-secondary-btn"
                  type="button"
                  data-testid="cancel-upload-btn"
                  :disabled="cancelling"
                  @click.stop="cancelUpload"
                >
                  {{ cancelling ? '正在取消...' : '取消上传' }}
                </button>
              </div>
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
              aria-label="刷新历史批次"
              title="刷新历史批次"
              @click="() => loadBatches()"
            >
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
              role="button"
              tabindex="0"
              :aria-pressed="selectedBatchId === batch.batch_id"
              @click="selectBatch(batch)"
              @keydown.enter.prevent="selectBatch(batch)"
              @keydown.space.prevent="selectBatch(batch)"
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'

import { getAccessToken } from '@/utils/auth-token'
import FieldMappingStep from './FieldMappingStep.vue'

interface BatchInfo {
  batch_id: string
  count: number
  created_at: string
  total_cost: number
}

const POLL_INTERVAL_MS = 800
const MAX_POLL_ATTEMPTS = 240
const MAX_POLL_CONSECUTIVE_ERRORS = 5

const emit = defineEmits<{
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
const cancelling = ref(false)
const uploadProgress = ref(0)
const uploadStageText = ref('请稍候，正在解析文件结构')
const activeTaskId = ref<string | null>(null)

let uploadRunId = 0
let uploadAbortController: AbortController | null = null
let batchesAbortController: AbortController | null = null
let pollTimer: ReturnType<typeof setTimeout> | null = null
let disposed = false

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

function resolveEndpointUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return apiBaseUrl ? `${apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}` : path
}

function getAuthHeaders(): Record<string, string> | undefined {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : undefined
}

function extractErrorMessage(data: any, fallback: string): string {
  const detail = data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (detail && typeof detail === 'object') {
    const base =
      (typeof detail.error === 'string' && detail.error.trim()) ||
      (typeof detail.error_message === 'string' && detail.error_message.trim()) ||
      (typeof detail.message === 'string' && detail.message.trim()) ||
      ''
    if (base) return base
  }
  if (typeof data?.error_message === 'string' && data.error_message.trim()) {
    return data.error_message.trim()
  }
  if (typeof data?.error === 'string' && data.error.trim()) return data.error.trim()
  if (typeof data?.message === 'string' && data.message.trim()) return data.message.trim()
  return fallback
}

function isAbortError(err: unknown): boolean {
  return Boolean(err && typeof err === 'object' && (err as { name?: string }).name === 'AbortError')
}

function clearPollTimer() {
  if (pollTimer !== null) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function waitWithSignal(ms: number, signal: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve()
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(Object.assign(new Error('已取消上传'), { name: 'AbortError' }))
      return
    }
    const onAbort = () => {
      clearPollTimer()
      reject(Object.assign(new Error('已取消上传'), { name: 'AbortError' }))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    pollTimer = setTimeout(() => {
      pollTimer = null
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, ms)
  })
}

function applyParsedUploadResult(resultData: any) {
  const parsedRowCount = Number(resultData?.row_count)
  const safeRowCount = Number.isFinite(parsedRowCount) && parsedRowCount >= 0 ? parsedRowCount : 0
  const parsedFileCount = Number(resultData?.file_count)
  const safeFileCount = Number.isFinite(parsedFileCount) && parsedFileCount > 0 ? parsedFileCount : 1

  uploadedFileId.value = String(resultData?.file_id || '')
  uploadedFileName.value = String(resultData?.filename || selectedFile.value?.name || '')
  uploadedRowCount.value = safeRowCount
  uploadedColumns.value = Array.isArray(resultData?.columns) ? resultData.columns : []
  uploadedSampleData.value = Array.isArray(resultData?.sample_data) ? resultData.sample_data : []

  message.success(`文件上传成功！共 ${safeRowCount} 行数据，${safeFileCount} 个文件`)

  // 跳转到字段映射步骤
  currentStep.value = 'mapping'
}

// 方法
const triggerFileInput = () => {
  if (uploading.value) return
  fileInput.value?.click()
}

const handleFileSelect = (event: Event) => {
  if (uploading.value) return
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  if (uploading.value) return
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
  if (uploading.value) return
  selectedFile.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

const cancelUpload = async () => {
  if (!uploading.value || cancelling.value) return
  cancelling.value = true
  const taskIdToCancel = activeTaskId.value
  uploadRunId += 1
  clearPollTimer()
  uploadAbortController?.abort()
  uploadAbortController = null
  activeTaskId.value = null
  uploading.value = false
  uploadProgress.value = 0
  uploadStageText.value = '请稍候，正在解析文件结构'

  try {
    if (taskIdToCancel) {
      await fetch(`${API_BASE}/smart-upload/tasks/${encodeURIComponent(taskIdToCancel)}/cancel`, {
        method: 'POST',
        headers: getAuthHeaders(),
      }).catch(() => undefined)
    }
    if (!disposed) {
      message.info('已取消上传')
    }
  } finally {
    cancelling.value = false
  }
}

const pollUploadTaskUntilReady = async (
  taskId: string,
  statusUrl: string,
  resultUrl: string,
  runId: number,
  signal: AbortSignal,
) => {
  let consecutiveErrors = 0
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    if (attempt > 0) {
      await waitWithSignal(POLL_INTERVAL_MS, signal)
    }
    if (disposed || runId !== uploadRunId || signal.aborted) {
      return null
    }

    let statusRes: Response
    try {
      statusRes = await fetch(statusUrl, {
        headers: getAuthHeaders(),
        signal,
      })
    } catch (err) {
      if (isAbortError(err) || disposed || runId !== uploadRunId || signal.aborted) {
        return null
      }
      consecutiveErrors += 1
      if (consecutiveErrors >= MAX_POLL_CONSECUTIVE_ERRORS) {
        throw new Error('轮询上传任务状态连续失败，请稍后重试')
      }
      continue
    }

    let statusData: any
    try {
      statusData = await statusRes.json()
    } catch {
      statusData = null
    }

    if (disposed || runId !== uploadRunId || signal.aborted) {
      return null
    }

    if (!statusRes.ok) {
      if (statusRes.status >= 400 && statusRes.status < 500) {
        throw new Error(
          extractErrorMessage(statusData, `查询解析进度失败 (${statusRes.status})`),
        )
      }
      consecutiveErrors += 1
      if (consecutiveErrors >= MAX_POLL_CONSECUTIVE_ERRORS) {
        throw new Error(
          extractErrorMessage(statusData, `查询解析进度失败 (${statusRes.status})`),
        )
      }
      continue
    }

    consecutiveErrors = 0
    const progress = Number(statusData?.progress)
    if (Number.isFinite(progress)) {
      uploadProgress.value = Math.max(0, Math.min(100, Math.round(progress)))
    }

    const taskStatus = String(statusData?.status || '').toLowerCase()
    if (taskStatus === 'succeeded') {
      uploadStageText.value = '解析完成，正在读取字段结果...'
      const resultRes = await fetch(resultUrl, {
        headers: getAuthHeaders(),
        signal,
      })
      let resultData: any
      try {
        resultData = await resultRes.json()
      } catch {
        throw new Error(`读取解析结果异常: ${resultRes.status} ${resultRes.statusText}`)
      }
      if (disposed || runId !== uploadRunId || signal.aborted) {
        return null
      }
      if (!resultRes.ok || resultData?.success === false) {
        throw new Error(extractErrorMessage(resultData, '获取上传解析结果失败'))
      }
      return resultData
    }

    if (taskStatus === 'failed') {
      throw new Error(extractErrorMessage(statusData, '文件解析失败，请检查文件格式后重试'))
    }

    if (taskStatus === 'cancelled') {
      return { __cancelled: true }
    }

    uploadStageText.value =
      uploadProgress.value > 0
        ? `正在后台解析文件（${uploadProgress.value}%），请稍候...`
        : '任务已提交，正在后台解析文件...'
  }

  throw new Error('文件解析超时，请稍后重试')
}

const smartUploadFile = async () => {
  if (!selectedFile.value || uploading.value) return

  const runId = ++uploadRunId
  clearPollTimer()
  uploadAbortController?.abort()
  const controller = new AbortController()
  uploadAbortController = controller

  uploading.value = true
  cancelling.value = false
  uploadProgress.value = 0
  activeTaskId.value = null
  uploadStageText.value = '正在上传文件，请稍候...'

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const response = await fetch(`${API_BASE}/smart-upload`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
      signal: controller.signal,
    })

    let data: any
    try {
      data = await response.json()
    } catch {
      throw new Error(`服务器响应异常: ${response.status} ${response.statusText}`)
    }

    if (disposed || runId !== uploadRunId || controller.signal.aborted) {
      return
    }

    if (!response.ok) {
      throw new Error(extractErrorMessage(data, `上传失败 (${response.status})`))
    }

    const isAsyncAccepted =
      response.status === 202 ||
      (Boolean(data?.task_id) &&
        !Array.isArray(data?.columns) &&
        data?.row_count === undefined)

    if (isAsyncAccepted) {
      const taskId = String(data?.task_id || '').trim()
      if (!taskId) {
        throw new Error('上传任务创建失败，未返回任务 ID')
      }
      activeTaskId.value = taskId
      uploadProgress.value = Number.isFinite(Number(data?.progress)) ? Number(data.progress) : 0
      uploadStageText.value =
        typeof data?.message === 'string' && data.message.trim()
          ? data.message.trim()
          : '任务已提交，正在后台解析文件...'

      const statusUrl = resolveEndpointUrl(
        typeof data?.status_url === 'string' && data.status_url.trim()
          ? data.status_url.trim()
          : `${API_BASE}/smart-upload/tasks/${encodeURIComponent(taskId)}`,
      )
      const resultUrl = resolveEndpointUrl(
        typeof data?.result_url === 'string' && data.result_url.trim()
          ? data.result_url.trim()
          : `${API_BASE}/smart-upload/tasks/${encodeURIComponent(taskId)}/result`,
      )

      const parsedResult = await pollUploadTaskUntilReady(
        taskId,
        statusUrl,
        resultUrl,
        runId,
        controller.signal,
      )
      if (disposed || runId !== uploadRunId || controller.signal.aborted || !parsedResult) {
        return
      }
      if (parsedResult.__cancelled) {
        message.info('上传任务已取消')
        return
      }
      applyParsedUploadResult(parsedResult)
      return
    }

    if (data?.success) {
      applyParsedUploadResult(data)
    } else {
      throw new Error(extractErrorMessage(data, '上传失败'))
    }
  } catch (err: any) {
    if (disposed || runId !== uploadRunId || controller.signal.aborted || isAbortError(err)) {
      return
    }
    console.error('Smart upload error:', err)
    message.error(err?.message || '上传失败')
  } finally {
    if (runId === uploadRunId) {
      clearPollTimer()
      uploading.value = false
      activeTaskId.value = null
      uploadAbortController = null
    }
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
  batchesAbortController?.abort()
  const controller = new AbortController()
  batchesAbortController = controller
  loadingBatches.value = true
  try {
    const response = await fetch(`${API_BASE}/batches?session_id=${encodeURIComponent(sid)}`, {
      headers: getAuthHeaders(),
      signal: controller.signal,
    })
    if (!response.ok) return
    const data = await response.json()
    if (!disposed && !controller.signal.aborted && data.success) {
      batches.value = data.data
    }
  } catch (err) {
    if (!isAbortError(err)) {
      console.error('加载批次列表失败:', err)
    }
  } finally {
    if (!disposed && batchesAbortController === controller) {
      loadingBatches.value = false
      batchesAbortController = null
    }
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

onUnmounted(() => {
  disposed = true
  uploadRunId += 1
  clearPollTimer()
  uploadAbortController?.abort()
  uploadAbortController = null
  batchesAbortController?.abort()
  batchesAbortController = null
})
</script>

<style scoped src="../../styles/data-upload.css"></style>
