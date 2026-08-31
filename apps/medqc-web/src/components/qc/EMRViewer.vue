<template>
  <div ref="viewerRef" class="emr-viewer">
    <div v-if="!hideDocTabs && documentItems.length > 1" class="mb-5">
      <div
        class="inline-flex items-center gap-1 rounded-xl border border-gray-100/50 bg-gray-100/80 p-1"
      >
        <button
          v-for="doc in documentItems"
          :key="docIdentityKey(doc)"
          :class="[
            'rounded-lg px-4 py-1.5 text-[13px] font-medium whitespace-nowrap transition-all duration-200',
            loadedDocKey === docIdentityKey(doc)
              ? 'bg-white text-blue-700 shadow-[0_1px_3px_rgba(0,0,0,0.08)]'
              : 'text-gray-500 hover:text-gray-700',
          ]"
          @click="handleSwitchDoc(doc)"
        >
          {{ displayDocName(doc) }}
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex h-64 items-center justify-center">
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
          {{ displayMetadataTitle }}
        </div>
        <div class="emr-struct__meta-row">
          <span v-if="displayDocumentId">文书ID：{{ displayDocumentId }}</span>
          <span v-if="metadata.record_time">记录时间：{{ metadata.record_time }}</span>
          <span v-if="authorSummary">录入/修改人：{{ authorSummary }}</span>
          <span v-if="signatureSummary">签名：{{ signatureSummary }}</span>
        </div>
        <div v-if="projectionNotice" class="emr-struct__projection-notice">
          {{ projectionNotice }}
        </div>
      </div>

      <section v-for="block in displayRenderBlocks" :key="block.block_id" class="emr-struct__block">
        <template v-if="block.block_type === 'kv_section'">
          <h4 class="emr-struct__block-title">
            {{ displayBlockTitle(block.title || '基础信息') }}
          </h4>
          <div v-if="(block.fields || []).length > 0" class="emr-struct__field-list">
            <article
              v-for="field in block.fields || []"
              :key="`${block.block_id}:${field.key}`"
              class="emr-struct__field-item"
              :data-field-value="field.value || ''"
            >
              <h5 class="emr-struct__field-label">
                {{ displayFieldLabel(field) }}
              </h5>
              <div class="emr-struct__field-value">
                {{ field.value || '-' }}
              </div>
            </article>
          </div>
          <div v-else class="emr-struct__empty">暂无结构化字段</div>
        </template>

        <template v-else-if="block.block_type === 'order_table'">
          <h4 class="emr-struct__block-title">
            {{ displayBlockTitle(block.title || '医嘱') }}
          </h4>
          <div v-if="(block.rows || []).length > 0" class="emr-struct__table-wrap">
            <table class="emr-struct__table">
              <thead>
                <tr>
                  <th v-for="col in block.columns || []" :key="col.key">
                    {{ displayColumnLabel(col) }}
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
          <div v-else class="emr-struct__empty">
            {{ block.empty_text || '暂无医嘱数据' }}
          </div>
        </template>

        <template v-else>
          <h4 class="emr-struct__block-title">
            {{ displayBlockTitle(block.title || '正文') }}
          </h4>
          <div
            class="emr-struct__paragraph"
            :data-anchor-text="(block.text || '').slice(0, 80)"
            v-html="renderParagraphContent(block.text || '')"
          />
        </template>
      </section>
    </div>

    <template v-else-if="renderedContent">
      <div class="emr-content-meta">
        <span v-if="displayDocumentId">文书ID：{{ displayDocumentId }}</span>
        <span v-if="metadata.record_time">记录时间：{{ metadata.record_time }}</span>
        <span v-if="authorSummary">录入/修改人：{{ authorSummary }}</span>
        <span v-if="signatureSummary">签名：{{ signatureSummary }}</span>
        <span v-if="projectionNotice" class="emr-content-meta__projection-notice">{{
          projectionNotice
        }}</span>
      </div>
      <div
        ref="contentRef"
        class="emr-content overflow-auto"
        :style="{ maxHeight: maxHeight + 'px' }"
        v-html="renderedContent"
      />
    </template>

    <div v-else class="flex h-64 flex-col items-center justify-center text-gray-400">
      <FileTextOutlined class="mb-3 text-4xl" />
      <p>暂无文书内容</p>
      <p class="text-xs">请在左侧选择病历</p>
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
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { useDefectHighlight } from '@/composables/useDefectHighlight'
import type { DefectAnnotation } from '@/composables/useDefectHighlight'
import { getAccessToken } from '@/utils/auth-token'
import { resolveMedicalFieldLabel } from '@/utils/medicalFieldLabels'

interface EmrDocumentSummary {
  id: string
  doc_type: string
  doc_name: string
  doc_key?: string
  execution_domain?: string
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

interface EmrDocumentPerson {
  role?: string
  name?: string
  code?: string
  signed_at?: string
  source_field?: string
}

interface EmrDocumentMetadata {
  doc_type?: string
  doc_name?: string
  doc_id?: string
  document_id?: string
  doc_key?: string
  group_key?: string
  record_time?: string
  source?: string
  authors?: EmrDocumentPerson[]
  signatures?: EmrDocumentPerson[]
  projection_incomplete?: boolean
  projection_notice?: string
}

const props = withDefaults(
  defineProps<{
    recordId?: string
    visitId?: string
    patientId?: string
    instituteId?: string
    docType?: string
    activeDocKey?: string
    documents?: EmrDocumentSummary[]
    documentsManaged?: boolean
    documentsLoading?: boolean
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
const metadata = ref<EmrDocumentMetadata>({})
const annotations = ref<DefectAnnotation[]>([])
const documentItems = ref<EmrDocumentSummary[]>([])
const loadedDocKey = ref('')
const loadedRecordId = ref('')
const showAnnotationPanel = ref(false)
const layoutVersion = ref('')
const renderBlocks = ref<EmrRenderBlock[]>([])
const boundClickContainer = ref<HTMLElement | null>(null)
let activeRequestController: AbortController | null = null

function beginRequest() {
  activeRequestController?.abort()
  const controller = new AbortController()
  activeRequestController = controller
  return controller
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === 'AbortError'
}

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

function normalizeDisplayText(value: unknown): string {
  return String(value || '')
    .replace(/\s+/gu, '')
    .trim()
}

/**
 * 同一份文书可能同时返回 record_content 字段和同内容的 paragraph 投影。
 * 结构化视图只保留一份：优先保留更完整的正文段落，避免“基础信息/记录内容”
 * 后面又重复渲染“正文”。这是展示层处理，不修改质控输入或接口原始数据。
 */
const displayRenderBlocks = computed<EmrRenderBlock[]>(() => {
  const paragraphs = renderBlocks.value
    .filter((block) => block.block_type === 'paragraph')
    .map((block) => normalizeDisplayText(block.text))
    .filter(Boolean)
  const seenParagraphs = new Set<string>()

  return renderBlocks.value.flatMap((block) => {
    if (block.block_type === 'kv_section') {
      const fields = (block.fields || []).filter((field) => {
        const displayLabel = normalizeDisplayText(field.label || field.key)
        const value = normalizeDisplayText(field.value)
        if (!value) return true
        const fieldWithTitle = `${displayLabel}:${value}`
        const isDuplicatedByParagraph = paragraphs.some(
          (paragraph) =>
            paragraph === value ||
            paragraph.startsWith(value) ||
            paragraph.startsWith(fieldWithTitle) ||
            paragraph.startsWith(`${displayLabel}：${value}`) ||
            // record_content 常被结构化接口同时投影为“基础信息”和“正文”。
            // 正文可能带有“新建S章节:”等前缀，不能只判断 startsWith(value)。
            // 仅对正文类字段做包含判断，避免误删普通字段在长正文中的偶然引用。
            (['record_content', 'recordcontent', 'recordcontenttext', 'content', 'text'].includes(
              String(field.key || '')
                .toLowerCase()
                .replace(/[\s-]+/g, '_'),
            ) &&
              paragraph.includes(value)),
        )
        return !isDuplicatedByParagraph
      })
      if ((block.fields || []).length > 0 && fields.length === 0) return []
      return [{ ...block, fields }]
    }

    if (block.block_type === 'paragraph') {
      const text = normalizeDisplayText(block.text)
      if (text && seenParagraphs.has(text)) return []
      if (text) seenParagraphs.add(text)
    }
    return [block]
  })
})

const displayMetadataTitle = computed(() =>
  displayDocName({
    doc_type: String(metadata.value.doc_type || ''),
    doc_name: String(metadata.value.doc_name || ''),
  }),
)

function summarizePeople(people: EmrDocumentPerson[] | undefined): string {
  if (!Array.isArray(people)) return ''
  const labels = people
    .map((person) => {
      const name = String(person.name || '').trim()
      const role = String(person.role || '').trim()
      return name || role
    })
    .filter(Boolean)
  return [...new Set(labels)].join('、')
}

const displayDocumentId = computed(() =>
  String(metadata.value.document_id || metadata.value.doc_id || '').trim(),
)
const authorSummary = computed(() => summarizePeople(metadata.value.authors))
const signatureSummary = computed(() => summarizePeople(metadata.value.signatures))
const projectionNotice = computed(() =>
  metadata.value.projection_incomplete === true
    ? String(metadata.value.projection_notice || '当前仅展示部分文书，请按需查看后续资料。').trim()
    : '',
)

const DOC_TYPE_LABELS: Record<string, string> = {
  admission_record: '入院记录',
  admission_note: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  consultation_record: '会诊记录',
  discharge_record: '出院记录',
  progress_note: '病程记录',
  course_record: '病程记录',
  surgery_record: '手术记录',
  operation_record: '手术记录',
  surgery_application: '手术申请单',
  presurg_summary: '术前小结',
  anesthesia_record: '麻醉记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  blood_application: '输血申请单',
  bloodtrans_record: '输血记录',
  transfusion_record: '输血记录',
  exam_master: '检查记录',
  exam_item_report: '检查报告',
  labtest_master: '检验申请单',
  labtest_item_report: '检验报告',
  order_record: '医嘱',
  inpat_drug_order: '药品医嘱',
  inpat_nondrug_order: '非药品医嘱',
  orders: '医嘱',
}

const BLOCK_TITLE_LABELS: Record<string, string> = {
  basic_info: '基础信息',
  basic: '基础信息',
  admission: '入院信息',
  hospitalization: '住院信息',
  diagnosis: '诊断',
  diagnoses: '诊断',
  procedure: '手术操作',
  procedures: '手术操作',
  exam: '检查检验',
  examination: '检查检验',
  orders: '医嘱',
  medical_orders: '医嘱',
  content: '正文',
  text: '正文',
}

const FIELD_LABELS: Record<string, string> = {
  record_time: '记录时间',
  department: '科室',
  dept_name: '科室',
  ward_name: '病区',
  ward_no: '病区',
  doctor_name: '医生',
  recorder_name: '记录者',
  submitter: '记录者',
  chief_complaint: '主诉',
  chief_complaints: '主诉',
  history_of_present_illness: '现病史',
  present_illness_history: '现病史',
  present_history: '现病史',
  current_medical_history: '现病史',
  past_history: '既往史',
  previous_history: '既往史',
  personal_history: '个人史',
  personal_his_tory: '个人史',
  marital_delivery_history: '婚育史',
  menstrual_history: '月经史',
  marital_history: '婚育史',
  family_history: '家族史',
  family_histo_ry: '家族史',
  allergy_history: '过敏史',
  drug_allergy_history: '药物过敏史',
  food_allergy_history: '食物过敏史',
  physical_examination: '体格检查',
  physical_exam: '体格检查',
  checkup: '体格检查',
  checkup_special: '专科情况',
  specialist_examination: '专科检查',
  auxiliary_examination: '辅助检查',
  assist_exam: '辅助检查',
  admission_diagnosis: '入院诊断',
  preliminary_diagnosis: '初步诊断',
  diagnosis: '诊断',
  treatment_plan: '诊疗计划',
  treatment_course: '诊疗经过',
  admission_condition: '入院情况',
  record_content: '记录内容',
  other_content: '其他内容',
}

const EN_LABELS: Record<string, string> = {
  'basic info': '基础信息',
  'chief complaint': '主诉',
  'chief complaints': '主诉',
  'history of present illness': '现病史',
  'present illness history': '现病史',
  'present history': '现病史',
  'current medical history': '现病史',
  'past history': '既往史',
  'previous history': '既往史',
  'personal history': '个人史',
  'personal his tory': '个人史',
  'marital delivery history': '婚育史',
  'menstrual history': '月经史',
  'marital history': '婚育史',
  'family history': '家族史',
  'family histo ry': '家族史',
  'allergy history': '过敏史',
  'drug allergy history': '药物过敏史',
  'food allergy history': '食物过敏史',
  'physical examination': '体格检查',
  'physical exam': '体格检查',
  'specialist examination': '专科检查',
  'auxiliary examination': '辅助检查',
  'assist exam': '辅助检查',
  'admission diagnosis': '入院诊断',
  'preliminary diagnosis': '初步诊断',
  'treatment plan': '诊疗计划',
  'treatment course': '诊疗经过',
  'admission condition': '入院情况',
  'record content': '记录内容',
  'other content': '其他内容',
}

function normalizeLabelKey(value?: string): string {
  return String(value || '')
    .trim()
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

function displayDocName(doc: Pick<EmrDocumentSummary, 'doc_name' | 'doc_type'>): string {
  const rawName = String(doc.doc_name || '').trim()
  const rawType = String(doc.doc_type || '').trim()
  const typeLabel = DOC_TYPE_LABELS[rawType] || EN_LABELS[normalizeLabelKey(rawType)]
  if (!rawName || rawName === rawType) return typeLabel || rawName || rawType || '病历文书'
  return EN_LABELS[normalizeLabelKey(rawName)] || typeLabel || rawName
}

function displayBlockTitle(title?: string): string {
  const raw = String(title || '').trim()
  if (!raw) return '正文'
  return BLOCK_TITLE_LABELS[raw] || FIELD_LABELS[raw] || EN_LABELS[normalizeLabelKey(raw)] || raw
}

function displayFieldLabel(field: EmrKvField): string {
  const rawLabel = String(field.label || field.key || '').trim()
  const rawKey = String(field.key || '').trim()
  return (
    FIELD_LABELS[rawKey] ||
    FIELD_LABELS[rawLabel] ||
    EN_LABELS[normalizeLabelKey(rawLabel)] ||
    EN_LABELS[normalizeLabelKey(rawKey)] ||
    resolveMedicalFieldLabel(rawLabel) ||
    resolveMedicalFieldLabel(rawKey) ||
    rawLabel ||
    rawKey ||
    '字段'
  )
}

function displayColumnLabel(col: EmrTableColumn): string {
  const rawLabel = String(col.label || col.key || '').trim()
  const rawKey = String(col.key || '').trim()
  return (
    FIELD_LABELS[rawKey] ||
    FIELD_LABELS[rawLabel] ||
    EN_LABELS[normalizeLabelKey(rawLabel)] ||
    EN_LABELS[normalizeLabelKey(rawKey)] ||
    resolveMedicalFieldLabel(rawLabel) ||
    resolveMedicalFieldLabel(rawKey) ||
    rawLabel ||
    rawKey ||
    '字段'
  )
}

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
  documentItems.value = []
  loadedDocKey.value = ''
  loadedRecordId.value = ''
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
  return documentItems.value.find((doc) => docIdentityKey(doc) === activeKey)
}

function pickInitialDocument(): EmrDocumentSummary | undefined {
  const byExternal = findDocByActiveKey(props.activeDocKey)
  if (byExternal) return byExternal
  if (props.docType) {
    const byType = documentItems.value.find((doc) => doc.doc_type === props.docType)
    if (byType) return byType
  }
  return documentItems.value.find((doc) => doc.has_content) || documentItems.value[0]
}

async function fetchDocuments() {
  if (props.documentsManaged) {
    documentItems.value = Array.isArray(props.documents) ? props.documents : []
    const target = pickInitialDocument()
    if (!target) {
      resetViewerState()
      if (!props.documentsLoading) emit('error', 'no-documents')
      return
    }
    loadedDocKey.value = docIdentityKey(target)
    loadedRecordId.value = effectiveRecordId.value
    await loadDocument(target)
    return
  }
  const url = buildUrl('documents')
  if (!url) {
    resetViewerState()
    emit('error', 'missing-identifiers')
    return
  }

  const controller = beginRequest()
  try {
    const response = await fetch(url, {
      headers: getAuthHeaders(),
      signal: controller.signal,
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
    documentItems.value = docList
    const target = pickInitialDocument()
    if (!target) {
      rawContent.value = ''
      annotations.value = []
      renderBlocks.value = []
      layoutVersion.value = String(payload.layout_version || '')
      emit('error', 'no-documents')
      return
    }
    loadedDocKey.value = docIdentityKey(target)
    loadedRecordId.value = effectiveRecordId.value
    await loadDocument(target)
  } catch (err) {
    if (isAbortError(err)) return
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

function hasRenderableDocument(emptyReason: unknown): boolean {
  if (String(emptyReason || '').trim()) return false
  if (rawContent.value.trim()) return true
  return renderBlocks.value.some((block) => {
    if (block.empty === true) return false
    if (String(block.text || '').trim()) return true
    if ((block.fields || []).some((field) => String(field.value || '').trim())) return true
    return (block.rows || []).some((row) =>
      Object.values(row).some((value) => String(value || '').trim()),
    )
  })
}

async function loadDocument(doc?: EmrDocumentSummary) {
  if (!doc) return
  const controller = beginRequest()
  loading.value = true
  loadedDocKey.value = docIdentityKey(doc)
  try {
    const extraParams: Record<string, string> = {}
    if (doc.doc_type) extraParams.doc_type = doc.doc_type
    if (doc.id) extraParams.doc_id = doc.id
    if (doc.execution_domain) extraParams.execution_domain = doc.execution_domain
    const url = buildUrl('render', extraParams)
    if (!url) {
      emit('error', 'missing-identifiers')
      return
    }

    const response = await fetch(url, {
      headers: getAuthHeaders(),
      signal: controller.signal,
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
    metadata.value = data.metadata && typeof data.metadata === 'object' ? data.metadata : {}
    annotations.value = data.defect_annotations || []
    layoutVersion.value = data.layout_version || ''
    renderBlocks.value = Array.isArray(data.render_blocks) ? data.render_blocks : []

    if (hasRenderableDocument(data.empty_reason)) {
      emit('loaded', data)
    } else {
      renderBlocks.value = []
      layoutVersion.value = ''
      emit('error', String(data.empty_reason || 'empty-content'))
    }

    nextTick(() => {
      bindHighlightClicks()
    })
  } catch (err) {
    if (isAbortError(err)) return
    console.error('加载文书内容失败:', err)
    emit('error', 'load-document-failed')
  } finally {
    if (activeRequestController === controller) loading.value = false
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

onBeforeUnmount(() => activeRequestController?.abort())

watch(
  () => [
    props.recordId,
    props.visitId,
    props.patientId,
    props.instituteId,
    props.docType,
    props.documents,
    props.documentsManaged,
    props.documentsLoading,
  ],
  () => {
    // 受控目录后台补齐时 documents 数组会追加项目，但当前文书仍然有效，
    // 不应因为目录变化再次请求同一份正文；切换病历/文书时 loadedDocKey 会失效。
    if (
      props.documentsManaged &&
      loadedRecordId.value === effectiveRecordId.value &&
      loadedDocKey.value &&
      documentItems.value.some((doc) => docIdentityKey(doc) === loadedDocKey.value) &&
      (!props.activeDocKey || props.activeDocKey === loadedDocKey.value)
    ) {
      return
    }
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
    if (loadedDocKey.value && docIdentityKey(doc) === loadedDocKey.value) return
    void loadDocument(doc)
  },
)
</script>

<style scoped>
.emr-content,
.emr-struct {
  margin: 0 auto;
  max-width: 112ch;
  border: 1px solid rgba(226, 232, 240, 0.62);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(252, 253, 255, 0.98));
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.035);
  padding: 18px 22px 26px;
  color: #475569;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'SimSun', serif;
  font-size: 14px;
  line-height: 1.78;
  word-break: normal;
  overflow-wrap: anywhere;
}

.emr-content {
  white-space: pre-wrap;
}

.emr-struct__header {
  margin-bottom: 14px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.7);
  padding-bottom: 12px;
}

.emr-struct__title {
  font-size: 18px;
  font-weight: 800;
  line-height: 1.45;
  color: #0f172a;
}

.emr-struct__time {
  margin-top: 3px;
  font-size: 12px;
  color: #64748b;
}

.emr-struct__meta-row,
.emr-content-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 3px 12px;
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.emr-struct__projection-notice,
.emr-content-meta__projection-notice {
  margin-top: 8px;
  border-left: 2px solid rgba(245, 158, 11, 0.75);
  padding-left: 8px;
  color: #92400e;
  font-size: 12px;
  line-height: 1.65;
}

.emr-content-meta {
  max-width: 112ch;
  margin: 0 auto 8px;
  padding: 0 4px;
}

.emr-content-meta__projection-notice {
  flex-basis: 100%;
}

.emr-struct__block {
  margin-bottom: 18px;
  border: 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.72);
  border-radius: 0;
  background: transparent;
  padding: 0 0 16px;
}

.emr-struct__block:last-child {
  margin-bottom: 0;
  border-bottom: 0;
  padding-bottom: 0;
}

.emr-struct__block-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.5;
  color: #0f172a;
}

.emr-struct__field-list {
  display: grid;
  gap: 14px;
}

.emr-struct__field-item {
  display: block;
  padding-left: 14px;
  border-left: 3px solid rgba(191, 219, 254, 0.9);
}

.emr-struct__field-label {
  margin: 0 0 4px;
  color: #475569;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.6;
}

.emr-struct__field-value {
  color: #0f172a;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.85;
  white-space: pre-wrap;
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
}
</style>
