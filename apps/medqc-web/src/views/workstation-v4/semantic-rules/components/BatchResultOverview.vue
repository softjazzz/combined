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
          </div>
          <p class="result-review-overview-desc">
            {{ model.outcomeText }}
          </p>
          <p class="result-review-overview-scope">
            {{ model.scopeText }}
          </p>
        </div>
      </div>
      <div class="result-review-overview-stats">
        <div class="mq-soft">
          <span>病历</span>
          <strong>{{ model.recordCount }}</strong>
          <small>份</small>
        </div>
        <div class="mq-soft">
          <span>客户质控点</span>
          <strong>{{ model.customerRuleCount }}</strong>
          <small>个</small>
        </div>
        <div class="mq-soft">
          <span>结果</span>
          <strong>{{ model.resultCount }}</strong>
          <small>条</small>
        </div>
      </div>
      <div class="result-overview-status-block">
        <span class="result-overview-status-label">状态分布</span>
        <div class="result-review-status-pills">
          <span
            v-for="item in model.statusPills"
            :key="item.key"
            class="result-review-status-pill mq-status"
            :class="[item.className, pillToneClass(item)]"
          >
            {{ item.label }} <strong>{{ item.value }}</strong>
          </span>
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

const PILL_TONES: Record<string, string> = {
  'is-danger': 'mq-status--danger',
  'is-warning': 'mq-status--warning',
  'is-success': 'mq-status--success',
}

// 数值为 0 时回到中性色，不做强调（规范 §8）。
function pillToneClass(item: BatchResultOverviewStatusPill): string {
  return item.value > 0 ? PILL_TONES[item.className] || '' : 'is-zero'
}
</script>

<style scoped>
/* v7.1：玻璃卡 + 指标小块 + 状态胶囊；只引用 --mq-* Token。 */
.result-overview-card {
  padding: 22px 28px 24px;
}

.result-overview-card-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 0.9fr);
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
  grid-template-columns: repeat(3, minmax(104px, auto));
  gap: var(--mq-space-3);
}

.result-review-overview-stats > div {
  display: grid;
  grid-template-columns: auto auto;
  align-items: baseline;
  justify-content: start;
  column-gap: var(--mq-space-1);
  padding: 14px 18px;
}

.result-review-overview-stats span {
  grid-column: 1 / -1;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
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

.result-overview-status-block {
  display: grid;
  gap: var(--mq-space-2);
  min-width: 0;
  padding-left: var(--mq-space-6);
  border-left: 0.5px solid var(--mq-border-strong);
}

.result-overview-status-label {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.result-review-status-pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--mq-space-2);
}

.result-review-status-pill {
  padding: 5px 12px;
  font-size: var(--mq-font-13);
  line-height: 20px;
}

.result-review-status-pill strong {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.result-review-status-pill.is-zero {
  color: var(--mq-text-tertiary);
}

@media (max-width: 1439px) {
  .result-overview-card-main {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .result-overview-status-block {
    grid-column: 1 / -1;
    padding-top: var(--mq-space-4);
    padding-left: 0;
    border-top: 0.5px solid var(--mq-border-strong);
    border-left: 0;
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
