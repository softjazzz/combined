<template>
  <div class="sync-config-page workstation-shell min-h-screen flex flex-col">
    <div
      class="flex-1 p-5 lg:p-6 overflow-hidden flex flex-col min-h-0 container mx-auto max-w-[1680px] w-full"
    >
      <a-tabs v-model:active-key="activeTab" class="system-config-tabs flex-1 min-h-0">
        <a-tab-pane key="dataSync" tab="数据同步配置">
          <div class="system-config-tab-shell flex flex-col h-full min-h-0 gap-4">
            <section class="wv4-analysis-overview">
              <div class="wv4-analysis-overview__header">
                <div>
                  <h2 class="wv4-analysis-overview__title">系统配置</h2>
                  <p class="system-config-subtitle mt-1">
                    统一管理数据同步、首页抽取和模型连接配置，危险执行需先预检确认。
                  </p>
                </div>

                <div class="wv4-analysis-overview__actions">
                  <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '测试远端 PG + 本地 PG'">
                    <a-button
                      class="wv4-analysis-overview__action wv4-overview-btn wv4-overview-btn--ghost"
                      :loading="state.isTestingAll"
                      :disabled="isReadonly"
                      @click="handleTestAllConnections"
                    >
                      测试全连接
                    </a-button>
                  </a-tooltip>

                  <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '执行前预检，不落库'">
                    <a-button
                      class="wv4-analysis-overview__action wv4-overview-btn wv4-overview-btn--ghost"
                      :loading="state.isPreflighting"
                      :disabled="isReadonly"
                      @click="handleRunPreflight"
                    >
                      试运行
                    </a-button>
                  </a-tooltip>

                  <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '保存策略并执行预检与同步'">
                    <a-button
                      class="wv4-analysis-overview__action wv4-overview-btn wv4-overview-btn--ghost"
                      :loading="state.isSavingPolicy || state.isPreflighting || state.isSyncing"
                      :disabled="isReadonly"
                      @click="handleSyncWithPolicy"
                    >
                      一键同步
                    </a-button>
                  </a-tooltip>

                  <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '预检通过后可执行同步'">
                    <a-button
                      type="primary"
                      class="wv4-analysis-overview__action wv4-overview-btn wv4-overview-btn--primary"
                      :loading="state.isSyncing"
                      :disabled="isReadonly || !hasPreflightPass"
                      @click="handleExecuteSync"
                    >
                      执行同步
                    </a-button>
                  </a-tooltip>
                </div>
              </div>

              <div class="wv4-analysis-overview__controls system-config-overview-controls">
                <a-space size="small" wrap>
                  <a-tag class="wv4-status-chip wv4-status-chip--brand"> Workstation V4 </a-tag>
                  <a-tag :class="['wv4-status-chip', `wv4-status-chip--${envTone}`]">
                    环境：{{ envLabel }}
                  </a-tag>
                  <a-tag
                    :class="[
                      'wv4-status-chip',
                      state.preflightResult?.executable
                        ? 'wv4-status-chip--success'
                        : 'wv4-status-chip--neutral',
                    ]"
                  >
                    预检：{{ state.preflightResult?.executable ? '通过' : '未执行/未通过' }}
                  </a-tag>
                  <a-tag class="wv4-status-chip wv4-status-chip--neutral">
                    策略版本：{{
                      state.policyForm.policy_version || state.policyForm.tier3_cron || '未生成'
                    }}
                  </a-tag>
                </a-space>
                <div class="system-config-overview-hint">
                  {{ preflightSummary }}
                </div>
              </div>
            </section>

            <div class="wv4-analysis-kpis">
              <article class="wv4-analysis-kpi-card wv4-analysis-kpi-card--brand">
                <div class="wv4-analysis-kpi-card__label">连接状态</div>
                <div class="wv4-analysis-kpi-card__value">{{ connectedCount }} / 2</div>
                <div class="wv4-analysis-kpi-card__desc">
                  健康度 {{ healthPercent }}% · {{ healthLabel }}
                </div>
              </article>

              <article class="wv4-analysis-kpi-card wv4-analysis-kpi-card--warning">
                <div class="wv4-analysis-kpi-card__label">待处理记录</div>
                <div class="wv4-analysis-kpi-card__value">
                  {{ state.stats.pendingRecords.toLocaleString() }}
                </div>
                <div class="wv4-analysis-kpi-card__desc">以 PG 状态统计聚合</div>
              </article>

              <article class="wv4-analysis-kpi-card wv4-analysis-kpi-card--danger">
                <div class="wv4-analysis-kpi-card__label">异常记录</div>
                <div class="wv4-analysis-kpi-card__value">
                  {{ state.stats.failedRecords.toLocaleString() }}
                </div>
                <div class="wv4-analysis-kpi-card__desc">建议先排查失败后再执行</div>
              </article>

              <article class="wv4-analysis-kpi-card wv4-analysis-kpi-card--success">
                <div class="wv4-analysis-kpi-card__label">最近同步时间</div>
                <div class="wv4-analysis-kpi-card__value system-config-kpi-time">
                  {{ lastSyncTimeLabel }}
                </div>
                <div class="wv4-analysis-kpi-card__desc">来源：状态接口聚合</div>
              </article>
            </div>

            <section class="system-config-execution-area flex-1 min-h-0">
              <aside class="system-config-side-panel">
                <div>
                  <div class="system-config-side-kicker">配置流程</div>
                  <h3>同步执行面板</h3>
                  <p>
                    左侧说明当前配置状态，右侧完成连接配置、预检和同步执行。所有正式写入前必须先完成预检确认。
                  </p>
                </div>

                <div class="system-config-state-list">
                  <div class="system-config-state-row">
                    <span>连接状态</span>
                    <strong>{{ connectedCount }} / 2</strong>
                  </div>
                  <div class="system-config-state-row">
                    <span>预检状态</span>
                    <strong>{{ state.preflightResult?.executable ? '已通过' : '待预检' }}</strong>
                  </div>
                  <div class="system-config-state-row">
                    <span>权限状态</span>
                    <strong>{{ isReadonly ? '只读' : '可执行' }}</strong>
                  </div>
                </div>

                <div class="system-config-danger-box">
                  <div class="system-config-side-kicker">风险操作</div>
                  <h4>危险操作集中确认</h4>
                  <p>
                    执行同步会影响本地数据表。当前页面只提供预检、确认和执行入口，不跳过后端安全校验。
                  </p>
                </div>
              </aside>

              <div class="layout-main flex-1 overflow-hidden min-h-0">
                <article
                  class="system-config-execution-card system-config-execution-card--connection overflow-hidden flex flex-col min-h-0"
                >
                  <ConnectionStudio />
                </article>

                <article
                  class="system-config-execution-card system-config-execution-card--runs overflow-hidden flex flex-col min-h-0"
                >
                  <SyncRunPanel />
                </article>
              </div>
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane key="frontpageExtraction" tab="首页抽取设置">
          <div class="system-config-tab-shell system-config-tab-shell--panel">
            <FrontpageExtractionSettingsPanel />
          </div>
        </a-tab-pane>

        <a-tab-pane key="llmConfig" tab="模型配置">
          <div class="system-config-tab-shell system-config-tab-shell--panel">
            <LLMApiConfig />
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import { message, Modal } from 'ant-design-vue'
import ConnectionStudio from './components/sync-console/ConnectionStudio.vue'
import SyncRunPanel from './components/sync-console/SyncRunPanel.vue'
import FrontpageExtractionSettingsPanel from './components/system-config/FrontpageExtractionSettingsPanel.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import { useDataSync } from './composables/useDataSync'

const activeTab = ref('dataSync')
const syncInitialized = ref(false)
const route = useRoute()

const {
  state,
  isReadonly,
  hasPreflightPass,
  initialize,
  resetState,
  testAllConnections,
  runPreflight,
  executeSync,
  savePolicy,
} = useDataSync()

const envLabel = computed(() => {
  const mode = (import.meta.env.MODE || 'development').toLowerCase()
  if (mode === 'production') return '生产'
  if (mode === 'test') return '测试'
  return '开发'
})

const envTone = computed(() => {
  if (envLabel.value === '生产') return 'red'
  if (envLabel.value === '测试') return 'gold'
  return 'green'
})

const connectedCount = computed(() =>
  Math.max(0, Math.min(2, Number(state.stats.connectedCount || 0))),
)

const healthPercent = computed(() =>
  Math.max(0, Math.min(100, Math.round((connectedCount.value / 2) * 100))),
)

const healthLabel = computed(() => {
  if (healthPercent.value >= 100) return '稳定'
  if (healthPercent.value >= 67) return '部分可用'
  return '高风险'
})

const lastSyncTimeLabel = computed(() =>
  state.stats.lastSyncTime ? dayjs(state.stats.lastSyncTime).format('YYYY-MM-DD HH:mm') : '—',
)

const preflightSummary = computed(() => {
  if (!state.preflightResult) return '尚未试运行，建议先预检后执行同步。'
  if (state.preflightResult.executable) {
    return `预检通过：预计影响 ${Number(state.preflightResult.estimated_impact || 0).toLocaleString()} 条。`
  }
  return `预检未通过：${state.preflightResult.blockers?.join('；') || '存在阻断项，请先处理。'}`
})

async function ensureSyncInitialized() {
  if (syncInitialized.value) return
  await initialize()
  syncInitialized.value = true
}

async function handleTestAllConnections() {
  try {
    const result = await testAllConnections()
    if (result.all_connected) {
      message.success('全连接测试通过')
    } else {
      message.warning(`全连接测试完成：${result.connected_count}/${result.total_sources} 可用`)
    }
  } catch {
    message.error('全连接测试失败')
  }
}

async function handleRunPreflight() {
  try {
    const result = await runPreflight('pg')
    if (result.executable) {
      message.success(
        `预检通过：预计影响 ${Number(result.estimated_impact || 0).toLocaleString()} 条`,
      )
    } else {
      message.warning(`预检未通过：${result.blockers?.join('；') || '存在阻断项'}`)
    }
  } catch {
    message.error('试运行失败')
  }
}

async function triggerSyncWithConfirm(autoSavePolicy: boolean) {
  if (autoSavePolicy) {
    await savePolicy()
    message.success('同步策略已保存')
  }

  let preflight = state.preflightResult
  if (!preflight || preflight.source !== 'pg') {
    preflight = await runPreflight('pg')
  }
  if (!preflight.executable) {
    message.warning(`预检未通过：${preflight.blockers?.join('；') || '存在阻断项'}`)
    return
  }

  const ok = await new Promise<boolean>((resolve) => {
    Modal.confirm({
      title: '执行前确认',
      content: `预计影响 ${Number(preflight?.estimated_impact || 0).toLocaleString()} 条记录，是否继续执行？`,
      okText: '继续执行',
      cancelText: '取消',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
  if (!ok) return

  const result = await executeSync('pg')
  if (result.success) {
    message.success('同步任务已启动')
  } else {
    message.warning(result.error || result.message || '同步任务未启动')
  }
}

async function handleSyncWithPolicy() {
  try {
    await triggerSyncWithConfirm(true)
  } catch {
    message.error('执行同步失败')
  }
}

async function handleExecuteSync() {
  try {
    await triggerSyncWithConfirm(false)
  } catch {
    message.error('执行同步失败')
  }
}

onMounted(async () => {
  if (route.query.tab === 'frontpageExtraction' || route.query.tab === 'llmConfig') {
    activeTab.value = route.query.tab
  }
  if (activeTab.value !== 'llmConfig') {
    await ensureSyncInitialized()
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'llmConfig') return
  await ensureSyncInitialized()
})

onUnmounted(() => {
  resetState()
})
</script>

<style>
@import './styles/workstation-v4-view.css';
</style>
<style scoped>
.sync-config-page {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  font-feature-settings:
    'rlig' 1,
    'calt' 1;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.sync-config-page :deep(.ant-btn),
.sync-config-page :deep(.ant-input),
.sync-config-page :deep(.ant-input-affix-wrapper),
.sync-config-page :deep(.ant-select),
.sync-config-page :deep(.ant-tabs),
.sync-config-page :deep(.ant-table),
.sync-config-page :deep(.ant-tag),
.sync-config-page :deep(.ant-select-dropdown),
.sync-config-page :deep(.ant-select-item),
.sync-config-page :deep(.ant-picker),
.sync-config-page :deep(.ant-input-number),
.sync-config-page :deep(label),
.sync-config-page :deep(button) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.system-config-tabs {
  display: flex !important;
  flex-direction: column;
  height: 100%;
}

.system-config-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
  flex-shrink: 0;
  border-radius: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  padding: 8px 12px;
}

.system-config-tabs :deep(.ant-tabs-content-holder),
.system-config-tabs :deep(.ant-tabs-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.system-config-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.system-config-tabs :deep(.ant-tabs-tab) {
  font-weight: 600;
  color: rgba(29, 29, 31, 0.56);
}

.system-config-tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #0066cc;
}

.system-config-tabs :deep(.ant-tabs-ink-bar) {
  background: #0066cc;
}

.system-config-tab-shell {
  height: 100%;
  min-height: 0;
}

.system-config-tab-shell--panel {
  overflow: auto;
  padding-right: 2px;
}

.system-config-overview-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.sync-config-page :deep(.wv4-analysis-overview),
.sync-config-page :deep(.wv4-analysis-kpi-card) {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.sync-config-page :deep(.wv4-analysis-overview:hover),
.sync-config-page :deep(.wv4-analysis-kpi-card:hover) {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.sync-config-page :deep(.wv4-analysis-overview__title) {
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 31px;
}

.sync-config-page :deep(.wv4-analysis-overview p),
.sync-config-page :deep(.wv4-analysis-kpi-card__desc) {
  color: rgba(29, 29, 31, 0.58);
}

.system-config-subtitle {
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.sync-config-page :deep(.wv4-analysis-kpi-card__label) {
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
}

.sync-config-page :deep(.wv4-analysis-kpi-card__value) {
  color: #1d1d1f;
  font-weight: 700;
}

.sync-config-page :deep(.wv4-analysis-kpi-card--brand .wv4-analysis-kpi-card__value) {
  color: #0066cc;
}

.system-config-overview-hint {
  font-size: 12px;
  color: rgba(29, 29, 31, 0.56);
}

.wv4-overview-btn {
  height: 34px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  padding-inline: 14px;
}

.wv4-overview-btn--ghost {
  border-color: rgba(0, 102, 204, 0.16);
  color: #0066cc;
  background: rgba(0, 102, 204, 0.06);
}

.wv4-overview-btn--primary {
  background: #0066cc;
  border-color: #0066cc;
  box-shadow: 0 5px 14px rgba(0, 102, 204, 0.18);
}

.wv4-status-chip {
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
  padding: 0 10px;
}

.wv4-status-chip--brand {
  border-color: rgba(0, 102, 204, 0.16);
  background: rgba(0, 102, 204, 0.06);
  color: #0066cc;
}

.wv4-status-chip--green,
.wv4-status-chip--success {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.wv4-status-chip--gold,
.wv4-status-chip--warning {
  border-color: rgba(245, 158, 11, 0.2);
  background: rgba(245, 158, 11, 0.08);
  color: #b45309;
}

.wv4-status-chip--red,
.wv4-status-chip--danger {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

.wv4-status-chip--neutral {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}

.system-config-execution-area {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 14px;
  border-radius: 20px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
  padding: 14px;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.system-config-execution-area:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.system-config-side-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.76);
  padding: 18px;
}

.system-config-side-kicker {
  color: rgba(29, 29, 31, 0.42);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.system-config-side-panel h3,
.system-config-danger-box h4 {
  margin: 4px 0 0;
  color: #1d1d1f;
  font-weight: 700;
}

.system-config-side-panel h3 {
  font-size: 18px;
}

.system-config-danger-box h4 {
  font-size: 15px;
}

.system-config-side-panel p,
.system-config-danger-box p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 22px;
}

.system-config-state-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.system-config-state-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.82);
  padding: 10px 12px;
}

.system-config-state-row span {
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  font-weight: 700;
}

.system-config-state-row strong {
  color: #0066cc;
  font-size: 13px;
  font-weight: 700;
}

.system-config-danger-box {
  margin-top: auto;
  border: 1px solid rgba(245, 158, 11, 0.18);
  border-radius: 14px;
  background: rgba(255, 247, 237, 0.72);
  padding: 14px;
}

.system-config-danger-box .system-config-side-kicker,
.system-config-danger-box h4,
.system-config-danger-box p {
  color: #b45309;
}

.layout-main {
  display: grid;
  grid-template-columns: minmax(640px, 1.75fr) minmax(320px, 0.72fr);
  gap: 14px;
}

.system-config-execution-card {
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 1px 4px rgba(0, 0, 0, 0.045);
}

.system-config-kpi-time {
  font-size: 24px;
  line-height: 1.2;
}

.sync-config-page :deep(.rounded-xl),
.sync-config-page :deep(.rounded-lg),
.sync-config-page :deep(.rounded) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.sync-config-page :deep(.bg-white),
.sync-config-page :deep(.bg-slate-50),
.sync-config-page :deep(.bg-slate-50\/40),
.sync-config-page :deep(.bg-slate-50\/70),
.sync-config-page :deep(.bg-slate-50\/80),
.sync-config-page :deep(.bg-slate-100),
.sync-config-page :deep(.bg-slate-100\/60),
.sync-config-page :deep(.bg-slate-100\/80) {
  background-color: rgba(255, 255, 255, 0.86) !important;
}

.sync-config-page :deep(.border-slate-100),
.sync-config-page :deep(.border-slate-200),
.sync-config-page :deep(.border-slate-200\/50),
.sync-config-page :deep(.border-slate-200\/80),
.sync-config-page :deep(.border-\[\#E5E7EB\]\/60) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.sync-config-page :deep(.text-slate-900),
.sync-config-page :deep(.text-slate-800),
.sync-config-page :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.sync-config-page :deep(.text-slate-600),
.sync-config-page :deep(.text-slate-500) {
  color: rgba(29, 29, 31, 0.6) !important;
}

.sync-config-page :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.38) !important;
}

.sync-config-page :deep(.bg-\[\#0066cc\]),
.sync-config-page :deep(.hover\:bg-\[\#0057b8\]:hover) {
  background-color: #0066cc !important;
}

.sync-config-page :deep(.focus\:border-\[\#0066cc\]:focus) {
  border-color: rgba(0, 102, 204, 0.38) !important;
}

.sync-config-page :deep(.focus\:ring-\[\#0066cc\]\/10:focus) {
  --tw-ring-color: rgba(0, 102, 204, 0.1) !important;
}

.sync-config-page :deep(.hover\:bg-blue-50\/30:hover) {
  background-color: rgba(0, 102, 204, 0.045) !important;
}

.sync-config-page :deep(.shadow-\[0_4px_12px_rgba\(37\,99\,235\,0\.22\)\]) {
  box-shadow: 0 4px 12px rgba(0, 102, 204, 0.16) !important;
}

.sync-config-page :deep(.font-mono) {
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.sync-config-page :deep(.uppercase) {
  letter-spacing: 0.02em;
}

@media (max-width: 1536px) {
  .layout-main {
    grid-template-columns: minmax(560px, 1.6fr) minmax(300px, 0.76fr);
  }
}

@media (max-width: 1366px) {
  .layout-main {
    grid-template-columns: minmax(480px, 1.45fr) minmax(280px, 0.8fr);
  }
}

@media (max-width: 980px) {
  .system-config-execution-area {
    grid-template-columns: 1fr;
  }

  .layout-main {
    grid-template-columns: 1fr;
  }

  .system-config-execution-card--runs {
    min-height: 420px;
  }

  .system-config-policy-area {
    max-height: none;
  }
}

@media (max-width: 768px) {
  .system-config-tabs :deep(.ant-tabs-nav) {
    margin-bottom: 12px;
    padding: 6px 10px;
  }

  .system-config-execution-area {
    padding: 10px;
  }

  .system-config-kpi-time {
    font-size: 18px;
  }
}
</style>
