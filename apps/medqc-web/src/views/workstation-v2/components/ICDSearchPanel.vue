<template>
  <div class="icd-search-panel">
    <!-- 顶部 Tab：临床版 / 医保版 -->
    <div class="panel-tabs">
      <a-segmented v-model:value="codeVersion" :options="versionTabs" block />
    </div>

    <!-- 编码视图 -->
    <div class="coding-view">
      <!-- 子 Tab：诊断 / 手术 -->
      <div class="sub-tabs">
        <a-segmented v-model:value="codeType" :options="codeTypeTabs" block />
      </div>

      <!-- 搜索框 -->
      <div class="search-box">
        <a-input-search
          v-model:value="searchQuery"
          :placeholder="codeType === 'icd10' ? '输入诊断名称或编码 (至少2位)...' : '输入手术名称或编码 (至少2位)...'"
          allow-clear
          @search="onSearch"
          @change="onSearchDebounced"
        >
          <template #prefix>
            <SearchOutlined style="color: #bfbfbf" />
          </template>
        </a-input-search>
      </div>

      <!-- 搜索结果 -->
      <div v-if="searchQuery.length >= 2 && searchResults.length > 0" class="search-results custom-scrollbar">
        <div class="result-header">
          <span>搜索结果</span>
          <a-tag color="blue">{{ searchTotal }} 条</a-tag>
        </div>
        <div
          v-for="item in searchResults"
          :key="item.code"
          class="result-item"
          @click="onResultClick(item)"
        >
          <div class="result-main">
            <span class="result-code">{{ item.code }}</span>
            <span class="result-name" v-html="highlightMatch(item.name, searchQuery)" />
            <a-tag v-if="item.type === 'icd10'" color="blue" size="small">ICD-10</a-tag>
            <a-tag v-else color="green" size="small">ICD-9</a-tag>
          </div>
          <!-- 映射附注 -->
          <div v-if="item.mapped_code" class="result-mapping" :class="{ 'mapping-diff': item.is_diff }">
            <span class="mapping-label">{{ item.mapped_version }}:</span>
            <span class="mapping-code">{{ item.mapped_code }}</span>
            <span v-if="item.is_diff && item.mapped_name" class="mapping-name">{{ item.mapped_name }}</span>
            <a-tag v-if="item.is_diff" color="orange" size="small">编码不同</a-tag>
            <a-tag v-else color="default" size="small">相同</a-tag>
          </div>
        </div>
        <div v-if="searchTotal > searchResults.length" class="result-more">
          <a-button type="link" size="small" @click="loadMoreResults">加载更多...</a-button>
        </div>
      </div>

      <!-- 无搜索结果提示 -->
      <div v-else-if="searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading" class="empty-hint">
        <SearchOutlined style="font-size: 32px; color: #d9d9d9" />
        <p>未找到匹配的编码</p>
      </div>

      <!-- 搜索中 -->
      <div v-else-if="searchLoading" class="empty-hint">
        <a-spin />
        <p>搜索中...</p>
      </div>

      <!-- 树形浏览（无搜索时显示） -->
      <div v-else class="tree-browser custom-scrollbar">
        <a-spin :spinning="treeLoading">
          <a-tree
            v-if="treeData.length > 0"
            :tree-data="treeData"
            :load-data="onLoadChildren"
            show-icon
            block-node
            :selectable="true"
            @select="onTreeSelect"
          >
            <template #icon="{ data }">
              <FolderOutlined v-if="!data.isLeaf" style="color: #1677ff" />
              <FileTextOutlined v-else style="color: #52c41a" />
            </template>
            <template #title="{ title, data }">
              <span :class="{ 'tree-leaf': data.isLeaf }">
                <template v-if="data.code_range">
                  <span class="tree-code-range">({{ data.code_range }})</span>
                </template>
                {{ title }}
              </span>
            </template>
          </a-tree>
          <div v-else class="empty-hint">
            <FolderOpenOutlined style="font-size: 32px; color: #d9d9d9" />
            <p>暂无编码数据</p>
          </div>
        </a-spin>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import {
  SearchOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'
import type { TreeProps } from 'ant-design-vue'

// ==================== Tab 状态 ====================
const codeVersion = ref('clinical')
const versionTabs = [
  { label: '🏥 临床版', value: 'clinical' },
  { label: '🏦 医保版', value: 'insurance' },
]

const codeType = ref('icd10')
const codeTypeTabs = [
  { label: '诊断搜索 (ICD-10)', value: 'icd10' },
  { label: '手术搜索 (ICD-9)', value: 'icd9cm3' },
]

// ==================== 搜索 ====================
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searchTotal = ref(0)
const searchLoading = ref(false)
let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null

function onSearchDebounced() {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(() => {
    if (searchQuery.value.length >= 2) {
      doSearch()
    } else {
      searchResults.value = []
      searchTotal.value = 0
    }
  }, 300)
}

function onSearch() {
  if (searchQuery.value.length >= 2) {
    doSearch()
  }
}

async function doSearch(offset = 0) {
  searchLoading.value = true
  try {
    const params = new URLSearchParams({
      q: searchQuery.value,
      type: codeType.value,
      version: codeVersion.value === 'clinical' ? 'clinical' : 'insurance',
      limit: '50',
      offset: String(offset),
    })
    const resp = await fetch(`/api/v1/icd/search?${params}`)
    const json = await resp.json()
    if (json.success) {
      if (offset === 0) {
        searchResults.value = json.data.items
      } else {
        searchResults.value.push(...json.data.items)
      }
      searchTotal.value = json.data.total
    }
  } catch (e) {
    console.error('ICD 搜索失败:', e)
  } finally {
    searchLoading.value = false
  }
}

function loadMoreResults() {
  doSearch(searchResults.value.length)
}

function highlightMatch(text: string, query: string): string {
  if (!query) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>')
}

function onResultClick(item: any) {
  console.log('选中编码:', item)
}

// ==================== 树形浏览 ====================
const treeData = ref<any[]>([])
const treeLoading = ref(false)

async function loadTree() {
  treeLoading.value = true
  try {
    const resp = await fetch(`/api/v1/icd/tree?type=${codeType.value}`)
    const json = await resp.json()
    if (json.success) {
      treeData.value = json.data.chapters.map((ch: any) => ({
        ...ch,
        children: ch.children?.map((sec: any) => ({
          ...sec,
          // 将 children 设为 undefined 以触发懒加载
          children: undefined,
        })) || [],
      }))
    }
  } catch (e) {
    console.error('加载 ICD 树失败:', e)
  } finally {
    treeLoading.value = false
  }
}

const onLoadChildren: TreeProps['loadData'] = (treeNode) => {
  return new Promise<void>(async (resolve) => {
    if (treeNode.dataRef?.children && treeNode.dataRef.children.length > 0) {
      resolve()
      return
    }
    try {
      const parentKey = treeNode.dataRef?.key || treeNode.key
      const params = new URLSearchParams({
        type: codeType.value,
        parent_key: String(parentKey),
      })
      const resp = await fetch(`/api/v1/icd/tree/children?${params}`)
      const json = await resp.json()
      if (json.success && json.data.children.length > 0) {
        treeNode.dataRef!.children = json.data.children.map((child: any) => ({
          ...child,
          children: child.isLeaf ? undefined : undefined,
        }))
      } else {
        treeNode.dataRef!.children = []
      }
    } catch (e) {
      console.error('加载子节点失败:', e)
      treeNode.dataRef!.children = []
    }
    resolve()
  })
}

function onTreeSelect(selectedKeys: string[], info: any) {
  const node = info.node
  if (node.isLeaf && node.code) {
    console.log('选中编码:', node.code, node.name || node.title)
  }
}

// 切换编码类型或版本时重新加载
watch([codeType, codeVersion], () => {
  searchQuery.value = ''
  searchResults.value = []
  searchTotal.value = 0
  loadTree()
})

onMounted(() => {
  loadTree()
})
</script>

<style scoped>
.icd-search-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 0;
}

.panel-tabs {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.coding-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.sub-tabs {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.search-box {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  font-weight: 600;
  font-size: 13px;
  color: #666;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  position: sticky;
  top: 0;
  z-index: 1;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.15s;
}
.result-item:hover {
  background: #e6f4ff;
}
.result-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-mapping {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 86px;
  font-size: 12px;
  color: #999;
}
.result-mapping.mapping-diff {
  color: #d46b08;
}
.mapping-label {
  font-weight: 500;
  color: #8c8c8c;
}
.mapping-code {
  font-family: 'Courier New', monospace;
  font-weight: 500;
  color: #8c8c8c;
}
.mapping-diff .mapping-code {
  color: #d46b08;
}
.mapping-name {
  color: #8c8c8c;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-code {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  color: #1677ff;
  min-width: 80px;
  font-size: 13px;
}

.result-name {
  flex: 1;
  font-size: 13px;
  color: #333;
}
.result-name :deep(mark) {
  background: #ffe58f;
  padding: 0 2px;
  border-radius: 2px;
}

.result-more {
  text-align: center;
  padding: 8px;
}

.tree-browser {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px;
}

.tree-code-range {
  color: #1677ff;
  font-weight: 500;
  margin-right: 4px;
  font-size: 12px;
}

.tree-leaf {
  color: #333;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
  color: #999;
}
.empty-hint h3 {
  margin: 12px 0 4px;
  font-size: 16px;
  color: #333;
}
.empty-hint p {
  margin: 4px 0;
  font-size: 13px;
}
.empty-hint .hint {
  color: #bbb;
  font-size: 12px;
}

.monitor-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #bfbfbf;
}
</style>
