<template>
  <section class="customer-qc-result-detail-card">
    <div class="customer-qc-result-detail-card__primary">
      <span class="customer-qc-result-detail-card__label">质控结论</span>
      <strong>{{ model.conclusion || '未返回结论' }}</strong>
    </div>
    <dl class="customer-qc-result-detail-card__facts">
      <template
        v-for="row in visibleRows"
        :key="row.key"
      >
        <dt>{{ row.label }}</dt>
        <dd>{{ row.value }}</dd>
      </template>
    </dl>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CustomerQcDisplayModel } from '@/views/workstation-v4/semantic-rules/customer-qc-display-model'

const props = defineProps<{
  model: CustomerQcDisplayModel
}>()

const visibleRows = computed(() =>
  [
    { key: 'detail', label: '判定明细', value: props.model.detail },
    { key: 'requirement', label: '规则要求', value: props.model.requirement },
    { key: 'actual-value', label: '实际值', value: props.model.actualValue },
    { key: 'source', label: '证据来源', value: props.model.evidenceSource },
    { key: 'suggestion', label: '处理建议', value: props.model.suggestion },
  ].filter((row) => Boolean(row.value)),
)
</script>

<style scoped>
.customer-qc-result-detail-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
}

.customer-qc-result-detail-card__primary {
  display: grid;
  gap: 6px;
}

.customer-qc-result-detail-card__primary strong {
  color: #1d1d1f;
  font-size: 16px;
  line-height: 1.6;
}

.customer-qc-result-detail-card__label,
.customer-qc-result-detail-card dt {
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
}

.customer-qc-result-detail-card__facts {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 10px 16px;
  margin: 0;
}

.customer-qc-result-detail-card dd {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  overflow-wrap: anywhere;
}

@media (max-width: 640px) {
  .customer-qc-result-detail-card__facts {
    grid-template-columns: 1fr;
    gap: 3px;
  }

  .customer-qc-result-detail-card dd {
    margin-bottom: 8px;
  }
}
</style>
