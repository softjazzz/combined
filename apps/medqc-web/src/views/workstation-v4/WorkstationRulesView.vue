<template>
  <div class="rules-shell">
    <div class="rules-page">
      <section class="rules-page-header">
        <div class="rules-title-block">
          <h1>质控规则管理</h1>
        </div>
        <div class="rules-tabs">
          <div class="rules-tab-group">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="rules-tab"
              :class="{ active: activeTab === tab.key }"
              @click="selectTab(tab.key)"
            >
              <span>{{ tab.label }}</span>
              <strong>{{ tab.count }}</strong>
            </button>
          </div>
        </div>
      </section>

      <div class="rules-panel-shell">
        <div class="rules-panel-inner">
          <CodingRulesTab v-if="activeTab === 'coding'" />
          <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
          <WorkstationSemanticRulesView v-else-if="activeTab === 'semantic'" />
          <SurgeryProcedureCatalogView v-else-if="activeTab === 'surgery-catalog'" />
          <SettlementRulesTab v-else />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'
import WorkstationSemanticRulesView from '@/views/workstation-v4/WorkstationSemanticRulesView.vue'
import SurgeryProcedureCatalogView from '@/views/workstation-v4/components/SurgeryProcedureCatalogView.vue'

const route = useRoute()
const router = useRouter()

type TabKey = 'coding' | 'frontpage' | 'settlement' | 'semantic' | 'surgery-catalog'
const SUPPORTED_TABS: TabKey[] = [
  'coding',
  'frontpage',
  'settlement',
  'semantic',
  'surgery-catalog',
]

const activeTab = ref<TabKey>('coding')

const tabs: Array<{ key: TabKey; label: string; count: string }> = [
  { key: 'coding', label: '编码规则', count: 'ICD' },
  { key: 'frontpage', label: '首页规则', count: '首页' },
  { key: 'settlement', label: '结算规则', count: '清单' },
  { key: 'semantic', label: '语义规则', count: '语义' },
  { key: 'surgery-catalog', label: '手术分级', count: '配置' },
]

const resolveTab = (tab: string | undefined): TabKey => {
  if (tab && SUPPORTED_TABS.includes(tab as TabKey)) {
    return tab as TabKey
  }
  return 'coding'
}

const selectTab = (tab: TabKey) => {
  activeTab.value = tab
  void router.replace({ query: { ...route.query, tab } })
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
.rules-shell {
  --rules-font-sans:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', sans-serif;
  --rules-font-display:
    'SF Pro Display', 'San Francisco', 'Source Han Sans SC', Inter, 'PingFang SC',
    'Microsoft YaHei UI', sans-serif;

  min-height: 100%;
  background: #f5f5f7;
  color: #1d1d1f;
  font-family: var(--rules-font-sans);
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  padding: 22px 24px 34px;
}

.rules-shell :deep(.ant-btn),
.rules-shell :deep(.ant-input),
.rules-shell :deep(.ant-input-affix-wrapper),
.rules-shell :deep(.ant-select),
.rules-shell :deep(.ant-select-dropdown),
.rules-shell :deep(.ant-select-item),
.rules-shell :deep(.ant-tag),
.rules-shell :deep(.ant-table),
.rules-shell :deep(.ant-modal),
.rules-shell :deep(.ant-dropdown),
.rules-shell :deep(.ant-pagination) {
  font-family: var(--rules-font-sans);
}

.rules-page {
  margin: 0 auto;
  max-width: 1440px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.rules-shell :deep(.ant-card),
.rules-shell :deep(.rule-card) {
  border-radius: 16px;
  border-color: rgba(0, 0, 0, 0.08);
  box-shadow: none;
}

.rules-page-header {
  align-items: flex-start;
  display: flex;
  gap: 20px;
  justify-content: space-between;
}

.rules-title-block {
  min-width: 280px;
}

.rules-title-block h1 {
  color: #1d1d1f;
  font-family: var(--rules-font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1.1;
  margin: 0;
}

.rules-tabs {
  align-items: center;
  display: flex;
  justify-content: flex-end;
  max-width: 780px;
}

.rules-tab-group {
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  display: flex;
  gap: 4px;
  padding: 4px;
}

.rules-panel-shell {
  min-width: 0;
}

.rules-panel-inner {
  min-width: 0;
}

.rules-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  border: none;
  border-radius: 12px;
  background: transparent;
  box-shadow: none;
  cursor: pointer;
  padding: 0 14px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0;
  transition: all 0.18s ease;
}

.rules-tab:hover {
  color: #1d1d1f;
  background: rgba(0, 0, 0, 0.05);
}

.rules-tab.active {
  background: #0066cc;
  box-shadow: 0 2px 10px rgba(0, 102, 204, 0.28);
  color: #ffffff;
}

.rules-tab strong {
  align-items: center;
  background: rgba(0, 102, 204, 0.1);
  border-radius: 999px;
  display: inline-flex;
  height: 18px;
  justify-content: center;
  min-width: 26px;
  padding: 0 6px;
  color: inherit;
  font-size: 10px;
  font-weight: 600;
}

.rules-tab.active strong {
  background: rgba(255, 255, 255, 0.24);
}

@media (max-width: 980px) {
  .rules-shell {
    padding: 14px;
  }

  .rules-page-header {
    flex-direction: column;
  }

  .rules-tabs {
    justify-content: flex-start;
    max-width: none;
  }

  .rules-tab-group {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
}
</style>

<style>
@import './styles/workstation-v4-view.css';
</style>
