<template>
  <a-modal
    :open="visible"
    title="LLM智能解析结果"
    width="1200px"
    :footer="null"
    :destroy-on-close="true"
    class="medical-document-result-modal"
    @update:open="$emit('update:visible', $event)"
  >
    <div class="modal-content">
      <!-- 解析概览 -->
      <div class="result-overview glass-card mb-4">
        <!-- 第一行：患者基本信息 -->
        <a-row
          :gutter="16"
          class="mb-3"
        >
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                患者姓名
              </div>
              <div
                class="overview-value"
                :class="{ 'missing-info': !data?.patientName || data?.patientName === '未识别' }"
              >
                {{ formatPatientInfo(data?.patientName) }}
              </div>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                性别
              </div>
              <div
                class="overview-value"
                :class="{ 'missing-info': !data?.patientGender }"
              >
                {{ formatPatientInfo(data?.patientGender) }}
              </div>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                年龄
              </div>
              <div
                class="overview-value"
                :class="{ 'missing-info': !data?.patientAge }"
              >
                {{ formatAge(data?.patientAge) }}
              </div>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                科室
              </div>
              <div
                class="overview-value"
                :class="{ 'missing-info': !data?.department || data?.department === '未识别' }"
              >
                {{ formatPatientInfo(data?.department) }}
              </div>
            </div>
          </a-col>
        </a-row>

        <!-- 第二行：统计信息 -->
        <a-row :gutter="16">
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                文书数量
              </div>
              <div class="overview-value">
                {{ documents.length }}个
              </div>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="overview-item">
              <div class="overview-label">
                整体置信度
              </div>
              <div class="overview-value confidence-score">
                {{ Math.round(data?.confidence || 0) }}%
              </div>
            </div>
          </a-col>
        </a-row>
      </div>

      <!-- 诊断信息 -->
      <div class="diagnosis-info glass-card mb-4">
        <a-row :gutter="16">
          <a-col :span="12">
            <div class="diagnosis-item">
              <div class="diagnosis-label">
                <MedicineBoxOutlined class="mr-2" />
                主要诊断
              </div>
              <div class="diagnosis-value">
                {{ data?.primaryDiagnosis || '未识别' }}
              </div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="diagnosis-item">
              <div class="diagnosis-label">
                <ScissorOutlined class="mr-2" />
                主要手术
              </div>
              <div class="diagnosis-value">
                {{ data?.majorSurgery || '无' }}
              </div>
            </div>
          </a-col>
        </a-row>
        <div
          v-if="data?.secondaryDiagnosis && data.secondaryDiagnosis.length > 0"
          class="secondary-diagnosis mt-3"
        >
          <div class="diagnosis-label mb-2">
            次要诊断
          </div>
          <div class="diagnosis-tags">
            <a-tag
              v-for="(diagnosis, index) in data.secondaryDiagnosis"
              :key="index"
              color="blue"
            >
              {{ diagnosis }}
            </a-tag>
          </div>
        </div>
      </div>

      <!-- 文书分类结果 -->
      <div class="documents-section">
        <div class="section-header">
          <FileTextOutlined class="mr-2" />
          <span class="section-title">文书分类结果</span>
          <a-tag
            color="green"
            class="ml-2"
          >
            共{{ documents.length }}个文书
          </a-tag>
        </div>

        <div
          v-if="documents.length === 0"
          class="empty-state"
        >
          <a-empty description="未识别到任何文书" />
        </div>

        <div
          v-else
          class="documents-grid"
        >
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="document-card glass-card"
            @click="showDocumentDetail(doc)"
          >
            <div class="document-header">
              <div class="document-title">
                <component
                  :is="getDocumentIcon(doc.type)"
                  class="document-icon mr-2"
                />
                {{ doc.title || getDocumentTypeLabel(doc.type) }}
              </div>
              <div class="document-meta">
                <a-tag
                  :color="getDocumentTypeColor(doc.type)"
                  size="small"
                >
                  {{ getDocumentTypeLabel(doc.type) }}
                </a-tag>
                <span
                  v-if="doc.confidence != null"
                  class="confidence-badge"
                >
                  {{ Math.round(doc.confidence) }}%
                </span>
              </div>
            </div>

            <div class="document-summary">
              {{ doc.content || '暂无摘要' }}
            </div>

            <div
              v-if="getDocumentTimestamp(doc)"
              class="document-timestamp"
            >
              <ClockCircleOutlined class="mr-1" />
              {{ formatTimestamp(getDocumentTimestamp(doc)) }}
            </div>

            <div class="document-actions">
              <a-button
                type="link"
                size="small"
                @click.stop="showDocumentDetail(doc)"
              >
                查看详情
              </a-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="modal-actions">
        <a-space>
          <a-button @click="handleClose">
            关闭
          </a-button>
          <a-button
            type="primary"
            @click="handleConfirm"
          >
            <DatabaseOutlined class="mr-1" />
            保存并跳转
          </a-button>
          <a-button @click="handleConfirmOnly">
            确认结果
          </a-button>
          <a-button @click="handleExport">
            <DownloadOutlined class="mr-1" />
            导出结果
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 文书详情弹窗 -->
    <a-modal
      v-model:open="showDetailModal"
      :title="selectedDocument?.title || '文书详情'"
      width="800px"
      :footer="null"
      :destroy-on-close="true"
      class="document-detail-modal"
    >
      <div
        v-if="selectedDocument"
        class="document-detail"
      >
        <div class="detail-header mb-4">
          <a-tag :color="getDocumentTypeColor(selectedDocument.type)">
            {{ getDocumentTypeLabel(selectedDocument.type) }}
          </a-tag>
          <span
            v-if="selectedDocument.confidence != null"
            class="confidence-badge ml-2"
          >
            置信度: {{ Math.round(selectedDocument.confidence) }}%
          </span>
        </div>

        <div class="detail-content">
          <a-typography-title :level="5">
            完整内容
          </a-typography-title>
          <div class="content-container">
            <pre class="document-content">{{ getFullContent(selectedDocument) }}</pre>
          </div>
        </div>
      </div>
    </a-modal>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, defineProps, defineEmits, type Component } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  MedicineBoxOutlined,
  ScissorOutlined,
  ClockCircleOutlined,
  DownloadOutlined,
  DatabaseOutlined,
  FileOutlined,
  ScheduleOutlined,
  ExperimentOutlined,
  HeartOutlined,
  SafetyOutlined,
} from '@ant-design/icons-vue'
import type { ExtractedMedicalData, ExtractedDocument, DocumentType } from '@/services/llmService'
import { getDocumentTypeLabel, getDocumentTypeColor } from '@/utils/documentTypeUtils'

interface Props {
  visible: boolean
  data: ExtractedMedicalData | null
  originalText?: string
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', data: ExtractedMedicalData): void
  (e: 'confirmOnly', data: ExtractedMedicalData): void
  (e: 'export', data: ExtractedMedicalData): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const showDetailModal = ref(false)
const selectedDocument = ref<ExtractedDocument | null>(null)

// 计算属性
const documents = computed(() => props.data?.documents || [])

// 方法
const handleClose = () => {
  emit('update:visible', false)
}

const handleConfirm = () => {
  if (props.data) {
    emit('confirm', props.data)
  }
  handleClose()
}

const handleConfirmOnly = () => {
  if (props.data) {
    emit('confirmOnly', props.data)
  }
  handleClose()
}

const handleExport = () => {
  if (props.data) {
    emit('export', props.data)
  }
}

const showDocumentDetail = (doc: ExtractedDocument) => {
  selectedDocument.value = doc
  showDetailModal.value = true
}

// 获取文档图标
const getDocumentIcon = (type: DocumentType) => {
  const iconMap: Record<string, Component> = {
    admission_record: FileOutlined,
    admission_record_24h_in: FileOutlined,
    admission_record_24h_out: FileOutlined,
    first_progress_note: ScheduleOutlined,
    daily_progress_note: ScheduleOutlined,
    attending_first_progress: ScheduleOutlined,
    attending_progress: ScheduleOutlined,
    stage_summary: ScheduleOutlined,
    operation_record: ScissorOutlined,
    preoperative_summary: HeartOutlined,
    discharge_record: FileOutlined,
    imaging_report: ExperimentOutlined,
    lab_report: ExperimentOutlined,
    other_examination: ExperimentOutlined,
    surgery_consent: SafetyOutlined,
    anesthesia_consent: SafetyOutlined,
    blood_transfusion_consent: SafetyOutlined,
    special_treatment_consent: SafetyOutlined,
    critical_illness_notice: SafetyOutlined,
  }
  return iconMap[type] || FileOutlined
}

// 获取文档时间戳
const getDocumentTimestamp = (doc: ExtractedDocument): string | null => {
  const titleMatch = doc.title?.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/)
  if (titleMatch) {
    return titleMatch[1]
  }

  if (doc.extractedAt) {
    return doc.extractedAt instanceof Date ? doc.extractedAt.toISOString() : String(doc.extractedAt)
  }

  return null
}

// 格式化时间戳
const formatTimestamp = (timestamp: string | null): string => {
  if (!timestamp) return ''

  try {
    if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(timestamp)) {
      return timestamp
    }

    const date = new Date(timestamp)
    if (isNaN(date.getTime())) return timestamp

    return date
      .toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
      .replace(/\//g, '-')
  } catch {
    return timestamp
  }
}

// 格式化患者信息
const formatPatientInfo = (value: string | undefined | null): string => {
  if (!value || value === '未识别' || value === 'null' || value === 'undefined') {
    return '未识别'
  }
  return value
}

// 格式化年龄
const formatAge = (age: number | undefined | null): string => {
  if (age === null || age === undefined || isNaN(age)) {
    return '未识别'
  }
  return `${age}岁`
}

// 获取完整内容
const getFullContent = (doc: ExtractedDocument): string => {
  if (doc.position?.fullContent && doc.position.fullContent.trim()) {
    return doc.position.fullContent
  }

  const source = props.originalText || ''
  if (source) {
    const si = doc.position?.startIndex
    const ei = doc.position?.endIndex
    if (
      typeof si === 'number' &&
      typeof ei === 'number' &&
      ei > si &&
      si >= 0 &&
      ei <= source.length
    ) {
      return source.slice(si, ei)
    }
  }

  return doc.content || '暂无内容'
}
</script>

<style scoped>
/* 玻璃质感卡片 */
.glass-card {
  backdrop-filter: blur(12px);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
}

/* 模态框内容 */
.modal-content {
  max-height: 70vh;
  overflow-y: auto;
  padding: 4px;
}

/* 解析概览 */
.result-overview {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(147, 51, 234, 0.1));
}

.overview-item {
  text-align: center;
  padding: 12px;
}

.overview-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
  font-weight: 500;
}

.overview-value {
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.confidence-score {
  color: #059669;
}

/* 诊断信息 */
.diagnosis-info {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.1));
}

.diagnosis-item {
  padding: 12px;
}

.diagnosis-label {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.diagnosis-value {
  font-size: 14px;
  color: #1f2937;
  line-height: 1.5;
}

.diagnosis-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* 文书分类结果 */
.documents-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 0;
  border-bottom: 2px solid #e5e7eb;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.empty-state {
  padding: 40px;
  text-align: center;
}

/* 文书网格 */
.documents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.document-card {
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
  min-height: 180px;
  display: flex;
  flex-direction: column;
}

.document-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
  border-color: rgba(59, 130, 246, 0.5);
}

.document-header {
  margin-bottom: 12px;
}

.document-title {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 8px;
  line-height: 1.4;
}

.document-icon {
  color: #6366f1;
  flex-shrink: 0;
}

.document-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.confidence-badge {
  font-size: 11px;
  color: #059669;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.document-summary {
  flex: 1;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
  margin-bottom: 12px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.document-timestamp {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 12px;
}

.document-actions {
  margin-top: auto;
  text-align: right;
}

/* 模态框操作按钮 */
.modal-actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #e5e7eb;
  text-align: right;
}

/* 文书详情模态框 */
.document-detail {
  padding: 8px;
}

.detail-header {
  display: flex;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e7eb;
}

.detail-content {
  margin-top: 16px;
}

.content-container {
  max-height: 400px;
  overflow-y: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
}

.document-content {
  padding: 16px;
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
  white-space: pre-wrap;
  word-wrap: break-word;
}

/* 患者信息样式 */
.missing-info {
  color: #f56565 !important;
  font-style: italic;
}

.overview-value {
  font-weight: 600;
  color: #1f2937;
}

.overview-item {
  text-align: center;
  padding: 8px;
}

.overview-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .documents-grid {
    grid-template-columns: 1fr;
  }

  .result-overview .ant-col {
    margin-bottom: 12px;
  }

  .diagnosis-info .ant-col {
    margin-bottom: 16px;
  }

  .modal-actions {
    text-align: center;
  }

  .modal-actions .ant-space {
    width: 100%;
    justify-content: center;
  }
}

/* 滚动条样式 */
.modal-content::-webkit-scrollbar,
.content-container::-webkit-scrollbar {
  width: 6px;
}

.modal-content::-webkit-scrollbar-track,
.content-container::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.modal-content::-webkit-scrollbar-thumb,
.content-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.modal-content::-webkit-scrollbar-thumb:hover,
.content-container::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
