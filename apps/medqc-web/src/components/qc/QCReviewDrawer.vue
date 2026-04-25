<template>
  <a-drawer
    :open="visible"
    title="病历联审详情"
    placement="right"
    :width="1100"
    class="qc-review-drawer"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <!-- 顶部：病历基本信息 -->
    <div class="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-100">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-sm"
          >
            {{ (record?.patient_name || '').charAt(0) }}
          </div>
          <div>
            <div class="text-base font-bold text-slate-800">
              {{ record?.patient_name || '-' }}
            </div>
            <div class="text-xs text-slate-400">
              病案号：{{ record?.record_id || '-' }}
            </div>
          </div>
        </div>
        <span
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
          :class="statusClass"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="statusDotClass"
          />
          {{ statusText }}
        </span>
      </div>
      <div class="grid grid-cols-4 gap-4 text-sm">
        <div>
          <span class="text-slate-400">科室</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.department || '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">出院日期</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.discharge_date || '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">质控得分</span>
          <div
            class="font-medium font-mono mt-0.5"
            :style="{ color: getScoreColor(record?.score) }"
          >
            {{ record?.score ?? '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">缺陷数</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.defect_count || 0 }}
          </div>
        </div>
      </div>
    </div>

    <!-- 双栏布局：左侧文书 + 右侧缺陷 -->
    <div
      class="flex gap-4"
      style="height: calc(100vh - 300px)"
    >
      <!-- 左侧：病历文书内容 -->
      <div class="flex-1 bg-white rounded-xl border border-slate-100 overflow-hidden flex flex-col">
        <div class="space-y-3 px-4 py-3 border-b border-slate-100">
          <a-segmented
            v-if="docGroupOptions.length > 0"
            v-model:value="activeDocGroup"
            :options="docGroupOptions"
            size="small"
          />
          <div
            v-if="currentGroupDocs.length > 0"
            class="flex flex-wrap gap-2"
          >
            <button
              v-for="doc in currentGroupDocs"
              :key="doc.doc_key"
              type="button"
              class="rounded-full border px-3 py-1 text-xs transition-all"
              :class="
                activeDocKey === doc.doc_key
                  ? 'border-blue-200 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-blue-100 hover:bg-white hover:text-slate-700'
              "
              @click="activeDocKey = doc.doc_key"
            >
              {{ renderDocButtonLabel(doc) }}
            </button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto p-5">
          <a-spin :spinning="docLoading">
            <template v-if="currentDoc">
              <div class="mb-4 rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                <div class="text-sm font-semibold text-slate-800">
                  {{ currentDocTitle }}
                </div>
                <div
                  v-if="currentDocMeta"
                  class="mt-1 text-xs text-slate-400"
                >
                  {{ currentDocMeta }}
                </div>
              </div>
              <div
                v-if="currentDocFlags.length > 0"
                class="mb-4 flex flex-wrap gap-2"
              >
                <span
                  v-for="flag in currentDocFlags"
                  :key="flag"
                  class="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs text-amber-700"
                >
                  {{ flag }}
                </span>
              </div>
              <div
                v-if="currentDocFieldList.length > 0"
                class="mb-4 grid gap-3 md:grid-cols-2"
              >
                <div
                  v-for="field in currentDocFieldList"
                  :key="field.key"
                  class="rounded-xl border border-slate-100 bg-white px-4 py-3"
                >
                  <div class="text-xs font-medium text-slate-400">
                    {{ field.label }}
                  </div>
                  <div
                    class="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700"
                  >
                    {{ field.value }}
                  </div>
                </div>
              </div>
              <div
                v-if="activeReviewIssueSummary"
                class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800"
              >
                <div class="font-semibold text-amber-900">
                  已定位当前质控问题原文
                </div>
                <div class="mt-1 leading-6">
                  {{ activeReviewIssueSummary }}
                </div>
              </div>
              <div
                v-if="currentDocSectionBlocks.length > 0"
                class="space-y-4"
              >
                <section
                  v-for="(section, index) in currentDocSectionBlocks"
                  :key="`${section.title}-${index}`"
                  class="rounded-xl border border-slate-100 bg-white px-4 py-4"
                >
                  <div class="mb-3 flex items-center justify-between gap-3">
                    <div class="text-sm font-semibold text-slate-800">
                      {{ section.title }}
                    </div>
                    <span
                      v-if="section.sourceField"
                      class="text-xs text-slate-300"
                    >
                      {{ section.sourceField }}
                    </span>
                  </div>
                  <div class="space-y-3">
                    <div
                      v-for="block in section.blocks"
                      :key="block.key"
                      :ref="(el) => setHighlightBlockRef(block.key, el as Element | null)"
                      class="doc-content doc-content--prewrap rounded-lg px-3 py-2 text-sm leading-relaxed text-slate-700 transition-all"
                      :class="
                        activeHighlightBlockKey === block.key
                          ? 'doc-content--active-highlight'
                          : 'bg-transparent'
                      "
                      v-html="renderBlockHtml(block)"
                    />
                  </div>
                </section>
              </div>
              <div
                v-else-if="currentDocContent"
                class="space-y-3"
              >
                <div
                  v-for="block in currentDocPlainBlocks"
                  :key="block.key"
                  :ref="(el) => setHighlightBlockRef(block.key, el as Element | null)"
                  class="doc-content doc-content--prewrap rounded-lg px-3 py-2 text-sm leading-relaxed text-slate-700 transition-all"
                  :class="
                    activeHighlightBlockKey === block.key
                      ? 'doc-content--active-highlight'
                      : 'bg-transparent'
                  "
                  v-html="renderBlockHtml(block)"
                />
              </div>
              <div
                v-else
                class="text-center py-12 text-slate-400"
              >
                <FileTextOutlined
                  style="font-size: 36px"
                  class="mb-3 block"
                />
                <p class="text-sm">
                  {{ docLoading ? '加载中...' : '当前文书暂无可展示内容' }}
                </p>
                <p class="text-xs mt-1 text-slate-300">
                  可切换其它文书继续查看
                </p>
              </div>
            </template>
            <div
              v-else
              class="text-center py-12 text-slate-400"
            >
              <FileTextOutlined
                style="font-size: 36px"
                class="mb-3 block"
              />
              <p class="text-sm">
                {{ docLoading ? '加载中...' : '暂无文书内容' }}
              </p>
              <p class="text-xs mt-1 text-slate-300">
                文书数据需从后端病历库获取
              </p>
            </div>
          </a-spin>
        </div>
      </div>

      <!-- 右侧：缺陷列表 -->
      <div class="w-[400px] flex-shrink-0 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-slate-800">
            质控问题
            <span class="text-xs text-slate-400 font-normal ml-2">共 {{ displayedIssueCount }} 项</span>
          </h3>
          <a-button
            size="small"
            type="text"
            class="text-slate-500"
            @click="loadDefects"
          >
            <ReloadOutlined :spin="defectLoading" />
          </a-button>
        </div>

        <a-spin
          :spinning="defectLoading"
          class="flex-1 overflow-hidden"
        >
          <div
            v-if="displayedIssueCount === 0"
            class="text-center py-8 text-slate-400 text-sm"
          >
            暂无质控问题
          </div>
          <div
            v-else-if="defectList.length > 0"
            class="space-y-3 overflow-y-auto pr-1"
            style="max-height: calc(100vh - 380px)"
          >
            <div
              v-for="defect in defectList"
              :key="defect.id"
              class="bg-white rounded-xl border border-slate-100 p-4 hover:shadow-md transition-all cursor-pointer group"
              :class="{ 'ring-2 ring-blue-200 border-blue-200': selectedDefectId === defect.id }"
              @click="handleDefectSelect(defect)"
            >
              <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span
                    class="w-2 h-2 rounded-full flex-shrink-0"
                    :class="{
                      'bg-rose-500': defect.severity === 'critical' || defect.severity === 'error',
                      'bg-amber-500': defect.severity === 'warning',
                      'bg-blue-500': defect.severity === 'info',
                    }"
                  />
                  <span class="text-sm font-medium text-slate-800">{{ defect.rule_name }}</span>
                </div>
                <span
                  class="text-xs px-2 py-0.5 rounded-md font-medium"
                  :class="{
                    'bg-amber-50 text-amber-600': defect.status === 'pending',
                    'bg-blue-50 text-blue-600': defect.status === 'urged',
                    'bg-emerald-50 text-emerald-600': defect.status === 'approved',
                    'bg-rose-50 text-rose-600': defect.status === 'rejected',
                    'bg-slate-100 text-slate-500': defect.status === 'remediated',
                  }"
                >
                  {{ getDefectStatusText(defect.status) }}
                </span>
              </div>
              <p class="text-xs text-slate-500 mb-2 line-clamp-2">
                {{ defect.description }}
              </p>
              <div class="flex items-center gap-4 text-xs text-slate-400">
                <span>分类：{{ defect.category }}</span>
                <span>位置：{{ defect.location }}</span>
              </div>

              <!-- 操作按钮（选中时显示） -->
              <QCReviewActionBar
                v-if="selectedDefectId === defect.id"
                :defect="defect"
                class="mt-3 pt-3 border-t border-slate-100"
                @action-done="handleActionDone"
              />
            </div>
          </div>
          <div
            v-else
            class="space-y-3 overflow-y-auto pr-1"
            style="max-height: calc(100vh - 380px)"
          >
            <div
              v-for="issue in reviewItemList"
              :key="issue.id"
              class="bg-white rounded-xl border border-slate-100 p-4 transition-all cursor-pointer"
              :class="{
                'ring-2 ring-blue-200 border-blue-200': selectedReviewIssueId === issue.id,
              }"
              @click="handleReviewIssueSelect(issue)"
            >
              <div class="flex items-start justify-between gap-3 mb-3">
                <div class="min-w-0">
                  <div class="text-sm font-semibold text-slate-800 break-words">
                    {{ issue.rule_code ? `${issue.rule_code} · ` : ''
                    }}{{ issue.rule_name || '质控规则' }}
                  </div>
                  <div class="flex flex-wrap items-center gap-2 mt-2 text-xs">
                    <span
                      class="px-2 py-0.5 rounded-full border"
                      :class="getReviewStatusClass(issue.status)"
                    >
                      {{ getReviewStatusText(issue.status) }}
                    </span>
                    <span
                      v-if="issue.document_type"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.document_type }}
                    </span>
                    <span
                      v-if="issue.rule_family"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.rule_family }}
                    </span>
                    <span
                      v-if="issue.defect_level"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.defect_level }}
                    </span>
                  </div>
                </div>
                <span
                  v-if="issue.confidence !== null && issue.confidence !== undefined"
                  class="text-xs text-slate-400 font-mono flex-shrink-0"
                >
                  {{ Number(issue.confidence).toFixed(2) }}
                </span>
              </div>

              <div
                v-if="issue.findings"
                class="text-xs text-slate-700 leading-6"
              >
                <span class="text-slate-400">结论：</span>{{ issue.findings }}
              </div>
              <div
                v-if="issue.evidence"
                class="text-xs text-slate-500 leading-6 mt-2"
              >
                <span class="text-slate-400">证据：</span>{{ issue.evidence }}
              </div>
              <div
                v-if="issue.suggestion"
                class="text-xs text-blue-600 leading-6 mt-2"
              >
                <span class="text-slate-400">建议：</span>{{ issue.suggestion }}
              </div>
            </div>
          </div>
        </a-spin>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ReloadOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getDefectList, getRecordDetail, type DefectItem } from '@/api/qcAdmin'
import QCReviewActionBar from './QCReviewActionBar.vue'

interface RecordData {
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
}

interface ReviewIssueItem {
  id: string
  source?: string
  job_id?: string
  record_id: string
  visit_id?: string
  patient_name?: string
  rule_code?: string
  rule_name: string
  status: 'non_compliant' | 'uncertain' | 'compliant' | 'not_applicable'
  document_type?: string
  rule_family?: string
  defect_level?: string
  findings?: string
  evidence?: string
  suggestion?: string
  confidence?: number | null
}

interface ReviewDocItem {
  id: string
  doc_key: string
  doc_type: string
  doc_name: string
  content: string
  has_content: boolean
  length: number
  document_id?: string
  document_title?: string
  sort_time?: string
  record_time?: string
  source_table?: string
  group_key?: string
  source_fields?: Array<{
    source_field?: string
    raw_value_preview?: string
    used?: boolean
  }>
  sections?: Array<{
    section_key?: string
    section_label?: string
    text?: string
    source_field?: string
  }>
  assembly_status?: string
  data_quality_flags?: string[]
}

interface ReviewDocTreeNode {
  id: string
  doc_key: string
  doc_type: string
  title: string
  record_time?: string
  has_content: boolean
  length: number
}

interface ReviewDocTreeGroup {
  key: string
  label: string
  count: number
  children: ReviewDocTreeNode[]
}

interface DocParagraphBlock {
  key: string
  text: string
}

interface DocSectionBlock {
  key: string
  title: string
  sourceField?: string
  blocks: DocParagraphBlock[]
}

interface HighlightTarget {
  docKey: string
  blockKey: string
  snippet: string
  docTitle: string
}

type SelectableIssue = {
  id: string
  rule_name?: string
  document_type?: string
  evidence?: string
  findings?: string
  suggestion?: string
}

const DOC_GROUP_LABELS: Record<string, string> = {
  all: '全部',
  frontpage: '病案首页',
  admission: '入院记录',
  course: '病程记录',
  exam_attention: '检查检验摘要',
  lab_results: '检验明细',
  exam_results: '检查结果',
  surgery: '手术相关',
  consult_discussion: '查房讨论',
  terminal: '出院记录',
  orders: '医嘱',
  index_coding_settlement: '首页结算',
}

const DOC_TYPE_LABELS: Record<string, string> = {
  mr: '病案首页',
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
  consultation_record: '会诊记录',
  rescue_record: '抢救记录',
  exam_attention_report: '检查关注摘要',
  lab_attention_report: '检验关注摘要',
  exam_master: '检查结果',
  exam_item_report: '检查结果',
  labtest_master: '检验申请单',
  labtest_item_report: '检验明细',
  surgery_record: '手术记录',
  anesthesia_record: '麻醉记录',
  presurg_summary: '术前小结',
  presurg_discussion: '术前讨论',
  surgery_safecheck_record: '手术安全核查记录',
  postsurg_firstcourse_record: '术后首次病程记录',
  discharge_record: '出院记录',
  death_record: '死亡记录',
  inpat_drug_order: '长期医嘱',
  inpat_nondrug_order: '临时医嘱',
}

const props = defineProps<{
  visible: boolean
  record: RecordData | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
}>()

const defectLoading = ref(false)
const defectList = ref<DefectItem[]>([])
const reviewItemList = ref<ReviewIssueItem[]>([])
const selectedDefectId = ref<string | null>(null)
const selectedReviewIssueId = ref<string | null>(null)
const docLoading = ref(false)
const recordDetail = ref<Record<string, unknown> | null>(null)
const activeDocGroup = ref('all')
const activeDocKey = ref('')
const activeHighlightTarget = ref<HighlightTarget | null>(null)
const highlightBlockElements = new Map<string, HTMLElement>()

function safeText(value: unknown): string {
  return String(value || '').trim()
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalizeSearchText(value: string): string {
  return safeText(value)
    .replace(/【[^】]*】/g, '')
    .replace(/\[[^\]]*]/g, '')
    .replace(/\s+/g, '')
    .replace(/[：:，,。；;、]/g, '')
}

function splitReadableParagraphs(text: string): string[] {
  const normalized = safeText(text).replace(/\r/g, '')
  if (!normalized) return []
  const lineBlocks = normalized
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (lineBlocks.length > 1) return lineBlocks

  const sentences = normalized
    .split(/(?<=[。！？；;])/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (sentences.length <= 1) return [normalized]

  const blocks: string[] = []
  let current = ''
  let sentenceCount = 0
  for (const sentence of sentences) {
    const next = current ? `${current}${sentence}` : sentence
    if (current && (next.length > 110 || sentenceCount >= 2)) {
      blocks.push(current)
      current = sentence
      sentenceCount = 1
    } else {
      current = next
      sentenceCount += 1
    }
  }
  if (current) blocks.push(current)
  return blocks
}

function extractIssueSearchText(
  issue: Pick<SelectableIssue, 'evidence' | 'findings' | 'rule_name'>,
): string {
  const evidence = safeText(issue.evidence)
  if (evidence) return evidence
  const findings = safeText(issue.findings)
  if (findings) return findings
  return safeText(issue.rule_name)
}

function matchesDocType(doc: ReviewDocItem, documentType?: string): boolean {
  const query = safeText(documentType).toLowerCase()
  if (!query) return false
  const candidates = [
    safeText(doc.doc_type).toLowerCase(),
    safeText(doc.source_table).toLowerCase(),
    safeText(doc.document_title).toLowerCase(),
    safeText(doc.doc_name).toLowerCase(),
  ]
  return candidates.some((item) => item && (item.includes(query) || query.includes(item)))
}

function formatDocTime(value?: string): string {
  const raw = safeText(value)
  if (!raw) return ''
  const normalized = raw.endsWith('Z') ? raw : raw.replace(' ', 'T')
  const date = new Date(normalized)
  if (!Number.isNaN(date.getTime())) {
    const formatter = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    })
    const parts = formatter.formatToParts(date)
    const get = (type: Intl.DateTimeFormatPartTypes) =>
      parts.find((part) => part.type === type)?.value || ''
    return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}`
  }
  return raw
}

function normalizeReviewDocItem(raw: unknown, index: number): ReviewDocItem | null {
  const source = (raw || {}) as Record<string, unknown>
  const id =
    safeText(source.document_id) ||
    safeText(source.id) ||
    safeText(source.doc_id) ||
    `${safeText(source.doc_type || source.type || source.source_table) || 'doc'}-${index}`
  const docType =
    safeText(source.doc_type) ||
    safeText(source.type) ||
    safeText(source.document_type) ||
    safeText(source.source_table)
  const content = safeText(source.content)
  const hasContent =
    typeof source.has_content === 'boolean'
      ? source.has_content
      : Boolean(content || Number(source.length || 0) > 0)
  const title =
    safeText(source.document_title) ||
    safeText(source.doc_name) ||
    safeText(source.label) ||
    DOC_TYPE_LABELS[docType] ||
    docType ||
    '未命名文书'
  return {
    id,
    doc_key: safeText(source.doc_key) || `${docType || 'unknown'}::${id}`,
    doc_type: docType,
    doc_name: title,
    content,
    has_content: hasContent,
    length: Number(source.length || content.length || 0),
    document_id: safeText(source.document_id) || id,
    document_title: safeText(source.document_title) || title,
    sort_time: safeText(source.sort_time) || safeText(source.record_time) || undefined,
    record_time: safeText(source.record_time) || safeText(source.sort_time) || undefined,
    source_table: safeText(source.source_table) || docType || undefined,
    group_key: safeText(source.group_key) || undefined,
    source_fields: Array.isArray(source.source_fields)
      ? source.source_fields
          .filter((item) => item && typeof item === 'object')
          .map((item) => item as ReviewDocItem['source_fields'][number])
      : [],
    sections: Array.isArray(source.sections)
      ? source.sections
          .filter((item) => item && typeof item === 'object')
          .map((item) => item as ReviewDocItem['sections'][number])
      : [],
    assembly_status: safeText(source.assembly_status) || undefined,
    data_quality_flags: Array.isArray(source.data_quality_flags)
      ? source.data_quality_flags.map((item) => safeText(item)).filter(Boolean)
      : [],
  }
}

function inferDocGroupKey(doc: ReviewDocItem): string {
  const explicit = safeText(doc.group_key)
  if (explicit) return explicit
  const docType = safeText(doc.doc_type || doc.source_table).toLowerCase()
  if (['mr', 'diagnosis', 'mr_surgery', 'mr_cost'].includes(docType)) return 'frontpage'
  if (docType.includes('admission')) return 'admission'
  if (docType.includes('attention_report')) return 'exam_attention'
  if (docType.includes('labtest')) return 'lab_results'
  if (docType.includes('exam')) return 'exam_results'
  if (docType.includes('consult') || docType.includes('discussion')) return 'consult_discussion'
  if (docType.includes('course') || docType.includes('rescue') || docType.includes('handoff')) {
    return 'course'
  }
  if (
    docType.includes('surgery') ||
    docType.includes('anesthesia') ||
    docType.includes('presurg')
  ) {
    return 'surgery'
  }
  if (docType.includes('discharge') || docType.includes('death')) return 'terminal'
  if (docType.includes('order')) return 'orders'
  return 'course'
}

function buildTreeNodeFromDoc(doc: ReviewDocItem): ReviewDocTreeNode {
  return {
    id: doc.document_id || doc.id,
    doc_key: doc.doc_key,
    doc_type: doc.doc_type,
    title: doc.document_title || doc.doc_name,
    record_time: doc.record_time || doc.sort_time,
    has_content: doc.has_content,
    length: doc.length,
  }
}

function buildFallbackDocTree(docs: ReviewDocItem[]): ReviewDocTreeGroup[] {
  const groups: Array<{ key: string; label: string }> = [
    { key: 'all', label: '全部' },
    { key: 'frontpage', label: DOC_GROUP_LABELS.frontpage },
    { key: 'admission', label: DOC_GROUP_LABELS.admission },
    { key: 'course', label: DOC_GROUP_LABELS.course },
    { key: 'exam_attention', label: DOC_GROUP_LABELS.exam_attention },
    { key: 'lab_results', label: DOC_GROUP_LABELS.lab_results },
    { key: 'exam_results', label: DOC_GROUP_LABELS.exam_results },
    { key: 'surgery', label: DOC_GROUP_LABELS.surgery },
    { key: 'consult_discussion', label: DOC_GROUP_LABELS.consult_discussion },
    { key: 'terminal', label: DOC_GROUP_LABELS.terminal },
    { key: 'orders', label: DOC_GROUP_LABELS.orders },
  ]
  const byGroup = new Map<string, ReviewDocTreeNode[]>()
  for (const doc of docs) {
    const node = buildTreeNodeFromDoc(doc)
    const groupKey = inferDocGroupKey(doc)
    byGroup.set(groupKey, [...(byGroup.get(groupKey) || []), node])
    byGroup.set('all', [...(byGroup.get('all') || []), node])
  }
  return groups.map((group) => ({
    key: group.key,
    label: group.label,
    count: (byGroup.get(group.key) || []).length,
    children: byGroup.get(group.key) || [],
  }))
}

function normalizeDocTree(rawTree: unknown, docs: ReviewDocItem[]): ReviewDocTreeGroup[] {
  const groups = Array.isArray(rawTree) ? rawTree : []
  const normalized = groups
    .map((rawGroup) => {
      const source = (rawGroup || {}) as Record<string, unknown>
      const groupKey = safeText(source.key || source.group_key)
      const groupLabel =
        safeText(source.label || source.title || source.name) ||
        DOC_GROUP_LABELS[groupKey] ||
        groupKey
      const rawChildren = Array.isArray(source.children)
        ? source.children
        : Array.isArray(source.nodes)
          ? source.nodes
          : []
      const children = rawChildren
        .map((rawNode) => {
          const nodeSource = (rawNode || {}) as Record<string, unknown>
          const id = safeText(nodeSource.id || nodeSource.doc_id || nodeSource.document_id)
          const docType = safeText(nodeSource.doc_type || nodeSource.type)
          const docKey = safeText(nodeSource.doc_key) || (docType && id ? `${docType}::${id}` : '')
          const matched =
            docs.find((doc) => doc.doc_key === docKey) ||
            docs.find((doc) => doc.document_id === id && doc.doc_type === docType)
          return {
            id: id || docKey || matched?.id || '',
            doc_key: docKey || matched?.doc_key || '',
            doc_type: docType || matched?.doc_type || '',
            title:
              safeText(nodeSource.title || nodeSource.label || nodeSource.doc_name) ||
              matched?.doc_name ||
              DOC_TYPE_LABELS[docType] ||
              '未命名文书',
            record_time:
              safeText(nodeSource.record_time || nodeSource.sort_time) ||
              matched?.record_time ||
              matched?.sort_time,
            has_content:
              typeof nodeSource.has_content === 'boolean'
                ? nodeSource.has_content
                : Boolean(matched?.has_content),
            length: Number(nodeSource.length || matched?.length || 0),
          } as ReviewDocTreeNode
        })
        .filter((node) => Boolean(node.id))

      return {
        key: groupKey || groupLabel,
        label: groupLabel,
        count: children.length,
        children,
      } as ReviewDocTreeGroup
    })
    .filter((group) => Boolean(group.key))

  const hasUsefulGroup = normalized.some(
    (group) => group.key !== 'all' && Array.isArray(group.children) && group.children.length > 0,
  )
  if (hasUsefulGroup) return normalized
  if (docs.length > 0) return buildFallbackDocTree(docs)
  return normalized
}

const rawDocumentList = computed(() => {
  const detail = recordDetail.value
  if (!detail) return []
  const documents = (detail.documents as Record<string, unknown> | undefined) || {}
  const rawDocuments = documents.raw_documents
  if (Array.isArray(rawDocuments) && rawDocuments.length > 0) {
    return rawDocuments
  }
  const fallbackDocs = [
    {
      doc_type: 'admission_record',
      document_title: '入院记录',
      content: detail.admissionNote || documents.admissionNote,
    },
    {
      doc_type: 'discharge_record',
      document_title: '出院记录',
      content: detail.dischargeNote || documents.dischargeNote,
    },
    {
      doc_type: 'course_record',
      document_title: '病程记录',
      content: detail.progressNote || documents.progressNote,
      group_key: 'course',
    },
    {
      doc_type: 'surgery_record',
      document_title: '手术相关文书',
      content: detail.surgeryNote || documents.surgeryNote,
      group_key: 'surgery',
    },
  ]
  return fallbackDocs.filter((item) => safeText(item.content))
})

const documentList = computed<ReviewDocItem[]>(() =>
  rawDocumentList.value
    .map((item, index) => normalizeReviewDocItem(item, index))
    .filter((item): item is ReviewDocItem => Boolean(item))
    .filter((item) => item.has_content),
)

const documentTree = computed<ReviewDocTreeGroup[]>(() => {
  const detail = recordDetail.value
  if (!detail) return []
  const documents = (detail.documents as Record<string, unknown> | undefined) || {}
  const rawTree = detail.documents_tree || documents.documents_tree
  return normalizeDocTree(rawTree, documentList.value)
})

const displayDocGroups = computed(() =>
  documentTree.value.filter(
    (group) => group.key !== 'all' && Array.isArray(group.children) && group.children.length > 0,
  ),
)

const docGroupOptions = computed(() =>
  displayDocGroups.value.map((group) => ({
    label: `${group.label} (${group.children.length})`,
    value: group.key,
  })),
)

const currentGroupNodes = computed<ReviewDocTreeNode[]>(() => {
  const groupKey = safeText(activeDocGroup.value)
  if (!groupKey || groupKey === 'all') {
    return documentList.value.map((doc) => buildTreeNodeFromDoc(doc))
  }
  return displayDocGroups.value.find((group) => group.key === groupKey)?.children || []
})

function resolveDocByNode(node: ReviewDocTreeNode): ReviewDocItem | undefined {
  return (
    documentList.value.find((doc) => doc.doc_key === node.doc_key) ||
    documentList.value.find(
      (doc) => doc.document_id === node.id && doc.doc_type === node.doc_type,
    ) ||
    documentList.value.find((doc) => doc.doc_type === node.doc_type)
  )
}

const currentGroupDocs = computed<ReviewDocItem[]>(() =>
  currentGroupNodes.value
    .map((node) => resolveDocByNode(node))
    .filter((doc): doc is ReviewDocItem => Boolean(doc))
    .filter((doc, index, list) => list.findIndex((item) => item.doc_key === doc.doc_key) === index),
)

const currentDoc = computed<ReviewDocItem | null>(() => {
  if (!currentGroupDocs.value.length) return null
  return (
    currentGroupDocs.value.find((doc) => doc.doc_key === activeDocKey.value) ||
    currentGroupDocs.value[0] ||
    null
  )
})

const currentDocContent = computed(() => currentDoc.value?.content || '')
const currentDocTitle = computed(
  () => currentDoc.value?.document_title || currentDoc.value?.doc_name || '病历文书',
)
const currentDocMeta = computed(() => {
  if (!currentDoc.value) return ''
  const parts = [formatDocTime(currentDoc.value.record_time || currentDoc.value.sort_time)]
  if (safeText(currentDoc.value.assembly_status)) {
    parts.push(`装配状态：${safeText(currentDoc.value.assembly_status)}`)
  }
  if (safeText(currentDoc.value.source_table)) {
    parts.push(`来源表：${safeText(currentDoc.value.source_table)}`)
  }
  return parts.filter(Boolean).join(' · ')
})

const currentDocFlags = computed(() => currentDoc.value?.data_quality_flags || [])

const currentDocFieldList = computed(() => {
  const fields = currentDoc.value?.source_fields || []
  return fields
    .filter((field) => Boolean(safeText(field?.raw_value_preview)))
    .filter((field) => field?.used !== false)
    .map((field) => ({
      key: safeText(field?.source_field) || 'field',
      label: safeText(field?.source_field) || '字段',
      value: safeText(field?.raw_value_preview),
    }))
})

const currentDocSectionList = computed(() => {
  const sections = currentDoc.value?.sections || []
  return sections
    .map((section, index) => ({
      key: safeText(section?.section_key) || `section-${index}`,
      title: safeText(section?.section_label) || `正文段落 ${index + 1}`,
      text: safeText(section?.text),
      sourceField: safeText(section?.source_field),
    }))
    .filter((section) => Boolean(section.text))
})

const currentDocSectionBlocks = computed<DocSectionBlock[]>(() =>
  currentDocSectionList.value
    .map((section) => ({
      key: section.key,
      title: section.title,
      sourceField: section.sourceField,
      blocks: splitReadableParagraphs(section.text).map((text, index) => ({
        key: `${section.key}-block-${index}`,
        text,
      })),
    }))
    .filter((section) => section.blocks.length > 0),
)

const currentDocPlainBlocks = computed<DocParagraphBlock[]>(() =>
  splitReadableParagraphs(currentDocContent.value).map((text, index) => ({
    key: `plain-block-${index}`,
    text,
  })),
)

const currentDocAllBlocks = computed<DocParagraphBlock[]>(() => {
  if (currentDocSectionBlocks.value.length > 0) {
    return currentDocSectionBlocks.value.flatMap((section) => section.blocks)
  }
  return currentDocPlainBlocks.value
})

const activeHighlightBlockKey = computed(() => activeHighlightTarget.value?.blockKey || '')

const activeReviewIssueSummary = computed(() => {
  const target = activeHighlightTarget.value
  if (!target) return ''
  return `已切换到“${target.docTitle}”，并定位到相关原文段落。`
})

function renderDocButtonLabel(doc: ReviewDocItem): string {
  const time = formatDocTime(doc.record_time || doc.sort_time)
  if (!time) return doc.document_title || doc.doc_name
  return `${time.slice(5, 16)} ${doc.document_title || doc.doc_name}`
}

function setHighlightBlockRef(blockKey: string, el: Element | null) {
  if (el instanceof HTMLElement) {
    highlightBlockElements.set(blockKey, el)
    return
  }
  highlightBlockElements.delete(blockKey)
}

function findHighlightTargetInDoc(
  doc: ReviewDocItem,
  issue: SelectableIssue,
): HighlightTarget | null {
  const queryText = extractIssueSearchText(issue)
  const normalizedQuery = normalizeSearchText(queryText)
  if (!normalizedQuery) return null

  const blocks =
    currentDoc.value?.doc_key === doc.doc_key
      ? currentDocAllBlocks.value
      : (() => {
          const sections = (doc.sections || [])
            .map((section, index) => {
              const baseKey = safeText(section?.section_key) || `section-${index}`
              return splitReadableParagraphs(safeText(section?.text)).map((text, blockIndex) => ({
                key: `${baseKey}-block-${blockIndex}`,
                text,
              }))
            })
            .flat()
          if (sections.length > 0) return sections
          return splitReadableParagraphs(doc.content).map((text, index) => ({
            key: `plain-block-${index}`,
            text,
          }))
        })()

  const matchedBlock = blocks.find((block) =>
    normalizeSearchText(block.text).includes(normalizedQuery),
  )
  if (!matchedBlock) return null
  return {
    docKey: doc.doc_key,
    blockKey: matchedBlock.key,
    snippet: queryText,
    docTitle: doc.document_title || doc.doc_name || '病历文书',
  }
}

function findBestHighlightTarget(issue: SelectableIssue): HighlightTarget | null {
  const docsByType = documentList.value.filter((doc) => matchesDocType(doc, issue.document_type))
  for (const doc of docsByType) {
    const target = findHighlightTargetInDoc(doc, issue)
    if (target) return target
  }
  for (const doc of documentList.value) {
    const target = findHighlightTargetInDoc(doc, issue)
    if (target) return target
  }
  return null
}

async function applyHighlightTarget(target: HighlightTarget | null) {
  if (!target) {
    activeHighlightTarget.value = null
    return
  }
  const doc = documentList.value.find((item) => item.doc_key === target.docKey)
  if (!doc) {
    activeHighlightTarget.value = null
    return
  }
  activeDocGroup.value = inferDocGroupKey(doc)
  activeDocKey.value = doc.doc_key
  activeHighlightTarget.value = target
  await nextTick()
  const el = highlightBlockElements.get(target.blockKey)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function renderHighlightedText(text: string, snippet: string): string {
  const safeTextValue = escapeHtml(text)
  const normalizedSnippet = normalizeSearchText(snippet)
  if (!normalizedSnippet) return safeTextValue

  const chars = Array.from(text)
  let rawStart = -1
  let rawEnd = -1
  let normalizedCursor = ''
  for (let index = 0; index < chars.length; index += 1) {
    const normalizedChar = normalizeSearchText(chars[index] || '')
    if (!normalizedChar) continue
    normalizedCursor += normalizedChar
    if (normalizedCursor.endsWith(normalizedSnippet)) {
      rawEnd = index + 1
      let remaining = normalizedSnippet.length
      let start = index
      while (start >= 0 && remaining > 0) {
        const width = normalizeSearchText(chars[start] || '').length
        if (width > 0) remaining -= width
        start -= 1
      }
      rawStart = start + 1
      break
    }
  }
  if (rawStart < 0 || rawEnd <= rawStart) return safeTextValue

  const before = escapeHtml(chars.slice(0, rawStart).join(''))
  const hit = escapeHtml(chars.slice(rawStart, rawEnd).join(''))
  const after = escapeHtml(chars.slice(rawEnd).join(''))
  return `${before}<mark class="doc-content__mark">${hit}</mark>${after}`
}

function renderBlockHtml(block: DocParagraphBlock): string {
  const target = activeHighlightTarget.value
  const html =
    target?.blockKey === block.key
      ? renderHighlightedText(block.text, target.snippet)
      : escapeHtml(block.text)
  return sanitizeHtml(html)
}

async function handleReviewIssueSelect(issue: ReviewIssueItem) {
  selectedReviewIssueId.value = issue.id
  selectedDefectId.value = null
  const target = findBestHighlightTarget(issue)
  await applyHighlightTarget(target)
}

async function handleDefectSelect(defect: DefectItem) {
  selectedDefectId.value = defect.id
  selectedReviewIssueId.value = null
  activeHighlightTarget.value = null
}

function syncActiveDocumentSelection() {
  if (!displayDocGroups.value.length) {
    activeDocGroup.value = 'all'
    activeDocKey.value = currentGroupDocs.value[0]?.doc_key || ''
    return
  }
  const validGroupKeys = displayDocGroups.value.map((group) => group.key)
  if (!validGroupKeys.includes(activeDocGroup.value)) {
    activeDocGroup.value = validGroupKeys[0]
  }
  const validDocKeys = currentGroupDocs.value.map((doc) => doc.doc_key)
  if (!validDocKeys.includes(activeDocKey.value)) {
    activeDocKey.value = currentGroupDocs.value[0]?.doc_key || ''
  }
}

const displayedIssueCount = computed(() =>
  defectList.value.length > 0 ? defectList.value.length : reviewItemList.value.length,
)

/**
 * HTML 净化：移除 script/iframe/事件属性，防止 XSS
 * 生产环境建议替换为 DOMPurify 等专业库
 */
const sanitizeHtml = (html: string): string => {
  if (!html) return ''
  return (
    html
      // 移除 script 标签及内容
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      // 移除 iframe
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
      .replace(/<iframe[^>]*\/>/gi, '')
      // 移除事件属性（on*="...")
      .replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\son\w+\s*=\s*[^\s>]*/gi, '')
      // 移除 javascript: 协议
      .replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"')
  )
}

// 状态样式计算
const statusClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved')
    return 'bg-emerald-50 text-emerald-600 border-emerald-100'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-50 text-rose-600 border-rose-100'
  return 'bg-amber-50 text-amber-600 border-amber-100'
})

const statusDotClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved') return 'bg-emerald-500'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-500'
  return 'bg-amber-500'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '待质控',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
    completed: '已通过',
    passed: '已通过',
    failed: '未通过',
  }
  return map[props.record?.status || ''] || props.record?.status || '-'
})

const getScoreColor = (score?: number) => {
  if (!score) return '#94a3b8'
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

const getDefectStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || status
}

const getReviewStatusText = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: '不合规',
    uncertain: '待复核',
    compliant: '合规',
    not_applicable: '不适用',
  }
  return map[status] || status
}

const getReviewStatusClass = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: 'bg-rose-50 text-rose-600 border-rose-100',
    uncertain: 'bg-amber-50 text-amber-600 border-amber-100',
    compliant: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    not_applicable: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  return map[status] || map.uncertain
}

// 加载缺陷列表
const loadDefects = async () => {
  if (!props.record?.record_id) return
  defectLoading.value = true
  try {
    const res = await getDefectList({ record_id: props.record.record_id })
    if (res.success && res.data) {
      defectList.value = (res.data as any).items || (res.data as any) || []
    }
  } catch {
    defectList.value = []
  } finally {
    defectLoading.value = false
  }
}

// 加载病历文书详情
const loadRecordDetail = async () => {
  if (!props.record?.record_id) return
  docLoading.value = true
  try {
    const res = await getRecordDetail(props.record.record_id)
    if (res.success && res.data) {
      const detail = res.data as Record<string, unknown>
      recordDetail.value = detail
      const inlineDefects = detail.defects
      if (Array.isArray(inlineDefects)) {
        defectList.value = inlineDefects as DefectItem[]
      }
      const reviewItems = detail.review_items
      if (Array.isArray(reviewItems)) {
        reviewItemList.value = reviewItems as ReviewIssueItem[]
      }
    }
  } catch {
    recordDetail.value = null
    reviewItemList.value = []
  } finally {
    docLoading.value = false
  }
}

// 操作完成后刷新
const handleActionDone = () => {
  loadDefects()
  emit('refresh')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

watch([displayDocGroups, currentGroupDocs], () => {
  syncActiveDocumentSelection()
})

watch([activeHighlightBlockKey, currentDocAllBlocks], async ([blockKey, blocks]) => {
  if (!blockKey || !blocks.some((block) => block.key === blockKey)) return
  await nextTick()
  const el = highlightBlockElements.get(blockKey)
  el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
})

// 打开时自动加载
watch(
  () => props.visible,
  (val) => {
    if (val && props.record) {
      selectedDefectId.value = null
      selectedReviewIssueId.value = null
      activeDocGroup.value = 'all'
      activeDocKey.value = ''
      activeHighlightTarget.value = null
      highlightBlockElements.clear()
      recordDetail.value = null
      reviewItemList.value = []
      loadDefects()
      loadRecordDetail()
    }
  },
)
</script>

<style scoped>
.qc-review-drawer :deep(.ant-drawer-body) {
  padding: 20px;
  background: #fafbfc;
}

.doc-content {
  font-size: 14px;
  line-height: 1.9;
  color: #333;
}

.doc-content--prewrap {
  white-space: pre-wrap;
  word-break: break-word;
}

.doc-content--active-highlight {
  background: #fff7d6;
  box-shadow: inset 0 0 0 1px #f3d57a;
}

.doc-content :deep(.doc-content__mark) {
  background: #facc15;
  color: #7c2d12;
  border-radius: 4px;
  padding: 0 2px;
}

.doc-content :deep(h4) {
  color: #1a1a1a;
  font-size: 16px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #3b82f6;
}

.doc-content :deep(b) {
  color: #1a1a1a;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
