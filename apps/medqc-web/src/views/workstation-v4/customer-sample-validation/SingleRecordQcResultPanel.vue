<template>
  <aside
    class="single-record-result-panel"
    aria-label="质控结果"
  >
    <header
      class="result-toolbar"
      data-testid="single-record-result-toolbar"
    >
      <div class="toolbar-top">
        <div class="toolbar-summary">
          <strong>质控结果</strong>
          <span data-testid="single-record-result-summary">{{ resultExecutionSummary }}</span>
        </div>
      </div>
      <template v-if="viewItems.length">
        <div
          v-if="!isGroupedPresentation"
          class="result-tabs"
          role="tablist"
          aria-label="质控结果状态筛选"
        >
          <button
            v-for="tab in statusTabs"
            :key="tab.key"
            type="button"
            role="tab"
            class="result-tab"
            :class="[`is-${tab.key}`, { 'is-active': activeTab === tab.key }]"
            :aria-selected="activeTab === tab.key"
            :data-testid="`single-record-result-tab-${tab.key}`"
            @click="activeTab = tab.key"
          >
            <span>{{ tab.label }}</span>
            <b>{{ tab.count }}</b>
          </button>
        </div>
        <div
          v-else
          class="result-tabs result-report-tabs"
          role="tablist"
          aria-label="病历质控报告分类"
        >
          <button
            v-for="tab in reportTabs"
            :key="tab.key"
            type="button"
            role="tab"
            class="result-tab"
            :class="[`is-${tab.key}`, { 'is-active': activeReportTab === tab.key }]"
            :aria-selected="activeReportTab === tab.key"
            :data-testid="`single-record-report-tab-${tab.key}`"
            @click="activeReportTab = tab.key"
          >
            <span>{{ tab.label }}</span>
            <b>{{ tab.count }}</b>
          </button>
        </div>
        <p
          v-if="isGroupedPresentation && presentation.counts.technicalError"
          class="result-system-status"
          data-testid="single-record-system-status"
        >
          系统状态：{{ presentation.counts.technicalError }} 条结果校验异常，仅在全部规则中展示
        </p>
      </template>
    </header>

    <div
      v-if="!hasVisibleResults"
      class="empty-state"
    >
      {{ viewItems.length ? '当前分类下没有质控结果' : '当前没有可展示的质控结果' }}
    </div>

    <div
      v-else
      class="result-list"
      :class="{ 'is-grouped': isGroupedPresentation }"
    >
      <article
        v-for="item in renderedItems"
        v-show="shouldRenderDocumentGroupItem(item.key)"
        :key="item.key"
        class="result-row"
        :class="[
          `is-${item.tone}`,
          {
            'is-expanded': expandedKey === item.key,
            'is-document-group-start': documentGroupForItem(item.key)?.isFirst,
            'is-document-group-collapsed': !isDocumentGroupExpandedForItem(item.key),
          },
        ]"
        :data-testid="
          isDocumentGroupExpandedForItem(item.key) ? 'single-record-result-row' : undefined
        "
      >
        <div
          v-if="isGroupedPresentation && documentGroupForItem(item.key)?.isFirst"
          class="result-document-group-header"
          data-testid="single-record-document-group"
        >
          <button
            type="button"
            class="result-document-group-toggle"
            data-testid="single-record-document-group-toggle"
            :aria-expanded="isDocumentGroupExpandedForItem(item.key)"
            @click="toggleDocumentGroup(documentGroupForItem(item.key)?.key || '')"
          >
            <span>
              <strong>{{ documentGroupForItem(item.key)?.sourceDocument }}</strong>
              <small>{{ documentGroupForItem(item.key)?.count }} 个质控点</small>
            </span>
            <ChevronUp
              v-if="isDocumentGroupExpandedForItem(item.key)"
              :size="17"
              :stroke-width="2"
              aria-hidden="true"
            />
            <ChevronRight
              v-else
              :size="17"
              :stroke-width="2"
              aria-hidden="true"
            />
          </button>
        </div>
        <button
          v-if="isDocumentGroupExpandedForItem(item.key)"
          type="button"
          class="result-trigger"
          :class="{ 'is-static': !isExpandable(item) }"
          :aria-expanded="isExpandable(item) ? expandedKey === item.key : undefined"
          :aria-label="
            isExpandable(item)
              ? `${expandedKey === item.key ? '收起' : '展开'}${item.rule_name}详情`
              : undefined
          "
          :data-testid="isExpandable(item) ? 'single-record-result-toggle' : undefined"
          @click="isExpandable(item) && toggle(item.key)"
        >
          <span class="result-main">
            <span
              class="result-row-header"
              data-testid="single-record-result-row-header"
            >
              <span class="result-row-meta">
                <span class="status-cell">
                  <span
                    class="status-pill"
                    :class="`is-${item.tone}`"
                  >{{
                    item.displayStatus
                  }}</span>
                </span>
                <span class="rule-code">{{ item.rule_id }}</span>
                <span
                  v-if="isGroupedPresentation && item.evidence?.length"
                  class="result-evidence-count"
                >
                  {{ item.evidence.length }}处证据
                </span>
              </span>
              <span
                v-if="isExpandable(item)"
                class="toggle-mark"
                aria-hidden="true"
              >
                <ChevronUp
                  v-if="expandedKey === item.key"
                  :size="17"
                  :stroke-width="2"
                  aria-hidden="true"
                />
                <ChevronRight
                  v-else
                  :size="17"
                  :stroke-width="2"
                  aria-hidden="true"
                />
              </span>
            </span>
            <strong class="rule-name">{{ item.rule_name }}</strong>
            <span
              v-if="copyMatchHeadline(item)"
              class="copy-match-headline"
              data-testid="copy-match-headline"
            >
              <span
                class="copy-match-headline-documents"
                data-testid="copy-match-headline-documents"
              >
                <span>
                  <strong>{{ copyMatchHeadline(item)?.leftLabel }}</strong>
                  <i aria-hidden="true">·</i>
                  <time>{{ copyMatchHeadline(item)?.leftTime }}</time>
                </span>
                <ArrowRight
                  aria-hidden="true"
                  :size="16"
                  :stroke-width="2"
                />
                <span>
                  <strong>{{ copyMatchHeadline(item)?.rightLabel }}</strong>
                  <i aria-hidden="true">·</i>
                  <time>{{ copyMatchHeadline(item)?.rightTime }}</time>
                </span>
              </span>
              <span
                class="copy-match-headline-metrics"
                data-testid="copy-match-headline-metrics"
              >
                <span class="is-primary">
                  相似度 <strong>{{ copyMatchHeadline(item)?.similarity }}</strong>
                </span>
                <span>
                  判定阈值 <strong>{{ copyMatchHeadline(item)?.threshold }}</strong>
                </span>
                <span v-if="copyMatchHeadline(item)?.additionalCount">
                  另有 <strong>{{ copyMatchHeadline(item)?.additionalCount }}</strong> 组
                </span>
              </span>
            </span>
            <span
              v-else
              class="rule-conclusion"
              data-testid="single-record-result-conclusion"
            >{{
              resultHeadline(item)
            }}</span>
          </span>
        </button>

        <section
          v-if="
            isDocumentGroupExpandedForItem(item.key) &&
              expandedKey === item.key &&
              isExpandable(item)
          "
          class="result-detail"
        >
          <div
            v-if="
              isCompliantResult(item) &&
                (timelinessMetrics(item).length ||
                  timelinessTimeline(item).length ||
                  item.criterion_results?.length ||
                  hasCompliantNarrative(item))
            "
            class="compliant-detail"
            data-testid="single-record-compliant-detail"
          >
            <div
              v-if="hasCompliantNarrative(item)"
              class="summary-narrative compliant-narrative"
            >
              <DetailBlock
                v-if="item.detail"
                :title="detailTitle(item)"
                :content="item.detail"
              />
              <DetailBlock
                v-if="item.actual"
                :title="actualTitle(item)"
                :content="item.actual"
              />
              <DetailBlock
                v-if="item.standard"
                :title="standardTitle(item)"
                :content="item.standard"
              />
            </div>
            <section
              v-if="timelinessMetrics(item).length"
              class="timeliness-metrics"
              :class="`has-${timelinessMetrics(item).length}-metrics`"
              data-testid="timeliness-metrics"
            >
              <div
                v-for="row in timelinessMetrics(item)"
                :key="row.key"
                class="timeliness-metric"
              >
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </div>
            </section>
            <div
              v-if="timelinessTimeline(item).length"
              class="timeliness-timeline"
              data-testid="timeliness-timeline"
            >
              <template
                v-for="(row, index) in timelinessTimeline(item)"
                :key="row.key"
              >
                <span class="timeline-point">
                  <small>{{ row.label }}</small>
                  <strong>{{ row.value }}</strong>
                </span>
                <span
                  v-if="index < timelinessTimeline(item).length - 1"
                  class="timeline-arrow"
                  aria-hidden="true"
                >
                  <ArrowRight
                    :size="15"
                    :stroke-width="1.8"
                  />
                </span>
              </template>
            </div>
            <section
              v-if="item.criterion_results?.length"
              class="detail-block criterion-block compliant-criterion-block"
              data-testid="single-record-compliant-criteria"
            >
              <h4>合规依据</h4>
              <article
                v-for="criterion in item.criterion_results"
                :key="criterion.criterion_id"
                class="criterion-row"
              >
                <div class="criterion-head">
                  <strong>{{ criterionLabel(criterion.criterion_id) }}</strong>
                  <span :class="`is-${criterion.status}`">{{
                    criterionStatusText(criterion.status)
                  }}</span>
                </div>
                <p>{{ criterionFactText(criterion) }}</p>
                <p
                  v-if="criterion.medical_analysis"
                  class="criterion-analysis"
                >
                  {{ criterion.medical_analysis }}
                </p>
              </article>
            </section>
          </div>

          <div
            v-if="
              !isCompliantResult(item) &&
                (item.detail ||
                  item.actual ||
                  item.standard ||
                  timelinessMetrics(item).length ||
                  timelinessTimeline(item).length)
            "
            class="decision-summary"
          >
            <div
              v-if="item.detail || item.actual || item.standard"
              class="summary-narrative"
            >
              <DetailBlock
                v-if="item.detail"
                :title="detailTitle(item)"
                :content="item.detail"
              />
              <DetailBlock
                v-if="item.actual"
                :title="actualTitle(item)"
                :content="item.actual"
              />
              <DetailBlock
                v-if="item.standard"
                :title="standardTitle(item)"
                :content="item.standard"
              />
            </div>

            <section
              v-if="timelinessMetrics(item).length"
              class="timeliness-metrics"
              :class="`has-${timelinessMetrics(item).length}-metrics`"
              data-testid="timeliness-metrics"
            >
              <div
                v-for="row in timelinessMetrics(item)"
                :key="row.key"
                class="timeliness-metric"
                :class="{ 'is-overdue': row.key === 'overdue_hours' }"
              >
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </div>
            </section>

            <div
              v-if="timelinessTimeline(item).length"
              class="timeliness-timeline"
              data-testid="timeliness-timeline"
            >
              <template
                v-for="(row, index) in timelinessTimeline(item)"
                :key="row.key"
              >
                <span class="timeline-point">
                  <small>{{ row.label }}</small>
                  <strong>{{ row.value }}</strong>
                </span>
                <span
                  v-if="index < timelinessTimeline(item).length - 1"
                  class="timeline-arrow"
                  aria-hidden="true"
                >
                  <ArrowRight
                    :size="15"
                    :stroke-width="1.8"
                  />
                </span>
              </template>
            </div>
          </div>

          <div
            v-if="!isCompliantResult(item) || hasCompliantSupportingDetails(item)"
            class="detail-grid"
            :class="{
              'is-compliant': isCompliantResult(item),
              'has-main-details': remainingDisplayFactRows(item).length,
            }"
            data-testid="single-record-detail-grid"
          >
            <div class="detail-column detail-column-main">
              <ExamLabEventResultBlock
                v-if="examLabEventPresentation(item)"
                :presentation="examLabEventPresentation(item)!"
              />
              <section
                v-if="implantEventFacts(item).length"
                class="detail-block implant-event-block"
                data-testid="implant-event-facts"
              >
                <header class="fact-block-header">
                  <h4>逐台手术核对</h4>
                  <span>分别展示每台手术缺少的植入物字段</span>
                </header>
                <div class="implant-event-list">
                  <article
                    v-for="event in implantEventFacts(item)"
                    :key="event.eventPosition"
                    class="implant-event-row"
                    data-testid="implant-event-fact"
                  >
                    <strong>{{ implantEventTitle(event) }}</strong>
                    <span>手术记录缺少：{{ event.missingLabels.join('、') }}</span>
                  </article>
                </div>
              </section>
              <section
                v-if="remainingDisplayFactRows(item).length"
                class="detail-block fact-block decision-fact-block"
                :data-testid="
                  isCompliantResult(item)
                    ? 'single-record-verification-facts'
                    : 'single-record-decision-facts'
                "
              >
                <header
                  class="fact-block-header"
                  :data-testid="
                    isCompliantResult(item)
                      ? 'single-record-verification-facts-header'
                      : 'single-record-decision-facts-header'
                  "
                >
                  <h4>{{ isCompliantResult(item) ? '核对依据' : '判定事实' }}</h4>
                  <span>
                    {{
                      isCompliantResult(item)
                        ? '本次质控采用的核对信息'
                        : '本次质控采用的关键判定信息'
                    }}
                  </span>
                </header>
                <dl class="fact-list">
                  <template
                    v-for="row in remainingDisplayFactRows(item)"
                    :key="row.key"
                  >
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.value }}</dd>
                  </template>
                </dl>
              </section>
              <section
                v-if="copyMatchPairs(item).length"
                class="detail-block copy-pair-block"
                data-testid="copy-match-pairs"
              >
                <div class="copy-pair-title">
                  <h4>重复病程组合</h4>
                  <span>共 {{ copyMatchPairs(item).length }} 组</span>
                </div>
                <div class="copy-pair-list">
                  <article
                    v-for="pair in copyMatchPairs(item)"
                    :key="pair.key"
                    class="copy-pair-row"
                    data-testid="copy-match-pair"
                  >
                    <div class="copy-pair-head">
                      <strong>组合 {{ pair.index }}</strong>
                      <span>相似度 {{ pair.similarity }}</span>
                    </div>
                    <div class="copy-pair-documents">
                      <span>{{ pair.leftLabel }} · {{ pair.leftTime }}</span>
                      <ArrowRight
                        aria-hidden="true"
                        :size="14"
                        :stroke-width="1.8"
                      />
                      <span>{{ pair.rightLabel }} · {{ pair.rightTime }}</span>
                    </div>
                  </article>
                </div>
                <p
                  v-if="displayEvidence(item).length"
                  class="copy-pair-hint"
                >
                  下方关键证据可分别定位这些病程原文。
                </p>
              </section>
              <section
                v-if="!isCompliantResult(item) && dataGapRows(item).length"
                class="detail-block fact-block"
              >
                <h4>待补资料</h4>
                <dl class="fact-list">
                  <template
                    v-for="row in dataGapRows(item)"
                    :key="row.key"
                  >
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.value }}</dd>
                  </template>
                </dl>
              </section>
              <section
                v-if="!isCompliantResult(item) && item.criterion_results?.length"
                class="detail-block criterion-block"
              >
                <h4>逐项判定</h4>
                <article
                  v-for="criterion in item.criterion_results"
                  :key="criterion.criterion_id"
                  class="criterion-row"
                >
                  <div class="criterion-head">
                    <strong>{{ criterionLabel(criterion.criterion_id) }}</strong>
                    <span :class="`is-${criterion.status}`">{{
                      criterionStatusText(criterion.status)
                    }}</span>
                  </div>
                  <p>{{ criterionFactText(criterion) }}</p>
                  <details
                    v-if="criterion.medical_analysis"
                    class="medical-analysis"
                  >
                    <summary>医学分析</summary>
                    <p>{{ criterion.medical_analysis }}</p>
                  </details>
                </article>
              </section>
            </div>

            <div class="detail-column detail-column-evidence">
              <section class="detail-block evidence-block">
                <h4>关键证据</h4>
                <div
                  v-if="displayEvidence(item).length"
                  class="evidence-list"
                >
                  <button
                    v-for="evidence in displayEvidence(item)"
                    :key="evidence.source_ref"
                    type="button"
                    class="evidence-link evidence-row"
                    data-testid="single-record-evidence"
                    @click="emit('locate-evidence', evidence)"
                  >
                    <span class="evidence-content">
                      <strong>{{ evidenceLabel(evidence) }}</strong>
                      <span
                        v-if="evidence.evidence_excerpt"
                        class="evidence-excerpt"
                      >
                        <em>{{ evidence.excerpt_kind || '病历原文依据' }}</em>
                        <span>{{ evidence.evidence_excerpt }}</span>
                      </span>
                      <span
                        v-else-if="evidence.field_path"
                        class="evidence-path"
                      >{{
                        evidence.field_path
                      }}</span>
                      <span
                        v-else
                        class="evidence-path"
                      >点击定位原文核对</span>
                    </span>
                    <span class="evidence-action">
                      定位原文
                      <ChevronRight
                        aria-hidden="true"
                        :size="14"
                        :stroke-width="2"
                      />
                    </span>
                  </button>
                </div>
                <p
                  v-else
                  class="muted"
                >
                  {{ emptyEvidenceText(item) }}
                </p>
              </section>

              <details
                v-if="item.model_analysis"
                class="medical-analysis model-analysis"
              >
                <summary>模型分析 / 医学判断</summary>
                <p>{{ item.model_analysis }}</p>
              </details>
            </div>
          </div>

          <section
            v-if="!isCompliantResult(item) && item.suggestion"
            class="suggestion-footer"
          >
            <strong>处理建议</strong>
            <p>{{ item.suggestion }}</p>
          </section>
        </section>
      </article>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ArrowRight, ChevronRight, ChevronUp } from 'lucide-vue-next'
import { computed, defineComponent, h, ref, watch } from 'vue'
import ExamLabEventResultBlock from './ExamLabEventResultBlock.vue'
import { buildExamLabEventPresentation } from './examLabEventPresentation'
import {
  buildSingleRecordQcPresentation,
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
  resolveSingleRecordQcResultTab,
  type SingleRecordQcEvidence,
  type SingleRecordQcCriterionResult,
  type SingleRecordQcResultItem,
  type SingleRecordQcResultReportTab,
  type SingleRecordQcResultTabKey,
  type SingleRecordQcResultViewItem,
} from './single-record-result-model'

const props = withDefaults(
  defineProps<{
    items: SingleRecordQcResultItem[]
    selectedKey?: string
    presentationMode?: 'flat' | 'grouped'
  }>(),
  { presentationMode: 'flat' },
)

const emit = defineEmits<{
  (event: 'select', key: string): void
  (event: 'locate-evidence', evidence: SingleRecordQcEvidence): void
}>()

const factLabels: Record<string, string> = {
  source_label: '核对文书',
  missing_fields: '缺失字段',
  failure_kind: '判定类型',
  checked_sources: '已核对来源',
  reviewed_record_scope: '已核对病程',
  target_document: '目标文书',
  performed_surgery_confirmed: '已实施手术',
  consent_state: '手术知情同意书',
  missing_signature_roles: '缺少签名',
  procedure_kind: '操作类型',
  effective_surgery_level: '手术等级',
  surgery_level_source: '等级来源',
  mdt_discussion_state: '多学科讨论',
  threshold_hours: '规定时限',
  copy_similarity: '实际相似度',
  copy_similarity_threshold: '判定阈值',
  compared_sections: '比对范围',
  anchor_time: '起算时间',
  observed_time: '记录时间',
  elapsed_hours: '实际间隔',
  overdue_hours: '超出时限',
  identified_implants: '已识别植入物',
  missing_visit_sources: '缺少访视记录',
  performed_anesthesia_confirmed: '已实施麻醉',
  performed_transfusion_confirmed: '已实施输血',
  record_count: '已核对记录',
  report_time: '报告时间',
  response_record_count: '相关病程记录',
  antimicrobials: '抗菌药物',
  window_hours: '评估时限',
  special_antimicrobials: '特殊级抗菌药物',
  expert_support_present: '专家支持记录',
  performed_surgery_count: '已实施手术',
  surgery_time: '手术时间',
  required_postop_dates: '应记录日期',
  covered_postop_dates: '已覆盖日期',
  surgeon_round_present: '术者查房记录',
  diagnosis_change_count: '诊断修正或补充',
  reason_recorded: '修改理由',
  basis_recorded: '诊断依据',
  completed_opinion_episode_count: '已完成会诊',
  recommendation_count: '会诊建议',
  specific_execution_count: '明确执行记录',
  generic_execution_count: '笼统执行记录',
  missing_execution_count: '未找到执行记录',
  ordered_procedures: '有创操作医嘱',
  course_documented: '对应病程记录',
}

const factValueLabels: Record<string, string> = {
  timeliness_requirement_not_met: '未在规定时限内完成',
  timeliness_requirement_satisfied: '在规定时限内完成',
  implant_information_incomplete: '植入物信息填写不完整',
  surgery_document_missing: '目标手术文书缺失',
  surgery_document_blank: '目标手术文书内容为空',
  surgery_consent_document_missing: '未检索到手术知情同意书',
  surgery_consent_body_missing: '手术知情同意书正文为空',
  surgery_consent_signature_missing: '手术知情同意书签名不完整',
  admission_first_course_copy_detected: '入院记录现病史与首次病程记录病例特点高度重复',
  copy_similarity_threshold_exceeded: '病程记录相似度达到判定阈值',
  implant_name: '名称',
  implant_type: '种类',
  implant_specification: '规格/型号',
  implant_material: '材质',
  implant_quantity: '数量',
  surgery_record: '手术记录',
  admission_record: '入院记录',
  first_course_record: '首次病程记录',
  presurg_summary: '术前小结',
  surgery_safecheck_record: '手术安全核查表',
  surgery: '手术',
  non_surgical_operation: '非手术操作',
  none: '未实施手术',
  unknown: '暂无法确认',
  hospital_performance: '院内绩效目录',
  national_catalog: '国家临床版目录',
  structured_field: '病历结构化字段',
  completed: '已完成',
  missing: '未完成',
  blank: '正文为空',
  signature_missing: '签名不完整',
  patient: '患者或代理人',
  surgeon: '术者',
}

const dataGapLabels: Record<string, string> = {
  reason_code: '缺口原因',
  missing_sources: '缺少来源',
  missing_fields: '缺少字段',
  required_sources: '所需来源',
  unavailable_sources: '不可用来源',
  availability: '来源状态',
}

// 这些字段保留在服务端结果中供追踪和调试，但不直接暴露给客户。
const hiddenCustomerFactKeys = new Set(['missing_fields', 'target_document'])
const examLabInternalFactKeys = new Set(['failure_kind', 'checked_sources'])
const hiddenDataGapKeys = new Set(['reason_code', 'missing_fields'])

const TIMELINESS_METRIC_KEYS = ['threshold_hours', 'elapsed_hours', 'overdue_hours'] as const
const TIMELINESS_TIME_KEYS = ['anchor_time', 'observed_time'] as const
const COPY_SOURCE_LABELS: Record<string, string> = {
  daily_course_record: '日常病程记录',
  senior_course_record: '上级医师查房记录',
}

function displayFactRows(item: SingleRecordQcResultItem) {
  const facts = item.customer_display_facts
  if (!facts || typeof facts !== 'object') return []
  return Object.entries(facts)
    .filter(([key]) => {
      if (!factLabels[key] || hiddenCustomerFactKeys.has(key)) return false
      return !(
        item.status === 'non_compliant' &&
        ['LX0609-011', 'LX0609-012', 'LX0609-014', 'LX0609-015'].includes(item.rule_id) &&
        examLabInternalFactKeys.has(key)
      )
    })
    .map(([key, rawValue]) => {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue]
      const value = values
        .map((entry) => {
          if (
            ['threshold_hours', 'elapsed_hours', 'overdue_hours', 'window_hours'].includes(key) &&
            typeof entry === 'number' &&
            Number.isFinite(entry)
          ) {
            return `${entry} 小时`
          }
          if (
            ['copy_similarity', 'copy_similarity_threshold'].includes(key) &&
            typeof entry === 'number' &&
            Number.isFinite(entry)
          ) {
            const percentage = Math.round(entry * 1000) / 10
            return `${Number.isInteger(percentage) ? percentage.toFixed(0) : percentage.toFixed(1)}%`
          }
          const customerLabel = factValueLabels[String(entry)]
          if (key === 'failure_kind') return customerLabel || ''
          return customerLabel || String(entry)
        })
        .filter(Boolean)
        .join('、')
      const sourceLabel = typeof facts.source_label === 'string' ? facts.source_label.trim() : ''
      const label =
        key === 'anchor_time' && item.rule_id === 'LX0609-002'
          ? '入院时间'
          : key === 'observed_time' && sourceLabel
            ? `${sourceLabel}时间`
            : key === 'failure_kind'
              ? '问题说明'
              : factLabels[key] || key
      return {
        key,
        label,
        value: value === 'true' ? '是' : value === 'false' ? '否' : value,
      }
    })
    .filter((row) => Boolean(row.value))
}

const implantFieldLabels: Record<string, string> = {
  implant_name: '名称',
  implant_type: '种类',
  implant_specification: '规格/型号',
  implant_material: '材质',
  implant_quantity: '数量',
}

function implantEventFacts(item: SingleRecordQcResultItem) {
  if (item.rule_id !== 'LX0609-025') return []
  if (
    item.customer_display_facts?.performed_surgery_confirmed !== true ||
    item.customer_display_facts?.source_label !== '手术记录' ||
    item.customer_display_facts?.source_document_type !== 'surgery_record'
  )
    return []
  const rawEvents = item.customer_display_facts?.implant_event_details
  if (!Array.isArray(rawEvents) || !rawEvents.length || rawEvents.length > 12) return []
  const events: Array<{
    eventPosition: number
    missingLabels: string[]
    implantNames: string[]
  }> = []
  for (const [index, candidate] of rawEvents.entries()) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) return []
    const row = candidate as Record<string, unknown>
    if (row.event_position !== index + 1) return []
    if (!Array.isArray(row.missing_fields) || !row.missing_fields.length) return []
    const missingLabels = row.missing_fields.flatMap((field) => {
      const label = typeof field === 'string' ? implantFieldLabels[field] : undefined
      return label ? [label] : []
    })
    if (missingLabels.length !== row.missing_fields.length) return []
    if (!Array.isArray(row.implant_names) || row.implant_names.length > 12) return []
    const implantNames = row.implant_names.flatMap((value) => {
      const name = typeof value === 'string' ? value.trim() : ''
      return name && name.length <= 80 ? [name] : []
    })
    if (implantNames.length !== row.implant_names.length) return []
    events.push({ eventPosition: index + 1, missingLabels, implantNames })
  }
  return events
}

function implantEventTitle(event: ReturnType<typeof implantEventFacts>[number]) {
  const names = event.implantNames.length ? ` · ${event.implantNames.join('、')}` : ''
  return `第 ${event.eventPosition} 台手术${names}`
}

function examLabEventPresentation(item: SingleRecordQcResultItem) {
  return buildExamLabEventPresentation(item)
}

function resultHeadline(item: SingleRecordQcResultViewItem) {
  return examLabEventPresentation(item)?.headline || item.conclusionText
}

type DisplayFactRow = ReturnType<typeof displayFactRows>[number]

function rowsByKeyOrder(item: SingleRecordQcResultItem, keys: readonly string[]): DisplayFactRow[] {
  const rows = displayFactRows(item)
  return keys
    .map((key) => rows.find((row) => row.key === key))
    .filter((row): row is DisplayFactRow => Boolean(row))
}

function timelinessMetrics(item: SingleRecordQcResultItem) {
  return rowsByKeyOrder(item, TIMELINESS_METRIC_KEYS)
}

function timelinessTimeline(item: SingleRecordQcResultItem) {
  return rowsByKeyOrder(item, TIMELINESS_TIME_KEYS)
}

function remainingDisplayFactRows(item: SingleRecordQcResultItem) {
  const displayedKeys = new Set(timelinessTimeline(item).map((row) => row.key))
  timelinessMetrics(item).forEach((row) => displayedKeys.add(row.key))
  if (examLabEventPresentation(item)) {
    displayedKeys.add('report_time')
    displayedKeys.add('response_record_count')
  }
  return displayFactRows(item).filter((row) => !displayedKeys.has(row.key))
}

function emptyEvidenceText(item: SingleRecordQcResultItem): string {
  if (item.status === 'non_compliant') {
    return '当前结果尚无可定位证据，请先人工核对相关文书后再处理。'
  }
  if (item.status === 'data_gap' || item.status === 'uncertain') {
    return '当前没有可定位证据，请根据资料缺口补齐或核对相关记录。'
  }
  return '本次结果没有可定位证据。'
}

function formatCopyPercentage(value: number): string {
  const percentage = Math.round(value * 1000) / 10
  return `${Number.isInteger(percentage) ? percentage.toFixed(0) : percentage.toFixed(1)}%`
}

function copyMatchPairs(item: SingleRecordQcResultItem) {
  if (item.rule_id !== 'LX0609-017') return []
  const rawPairs = item.customer_display_facts?.copy_match_pairs
  if (!Array.isArray(rawPairs)) return []
  return rawPairs.slice(0, 4).flatMap((rawPair, rawIndex) => {
    if (!rawPair || typeof rawPair !== 'object') return []
    const pair = rawPair as Record<string, unknown>
    const sourceTypes = pair.source_types
    const recordTimes = pair.record_times
    const similarity = pair.similarity
    if (
      !Array.isArray(sourceTypes) ||
      sourceTypes.length !== 2 ||
      !sourceTypes.every(
        (sourceType): sourceType is string =>
          typeof sourceType === 'string' && Boolean(COPY_SOURCE_LABELS[sourceType]),
      ) ||
      !Array.isArray(recordTimes) ||
      recordTimes.length !== 2 ||
      !recordTimes.every(
        (recordTime): recordTime is string =>
          typeof recordTime === 'string' && Boolean(recordTime.trim()),
      ) ||
      typeof similarity !== 'number' ||
      !Number.isFinite(similarity) ||
      similarity < 0 ||
      similarity > 1
    ) {
      return []
    }
    return [
      {
        key: `${rawIndex}-${sourceTypes.join('-')}-${recordTimes.join('-')}`,
        index: rawIndex + 1,
        leftLabel: COPY_SOURCE_LABELS[sourceTypes[0]] || sourceTypes[0],
        leftTime: recordTimes[0],
        rightLabel: COPY_SOURCE_LABELS[sourceTypes[1]] || sourceTypes[1],
        rightTime: recordTimes[1],
        similarity: formatCopyPercentage(similarity),
      },
    ]
  })
}

function copyMatchHeadline(item: SingleRecordQcResultItem) {
  const pairs = copyMatchPairs(item)
  const firstPair = pairs[0]
  const threshold = item.customer_display_facts?.copy_similarity_threshold
  if (
    !firstPair ||
    typeof threshold !== 'number' ||
    !Number.isFinite(threshold) ||
    threshold < 0 ||
    threshold > 1
  ) {
    return null
  }
  return {
    ...firstPair,
    threshold: formatCopyPercentage(threshold),
    additionalCount: Math.max(0, pairs.length - 1),
  }
}

function dataGapValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(dataGapValue).filter(Boolean).join('、')
  }
  if (value && typeof value === 'object') {
    return Object.entries(value)
      .map(([key, entry]) => `${key}：${dataGapValue(entry)}`)
      .filter(Boolean)
      .join('；')
  }
  if (value === true) return '可用'
  if (value === false) return '不可用'
  return String(value || '').trim()
}

function dataGapRows(item: SingleRecordQcResultItem) {
  const details = item.data_gap_details
  if (!details || typeof details !== 'object') return []
  return Object.entries(details)
    .filter(([key]) => Boolean(dataGapLabels[key]) && !hiddenDataGapKeys.has(key))
    .map(([key, value]) => ({
      key,
      label: dataGapLabels[key] || key,
      value: dataGapValue(value),
    }))
    .filter((row) => Boolean(row.value))
}

const DetailBlock = defineComponent({
  name: 'SingleRecordQcDetailBlock',
  props: {
    title: { type: String, required: true },
    content: { type: String, required: true },
  },
  setup(detailProps) {
    return () =>
      h('section', { class: 'detail-block' }, [
        h('h4', detailProps.title),
        h('p', detailProps.content),
      ])
  },
})

const viewItems = computed(() => buildSingleRecordQcResultItems(props.items))
const isGroupedPresentation = computed(() => props.presentationMode === 'grouped')
const presentation = computed(() => buildSingleRecordQcPresentation(props.items))
const resultExecutionSummary = computed(() => {
  const total = viewItems.value.length
  const notExecuted = viewItems.value.filter((item) => item.status === 'not_executed').length
  const executed = total - notExecuted
  return notExecuted > 0
    ? `${total} 个质控点 · 已执行 ${executed} · 未执行 ${notExecuted}`
    : `${total} 个质控点 · 已执行 ${executed}`
})
const statusTabs = computed(() => buildSingleRecordQcStatusTabs(viewItems.value))
const activeTab = ref<SingleRecordQcResultTabKey>('all')
const activeReportTab = ref<SingleRecordQcResultReportTab>('all')
const reportTabs = computed(() => [
  {
    key: 'non_compliant' as const,
    label: '确定问题',
    count: presentation.value.counts.nonCompliant,
  },
  { key: 'data_gap' as const, label: '资料待核实', count: presentation.value.counts.dataGap },
  { key: 'uncertain' as const, label: '待判断', count: presentation.value.counts.uncertain },
  { key: 'all' as const, label: '全部规则', count: viewItems.value.length },
])
const visibleItems = computed(() =>
  activeTab.value === 'all'
    ? viewItems.value
    : viewItems.value.filter((item) => resolveSingleRecordQcResultTab(item) === activeTab.value),
)
const visibleGroups = computed(() => {
  if (isGroupedPresentation.value) {
    return presentation.value.sectionsByTab[activeReportTab.value]
  }
  return visibleItems.value.length
    ? [{ key: 'flat-results', sourceDocument: '', items: visibleItems.value }]
    : []
})
const renderedItems = computed(() => visibleGroups.value.flatMap((group) => group.items))

interface DocumentGroupItemMeta {
  key: string
  sourceDocument: string
  count: number
  isFirst: boolean
}

const documentGroupByItemKey = computed(() => {
  const entries = new Map<string, DocumentGroupItemMeta>()
  if (!isGroupedPresentation.value) return entries

  visibleGroups.value.forEach((group) => {
    group.items.forEach((item, index) => {
      entries.set(item.key, {
        key: group.key,
        sourceDocument: group.sourceDocument,
        count: group.items.length,
        isFirst: index === 0,
      })
    })
  })
  return entries
})
const hasVisibleResults = computed(() => renderedItems.value.length > 0)
const expandedKey = ref('')
const collapsedDocumentGroupKeys = ref<Set<string>>(new Set())

function documentGroupForItem(itemKey: string) {
  return documentGroupByItemKey.value.get(itemKey)
}

function isDocumentGroupExpanded(key: string) {
  return !collapsedDocumentGroupKeys.value.has(key)
}

function toggleDocumentGroup(key: string) {
  if (!key) return
  const next = new Set(collapsedDocumentGroupKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedDocumentGroupKeys.value = next
}

function isDocumentGroupExpandedForItem(itemKey: string) {
  const group = documentGroupForItem(itemKey)
  return !group || isDocumentGroupExpanded(group.key)
}

function shouldRenderDocumentGroupItem(itemKey: string) {
  const group = documentGroupForItem(itemKey)
  return !group || group.isFirst || isDocumentGroupExpanded(group.key)
}

function resolveDefaultReportTab(): SingleRecordQcResultReportTab {
  if (presentation.value.counts.nonCompliant) return 'non_compliant'
  if (presentation.value.counts.dataGap) return 'data_gap'
  if (presentation.value.counts.uncertain) return 'uncertain'
  return 'all'
}

watch(
  [() => props.presentationMode, () => props.items],
  () => {
    if (!isGroupedPresentation.value) return
    activeReportTab.value = resolveDefaultReportTab()
    collapsedDocumentGroupKeys.value = new Set()
    expandedKey.value = ''
  },
  { immediate: true },
)

function toggle(key: string) {
  expandedKey.value = expandedKey.value === key ? '' : key
  emit('select', key)
}

function criterionLabel(criterionId: string) {
  const labels: Record<string, string> = {
    chief_complaint_length: '主诉书写规范性',
    diagnostic_direction: '诊断指向性',
  }
  return labels[criterionId] || '子项核对'
}

function evidenceLabel(evidence: SingleRecordQcEvidence) {
  if (evidence.source_label) return evidence.source_label
  const labels: Record<string, string> = {
    admission_record: '入院记录',
    first_course_record: '首次病程记录',
    daily_course_record: '日常病程记录',
    senior_course_record: '上级医师查房记录',
    consultation_record: '会诊记录',
    exam_master: 'CT/MRI 检查报告',
    exam_item_report: 'CT/MRI 检查报告',
    labtest_master: '细菌培养报告',
    labtest_item_report: '细菌培养报告',
    bloodtrans_record: '输血记录',
    surgery_record: '手术记录',
    inpat_drug_order: '药物医嘱',
    inpat_nondrug_order: '医嘱',
  }
  return labels[evidence.source_type || ''] || '来源文书'
}

const examLabCourseEvidenceTypes = new Set([
  'first_course_record',
  'daily_course_record',
  'senior_course_record',
  'rescue_record',
])

function displayEvidence(item: SingleRecordQcResultItem): SingleRecordQcEvidence[] {
  const evidence = Array.isArray(item.evidence) ? item.evidence : []
  if (
    item.status !== 'non_compliant' ||
    !['LX0609-011', 'LX0609-012', 'LX0609-014', 'LX0609-015'].includes(item.rule_id)
  ) {
    return evidence
  }
  // 这类“未记录”结果中，病程仅代表已核对范围，并不是支持缺陷的命中文书。
  return evidence.filter((item) => !examLabCourseEvidenceTypes.has(item.source_type || ''))
}

function criterionStatusText(status: string) {
  if (status === 'passed') return '通过'
  if (status === 'failed') return '未通过'
  return '待确认'
}

function criterionFactText(criterion: SingleRecordQcCriterionResult) {
  if (criterion.criterion_id === 'chief_complaint_length') {
    const actual = criterion.actual_value ?? '未返回'
    const expected = criterion.expected_value ?? '未返回'
    return `主诉共 ${actual} 字；标准为不超过 ${expected} 字。`
  }
  if (criterion.criterion_id === 'diagnostic_direction') {
    if (criterion.status === 'passed') return '主诉与第一诊断的医学指向关系已通过核对。'
    if (criterion.status === 'failed') return '主诉与第一诊断的医学指向关系未通过核对。'
    return '当前资料不足以完成主诉与第一诊断的医学指向核对。'
  }
  const actual = criterion.actual_value === undefined ? '' : `实际值：${criterion.actual_value}；`
  const expected =
    criterion.expected_value === undefined ? '' : `标准：${criterion.expected_value}。`
  return actual || expected ? `${actual}${expected}` : '该子项已按规则要求完成核对。'
}

function isCompliantResult(item: SingleRecordQcResultItem) {
  return item.status === 'compliant'
}

function isExpandable(item: SingleRecordQcResultViewItem) {
  if (!isCompliantResult(item)) return true
  return Boolean(
    timelinessMetrics(item).length ||
      timelinessTimeline(item).length ||
      item.criterion_results?.length ||
      hasCompliantNarrative(item) ||
      hasCompliantSupportingDetails(item),
  )
}

function hasCompliantNarrative(item: SingleRecordQcResultItem) {
  return Boolean(item.detail || item.actual || item.standard)
}

function hasCompliantSupportingDetails(item: SingleRecordQcResultItem) {
  return Boolean(
    remainingDisplayFactRows(item).length || item.evidence?.length || item.model_analysis,
  )
}

function isPendingEvidenceStatus(item: SingleRecordQcResultItem) {
  return (
    item.status === 'data_gap' ||
    item.status === 'evaluation_unknown' ||
    item.status === 'uncertain'
  )
}

function detailTitle(item: SingleRecordQcResultItem) {
  if (isCompliantResult(item)) return '核对说明'
  return isPendingEvidenceStatus(item) ? '缺口说明' : '完整判定说明'
}

function actualTitle(item: SingleRecordQcResultItem) {
  if (isCompliantResult(item)) return '核对情况'
  return isPendingEvidenceStatus(item) ? '当前已知情况' : '实际情况'
}

function standardTitle(item: SingleRecordQcResultItem) {
  if (isCompliantResult(item)) return '合规标准'
  return isPendingEvidenceStatus(item) ? '所需核对条件' : '核对标准'
}

watch(
  () => props.selectedKey,
  (value) => {
    if (!value || !viewItems.value.some((item) => item.key === value)) return
    expandedKey.value = value
  },
  { immediate: true },
)

watch(
  statusTabs,
  (tabs) => {
    if (!tabs.some((tab) => tab.key === activeTab.value)) activeTab.value = 'all'
  },
  { immediate: true },
)
</script>

<style scoped>
.single-record-result-panel {
  container-type: inline-size;
  min-width: 0;
  height: 100%;
  overflow: auto;
  background: rgba(255, 255, 255, 0.88);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'SF Pro Text', Inter, 'PingFang SC', 'Microsoft YaHei UI', system-ui,
    sans-serif;
}

.result-toolbar {
  position: sticky;
  z-index: 3;
  top: 0;
  display: block;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(18px);
}

.toolbar-top {
  padding: 13px 14px 7px;
}

.toolbar-summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: max-content;
}

.toolbar-summary strong {
  font-size: 17px;
  font-weight: 680;
  line-height: 24px;
  letter-spacing: -0.02em;
}

.toolbar-summary span,
.muted {
  font-size: 12px;
  line-height: 18px;
  color: rgba(29, 29, 31, 0.58);
}

.result-tabs {
  display: flex;
  gap: 7px;
  min-width: 0;
  padding: 5px 10px 10px;
  overflow-x: auto;
  scrollbar-width: none;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  padding: 2px 8px;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 650;
  line-height: 17px;
  white-space: nowrap;
}

.status-pill::before {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: rgba(29, 29, 31, 0.28);
  content: '';
}

.is-danger.status-pill {
  background: rgba(239, 68, 68, 0.08);
  color: #d92d20;
}

.is-danger.status-pill::before {
  background: #ef4444;
}

.is-warning.status-pill {
  background: rgba(245, 158, 11, 0.1);
  color: #a86500;
}

.is-warning.status-pill::before {
  background: #d99512;
}

.is-success.status-pill {
  background: rgba(16, 185, 129, 0.09);
  color: #087443;
}

.is-success.status-pill::before {
  background: #15966a;
}

.result-tab {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 32px;
  padding: 5px 9px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.84);
  color: rgba(29, 29, 31, 0.62);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.025);
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease;
  white-space: nowrap;
}

.result-tab:hover {
  border-color: rgba(0, 0, 0, 0.14);
  background: #fff;
  color: rgba(29, 29, 31, 0.84);
  box-shadow: 0 2px 7px rgba(0, 0, 0, 0.07);
}

.result-tab.is-active {
  border-color: #0066cc;
  background: #0066cc;
  color: #fff;
  box-shadow: 0 3px 9px rgba(0, 102, 204, 0.2);
}

.result-tab.is-non_compliant:not(.is-active) {
  border-color: rgba(239, 68, 68, 0.14);
  background: rgba(239, 68, 68, 0.055);
  color: #c62828;
}

.result-tab.is-pending:not(.is-active),
.result-tab.is-data_gap:not(.is-active) {
  border-color: rgba(245, 158, 11, 0.18);
  background: rgba(245, 158, 11, 0.07);
  color: #9a6200;
}

.result-tab.is-uncertain:not(.is-active) {
  border-color: rgba(0, 102, 204, 0.14);
  background: rgba(0, 102, 204, 0.055);
  color: #245f9e;
}

.result-tab.is-not_applicable:not(.is-active) {
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.58);
}

.result-tab.is-compliant:not(.is-active) {
  border-color: rgba(16, 185, 129, 0.14);
  background: rgba(16, 185, 129, 0.055);
  color: #087443;
}

.result-tab b {
  display: inline-flex;
  min-width: 20px;
  height: 20px;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.065);
  color: inherit;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
}

.result-tab.is-active b {
  background: rgba(255, 255, 255, 0.2);
}

.result-system-status {
  margin: 0;
  padding: 7px 14px 9px;
  border-top: 1px solid rgba(0, 0, 0, 0.055);
  color: rgba(29, 29, 31, 0.54);
  font-size: 11px;
  line-height: 17px;
}

.empty-state {
  padding: 56px 18px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 14px;
  text-align: center;
}

.result-list {
  display: grid;
  gap: 9px;
  padding: 10px 12px 16px;
  background: #f5f5f7;
}

.result-list.is-grouped {
  gap: 13px;
}

.result-document-group-header {
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
}

.result-document-group-toggle {
  display: flex;
  width: 100%;
  min-height: 34px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 12px;
  border: 0;
  background: transparent;
  color: rgba(29, 29, 31, 0.78);
  cursor: pointer;
  text-align: left;
}

.result-document-group-toggle:hover {
  color: #0066cc;
}

.result-document-group-toggle > span {
  display: inline-flex;
  min-width: 0;
  align-items: baseline;
  gap: 7px;
}

.result-document-group-toggle strong {
  font-size: 13px;
  font-weight: 680;
  line-height: 20px;
}

.result-document-group-toggle small {
  color: rgba(29, 29, 31, 0.44);
  font-size: 11px;
  line-height: 17px;
}

.result-row {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.025);
  transition:
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.result-row.is-document-group-collapsed {
  border-color: rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.72);
  box-shadow: none;
}

.result-row:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.06),
    0 6px 22px rgba(0, 0, 0, 0.04);
  transform: translateY(-1px);
}

.result-row.is-expanded {
  border-color: rgba(0, 102, 204, 0.28);
  background: #fff;
  box-shadow: 0 8px 20px rgba(0, 102, 204, 0.08);
}

.result-trigger {
  display: block;
  width: 100%;
  min-height: 0;
  padding: 13px 14px 12px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.result-trigger:hover {
  background: transparent;
}

.result-trigger.is-static {
  cursor: default;
}

.result-row:not(.is-expanded) .result-trigger {
  padding: 11px 13px 10px;
}

.status-cell {
  display: inline-flex;
  min-width: 0;
  align-items: center;
}

.result-main {
  display: block;
  min-width: 0;
  padding: 0;
}

.result-row-header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.result-row-meta {
  display: inline-flex;
  min-width: 0;
  align-items: center;
  gap: 7px;
}

.rule-code {
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.035);
  padding: 1px 5px;
  color: rgba(29, 29, 31, 0.46);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.result-evidence-count {
  color: rgba(29, 29, 31, 0.46);
  font-size: 11px;
  font-weight: 550;
  line-height: 18px;
  white-space: nowrap;
}

.toggle-mark {
  display: inline-flex;
  min-width: 0;
  height: 28px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 28px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.035);
  color: rgba(29, 29, 31, 0.42);
}

.result-row.is-expanded .toggle-mark {
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.rule-name {
  display: block;
  min-width: 0;
  margin-top: 9px;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  font-weight: 700;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.rule-conclusion {
  display: block;
  margin-top: 7px;
  color: rgba(29, 29, 31, 0.76);
  font-size: 14px;
  font-weight: 520;
  line-height: 22px;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.copy-match-headline {
  display: grid;
  gap: 8px;
  margin-top: 9px;
  padding: 10px 11px;
  border-left: 3px solid #ef4444;
  border-radius: 0 9px 9px 0;
  background: rgba(239, 68, 68, 0.045);
  text-align: left;
}

.copy-match-headline-documents {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  color: rgba(29, 29, 31, 0.82);
  font-size: 12px;
  line-height: 19px;
}

.copy-match-headline-documents > span {
  display: inline-flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 5px;
  align-items: baseline;
}

.copy-match-headline-documents strong {
  color: #1d1d1f;
  font-weight: 650;
}

.copy-match-headline-documents i {
  color: rgba(29, 29, 31, 0.32);
  font-style: normal;
}

.copy-match-headline-documents time {
  color: rgba(29, 29, 31, 0.66);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.copy-match-headline-documents svg {
  flex: 0 0 auto;
  color: rgba(29, 29, 31, 0.38);
}

.copy-match-headline-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
  color: rgba(29, 29, 31, 0.65);
  font-size: 11px;
  line-height: 18px;
}

.copy-match-headline-metrics > span {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
}

.copy-match-headline-metrics .is-primary {
  background: rgba(239, 68, 68, 0.09);
  color: #c62828;
}

.copy-match-headline-metrics strong {
  color: inherit;
  font-size: 12px;
  font-weight: 750;
}

.result-row:not(.is-expanded) .rule-name,
.result-row:not(.is-expanded) .rule-conclusion {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
}

.result-row:not(.is-expanded) .rule-name {
  -webkit-line-clamp: 2;
}

.result-row:not(.is-expanded) .rule-conclusion {
  -webkit-line-clamp: 2;
}

.result-detail {
  margin: 0 14px 14px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 10px;
  background: rgba(248, 250, 252, 0.74);
}

.compliant-detail {
  padding: 14px 16px 12px;
  background: rgba(255, 255, 255, 0.72);
}

.compliant-detail .timeliness-metrics {
  margin-top: 0;
}

.compliant-criterion-block {
  padding-top: 1px;
}

.compliant-detail > :not(:first-child) {
  margin-top: 11px;
  padding-top: 11px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
}

.decision-summary {
  padding: 13px 16px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.54);
}

.summary-narrative {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.detail-block,
.medical-analysis {
  min-width: 0;
  margin: 0;
}

.detail-block h4,
.medical-analysis summary {
  margin: 0 0 5px;
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  font-weight: 650;
  line-height: 18px;
}

.detail-block p,
.medical-analysis p {
  margin: 0;
  color: rgba(29, 29, 31, 0.82);
  font-size: 13px;
  line-height: 20px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.timeliness-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 13px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.timeliness-metrics.has-1-metrics {
  grid-template-columns: minmax(0, 1fr);
}

.timeliness-metrics.has-2-metrics {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.timeliness-metric {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 10px;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
  text-align: center;
}

.timeliness-metric:last-child {
  border-right: 0;
}

.timeliness-metric span {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  font-weight: 600;
  line-height: 17px;
}

.timeliness-metric strong {
  color: rgba(29, 29, 31, 0.9);
  font-size: 17px;
  font-weight: 650;
  line-height: 23px;
}

.timeliness-metric.is-overdue strong {
  color: #d92d20;
}

.timeliness-timeline {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 10px;
  color: rgba(29, 29, 31, 0.64);
}

.timeline-point {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 6px;
}

.timeline-point small {
  color: rgba(29, 29, 31, 0.5);
  font-size: 11px;
  line-height: 17px;
}

.timeline-point strong {
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.timeline-arrow {
  display: inline-flex;
  align-items: center;
  color: rgba(0, 102, 204, 0.5);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(260px, 0.92fr);
}

.detail-grid.is-compliant:not(.has-main-details) {
  grid-template-columns: minmax(0, 1fr);
}

.detail-grid.is-compliant:not(.has-main-details) .detail-column-main {
  display: none;
}

.detail-grid.is-compliant .detail-column-evidence {
  border-left: 0;
}

.detail-column {
  min-width: 0;
  padding: 2px 14px 11px;
}

.detail-column-evidence {
  border-left: 1px solid rgba(0, 0, 0, 0.07);
}

.detail-column > .detail-block,
.detail-column > .medical-analysis {
  padding: 11px 0 0;
}

.detail-column > :not(:first-child) {
  margin-top: 11px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
}

.fact-list {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr);
  gap: 5px 10px;
  margin: 0;
}

.decision-fact-block {
  overflow: hidden;
  padding: 0 !important;
  border: 1px solid rgba(18, 38, 63, 0.08);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.78);
}

.fact-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(18, 38, 63, 0.07);
  background: rgba(22, 119, 255, 0.035);
}

.detail-block .fact-block-header h4 {
  margin: 0;
  color: rgba(20, 42, 68, 0.78);
  font-weight: 700;
}

.fact-block-header span {
  color: rgba(20, 42, 68, 0.5);
  font-size: 11px;
  line-height: 17px;
}

.decision-fact-block .fact-list {
  padding: 9px 10px 10px;
}

.decision-fact-block .fact-list dt {
  color: rgba(20, 42, 68, 0.58);
  font-weight: 550;
}

.decision-fact-block .fact-list dd {
  color: rgba(20, 42, 68, 0.9);
  font-weight: 550;
}

.implant-event-block {
  overflow: hidden;
  padding: 0 !important;
  border: 1px solid rgba(217, 45, 32, 0.14);
  border-radius: 9px;
  background: rgba(255, 251, 250, 0.78);
}

.implant-event-list {
  display: grid;
  gap: 0;
}

.implant-event-row {
  display: grid;
  gap: 3px;
  padding: 9px 10px;
  border-top: 1px solid rgba(217, 45, 32, 0.08);
}

.implant-event-row:first-child {
  border-top: 0;
}

.implant-event-row strong {
  color: rgba(29, 29, 31, 0.9);
  font-size: 12px;
  font-weight: 700;
  line-height: 19px;
}

.implant-event-row span {
  color: #b42318;
  font-size: 12px;
  font-weight: 600;
  line-height: 19px;
}

.fact-list dt {
  color: rgba(29, 29, 31, 0.52);
  font-size: 12px;
  line-height: 19px;
}

.fact-list dd {
  margin: 0;
  color: rgba(29, 29, 31, 0.84);
  font-size: 12px;
  line-height: 19px;
  overflow-wrap: anywhere;
}

.copy-pair-title,
.copy-pair-head,
.copy-pair-documents {
  display: flex;
  align-items: center;
}

.copy-pair-title {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
}

.copy-pair-title h4 {
  margin-bottom: 0;
}

.copy-pair-title > span {
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  font-weight: 600;
}

.copy-pair-list {
  display: grid;
  gap: 6px;
}

.copy-pair-row {
  display: grid;
  gap: 5px;
  padding: 8px 9px;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 8px;
  background: rgba(0, 102, 204, 0.025);
}

.copy-pair-head {
  justify-content: space-between;
  gap: 10px;
}

.copy-pair-head strong {
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  font-weight: 650;
}

.copy-pair-head span {
  color: #d92d20;
  font-size: 11px;
  font-weight: 650;
}

.copy-pair-documents {
  flex-wrap: wrap;
  gap: 6px;
  color: rgba(29, 29, 31, 0.66);
  font-size: 11px;
  line-height: 18px;
}

.copy-pair-documents svg {
  flex: 0 0 auto;
  color: rgba(0, 102, 204, 0.55);
}

.copy-pair-hint {
  margin-top: 7px !important;
  color: rgba(29, 29, 31, 0.48) !important;
  font-size: 11px !important;
  line-height: 17px !important;
}

.medical-analysis summary {
  cursor: pointer;
  color: #0066cc;
  list-style-position: inside;
}

.medical-analysis[open] summary {
  margin-bottom: 6px;
}

.criterion-block {
  display: grid;
}

.criterion-row {
  padding: 8px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.criterion-row:first-of-type {
  border-top: 0;
}

.criterion-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.criterion-head strong {
  font-size: 12px;
  line-height: 19px;
}

.criterion-head span {
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 17px;
}

.criterion-head .is-passed {
  background: #ecfdf3;
  color: #087443;
}

.criterion-head .is-failed {
  background: #fff0f0;
  color: #d92d20;
}

.criterion-head .is-unknown {
  background: #fff7e8;
  color: #b26a00;
}

.criterion-row > p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  line-height: 19px;
}

.criterion-row > .criterion-analysis {
  margin-top: 5px;
  color: rgba(29, 29, 31, 0.82);
}

.criterion-row .medical-analysis {
  margin-top: 7px;
}

.evidence-list {
  display: grid;
}

.evidence-link {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border: 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.evidence-link:first-child {
  border-top: 0;
}

.evidence-link:hover {
  background: rgba(0, 102, 204, 0.035);
}

.evidence-content {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.evidence-link strong {
  color: rgba(29, 29, 31, 0.88);
  font-size: 12px;
  line-height: 19px;
}

.evidence-path,
.evidence-excerpt {
  color: rgba(29, 29, 31, 0.54);
  font-size: 11px;
  line-height: 17px;
}

.evidence-excerpt {
  display: grid;
  gap: 1px;
  margin-top: 1px;
  text-align: left;
}

.evidence-excerpt em {
  color: rgba(29, 29, 31, 0.45);
  font-size: 11px;
  font-style: normal;
  font-weight: 600;
}

.evidence-action {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 3px;
  color: #0066cc;
  font-size: 11px;
  font-weight: 600;
  line-height: 17px;
}

.model-analysis p {
  color: rgba(29, 29, 31, 0.68);
  font-size: 12px;
  line-height: 19px;
}

.suggestion-footer {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 9px 14px 11px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.56);
}

.suggestion-footer strong {
  flex: 0 0 auto;
  color: rgba(29, 29, 31, 0.54);
  font-size: 12px;
  line-height: 19px;
}

.suggestion-footer p {
  margin: 0;
  color: rgba(29, 29, 31, 0.78);
  font-size: 12px;
  line-height: 19px;
}

@container (max-width: 900px) {
  .result-tabs {
    width: 100%;
  }

  .summary-narrative,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .summary-narrative {
    gap: 10px;
  }

  .detail-column-evidence {
    border-top: 1px solid rgba(0, 0, 0, 0.07);
    border-left: 0;
  }

  .timeliness-timeline {
    flex-wrap: wrap;
    gap: 6px 8px;
  }
}

@container (max-width: 560px) {
  .result-trigger {
    padding: 12px;
  }

  .result-detail {
    margin: 0 12px 12px;
  }

  .status-pill {
    font-size: 12px;
  }

  .rule-name {
    font-size: 14px;
    line-height: 22px;
  }

  .rule-conclusion {
    font-size: 14px;
    line-height: 21px;
  }

  .copy-match-headline-documents {
    font-size: 12px;
    line-height: 19px;
  }

  .timeliness-metric {
    padding: 8px 4px;
  }

  .timeliness-metric strong {
    font-size: 14px;
    line-height: 20px;
  }
}
</style>
