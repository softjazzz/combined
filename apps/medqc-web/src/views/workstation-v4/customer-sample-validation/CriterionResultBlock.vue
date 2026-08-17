<template>
  <section
    v-if="criteria.length"
    class="detail-block criterion-block"
    :class="{ 'compliant-criterion-block': variant === 'compliant' }"
    :data-testid="variant === 'compliant' ? 'single-record-compliant-criteria' : undefined"
  >
    <h4>{{ variant === 'compliant' ? '合规依据' : '逐项判定' }}</h4>
    <article
      v-for="criterion in criteria"
      :key="criterion.criterion_id"
      class="criterion-row"
    >
      <div class="criterion-head">
        <strong>{{ criterionLabel(criterion.criterion_id) }}</strong>
        <span :class="`is-${criterion.status}`">{{ criterionStatusText(criterion.status) }}</span>
      </div>
      <p>{{ criterionFactText(criterion) }}</p>
      <p
        v-if="variant === 'compliant' && criterion.medical_analysis"
        class="criterion-analysis"
      >
        {{ criterion.medical_analysis }}
      </p>
      <details
        v-if="variant === 'decision' && criterion.medical_analysis"
        class="medical-analysis"
      >
        <summary>医学分析</summary>
        <p>{{ criterion.medical_analysis }}</p>
      </details>
    </article>
  </section>
</template>

<script setup lang="ts">
import type { SingleRecordQcCriterionResult } from './single-record-result-model'

defineProps<{
  criteria: SingleRecordQcCriterionResult[]
  variant: 'compliant' | 'decision'
}>()

function criterionLabel(criterionId: string) {
  const labels: Record<string, string> = {
    chief_complaint_length: '主诉书写规范性',
    diagnostic_direction: '诊断指向性',
  }
  return labels[criterionId] || '子项核对'
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
</script>

<style scoped>
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

.compliant-criterion-block {
  padding-top: 1px;
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

.medical-analysis summary {
  cursor: pointer;
  color: #0066cc;
  list-style-position: inside;
}

.medical-analysis[open] summary {
  margin-bottom: 6px;
}
</style>
