<template>
  <main class="mq-page system-config-page">
    <!-- 页头：眉标 + 大标题；右侧分段切换替代原 Tabs，页签可见性规则不变 -->
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">数据与配置 · 系统配置</span>
        <h1 class="mq-page-title">系统配置</h1>
      </div>
      <div
        class="mq-segmented"
        role="tablist"
        aria-label="系统配置分类"
        data-testid="system-config-tabs"
        :data-active-key="activeTab"
      >
        <button
          v-for="tab in configTabs"
          :key="tab.key"
          type="button"
          role="tab"
          class="mq-segmented__item"
          :class="{ 'is-active': activeTab === tab.key }"
          :aria-selected="activeTab === tab.key"
          :data-testid="tab.testId"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </header>

    <template v-if="activeTab === 'dataSync'">
      <section class="mq-card mq-card--padded sync-card" aria-labelledby="sync-card-title">
        <div class="mq-card__head">
          <div>
            <h2 id="sync-card-title" class="mq-card__title">病历数据同步设置</h2>
            <p class="mq-card__desc">
              {{ pageSubtitle }}
            </p>
          </div>
          <span v-if="lastSyncLabel" class="mq-status" :class="lastSyncStatusClass">{{
            lastSyncLabel
          }}</span>
        </div>

        <ol class="sync-steps">
          <!-- 第 1 步：病历类型 -->
          <li class="sync-step is-done">
            <span class="sync-step__marker" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="3"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="m5 12.5 4.5 4.5L19 7.5" />
              </svg>
            </span>
            <div class="sync-step__body">
              <div class="sync-step__heading">
                <h3>选择病历类型</h3>
                <p>先明确本次要同步在院病历、已出院病历，或两者一起同步。</p>
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
                  <span class="sync-scene-card__radio" aria-hidden="true" />
                  <span class="sync-scene-card__copy">
                    <strong>{{ option.label }}</strong>
                    <span>{{ option.description }}</span>
                  </span>
                </button>
              </div>
              <p class="sync-step__note">按机构、患者和就诊三坐标匹配病历；mr_no 不是同步条件。</p>
            </div>
          </li>

          <!-- 第 2 步：同步范围 -->
          <li class="sync-step" :class="{ 'is-done': Boolean(state.preflightResult) }">
            <span class="sync-step__marker" aria-hidden="true">
              <svg
                v-if="state.preflightResult"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="3"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="m5 12.5 4.5 4.5L19 7.5" />
              </svg>
              <template v-else>2</template>
            </span>
            <div class="sync-step__body">
              <div class="sync-step__heading">
                <h3>设置同步范围</h3>
                <p>{{ syncScopeDescription }}</p>
              </div>
              <div class="sync-scope-fields">
                <label class="mq-field sync-scope-fields__department">
                  <span class="mq-field__label">抽取科室</span>
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
                  <span
                    v-if="state.departmentsLoading"
                    class="mq-field__hint"
                    role="status"
                    data-testid="departments-background-loading"
                  >正在后台读取服务器科室，可继续使用其他设置。</span>
                  <span
                    v-else-if="state.departmentsError"
                    class="mq-field__hint"
                    role="status"
                    data-testid="departments-background-error"
                  >
                    {{ state.departmentsError }}
                    <button type="button" class="mq-btn mq-btn--ghost mq-btn--sm" @click="loadDepartments()">
                      重试
                    </button>
                  </span>
                </label>
                <div
                  v-if="state.policyForm.scope === 'running'"
                  class="mq-field sync-scope-fields__now"
                >
                  <span class="mq-field__label">当前在院统计时间</span>
                  <strong class="sync-scope-fields__now-value"
                    >以执行检查时的医院当前时间为准</strong
                  >
                </div>
                <label v-else class="mq-field">
                  <span class="mq-field__label">{{ syncStartDateLabel }}</span>
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
                <label v-if="state.policyForm.scope !== 'running'" class="mq-field">
                  <span class="mq-field__label">{{ syncEndDateLabel }}</span>
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
                  class="sync-scope-fields__action"
                  data-testid="check-record-scope-action"
                  :loading="state.isPreflighting"
                  :disabled="isReadonly"
                  @click="handleRunPreflight"
                >
                  检查病历范围
                </a-button>
              </div>
            </div>
          </li>

          <!-- 第 3 步：检查结果与执行 -->
          <li class="sync-step sync-step--last">
            <span class="sync-step__marker" aria-hidden="true">3</span>
            <div class="sync-step__body">
              <div class="sync-step__heading">
                <h3>检查结果</h3>
                <p>{{ preflightSummary }}</p>
              </div>

              <div v-if="state.preflightResult" class="mq-soft sync-result">
                <div class="sync-result__metric sync-result__metric--primary">
                  <span>{{ candidateProgressLabel }}</span>
                  <strong
                    >{{ Number(state.preflightResult.estimated_impact || 0).toLocaleString()
                    }}<small>份病历</small></strong
                  >
                </div>
                <div class="sync-result__metric">
                  <span>病历类型</span>
                  <strong>{{ syncScopeDisplayLabel }}</strong>
                  <em>{{ syncAnchorLabel }}</em>
                </div>
                <div class="sync-result__metric">
                  <span>同步范围</span>
                  <strong>{{ policyDepartmentLabel }}</strong>
                  <em>{{ policyDateRangeLabel }}</em>
                </div>
                <span class="mq-status sync-result__status" :class="preflightStatusClass">
                  {{ hasPreflightPass ? '可同步' : '需处理' }}
                </span>
              </div>
              <div v-else class="sync-result-empty">
                <span class="mq-status">待检查</span>
                选择范围后点击“检查病历范围”，这里会显示候选病历数和阻断原因。
              </div>

              <div
                v-if="
                  state.preflightResult?.blockers?.length || state.preflightResult?.warnings?.length
                "
                class="sync-messages"
              >
                <p
                  v-for="item in state.preflightResult.blockers || []"
                  :key="`blocker-${item}`"
                  class="sync-message is-blocker"
                >
                  <MqIcon name="tech_error" :size="18" color="#E0263A" />
                  {{ item }}
                </p>
                <p
                  v-for="item in state.preflightResult.warnings || []"
                  :key="`warning-${item}`"
                  class="sync-message is-warning"
                >
                  <MqIcon name="tech_error" :size="18" color="#C25E00" />
                  {{ item }}
                </p>
              </div>

              <div v-if="showSyncProgress" class="mq-inset sync-progress">
                <div class="sync-progress__head">
                  <div>
                    <h4>同步执行进度</h4>
                    <p>{{ syncProgressStageText }}</p>
                  </div>
                  <span
                    class="mq-status"
                    :class="syncProgressStatusClass"
                    data-testid="sync-progress-status"
                  >
                    {{ state.isSyncing ? '执行中' : syncProgressStatusText }}
                  </span>
                </div>

                <a-progress
                  :percent="syncProgressPercent"
                  :show-info="false"
                  :stroke-color="syncProgressStrokeColor"
                />

                <div class="sync-progress__grid">
                  <div>
                    <span>本次候选</span>
                    <strong>{{ syncProgressCandidateCount.toLocaleString() }} 份</strong>
                  </div>
                  <div>
                    <span>可进入病历池</span>
                    <strong
                      >{{ syncProgressVisitCompleted }} / {{ syncProgressVisitTotal }} 份</strong
                    >
                  </div>
                  <div>
                    <span>资料类别进度</span>
                    <strong>{{ syncProgressTablesDone }} / {{ syncProgressTablesTotal }}</strong>
                  </div>
                  <div v-if="syncBundleProgressVisible">
                    <span>病历资料视图</span>
                    <strong
                      >{{ syncBundleProgressCompleted }} / {{ syncBundleProgressTotal }} 份</strong
                    >
                  </div>
                </div>

                <details
                  v-if="isSyncAdvancedUser"
                  class="sync-progress__details"
                  data-testid="sync-technical-details"
                >
                  <summary>同步详情</summary>
                  <div class="sync-progress__meta">
                    <span>当前资料表：{{ syncProgressCurrentTable }}</span>
                    <span>剩余资料表：{{ syncProgressTablesRemaining }}</span>
                    <span>已拉取行数：{{ syncProgressRowsPulled.toLocaleString() }}</span>
                    <span>已写入行数：{{ syncProgressRowsUpserted.toLocaleString() }}</span>
                    <span>预计剩余：{{ syncProgressEtaText }}</span>
                  </div>
                </details>
                <p class="sync-progress__note">
                  病历主记录写入后即可进入病历池；病程、医嘱、检查检验等资料会继续同步并统一刷新。
                  <span v-if="syncProgressVisitWarning">{{ syncProgressVisitWarning }}</span>
                </p>
              </div>

              <div v-if="hasPreflightPass" class="sync-actions">
                <label class="sync-actions__confirm" :class="{ 'is-disabled': isReadonly }">
                  <input v-model="syncScopeConfirmed" type="checkbox" :disabled="isReadonly" />
                  <span
                    >我已确认同步
                    {{ Number(state.preflightResult?.estimated_impact || 0).toLocaleString() }}
                    份病历</span
                  >
                </label>
                <a-tooltip :title="syncScopeConfirmed ? '正式写入本地 CDM' : '请先确认同步范围'">
                  <a-button
                    type="primary"
                    size="large"
                    :loading="state.isSyncing"
                    :disabled="isReadonly || !syncScopeConfirmed"
                    @click="handleExecuteSync"
                  >
                    {{ executeActionLabel }}
                  </a-button>
                </a-tooltip>
              </div>
            </div>
          </li>
        </ol>
      </section>

      <!-- 高级设置：仅实施/同步管理员可见 -->
      <section
        v-if="isSyncAdvancedUser"
        class="mq-card mq-card--padded sync-advanced"
        aria-labelledby="sync-advanced-title"
      >
        <div class="mq-card__head">
          <div>
            <h2 id="sync-advanced-title" class="mq-card__title">高级设置与运行记录</h2>
            <p class="mq-card__desc">
              仅供实施/管理员排障使用。这里包含连接配置、表组预检、源库诊断和运行日志。
            </p>
          </div>
          <div class="sync-advanced__actions">
            <a-button
              :loading="state.isTestingAll"
              :disabled="isReadonly"
              @click="handleTestAllConnections"
            >
              检测数据连接
            </a-button>
            <a-button
              data-testid="advanced-sync-toggle"
              @click="detailWorkbenchOpen = !detailWorkbenchOpen"
            >
              {{ detailWorkbenchOpen ? '收起' : '展开高级设置' }}
            </a-button>
          </div>
        </div>

        <template v-if="detailWorkbenchOpen">
          <div class="sync-preflight">
            <div class="sync-preflight__head">
              <h4>clinical_data 表组预检</h4>
              <span>
                可执行 {{ preflightPassCount }} / {{ preflightTableRows.length }}，阻断
                {{ preflightBlockerCount }} 项，警告 {{ preflightWarningCount }} 项。
              </span>
            </div>
            <div v-if="preflightTableRows.length === 0" class="mq-inset sync-preflight__empty">
              尚未生成表组预检结果。
            </div>
            <div v-else class="mq-inset sync-preflight__table">
              <table class="mq-table">
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
                  <tr v-for="row in preflightTableRows" :key="row.table">
                    <td class="mq-mono">
                      {{ row.table }}
                    </td>
                    <td class="mq-mono">
                      {{ row.source }}
                    </td>
                    <td class="mq-mono">
                      {{ row.dateField }}
                    </td>
                    <td>
                      <span
                        class="mq-status"
                        :class="row.executable ? 'mq-status--success' : 'mq-status--danger'"
                      >
                        {{ row.executable ? '可执行' : '阻断' }}
                      </span>
                    </td>
                    <td :class="{ 'is-blocked': !row.executable }">
                      {{ row.blockers || '字段与连接检查通过' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="sync-advanced__panels">
            <article class="mq-inset sync-advanced__panel">
              <ConnectionStudio />
            </article>
            <article class="mq-inset sync-advanced__panel">
              <SyncRunPanel />
            </article>
          </div>
        </template>
      </section>
    </template>

    <section
      v-else-if="activeTab === 'frontpageExtraction' && canManageFrontpageConfig"
      class="mq-card system-config-panel"
    >
      <FrontpageExtractionSettingsPanel />
    </section>

    <section
      v-else-if="activeTab === 'llmObservability' && canViewLlmObservability"
      class="mq-card system-config-panel"
    >
      <LlmPerformanceObservabilityPanel />
    </section>

    <section
      v-else-if="activeTab === 'accounts' && canManageAccounts"
      class="mq-card system-config-panel account-config-panel"
    >
      <AccountManagementPanel />
    </section>

    <section
      v-else-if="activeTab === 'llmConfig' && canManageLlmConfig"
      class="mq-card system-config-panel"
    >
      <LLMApiConfig />
    </section>

    <!-- 执行前确认：页面内弹窗，跟随工作台主题（静态 Modal.confirm 拿不到嵌套主题） -->
    <a-modal
      :open="executeConfirm.open"
      :footer="null"
      :width="460"
      centered
      wrap-class-name="mq-modal"
      :mask-style="{ backdropFilter: 'blur(6px)' }"
      @cancel="closeExecuteConfirm(false)"
    >
      <div v-if="executeConfirm.open" class="sync-confirm">
        <MqIconTile name="sync" tone="brand" :size="52" :icon-size="28" />
        <div class="sync-confirm__copy">
          <h2>{{ isDemoSyncUser ? '开始同步' : '执行前确认' }}</h2>
          <p>
            找到可同步病历 <b>{{ executeConfirm.count.toLocaleString() }}</b> 份，是否继续？
          </p>
        </div>
        <dl class="mq-soft sync-confirm__summary">
          <div>
            <dt>病历类型</dt>
            <dd>{{ syncScopeDisplayLabel }}</dd>
          </div>
          <div>
            <dt>同步范围</dt>
            <dd>{{ policyDepartmentLabel }}</dd>
          </div>
          <div>
            <dt>{{ state.policyForm.scope === 'running' ? '统计时间' : '出院日期' }}</dt>
            <dd>{{ policyDateRangeLabel }}</dd>
          </div>
        </dl>
        <div class="sync-confirm__actions">
          <button type="button" class="mq-btn" @click="closeExecuteConfirm(false)">取消</button>
          <button
            type="button"
            class="mq-btn mq-btn--primary"
            data-testid="execute-confirm-ok"
            @click="closeExecuteConfirm(true)"
          >
            {{ isDemoSyncUser ? '开始同步' : '继续执行' }}
          </button>
        </div>
      </div>
    </a-modal>
  </main>
</template>

<script setup lang="ts">
import { useWorkstationConfirmation } from '@/components/layout/workstationConfirmation'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import datePickerZhCN from 'ant-design-vue/es/date-picker/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import type { SyncTableValidationItem } from '@/api/sync'
import ConnectionStudio from './components/sync-console/ConnectionStudio.vue'
import SyncRunPanel from './components/sync-console/SyncRunPanel.vue'
import FrontpageExtractionSettingsPanel from './components/system-config/FrontpageExtractionSettingsPanel.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import { useDataSync } from './composables/useDataSync'
import LlmPerformanceObservabilityPanel from './components/system-config/LlmPerformanceObservabilityPanel.vue'
import AccountManagementPanel from './components/system-config/AccountManagementPanel.vue'
import { useAuthStore } from '@/stores/auth'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'

const workstationConfirmation = useWorkstationConfirmation()

const activeTab = ref('dataSync')
const syncInitialized = ref(false)
const detailWorkbenchOpen = ref(false)
const syncScopeConfirmed = ref(false)
const currentPageSyncStarted = ref(false)
const route = useRoute()
const authStore = useAuthStore()

const {
  state,
  isReadonly,
  hasPreflightPass,
  initialize,
  loadDepartments,
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
const canManageAccounts = computed(() => authStore.userRoles.includes('admin'))
const isDemoSyncUser = computed(() => !isSyncAdvancedUser.value)

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
    { key: 'dataSync', label: '数据同步', testId: undefined, visible: true },
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

const LAST_SYNC_STATUS_TEXT: Record<string, string> = {
  success: '成功',
  partial: '部分完成',
  failed: '失败',
  running: '执行中',
}

const lastSyncLabel = computed(() => {
  const time = state.stats.lastSyncTime
  if (!time || !dayjs(time).isValid()) return ''
  const status = LAST_SYNC_STATUS_TEXT[String(state.pgSyncState?.last_sync_status || '')]
  return `上次同步 ${dayjs(time).format('MM-DD HH:mm')}${status ? ` · ${status}` : ''}`
})

const lastSyncStatusClass = computed(() => {
  const status = String(state.pgSyncState?.last_sync_status || '')
  if (status === 'failed') return 'mq-status--danger'
  if (status === 'partial') return 'mq-status--warning'
  return ''
})

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

const executeActionLabel = computed(() => (isDemoSyncUser.value ? '开始同步' : '确认执行同步'))

const candidateProgressLabel = computed(() =>
  isDemoSyncUser.value ? '找到可同步病历' : '候选病历',
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

const syncProgress = computed<Record<string, unknown>>(() => {
  if (!state.isSyncing && !currentPageSyncStarted.value) return {}
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
  const status = String(syncProgress.value.status || (state.isSyncing ? 'running' : 'never'))
  if (status === 'success') return '已完成'
  if (status === 'partial') return '部分完成'
  if (status === 'failed') return '失败'
  if (status === 'running') return '执行中'
  return '未开始'
})

const syncProgressStatusClass = computed(() => {
  const status = String(syncProgress.value.status || (state.isSyncing ? 'running' : ''))
  if (status === 'failed') return 'mq-status--danger'
  if (status === 'partial') return 'mq-status--warning'
  if (status === 'success') return 'mq-status--success'
  return state.isSyncing ? 'mq-status--info' : ''
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
const syncProgressRowsUpserted = computed(() => Number(syncProgress.value.rows_upserted_total || 0))
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
  const status = String(syncProgress.value.status || (state.isSyncing ? 'running' : ''))
  if (status === 'failed') return '#ef4444'
  if (status === 'partial') return '#ff9500'
  return '#0a6cff'
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
const showSyncProgress = true

const preflightStatusClass = computed(() =>
  hasPreflightPass.value ? 'mq-status--success' : 'mq-status--warning',
)

// 执行前确认：页面内弹窗，确认结果以 Promise 返回给同步流程
const executeConfirm = reactive({ open: false, count: 0 })
let resolveExecuteConfirm: ((ok: boolean) => void) | null = null

function askExecuteConfirm(count: number): Promise<boolean> {
  resolveExecuteConfirm?.(false)
  executeConfirm.count = count
  executeConfirm.open = true
  return new Promise<boolean>((resolve) => {
    resolveExecuteConfirm = resolve
  })
}

function closeExecuteConfirm(ok: boolean) {
  executeConfirm.open = false
  resolveExecuteConfirm?.(ok)
  resolveExecuteConfirm = null
}

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

async function ensureSyncInitialized() {
  if (syncInitialized.value) return
  await initialize()
  if (state.isSyncing) currentPageSyncStarted.value = true
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
      workstationConfirmation.confirm({
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

  const ok = await askExecuteConfirm(Number(preflight?.estimated_impact || 0))
  if (!ok) return

  const result = await executeSync('pg')
  currentPageSyncStarted.value = Boolean(result.success || result.status === 'partial')
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
  void loadDepartments()
  const requestedTab = typeof route.query.tab === 'string' ? route.query.tab : ''
  const canOpenRequestedTab =
    (requestedTab === 'frontpageExtraction' && canManageFrontpageConfig.value) ||
    (requestedTab === 'llmConfig' && canManageLlmConfig.value) ||
    (requestedTab === 'llmObservability' && canViewLlmObservability.value) ||
    (requestedTab === 'accounts' && canManageAccounts.value)
  if (canOpenRequestedTab) {
    activeTab.value = requestedTab
  }
  if (!['llmConfig', 'llmObservability', 'accounts'].includes(activeTab.value)) {
    await ensureSyncInitialized()
  }
})

watch(activeTab, async (tab) => {
  if (['llmConfig', 'llmObservability', 'accounts'].includes(tab)) return
  await ensureSyncInitialized()
})

watch(hasPreflightPass, (isReady) => {
  if (!isReady) {
    syncScopeConfirmed.value = false
  }
})

onUnmounted(() => {
  closeExecuteConfirm(false)
  resetState()
})
</script>

<style>
@import './styles/workstation-v4-view.css';
</style>
<style scoped src="./styles/system-config.css"></style>
