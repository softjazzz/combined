<template>
  <div class="icd-workstation flex h-full flex-col font-sans">
    <ICDSearchHero
      :code-version="codeVersion"
      :code-type="codeType"
      :search-query="searchQuery"
      :stats="codeStats"
      @update:code-version="onVersionChange"
      @update:code-type="onTypeChange"
      @update:search-query="(v) => (searchQuery = v)"
      @search="handleSearch"
    />

    <div class="icd-workspace mx-auto flex w-full max-w-7xl flex-1 gap-5 px-6 py-5 min-h-0">
      <div class="icd-result-shell flex flex-1 flex-col overflow-y-auto custom-scrollbar">
        <div class="icd-result-head sticky top-0 z-10 flex items-center justify-between px-4 py-3">
          <div class="min-w-0">
            <div class="text-[12px] font-semibold text-slate-700">
              {{ searchQuery.length >= 2 ? '编码搜索结果' : '编码目录浏览' }}
            </div>
            <div class="mt-0.5 text-[11px] text-slate-400">
              {{ codeType === 'icd10' ? '诊断编码' : '手术编码' }} ·
              {{ codeVersion === 'clinical' ? '临床版' : '医保版' }}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span
              class="rounded-full border border-blue-100 bg-blue-50/80 px-2.5 py-1 text-[11px] font-semibold text-[#0057b8]"
            >
              {{ codeType === 'icd10' ? 'ICD-10' : 'ICD-9' }}
            </span>
            <span
              class="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500"
            >
              {{ searchQuery.length >= 2 ? `${searchTotal} 条` : `${treeData.length} 章` }}
            </span>
          </div>
        </div>

        <div
          v-if="searchLoading"
          class="flex flex-col items-center justify-center py-20 text-slate-400"
        >
          <a-spin />
          <p class="mt-3 text-sm">
            搜索中...
          </p>
        </div>

        <div
          v-else-if="searchQuery.length >= 2 && searchResults.length > 0"
          class="flex flex-1 flex-col"
        >
          <div class="p-2.5">
            <div
              v-for="item in searchResults"
              :key="item.code + item.type"
              :class="[
                'icd-result-row group flex cursor-pointer items-start gap-3 px-3 py-3 transition-all duration-150',
                selectedCode?.code === item.code ? 'is-selected' : '',
              ]"
              @click="selectCode(item)"
            >
              <div
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[14px] border border-blue-100 bg-blue-50 text-[12px] font-semibold text-[#0057b8]"
              >
                {{ item.type === 'icd10' ? '诊' : '术' }}
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span
                    :class="[
                      'font-mono text-[13px] font-semibold',
                      selectedCode?.code === item.code ? 'text-[#0057b8]' : 'text-slate-500',
                    ]"
                  >{{ item.code }}</span>
                  <span
                    class="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-semibold text-slate-500"
                  >
                    {{ item.type === 'icd10' ? 'ICD-10' : 'ICD-9' }}
                  </span>
                </div>
                <div
                  class="mt-1 text-[14px] font-medium leading-6 text-slate-800"
                  v-html="highlightMatch(item.name, searchQuery)"
                />
              </div>
            </div>
          </div>
          <div
            v-if="searchTotal > searchResults.length"
            class="py-3 text-center"
          >
            <a-button
              type="link"
              size="small"
              @click="loadMoreResults"
            >
              加载更多
            </a-button>
          </div>
        </div>

        <div
          v-else-if="searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading"
          class="flex flex-col items-center justify-center py-20 text-slate-400"
        >
          <SearchOutlined style="font-size: 40px; opacity: 0.3" />
          <p class="mt-3 text-sm">
            未找到匹配 "{{ searchQuery }}" 的编码
          </p>
        </div>

        <div
          v-else
          class="flex-1 p-3"
        >
          <a-spin :spinning="treeLoading">
            <div
              v-if="treeData.length > 0"
              class="rounded-[20px] border border-slate-200/80 bg-white/94 p-3"
            >
              <div class="mb-3 flex items-center justify-between px-1">
                <div>
                  <div class="text-[12px] font-semibold text-slate-500">
                    编码目录
                  </div>
                  <div class="mt-0.5 text-[11px] text-slate-400">
                    支持逐级展开定位章节、类目与叶子编码
                  </div>
                </div>
                <span
                  class="rounded-full border border-slate-200 bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-slate-500"
                >
                  当前 {{ codeType === 'icd10' ? '诊断' : '手术' }}
                </span>
              </div>
              <a-tree
                :tree-data="treeData"
                :load-data="onLoadChildren"
                block-node
                :selectable="true"
                :show-icon="false"
                :show-line="false"
                class="icd-tree-modern"
                @select="onTreeSelect"
              >
                <template #switcherIcon="{ expanded }">
                  <svg
                    :class="[
                      'h-4 w-4 shrink-0 transition-transform duration-200',
                      expanded ? 'rotate-90 text-blue-500' : 'text-slate-400',
                    ]"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </template>
                <template #title="{ title, data }">
                  <div class="flex items-center gap-2 py-0.5">
                    <span
                      v-if="data.isLeaf"
                      class="mx-0.5 h-1 w-1 shrink-0 rounded-full bg-slate-300"
                    />
                    <span
                      v-if="data.code_range || data.code"
                      :class="[
                        'min-w-[70px] shrink-0 font-mono text-[13px]',
                        data.isLeaf ? 'font-medium text-slate-500' : 'font-semibold text-slate-600',
                      ]"
                    >{{ data.code_range || data.code }}</span>
                    <span
                      :class="[
                        'truncate text-[14px]',
                        data.isLeaf ? 'text-slate-600' : 'font-semibold text-slate-800',
                      ]"
                    >{{ title }}</span>
                  </div>
                </template>
              </a-tree>
            </div>
            <div
              v-else
              class="flex flex-col items-center justify-center py-20 text-slate-400"
            >
              <svg
                class="h-10 w-10 opacity-30"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="1.5"
                  d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"
                />
              </svg>
              <p class="mt-3 text-sm">
                暂无编码数据
              </p>
            </div>
          </a-spin>
        </div>
      </div>

      <div class="icd-detail-shell w-[420px] shrink-0 p-3">
        <ICDDetailPanel
          :selected-code="selectedCode"
          :allow-apply="allowApply"
          :apply-label="applyLabel"
          @copy="onCopyCode"
          @apply="onApplyCode"
        />
      </div>
    </div>

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
import { getAccessToken } from '@/utils/auth-token'

import ICDSearchHero from './ICDSearchHero.vue'
import ICDDetailPanel from './ICDDetailPanel.vue'
import ICDRecentBar from './ICDRecentBar.vue'
import type { ICDCodeDetail } from './ICDDetailPanel.vue'
import type { RecentCode } from './ICDRecentBar.vue'

withDefaults(
  defineProps<{
    allowApply?: boolean
    applyLabel?: string
  }>(),
  {
    allowApply: false,
    applyLabel: '',
  },
)

const emit = defineEmits<{
  apply: [detail: ICDCodeDetail]
}>()

function getAuthHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAccessToken()
  const headers: Record<string, string> = { ...extra }
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

const codeVersion = ref('clinical')
const codeType = ref('icd10')
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searchTotal = ref(0)
const searchLoading = ref(false)
const selectedCode = ref<ICDCodeDetail | null>(null)
const recentCodes = ref<RecentCode[]>([])
const codeStats = ref<{ icd10Count?: number; icd9Count?: number }>({})

function onVersionChange(v: string) {
  codeVersion.value = v
}

function onTypeChange(v: string) {
  codeType.value = v
}

/** ICDSearchHero 的 search emit 传的是 string（搜索词），这里忽略它，从 offset=0 开始搜索 */
function handleSearch() {
  doSearch(0)
}

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
    const resp = await fetch(`/api/v1/icd/search?${params}`, {
      headers: getAuthHeaders(),
    })
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
  return text.replace(
    new RegExp(`(${escaped})`, 'gi'),
    '<mark class="rounded bg-blue-100 px-0.5 font-medium text-[#0057b8]">$1</mark>',
  )
}

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
  recentCodes.value = [entry, ...recentCodes.value.filter((r) => r.code !== entry.code)].slice(0, 8)
}

function onCopyCode(code: string) {
  navigator.clipboard
    .writeText(code)
    .then(() => {
      message.success(`已复制编码 ${code}`)
    })
    .catch(() => {
      message.error('复制失败，请手动复制')
    })
}

function onApplyCode(detail: ICDCodeDetail) {
  emit('apply', detail)
}

const treeData = ref<any[]>([])
const treeLoading = ref(false)

async function loadTree() {
  treeLoading.value = true
  try {
    const resp = await fetch(`/api/v1/icd/tree?type=${codeType.value}`, {
      headers: getAuthHeaders(),
    })
    const json = await resp.json()
    if (json.success) {
      treeData.value = json.data.chapters.map((ch: any) => ({
        ...ch,
        children:
          ch.children?.map((sec: any) => ({
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

const onLoadChildren: TreeProps['loadData'] = async (treeNode) => {
  if (treeNode.dataRef?.children && treeNode.dataRef.children.length > 0) {
    return
  }
  try {
    const parentKey = treeNode.dataRef?.key || treeNode.key
    const params = new URLSearchParams({
      type: codeType.value,
      parent_key: String(parentKey),
    })
    const resp = await fetch(`/api/v1/icd/tree/children?${params}`, {
      headers: getAuthHeaders(),
    })
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
.icd-workstation {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'SF Pro Display', 'San Francisco', 'PingFang SC',
    'Microsoft YaHei UI', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.icd-workspace {
  background: transparent;
}

.icd-result-shell,
.icd-detail-shell {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 16px 36px rgba(15, 23, 42, 0.06);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.icd-result-head {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.icd-workstation :deep(.text-slate-900),
.icd-workstation :deep(.text-slate-800),
.icd-workstation :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.icd-workstation :deep(.text-slate-600),
.icd-workstation :deep(.text-slate-500) {
  color: rgba(29, 29, 31, 0.6) !important;
}

.icd-workstation :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.38) !important;
}

.icd-workstation :deep(.text-\[\#0057b8\]),
.icd-workstation :deep(.text-blue-500) {
  color: #2b6cf6 !important;
}

.icd-workstation :deep(.border-slate-200),
.icd-workstation :deep(.border-slate-200\/80),
.icd-workstation :deep(.border-blue-100) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.icd-workstation :deep(.bg-white),
.icd-workstation :deep(.bg-white\/90),
.icd-workstation :deep(.bg-white\/94) {
  background-color: rgba(255, 255, 255, 0.82) !important;
}

.icd-workstation :deep(.bg-blue-50),
.icd-workstation :deep(.bg-blue-50\/80) {
  background-color: rgba(43, 108, 246, 0.08) !important;
}

.icd-workstation :deep(.font-semibold) {
  font-weight: 650 !important;
}

.icd-result-row {
  border: 1px solid transparent;
  border-radius: 14px;
  color: rgba(29, 29, 31, 0.76);
}

.icd-result-row:hover {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(245, 245, 247, 0.72);
}

.icd-result-row.is-selected {
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.08);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    0 3px 10px rgba(43, 108, 246, 0.08);
}

.icd-tree-modern :deep(.ant-tree-switcher) {
  display: flex !important;
  align-items: center;
  justify-content: center;
  width: 24px !important;
}

.icd-tree-modern :deep(.ant-tree-node-content-wrapper) {
  padding: 6px 10px !important;
  border-radius: 12px !important;
  transition:
    background 0.18s ease,
    color 0.18s ease !important;
}

.icd-tree-modern :deep(.ant-tree-node-content-wrapper:hover) {
  background: rgba(0, 0, 0, 0.04) !important;
}

.icd-tree-modern :deep(.ant-tree-node-selected .ant-tree-node-content-wrapper),
.icd-tree-modern :deep(.ant-tree-node-content-wrapper.ant-tree-node-selected) {
  background: rgba(43, 108, 246, 0.08) !important;
  color: #2b6cf6 !important;
}

.icd-tree-modern :deep(.ant-tree-treenode) {
  padding: 1px 0 !important;
}

.icd-tree-modern :deep(.ant-tree-indent-unit) {
  width: 20px !important;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(29, 29, 31, 0.16);
  border-radius: 3px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(29, 29, 31, 0.24);
}
</style>
