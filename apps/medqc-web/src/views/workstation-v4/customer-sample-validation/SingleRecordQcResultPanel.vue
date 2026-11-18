<template>
  <aside class="single-record-result-panel" aria-label="质控结果">
    <header class="result-toolbar" data-testid="single-record-result-toolbar">
      <div class="toolbar-top">
        <div class="toolbar-summary">
          <strong class="result-section-title"
            ><ClipboardCheck :size="18" aria-hidden="true" />质控结果</strong
          >
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
            <ListFilter :size="14" aria-hidden="true" /><span>{{ tab.label }}</span>
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
            <ListFilter :size="14" aria-hidden="true" /><span>{{ tab.label }}</span>
            <b>{{ tab.count }}</b>
          </button>
        </div>
        <p
          v-if="!confirmedResultsOnly && isGroupedPresentation && presentation.counts.technicalError"
          class="result-system-status"
          data-testid="single-record-system-status"
        >
          系统状态：{{ presentation.counts.technicalError }} 条结果校验异常，仅在全部规则中展示
        </p>
      </template>
      <p v-if="confirmedResultsOnly && technicalFailureCount" class="result-system-status" data-testid="single-record-execution-failure">
        有 {{ technicalFailureCount }} 项未能完成判定，请查看任务状态。
      </p>
    </header>

    <div v-if="!hasVisibleResults" class="empty-state">
      {{ confirmedResultsOnly ? '当前没有可展示的确定问题' : viewItems.length ? '当前分类下没有质控结果' : '当前没有可展示的质控结果' }}
    </div>

    <div v-else class="result-list" :class="{ 'is-grouped': isGroupedPresentation }">
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
          v-if="
            isGroupedPresentation &&
            documentGroupForItem(item.key)?.isFirst &&
            (documentGroupForItem(item.key)?.count || 0) > 1
          "
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
            <ChevronRight v-else :size="17" :stroke-width="2" aria-hidden="true" />
          </button>
        </div>
        <button
          v-if="isDocumentGroupExpandedForItem(item.key)"
          type="button"
          class="result-trigger"
          :aria-expanded="expandedKey === item.key"
          :aria-label="`${expandedKey === item.key ? '收起' : '展开'}${displayRuleName(item)}详情`"
          data-testid="single-record-result-toggle"
          @click="handleContentClick($event, item)"
        >
          <span class="result-main">
            <span class="result-title-row">
              <span v-if="isCompliantResult(item)" class="status-cell compliant-dot">
                <span class="visually-hidden">合规</span>
              </span>
              <strong class="rule-name" :title="displayRuleName(item)">{{ displayRuleName(item) }}</strong>
              <span v-if="isCompliantResult(item)" class="rule-code" :title="item.rule_id">{{
                shortRuleCode(item.rule_id)
              }}</span>
              <span
                v-else
                class="status-cell status-pill mq-status"
                :class="[`is-${item.tone}`, statusModifierClass(item)]"
                >{{ item.status === 'data_gap' ? '资料待核实' : item.displayStatus }}</span
              >
            </span>
            <span
              v-if="!isCompliantResult(item) || expandedKey === item.key"
              class="result-row-header"
              data-testid="single-record-result-row-header"
            >
              <span
                v-if="!copyMatchHeadline(item)"
                class="rule-conclusion"
                data-testid="single-record-result-conclusion"
                >{{ resultHeadline(item) }}</span
              >
              <span v-else class="rule-conclusion-spacer" aria-hidden="true" />
              <span v-if="!isCompliantResult(item)" class="rule-code" :title="item.rule_id">{{
                shortRuleCode(item.rule_id)
              }}</span>
            </span>
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
                <ArrowRight aria-hidden="true" :size="16" :stroke-width="1.6" />
                <span>
                  <strong>{{ copyMatchHeadline(item)?.rightLabel }}</strong>
                  <i aria-hidden="true">·</i>
                  <time>{{ copyMatchHeadline(item)?.rightTime }}</time>
                </span>
              </span>
              <span class="copy-match-headline-metrics" data-testid="copy-match-headline-metrics">
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
            <span class="result-details-hint" aria-hidden="true">
              {{ expandedKey === item.key ? '收起详情' : '展开详情' }}
              <ChevronUp v-if="expandedKey === item.key" :size="16" />
              <ChevronDown v-else :size="16" />
            </span>
          </span>
        </button>

        <template v-if="isDocumentGroupExpandedForItem(item.key) && expandedKey === item.key">
          <ConsultationRecommendationSummary
            v-if="consultationRecommendationPresentation(item)"
            :presentation="consultationRecommendationPresentation(item)!"
          />

          <ExamLabEventResultBlock
            v-if="examLabEventPresentation(item)"
            class="result-event-overview"
            :presentation="examLabEventPresentation(item)!"
          />

          <section class="result-detail">
            <p
              v-if="item.status === 'not_applicable' && item.audit_evidence_status === 'not_retained'"
              class="audit-evidence-note"
              data-testid="single-record-audit-evidence-not-retained"
            >
              {{ item.audit_evidence_message || '本次不适用判定的审计依据当时未保留，原结论未改写。' }}
            </p>
            <div
              v-if="
                isCompliantResult(item) &&
                (hasTimelinessResult(item) ||
                  item.criterion_results?.length ||
                  hasCompliantNarrative(item))
              "
              class="compliant-detail"
              data-testid="single-record-compliant-detail"
            >
              <div v-if="hasCompliantNarrative(item)" class="summary-narrative compliant-narrative">
                <DetailBlock v-if="item.detail" :title="detailTitle(item)" :content="item.detail" />
                <DetailBlock v-if="item.actual" :title="actualTitle(item)" :content="item.actual" />
                <DetailBlock
                  v-if="item.standard"
                  :title="standardTitle(item)"
                  :content="item.standard"
                />
              </div>
              <TimelinessResultBlock
                v-if="hasTimelinessResult(item)"
                :item="item"
                variant="compliant"
              />
              <CriterionResultBlock
                v-if="item.criterion_results?.length"
                :criteria="item.criterion_results || []"
                variant="compliant"
              />
            </div>

            <div
              v-if="
                !isCompliantResult(item) &&
                (item.detail || item.actual || item.standard || hasTimelinessResult(item))
              "
              class="decision-summary"
            >
              <div v-if="item.detail || item.actual || item.standard" class="summary-narrative">
                <DetailBlock v-if="item.detail" :title="detailTitle(item)" :content="item.detail" />
                <DetailBlock v-if="item.actual" :title="actualTitle(item)" :content="item.actual" />
                <DetailBlock
                  v-if="item.standard"
                  :title="standardTitle(item)"
                  :content="item.standard"
                />
              </div>

              <TimelinessResultBlock
                v-if="hasTimelinessResult(item)"
                :item="item"
                variant="decision"
              />
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
                </header>
                <dl class="fact-list">
                  <template v-for="row in remainingDisplayFactRows(item)" :key="row.key">
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
                      <ArrowRight aria-hidden="true" :size="14" :stroke-width="1.6" />
                      <span>{{ pair.rightLabel }} · {{ pair.rightTime }}</span>
                    </div>
                  </article>
                </div>
                <p v-if="displayEvidence(item).length" class="copy-pair-hint">
                  下方关键证据可分别定位这些病程原文。
                </p>
              </section>
              <section
                v-if="!isCompliantResult(item) && dataGapRows(item).length"
                class="detail-block fact-block data-gap-block"
              >
                <h4>待补资料</h4>
                <dl class="fact-list">
                  <template v-for="row in dataGapRows(item)" :key="row.key">
                    <dt>{{ row.label }}</dt>
                    <dd>{{ row.value }}</dd>
                  </template>
                </dl>
              </section>
              <CriterionResultBlock
                v-if="!isCompliantResult(item) && item.criterion_results?.length"
                :criteria="item.criterion_results || []"
                variant="decision"
              />

              <div
                v-if="displayEvidence(item).length"
                class="evidence-chips"
                data-testid="single-record-evidence-disclosure"
              >
                <span class="evidence-chips-label">关键证据</span>
                <button
                  v-for="evidence in displayEvidence(item)"
                  :key="evidence.source_ref"
                  type="button"
                  class="evidence-chip"
                  data-testid="single-record-evidence"
                  :title="evidenceHint(evidence)"
                  @click="emit('locate-evidence', evidence)"
                >
                  {{ evidenceLabel(evidence) }}
                </button>
              </div>
              <p v-else class="empty-evidence-note" data-testid="single-record-empty-evidence">
                暂无可定位证据<span>{{ emptyEvidenceText(item) }}</span>
              </p>

              <details v-if="item.model_analysis" class="medical-analysis model-analysis">
                <summary>查看模型分析</summary>
                <p>{{ item.model_analysis }}</p>
              </details>
            </div>
          </section>

          <details
            v-if="!isCompliantResult(item) && item.suggestion"
            class="result-suggestion-disclosure"
            data-testid="single-record-suggestion-disclosure"
          >
            <summary>修改建议</summary>
            <QcRemediationSuggestion
              class="result-suggestion"
              compact
              :suggestion="item.suggestion"
              :status="item.status"
              :rule-id="item.rule_id"
              :record-context="debugContext"
            />
          </details>

          <section
            v-if="feedbackEnabled && feedbackOpenKey === item.key"
            class="result-feedback-panel mq-soft"
            data-testid="single-record-feedback-disclosure"
          >
            <QcResultFeedbackControl
              :feedback="feedbackByRule[item.rule_id]"
              :loading="feedbackLoading"
              :saving="feedbackSavingRuleId === item.rule_id"
              :error-message="feedbackError"
              @submit="emit('submit-feedback', item.rule_id, $event)"
            />
          </section>

          <dl
            v-if="ruleTextOpenKey === item.key"
            class="rule-fulltext mq-soft"
            data-testid="single-record-rule-fulltext"
          >
            <dt>规则</dt>
            <dd>{{ displayRuleName(item) }}</dd>
            <template v-if="item.source_document">
              <dt>文书</dt>
              <dd>{{ item.source_document }}</dd>
            </template>
            <dt>编号</dt>
            <dd class="rule-fulltext-code">
              {{ item.rule_id }}
            </dd>
          </dl>

          <footer class="result-card-actions">
            <button
              v-if="feedbackEnabled"
              type="button"
              class="result-action-pill"
              data-testid="single-record-feedback-entry-hint"
              :aria-expanded="feedbackOpenKey === item.key"
              @click="toggleFeedback(item.key)"
            >
              反馈此结果
            </button>
            <button
              type="button"
              class="result-action-link"
              data-testid="single-record-rule-fulltext-toggle"
              :aria-expanded="ruleTextOpenKey === item.key"
              @click="toggleRuleText(item.key)"
            >
              规则全文
            </button>
            <button
              type="button"
              v-if="!confirmedResultsOnly"
              class="result-row-debug-copy"
              data-testid="copy-single-qc-debug-result"
              title="复制本条脱敏调试信息"
              :aria-label="`复制${displayRuleName(item)}的脱敏调试信息`"
              :disabled="Boolean(debugCopyingKey)"
              @click="copySingleDebugResult(item)"
            >
              <MqIcon name="copy" :size="16" />
              <span class="visually-hidden">{{
                debugCopyingKey === item.key ? '复制中' : '复制调试信息'
              }}</span>
            </button>
          </footer>
        </template>
      </article>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ClipboardCheck,
  ListFilter,
} from 'lucide-vue-next'
import { computed, defineComponent, h, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useQcResultVisibility } from '@/composables/useQcResultVisibility'
import QcResultFeedbackControl from './QcResultFeedbackControl.vue'
import type {
  QcResultFeedbackRecord,
  SaveQcResultFeedbackInput,
} from '@/api/qc-result-feedback-demo'
import CriterionResultBlock from './CriterionResultBlock.vue'
import ConsultationRecommendationSummary from './ConsultationRecommendationSummary.vue'
import ExamLabEventResultBlock from './ExamLabEventResultBlock.vue'
import TimelinessResultBlock from './TimelinessResultBlock.vue'
import QcRemediationSuggestion from '@/views/workstation-v4/components/qc/QcRemediationSuggestion.vue'
import { buildExamLabEventPresentation } from './examLabEventPresentation'
import { customerFactValueLabel } from './customerFactValuePresentation'
import {
  buildConsultationRecommendationPresentation,
  buildSingleRecordQcPresentation,
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
  recommendationEvidenceForSingleRecord,
  resolveSingleRecordQcResultTab,
  type SingleRecordQcEvidence,
  type SingleRecordQcResultItem,
  type SingleRecordQcResultReportTab,
  type SingleRecordQcResultTabKey,
  type SingleRecordQcResultViewItem,
} from './single-record-result-model'
import { hasTimelinessResult, timelinessResultRows } from './timelinessResultPresentation'
import {
  buildQcResultDebugText,
  copyQcResultDebugText,
  type QcResultDebugContext,
} from './qcResultDebugExport'

const props = withDefaults(
  defineProps<{
    items: SingleRecordQcResultItem[]
    selectedKey?: string
    presentationMode?: 'flat' | 'grouped'
    feedbackByRule?: Record<string, QcResultFeedbackRecord>
    feedbackEnabled?: boolean
    feedbackLoading?: boolean
    feedbackError?: string
    feedbackSavingRuleId?: string
    debugContext?: QcResultDebugContext
  }>(),
  {
    presentationMode: 'flat',
    feedbackByRule: () => ({}),
    feedbackEnabled: false,
    feedbackLoading: false,
    feedbackError: '',
    feedbackSavingRuleId: '',
  },
)

const emit = defineEmits<{
  (event: 'select', key: string): void
  (event: 'locate-evidence', evidence: SingleRecordQcEvidence): void
  (event: 'submit-feedback', ruleId: string, input: SaveQcResultFeedbackInput): void
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
  copy_similarity: '实际相似度',
  copy_similarity_threshold: '判定阈值',
  compared_sections: '比对范围',
  identified_implants: '已识别植入物',
  missing_visit_sources: '缺少访视记录',
  performed_anesthesia_confirmed: '已实施麻醉',
  performed_transfusion_confirmed: '已实施输血',
  transfusion_order_present: '已开立输血医嘱',
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
        ['LX0609-06-01-04', 'LX0609-06-01-05', 'LX0609-06-03-03', 'LX0609-06-03-04'].includes(
          item.rule_id,
        ) &&
        examLabInternalFactKeys.has(key)
      )
    })
    .map(([key, rawValue]) => {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue]
      const value = values
        .map((entry) => {
          if (key === 'window_hours' && typeof entry === 'number' && Number.isFinite(entry)) {
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
          const customerLabel = customerFactValueLabel(entry)
          if (key === 'failure_kind') return customerLabel || ''
          return customerLabel || String(entry)
        })
        .filter(Boolean)
        .join('、')
      const sourceLabel = typeof facts.source_label === 'string' ? facts.source_label.trim() : ''
      const label =
        key === 'anchor_time' && item.rule_id === 'LX0609-01-02-01'
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
  if (item.rule_id !== 'LX0609-04-02-04') return []
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

function consultationRecommendationPresentation(item: SingleRecordQcResultItem) {
  return buildConsultationRecommendationPresentation(item)
}

function resultHeadline(item: SingleRecordQcResultViewItem) {
  const examHeadline = examLabEventPresentation(item)?.headline
  if (examHeadline) return examHeadline

  // LX0609-01-01-02 的结论已包含完整医学分析；逐项判定区域会再次展示该分析。
  // 列表摘要只保留判定结论，完整内容仍在下方“医学分析”中查看，避免重复。
  if (
    item.rule_id === 'LX0609-01-01-02' &&
    item.criterion_results?.some(
      (criterion) =>
        criterion.criterion_id === 'diagnostic_direction' && criterion.medical_analysis,
    )
  ) {
    const conclusion = item.conclusionText
    const markers = ['不能据此导出第一诊断：', '第一诊断可导出：']
    const marker = markers.find((value) => conclusion.includes(value))
    if (marker) {
      return `${conclusion.split(marker, 1)[0]}${marker.replace('：', '')}。`
    }
  }
  return item.conclusionText
}

type DisplayFactRow = ReturnType<typeof displayFactRows>[number]

function remainingDisplayFactRows(item: SingleRecordQcResultItem) {
  const displayedKeys = new Set<string>(timelinessResultRows(item).map((row) => row.key))
  if (examLabEventPresentation(item)) {
    displayedKeys.add('report_time')
    displayedKeys.add('response_record_count')
  }
  if (consultationRecommendationPresentation(item)) {
    displayedKeys.add('completed_opinion_episode_count')
    displayedKeys.add('recommendation_count')
    displayedKeys.add('specific_execution_count')
    displayedKeys.add('generic_execution_count')
    displayedKeys.add('missing_execution_count')
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
  if (item.rule_id !== 'LX0609-12-01-02') return []
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

const { confirmedResultsOnly } = useQcResultVisibility()
const allViewItems = computed(() => buildSingleRecordQcResultItems(props.items))
const viewItems = computed(() =>
  confirmedResultsOnly.value
    ? allViewItems.value.filter((item) => item.status === 'non_compliant')
    : allViewItems.value,
)
const technicalFailureCount = computed(
  () => allViewItems.value.filter((item) => item.status === 'technical_error').length,
)
const debugCopyingKey = ref('')

async function copySingleDebugResult(item: SingleRecordQcResultViewItem) {
  if (confirmedResultsOnly.value || debugCopyingKey.value) return
  debugCopyingKey.value = item.key
  try {
    const copied = await copyQcResultDebugText(buildQcResultDebugText([item], props.debugContext))
    if (copied) message.success('本条脱敏质控调试信息已复制')
    else message.error('复制失败，请检查浏览器剪贴板权限')
  } finally {
    debugCopyingKey.value = ''
  }
}

const isGroupedPresentation = computed(() => props.presentationMode === 'grouped')
const presentation = computed(() => buildSingleRecordQcPresentation(props.items))
const resultExecutionSummary = computed(() => {
  if (confirmedResultsOnly.value) return `${viewItems.value.length} 条确定问题`
  const total = viewItems.value.length
  const notExecuted = viewItems.value.filter((item) => item.status === 'not_executed').length
  const executed = total - notExecuted
  return notExecuted > 0
    ? `${total} 个质控点 · 已执行 ${executed} · 未执行 ${notExecuted}`
    : `${total} 个质控点 · 已执行 ${executed}`
})
const statusTabs = computed(() =>
  buildSingleRecordQcStatusTabs(viewItems.value).filter(
    (tab) => !confirmedResultsOnly.value || tab.key === 'non_compliant',
  ),
)
const activeTab = ref<SingleRecordQcResultTabKey>('non_compliant')
const activeReportTab = ref<SingleRecordQcResultReportTab>('all')
const reportTabs = computed(() => [
  {
    key: 'non_compliant' as const,
    label: '确定问题',
    count: presentation.value.counts.nonCompliant,
  },
  { key: 'data_gap' as const, label: '资料待核实', count: presentation.value.counts.dataGap },
  { key: 'uncertain' as const, label: '待判断', count: presentation.value.counts.uncertain },
  { key: 'compliant' as const, label: '合规', count: presentation.value.counts.compliant },
  {
    key: 'not_applicable' as const,
    label: '不适用',
    count: presentation.value.counts.notApplicable,
  },
  { key: 'all' as const, label: '全部规则', count: viewItems.value.length },
].filter((tab) => !confirmedResultsOnly.value || tab.key === 'non_compliant'))
const visibleItems = computed(() =>
  activeTab.value === 'all'
    ? viewItems.value
    : viewItems.value.filter((item) => resolveSingleRecordQcResultTab(item) === activeTab.value),
)
const visibleGroups = computed(() => {
  if (isGroupedPresentation.value) {
    return presentation.value.sectionsByTab[confirmedResultsOnly.value ? 'non_compliant' : activeReportTab.value]
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
const feedbackOpenKey = ref('')
const ruleTextOpenKey = ref('')
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
  return !group || group.count <= 1 || isDocumentGroupExpanded(group.key)
}

function shouldRenderDocumentGroupItem(itemKey: string) {
  const group = documentGroupForItem(itemKey)
  return !group || group.count <= 1 || group.isFirst || isDocumentGroupExpanded(group.key)
}

function resolveDefaultReportTab(): SingleRecordQcResultReportTab {
  if (confirmedResultsOnly.value) return 'non_compliant'
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

function handleContentClick(event: MouseEvent, item: SingleRecordQcResultViewItem) {
  const selection = window.getSelection()
  const target = event.currentTarget
  // 拖选文字后释放鼠标也会触发 click，不应因此展开或收起卡片。
  if (
    event.detail > 0 &&
    selection &&
    !selection.isCollapsed &&
    target instanceof Node &&
    (target.contains(selection.anchorNode) || target.contains(selection.focusNode))
  )
    return
  toggle(item.key)
}

function toggleFeedback(key: string) {
  feedbackOpenKey.value = feedbackOpenKey.value === key ? '' : key
}

function toggleRuleText(key: string) {
  ruleTextOpenKey.value = ruleTextOpenKey.value === key ? '' : key
}

function displayRuleName(item: Pick<SingleRecordQcResultViewItem, 'rule_name' | 'rule_id'>): string {
  return typeof item.rule_name === 'string' && item.rule_name.trim() ? item.rule_name : item.rule_id
}

/** 同一页面的规则都属于同一目录，编号去掉目录前缀，完整编号放在 title 中。 */
function shortRuleCode(ruleId: string): string {
  return ruleId.replace(/^[A-Z]+\d+-(?=\d)/, '')
}

function statusModifierClass(item: SingleRecordQcResultViewItem): string {
  return item.tone === 'neutral' ? '' : `mq-status--${item.tone}`
}

/** 证据胶囊只显示文书名，原文摘录放在悬停提示中；点击后在左侧病历中定位高亮。 */
function evidenceHint(evidence: SingleRecordQcEvidence): string {
  if (evidence.excerpt_kind === '文书级依据') return '已定位到文书，未定位到具体片段'
  if (evidence.evidence_excerpt) {
    return `${evidence.excerpt_kind || '病历原文依据'}：${evidence.evidence_excerpt}`
  }
  return '在病历中定位相关文书'
}

function evidenceLabel(evidence: SingleRecordQcEvidence) {
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
    rescue_record: '抢救记录',
    surgery_record: '手术记录',
    inpat_drug_order: '药物医嘱',
    inpat_nondrug_order: '医嘱',
  }
  const sourceLabel = evidence.source_label || labels[evidence.source_type || ''] || '来源文书'
  if (evidence.recommendation_index && evidence.evidence_role) {
    return `第${evidence.recommendation_index}条建议 · ${evidence.evidence_role === 'opinion' ? '会诊意见' : '执行证据'} · ${sourceLabel}`
  }
  return sourceLabel
}

const examLabCourseEvidenceTypes = new Set([
  'first_course_record',
  'daily_course_record',
  'senior_course_record',
  'rescue_record',
])

function displayEvidence(item: SingleRecordQcResultItem): SingleRecordQcEvidence[] {
  const evidence = recommendationEvidenceForSingleRecord(item)
  if (
    item.status !== 'non_compliant' ||
    !['LX0609-06-01-04', 'LX0609-06-01-05', 'LX0609-06-03-03', 'LX0609-06-03-04'].includes(
      item.rule_id,
    )
  ) {
    return evidence
  }
  // 这类“未记录”结果中，病程仅代表已核对范围，并不是支持缺陷的命中文书。
  return evidence.filter((item) => !examLabCourseEvidenceTypes.has(item.source_type || ''))
}

function isCompliantResult(item: SingleRecordQcResultItem) {
  return item.status === 'compliant'
}

function hasCompliantNarrative(item: SingleRecordQcResultItem) {
  return Boolean(item.detail || item.actual || item.standard)
}

function hasCompliantSupportingDetails(item: SingleRecordQcResultItem) {
  return Boolean(
    remainingDisplayFactRows(item).length || displayEvidence(item).length || item.model_analysis,
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
    if (!tabs.some((tab) => tab.key === activeTab.value)) activeTab.value = 'non_compliant'
  },
  { immediate: true },
)

watch(
  reportTabs,
  (tabs) => {
    if (!tabs.some((tab) => tab.key === activeReportTab.value)) activeReportTab.value = 'non_compliant'
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
    -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei UI',
    'Microsoft YaHei', sans-serif;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px 5px;
}

.toolbar-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
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
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 5px;
  min-width: 0;
  padding: 4px 12px 8px;
}
.result-tab {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 5px;
  min-height: 28px;
  padding: 3px 8px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.84);
  color: rgba(29, 29, 31, 0.62);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
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
  border-color: #0a6cff;
  background: #0a6cff;
  color: #fff;
  box-shadow: none;
}

.result-tab:not(.is-active) {
  border-color: #e5eaf0;
  background: #f7f9fc;
  color: #52647b;
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
  grid-template-columns: minmax(0, 1fr);
  min-width: 0;
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
  color: #0a6cff;
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
  min-width: 0;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.025);
  isolation: isolate;
  transition:
    background-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
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
  border-color: rgba(10, 108, 255, 0.22);
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.result-row.is-expanded::before {
  opacity: 1;
  transform: scaleY(1);
}

.result-row.is-expanded {
  border-color: #dce4ee;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.result-trigger {
  position: relative;
  z-index: 1;
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-height: 0;
  padding: 10px 14px 8px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.result-trigger:hover {
  background: transparent;
}
.result-row:not(.is-expanded) .result-trigger {
  padding: 9px 14px 7px;
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
  -webkit-user-select: text;
  user-select: text;
  cursor: text;
}

.result-row-header {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-right: 0;
  min-height: 22px;
}

.result-row-debug-copy {
  margin-left: auto;
  display: inline-flex;
  height: 28px;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  padding: 0 8px;
  color: rgba(29, 29, 31, 0.62);
  cursor: pointer;
  font-size: 11px;
  font-weight: 650;
  line-height: 1;
  transition:
    border-color 160ms ease,
    background 160ms ease,
    color 160ms ease;
  white-space: nowrap;
}

.result-row-debug-copy:hover:not(:disabled) {
  border-color: rgba(10, 108, 255, 0.28);
  background: #f5f9ff;
  color: #0a6cff;
}

.result-row-debug-copy:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

/* 复制调试信息只给实施人员用：弱化为图标按钮，文字仅供读屏 */
.result-row-debug-copy {
  width: 28px;
  justify-content: center;
  padding: 0;
  border-color: transparent;
  background: transparent;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
.rule-code {
  padding: 1px 0;
  color: rgba(29, 29, 31, 0.46);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}
@media (prefers-reduced-motion: reduce) {
  .result-row,
  .result-row::before {
    transition: none;
  }

  .result-row:hover {
    transform: none;
  }
}

.rule-name {
  display: block;
  min-width: 0;
  margin: 0 0 5px;
  color: #263547;
  font-size: 14px;
  line-height: 22px;
  font-weight: 700;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.result-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 5px;
}
.result-title-row .rule-name {
  flex: 1;
  margin: 0;
}
.rule-conclusion {
  display: block;
  color: #526071;
  font-size: 13px;
  font-weight: 400;
  line-height: 22px;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}
.empty-evidence-note {
  margin: 0;
  padding: 12px 0;
  color: #6b7b8e;
  font-size: 13px;
  line-height: 21px;
}
.empty-evidence-note span {
  display: block;
  font-size: 12px;
}
.result-card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 16px;
  margin: 0 14px;
  padding: 5px 0 6px;
  border-top: 1px solid #edf0f4;
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

.result-detail {
  margin: 0 10px 10px;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.compliant-detail {
  padding: 10px 12px 9px;
  background: rgba(255, 255, 255, 0.72);
}

.compliant-detail > :not(:first-child) {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.065);
}

.decision-summary {
  padding: 10px 12px 9px;
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

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
}

.detail-grid.is-compliant:not(.has-main-details) {
  grid-template-columns: minmax(0, 1fr);
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
  border: 0;
  border-radius: 6px;
  background: transparent;
}

.fact-block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-bottom: 0;
  background: transparent;
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
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 0;
  padding: 0 10px 8px;
}

.decision-fact-block .fact-list dt,
.decision-fact-block .fact-list dd {
  min-width: 0;
  min-height: 36px;
  padding: 8px 0;
  border-bottom: 1px solid #edf1f5;
  font-size: 13px;
  line-height: 20px;
  overflow-wrap: anywhere;
}

.decision-fact-block .fact-list dt:last-of-type,
.decision-fact-block .fact-list dd:last-of-type {
  border-bottom: 0;
}

.decision-fact-block .fact-list dt {
  padding-right: 16px;
  color: rgba(20, 42, 68, 0.58);
  font-weight: 550;
}

.decision-fact-block .fact-list dd {
  text-align: right;
  font-variant-numeric: tabular-nums;
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
  background: rgba(10, 108, 255, 0.025);
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
  color: rgba(10, 108, 255, 0.55);
}

.copy-pair-hint {
  margin-top: 7px !important;
  color: rgba(29, 29, 31, 0.48) !important;
  font-size: 11px !important;
  line-height: 17px !important;
}

/* 历史不适用结果缺审计回执：弱提示，不改结论样式。 */
.audit-evidence-note {
  margin: 0 0 8px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}

.medical-analysis summary {
  cursor: pointer;
  color: #0a6cff;
  list-style-position: inside;
}

.medical-analysis[open] summary {
  margin-bottom: 6px;
}
.model-analysis p {
  color: rgba(29, 29, 31, 0.68);
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
}

@container (max-width: 560px) {
  .result-trigger {
    padding: 10px 14px 8px;
  }

  .result-detail {
    margin: 0 8px 8px;
  }

  .status-pill {
    font-size: 12px;
  }

  .rule-name {
    font-size: 14px;
    line-height: 22px;
  }

  .rule-conclusion {
    font-size: 13px;
    line-height: 22px;
  }

  .copy-match-headline-documents {
    font-size: 12px;
    line-height: 19px;
  }
}

/* ===== v7.1 液态玻璃覆盖：透明底、分段式筛选、Token 语义色、结果卡圆角 ===== */
.single-record-result-panel {
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}
.result-toolbar {
  border-bottom: 0.5px solid var(--mq-border);
  background: rgba(255, 255, 255, 0.72);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
}
.toolbar-summary strong {
  font-family: var(--mq-font-display);
  font-weight: 700;
}
.result-tabs {
  gap: 2px;
  margin: 4px 12px 10px;
  padding: 3px;
  border-radius: 13px;
  background: var(--mq-bg-muted);
}
.result-tab {
  min-height: 30px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  box-shadow: none;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}
.result-tab:hover {
  background: rgba(255, 255, 255, 0.6);
  color: var(--mq-text-primary);
}
.result-tab.is-active {
  border-color: transparent;
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(10, 55, 115, 0.12);
  color: var(--mq-text-primary);
  font-weight: 600;
}
.result-tab.is-active b {
  background: var(--mq-info-bg);
  color: var(--mq-info-text);
}
.result-row {
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 2px 10px rgba(10, 55, 115, 0.06);
}
.result-row.is-active,
.result-row[aria-current='true'] {
  border-color: var(--mq-brand-600);
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.1);
}
.result-row :deep(.ant-btn),
.result-card-actions button {
  border-radius: 999px;
}

/* ===== 展开详情轻量化：时限与判定事实统一为左对齐「标签 内容」列表，证据 / 反馈收为细行（只改样式） ===== */
.result-detail .decision-summary {
  padding: 4px 0 0;
  border-bottom: 0;
  background: transparent;
}
.result-detail :deep(.timeliness-metrics) {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
  margin-top: 8px;
  padding: 0;
  border: 0;
}

.result-detail :deep(.timeliness-metric) {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  padding: 0;
  border-right: 0;
  text-align: left;
}

.result-detail :deep(.timeliness-metric span),
.result-detail .decision-fact-block .fact-list dt {
  color: #6b7280;
  font-size: 12px;
  font-weight: 400;
  line-height: 20px;
}

.result-detail :deep(.timeliness-metric strong),
.result-detail .decision-fact-block .fact-list dd {
  color: #1f2937;
  font-size: 13px;
  font-weight: 400;
  line-height: 20px;
}

.result-detail :deep(.timeliness-metric.is-overdue strong) {
  color: #c62828;
}

.result-detail :deep(.timeline-point strong) {
  font-weight: 400;
}

/* 时限与事实已并成同一张列表，分组标题只留给读屏，避免出现「有标签没内容」的空行 */
.result-detail .decision-fact-block .fact-block-header {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.result-detail .decision-fact-block {
  padding-top: 6px !important;
}
.result-detail .decision-fact-block .fact-list {
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 6px 10px;
  padding: 0 0 10px;
}

.result-detail .decision-fact-block .fact-list dt,
.result-detail .decision-fact-block .fact-list dd {
  min-height: 0;
  padding: 0;
  border-bottom: 0;
  text-align: left;
}
</style>

<style scoped src="../styles/single-record-result-card.css"></style>
