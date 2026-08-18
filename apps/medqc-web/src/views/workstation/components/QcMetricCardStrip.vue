<template>
  <section class="qc-metric-card-strip" v-bind="$attrs">
    <article
      v-for="card in cards"
      :key="card.key"
      :class="['qc-metric-card-strip__card', `is-${card.tone}`]"
    >
      <div class="qc-metric-card-strip__head">
        <span class="qc-metric-card-strip__label">{{ card.label }}</span>
        <span class="qc-metric-card-strip__icon" aria-hidden="true">
          <component :is="card.icon" :size="19" :stroke-width="2.1" />
        </span>
      </div>
      <strong class="qc-metric-card-strip__value">{{ card.value }}</strong>
      <small class="qc-metric-card-strip__helper">{{ card.helper }}</small>
    </article>
  </section>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineOptions({ inheritAttrs: false })

interface QcMetricCard {
  key: string
  label: string
  value: number
  helper: string
  icon: Component
  tone: 'brand' | 'warning' | 'success' | 'danger'
}

defineProps<{
  cards: readonly QcMetricCard[]
}>()
</script>

<style scoped>
.qc-metric-card-strip {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.qc-metric-card-strip__card {
  min-width: 0;
  padding: 18px 20px 17px;
  position: relative;
  border: 1px solid rgba(0, 0, 0, 0.075);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.028);
  backdrop-filter: blur(18px);
}

.qc-metric-card-strip__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.qc-metric-card-strip__label {
  overflow: hidden;
  color: rgba(29, 29, 31, 0.55);
  font-size: 15px;
  font-weight: 650;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-metric-card-strip__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 10px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.qc-metric-card-strip__value {
  display: block;
  margin: 9px 0 2px;
  color: #1d1d1f;
  font-size: 32px;
  letter-spacing: -0.03em;
  line-height: 39px;
}

.qc-metric-card-strip__helper {
  display: block;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.42);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-metric-card-strip__card.is-brand .qc-metric-card-strip__value {
  color: #0066cc;
}

.qc-metric-card-strip__card.is-brand .qc-metric-card-strip__icon {
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
}

.qc-metric-card-strip__card.is-warning .qc-metric-card-strip__value {
  color: #c17a08;
}

.qc-metric-card-strip__card.is-warning .qc-metric-card-strip__icon {
  background: rgba(245, 158, 11, 0.1);
  color: #c17a08;
}

.qc-metric-card-strip__card.is-success .qc-metric-card-strip__value {
  color: #047857;
}

.qc-metric-card-strip__card.is-success .qc-metric-card-strip__icon {
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
}

.qc-metric-card-strip__card.is-danger .qc-metric-card-strip__value {
  color: #dc2626;
}

.qc-metric-card-strip__card.is-danger .qc-metric-card-strip__icon {
  background: rgba(239, 68, 68, 0.09);
  color: #dc2626;
}

@media (max-width: 980px) {
  .qc-metric-card-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .qc-metric-card-strip {
    grid-template-columns: 1fr;
  }
}
</style>
