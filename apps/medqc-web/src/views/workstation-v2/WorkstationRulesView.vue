<template>
  <div class="min-h-screen bg-slate-50 dark:bg-slate-900">
    <!-- 顶部标题区 -->
    <header class="px-8 pt-6 pb-4 bg-white dark:bg-slate-900 border-b border-slate-100 dark:border-slate-800">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-slate-800 dark:text-white tracking-tight">质控规则管理</h2>
          <p class="text-sm text-slate-500 mt-1">{{ activeTabDescription }}</p>
        </div>
      </div>
      <!-- 三个 Tab -->
      <nav class="mt-4 -mb-px flex space-x-6 border-b border-slate-200 dark:border-slate-700">
        <a
          v-for="tab in tabs"
          :key="tab.key"
          href="#"
          @click.prevent="switchTab(tab.key)"
          :class="[
            activeTab === tab.key
              ? 'border-blue-500 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300',
            'whitespace-nowrap pb-3 border-b-2 font-semibold text-sm flex items-center gap-1.5 transition-colors'
          ]"
        >
          <component :is="tab.icon" />
          {{ tab.label }}
        </a>
      </nav>
    </header>

    <!-- Tab 内容 -->
    <div class="flex-1 p-6">
      <CodingRulesTab v-if="activeTab === 'coding'" />
      <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
      <SettlementRulesTab v-else-if="activeTab === 'settlement'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MedicineBoxOutlined,
  FileSearchOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'

const route = useRoute()
const router = useRouter()

type TabKey = 'coding' | 'frontpage' | 'settlement'

const activeTab = ref<TabKey>('coding')

const tabs = [
  { key: 'coding' as const, label: '编码质控规则', icon: MedicineBoxOutlined },
  { key: 'frontpage' as const, label: '首页质控规则', icon: FileSearchOutlined },
  { key: 'settlement' as const, label: '医保结算清单质控规则', icon: SafetyCertificateOutlined },
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
