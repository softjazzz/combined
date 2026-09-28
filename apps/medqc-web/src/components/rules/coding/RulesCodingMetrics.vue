<template>
  <section class="grid grid-cols-2 gap-3 xl:grid-cols-4">
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'total' })"
    >
      <div class="rules-metric__label">
        {{ totalLabel }}
      </div>
      <div class="rules-metric__value">
        {{ totalRules }}
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'enabled' })"
    >
      <div class="rules-metric__label">
        {{ enabledLabel }}
      </div>
      <div class="rules-metric__value rules-metric__value--brand">
        {{ enabledRules }}
      </div>
      <div class="rules-metric__sub">
        {{ enabledSubtext || `草稿 ${draftRules} · 停用 ${disabledRules}` }}
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'hit7d' })"
    >
      <div class="rules-metric__label">
        {{ hitLabel }}
      </div>
      <div class="rules-metric__value">
        {{ hit7d }}
      </div>
      <div class="rules-metric__sub">
        {{ hitSubtext || `命中率 ${hitRate7d.toFixed(1)}%` }}
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'risk' })"
    >
      <div class="rules-metric__label">
        {{ riskLabel }}
      </div>
      <div class="rules-metric__value rules-metric__value--danger">
        {{ highRiskRules }}
      </div>
      <div class="rules-metric__sub">
        {{ riskSubtext || `冲突 ${conflictRules} · 误报高 ${falsePositiveHighRules}` }}
      </div>
    </a-card>
  </section>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    totalRules: number
    enabledRules: number
    draftRules: number
    disabledRules: number
    hit7d: number
    hitRate7d: number
    highRiskRules: number
    conflictRules: number
    falsePositiveHighRules: number
    totalLabel?: string
    enabledLabel?: string
    hitLabel?: string
    riskLabel?: string
    enabledSubtext?: string
    hitSubtext?: string
    riskSubtext?: string
  }>(),
  {
    totalLabel: '总规则数',
    enabledLabel: '启用中',
    hitLabel: '近7天命中',
    riskLabel: '高风险规则',
    enabledSubtext: '',
    hitSubtext: '',
    riskSubtext: '',
  },
)

const emit = defineEmits<{
  'click-metric': [payload: { key: 'total' | 'enabled' | 'hit7d' | 'risk' }]
}>()
</script>

<style scoped>
.rules-metric__label {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.rules-metric__value {
  margin-top: 4px;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-display);
  font-size: 28px;
  font-weight: 600;
  line-height: 34px;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.rules-metric__value--brand {
  color: var(--mq-brand-600);
}

.rules-metric__value--danger {
  color: var(--mq-danger-text, #c93a3a);
}

.rules-metric__sub {
  margin-top: 2px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}
</style>
