<template>
  <div class="flex h-full min-w-0 flex-1 overflow-hidden bg-[#f5f9fc] p-4">
    <main
      class="custom-scrollbar flex min-w-0 flex-1 flex-col overflow-y-auto rounded-[18px] border border-slate-200/80 bg-white px-4 pb-4 pt-4 shadow-[0_12px_28px_rgba(15,23,42,0.05)]"
    >
      <section class="wv4-analysis-overview mb-4">
        <div class="wv4-analysis-overview__header">
          <div>
            <div class="wv4-analysis-overview__eyebrow">
              Workstation / Rules
            </div>
            <h2 class="wv4-analysis-overview__title">
              {{ rulesSubTabTitle }}
            </h2>
            <p class="wv4-analysis-overview__subtitle">
              {{ rulesSubTabDesc }}
            </p>
          </div>
          <div class="wv4-analysis-overview__actions">
            <button
              class="flex items-center gap-1.5 rounded-[14px] border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-500 transition-all hover:border-blue-200 hover:text-blue-700 hover:shadow-[0_8px_18px_rgba(37,99,235,0.08)]"
              @click="emit('back')"
            >
              <LeftOutlined />
              返回病历列表
            </button>
          </div>
        </div>
      </section>
      <div class="cw-rules-content flex-1 min-w-0">
        <AsyncCodingRulesTab v-if="rulesSubTab === 'coding'" />
        <AsyncFrontpageRulesOverview v-else-if="rulesSubTab === 'frontpage'" />
        <AsyncSettlementRulesOverview v-else-if="rulesSubTab === 'settlement'" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { LeftOutlined } from '@ant-design/icons-vue'
import type { DeptInfo } from '../types'

const props = defineProps<{
  departments: DeptInfo[]
  rulesSubTab: 'coding' | 'frontpage' | 'settlement'
  rulesSubTabTitle: string
}>()

const emit = defineEmits<{
  'select-department': [dept: string]
  back: []
}>()

const AsyncCodingRulesTab = defineAsyncComponent(
  () => import('@/components/rules/CodingRulesTab.vue'),
)
const AsyncFrontpageRulesOverview = defineAsyncComponent(
  () => import('./FrontpageRulesOverview.vue'),
)
const AsyncSettlementRulesOverview = defineAsyncComponent(
  () => import('./SettlementRulesOverview.vue'),
)

const rulesSubTabDesc = computed(() => {
  const map = {
    coding: '维护编码质控规则的审核逻辑、扣分策略与适用范围。',
    frontpage: '聚焦病案首页字段完整性与一致性规则，保障首页生成质量。',
    settlement: '统一结算清单质控规则，提前识别费用与医保字段异常。',
  }
  return map[props.rulesSubTab]
})
</script>
