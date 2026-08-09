<template>
  <section
    class="record-compare-shell"
    :data-mobile-tab="mobileTab"
  >
    <header class="record-compare-head">
      <div>
        <strong>病历原文对照</strong>
        <span>点击质控结果，核对对应文书与证据片段</span>
      </div>
      <div
        class="record-compare-mobile-tabs"
        role="tablist"
        aria-label="病历与结果切换"
      >
        <button
          type="button"
          :class="{ 'is-active': mobileTab === 'record' }"
          @click="mobileTab = 'record'"
        >
          病历原文
        </button>
        <button
          type="button"
          :class="{ 'is-active': mobileTab === 'result' }"
          @click="mobileTab = 'result'"
        >
          质控结果
        </button>
      </div>
    </header>

    <div class="record-compare-grid">
      <ReadonlyMedicalDocumentDirectory
        class="record-document-nav"
        :documents="documents"
        :selected-key="selectedDocumentKey"
        :loading="loading"
        :error="loadError"
        @select="selectDocument"
        @retry="loadDocuments"
      />

      <main class="record-content-column">
        <div class="record-content-toolbar">
          <div>
            <strong>
              {{ selectedDocument ? resolveDocumentDisplayTitle(selectedDocument) : '病历原文' }}
            </strong>
            <time
              v-if="selectedDocument"
              class="record-content-time"
              :class="{ 'is-missing': !resolveDocumentTime(selectedDocument) }"
            >
              <span>记录时间</span>
              <b>{{ formatDocumentTime(resolveDocumentTime(selectedDocument)) }}</b>
            </time>
          </div>
          <label
            v-if="documents.length"
            class="record-document-select"
          >
            <span>选择文书</span>
            <select
              :value="selectedDocumentKey"
              @change="handleDocumentSelect"
            >
              <option
                v-for="document in documents"
                :key="document.key"
                :value="document.key"
              >
                {{ resolveDocumentDisplayTitle(document) }}
              </option>
            </select>
          </label>
          <span
            class="record-location-chip"
            :class="`is-${locationState}`"
          >
            {{ locationMessage }}
          </span>
        </div>

        <div
          v-if="selectedDocument"
          ref="recordScroller"
          class="record-content-scroll"
          tabindex="0"
        >
          <ReadonlyMedicalOrderTable
            v-if="isMedicalOrderDocument(selectedDocument)"
            :documents="documents"
            :selected-key="selectedDocumentKey"
            @select="selectDocument"
          />
          <div
            v-else-if="documentSectionViews.length"
            class="record-content-sections"
          >
            <section
              v-for="section in documentSectionViews"
              :key="section.key"
              class="record-content-section"
              :class="{ 'is-evidence-target': section.isMatchedSection }"
              :data-section-key="section.key"
            >
              <h3 class="record-content-section-title">
                {{ section.label }}
              </h3>
              <p class="record-content-section-text">
                <span>{{ section.parts.before }}</span><mark
                  v-if="section.parts.match"
                  :ref="setHighlightElement"
                  class="record-evidence-highlight"
                  tabindex="0"
                  @click="emitSelectedIssue"
                  @keydown.enter="emitSelectedIssue"
                >{{ section.parts.match }}</mark><span>{{ section.parts.after }}</span>
              </p>
            </section>
          </div>
          <pre
            v-else
            class="record-content-text"
          ><span>{{ documentTextParts.before }}</span><mark
                v-if="documentTextParts.match"
                :ref="setHighlightElement"
                class="record-evidence-highlight"
                tabindex="0"
                @click="emitSelectedIssue"
                @keydown.enter="emitSelectedIssue"
          >{{ documentTextParts.match }}</mark><span>{{ documentTextParts.after }}</span></pre>
        </div>
        <div
          v-else
          class="record-content-empty"
        >
          <strong>暂无可对照的病历原文</strong>
          <span>质控结果仍可查看，但当前无法定位到来源文书。</span>
        </div>
      </main>

      <aside
        class="record-result-column"
        aria-label="质控结果"
      >
        <SingleRecordQcResultPanel
          v-if="hasSingleRecordResult"
          :items="singleRecordItems || []"
          :presentation-mode="presentationMode"
          @select="selectSingleRecordResult"
          @locate-evidence="locateSingleRecordEvidence"
        />
        <template v-else>
          <div class="record-column-head">
            <div>
              <strong>质控结果</strong>
              <span>按风险优先 · 点击展开核对依据</span>
            </div>
            <span class="record-result-count">{{ sortedIssues.length }} 条</span>
          </div>
          <div
            v-if="!sortedIssues.length"
            class="record-compare-state"
          >
            当前没有可展示的质控结果
          </div>
          <div
            v-else
            class="record-result-list"
          >
            <article
              v-for="issue in sortedIssues"
              :key="issue.key"
              class="record-result-entry"
              :class="[
                `is-${resolveStatusTone(issue.status)}`,
                {
                  'is-active': issue.key === selectedIssueKey,
                  'is-expanded': issue.key === expandedIssueKey,
                },
              ]"
            >
              <button
                type="button"
                class="record-result-item"
                :aria-expanded="issue.key === expandedIssueKey"
                @click="selectIssue(issue.key)"
              >
                <span class="record-result-item-head">
                  <span class="record-result-meta">
                    <span class="record-result-status">
                      {{ issue.result_kind_text || issue.status_text }}
                    </span>
                    <span class="record-result-code">{{ issue.rule_code }}</span>
                  </span>
                  <span
                    class="record-result-toggle"
                    aria-hidden="true"
                  >
                    <ChevronDown
                      :size="15"
                      :class="{ 'is-open': issue.key === expandedIssueKey }"
                    />
                  </span>
                </span>
                <strong :title="issue.rule_name">{{ issue.rule_name }}</strong>
                <small
                  v-if="resolveIssueSummary(issue)"
                  class="record-result-summary-line"
                >
                  {{ resolveIssueSummary(issue) }}
                </small>
              </button>

              <div
                v-if="issue.key === expandedIssueKey"
                class="record-result-detail"
              >
                <section
                  v-if="issue.detail"
                  class="record-result-analysis"
                >
                  <div class="record-result-section-heading">
                    <ClipboardCheck
                      :size="15"
                      aria-hidden="true"
                    />
                    <span>完整判定说明</span>
                  </div>
                  <div class="record-result-narrative">
                    <p
                      v-for="(line, index) in resolveIssueDetailLines(issue)"
                      :key="`${issue.key}-${index}`"
                      class="record-result-narrative-line"
                      :class="{ 'is-decision': line.startsWith('综合判定') }"
                    >
                      {{ line }}
                    </p>
                  </div>
                </section>
                <div
                  v-if="issue.actual_value || issue.requirement"
                  class="record-result-comparison"
                >
                  <section v-if="issue.actual_value">
                    <div class="record-result-section-heading">
                      <Scale
                        :size="15"
                        aria-hidden="true"
                      />
                      <span>实际情况</span>
                    </div>
                    <p>{{ issue.actual_value }}</p>
                  </section>
                  <section v-if="issue.requirement">
                    <div class="record-result-section-heading">
                      <Target
                        :size="15"
                        aria-hidden="true"
                      />
                      <span>核对标准</span>
                    </div>
                    <p>{{ issue.requirement }}</p>
                  </section>
                </div>
                <section
                  v-if="issue.evidences.length"
                  class="record-result-evidence"
                >
                  <div class="record-result-section-heading">
                    <FileSearch
                      :size="15"
                      aria-hidden="true"
                    />
                    <span>关键证据</span>
                  </div>
                  <button
                    v-for="evidence in issue.evidences"
                    :key="evidence.key"
                    type="button"
                    class="record-evidence-button"
                    @click="locateEvidence(evidence)"
                  >
                    <strong>
                      {{ resolveEvidenceSourceLabel(evidence) }}
                    </strong>
                    <time v-if="evidence.record_time">
                      记录时间 {{ formatDocumentTime(evidence.record_time) }}
                    </time>
                    <small
                      v-if="resolveEvidenceExcerpt(evidence)"
                      class="record-evidence-excerpt"
                    >
                      <span>{{ resolveEvidenceExcerpt(evidence)?.label }}</span>
                      {{ resolveEvidenceExcerpt(evidence)?.text }}
                    </small>
                    <small v-else>点击定位原文核对</small>
                  </button>
                </section>
                <section class="record-result-guidance">
                  <div class="record-result-section-heading">
                    <Lightbulb
                      :size="15"
                      aria-hidden="true"
                    />
                    <span>处理建议</span>
                  </div>
                  <p>{{ issue.suggestion || '请结合病历原文确认。' }}</p>
                </section>
              </div>
            </article>
          </div>
        </template>
      </aside>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ChevronDown, ClipboardCheck, FileSearch, Lightbulb, Scale, Target } from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { getEditableMedicalRecordDocuments } from '@/services/manual-case-sample-service'
import ReadonlyMedicalDocumentDirectory from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentDirectory.vue'
import ReadonlyMedicalOrderTable from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalOrderTable.vue'
import SingleRecordQcResultPanel from '@/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue'
import {
  formatMedicalDocumentTime,
  isMedicalOrderDocument,
  resolveMedicalDocumentTime,
  resolveMedicalDocumentTitle,
  resolveMedicalDocumentTypeLabel,
} from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'
import {
  buildSingleRecordQcResultItems,
  type SingleRecordQcEvidence,
  type SingleRecordQcResultItem,
} from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'
import type {
  QCRecordCompareEvidence,
  QCRecordCompareIssue,
} from '@/views/workstation-v4/semantic-rules/types'

const props = withDefaults(
  defineProps<{
    visitId: string
    jobId?: string
    recordRef?: string
    instituteId?: string
    patientId?: string
    issues: QCRecordCompareIssue[]
    /** 单病历纵向切片专用；存在时右栏不再使用批量结果旧模型。 */
    singleRecordItems?: SingleRecordQcResultItem[]
    presentationMode?: 'flat' | 'grouped'
    activeIssueKey?: string
  }>(),
  { presentationMode: 'flat' },
)

const emit = defineEmits<{
  (event: 'select-issue', issueKey: string): void
}>()

type LocationState = 'matched' | 'section' | 'document' | 'missing' | 'idle'

const documents = ref<EditableMedicalRecordDocument[]>([])
const loading = ref(false)
const loadError = ref('')
const selectedDocumentKey = ref('')
const selectedIssueKey = ref('')
const expandedIssueKey = ref('')
const matchedRange = ref<{ start: number; end: number } | null>(null)
const matchedSectionKey = ref('')
const locationState = ref<LocationState>('idle')
const mobileTab = ref<'record' | 'result'>('record')
const recordScroller = ref<HTMLElement | null>(null)
const highlightElement = ref<HTMLElement | null>(null)
let loadGeneration = 0

const STATUS_PRIORITY: Record<string, number> = {
  non_compliant: 0,
  ai_suggested_non_compliant: 1,
  evaluation_unknown: 1,
  uncertain: 1,
  data_gap: 2,
  technical_error: 2,
  not_executed: 2,
  compliant: 3,
  ai_suggested_compliant: 3,
  not_applicable: 4,
}

const GENERIC_RESULT_SUMMARIES = new Set([
  '发现该质控点对应的明确问题。',
  '当前受控数据不足以形成确定结论。',
  '规则要求未满足',
])

function resolveDocumentDisplayTitle(document: EditableMedicalRecordDocument) {
  return resolveMedicalDocumentTitle(document)
}

function resolveEvidenceSourceLabel(evidence: QCRecordCompareEvidence) {
  return (
    resolveMedicalDocumentTypeLabel(evidence.source_document_name) ||
    resolveMedicalDocumentTypeLabel(evidence.source_document_type) ||
    resolveMedicalDocumentTypeLabel(evidence.source_table) ||
    '来源文书'
  )
}

function resolveDocumentTime(document: EditableMedicalRecordDocument) {
  return resolveMedicalDocumentTime(document)
}

const sortedIssues = computed(() =>
  props.issues
    .map((issue, index) => ({ issue, index }))
    .sort(
      (left, right) =>
        (STATUS_PRIORITY[left.issue.status] ?? 5) - (STATUS_PRIORITY[right.issue.status] ?? 5) ||
        left.index - right.index,
    )
    .map(({ issue }) => issue),
)

const hasSingleRecordResult = computed(() => Array.isArray(props.singleRecordItems))
const singleRecordViewItems = computed(() =>
  buildSingleRecordQcResultItems(props.singleRecordItems),
)

const selectedIssue = computed(
  () =>
    sortedIssues.value.find((issue) => issue.key === selectedIssueKey.value) ||
    sortedIssues.value[0] ||
    null,
)

function resolveIssueSummary(issue: QCRecordCompareIssue) {
  const safeSummary = String(issue.summary || '').trim()
  if (safeSummary) return safeSummary
  const conclusion = String(issue.conclusion || '').trim()
  if (conclusion && !GENERIC_RESULT_SUMMARIES.has(conclusion)) return conclusion
  if (issue.status === 'non_compliant') {
    return '本次核对未满足该质控点要求，需补充或修正对应文书。'
  }
  if (issue.status === 'data_gap') {
    return '当前资料不足以完成该质控点的确定性核对。'
  }
  if (['evaluation_unknown', 'uncertain', 'ai_suggested_non_compliant'].includes(issue.status)) {
    return '现有资料需要由质控人员进一步复核后确认。'
  }
  return conclusion || '未返回可展示的结果摘要。'
}

function resolveIssueDetailLines(issue: QCRecordCompareIssue) {
  return String(issue.detail || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

const selectedDocument = computed(
  () => documents.value.find((document) => document.key === selectedDocumentKey.value) || null,
)
const locationMessage = computed(() => {
  if (loading.value) return '正在读取原文'
  if (loadError.value) return '原文读取失败'
  if (locationState.value === 'matched') return '已定位到证据段落'
  if (locationState.value === 'section') {
    const section = selectedDocument.value?.sections?.find(
      (item) => item.key === matchedSectionKey.value,
    )
    return section?.label ? `已定位到${section.label}章节` : '已定位到对应章节'
  }
  if (locationState.value === 'document') return '已定位到文书，未定位到具体片段'
  if (locationState.value === 'missing') return '未找到对应文书，请手动核对'
  return selectedDocument.value ? '手动浏览文书' : '等待选择质控结果'
})
const documentTextParts = computed(() => {
  const content = selectedDocument.value?.content || ''
  const range = matchedRange.value
  if (!range || range.start < 0 || range.end <= range.start || range.end > content.length) {
    return { before: content, match: '', after: '' }
  }
  return {
    before: content.slice(0, range.start),
    match: content.slice(range.start, range.end),
    after: content.slice(range.end),
  }
})

const documentSectionViews = computed(() => {
  const document = selectedDocument.value
  const sections = document?.sections || []
  if (!document || !sections.length) return []
  const content = document.content || ''
  const range = matchedRange.value
  let cursor = 0
  return sections.map((section) => {
    const text = section.text
    const sectionStart = content.indexOf(text, cursor)
    if (sectionStart >= 0) cursor = sectionStart + text.length
    const localStart =
      range &&
      sectionStart >= 0 &&
      range.start >= sectionStart &&
      range.end <= sectionStart + text.length
        ? range.start - sectionStart
        : -1
    const localEnd = localStart >= 0 && range ? range.end - sectionStart : -1
    return {
      ...section,
      isMatchedSection: matchedSectionKey.value === section.key,
      parts:
        localStart >= 0 && localEnd > localStart
          ? {
              before: text.slice(0, localStart),
              match: text.slice(localStart, localEnd),
              after: text.slice(localEnd),
            }
          : { before: text, match: '', after: '' },
    }
  })
})

function formatDocumentTime(value?: string) {
  return formatMedicalDocumentTime(value)
}

function normalizeReference(value?: string) {
  return String(value || '')
    .normalize('NFKC')
    .replace(/\s+/gu, '')
    .toLowerCase()
}

function normalizeDate(value?: string) {
  const match = String(value || '').match(/\d{4}[-/]\d{1,2}[-/]\d{1,2}/u)
  return match ? match[0].replace(/\//gu, '-') : ''
}

function buildNormalizedText(value: string) {
  let normalized = ''
  const positions: number[] = []
  let offset = 0
  for (const character of value) {
    const start = offset
    const converted = character.normalize('NFKC').toLowerCase()
    for (const normalizedCharacter of converted) {
      if (/\s/u.test(normalizedCharacter)) continue
      normalized += normalizedCharacter
      positions.push(start)
    }
    offset += character.length
  }
  return { normalized, positions }
}

function buildQuoteCandidates(value: string) {
  const quote = value
    .replace(/\.{3,}$/u, '')
    .replace(/…+$/u, '')
    .trim()
  const candidates = [
    quote,
    ...quote
      .split(/[\n。；！？]+/u)
      .map((part) =>
        part.replace(/^(?:证据说明|关键证据|来源片段|证据片段|判定依据|原文)[：:\s]*/u, '').trim(),
      ),
  ]
  return Array.from(new Set(candidates))
    .filter((candidate) => buildNormalizedText(candidate).normalized.length >= 8)
    .sort(
      (left, right) =>
        buildNormalizedText(right).normalized.length - buildNormalizedText(left).normalized.length,
    )
}

function findQuoteRange(document: EditableMedicalRecordDocument, quote: string) {
  const normalizedDocument = buildNormalizedText(document.content || '')
  for (const candidate of buildQuoteCandidates(quote)) {
    const normalizedQuote = buildNormalizedText(candidate).normalized
    const index = normalizedDocument.normalized.indexOf(normalizedQuote)
    if (index < 0) continue
    const start = normalizedDocument.positions[index]
    const lastPosition = normalizedDocument.positions[index + normalizedQuote.length - 1]
    if (start === undefined || lastPosition === undefined) continue
    const trailingCharacter = Array.from((document.content || '').slice(lastPosition))[0] || ''
    return { start, end: lastPosition + trailingCharacter.length }
  }
  return null
}

function findSectionKey(document: EditableMedicalRecordDocument, fieldPath?: string) {
  const normalizedFieldPath = normalizeReference(fieldPath)
  if (!normalizedFieldPath) return ''
  const matches = (document.sections || []).filter((section) =>
    [section.key, section.source_field]
      .map(normalizeReference)
      .some((candidate) => candidate && candidate === normalizedFieldPath),
  )
  return matches.length === 1 ? matches[0]?.key || '' : ''
}

interface EvidenceExcerpt {
  label: string
  text: string
}

function compactEvidenceExcerpt(value: string) {
  const compact = String(value || '')
    .replace(/\s+/gu, ' ')
    .trim()
  if (!compact) return ''
  return compact.length > 180 ? `${compact.slice(0, 180)}…` : compact
}

function resolveEvidenceExcerpt(evidence: QCRecordCompareEvidence): EvidenceExcerpt | null {
  const document = matchDocumentById(evidence)
  if (document) {
    const sectionKey = findSectionKey(document, evidence.section_field_path)
    const section = document.sections?.find((item) => item.key === sectionKey)
    const sectionText = compactEvidenceExcerpt(String(section?.text || ''))
    if (sectionText)
      return { label: `原文摘录 · ${section?.label || '对应章节'}`, text: sectionText }
  }
  // 仅展示后端已经明确提供的原文摘录；安全引用本身绝不作为“原文”回显。
  const quote = compactEvidenceExcerpt(evidence.quote)
  if (quote && quote !== String(evidence.source_ref || '').trim()) {
    return { label: '原文摘录 · 判定依据', text: quote }
  }
  // 对“字段缺失”等不可能有缺失字段原文的结论，展示已精确绑定文书的节选。
  // 该节选只用于客户核对，不能被解释为缺失字段已经存在。
  if (document) {
    const firstSection = document.sections?.find((item) => compactEvidenceExcerpt(item.text))
    const documentExcerpt = compactEvidenceExcerpt(firstSection?.text || document.content || '')
    if (documentExcerpt) {
      return {
        label: `核对文书 · ${firstSection?.label || resolveDocumentDisplayTitle(document)}`,
        text: documentExcerpt,
      }
    }
  }
  return null
}

function matchDocumentById(evidence: QCRecordCompareEvidence) {
  const sourceRef = normalizeReference(evidence.source_ref)
  if (sourceRef) {
    const referencedDocuments = documents.value.filter(
      (document) => normalizeReference(document.source_ref) === sourceRef,
    )
    const sourceTypes = [evidence.source_document_type, evidence.source_table]
      .map(normalizeReference)
      .filter(Boolean)
    if (sourceTypes.length) {
      const typedDocuments = referencedDocuments.filter((document) =>
        [document.document_type, document.source_table]
          .map(normalizeReference)
          .some((documentType) => documentType && sourceTypes.includes(documentType)),
      )
      if (typedDocuments.length === 1) return typedDocuments[0]
      if (typedDocuments.length > 1) return null
    }
    // 同一安全引用对应多种投影视图时，不允许仅凭引用顺序猜测文书。
    if (referencedDocuments.length === 1) return referencedDocuments[0]
    if (referencedDocuments.length > 1) return null
  }
  const sourceId = normalizeReference(evidence.source_document_id)
  if (!sourceId) return null
  return (
    documents.value.find(
      (document) =>
        normalizeReference(document.source_document_id) === sourceId ||
        normalizeReference(document.key) === sourceId,
    ) || null
  )
}

function scoreDocumentMetadata(
  document: EditableMedicalRecordDocument,
  evidence: QCRecordCompareEvidence,
) {
  const documentTypes = [document.document_type, document.source_table, document.title].map(
    normalizeReference,
  )
  const sourceTypes = [
    evidence.source_document_type,
    evidence.source_table,
    evidence.source_document_name,
    selectedIssue.value?.target_document_type,
    selectedIssue.value?.rule_name,
  ]
    .map(normalizeReference)
    .filter(Boolean)
  let score = 0
  sourceTypes.forEach((sourceType) => {
    documentTypes.forEach((documentType) => {
      if (!documentType) return
      if (sourceType === documentType) score = Math.max(score, 8)
      else if (sourceType.includes(documentType) || documentType.includes(sourceType)) {
        score = Math.max(score, 5)
      }
    })
  })
  const evidenceDate = normalizeDate(evidence.record_time)
  const documentDate = normalizeDate(document.record_time || document.submit_time)
  if (evidenceDate && documentDate && evidenceDate === documentDate) score += 3
  return score
}

function matchDocumentByMetadata(evidence: QCRecordCompareEvidence) {
  return (
    documents.value
      .map((document) => ({ document, score: scoreDocumentMetadata(document, evidence) }))
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score)[0]?.document || null
  )
}

async function applyLocatedDocument(
  document: EditableMedicalRecordDocument,
  range: { start: number; end: number } | null,
  sectionKey = '',
) {
  selectedDocumentKey.value = document.key
  matchedRange.value = range
  matchedSectionKey.value = range ? '' : sectionKey
  locationState.value = range ? 'matched' : sectionKey ? 'section' : 'document'
  mobileTab.value = 'record'
  await nextTick()
  if (range) highlightElement.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  else if (sectionKey) {
    const sectionElement = Array.from(
      recordScroller.value?.querySelectorAll<HTMLElement>('[data-section-key]') || [],
    ).find((element) => element.dataset.sectionKey === sectionKey)
    sectionElement?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  } else recordScroller.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
}

async function tryLocateEvidence(
  evidence: QCRecordCompareEvidence,
  allowMetadataFallback: boolean,
) {
  const exactDocument = matchDocumentById(evidence)
  if (exactDocument) {
    const range = findQuoteRange(exactDocument, evidence.quote)
    await applyLocatedDocument(
      exactDocument,
      range,
      range ? '' : findSectionKey(exactDocument, evidence.section_field_path),
    )
    return true
  }
  // 安全引用是精确定位合同；存在但未命中时不得再猜测其他文书。
  if (normalizeReference(evidence.source_ref)) return false
  const quoteDocument = documents.value
    .map((document) => ({ document, range: findQuoteRange(document, evidence.quote) }))
    .find((item) => item.range)
  if (quoteDocument) {
    await applyLocatedDocument(quoteDocument.document, quoteDocument.range)
    return true
  }
  if (allowMetadataFallback) {
    const metadataDocument = matchDocumentByMetadata(evidence)
    if (metadataDocument) {
      await applyLocatedDocument(
        metadataDocument,
        null,
        findSectionKey(metadataDocument, evidence.section_field_path),
      )
      return true
    }
  }
  return false
}

async function locateEvidence(evidence: QCRecordCompareEvidence) {
  if (documents.value.length && (await tryLocateEvidence(evidence, true))) return
  locationState.value = 'missing'
  matchedRange.value = null
  matchedSectionKey.value = ''
}

function toCompareEvidence(evidence: SingleRecordQcEvidence): QCRecordCompareEvidence {
  return {
    key: `${evidence.source_ref}-${evidence.field_path || 'source'}`,
    source_ref: evidence.source_ref,
    source_document_type: evidence.source_type,
    source_document_name: evidence.source_label,
    record_time: evidence.record_time,
    section_field_path: evidence.field_path,
    quote: evidence.evidence_excerpt || '',
  }
}

async function locateSingleRecordEvidence(evidence: SingleRecordQcEvidence) {
  await locateEvidence(toCompareEvidence(evidence))
}

async function selectSingleRecordResult(key: string) {
  const result = singleRecordViewItems.value.find((item) => item.key === key)
  const evidence = result?.evidence?.[0]
  if (!evidence) return
  await locateSingleRecordEvidence(evidence)
}

async function locateSelectedIssue() {
  const issue = selectedIssue.value
  if (!issue) {
    locationState.value = 'idle'
    return
  }
  if (!documents.value.length) {
    locationState.value = loading.value ? 'idle' : 'missing'
    matchedRange.value = null
    matchedSectionKey.value = ''
    return
  }
  const referencedEvidences = issue.evidences.filter((evidence) =>
    normalizeReference(evidence.source_ref),
  )
  if (referencedEvidences.length) {
    const orderedReferencedEvidences = [...referencedEvidences].sort((left, right) => {
      const priority = (evidence: QCRecordCompareEvidence) => {
        if (buildQuoteCandidates(evidence.quote).length) return 3
        if (normalizeReference(evidence.section_field_path)) return 2
        return 1
      }
      return priority(right) - priority(left)
    })
    for (const evidence of orderedReferencedEvidences) {
      if (await tryLocateEvidence(evidence, false)) return
    }
    locationState.value = 'missing'
    matchedRange.value = null
    matchedSectionKey.value = ''
    return
  }
  for (const evidence of issue.evidences) {
    if (await tryLocateEvidence(evidence, false)) return
  }
  for (const evidence of issue.evidences) {
    if (await tryLocateEvidence(evidence, true)) return
  }
  const document = matchDocumentByMetadata({
    key: `${issue.key}-target-document`,
    source_document_type: issue.target_document_type,
    quote: '',
  })
  if (document) {
    await applyLocatedDocument(document, null)
    return
  }
  locationState.value = 'missing'
  matchedRange.value = null
  matchedSectionKey.value = ''
}

async function selectIssue(issueKey: string) {
  const shouldCollapse = selectedIssueKey.value === issueKey && expandedIssueKey.value === issueKey
  selectedIssueKey.value = issueKey
  expandedIssueKey.value = shouldCollapse ? '' : issueKey
  emit('select-issue', issueKey)
  if (shouldCollapse) return
  await nextTick()
  await locateSelectedIssue()
}

function emitSelectedIssue() {
  if (selectedIssueKey.value) emit('select-issue', selectedIssueKey.value)
}

function setHighlightElement(value: unknown) {
  if (value instanceof HTMLElement) highlightElement.value = value
}

function selectDocument(documentKey: string) {
  selectedDocumentKey.value = documentKey
  matchedRange.value = null
  matchedSectionKey.value = ''
  locationState.value = 'idle'
}

function isAdmissionRecordDocument(document: EditableMedicalRecordDocument) {
  const typeText = [
    document.document_type,
    document.source_table,
    document.title,
    resolveDocumentDisplayTitle(document),
  ]
    .map((value) =>
      String(value || '')
        .trim()
        .toLowerCase(),
    )
    .filter(Boolean)
    .join(' ')
  return typeText.includes('admission_record') || typeText.includes('入院记录')
}

function resolveDefaultDocumentKey() {
  return (
    documents.value.find(
      (document) => isAdmissionRecordDocument(document) && Boolean(document.content?.trim()),
    )?.key ||
    documents.value.find(isAdmissionRecordDocument)?.key ||
    documents.value.find((document) => Boolean(document.content?.trim()))?.key ||
    documents.value[0]?.key ||
    ''
  )
}

function handleDocumentSelect(event: Event) {
  selectDocument((event.target as HTMLSelectElement).value)
}

function resolveStatusTone(status: string) {
  if (status === 'non_compliant') return 'danger'
  if (['ai_suggested_non_compliant', 'evaluation_unknown', 'uncertain'].includes(status)) {
    return 'review'
  }
  if (['data_gap', 'technical_error', 'not_executed'].includes(status)) return 'warning'
  if (['compliant', 'ai_suggested_compliant'].includes(status)) return 'success'
  return 'muted'
}

async function loadDocuments() {
  const visitId = String(props.visitId || '').trim()
  const jobId = String(props.jobId || '').trim()
  const recordRef = String(props.recordRef || '').trim()
  const generation = ++loadGeneration
  documents.value = []
  selectedDocumentKey.value = ''
  matchedRange.value = null
  matchedSectionKey.value = ''
  locationState.value = 'idle'
  loadError.value = ''
  if (!visitId && !(jobId && recordRef)) {
    loadError.value = '当前结果缺少可读取病历的就诊标识'
    return
  }
  loading.value = true
  const result = await getEditableMedicalRecordDocuments(visitId || recordRef, {
    // 文书 Bundle 仍以三坐标读取；job/record_ref 仅用于结果归属，不可替代病历身份。
    institute_id: String(props.instituteId || '').trim() || undefined,
    patient_id: String(props.patientId || '').trim() || undefined,
    visit_id: visitId,
    ...(jobId && recordRef
      ? {
          job_id: jobId,
          record_ref: recordRef,
        }
      : {}),
  })
  if (generation !== loadGeneration) return
  loading.value = false
  if (!result.success || !result.data) {
    loadError.value = result.message || '读取病历文书失败'
    return
  }
  documents.value = result.data.documents.filter((document) => document.enabled !== false)
  selectedDocumentKey.value = resolveDefaultDocumentKey()
  await locateSelectedIssue()
}

watch(
  () => props.activeIssueKey,
  (value) => {
    const nextKey = String(value || '').trim()
    if (!nextKey || nextKey === selectedIssueKey.value) return
    selectedIssueKey.value = nextKey
    expandedIssueKey.value = ''
    void locateSelectedIssue()
  },
  { immediate: true },
)
watch(
  sortedIssues,
  (issues) => {
    if (issues.some((issue) => issue.key === selectedIssueKey.value)) return
    selectedIssueKey.value = issues[0]?.key || ''
    expandedIssueKey.value = ''
    void locateSelectedIssue()
  },
  { immediate: true },
)
watch(
  () => [props.visitId, props.instituteId, props.patientId, props.jobId, props.recordRef],
  () => void loadDocuments(),
  { immediate: true },
)
onBeforeUnmount(() => {
  loadGeneration += 1
  documents.value = []
})
</script>

<style scoped>
.record-compare-shell {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  color: #1d1d1f;
}
.record-compare-head,
.record-column-head {
  min-height: 54px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.record-compare-head > div:first-child,
.record-column-head > div {
  display: grid;
  gap: 2px;
}
.record-compare-head strong,
.record-column-head strong {
  font-size: 14px;
  line-height: 20px;
  font-weight: 650;
}
.record-compare-head span,
.record-column-head span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
}
.record-compare-grid {
  height: min(720px, calc(100vh - 250px));
  min-height: 560px;
  display: grid;
  grid-template-columns: 270px minmax(420px, 1fr) minmax(410px, 460px);
}
.record-document-nav,
.record-content-column,
.record-result-column {
  min-width: 0;
  min-height: 0;
}
.record-document-nav {
  border-right: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(245, 245, 247, 0.72);
  display: flex;
  flex-direction: column;
}
.record-content-column {
  background: #fff;
  display: flex;
  flex-direction: column;
}
.record-content-toolbar {
  min-height: 54px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  display: flex;
  align-items: center;
  gap: 12px;
}
.record-content-toolbar > div {
  min-width: 0;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.record-content-toolbar strong {
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-content-time {
  padding: 4px 8px;
  border-radius: 7px;
  background: rgba(0, 102, 204, 0.07);
  color: #174f83;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.record-content-time span {
  color: rgba(0, 72, 140, 0.6);
  font-size: 10px;
  font-weight: 600;
}
.record-content-time b {
  font-weight: 650;
}
.record-content-time.is-missing {
  background: rgba(245, 158, 11, 0.1);
  color: #92400e;
}
.record-location-chip {
  margin-left: auto;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.62) !important;
  font-size: 11px !important;
}
.record-location-chip.is-matched {
  background: rgba(16, 185, 129, 0.1);
  color: #047857 !important;
}
.record-location-chip.is-document {
  background: rgba(245, 158, 11, 0.12);
  color: #a16207 !important;
}
.record-location-chip.is-missing {
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c !important;
}
.record-content-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 24px 30px 54px;
  scroll-behavior: smooth;
}
.record-content-text {
  max-width: 820px;
  margin: 0 auto;
  color: #202124;
  font-family: inherit;
  font-size: 14px;
  font-weight: 450;
  line-height: 2;
  white-space: pre-wrap;
  word-break: break-word;
}
.record-content-sections {
  max-width: 820px;
  margin: 0 auto;
  display: grid;
  gap: 0;
}
.record-content-section {
  padding: 18px 0 20px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  transition:
    background 240ms ease,
    box-shadow 240ms ease;
}
.record-content-section.is-evidence-target {
  margin: 0 -14px;
  padding-right: 14px;
  padding-left: 14px;
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.07);
  box-shadow: inset 3px 0 0 rgba(245, 158, 11, 0.88);
}
.record-content-section.is-evidence-target .record-content-section-title {
  color: #a65f00;
}
.record-content-section:first-child {
  padding-top: 2px;
}
.record-content-section:last-child {
  border-bottom: 0;
}
.record-content-section-title {
  margin: 0 0 9px;
  color: #0066cc;
  font-size: 13px;
  font-weight: 650;
  line-height: 20px;
}
.record-content-section-text {
  margin: 0;
  color: #202124;
  font-size: 14px;
  font-weight: 450;
  line-height: 2;
  white-space: pre-wrap;
  word-break: break-word;
}
.record-evidence-highlight {
  padding: 2px 1px;
  border-radius: 3px;
  background: #fff0a8;
  color: #6b4b00;
  box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2);
}
.record-result-column {
  border-left: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 251, 252, 0.96);
  display: flex;
  flex-direction: column;
}
.record-result-column .record-column-head {
  background: rgba(255, 255, 255, 0.94);
}
.record-result-count {
  padding: 3px 8px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.62) !important;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.record-result-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  border-bottom: 0;
  padding: 0;
}
.record-result-entry {
  position: relative;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
  transition: background 180ms ease;
}
.record-result-entry + .record-result-entry {
  margin-top: 0;
}
.record-result-entry:hover {
  background: rgba(255, 255, 255, 0.82);
}
.record-result-entry.is-active {
  background: #fff;
}
.record-result-entry.is-expanded {
  background: #fff;
  box-shadow: inset 2px 0 0 #0066cc;
}
.record-result-entry.is-expanded .record-result-item {
  background: rgba(0, 102, 204, 0.025);
}
.record-result-item {
  width: 100%;
  position: static;
  padding: 13px 16px 14px;
  border: 0;
  border-radius: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 6px;
  transition: background 180ms ease;
}
.record-result-item:hover {
  background: rgba(0, 0, 0, 0.025);
}
.record-result-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.record-result-meta {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.record-result-status {
  width: max-content;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.62);
  font-size: 10.5px;
  font-weight: 600;
  line-height: 16px;
}
.record-result-entry.is-danger .record-result-status {
  background: rgba(239, 68, 68, 0.09);
  color: #c24136;
}
.record-result-entry.is-review .record-result-status,
.record-result-entry.is-warning .record-result-status {
  background: rgba(245, 158, 11, 0.12);
  color: #a16207;
}
.record-result-entry.is-success .record-result-status {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}
.record-result-code {
  color: #0066cc;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.record-result-item strong {
  color: #1d1d1f;
  font-size: 13.5px;
  font-weight: 650;
  line-height: 21px;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
.record-result-summary-line {
  display: -webkit-box;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.58);
  font-size: 11.5px;
  font-weight: 500;
  line-height: 18px;
  text-overflow: unset;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}
.record-result-toggle {
  color: rgba(29, 29, 31, 0.4);
  line-height: 0;
}
.record-result-toggle svg {
  display: block;
  transition: transform 180ms ease;
}
.record-result-toggle svg.is-open {
  transform: rotate(180deg);
}
.record-result-detail {
  margin: 0 16px 0 18px;
  padding: 0 0 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
}
.record-result-analysis,
.record-result-evidence {
  padding-top: 15px;
}
.record-result-section-heading {
  color: rgba(29, 29, 31, 0.56);
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.record-result-section-heading svg {
  color: rgba(0, 102, 204, 0.76);
  flex: none;
}
.record-result-detail p {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  line-height: 22px;
  white-space: pre-wrap;
}
.record-result-narrative {
  margin-top: 7px;
  display: grid;
  gap: 5px;
}
.record-result-detail .record-result-narrative-line {
  margin: 0;
}
.record-result-narrative-line.is-decision {
  padding-top: 7px;
  border-top: 1px dashed rgba(0, 0, 0, 0.08);
  color: #1d1d1f;
  font-weight: 600;
}
.record-result-comparison {
  margin-top: 15px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
  border-bottom: 1px solid rgba(0, 0, 0, 0.065);
  display: grid;
}
.record-result-comparison section {
  min-width: 0;
  padding: 12px 0 13px;
}
.record-result-comparison section + section {
  border-top: 1px dashed rgba(0, 0, 0, 0.065);
}
.record-evidence-button {
  width: 100%;
  margin-top: 6px;
  padding: 9px 8px;
  border: 0;
  border-top: 1px solid rgba(0, 0, 0, 0.055);
  border-radius: 7px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 3px;
}
.record-evidence-button:hover {
  background: rgba(0, 102, 204, 0.04);
}
.record-evidence-button strong {
  color: rgba(29, 29, 31, 0.62);
  font-size: 11px;
}
.record-evidence-button time {
  color: rgba(0, 72, 140, 0.68);
  font-size: 10.5px;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}
.record-evidence-button small {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.82);
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-evidence-button .record-evidence-excerpt {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  color: rgba(29, 29, 31, 0.82);
  text-overflow: ellipsis;
  white-space: normal;
}
.record-evidence-excerpt span {
  margin-right: 4px;
  color: rgba(0, 72, 140, 0.72);
  font-weight: 650;
}
.record-result-guidance {
  margin-top: 15px;
  padding: 10px 0 0 11px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
  border-left: 2px solid rgba(0, 102, 204, 0.32);
}
.record-result-guidance p {
  color: rgba(29, 29, 31, 0.82);
}
.record-compare-state,
.record-content-empty {
  padding: 30px 16px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  line-height: 20px;
  text-align: center;
  display: grid;
  gap: 8px;
  place-content: center;
}
.record-compare-state button {
  border: 0;
  background: transparent;
  color: #0066cc;
  cursor: pointer;
}
.record-content-empty {
  flex: 1;
}
.record-content-empty strong {
  color: rgba(29, 29, 31, 0.72);
  font-size: 14px;
}
.record-document-select,
.record-compare-mobile-tabs {
  display: none;
}
@media (max-width: 1199px) {
  .record-compare-grid {
    grid-template-columns: minmax(380px, 1fr) minmax(360px, 400px);
  }
  .record-document-nav {
    display: none;
  }
  .record-document-select {
    min-width: 180px;
    margin-left: auto;
    display: block;
  }
  .record-document-select > span {
    display: none;
  }
  .record-document-select select {
    width: 100%;
    height: 32px;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    background: #fff;
    font-size: 12px;
  }
  .record-location-chip {
    margin-left: 0;
  }
}
@media (max-width: 900px) {
  .record-compare-mobile-tabs {
    padding: 3px;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.05);
    display: flex;
  }
  .record-compare-mobile-tabs button {
    padding: 5px 10px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: rgba(29, 29, 31, 0.58);
    font-size: 12px;
  }
  .record-compare-mobile-tabs button.is-active {
    background: #fff;
    color: #0066cc;
  }
  .record-compare-grid {
    height: min(680px, calc(100vh - 230px));
    min-height: 520px;
    display: block;
  }
  .record-content-column,
  .record-result-column {
    height: 100%;
  }
  .record-compare-shell[data-mobile-tab='record'] .record-result-column,
  .record-compare-shell[data-mobile-tab='result'] .record-content-column {
    display: none;
  }
  .record-content-toolbar {
    flex-wrap: wrap;
  }
  .record-location-chip {
    order: 3;
    width: 100%;
  }
}
</style>
