<template>
  <section class="consultation-summary" data-testid="consultation-recommendation-summary">
    <header class="consultation-summary-header">
      <div class="consultation-summary-heading">
        <h4>逐条建议核对</h4>
        <p>展示建议原文及对应的执行证据核对结果</p>
      </div>
      <p class="consultation-summary-counts" aria-label="会诊建议核对统计">
        <strong>{{ presentation.comparedCount }}</strong> 条纳入核对
        <span v-if="presentation.excludedCount"> · {{ presentation.excludedCount }} 条不纳入 </span>
      </p>
    </header>

    <section
      v-if="comparedRows.length"
      class="consultation-compared"
      aria-labelledby="consultation-compared-title"
    >
      <h5 id="consultation-compared-title">纳入缺陷核对</h5>
      <ol class="consultation-recommendation-list">
        <li
          v-for="(row, index) in comparedRows"
          :key="row.key"
          class="consultation-recommendation-row"
          data-testid="consultation-recommendation-row"
        >
          <span class="consultation-recommendation-index" aria-hidden="true">
            {{ index + 1 }}
          </span>
          <div class="consultation-recommendation-content">
            <div class="consultation-recommendation-head">
              <span class="consultation-recommendation-position">
                第{{ row.episodeIndex }}次会诊<span v-if="row.recommendationIndex">
                  · 第{{ row.recommendationIndex }}条建议</span
                >
              </span>
              <span
                class="mq-status consultation-recommendation-status"
                :class="{
                  'mq-status--success': row.state === 'specific',
                  'mq-status--warning': row.state === 'generic' || row.state === 'unknown',
                  'mq-status--danger': row.state === 'missing',
                }"
              >
                {{ row.statusLabel }}
              </span>
            </div>
            <p class="consultation-recommendation-text">
              {{ row.text }}
            </p>
            <p class="consultation-recommendation-detail">
              {{ row.detail }}
            </p>
          </div>
        </li>
      </ol>
    </section>

    <section
      v-if="excludedRows.length"
      class="consultation-excluded mq-soft"
      aria-labelledby="consultation-excluded-title"
    >
      <div class="consultation-excluded-heading">
        <h5 id="consultation-excluded-title">不作为缺陷依据</h5>
        <span>{{ excludedRows.length }} 条</span>
      </div>
      <p class="consultation-excluded-intro">
        条件是否成立无法从现有记录确认，因此不参与执行证据对比。
      </p>
      <div
        v-for="row in excludedRows"
        :key="row.key"
        class="consultation-excluded-row"
        data-testid="consultation-recommendation-row"
      >
        <span class="consultation-recommendation-position">
          第{{ row.episodeIndex }}次会诊<span v-if="row.recommendationIndex">
            · 第{{ row.recommendationIndex }}条建议</span
          >
        </span>
        <p class="consultation-recommendation-text">
          {{ row.text }}
        </p>
        <p class="consultation-recommendation-detail">
          {{ row.detail }}
        </p>
      </div>
    </section>

    <footer class="consultation-checked-sources">
      <strong>本次已核对</strong>
      <span>{{ presentation.checkedSources.join('、') }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { ConsultationRecommendationPresentation } from './single-record-result-model'

const props = defineProps<{
  presentation: ConsultationRecommendationPresentation
}>()

const comparedRows = computed(() =>
  props.presentation.rows.filter((row) => row.state !== 'excluded'),
)
const excludedRows = computed(() =>
  props.presentation.rows.filter((row) => row.state === 'excluded'),
)
</script>

<style scoped>
.consultation-summary {
  margin: 0 var(--mq-space-4) var(--mq-space-4);
  padding: var(--mq-space-4) var(--mq-space-5) var(--mq-space-3);
  border-top: 1px solid var(--mq-border);
}

.consultation-summary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--mq-space-4);
  margin-bottom: var(--mq-space-4);
}

.consultation-summary-heading h4,
.consultation-summary-heading p,
.consultation-summary-counts,
.consultation-compared h5,
.consultation-excluded h5,
.consultation-excluded p,
.consultation-recommendation-row p {
  margin: 0;
}

.consultation-summary-heading h4 {
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 600;
  line-height: 20px;
}

.consultation-summary-heading p {
  margin-top: 2px;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 18px;
}

.consultation-summary-counts {
  flex-shrink: 0;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 20px;
  white-space: nowrap;
}

.consultation-summary-counts strong {
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.consultation-compared h5,
.consultation-excluded h5 {
  color: var(--mq-text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.consultation-recommendation-list {
  margin: var(--mq-space-2) 0 0;
  padding: 0;
  list-style: none;
}

.consultation-recommendation-row {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: var(--mq-space-3);
  padding: var(--mq-space-3) 0;
  border-bottom: 1px solid var(--mq-border);
}

.consultation-recommendation-row:last-child {
  border-bottom: 0;
}

.consultation-recommendation-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--mq-bg-muted);
  color: var(--mq-text-secondary);
  font-family: var(--mq-font-mono);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.consultation-recommendation-content {
  min-width: 0;
}

.consultation-recommendation-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mq-space-3);
}

.consultation-recommendation-position {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 18px;
}

.consultation-recommendation-status {
  flex-shrink: 0;
}

.consultation-recommendation-text {
  margin-top: var(--mq-space-1) !important;
  color: var(--mq-text-primary);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.consultation-recommendation-detail {
  margin-top: var(--mq-space-1) !important;
  color: var(--mq-text-secondary);
  font-size: 12px;
  line-height: 18px;
}

.consultation-excluded {
  margin-top: var(--mq-space-3);
  padding: var(--mq-space-3) var(--mq-space-4);
}

.consultation-excluded-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mq-space-3);
}

.consultation-excluded-heading span,
.consultation-excluded-intro {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 18px;
}

.consultation-excluded-intro {
  margin-top: 2px !important;
}

.consultation-excluded-row {
  margin-top: var(--mq-space-3);
  padding-top: var(--mq-space-3);
  border-top: 1px solid var(--mq-border);
}

.consultation-checked-sources {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--mq-space-2);
  margin-top: var(--mq-space-4);
  padding-top: var(--mq-space-3);
  border-top: 1px solid var(--mq-border);
  font-size: 12px;
  line-height: 18px;
}

.consultation-checked-sources strong {
  color: var(--mq-text-secondary);
  font-weight: 600;
}

.consultation-checked-sources span {
  color: var(--mq-text-tertiary);
}

@container (max-width: 560px) {
  .consultation-summary {
    padding-inline: var(--mq-space-3);
  }

  .consultation-summary-header,
  .consultation-recommendation-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .consultation-summary-counts {
    white-space: normal;
  }

  .consultation-checked-sources {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
