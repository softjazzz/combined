<template>
  <div
    class="rules-shell min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] px-4 pb-6 pt-4 font-sans xl:px-5"
  >
    <div class="mx-auto w-full max-w-[1440px]">
      <section class="wv4-analysis-overview mb-4">
        <div class="wv4-analysis-overview__header">
          <div>
            <div class="wv4-analysis-overview__eyebrow">
              Workstation / Rules
            </div>
            <h2 class="wv4-analysis-overview__title">
              规则工作台
            </h2>
            <p class="wv4-analysis-overview__subtitle">
              统一维护编码、首页与结算规则，保持规则库质量和执行一致性。
            </p>
          </div>
        </div>
      </section>
      <div
        class="rounded-3xl border border-slate-200/85 bg-white p-4 shadow-[0_14px_34px_rgba(148,163,184,0.12)]"
      >
        <CodingRulesTab v-if="activeTab === 'coding'" />
        <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
        <SettlementRulesTab v-else />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'

const route = useRoute()

type TabKey = 'coding' | 'frontpage' | 'settlement'
const SUPPORTED_TABS: TabKey[] = ['coding', 'frontpage', 'settlement']

const activeTab = ref<TabKey>('coding')

const resolveTab = (tab: string | undefined): TabKey => {
  if (tab && SUPPORTED_TABS.includes(tab as TabKey)) {
    return tab as TabKey
  }
  return 'coding'
}

onMounted(() => {
  activeTab.value = resolveTab(route.query.tab as string | undefined)
})

watch(
  () => route.query.tab,
  (newTab) => {
    activeTab.value = resolveTab(newTab as string | undefined)
  },
)
</script>

<style scoped>
.rules-shell :deep(.ant-card),
.rules-shell :deep(.rule-card) {
  border-radius: 24px;
  border-color: rgba(226, 232, 240, 0.85);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
}
</style>

<style src="./styles/workstation-v4-view.css"></style>
