<template>
  <div
    ref="viewerRef"
    class="emr-viewer"
  >
    <div
      v-if="!hideDocTabs && documents.length > 1"
      class="mb-5"
    >
      <div
        class="inline-flex items-center gap-1 rounded-xl border border-gray-100/50 bg-gray-100/80 p-1"
      >
        <button
          v-for="doc in documents"
          :key="doc.id"
          :class="[
            'rounded-lg px-4 py-1.5 text-[13px] font-medium whitespace-nowrap transition-all duration-200',
            activeDocId === doc.id
              ? 'bg-white text-blue-700 shadow-[0_1px_3px_rgba(0,0,0,0.08)]'
              : 'text-gray-500 hover:text-gray-700',
          ]"
          @click="handleSwitchDoc(doc)"
        >
          {{ doc.doc_name || doc.doc_type }}
        </button>
      </div>
    </div>

    <div
      v-if="loading"
      class="flex h-64 items-center justify-center"
    >
      <a-spin tip="正在加载文书内容..." />
    </div>

    <div
      v-else-if="isStructuredLayout"
      ref="contentRef"
      class="emr-struct overflow-auto"
      :style="{ maxHeight: maxHeight + 'px' }"
    >
      <div class="emr-struct__header">
        <div class="emr-struct__title">
          {{ metadata.doc_name || metadata.doc_type || '病历文书' }}
        </div>
        <div
          v-if="metadata.record_time"
          class="emr-struct__time"
        >
          记录时间：{{ metadata.record_time }}
        </div>
      </div>

      <section
        v-for="block in renderBlocks"
        :key="block.block_id"
        class="emr-struct__block"
      >
        <template v-if="block.block_type === 'kv_section'">
          <h4 class="emr-struct__block-title">
            {{ block.title || '基础信息' }}
          </h4>
          <div
            v-if="(block.fields || []).length > 0"
            class="emr-struct__kv-grid"
          >
            <div
              v-for="field in block.fields || []"
              :key="`${block.block_id}:${field.key}`"
              class="emr-struct__kv-row"
              :data-field-value="field.value || ''"
            >
              <span class="emr-struct__kv-label">{{ field.label }}</span>
              <span class="emr-struct__kv-value">{{ field.value || '-' }}</span>
            </div>
          </div>
          <div
            v-else
            class="emr-struct__empty"
          >
            暂无结构化字段
          </div>
        </template>

        <template v-else-if="block.block_type === 'order_table'">
          <h4 class="emr-struct__block-title">
            {{ block.title || '医嘱' }}
          </h4>
          <div
            v-if="(block.rows || []).length > 0"
            class="emr-struct__table-wrap"
          >
            <table class="emr-struct__table">
              <thead>
                <tr>
                  <th
                    v-for="col in block.columns || []"
                    :key="col.key"
                  >
                    {{ col.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, rowIdx) in block.rows || []"
                  :key="`${block.block_id}:row:${rowIdx}`"
                >
                  <td
                    v-for="col in block.columns || []"
                    :key="`${block.block_id}:row:${rowIdx}:${col.key}`"
                  >
                    {{ row[col.key] || '-' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div
            v-else
            class="emr-struct__empty"
          >
            {{ block.empty_text || '暂无医嘱数据' }}
          </div>
        </template>

        <template v-else>
          <h4 class="emr-struct__block-title">
            {{ block.title || '正文' }}
          </h4>
          <div
            class="emr-struct__paragraph"
            :data-anchor-text="(block.text || '').slice(0, 80)"
            v-html="renderParagraphContent(block.text || '')"
          />
        </template>
      </section>
    </div>

    <div
      v-else-if="renderedContent"
      ref="contentRef"
      class="emr-content overflow-auto"
      :style="{ maxHeight: maxHeight + 'px' }"
      v-html="renderedContent"
    />

    <div
      v-else
      class="flex h-64 flex-col items-center justify-center text-gray-400"
    >
      <FileTextOutlined class="mb-3 text-4xl" />
      <p>暂无文书内容</p>
      <p class="text-xs">
        请在左侧选择病历
      </p>
    </div>

    <div
      v-if="showAnnotationPanel && annotations.length > 0"
      class="annotation-panel fixed right-4 bottom-4 z-50 max-h-[26rem] w-72 overflow-hidden rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] shadow-[0_16px_34px_rgba(15,23,42,0.14)] backdrop-blur-xl"
    >
      <div
        class="flex items-center justify-between border-b border-slate-200/80 bg-white/72 px-4 py-3"
      >
        <span class="text-sm font-bold text-slate-700">缺陷标注 ({{ annotations.length }})</span>
        <button
          class="text-slate-400 transition-colors hover:text-slate-600"
          @click="showAnnotationPanel = false"
        >
          ✕
        </button>
      </div>
      <div class="max-h-80 divide-y divide-slate-100 overflow-y-auto">
        <div
          v-for="ann in annotations"
          :key="ann.defect_id"
          :class="[
            'cursor-pointer px-4 py-3 text-sm transition-colors',
            activeDefectId === ann.defect_id ? 'bg-blue-50/80' : 'hover:bg-slate-50/80',
          ]"
          @click="handleAnnotationClick(ann)"
        >
          <div class="mb-1 flex items-center gap-2">
            <span
              :class="[
                'h-2 w-2 rounded-full',
                ann.severity === 'critical'
                  ? 'bg-blue-700'
                  : ann.severity === 'error'
                    ? 'bg-blue-600'
                    : ann.severity === 'warning'
                      ? 'bg-blue-500'
                      : 'bg-blue-400',
              ]"
            />
            <span class="truncate font-medium text-slate-700">{{
              ann.rule_name || ann.category
            }}</span>
          </div>
          <p class="line-clamp-2 text-xs text-slate-500">
            {{ ann.description }}
          </p>
        </div>
      </div>
    </div>

    <button
      v-if="annotations.length > 0 && !showAnnotationPanel"
      class="fixed right-4 bottom-4 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-white shadow-[0_12px_24px_rgba(37,99,235,0.22)] transition-all hover:scale-105 hover:bg-blue-700"
      @click="showAnnotationPanel = true"
    >
      <span class="text-sm font-bold">{{ annotations.length }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { useDefectHighlight } from '@/composables/useDefectHighlight'
import type { DefectAnnotation } from '@/composables/useDefectHighlight'
import { getAccessToken } from '@/utils/auth-token'

interface EmrDocumentSummary {
  id: string
  doc_type: string
  doc_name: string
  doc_key?: string
  has_content?: boolean
}

interface EmrKvField {
  key: string
  label: string
  value: string
}

interface EmrTableColumn {
  key: string
  label: string
}

interface EmrRenderBlock {
  block_id: string
  block_type: 'kv_section' | 'paragraph' | 'order_table'
  title?: string
  fields?: EmrKvField[]
  text?: string
  columns?: EmrTableColumn[]
  rows?: Array<Record<string, string>>
  empty?: boolean
  empty_text?: string
}

const props = withDefaults(
  defineProps<{
    recordId?: string
    visitId?: string
    patientId?: string
    instituteId?: string
    docType?: string
    activeDocKey?: string
    maxHeight?: number
    hideDocTabs?: boolean
  }>(),
  {
    maxHeight: 600,
    hideDocTabs: false,
  },
)

const emit = defineEmits<{
  (e: 'defect-click', defectId: string): void
  (e: 'loaded', data: any): void
  (e: 'error', reason?: string): void
}>()

const loading = ref(false)
const rawContent = ref('')
const contentType = ref<'text' | 'html'>('text')
const metadata = ref<Record<string, string>>({})
const annotations = ref<DefectAnnotation[]>([])
const documents = ref<EmrDocumentSummary[]>([])
const activeDocId = ref<string | null>(null)
const showAnnotationPanel = ref(false)
const layoutVersion = ref('')
const renderBlocks = ref<EmrRenderBlock[]>([])
const boundClickContainer = ref<HTMLElement | null>(null)

const viewerRef = ref<HTMLElement>()
const contentRef = ref<HTMLElement>()

const { activeDefectId, highlightDefects, scrollToDefect, onDefectClick, bindClickEvents } =
  useDefectHighlight()

const effectiveRecordId = computed(() => props.recordId || props.visitId || '')
const hasTripletContext = computed(() => !!(props.visitId && props.patientId && props.instituteId))

const baseQueryString = computed(() => {
  const params = new URLSearchParams()
  if (props.visitId) params.append('visit_id', props.visitId)
  if (props.patientId) params.append('patient_id', props.patientId)
  if (props.instituteId) params.append('institute_id', props.instituteId)
  return params.toString()
})

const renderedContent = computed(() => {
  if (!rawContent.value) return ''
  if (contentType.value === 'html') return rawContent.value
  return highlightDefects(rawContent.value, annotations.value)
})

const isStructuredLayout = computed(
  () => layoutVersion.value === 'bundle_struct_v1' && renderBlocks.value.length > 0,
)

function buildUrl(path: 'documents' | 'render', extraParams?: Record<string, string>) {
  const baseId = effectiveRecordId.value
  if (!baseId) return ''
  const params = new URLSearchParams(baseQueryString.value)
  Object.entries(extraParams || {}).forEach(([key, value]) => {
    if (value) params.append(key, value)
  })
  const query = params.toString()
  return `/api/v1/emr/${encodeURIComponent(baseId)}/${path}${query ? `?${query}` : ''}`
}

function docIdentityKey(doc: EmrDocumentSummary): string {
  return String(doc.doc_key || `${doc.doc_type || ''}::${doc.id || ''}`)
}

function resetViewerState() {
  rawContent.value = ''
  contentType.value = 'text'
  metadata.value = {}
  annotations.value = []
  documents.value = []
  activeDocId.value = null
  layoutVersion.value = ''
  renderBlocks.value = []
}

function getAuthHeaders(): Record<string, string> {
  const token = getAccessToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

function readEnvelopeMessage(result: unknown, fallbackMessage: string): string {
  if (!result || typeof result !== 'object') return fallbackMessage
  const envelope = result as {
    message?: unknown
    normalized?: {
      message?: unknown
    }
  }
  const normalizedMessage = envelope.normalized?.message
  if (typeof normalizedMessage === 'string' && normalizedMessage.trim()) return normalizedMessage
  if (typeof envelope.message === 'string' && envelope.message.trim()) return envelope.message
  return fallbackMessage
}

function findDocByActiveKey(activeKey?: string): EmrDocumentSummary | undefined {
  if (!activeKey) return undefined
  return documents.value.find((doc) => docIdentityKey(doc) === activeKey)
}

function pickInitialDocument(): EmrDocumentSummary | undefined {
  const byExternal = findDocByActiveKey(props.activeDocKey)
  if (byExternal) return byExternal
  if (props.docType) {
    const byType = documents.value.find((doc) => doc.doc_type === props.docType)
    if (byType) return byType
  }
  return documents.value.find((doc) => doc.has_content) || documents.value[0]
}

async function fetchDocuments() {
  const url = buildUrl('documents')
  if (!url) {
    resetViewerState()
    emit('error', 'missing-identifiers')
    return
  }

  try {
    const response = await fetch(url, {
      headers: getAuthHeaders(),
    })
    const result = await response.json()
    if (response.status === 401 || response.status === 403) {
      emit('error', 'unauthorized')
      return
    }
    if (result?.success === false) {
      emit('error', readEnvelopeMessage(result, 'load-documents-failed'))
      return
    }
    const payload = result?.data || {}
    const docList = Array.isArray(payload.documents)
      ? payload.documents
      : Array.isArray(payload)
        ? payload
        : []
    documents.value = docList
    const target = pickInitialDocument()
    if (!target) {
      rawContent.value = ''
      annotations.value = []
      renderBlocks.value = []
      layoutVersion.value = String(payload.layout_version || '')
      emit('error', 'no-documents')
      return
    }
    activeDocId.value = target.id || null
    await loadDocument(target)
  } catch (err) {
    console.error('获取文书列表失败:', err)
    emit('error', 'load-documents-failed')
  }
}

function bindHighlightClicks() {
  const container = contentRef.value
  if (!container) return
  if (boundClickContainer.value === container) return
  bindClickEvents(container)
  boundClickContainer.value = container
}

async function loadDocument(doc?: EmrDocumentSummary) {
  if (!doc) return
  loading.value = true
  activeDocId.value = doc.id || null
  try {
    const extraParams: Record<string, string> = {}
    if (doc.doc_type) extraParams.doc_type = doc.doc_type
    if (doc.id) extraParams.doc_id = doc.id
    const url = buildUrl('render', extraParams)
    if (!url) {
      emit('error', 'missing-identifiers')
      return
    }

    const response = await fetch(url, {
      headers: getAuthHeaders(),
    })
    const result = await response.json()
    if (response.status === 401 || response.status === 403) {
      emit('error', 'unauthorized')
      return
    }
    if (result?.success === false || !result?.data) {
      emit('error', readEnvelopeMessage(result, 'load-document-failed'))
      return
    }

    const data = result.data
    rawContent.value = data.content || ''
    contentType.value = data.content_type || 'text'
    metadata.value = data.metadata || {}
    annotations.value = data.defect_annotations || []
    layoutVersion.value = data.layout_version || ''
    renderBlocks.value = Array.isArray(data.render_blocks) ? data.render_blocks : []

    if (rawContent.value || renderBlocks.value.length > 0) {
      emit('loaded', data)
    } else {
      emit('error', 'empty-content')
    }

    nextTick(() => {
      bindHighlightClicks()
    })
  } catch (err) {
    console.error('加载文书内容失败:', err)
    emit('error', 'load-document-failed')
  } finally {
    loading.value = false
  }
}

function handleSwitchDoc(doc: EmrDocumentSummary) {
  void loadDocument(doc)
}

function scrollStructuredByKeyword(keyword?: string): boolean {
  const text = String(keyword || '').trim()
  const container = contentRef.value
  if (!text || !container) return false
  const candidates = Array.from(
    container.querySelectorAll<HTMLElement>('[data-anchor-text], [data-field-value], .emr-defect'),
  )
  const hit = candidates.find((item) => (item.textContent || '').includes(text))
  if (!hit) return false
  hit.scrollIntoView({ behavior: 'smooth', block: 'center' })
  hit.style.outline = '2px solid #3b82f6'
  hit.style.outlineOffset = '2px'
  setTimeout(() => {
    hit.style.outline = 'none'
  }, 1500)
  return true
}

function handleAnnotationClick(ann: DefectAnnotation) {
  const scrolled = isStructuredLayout.value ? scrollStructuredByKeyword(ann.keyword) : false
  if (!scrolled) {
    scrollToDefect(ann.defect_id, contentRef.value)
  }
  emit('defect-click', ann.defect_id)
}

function renderParagraphContent(text: string): string {
  const normalized = String(text || '')
  if (!normalized) return ''
  const localAnnotations: DefectAnnotation[] = []
  for (const ann of annotations.value) {
    const keyword = String(ann.keyword || '').trim()
    if (!keyword) continue
    const index = normalized.indexOf(keyword)
    if (index < 0) continue
    localAnnotations.push({
      ...ann,
      start_offset: index,
      end_offset: index + keyword.length,
    })
  }
  return highlightDefects(normalized, localAnnotations)
}

function scrollTo(defectId: string) {
  if (isStructuredLayout.value) {
    const ann = annotations.value.find((item) => item.defect_id === defectId)
    if (ann && scrollStructuredByKeyword(ann.keyword)) return
  }
  scrollToDefect(defectId, contentRef.value)
}

defineExpose({ scrollTo, loadDocument })

onDefectClick((defectId) => {
  emit('defect-click', defectId)
})

watch(
  () => [props.recordId, props.visitId, props.patientId, props.instituteId, props.docType],
  () => {
    if (effectiveRecordId.value || hasTripletContext.value) {
      void fetchDocuments()
    } else {
      resetViewerState()
    }
  },
  { immediate: true },
)

watch(
  () => props.activeDocKey,
  (newKey) => {
    const doc = findDocByActiveKey(newKey)
    if (!doc) return
    if (activeDocId.value && doc.id === activeDocId.value) return
    void loadDocument(doc)
  },
)
</script>

<style scoped>
.emr-content,
.emr-struct {
  margin: 0 auto;
  max-width: 104ch;
  border: 1px solid rgba(226, 232, 240, 0.56);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(252, 253, 255, 0.98));
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.025);
  padding: 12px 14px 22px;
  color: #475569;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'SimSun', serif;
  font-size: 14px;
  line-height: 1.9;
  word-break: break-all;
}

.emr-content {
  white-space: pre-wrap;
}

.emr-struct__header {
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
  padding-bottom: 10px;
}

.emr-struct__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.emr-struct__time {
  margin-top: 3px;
  font-size: 12px;
  color: #64748b;
}

.emr-struct__block {
  margin-bottom: 12px;
  border: 1px solid rgba(226, 232, 240, 0.62);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  padding: 10px 12px;
}

.emr-struct__block-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.emr-struct__kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 14px;
}

.emr-struct__kv-row {
  display: grid;
  grid-template-columns: 88px 1fr;
  align-items: start;
  gap: 8px;
}

.emr-struct__kv-label {
  color: #64748b;
  font-weight: 600;
}

.emr-struct__kv-value {
  color: #334155;
}

.emr-struct__paragraph {
  white-space: pre-wrap;
  color: #334155;
}

.emr-struct__table-wrap {
  overflow-x: auto;
}

.emr-struct__table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
}

.emr-struct__table th,
.emr-struct__table td {
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  padding: 6px 8px;
  text-align: left;
  color: #334155;
}

.emr-struct__table th {
  background: rgba(248, 250, 252, 0.9);
  color: #64748b;
  font-weight: 700;
}

.emr-struct__empty {
  border: 1px dashed rgba(148, 163, 184, 0.45);
  border-radius: 8px;
  padding: 10px;
  text-align: center;
  color: #94a3b8;
  font-size: 12px;
}

.emr-content :deep(.emr-section-title),
.emr-struct :deep(.emr-section-title) {
  display: block;
  margin-top: 1.15em;
  margin-bottom: 0.1em;
  color: #1e293b;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.emr-content :deep(.emr-section-title:first-child),
.emr-struct :deep(.emr-section-title:first-child) {
  margin-top: 0;
}

.emr-content :deep(.emr-defect),
.emr-struct :deep(.emr-defect) {
  position: relative;
  cursor: help;
  border-bottom: 1.5px dashed;
  padding-bottom: 1px;
  transition:
    background-color 0.15s,
    border-color 0.15s;
}

.emr-content :deep(.emr-defect--critical),
.emr-struct :deep(.emr-defect--critical) {
  background-color: rgba(219, 234, 254, 0.82);
  border-color: #2563eb;
}

.emr-content :deep(.emr-defect--error),
.emr-struct :deep(.emr-defect--error) {
  background-color: rgba(239, 246, 255, 0.82);
  border-color: #3b82f6;
}

.emr-content :deep(.emr-defect--warning),
.emr-struct :deep(.emr-defect--warning) {
  background-color: rgba(239, 246, 255, 0.62);
  border-color: #60a5fa;
}

.emr-content :deep(.emr-defect--info),
.emr-struct :deep(.emr-defect--info) {
  background-color: rgba(239, 246, 255, 0.52);
  border-color: #3b82f6;
}

.emr-content :deep(.emr-defect:hover),
.emr-struct :deep(.emr-defect:hover) {
  filter: brightness(0.97);
}

.emr-content :deep(.emr-defect-tip),
.emr-struct :deep(.emr-defect-tip) {
  display: none;
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 200;
  width: 260px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
  padding: 11px 13px;
  pointer-events: none;
  white-space: normal;
  word-break: break-all;
}

.emr-content :deep(.emr-defect:hover .emr-defect-tip),
.emr-struct :deep(.emr-defect:hover .emr-defect-tip) {
  display: block;
}

.emr-content :deep(.emr-defect-tip__header),
.emr-struct :deep(.emr-defect-tip__header) {
  display: flex;
  align-items: center;
  margin-bottom: 7px;
  border-bottom: 1px solid #f1f5f9;
  padding-bottom: 7px;
  font-size: 11px;
  font-weight: 700;
}

.emr-content :deep(.emr-defect-tip__header--critical),
.emr-struct :deep(.emr-defect-tip__header--critical) {
  color: #1d4ed8;
}

.emr-content :deep(.emr-defect-tip__header--error),
.emr-struct :deep(.emr-defect-tip__header--error) {
  color: #2563eb;
}

.emr-content :deep(.emr-defect-tip__header--warning),
.emr-struct :deep(.emr-defect-tip__header--warning) {
  color: #3b82f6;
}

.emr-content :deep(.emr-defect-tip__header--info),
.emr-struct :deep(.emr-defect-tip__header--info) {
  color: #2563eb;
}

.emr-content :deep(.emr-defect-tip__body),
.emr-struct :deep(.emr-defect-tip__body) {
  color: #475569;
  font-size: 12.5px;
  line-height: 1.6;
}

.emr-content :deep(.emr-defect-tip__suggest),
.emr-struct :deep(.emr-defect-tip__suggest) {
  margin-top: 7px;
  border-top: 1px solid #f1f5f9;
  padding-top: 7px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}

@media (max-width: 960px) {
  .emr-content,
  .emr-struct {
    max-width: none;
    padding: 12px 14px 18px;
  }

  .emr-struct__kv-grid {
    grid-template-columns: 1fr;
  }
}
</style>
