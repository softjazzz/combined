<template>
  <div class="field-mapping-step">
    <!-- 头部 -->
    <div class="mapping-header">
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="mapping-back-btn"
          aria-label="返回重新上传"
          title="返回重新上传"
          @click="$emit('back')"
        >
          <ArrowLeftOutlined class="text-lg" />
        </button>
        <div>
          <h2 class="text-xl font-semibold text-slate-800">
            字段映射确认
          </h2>
          <p class="mapping-subtitle mt-1">
            AI 已自动识别字段对应关系，请核对后确认
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <div
          v-if="confidence > 0"
          class="flex items-center gap-2"
        >
          <span class="mapping-confidence-label">AI 置信度</span>
          <a-progress
            :percent="Math.round(confidence * 100)"
            :size="[120, 6]"
            :stroke-color="confidence > 0.8 ? '#52c41a' : confidence > 0.5 ? '#faad14' : '#f5222d'"
          />
        </div>
        <a-tag
          v-if="fallback"
          color="orange"
        >
          规则引擎模式
        </a-tag>
      </div>
    </div>

    <!-- 加载中 -->
    <div
      v-if="loading"
      class="mapping-loading"
    >
      <a-spin size="large" />
      <p class="mapping-loading-title mt-4">
        正在进行 AI 字段识别...
      </p>
      <p class="mapping-loading-hint mt-1">
        首次分析可能需要 5-10 秒
      </p>
    </div>

    <!-- 映射内容 -->
    <div
      v-else
      class="mapping-content"
    >
      <!-- 数据预览 -->
      <div class="preview-section">
        <h3 class="section-title">
          <FileExcelOutlined class="text-green-500" />
          数据预览
          <a-tag>{{ fileName }}</a-tag>
          <a-tag color="blue">
            {{ rowCount }} 行
          </a-tag>
        </h3>
        <div class="preview-table-wrapper">
          <table class="preview-table">
            <thead>
              <tr>
                <th
                  v-for="col in columns"
                  :key="col"
                  class="preview-th"
                >
                  {{ col }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in sampleData.slice(0, 3)"
                :key="idx"
              >
                <td
                  v-for="col in columns"
                  :key="col"
                  class="preview-td"
                >
                  {{ row[col] || '-' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 字段映射表格 -->
      <div class="mapping-section">
        <h3 class="section-title">
          <SwapOutlined class="text-[#0a6cff]" />
          字段映射
          <span class="mapped-count">
            {{ mappedCount }} / {{ Object.keys(localMappings).length }} 已映射
          </span>
        </h3>

        <div class="mapping-grid">
          <div
            v-for="col in columns"
            :key="col"
            class="mapping-row"
            :class="{
              'mapping-row-mapped': localMappings[col],
              'mapping-row-unmapped': !localMappings[col],
              'mapping-row-required-missing': isRequiredFieldMissing(col),
            }"
          >
            <!-- 源列名 -->
            <div class="source-col">
              <span class="col-name">{{ col }}</span>
              <span
                v-if="sampleData[0]"
                class="col-sample"
              >
                {{ String(sampleData[0][col] || '').slice(0, 20) }}
              </span>
            </div>

            <!-- 箭头 -->
            <div class="mapping-arrow">
              <RightOutlined
                v-if="localMappings[col]"
                class="text-green-500"
              />
              <MinusOutlined
                v-else
                class="mapping-arrow-unmapped"
              />
            </div>

            <!-- 目标字段选择 -->
            <div class="target-field">
              <a-select
                v-model:value="localMappings[col]"
                placeholder="选择标准字段"
                allow-clear
                show-search
                :filter-option="filterOption"
                style="width: 100%"
                size="small"
              >
                <a-select-option
                  v-for="(field, key) in standardFields"
                  :key="key"
                  :value="key"
                  :disabled="isFieldUsed(key, col)"
                >
                  <div class="field-option">
                    <span>{{ field.name }}</span>
                    <a-tag
                      v-if="field.required"
                      color="red"
                      size="small"
                      class="ml-1"
                    >
                      必填
                    </a-tag>
                    <span class="field-key">{{ key }}</span>
                  </div>
                </a-select-option>
              </a-select>
            </div>
          </div>
        </div>
      </div>

      <!-- 缺失必填字段警告 -->
      <div
        v-if="missingRequired.length > 0"
        class="missing-warning"
      >
        <a-alert
          type="warning"
          show-icon
          :message="`缺少 ${missingRequired.length} 个必填字段`"
          :description="
            '缺失: ' + missingRequired.map((k) => standardFields[k]?.name || k).join('、')
          "
        />
      </div>

      <!-- 操作按钮 -->
      <div class="mapping-actions">
        <a-button :disabled="confirming" @click="$emit('back')">
          <template #icon>
            <ArrowLeftOutlined />
          </template>
          返回修改
        </a-button>
        <a-button :disabled="confirming || loading" @click="resetMappings">
          <template #icon>
            <UndoOutlined />
          </template>
          重置映射
        </a-button>
        <a-button
          type="primary"
          data-testid="confirm-mapping-btn"
          :loading="confirming"
          :disabled="confirming || mappedCount === 0"
          @click="confirmMapping"
        >
          <template #icon>
            <CheckOutlined />
          </template>
          确认映射并生成报表 ({{ mappedCount }} 个字段)
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { message } from 'ant-design-vue'
import { getAccessToken } from '@/utils/auth-token'
import {
  ArrowLeftOutlined,
  FileExcelOutlined,
  SwapOutlined,
  RightOutlined,
  MinusOutlined,
  CheckOutlined,
  UndoOutlined,
} from '@ant-design/icons-vue'

interface StandardField {
  name: string
  description: string
  required: boolean
  category: string
  aliases: string[]
}

interface Props {
  fileId: string
  fileName: string
  rowCount: number
  columns: string[]
  sampleData: Record<string, any>[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'back'): void
  (
    e: 'confirmed',
    data: {
      fileId: string
      mappings: Record<string, string>
      analysisResults: any
      charts: any
      aiInsights: string[]
    },
  ): void
}>()

// API base URL
const apiBaseUrl = ((import.meta as any)?.env?.VITE_API_BASE_URL || '').trim().replace(/\/$/, '')
const API_BASE = apiBaseUrl ? `${apiBaseUrl}/api/v1/drg` : '/api/v1/drg'

function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}`, ...extraHeaders } : extraHeaders
}

function isAbortError(err: unknown): boolean {
  return Boolean(err && typeof err === 'object' && (err as { name?: string }).name === 'AbortError')
}

function formatMappingError(data: any, status?: number, fallback = '映射确认失败'): string {
  const detail = data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  if (detail && typeof detail === 'object') {
    const baseError =
      (typeof detail.error === 'string' && detail.error.trim()) ||
      (typeof detail.message === 'string' && detail.message.trim()) ||
      fallback
    const missingNames = Array.isArray(detail.missing_field_names)
      ? detail.missing_field_names.filter(
          (item: unknown) => typeof item === 'string' && item.trim(),
        )
      : Array.isArray(detail.missing_fields)
        ? detail.missing_fields.filter(
            (item: unknown) => typeof item === 'string' && item.trim(),
          )
        : []
    if (missingNames.length > 0) {
      return `${baseError}：缺少 ${missingNames.join('、')}`
    }
    return baseError
  }
  if (typeof data?.error === 'string' && data.error.trim()) {
    return data.error.trim()
  }
  if (typeof data?.message === 'string' && data.message.trim()) {
    return data.message.trim()
  }
  return status ? `${fallback} (HTTP ${status})` : fallback
}

// 状态
const loading = ref(true)
const confirming = ref(false)
const localMappings = ref<Record<string, string>>({})
const standardFields = ref<Record<string, StandardField>>({})
const confidence = ref(0)
const fallback = ref(false)

let disposed = false
let mappingLoadSeq = 0
let loadAbortController: AbortController | null = null
let confirmAbortController: AbortController | null = null

// 计算属性
const mappedCount = computed(() => {
  return Object.values(localMappings.value).filter((v) => !!v).length
})

const missingRequired = computed(() => {
  const mappedFieldKeys = new Set(Object.values(localMappings.value).filter(Boolean))
  return Object.entries(standardFields.value)
    .filter(([key, field]) => field.required && !mappedFieldKeys.has(key))
    .map(([key]) => key)
})

// 方法
const filterOption = (input: string, option: any) => {
  const field = standardFields.value[option.value]
  if (!field) return false
  const searchStr = `${field.name} ${option.value} ${field.description}`.toLowerCase()
  return searchStr.includes(input.toLowerCase())
}

const isFieldUsed = (fieldKey: string, currentCol: string) => {
  return Object.entries(localMappings.value).some(
    ([col, key]) => key === fieldKey && col !== currentCol,
  )
}

const isRequiredFieldMissing = (_col: string) => {
  return false // 视觉标记用
}

const resetMappings = () => {
  if (confirming.value || loading.value) return
  // 重新请求 AI 映射
  void fetchMappingSuggestion()
}

const fetchMappingSuggestion = async () => {
  if (disposed) return
  const seq = ++mappingLoadSeq
  loadAbortController?.abort()
  const controller = new AbortController()
  loadAbortController = controller

  loading.value = true
  try {
    const response = await fetch(`${API_BASE}/mapping/suggest`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ file_id: props.fileId }),
      signal: controller.signal,
    })

    let data: any
    try {
      data = await response.json()
    } catch {
      throw new Error(`服务器响应异常: ${response.status}`)
    }

    if (disposed || seq !== mappingLoadSeq || controller.signal.aborted) return

    if (!response.ok) {
      throw new Error(formatMappingError(data, response.status, '获取字段映射建议失败'))
    }

    if (data.suggested_mappings) {
      localMappings.value = { ...data.suggested_mappings }
    }
    if (data.standard_fields) {
      standardFields.value = data.standard_fields
    }
    confidence.value = data.confidence || 0
    fallback.value = data.fallback || false
  } catch (err: any) {
    if (disposed || seq !== mappingLoadSeq || controller.signal.aborted || isAbortError(err)) {
      return
    }
    message.error('获取字段映射建议失败: ' + (err.message || ''))
  } finally {
    if (!disposed && seq === mappingLoadSeq) {
      loading.value = false
    }
  }
}

const pollMappingStatus = async (): Promise<boolean> => {
  if (disposed) return false
  const seq = ++mappingLoadSeq
  loadAbortController?.abort()
  const controller = new AbortController()
  loadAbortController = controller

  // 先尝试轮询后台映射是否已完成
  try {
    const response = await fetch(`${API_BASE}/mapping-status/${encodeURIComponent(props.fileId)}`, {
      headers: getAuthHeaders(),
      signal: controller.signal,
    })
    if (disposed || seq !== mappingLoadSeq || controller.signal.aborted || !response.ok) {
      return false
    }
    const data = await response.json()
    if (disposed || seq !== mappingLoadSeq || controller.signal.aborted) {
      return false
    }
    if (data.ready) {
      // 直接使用缓存结果
      if (data.mappings) {
        localMappings.value = { ...data.mappings }
        confidence.value = data.confidence || 0
      }
      // 仍然需要获取标准字段列表
      const fieldsRes = await fetch(`${API_BASE}/mapping/fields`, {
        headers: getAuthHeaders(),
        signal: controller.signal,
      })
      if (disposed || seq !== mappingLoadSeq || controller.signal.aborted || !fieldsRes.ok) {
        return false
      }
      const fieldsData = await fieldsRes.json()
      if (disposed || seq !== mappingLoadSeq || controller.signal.aborted) {
        return false
      }
      if (fieldsData.fields) {
        standardFields.value = fieldsData.fields
      }
      loading.value = false
      return true
    }
  } catch {
    // 忽略并降级至直接请求建议
  }
  return false
}

const confirmMapping = async () => {
  if (confirming.value || disposed) return

  const validMappings: Record<string, string> = {}
  for (const [col, key] of Object.entries(localMappings.value)) {
    if (key) validMappings[col] = key
  }

  if (Object.keys(validMappings).length === 0) {
    message.warning('请至少映射一个字段')
    return
  }

  confirmAbortController?.abort()
  const controller = new AbortController()
  confirmAbortController = controller

  confirming.value = true
  try {
    const response = await fetch(`${API_BASE}/mapping/confirm`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        file_id: props.fileId,
        mappings: validMappings,
      }),
      signal: controller.signal,
    })

    let data: any
    try {
      data = await response.json()
    } catch {
      throw new Error(`服务器响应异常: ${response.status}`)
    }

    if (disposed || controller.signal.aborted) return

    if (!response.ok || !data?.success) {
      throw new Error(formatMappingError(data, response.status, '映射确认失败'))
    }

    const rowCount = Number.isFinite(Number(data.row_count)) ? Number(data.row_count) : props.rowCount
    message.success(`分析完成！共处理 ${rowCount} 条记录`)
    emit('confirmed', {
      fileId: props.fileId,
      mappings: validMappings,
      analysisResults: data.analysis_results,
      charts: data.charts,
      aiInsights: data.ai_insights || [],
    })
  } catch (err: any) {
    if (disposed || controller.signal.aborted || isAbortError(err)) return
    console.error('Confirm mapping error:', err)
    message.error(err?.message || '映射确认失败')
  } finally {
    if (!disposed && confirmAbortController === controller) {
      confirming.value = false
      confirmAbortController = null
    }
  }
}

// 生命周期
onMounted(async () => {
  // 先尝试轮询是否有缓存
  const cached = await pollMappingStatus()
  if (!cached && !disposed) {
    // 没有缓存，直接请求 AI 映射
    await fetchMappingSuggestion()
  }
})

onBeforeUnmount(() => {
  disposed = true
  mappingLoadSeq += 1
  loadAbortController?.abort()
  loadAbortController = null
  confirmAbortController?.abort()
  confirmAbortController = null
})
</script>

<style scoped>
.field-mapping-step {
  flex: 1 1 auto;
  min-height: 0;
  height: auto;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  color: var(--mq-text-primary);
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'San Francisco', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  overflow-y: auto;
  overflow-x: hidden;
}

.mapping-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  flex-shrink: 0;
}

.mapping-back-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--mq-border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--mq-text-secondary);
  cursor: pointer;
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.mapping-back-btn:hover {
  color: var(--mq-text-primary);
  border-color: var(--mq-border-strong);
  background: #ffffff;
}

.mapping-back-btn:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

.mapping-subtitle,
.mapping-loading-title {
  color: var(--mq-text-secondary);
  font-size: 14px;
}

.mapping-confidence-label,
.mapping-loading-hint {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.mapping-arrow-unmapped {
  color: var(--mq-text-tertiary);
}

.mapping-header :deep(h2) {
  color: var(--mq-text-primary);
  font-size: 20px;
  line-height: 26px;
}

.mapping-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 240px;
}

.mapping-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 20px 24px 28px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--mq-text-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mapped-count {
  font-weight: 500;
  font-size: 13px;
  color: var(--mq-text-tertiary);
  margin-left: auto;
}

/* 数据预览 */
.preview-section {
  margin-bottom: 24px;
}

.preview-table-wrapper {
  overflow-x: auto;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.9);
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  white-space: nowrap;
}

.preview-th {
  padding: 8px 12px;
  background: #f5f5f7;
  font-weight: 600;
  color: var(--mq-text-secondary);
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
}

.preview-td {
  padding: 6px 12px;
  color: var(--mq-text-secondary);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 字段映射 */
.mapping-section {
  margin-bottom: 20px;
}

.mapping-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mapping-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(0, 0, 0, 0.08);
  transition: all 0.2s;
}

.mapping-row-mapped {
  border-color: rgba(16, 185, 129, 0.18);
  background: rgba(16, 185, 129, 0.06);
}

.mapping-row-unmapped {
  border-style: dashed;
  border-color: rgba(0, 0, 0, 0.14);
  background: rgba(255, 255, 255, 0.82);
}

.source-col {
  flex: 1;
  min-width: 0;
}

.col-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--mq-text-primary);
}

.col-sample {
  display: block;
  font-size: 11px;
  color: var(--mq-text-tertiary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mapping-arrow {
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}

.target-field {
  flex: 1.2;
  min-width: 0;
}

.field-option {
  display: flex;
  align-items: center;
  gap: 4px;
}

.field-key {
  font-size: 10px;
  color: var(--mq-text-tertiary);
  margin-left: auto;
}

/* 警告 */
.missing-warning {
  margin-bottom: 16px;
}

/* 操作按钮 */
.mapping-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
</style>
