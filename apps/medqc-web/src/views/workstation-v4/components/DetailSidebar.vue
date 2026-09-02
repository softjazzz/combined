<template>
  <aside
    class="detail-apple-sidebar custom-scrollbar w-[220px] min-w-[220px] max-w-[220px] basis-[220px] shrink-0 overflow-y-auto border-r"
  >
    <div
      v-if="record"
      class="flex h-full flex-col"
    >
      <div class="flex-1 px-2.5 pb-4 pt-3">
        <div class="mb-3 flex items-center justify-between px-1">
          <div>
            <h3 class="m-0 text-[13px] font-semibold text-slate-900">
              病历文书
            </h3>
            <p class="m-0 mt-0.5 text-[11px] font-semibold text-slate-400">
              按文书类型分组
            </p>
          </div>
          <SyncOutlined
            v-if="documentsLoading"
            spin
            class="text-[12px] text-[#0066cc]"
          />
        </div>

        <button
          type="button"
          class="mb-2.5 flex w-full items-center justify-between rounded-[10px] border px-3 py-2 text-left transition-all duration-150"
          :class="isAllNodeActive ? 'detail-doc-entry--active' : 'detail-doc-entry--idle'"
          @click="emit('show-concat')"
        >
          <span class="flex min-w-0 items-center gap-2">
            <span
              class="flex h-7 w-7 items-center justify-center rounded-[8px]"
              :class="isAllNodeActive ? 'detail-doc-icon--active' : 'detail-doc-icon--idle'"
            >
              <FileTextOutlined />
            </span>
            <span class="min-w-0">
              <span class="block text-[12px] font-semibold">所有单据</span>
              <span class="block text-[10px] font-semibold text-slate-400">合并查看全文</span>
            </span>
          </span>
          <span
            class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500"
          >
            {{ totalDocCount }}
          </span>
        </button>

        <template v-if="displayTree.length > 0">
          <div class="space-y-1.5">
            <section
              v-for="group in displayTree"
              :key="group.key"
              class="rounded-[12px] border border-transparent"
            >
              <button
                type="button"
                class="detail-doc-group flex w-full items-center justify-between rounded-[10px] border border-transparent px-2.5 py-2 text-left text-[12px] font-semibold text-slate-700 transition-all duration-150"
                @click="toggleGroup(group.key)"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <CaretRightOutlined
                    class="text-[10px] text-slate-400 transition-transform duration-150"
                    :class="isGroupExpanded(group.key) ? 'rotate-90' : ''"
                  />
                  <span class="truncate">{{ group.label }}</span>
                </span>
                <span
                  class="ml-2 shrink-0 rounded-full bg-white/85 px-2 py-0.5 text-[10px] font-semibold text-slate-500 shadow-[0_1px_0_rgba(148,163,184,0.18)]"
                >{{ group.count }}</span>
              </button>

              <template v-if="isGroupExpanded(group.key) && group.subgroups?.length">
                <section
                  v-for="subgroup in group.subgroups"
                  :key="`${group.key}:${subgroup.key}`"
                  class="detail-doc-subgroup ml-2 mt-1 border-l border-blue-100/60 pl-1"
                >
                  <button
                    type="button"
                    class="detail-doc-group flex w-full items-center justify-between rounded-[10px] border border-transparent px-2 py-1.5 text-left text-[11px] font-semibold text-slate-600 transition-all duration-150"
                    @click="toggleGroup(subgroup.key)"
                  >
                    <span class="flex min-w-0 items-center gap-1.5">
                      <CaretRightOutlined
                        class="text-[9px] text-slate-400 transition-transform duration-150"
                        :class="isGroupExpanded(subgroup.key) ? 'rotate-90' : ''"
                      />
                      <span class="truncate">{{ subgroup.label }}</span>
                    </span>
                    <span
                      class="ml-2 shrink-0 rounded-full bg-white/85 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500"
                    >{{ subgroup.count }}</span>
                  </button>
                  <div
                    v-if="isGroupExpanded(subgroup.key)"
                    class="ml-1 mt-0.5 space-y-1 pl-1"
                  >
                    <button
                      v-for="node in subgroup.children"
                      :key="`${subgroup.key}:${node.id}`"
                      type="button"
                      class="group relative flex w-full items-start gap-2 rounded-[10px] border px-2 py-2 text-left transition-all duration-150"
                      :class="
                        hasDocContent(resolveDocByNode(node))
                          ? isActiveNode(node)
                            ? 'detail-doc-entry--active'
                            : 'detail-doc-entry--idle'
                          : 'cursor-default border-transparent bg-transparent text-slate-400/70'
                      "
                      @click="handleNodeClick(node)"
                    >
                      <span
                        class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] text-[12px]"
                        :class="
                          hasDocContent(resolveDocByNode(node))
                            ? isActiveNode(node)
                              ? 'detail-doc-icon--active'
                              : 'bg-white text-slate-400 group-hover:bg-blue-50 group-hover:text-[#0066cc]'
                            : 'bg-slate-100 text-slate-300'
                        "
                      >
                        <FileTextOutlined />
                      </span>
                      <span class="min-w-0 flex-1 overflow-hidden">
                        <span class="mb-0.5 block text-[10px] font-semibold text-slate-400">
                          {{ resolveNodeDateLabel(node) || '未标注时间' }}
                        </span>
                        <span class="block truncate text-[12px] font-bold leading-[1.45]">
                          {{ renderTreeNodePrimary(node) }}
                        </span>
                        <span
                          v-if="!hasDocContent(resolveDocByNode(node))"
                          class="mt-0.5 block text-[10px] font-semibold text-slate-300"
                        >
                          暂无正文
                        </span>
                        <span
                          v-else-if="node.projection_incomplete"
                          class="mt-0.5 block text-[10px] font-semibold text-amber-600"
                          :title="node.projection_notice || ''"
                        >
                          更多文书待查看
                        </span>
                      </span>
                    </button>
                  </div>
                </section>
              </template>
              <div
                v-else-if="isGroupExpanded(group.key)"
                class="ml-1 mt-0.5 space-y-1 pl-1"
              >
                <button
                  v-for="node in group.children"
                  :key="`${group.key}:${node.id}`"
                  type="button"
                  class="group relative flex w-full items-start gap-2 rounded-[10px] border px-2 py-2 text-left transition-all duration-150"
                  :class="
                    hasDocContent(resolveDocByNode(node))
                      ? isActiveNode(node)
                        ? 'detail-doc-entry--active'
                        : 'detail-doc-entry--idle'
                      : 'cursor-default border-transparent bg-transparent text-slate-400/70'
                  "
                  @click="handleNodeClick(node)"
                >
                  <span
                    class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] text-[12px]"
                    :class="
                      hasDocContent(resolveDocByNode(node))
                        ? isActiveNode(node)
                          ? 'detail-doc-icon--active'
                          : 'bg-white text-slate-400 group-hover:bg-blue-50 group-hover:text-[#0066cc]'
                        : 'bg-slate-100 text-slate-300'
                    "
                  >
                    <FileTextOutlined />
                  </span>
                  <span class="min-w-0 flex-1 overflow-hidden">
                    <span class="mb-0.5 block text-[10px] font-semibold text-slate-400">
                      {{ resolveNodeDateLabel(node) || '未标注时间' }}
                    </span>
                    <span class="block truncate text-[12px] font-bold leading-[1.45]">
                      {{ renderTreeNodePrimary(node) }}
                    </span>
                    <span
                      v-if="!hasDocContent(resolveDocByNode(node))"
                      class="mt-0.5 block text-[10px] font-semibold text-slate-300"
                    >
                      暂无正文
                    </span>
                    <span
                      v-else-if="node.projection_incomplete"
                      class="mt-0.5 block text-[10px] font-semibold text-amber-600"
                      :title="node.projection_notice || ''"
                    >
                      更多文书待查看
                    </span>
                  </span>
                </button>
              </div>
            </section>
          </div>
        </template>

        <template v-else>
          <div class="space-y-1">
            <div
              v-for="doc in documents"
              :key="doc.doc_key || doc.type + doc.label"
              :class="[
                'group relative flex items-center justify-between rounded-[10px] border px-2 py-1.5 transition-all duration-150',
                hasDocContent(doc)
                  ? isActive(doc)
                    ? 'cursor-pointer detail-doc-entry--active'
                    : 'cursor-pointer detail-doc-entry--idle'
                  : 'border-transparent bg-transparent text-slate-300',
              ]"
              @click="hasDocContent(doc) && $emit('preview-doc', doc)"
            >
              <span
                v-if="hasDocContent(doc)"
                class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r-full transition-all duration-150"
                :class="
                  isActive(doc) ? 'detail-doc-indicator--active' : 'detail-doc-indicator--idle'
                "
              />
              <span class="flex min-w-0 items-center gap-2">
                <span
                  class="flex h-6 w-6 items-center justify-center rounded-[8px]"
                  :class="
                    doc.has_content
                      ? isActive(doc)
                        ? 'detail-doc-icon--active'
                        : 'bg-slate-100 text-[#0066cc] group-hover:bg-blue-50'
                      : 'bg-slate-100 text-slate-300'
                  "
                >
                  <FileTextOutlined />
                </span>
                <span
                  :class="
                    hasDocContent(doc)
                      ? isActive(doc)
                        ? 'truncate text-[12px] font-bold text-[#0066cc]'
                        : 'truncate text-[12px] font-semibold text-slate-700'
                      : 'truncate text-[12px]'
                  "
                >
                  {{ resolveDocLabel(doc) }}
                </span>
              </span>

              <span
                v-if="hasDocContent(doc)"
                class="ml-2 flex shrink-0 items-center gap-1.5"
              >
                <span class="text-[10px] font-semibold text-slate-400">{{ doc.length }}字</span>
                <EyeOutlined class="text-[11px] text-slate-300 group-hover:text-[#0066cc]" />
              </span>
              <span
                v-else
                class="text-[11px] text-slate-200"
              >-</span>
            </div>

            <div
              v-if="!documentsLoading && documents.length === 0"
              class="py-4 text-center text-[12px] text-slate-400"
            >
              暂无病历文书
            </div>
          </div>
        </template>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  SyncOutlined,
  FileTextOutlined,
  EyeOutlined,
  CaretRightOutlined,
} from '@ant-design/icons-vue'
import type { PatientRecord, DocItem, DocTreeGroup, DocTreeNode } from '../types'
import { formatDocSortTime, resolveDocDisplayTitle } from '../utils/documentDisplay'

const props = defineProps<{
  record: PatientRecord | undefined
  documents: DocItem[]
  documentsTree: DocTreeGroup[]
  documentsLoading: boolean
  activeDocType?: string
}>()

const emit = defineEmits<{
  'preview-doc': [doc: DocItem]
  'show-concat': []
}>()

const displayTree = computed(() =>
  (props.documentsTree || []).filter(
    (group) =>
      group.key !== 'all' &&
      ((group.children || []).length > 0 ||
        (group.subgroups || []).some((subgroup) => (subgroup.children || []).length > 0)),
  ),
)
const totalDocCount = computed(
  () => props.documents.length || displayTree.value.reduce((sum, group) => sum + group.count, 0),
)
const expandedGroupKeys = ref<string[]>([])
const isAllNodeActive = computed(() => !String(props.activeDocType || '').trim())

watch(
  [displayTree, () => props.activeDocType],
  ([groups]) => {
    const keys = (groups || [])
      .flatMap((group) => [
        String(group.key || ''),
        ...(group.subgroups || []).map((subgroup) => String(subgroup.key || '')),
      ])
      .filter(Boolean)
    if (!keys.length) {
      expandedGroupKeys.value = []
      return
    }
    const kept = expandedGroupKeys.value.filter((key) => keys.includes(key))
    const activeGroup = findActiveGroupKey(groups || [])
    if (activeGroup && !kept.includes(activeGroup)) {
      kept.push(activeGroup)
    }
    const activeParent = (groups || []).find((group) =>
      (group.subgroups || []).some((subgroup) => subgroup.key === activeGroup),
    )
    if (activeParent && !kept.includes(activeParent.key)) kept.push(activeParent.key)
    if (!kept.length) {
      expandedGroupKeys.value = keys
      return
    }
    expandedGroupKeys.value = kept
  },
  { immediate: true },
)

function docIdentityKey(doc: DocItem) {
  return String(
    doc.doc_key ||
      `${doc.doc_type || doc.type || ''}::${doc.document_id || doc.id || doc.label || ''}`,
  )
}

function isActive(doc: DocItem) {
  return (props.activeDocType || '') === docIdentityKey(doc)
}

function hasDocContent(doc?: DocItem): boolean {
  if (!doc) return false
  if (typeof doc.has_content === 'boolean') return doc.has_content
  return Boolean((doc.content || '').trim() || Number(doc.length || 0) > 0)
}

function resolveDocLabel(doc: DocItem): string {
  return resolveDocDisplayTitle(doc)
}

function normalizeMatchText(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/\s+/g, ' ')
}

function resolveRawNodeTitle(node: DocTreeNode): string {
  const typedNode = node as unknown as Record<string, unknown>
  return (
    normalizeMatchText(node.title) ||
    normalizeMatchText(String(typedNode.label || '')) ||
    normalizeMatchText(String(typedNode.doc_name || ''))
  )
}

function resolveNodeTitle(node: DocTreeNode): string {
  const byNode = resolveRawNodeTitle(node)
  if (byNode && /[\u3400-\u9fff]/u.test(byNode)) return byNode
  const matched = resolveDocByNode(node)
  if (matched) return resolveDocLabel(matched)
  if (byNode) {
    const translated = resolveDocDisplayTitle({
      type: node.doc_type,
      label: byNode,
      doc_type: node.doc_type,
      document_title: byNode,
      content: null,
    })
    return translated || byNode
  }
  return String(node.doc_type || '').trim() || '未命名文书'
}

function resolveNodeDateLabel(node: DocTreeNode): string {
  const formatted = formatDocSortTime(node.record_time)
  if (!formatted) return ''
  return formatted.slice(0, 10)
}

function renderTreeNodePrimary(node: DocTreeNode): string {
  const dateLabel = resolveNodeDateLabel(node)
  const title = resolveNodeTitle(node)
  if (!dateLabel) return title
  if (!title.startsWith(dateLabel)) return title
  return title.slice(dateLabel.length).trim() || title
}

function resolveDocDateLabel(doc: DocItem): string {
  const formatted = formatDocSortTime(doc.record_time || doc.sort_time)
  if (!formatted) return ''
  return formatted.slice(0, 10)
}

function stripDatePrefix(title: string, dateLabel: string): string {
  if (!dateLabel || !title.startsWith(dateLabel)) return title
  return title.slice(dateLabel.length).trim()
}

function isSameDocTitle(nodeTitle: string, docTitle: string, dateLabel: string): boolean {
  const cleanNodeTitle = normalizeMatchText(stripDatePrefix(nodeTitle, dateLabel))
  const cleanDocTitle = normalizeMatchText(stripDatePrefix(docTitle, dateLabel))
  if (!cleanNodeTitle || !cleanDocTitle) return false
  return cleanNodeTitle.includes(cleanDocTitle) || cleanDocTitle.includes(cleanNodeTitle)
}

function resolveDocByNode(node: DocTreeNode): DocItem | undefined {
  const byDocKey = props.documents.find(
    (doc) => node.doc_key && (doc.doc_key || '') === node.doc_key,
  )
  if (byDocKey) return byDocKey

  const byIdentity = props.documents.find(
    (doc) =>
      (doc.document_id || doc.id || '') === node.id &&
      (doc.doc_type || doc.type || '') === node.doc_type,
  )
  if (byIdentity) return byIdentity

  const nodeDate = resolveNodeDateLabel(node)
  const nodeTitle = resolveRawNodeTitle(node)
  if (nodeDate && nodeTitle) {
    const byDateAndTitle = props.documents.find(
      (doc) =>
        resolveDocDateLabel(doc) === nodeDate &&
        isSameDocTitle(nodeTitle, resolveDocLabel(doc), nodeDate),
    )
    if (byDateAndTitle) return byDateAndTitle
  }

  const byTitle = props.documents.filter((doc) =>
    isSameDocTitle(nodeTitle, resolveDocLabel(doc), nodeDate),
  )
  if (byTitle.length === 1) return byTitle[0]

  const sameTypeDocs = props.documents.filter(
    (doc) => (doc.doc_type || doc.type || '') === node.doc_type,
  )
  if (sameTypeDocs.length === 1) return sameTypeDocs[0]

  return undefined
}

function isActiveNode(node: DocTreeNode) {
  const doc = resolveDocByNode(node)
  if (!doc) return false
  return isActive(doc)
}

function handleNodeClick(node: DocTreeNode) {
  const doc = resolveDocByNode(node)
  if (!doc || !hasDocContent(doc)) return
  emit('preview-doc', doc)
}

function findActiveGroupKey(groups: DocTreeGroup[]): string {
  for (const group of groups) {
    if ((group.children || []).some((node) => isActiveNode(node))) {
      return String(group.key || '')
    }
    const activeSubgroup = (group.subgroups || []).find((subgroup) =>
      (subgroup.children || []).some((node) => isActiveNode(node)),
    )
    if (activeSubgroup) return String(activeSubgroup.key || '')
  }
  return ''
}

function isGroupExpanded(groupKey: string): boolean {
  return expandedGroupKeys.value.includes(groupKey)
}

function toggleGroup(groupKey: string) {
  if (isGroupExpanded(groupKey)) {
    expandedGroupKeys.value = expandedGroupKeys.value.filter((key) => key !== groupKey)
    return
  }
  expandedGroupKeys.value = [...expandedGroupKeys.value, groupKey]
}
</script>

<style scoped>
.detail-apple-sidebar {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(255, 255, 255, 0.82) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.detail-apple-sidebar h3 {
  color: #1d1d1f !important;
  font-size: 14px !important;
  font-weight: 650 !important;
  letter-spacing: 0 !important;
  line-height: 20px !important;
}

.detail-apple-sidebar p {
  color: rgba(29, 29, 31, 0.45) !important;
  font-size: 11px !important;
  font-weight: 500 !important;
}

.detail-apple-sidebar button {
  font-family: inherit;
  letter-spacing: 0 !important;
}

.detail-apple-sidebar .font-semibold,
.detail-apple-sidebar .font-bold {
  font-weight: 600 !important;
}

.detail-apple-sidebar .font-semibold {
  font-weight: 500 !important;
}

.detail-apple-sidebar .text-slate-900,
.detail-apple-sidebar .text-slate-800,
.detail-apple-sidebar .text-slate-700 {
  color: #1d1d1f !important;
}

.detail-apple-sidebar .text-slate-600,
.detail-apple-sidebar .text-slate-500,
.detail-apple-sidebar .text-slate-400 {
  color: rgba(29, 29, 31, 0.56) !important;
}

.detail-apple-sidebar .text-slate-300,
.detail-apple-sidebar .text-slate-200 {
  color: rgba(29, 29, 31, 0.28) !important;
}

.detail-apple-sidebar .text-\[\#0066cc\] {
  color: #0066cc !important;
}

.detail-apple-sidebar .border-slate-200\/70,
.detail-apple-sidebar .border-slate-200\/80 {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.detail-apple-sidebar .bg-white,
.detail-apple-sidebar .bg-white\/75,
.detail-apple-sidebar .bg-white\/80,
.detail-apple-sidebar .bg-white\/85 {
  background: rgba(255, 255, 255, 0.72) !important;
}

.detail-apple-sidebar .bg-slate-100,
.detail-apple-sidebar .bg-blue-50 {
  background: rgba(0, 102, 204, 0.07) !important;
}

.detail-apple-sidebar button:hover {
  background: rgba(0, 0, 0, 0.035) !important;
  border-color: rgba(0, 0, 0, 0.1) !important;
  color: #1d1d1f !important;
}

.detail-apple-sidebar .detail-doc-entry--active {
  border-color: rgba(0, 102, 204, 0.18) !important;
  background: rgba(0, 102, 204, 0.07) !important;
  color: #0066cc !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    0 2px 10px rgba(0, 102, 204, 0.08) !important;
}

.detail-apple-sidebar .detail-doc-entry--idle,
.detail-apple-sidebar .detail-doc-group {
  border-color: transparent !important;
  background: transparent !important;
  color: rgba(29, 29, 31, 0.62) !important;
}

.detail-apple-sidebar .detail-doc-entry--idle:hover,
.detail-apple-sidebar .detail-doc-group:hover {
  border-color: rgba(0, 0, 0, 0.08) !important;
  background: rgba(0, 0, 0, 0.035) !important;
}

.detail-apple-sidebar .detail-doc-icon--active {
  background: rgba(0, 102, 204, 0.08) !important;
  color: #0066cc !important;
}

.detail-apple-sidebar .detail-doc-icon--idle {
  background: rgba(0, 0, 0, 0.04) !important;
  color: rgba(29, 29, 31, 0.52) !important;
}

.detail-apple-sidebar .detail-doc-indicator--active,
.detail-apple-sidebar .detail-doc-indicator--idle:hover {
  background: #0066cc !important;
}

.detail-apple-sidebar button:hover .text-slate-400,
.detail-apple-sidebar button:hover .text-slate-500,
.detail-apple-sidebar button:hover .text-slate-600,
.detail-apple-sidebar button:hover .text-slate-700 {
  color: #1d1d1f !important;
}

.detail-apple-sidebar button[class*='shadow-'] {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    0 2px 10px rgba(0, 102, 204, 0.08) !important;
}

.detail-apple-sidebar .border-l {
  border-left: 0 !important;
  margin-left: 4px !important;
  padding-left: 4px !important;
}

.detail-apple-sidebar .custom-scrollbar::-webkit-scrollbar-thumb,
.detail-apple-sidebar::-webkit-scrollbar-thumb {
  background: rgba(29, 29, 31, 0.18);
}
</style>
