<template>
  <div class="medical-record-detail-new">
    <!-- 加载状态 -->
    <div
      v-if="loading"
      class="loading-container"
    >
      <a-spin
        size="large"
        tip="加载中..."
      >
        <div class="loading-placeholder" />
      </a-spin>
    </div>

    <!-- 错误状态 -->
    <div
      v-else-if="error"
      class="error-container"
    >
      <a-card>
        <a-result
          status="error"
          :title="error"
          sub-title="请检查记录ID是否正确，或稍后重试"
        >
          <template #extra>
            <a-button
              type="primary"
              @click="loadData"
            >
              重新加载
            </a-button>
            <a-button @click="goBack">
              返回
            </a-button>
          </template>
        </a-result>
      </a-card>
    </div>

    <!-- 三栏布局 -->
    <LayoutShell
      v-else
      v-model:nav-width="navWidth"
      v-model:aside-width="asideWidth"
      v-model:collapsed-nav="collapsedNav"
      v-model:collapsed-aside="collapsedAside"
      :patient="patient"
      @back="goBack"
    >
      <!-- 左侧导航树 -->
      <template #nav>
        <NavTree
          :tree-data="treeData"
          :selected-key="selectedDocId"
          @select="handleDocumentSelect"
        />
      </template>

      <!-- 工具栏 -->
      <template #toolbar>
        <Toolbar
          v-model:summary="summaryMode"
          :is-editing="isEditing"
          :can-edit="!!currentDocument"
          :can-delete="!!currentDocument"
          :saving="saving"
          @font-up="increaseFontSize"
          @font-down="decreaseFontSize"
          @toggle-summary="toggleSummaryMode"
          @search="handleContentSearch"
          @copy-link="handleCopyLink"
          @fullscreen="handleFullscreen"
          @print="handlePrint"
          @open-compare="handleOpenCompare"
          @start-edit="startEdit"
          @save-edit="saveEdit"
          @cancel-edit="cancelEdit"
          @create-document="showCreateDocumentModal"
          @delete-document="showDeleteDocumentModal"
        />
      </template>

      <!-- 主要内容区域 -->
      <template #content>
        <div
          class="content-area"
          :style="contentStyle"
        >
          <!-- 文档标题和元信息 -->
          <div
            v-if="currentDocument"
            class="document-header"
          >
            <h2 class="document-title">
              {{ currentDocument.title }}
            </h2>
            <div class="document-meta">
              <a-tag color="blue">
                {{ currentDocument.category || '未分类' }}
              </a-tag>
              <a-tag
                v-if="currentDocument.ai_classified"
                color="green"
              >
                AI分类 {{ Math.round((currentDocument.classification_confidence || 0) * 100) }}%
              </a-tag>
              <span class="document-time">
                {{ formatDateTime(currentDocument.created_at) }}
              </span>
            </div>
          </div>

          <!-- 文档内容 -->
          <div
            ref="contentRef"
            class="document-content"
          >
            <div v-if="currentDocument">
              <!-- 编辑模式 -->
              <div
                v-if="isEditing"
                class="edit-mode"
              >
                <DocumentEditor
                  :content="editingContent"
                  :auto-save="false"
                  @update:content="editingContent = $event"
                  @save="saveEdit"
                />
              </div>

              <!-- 只读模式 -->
              <div
                v-else
                class="read-mode"
              >
                <div v-if="summaryMode && currentDocument.summary">
                  <h4>摘要</h4>
                  <div
                    class="content-text"
                    v-html="highlightedContent(currentDocument.summary)"
                  />
                </div>
                <div v-else>
                  <div
                    class="content-text"
                    v-html="highlightedContent(displayContent)"
                  />
                </div>
              </div>
            </div>
            <div
              v-else
              class="no-document"
            >
              <a-empty
                description="请从左侧选择要查看的文档"
                :image="Empty.PRESENTED_IMAGE_SIMPLE"
              />
            </div>
          </div>
        </div>
      </template>

      <!-- 右侧上下文信息 -->
      <template #aside>
        <ContextAside
          :patient="patient"
          :docs="allDocuments"
        />
      </template>
    </LayoutShell>

    <!-- 文档管理模态框 -->
    <CreateDocumentModal
      v-model:visible="createModalVisible"
      :record-id="recordId"
      :document-types="documentTypes"
      @success="handleDocumentCreated"
    />

    <DeleteDocumentModal
      v-model:visible="deleteModalVisible"
      :document-id="selectedDocId"
      :document-title="currentDocument?.title || ''"
      :document-type="currentDocument?.category || ''"
      @success="handleDocumentDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Empty } from 'ant-design-vue'

// 导入组件
import LayoutShell from '@/mr/components/LayoutShell.vue'
import NavTree from '@/mr/components/NavTree.vue'
import Toolbar from '@/mr/components/Toolbar.vue'
import ContextAside from '@/mr/components/ContextAside.vue'
import DocumentEditor from '@/mr/components/DocumentEditor.vue'
import CreateDocumentModal from '@/mr/components/CreateDocumentModal.vue'
import DeleteDocumentModal from '@/mr/components/DeleteDocumentModal.vue'

// 导入API和工具函数
import {
  fetchPatientById,
  fetchDocumentsByRecord,
  buildTreeData,
  extractDocuments,
  findDocumentById,
  generateSummary,
  highlightSearchKeyword,
  getDocumentFullContent,
  updateDocument,
  getDocumentTypes,
  createDocument,
  deleteDocument,
  config,
  type Patient,
  type Document,
  type DocumentsResponse,
  type DocumentCategory,
  type TreeNode
} from '@/mr/data/api'

type DocumentView = Document & { category?: string }

const route = useRoute()
const router = useRouter()

// 响应式状态
const loading = ref(true)
const error = ref('')
const patient = ref<Patient | null>(null)
const documentsResponse = ref<DocumentsResponse | null>(null)
const selectedDocId = ref('')

// 布局状态
const navWidth = ref(280)
const asideWidth = ref(320)
const collapsedNav = ref(false)
const collapsedAside = ref(false)

// 显示状态
const summaryMode = ref(false)
const fontSize = ref(14)
const searchKeyword = ref('')

// 编辑状态
const isEditing = ref(false)
const editingContent = ref('')
const saving = ref(false)
const originalContent = ref('')

// 文档管理状态
const createModalVisible = ref(false)
const deleteModalVisible = ref(false)
const documentTypes = ref<DocumentCategory[]>([])

// 内容引用
const contentRef = ref<HTMLElement>()

// 计算属性
const recordId = computed(() => route.params.id as string)

const treeData = computed<TreeNode[]>(() => {
  if (!documentsResponse.value) return []
  return buildTreeData(documentsResponse.value)
})

const allDocuments = computed<DocumentView[]>(() => {
  if (!documentsResponse.value) return []
  return extractDocuments(documentsResponse.value) as DocumentView[]
})

const currentDocument = computed<DocumentView | null>(() => {
  if (!documentsResponse.value || !selectedDocId.value) return null
  return findDocumentById(documentsResponse.value, selectedDocId.value) as DocumentView | null
})

const displayContent = computed(() => {
  if (!currentDocument.value) return ''

  // 获取原始文本
  const originalText = patient.value?.raw_text || ''

  if (summaryMode.value) {
    return currentDocument.value.summary ||
           generateSummary(getDocumentFullContent(currentDocument.value, originalText), config.DEFAULT_SUMMARY_LENGTH)
  }

  // 使用完整内容而不是摘要
  return getDocumentFullContent(currentDocument.value, originalText)
})

const contentStyle = computed(() => ({
  fontSize: fontSize.value + 'px',
  lineHeight: Math.max(1.4, fontSize.value / 10)
}))

// 方法
const loadData = async () => {
  loading.value = true
  error.value = ''

  try {
    // 并行加载患者信息和文档
    const [patientData, documentsData] = await Promise.all([
      fetchPatientById(recordId.value),
      fetchDocumentsByRecord(recordId.value)
    ])

    patient.value = patientData
    documentsResponse.value = documentsData

    console.log('数据加载成功:', { patient: patientData, documents: documentsData })

    // 如果URL中有docId参数，选中对应文档
    const urlDocId = route.query.docId as string
    if (urlDocId && documentsData.categories.some(cat =>
      cat.documents.some(doc => doc.id === urlDocId)
    )) {
      selectedDocId.value = urlDocId
    } else if (documentsData.categories.length > 0 && documentsData.categories[0].documents.length > 0) {
      // 默认选中第一个文档
      selectedDocId.value = documentsData.categories[0].documents[0].id
    }

  } catch (err) {
    console.error('加载数据失败:', err)
    error.value = err instanceof Error ? err.message : '加载失败'
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  console.log('goBack called')
  // 直接跳转到医疗记录列表页面
  router.push('/dashboard/medical-records')
}

const handleDocumentSelect = ({ docId }: { docId: string }) => {
  selectedDocId.value = docId

  // 更新URL参数
  router.replace({
    name: route.name!,
    params: route.params,
    query: { ...route.query, docId }
  })
}

const toggleSummaryMode = () => {
  summaryMode.value = !summaryMode.value
  localStorage.setItem(config.STORAGE_KEYS.SUMMARY_MODE, String(summaryMode.value))
}

const increaseFontSize = () => {
  fontSize.value = Math.min(24, fontSize.value + 1)
  localStorage.setItem(config.STORAGE_KEYS.FONT_SIZE, String(fontSize.value))
}

const decreaseFontSize = () => {
  fontSize.value = Math.max(12, fontSize.value - 1)
  localStorage.setItem(config.STORAGE_KEYS.FONT_SIZE, String(fontSize.value))
}

const handleContentSearch = (keyword: string, results: Element[]) => {
  searchKeyword.value = keyword

  if (results.length > 0) {
    // 滚动到第一个搜索结果
    nextTick(() => {
      const firstResult = results[0]
      firstResult.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      })
    })
  }
}

const highlightedContent = (content: string) => {
  if (!searchKeyword.value) return content
  return highlightSearchKeyword(content, searchKeyword.value)
}

const handleCopyLink = () => {
  message.success('链接已复制到剪贴板')
}

const handleFullscreen = () => {
  message.info('全屏模式切换')
}

const handlePrint = () => {
  message.info('打印功能')
}

const handleOpenCompare = () => {
  message.info('对比视图功能开发中')
}

// 编辑功能
const startEdit = () => {
  if (!currentDocument.value) {
    message.error('请先选择要编辑的文档')
    return
  }

  // 获取完整内容作为编辑内容
  const originalText = patient.value?.raw_text || ''
  const fullContent = getDocumentFullContent(currentDocument.value, originalText)

  originalContent.value = fullContent
  editingContent.value = fullContent
  isEditing.value = true

  message.info('已进入编辑模式')
}

const saveEdit = async () => {
  if (!currentDocument.value) {
    message.error('没有选中的文档')
    return
  }

  if (editingContent.value === originalContent.value) {
    message.info('内容未发生变化')
    return
  }

  saving.value = true

  try {
    // 调用后端API保存文档
    await updateDocument(currentDocument.value.id, editingContent.value)

    // 更新本地数据
    if (currentDocument.value) {
      currentDocument.value.content = editingContent.value
      originalContent.value = editingContent.value
    }

    isEditing.value = false
    message.success('文档保存成功')

    // 重新加载数据以确保一致性
    await loadData()

  } catch (error) {
    console.error('保存文档失败:', error)
    message.error(`保存失败: ${error instanceof Error ? error.message : '未知错误'}`)
  } finally {
    saving.value = false
  }
}

const cancelEdit = () => {
  if (editingContent.value !== originalContent.value) {
    // 确认取消编辑
    const confirmed = confirm('您有未保存的更改，确定要取消编辑吗？')
    if (!confirmed) return
  }

  editingContent.value = originalContent.value
  isEditing.value = false
  message.info('已取消编辑')
}

// 文档管理功能
const showCreateDocumentModal = () => {
  createModalVisible.value = true
}

const showDeleteDocumentModal = () => {
  if (!currentDocument.value) {
    message.warning('请先选择要删除的文档')
    return
  }
  deleteModalVisible.value = true
}

const handleDocumentCreated = async (document: unknown) => {
  try {
    message.success('文档创建成功')

    // 重新加载数据
    await loadData()

    // 自动选中新创建的文档
    if (typeof document === 'object' && document !== null && 'id' in document) {
      selectedDocId.value = String((document as { id: unknown }).id)
    }

  } catch (error) {
    console.error('处理文档创建后续操作失败:', error)
  }
}

const handleDocumentDeleted = async (result: unknown) => {
  try {
    const operationType = (
      typeof result === 'object' &&
      result !== null &&
      'deleteType' in result &&
      (result as { deleteType?: string }).deleteType === 'hard'
    ) ? '永久删除' : '删除'
    message.success(`文档${operationType}成功`)

    // 清除当前选中的文档
    selectedDocId.value = ''

    // 重新加载数据
    await loadData()

    // 如果有其他文档，自动选中第一个
    if (documentsResponse.value?.categories?.length) {
      for (const category of documentsResponse.value.categories) {
        if (category.documents?.length) {
          selectedDocId.value = category.documents[0].id
          break
        }
      }
    }

  } catch (error) {
    console.error('处理文档删除后续操作失败:', error)
  }
}

const loadDocumentTypes = async () => {
  try {
    documentTypes.value = await getDocumentTypes()
  } catch (error) {
    console.error('加载文档类型失败:', error)
    message.error('加载文档类型失败')
  }
}

const formatDateTime = (dateStr: string) => {
  if (!dateStr) return ''
  try {
    return new Date(dateStr).toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

// 初始化布局状态
const initializeLayout = () => {
  // 从localStorage恢复布局状态
  const savedNavWidth = localStorage.getItem(config.STORAGE_KEYS.NAV_WIDTH)
  const savedAsideWidth = localStorage.getItem(config.STORAGE_KEYS.ASIDE_WIDTH)
  const savedCollapsedNav = localStorage.getItem(config.STORAGE_KEYS.COLLAPSED_NAV)
  const savedCollapsedAside = localStorage.getItem(config.STORAGE_KEYS.COLLAPSED_ASIDE)
  const savedFontSize = localStorage.getItem(config.STORAGE_KEYS.FONT_SIZE)
  const savedSummaryMode = localStorage.getItem(config.STORAGE_KEYS.SUMMARY_MODE)

  if (savedNavWidth) navWidth.value = parseInt(savedNavWidth)
  if (savedAsideWidth) asideWidth.value = parseInt(savedAsideWidth)
  if (savedCollapsedNav) collapsedNav.value = savedCollapsedNav === 'true'
  if (savedCollapsedAside) collapsedAside.value = savedCollapsedAside === 'true'
  if (savedFontSize) fontSize.value = parseInt(savedFontSize)
  if (savedSummaryMode) summaryMode.value = savedSummaryMode === 'true'
}

// 监听布局变化并保存
watch([navWidth, asideWidth, collapsedNav, collapsedAside], () => {
  localStorage.setItem(config.STORAGE_KEYS.NAV_WIDTH, String(navWidth.value))
  localStorage.setItem(config.STORAGE_KEYS.ASIDE_WIDTH, String(asideWidth.value))
  localStorage.setItem(config.STORAGE_KEYS.COLLAPSED_NAV, String(collapsedNav.value))
  localStorage.setItem(config.STORAGE_KEYS.COLLAPSED_ASIDE, String(collapsedAside.value))
})

// 组件挂载
onMounted(() => {
  initializeLayout()
  loadData()
  loadDocumentTypes()
})
</script>

<style scoped>
.medical-record-detail-new {
  height: 100vh;
  overflow: hidden;
}

.loading-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-placeholder {
  width: 400px;
  height: 300px;
}

.error-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.content-area {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
}

.document-header {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.document-title {
  margin: 0 0 12px 0;
  font-size: 24px;
  font-weight: 600;
  color: #262626;
}

.document-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.document-time {
  color: #666;
  font-size: 14px;
}

.document-content {
  flex: 1;
}

.content-text {
  line-height: 1.8;
  color: #262626;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.content-text :deep(mark) {
  background: #fff566;
  padding: 2px 4px;
  border-radius: 2px;
}

.no-document {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.edit-mode {
  height: calc(100vh - 200px);
}

.read-mode {
  min-height: 200px;
}

.no-document {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 打印样式 */
@media print {
  .medical-record-detail-new :deep(.layout-nav),
  .medical-record-detail-new :deep(.layout-aside),
  .medical-record-detail-new :deep(.layout-resizer),
  .medical-record-detail-new :deep(.layout-toolbar) {
    display: none !important;
  }

  .medical-record-detail-new :deep(.layout-content) {
    margin: 0 !important;
  }

  .content-area {
    padding: 0 !important;
  }
}
</style>
