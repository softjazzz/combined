<template>
  <div class="readonly-medical-document-content" data-testid="readonly-medical-document-content">
    <template v-if="isReportDocument">
      <section v-if="reportMetadataRows.length" class="readonly-report-metadata">
        <div v-for="item in reportMetadataRows" :key="item.key" class="readonly-report-meta-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </section>
      <section v-if="isLabReport" class="readonly-report-results">
        <h5>检验结果</h5>
        <div class="readonly-report-table-wrap">
          <table class="readonly-report-table">
            <thead>
              <tr>
                <th>检验项目</th>
                <th>结果</th>
                <th>结果提示</th>
                <th>正常值范围</th>
                <th>单位</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in reportItems" :key="item.item_id || item.item_no || index">
                <td>{{ item.item_name || '未命名项目' }}</td>
                <td class="readonly-report-result-value">
                  {{ item.result || '—' }}
                </td>
                <td :class="{ 'is-abnormal': Boolean(item.abnormal_indicator) }">
                  {{ item.abnormal_indicator || '—' }}
                </td>
                <td>{{ item.reference_range || '—' }}</td>
                <td>{{ item.unit || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section v-else class="readonly-report-results">
        <h5>检查结果</h5>
        <div class="readonly-exam-items">
          <article
            v-for="(item, index) in reportItems"
            :key="item.item_id || item.item_no || index"
            class="readonly-exam-item"
          >
            <h6>{{ item.item_name || `检查项目 ${index + 1}` }}</h6>
            <dl>
              <template v-if="item.findings">
                <dt>检查所见</dt>
                <dd>{{ item.findings }}</dd>
              </template>
              <template v-if="item.impression">
                <dt>检查结论</dt>
                <dd>{{ item.impression }}</dd>
              </template>
            </dl>
          </article>
        </div>
      </section>
    </template>
    <template v-else-if="sectionViews.length">
      <section
        v-for="section in sectionViews"
        :key="section.key"
        class="readonly-medical-document-section"
      >
        <h5 class="readonly-medical-document-section-title">
          {{ section.label }}
        </h5>
        <pre class="readonly-medical-document-section-text">{{ section.text }}</pre>
      </section>
    </template>
    <pre v-else class="readonly-medical-document-fallback">{{ document.content || '未记录' }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  EditableMedicalRecordDocument,
  EditableMedicalRecordSection,
  EditableMedicalReportItem,
} from './types'
import { deduplicateMedicalDocumentSections } from './medicalDocumentDisplay'

const props = defineProps<{
  document: EditableMedicalRecordDocument
}>()

type SectionView = {
  key: string
  label: string
  text: string
  orderIndex: number
  sourceIndex: number
}

const REPORT_METADATA_LABELS: Record<string, string> = {
  request_datetime: '申请时间',
  request_time: '申请时间',
  exam_time: '检查时间',
  report_datetime: '报告时间',
  report_time: '报告时间',
  specimen: '标本类型',
  exam_type: '检查类型',
  request_dept: '申请科室',
  performed_dept: '执行科室',
  request_physician: '申请医生',
  reporter: '报告医生',
  verifier: '审核医生',
}

const reportItems = computed<EditableMedicalReportItem[]>(() => props.document.report_items || [])
const isLabReport = computed(() => props.document.document_type === 'labtest_item_report')
const isExamReport = computed(() => props.document.document_type === 'exam_item_report')
const isReportDocument = computed(
  () => (isLabReport.value || isExamReport.value) && reportItems.value.length > 0,
)
const reportMetadataRows = computed(() =>
  Object.entries(props.document.report_metadata || {})
    .filter(([key, value]) => Boolean(REPORT_METADATA_LABELS[key] && String(value || '').trim()))
    .map(([key, value]) => ({ key, label: REPORT_METADATA_LABELS[key], value })),
)

function normalizeLine(value: string): string {
  return value.replace(/\s+/g, '').replace(/[：:]+$/u, '')
}

function removeDuplicateSectionTitle(section: EditableMedicalRecordSection): string {
  const text = String(section.text || '').trim()
  if (!text) return '未记录'

  const lines = text.split(/\r?\n/u)
  if (lines.length > 1 && normalizeLine(lines[0] || '') === normalizeLine(section.label)) {
    return lines.slice(1).join('\n').trim() || '未记录'
  }
  return text
}

const sectionViews = computed<SectionView[]>(() =>
  deduplicateMedicalDocumentSections(props.document.sections || [])
    .map((section, sourceIndex) => ({
      key: section.key || `section-${sourceIndex}`,
      label: String(section.label || '').trim() || '未命名章节',
      text: removeDuplicateSectionTitle(section),
      orderIndex: Number.isFinite(section.order_index)
        ? Number(section.order_index)
        : Number.MAX_SAFE_INTEGER,
      sourceIndex,
    }))
    .sort(
      (left, right) => left.orderIndex - right.orderIndex || left.sourceIndex - right.sourceIndex,
    ),
)
</script>

<style scoped>
.readonly-medical-document-content {
  min-height: 420px;
  max-height: 62vh;
  overflow-y: auto;
  padding: 2px 20px 20px;
  border: 1px solid #dce6f0;
  border-radius: 10px;
  background: #fff;
  color: #172033;
}

.readonly-medical-document-section {
  padding: 20px 0;
  border-bottom: 1px solid #edf1f5;
}

.readonly-medical-document-section:last-child {
  border-bottom: 0;
}

.readonly-report-metadata {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 28px;
  padding: 20px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.readonly-report-meta-item {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  min-width: 0;
  font-size: 13px;
  line-height: 20px;
}

.readonly-report-meta-item span {
  color: rgba(29, 29, 31, 0.52);
}

.readonly-report-meta-item strong {
  overflow-wrap: anywhere;
  color: #1d1d1f;
  font-weight: 600;
}

.readonly-report-results {
  padding: 18px 0 4px;
}

.readonly-report-results > h5 {
  margin: 0 0 12px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
  line-height: 22px;
}

.readonly-report-table-wrap {
  overflow-x: auto;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
}

.readonly-report-table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 13px;
  line-height: 20px;
}

.readonly-report-table th,
.readonly-report-table td {
  padding: 9px 12px;
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  text-align: left;
  vertical-align: middle;
}

.readonly-report-table th:last-child,
.readonly-report-table td:last-child {
  border-right: 0;
}

.readonly-report-table tbody tr:last-child td {
  border-bottom: 0;
}

.readonly-report-table th {
  background: #f5f5f7;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 600;
}

.readonly-report-table th:first-child {
  width: 36%;
}

.readonly-report-table tbody tr:hover {
  background: rgba(0, 102, 204, 0.025);
}

.readonly-report-result-value {
  color: #1d1d1f;
  font-weight: 600;
}

.readonly-report-table .is-abnormal {
  color: #c2410c;
  font-weight: 600;
}

.readonly-exam-items {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.readonly-exam-item {
  padding: 16px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.readonly-exam-item h6 {
  margin: 0 0 10px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}

.readonly-exam-item dl {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px 14px;
  margin: 0;
  font-size: 13px;
  line-height: 22px;
}

.readonly-exam-item dt {
  color: rgba(29, 29, 31, 0.52);
}

.readonly-exam-item dd {
  margin: 0;
  color: #27364a;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .readonly-report-metadata {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.readonly-medical-document-section-title {
  position: relative;
  margin: 0 0 10px;
  padding-left: 12px;
  color: #1264a3;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
}

.readonly-medical-document-section-title::before {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: #4096ff;
  content: '';
}

.readonly-medical-document-section-text,
.readonly-medical-document-fallback {
  margin: 0;
  color: #27364a;
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  font-size: 15px;
  line-height: 1.9;
  white-space: pre-wrap;
  word-break: break-word;
}

.readonly-medical-document-fallback {
  min-height: 380px;
  padding: 20px 0;
}
</style>
