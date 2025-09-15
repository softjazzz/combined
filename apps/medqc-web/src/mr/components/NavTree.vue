<template>
  <div class="nav-tree">
    <!-- 搜索框 -->
    <div class="tree-search">
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索文档..."
        allow-clear
        @search="handleSearch"
        @change="handleSearch"
      />
    </div>

    <!-- 树形导航 -->
    <div class="tree-container">
      <a-tree
        v-if="filteredTreeData.length > 0"
        :tree-data="filteredTreeData"
        :selected-keys="selectedKeys"
        :expanded-keys="expandedKeys"
        @select="handleSelect"
        @expand="handleExpand"
        show-icon
        block-node
      >
        <template #icon="{ dataRef }">
          <FolderOutlined v-if="!dataRef.isLeaf" />
          <FileTextOutlined v-else />
        </template>

        <template #title="{ dataRef }">
          <div class="tree-node-title">
            <span class="node-text" v-html="highlightText(getDisplayTitle(dataRef))"></span>
          </div>
        </template>
      </a-tree>

      <!-- 空状态 -->
      <div v-else class="tree-empty">
        <a-empty
          :description="searchKeyword ? '未找到匹配的文档' : '暂无文档'"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Empty } from 'ant-design-vue'
import {
  FolderOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'

interface TreeNode {
  key: string
  title: string
  isLeaf?: boolean
  children?: TreeNode[]
  aiScore?: number
  created_at?: string
  category?: string
}

interface Props {
  treeData: TreeNode[]
  selectedKey?: string
}

const props = withDefaults(defineProps<Props>(), {
  treeData: () => [],
  selectedKey: ''
})

const emit = defineEmits<{
  'select': [data: { docId: string; node: TreeNode }]
}>()

// 响应式状态
const searchKeyword = ref('')
const selectedKeys = ref<string[]>([])
const expandedKeys = ref<string[]>([])

// 监听选中状态变化
watch(() => props.selectedKey, (newKey) => {
  selectedKeys.value = newKey ? [newKey] : []
}, { immediate: true })

// 初始化展开所有分类节点
watch(() => props.treeData, (newData) => {
  if (newData && newData.length > 0) {
    const categoryKeys = newData
      .filter(node => !node.isLeaf)
      .map(node => node.key)
    expandedKeys.value = categoryKeys
  }
}, { immediate: true })

// 过滤树数据
const filteredTreeData = computed(() => {
  if (!searchKeyword.value.trim()) {
    return props.treeData
  }

  const keyword = searchKeyword.value.toLowerCase()

  return props.treeData.map(categoryNode => {
    if (!categoryNode.children) return categoryNode

    const filteredChildren = categoryNode.children.filter(child =>
      child.title.toLowerCase().includes(keyword) ||
      child.category?.toLowerCase().includes(keyword)
    )

    if (filteredChildren.length === 0) return null

    return {
      ...categoryNode,
      title: `${categoryNode.title.split('(')[0]}(${filteredChildren.length})`,
      children: filteredChildren
    }
  }).filter(Boolean) as TreeNode[]
})

// 获取显示标题
const getDisplayTitle = (node: TreeNode) => {
  if (!node.isLeaf) {
    // 一级目录（分类）：只显示中文分类名称和文档数量
    return node.title
  } else {
    // 二级目录（文档）：只显示文档标题，移除日期时间等信息
    let title = node.title

    // 移除日期时间信息（格式如：2025-03-30 01:08）
    title = title.replace(/\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/g, '').trim()

    // 移除多余的空白字符
    title = title.replace(/\s+/g, ' ').trim()

    return title || '未命名文档'
  }
}

// 高亮搜索关键词
const highlightText = (text: string) => {
  if (!searchKeyword.value.trim()) return text

  const keyword = searchKeyword.value.trim()
  const regex = new RegExp(`(${escapeRegExp(keyword)})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

// 转义正则表达式特殊字符
const escapeRegExp = (string: string) => {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 这些函数已移除，因为不再显示AI评分和时间信息

// 处理搜索
const handleSearch = () => {
  // 搜索时自动展开所有匹配的分类
  if (searchKeyword.value.trim()) {
    const matchedCategories = filteredTreeData.value
      .filter(node => !node.isLeaf)
      .map(node => node.key)
    expandedKeys.value = matchedCategories
  }
}

// 处理节点选择
const handleSelect = (keys: string[], { node }: any) => {
  if (keys.length === 0) return

  const selectedKey = keys[0]
  const selectedNode = findNodeByKey(props.treeData, selectedKey)

  if (selectedNode && selectedNode.isLeaf) {
    emit('select', {
      docId: selectedKey,
      node: selectedNode
    })
  }
}

// 处理节点展开
const handleExpand = (keys: string[]) => {
  expandedKeys.value = keys
}

// 根据 key 查找节点
const findNodeByKey = (nodes: TreeNode[], key: string): TreeNode | null => {
  for (const node of nodes) {
    if (node.key === key) return node
    if (node.children) {
      const found = findNodeByKey(node.children, key)
      if (found) return found
    }
  }
  return null
}
</script>

<style scoped>
.nav-tree {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.tree-search {
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.tree-container {
  flex: 1;
  overflow: auto;
  padding: 8px 0;
}

.tree-node-title {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 20px;
  line-height: 1.2;
}

.node-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
  max-width: 100%;
  font-size: 13px;
}

.node-text :deep(mark) {
  background: #fff566;
  padding: 0 2px;
  border-radius: 2px;
}

.tree-empty {
  padding: 40px 20px;
  text-align: center;
}

/* 自定义树节点样式 */
:deep(.ant-tree-node-content-wrapper) {
  width: 100%;
  padding: 2px 8px;
  border-radius: 4px;
  transition: all 0.2s;
  min-height: 24px;
  line-height: 20px;
}

:deep(.ant-tree-node-content-wrapper:hover) {
  background: #f5f5f5;
}

:deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background: #e6f7ff;
  border-color: #1890ff;
}

:deep(.ant-tree-treenode) {
  padding: 0;
  margin: 0;
}

:deep(.ant-tree-switcher) {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 强制单行显示 */
:deep(.ant-tree-title) {
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  max-width: 100% !important;
}

:deep(.ant-tree-node-content-wrapper .ant-tree-title) {
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
}

/* 紧凑布局 */
:deep(.ant-tree) {
  line-height: 1.2 !important;
}

:deep(.ant-tree-list-holder-inner) {
  padding: 0 !important;
}

:deep(.ant-tree-treenode-leaf-last) {
  margin-bottom: 0 !important;
}

:deep(.ant-tree-child-tree) {
  margin-top: 0 !important;
}

:deep(.ant-tree-indent-unit) {
  width: 16px !important;
}

/* 减少图标和文字间距 */
:deep(.ant-tree-iconEle) {
  margin-right: 4px !important;
}

/* 调整切换器大小 */
:deep(.ant-tree-switcher) {
  width: 16px !important;
  height: 20px !important;
  line-height: 20px !important;
}

/* Diamante 紧凑模式：更小的行高与间距，标题单行省略 */
:deep(.ant-tree) {
  font-size: 13px;
  line-height: 20px !important;
}

:deep(.ant-tree .ant-tree-treenode) {
  margin: 0 !important;
  padding: 0 !important;
}

:deep(.ant-tree .ant-tree-node-content-wrapper) {
  height: 24px !important;
  line-height: 24px !important;
  padding: 0 6px !important;
}

:deep(.ant-tree .ant-tree-switcher),
:deep(.ant-tree .ant-tree-iconEle),
:deep(.ant-tree .ant-tree-indent-unit) {
  height: 24px !important;
  line-height: 24px !important;
}

:deep(.ant-tree .ant-tree-title) {
  display: inline-block !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  line-height: 24px !important;
  vertical-align: middle !important;
}

:deep(.ant-tree-list),
:deep(.ant-tree-list-holder-inner) {
  margin: 0 !important;
  padding: 0 !important;
}

</style>
