<template>
  <section class="grid grid-cols-2 gap-3 xl:grid-cols-4">
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'total' })"
    >
      <div class="text-[12px] text-slate-500">
        总规则数
      </div>
      <div class="mt-1 text-[24px] font-bold text-slate-900">
        {{ totalRules }}
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'enabled' })"
    >
      <div class="text-[12px] text-slate-500">
        启用中
      </div>
      <div class="mt-1 text-[24px] font-bold text-blue-700">
        {{ enabledRules }}
      </div>
      <div class="text-[11px] text-slate-500">
        草稿 {{ draftRules }} · 停用 {{ disabledRules }}
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'hit7d' })"
    >
      <div class="text-[12px] text-slate-500">
        近7天命中
      </div>
      <div class="mt-1 text-[24px] font-bold text-slate-900">
        {{ hit7d }}
      </div>
      <div class="text-[11px] text-slate-500">
        命中率 {{ hitRate7d.toFixed(1) }}%
      </div>
    </a-card>
    <a-card
      size="small"
      class="cursor-pointer"
      @click="emit('click-metric', { key: 'risk' })"
    >
      <div class="text-[12px] text-slate-500">
        高风险规则
      </div>
      <div class="mt-1 text-[24px] font-bold text-red-600">
        {{ highRiskRules }}
      </div>
      <div class="text-[11px] text-slate-500">
        冲突 {{ conflictRules }} · 误报高 {{ falsePositiveHighRules }}
      </div>
    </a-card>
  </section>
</template>

<script setup lang="ts">
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
}>()

const emit = defineEmits<{
  'click-metric': [payload: { key: 'total' | 'enabled' | 'hit7d' | 'risk' }]
}>()
</script>
