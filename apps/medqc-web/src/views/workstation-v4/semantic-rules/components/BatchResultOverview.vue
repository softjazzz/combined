<template>
  <section v-if="model" class="result-review-overview result-overview-card mq-card">
    <div class="result-overview-card-main">
      <div class="result-overview-identity">
        <MqIconTile class="result-overview-icon" name="task" tone="brand" :size="44" />
        <div class="result-review-overview-copy">
          <div class="result-review-overview-title-row">
            <h3>{{ model.title }}</h3>
            <span
              class="result-review-status-chip mq-status"
              :class="[model.statusClass, `mq-status--${statusTone}`]"
            >
              {{ model.statusText }}
            </span>
          </div>
          <div class="result-review-overview-meta">
            <span v-if="model.createdAtText"> 创建时间：{{ model.createdAtText }} </span>
            <span v-if="model.finishedAtText"> 完成时间：{{ model.finishedAtText }} </span>
            <span>规则集：泸县0609质控点验证 v1</span>
            <span>执行病历：{{ model.recordCount }} 份</span>
            <span>客户质控点：{{ model.customerRuleCount }} 个</span>
          </div>
          <p class="result-review-overview-desc">
            {{ model.outcomeText }}
          </p>
          <p class="result-review-overview-scope">
            {{ model.scopeText }}
          </p>
        </div>
      </div>
      <div class="result-review-overview-stats" data-testid="batch-result-metrics">
        <div
          v-for="metric in metrics"
          :key="metric.key"
          class="mq-soft"
          :class="metric.value > 0 && metric.tone ? `is-${metric.tone}` : ''"
        >
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.unit }}</small>
          <em v-if="metric.hint">{{ metric.hint }}</em>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'

type BatchResultOverviewStatusPill = {
  key: string
  label: string
  value: number
  className: string
}

type BatchResultOverviewModel = {
  title: string
  statusClass: string
  statusText: string
  createdAtText: string
  finishedAtText: string
  recordCount: number
  customerRuleCount: number
  resultCount: number
  outcomeText: string
  scopeText: string
  statusPills: BatchResultOverviewStatusPill[]
  /** 发现确定问题的病历数（客户视图模型提供；缺省时不显示该说明）。 */
  issueRecordCount?: number
}

const props = defineProps<{
  model: BatchResultOverviewModel | null
}>()

// 任务状态类名沿用父组件旧的 tailwind 取值；这里只映射为 v7.1 状态胶囊色调。
const statusTone = computed(() => {
  const value = props.model?.statusClass || ''
  if (/emerald|completed/.test(value)) return 'success'
  if (/rose|failed/.test(value)) return 'danger'
  if (/blue|running/.test(value)) return 'info'
  if (/slate|canceled/.test(value)) return 'neutral'
  return 'warning'
})

function pillValue(key: string): number {
  return props.model?.statusPills.find((item) => item.key === key)?.value || 0
}

// 客户只看四个结论性指标；数值为 0 时不着色（规范 §8）。
const metrics = computed(() => {
  const model = props.model
  if (!model) return []
  const issues = pillValue('non_compliant')
  const records = Math.max(0, model.recordCount)
  return [
    {
      key: 'records',
      label: '质控病历',
      value: records,
      unit: '份',
      tone: '',
      hint:
        typeof model.issueRecordCount === 'number' ? `${model.issueRecordCount} 份发现问题` : '',
    },
    {
      key: 'issues',
      label: '确定问题',
      value: issues,
      unit: '条',
      tone: 'danger',
      hint: records > 1 && issues > 0 ? `平均每份 ${(issues / records).toFixed(1)} 条` : '',
    },
    {
      key: 'data-gap',
      label: '需补充资料',
      value: pillValue('data_gap'),
      unit: '条',
      tone: 'warning',
      hint: '资料不全，暂无法判定',
    },
    {
      key: 'compliant',
      label: '合格',
      value: pillValue('compliant'),
      unit: '条',
      tone: 'success',
      hint: pillValue('not_applicable') > 0 ? `另 ${pillValue('not_applicable')} 条不适用` : '',
    },
  ]
})
</script>

<style scoped>
/* v7.1：玻璃卡 + 指标小块 + 状态胶囊；只引用 --mq-* Token。 */
.result-overview-card {
  padding: 22px 28px 24px;
}

.result-overview-card-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: var(--mq-space-6);
  align-items: center;
}

.result-overview-identity {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: var(--mq-space-4);
  align-items: start;
  min-width: 0;
}

.result-review-overview-copy {
  min-width: 0;
}

.result-review-overview-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--mq-space-3);
}

.result-review-overview-title-row h3 {
  margin: 0;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: var(--mq-font-20);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.3;
}

.result-review-overview-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--mq-space-1) var(--mq-space-4);
  margin-top: var(--mq-space-2);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.result-review-overview-desc,
.result-review-overview-scope {
  margin: var(--mq-space-2) 0 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 1.6;
}

.result-review-overview-scope {
  margin-top: var(--mq-space-1);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.result-review-overview-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(112px, 1fr));
  gap: var(--mq-space-3);
}

.result-review-overview-stats > div {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: baseline;
  column-gap: var(--mq-space-1);
  padding: 14px 16px;
}

.result-review-overview-stats span,
.result-review-overview-stats em {
  grid-column: 1 / -1;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-style: normal;
  font-weight: 600;
}

.result-review-overview-stats em {
  font-weight: 400;
}

.result-review-overview-stats strong {
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: 34px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.15;
}

.result-review-overview-stats small {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-13);
}

.result-review-overview-stats .is-danger strong {
  color: var(--mq-danger-text);
}

.result-review-overview-stats .is-warning strong {
  color: var(--mq-warning-text);
}

.result-review-overview-stats .is-success strong {
  color: var(--mq-success-text);
}

@media (max-width: 1439px) {
  .result-overview-card-main {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 900px) {
  .result-overview-card {
    padding: 18px 20px;
  }

  .result-overview-card-main {
    grid-template-columns: minmax(0, 1fr);
  }

  .result-review-overview-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
