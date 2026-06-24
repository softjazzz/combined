<template>
  <section class="overview-shell">
    <div class="overview-head">
      <div>
        <p class="overview-eyebrow">
          四川省语义质控规则库
        </p>
        <h2 class="overview-title">
          规则运营总览
        </h2>
        <p class="overview-subtitle">
          面向病历质控运营与审计，统一管理规则复杂度、缺陷风险与执行入口。
        </p>
      </div>
      <div class="overview-actions">
        <a-button
          class="overview-action-btn"
          @click="emit('query')"
        >
          查询
        </a-button>
        <a-button
          class="overview-action-btn"
          @click="emit('reset')"
        >
          重置
        </a-button>
        <a-button
          class="overview-action-btn"
          :loading="loading"
          @click="emit('refresh')"
        >
          刷新
        </a-button>
      </div>
    </div>

    <div class="kpi-grid">
      <article
        v-for="card in kpiCards"
        :key="card.key"
        class="kpi-card"
        :class="`kpi-card-${card.tone}`"
      >
        <p class="kpi-label">
          {{ card.label }}
        </p>
        <p class="kpi-value">
          {{ card.value }}
        </p>
        <p class="kpi-desc">
          {{ card.desc }}
        </p>
      </article>
    </div>
  </section>

  <section class="analysis-shell">
    <article class="analysis-panel">
      <div class="analysis-head">
        <h3 class="analysis-title">
          风险分布
        </h3>
      </div>
      <div class="risk-list">
        <div class="risk-row">
          <div class="risk-meta">
            <span>严重缺陷（阻断）</span>
            <span class="risk-count danger">{{ criticalDefectCount }}</span>
          </div>
          <div class="risk-track">
            <div
              class="risk-fill danger"
              :style="{ width: `${getDefectRate(criticalDefectCount)}%` }"
            />
          </div>
        </div>
        <div class="risk-row">
          <div class="risk-meta">
            <span>一般缺陷（警告）</span>
            <span class="risk-count warning">{{ majorDefectCount }}</span>
          </div>
          <div class="risk-track">
            <div
              class="risk-fill warning"
              :style="{ width: `${getDefectRate(majorDefectCount)}%` }"
            />
          </div>
        </div>
        <div class="risk-row">
          <div class="risk-meta">
            <span>轻微缺陷（提示）</span>
            <span class="risk-count safe">{{ minorDefectCount }}</span>
          </div>
          <div class="risk-track">
            <div
              class="risk-fill safe"
              :style="{ width: `${getDefectRate(minorDefectCount)}%` }"
            />
          </div>
        </div>
      </div>
      <p class="risk-footnote">
        风险密度 {{ riskDensity }}
      </p>
    </article>

    <article class="analysis-panel">
      <div class="analysis-head">
        <h3 class="analysis-title">
          分类覆盖 Top3
        </h3>
      </div>
      <div class="category-list">
        <div
          v-for="(cat, idx) in topCategories"
          :key="cat.name"
          class="category-item"
        >
          <div class="category-index">
            0{{ idx + 1 }}
          </div>
          <div class="category-meta">
            <span class="category-name">{{ cat.name }}</span>
            <span class="category-ratio">{{ getCategoryRatio(cat.count) }}</span>
          </div>
          <div class="category-count">
            {{ cat.count }}
          </div>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import type { SemanticKpiCard } from '../types'

defineProps<{
  loading: boolean
  kpiCards: SemanticKpiCard[]
  criticalDefectCount: number
  majorDefectCount: number
  minorDefectCount: number
  riskDensity: string
  topCategories: Array<{ name: string; count: number }>
  getDefectRate: (count: number) => number
  getCategoryRatio: (count: number) => string
}>()

const emit = defineEmits<{
  query: []
  reset: []
  refresh: []
}>()
</script>

<style scoped>
.overview-shell {
  border: 1px solid rgba(226, 232, 240, 0.88);
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 12px 28px rgba(148, 163, 184, 0.1);
  padding: 20px;
}

.overview-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.overview-eyebrow {
  margin: 0 0 6px;
  color: #5b6b84;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.overview-title {
  margin: 0;
  font-size: 28px;
  line-height: 1.25;
  color: #0f172a;
  font-weight: 700;
}

.overview-subtitle {
  margin: 10px 0 0;
  color: #475569;
  font-size: 14px;
}

.overview-actions {
  display: inline-flex;
  gap: 8px;
}

.overview-action-btn {
  height: 30px;
  border-radius: 8px;
  font-size: 13px;
}

.kpi-grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.12);
  padding: 14px 16px;
}

.kpi-label {
  margin: 0;
  color: #64748b;
  font-size: 12px;
}

.kpi-value {
  margin: 6px 0 0;
  color: #0f172a;
  font-size: 34px;
  line-height: 1.05;
  font-weight: 700;
}

.kpi-desc {
  margin: 6px 0 0;
  color: #94a3b8;
  font-size: 11px;
}

.kpi-card-brand {
  border-color: rgba(47, 111, 237, 0.35);
}

.kpi-card-danger {
  border-color: rgba(239, 68, 68, 0.35);
}

.kpi-card-warning {
  border-color: rgba(245, 158, 11, 0.35);
}

.kpi-card-safe {
  border-color: rgba(16, 185, 129, 0.35);
}

.analysis-shell {
  margin-top: 16px;
  display: grid;
  gap: 16px;
  grid-template-columns: 1.3fr 1fr;
}

.analysis-panel {
  border-radius: 20px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.12);
  padding: 16px;
}

.analysis-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.analysis-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: #0f172a;
}

.risk-list {
  display: grid;
  gap: 14px;
}

.risk-meta {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: #334155;
  margin-bottom: 6px;
}

.risk-track {
  height: 10px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.risk-fill {
  height: 100%;
  border-radius: inherit;
}

.risk-fill.danger {
  background: #ef4444;
}

.risk-fill.warning {
  background: #f59e0b;
}

.risk-fill.safe {
  background: #10b981;
}

.risk-count {
  font-weight: 700;
}

.risk-count.danger {
  color: #dc2626;
}

.risk-count.warning {
  color: #d97706;
}

.risk-count.safe {
  color: #059669;
}

.risk-footnote {
  margin: 14px 0 0;
  text-align: right;
  color: #64748b;
  font-size: 13px;
}

.category-list {
  display: grid;
  gap: 10px;
}

.category-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  align-items: center;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 12px;
  padding: 10px 12px;
}

.category-index {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.category-name {
  display: block;
  color: #0f2747;
  font-size: 14px;
  font-weight: 600;
}

.category-ratio {
  color: #64748b;
  font-size: 13px;
}

.category-count {
  color: #0f2747;
  font-weight: 700;
  font-size: 24px;
  line-height: 1;
}

@media (max-width: 1279px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .analysis-shell {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1023px) {
  .overview-head {
    flex-direction: column;
  }
  .overview-actions {
    flex-wrap: wrap;
  }
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
