<template>
  <aside
    class="w-56 flex-shrink-0 border-r border-slate-200/70 flex flex-col bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.95))] shadow-[8px_0_20px_rgba(15,23,42,0.03)]"
  >
    <div class="border-b border-slate-200/75 px-5 py-4 flex-shrink-0">
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
    <div class="flex-1 overflow-y-auto py-2.5 custom-scrollbar">
      <div
        v-for="dept in departments"
        :key="dept.name"
        :class="[
          'mx-2 mb-1 flex items-center justify-between px-3.5 py-3 rounded-xl cursor-pointer text-sm transition-all duration-200',
          'text-slate-600 hover:bg-white hover:shadow-sm dark:text-slate-400 dark:hover:bg-slate-800',
        ]"
        @click="emit('select-department', dept.name)"
      >
        <span class="truncate">{{ dept.name }}</span>
        <div class="flex items-center gap-1.5">
          <span
            v-if="dept.warningCount > 0"
            class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-500 text-white text-[10px] font-bold px-1"
            >{{ dept.warningCount }}</span
          >
          <span
            class="min-w-[20px] h-[20px] flex items-center justify-center rounded-full text-[10px] font-bold px-1.5 bg-slate-200/80 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
            >{{ dept.total }}</span
          >
        </div>
      </div>
    </div>
    <div class="flex-shrink-0 border-t border-slate-200/70 px-2.5 py-2.5">
      <div
        class="flex items-center gap-2.5 rounded-[16px] border border-blue-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.96),rgba(219,234,254,0.9))] px-3.5 py-3 text-sm font-bold text-blue-700 shadow-[0_10px_22px_rgba(37,99,235,0.08)]"
      >
        <SafetyCertificateOutlined class="text-base" />
        <div>
          <div>质控规则</div>
          <div class="text-[11px] font-medium text-blue-600/80">统一规则总览</div>
        </div>
      </div>
    </div>
  </aside>
  <main
    class="flex-1 flex flex-col min-w-0 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(241,245,249,0.98))] overflow-y-auto"
  >
    <header
      class="flex-shrink-0 border-b border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,250,252,0.96))] px-6 py-4"
    >
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <h2 class="text-[28px] font-black leading-none tracking-[-0.02em] text-slate-900">
            {{ rulesSubTabTitle }}
          </h2>
        </div>
        <div class="flex flex-col items-end gap-3">
          <button
            class="flex items-center gap-1.5 rounded-[14px] border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-500 transition-all hover:border-blue-200 hover:text-blue-700 hover:shadow-[0_8px_18px_rgba(37,99,235,0.08)]"
            @click="emit('back')"
          >
            <LeftOutlined />
            返回病历列表
          </button>
        </div>
      </div>
    </header>
    <div class="flex-1 p-6">
      <AsyncCodingRulesTab v-if="rulesSubTab === 'coding'" />
      <AsyncFrontpageRulesOverview v-else-if="rulesSubTab === 'frontpage'" />
      <AsyncSettlementRulesOverview v-else-if="rulesSubTab === 'settlement'" />
    </div>
  </main>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
import { LeftOutlined, MedicineBoxOutlined, SafetyCertificateOutlined } from '@ant-design/icons-vue'
import type { DeptInfo } from '../types'

defineProps<{
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
</script>
