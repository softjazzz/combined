<template>
  <section
    class="record-compare-shell"
    :class="{ 'is-document-only': documentOnly, 'fills-available-height': fillAvailableHeight }"
    :data-mobile-tab="mobileTab"
  >
    <header
      v-if="!documentOnly"
      class="record-compare-head"
    >
      <div>
        <strong>{{ documentOnly ? '病历文书' : '病历原文对照' }}</strong>
        <span>{{
          documentOnly
            ? '选择文书查看完整内容'
            : fallbackToCurrentActive
              ? '历史快照未保留，当前已自动展示病历最新文书用于核对'
              : lazyResultDocuments
                ? '按本次质控保存的原文核对'
                : sourceView === 'current'
                  ? '当前病历可能已更新，质控结果仍为执行时结果'
                  : '点击质控结果，核对对应文书与证据片段'
        }}</span>
      </div>
      <div
        v-if="!documentOnly"
        class="record-compare-mobile-tabs"
        role="tablist"
        aria-label="病历与结果切换"
      >
        <button
          type="button"
          role="tab"
          :aria-selected="mobileTab === 'record'"
          :class="{ 'is-active': mobileTab === 'record' }"
          @click="mobileTab = 'record'"
        >
          病历原文
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="mobileTab === 'result'"
          :class="{ 'is-active': mobileTab === 'result' }"
          @click="mobileTab = 'result'"
        >
          质控结果
        </button>
      </div>
    </header>

    <div
      v-if="fallbackToCurrentActive && fallbackNotice && !documentOnly"
      class="record-compare-fallback-banner"
      data-testid="record-compare-fallback-notice"
      role="status"
    >
      {{ fallbackNotice }}
    </div>

    <div class="record-compare-grid">
      <ReadonlyMedicalDocumentDirectory
        class="record-document-nav"
        :documents="documents"
        :selected-key="selectedDocumentKey"
        :loading="loading"
        :error="loadError"
        :summary-only="lazyResultDocuments"
        :orders-load-state="ordersLoadState"
        @select="selectDocument"
        @retry="loadDocuments"
        @load-orders="loadOrders"
      />

      <section
        class="record-content-column"
        aria-label="病历原文"
      >
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
              <span>{{ resolveMedicalDocumentTimeLabel(selectedDocument) }}</span>
              <b>{{ formatDocumentTime(resolveDocumentTime(selectedDocument)) }}</b>
            </time>
            <time
              v-if="
                selectedDocument && isAdmissionRecordDocument(selectedDocument) && admissionTime
              "
              class="record-content-time"
              data-testid="record-admission-time"
            >
              <span>入院时间</span>
              <b>{{ formatDocumentTime(admissionTime) }}</b>
            </time>
            <time
              v-if="
                selectedDocument &&
                  resolveMedicalDocumentTypeLabel(selectedDocument) === '出院记录' &&
                  dischargeTime
              "
              class="record-content-time"
              data-testid="record-discharge-time"
            >
              <span>出院时间</span>
              <b>{{ formatDocumentTime(dischargeTime) }}</b>
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
              <template
                v-for="document in pdfDocumentDirectory.primaryDocuments"
                :key="document.key"
              >
                <option :value="document.key">
                  {{ resolveDocumentDisplayTitle(document) }}
                </option>
                <optgroup
                  v-if="pdfDocumentDirectory.versionsByParent.has(document.key)"
                  :label="`${resolveDocumentDisplayTitle(document)} · PDF对照版本`"
                >
                  <option
                    v-for="version in pdfDocumentDirectory.versionsByParent.get(document.key)"
                    :key="version.key"
                    :value="version.key"
                  >
                    {{
                      version.pdf_review_relation === 'same_content'
                        ? 'PDF文本（正文一致）'
                        : 'PDF版本（待核对）'
                    }}
                    · {{ formatDocumentTime(resolveDocumentTime(version)) }}
                  </option>
                </optgroup>
              </template>
            </select>
          </label>
          <button
            v-if="ordersLoadState"
            type="button"
            class="record-load-orders-btn"
            :class="{ 'is-failed': ordersLoadState === 'failed' }"
            data-testid="record-narrow-load-orders"
            :disabled="ordersLoadState === 'loading'"
            @click="loadAndSelectOrders"
          >
            {{
              ordersLoadState === 'loading'
                ? '读取医嘱中…'
                : ordersLoadState === 'failed'
                  ? '重试加载医嘱'
                  : '查看医嘱'
            }}
          </button>
          <span
            v-if="!documentOnly"
            class="record-location-chip"
            :class="`is-${locationState}`"
          >
            {{ locationMessage }}
          </span>
        </div>

        <HospitalLoading
          v-if="loading || contentLoading"
          :label="loading ? '正在读取文书目录' : '正在读取文书正文'"
          fill
        />
        <div
          v-else-if="contentLoadError"
          class="record-content-empty"
        >
          <strong>当前文书读取失败</strong>
          <span>{{ contentLoadError }}</span>
          <button
            type="button"
            class="record-content-retry"
            @click="retrySelectedDocument"
          >
            重新读取
          </button>
        </div>
        <div
          v-else-if="selectedDocument"
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
          <ReadonlyFrontpageContent
            v-else-if="
              selectedDocument.document_type === 'mr' && selectedDocument.frontpage_display
            "
            :display="selectedDocument.frontpage_display"
          />
          <div
            v-else-if="documentSectionViews.length"
            class="record-content-sections"
          >
            <section
              v-for="section in documentSectionViews"
              :key="section.key"
              class="record-content-section"
              :class="{
                'is-evidence-target': section.isMatchedSection,
                'has-block-highlight': section.isBlockHighlight,
              }"
              :data-section-key="section.key"
            >
              <h3 class="record-content-section-title">
                {{ section.displayLabel }}
              </h3>
              <p class="record-content-section-text">
                <span>{{ section.parts.before }}</span><mark
                  v-if="section.parts.match"
                  :ref="setHighlightElement"
                  class="record-evidence-highlight"
                  :class="{
                    'is-block-highlight': section.isBlockHighlight,
                    'is-interactive': Boolean(selectedIssueKey),
                  }"
                  :tabindex="selectedIssueKey ? 0 : undefined"
                  @click="selectedIssueKey ? emitSelectedIssue() : undefined"
                  @keydown.enter="selectedIssueKey ? emitSelectedIssue() : undefined"
                >{{ section.parts.match }}</mark><span>{{ section.parts.after }}</span>
              </p>
            </section>
          </div>
          <ReadonlyMedicalDocumentContent
            v-else-if="hasStructuredReportFallback(selectedDocument)"
            :document="selectedDocument"
          />
          <pre
            v-else
            class="record-content-text"
          ><span>{{ documentTextParts.before }}</span><mark
                v-if="documentTextParts.match"
                :ref="setHighlightElement"
                class="record-evidence-highlight"
                :class="{
                  'is-block-highlight': documentTextIsBlockHighlight,
                  'is-interactive': Boolean(selectedIssueKey),
                }"
                :tabindex="selectedIssueKey ? 0 : undefined"
                @click="selectedIssueKey ? emitSelectedIssue() : undefined"
                @keydown.enter="selectedIssueKey ? emitSelectedIssue() : undefined"
          >{{ documentTextParts.match }}</mark><span>{{ documentTextParts.after }}</span></pre>
        </div>
        <div
          v-else-if="lazyResultDocuments && !loadError && (documents.length || ordersLoadState)"
          class="record-content-empty"
        >
          <strong>请选择文书查看原文</strong>
        </div>
        <div
          v-else
          class="record-content-empty"
        >
          <strong>{{ documentOnly ? '暂无病历文书' : '暂无可对照的病历原文' }}</strong>
          <span>{{
            documentOnly
              ? '当前没有可展示的文书内容。'
              : '质控结果仍可查看，但当前无法定位到来源文书。'
          }}</span>
        </div>
      </section>

      <aside
        v-if="!documentOnly"
        class="record-result-column"
        aria-label="质控结果"
      >
        <SingleRecordQcResultPanel
          v-if="hasSingleRecordResult"
          :items="singleRecordItems || []"
          :debug-context="debugContext"
          :presentation-mode="presentationMode"
          :feedback-by-rule="feedbackByRule"
          :feedback-enabled="feedbackEnabled"
          :feedback-loading="feedbackLoading"
          :feedback-error="feedbackError"
          :feedback-error-by-rule="feedbackErrorByRule"
          :feedback-saving-rule-id="feedbackSavingRuleId"
          @select="selectSingleRecordResult"
          @locate-evidence="locateSingleRecordEvidence"
          @submit-feedback="handleSubmitFeedback"
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
                <strong :title="displayQcRuleName(issue.rule_name, issue.rule_code)">{{
                  displayQcRuleName(issue.rule_name, issue.rule_code)
                }}</strong>
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
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import { ChevronDown, ClipboardCheck, FileSearch, Lightbulb, Scale, Target } from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
  getEditableMedicalRecordDocument,
  getEditableMedicalRecordDocuments,
} from '@/services/manual-case-sample-service'
import ReadonlyMedicalDocumentDirectory from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentDirectory.vue'
import ReadonlyMedicalDocumentContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue'
import ReadonlyFrontpageContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyFrontpageContent.vue'
import ReadonlyMedicalOrderTable from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalOrderTable.vue'
import SingleRecordQcResultPanel from '@/views/workstation-v4/customer-sample-validation/SingleRecordQcResultPanel.vue'
import HospitalLoading from '@/components/qc/HospitalLoading.vue'
import {
  deduplicateMedicalDocumentSections,
  displayMedicalDocumentSectionText,
  formatDiagnosisSection,
  resolvePreliminaryDiagnosisDisplay,
  formatMedicalDocumentTime,
  isMedicalOrderDocument,
  resolveMedicalDocumentTime,
  resolveMedicalDocumentTimeLabel,
  resolveMedicalDocumentTitle,
  resolveMedicalDocumentTypeLabel,
} from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'
import { resolveSafeMedicalSectionLabel } from '@/utils/medicalFieldLabels'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'
import { groupPdfDocumentVersions } from '@/views/workstation-v4/customer-sample-validation/pdfDocumentVersions'
import {
  buildSingleRecordQcResultItems,
  displayQcRuleName,
  recommendationEvidenceForSingleRecord,
  type SingleRecordQcEvidence,
  type SingleRecordQcResultItem,
} from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'
import type {
  QCRecordCompareEvidence,
  QCRecordCompareIssue,
} from '@/views/workstation-v4/semantic-rules/types'
import type { SaveQcResultFeedbackInput } from '@/api/qc-result-feedback-demo'
import type { QcResultDebugContext } from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'
import { useQcResultFeedback } from '@/views/workstation-v4/customer-sample-validation/useQcResultFeedback'

const { confirmedResultsOnly } = useQcResultVisibility()

const props = withDefaults(
  defineProps<{
    visitId: string
    documentOnly?: boolean
    fillAvailableHeight?: boolean
    sourceView?: 'saved' | 'current'
    lazyResultDocuments?: boolean
    /** 当前病历完整文书；传入后不再请求历史 Bundle 目录或正文。 */
    providedDocuments?: EditableMedicalRecordDocument[]
    /** 后端解析的本次住院入院时间，仅用于展示。 */
    admissionTime?: string
    /** 已有住院信息中的出院时间，不使用文书记录时间替代。 */
    dischargeTime?: string
    jobId?: string
    recordRef?: string
    instituteId?: string
    patientId?: string
    issues: QCRecordCompareIssue[]
    /** 单病历纵向切片专用；存在时右栏不再使用批量结果旧模型。 */
    singleRecordItems?: SingleRecordQcResultItem[]
    /** 未完成整例交付的保存结果可查看，但不冒充可反馈的正式结果。 */
    feedbackAvailable?: boolean
    presentationMode?: 'flat' | 'grouped'
    debugContext?: QcResultDebugContext
    activeIssueKey?: string
  }>(),
  { presentationMode: 'flat', sourceView: 'saved', feedbackAvailable: true },
)

const emit = defineEmits<{
  (event: 'select-issue', issueKey: string): void
}>()

const qcFeedback = useQcResultFeedback(
  () => (props.feedbackAvailable ? props.jobId : undefined),
  () => props.recordRef,
)
const feedbackByRule = qcFeedback.feedbackByRule
const feedbackEnabled = qcFeedback.isEnabled
const feedbackLoading = qcFeedback.loading
const feedbackError = qcFeedback.error
const feedbackErrorByRule = qcFeedback.errorByRule
const feedbackSavingRuleId = qcFeedback.savingRuleId

function handleSubmitFeedback(ruleId: string, input: SaveQcResultFeedbackInput) {
  if (!props.feedbackAvailable) return
  void qcFeedback.save(ruleId, input)
}

type LocationState = 'matched' | 'section' | 'document' | 'missing' | 'idle'

const documents = ref<EditableMedicalRecordDocument[]>([])
const pdfDocumentDirectory = computed(() => groupPdfDocumentVersions(documents.value))
const loading = ref(false)
const ordersLoadState = ref<'deferred' | 'loading' | 'failed'>()
let orderRequest: Promise<void> | undefined
let documentSelectionSequence = 0
const loadError = ref('')
const contentLoadError = ref('')
const fallbackToCurrentActive = ref(false)
const fallbackNotice = ref('')
const contentLoadingKey = ref('')
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
const documentRequests = new Map<string, ReturnType<typeof getEditableMedicalRecordDocument>>()

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
  const sourceLabel =
    resolveMedicalDocumentTypeLabel(evidence.source_document_name) ||
    resolveMedicalDocumentTypeLabel(evidence.source_document_type) ||
    resolveMedicalDocumentTypeLabel(evidence.source_table) ||
    '来源文书'
  if (evidence.recommendation_index && evidence.evidence_role) {
    const roleLabel = evidence.evidence_role === 'opinion' ? '会诊意见' : '执行证据'
    return `第${evidence.recommendation_index}条建议 · ${roleLabel} · ${sourceLabel}`
  }
  return sourceLabel
}

function resolveDocumentTime(document: EditableMedicalRecordDocument) {
  return resolveMedicalDocumentTime(document)
}

const sortedIssues = computed(() =>
  props.issues
    .filter((issue) => !confirmedResultsOnly.value || issue.status === 'non_compliant')
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
  buildSingleRecordQcResultItems(props.singleRecordItems).filter(
    (item) => !confirmedResultsOnly.value || item.status === 'non_compliant',
  ),
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
function displaySectionLabel(value?: string): string {
  return resolveSafeMedicalSectionLabel(value)
}

const contentLoading = computed(
  () => Boolean(selectedDocumentKey.value) && contentLoadingKey.value === selectedDocumentKey.value,
)
const locationMessage = computed(() => {
  if (loading.value) return '正在读取文书目录'
  if (contentLoading.value) return '正在读取当前文书'
  if (contentLoadError.value) return '当前文书读取失败'
  if (loadError.value) return '原文读取失败'
  if (locationState.value === 'matched') return '已定位到证据段落'
  if (locationState.value === 'section') {
    const section = selectedDocument.value?.sections?.find(
      (item) => item.key === matchedSectionKey.value,
    )
    const label = section && (resolvePreliminaryDiagnosisDisplay(section)?.label || section.label)
    return label ? `已定位到${displaySectionLabel(label)}章节` : '已定位到对应章节'
  }
  if (locationState.value === 'document') return '已定位到文书，未定位到具体片段'
  if (locationState.value === 'missing') return '未找到对应文书，请手动核对'
  return selectedDocument.value ? '手动浏览文书' : '等待选择质控结果'
})
function isBlockEvidenceMatch(parts: { before: string; match: string; after: string }) {
  const match = parts.match.trim()
  if (!match) return false
  if (!parts.before.trim() && !parts.after.trim()) return true
  const startsOnNewLine = !parts.before || /\n[ \t]*$/u.test(parts.before)
  const endsOnNewLine = !parts.after || /^[ \t]*\n/u.test(parts.after)
  return startsOnNewLine && endsOnNewLine && (match.includes('\n') || match.length >= 60)
}

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
const documentTextIsBlockHighlight = computed(() => isBlockEvidenceMatch(documentTextParts.value))

const documentSectionViews = computed(() => {
  const document = selectedDocument.value
  const sections = deduplicateMedicalDocumentSections(document?.sections || [])
  if (!document || !sections.length) return []
  const content = document.content || ''
  const range = matchedRange.value
  let cursor = 0
  return sections.map((section) => {
    const text = displayMedicalDocumentSectionText(section)
    const sectionStart = content.indexOf(text, cursor)
    if (sectionStart >= 0) cursor = sectionStart + text.length
    const localStart =
      range &&
      sectionStart >= 0 &&
      range.start >= sectionStart &&
      range.end <= sectionStart + text.length
        ? range.start - sectionStart
        : -1
    const quote = localStart >= 0 && range ? text.slice(localStart, range.end - sectionStart) : ''
    const preliminary = resolvePreliminaryDiagnosisDisplay(section, text)
    let displayedText = preliminary?.text ?? formatDiagnosisSection(section.label, text)
    let quoteStart = -1
    if (quote) {
      const uniqueInSource =
        preliminary && text.indexOf(quote) === localStart && text.lastIndexOf(quote) === localStart
      quoteStart = uniqueInSource ? displayedText.indexOf(quote) : -1
      if (quoteStart < 0 || quoteStart !== displayedText.lastIndexOf(quote)) {
        // 无法在展示文本中唯一复现时，按原定位显示证据，避免高亮另一处相同文字。
        displayedText = text
        quoteStart = localStart
      }
    }
    const parts =
      quoteStart >= 0
        ? {
            before: displayedText.slice(0, quoteStart),
            match: quote,
            after: displayedText.slice(quoteStart + quote.length),
          }
        : { before: displayedText, match: '', after: '' }
    return {
      ...section,
      displayLabel: displaySectionLabel(preliminary?.label || section.label),
      isMatchedSection: matchedSectionKey.value === section.key,
      isBlockHighlight: isBlockEvidenceMatch(parts),
      parts,
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
  return matchDocumentByIdWithOverride(evidence)?.document || null
}

type DocumentMatch = {
  document: EditableMedicalRecordDocument
  renderSourceDocumentId?: string
  renderSourceRef?: string
}

function matchDocumentByIdWithOverride(evidence: QCRecordCompareEvidence): DocumentMatch | null {
  const sourceRef = normalizeReference(evidence.source_ref)
  if (sourceRef) {
    const referencedDocuments = documents.value.filter(
      (document) => normalizeReference(document.source_ref) === sourceRef,
    )
    const sourceTypes = [evidence.source_document_type, evidence.source_table]
      .map(normalizeReference)
      .filter(Boolean)
    const matchesSource = (...types: (string | undefined)[]) =>
      types.map(normalizeReference).some((type) => type && sourceTypes.includes(type))
    const directMatches = sourceTypes.length
      ? referencedDocuments.filter((document) =>
          matchesSource(document.document_type, document.source_table),
        )
      : referencedDocuments
    const aliasMatches = documents.value.flatMap((document) =>
      (document.source_document_aliases || [])
        .filter((alias) => normalizeReference(alias.source_ref) === sourceRef)
        .map((alias) => ({ document, alias })),
    )
    const typedAliasMatches = sourceTypes.length
      ? aliasMatches.filter(({ document, alias }) =>
          alias.source_document_type
            ? matchesSource(alias.source_document_type)
            : matchesSource(document.document_type, document.source_table),
        )
      : aliasMatches
    if (directMatches.length > 1 || typedAliasMatches.length > 1) return null
    if (typedAliasMatches.length === 1) {
      const { document, alias } = typedAliasMatches[0]
      const rendersListedDocument = alias.source_document_id === document.source_document_id
      // 直接引用与别名指向不同原文时，保留无法定位状态。
      if (directMatches[0] && (directMatches[0] !== document || !rendersListedDocument)) {
        return null
      }
      if (rendersListedDocument) return { document }
      return {
        document,
        renderSourceDocumentId: alias.source_document_id,
        renderSourceRef: alias.source_ref,
      }
    }
    if (directMatches.length === 1) return { document: directMatches[0] }
    // 已声明检查来源的证据不能命中另一来源恰好同号的文书。
    if (sourceTypes.some((type) => type === 'exam_master' || type === 'exam_item_report')) {
      return null
    }
    if (referencedDocuments.length === 1) return { document: referencedDocuments[0] }
    if (referencedDocuments.length > 1) return null
  }
  const sourceId = normalizeReference(evidence.source_document_id)
  if (!sourceId) return null
  const sourceDocument = documents.value.find(
    (document) =>
      normalizeReference(document.source_document_id) === sourceId ||
      normalizeReference(document.key) === sourceId,
  )
  return sourceDocument ? { document: sourceDocument } : null
}

function hasStructuredReportFallback(document: EditableMedicalRecordDocument) {
  return (
    Boolean(document.report_items?.length) &&
    !document.content?.trim() &&
    !deduplicateMedicalDocumentSections(document.sections || []).length
  )
}

function isDocumentLoaded(document: EditableMedicalRecordDocument) {
  return (
    isMedicalOrderDocument(document) ||
    document.content_loaded === true ||
    Boolean(document.content?.trim()) ||
    Boolean(document.sections?.length) ||
    Boolean(document.report_items?.length)
  )
}

function replaceDocument(document: EditableMedicalRecordDocument) {
  documents.value = documents.value.map((item) =>
    item.key === document.key ? { ...item, ...document } : item,
  )
}

const DEFAULT_HISTORICAL_FALLBACK_NOTICE =
  '该历史质控轮次未保留冻结原文快照，当前已自动展示病历最新文书用于核对。'

function localizeDocumentError(rawMessage: string | undefined, fallback: string): string {
  const text = String(rawMessage || '').trim()
  if (!text) return fallback
  if (text.includes('historical_material_snapshot_not_retained')) {
    return DEFAULT_HISTORICAL_FALLBACK_NOTICE
  }
  if (text.includes('historical_material_snapshot_unavailable')) {
    return '历史病历原文快照暂不可用，请稍后重试或查看当前最新病历文书。'
  }
  if (text.includes('historical_and_current_material_views_conflict')) {
    return '历史快照与当前病历视图参数冲突，请重新打开病历原文。'
  }
  return text
}

function isHistoricalSnapshotNotRetained(result: {
  success?: boolean
  status?: number
  errorCode?: string
  message?: string
}): boolean {
  if (result.success) return false
  const code = String(result.errorCode || '').trim()
  const message = String(result.message || '').trim()
  if (code === 'historical_material_snapshot_not_retained') return true
  if (message.includes('historical_material_snapshot_not_retained')) return true
  if (result.status === 409 && message.includes('冻结原文快照')) return true
  return false
}

function applyMaterialFallbackMetadata(data: unknown) {
  if (!data || typeof data !== 'object') return
  const candidate = data as {
    material_source_fallback?: unknown
    material_source_notice?: unknown
  }
  if (candidate.material_source_fallback === true) {
    fallbackToCurrentActive.value = true
    const notice =
      typeof candidate.material_source_notice === 'string' && candidate.material_source_notice.trim()
        ? candidate.material_source_notice.trim()
        : DEFAULT_HISTORICAL_FALLBACK_NOTICE
    fallbackNotice.value = notice
  }
}

async function ensureDocumentLoaded(
  documentKey: string,
  renderOverride?: { sourceDocumentId: string; sourceRef?: string },
) {
  const summary = documents.value.find((document) => document.key === documentKey)
  if (!summary) return null
  if (isMedicalOrderDocument(summary)) return summary
  const currentClinicalSurgery = props.sourceView === 'current' && Boolean(summary.clinical_surgery_version)
  if (!currentClinicalSurgery) {
    if (props.providedDocuments !== undefined || props.sourceView === 'current') return summary
    if (!renderOverride && isDocumentLoaded(summary)) return summary
  }
  if (!summary.execution_domain && !props.lazyResultDocuments) {
    if (selectedDocumentKey.value === documentKey) {
      contentLoadError.value = '当前文书缺少按需读取标识，请刷新页面后重试。'
    }
    return null
  }

  const generation = loadGeneration
  if (selectedDocumentKey.value === documentKey) {
    contentLoadingKey.value = documentKey
    contentLoadError.value = ''
  }
  const requestKey = renderOverride?.sourceDocumentId
    ? `${documentKey}::${renderOverride.sourceDocumentId}`
    : documentKey
  let request = documentRequests.get(requestKey)
  try {
    if (!request) {
      const renderSummary = renderOverride
        ? {
            ...summary,
            source_document_id: renderOverride.sourceDocumentId,
            ...(renderOverride.sourceRef ? { source_ref: renderOverride.sourceRef } : {}),
          }
        : props.lazyResultDocuments
          ? { ...summary, source_document_id: summary.key }
          : summary
      const useHistoricalFallback = Boolean(
        props.lazyResultDocuments && props.jobId && props.sourceView !== 'current',
      )
      request = (async () => {
        const initialResult = await getEditableMedicalRecordDocument(props.visitId, renderSummary, {
          ...(props.jobId ? { job_id: props.jobId } : {}),
          ...(props.sourceView === 'saved' && props.jobId && props.recordRef
            ? { record_ref: props.recordRef }
            : {}),
          ...(useHistoricalFallback ? { fallback_to_current: true } : {}),
          institute_id: String(props.instituteId || '').trim() || undefined,
          patient_id: String(props.patientId || '').trim() || undefined,
          visit_id: String(props.visitId || '').trim(),
        })
        if (!initialResult.success && props.jobId && isHistoricalSnapshotNotRetained(initialResult)) {
          const fallbackResult = await getEditableMedicalRecordDocument(
            props.visitId,
            renderSummary,
            {
              source_view: 'current',
              institute_id: String(props.instituteId || '').trim() || undefined,
              patient_id: String(props.patientId || '').trim() || undefined,
              visit_id: String(props.visitId || '').trim(),
            },
          )
          if (fallbackResult.success) {
            fallbackToCurrentActive.value = true
            fallbackNotice.value = fallbackNotice.value || DEFAULT_HISTORICAL_FALLBACK_NOTICE
          }
          return fallbackResult
        }
        return initialResult
      })()
      documentRequests.set(requestKey, request)
    }
    const result = await request
    if (generation !== loadGeneration) return null
    if (!result.success || !result.data) {
      if (selectedDocumentKey.value === documentKey) {
        contentLoadError.value = localizeDocumentError(result.message, '读取当前文书失败')
      }
      return null
    }
    const loadedDocument = {
      ...summary,
      ...result.data,
      // 仅使用 override 作为渲染请求参数，目录仍保留汇总项身份与安全引用。
      key: summary.key,
      source_document_id: summary.source_document_id,
      source_ref: summary.source_ref,
      source_document_aliases: summary.source_document_aliases,
      content_loaded: true,
    }
    replaceDocument(loadedDocument)
    return loadedDocument
  } catch {
    if (generation !== loadGeneration) return null
    if (selectedDocumentKey.value === documentKey) {
      contentLoadError.value = '读取当前文书失败'
    }
    return null
  } finally {
    if (request && documentRequests.get(requestKey) === request) {
      documentRequests.delete(requestKey)
    }
    if (generation === loadGeneration && contentLoadingKey.value === documentKey) {
      contentLoadingKey.value = ''
    }
  }
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
  sequence?: number,
) {
  selectedDocumentKey.value = document.key
  const isOrderDoc = isMedicalOrderDocument(document)
  const isFrontpageDoc = document.document_type === 'mr' && Boolean(document.frontpage_display)
  const isStructuredReportDoc = hasStructuredReportFallback(document)
  const supportsInlineHighlight = !isOrderDoc && !isFrontpageDoc && !isStructuredReportDoc

  matchedRange.value = supportsInlineHighlight ? range : null
  let hasVisibleQuoteHighlight = false
  if (matchedRange.value) {
    if (documentSectionViews.value.length) {
      hasVisibleQuoteHighlight = documentSectionViews.value.some((section) =>
        Boolean(section.parts.match),
      )
    } else {
      hasVisibleQuoteHighlight = Boolean(documentTextParts.value.match)
    }
  }
  if (!hasVisibleQuoteHighlight) {
    matchedRange.value = null
  }

  const effectiveSectionKey = hasVisibleQuoteHighlight ? '' : sectionKey
  matchedSectionKey.value = effectiveSectionKey
  locationState.value = hasVisibleQuoteHighlight
    ? 'matched'
    : effectiveSectionKey
      ? 'section'
      : 'document'
  mobileTab.value = 'record'
  await nextTick()
  if (sequence !== undefined && sequence !== documentSelectionSequence) return
  if (isOrderDoc) {
    let activeOrderRow = recordScroller.value?.querySelector<HTMLElement>(
      '.editable-copy-order-table-wrap tbody tr.is-active',
    )
    if (!activeOrderRow) {
      await nextTick()
      if (sequence !== undefined && sequence !== documentSelectionSequence) return
      activeOrderRow = recordScroller.value?.querySelector<HTMLElement>(
        '.editable-copy-order-table-wrap tbody tr.is-active',
      )
    }
    activeOrderRow?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  } else if (hasVisibleQuoteHighlight) {
    highlightElement.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  } else if (effectiveSectionKey) {
    const sectionElement = Array.from(
      recordScroller.value?.querySelectorAll<HTMLElement>('[data-section-key]') || [],
    ).find((element) => element.dataset.sectionKey === effectiveSectionKey)
    sectionElement?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  } else {
    recordScroller.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
  }
}

async function tryLocateEvidence(
  evidence: QCRecordCompareEvidence,
  allowMetadataFallback: boolean,
  sequence = documentSelectionSequence,
) {
  const exactMatch = matchDocumentByIdWithOverride(evidence)
  if (exactMatch) {
    const exactSummary = exactMatch.document
    selectedDocumentKey.value = exactSummary.key
    matchedRange.value = null
    matchedSectionKey.value = ''
    locationState.value = 'idle'
    const exactDocument = await ensureDocumentLoaded(
      exactSummary.key,
      exactMatch.renderSourceDocumentId
        ? {
            sourceDocumentId: exactMatch.renderSourceDocumentId,
            sourceRef: exactMatch.renderSourceRef,
          }
        : undefined,
    )
    if (!exactDocument || sequence !== documentSelectionSequence) return false
    const range = findQuoteRange(exactDocument, evidence.quote)
    await applyLocatedDocument(
      exactDocument,
      range,
      findSectionKey(exactDocument, evidence.section_field_path),
      sequence,
    )
    return true
  }
  // 安全引用是精确定位合同；存在但未命中时不得再猜测其他文书。
  if (normalizeReference(evidence.source_ref)) return false
  const quoteDocument = documents.value
    .filter(isDocumentLoaded)
    .map((document) => ({ document, range: findQuoteRange(document, evidence.quote) }))
    .find((item) => item.range)
  if (quoteDocument) {
    await applyLocatedDocument(
      quoteDocument.document,
      quoteDocument.range,
      findSectionKey(quoteDocument.document, evidence.section_field_path),
      sequence,
    )
    return true
  }
  if (allowMetadataFallback) {
    const metadataSummary = matchDocumentByMetadata(evidence)
    if (metadataSummary) {
      selectedDocumentKey.value = metadataSummary.key
      matchedRange.value = null
      matchedSectionKey.value = ''
      locationState.value = 'idle'
      const metadataDocument = await ensureDocumentLoaded(metadataSummary.key)
      if (!metadataDocument || sequence !== documentSelectionSequence) return false
      await applyLocatedDocument(
        metadataDocument,
        null,
        findSectionKey(metadataDocument, evidence.section_field_path),
        sequence,
      )
      return true
    }
  }
  return false
}

async function locateEvidence(evidence: QCRecordCompareEvidence) {
  const sequence = ++documentSelectionSequence
  if (
    ordersLoadState.value &&
    [evidence.source_document_type, evidence.source_table].some((type) =>
      normalizeReference(type).includes('order'),
    )
  ) {
    await loadOrders()
  }
  if (sequence !== documentSelectionSequence) return
  if (documents.value.length && (await tryLocateEvidence(evidence, true, sequence))) return
  if (sequence !== documentSelectionSequence) return
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
    recommendation_index: evidence.recommendation_index,
    evidence_role: evidence.evidence_role,
    quote: evidence.evidence_excerpt || '',
  }
}

const EXAM_LAB_COURSE_EVIDENCE_TYPES = new Set([
  'first_course_record',
  'daily_course_record',
  'senior_course_record',
  'rescue_record',
])

function displayEvidenceForSingleRecord(item: SingleRecordQcResultItem): SingleRecordQcEvidence[] {
  const evidence = recommendationEvidenceForSingleRecord(item)
  if (
    item.status !== 'non_compliant' ||
    !['LX0609-06-01-04', 'LX0609-06-01-05', 'LX0609-06-03-03', 'LX0609-06-03-04'].includes(
      item.rule_id,
    )
  ) {
    return evidence
  }
  return evidence.filter((entry) => !EXAM_LAB_COURSE_EVIDENCE_TYPES.has(entry.source_type || ''))
}

async function locateSingleRecordEvidence(evidence: SingleRecordQcEvidence) {
  await locateEvidence(toCompareEvidence(evidence))
}

async function selectSingleRecordResult(key: string) {
  const result = singleRecordViewItems.value.find((item) => item.key === key)
  const evidence = result ? displayEvidenceForSingleRecord(result)[0] : undefined
  if (!evidence) {
    ++documentSelectionSequence
    matchedRange.value = null
    matchedSectionKey.value = ''
    locationState.value = 'idle'
    return
  }
  await locateSingleRecordEvidence(evidence)
}

async function locateSelectedIssue() {
  if (props.documentOnly) return
  const sequence = ++documentSelectionSequence
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
      if (sequence !== documentSelectionSequence) return
      if (await tryLocateEvidence(evidence, false, sequence)) return
      if (sequence !== documentSelectionSequence) return
    }
    if (sequence !== documentSelectionSequence) return
    locationState.value = 'missing'
    matchedRange.value = null
    matchedSectionKey.value = ''
    return
  }
  for (const evidence of issue.evidences) {
    if (sequence !== documentSelectionSequence) return
    if (await tryLocateEvidence(evidence, false, sequence)) return
    if (sequence !== documentSelectionSequence) return
  }
  for (const evidence of issue.evidences) {
    if (sequence !== documentSelectionSequence) return
    if (await tryLocateEvidence(evidence, true, sequence)) return
    if (sequence !== documentSelectionSequence) return
  }
  if (sequence !== documentSelectionSequence) return
  const document = matchDocumentByMetadata({
    key: `${issue.key}-target-document`,
    source_document_type: issue.target_document_type,
    quote: '',
  })
  if (document) {
    selectedDocumentKey.value = document.key
    matchedRange.value = null
    matchedSectionKey.value = ''
    locationState.value = 'idle'
    const loadedDocument = await ensureDocumentLoaded(document.key)
    if (sequence !== documentSelectionSequence) return
    if (!loadedDocument) {
      locationState.value = 'missing'
      return
    }
    await applyLocatedDocument(loadedDocument, null, '', sequence)
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
  highlightElement.value = value instanceof HTMLElement ? value : null
}

async function selectDocument(documentKey: string) {
  ++documentSelectionSequence
  selectedDocumentKey.value = documentKey
  contentLoadError.value = ''
  matchedRange.value = null
  matchedSectionKey.value = ''
  locationState.value = 'idle'
  const summary = documents.value.find((document) => document.key === documentKey)
  if (summary && isMedicalOrderDocument(summary)) return
  await ensureDocumentLoaded(documentKey)
}

function isAdmissionRecordDocument(document: EditableMedicalRecordDocument) {
  return [document.document_type, document.source_table].some((type) =>
    ['admission_record', '入院记录'].includes(normalizeReference(type)),
  )
}

function findAdmissionDocument() {
  return pdfDocumentDirectory.value.primaryDocuments.find(isAdmissionRecordDocument)
}

function resolveDefaultDocumentKey() {
  return findAdmissionDocument()?.key || documents.value[0]?.key || ''
}

function handleDocumentSelect(event: Event) {
  void selectDocument((event.target as HTMLSelectElement).value)
}

function retrySelectedDocument() {
  const documentKey = selectedDocumentKey.value
  if (!documentKey) return
  documentRequests.delete(documentKey)
  void ensureDocumentLoaded(documentKey)
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

function loadOrders() {
  if (!ordersLoadState.value) return
  if (orderRequest) return orderRequest
  const generation = loadGeneration
  const visitId = props.visitId.trim()
  ordersLoadState.value = 'loading'
  orderRequest = (async () => {
    try {
      let result = await getEditableMedicalRecordDocuments(visitId, {
        institute_id: props.instituteId,
        patient_id: props.patientId,
        visit_id: visitId,
        job_id: props.jobId,
        record_ref: props.recordRef || undefined,
        view: 'summary',
        document_scope: 'orders',
        ...(props.jobId && props.sourceView !== 'current' ? { fallback_to_current: true } : {}),
      })
      if (generation !== loadGeneration) return
      if (!result.success && props.jobId && isHistoricalSnapshotNotRetained(result)) {
        const currentResult = await getEditableMedicalRecordDocuments(visitId, {
          institute_id: props.instituteId,
          patient_id: props.patientId,
          visit_id: visitId,
          view: 'full',
          source_view: 'current',
        })
        if (generation !== loadGeneration) return
        if (currentResult.success && currentResult.data) {
          fallbackToCurrentActive.value = true
          fallbackNotice.value = fallbackNotice.value || DEFAULT_HISTORICAL_FALLBACK_NOTICE
          result = {
            ...currentResult,
            data: {
              ...currentResult.data,
              documents: currentResult.data.documents.filter((document) =>
                isMedicalOrderDocument(document),
              ),
            },
          }
        } else {
          result = currentResult
        }
      }
      if (!result.success || !result.data) {
        ordersLoadState.value = 'failed'
        return
      }
      applyMaterialFallbackMetadata(result.data)
      documents.value = [
        ...documents.value,
        ...result.data.documents.filter((document) => document.enabled !== false),
      ]
      ordersLoadState.value = undefined
    } catch {
      if (generation === loadGeneration) {
        ordersLoadState.value = 'failed'
      }
    } finally {
      if (generation === loadGeneration) orderRequest = undefined
    }
  })()
  return orderRequest
}

async function loadAndSelectOrders() {
  const generation = loadGeneration
  await loadOrders()
  if (generation !== loadGeneration || ordersLoadState.value) return
  const firstOrder = documents.value.find((document) => isMedicalOrderDocument(document))
  if (firstOrder) {
    await selectDocument(firstOrder.key)
  }
}

async function loadDocuments() {
  const visitId = String(props.visitId || '').trim()
  const jobId = String(props.jobId || '').trim()
  const recordRef = String(props.recordRef || '').trim()
  const generation = ++loadGeneration
  ++documentSelectionSequence
  ordersLoadState.value = undefined
  orderRequest = undefined
  documents.value = []
  selectedDocumentKey.value = ''
  matchedRange.value = null
  matchedSectionKey.value = ''
  locationState.value = 'idle'
  loadError.value = ''
  contentLoadError.value = ''
  fallbackToCurrentActive.value = false
  fallbackNotice.value = ''
  contentLoadingKey.value = ''
  documentRequests.clear()
  loading.value = false
  if (props.providedDocuments !== undefined) {
    documents.value = props.providedDocuments.filter((document) => document.enabled !== false)
    selectedDocumentKey.value = resolveDefaultDocumentKey()
    mobileTab.value = 'record'
    if (selectedDocumentKey.value) await ensureDocumentLoaded(selectedDocumentKey.value)
    return
  }
  if ((!visitId && !(jobId && recordRef)) || (props.lazyResultDocuments && !jobId)) {
    loadError.value = '当前结果缺少可读取病历的就诊标识'
    return
  }
  loading.value = true
  try {
    const useHistoricalFallback = Boolean(
      props.lazyResultDocuments && jobId && props.sourceView !== 'current',
    )
    let result = await getEditableMedicalRecordDocuments(visitId || recordRef, {
      // 文书 Bundle 仍以三坐标读取；job/record_ref 仅用于结果归属，不可替代病历身份。
      institute_id: String(props.instituteId || '').trim() || undefined,
      patient_id: String(props.patientId || '').trim() || undefined,
      visit_id: visitId,
      ...(jobId && props.sourceView !== 'current'
        ? {
            job_id: jobId,
            ...(recordRef ? { record_ref: recordRef } : {}),
            ...(useHistoricalFallback ? { fallback_to_current: true } : {}),
          }
        : {}),
      ...(props.sourceView === 'current'
        ? { view: 'full' as const, source_view: 'current' as const }
        : {
            view: 'summary' as const,
            ...(props.lazyResultDocuments ? { document_scope: 'clinical' as const } : {}),
          }),
    })
    if (generation !== loadGeneration) return
    let clientFullFallbackLoaded = false
    if (
      !result.success &&
      jobId &&
      props.sourceView !== 'current' &&
      isHistoricalSnapshotNotRetained(result)
    ) {
      const currentFallback = await getEditableMedicalRecordDocuments(visitId || recordRef, {
        institute_id: String(props.instituteId || '').trim() || undefined,
        patient_id: String(props.patientId || '').trim() || undefined,
        visit_id: visitId,
        view: 'full',
        source_view: 'current',
      })
      if (generation !== loadGeneration) return
      if (currentFallback.success && currentFallback.data) {
        fallbackToCurrentActive.value = true
        fallbackNotice.value = DEFAULT_HISTORICAL_FALLBACK_NOTICE
        clientFullFallbackLoaded = true
      }
      result = currentFallback
    }
    loading.value = false
    if (!result.success || !result.data) {
      loadError.value = localizeDocumentError(result.message, '读取病历文书失败')
      return
    }
    applyMaterialFallbackMetadata(result.data)
    documents.value = result.data.documents.filter((document) => document.enabled !== false)
    if (props.lazyResultDocuments && !clientFullFallbackLoaded) {
      ordersLoadState.value = 'deferred'
      const defaultKey = findAdmissionDocument()?.key || resolveDefaultDocumentKey()
      if (defaultKey) await selectDocument(defaultKey)
      return
    }
    selectedDocumentKey.value = resolveDefaultDocumentKey()
    if (selectedIssue.value) await locateSelectedIssue()
    else if (selectedDocumentKey.value) await ensureDocumentLoaded(selectedDocumentKey.value)
  } catch {
    if (generation === loadGeneration) {
      loadError.value = '读取病历文书失败'
    }
  } finally {
    if (generation === loadGeneration) {
      loading.value = false
    }
  }
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
  () => [
    props.visitId,
    props.instituteId,
    props.patientId,
    props.jobId,
    props.recordRef,
    props.providedDocuments,
    props.documentOnly,
    props.sourceView,
    props.lazyResultDocuments,
  ],
  () => void loadDocuments(),
  { immediate: true },
)
onBeforeUnmount(() => {
  loadGeneration += 1
  ++documentSelectionSequence
  documentRequests.clear()
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
.record-compare-fallback-banner {
  padding: 8px 14px;
  border-bottom: 1px solid rgba(217, 119, 6, 0.18);
  background: #fffbeb;
  color: #92400e;
  font-size: 12px;
  line-height: 18px;
}
.record-compare-grid {
  /* 抽屉内可用高度不足时允许收缩，避免固定 560px 留出无效空白。 */
  height: clamp(360px, calc(100dvh - 250px), 720px);
  min-height: 0;
  display: grid;
  grid-template-columns: 270px minmax(420px, 1fr) minmax(410px, 460px);
}
.is-document-only .record-compare-grid {
  grid-template-columns: 270px minmax(0, 1fr);
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
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
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
  color: var(--mq-text-primary);
  font-size: 18px;
  font-weight: 700;
  line-height: 26px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-content-time {
  padding: 4px 8px;
  border-radius: 7px;
  background: rgba(10, 108, 255, 0.07);
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
  flex: none;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.62) !important;
  font-size: 11px !important;
  line-height: 16px;
  white-space: nowrap;
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
  margin: 0;
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
  margin: 0;
  display: grid;
  gap: 0;
}
.record-content-section {
  padding: 16px 0;
  border-bottom: 1px solid var(--mq-border);
  transition:
    background 240ms ease,
    box-shadow 240ms ease;
}
.record-content-section.is-evidence-target {
  margin: 0 -14px;
  padding-right: 14px;
  padding-left: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #edf4ff;
  box-shadow: none;
}
.record-content-section.is-evidence-target.has-block-highlight {
  margin: 0;
  padding-right: 0;
  padding-left: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.record-content-section.is-evidence-target .record-content-section-title {
  color: #1d4ed8;
}
.record-content-section:first-child {
  padding-top: 2px;
}
.record-content-section:last-child {
  border-bottom: 0;
}
.record-content-section-title {
  position: relative;
  margin: 0 0 6px;
  padding-inline-start: 10px;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-16);
  font-weight: 700;
  line-height: 24px;
}
.record-content-section-title::before {
  position: absolute;
  inset-block-start: 5px;
  inset-inline-start: 0;
  inline-size: 3px;
  block-size: 14px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.42;
  content: '';
}
.record-content-section-text {
  margin: 0;
  color: #202124;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
}
.record-evidence-highlight {
  padding: 2px 5px;
  border-radius: 5px;
  background: #dbeafe;
  color: #0f172a;
  font-weight: 500;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.28);
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  transition:
    background 160ms ease,
    box-shadow 160ms ease;
}
.record-evidence-highlight.is-interactive {
  cursor: pointer;
}
.record-evidence-highlight.is-interactive:hover,
.record-evidence-highlight.is-interactive:focus-visible {
  background: #bfdbfe;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.45);
  outline: none;
}
.record-evidence-highlight.is-block-highlight {
  display: block;
  margin: 6px 0;
  padding: 12px 15px;
  border: 1.5px solid #93c5fd;
  border-radius: 10px;
  background: #e2eeff;
  color: #0f172a;
  font-weight: 400;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.11);
}
.record-evidence-highlight.is-block-highlight::before {
  content: '定位原文';
  display: block;
  width: fit-content;
  margin-bottom: 7px;
  padding: 1px 8px;
  border-radius: 999px;
  background: #2563eb;
  color: #ffffff;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  letter-spacing: 0.02em;
}
.record-evidence-highlight.is-block-highlight.is-interactive:hover,
.record-evidence-highlight.is-block-highlight.is-interactive:focus-visible {
  background: #d8e8ff;
  border-color: #60a5fa;
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.15);
  outline: none;
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
  box-shadow: inset 2px 0 0 #0a6cff;
}
.record-result-entry.is-expanded .record-result-item {
  background: rgba(10, 108, 255, 0.025);
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
  color: var(--mq-text-tertiary);
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
  color: rgba(10, 108, 255, 0.76);
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
  background: rgba(10, 108, 255, 0.04);
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
  border-left: 2px solid rgba(10, 108, 255, 0.32);
}
.record-result-guidance p {
  color: rgba(29, 29, 31, 0.82);
}
.record-compare-state,
.record-content-empty {
  padding: 30px 16px;
  color: var(--mq-text-tertiary);
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
  color: #0a6cff;
  cursor: pointer;
}
.record-content-empty {
  flex: 1;
}
.record-content-empty strong {
  color: rgba(29, 29, 31, 0.72);
  font-size: 14px;
}
.record-content-retry {
  min-height: 32px;
  padding: 0 14px;
  border: 1px solid rgba(10, 108, 255, 0.2);
  border-radius: 8px;
  background: rgba(10, 108, 255, 0.07);
  color: #0a6cff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 650;
}
.record-document-select,
.record-load-orders-btn,
.record-compare-mobile-tabs {
  display: none;
}
@media (max-width: 1199px) {
  .is-document-only .record-compare-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .record-compare-grid {
    grid-template-columns: minmax(380px, 1fr) minmax(360px, 400px);
  }
  .record-document-nav {
    display: none;
  }
  .record-document-select {
    position: relative;
    min-width: 180px;
    margin-left: auto;
    display: block;
  }
  .record-document-select > span {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  .record-document-select select {
    width: 100%;
    height: 32px;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    background: #fff;
    font-size: 12px;
  }
  .record-load-orders-btn {
    display: inline-flex;
    flex: none;
    height: 32px;
    align-items: center;
    justify-content: center;
    padding: 0 10px;
    border: 1px solid rgba(10, 108, 255, 0.24);
    border-radius: 8px;
    background: rgba(10, 108, 255, 0.07);
    color: #0a6cff;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
    transition:
      background 160ms ease,
      border-color 160ms ease;
  }
  .record-load-orders-btn:hover:not(:disabled) {
    border-color: rgba(10, 108, 255, 0.42);
    background: rgba(10, 108, 255, 0.13);
  }
  .record-load-orders-btn:disabled {
    cursor: not-allowed;
    opacity: 0.65;
  }
  .record-load-orders-btn.is-failed {
    border-color: rgba(180, 35, 24, 0.28);
    background: rgba(239, 68, 68, 0.08);
    color: #b42318;
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
    color: #0a6cff;
  }
  .record-compare-grid {
    height: clamp(320px, calc(100dvh - 230px), 680px);
    min-height: 0;
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

/* ===== v7.1 液态玻璃覆盖：外框透明，目录 / 原文 / 结果三栏为独立玻璃卡 ===== */
.record-compare-shell {
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}
.record-compare-head {
  min-height: 0;
  padding: 14px 18px 10px;
  border-bottom: 0;
}
.record-compare-head strong {
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-16);
  font-weight: 700;
}
.record-compare-head span {
  color: var(--mq-text-tertiary);
}
.record-compare-grid {
  gap: 14px;
  padding: 0 16px 16px;
}
.record-compare-shell.fills-available-height {
  display: flex;
  min-height: 0;
  flex: 1 1 0;
  flex-direction: column;
}
.fills-available-height .record-compare-grid {
  height: auto;
  flex: 1 1 0;
  grid-template-rows: minmax(0, 1fr);
}
.record-document-nav,
.record-content-column,
.record-result-column {
  overflow: hidden;
  border: 1px solid var(--mq-glass-border);
  border-radius: var(--mq-radius-card);
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
}
.record-document-nav {
  border-right: 1px solid var(--mq-glass-border);
}
.record-content-column {
  background: rgba(255, 255, 255, 0.82);
}
.record-content-toolbar {
  border-bottom: 0.5px solid var(--mq-border);
  background: transparent;
}
.record-column-head {
  border-bottom: 0.5px solid var(--mq-border);
}
.record-result-entry {
  border-radius: 16px;
}
.record-result-entry.is-active {
  border-color: var(--mq-brand-600);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.1);
}
</style>
