<template>
  <div class="field-mapping-step">
    <!-- 头部 -->
    <div class="mapping-header">
      <div class="flex items-center gap-3">
        <button
          class="text-slate-400 hover:text-slate-600 transition-colors"
          @click="$emit('back')"
        >
          <ArrowLeftOutlined class="text-lg" />
        </button>
        <div>
          <h2 class="text-xl font-semibold text-slate-800">
            字段映射确认
          </h2>
          <p class="text-sm text-slate-500 mt-1">
            AI 已自动识别字段对应关系，请核对后确认
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <div
          v-if="confidence > 0"
          class="flex items-center gap-2"
        >
          <span class="text-xs text-slate-500">AI 置信度</span>
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
      <p class="mt-4 text-slate-500">
        正在进行 AI 字段识别...
      </p>
      <p class="text-xs text-slate-400 mt-1">
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
                class="text-slate-300"
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
        <a-button @click="$emit('back')">
          <template #icon>
            <ArrowLeftOutlined />
          </template>
          返回修改
        </a-button>
        <a-button @click="resetMappings">
          <template #icon>
            <UndoOutlined />
          </template>
          重置映射
        </a-button>
        <a-button
          type="primary"
          :loading="confirming"
          :disabled="mappedCount === 0"
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
import { ref, computed, onMounted, watch } from 'vue'
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

// 状态
const loading = ref(true)
const confirming = ref(false)
const localMappings = ref<Record<string, string>>({})
const standardFields = ref<Record<string, StandardField>>({})
const confidence = ref(0)
const fallback = ref(false)

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

const isRequiredFieldMissing = (col: string) => {
  return false // 视觉标记用
}

const resetMappings = () => {
  // 重新请求 AI 映射
  fetchMappingSuggestion()
}

const fetchMappingSuggestion = async () => {
  loading.value = true
  try {
    const response = await fetch(`${API_BASE}/mapping/suggest`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ file_id: props.fileId }),
    })
    const data = await response.json()

    if (data.suggested_mappings) {
      localMappings.value = { ...data.suggested_mappings }
    }
    if (data.standard_fields) {
      standardFields.value = data.standard_fields
    }
    confidence.value = data.confidence || 0
    fallback.value = data.fallback || false
  } catch (err: any) {
    message.error('获取字段映射建议失败: ' + (err.message || ''))
  } finally {
    loading.value = false
  }
}

const pollMappingStatus = async () => {
  // 先尝试轮询后台映射是否已完成
  try {
    const response = await fetch(`${API_BASE}/mapping-status/${props.fileId}`, {
      headers: getAuthHeaders(),
    })
    const data = await response.json()
    if (data.ready) {
      // 直接使用缓存结果
      if (data.mappings) {
        localMappings.value = { ...data.mappings }
        confidence.value = data.confidence || 0
      }
      // 仍然需要获取标准字段列表
      const fieldsRes = await fetch(`${API_BASE}/mapping/fields`, {
        headers: getAuthHeaders(),
      })
      const fieldsData = await fieldsRes.json()
      if (fieldsData.fields) {
        standardFields.value = fieldsData.fields
      }
      loading.value = false
      return true
    }
  } catch {
    // 忽略
  }
  return false
}

const confirmMapping = async () => {
  const validMappings: Record<string, string> = {}
  for (const [col, key] of Object.entries(localMappings.value)) {
    if (key) validMappings[col] = key
  }

  if (Object.keys(validMappings).length === 0) {
    message.warning('请至少映射一个字段')
    return
  }

  confirming.value = true
  try {
    const response = await fetch(`${API_BASE}/mapping/confirm`, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({
        file_id: props.fileId,
        mappings: validMappings,
      }),
    })

    let data
    try {
      data = await response.json()
    } catch {
      throw new Error(`服务器响应异常: ${response.status}`)
    }

    if (data.success) {
      message.success(`分析完成！共处理 ${data.row_count} 条记录`)
      emit('confirmed', {
        fileId: props.fileId,
        mappings: validMappings,
        analysisResults: data.analysis_results,
        charts: data.charts,
        aiInsights: data.ai_insights || [],
      })
    } else {
      throw new Error(data.detail || data.error || '映射确认失败')
    }
  } catch (err: any) {
    console.error('Confirm mapping error:', err)
    message.error(err.message || '映射确认失败')
  } finally {
    confirming.value = false
  }
}

// 生命周期
onMounted(async () => {
  // 先尝试轮询是否有缓存
  const cached = await pollMappingStatus()
  if (!cached) {
    // 没有缓存，直接请求 AI 映射
    await fetchMappingSuggestion()
  }
})
</script>

<style scoped>
.field-mapping-step {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'San Francisco', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  overflow: hidden;
}

.mapping-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: rgba(255, 255, 255, 0.86);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  flex-shrink: 0;
}

.mapping-header :deep(h2) {
  color: #1d1d1f;
  font-size: 20px;
  line-height: 26px;
}

.mapping-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.mapping-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.mapped-count {
  font-weight: 400;
  font-size: 13px;
  color: rgba(29, 29, 31, 0.38);
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
  color: rgba(29, 29, 31, 0.66);
  text-align: left;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
}

.preview-td {
  padding: 6px 12px;
  color: rgba(29, 29, 31, 0.66);
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
  border-color: rgba(0, 0, 0, 0.08);
  opacity: 0.7;
}

.source-col {
  flex: 1;
  min-width: 0;
}

.col-name {
  font-weight: 600;
  font-size: 13px;
  color: #1d1d1f;
}

.col-sample {
  display: block;
  font-size: 11px;
  color: rgba(29, 29, 31, 0.38);
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
  color: rgba(29, 29, 31, 0.38);
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
  gap: 12px;
  padding: 16px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}
</style>
