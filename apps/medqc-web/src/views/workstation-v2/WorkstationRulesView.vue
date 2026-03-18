<template>
  <div class="rules-shell min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-6 md:p-8 font-sans flex flex-col items-center">
    <div class="w-full max-w-7xl space-y-6">
      <div class="rounded-[28px] border border-white/80 bg-white/88 p-6 shadow-[0_16px_34px_rgba(15,23,42,0.06)]">
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div class="text-[11px] tracking-[0.14em] text-slate-400">规则中心</div>
            <h1 class="mt-1 text-[30px] font-black text-slate-900 tracking-[-0.03em]">质控规则管理</h1>
            <p class="text-[13px] text-slate-500 mt-2 font-medium">{{ activeTabDescription }}</p>
          </div>
          <div class="flex rounded-[20px] border border-slate-200/80 bg-slate-50/90 p-1.5 shrink-0 overflow-x-auto shadow-sm">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              @click="switchTab(tab.key)"
              :class="[
                activeTab === tab.key
                  ? 'bg-white text-sky-700 font-bold shadow-sm border border-sky-100'
                  : 'text-slate-500 hover:text-slate-800 font-medium transition-colors border border-transparent',
                'px-4 md:px-5 py-2 text-[13px] rounded-[14px] outline-none whitespace-nowrap'
              ]"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
      </div>

      <div class="rounded-[28px] border border-white/80 bg-white/78 p-4 shadow-[0_14px_30px_rgba(15,23,42,0.05)]">
        <CodingRulesTab v-if="activeTab === 'coding'" />
        <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
        <SettlementRulesTab v-else-if="activeTab === 'settlement'" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'

const route = useRoute()
const router = useRouter()

type TabKey = 'coding' | 'frontpage' | 'settlement'

const activeTab = ref<TabKey>('coding')

const tabs = [
  { key: 'coding' as const, label: '编码质控规则' },
  { key: 'frontpage' as const, label: '首页质控规则' },
  { key: 'settlement' as const, label: '医保结算清单质控规则' },
]

const descriptions: Record<TabKey, string> = {
  coding: '基于 ICD 编码规范的 18 类质控规则，覆盖 9.4 万+条编码数据。',
  frontpage: '基于病案首页数据的质控规则，校验首页字段的完整性和一致性。',
  settlement: '针对医保结算清单数据的质控规则，覆盖必填项校验及逻辑一致性。',
}

const activeTabDescription = computed(() => descriptions[activeTab.value])

const switchTab = (key: TabKey) => {
  activeTab.value = key
  router.replace({ query: { tab: key } })
}

// 从 URL query 读取初始 tab
onMounted(() => {
  const tab = route.query.tab as string
  if (tab && ['coding', 'frontpage', 'settlement'].includes(tab)) {
    activeTab.value = tab as TabKey
  }
})

// 监听 URL query 变化（侧边栏切换时触发）
watch(() => route.query.tab, (newTab) => {
  if (newTab && ['coding', 'frontpage', 'settlement'].includes(newTab as string)) {
    activeTab.value = newTab as TabKey
  }
})
</script>

<style scoped>
.rules-shell :deep(.ant-card),
.rules-shell :deep(.rule-card) {
  border-radius: 22px;
  border-color: rgba(226, 232, 240, 0.85);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}
</style>
