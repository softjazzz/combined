<template>
  <a-modal
    :open="visible"
    title="LLM 精准解析结果"
    width="1400px"
    :footer="null"
    :destroy-on-close="true"
    :mask-closable="false"
    class="llm-result-modal"
    @update:open="$emit('update:visible', $event)"
  >
    <div class="modal-content">
      <!-- 顶部统计信息 -->
      <div class="top-stats mb-4">
        <a-row :gutter="16">
          <a-col :span="8">
            <div class="stat-card">
              <div class="stat-title">
                模型信息
              </div>
              <div class="stat-content">
                <div>提供商：{{ providerName || '未知' }}</div>
                <div>模型：{{ modelCode || '未知' }}</div>
                <div>Endpoint：{{ endpoint || '-' }}</div>
              </div>
            </div>
          </a-col>
          <a-col :span="8">
            <div class="stat-card">
              <div class="stat-title">
                用量与耗时
              </div>
              <div class="stat-content">
                <div>Tokens：{{ tokensUsed || 0 }}</div>
                <div>耗时：{{ processingTime || 0 }} ms</div>
                <div v-if="savedPct != null">
                  预计节省：{{ savedPct }}%
                </div>
              </div>
            </div>
          </a-col>
          <a-col :span="8">
            <div class="stat-card">
              <div class="stat-title">
                整体置信度
              </div>
              <div class="stat-content">
                <a-progress
                  :percent="confidencePct"
                  :status="
                    confidencePct >= 80 ? 'success' : confidencePct >= 60 ? 'active' : 'normal'
                  "
                  size="small"
                />
              </div>
            </div>
          </a-col>
        </a-row>
      </div>

      <!-- 患者基本信息 -->
      <div class="patient-info mb-4">
        <div class="info-title">
          患者基本信息
        </div>
        <a-row :gutter="24">
          <a-col :span="6">
            <div class="info-item">
              <span class="info-label">患者姓名：</span>
              <span class="info-value">{{ data?.patientName || '-' }}</span>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="info-item">
              <span class="info-label">科室：</span>
              <span class="info-value">{{ data?.department || '-' }}</span>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="info-item">
              <span class="info-label">年龄：</span>
              <span class="info-value">{{ data?.patientAge ?? '-' }}</span>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="info-item">
              <span class="info-label">性别：</span>
              <span class="info-value">{{ data?.patientGender || '-' }}</span>
            </div>
          </a-col>
        </a-row>
      </div>

      <!-- 诊断与手术信息 -->
      <div class="diagnosis-info mb-4">
        <a-row :gutter="16">
          <a-col :span="12">
            <div class="diagnosis-card">
              <div class="diagnosis-title">
                诊断信息
              </div>
              <div class="diagnosis-content">
                <div class="diagnosis-item">
                  <span class="diagnosis-label">主要诊断：</span>
                  <span class="diagnosis-value">{{ data?.primaryDiagnosis || '-' }}</span>
                </div>
                <div class="diagnosis-item">
                  <span class="diagnosis-label">次要诊断：</span>
                  <div class="diagnosis-tags">
                    <a-tag
                      v-for="(d, i) in data?.secondaryDiagnosis || []"
                      :key="i"
                      color="blue"
                    >
                      {{ d }}
                    </a-tag>
                    <span v-if="!(data?.secondaryDiagnosis || []).length">-</span>
                  </div>
                </div>
              </div>
            </div>
          </a-col>
          <a-col :span="12">
            <div class="diagnosis-card">
              <div class="diagnosis-title">
                手术信息
              </div>
              <div class="diagnosis-content">
                <div class="diagnosis-item">
                  <span class="diagnosis-label">主要手术：</span>
                  <span class="diagnosis-value">{{ data?.majorSurgery || '-' }}</span>
                </div>
              </div>
            </div>
          </a-col>
        </a-row>
      </div>

      <!-- 主要内容区域：左右分栏 -->
      <div class="main-content">
        <div class="content-title">
          文书分类与预览
        </div>
        <div class="content-body">
          <!-- 左侧：文书树状结构 -->
          <div class="left-panel">
            <div class="panel-title">
              医疗文书目录
            </div>
            <div class="document-tree">
              <a-tree
                v-if="treeData.length > 0"
                :tree-data="treeData"
                :selected-keys="selectedKeys"
                :expanded-keys="expandedKeys"
                :default-expand-all="true"
                class="custom-tree"
                @select="onDocumentSelect"
                @expand="onTreeExpand"
              >
                <template #title="{ title, confidence, type, icon, isLeaf }">
                  <div
                    class="tree-node"
                    :class="{ 'category-node': !isLeaf, 'document-node': isLeaf }"
                  >
                    <component
                      :is="isLeaf ? getDocumentIcon(type) : getCategoryIcon(icon)"
                      class="node-icon"
                      :class="{ 'category-icon': !isLeaf }"
                    />
                    <span class="node-title">{{ title }}</span>
                    <span
                      v-if="confidence != null && isLeaf"
                      class="node-confidence"
                    >
                      {{ Math.round(confidence) }}%
                    </span>
                  </div>
                </template>
                <template #switcherIcon="{ expanded }">
                  <component :is="expanded ? FolderOpenOutlined : FolderOutlined" />
                </template>
              </a-tree>
              <div
                v-else
                class="empty-tree"
              >
                <a-empty description="暂无文书数据" />
              </div>
            </div>
          </div>

          <!-- 右侧：文书内容详情 -->
          <div class="right-panel">
            <div class="panel-title">
              {{ selectedDocument?.title || '文书内容' }}
              <a-tag
                v-if="selectedDocument"
                :color="getDocumentTypeColor(selectedDocument.type)"
                size="small"
              >
                {{ getDocumentTypeLabel(selectedDocument.type) }}
              </a-tag>
            </div>
            <div class="document-content">
              <div
                v-if="loading"
                class="content-loading"
              >
                <a-spin size="large" />
                <div class="loading-text">
                  加载中...
                </div>
              </div>
              <div
                v-else-if="selectedDocument"
                class="content-text"
              >
                <pre class="document-text">{{ getDocumentContent(selectedDocument) }}</pre>
              </div>
              <div
                v-else
                class="content-empty"
              >
                <a-empty description="请选择左侧文书查看内容" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作按钮 -->
      <div class="modal-actions">
        <a-space size="large">
          <!-- 保存操作 -->
          <a-space>
            <a-button
              type="primary"
              :loading="saving"
              :icon="h(DatabaseOutlined)"
              @click="saveAndRedirect"
            >
              保存并查看详情
            </a-button>
            <a-button
              :loading="saving"
              :icon="h(SaveOutlined)"
              @click="saveOnly"
            >
              仅保存到数据库
            </a-button>
          </a-space>

          <!-- 导出操作 -->
          <a-space>
            <a-button
              :icon="h(DownloadOutlined)"
              @click="exportResult"
            >
              导出JSON
            </a-button>
            <a-button
              :icon="h(FilePdfOutlined)"
              @click="exportPDF"
            >
              导出PDF报告
            </a-button>
          </a-space>

          <!-- 其他操作 -->
          <a-space>
            <a-button
              :icon="h(PlusOutlined)"
              @click="goToImport"
            >
              继续导入
            </a-button>
            <a-button
              :icon="h(CloseOutlined)"
              @click="handleClose"
            >
              关闭
            </a-button>
          </a-space>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, h, defineProps, defineEmits, type Component } from 'vue'
import { message } from 'ant-design-vue'
import {
  DatabaseOutlined,
  SaveOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  PlusOutlined,
  CloseOutlined,
  FileOutlined,
  ScheduleOutlined,
  ExperimentOutlined,
  HeartOutlined,
  SafetyOutlined,
  ScissorOutlined,
  FileTextOutlined,
  EditOutlined,
  ExportOutlined,
  FolderOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons-vue'
import type { ExtractedDocument } from '@/services/llmService'
import { DocumentType } from '@/services/llmService'
import {
  getDocumentTypeLabel,
  getDocumentTypeColor,
  getDocumentCategory,
} from '@/utils/documentTypeUtils'

interface LLMAnalysisMeta {
  provider?: string
  model?: string
  endpoint?: string
  tokensUsed?: number
  processingTime?: number
}

interface TreeNodeData {
  key: string
  title: string
  confidence?: number
  type: DocumentType
  document: ExtractedDocument
  isLeaf: true
}

interface CategoryTreeNode {
  key: string
  title: string
  icon: string
  children: TreeNodeData[]
  isLeaf: false
  selectable: false
}

interface Props {
  visible: boolean
  data?: Partial<{
    documents: ExtractedDocument[]
    patientName?: string
    department?: string
    patientAge?: number
    patientGender?: string
    primaryDiagnosis?: string
    secondaryDiagnosis?: string[]
    majorSurgery?: string
    confidence?: number
    content?: string
  }> | null
  result?: LLMAnalysisMeta | null
  originalText?: string
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'save-and-redirect'): void
  (e: 'save-only'): void
  (e: 'export-result'): void
  (e: 'export-pdf'): void
  (e: 'go-to-import'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const selectedKeys = ref<string[]>([])
const expandedKeys = ref<string[]>([])
const selectedDocument = ref<ExtractedDocument | null>(null)

// 计算属性
const providerName = computed(() => props.result?.provider || '未知')
const modelCode = computed(() => props.result?.model || '未知')
const endpoint = computed(() => props.result?.endpoint || '-')
const tokensUsed = computed(() => props.result?.tokensUsed || 0)
const processingTime = computed(() => props.result?.processingTime || 0)
const confidencePct = computed(() => {
  const c = props.data?.confidence
  if (typeof c === 'number') return Math.max(0, Math.min(100, Math.round(c)))
  return 0
})
const savedPct = computed(() => {
  try {
    const text = typeof props.data?.content === 'string' ? props.data!.content : ''
    const baseline = (text ? Math.round(text.length / 4) : 0) + 1000
    const used = tokensUsed.value || 0
    if (baseline <= 0) return null
    return Math.max(0, Math.round((Math.max(0, baseline - used) / baseline) * 100))
  } catch {
    return null
  }
})

// 构建树形数据
const treeData = computed<CategoryTreeNode[]>(() => {
  const documents = Array.isArray(props.data?.documents) ? props.data!.documents : []

  // 按分类分组文书
  const groupedDocs = new Map<string, TreeNodeData[]>()

  documents.forEach((doc: ExtractedDocument, index: number) => {
    const docType = resolveDocumentType(doc)
    const category = getDocumentCategory(docType)
    if (!groupedDocs.has(category)) {
      groupedDocs.set(category, [])
    }
    const categoryBucket = groupedDocs.get(category)
    if (!categoryBucket) return
    categoryBucket.push({
      key: doc.id || `doc_${index}`,
      title: doc.title || getDocumentTypeLabel(docType),
      confidence: doc.confidence,
      type: docType,
      document: doc,
      isLeaf: true,
    })
  })

  // 构建树形结构
  const treeNodes: CategoryTreeNode[] = []

  // 定义分类顺序和标签
  const categoryOrder: Array<{ key: string; label: string; icon: string }> = [
    { key: 'admission_record', label: '入院记录', icon: 'FileTextOutlined' },
    { key: 'progress_note', label: '病程记录', icon: 'EditOutlined' },
    { key: 'operation_record', label: '手术记录', icon: 'ScissorOutlined' },
    { key: 'discharge_record', label: '出院记录', icon: 'ExportOutlined' },
    { key: 'auxiliary_examination', label: '检验检查报告', icon: 'ExperimentOutlined' },
    { key: 'informed_consent', label: '知情同意书', icon: 'SafetyOutlined' },
  ]

  categoryOrder.forEach((category) => {
    const categoryDocs = groupedDocs.get(category.key) || []
    if (categoryDocs.length > 0) {
      treeNodes.push({
        key: category.key,
        title: category.label,
        icon: category.icon,
        children: categoryDocs,
        isLeaf: false,
        selectable: false, // 分类节点不可选择
      })
    }
  })

  return treeNodes
})

// 监听数据变化，自动选择第一个文书
watch(
  () => props.data?.documents,
  (docs) => {
    const list = Array.isArray(docs) ? docs : []
    if (list.length > 0) {
      const firstDoc = list[0]
      const firstKey = firstDoc.id || 'doc_0'
      selectedKeys.value = [firstKey]
      selectedDocument.value = firstDoc

      // 展开所有分类节点
      const categoryKeys = [
        'admission_record',
        'progress_note',
        'operation_record',
        'discharge_record',
        'auxiliary_examination',
        'informed_consent',
      ]
      expandedKeys.value = categoryKeys
    } else {
      selectedKeys.value = []
      selectedDocument.value = null
      expandedKeys.value = []
    }
  },
  { immediate: true },
)

// 方法
const handleClose = () => {
  emit('update:visible', false)
}

const onDocumentSelect = (keys: string[], info: unknown) => {
  if (keys.length > 0) {
    const selectedNode = (info as { node?: { isLeaf?: boolean; document?: ExtractedDocument } })
      .node
    // 只有文书节点（叶子节点）才能被选中
    if (selectedNode?.isLeaf && selectedNode.document) {
      selectedKeys.value = keys
      selectedDocument.value = selectedNode.document
    } else {
      // 如果选中的是分类节点，清除选择
      selectedKeys.value = []
      selectedDocument.value = null
    }
  } else {
    selectedKeys.value = []
    selectedDocument.value = null
  }
}

const onTreeExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

const getCategoryIcon = (iconName: string) => {
  const iconMap: Record<string, Component> = {
    FileTextOutlined,
    EditOutlined,
    ScissorOutlined,
    ExportOutlined,
    ExperimentOutlined,
    SafetyOutlined,
  }
  return iconMap[iconName] || FolderOutlined
}

const resolveDocumentType = (doc: ExtractedDocument): DocumentType => {
  return (doc.type as DocumentType) || DocumentType.DAILY_PROGRESS_NOTE
}

const getDocumentIcon = (type: DocumentType) => {
  const iconMap = {
    [DocumentType.ADMISSION_RECORD]: FileTextOutlined,
    [DocumentType.ADMISSION_RECORD_24H_IN]: FileTextOutlined,
    [DocumentType.ADMISSION_RECORD_24H_OUT]: FileTextOutlined,
    [DocumentType.FIRST_PROGRESS_NOTE]: EditOutlined,
    [DocumentType.DAILY_PROGRESS_NOTE]: EditOutlined,
    [DocumentType.ATTENDING_FIRST_PROGRESS]: EditOutlined,
    [DocumentType.ATTENDING_PROGRESS]: EditOutlined,
    [DocumentType.CONSULTATION_RECORD]: EditOutlined,
    [DocumentType.HANDOVER_RECORD]: EditOutlined,
    [DocumentType.STAGE_SUMMARY]: EditOutlined,
    [DocumentType.OPERATION_RECORD]: ScissorOutlined,
    [DocumentType.PREOPERATIVE_SUMMARY]: ScissorOutlined,
    [DocumentType.DISCHARGE_RECORD]: ExportOutlined,
    [DocumentType.DEATH_RECORD]: ExportOutlined,
    [DocumentType.DEATH_CASE_DISCUSSION]: ExportOutlined,
    [DocumentType.IMAGING_REPORT]: ExperimentOutlined,
    [DocumentType.LAB_REPORT]: ExperimentOutlined,
    [DocumentType.OTHER_EXAMINATION]: ExperimentOutlined,
    [DocumentType.SURGERY_CONSENT]: SafetyOutlined,
    [DocumentType.ANESTHESIA_CONSENT]: SafetyOutlined,
    [DocumentType.BLOOD_TRANSFUSION_CONSENT]: SafetyOutlined,
    [DocumentType.SPECIAL_TREATMENT_CONSENT]: SafetyOutlined,
    [DocumentType.CRITICAL_ILLNESS_NOTICE]: SafetyOutlined,
  }
  return iconMap[type] || FileOutlined
}

const getDocumentContent = (doc: ExtractedDocument): string => {
  if (doc.position?.fullContent && doc.position.fullContent.trim()) {
    return doc.position.fullContent
  }

  const source = props.originalText || props.data?.content || ''
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

// 事件处理
const saveAndRedirect = () => {
  emit('save-and-redirect')
}

const saveOnly = () => {
  emit('save-only')
}

const exportResult = () => {
  emit('export-result')
}

const exportPDF = () => {
  emit('export-pdf')
}

const goToImport = () => {
  emit('go-to-import')
}
</script>

<style scoped>
.llm-result-modal :deep(.ant-modal-content) {
  height: 90vh;
  display: flex;
  flex-direction: column;
}

.llm-result-modal :deep(.ant-modal-body) {
  flex: 1;
  padding: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 顶部统计信息 */
.top-stats {
  flex-shrink: 0;
}

.stat-card {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 12px;
  height: 100%;
}

.stat-title {
  font-size: 12px;
  color: #666;
  font-weight: 500;
  margin-bottom: 8px;
}

.stat-content {
  font-size: 13px;
  line-height: 1.4;
}

.stat-content > div {
  margin-bottom: 2px;
}

/* 患者基本信息 */
.patient-info {
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 16px;
}

.info-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 8px;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.info-label {
  font-size: 13px;
  color: #666;
  min-width: 60px;
}

.info-value {
  font-size: 13px;
  color: #333;
  font-weight: 500;
}

/* 诊断信息 */
.diagnosis-info {
  flex-shrink: 0;
}

.diagnosis-card {
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 16px;
  height: 100%;
}

.diagnosis-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 8px;
}

.diagnosis-content {
  font-size: 13px;
}

.diagnosis-item {
  margin-bottom: 12px;
  display: flex;
  align-items: flex-start;
}

.diagnosis-label {
  color: #666;
  min-width: 80px;
  flex-shrink: 0;
}

.diagnosis-value {
  color: #333;
  font-weight: 500;
}

.diagnosis-tags {
  flex: 1;
}

.diagnosis-tags .ant-tag {
  margin-bottom: 4px;
}

/* 主要内容区域 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.content-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid #2b6cf6;
}

.content-body {
  flex: 1;
  display: flex;
  gap: 16px;
  min-height: 0;
}

/* 左侧面板 */
.left-panel {
  width: 350px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  padding: 16px;
  border-bottom: 1px solid #e9ecef;
  background: #f8f9fa;
  border-radius: 6px 6px 0 0;
}

.document-tree {
  flex: 1;
  padding: 8px;
  overflow-y: auto;
}

.custom-tree :deep(.ant-tree-node-content-wrapper) {
  padding: 6px 8px;
  border-radius: 4px;
  transition: all 0.2s;
  margin: 2px 0;
}

.custom-tree :deep(.ant-tree-node-content-wrapper:hover) {
  background-color: #f0f8ff;
}

.custom-tree :deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
}

/* 分类节点样式 */
.custom-tree :deep(.ant-tree-treenode) .category-node {
  font-weight: 600;
}

.custom-tree :deep(.ant-tree-treenode) .category-node .node-title {
  color: #262626;
  font-size: 14px;
}

.custom-tree :deep(.ant-tree-treenode) .category-node .category-icon {
  color: #2b6cf6;
  font-size: 16px;
}

/* 文书节点样式 */
.custom-tree :deep(.ant-tree-treenode) .document-node .node-title {
  color: #595959;
  font-size: 13px;
}

.custom-tree :deep(.ant-tree-treenode) .document-node .node-icon {
  color: #8c8c8c;
  font-size: 14px;
}

/* 树形结构缩进 */
.custom-tree :deep(.ant-tree-child-tree) {
  margin-left: 8px;
}

.custom-tree :deep(.ant-tree-switcher) {
  color: #2b6cf6;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.node-icon {
  flex-shrink: 0;
}

.node-title {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-confidence {
  font-size: 11px;
  color: #666;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.empty-tree {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
  background: #fff;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.right-panel .panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.document-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  min-height: 0;
}

.content-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 16px;
}

.loading-text {
  color: #666;
  font-size: 14px;
}

.content-text {
  height: 100%;
}

.document-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e9ecef;
}

.content-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
}

/* 底部操作按钮 */
.modal-actions {
  flex-shrink: 0;
  padding: 16px 0 0 0;
  border-top: 1px solid #e9ecef;
  margin-top: 16px;
  display: flex;
  justify-content: center;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .left-panel {
    width: 300px;
  }
}

@media (max-width: 992px) {
  .content-body {
    flex-direction: column;
  }

  .left-panel {
    width: 100%;
    height: 200px;
  }

  .right-panel {
    flex: 1;
  }
}

/* 工具类 */
.mb-4 {
  margin-bottom: 16px;
}
</style>
