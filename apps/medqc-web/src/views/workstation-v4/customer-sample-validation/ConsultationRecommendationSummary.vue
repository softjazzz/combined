<template>
  <section
    class="consultation-summary"
    data-testid="consultation-recommendation-summary"
  >
    <header class="consultation-summary-header">
      <div>
        <h4>逐条建议核对</h4>
        <p>建议原文、执行证据状态和未纳入原因分别展示</p>
      </div>
      <div
        class="consultation-summary-counts"
        aria-label="会诊建议核对统计"
      >
        <span>纳入核对 {{ presentation.comparedCount }}</span>
        <span
          v-if="presentation.excludedCount"
          class="is-muted"
        >
          未纳入 {{ presentation.excludedCount }}
        </span>
      </div>
    </header>

    <div class="consultation-recommendation-list">
      <article
        v-for="row in presentation.rows"
        :key="row.key"
        class="consultation-recommendation-row"
        :class="`is-${row.state}`"
        data-testid="consultation-recommendation-row"
      >
        <div class="consultation-recommendation-head">
          <span class="consultation-recommendation-position">
            第{{ row.episodeIndex }}次会诊<span v-if="row.recommendationIndex">
              · 第{{ row.recommendationIndex }}条建议</span>
          </span>
          <span
            class="consultation-recommendation-status"
            :class="`is-${row.state}`"
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
      </article>
    </div>

    <footer class="consultation-checked-sources">
      <strong>已核对范围</strong>
      <span>{{ presentation.checkedSources.join('、') }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import type { ConsultationRecommendationPresentation } from './single-record-result-model'

defineProps<{
  presentation: ConsultationRecommendationPresentation
}>()
</script>

<style scoped>
.consultation-summary {
  margin: 0 14px 12px;
  overflow: hidden;
  border: 1px solid rgba(76, 94, 118, 0.14);
  border-radius: 10px;
  background: #f8fafc;
}

.consultation-summary-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(18, 38, 63, 0.07);
  background: rgba(255, 255, 255, 0.92);
}

.consultation-summary-header h4,
.consultation-summary-header p,
.consultation-recommendation-row p {
  margin: 0;
}

.consultation-summary-header h4 {
  color: #344256;
  font-size: 13px;
  font-weight: 600;
  line-height: 19px;
}

.consultation-summary-header p {
  margin-top: 2px;
  color: rgba(20, 42, 68, 0.52);
  font-size: 12px;
  line-height: 18px;
}

.consultation-summary-counts {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 5px;
}

.consultation-summary-counts span {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: #315b9a;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.consultation-summary-counts span.is-muted {
  background: rgba(71, 85, 105, 0.08);
  color: #64748b;
}

.consultation-recommendation-list {
  display: grid;
}

.consultation-recommendation-row {
  display: grid;
  gap: 4px;
  padding: 11px 12px 11px 15px;
  border-top: 1px solid rgba(18, 38, 63, 0.06);
  border-left: 3px solid #cbd5e1;
  background: rgba(255, 255, 255, 0.72);
}

.consultation-recommendation-row:first-child {
  border-top: 0;
}

.consultation-recommendation-row.is-specific {
  border-left-color: #22a06b;
}

.consultation-recommendation-row.is-generic,
.consultation-recommendation-row.is-unknown {
  border-left-color: #d99b24;
}

.consultation-recommendation-row.is-missing {
  border-left-color: #d64545;
}

.consultation-recommendation-row.is-excluded {
  border-left-color: #94a3b8;
  background: rgba(241, 245, 249, 0.8);
}

.consultation-recommendation-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.consultation-recommendation-position {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 18px;
}

.consultation-recommendation-status {
  flex-shrink: 0;
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(71, 85, 105, 0.08);
  color: #64748b;
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.consultation-recommendation-status.is-specific {
  background: rgba(16, 185, 129, 0.1);
  color: #087443;
}

.consultation-recommendation-status.is-generic,
.consultation-recommendation-status.is-unknown {
  background: rgba(245, 158, 11, 0.11);
  color: #946000;
}

.consultation-recommendation-status.is-missing {
  background: rgba(239, 68, 68, 0.09);
  color: #c62828;
}

.consultation-recommendation-text {
  color: #253246;
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.consultation-recommendation-detail {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  line-height: 18px;
}

.consultation-checked-sources {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  padding: 9px 12px;
  border-top: 1px solid rgba(18, 38, 63, 0.07);
  background: rgba(241, 245, 249, 0.72);
  font-size: 12px;
  line-height: 18px;
}

.consultation-checked-sources strong {
  color: #475569;
  font-weight: 600;
}

.consultation-checked-sources span {
  color: #64748b;
}

@container (max-width: 560px) {
  .consultation-summary-header,
  .consultation-recommendation-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .consultation-summary-counts {
    justify-content: flex-start;
  }

  .consultation-checked-sources {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}
</style>
