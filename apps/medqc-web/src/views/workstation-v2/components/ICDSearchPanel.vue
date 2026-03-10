<template>
  <div class="icd-workspace">
    <!-- 顶部 Hero 搜索区 -->
    <ICDSearchHero
      :code-version="codeVersion"
      :code-type="codeType"
      :search-query="searchQuery"
      :stats="codeStats"
      @update:code-version="onVersionChange"
      @update:code-type="onTypeChange"
      @update:search-query="(v) => searchQuery = v"
      @search="doSearch"
    />

    <!-- 主内容区：双栏 -->
    <div class="workspace-body">
      <!-- 左栏：搜索结果 / 树形浏览 -->
      <div class="workspace-left custom-scrollbar">
        <!-- 搜索中 -->
        <div v-if="searchLoading" class="state-hint">
          <a-spin />
          <p>搜索中…</p>
        </div>

        <!-- 搜索结果 -->
        <div v-else-if="searchQuery.length >= 2 && searchResults.length > 0" class="search-results">
          <div class="results-header">
            <span>搜索结果</span>
            <a-tag color="blue">{{ searchTotal }} 条</a-tag>
          </div>
          <div
            v-for="item in searchResults"
            :key="item.code + item.type"
            class="result-card"
            :class="{ 'result-card--active': selectedCode?.code === item.code }"
            @click="selectCode(item)"
          >
            <div class="result-main">
              <span class="result-code">{{ item.code }}</span>
              <span class="result-name" v-html="highlightMatch(item.name, searchQuery)" />
              <a-tag
                :color="item.type === 'icd10' ? 'blue' : 'green'"
                size="small"
                class="result-type-tag"
              >
                {{ item.type === 'icd10' ? 'ICD-10' : 'ICD-9' }}
              </a-tag>
            </div>
            <!-- 映射附注 -->
            <div v-if="item.mapped_code" class="result-mapping" :class="{ 'mapping-diff': item.is_diff }">
              <span class="mapping-label">{{ item.mapped_version }}:</span>
              <span class="mapping-code">{{ item.mapped_code }}</span>
              <a-tag v-if="item.is_diff" color="orange" size="small">编码不同</a-tag>
              <a-tag v-else color="default" size="small">相同</a-tag>
            </div>
          </div>
          <div v-if="searchTotal > searchResults.length" class="load-more">
            <a-button type="link" size="small" @click="loadMoreResults">加载更多…</a-button>
          </div>
        </div>

        <!-- 无搜索结果 -->
        <div v-else-if="searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading" class="state-hint">
          <SearchOutlined style="font-size: 40px; color: #d9d9d9" />
          <p>未找到匹配 "{{ searchQuery }}" 的编码</p>
        </div>

        <!-- 树形浏览（默认） -->
        <div v-else class="tree-browser">
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
                <FolderOutlined v-if="!data.isLeaf" class="tree-folder-icon" />
                <FileTextOutlined v-else class="tree-leaf-icon" />
              </template>
              <template #title="{ title, data }">
                <span class="tree-node" :class="{ 'tree-node--leaf': data.isLeaf }">
                  <span v-if="data.code_range" class="tree-range-tag">{{ data.code_range }}</span>
                  {{ title }}
                </span>
              </template>
            </a-tree>
            <div v-else class="state-hint">
              <FolderOpenOutlined style="font-size: 40px; color: #d9d9d9" />
              <p>暂无编码数据</p>
            </div>
          </a-spin>
        </div>
      </div>

      <!-- 右栏：编码详情 -->
      <div class="workspace-right">
        <ICDDetailPanel
          :selected-code="selectedCode"
          :allow-apply="allowApply"
          :apply-label="applyLabel"
          @copy="onCopyCode"
          @apply="onApplyCode"
        />
      </div>
    </div>

    <!-- 底部最近查看 -->
    <ICDRecentBar
      :recent-codes="recentCodes"
      @select="selectCode"
      @clear="recentCodes = []"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  FolderOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'
import type { TreeProps } from 'ant-design-vue'

import ICDSearchHero from './ICDSearchHero.vue'
import ICDDetailPanel from './ICDDetailPanel.vue'
import ICDRecentBar from './ICDRecentBar.vue'
import type { ICDCodeDetail } from './ICDDetailPanel.vue'
import type { RecentCode } from './ICDRecentBar.vue'

const props = withDefaults(defineProps<{
  allowApply?: boolean
  applyLabel?: string
}>(), {
  allowApply: false,
  applyLabel: '',
})

const emit = defineEmits<{
  apply: [detail: ICDCodeDetail]
}>()

// ==================== 状态管理 ====================
const codeVersion = ref('clinical')
const codeType = ref('icd10')
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searchTotal = ref(0)
const searchLoading = ref(false)
const selectedCode = ref<ICDCodeDetail | null>(null)
const recentCodes = ref<RecentCode[]>([])
const codeStats = ref<{ icd10Count?: number; icd9Count?: number }>({})

// ==================== 事件处理 ====================
function onVersionChange(v: string) {
  codeVersion.value = v
}

function onTypeChange(v: string) {
  codeType.value = v
}

// ==================== 搜索 ====================
async function doSearch(offset = 0) {
  if (typeof offset === 'string') offset = 0
  if (searchQuery.value.length < 2) return
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

// ==================== 编码选择 ====================
function selectCode(item: any) {
  selectedCode.value = {
    code: item.code,
    name: item.name || item.title,
    type: item.type || codeType.value,
    mapped_code: item.mapped_code,
    mapped_name: item.mapped_name,
    mapped_version: item.mapped_version,
    is_diff: item.is_diff,
    category_path: item.category_path,
    inclusions: item.inclusions,
    exclusions: item.exclusions,
  }
  addToRecent(item)
}

function addToRecent(item: any) {
  const entry: RecentCode = {
    code: item.code,
    name: item.name || item.title || '',
    type: item.type || codeType.value,
  }
  // 去重并限制最多8条
  recentCodes.value = [
    entry,
    ...recentCodes.value.filter((r) => r.code !== entry.code),
  ].slice(0, 8)
}

function onCopyCode(code: string) {
  navigator.clipboard.writeText(code).then(() => {
    message.success(`已复制编码: ${code}`)
  }).catch(() => {
    message.error('复制失败，请手动复制')
  })
}

function onApplyCode(detail: ICDCodeDetail) {
  emit('apply', detail)
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
          children: undefined,
        })) || [],
      }))
      // 更新统计
      if (json.data.stats) {
        codeStats.value = {
          icd10Count: json.data.stats.icd10_count,
          icd9Count: json.data.stats.icd9cm3_count,
        }
      }
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
    selectCode({
      code: node.code,
      name: node.name || node.title,
      type: codeType.value,
    })
  }
}

// ==================== 监听切换 ====================
watch([codeType, codeVersion], () => {
  searchQuery.value = ''
  searchResults.value = []
  searchTotal.value = 0
  selectedCode.value = null
  loadTree()
})

onMounted(() => {
  loadTree()
})
</script>

<style scoped>
/* ==================== 工作台容器 ==================== */
.icd-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}

/* ==================== 主体双栏 ==================== */
.workspace-body {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 16px;
  flex: 1;
  min-height: 0;
  padding: 16px 20px;
}

.workspace-left {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #f0f0f0;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
  overflow-y: auto;
  min-height: 0;
}

.workspace-right {
  min-height: 0;
}

/* ==================== 状态提示 ==================== */
.state-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: #999;
}
.state-hint p {
  margin: 12px 0 0;
  font-size: 14px;
}

/* ==================== 搜索结果 ==================== */
.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-weight: 600;
  font-size: 13px;
  color: #666;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
  position: sticky;
  top: 0;
  z-index: 2;
  border-radius: 12px 12px 0 0;
}

.result-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f8f8f8;
  border-left: 3px solid transparent;
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.result-card:hover {
  background: #f0f7ff;
  border-left-color: #0066CC;
}
.result-card--active {
  background: #e8f4ff;
  border-left-color: #0066CC;
}

.result-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.result-code {
  font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
  font-weight: 700;
  color: #0066CC;
  min-width: 80px;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.3px;
  flex-shrink: 0;
}

.result-name {
  flex: 1;
  font-size: 14px;
  color: #333;
  min-width: 0;
}
.result-name :deep(mark) {
  background: #ffe58f;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 500;
}

.result-type-tag {
  flex-shrink: 0;
}

.result-mapping {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 90px;
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
  font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
  font-weight: 500;
}

.load-more {
  text-align: center;
  padding: 12px;
}

/* ==================== 树形浏览 ==================== */
.tree-browser {
  padding: 12px 8px;
}

.tree-folder-icon {
  color: #0066CC;
}
.tree-leaf-icon {
  color: #00A651;
}

.tree-node {
  font-size: 14px;
  color: #333;
}
.tree-node--leaf {
  color: #444;
}

.tree-range-tag {
  display: inline-block;
  font-family: 'SF Mono', 'Menlo', 'Courier New', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #0066CC;
  background: #e8f4ff;
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 6px;
  letter-spacing: 0.3px;
}

/* ==================== 滚动条 ==================== */
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e0e0e0;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #ccc;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .workspace-body {
    grid-template-columns: 1fr;
  }
  .workspace-right {
    display: none;
  }
}
</style>
