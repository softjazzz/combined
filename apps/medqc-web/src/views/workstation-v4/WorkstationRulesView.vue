<template>
  <div class="rules-shell">
    <div class="rules-page mq-page">
      <section class="rules-page-header mq-page-head">
        <div class="mq-page-head__copy">
          <span class="mq-page-eyebrow">规则 · 规则执行工作台</span>
          <h1 class="mq-page-title">
            质控规则
          </h1>
        </div>
        <div
          class="rules-tab-group mq-segmented"
          role="tablist"
          aria-label="规则分类"
        >
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            role="tab"
            class="rules-tab mq-segmented__item"
            :class="{ active: activeTab === tab.key, 'is-active': activeTab === tab.key }"
            :aria-selected="activeTab === tab.key"
            @click="selectTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </div>
      </section>

      <div class="rules-panel-shell">
        <CodingRulesTab v-if="activeTab === 'coding'" />
        <FrontpageRulesTab v-else-if="activeTab === 'frontpage'" />
        <WorkstationSemanticRulesView v-else-if="activeTab === 'semantic'" />
        <SettlementRulesTab v-else-if="activeTab === 'settlement'" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesTab from '@/components/rules/FrontpageRulesTab.vue'
import SettlementRulesTab from '@/components/rules/SettlementRulesTab.vue'
import WorkstationSemanticRulesView from '@/views/workstation-v4/WorkstationSemanticRulesView.vue'

const route = useRoute()
const router = useRouter()

type TabKey = 'coding' | 'frontpage' | 'settlement' | 'semantic'
const SUPPORTED_TABS: TabKey[] = ['coding', 'frontpage', 'settlement', 'semantic']

const activeTab = ref<TabKey>()

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'coding', label: '编码规则' },
  { key: 'frontpage', label: '首页规则' },
  { key: 'settlement', label: '结算规则' },
  { key: 'semantic', label: '语义规则' },
]

const resolveTab = (tab: string | undefined): TabKey => {
  if (tab && SUPPORTED_TABS.includes(tab as TabKey)) {
    return tab as TabKey
  }
  return 'semantic'
}

// 导航合并为单一入口后，语义规则 Tab 沿用原侧栏入口的默认规则集
const DEFAULT_SEMANTIC_RULE_SET_KEY = 'luxian_0609_qc_v1'

const selectTab = (tab: TabKey) => {
  activeTab.value = tab
  const query: Record<string, unknown> = { ...route.query, tab }
  if (tab === 'semantic' && !route.query.ruleSetKey) {
    query.ruleSetKey = DEFAULT_SEMANTIC_RULE_SET_KEY
  }
  void router.replace({ query: query as typeof route.query })
}

// 默认入口先补齐0609查询参数，再挂载规则列表，避免先请求其他规则集。
watch(
  () => [route.query.tab, route.query.ruleSetKey],
  () => {
    const tab = resolveTab(route.query.tab as string | undefined)
    if (tab === 'semantic' && route.query.ruleSetKey == null) {
      activeTab.value = undefined
      void router.replace({
        query: { ...route.query, tab, ruleSetKey: DEFAULT_SEMANTIC_RULE_SET_KEY },
      })
      return
    }
    activeTab.value = tab
  },
  { immediate: true },
)
</script>

<style scoped>
/* v7.1：页头、分段切换来自 mq-components.css；这里只把三个传统规则 Tab 的白卡换成玻璃卡 */
.rules-shell {
  min-height: 100%;
  background: transparent;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

.rules-panel-shell {
  min-width: 0;
}

.rules-panel-shell :deep(.rounded-2xl.bg-white),
.rules-panel-shell :deep(.ant-card) {
  border: 1px solid var(--mq-glass-border) !important;
  border-radius: var(--mq-radius-card) !important;
  background: var(--mq-glass-bg) !important;
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow) !important;
}

.rules-panel-shell :deep(.ant-table),
.rules-panel-shell :deep(.ant-table-container),
.rules-panel-shell :deep(.ant-table-cell-fix-left),
.rules-panel-shell :deep(.ant-table-cell-fix-right) {
  background: transparent;
}

.rules-panel-shell :deep(.ant-table-thead > tr > th) {
  background: rgba(118, 128, 160, 0.06);
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 600;
}

.rules-panel-shell :deep(.ant-table-thead > tr > th::before) {
  display: none;
}

.rules-panel-shell :deep(.ant-table-tbody > tr > td) {
  border-bottom: 0.5px solid var(--mq-border);
  background: transparent;
}

.rules-panel-shell :deep(.ant-table-tbody > tr:hover > td) {
  background: rgba(10, 108, 255, 0.04);
}

.rules-panel-shell :deep(.ant-input-affix-wrapper),
.rules-panel-shell :deep(.ant-input),
.rules-panel-shell :deep(.ant-select:not(.ant-select-customize-input) .ant-select-selector) {
  border-color: rgba(60, 60, 80, 0.1);
  border-radius: var(--mq-radius-control);
  background: rgba(255, 255, 255, 0.85);
}

@media (max-width: 980px) {
  .rules-page-header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<style>
@import './styles/workstation-v4-view.css';
</style>
