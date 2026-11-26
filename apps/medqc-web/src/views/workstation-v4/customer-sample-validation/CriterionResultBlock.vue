<template>
  <section
    v-if="criteria.length"
    class="detail-block criterion-block"
    :class="{
      'compliant-criterion-block': variant === 'compliant',
      'mq-soft': variant === 'decision',
    }"
    :data-testid="variant === 'compliant' ? 'single-record-compliant-criteria' : undefined"
  >
    <h4>{{ variant === 'compliant' ? '合规依据' : '逐项判定' }}</h4>
    <article
      v-for="criterion in criteria"
      :key="criterion.criterion_id"
      class="criterion-row"
      :class="`is-${criterion.status}`"
    >
      <MqIcon class="criterion-icon" :name="criterionIcon(criterion.status)" :size="18" />
      <div class="criterion-body">
        <div class="criterion-head">
          <strong>{{ criterionLabel(criterion.criterion_id) }}</strong>
          <span :class="`is-${criterion.status}`">{{ criterionStatusText(criterion.status) }}</span>
        </div>
        <p>{{ criterionFactText(criterion) }}</p>
        <p v-if="variant === 'compliant' && criterion.medical_analysis" class="criterion-analysis">
          {{ criterion.medical_analysis }}
        </p>
        <details
          v-if="variant === 'decision' && criterion.medical_analysis"
          class="medical-analysis"
        >
          <summary>查看医学分析</summary>
          <p>{{ criterion.medical_analysis }}</p>
        </details>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import MqIcon from '@/components/icons/MqIcon.vue'
import type { MqIconName } from '@/components/icons/mqIcons'
import type { SingleRecordQcCriterionResult } from './single-record-result-model'

defineProps<{
  criteria: SingleRecordQcCriterionResult[]
  variant: 'compliant' | 'decision'
}>()

function criterionLabel(criterionId: string) {
  const labels: Record<string, string> = {
    chief_complaint_length: '主诉书写规范性',
    diagnostic_direction: '诊断指向性',
    differential_diagnosis_relation: '鉴别诊断关联性',
  }
  return labels[criterionId] || '子项核对'
}

function criterionStatusText(status: string) {
  if (status === 'passed') return '通过'
  if (status === 'failed') return '未通过'
  return '待确认'
}

function criterionIcon(status: string): MqIconName {
  if (status === 'passed') return 'success'
  if (status === 'failed') return 'failed'
  return 'pending'
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
  if (criterion.criterion_id === 'differential_diagnosis_relation') {
    if (criterion.actual_value === 'related') return '鉴别诊断与第一诊断的临床问题存在合理关联。'
    if (criterion.actual_value === 'unrelated') return '鉴别诊断与第一诊断的临床问题未发现合理关联。'
    return '当前资料不足以可靠判断鉴别诊断与第一诊断的关联。'
  }
  const facts = []
  if (criterion.actual_value != null && criterion.actual_value !== '') {
    facts.push(`实际值：${criterion.actual_value}`)
  }
  if (criterion.expected_value != null && criterion.expected_value !== '') {
    facts.push(`标准：${criterion.expected_value}`)
  }
  return facts.length ? `${facts.join('；')}。` : '该子项已按规则要求完成核对。'
}
</script>

<style scoped>
.detail-block,
.medical-analysis {
  min-width: 0;
  margin: 0;
}

/* 子项结论靠图标表达，分组标题与状态文字只留给读屏 */
.detail-block h4,
.criterion-head span {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.detail-block p,
.medical-analysis p {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: 13px;
  line-height: 20px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.criterion-block {
  position: relative;
  display: grid;
  gap: 10px;
}

.criterion-block.mq-soft {
  padding: 12px 14px;
}

.criterion-row {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 8px;
}

/* 图标颜色继承 currentColor，按子项状态取语义色 */
.criterion-icon {
  margin-top: 1px;
  color: var(--mq-warning-text);
}

.criterion-row.is-passed .criterion-icon {
  color: var(--mq-success-text);
}

.criterion-row.is-failed .criterion-icon {
  color: var(--mq-danger-text);
}

.criterion-body {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 2px;
}

.criterion-head strong {
  color: var(--mq-text-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

/* 已通过的子项压成一行：名称 + 核对依据 */
.criterion-row.is-passed .criterion-body {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 12px;
}

.criterion-row > .criterion-body > .criterion-analysis {
  flex-basis: 100%;
  margin-top: 2px;
}

.medical-analysis summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
  color: var(--mq-info-text);
  font-size: 13px;
  font-weight: 600;
  list-style: none;
  cursor: pointer;
}

.medical-analysis summary::-webkit-details-marker {
  display: none;
}

.medical-analysis summary::before {
  display: inline-block;
  font-size: 11px;
  line-height: 1;
  content: '▸';
  transition: transform 160ms ease;
}

.medical-analysis[open] summary::before {
  transform: rotate(90deg);
}

.medical-analysis[open] summary {
  margin-bottom: 4px;
}

.medical-analysis[open] > p {
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
}
</style>
