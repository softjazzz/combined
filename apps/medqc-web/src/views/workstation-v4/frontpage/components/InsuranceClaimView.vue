<template>
  <div
    v-if="insuranceClaim"
    class="bg-white/90 rounded-2xl p-6 border border-black/[0.08] shadow-[0_1px_4px_rgba(0,0,0,0.045),0_2px_8px_rgba(0,0,0,0.035)]"
  >
    <div class="text-center mb-6">
      <p class="text-xs text-[rgba(29,29,31,0.56)] mb-1">
        总费用
      </p>
      <div class="text-[24px] font-semibold text-[#1d1d1f] leading-8">
        ¥ {{ insuranceClaim.total_cost.toFixed(2) }}
      </div>
    </div>
    <div class="space-y-3">
      <div class="flex justify-between text-sm py-2 border-b border-black/[0.08]">
        <span class="text-[rgba(29,29,31,0.56)]">基金支付</span>
        <span class="font-medium text-green-600">¥ {{ insuranceClaim.fund_pay.toFixed(2) }}</span>
      </div>
      <div class="flex justify-between text-sm py-2 border-b border-black/[0.08]">
        <span class="text-[rgba(29,29,31,0.56)]">个人自付</span>
        <span class="font-medium text-orange-600">¥ {{ insuranceClaim.patient_pay.toFixed(2) }}</span>
      </div>
      <div class="flex justify-between text-sm py-2">
        <span class="text-[rgba(29,29,31,0.56)]">医保类型</span>
        <span class="text-[rgba(29,29,31,0.78)]">{{ insuranceClaim.insurance_type }}</span>
      </div>
    </div>
  </div>
  <div
    v-else
    class="flex items-center justify-center h-48 text-[rgba(29,29,31,0.38)]"
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
