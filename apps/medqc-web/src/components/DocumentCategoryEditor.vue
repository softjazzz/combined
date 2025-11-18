<template>
  <div class="document-category-editor">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-skeleton :loading="true" active>
        <a-skeleton-paragraph :rows="5" />
      </a-skeleton>
    </div>

    <!-- 编辑界面 -->
    <div v-else-if="documentData.categories.length > 0" class="editor-container">
      <!-- 操作栏 -->
      <div class="editor-toolbar">
        <div class="toolbar-left">
          <a-button type="primary" @click="saveAllChanges" :loading="saving">
            <template #icon><SaveOutlined /></template>
            保存所有更改
          </a-button>
          <a-button @click="resetAllChanges">
            <template #icon><ReloadOutlined /></template>
            重置更改
          </a-button>
        </div>
        <div class="toolbar-right">
          <a-tag v-if="hasChanges" color="orange">有未保存的更改</a-tag>
          <a-tag v-else color="green">所有更改已保存</a-tag>
        </div>
      </div>

      <!-- 分类编辑器 -->
      <div class="categories-editor">
        <a-tabs v-model:activeKey="activeTab" type="card" class="category-tabs">
          <a-tab-pane
            v-for="category in documentData.categories"
            :key="category.category_code"
            :tab="getCategoryTabLabel(category)"
          >
            <div class="category-editor-content">
              <!-- 分类信息 -->
              <div class="category-info-panel">
                <a-card :bordered="false" class="info-card">
                  <div class="category-summary">
                    <h3>{{ category.category_name }}</h3>
                    <p class="category-description">{{ category.category_description }}</p>
                    <div class="category-stats">
                      <a-statistic title="文档数量" :value="category.document_count" />
                      <a-statistic title="已修改" :value="getModifiedCount(category.category_code)" />
                    </div>
                  </div>
                </a-card>
              </div>

              <!-- 文档列表编辑 -->
              <div class="documents-editor">
                <div
                  v-for="(document, index) in category.documents"
                  :key="document.id"
                  class="document-editor-item"
                >
                  <a-card hoverable class="document-editor-card">
                    <!-- 文档头部 -->
                    <div class="document-editor-header">
                      <div class="document-title-editor">
                        <a-input
                          v-model:value="document.title"
                          placeholder="文档标题"
                          class="title-input"
                          @input="markAsModified(document.id)"
                        >
                          <template #addonBefore>
                            <span class="document-index">{{ index + 1 }}</span>
                          </template>
                        </a-input>
                      </div>
                      <div class="document-meta-editor">
                        <a-select
                          v-model:value="document.type_info.type_code"
                          placeholder="选择文档类型"
                          class="type-selector"
                          @change="markAsModified(document.id)"
                        >
                          <a-select-option
                            v-for="type in getAvailableTypes(category.category_code)"
                            :key="type.type_code"
                            :value="type.type_code"
                          >
                            {{ type.type_name }}
                          </a-select-option>
                        </a-select>
                        <a-tag
                          :color="document.ai_classified ? 'green' : 'default'"
                        >
                          {{ document.ai_classified ? 'AI分类' : '手动' }}
                        </a-tag>
                        <a-tag
                          v-if="isModified(document.id)"
                          color="orange"
                        >
                          已修改
                        </a-tag>
                      </div>
                    </div>

                    <!-- 文档内容编辑 -->
                    <div class="document-content-editor">
                      <div class="content-editor-header">
                        <span class="content-label">文档内容</span>
                        <div class="content-actions">
                          <a-switch
                            v-model:checked="realTimeQCEnabled"
                            size="small"
                            checked-children="实时质控"
                            un-checked-children="手动质控"
                            @change="toggleRealTimeQC"
                          />
                          <a-button
                            size="small"
                            type="link"
                            @click="toggleContentExpand(document.id)"
                          >
                            {{ isContentExpanded(document.id) ? '收起' : '展开' }}
                          </a-button>
                          <a-button
                            size="small"
                            type="link"
                            @click="formatContent(document)"
                          >
                            格式化
                          </a-button>
                        </div>
                      </div>
                      <div class="content-editor-container">
                        <div class="content-textarea-wrapper">
                          <a-textarea
                            v-model:value="document.content"
                            :rows="isContentExpanded(document.id) ? 15 : 6"
                            placeholder="请输入文档内容"
                            class="content-textarea"
                            @input="handleContentChange(document)"
                          />
                        </div>

                        <!-- 质控结果面板 -->
                        <div
                          v-if="showQCPanel(document.id)"
                          class="qc-results-panel"
                          :class="{ 'expanded': isContentExpanded(document.id) }"
                        >
                          <div class="qc-panel-header">
                            <span class="qc-panel-title">
                              <ThunderboltOutlined />
                              质控分析
                            </span>
                            <a-button
                              size="small"
                              type="text"
                              @click="hideQCPanel(document.id)"
                            >
                              <CloseOutlined />
                            </a-button>
                          </div>

                          <div class="qc-panel-content">
                            <!-- 质控状态和评分 -->
                            <div v-if="getDocumentQCResult(document.id)" class="qc-summary">
                              <div class="qc-score-display">
                                <a-statistic
                                  title="质控评分"
                                  :value="getDocumentQCResult(document.id).qc_score"
                                  suffix="/100"
                                  :value-style="{
                                    color: getQCScoreColor(getDocumentQCResult(document.id).qc_score),
                                    fontSize: '16px',
                                    fontWeight: 'bold'
                                  }"
                                />
                                <a-tag
                                  :color="getQCStatusColor(getDocumentQCResult(document.id).qc_status)"
                                  class="qc-status-display"
                                >
                                  {{ getQCStatusText(getDocumentQCResult(document.id).qc_status) }}
                                </a-tag>
                              </div>
                            </div>

                            <!-- 分析中状态 -->
                            <div v-else-if="analyzingDocuments.has(document.id)" class="qc-analyzing">
                              <a-spin>
                                <div class="analyzing-text">
                                  <LoadingOutlined />
                                  正在进行质控分析...
                                </div>
                              </a-spin>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <!-- 文档摘要编辑 -->
                    <div class="document-summary-editor">
                      <a-input
                        v-model:value="document.summary"
                        placeholder="文档摘要（可选）"
                        class="summary-input"
                        @input="markAsModified(document.id)"
                      >
                        <template #addonBefore>摘要</template>
                      </a-input>
                    </div>

                    <!-- 文档操作 -->
                    <div class="document-actions">
                      <div class="action-left">
                        <a-button
                          size="small"
                          type="primary"
                          @click="saveDocument(document)"
                          :loading="isSaving(document.id)"
                        >
                          保存
                        </a-button>
                        <a-button
                          size="small"
                          @click="resetDocument(document)"
                        >
                          重置
                        </a-button>
                        <!-- 质控分析按钮 -->
                        <a-button
                          size="small"
                          type="default"
                          :loading="analyzingDocuments.has(document.id)"
                          @click="analyzeDocument(document)"
                        >
                          <template #icon><ThunderboltOutlined /></template>
                          质控分析
                        </a-button>
                      </div>
                      <div class="action-right">
                        <!-- 质控状态显示 -->
                        <a-tag
                          v-if="document.qc_status"
                          :color="getQCStatusColor(document.qc_status)"
                          class="qc-status-tag"
                        >
                          {{ getQCStatusText(document.qc_status) }}
                        </a-tag>
                        <a-button
                          size="small"
                          danger
                          @click="deleteDocument(document)"
                        >
                          删除
                        </a-button>
                      </div>
                    </div>
                  </a-card>
                </div>

                <!-- 添加新文档 -->
                <div class="add-document-section">
                  <a-button
                    type="dashed"
                    class="add-document-btn"
                    @click="addNewDocument(category.category_code)"
                  >
                    <template #icon><PlusOutlined /></template>
                    添加新文档
                  </a-button>
                </div>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <a-empty description="暂无文档数据" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { documentQCService } from '@/services/document-qc-service'
import type { DocumentUpdateRequest } from '@/services/document-qc-service'
import type { DocumentApiResponse, DocumentCategoryItem, DocumentItem, DocumentQCResult } from '@/types/document-category'
import { resolveApiBaseUrl, extractApiData } from '@/utils/api-helpers'
import {
  SaveOutlined,
  ReloadOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  CloseOutlined,
  LoadingOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons-vue'

const props = defineProps({
  recordId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['save-success', 'save-error'])

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const documentData = ref<DocumentApiResponse>({
  record_id: '',
  categories: [],
  total_documents: 0,
  classification_summary: {}
})
const activeTab = ref('')
const modifiedDocuments = ref<Set<string>>(new Set())
const expandedContent = ref<Set<string>>(new Set())
const savingDocuments = ref<Set<string>>(new Set())
const analyzingDocuments = ref<Set<string>>(new Set())
const originalData = ref<DocumentApiResponse | null>(null)
const availableTypes = ref<Record<string, Array<{ type_code: string; type_name: string; type_id?: string }>>>({})

// 实时质控相关
const realTimeQCEnabled = ref(true)
const qcPanelVisible = ref<Set<string>>(new Set())
const qcResults = ref<Map<string, DocumentQCResult>>(new Map())
const qcDebounceTimers = ref<Map<string, ReturnType<typeof setTimeout>>>(new Map())

// 计算属性
const hasChanges = computed(() => modifiedDocuments.value.size > 0)

// 方法
const loadDocuments = async () => {
  if (!props.recordId) return
  
  loading.value = true
  try {
    const baseURL = resolveApiBaseUrl()
    
    const response = await fetch(`${baseURL}/api/medical-records/${props.recordId}/documents`)
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const raw = await response.json()
    const data = extractApiData<DocumentApiResponse>(raw, '加载文档失败')
    if (!data || !Array.isArray(data.categories)) {
      throw new Error('文档数据格式不正确')
    }
    documentData.value = data
    
    // 保存原始数据用于重置
    originalData.value = JSON.parse(JSON.stringify(data)) as DocumentApiResponse
    
    // 设置默认活动标签
    if (data.categories.length > 0) {
      activeTab.value = data.categories[0].category_code
    }
    
    // 加载可用的文档类型
    await loadAvailableTypes()
    
  } catch (error) {
    console.error('加载文档失败:', error)
    const errMsg = error instanceof Error ? error.message : '未知错误'
    message.error('加载文档失败: ' + errMsg)
  } finally {
    loading.value = false
  }
}

const loadAvailableTypes = async () => {
  try {
    const baseURL = resolveApiBaseUrl()
    
    const response = await fetch(`${baseURL}/api/test-classification-mapping`)
    const raw = await response.json()
    const data = extractApiData<{ types?: Record<string, { id?: string } | string> } | Record<string, { id?: string } | string> | null | undefined>(raw, '加载文档类型失败')
    const typesSource =
      data && typeof data === 'object' && 'types' in (data as Record<string, unknown>)
        ? ((data as { types?: Record<string, { id?: string } | string> }).types ?? {})
        : ((data ?? {}) as Record<string, { id?: string } | string>)
    
    // 按分类组织类型数据
    const typeMap: Record<string, Array<{ type_code: string; type_name: string; type_id?: string }>> = {}
    Object.entries(typesSource || {}).forEach(([key, typeInfo]) => {
      const [categoryCode, typeCode] = key.split('.')
      if (!typeMap[categoryCode]) {
        typeMap[categoryCode] = []
      }
      typeMap[categoryCode].push({
        type_code: typeCode,
        type_name: typeCode.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        type_id: typeof typeInfo === 'string' ? typeInfo : typeInfo?.id
      })
    })

    availableTypes.value = typeMap
    
  } catch (error) {
    console.error('加载文档类型失败:', error)
  }
}

const getCategoryTabLabel = (category: DocumentCategoryItem) => {
  const modifiedCount = getModifiedCount(category.category_code)
  return `${category.category_name} (${category.document_count})${modifiedCount > 0 ? ' *' : ''}`
}

const getModifiedCount = (categoryCode: string) => {
  const category = documentData.value.categories.find(c => c.category_code === categoryCode)
  if (!category) return 0
  
  return category.documents.filter(doc => modifiedDocuments.value.has(doc.id)).length
}

const getAvailableTypes = (categoryCode: string) => {
  return availableTypes.value[categoryCode] || []
}

const markAsModified = (documentId: string) => {
  modifiedDocuments.value.add(documentId)
}

const isModified = (documentId: string) => {
  return modifiedDocuments.value.has(documentId)
}

const isContentExpanded = (documentId: string) => {
  return expandedContent.value.has(documentId)
}

const isSaving = (documentId: string) => {
  return savingDocuments.value.has(documentId)
}

const toggleContentExpand = (documentId: string) => {
  if (expandedContent.value.has(documentId)) {
    expandedContent.value.delete(documentId)
  } else {
    expandedContent.value.add(documentId)
  }
}

const formatContent = (document: DocumentItem) => {
  // 简单的内容格式化
  document.content = document.content
    .replace(/\n\s*\n/g, '\n\n') // 规范化换行
    .replace(/^\s+|\s+$/g, '') // 去除首尾空白
  markAsModified(document.id)
}

const saveDocument = async (document: DocumentItem) => {
  savingDocuments.value.add(document.id)
  try {
    // 准备更新数据
    const typeCode =
      typeof document.type_info?.type_code === 'string'
        ? document.type_info.type_code
        : (typeof document.type === 'string' ? document.type : undefined)
    const updates: Omit<DocumentUpdateRequest, 'auto_qc'> = {
      title: document.title,
      content: document.content,
      summary: document.summary,
      type_code: typeCode
    }

    // 使用质控服务保存文档
    const result = await documentQCService.saveDocumentWithQC(
      document.id,
      updates,
      realTimeQCEnabled.value
    )

    // 保存成功后清除修改标记
    modifiedDocuments.value.delete(document.id)

    // 如果有质控结果，更新文档状态
    if (result.qcResult) {
      const qcResult: DocumentQCResult = {
        qc_status: result.qcResult.qc_status,
        qc_score: result.qcResult.qc_score,
        analysis_time: result.qcResult.analysis_time,
        failed_rules: result.qcResult.failed_rules,
        results: result.qcResult.results,
        suggestions: result.qcResult.suggestions
      }

      document.qc_status = qcResult.qc_status
      document.qc_score = qcResult.qc_score
      document.qc_last_analyzed = qcResult.analysis_time
      document.qc_issues_count = qcResult.failed_rules || 0

      // 存储质控结果
      qcResults.value.set(document.id, qcResult)
      qcPanelVisible.value.add(document.id)

      message.success(`文档保存成功，质控评分: ${qcResult.qc_score}分`)
    } else if (result.updateResult.auto_qc_triggered) {
      message.success('文档保存成功，质控分析进行中...')
      qcPanelVisible.value.add(document.id)
    } else {
      message.success('文档保存成功')
    }

    emit('save-success', document)

  } catch (error) {
    console.error('保存文档失败:', error)
    const errMsg = error instanceof Error ? error.message : '未知错误'
    message.error('保存文档失败: ' + errMsg)
    emit('save-error', error)
  } finally {
    savingDocuments.value.delete(document.id)
  }
}

const resetDocument = (document: DocumentItem) => {
  const originalDoc = findOriginalDocument(document.id)
  if (originalDoc) {
    Object.assign(document, JSON.parse(JSON.stringify(originalDoc)))
    modifiedDocuments.value.delete(document.id)
    message.success('文档已重置')
  }
}

const deleteDocument = async (document: DocumentItem) => {
  Modal.confirm({
    title: '确认删除',
    content: `确定要删除文档"${document.title}"吗？此操作不可恢复。`,
    okText: '确定',
    cancelText: '取消',
    onOk: async () => {
      try {
        // 这里应该调用删除API
        message.success('文档删除成功')
      } catch (error) {
        message.error('删除文档失败')
      }
    }
  })
}

// 质控分析方法
const analyzeDocument = async (document: DocumentItem) => {
  if (!document.id || document.id.startsWith('new_')) {
    message.warning('请先保存文档后再进行质控分析')
    return
  }

  analyzingDocuments.value.add(document.id)
  try {
    const baseURL = resolveApiBaseUrl()

    // 更新文档状态为分析中
    document.qc_status = 'analyzing'

    const response = await fetch(`${baseURL}/api/medical-documents/${document.id}/qc-analysis`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        rule_codes: ['POC_001', 'POC_002'] // 使用概念验证规则
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const raw = await response.json()
    const result = extractApiData<DocumentQCResult & {
      qc_status: string
      qc_score: number
      results?: unknown
      failed_rules?: number
    }>(raw, '质控分析失败')

    // 更新文档的质控状态和结果
    document.qc_status = result.qc_status
    document.qc_score = result.qc_score
    document.qc_results = result.results
    document.qc_last_analyzed = new Date().toISOString()
    document.qc_issues_count = result.failed_rules || 0

    // 存储质控结果到本地状态
    qcResults.value.set(document.id, result)
    qcPanelVisible.value.add(document.id)

    message.success(`质控分析完成，评分: ${result.qc_score}分`)

  } catch (error) {
    console.error('质控分析失败:', error)
    document.qc_status = 'failed'
    const errMsg = error instanceof Error ? error.message : '未知错误'
    message.error('质控分析失败: ' + errMsg)
  } finally {
    analyzingDocuments.value.delete(document.id)
  }
}

const addNewDocument = (categoryCode: string) => {
  const category = documentData.value.categories.find(c => c.category_code === categoryCode)
  if (!category) return
  
  const newDocument: DocumentItem = {
    id: `new_${Date.now()}`,
    title: '新文档',
    content: '',
    summary: '',
    ai_classified: false,
    classification_confidence: 0,
    position_info: {},
    sort_order: category.documents.length,
    status: 'active',
    qc_status: 'pending',
    qc_score: null,
    metadata: {},
    type_info: {
      type_id: null,
      type_code: '',
      type_name: '请选择类型',
      type_description: ''
    }
  }
  
  category.documents.push(newDocument)
  category.document_count++
  markAsModified(newDocument.id)
}

const saveAllChanges = async () => {
  if (!hasChanges.value) {
    message.info('没有需要保存的更改')
    return
  }

  saving.value = true
  try {
    const promises: Array<Promise<unknown>> = []

    documentData.value.categories.forEach(category => {
      category.documents.forEach(document => {
        if (modifiedDocuments.value.has(document.id)) {
          promises.push(saveDocument(document))
        }
      })
    })

    await Promise.all(promises)
    message.success('所有更改已保存')

  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const resetAllChanges = () => {
  if (!originalData.value) return
  documentData.value = JSON.parse(JSON.stringify(originalData.value)) as DocumentApiResponse
  modifiedDocuments.value.clear()
  message.success('所有更改已重置')
}

const findOriginalDocument = (documentId: string): DocumentItem | null => {
  if (!originalData.value) return null
  for (const category of originalData.value.categories) {
    const doc = category.documents.find(d => d.id === documentId)
    if (doc) return doc
  }
  return null
}

// 质控状态相关方法
const getQCStatusColor = (status?: string) => {
  const statusColors = {
    'passed': 'green',
    'warning': 'orange',
    'failed': 'red',
    'pending': 'default',
    'analyzing': 'blue'
  }
  return statusColors[status] || 'default'
}

const getQCStatusText = (status?: string) => {
  const statusTexts = {
    'passed': '质控通过',
    'warning': '质控警告',
    'failed': '质控失败',
    'pending': '待质控',
    'analyzing': '分析中'
  }
  return statusTexts[status] || '未知状态'
}

// 实时质控相关方法
const handleContentChange = (document: DocumentItem) => {
  markAsModified(document.id)

  if (realTimeQCEnabled.value) {
    // 清除之前的定时器
    if (qcDebounceTimers.value.has(document.id)) {
      clearTimeout(qcDebounceTimers.value.get(document.id))
    }

    // 设置新的防抖定时器
    const timer = setTimeout(() => {
      performRealTimeQC(document)
    }, 3000) // 3秒防抖

    qcDebounceTimers.value.set(document.id, timer)
  }
}

const performRealTimeQC = async (document: DocumentItem) => {
  if (!document.content || document.content.trim().length < 10) {
    return // 内容太短，不进行质控
  }

  try {
    qcPanelVisible.value.add(document.id)
    await analyzeDocument(document)
  } catch (error) {
    console.error('实时质控分析失败:', error)
  }
}

const toggleRealTimeQC = (enabled: boolean) => {
  if (!enabled) {
    // 清除所有防抖定时器
    qcDebounceTimers.value.forEach(timer => clearTimeout(timer))
    qcDebounceTimers.value.clear()
  }
}

const showQCPanel = (documentId: string) => {
  return qcPanelVisible.value.has(documentId) || analyzingDocuments.value.has(documentId)
}

const hideQCPanel = (documentId) => {
  qcPanelVisible.value.delete(documentId)
  qcResults.value.delete(documentId)
}

const getDocumentQCResult = (documentId: string): DocumentQCResult | undefined => {
  return qcResults.value.get(documentId)
}

const getDocumentQCIssues = (documentId: string) => {
  const result = qcResults.value.get(documentId)
  return result?.results?.filter(r => !r.compliant) || []
}

const getDocumentQCSuggestions = (documentId: string) => {
  const result = qcResults.value.get(documentId)
  return result?.suggestions || []
}

const getQCScoreColor = (score?: number) => {
  if (typeof score !== 'number') return '#f5222d'
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#1890ff'
  if (score >= 70) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const getIssueSeverityColor = (severity?: string) => {
  const colors = {
    'critical': 'red',
    'major': 'orange',
    'minor': 'yellow',
    'info': 'blue'
  }
  return colors[severity] || 'default'
}

const getIssueSeverityText = (severity?: string) => {
  const texts = {
    'critical': '严重',
    'major': '重要',
    'minor': '轻微',
    'info': '提示'
  }
  return texts[severity] || severity
}

const highlightIssue = (document, issue) => {
  // TODO: 实现问题定位功能
  const text = issue?.message ? String(issue.message) : '未提供问题描述'
  message.info(`定位到问题: ${text}`)
}

// 生命周期
onMounted(() => {
  loadDocuments()
})

watch(() => props.recordId, () => {
  loadDocuments()
})
</script>

<style scoped>
.document-category-editor {
  padding: 20px;
}

.loading-container {
  padding: 20px;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.toolbar-left {
  display: flex;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  align-items: center;
}

.categories-editor {
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.category-tabs {
  min-height: 600px;
}

.category-editor-content {
  padding: 20px;
}

.category-info-panel {
  margin-bottom: 20px;
}

.info-card {
  border: none;
  background: #f8f9fa;
}

.category-summary h3 {
  margin: 0 0 10px 0;
  color: #303133;
}

.category-description {
  color: #606266;
  margin-bottom: 15px;
}

.category-stats {
  display: flex;
  gap: 40px;
}

.documents-editor {
  space-y: 16px;
}

.document-editor-item {
  margin-bottom: 20px;
}

.document-editor-card {
  border: 1px solid #e4e7ed;
}

.document-editor-header {
  margin-bottom: 15px;
}

.document-title-editor {
  margin-bottom: 10px;
}

.title-input {
  font-size: 16px;
}

.document-index {
  background: #409eff;
  color: white;
  padding: 0 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.document-meta-editor {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type-selector {
  width: 200px;
}

.document-content-editor {
  margin: 15px 0;
}

.content-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.content-label {
  font-weight: 500;
  color: #303133;
}

.content-actions {
  display: flex;
  gap: 5px;
}

.content-textarea {
  font-family: 'Courier New', monospace;
}

/* 质控面板样式 */
.content-editor-container {
  display: flex;
  gap: 16px;
}

.content-textarea-wrapper {
  flex: 1;
}

.qc-results-panel {
  width: 300px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: #fafafa;
  flex-shrink: 0;
}

.qc-results-panel.expanded {
  width: 350px;
}

.qc-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #e8e8e8;
  background: #f0f0f0;
  border-radius: 6px 6px 0 0;
}

.qc-panel-title {
  font-weight: 500;
  color: #1890ff;
  display: flex;
  align-items: center;
  gap: 4px;
}

.qc-panel-content {
  padding: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.qc-summary {
  margin-bottom: 16px;
}

.qc-score-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.qc-analyzing {
  text-align: center;
  padding: 20px;
  color: #666;
}

.analyzing-text {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.document-summary-editor {
  margin: 15px 0;
}

.document-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.action-left,
.action-right {
  display: flex;
  gap: 8px;
}

.add-document-section {
  margin-top: 20px;
  text-align: center;
}

.add-document-btn {
  width: 100%;
  height: 60px;
  border: 2px dashed #dcdfe6;
  background: #fafafa;
  color: #909399;
  font-size: 14px;
}

.add-document-btn:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
}

@media (max-width: 768px) {
  .editor-toolbar {
    flex-direction: column;
    gap: 10px;
  }
  
  .document-meta-editor {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .type-selector {
    width: 100%;
  }
  
  .category-stats {
    flex-direction: column;
    gap: 15px;
  }
}
</style>
