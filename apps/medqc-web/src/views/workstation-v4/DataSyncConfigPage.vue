<template>
  <div class="sync-config-page workstation-shell min-h-screen flex flex-col">
    <div
      class="flex-1 p-5 lg:p-6 overflow-hidden flex flex-col min-h-0 container mx-auto max-w-[1680px] w-full"
    >
      <a-tabs
        v-model:active-key="activeTab"
        class="system-config-tabs flex-1 min-h-0"
      >
        <a-tab-pane
          key="dataSync"
          tab="数据同步配置"
        >
          <div class="system-config-tab-shell flex flex-col h-full min-h-0 gap-4">
            <section class="system-config-hero">
              <div class="system-config-hero__main">
                <div class="system-config-breadcrumb">
                  系统配置 / 数据同步设置
                </div>
                <h2>病历数据同步设置</h2>
                <p>
                  {{ pageSubtitle }}
                </p>
              </div>
            </section>

            <section class="sync-guided-workbench">
              <div class="sync-guided-step">
                <div class="sync-guided-step__heading">
                  <span>1</span>
                  <div>
                    <h3>选择病历类型</h3>
                    <p>先明确本次要同步在院病历、已出院病历，或两者一起同步。</p>
                  </div>
                </div>
                <div class="sync-scene-cards">
                  <button
                    v-for="option in syncSceneOptions"
                    :key="option.value"
                    type="button"
                    class="sync-scene-card"
                    :class="{ 'is-active': state.policyForm.scope === option.value }"
                    :data-testid="`sync-scene-${option.value}`"
                    :disabled="isReadonly"
                    @click="selectSyncScene(option.value)"
                  >
                    <strong>{{ option.label }}</strong>
                    <span>{{ option.description }}</span>
                  </button>
                </div>
                <p class="sync-identity-note">
                  按机构、患者和就诊三坐标匹配病历；mr_no 不是同步条件。
                </p>
              </div>

              <div class="sync-guided-divider" />

              <div class="sync-guided-step">
                <div class="sync-guided-step__heading">
                  <span>2</span>
                  <div>
                    <h3>设置同步范围</h3>
                    <p>{{ syncScopeDescription }}</p>
                  </div>
                </div>
                <div class="sync-filter-row">
                  <label class="system-config-scope-field sync-filter-row__department">
                    <span>抽取科室</span>
                    <a-select
                      v-model:value="state.policyForm.target_departments"
                      mode="multiple"
                      :disabled="isReadonly"
                      :loading="state.departmentsLoading"
                      :options="policyDepartmentOptions"
                      :max-tag-count="3"
                      style="width: 100%"
                      placeholder="默认全院"
                      @change="handlePolicyDepartmentChange"
                    />
                  </label>
                  <div
                    v-if="state.policyForm.scope === 'running'"
                    class="system-config-scope-field sync-current-time"
                  >
                    <span>当前在院统计时间</span>
                    <strong>以执行检查时的医院当前时间为准</strong>
                  </div>
                  <label
                    v-else
                    class="system-config-scope-field sync-filter-row__date"
                  >
                    <span>{{ syncStartDateLabel }}</span>
                    <a-date-picker
                      v-model:value="state.policyForm.start_date"
                      :locale="datePickerZhCN"
                      format="YYYY年MM月DD日"
                      value-format="YYYY-MM-DD"
                      :disabled="isReadonly"
                      style="width: 100%"
                      :placeholder="syncStartDatePlaceholder"
                    />
                  </label>
                  <label
                    v-if="state.policyForm.scope !== 'running'"
                    class="system-config-scope-field sync-filter-row__date"
                  >
                    <span>{{ syncEndDateLabel }}</span>
                    <a-date-picker
                      v-model:value="state.policyForm.end_date"
                      :locale="datePickerZhCN"
                      format="YYYY年MM月DD日"
                      value-format="YYYY-MM-DD"
                      :disabled="isReadonly"
                      style="width: 100%"
                      :placeholder="syncEndDatePlaceholder"
                    />
                  </label>
                  <a-button
                    type="primary"
                    class="wv4-overview-btn wv4-overview-btn--primary sync-check-action"
                    data-testid="check-record-scope-action"
                    :loading="state.isPreflighting"
                    :disabled="isReadonly"
                    @click="handleRunPreflight"
                  >
                    检查病历范围
                  </a-button>
                </div>
              </div>

              <div class="sync-guided-divider" />

              <div class="sync-guided-step sync-result-step">
                <div class="sync-guided-step__heading sync-guided-step__heading--result">
                  <span>3</span>
                  <div>
                    <h3>检查结果</h3>
                    <p>{{ preflightSummary }}</p>
                  </div>
                  <a-tag
                    :class="[
                      'wv4-status-chip',
                      hasPreflightPass ? 'wv4-status-chip--success' : 'wv4-status-chip--neutral',
                    ]"
                  >
                    {{ hasPreflightPass ? '可同步' : state.preflightResult ? '需处理' : '待检查' }}
                  </a-tag>
                </div>

                <div
                  v-if="state.preflightResult"
                  class="sync-result-summary"
                >
                  <div class="sync-result-metric sync-result-metric--primary">
                    <span>{{ candidateProgressLabel }}</span>
                    <strong>{{
                      Number(state.preflightResult.estimated_impact || 0).toLocaleString()
                    }}</strong>
                    <em>份病历</em>
                  </div>
                  <div class="sync-result-metric">
                    <span>病历类型</span>
                    <strong>{{ syncScopeDisplayLabel }}</strong>
                    <em>{{ syncAnchorLabel }}</em>
                  </div>
                  <div class="sync-result-metric">
                    <span>同步范围</span>
                    <strong>{{ policyDepartmentLabel }}</strong>
                    <em>{{ policyDateRangeLabel }}</em>
                  </div>
                </div>
                <div
                  v-else
                  class="sync-result-empty"
                >
                  选择范围后点击“检查病历范围”，这里会显示候选病历数和阻断原因。
                </div>

                <div
                  v-if="
                    state.preflightResult?.blockers?.length ||
                      state.preflightResult?.warnings?.length
                  "
                  class="sync-result-messages"
                >
                  <p
                    v-for="item in state.preflightResult.blockers || []"
                    :key="`blocker-${item}`"
                    class="is-blocker"
                  >
                    {{ item }}
                  </p>
                  <p
                    v-for="item in state.preflightResult.warnings || []"
                    :key="`warning-${item}`"
                    class="is-warning"
                  >
                    {{ item }}
                  </p>
                </div>

                <div
                  v-if="showSyncProgress"
                  class="system-config-sync-progress"
                >
                  <div class="system-config-sync-progress__head">
                    <div>
                      <h4>同步执行进度</h4>
                      <p>{{ syncProgressStageText }}</p>
                    </div>
                    <a-tag
                      class="wv4-status-chip"
                      :class="syncProgressStatusClass"
                    >
                      {{ state.isSyncing ? '执行中' : syncProgressStatusText }}
                    </a-tag>
                  </div>

                  <a-progress
                    :percent="syncProgressPercent"
                    :show-info="false"
                    :stroke-color="syncProgressStrokeColor"
                  />

                  <div class="system-config-progress-grid">
                    <div>
                      <span>本次候选</span>
                      <strong>{{ syncProgressCandidateCount.toLocaleString() }} 份</strong>
                    </div>
                    <div>
                      <span>可进入病历池</span>
                      <strong>{{ syncProgressVisitCompleted }} / {{ syncProgressVisitTotal }} 份</strong>
                    </div>
                    <div>
                      <span>资料类别进度</span>
                      <strong>{{ syncProgressTablesDone }} / {{ syncProgressTablesTotal }}</strong>
                    </div>
                    <div v-if="syncBundleProgressVisible">
                      <span>病历资料视图</span>
                      <strong>{{ syncBundleProgressCompleted }} /
                        {{ syncBundleProgressTotal }} 份</strong>
                    </div>
                  </div>

                  <details
                    v-if="isSyncAdvancedUser"
                    class="system-config-progress-details"
                    data-testid="sync-technical-details"
                  >
                    <summary>同步详情</summary>
                    <div class="system-config-progress-meta">
                      <span>当前资料表：{{ syncProgressCurrentTable }}</span>
                      <span>剩余资料表：{{ syncProgressTablesRemaining }}</span>
                      <span>已拉取行数：{{ syncProgressRowsPulled.toLocaleString() }}</span>
                      <span>已写入行数：{{ syncProgressRowsUpserted.toLocaleString() }}</span>
                      <span>预计剩余：{{ syncProgressEtaText }}</span>
                    </div>
                  </details>
                  <p class="system-config-progress-note">
                    病历主记录写入后即可进入病历池；病程、医嘱、检查检验等资料会继续同步并统一刷新。
                    <span v-if="syncProgressVisitWarning">{{ syncProgressVisitWarning }}</span>
                  </p>
                </div>
                <div
                  v-if="hasPreflightPass"
                  class="sync-result-actions"
                >
                  <label
                    class="system-config-confirm-check"
                    :class="{ 'is-disabled': isReadonly }"
                  >
                    <input
                      v-model="syncScopeConfirmed"
                      type="checkbox"
                      :disabled="isReadonly"
                    >
                    <span>我已确认同步
                      {{ Number(state.preflightResult?.estimated_impact || 0).toLocaleString() }}
                      份病历</span>
                  </label>
                  <a-tooltip :title="syncScopeConfirmed ? '正式写入本地 CDM' : '请先确认同步范围'">
                    <a-button
                      type="primary"
                      class="wv4-overview-btn wv4-overview-btn--primary"
                      :loading="state.isSyncing"
                      :disabled="isReadonly || !syncScopeConfirmed"
                      @click="handleExecuteSync"
                    >
                      {{ executeActionLabel }}
                    </a-button>
                  </a-tooltip>
                </div>
              </div>
            </section>

            <section
              v-if="isSyncAdvancedUser"
              class="system-config-advanced-section"
            >
              <div class="system-config-advanced-head">
                <div>
                  <h3>高级设置与运行记录</h3>
                  <p>仅供实施/管理员排障使用。这里包含连接配置、表组预检、源库诊断和运行日志。</p>
                </div>
                <div class="system-config-advanced-actions">
                  <a-button
                    class="wv4-overview-btn wv4-overview-btn--ghost"
                    :loading="state.isTestingAll"
                    :disabled="isReadonly"
                    @click="handleTestAllConnections"
                  >
                    检测数据连接
                  </a-button>
                  <a-button
                    class="wv4-overview-btn wv4-overview-btn--ghost"
                    data-testid="advanced-sync-toggle"
                    @click="detailWorkbenchOpen = !detailWorkbenchOpen"
                  >
                    {{ detailWorkbenchOpen ? '收起' : '展开高级设置' }}
                  </a-button>
                </div>
              </div>

              <div
                v-if="detailWorkbenchOpen"
                class="system-config-preflight-table system-config-advanced-preflight"
              >
                <div class="system-config-section-head system-config-section-head--compact">
                  <div>
                    <h4>clinical_data 表组预检</h4>
                    <p>
                      可执行 {{ preflightPassCount }} / {{ preflightTableRows.length }}，阻断
                      {{ preflightBlockerCount }} 项，警告 {{ preflightWarningCount }} 项。
                    </p>
                  </div>
                </div>
                <div
                  v-if="preflightTableRows.length === 0"
                  class="system-config-empty-table"
                >
                  尚未生成表组预检结果。
                </div>
                <table v-else>
                  <thead>
                    <tr>
                      <th>本地表</th>
                      <th>源表</th>
                      <th>日期字段</th>
                      <th>状态</th>
                      <th>说明</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="row in preflightTableRows"
                      :key="row.table"
                    >
                      <td>{{ row.table }}</td>
                      <td>{{ row.source }}</td>
                      <td>{{ row.dateField }}</td>
                      <td>
                        <span :class="row.executable ? 'is-pass' : 'is-blocked'">
                          {{ row.executable ? '可执行' : '阻断' }}
                        </span>
                      </td>
                      <td>{{ row.blockers || '字段与连接检查通过' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div
                v-if="detailWorkbenchOpen"
                class="system-config-detail-workbench"
              >
                <article
                  class="system-config-execution-card system-config-execution-card--connection"
                >
                  <ConnectionStudio />
                </article>

                <article class="system-config-execution-card system-config-execution-card--runs">
                  <SyncRunPanel />
                </article>
              </div>
            </section>
          </div>
        </a-tab-pane>

        <a-tab-pane
          v-if="canManageFrontpageConfig"
          key="frontpageExtraction"
          tab="首页抽取设置"
          data-testid="frontpage-config-tab"
        >
          <div class="system-config-tab-shell system-config-tab-shell--panel">
            <FrontpageExtractionSettingsPanel />
          </div>
        </a-tab-pane>

        <a-tab-pane
          v-if="canViewLlmObservability"
          key="llmObservability"
          tab="模型性能"
          data-testid="llm-observability-tab"
        >
          <div class="system-config-tab-shell system-config-tab-shell--panel">
            <LlmPerformanceObservabilityPanel />
          </div>
        </a-tab-pane>

        <a-tab-pane
          v-if="canManageLlmConfig"
          key="llmConfig"
          tab="模型配置"
          data-testid="llm-config-tab"
        >
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
import { message, Modal } from 'ant-design-vue'
import datePickerZhCN from 'ant-design-vue/es/date-picker/locale/zh_CN'
import 'dayjs/locale/zh-cn'
import type { SyncTableValidationItem } from '@/api/sync'
import ConnectionStudio from './components/sync-console/ConnectionStudio.vue'
import SyncRunPanel from './components/sync-console/SyncRunPanel.vue'
import FrontpageExtractionSettingsPanel from './components/system-config/FrontpageExtractionSettingsPanel.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import { useDataSync } from './composables/useDataSync'
import LlmPerformanceObservabilityPanel from './components/system-config/LlmPerformanceObservabilityPanel.vue'
import { useAuthStore } from '@/stores/auth'

const activeTab = ref('dataSync')
const syncInitialized = ref(false)
const detailWorkbenchOpen = ref(false)
const syncScopeConfirmed = ref(false)
const route = useRoute()
const authStore = useAuthStore()

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

const isSyncAdvancedUser = computed(() =>
  authStore.userRoles.some((role) => role === 'super_admin' || role === 'sync_admin'),
)
const canManageFrontpageConfig = computed(() =>
  authStore.userRoles.some((role) =>
    ['admin', 'qc_manager', 'sync_admin', 'super_admin'].includes(role),
  ),
)
const canManageLlmConfig = computed(() =>
  authStore.userRoles.some((role) => ['admin', 'sync_admin', 'super_admin'].includes(role)),
)
const isDemoSyncUser = computed(() => !isSyncAdvancedUser.value)

const isObservabilityOperationalAdmin = computed(() =>
  authStore.userRoles.some((role) => role === 'sync_admin' || role === 'super_admin'),
)
const canViewLlmObservability = computed(
  () =>
    canManageLlmConfig.value &&
    (authStore.user?.is_demo_account !== true || isObservabilityOperationalAdmin.value),
)
const syncSceneOptions = [
  { label: '在院病历', value: 'running', description: '同步执行时仍在院的全部病历' },
  { label: '已出院病历', value: 'final', description: '按出院日期范围同步终末病历' },
  { label: '在院及已出院', value: 'both', description: '当前在院 + 期间出院病历' },
] as const

function selectSyncScene(scene: 'running' | 'final' | 'both') {
  if (isReadonly.value) return
  state.policyForm.scope = scene
}

const syncScopeDisplayLabel = computed(() => {
  if (state.policyForm.scope === 'running') return '在院病历'
  if (state.policyForm.scope === 'both') return '在院及已出院病历'
  return '已出院病历'
})

const syncScopeDescription = computed(() => {
  if (state.policyForm.scope === 'running') {
    return '同步执行时仍在院的全部病历，不限制入院日期；不要求病案首页号。'
  }
  if (state.policyForm.scope === 'both') {
    return '同步当前仍在院的病历，并按所选出院日期范围同步已出院病历。'
  }
  return '按出院日期和科室筛选已出院病历；修改后需要重新预检。'
})

const syncStartDateLabel = computed(() => {
  return '出院开始日期'
})

const syncStartDatePlaceholder = computed(() => `请选择${syncStartDateLabel.value}`)

const syncEndDateLabel = computed(() => '出院结束日期')
const syncEndDatePlaceholder = computed(() => `请选择${syncEndDateLabel.value}`)

const syncAnchorLabel = computed(() => {
  if (state.policyForm.scope === 'running') return '住院登记 / 当前在院状态'
  if (state.policyForm.scope === 'both') return '当前在院 + 出院日期范围'
  return '出院记录 / 出院日期'
})

const noCandidateMessage = computed(() => {
  if (state.policyForm.scope === 'running') {
    return '当前没有找到符合条件的在院病历，请检查科室或住院登记数据。'
  }
  if (state.policyForm.scope === 'both') {
    return '没有找到符合条件的在院或已出院病历，请检查科室、日期范围或住院登记数据。'
  }
  return '没有找到符合条件的已出院病历，请检查科室名称或出院日期范围。'
})

const pageSubtitle = computed(() =>
  isDemoSyncUser.value
    ? '选择在院、已出院或合并范围，先检查可同步病历，再同步到本地用于质控。'
    : '按三坐标病例范围抽取在院及已出院病历，先只读检测，再预检影响，最后人工确认同步。',
)

const preflightActionLabel = computed(() => (isDemoSyncUser.value ? '检查病历范围' : '重新预检'))

const executeActionLabel = computed(() => (isDemoSyncUser.value ? '开始同步' : '确认执行同步'))

const safeBannerTitle = computed(() =>
  isDemoSyncUser.value ? '当前不会修改医院源库。' : '当前不会写入源库，所有修改只写入本地 CDM。',
)

const safeBannerDescription = computed(() =>
  isDemoSyncUser.value
    ? '同步只会把符合条件的病历复制到本地，用于后续质控验证和演示。'
    : '本页与客户样本验证共用三坐标病例同步链；客户样本的定向同步仍在“客户样本验证”页面执行。',
)

const summaryDescription = computed(() =>
  isDemoSyncUser.value
    ? '请先确认住院范围、科室和日期，再检查是否找到可同步病历。'
    : '用于快速核对源库、范围和调度，详细配置在下方连接面板中维护。',
)

const safeNoteText = computed(() =>
  isDemoSyncUser.value
    ? '点击“开始同步”后，也只会写入本地演示环境；不会回写或修改医院源库。'
    : '在点击“确认执行同步”前，不会写入源库；同步只影响本地 CDM。客户样本池同步另走专用链路。',
)

const candidateProgressLabel = computed(() =>
  isDemoSyncUser.value ? '找到可同步病历' : '候选病历',
)

const connectedCount = computed(() =>
  Math.max(0, Math.min(2, Number(state.stats.connectedCount || 0))),
)

const preflightSummary = computed(() => {
  if (!state.preflightResult) {
    return isDemoSyncUser.value
      ? '请选择住院范围、科室和日期，然后点击“检查病历范围”。'
      : '尚未试运行，建议先预检候选病历范围后执行同步。'
  }
  const estimated = Number(state.preflightResult.estimated_impact || 0)
  if (estimated === 0 && (state.preflightResult.blockers?.length || 0) === 0) {
    return noCandidateMessage.value
  }
  if (!hasPreflightPass.value) {
    return isDemoSyncUser.value
      ? '同步范围已变化，请重新检查病历范围后再开始同步。'
      : '同步范围已变化，请重新试运行后再执行同步。'
  }
  if (state.preflightResult.executable) {
    return isDemoSyncUser.value
      ? `检查完成：找到可同步病历 ${estimated.toLocaleString()} 份。`
      : `预检通过：预计涉及 ${estimated.toLocaleString()} 份病历。`
  }
  return isDemoSyncUser.value
    ? `检查未通过：${state.preflightResult.blockers?.join('；') || '请先处理提示项。'}`
    : `预检未通过：${state.preflightResult.blockers?.join('；') || '存在阻断项，请先处理。'}`
})

const enabledTableCount = computed(() => state.pgSyncTables.filter((item) => item.enabled).length)

const selectedTableGroupSummary = computed(() => {
  const selected = Array.isArray(state.selectedTableGroups) ? state.selectedTableGroups : []
  if (selected.length === 0) {
    return '默认核心8表'
  }
  const labelMap = new Map(
    state.pgTableGroups.map((item) => [
      String(item.id || '').trim(),
      String(item.label || item.id || '').trim(),
    ]),
  )
  const labels = selected
    .map((item) => labelMap.get(String(item || '').trim()) || String(item || '').trim())
    .filter(Boolean)
  return labels.length > 0 ? labels.join(' / ') : '默认核心8表'
})

const policyDepartmentOptions = computed(() => [
  { label: '全院', value: '*' },
  ...state.availableDepartments.map((name) => ({
    label: name,
    value: name,
  })),
])

const policyDepartmentLabel = computed(() => {
  const departments = state.policyForm.target_departments || []
  if (departments.length === 0 || departments.includes('*')) return '全院'
  if (departments.length <= 2) return departments.join('、')
  return `${departments.slice(0, 2).join('、')} 等 ${departments.length} 个科室`
})

const policyDateRangeLabel = computed(() => {
  const end = state.policyForm.end_date || '未设'
  if (state.policyForm.scope === 'running') return '执行时刻'
  const start = state.policyForm.start_date || '未设'
  return `${start} ~ ${end}`
})

const nightWindowLabel = computed(() => {
  const start = state.policyForm.night_window_start || '--:--'
  const end = state.policyForm.night_window_end || '--:--'
  return `${start} ~ ${end}`
})

const summaryItems = computed(() => {
  if (isDemoSyncUser.value) {
    return [
      {
        label: '同步方式',
        value: syncScopeDisplayLabel.value,
        description: syncAnchorLabel.value,
      },
      {
        label: '筛选范围',
        value: policyDateRangeLabel.value,
        description: '可按科室进一步缩小范围',
      },
      {
        label: '同步内容',
        value: '病历与相关文书资料',
        description: '同步后可在病历池中查看和质控',
      },
      {
        label: '当前状态',
        value: state.preflightResult ? candidateProgressLabel.value : '等待检查',
        description: state.preflightResult
          ? `${Number(state.preflightResult.estimated_impact || 0).toLocaleString()} 份`
          : '请先检查病历范围',
      },
    ]
  }

  return [
    {
      label: '源库',
      value: 'clinical_data',
      description: 'PG 源库 · 只读连接',
    },
    {
      label: '抽取锚点',
      value: syncAnchorLabel.value,
      description: '按完整三坐标计算候选病历',
    },
    {
      label: '同步范围',
      value: selectedTableGroupSummary.value,
      description: `启用表 ${enabledTableCount.value} / ${state.pgSyncTables.length}`,
    },
    {
      label: '调度窗口',
      value: policyDateRangeLabel.value,
      description: `夜间窗口 ${nightWindowLabel.value}`,
    },
  ]
})

const syncSafetySteps = computed(() => [
  {
    key: 'readonly',
    index: '1',
    title: isDemoSyncUser.value ? '选择同步范围' : '只读源库检测',
    description: isDemoSyncUser.value
      ? `选择${syncScopeDisplayLabel.value}、科室和日期，明确本次同步范围。`
      : connectedCount.value >= 2
        ? '源库与本地库连接可用。'
        : '验证 clinical_data 与本地 CDM 连通性。',
    tone: connectedCount.value >= 2 ? 'ready' : 'neutral',
  },
  {
    key: 'preflight',
    index: '2',
    title: isDemoSyncUser.value ? '检查可同步病历' : '试运行预检',
    description: state.preflightResult
      ? `${candidateProgressLabel.value} ${Number(state.preflightResult.estimated_impact || 0).toLocaleString()} 份。`
      : isDemoSyncUser.value
        ? '检查所选范围内是否能找到可同步病历。'
        : '按三坐标病例范围模拟抽取，生成影响范围和阻断项。',
    tone: state.preflightResult?.executable ? 'ready' : state.preflightResult ? 'warn' : 'neutral',
  },
  {
    key: 'confirm',
    index: '3',
    title: isDemoSyncUser.value ? '开始同步' : '人工确认写入',
    description: hasPreflightPass.value
      ? isDemoSyncUser.value
        ? '检查通过后即可开始同步。'
        : '预检结果有效，可人工确认同步。'
      : isDemoSyncUser.value
        ? '检查通过后才启用同步。'
        : '预检通过后才启用正式同步。',
    tone: hasPreflightPass.value ? 'ready' : 'locked',
  },
])

const executionChecklist = computed(() => {
  const estimated = Number(state.preflightResult?.estimated_impact || 0)
  const blockers = state.preflightResult?.blockers || []
  const warnings = state.preflightResult?.warnings || []
  if (isDemoSyncUser.value) {
    return [
      {
        label: '数据连接',
        value: connectedCount.value >= 1 ? '连接状态已检测' : '等待连接检测',
        status: connectedCount.value >= 1 ? '已检测' : '待检测',
        tone: connectedCount.value >= 1 ? 'ready' : 'neutral',
      },
      {
        label: '筛选依据',
        value: syncAnchorLabel.value,
        status: '已确认',
        tone: 'ready',
      },
      {
        label: candidateProgressLabel.value,
        value: state.preflightResult ? `${estimated.toLocaleString()} 份病历` : '等待检查',
        status: state.preflightResult ? '已检查' : '待检查',
        tone: state.preflightResult ? (estimated > 0 ? 'ready' : 'warn') : 'neutral',
      },
      {
        label: '检查结果',
        value:
          blockers.length > 0
            ? blockers.join('；')
            : warnings.length > 0
              ? warnings.join('；')
              : state.preflightResult
                ? estimated > 0
                  ? '可开始同步'
                  : '请调整科室或日期后重试'
                : '等待检查病历范围',
        status:
          blockers.length > 0
            ? '需处理'
            : estimated === 0 && state.preflightResult
              ? '未找到'
              : '可继续',
        tone: blockers.length > 0 || (estimated === 0 && state.preflightResult) ? 'warn' : 'ready',
      },
    ]
  }

  return [
    {
      label: '源库 clinical_data',
      value: connectedCount.value >= 1 ? '连接状态已检测' : '等待只读连接检测',
      status: connectedCount.value >= 1 ? '已就绪' : '待检测',
      tone: connectedCount.value >= 1 ? 'ready' : 'neutral',
    },
    {
      label: '本地 CDM',
      value: connectedCount.value >= 2 ? '本地库可访问' : '等待本地库检测',
      status: connectedCount.value >= 2 ? '已就绪' : '待检测',
      tone: connectedCount.value >= 2 ? 'ready' : 'neutral',
    },
    {
      label: '抽取锚点',
      value: syncAnchorLabel.value,
      status: '已确认',
      tone: 'ready',
    },
    {
      label: '同步范围',
      value: `${selectedTableGroupSummary.value}，启用 ${enabledTableCount.value} 张表`,
      status: enabledTableCount.value > 0 ? '已选择' : '待配置',
      tone: enabledTableCount.value > 0 ? 'ready' : 'neutral',
    },
    {
      label: '预计涉及',
      value: state.preflightResult ? `${estimated.toLocaleString()} 份病历` : '等待预检估算',
      status: state.preflightResult ? '已估算' : '待预检',
      tone: state.preflightResult ? 'ready' : 'neutral',
    },
    {
      label: '阻断/警告',
      value: `阻断 ${blockers.length} 项，警告 ${warnings.length} 项`,
      status: blockers.length > 0 ? '需处理' : '可继续',
      tone: blockers.length > 0 ? 'danger' : warnings.length > 0 ? 'warn' : 'ready',
    },
  ]
})

const syncProgress = computed<Record<string, unknown>>(() => {
  const raw = state.pgSyncState?.progress
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
})

const syncVisitProgress = computed<Record<string, unknown>>(() => {
  const raw = syncProgress.value.visit_progress
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
})

const syncBundleProgress = computed<Record<string, unknown>>(() => {
  const raw = syncProgress.value.bundle_progress
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
})

const syncProgressStageLabelMap: Record<string, string> = {
  initializing: '正在准备同步任务',
  preflight: '正在检查同步条件',
  scope_resolution: '正在确定病历范围',
  syncing_table: '正在同步病历资料',
  primary_visibility: '正在同步病历主记录',
  primary_unavailable: '部分病历主记录待处理',
  bundle_refresh: '正在刷新病历资料视图',
  finalizing: '正在刷新病历资料视图',
  completed: '同步已完成',
  failed: '同步未完成，请查看原因',
  rejected: '同步任务未启动',
}

const syncProgressStatusText = computed(() => {
  const status = String(syncProgress.value.status || state.pgSyncState?.last_sync_status || 'never')
  if (status === 'success') return '已完成'
  if (status === 'partial') return '部分完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  return '未开始'
})

const syncProgressStatusClass = computed(() => {
  const status = String(syncProgress.value.status || state.pgSyncState?.last_sync_status || '')
  if (status === 'failed') return 'wv4-status-chip--danger'
  if (status === 'partial') return 'wv4-status-chip--warning'
  if (status === 'success') return 'wv4-status-chip--success'
  return state.isSyncing ? 'wv4-status-chip--brand' : 'wv4-status-chip--neutral'
})

const syncProgressTablesTotal = computed(() => Number(syncProgress.value.tables_total || 0))
const syncProgressTablesDone = computed(() =>
  Math.min(syncProgressTablesTotal.value, Number(syncProgress.value.tables_done || 0)),
)
const syncProgressTablesRemaining = computed(() =>
  Math.max(0, syncProgressTablesTotal.value - syncProgressTablesDone.value),
)
const syncBundleProgressTotal = computed(() => Number(syncBundleProgress.value.total || 0))
const syncBundleProgressCompleted = computed(() =>
  Math.min(syncBundleProgressTotal.value, Number(syncBundleProgress.value.completed || 0)),
)
const syncBundleProgressVisible = computed(
  () =>
    syncBundleProgressTotal.value > 0 ||
    String(syncProgress.value.stage || '') === 'bundle_refresh',
)
const syncProgressRowsPulled = computed(() => Number(syncProgress.value.rows_pulled_total || 0))
const syncProgressRowsUpserted = computed(() =>
  Number(syncProgress.value.rows_upserted_total || state.pgSyncState?.total_records_synced || 0),
)
const syncProgressCandidateCount = computed(() => {
  const fromProgress = Number(syncProgress.value.eligible_visit_count || 0)
  if (fromProgress > 0) return fromProgress
  return Number(state.preflightResult?.estimated_impact || 0)
})
const syncProgressVisitTotal = computed(() => {
  const total = Number(syncVisitProgress.value.total || 0)
  return total > 0 ? total : syncProgressCandidateCount.value
})
const syncProgressVisitCompleted = computed(() =>
  Math.min(syncProgressVisitTotal.value, Number(syncVisitProgress.value.completed || 0)),
)
const syncProgressVisitMissingMr = computed(() => Number(syncVisitProgress.value.missing_mr || 0))
const syncProgressVisitDetailOnly = computed(() => Number(syncVisitProgress.value.detail_only || 0))
const syncProgressVisitWarning = computed(() => {
  const detailOnly = syncProgressVisitDetailOnly.value
  if (detailOnly > 0) {
    return `有 ${detailOnly.toLocaleString()} 份病历明细已同步但病历池暂不可见。`
  }
  const missingMr = syncProgressVisitMissingMr.value
  if (missingMr > 0 && !state.isSyncing) {
    return `有 ${missingMr.toLocaleString()} 份候选病历缺少主记录。`
  }
  return ''
})
const syncProgressCurrentTable = computed(() => {
  const table = String(syncProgress.value.current_table || '').trim()
  return table || '等待表同步开始'
})
const syncProgressPercent = computed(() => {
  if (
    String(syncProgress.value.stage || '') === 'bundle_refresh' &&
    syncBundleProgressTotal.value > 0
  ) {
    return Math.max(
      0,
      Math.min(
        100,
        Math.round((syncBundleProgressCompleted.value / syncBundleProgressTotal.value) * 100),
      ),
    )
  }
  if (syncProgressTablesTotal.value > 0) {
    return Math.max(
      0,
      Math.min(
        100,
        Math.round((syncProgressTablesDone.value / syncProgressTablesTotal.value) * 100),
      ),
    )
  }
  if (state.isSyncing) return 5
  return syncProgressRowsUpserted.value > 0 ? 100 : 0
})
const syncProgressStrokeColor = computed(() => {
  const status = String(syncProgress.value.status || state.pgSyncState?.last_sync_status || '')
  if (status === 'failed') return '#ef4444'
  if (status === 'partial') return '#f59e0b'
  return '#2b6cf6'
})
const syncProgressEtaText = computed(() => {
  const eta = Number(syncProgress.value.eta_seconds)
  if (!Number.isFinite(eta) || eta <= 0) return state.isSyncing ? '计算中' : '—'
  if (eta < 60) return `${eta} 秒`
  return `${Math.ceil(eta / 60)} 分钟`
})
const syncProgressStageText = computed(() => {
  const stage = String(syncProgress.value.stage || '').trim()
  const label = syncProgressStageLabelMap[stage] || (state.isSyncing ? '正在同步数据' : '等待执行')
  return label
})
const showSyncProgress = computed(
  () =>
    state.isSyncing ||
    Boolean(syncProgress.value.stage) ||
    ['success', 'partial', 'failed'].includes(String(state.pgSyncState?.last_sync_status || '')),
)

const preflightSourceRows = computed<SyncTableValidationItem[]>(() => {
  const result = state.preflightResult
  if (!result) return []
  if (result.execution_table_validations?.length) {
    return result.execution_table_validations
  }
  return result.table_validations || []
})

const preflightTableRows = computed(() =>
  preflightSourceRows.value.map((item) => ({
    table: item.table || '-',
    source: item.source || item.source_table || '-',
    dateField: item.resolved_date_field || item.date_field || item.fallback_date_field || '-',
    executable: Boolean(item.executable),
    blockers: (item.blockers || []).join('；'),
  })),
)

const preflightPassCount = computed(
  () => preflightTableRows.value.filter((item) => item.executable).length,
)
const preflightBlockerCount = computed(() => state.preflightResult?.blockers?.length || 0)
const preflightWarningCount = computed(() => state.preflightResult?.warnings?.length || 0)

const normalizePolicyDepartments = (values: string[]): string[] => {
  const cleaned = [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))]
  if (cleaned.length === 0) {
    return ['*']
  }
  if (cleaned.includes('*') && cleaned.length > 1) {
    const latest = cleaned[cleaned.length - 1]
    return latest === '*' ? ['*'] : cleaned.filter((item) => item !== '*')
  }
  return cleaned
}

const handlePolicyDepartmentChange = (values: string[]) => {
  state.policyForm.target_departments = normalizePolicyDepartments(values)
}

const riskAdviceItems = computed(() => {
  const blockers = state.preflightResult?.blockers || []
  const warnings = state.preflightResult?.warnings || []
  const items = [
    {
      title: '存在无法匹配的 visit_id',
      description: '若住院登记或出院记录缺少三坐标身份与关键时间，本页无法计算病历候选范围。',
      action: '请核对 institute_id、patient_id、visit_id 以及入院/出院时间；mr_no 不是同步前提。',
      tone: warnings.length || blockers.length ? 'warn' : 'neutral',
    },
    {
      title: '关键文书可能缺表',
      description: '首次病程、医嘱、检查检验、病理报告缺失会直接影响 0609 质控解释性。',
      action: '0609/客户样本定向同步建议在客户验证页执行；本页用于全院在院、已出院病历批量同步。',
      tone: preflightTableRows.value.some((item) => !item.executable) ? 'danger' : 'neutral',
    },
    {
      title: '正式同步前可回退',
      description: '本页只写入本地 CDM，不写回源库；若同步异常，可重新选择范围后再同步。',
      action: '建议保留本次预检结果和运行日志。',
      tone: 'info',
    },
  ]
  return items
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
    const estimated = Number(result.estimated_impact || 0)
    const blockers = result.blockers || []
    if (blockers.length > 0) {
      message.warning(
        isDemoSyncUser.value
          ? `检查未通过：${blockers.join('；')}`
          : `预检未通过：${blockers.join('；')}`,
      )
    } else if (estimated === 0) {
      message.warning(noCandidateMessage.value)
    } else if (result.executable) {
      message.success(
        isDemoSyncUser.value
          ? `检查完成：找到可同步病历 ${estimated.toLocaleString()} 份`
          : `预检通过：预计涉及 ${estimated.toLocaleString()} 份病历`,
      )
    } else {
      message.warning(
        isDemoSyncUser.value
          ? `检查未通过：${result.blockers?.join('；') || '请先处理提示项'}`
          : `预检未通过：${result.blockers?.join('；') || '存在阻断项'}`,
      )
    }
  } catch {
    message.error(isDemoSyncUser.value ? '检查病历范围失败' : '试运行失败')
  }
}

async function triggerSyncWithConfirm(autoSavePolicy: boolean) {
  if (autoSavePolicy) {
    const shouldSavePolicy = await new Promise<boolean>((resolve) => {
      Modal.confirm({
        title: isDemoSyncUser.value ? '保存范围并检查' : '保存策略并同步',
        content: isDemoSyncUser.value
          ? '将先保存当前住院范围、科室和日期，再检查是否有可同步病历。'
          : '将先保存当前同步策略，再执行试运行预检。预检通过后还会再次确认是否正式同步。',
        okText: isDemoSyncUser.value ? '保存并检查' : '保存并试运行',
        cancelText: '取消',
        onOk: () => resolve(true),
        onCancel: () => resolve(false),
      })
    })
    if (!shouldSavePolicy) return

    await savePolicy()
    message.success('同步策略已保存')
  }

  let preflight = state.preflightResult
  if (!preflight || preflight.source !== 'pg' || !hasPreflightPass.value) {
    preflight = await runPreflight('pg')
  }
  if (!preflight.executable) {
    const estimated = Number(preflight.estimated_impact || 0)
    const blockers = preflight.blockers || []
    message.warning(
      blockers.length > 0
        ? isDemoSyncUser.value
          ? `检查未通过：${blockers.join('；')}`
          : `预检未通过：${blockers.join('；')}`
        : estimated === 0
          ? noCandidateMessage.value
          : isDemoSyncUser.value
            ? '检查未通过：请先处理提示项'
            : '预检未通过：存在阻断项',
    )
    return
  }

  const ok = await new Promise<boolean>((resolve) => {
    Modal.confirm({
      title: isDemoSyncUser.value ? '开始同步' : '执行前确认',
      content: `找到可同步病历 ${Number(preflight?.estimated_impact || 0).toLocaleString()} 份，是否继续？`,
      okText: isDemoSyncUser.value ? '开始同步' : '继续执行',
      cancelText: '取消',
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    })
  })
  if (!ok) return

  const result = await executeSync('pg')
  if (result.success) {
    if (result.status === 'timeout_polling') {
      message.warning(result.message || '同步请求仍可能在后端执行，已转入状态轮询')
    } else {
      message.success('同步执行完成，已开始刷新状态')
    }
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
  const requestedTab = typeof route.query.tab === 'string' ? route.query.tab : ''
  const canOpenRequestedTab =
    (requestedTab === 'frontpageExtraction' && canManageFrontpageConfig.value) ||
    (requestedTab === 'llmConfig' && canManageLlmConfig.value) ||
    (requestedTab === 'llmObservability' && canViewLlmObservability.value)
  if (canOpenRequestedTab) {
    activeTab.value = requestedTab
  }
  if (activeTab.value !== 'llmConfig' && activeTab.value !== 'llmObservability') {
    await ensureSyncInitialized()
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'llmConfig' || tab === 'llmObservability') return
  await ensureSyncInitialized()
})

watch(hasPreflightPass, (isReady) => {
  if (!isReady) {
    syncScopeConfirmed.value = false
  }
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
  color: #2b6cf6;
}

.system-config-tabs :deep(.ant-tabs-ink-bar) {
  background: #2b6cf6;
}

.system-config-tab-shell {
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding-bottom: 86px;
}

.system-config-tab-shell--panel {
  overflow: auto;
  padding-right: 2px;
}

.system-config-hero,
.system-config-safe-banner,
.system-config-safety-card,
.system-config-safe-workbench,
.system-config-advanced-section,
.system-config-detail-workbench,
.system-config-preflight-panel,
.system-config-risk-panel,
.system-config-config-summary {
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035);
}

.system-config-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border-radius: 20px;
  padding: 20px 22px;
}

.system-config-breadcrumb {
  color: rgba(29, 29, 31, 0.45);
  font-size: 13px;
  font-weight: 700;
}

.system-config-hero h2 {
  margin: 8px 0 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  line-height: 32px;
}

.system-config-hero p {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
}

.system-config-hero__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.sync-guided-workbench {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 8px 24px rgba(0, 0, 0, 0.04);
  padding: 24px;
}

.sync-guided-step {
  min-width: 0;
}

.sync-guided-step__heading {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.sync-guided-step__heading > span {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(43, 108, 246, 0.1);
  color: #2b6cf6;
  font-size: 13px;
  font-weight: 800;
}

.sync-guided-step__heading h3 {
  margin: 1px 0 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 700;
  line-height: 24px;
}

.sync-guided-step__heading p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 20px;
}

.sync-guided-step__heading--result {
  align-items: center;
}

.sync-guided-step__heading--result > div {
  flex: 1;
}

.sync-guided-divider {
  height: 1px;
  margin: 24px 0;
  background: rgba(0, 0, 0, 0.07);
}

.sync-scene-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.sync-scene-card {
  display: flex;
  min-height: 86px;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 6px;
  border: 1px solid rgba(0, 0, 0, 0.09);
  border-radius: 14px;
  background: rgba(250, 250, 252, 0.76);
  color: #1d1d1f;
  cursor: pointer;
  padding: 16px 18px;
  text-align: left;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.sync-scene-card:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(43, 108, 246, 0.22);
}

.sync-scene-card.is-active {
  border-color: rgba(43, 108, 246, 0.42);
  background: rgba(234, 242, 255, 0.82);
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.06);
}

.sync-scene-card:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.sync-scene-card strong {
  color: inherit;
  font-size: 15px;
  font-weight: 700;
}

.sync-scene-card.is-active strong {
  color: #2b6cf6;
}

.sync-scene-card span {
  color: rgba(29, 29, 31, 0.54);
  font-size: 12px;
  line-height: 18px;
}

.sync-identity-note {
  margin: 12px 0 0;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  line-height: 18px;
}

.sync-filter-row {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) minmax(180px, 0.8fr) minmax(180px, 0.8fr) auto;
  align-items: end;
  gap: 12px;
  margin-top: 16px;
}

.sync-filter-row__department,
.sync-filter-row__date {
  min-width: 0;
}

.sync-current-time {
  grid-column: span 2;
  min-height: 40px;
  justify-content: center;
  padding: 10px 14px;
  border: 1px solid rgba(43, 108, 246, 0.16);
  border-radius: 10px;
  background: rgba(43, 108, 246, 0.04);
}

.sync-current-time strong {
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
  font-weight: 600;
}

.sync-check-action {
  min-height: 40px;
  white-space: nowrap;
}

.sync-result-step {
  min-height: 160px;
}

.sync-result-summary {
  display: grid;
  grid-template-columns: 0.72fr 1fr 1.2fr;
  gap: 12px;
  margin-top: 16px;
}

.sync-result-metric {
  min-width: 0;
  border: 1px solid rgba(0, 0, 0, 0.07);
  border-radius: 14px;
  background: rgba(250, 250, 252, 0.72);
  padding: 14px 16px;
}

.sync-result-metric--primary {
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(234, 242, 255, 0.62);
}

.sync-result-metric span,
.sync-result-metric em {
  display: block;
  overflow: hidden;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-style: normal;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-result-metric strong {
  display: block;
  overflow: hidden;
  margin: 5px 0 3px;
  color: #1d1d1f;
  font-size: 18px;
  font-weight: 700;
  line-height: 24px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-result-metric--primary strong {
  color: #2b6cf6;
  font-size: 26px;
  line-height: 30px;
}

.sync-result-empty {
  margin-top: 16px;
  border: 1px dashed rgba(0, 0, 0, 0.12);
  border-radius: 14px;
  background: rgba(250, 250, 252, 0.6);
  color: rgba(29, 29, 31, 0.48);
  font-size: 13px;
  line-height: 22px;
  padding: 22px 18px;
  text-align: center;
}

.sync-result-messages {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.sync-result-messages p {
  margin: 0;
  border-radius: 10px;
  font-size: 12px;
  line-height: 20px;
  padding: 9px 12px;
}

.sync-result-messages .is-blocker {
  background: rgba(254, 242, 242, 0.86);
  color: #b91c1c;
}

.sync-result-messages .is-warning {
  background: rgba(255, 251, 235, 0.86);
  color: #a16207;
}

.sync-result-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 18px;
  border-top: 1px solid rgba(0, 0, 0, 0.07);
  padding-top: 16px;
}

@media (max-width: 980px) {
  .sync-filter-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .sync-current-time {
    grid-column: auto;
  }

  .sync-result-summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .sync-guided-workbench {
    padding: 18px;
  }

  .sync-scene-cards,
  .sync-filter-row {
    grid-template-columns: 1fr;
  }

  .sync-result-actions {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 820px) {
  .sync-scene-cards {
    grid-template-columns: 1fr;
  }
}

.system-config-safe-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  border-color: rgba(43, 108, 246, 0.18);
  border-radius: 18px;
  background: rgba(234, 242, 255, 0.78);
  padding: 16px 18px;
}

.system-config-safe-shield {
  display: flex;
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: #2b6cf6;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
}

.system-config-safe-banner strong {
  color: #2b6cf6;
  font-size: 15px;
}

.system-config-safe-banner p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.62);
  font-size: 13px;
  line-height: 22px;
}

.system-config-safety-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.system-config-safety-card {
  display: flex;
  min-height: 116px;
  align-items: flex-start;
  gap: 14px;
  border-radius: 18px;
  padding: 18px;
}

.system-config-safety-card > span {
  display: flex;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(43, 108, 246, 0.1);
  color: #2b6cf6;
  font-weight: 800;
}

.system-config-safety-card strong,
.system-config-section-head h3,
.system-config-section-head h4,
.system-config-config-summary h3 {
  color: #1d1d1f;
  font-weight: 700;
}

.system-config-safety-card p {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 22px;
}

.system-config-safety-card--ready {
  border-color: rgba(43, 108, 246, 0.16);
}

.system-config-safety-card--warn {
  border-color: rgba(245, 158, 11, 0.22);
  background: rgba(255, 251, 235, 0.86);
}

.system-config-safety-card--locked {
  background: rgba(250, 250, 252, 0.84);
}

.system-config-safe-workbench {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 340px;
  gap: 14px;
  min-height: 520px;
  border-radius: 20px;
  padding: 14px;
}

.system-config-config-summary,
.system-config-preflight-panel,
.system-config-risk-panel {
  min-height: 0;
  border-radius: 18px;
  padding: 18px;
}

.system-config-config-summary p,
.system-config-section-head p {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 13px;
  line-height: 22px;
}

.system-config-summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.system-config-summary-list div {
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.72);
  padding: 11px 12px;
}

.system-config-summary-list span {
  display: block;
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
  font-weight: 700;
}

.system-config-summary-list strong {
  display: block;
  margin-top: 4px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 700;
}

.system-config-summary-list em,
.system-config-risk-item em {
  display: block;
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-style: normal;
}

.system-config-safe-note {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px solid rgba(43, 108, 246, 0.16);
  background: rgba(234, 242, 255, 0.7);
  padding: 13px;
}

.system-config-safe-note strong {
  color: #2b6cf6;
}

.system-config-safe-note p {
  margin: 6px 0 0;
}

.system-config-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.system-config-section-head h3,
.system-config-section-head h4 {
  margin: 0;
  font-size: 17px;
  line-height: 22px;
}

.system-config-section-head--compact {
  align-items: center;
}

.system-config-checklist {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.system-config-check-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.72);
  padding: 11px 12px;
}

.system-config-check-row > span {
  flex: 0 0 auto;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.05);
  color: rgba(29, 29, 31, 0.55);
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  padding: 0 8px;
}

.system-config-check-row strong {
  display: block;
  color: #1d1d1f;
  font-size: 13px;
}

.system-config-check-row em {
  display: block;
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-style: normal;
  line-height: 18px;
}

.system-config-check-row--ready > span {
  background: rgba(43, 108, 246, 0.08);
  color: #2b6cf6;
}

.system-config-check-row--warn > span {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.system-config-check-row--danger > span {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

.system-config-scope-form {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px solid rgba(43, 108, 246, 0.14);
  background: rgba(250, 252, 255, 0.9);
  padding: 14px;
}

.system-config-scope-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.system-config-scope-field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 7px;
}

.system-config-scope-field--scene {
  grid-column: span 3;
}

.system-config-scope-field--department {
  grid-column: span 4;
}

.system-config-scope-field--date {
  grid-column: span 4;
}

.system-config-scope-field > span {
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 700;
}

.system-config-scope-field :deep(.ant-select-selector),
.system-config-scope-field :deep(.ant-picker) {
  min-height: 40px;
}

@media (max-width: 1280px) {
  .system-config-scope-field--scene,
  .system-config-scope-field--department,
  .system-config-scope-field--date {
    grid-column: span 6;
  }
}

@media (max-width: 760px) {
  .system-config-scope-field--scene,
  .system-config-scope-field--department,
  .system-config-scope-field--date {
    grid-column: 1 / -1;
  }
}

.system-config-preflight-table {
  margin-top: 16px;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.system-config-preflight-table .system-config-section-head {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.82);
  padding: 12px 14px;
}

.system-config-preflight-table table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.system-config-preflight-table th,
.system-config-preflight-table td {
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  padding: 10px 12px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 12px;
  line-height: 18px;
  text-align: left;
}

.system-config-preflight-table th {
  background: rgba(250, 250, 252, 0.7);
  color: rgba(29, 29, 31, 0.48);
  font-weight: 700;
}

.system-config-preflight-table td {
  word-break: break-word;
}

.system-config-preflight-table tr:last-child td {
  border-bottom: 0;
}

.system-config-preflight-table .is-pass {
  color: #2b6cf6;
  font-weight: 700;
}

.system-config-preflight-table .is-blocked {
  color: #b91c1c;
  font-weight: 700;
}

.system-config-empty-table {
  padding: 24px 14px;
  color: rgba(29, 29, 31, 0.48);
  font-size: 13px;
}

.system-config-sync-progress {
  margin-top: 16px;
  border-radius: 14px;
  border: 1px solid rgba(43, 108, 246, 0.14);
  background: rgba(250, 252, 255, 0.86);
  padding: 14px;
}

.system-config-sync-progress__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.system-config-sync-progress__head h4 {
  margin: 0;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 700;
  line-height: 20px;
}

.system-config-sync-progress__head p {
  margin: 4px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}

.system-config-progress-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(116px, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.system-config-progress-grid div {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 10px 11px;
}

.system-config-progress-grid span {
  display: block;
  color: rgba(29, 29, 31, 0.48);
  font-size: 12px;
  font-weight: 700;
}

.system-config-progress-grid strong {
  display: block;
  margin-top: 4px;
  color: #1d1d1f;
  font-size: 16px;
  font-weight: 700;
  line-height: 22px;
}

.system-config-progress-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.system-config-progress-details {
  margin-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  padding-top: 10px;
}

.system-config-progress-details summary {
  width: fit-content;
  cursor: pointer;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 600;
  list-style-position: inside;
}

.system-config-progress-meta span {
  border-radius: 999px;
  background: rgba(43, 108, 246, 0.08);
  color: rgba(0, 70, 140, 0.82);
  font-size: 12px;
  font-weight: 600;
  line-height: 24px;
  padding: 0 10px;
}

.system-config-progress-note {
  margin: 10px 0 0;
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  line-height: 18px;
}

.system-config-risk-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 14px;
}

.system-config-risk-item {
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.75);
  padding: 13px;
}

.system-config-risk-item strong {
  color: #1d1d1f;
  font-size: 13px;
}

.system-config-risk-item p {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  line-height: 20px;
}

.system-config-risk-item--warn {
  border-color: rgba(245, 158, 11, 0.2);
  background: rgba(255, 251, 235, 0.72);
}

.system-config-risk-item--danger {
  border-color: rgba(239, 68, 68, 0.18);
  background: rgba(254, 242, 242, 0.68);
}

.system-config-risk-item--info {
  border-color: rgba(43, 108, 246, 0.14);
  background: rgba(234, 242, 255, 0.66);
}

.system-config-advanced-section {
  overflow: hidden;
  border-radius: 20px;
}

.system-config-advanced-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
}

.system-config-advanced-head h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 700;
  line-height: 22px;
}

.system-config-advanced-head p {
  margin: 6px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 13px;
  line-height: 22px;
}

.system-config-advanced-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10px;
}

.system-config-advanced-preflight {
  margin: 0 14px 14px;
}

.system-config-detail-workbench {
  display: grid;
  grid-template-columns: minmax(640px, 1.7fr) minmax(340px, 0.82fr);
  gap: 14px;
  min-height: 440px;
  overflow: hidden;
  border-width: 1px 0 0;
  border-radius: 0;
  background: rgba(250, 250, 252, 0.68);
  box-shadow: none;
  padding: 14px;
}

.system-config-safe-action-bar {
  position: sticky;
  z-index: 8;
  bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  box-shadow:
    0 8px 24px rgba(0, 0, 0, 0.08),
    0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 14px 16px;
}

.system-config-safe-action-bar strong {
  display: block;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 700;
}

.system-config-safe-action-bar p {
  max-width: 560px;
  margin: 3px 0 0;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  line-height: 18px;
}

.system-config-safe-action-bar__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.system-config-confirm-check {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 8px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(250, 250, 252, 0.9);
  color: rgba(29, 29, 31, 0.72);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  padding: 0 12px;
  transition:
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.system-config-confirm-check input {
  width: 14px;
  height: 14px;
  accent-color: #2b6cf6;
}

.system-config-confirm-check:not(.is-disabled):hover {
  border-color: rgba(43, 108, 246, 0.24);
  background: rgba(234, 242, 255, 0.72);
}

.system-config-confirm-check.is-disabled {
  cursor: not-allowed;
  opacity: 0.55;
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
  color: #2b6cf6;
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
  border-color: rgba(43, 108, 246, 0.16);
  color: #2b6cf6;
  background: rgba(43, 108, 246, 0.06);
}

.wv4-overview-btn--primary {
  background: #2b6cf6;
  border-color: #2b6cf6;
  color: #ffffff;
  box-shadow: 0 5px 14px rgba(43, 108, 246, 0.18);
}

.wv4-overview-btn--primary:not(:disabled):not(.ant-btn-disabled):hover,
.wv4-overview-btn--primary:not(:disabled):not(.ant-btn-disabled):focus {
  background: #0057b8;
  border-color: #0057b8;
  color: #ffffff;
}

.wv4-overview-btn--primary:disabled,
.wv4-overview-btn--primary[disabled],
.wv4-overview-btn--primary.ant-btn-disabled {
  background: rgba(0, 0, 0, 0.06) !important;
  border-color: rgba(0, 0, 0, 0.08) !important;
  color: rgba(29, 29, 31, 0.46) !important;
  box-shadow: none !important;
  cursor: not-allowed;
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
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.06);
  color: #2b6cf6;
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
  color: #2b6cf6;
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

.sync-config-page :deep(.bg-\[\#2b6cf6\]),
.sync-config-page :deep(.hover\:bg-\[\#0057b8\]:hover) {
  background-color: #2b6cf6 !important;
}

.sync-config-page :deep(.focus\:border-\[\#2b6cf6\]:focus) {
  border-color: rgba(43, 108, 246, 0.38) !important;
}

.sync-config-page :deep(.focus\:ring-\[\#2b6cf6\]\/10:focus) {
  --tw-ring-color: rgba(43, 108, 246, 0.1) !important;
}

.sync-config-page :deep(.hover\:bg-blue-50\/30:hover) {
  background-color: rgba(43, 108, 246, 0.045) !important;
}

.sync-config-page :deep(.shadow-\[0_4px_12px_rgba\(37\,99\,235\,0\.22\)\]) {
  box-shadow: 0 4px 12px rgba(43, 108, 246, 0.16) !important;
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
