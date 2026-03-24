<template>
  <div class="rules-shell min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-6 md:p-8 font-sans flex flex-col items-center">
    <div class="w-full max-w-7xl space-y-6">
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

const titles: Record<TabKey, string> = {
  coding: '编码质控规则管理',
  frontpage: '首页质控规则管理',
  settlement: '结算清单质控规则管理',
}

const activeTabTitle = computed(() => titles[activeTab.value])

onMounted(() => {
  const tab = route.query.tab as string
  if (tab && ['coding', 'frontpage', 'settlement'].includes(tab)) {
    activeTab.value = tab as TabKey
  }
})

watch(
  () => route.query.tab,
  (newTab) => {
    if (newTab && ['coding', 'frontpage', 'settlement'].includes(newTab as string)) {
      activeTab.value = newTab as TabKey
    }
  },
)
</script>

<style scoped>
.rules-shell :deep(.ant-card),
.rules-shell :deep(.rule-card) {
  border-radius: 22px;
  border-color: rgba(226, 232, 240, 0.85);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}
</style>
