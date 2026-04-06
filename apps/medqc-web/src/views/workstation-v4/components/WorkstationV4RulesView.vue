<template>
  <div
    class="flex h-full min-w-0 flex-1 overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-4"
  >
    <aside
      class="w-56 flex-shrink-0 rounded-l-3xl border border-slate-200/80 border-r-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.95))] shadow-[8px_0_22px_rgba(15,23,42,0.05)]"
    >
      <div class="border-b border-slate-200/75 px-5 py-4">
        <div class="flex items-center gap-3">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-[16px] border border-blue-100 bg-blue-50/90 shadow-[0_8px_16px_rgba(37,99,235,0.08)]"
          >
            <MedicineBoxOutlined class="text-blue-600 text-lg" />
          </div>
          <div>
            <div class="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
              Rules Console
            </div>
            <span class="font-black text-slate-900 text-[16px] tracking-tight">病案工作台</span>
          </div>
        </div>
      </div>
      <div class="custom-scrollbar max-h-[calc(100vh-210px)] overflow-y-auto py-2.5">
        <div
          v-for="dept in departments"
          :key="dept.name"
          class="mx-2 mb-1 flex cursor-pointer items-center justify-between rounded-xl px-3.5 py-3 text-sm text-slate-600 transition-all duration-200 hover:bg-white hover:shadow-sm"
          @click="emit('select-department', dept.name)"
        >
          <span class="truncate">{{ dept.name }}</span>
          <div class="flex items-center gap-1.5">
            <span
              v-if="dept.warningCount > 0"
              class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-500 px-1 text-[10px] font-bold text-white"
            >{{ dept.warningCount }}</span>
            <span
              class="min-w-[20px] h-[20px] flex items-center justify-center rounded-full bg-slate-200/80 px-1.5 text-[10px] font-bold text-slate-500"
            >{{ dept.total }}</span>
          </div>
        </div>
      </div>
      <div class="border-t border-slate-200/70 px-2.5 py-2.5">
        <div
          class="flex items-center gap-2.5 rounded-[16px] border border-blue-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.96),rgba(219,234,254,0.9))] px-3.5 py-3 text-sm font-bold text-blue-700 shadow-[0_10px_22px_rgba(37,99,235,0.08)]"
        >
          <SafetyCertificateOutlined class="text-base" />
          <div>
            <div>质控规则</div>
            <div class="text-[11px] font-medium text-blue-600/80">
              统一规则总览
            </div>
          </div>
        </div>
      </div>
    </aside>
    <main
      class="custom-scrollbar flex min-w-0 flex-1 flex-col overflow-y-auto rounded-r-3xl border border-slate-200/80 border-l-0 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(241,245,249,0.98))] px-4 pb-4 pt-4"
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
      <div
        class="cw-rules-content flex-1 rounded-3xl border border-slate-200/85 bg-white p-6 shadow-[0_14px_34px_rgba(148,163,184,0.12)]"
      >
        <AsyncCodingRulesTab v-if="rulesSubTab === 'coding'" />
        <AsyncFrontpageRulesOverview v-else-if="rulesSubTab === 'frontpage'" />
        <AsyncSettlementRulesOverview v-else-if="rulesSubTab === 'settlement'" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { LeftOutlined, MedicineBoxOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'
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
