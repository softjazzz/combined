<template>
  <aside
    class="custom-scrollbar w-[220px] min-w-[206px] max-w-[236px] shrink-0 overflow-y-auto border-r border-slate-200/70 bg-[linear-gradient(180deg,rgba(247,251,255,0.96),rgba(240,247,255,0.98))]"
  >
    <div
      v-if="record"
      class="flex h-full flex-col"
    >
      <div class="flex-1 px-2.5 pb-4 pt-3">
        <div class="mb-2.5 flex items-center justify-between px-1">
          <h3 class="m-0 text-[11px] font-black tracking-[0.16em] text-sky-700/75">
            病历文书
          </h3>
          <SyncOutlined
            v-if="documentsLoading"
            spin
            class="text-[12px] text-sky-600"
          />
        </div>

        <div
          class="mb-2 rounded-[8px] border border-slate-200/70 bg-white/90 px-2 py-1.5 text-[12px] text-slate-500"
        >
          所有单据
        </div>

        <template v-if="displayTree.length > 0">
          <div class="space-y-1">
            <button
              type="button"
              class="flex w-full items-center justify-between rounded-[8px] border px-2 py-1.5 text-left text-[12px] font-semibold transition-all duration-150"
              :class="
                isAllNodeActive
                  ? 'border-sky-200 bg-white text-sky-800 shadow-[0_6px_14px_rgba(14,165,233,0.12)]'
                  : 'border-transparent bg-transparent text-slate-700 hover:border-sky-100 hover:bg-white/75'
              "
              @click="emit('show-concat')"
            >
              <span>全部</span>
            </button>

            <section
              v-for="group in displayTree"
              :key="group.key"
              class="rounded-[8px]"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between rounded-[8px] border border-transparent px-2 py-1.5 text-left text-[12px] font-bold text-slate-700 transition-all duration-150 hover:border-sky-100 hover:bg-white/70"
                @click="toggleGroup(group.key)"
              >
                <span class="flex min-w-0 items-center gap-1.5">
                  <CaretRightOutlined
                    class="text-[10px] text-slate-400 transition-transform duration-150"
                    :class="isGroupExpanded(group.key) ? 'rotate-90' : ''"
                  />
                  <span class="truncate">{{ group.label }}</span>
                </span>
                <span class="ml-2 shrink-0 text-[10px] font-semibold text-slate-400">{{
                  group.count
                }}</span>
              </button>

              <div
                v-if="isGroupExpanded(group.key)"
                class="ml-3 mt-0.5 space-y-0.5 border-l border-slate-200/80 pl-2"
              >
                <button
                  v-for="node in group.children"
                  :key="`${group.key}:${node.id}`"
                  type="button"
                  class="group flex w-full items-center rounded-[8px] border px-2 py-1.5 text-left transition-all duration-150"
                  :class="
                    hasDocContent(resolveDocByNode(node))
                      ? isActiveNode(node)
                        ? 'border-sky-200 bg-white text-sky-800 shadow-[0_4px_10px_rgba(14,165,233,0.1)]'
                        : 'border-transparent bg-transparent text-slate-600 hover:border-sky-100 hover:bg-white/75'
                      : 'cursor-default border-transparent bg-transparent text-slate-300'
                  "
                  @click="handleNodeClick(node)"
                >
                  <span class="min-w-0 truncate text-[12px] font-semibold">
                    {{ renderTreeNodeTitle(node) }}
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

function resolveNodeTitle(node: DocTreeNode): string {
  const typedNode = node as unknown as Record<string, unknown>
  const byNode =
    String(node.title || '').trim() ||
    String(typedNode.label || '').trim() ||
    String(typedNode.doc_name || '').trim()
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

function renderTreeNodeTitle(node: DocTreeNode): string {
  const dateLabel = resolveNodeDateLabel(node)
  const title = resolveNodeTitle(node)
  if (!dateLabel || title.startsWith(dateLabel)) return title
  return `${dateLabel} ${title}`
}

function resolveDocByNode(node: DocTreeNode): DocItem | undefined {
  return (
    props.documents.find((doc) => (doc.doc_key || '') === node.doc_key) ||
    props.documents.find(
      (doc) =>
        (doc.document_id || doc.id || '') === node.id &&
        (doc.doc_type || doc.type || '') === node.doc_type,
    ) ||
    props.documents.find((doc) => (doc.doc_type || doc.type || '') === node.doc_type)
  )
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
