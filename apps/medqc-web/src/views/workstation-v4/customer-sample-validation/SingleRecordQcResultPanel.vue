<template>
  <aside
    class="single-record-result-panel"
    aria-label="质控结果"
  >
    <header
      class="result-toolbar"
      data-testid="single-record-result-toolbar"
    >
      <div class="toolbar-summary">
        <strong>质控结果</strong>
        <span data-testid="single-record-result-summary">{{ viewItems.length }} 条结果</span>
      </div>
      <div
        v-if="viewItems.length"
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
          :class="{ 'is-active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          :data-testid="`single-record-result-tab-${tab.key}`"
          @click="activeTab = tab.key"
        >
          <span>{{ tab.label }}</span>
          <b>{{ tab.count }}</b>
        </button>
      </div>
    </header>

    <div
      v-if="!visibleItems.length"
      class="empty-state"
    >
      {{ viewItems.length ? '当前分类下没有质控结果' : '当前没有可展示的质控结果' }}
    </div>

    <div
      v-else
      class="result-list"
    >
      <article
        v-for="item in visibleItems"
        :key="item.key"
        class="result-row"
        :class="[
          `is-${item.tone}`,
          {
            'is-expanded': expandedKey === item.key,
          },
        ]"
        data-testid="single-record-result-row"
      >
        <button
          type="button"
          class="result-trigger"
          :aria-expanded="expandedKey === item.key"
          @click="toggle(item.key)"
        >
          <span
            class="result-row-header"
            data-testid="single-record-result-row-header"
          >
            <span class="result-identity">
              <span
                class="status-pill"
                :class="`is-${item.tone}`"
              >{{ item.displayStatus }}</span>
              <span class="rule-code">{{ item.rule_id }}</span>
              <strong class="rule-name">{{ item.rule_name }}</strong>
            </span>
            <span
              class="toggle-mark"
              aria-hidden="true"
            >{{
              expandedKey === item.key ? '⌃' : '⌄'
            }}</span>
          </span>
          <span
            class="rule-conclusion"
            data-testid="single-record-result-conclusion"
          >{{
            item.conclusionText
          }}</span>
        </button>

        <section
          v-if="expandedKey === item.key"
          class="result-detail"
        >
          <div
            v-if="
              item.detail ||
                item.actual ||
                item.standard ||
                completeTimelinessMetrics(item).length ||
                timelinessTimeline(item).length
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
              v-if="completeTimelinessMetrics(item).length"
              class="timeliness-metrics"
              data-testid="timeliness-metrics"
            >
              <div
                v-for="row in completeTimelinessMetrics(item)"
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
                >→</span>
              </template>
            </div>
          </div>

          <div
            class="detail-grid"
            data-testid="single-record-detail-grid"
          >
            <div class="detail-column detail-column-main">
              <section
                v-if="remainingDisplayFactRows(item).length"
                class="detail-block fact-block"
              >
                <h4>判定事实</h4>
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
                v-if="dataGapRows(item).length"
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
                v-if="item.criterion_results?.length"
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
                  v-if="item.evidence?.length"
                  class="evidence-list"
                >
                  <button
                    v-for="evidence in item.evidence"
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
                      <span aria-hidden="true">›</span>
                    </span>
                  </button>
                </div>
                <p
                  v-else
                  class="muted"
                >
                  未返回可定位原文。
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
            v-if="item.suggestion"
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
import { computed, defineComponent, h, ref, watch } from 'vue'
import {
  buildSingleRecordQcResultItems,
  buildSingleRecordQcStatusTabs,
  resolveSingleRecordQcResultTab,
  type SingleRecordQcEvidence,
  type SingleRecordQcCriterionResult,
  type SingleRecordQcResultItem,
  type SingleRecordQcResultTabKey,
  type SingleRecordQcResultViewItem,
} from './single-record-result-model'

const props = defineProps<{
  items: SingleRecordQcResultItem[]
  selectedKey?: string
}>()

const emit = defineEmits<{
  (event: 'select', key: string): void
  (event: 'locate-evidence', evidence: SingleRecordQcEvidence): void
}>()

const factLabels: Record<string, string> = {
  source_label: '核对文书',
  missing_fields: '缺失字段',
  failure_kind: '判定类型',
  checked_sources: '已核对来源',
  target_document: '目标文书',
  performed_surgery_confirmed: '已实施手术',
  threshold_hours: '规定时限',
  anchor_time: '起算时间',
  observed_time: '记录时间',
  elapsed_hours: '实际间隔',
  overdue_hours: '超出时限',
}

const factValueLabels: Record<string, string> = {
  timeliness_requirement_not_met: '未在规定时限内完成',
  implant_information_incomplete: '植入物信息填写不完整',
  surgery_document_missing: '目标手术文书缺失',
  surgery_document_blank: '目标手术文书内容为空',
  implant_name: '名称',
  implant_category: '种类',
  implant_specification: '规格/型号',
  implant_material: '材质',
  implant_barcode: '条码/批号',
  implant_quantity: '数量',
  surgery_record: '手术记录',
  first_course_record: '首次病程记录',
  presurg_summary: '术前小结',
  surgery_safecheck_record: '手术安全核查表',
}

const dataGapLabels: Record<string, string> = {
  reason_code: '缺口原因',
  missing_sources: '缺少来源',
  missing_fields: '缺少字段',
  required_sources: '所需来源',
  unavailable_sources: '不可用来源',
  availability: '来源状态',
}

const TIMELINESS_METRIC_KEYS = ['threshold_hours', 'elapsed_hours', 'overdue_hours'] as const
const TIMELINESS_TIME_KEYS = ['anchor_time', 'observed_time'] as const

function displayFactRows(item: SingleRecordQcResultItem) {
  const facts = item.customer_display_facts
  if (!facts || typeof facts !== 'object') return []
  return Object.entries(facts)
    .filter(([key]) => Boolean(factLabels[key]))
    .map(([key, rawValue]) => {
      const values = Array.isArray(rawValue) ? rawValue : [rawValue]
      const value = values
        .map((entry) => {
          if (
            ['threshold_hours', 'elapsed_hours', 'overdue_hours'].includes(key) &&
            typeof entry === 'number' &&
            Number.isFinite(entry)
          ) {
            return `${entry} 小时`
          }
          return factValueLabels[String(entry)] || String(entry)
        })
        .filter(Boolean)
        .join('、')
      const sourceLabel = typeof facts.source_label === 'string' ? facts.source_label.trim() : ''
      const label =
        key === 'anchor_time' && item.rule_id === 'LX0609-002'
          ? '入院时间'
          : key === 'observed_time' && sourceLabel
            ? `${sourceLabel}时间`
            : factLabels[key] || key
      return {
        key,
        label,
        value: value === 'true' ? '是' : value === 'false' ? '否' : value,
      }
    })
    .filter((row) => Boolean(row.value))
}

type DisplayFactRow = ReturnType<typeof displayFactRows>[number]

function rowsByKeyOrder(item: SingleRecordQcResultItem, keys: readonly string[]): DisplayFactRow[] {
  const rows = displayFactRows(item)
  return keys
    .map((key) => rows.find((row) => row.key === key))
    .filter((row): row is DisplayFactRow => Boolean(row))
}

function completeTimelinessMetrics(item: SingleRecordQcResultItem) {
  const rows = rowsByKeyOrder(item, TIMELINESS_METRIC_KEYS)
  return rows.length === TIMELINESS_METRIC_KEYS.length ? rows : []
}

function timelinessTimeline(item: SingleRecordQcResultItem) {
  return rowsByKeyOrder(item, TIMELINESS_TIME_KEYS)
}

function remainingDisplayFactRows(item: SingleRecordQcResultItem) {
  const displayedKeys = new Set(timelinessTimeline(item).map((row) => row.key))
  completeTimelinessMetrics(item).forEach((row) => displayedKeys.add(row.key))
  return displayFactRows(item).filter((row) => !displayedKeys.has(row.key))
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
    .filter(([key]) => Boolean(dataGapLabels[key]))
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
const statusTabs = computed(() => buildSingleRecordQcStatusTabs(viewItems.value))
const activeTab = ref<SingleRecordQcResultTabKey>('all')
const visibleItems = computed(() =>
  activeTab.value === 'all'
    ? viewItems.value
    : viewItems.value.filter((item) => resolveSingleRecordQcResultTab(item) === activeTab.value),
)
const expandedKey = ref('')

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
    surgery_record: '手术记录',
    inpat_drug_order: '药物医嘱',
    inpat_nondrug_order: '医嘱',
  }
  return labels[evidence.source_type || ''] || '来源文书'
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

function isPendingEvidenceStatus(item: SingleRecordQcResultItem) {
  return (
    item.status === 'data_gap' ||
    item.status === 'evaluation_unknown' ||
    item.status === 'uncertain'
  )
}

function detailTitle(item: SingleRecordQcResultItem) {
  return isPendingEvidenceStatus(item) ? '缺口说明' : '完整判定说明'
}

function actualTitle(item: SingleRecordQcResultItem) {
  return isPendingEvidenceStatus(item) ? '当前已知情况' : '实际情况'
}

function standardTitle(item: SingleRecordQcResultItem) {
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
  z-index: 2;
  top: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 48px;
  padding: 8px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(18px);
}

.toolbar-summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: max-content;
}

.toolbar-summary strong {
  font-size: 15px;
  font-weight: 650;
  line-height: 22px;
}

.toolbar-summary span,
.muted {
  font-size: 12px;
  line-height: 18px;
  color: rgba(29, 29, 31, 0.58);
}

.result-tabs {
  display: flex;
  gap: 4px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.status-pill {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 58px;
  padding: 1px 7px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 6px;
  background: rgba(29, 29, 31, 0.035);
  color: rgba(29, 29, 31, 0.56);
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
}

.status-pill::before {
  width: 5px;
  height: 5px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: rgba(29, 29, 31, 0.28);
  content: '';
}

.is-danger.status-pill {
  border-color: rgba(217, 45, 32, 0.12);
  background: rgba(217, 45, 32, 0.055);
  color: #c9362b;
}

.is-danger.status-pill::before {
  background: #d92d20;
}

.is-warning.status-pill {
  border-color: rgba(178, 106, 0, 0.11);
  background: rgba(178, 106, 0, 0.05);
  color: #98620c;
}

.is-success.status-pill {
  border-color: rgba(8, 116, 67, 0.1);
  background: rgba(8, 116, 67, 0.045);
  color: #166b48;
}

.result-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 30px;
  padding: 4px 7px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(29, 29, 31, 0.62);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
}

.result-tab:hover {
  background: rgba(0, 0, 0, 0.045);
  color: rgba(29, 29, 31, 0.84);
}

.result-tab.is-active {
  background: rgba(0, 102, 204, 0.065);
  color: #0066cc;
  box-shadow: inset 0 0 0 1px rgba(0, 102, 204, 0.06);
}

.result-tab b {
  min-width: 17px;
  padding: 0 4px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.045);
  color: inherit;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
}

.empty-state {
  padding: 56px 18px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 14px;
  text-align: center;
}

.result-list {
  display: grid;
  gap: 6px;
  padding: 7px 8px 10px;
}

.result-row {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.065);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.78);
  transition:
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}

.result-row:hover {
  border-color: rgba(0, 0, 0, 0.11);
  background: #fff;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.045);
}

.result-row.is-expanded {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.025);
  box-shadow: 0 4px 16px rgba(0, 76, 153, 0.06);
}

.result-trigger {
  display: block;
  width: 100%;
  padding: 11px 12px 10px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.result-trigger:hover {
  background: transparent;
}

.result-row-header,
.result-identity {
  display: flex;
  align-items: center;
  min-width: 0;
}

.result-row-header {
  justify-content: space-between;
  gap: 12px;
}

.result-identity {
  flex: 1 1 auto;
  gap: 7px;
}

.rule-code {
  flex: 0 0 auto;
  padding: 1px 5px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 5px;
  background: rgba(29, 29, 31, 0.03);
  color: rgba(29, 29, 31, 0.5);
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  line-height: 17px;
  white-space: nowrap;
}

.toggle-mark {
  flex: 0 0 auto;
  color: rgba(29, 29, 31, 0.42);
  font-size: 15px;
}

.rule-name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.9);
  font-size: 14px;
  line-height: 20px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rule-conclusion {
  display: -webkit-box;
  margin-top: 6px;
  padding-left: 1px;
  color: rgba(29, 29, 31, 0.66);
  font-size: 13px;
  line-height: 20px;
  overflow: hidden;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.result-detail {
  border-top: 1px solid rgba(0, 0, 0, 0.065);
  background: rgba(246, 247, 249, 0.72);
}

.decision-summary {
  padding: 12px 14px 11px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  background: rgba(255, 255, 255, 0.65);
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
  margin-top: 11px;
  border: 1px solid rgba(0, 0, 0, 0.075);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.74);
}

.timeliness-metric {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 8px 10px;
  border-right: 1px solid rgba(0, 0, 0, 0.07);
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
  font-size: 14px;
  font-weight: 650;
  line-height: 20px;
}

.timeliness-metric.is-overdue strong {
  color: #d92d20;
}

.timeliness-timeline {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 9px;
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
  color: rgba(0, 102, 204, 0.5);
  font-size: 14px;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(260px, 0.92fr);
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

@media (max-width: 900px) {
  .result-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

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
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }

  .timeline-arrow {
    display: none;
  }
}

@media (max-width: 560px) {
  .result-identity {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 4px 7px;
  }

  .rule-name {
    flex-basis: 100%;
    white-space: normal;
  }

  .timeliness-metrics {
    grid-template-columns: 1fr;
  }

  .timeliness-metric {
    border-right: 0;
    border-bottom: 1px solid rgba(0, 0, 0, 0.07);
  }

  .timeliness-metric:last-child {
    border-bottom: 0;
  }
}
</style>
