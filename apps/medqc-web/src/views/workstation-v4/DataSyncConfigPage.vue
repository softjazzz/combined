<template>
  <section class="mq-page system-config-page" aria-labelledby="system-config-title">
    <!-- 页头：眉标 + 大标题；右侧分段切换替代原 Tabs，页签可见性规则不变 -->
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">数据与配置 · 系统配置</span>
        <h1 id="system-config-title" class="mq-page-title">系统配置</h1>
      </div>
      <div
        class="mq-segmented"
        role="tablist"
        aria-label="系统配置分类"
        data-testid="system-config-tabs"
        :data-active-key="activeTab"
      >
        <button
          v-for="(tab, index) in configTabs"
          :key="tab.key"
          :id="`system-config-tab-${tab.key}`"
          :ref="(el) => setTabButtonRef(tab.key, el)"
          type="button"
          role="tab"
          class="mq-segmented__item"
          :class="{ 'is-active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          :aria-controls="`system-config-panel-${tab.key}`"
          :tabindex="activeTab === tab.key ? 0 : -1"
          :data-testid="tab.testId"
          @click="handleSelectTab(tab.key)"
          @keydown="handleTabKeydown($event, index)"
        >
          {{ tab.label }}
        </button>
      </div>
    </header>

    <div
      v-if="activeTab === 'dailyQc' && canManageLlmConfig"
      id="system-config-panel-dailyQc"
      role="tabpanel"
      aria-labelledby="system-config-tab-dailyQc"
      class="system-config-tabpanel"
    >
      <DailyQcSchedulePanel />
    </div>

    <div
      v-else-if="activeTab === 'dataSync'"
      id="system-config-panel-dataSync"
      role="tabpanel"
      aria-labelledby="system-config-tab-dataSync"
      class="system-config-tabpanel"
    >
      <ClinicalSourceSettingsPanel v-if="canManageLlmConfig" />
      <DataPipelineSettingsPanel v-if="canManageLlmConfig" />
    </div>

    <section
      v-else-if="activeTab === 'frontpageExtraction' && canManageFrontpageConfig"
      id="system-config-panel-frontpageExtraction"
      role="tabpanel"
      aria-labelledby="system-config-tab-frontpageExtraction"
      class="mq-card system-config-panel"
    >
      <FrontpageExtractionSettingsPanel />
    </section>

    <section
      v-else-if="activeTab === 'qcRuntime' && canViewLlmObservability"
      id="system-config-panel-qcRuntime"
      role="tabpanel"
      aria-labelledby="system-config-tab-qcRuntime"
      class="mq-card system-config-panel"
    >
      <QcRuntimeSettingsPanel />
    </section>

    <section
      v-else-if="activeTab === 'llmObservability' && canViewLlmObservability"
      id="system-config-panel-llmObservability"
      role="tabpanel"
      aria-labelledby="system-config-tab-llmObservability"
      class="mq-card system-config-panel"
    >
      <LlmPerformanceObservabilityPanel />
    </section>

    <section
      v-else-if="activeTab === 'accounts' && canManageAccounts"
      id="system-config-panel-accounts"
      role="tabpanel"
      aria-labelledby="system-config-tab-accounts"
      class="mq-card system-config-panel account-config-panel"
    >
      <AccountManagementPanel />
    </section>

    <section
      v-else-if="activeTab === 'llmConfig' && canManageLlmConfig"
      id="system-config-panel-llmConfig"
      role="tabpanel"
      aria-labelledby="system-config-tab-llmConfig"
      class="model-settings-panel"
    >
      <LLMApiConfig ref="llmConfigRef" />
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as vueRouter from 'vue-router'
import FrontpageExtractionSettingsPanel from './components/system-config/FrontpageExtractionSettingsPanel.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import DailyQcSchedulePanel from './components/system-config/DailyQcSchedulePanel.vue'
import LlmPerformanceObservabilityPanel from './components/system-config/LlmPerformanceObservabilityPanel.vue'
import AccountManagementPanel from './components/system-config/AccountManagementPanel.vue'
import QcRuntimeSettingsPanel from './components/system-config/QcRuntimeSettingsPanel.vue'
import ClinicalSourceSettingsPanel from './components/system-config/ClinicalSourceSettingsPanel.vue'
import DataPipelineSettingsPanel from './components/system-config/DataPipelineSettingsPanel.vue'
import { useAuthStore } from '@/stores/auth'

const llmConfigRef = ref<{
  hasUnsavedChanges?: boolean
  confirmDiscardChanges?: () => Promise<boolean>
} | null>(null)

function tryUseRoute() {
  try {
    return typeof vueRouter.useRoute === 'function' ? vueRouter.useRoute() : undefined
  } catch {
    return undefined
  }
}

function tryUseRouter() {
  try {
    return typeof vueRouter.useRouter === 'function' ? vueRouter.useRouter() : undefined
  } catch {
    return undefined
  }
}

const route = tryUseRoute()
const router = tryUseRouter()
const authStore = useAuthStore()

let disposed = false
let tabTransitionSeq = 0

const canManageFrontpageConfig = computed(() =>
  authStore.userRoles.some((role) =>
    ['admin', 'qc_manager', 'sync_admin', 'super_admin'].includes(role),
  ),
)
const canManageLlmConfig = computed(() =>
  authStore.userRoles.some((role) => ['admin', 'sync_admin', 'super_admin'].includes(role)),
)
const canManageAccounts = computed(() =>
  authStore.userRoles.some((role) => role === 'admin' || role === 'super_admin'),
)

const isObservabilityOperationalAdmin = computed(() =>
  authStore.userRoles.some((role) => role === 'sync_admin' || role === 'super_admin'),
)
const canViewLlmObservability = computed(
  () =>
    canManageLlmConfig.value &&
    (authStore.user?.is_demo_account !== true || isObservabilityOperationalAdmin.value),
)

// 页签：显示条件与原 a-tab-pane 的 v-if 一致
const configTabs = computed(() =>
  [
    {
      key: 'dataSync',
      label: '数据同步',
      testId: undefined,
      visible: canManageLlmConfig.value,
    },
    { key: 'qcRuntime', label: '质控运行', testId: 'qc-runtime-tab', visible: canViewLlmObservability.value },
    { key: 'dailyQc', label: '定时质控', testId: 'daily-qc-config-tab', visible: canManageLlmConfig.value },
    {
      key: 'frontpageExtraction',
      label: '首页抽取设置',
      testId: 'frontpage-config-tab',
      visible: canManageFrontpageConfig.value,
    },
    {
      key: 'llmObservability',
      label: '模型性能',
      testId: 'llm-observability-tab',
      visible: canViewLlmObservability.value,
    },
    {
      key: 'llmConfig',
      label: '模型配置',
      testId: 'llm-config-tab',
      visible: canManageLlmConfig.value,
    },
    {
      key: 'accounts',
      label: '账号管理',
      testId: 'account-management-tab',
      visible: canManageAccounts.value,
    },
  ].filter((tab) => tab.visible),
)

function resolveAllowedTab(requested: unknown): string {
  const tabKey = typeof requested === 'string' ? requested : ''
  if (tabKey && configTabs.value.some((tab) => tab.key === tabKey)) {
    return tabKey
  }
  return configTabs.value[0]?.key || ''
}

const activeTab = ref(resolveAllowedTab(route?.query?.tab))

function syncTabToRoute(tab: string) {
  if (!tab || !router || typeof router.replace !== 'function') return
  const currentQuery = route?.query || {}
  const currentTab = typeof currentQuery.tab === 'string' ? currentQuery.tab : ''
  if (currentTab === tab) return
  const nextQuery: Record<string, any> = { ...currentQuery, tab }
  if (tab !== 'accounts') {
    delete nextQuery.section
    delete nextQuery.registration_id
  }
  void Promise.resolve(router.replace({ query: nextQuery })).catch(() => {})
}

const tabButtonRefs = new Map<string, HTMLButtonElement>()

function setTabButtonRef(key: string, el: unknown) {
  if (el instanceof HTMLButtonElement) {
    tabButtonRefs.set(key, el)
  } else {
    tabButtonRefs.delete(key)
  }
}

function needsDiscardConfirm(): boolean {
  return Boolean(
    activeTab.value === 'llmConfig' &&
      llmConfigRef.value?.hasUnsavedChanges &&
      typeof llmConfigRef.value.confirmDiscardChanges === 'function',
  )
}

async function handleSelectTab(nextTab: string) {
  if (!nextTab || nextTab === activeTab.value) return
  if (!configTabs.value.some((tab) => tab.key === nextTab)) return
  if (needsDiscardConfirm()) {
    const seq = ++tabTransitionSeq
    const canLeave = Boolean(await llmConfigRef.value?.confirmDiscardChanges?.())
    if (!canLeave || disposed || seq !== tabTransitionSeq) return
  } else {
    tabTransitionSeq += 1
  }
  activeTab.value = nextTab
  syncTabToRoute(nextTab)
}

async function handleTabKeydown(event: KeyboardEvent, currentIndex: number) {
  const tabs = configTabs.value
  if (tabs.length <= 1) return
  let nextIndex = -1
  if (event.key === 'ArrowRight') {
    nextIndex = (currentIndex + 1) % tabs.length
  } else if (event.key === 'ArrowLeft') {
    nextIndex = (currentIndex - 1 + tabs.length) % tabs.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = tabs.length - 1
  } else {
    return
  }
  event.preventDefault()
  const nextTab = tabs[nextIndex]
  if (!nextTab) return
  await handleSelectTab(nextTab.key)
  if (activeTab.value === nextTab.key) {
    tabButtonRefs.get(nextTab.key)?.focus()
  }
}

onMounted(() => {
  activeTab.value = resolveAllowedTab(route?.query?.tab)
})

watch(
  () => route?.query?.tab,
  async (requestedTab) => {
    const resolved = resolveAllowedTab(requestedTab)
    if (resolved === activeTab.value) return
    if (needsDiscardConfirm()) {
      const seq = ++tabTransitionSeq
      const canLeave = Boolean(await llmConfigRef.value?.confirmDiscardChanges?.())
      if (disposed || seq !== tabTransitionSeq) return
      if (!canLeave) {
        syncTabToRoute(activeTab.value)
        return
      }
      const latestResolved = resolveAllowedTab(route?.query?.tab)
      if (latestResolved !== activeTab.value) {
        activeTab.value = latestResolved
      }
      return
    }
    tabTransitionSeq += 1
    activeTab.value = resolved
  },
)

watch(
  configTabs,
  () => {
    if (!configTabs.value.some((tab) => tab.key === activeTab.value)) {
      activeTab.value = resolveAllowedTab(route?.query?.tab)
    }
  },
)

onUnmounted(() => {
  disposed = true
  tabTransitionSeq += 1
})
</script>

<style>
@import './styles/workstation-v4-view.css';
</style>
<style scoped src="./styles/system-config.css"></style>
