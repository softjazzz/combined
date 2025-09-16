<template>
  <div class="document-category-view">
    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <a-skeleton :loading="true" active>
        <a-skeleton-paragraph :rows="5" />
      </a-skeleton>
    </div>

    <!-- 文档分类展示 -->
    <div v-else-if="documentData.categories.length > 0" class="categories-container">
      <!-- 统计概览 -->
      <div class="summary-card">
        <a-card :bordered="false" class="summary-header">
          <div class="summary-content">
            <div class="summary-item">
              <span class="summary-label">总文档数</span>
              <span class="summary-value">{{ documentData.total_documents }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">分类数</span>
              <span class="summary-value">{{ documentData.categories.length }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">AI分类</span>
              <span class="summary-value">{{ aiClassifiedCount }}</span>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 分类列表 -->
      <div class="categories-list">
        <a-collapse v-model:activeKey="activeCategories" accordion>
          <a-collapse-panel
            v-for="category in documentData.categories"
            :key="category.category_code"
            :header="getCategoryHeader(category)"
            class="category-item"
          >
            <!-- 分类标题 -->
            <template #header>
              <div class="category-header">
                <div class="category-info">
                  <span class="category-name">{{ category.category_name }}</span>
                  <a-tag color="blue" class="document-count">
                    {{ category.document_count }} 个文档
                  </a-tag>
                </div>
                <div class="category-types">
                  <a-tag
                    v-for="(typeInfo, typeCode) in getTypesForCategory(category.category_code)"
                    :key="typeCode"
                    size="small"
                    :color="getTypeTagColor(typeCode)"
                    class="type-tag"
                  >
                    {{ typeInfo.name }} ({{ typeInfo.count }})
                  </a-tag>
                </div>
              </div>
            </template>

            <!-- 分类内容 -->
            <div class="category-content">
              <!-- 适用规则展示 -->
              <div class="applicable-rules-section" v-if="getApplicableRules(category.category_code).length > 0">
                <h4 class="rules-title">
                  <ExperimentOutlined />
                  适用质控规则 ({{ getApplicableRules(category.category_code).length }}条)
                </h4>
                <div class="rules-grid">
                  <a-card
                    v-for="rule in getApplicableRules(category.category_code)"
                    :key="rule.rule_id"
                    size="small"
                    class="rule-card"
                    hoverable
                  >
                    <div class="rule-header">
                      <span class="rule-name">{{ rule.name }}</span>
                      <div class="rule-tags">
                        <a-tag size="small" :color="getCategoryColor(rule.category)">
                          {{ getCategoryDisplayName(rule.category) }}
                        </a-tag>
                        <a-tag size="small" :color="getSeverityColor(rule.defect_level)">
                          {{ getSeverityDisplayName(rule.defect_level) }}
                        </a-tag>
                      </div>
                    </div>
                    <div class="rule-description">
                      {{ rule.description || '暂无描述' }}
                    </div>
                    <div class="rule-footer">
                      <span class="rule-score">扣分: {{ rule.score_deduction || 0 }}分</span>
                      <span class="rule-complexity">{{ rule.complexity || '中复杂度' }}</span>
                    </div>
                  </a-card>
                </div>
              </div>
              
              <!-- 文档列表 -->
              <div class="documents-section">
                <h4 class="documents-title" v-if="getApplicableRules(category.category_code).length > 0">
                  <FileTextOutlined />
                  文档列表 ({{ category.document_count }}个)
                </h4>
                <div class="documents-grid">
                <a-card
                  v-for="document in category.documents"
                  :key="document.id"
                  hoverable
                  class="document-card"
                  @click="handleDocumentClick(document)"
                >
                  <div class="document-header">
                    <div class="document-title">
                      <span class="title-text">{{ document.title }}</span>
                      <div class="document-tags">
                        <a-tag
                          :color="document.ai_classified ? 'green' : 'default'"
                          class="ai-tag"
                        >
                          {{ document.ai_classified ? 'AI分类' : '手动' }}
                        </a-tag>
                        <!-- 质控状态标签 -->
                        <a-tag
                          v-if="document.qc_status"
                          :color="getQCStatusColor(document.qc_status)"
                          class="qc-status-tag"
                        >
                          <template #icon>
                            <CheckCircleOutlined v-if="document.qc_status === 'passed'" />
                            <ExclamationCircleOutlined v-else-if="document.qc_status === 'warning'" />
                            <CloseCircleOutlined v-else-if="document.qc_status === 'failed'" />
                            <ClockCircleOutlined v-else-if="document.qc_status === 'pending'" />
                            <LoadingOutlined v-else-if="document.qc_status === 'analyzing'" />
                          </template>
                          {{ getQCStatusText(document.qc_status) }}
                        </a-tag>
                        <!-- 质控问题数量提示 -->
                        <a-tag
                          v-if="document.qc_issues_count > 0"
                          color="orange"
                          class="qc-issues-tag"
                        >
                          {{ document.qc_issues_count }}个问题
                        </a-tag>
                      </div>
                    </div>
                    <div class="document-meta">
                      <span class="document-type">{{ getDocumentTypeName(document) }}</span>
                      <span v-if="document.classification_confidence > 0" class="confidence">
                        分类置信度: {{ Math.round(document.classification_confidence * 100) }}%
                      </span>
                      <!-- 质控评分 -->
                      <span v-if="document.qc_score !== null && document.qc_score !== undefined" class="qc-score">
                        <a-tooltip :title="`质控评分: ${document.qc_score}/100分`">
                          <span :class="getQCScoreClass(document.qc_score)">
                            质控: {{ document.qc_score }}分
                          </span>
                        </a-tooltip>
                      </span>
                      <!-- 最后质控分析时间 -->
                      <span v-if="document.qc_last_analyzed" class="qc-last-analyzed">
                        <a-tooltip :title="`最后质控时间: ${formatDateTime(document.qc_last_analyzed)}`">
                          <ClockCircleOutlined />
                          {{ formatRelativeTime(document.qc_last_analyzed) }}
                        </a-tooltip>
                      </span>
                    </div>
                  </div>

                  <div class="document-content">
                    <p class="content-preview">{{ document.content_preview }}</p>
                  </div>

                  <div class="document-footer">
                    <div class="document-status">
                      <a-tag
                        :color="getStatusTagColor(document.qc_status)"
                      >
                        {{ getStatusText(document.qc_status) }}
                      </a-tag>
                      <span v-if="document.qc_score" class="qc-score">
                        质控分: {{ document.qc_score }}
                      </span>
                    </div>
                    <div class="document-actions">
                      <a-button
                        size="small"
                        type="primary"
                        @click.stop="editDocument(document)"
                      >
                        编辑
                      </a-button>
                      <a-button
                        size="small"
                        @click.stop="viewDocument(document)"
                      >
                        查看
                      </a-button>
                      <a-button
                        size="small"
                        type="default"
                        :loading="analyzingDocuments.has(document.id)"
                        @click.stop="analyzeDocumentQC(document)"
                      >
                        <template #icon><ExperimentOutlined /></template>
                        {{ analyzingDocuments.has(document.id) ? '分析中' : '质控分析' }}
                      </a-button>
                      <a-button
                        size="small"
                        type="link"
                        @click.stop="viewQCResults(document)"
                        v-if="document.qc_status && document.qc_status !== 'pending'"
                      >
                        <template #icon><BarChartOutlined /></template>
                        查看结果
                      </a-button>
                    </div>
                  </div>
                </a-card>
              </div>
              </div>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <a-empty description="暂无文档数据" />
    </div>

    <!-- 文档详情对话框 -->
    <a-modal
      v-model:open="documentDialogVisible"
      :title="selectedDocument?.title"
      width="80%"
      class="document-dialog"
      :footer="null"
    >
      <div v-if="selectedDocument" class="document-detail">
        <div class="document-info">
          <a-descriptions :column="2" bordered>
            <a-descriptions-item label="文档类型">
              {{ getDocumentTypeName(selectedDocument) }}
            </a-descriptions-item>
            <a-descriptions-item label="AI分类">
              <a-tag :color="selectedDocument.ai_classified ? 'green' : 'default'">
                {{ selectedDocument.ai_classified ? '是' : '否' }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="置信度" v-if="selectedDocument.classification_confidence > 0">
              {{ Math.round(selectedDocument.classification_confidence * 100) }}%
            </a-descriptions-item>
            <a-descriptions-item label="质控状态">
              <a-tag :color="getStatusTagColor(selectedDocument.qc_status)">
                {{ getStatusText(selectedDocument.qc_status) }}
              </a-tag>
            </a-descriptions-item>
          </a-descriptions>
        </div>
        <div class="document-content-full">
          <h4>文档内容</h4>
          <div class="content-text">{{ getFullContent(selectedDocument) }}</div>
        </div>
      </div>
    </a-modal>

    <!-- 质控分析进度 -->
    <a-modal
      v-model:open="showAnalysisProgress"
      title="质控分析进度"
      width="800px"
      :footer="null"
      centered
    >
      <AnalysisProgress
        v-if="showAnalysisProgress && currentAnalysisDocument"
        :record-id="currentAnalysisDocument.id"
        :auto-start="true"
        @analysis-completed="onAnalysisComplete"
        @analysis-failed="onAnalysisError"
      />
    </a-modal>

    <!-- 质控结果展示 -->
    <a-modal
      v-model:open="showQCResults"
      title="质控分析结果"
      width="1000px"
      :footer="null"
      centered
    >
      <QCResultDisplay
        v-if="showQCResults && currentQCDocument && qcAnalysisResult"
        :result="qcAnalysisResult"
        @highlight-issue="handleHighlightIssue"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ExperimentOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import AnalysisProgress from './qc/AnalysisProgress.vue'
import QCResultDisplay from './qc/QCResultDisplay.vue'

const props = defineProps({
  recordId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['document-edit', 'document-view'])

// 响应式数据
const loading = ref(false)
const documentData = ref({
  record_id: '',
  categories: [],
  total_documents: 0,
  classification_summary: {}
})
const originalRecordContent = ref('')
const activeCategories = ref([])
const documentDialogVisible = ref(false)
const selectedDocument = ref(null)
const analyzingDocuments = ref(new Set()) // 正在分析的文档ID集合

// 质控分析相关状态
const showAnalysisProgress = ref(false)
const currentAnalysisDocument = ref(null)
const showQCResults = ref(false)
const currentQCDocument = ref(null)
const qcAnalysisResult = ref(null)

// 质控规则相关数据
const qcRules = ref([])
const rulesByDocumentType = ref({})

// 计算属性
const aiClassifiedCount = computed(() => {
  let count = 0
  documentData.value.categories.forEach(category => {
    category.documents.forEach(doc => {
      if (doc.ai_classified) count++
    })
  })
  return count
})

// 方法
const loadQCRules = async () => {
  try {
    const baseURL = import.meta.env.VITE_API_BASE_URL || ''
    const response = await fetch(`${baseURL}/api/qc/sichuan/rules?grouped=true`)
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    const data = await response.json()
    rulesByDocumentType.value = data.rules_by_document_type || {}
    
    // 展平所有规则到 qcRules 数组
    qcRules.value = []
    Object.values(rulesByDocumentType.value).forEach(rules => {
      qcRules.value.push(...rules)
    })
    
  } catch (error) {
    console.error('加载质控规则失败:', error)
    // 不显示错误消息，静默失败
  }
}

const loadDocuments = async () => {
  if (!props.recordId) return

  loading.value = true
  try {
    // 使用相对路径，交由 Vite 代理转发，避免硬编码 IP/端口
    const baseURL = import.meta.env.VITE_API_BASE_URL || ''

    // 并行获取文档分类数据和原始记录内容
    const [documentsResponse, recordResponse] = await Promise.all([
      fetch(`${baseURL}/api/medical-records/${props.recordId}/documents`),
      fetch(`${baseURL}/api/medical-records/${props.recordId}`)
    ])
    
    // 同时加载质控规则
    await loadQCRules()

    if (!documentsResponse.ok) {
      throw new Error(`HTTP error! status: ${documentsResponse.status}`)
    }

    if (!recordResponse.ok) {
      throw new Error(`HTTP error! status: ${recordResponse.status}`)
    }

    const documentsData = await documentsResponse.json()
    const recordData = await recordResponse.json()

    // 对分类进行排序
    const sortedCategories = sortDocumentCategories(documentsData.categories)
    documentsData.categories = sortedCategories

    documentData.value = documentsData
    originalRecordContent.value = recordData.content || ''

    // 默认展开第一个分类
    if (documentsData.categories.length > 0) {
      activeCategories.value = [documentsData.categories[0].category_code]
    }

  } catch (error) {
    console.error('加载文档失败:', error)
    message.error('加载文档失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 文档分类排序函数
const sortDocumentCategories = (categories) => {
  // 定义分类优先级顺序
  const categoryPriority = {
    'progress_note': 1,        // 病程记录 - 最高优先级
    'operation_record': 2,     // 手术记录 - 中等优先级
    'examination_report': 3    // 检查报告 - 最低优先级
  }

  return [...categories].sort((a, b) => {
    const priorityA = categoryPriority[a.category_code] || 999 // 未定义的分类放在最后
    const priorityB = categoryPriority[b.category_code] || 999

    // 按优先级升序排序（数字越小优先级越高）
    if (priorityA !== priorityB) {
      return priorityA - priorityB
    }

    // 如果优先级相同，按分类名称排序
    return a.category_name.localeCompare(b.category_name, 'zh-CN')
  })
}

const getCategoryHeader = (category) => {
  return `${category.category_name} (${category.document_count})`
}

const getTypesForCategory = (categoryCode) => {
  return documentData.value.classification_summary[categoryCode]?.types || {}
}

const getTypeTagColor = (typeCode) => {
  const typeMap = {
    'first_progress_note': 'green',
    'daily_progress_note': 'green',
    'attending_progress': 'orange',
    'imaging_report': 'blue',
    'laboratory_test': 'blue',
    'preoperative_summary': 'red',
    'operation_record': 'red'
  }
  return typeMap[typeCode] || 'default'
}

// 获取适用于某个文档分类的质控规则
const getApplicableRules = (categoryCode) => {
  // 映射文档分类代码到中文名称（6个标准分类）
  const categoryMapping = {
    'admission_record': '入院记录',
    'progress_note': '病程记录',
    'discharge_record': '出院记录',
    'operation_record': '手术相关记录',
    'examination_report': '辅助检查',
    'consent_form': '知情同意书'
  }
  
  const chineseName = categoryMapping[categoryCode]
  if (!chineseName) return []
  
  return rulesByDocumentType.value[chineseName] || []
}

// 获取分类颜色
const getCategoryColor = (category) => {
  const categoryColors = {
    'completeness': 'blue',
    'accuracy': 'green', 
    'timeliness': 'orange',
    'consistency': 'purple',
    'compliance': 'red'
  }
  return categoryColors[category] || 'default'
}

// 获取分类显示名称
const getCategoryDisplayName = (category) => {
  const categoryNames = {
    'completeness': '完整性',
    'accuracy': '准确性',
    'timeliness': '时效性', 
    'consistency': '一致性',
    'compliance': '合规性'
  }
  return categoryNames[category] || category
}

// 获取严重程度颜色
const getSeverityColor = (severity) => {
  const severityColors = {
    'critical': 'red',
    'major': 'orange',
    'minor': 'blue'
  }
  return severityColors[severity] || 'default'
}

// 获取严重程度显示名称
const getSeverityDisplayName = (severity) => {
  const severityNames = {
    'critical': '严重缺陷',
    'major': '重要缺陷', 
    'minor': '一般缺陷'
  }
  return severityNames[severity] || severity
}

// 兼容缺失的 type_info 或 type_name 字段
const getDocumentTypeName = (doc) => {
  try {
    return doc?.type_info?.type_name || doc?.type_name || '未分类'
  } catch {
    return '未分类'
  }
}

const getStatusTagColor = (status) => {
  const statusMap = {
    // 原有状态
    'pending': 'default',
    'approved': 'green',
    'rejected': 'red',
    'reviewing': 'orange',
    // 概念验证质控状态
    'passed': 'green',
    'warning': 'orange',
    'failed': 'red'
  }
  return statusMap[status] || 'default'
}

// 质控状态相关方法
const getQCStatusColor = (status) => {
  const statusColors = {
    'passed': 'green',
    'warning': 'orange',
    'failed': 'red',
    'pending': 'default',
    'analyzing': 'blue'
  }
  return statusColors[status] || 'default'
}

const getQCStatusText = (status) => {
  const statusTexts = {
    'passed': '质控通过',
    'warning': '质控警告',
    'failed': '质控失败',
    'pending': '待质控',
    'analyzing': '分析中'
  }
  return statusTexts[status] || '未知状态'
}

// 质控评分样式类
const getQCScoreClass = (score) => {
  if (score >= 90) return 'qc-score-excellent'
  if (score >= 80) return 'qc-score-good'
  if (score >= 70) return 'qc-score-fair'
  if (score >= 60) return 'qc-score-poor'
  return 'qc-score-fail'
}

// 时间格式化方法
const formatDateTime = (dateTime) => {
  if (!dateTime) return ''
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatRelativeTime = (dateTime) => {
  if (!dateTime) return ''
  const now = new Date()
  const date = new Date(dateTime)
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  return formatDateTime(dateTime)
}

const getStatusText = (status) => {
  const statusMap = {
    // 原有状态
    'pending': '待审核',
    'approved': '已通过',
    'rejected': '已拒绝',
    'reviewing': '审核中',
    // 概念验证质控状态
    'passed': '质控通过',
    'warning': '质控警告',
    'failed': '质控失败'
  }
  return statusMap[status] || '未知'
}

const handleDocumentClick = (document) => {
  // 创建一个包含完整内容的文档副本
  selectedDocument.value = {
    ...document,
    content: getFullContent(document)
  }
  documentDialogVisible.value = true
}

const editDocument = (document) => {
  emit('document-edit', document)
}

const viewDocument = (document) => {
  // 创建一个包含完整内容的文档副本
  const documentWithFullContent = {
    ...document,
    content: getFullContent(document)
  }
  emit('document-view', documentWithFullContent)
}

// 获取文档的完整内容
const getFullContent = (document) => {
  // 1) 优先：使用新的 fullContent 字段（来自确定性切片）
  if (document.position_info?.fullContent && document.position_info.fullContent.trim()) {
    return document.position_info.fullContent
  }

  // 2) 次选：按精确的指针切片（startIndex/endIndex）
  const source = originalRecordContent.value || ''
  if (source && document.position_info) {
    const si = document.position_info.startIndex
    const ei = document.position_info.endIndex
    if (typeof si === 'number' && typeof ei === 'number' && ei > si && si >= 0 && ei <= source.length) {
      return source.slice(si, ei)
    }
  }

  // 3) 备用方案：基于文档标题在原始文本中搜索完整内容
  if (source && document.title) {
    const extractedContent = extractContentByTitle(source, document.title)
    if (extractedContent && extractedContent.length > (document.content || '').length) {
      return extractedContent
    }
  }

  // 4) 兜底：使用现有内容
  return document.content || document.content_preview || '暂无内容'
}

// 根据文档标题从原始文本中提取完整内容
const extractContentByTitle = (source, title) => {
  try {
    // 查找标题在原始文本中的位置
    const titleIndex = source.indexOf(title)
    if (titleIndex === -1) {
      return null
    }

    // 从标题开始，查找内容的结束位置
    let startIndex = titleIndex
    let endIndex = source.length

    // 查找下一个文档标题或特定的结束标记
    const nextTitlePatterns = [
      /\n\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+[^\n]+记录/g,  // 下一个带时间的记录
    ]

    // 查找最近的下一个记录标题
    for (const pattern of nextTitlePatterns) {
      pattern.lastIndex = startIndex + title.length  // 从标题后开始搜索
      const match = pattern.exec(source)
      if (match && match.index < endIndex) {
        endIndex = match.index
      }
    }

    // 提取内容
    let content = source.slice(startIndex, endIndex).trim()

    // 清理内容：移除页面分隔符和医院标题
    content = cleanMedicalRecordContent(content)

    return content.trim()
  } catch (error) {
    console.error('提取文档内容失败:', error)
    return null
  }
}

// 清理医疗记录内容
const cleanMedicalRecordContent = (content) => {
  // 移除页面标记
  content = content.replace(/\n={3,}\s*第\(\d+\)页\s*={3,}/g, '')

  // 移除医院标题和页面信息块
  content = content.replace(/\n\s*泸县人民医院\s*\n病\s*程\s*记\s*录\s*\n科室：[^\n]*\n姓名：[^\n]*\n年龄：[^\n]*\n性别：[^\n]*\n床号：[^\n]*\n住院号:[^\n]*\n第\(\d+\)页/g, '')

  // 移除单独的分页标记
  content = content.replace(/\n\s*=+\s*第\d+页\s*=+\s*\n/g, '\n')

  // 移除多余的空行
  content = content.replace(/\n{3,}/g, '\n\n')

  // 移除开头和结尾的空白
  return content.trim()
}

// 质控分析方法
const analyzeDocumentQC = async (document) => {
  try {
    // 设置当前分析文档并显示进度
    currentAnalysisDocument.value = document
    showAnalysisProgress.value = true

    // 添加到正在分析的集合中
    analyzingDocuments.value.add(document.id)

  } catch (error) {
    message.destroy()
    console.error('质控分析失败:', error)
    message.error(`质控分析失败: ${error.message}`)
  } finally {
    // 从正在分析的集合中移除
    analyzingDocuments.value.delete(document.id)
  }
}

// 查看质控结果
const viewQCResults = (document) => {
  currentQCDocument.value = document
  showQCResults.value = true
}

// 质控分析完成回调
const onAnalysisComplete = (result) => {
  try {
    // 更新文档的质控状态
    const updatedDocument = {
      ...currentAnalysisDocument.value,
      qc_status: result.qc_status,
      qc_score: result.qc_score,
      qc_last_analyzed: result.analysis_time
    }

    // 在documentData中更新对应的文档
    documentData.value.categories.forEach(category => {
      const docIndex = category.documents.findIndex(d => d.id === currentAnalysisDocument.value.id)
      if (docIndex !== -1) {
        category.documents[docIndex] = updatedDocument
      }
    })

    // 显示分析结果
    const statusText = getStatusText(result.qc_status)
    const statusIcon = result.qc_status === 'passed' ? '✅' :
                      result.qc_status === 'warning' ? '⚠️' : '❌'

    message.success(
      `${statusIcon} 质控分析完成！状态: ${statusText}，评分: ${result.qc_score}分`,
      3
    )

  } finally {
    // 从正在分析的集合中移除
    analyzingDocuments.value.delete(currentAnalysisDocument.value.id)
  }
}

// 质控分析错误回调
const onAnalysisError = (error) => {
  console.error('质控分析失败:', error)
  message.error(`质控分析失败: ${error.message}`)

  // 从正在分析的集合中移除
  if (currentAnalysisDocument.value) {
    analyzingDocuments.value.delete(currentAnalysisDocument.value.id)
  }
}

// 查看结果回调
const onViewResults = (result) => {
  if (currentAnalysisDocument.value) {
    viewQCResults(currentAnalysisDocument.value)
  }
}

// 高亮问题处理
const handleHighlightIssue = (issue) => {
  console.log('高亮问题:', issue)
  // 这里可以添加高亮逻辑
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
.document-category-view {
  padding: 20px;
}

.loading-container {
  padding: 20px;
}

.summary-card {
  margin-bottom: 20px;
}

.summary-header {
  border: none;
}

.summary-content {
  display: flex;
  justify-content: space-around;
  align-items: center;
}

.summary-item {
  text-align: center;
}

.summary-label {
  display: block;
  font-size: 14px;
  color: #666;
  margin-bottom: 5px;
}

.summary-value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.categories-list {
  margin-top: 20px;
}

.category-item {
  margin-bottom: 10px;
}

.category-header {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-right: 20px;
}

.category-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-name {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.document-count {
  margin-left: 10px;
}

.category-types {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.type-tag {
  margin: 2px;
}

.category-content {
  padding: 20px 0;
}

.documents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
}

.document-card {
  cursor: pointer;
  transition: all 0.3s ease;
}

.document-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.document-header {
  margin-bottom: 12px;
}

.document-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.title-text {
  font-weight: bold;
  color: #303133;
  font-size: 16px;
}

.ai-tag {
  margin-left: 8px;
}

.document-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

.document-type {
  font-weight: 500;
}

.confidence {
  color: #67c23a;
}

/* 质控相关样式 */
.document-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.qc-status-tag {
  display: flex;
  align-items: center;
  gap: 2px;
}

.qc-issues-tag {
  font-weight: 500;
}

.qc-score {
  font-weight: 500;
  margin-left: 8px;
}

.qc-score-excellent {
  color: #52c41a;
}

.qc-score-good {
  color: #1890ff;
}

.qc-score-fair {
  color: #faad14;
}

.qc-score-poor {
  color: #fa8c16;
}

.qc-score-fail {
  color: #f5222d;
}

.qc-last-analyzed {
  color: #8c8c8c;
  font-size: 11px;
  margin-left: 8px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.document-content {
  margin: 12px 0;
}

.content-preview {
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.document-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.document-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.qc-score {
  font-size: 12px;
  color: #67c23a;
  font-weight: 500;
}

.document-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  padding: 60px 20px;
  text-align: center;
}

.document-dialog .document-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.document-info {
  margin-bottom: 20px;
}

.document-content-full h4 {
  margin-bottom: 10px;
  color: #303133;
}

.content-text {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  white-space: pre-wrap;
  line-height: 1.6;
  font-size: 14px;
  color: #606266;
  max-height: 400px;
  overflow-y: auto;
}

/* 质控规则相关样式 */
.applicable-rules-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.rules-title {
  margin: 0 0 16px 0;
  color: #495057;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.rule-card {
  border: 1px solid #dee2e6;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.rule-card:hover {
  border-color: #1890ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.rule-name {
  font-weight: 600;
  color: #212529;
  font-size: 14px;
  line-height: 1.4;
  flex: 1;
  margin-right: 8px;
}

.rule-tags {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}

.rule-description {
  color: #6c757d;
  font-size: 12px;
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.rule-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #868e96;
}

.rule-score {
  font-weight: 500;
  color: #dc3545;
}

.rule-complexity {
  color: #6c757d;
}

.documents-section {
  margin-top: 16px;
}

.documents-title {
  margin: 0 0 16px 0;
  color: #495057;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .documents-grid {
    grid-template-columns: 1fr;
  }
  
  .rules-grid {
    grid-template-columns: 1fr;
  }
  
  .category-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .summary-content {
    flex-direction: column;
    gap: 20px;
  }
  
  .rule-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .rule-tags {
    flex-direction: row;
  }
}
</style>
