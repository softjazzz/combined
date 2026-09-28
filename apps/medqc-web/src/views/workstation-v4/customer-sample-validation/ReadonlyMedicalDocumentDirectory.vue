<template>
  <aside
    class="readonly-medical-document-directory"
    aria-label="病历文书目录"
  >
    <div class="readonly-medical-document-directory-head">
      <strong>文书目录</strong>
      <span>{{ filteredDocuments.length }} / {{ documents.length }}</span>
    </div>

    <div
      v-if="loading"
      class="readonly-medical-document-state"
    >
      正在读取病历文书…
    </div>
    <div
      v-else-if="error"
      class="readonly-medical-document-state is-error"
    >
      <span>{{ error }}</span>
      <button
        type="button"
        @click="emit('retry')"
      >
        重新读取
      </button>
    </div>
    <div
      v-else-if="!documents.length"
      class="readonly-medical-document-state"
    >
      当前未返回可查看的病历原文
    </div>
    <template v-else>
      <input
        v-model="query"
        type="search"
        class="readonly-medical-document-search"
        data-testid="record-document-search"
        placeholder="搜索标题、正文或医嘱"
      >
      <div class="readonly-medical-document-filter">
        <button
          type="button"
          data-testid="record-document-filter-all"
          :class="{ 'is-active': filter === 'all' }"
          @click="filter = 'all'"
        >
          全部
        </button>
        <button
          type="button"
          data-testid="record-document-filter-content"
          :class="{ 'is-active': filter === 'content' }"
          @click="filter = 'content'"
        >
          有正文
        </button>
        <button
          type="button"
          data-testid="record-document-filter-order"
          :class="{ 'is-active': filter === 'orders' }"
          @click="filter = 'orders'"
        >
          医嘱
        </button>
      </div>

      <div
        v-if="filteredDocuments.length"
        class="readonly-medical-document-groups record-document-groups is-tree editable-copy-document-directory-list"
      >
        <section
          v-for="group in documentGroups"
          :key="group.key"
          class="readonly-medical-document-group record-document-group"
        >
          <button
            type="button"
            class="readonly-medical-document-group-title record-document-group-title"
            :aria-expanded="isGroupExpanded(group.key)"
            :data-testid="`record-document-group-toggle-${group.key === 'orders' ? 'order' : group.key}`"
            @click="toggleGroup(group.key)"
          >
            <span>
              <i />
              <b
                class="readonly-medical-document-group-chevron"
                aria-hidden="true"
              >{{
                isGroupExpanded(group.key) ? '⌄' : '›'
              }}</b>
              {{ group.label }}
            </span>
            <em>{{ group.items.length }}</em>
          </button>
          <template v-if="isGroupExpanded(group.key) && group.subgroups?.length">
            <section
              v-for="subgroup in group.subgroups"
              :key="subgroup.key"
              class="readonly-medical-document-subgroup"
            >
              <button
                type="button"
                class="readonly-medical-document-group-title readonly-medical-document-subgroup-title"
                :aria-expanded="isGroupExpanded(subgroup.key)"
                :data-testid="`record-document-group-toggle-${subgroup.key}`"
                @click="toggleGroup(subgroup.key)"
              >
                <span>
                  <i />
                  <b
                    class="readonly-medical-document-group-chevron"
                    aria-hidden="true"
                  >{{
                    isGroupExpanded(subgroup.key) ? '⌄' : '›'
                  }}</b>
                  {{ subgroup.label }}
                </span>
                <em>{{ subgroup.items.length }}</em>
              </button>
              <template v-if="isGroupExpanded(subgroup.key)">
                <button
                  v-for="document in subgroup.items"
                  :key="document.key"
                  type="button"
                  class="readonly-medical-document-item record-document-item"
                  :class="{
                    'is-active': document.key === selectedKey,
                    'is-empty': !medicalDocumentHasContent(document),
                  }"
                  :disabled="!medicalDocumentHasContent(document)"
                  @click="emit('select', document.key)"
                >
                  <strong>{{ resolveMedicalDocumentTitle(document) }}</strong>
                  <small
                    class="readonly-medical-document-meta record-document-time"
                    :class="{ 'is-missing': !resolveMedicalDocumentTime(document) }"
                    :title="formatMedicalDocumentTime(resolveMedicalDocumentTime(document))"
                  >{{ formatDocumentMeta(document) }}</small>
                </button>
              </template>
            </section>
          </template>
          <template v-else-if="isGroupExpanded(group.key) && group.key === 'orders'">
            <button
              type="button"
              data-testid="record-document-order-group"
              class="readonly-medical-document-item record-document-item"
              :class="{ 'is-active': isOrderGroupSelected(group.items) }"
              @click="selectOrderGroup(group.items)"
            >
              <strong>医嘱（{{ group.items.length }}条）</strong>
              <small class="readonly-medical-document-meta record-document-time">
                点击查看长期/临时医嘱
              </small>
            </button>
          </template>
          <template v-else-if="isGroupExpanded(group.key)">
            <button
              v-for="document in group.items"
              :key="document.key"
              type="button"
              class="readonly-medical-document-item record-document-item"
              :class="{
                'is-active': document.key === selectedKey,
                'is-empty': !medicalDocumentHasContent(document),
              }"
              :disabled="!medicalDocumentHasContent(document)"
              @click="emit('select', document.key)"
            >
              <strong>{{ resolveMedicalDocumentTitle(document) }}</strong>
              <small
                class="readonly-medical-document-meta record-document-time"
                :class="{ 'is-missing': !resolveMedicalDocumentTime(document) }"
                :title="formatMedicalDocumentTime(resolveMedicalDocumentTime(document))"
              >
                {{ formatDocumentMeta(document) }}
              </small>
            </button>
          </template>
        </section>
      </div>
      <div
        v-else
        class="readonly-medical-document-state"
      >
        没有匹配的文书
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { EditableMedicalRecordDocument } from './types'
import {
  formatMedicalDocumentTime,
  isMedicalOrderDocument,
  medicalDocumentHasContent,
  resolveMedicalDocumentGroup,
  resolveMedicalDocumentTime,
  resolveMedicalDocumentTitle,
} from './medicalDocumentDisplay'

const props = withDefaults(
  defineProps<{
    documents: EditableMedicalRecordDocument[]
    selectedKey?: string
    loading?: boolean
    error?: string
  }>(),
  {
    selectedKey: '',
    loading: false,
    error: '',
  },
)

const emit = defineEmits<{
  (event: 'select', key: string): void
  (event: 'retry'): void
}>()

type DocumentFilter = 'all' | 'content' | 'orders'

const query = ref('')
const filter = ref<DocumentFilter>('all')
const expandedGroupKeys = ref(new Set<string>())

type DirectoryGroup = {
  key: string
  label: string
  items: EditableMedicalRecordDocument[]
  subgroups?: DirectoryGroup[]
}

const filteredDocuments = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return props.documents.filter((document) => {
    if (filter.value === 'content' && !medicalDocumentHasContent(document)) return false
    if (filter.value === 'orders' && !isMedicalOrderDocument(document)) return false
    if (!keyword) return true
    return [
      resolveMedicalDocumentTitle(document),
      document.title,
      document.document_type,
      document.content,
      ...(document.sections || []).flatMap((section) => [section.label, section.text]),
    ]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const documentGroups = computed(() => {
  const groups = new Map<string, DirectoryGroup>()
  const nestedGroups = new Map<string, Map<string, DirectoryGroup>>()
  filteredDocuments.value.forEach((document) => {
    const group = resolveMedicalDocumentGroup(document)
    if (group.parentKey) {
      const parentGroups = nestedGroups.get(group.parentKey) || new Map<string, DirectoryGroup>()
      const subgroup = parentGroups.get(group.key) || {
        key: group.key,
        label: group.label,
        items: [],
      }
      subgroup.items.push(document)
      parentGroups.set(group.key, subgroup)
      nestedGroups.set(group.parentKey, parentGroups)
      return
    }
    const current = groups.get(group.key) || { key: group.key, label: group.label, items: [] }
    current.items.push(document)
    groups.set(group.key, current)
  })
  for (const [parentKey, parentGroups] of nestedGroups) {
    const subgroupOrder =
      parentKey === 'admission'
        ? ['admission.record', 'admission.first']
        : ['course.senior', 'course.ordinary', 'course.other']
    const subgroups = subgroupOrder
      .map((key) => parentGroups.get(key))
      .filter((group): group is DirectoryGroup => Boolean(group))
    if (subgroups.length) {
      groups.set(parentKey, {
        key: parentKey,
        label: parentKey === 'admission' ? '入院与首次病程' : '日常病程与查房',
        items: subgroups.flatMap((subgroup) => subgroup.items),
        subgroups,
      })
    }
  }
  const order = [
    'frontpage',
    'admission',
    'course',
    'consultation',
    'surgery',
    'transfusion',
    'exam_lab',
    'discharge',
    'handoff',
    'other',
    'orders',
  ]
  return order
    .map((key) => groups.get(key))
    .filter((group): group is DirectoryGroup => Boolean(group))
})

function resolveGroupKey(document: EditableMedicalRecordDocument): string {
  return resolveMedicalDocumentGroup(document).key
}

function isGroupExpanded(groupKey: string): boolean {
  return expandedGroupKeys.value.has(groupKey)
}

function toggleGroup(groupKey: string) {
  const next = new Set(expandedGroupKeys.value)
  if (next.has(groupKey)) next.delete(groupKey)
  else next.add(groupKey)
  expandedGroupKeys.value = next
}

function syncExpandedGroups() {
  const groupKeys = documentGroups.value.flatMap((group) => [
    group.key,
    ...(group.subgroups || []).map((subgroup) => subgroup.key),
  ])
  const keyword = query.value.trim()
  if (keyword) {
    expandedGroupKeys.value = new Set(groupKeys)
    return
  }

  const selectedDocument = props.documents.find((document) => document.key === props.selectedKey)
  const selectedGroupKey = selectedDocument ? resolveGroupKey(selectedDocument) : ''
  if (selectedGroupKey && groupKeys.includes(selectedGroupKey)) {
    const selectedParent = documentGroups.value.find((group) =>
      (group.subgroups || []).some((subgroup) => subgroup.key === selectedGroupKey),
    )
    expandedGroupKeys.value = new Set(
      selectedParent ? [selectedParent.key, selectedGroupKey] : [selectedGroupKey],
    )
    return
  }

  if (!expandedGroupKeys.value.size && groupKeys[0]) {
    const firstGroup = documentGroups.value[0]
    expandedGroupKeys.value = new Set([
      groupKeys[0],
      ...(firstGroup?.subgroups || []).map((subgroup) => subgroup.key),
    ])
  }
}

watch(
  [
    () => props.selectedKey,
    query,
    filter,
    () =>
      documentGroups.value
        .flatMap((group) => [group.key, ...(group.subgroups || []).map((subgroup) => subgroup.key)])
        .join('|'),
  ],
  syncExpandedGroups,
  { immediate: true },
)

function formatDocumentMeta(document: EditableMedicalRecordDocument): string {
  const time = formatMedicalDocumentTime(resolveMedicalDocumentTime(document))
  const match = time.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/)
  if (!match) return time
  const monthDay = `${match[2].padStart(2, '0')}月${match[3].padStart(2, '0')}日`
  return Number(match[1]) === new Date().getFullYear() ? monthDay : `${match[1]}年${monthDay}`
}

function isOrderGroupSelected(items: EditableMedicalRecordDocument[]): boolean {
  return items.some((document) => document.key === props.selectedKey)
}

function selectOrderGroup(items: EditableMedicalRecordDocument[]) {
  const firstOrder = items[0]
  if (firstOrder) emit('select', firstOrder.key)
}
</script>

<style scoped>
.readonly-medical-document-directory {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.76);
}

.readonly-medical-document-directory-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 14px 10px;
}

.readonly-medical-document-directory-head strong {
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 700;
}

.readonly-medical-document-directory-head span {
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.08);
  padding: 2px 8px;
  color: #0a6cff;
  font-size: 12px;
  font-weight: 700;
}

.readonly-medical-document-search {
  width: calc(100% - 28px);
  height: 36px;
  margin: 0 14px 10px;
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: 8px;
  outline: none;
  background: #fff;
  padding: 0 11px;
  color: #1d1d1f;
  font: inherit;
  font-size: 13px;
}

.readonly-medical-document-search:focus {
  border-color: rgba(10, 108, 255, 0.42);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.08);
}

.readonly-medical-document-filter {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
  padding: 0 14px 10px;
}

.readonly-medical-document-filter button {
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.84);
  padding: 5px 4px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
}

.readonly-medical-document-filter button.is-active {
  border-color: rgba(10, 108, 255, 0.25);
  background: rgba(10, 108, 255, 0.09);
  color: #0a6cff;
}

.readonly-medical-document-groups {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 2px 12px 14px 18px;
}

.readonly-medical-document-group + .readonly-medical-document-group {
  margin-top: 4px;
}

.readonly-medical-document-subgroup {
  margin-left: 10px;
  border-left: 1px solid rgba(10, 108, 255, 0.12);
  padding-left: 6px;
}

.readonly-medical-document-subgroup-title {
  padding-top: 8px;
  color: rgba(29, 29, 31, 0.62);
}

.readonly-medical-document-group-title {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border: 0;
  background: transparent;
  padding: 12px 6px 6px 0;
  color: rgba(29, 29, 31, 0.54);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.readonly-medical-document-group-title span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.readonly-medical-document-group-title i {
  width: 7px;
  height: 7px;
  border: 2px solid rgba(10, 108, 255, 0.55);
  border-radius: 999px;
  background: #fff;
}

.readonly-medical-document-group-chevron {
  display: inline-grid;
  width: 10px;
  place-items: center;
  color: rgba(29, 29, 31, 0.56);
  font-size: 16px;
  font-weight: 600;
  line-height: 1;
}

.readonly-medical-document-group-title:hover .readonly-medical-document-group-chevron {
  color: #0a6cff;
}

.readonly-medical-document-group-title em {
  font-style: normal;
}

.readonly-medical-document-item {
  position: relative;
  display: grid;
  width: calc(100% - 10px);
  margin: 0 0 5px 10px;
  gap: 3px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  padding: 8px 9px 8px 16px;
  text-align: left;
  cursor: pointer;
}

.readonly-medical-document-item::before {
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -6px;
  width: 1px;
  background: rgba(10, 108, 255, 0.16);
  content: '';
}

.readonly-medical-document-item::after {
  position: absolute;
  top: 19px;
  left: -6px;
  width: 12px;
  height: 1px;
  background: rgba(10, 108, 255, 0.2);
  content: '';
}

.readonly-medical-document-item:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.035);
}

.readonly-medical-document-item.is-active {
  border-color: rgba(10, 108, 255, 0.22);
  background: rgba(10, 108, 255, 0.09);
}

.readonly-medical-document-item.is-empty {
  cursor: not-allowed;
  opacity: 0.56;
}

.readonly-medical-document-item strong,
.readonly-medical-document-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.readonly-medical-document-item strong {
  color: rgba(29, 29, 31, 0.86);
  font-size: 13px;
  line-height: 20px;
}

.readonly-medical-document-meta {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
}

.readonly-medical-document-meta.is-missing {
  color: #a16207;
}

.readonly-medical-document-item.is-active strong,
.readonly-medical-document-item.is-active .readonly-medical-document-meta {
  color: #0a6cff;
}

.readonly-medical-document-state {
  display: grid;
  min-height: 120px;
  place-content: center;
  gap: 10px;
  padding: 18px;
  color: rgba(29, 29, 31, 0.55);
  font-size: 13px;
  text-align: center;
}

.readonly-medical-document-state button {
  border: 0;
  background: transparent;
  color: #0a6cff;
  cursor: pointer;
}

.readonly-medical-document-state.is-error {
  color: #b42318;
}
</style>
