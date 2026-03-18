<template>
  <div class="flex flex-col h-full bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] font-sans">
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
    <div class="flex-1 flex max-w-7xl w-full mx-auto px-6 py-5 gap-5 min-h-0">
      
      <!-- 左栏：搜索结果 / 树形浏览 -->
      <div class="flex-1 bg-white/92 rounded-[24px] border border-white/80 shadow-[0_18px_40px_rgba(15,23,42,0.06)] overflow-y-auto custom-scrollbar">
        <!-- 搜索中 -->
        <div v-if="searchLoading" class="flex flex-col items-center justify-center py-20 text-slate-400">
          <a-spin />
          <p class="mt-3 text-sm">搜索中…</p>
        </div>

        <!-- 搜索结果 -->
        <div v-else-if="searchQuery.length >= 2 && searchResults.length > 0">
          <div class="flex items-center justify-between px-4 py-3 bg-slate-50/80 border-b border-slate-100 sticky top-0 z-10">
            <span class="text-[13px] font-semibold text-slate-500">搜索结果</span>
            <a-tag color="blue">{{ searchTotal }} 条</a-tag>
          </div>
          <div class="p-1">
            <div
              v-for="item in searchResults"
              :key="item.code + item.type"
              :class="[
                'flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150',
                selectedCode?.code === item.code
                  ? 'bg-blue-50/70 border border-blue-100/60'
                  : 'hover:bg-slate-50 border border-transparent'
              ]"
              @click="selectCode(item)"
            >
              <span
                :class="[
                  'font-mono text-[13px] font-semibold shrink-0 min-w-[90px]',
                  selectedCode?.code === item.code ? 'text-blue-700' : 'text-slate-500'
                ]"
              >{{ item.code }}</span>
              <span class="text-[14px] text-slate-700 truncate flex-1" v-html="highlightMatch(item.name, searchQuery)" />
              <a-tag
                :color="item.type === 'icd10' ? 'blue' : 'green'"
                size="small"
                class="shrink-0"
              >
                {{ item.type === 'icd10' ? 'ICD-10' : 'ICD-9' }}
              </a-tag>
            </div>
          </div>
          <div v-if="searchTotal > searchResults.length" class="text-center py-3">
            <a-button type="link" size="small" @click="loadMoreResults">加载更多…</a-button>
          </div>
        </div>

        <!-- 无搜索结果 -->
        <div v-else-if="searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading" class="flex flex-col items-center justify-center py-20 text-slate-400">
          <SearchOutlined style="font-size: 40px; opacity: 0.3" />
          <p class="mt-3 text-sm">未找到匹配 "{{ searchQuery }}" 的编码</p>
        </div>

        <!-- 树形浏览（极简箭头 + 双拼排版） -->
        <div v-else class="p-3">
          <a-spin :spinning="treeLoading">
            <div v-if="treeData.length > 0" class="space-y-0.5">
              <a-tree
                :tree-data="treeData"
                :load-data="onLoadChildren"
                block-node
                :selectable="true"
                :show-icon="false"
                :show-line="false"
                @select="onTreeSelect"
                class="icd-tree-modern"
              >
                <template #switcherIcon="{ expanded }">
                  <svg
                    :class="['w-4 h-4 transition-transform duration-200 shrink-0', expanded ? 'text-blue-500 rotate-90' : 'text-slate-400']"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </template>
                <template #title="{ title, data }">
                  <div
                    :class="[
                      'flex items-center gap-2 py-0.5',
                      data.isLeaf ? '' : ''
                    ]"
                  >
                    <span v-if="data.isLeaf" class="w-1 h-1 rounded-full bg-slate-300 shrink-0 mx-0.5"></span>
                    <span
                      v-if="data.code_range || data.code"
                      :class="[
                        'font-mono text-[13px] shrink-0',
                        data.isLeaf ? 'font-medium text-slate-500' : 'font-semibold text-slate-600',
                        'min-w-[70px]'
                      ]"
                    >{{ data.code_range || data.code }}</span>
                    <span
                      :class="[
                        'text-[14px] truncate',
                        data.isLeaf ? 'text-slate-600' : 'font-semibold text-slate-800'
                      ]"
                    >{{ title }}</span>
                  </div>
                </template>
              </a-tree>
            </div>
            <div v-else class="flex flex-col items-center justify-center py-20 text-slate-400">
              <svg class="w-10 h-10 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              <p class="mt-3 text-sm">暂无编码数据</p>
            </div>
          </a-spin>
        </div>
      </div>

      <!-- 右栏：编码详情知识卡片 -->
      <div class="w-[400px] shrink-0 rounded-[24px] border border-white/80 bg-white/86 p-3 shadow-[0_18px_40px_rgba(15,23,42,0.05)]">
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
import { SearchOutlined } from '@ant-design/icons-vue'
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
  return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="bg-amber-200/70 px-0.5 rounded font-medium">$1</mark>')
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
/* 极简树样式覆盖 */
.icd-tree-modern :deep(.ant-tree-switcher) {
  display: flex !important;
  align-items: center;
  justify-content: center;
  width: 24px !important;
}

.icd-tree-modern :deep(.ant-tree-node-content-wrapper) {
  padding: 4px 8px !important;
  border-radius: 8px !important;
  transition: background 0.15s !important;
}

.icd-tree-modern :deep(.ant-tree-node-content-wrapper:hover) {
  background: #f8fafc !important;
}

.icd-tree-modern :deep(.ant-tree-node-selected .ant-tree-node-content-wrapper),
.icd-tree-modern :deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background: rgba(59, 130, 246, 0.06) !important;
}

.icd-tree-modern :deep(.ant-tree-treenode) {
  padding: 1px 0 !important;
}

.icd-tree-modern :deep(.ant-tree-indent-unit) {
  width: 20px !important;
}

/* 滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
