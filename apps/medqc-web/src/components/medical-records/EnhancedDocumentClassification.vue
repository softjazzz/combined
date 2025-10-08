<template>
  <div class="enhanced-document-classification">
    <!-- 分类概览卡片 -->
    <div class="info-card classification-overview">
      <div class="card-header">
        <FolderOpenOutlined class="header-icon" />
        <h3>文档分类</h3>
        <div class="header-actions">
          <a-tooltip :title="'隐藏侧栏'">
            <a-button type="text" size="small" @click="$emit('toggle-sidebar')">
              隐藏侧栏
            </a-button>
          </a-tooltip>
          <a-tooltip title="刷新分类">
            <a-button type="text" size="small" @click="refreshClassification">
              <ReloadOutlined />
            </a-button>
          </a-tooltip>
          <a-dropdown>
            <a-button type="text" size="small">
              <FilterOutlined />
            </a-button>
            <template #overlay>
              <a-menu @click="handleFilterChange">
                <a-menu-item key="all">
                  <CheckOutlined v-if="activeFilter === 'all'" />
                  全部文档
                </a-menu-item>
                <a-menu-item key="ai-classified">
                  <CheckOutlined v-if="activeFilter === 'ai-classified'" />
                  AI分类
                </a-menu-item>
                <a-menu-item key="manual">
                  <CheckOutlined v-if="activeFilter === 'manual'" />
                  手动分类
                </a-menu-item>
                <a-menu-item key="high-confidence">
                  <CheckOutlined v-if="activeFilter === 'high-confidence'" />
                  高置信度
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </div>
      <div class="card-content">
        <!-- 分类统计 -->
        <div class="classification-stats">
          <div class="stat-item">
            <div class="stat-number">{{ totalDocuments }}</div>
            <div class="stat-label">总文档数</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ classificationStats.aiClassified }}</div>
            <div class="stat-label">AI分类</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ classificationStats.categories }}</div>
            <div class="stat-label">分类类型</div>
          </div>
          <div class="stat-item">
            <div class="stat-number">{{ Math.round(classificationStats.avgConfidence * 100) }}%</div>
            <div class="stat-label">平均置信度</div>
          </div>
        </div>

        <!-- 分类方法信息 -->
        <div v-if="classificationResult" class="classification-method">
          <div class="method-info">
            <a-tag :color="getMethodColor(classificationResult.method)">
              {{ getMethodText(classificationResult.method) }}
            </a-tag>
            <span class="method-description">
              {{ getMethodDescription(classificationResult.method) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 文档分类树形结构 -->
    <div class="info-card document-tree">
      <div class="card-header">
        <ApartmentOutlined class="header-icon" />
        <h3>分类结构</h3>
        <div class="header-actions">
          <a-button-group size="small">
            <a-button 
              :type="viewMode === 'tree' ? 'primary' : 'default'"
              @click="viewMode = 'tree'"
            >
              <NodeIndexOutlined />
              树形
            </a-button>
            <a-button 
              :type="viewMode === 'grid' ? 'primary' : 'default'"
              @click="viewMode = 'grid'"
            >
              <AppstoreOutlined />
              网格
            </a-button>
            <a-button 
              :type="viewMode === 'list' ? 'primary' : 'default'"
              @click="viewMode = 'list'"
            >
              <UnorderedListOutlined />
              列表
            </a-button>
          </a-button-group>
        </div>
      </div>
      <div class="card-content">
        <!-- 搜索和筛选 -->
        <div class="classification-controls">
          <a-input-search
            v-model:value="searchKeyword"
            placeholder="搜索文档..."
            style="width: 100%"
            @search="handleSearch"
            allow-clear
          />
        </div>

        <!-- 树形视图 -->
        <div v-if="viewMode === 'tree'" class="tree-view">
          <a-tree
            :tree-data="documentTreeData"
            :expanded-keys="expandedKeys"
            :selected-keys="selectedKeys"
            @expand="onExpand"
            @select="onSelect"
            show-icon
          >
            <template #icon="{ dataRef }">
              <FolderOutlined v-if="dataRef.isCategory" />
              <FileTextOutlined v-else />
            </template>
            <template #title="{ dataRef }">
              <div class="tree-node-title">
                <span class="node-text">{{ dataRef.title }}</span>
                <div class="node-tags">
                  <a-tag 
                    v-if="!dataRef.isCategory" 
                    size="small" 
                    :color="getConfidenceColor(dataRef.confidence)"
                  >
                    {{ Math.round(dataRef.confidence * 100) }}%
                  </a-tag>
                  <a-tag 
                    v-if="!dataRef.isCategory && dataRef.aiClassified" 
                    size="small" 
                    color="green"
                  >
                    AI
                  </a-tag>
                </div>
              </div>
            </template>
          </a-tree>
        </div>

        <!-- 网格视图 -->
        <div v-if="viewMode === 'grid'" class="grid-view">
          <div class="document-grid">
            <div
              v-for="document in filteredDocuments"
              :key="document.id"
              class="document-card"
              :class="{ 'selected': selectedDocumentId === document.id }"
              @click="selectDocument(document)"
            >
              <div class="card-icon">
                <FileTextOutlined />
              </div>
              <div class="card-content">
                <div class="document-title">{{ document.title || '未命名文档' }}</div>
                <div class="document-type">{{ document.type || '未分类' }}</div>
              <div class="document-meta">
                <a-tag 
                  size="small" 
                  :color="getConfidenceColor(document.confidence)"
                >
                  {{ Math.round((document.confidence || 0) * 100) }}%
                </a-tag>
                <a-tag 
                  v-if="document.ai_classified" 
                  size="small" 
                  color="green"
                >
                  AI分类
                </a-tag>
                <a-tag size="small" :color="getContentState(document).color">
                  {{ getContentState(document).label }}
                </a-tag>
                <span class="doc-length" v-if="getContentState(document).length > 0">
                  {{ getContentState(document).length }}字
                </span>
              </div>
            </div>
          </div>
        </div>
        </div>

        <!-- 列表视图 -->
        <div v-if="viewMode === 'list'" class="list-view">
          <a-list
            :data-source="filteredDocuments"
            item-layout="horizontal"
          >
            <template #renderItem="{ item }">
              <a-list-item
                class="document-list-item"
                :class="{ 'selected': selectedDocumentId === item.id }"
                @click="selectDocument(item)"
              >
                <a-list-item-meta>
                  <template #avatar>
                    <a-avatar :style="{ backgroundColor: getTypeColor(item.type) }">
                      <FileTextOutlined />
                    </a-avatar>
                  </template>
                  <template #title>
                    <div class="list-item-title">
                      {{ item.title || '未命名文档' }}
                      <div class="list-item-tags">
                        <a-tag 
                          size="small" 
                          :color="getConfidenceColor(item.confidence)"
                        >
                          {{ Math.round((item.confidence || 0) * 100) }}%
                        </a-tag>
                        <a-tag 
                          v-if="item.ai_classified" 
                          size="small" 
                          color="green"
                        >
                          AI分类
                        </a-tag>
                        <a-tag size="small" :color="getContentState(item).color">
                          {{ getContentState(item).label }}
                        </a-tag>
                        <a-tag size="small" color="default" v-if="getContentState(item).length > 0">
                          {{ getContentState(item).length }}字
                        </a-tag>
                      </div>
                    </div>
                  </template>
                  <template #description>
                    <div class="list-item-description">
                      <span class="document-type">{{ item.type || '未分类' }}</span>
                      <span class="document-size" v-if="item.content">
                        {{ item.content.length }} 字符
                      </span>
                    </div>
                  </template>
                </a-list-item-meta>
                <template #actions>
                  <a-button type="text" size="small" @click.stop="viewDocument(item)">
                    <EyeOutlined />
                  </a-button>
                  <a-button type="text" size="small" @click.stop="editDocument(item)">
                    <EditOutlined />
                  </a-button>
                </template>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </div>
    </div>

    <!-- 快速操作 -->
    <div class="info-card quick-actions">
      <div class="card-header">
        <ThunderboltOutlined class="header-icon" />
        <h3>快速操作</h3>
      </div>
      <div class="card-content">
        <div class="action-buttons">
          <a-button block @click="reclassifyAll">
            <ReloadOutlined />
            重新分类
          </a-button>
          <a-button block @click="exportClassification">
            <ExportOutlined />
            导出分类
          </a-button>
          <a-button block @click="validateClassification">
            <CheckCircleOutlined />
            验证分类
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import {
  FolderOpenOutlined,
  ReloadOutlined,
  FilterOutlined,
  CheckOutlined,
  ApartmentOutlined,
  NodeIndexOutlined,
  AppstoreOutlined,
  UnorderedListOutlined,
  FolderOutlined,
  FileTextOutlined,
  EyeOutlined,
  EditOutlined,
  ThunderboltOutlined,
  ExportOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  documents: unknown[]
  classificationResult?: Record<string, unknown>
}

const props = withDefaults(defineProps<Props>(), {
  documents: () => [],
  classificationResult: undefined
})

// Emits
const emit = defineEmits<{
  'document-select': [document: unknown]
  'classification-filter': [filter: unknown]
  'refresh': []
  'reclassify': []
  'export': []
  'validate': []
}>()

// 响应式状态
const activeFilter = ref('all')
const viewMode = ref<'tree' | 'grid' | 'list'>('tree')
const searchKeyword = ref('')
const selectedDocumentId = ref<string | null>(null)
const expandedKeys = ref<string[]>([])
const selectedKeys = ref<string[]>([])

// 计算属性
const totalDocuments = computed(() => props.documents.length)

const classificationStats = computed(() => {
  const docs = props.documents
  const aiClassified = docs.filter(doc => doc.ai_classified).length
  const categories = new Set(docs.map(doc => doc.type).filter(Boolean)).size
  const avgConfidence = docs.length > 0 
    ? docs.reduce((sum, doc) => sum + (doc.confidence || 0), 0) / docs.length 
    : 0

  return {
    aiClassified,
    categories,
    avgConfidence
  }
})

const filteredDocuments = computed(() => {
  let filtered = props.documents

  // 应用筛选器
  switch (activeFilter.value) {
    case 'ai-classified':
      filtered = filtered.filter(doc => doc.ai_classified)
      break
    case 'manual':
      filtered = filtered.filter(doc => !doc.ai_classified)
      break
    case 'high-confidence':
      filtered = filtered.filter(doc => (doc.confidence || 0) > 0.8)
      break
  }

  // 应用搜索
  if (searchKeyword.value.trim()) {
    const keyword = searchKeyword.value.toLowerCase()
    filtered = filtered.filter(doc => 
      (doc.title || '').toLowerCase().includes(keyword) ||
      (doc.type || '').toLowerCase().includes(keyword) ||
      (doc.content || '').toLowerCase().includes(keyword)
    )
  }

  return filtered
})

// 内容状态：正文/预览/无内容 + 长度
const getContentState = (doc: unknown): { label: string; color: string; length: number } => {
  const content = (doc && typeof doc.content === 'string') ? doc.content.trim() : ''
  const preview = (doc && typeof doc.content_preview === 'string') ? doc.content_preview.trim() : ''
  if (content) return { label: '正文', color: 'blue', length: content.length }
  if (preview) return { label: '预览', color: 'orange', length: preview.length }
  return { label: '无内容', color: 'default', length: 0 }
}

const documentTreeData = computed(() => {
  console.log('=== 构建文档树数据 ===')
  console.log('filteredDocuments:', filteredDocuments.value)

  const typeGroups = new Map<string, any[]>()

  filteredDocuments.value.forEach(doc => {
    const type = doc.type || '未分类'
    if (!typeGroups.has(type)) {
      typeGroups.set(type, [])
    }
    typeGroups.get(type)!.push(doc)
  })

  const treeData = Array.from(typeGroups.entries()).map(([type, docs]) => ({
    key: `category-${type}`,
    title: `${type} (${docs.length})`,
    isCategory: true,
    children: docs.map((doc, index) => ({
      key: `doc-${doc.id || `${type}-${index}`}`, // 使用索引作为备用ID
      title: doc.title || doc.type || '未命名文档',
      isCategory: false,
      confidence: doc.confidence || 0,
      aiClassified: doc.ai_classified,
      document: doc
    }))
  }))

  console.log('构建的树形数据:', treeData)
  return treeData
})

// 方法
const handleFilterChange = ({ key }: { key: string }) => {
  activeFilter.value = key
  emit('classification-filter', { filter: key })
}

const handleSearch = (value: string) => {
  searchKeyword.value = value
}

const selectDocument = (document: unknown) => {
  console.log('=== EnhancedDocumentClassification selectDocument ===')
  console.log('选中的文档:', document)
  console.log('文档ID:', document?.id)
  console.log('文档类型:', document?.type)

  selectedDocumentId.value = document.id
  emit('document-select', document)

  console.log('已发送 document-select 事件')
}

const viewDocument = (document: unknown) => {
  // 查看文档详情
  console.log('View document:', document)
}

const editDocument = (document: unknown) => {
  // 编辑文档
  console.log('Edit document:', document)
}

const onExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

const onSelect = (keys: string[], { node }: unknown) => {
  console.log('=== Tree onSelect 调试 ===')
  console.log('选中的keys:', keys)
  console.log('节点信息:', node)
  console.log('是否为分类:', node?.isCategory)
  console.log('是否有document:', !!node?.document)

  selectedKeys.value = keys
  if (!node.isCategory && node.document) {
    console.log('调用 selectDocument')
    selectDocument(node.document)
  } else {
    console.log('跳过 selectDocument - 可能是分类节点或无document数据')
  }
}

const refreshClassification = () => {
  emit('refresh')
}

const reclassifyAll = () => {
  emit('reclassify')
}

const exportClassification = () => {
  emit('export')
}

const validateClassification = () => {
  emit('validate')
}

// 工具函数
const getMethodColor = (method: string) => {
  const colors: Record<string, string> = {
    'AI自动分类': 'green',
    'LLM精准解析': 'blue',
    '手动分类': 'orange',
    '规则匹配': 'purple'
  }
  return colors[method] || 'default'
}

const getMethodText = (method: string) => {
  return method || '未知方法'
}

const getMethodDescription = (method: string) => {
  const descriptions: Record<string, string> = {
    'AI自动分类': '基于机器学习模型的自动文档分类',
    'LLM精准解析': '使用大语言模型进行精确的文档理解和分类',
    '手动分类': '人工手动进行的文档分类',
    '规则匹配': '基于预定义规则的文档分类'
  }
  return descriptions[method] || '暂无描述'
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.9) return 'green'
  if (confidence >= 0.7) return 'blue'
  if (confidence >= 0.5) return 'orange'
  return 'red'
}

const getTypeColor = (type: string) => {
  const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2']
  const hash = type ? type.split('').reduce((a, b) => a + b.charCodeAt(0), 0) : 0
  return colors[hash % colors.length]
}

// 监听文档数据变化，自动展开所有分类
watch(documentTreeData, (newData) => {
  if (newData && newData.length > 0) {
    // 自动展开所有分类节点
    const categoryKeys = newData.map(item => item.key)
    expandedKeys.value = categoryKeys
    console.log('自动展开分类节点:', categoryKeys)
  }
})

// 在组件挂载后初始化展开状态
onMounted(() => {
  nextTick(() => {
    if (documentTreeData.value && documentTreeData.value.length > 0) {
      const categoryKeys = documentTreeData.value.map(item => item.key)
      expandedKeys.value = categoryKeys
      console.log('组件挂载后自动展开分类节点:', categoryKeys)
    }
  })
})
</script>

<style scoped>
.enhanced-document-classification {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.card-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header h3 {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.header-icon {
  font-size: 18px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-content {
  padding: 20px;
}

.classification-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.stat-number {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.classification-method {
  padding: 16px;
  background: #f0f9ff;
  border-radius: 8px;
  border-left: 4px solid #3b82f6;
}

.method-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.method-description {
  font-size: 14px;
  color: #374151;
}

.classification-controls {
  margin-bottom: 16px;
}

.tree-view {
  max-height: 400px;
  overflow-y: auto;
}

.tree-node-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.node-text {
  flex: 1;
  margin-right: 8px;
}

.node-tags {
  display: flex;
  gap: 4px;
}

.document-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.document-card {
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: white;
}

.document-card:hover {
  border-color: #3b82f6;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
}

.document-card.selected {
  border-color: #3b82f6;
  background: #eff6ff;
}

.card-icon {
  text-align: center;
  margin-bottom: 12px;
  font-size: 24px;
  color: #6b7280;
}

.document-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
  font-size: 14px;
}

.document-type {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.document-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.doc-length {
  font-size: 12px;
  color: #6b7280;
}

.list-view {
  max-height: 400px;
  overflow-y: auto;
}

.document-list-item {
  cursor: pointer;
  transition: background-color 0.2s ease;
  border-radius: 8px;
  margin-bottom: 8px;
}

.document-list-item:hover {
  background-color: #f9fafb;
}

.document-list-item.selected {
  background-color: #eff6ff;
}

.list-item-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.list-item-tags {
  display: flex;
  gap: 4px;
}

.list-item-description {
  display: flex;
  gap: 16px;
  align-items: center;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .classification-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .document-grid {
    grid-template-columns: 1fr;
  }
  
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: stretch;
  }
}
</style>
