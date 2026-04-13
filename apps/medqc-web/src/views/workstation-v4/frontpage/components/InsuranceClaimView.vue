<template>
  <div
    v-if="insuranceClaim"
    class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-6 border border-slate-100 dark:border-slate-700"
  >
    <div class="text-center mb-6">
      <p class="text-xs text-slate-500 uppercase tracking-wide mb-1">
        总费用
      </p>
      <div class="text-3xl font-bold text-slate-800 dark:text-white">
        ¥ {{ insuranceClaim.total_cost.toFixed(2) }}
      </div>
    </div>
    <div class="space-y-3">
      <div
        class="flex justify-between text-sm py-2 border-b border-slate-200 dark:border-slate-600"
      >
        <span class="text-slate-500 dark:text-slate-400">基金支付</span>
        <span class="font-medium text-green-600">¥ {{ insuranceClaim.fund_pay.toFixed(2) }}</span>
      </div>
      <div
        class="flex justify-between text-sm py-2 border-b border-slate-200 dark:border-slate-600"
      >
        <span class="text-slate-500 dark:text-slate-400">个人自付</span>
        <span class="font-medium text-orange-600">¥ {{ insuranceClaim.patient_pay.toFixed(2) }}</span>
      </div>
      <div class="flex justify-between text-sm py-2">
        <span class="text-slate-500 dark:text-slate-400">医保类型</span>
        <span class="text-slate-700 dark:text-slate-300">{{ insuranceClaim.insurance_type }}</span>
      </div>
    </div>
  </div>
  <div
    v-else
    class="flex items-center justify-center h-48 text-slate-400"
  >
    暂无医保数据
  </div>
</template>

<script setup lang="ts">
export interface InsuranceClaim {
  settlement_id?: string
  insurance_type: string
  total_cost: number
  fund_pay: number
  patient_pay: number
}

defineProps<{
  insuranceClaim: InsuranceClaim | null
}>()
</script>
