<template>
  <aside
    class="custom-scrollbar w-[220px] min-w-[220px] max-w-[220px] basis-[220px] shrink-0 overflow-y-auto border-r border-slate-200/70 bg-[linear-gradient(180deg,rgba(247,251,255,0.96),rgba(240,247,255,0.98))]"
  >
    <div
      v-if="record"
      class="flex h-full flex-col"
    >
      <div class="flex-1 px-2.5 pb-4 pt-3">
        <div class="mb-3 flex items-center justify-between px-1">
          <div>
            <h3 class="m-0 text-[13px] font-black text-slate-900">
              病历文书
            </h3>
            <p class="m-0 mt-0.5 text-[11px] font-semibold text-slate-400">
              按文书类型分组
            </p>
          </div>
          <SyncOutlined
            v-if="documentsLoading"
            spin
            class="text-[12px] text-sky-600"
          />
        </div>

        <button
          type="button"
          class="mb-2.5 flex w-full items-center justify-between rounded-[10px] border px-3 py-2 text-left transition-all duration-150"
          :class="
            isAllNodeActive
              ? 'border-sky-200 bg-white text-sky-800 shadow-[0_8px_18px_rgba(14,165,233,0.12)]'
              : 'border-slate-200/70 bg-white/80 text-slate-600 hover:border-sky-100 hover:bg-white'
          "
          @click="emit('show-concat')"
        >
          <span class="flex min-w-0 items-center gap-2">
            <span
              class="flex h-7 w-7 items-center justify-center rounded-[8px]"
              :class="isAllNodeActive ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-500'"
            >
              <FileTextOutlined />
            </span>
            <span class="min-w-0">
              <span class="block text-[12px] font-black">所有单据</span>
              <span class="block text-[10px] font-semibold text-slate-400">合并查看全文</span>
            </span>
          </span>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-black text-slate-500">
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
                class="flex w-full items-center justify-between rounded-[10px] border border-transparent px-2.5 py-2 text-left text-[12px] font-black text-slate-700 transition-all duration-150 hover:border-sky-100 hover:bg-white/75"
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
                  class="ml-2 shrink-0 rounded-full bg-white/85 px-2 py-0.5 text-[10px] font-black text-slate-500 shadow-[0_1px_0_rgba(148,163,184,0.18)]"
                >{{ group.count }}</span>
              </button>

              <div
                v-if="isGroupExpanded(group.key)"
                class="ml-3 mt-0.5 space-y-1 border-l border-slate-200/80 pl-2"
              >
                <button
                  v-for="node in group.children"
                  :key="`${group.key}:${node.id}`"
                  type="button"
                  class="group relative flex w-full items-start gap-2 rounded-[10px] border px-2 py-2 text-left transition-all duration-150"
                  :class="
                    hasDocContent(resolveDocByNode(node))
                      ? isActiveNode(node)
                        ? 'border-sky-200 bg-white text-sky-800 shadow-[0_6px_14px_rgba(14,165,233,0.12)]'
                        : 'border-transparent bg-transparent text-slate-600 hover:border-sky-100 hover:bg-white/75'
                      : 'cursor-default border-transparent bg-transparent text-slate-400/70'
                  "
                  @click="handleNodeClick(node)"
                >
                  <span
                    class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[8px] text-[12px]"
                    :class="
                      hasDocContent(resolveDocByNode(node))
                        ? isActiveNode(node)
                          ? 'bg-sky-100 text-sky-700'
                          : 'bg-white text-slate-400 group-hover:bg-blue-50 group-hover:text-blue-600'
                        : 'bg-slate-100 text-slate-300'
                    "
                  >
                    <FileTextOutlined />
                  </span>
                  <span class="min-w-0 flex-1 overflow-hidden">
                    <span class="mb-0.5 block text-[10px] font-black text-slate-400">
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
                    ? 'cursor-pointer border-sky-200 bg-white text-sky-800 shadow-[0_6px_14px_rgba(14,165,233,0.12)]'
                    : 'cursor-pointer border-transparent bg-transparent hover:border-sky-100 hover:bg-white/75'
                  : 'border-transparent bg-transparent text-slate-300',
              ]"
              @click="hasDocContent(doc) && $emit('preview-doc', doc)"
            >
              <span
                v-if="hasDocContent(doc)"
                class="absolute left-0 top-1.5 bottom-1.5 w-[2px] rounded-r-full transition-all duration-150"
                :class="isActive(doc) ? 'bg-sky-500' : 'bg-transparent group-hover:bg-sky-300'"
              />
              <span class="flex min-w-0 items-center gap-2">
                <span
                  class="flex h-6 w-6 items-center justify-center rounded-[8px]"
                  :class="
                    doc.has_content
                      ? isActive(doc)
                        ? 'bg-sky-100 text-sky-700'
                        : 'bg-slate-100 text-blue-600 group-hover:bg-blue-50'
                      : 'bg-slate-100 text-slate-300'
                  "
                >
                  <FileTextOutlined />
                </span>
                <span
                  :class="
                    hasDocContent(doc)
                      ? isActive(doc)
                        ? 'truncate text-[12px] font-bold text-sky-800'
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
                <EyeOutlined class="text-[11px] text-slate-300 group-hover:text-blue-400" />
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
import { formatDocSortTime } from '../utils/documentDisplay'

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
    (group) => group.key !== 'all' && (group.children || []).length > 0,
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
    const keys = (groups || []).map((group) => String(group.key || '')).filter(Boolean)
    if (!keys.length) {
      expandedGroupKeys.value = []
      return
    }
    const kept = expandedGroupKeys.value.filter((key) => keys.includes(key))
    const activeGroup = findActiveGroupKey(groups || [])
    if (activeGroup && !kept.includes(activeGroup)) {
      kept.push(activeGroup)
    }
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
  return (
    String(doc.label || '').trim() ||
    String(doc.doc_name || '').trim() ||
    String(doc.document_title || '').trim() ||
    String(doc.doc_type || doc.type || '').trim() ||
    String(doc.id || doc.document_id || '').trim() ||
    '未命名文书'
  )
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
  if (byNode) return byNode
  const matched = resolveDocByNode(node)
  if (matched) return resolveDocLabel(matched)
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
