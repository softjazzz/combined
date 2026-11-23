<template>
  <a-drawer
    :open="open"
    width="760"
    placement="right"
    class="qc-agent-drawer"
    :body-style="{ padding: 0, background: 'color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface))' }"
    @close="handleClose"
  >
    <template #title>
      <div class="qc-agent-drawer__title">
        <div>
          <div class="qc-agent-drawer__heading">
            质控助手
          </div>
          <div class="qc-agent-drawer__subtitle">
            单病历只读分析，支持质控、编码、入组模拟
          </div>
        </div>
        <SafetyCertificateOutlined class="qc-agent-drawer__title-icon" />
        <span class="qc-agent-drawer__safe">只读模式</span>
      </div>
    </template>

    <div class="qc-agent-panel">
      <section class="qc-agent-context">
        <div class="qc-agent-context__main">
          <div class="qc-agent-context__label">
            当前上下文
          </div>
          <div class="qc-agent-context__value">
            {{ contextSummary }}
          </div>
        </div>
        <div class="qc-agent-capabilities">
          <button
            v-for="capability in capabilityItems"
            :key="capability.key"
            type="button"
            :class="[
              'qc-agent-capability',
              { 'qc-agent-capability--active': currentCapability === capability.key },
            ]"
            @click="selectCapability(capability.key)"
          >
            {{ capability.label }}
          </button>
        </div>
      </section>

      <section
        v-if="showSqlbotPanel"
        class="qc-agent-sqlbot"
        data-testid="qc-agent-sqlbot-panel"
      >
        <div class="qc-agent-sqlbot__head">
          <div>
            <div class="qc-agent-sqlbot__eyebrow">
              SQLBot 问数
            </div>
            <div class="qc-agent-sqlbot__title">
              病案数据分析入口
            </div>
          </div>
          <div class="qc-agent-sqlbot__actions">
            <span
              :class="[
                'qc-agent-sqlbot__status',
                { 'qc-agent-sqlbot__status--enabled': sqlbotEnabled },
              ]"
            >
              {{ sqlbotStatusText }}
            </span>
            <button
              v-if="sqlbotPanelOpen"
              type="button"
              class="qc-agent-sqlbot__close"
              @click="sqlbotPanelOpen = false"
            >
              收起
            </button>
          </div>
        </div>
        <div
          v-if="sqlbotLoading"
          class="qc-agent-sqlbot__placeholder"
        >
          正在读取 SQLBot 配置...
        </div>
        <iframe
          v-else-if="sqlbotEnabled && sqlbotConfig?.embed_url"
          class="qc-agent-sqlbot__iframe"
          :src="sqlbotConfig.embed_url"
          title="SQLBot 问数"
        />
        <div
          v-else
          class="qc-agent-sqlbot__placeholder"
        >
          <strong>SQLBot 未配置</strong>
          <span>{{ sqlbotConfig?.message || sqlbotError || sqlbotFallbackMessage }}</span>
          <small>配置完成后，这里会以独立嵌入面板打开问数能力；现有质控、编码和入组流程不受影响。</small>
        </div>
      </section>

      <section
        class="qc-agent-workspace"
        data-testid="qc-agent-chat-messages"
      >
        <div
          v-if="!hasMessages"
          class="qc-agent-message qc-agent-message--assistant qc-agent-message--welcome"
        >
          <div class="qc-agent-message__avatar">
            AI
          </div>
          <div class="qc-agent-message__bubble">
            <div class="qc-agent-welcome__title">
              我可以帮你做单病历只读分析。
            </div>
            <div class="qc-agent-welcome__desc">
              你可以直接输入质控、编码或入组请求，系统会调用受控工具并返回结构化结果。
            </div>
            <div class="qc-agent-prompt-chips">
              <button
                v-for="suggestion in promptSuggestions"
                :key="suggestion.label"
                type="button"
                class="qc-agent-prompt-chip"
                @click="applyShortcut(suggestion)"
              >
                {{ suggestion.label }}
              </button>
            </div>
          </div>
        </div>

        <article
          v-for="message in messages"
          :key="message.id"
          :class="['qc-agent-message', `qc-agent-message--${message.role}`]"
        >
          <div
            v-if="message.role !== 'user'"
            class="qc-agent-message__avatar"
          >
            {{ message.role === 'system' ? '!' : 'AI' }}
          </div>
          <div class="qc-agent-message__bubble">
            <template v-if="message.response">
              <AgentResponseCard
                :response="message.response"
                @confirm-candidate="handleConfirmCandidate"
              />
              <div
                v-if="nextActionsForResponse(message.response).length"
                class="qc-agent-next-actions"
              >
                <button
                  v-for="action in nextActionsForResponse(message.response)"
                  :key="action.label"
                  type="button"
                  class="qc-agent-next-action"
                  @click="applyActionMessage(action)"
                >
                  {{ action.label }}
                </button>
              </div>
            </template>
            <template v-else>
              {{ message.content }}
            </template>
          </div>
        </article>
      </section>

      <section
        v-if="error"
        class="qc-agent-error"
      >
        {{ error }}
      </section>

      <section class="qc-agent-commandbar">
        <a-textarea
          v-model:value="draftMessage"
          data-testid="qc-agent-message-input"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          placeholder="输入质控、编码或入组请求，支持 visit_id、诊断名称、ICD 编码、DRG/DIP 查询"
          :disabled="loading"
          @keydown.enter.exact.prevent="handleSend"
        />
        <div class="qc-agent-commandbar__actions">
          <div class="qc-agent-commandbar__left">
            <a-button
              v-for="action in commandActions"
              :key="action.label"
              size="small"
              class="qc-agent-commandbar__button"
              :disabled="loading && action.kind !== 'clear'"
              @click="handleCommandAction(action.kind)"
            >
              {{ action.label }}
            </a-button>
          </div>
          <a-button
            type="primary"
            size="small"
            :loading="loading"
            data-testid="qc-agent-send-button"
            @click="handleSend"
          >
            <SendOutlined />
            发送
          </a-button>
        </div>
      </section>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { SafetyCertificateOutlined, SendOutlined } from '@ant-design/icons-vue'

import { sqlbotApi, type SQLBotConfigResponse } from '@/api/sqlbot'
import type {
  QCAgentCandidate,
  QCAgentChatResponse,
  QCAgentCodingSuggestionItem,
  QCAgentExecutedRule,
  QCAgentICDCandidate,
  QCAgentMatchedDocument,
  QCAgentRuleIssue,
  QCAgentRunResult,
  QCAgentSkippedRule,
  QCAgentUserContext,
} from '@/api/qcAgent'
import { sanitizeQcAgentPayload, useQcAgentChat } from '../composables/useQcAgentChat'

type AgentCapability = 'qc' | 'coding' | 'grouping' | 'analytics'
type NormalizedResultType =
  | 'qc_result'
  | 'qc_rules_result'
  | 'icd_search_result'
  | 'coding_suggestion_result'
  | 'drg_grouping_result'
  | 'dip_grouping_result'
  | 'clarification'
  | 'confirmation'
  | 'unsupported'
  | 'unknown'

interface ShortcutItem {
  label: string
  capability: AgentCapability
  build: (visitId: string) => string
}

interface ShortcutGroup {
  key: AgentCapability
  title: string
  items: ShortcutItem[]
}

interface CommandAction {
  label: string
  kind: AgentCapability | 'record' | 'clear'
}

interface AssistantAction {
  label: string
  capability: AgentCapability
  message: string
}

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  userContext?: QCAgentUserContext
  contextLabel?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const selectedCapability = ref<AgentCapability>('qc')
const draftMessage = ref('')
const sqlbotConfig = ref<SQLBotConfigResponse | null>(null)
const sqlbotLoading = ref(false)
const sqlbotError = ref('')
const sqlbotPanelOpen = ref(false)

const { messages, loading, error, hasMessages, lastResponse, chat, confirmCandidate, clear } =
  useQcAgentChat()

const capabilityItems: Array<{ key: AgentCapability; label: string }> = [
  { key: 'qc', label: '质控' },
  { key: 'coding', label: '编码' },
  { key: 'grouping', label: 'DRG/DIP' },
  { key: 'analytics', label: '问数' },
]

const commandActions: CommandAction[] = [
  { label: '规则', kind: 'qc' },
  { label: '编码', kind: 'coding' },
  { label: '入组', kind: 'grouping' },
  { label: '病历', kind: 'record' },
  { label: '问数', kind: 'analytics' },
  { label: '清空', kind: 'clear' },
]

const shortcutGroups: ShortcutGroup[] = [
  {
    key: 'qc',
    title: '质控',
    items: [
      {
        label: '查房记录质控',
        capability: 'qc',
        build: (visitId) =>
          visitId ? `对 visit_id=${visitId} 的查房记录做质控` : '对查房记录做质控',
      },
      {
        label: '出院记录完整性',
        capability: 'qc',
        build: (visitId) =>
          visitId ? `对 visit_id=${visitId} 的出院记录做完整性质控` : '对出院记录做完整性质控',
      },
      {
        label: '用 WR-001 检查',
        capability: 'qc',
        build: (visitId) =>
          visitId ? `用 WR-001 检查 visit_id=${visitId} 的查房记录` : '用 WR-001 检查查房记录',
      },
      {
        label: '查看执行计划',
        capability: 'qc',
        build: (visitId) =>
          visitId ? `对 visit_id=${visitId} 说明可执行的质控计划` : '说明可执行的质控计划',
      },
    ],
  },
  {
    key: 'coding',
    title: '编码',
    items: [
      {
        label: 'ICD 诊断编码查询',
        capability: 'coding',
        build: () => '查询 2型糖尿病 的 ICD 诊断编码',
      },
      {
        label: '手术操作编码查询',
        capability: 'coding',
        build: () => '查 腹腔镜胆囊切除术 的手术操作编码',
      },
      {
        label: '当前病历编码建议',
        capability: 'coding',
        build: (visitId) =>
          visitId ? `给 visit_id=${visitId} 推荐诊断和手术编码` : '给当前病历推荐诊断和手术编码',
      },
      {
        label: '编码映射医保版',
        capability: 'coding',
        build: () => '查询医保版高血压编码',
      },
    ],
  },
  {
    key: 'grouping',
    title: '入组',
    items: [
      {
        label: 'DRG 实时入组',
        capability: 'grouping',
        build: () => '用主诊断 K80.101 和手术 51.2101 做 DRG 入组',
      },
      {
        label: 'DIP 入组预测',
        capability: 'grouping',
        build: () => '用 I10.x01，年龄 65，住院 7 天，费用 8000 做 DIP 入组',
      },
      {
        label: '当前病历模拟入组',
        capability: 'grouping',
        build: (visitId) =>
          visitId ? `对 visit_id=${visitId} 做 DRG/DIP 模拟入组` : '对当前病历做 DRG/DIP 模拟入组',
      },
      {
        label: '解释入组依据',
        capability: 'grouping',
        build: () => '解释 DRG/DIP 入组依据和需要的主诊断、手术、年龄、费用参数',
      },
    ],
  },
  {
    key: 'analytics',
    title: '问数',
    items: [
      {
        label: '统计今天病案问题集中点',
        capability: 'analytics',
        build: () => '统计今天病案问题集中点',
      },
    ],
  },
]

const promptSuggestions: ShortcutItem[] = [
  shortcutGroups[0].items[0],
  { ...shortcutGroups[1].items[0], label: 'ICD 编码查询' },
  shortcutGroups[1].items[2],
  { ...shortcutGroups[2].items[2], label: 'DRG/DIP 模拟入组' },
  shortcutGroups[3].items[0],
]

const safeUserContext = computed(() => sanitizeQcAgentPayload(props.userContext || {}))

const contextSummary = computed(() => {
  if (props.contextLabel) return props.contextLabel
  const visitId = safeUserContext.value.visit_id
  if (visitId) {
    const name = safeUserContext.value.name || safeUserContext.value.patient_name || '当前病历'
    const department =
      safeUserContext.value.department || safeUserContext.value.dept || '未标注科室'
    return `${name} / ${department} / visit_id=${visitId}`
  }
  return '请输入 visit_id、住院号、患者姓名或科室'
})

const currentCapability = computed<AgentCapability>(() => {
  const responseCapability = capabilityFromResponse(lastResponse.value || undefined)
  if (responseCapability) return responseCapability
  return selectedCapability.value
})

const sqlbotEnabled = computed(() =>
  Boolean(sqlbotConfig.value?.enabled && sqlbotConfig.value?.embed_url),
)

const showSqlbotPanel = computed(
  () => selectedCapability.value === 'analytics' || sqlbotPanelOpen.value,
)

const sqlbotStatusText = computed(() => {
  if (sqlbotLoading.value) return '读取中'
  return sqlbotEnabled.value ? '已配置' : '待接入'
})

const sqlbotFallbackMessage = '请配置 SQLBOT_ENABLED=true 和 SQLBOT_EMBED_URL 后再使用问数能力。'

onMounted(() => {
  void loadSqlbotConfig()
})

function visitIdFromContext() {
  return String(safeUserContext.value.visit_id || '').trim()
}

function selectCapability(capability: AgentCapability) {
  selectedCapability.value = capability
  if (capability === 'analytics') {
    void openSqlbotPanel()
  }
}

function applyShortcut(shortcut: ShortcutItem) {
  selectedCapability.value = shortcut.capability
  if (shortcut.capability === 'analytics') {
    void openSqlbotPanel(shortcut.build(visitIdFromContext()))
    return
  }
  draftMessage.value = shortcut.build(visitIdFromContext())
}

function applyActionMessage(action: AssistantAction) {
  selectedCapability.value = action.capability
  draftMessage.value = action.message
}

function handleCommandAction(kind: CommandAction['kind']) {
  if (kind === 'clear') {
    clear()
    draftMessage.value = ''
    return
  }
  if (kind === 'record') {
    draftMessage.value = visitIdFromContext()
      ? `查看 visit_id=${visitIdFromContext()} 的病历可分析内容`
      : '根据 visit_id 查看病历可分析内容'
    return
  }
  if (kind === 'analytics') {
    selectedCapability.value = 'analytics'
    void openSqlbotPanel('统计今天病案问题集中点')
    return
  }
  selectedCapability.value = kind
  const defaultShortcut = shortcutGroups.find((group) => group.key === kind)?.items[0]
  if (defaultShortcut) draftMessage.value = defaultShortcut.build(visitIdFromContext())
}

async function handleSend() {
  const message = draftMessage.value.trim()
  if (!message) return
  selectedCapability.value = capabilityFromText(message)
  if (selectedCapability.value === 'analytics') {
    await openSqlbotPanel(message)
    return
  }
  draftMessage.value = ''
  await chat(message, { userContext: safeUserContext.value })
}

async function loadSqlbotConfig(force = false) {
  if (sqlbotConfig.value && !force) return sqlbotConfig.value
  sqlbotLoading.value = true
  sqlbotError.value = ''
  try {
    sqlbotConfig.value = await sqlbotApi.getConfig()
  } catch {
    sqlbotError.value = 'SQLBot 配置读取失败。'
    sqlbotConfig.value = {
      enabled: false,
      display_mode: 'disabled',
      message: 'SQLBot 配置读取失败，请确认后端服务和登录态正常。',
    }
  } finally {
    sqlbotLoading.value = false
  }
  return sqlbotConfig.value
}

async function openSqlbotPanel(fallbackMessage?: string) {
  selectedCapability.value = 'analytics'
  const config = await loadSqlbotConfig()
  if (config?.enabled && config.embed_url) {
    sqlbotPanelOpen.value = true
    draftMessage.value = ''
    return
  }
  sqlbotPanelOpen.value = false
  draftMessage.value = fallbackMessage || '统计今天病案问题集中点'
}

async function handleConfirmCandidate(candidate: QCAgentCandidate) {
  await confirmCandidate(candidate, { userContext: safeUserContext.value })
}

function nextActionsForResponse(response: QCAgentChatResponse): AssistantAction[] {
  const resultType = normalizeResultType(response)
  const visitId = visitIdFromContext()
  const visitText = visitId ? `visit_id=${visitId}` : '当前病历'

  if (resultType === 'qc_result') {
    const firstRule = firstIssueRuleId(response.result)
    return [
      {
        label: '查看执行计划',
        capability: 'qc',
        message: visitId ? `对 visit_id=${visitId} 说明可执行的质控计划` : '说明可执行的质控计划',
      },
      {
        label: '继续检查出院记录',
        capability: 'qc',
        message: `对 ${visitText} 的出院记录做完整性质控`,
      },
      {
        label: firstRule ? `解释 ${firstRule}` : '解释规则',
        capability: 'qc',
        message: firstRule
          ? `解释 ${firstRule} 的质控依据和处理建议`
          : '解释本次质控结果里的主要规则依据',
      },
    ]
  }

  if (resultType === 'qc_rules_result') {
    return [
      {
        label: '按这些规则质控',
        capability: 'qc',
        message: visitId
          ? `对 visit_id=${visitId} 的查房记录按相关规则做质控`
          : '对查房记录按相关规则做质控',
      },
      {
        label: '查看完整性规则',
        capability: 'qc',
        message: '列一下查房记录完整性质控规则',
      },
      {
        label: '出院记录规则',
        capability: 'qc',
        message: '列一下出院记录相关质控规则',
      },
    ]
  }

  if (resultType === 'icd_search_result' || resultType === 'coding_suggestion_result') {
    const firstCode = firstCandidateCode(response.result)
    return [
      {
        label: '继续查相近编码',
        capability: 'coding',
        message: firstCode ? `继续查询 ${firstCode} 的相近编码` : '继续查相近 ICD 编码',
      },
      {
        label: '用于 DRG/DIP 入组',
        capability: 'grouping',
        message: firstCode
          ? `用主诊断 ${firstCode} 做 DRG/DIP 模拟入组`
          : '用当前编码建议做 DRG/DIP 模拟入组',
      },
      {
        label: '当前病历编码建议',
        capability: 'coding',
        message: visitId
          ? `给 visit_id=${visitId} 推荐诊断和手术编码`
          : '给当前病历推荐诊断和手术编码',
      },
    ]
  }

  if (resultType === 'drg_grouping_result' || resultType === 'dip_grouping_result') {
    return [
      {
        label: '解释入组依据',
        capability: 'grouping',
        message: '解释本次 DRG/DIP 入组依据和风险提示',
      },
      {
        label: '查看编码建议',
        capability: 'coding',
        message: visitId
          ? `给 visit_id=${visitId} 推荐诊断和手术编码`
          : '给当前病历推荐诊断和手术编码',
      },
      {
        label: '重新模拟',
        capability: 'grouping',
        message: visitId
          ? `重新对 visit_id=${visitId} 做 DRG/DIP 模拟入组`
          : '重新做 DRG/DIP 模拟入组',
      },
    ]
  }

  return []
}

function handleClose() {
  open.value = false
  emit('close')
}

function capabilityFromText(text: string): AgentCapability {
  if (text.includes('问数') || text.includes('统计') || text.includes('集中点')) return 'analytics'
  if (/\b(?:DRG|DIP)\b/i.test(text) || text.includes('入组')) return 'grouping'
  if (text.includes('编码') || /\bICD\b/i.test(text)) return 'coding'
  return 'qc'
}

function capabilityFromResponse(response?: QCAgentChatResponse): AgentCapability | null {
  const capability = String(response?.parsed_intent?.capability || '')
  const resultType = normalizeResultType(response)
  if (capability.includes('icd') || resultType === 'icd_search_result') return 'coding'
  if (resultType === 'coding_suggestion_result') return 'coding'
  if (capability.includes('dip') || capability.includes('drg')) return 'grouping'
  if (resultType === 'drg_grouping_result' || resultType === 'dip_grouping_result')
    return 'grouping'
  if (resultType === 'qc_result' || resultType === 'qc_rules_result') return 'qc'
  return null
}

function normalizeResultType(response?: QCAgentChatResponse): NormalizedResultType {
  if (!response) return 'unknown'
  if (response.status === 'needs_confirmation') return 'confirmation'
  if (response.status === 'needs_clarification') return 'clarification'
  if (response.status === 'unsupported') return 'unsupported'
  const resultType = String(response.parsed_intent?.result_type || '')
  if (resultType === 'document_qc' || resultType === 'qc_result') return 'qc_result'
  if (resultType === 'qc_rules' || resultType === 'qc_rules_result') return 'qc_rules_result'
  if (resultType === 'icd_candidates' || resultType === 'icd_search_result') {
    return 'icd_search_result'
  }
  if (resultType === 'record_icd_suggestions' || resultType === 'coding_suggestion_result') {
    return 'coding_suggestion_result'
  }
  if (resultType === 'drg_group' || resultType === 'drg_grouping_result') {
    return 'drg_grouping_result'
  }
  if (resultType === 'dip_group' || resultType === 'dip_grouping_result') {
    return 'dip_grouping_result'
  }
  const result = response.result
  if (result?.qc_summary) return 'qc_result'
  if (result?.rules) return 'qc_rules_result'
  if (result?.candidates) return 'icd_search_result'
  if (result?.diagnosis_candidates || result?.procedure_candidates) {
    return 'coding_suggestion_result'
  }
  if (result?.drg_code || result?.adrg_code || result?.external_call) return 'drg_grouping_result'
  if (result?.dip_code || result?.dip_name) return 'dip_grouping_result'
  return 'unknown'
}

function statusLabel(status: string) {
  if (status === 'completed') return '完成'
  if (status === 'needs_confirmation') return '待确认'
  if (status === 'needs_clarification') return '需澄清'
  if (status === 'unsupported') return '不支持'
  return status || '未知'
}

function resultTypeLabel(type: NormalizedResultType) {
  if (type === 'qc_result') return '文书质控'
  if (type === 'qc_rules_result') return '规则目录'
  if (type === 'icd_search_result') return 'ICD 查询'
  if (type === 'coding_suggestion_result') return '编码建议'
  if (type === 'drg_grouping_result') return 'DRG 模拟'
  if (type === 'dip_grouping_result') return 'DIP 预测'
  if (type === 'confirmation') return '候选确认'
  if (type === 'clarification') return '澄清信息'
  if (type === 'unsupported') return '受控拒绝'
  return '智能分析'
}

function codeTypeLabel(value: string | undefined) {
  if (value === 'diagnosis') return '诊断'
  if (value === 'procedure') return '手术操作'
  if (value === 'all') return '全部'
  return value || '-'
}

function versionLabel(value: string | undefined) {
  if (value === 'insurance') return '医保版'
  if (value === 'clinical') return '国临版'
  return value || '-'
}

function safeArray<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value : []
}

function textValue(value: unknown, fallback = '-') {
  const text = String(value ?? '').trim()
  return text || fallback
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function formatNumber(value: unknown, fallback = '-') {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : fallback
}

function formatMoney(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)} 元` : '-'
}

function formatConfidence(value: unknown) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '-'
  return `${Math.round(value * 100)}%`
}

function uniqueTextItems(items: Array<string | undefined>) {
  const seen = new Set<string>()
  return items.filter((item): item is string => {
    const text = String(item || '').trim()
    if (!text || seen.has(text)) return false
    seen.add(text)
    return true
  })
}

function issueMessage(issue: QCAgentRuleIssue) {
  return issue.message || issue.description || issue.evidence_summary || '未返回问题描述'
}

function ruleStatusLabel(rule: QCAgentExecutedRule) {
  if (rule.status === 'passed' || rule.passed === true) return '通过'
  if (rule.status === 'failed' || rule.passed === false) return '未通过'
  return rule.status || '未知'
}

function ruleStatusClass(rule: QCAgentExecutedRule) {
  return rule.status === 'failed' || rule.passed === false
    ? 'qc-agent-rule-status--failed'
    : 'qc-agent-rule-status--passed'
}

function matchedDocumentSummary(documents: QCAgentMatchedDocument[] | undefined) {
  const items = safeArray(documents)
  if (!items.length) return '未返回文书元数据'
  const totalLength = items.reduce((sum, item) => sum + numberValue(item.text_length), 0)
  const types = uniqueTextItems(items.map((item) => item.document_type)).slice(0, 3)
  const typeText = types.length ? types.join('、') : '未标注文书类型'
  return `命中 ${items.length} 份文书，${typeText}，合计 ${totalLength} 字`
}

function skippedReasonLabel(rule: QCAgentSkippedRule) {
  if (rule.reason_label) return rule.reason_label
  if (rule.reason === 'requires_llm') return '需要受控 LLM 判断'
  if (rule.reason === 'unsupported_execution_mode') return '暂未接入只读程序化执行器'
  if (rule.reason === 'unknown_rule') return '规则目录未找到'
  if (rule.reason === 'not_applicable_document') return '不适用于当前文书类型'
  return rule.reason || '当前阶段未执行'
}

function skippedNextStep(rule: QCAgentSkippedRule) {
  if (rule.next_step) return rule.next_step
  if (rule.reason === 'requires_llm') return '需接入受控 LLM 规则执行器后判断。'
  if (rule.reason === 'unsupported_execution_mode') {
    return '需补充安全程序化 evaluator 或接入正式只读规则引擎。'
  }
  if (rule.reason === 'not_applicable_document') return '请更换文书类型或选择适用规则。'
  return '请由质控员复核规则适用性和执行方式。'
}

function executionStats(result: QCAgentRunResult | undefined) {
  const qcSummary = result?.qc_summary || {}
  const skippedRules = safeArray(result?.skipped_rules)
  const skippedCount = numberValue(qcSummary.skipped_count, skippedRules.length)
  const issueCount = numberValue(qcSummary.issue_count)
  const passedCount = numberValue(qcSummary.passed_count, numberValue(qcSummary.passed))
  const selectedRuleCount = numberValue(
    qcSummary.rule_count,
    safeArray(result?.selected_rules).length || passedCount + issueCount + skippedCount,
  )
  const executedRuleCount = numberValue(qcSummary.total_rules, passedCount + issueCount)
  return {
    issueCount,
    passedCount,
    skippedCount,
    selectedRuleCount,
    executedRuleCount,
    isPartial: skippedCount > 0 || selectedRuleCount > executedRuleCount,
  }
}

function highRiskIssueCount(result: QCAgentRunResult | undefined) {
  const issueSource = safeArray(result?.issues?.length ? result?.issues : result?.results)
  return issueSource.filter((issue) => {
    if (issue.passed === true || issue.status === 'passed') return false
    const severity = String(issue.severity || '').toLowerCase()
    return ['high', 'critical', '高风险', '严重'].some((keyword) => severity.includes(keyword))
  }).length
}

function firstIssueRuleId(result: QCAgentRunResult | undefined) {
  const issueSource = safeArray(result?.issues?.length ? result?.issues : result?.results)
  return issueSource.find((issue) => issue.rule_id)?.rule_id || ''
}

function firstCandidateCode(result: QCAgentRunResult | undefined) {
  const directCode = safeArray(result?.candidates).find((candidate) => candidate.code)?.code
  if (directCode) return directCode
  const diagnosisCode = safeArray(result?.diagnosis_candidates)
    .flatMap((item) => safeArray(item.candidates))
    .find((candidate) => candidate.code)?.code
  if (diagnosisCode) return diagnosisCode
  return safeArray(result?.procedure_candidates)
    .flatMap((item) => safeArray(item.candidates))
    .find((candidate) => candidate.code)?.code
}

function conclusionText(result: QCAgentRunResult | undefined) {
  const stats = executionStats(result)
  if (stats.issueCount > 0) return `发现 ${stats.issueCount} 条问题，需复核处理。`
  if (stats.skippedCount > 0) {
    return `已执行 ${stats.passedCount} 条规则，暂未发现问题；另有 ${stats.skippedCount} 条规则因当前只读执行边界未执行。`
  }
  return `已执行 ${stats.passedCount} 条规则，未发现问题。`
}

function fieldRow(label: string, value: unknown) {
  return h('div', { class: 'qc-agent-field' }, [
    h('span', { class: 'qc-agent-field__label' }, label),
    h('strong', { class: 'qc-agent-field__value' }, textValue(value)),
  ])
}

function metricItem(label: string, value: unknown) {
  return h('div', { class: 'qc-agent-summary-item' }, [
    h('span', label),
    h('strong', textValue(value, '0')),
  ])
}

function renderPlan(response: QCAgentChatResponse) {
  const plan = safeArray(response.plan)
  if (!plan.length) return null
  return h('div', { class: 'qc-agent-block' }, [
    h('div', { class: 'qc-agent-block__title' }, '执行计划'),
    h(
      'ol',
      { class: 'qc-agent-plan' },
      plan.map((item) =>
        h('li', { class: 'qc-agent-plan__item' }, [
          h('span', { class: 'qc-agent-plan__dot' }),
          h('span', { class: 'qc-agent-plan__tool' }, item.tool_name || '-'),
          h('span', { class: 'qc-agent-plan__separator' }, '·'),
          h('span', { class: 'qc-agent-plan__status' }, item.status || ''),
        ]),
      ),
    ),
  ])
}

function renderWarnings(response: QCAgentChatResponse) {
  const warnings = uniqueTextItems([
    ...safeArray(response.warnings),
    ...safeArray(response.result?.warnings),
  ])
  if (!warnings.length) return null
  return h('div', { class: 'qc-agent-block' }, [
    h('div', { class: 'qc-agent-block__title' }, '提示'),
    h(
      'ul',
      { class: 'qc-agent-warnings' },
      warnings.map((item) => h('li', item)),
    ),
  ])
}

function renderCandidates(
  response: QCAgentChatResponse,
  emit: (event: 'confirm-candidate', candidate: QCAgentCandidate) => void,
) {
  const candidates = safeArray(response.candidates)
  if (!candidates.length) return null
  return h('div', { class: 'qc-agent-block' }, [
    h('div', { class: 'qc-agent-block__title' }, '候选病历'),
    h(
      'div',
      { class: 'qc-agent-candidates' },
      candidates.map((candidate) =>
        h('div', { class: 'qc-agent-candidate' }, [
          h('div', { class: 'qc-agent-candidate__main' }, [
            h('strong', candidate.patient_name || '未命名患者'),
            h('span', `visit_id=${candidate.visit_id || '-'}`),
          ]),
          h(
            'div',
            { class: 'qc-agent-candidate__meta' },
            [
              candidate.department || '未标注科室',
              candidate.discharge_date ? `出院 ${candidate.discharge_date}` : '',
              candidate.mr_no ? `病案号 ${candidate.mr_no}` : '',
            ]
              .filter(Boolean)
              .join(' / '),
          ),
          h(
            'button',
            {
              class: 'qc-agent-candidate__button',
              type: 'button',
              onClick: () => emit('confirm-candidate', candidate),
            },
            '选择并继续',
          ),
        ]),
      ),
    ),
  ])
}

function renderQCResult(result: QCAgentRunResult | undefined) {
  const issueSource = safeArray(result?.issues?.length ? result?.issues : result?.results)
  const issues = issueSource.filter((issue) => issue.passed !== true && issue.status !== 'passed')
  const executedRules = safeArray(result?.executed_rules)
  const skippedRules = safeArray(result?.skipped_rules)
  const stats = executionStats(result)
  const highRiskCount = highRiskIssueCount(result)

  return [
    h('div', { class: 'qc-agent-conclusion' }, [
      h('div', { class: 'qc-agent-conclusion__label' }, '本次结论'),
      h('div', { class: 'qc-agent-conclusion__text' }, conclusionText(result)),
    ]),
    h('div', { class: 'qc-agent-summary-grid' }, [
      metricItem('发现问题', stats.issueCount),
      metricItem('高风险', highRiskCount),
      metricItem('执行规则', stats.executedRuleCount),
    ]),
    h('div', { class: 'qc-agent-block' }, [
      h('div', { class: 'qc-agent-block__title' }, '已发现问题'),
      issues.length
        ? h(
            'div',
            { class: 'qc-agent-issues' },
            issues.map((issue) =>
              h('div', { class: 'qc-agent-issue' }, [
                h('div', { class: 'qc-agent-issue__head' }, [
                  h('span', issue.rule_id || '-'),
                  h('em', issue.severity || 'normal'),
                ]),
                h('div', { class: 'qc-agent-issue__message' }, issueMessage(issue)),
                issue.evidence_summary
                  ? h('div', { class: 'qc-agent-issue__evidence' }, [
                      h('strong', '证据：'),
                      h('span', issue.evidence_summary),
                    ])
                  : null,
                issue.suggestion
                  ? h('div', { class: 'qc-agent-issue__suggestion' }, [
                      h('strong', '建议：'),
                      h('span', issue.suggestion),
                    ])
                  : null,
              ]),
            ),
          )
        : h('div', { class: 'qc-agent-empty-note' }, '已执行规则暂未发现问题。'),
    ]),
    executedRules.length
      ? h('div', { class: 'qc-agent-block' }, [
          h('div', { class: 'qc-agent-block__title' }, '已执行规则'),
          h(
            'div',
            { class: 'qc-agent-executed-rules' },
            executedRules.slice(0, 6).map((rule) => renderExecutedRule(rule)),
          ),
          executedRules.length > 6
            ? h('details', { class: 'qc-agent-more-rules' }, [
                h('summary', `展开其余 ${executedRules.length - 6} 条已执行规则`),
                h(
                  'div',
                  { class: 'qc-agent-executed-rules qc-agent-executed-rules--more' },
                  executedRules.slice(6).map((rule) => renderExecutedRule(rule)),
                ),
              ])
            : null,
        ])
      : null,
    skippedRules.length
      ? h('div', { class: 'qc-agent-block' }, [
          h('div', { class: 'qc-agent-block__title' }, '未执行规则'),
          h(
            'div',
            { class: 'qc-agent-skipped-note' },
            '这些规则已被选中，但当前即时质控模式未执行；需要正式规则引擎或 LLM 能力后才能判断。',
          ),
          h(
            'div',
            { class: 'qc-agent-skipped-rules' },
            skippedRules
              .slice(0, 8)
              .map((rule) =>
                h('div', { class: 'qc-agent-skipped-rule' }, [
                  h('div', { class: 'qc-agent-skipped-rule__head' }, [
                    h('span', rule.rule_id || '-'),
                    h('strong', rule.rule_name || skippedReasonLabel(rule)),
                  ]),
                  h('div', { class: 'qc-agent-skipped-rule__reason' }, [
                    h('strong', skippedReasonLabel(rule)),
                    h('span', skippedNextStep(rule)),
                  ]),
                ]),
              ),
          ),
        ])
      : null,
  ]
}

function renderExecutedRule(rule: QCAgentExecutedRule) {
  return h('div', { class: 'qc-agent-executed-rule' }, [
    h('div', { class: 'qc-agent-rule-card__head' }, [
      h('span', { class: 'qc-agent-rule-card__id' }, rule.rule_id || '-'),
      h('em', { class: ['qc-agent-rule-status', ruleStatusClass(rule)] }, ruleStatusLabel(rule)),
    ]),
    h('div', { class: 'qc-agent-rule-card__name' }, rule.rule_name || '未命名规则'),
    rule.explanation ? h('div', { class: 'qc-agent-rule-card__text' }, rule.explanation) : null,
    rule.evidence_summary
      ? h('div', { class: 'qc-agent-rule-card__evidence' }, [
          h('strong', '证据：'),
          h('span', rule.evidence_summary),
        ])
      : null,
    h('div', { class: 'qc-agent-rule-card__meta' }, matchedDocumentSummary(rule.matched_documents)),
  ])
}

function renderICDSearchResult(result: QCAgentRunResult | undefined) {
  const candidates = safeArray(result?.candidates)
  const visibleCandidates = candidates.slice(0, 6)
  const overflowCandidates = candidates.slice(6)
  const topCandidate = candidates[0]
  return [
    h('div', { class: 'qc-agent-icd-overview' }, [
      h('div', { class: 'qc-agent-icd-overview__main' }, [
        h('span', { class: 'qc-agent-icd-overview__eyebrow' }, 'ICD 候选检索'),
        h(
          'strong',
          { class: 'qc-agent-icd-overview__query' },
          textValue(result?.query, '未识别查询词'),
        ),
        h('div', { class: 'qc-agent-icd-overview__meta' }, [
          h('span', codeTypeLabel(result?.code_type)),
          h('span', versionLabel(result?.version)),
          h('span', `${textValue(result?.returned ?? candidates.length, '0')} 条候选`),
        ]),
      ]),
      topCandidate
        ? h('div', { class: 'qc-agent-icd-overview__best' }, [
            h('span', '首位匹配'),
            h('strong', topCandidate.code || '-'),
            h('small', topCandidate.name || '未命名编码'),
          ])
        : null,
    ]),
    h('div', { class: 'qc-agent-block' }, [
      h('div', { class: 'qc-agent-block__head' }, [
        h('div', { class: 'qc-agent-block__title' }, '候选编码'),
        h('div', { class: 'qc-agent-block__hint' }, '按名称匹配度排序，结果仅供编码员复核'),
      ]),
      candidates.length
        ? h('div', { class: 'qc-agent-code-list' }, [
            ...visibleCandidates.map((candidate, index) =>
              renderCodeCandidate(candidate, true, index + 1),
            ),
            overflowCandidates.length
              ? h('details', { class: 'qc-agent-more-codes' }, [
                  h('summary', `展开其余 ${overflowCandidates.length} 条候选编码`),
                  h(
                    'div',
                    { class: 'qc-agent-code-list qc-agent-code-list--more' },
                    overflowCandidates.map((candidate, index) =>
                      renderCodeCandidate(candidate, true, visibleCandidates.length + index + 1),
                    ),
                  ),
                ])
              : null,
          ])
        : h('div', { class: 'qc-agent-empty-note' }, '未返回 ICD 候选编码。'),
    ]),
  ]
}

function renderCodeCandidate(candidate: QCAgentICDCandidate, withActions = false, rank?: number) {
  const confidence = formatConfidence(candidate.confidence)
  const mappingText = `${candidate.mapped_code || '-'} ${candidate.mapped_name || ''}`.trim()
  return h('div', { class: 'qc-agent-code-card' }, [
    h('div', { class: 'qc-agent-code-card__rank' }, rank ? String(rank).padStart(2, '0') : ''),
    h('div', { class: 'qc-agent-code-card__body' }, [
      h('div', { class: 'qc-agent-code-card__head' }, [
        h('div', { class: 'qc-agent-code-card__identity' }, [
          h('span', { class: 'qc-agent-code-card__code' }, candidate.code || '-'),
          h('em', versionLabel(candidate.version)),
        ]),
        h('span', { class: confidenceClass(candidate.confidence) }, confidence),
      ]),
      h('div', { class: 'qc-agent-code-card__name' }, candidate.name || '未命名编码'),
      h('div', { class: 'qc-agent-code-card__meta' }, [
        metaPill('类型', codeTypeLabel(candidate.type)),
        metaPill('匹配', matchTypeLabel(candidate.match_type)),
      ]),
      candidate.mapped_code || candidate.mapped_name
        ? h('div', { class: 'qc-agent-code-card__mapping' }, [
            h('span', '映射'),
            h('strong', mappingText),
          ])
        : null,
      withActions
        ? h('div', { class: 'qc-agent-code-card__actions' }, [
            h('button', { type: 'button' }, '复制编码'),
            h('button', { type: 'button' }, '用于入组'),
            h('button', { type: 'button' }, '查相近编码'),
          ])
        : null,
    ]),
  ])
}

function confidenceClass(value: unknown) {
  const score = typeof value === 'number' && Number.isFinite(value) ? value : 0
  return [
    'qc-agent-code-card__confidence',
    score >= 0.9
      ? 'qc-agent-code-card__confidence--high'
      : score >= 0.75
        ? 'qc-agent-code-card__confidence--medium'
        : 'qc-agent-code-card__confidence--low',
  ]
}

function matchTypeLabel(value: string | undefined) {
  if (value === 'exact_code') return '编码精确'
  if (value === 'exact_name') return '名称精确'
  if (value === 'name_contains') return '名称包含'
  if (value === 'semantic') return '语义召回'
  return value || '-'
}

function metaPill(label: string, value: unknown) {
  return h('span', { class: 'qc-agent-meta-pill' }, [
    h('small', label),
    h('strong', textValue(value)),
  ])
}

function renderCodingSuggestionResult(result: QCAgentRunResult | undefined) {
  return [
    h('div', { class: 'qc-agent-result-summary' }, [
      fieldRow('病历', recordSummaryText(result?.record_summary)),
      fieldRow('主要诊断候选', safeArray(result?.diagnosis_candidates).length),
      fieldRow('手术/操作候选', safeArray(result?.procedure_candidates).length),
      fieldRow('口径', '仅为编码建议，不写入正式首页或结算表'),
    ]),
    renderCodingSuggestionGroup('主要诊断候选', safeArray(result?.diagnosis_candidates)),
    renderCodingSuggestionGroup('手术/操作候选', safeArray(result?.procedure_candidates)),
  ]
}

function recordSummaryText(summary: Record<string, unknown> | undefined) {
  if (!summary) return '-'
  const name = textValue(summary.patient_name || summary.name, '未命名患者')
  const visitId = textValue(summary.visit_id, '-')
  const department = textValue(summary.department || summary.dept, '未标注科室')
  return `${name} / ${department} / visit_id=${visitId}`
}

function renderCodingSuggestionGroup(title: string, items: QCAgentCodingSuggestionItem[]) {
  return h('div', { class: 'qc-agent-block' }, [
    h('div', { class: 'qc-agent-block__title' }, title),
    items.length
      ? h(
          'div',
          { class: 'qc-agent-coding-list' },
          items.map((item) =>
            h('div', { class: 'qc-agent-coding-item' }, [
              h('div', { class: 'qc-agent-coding-item__head' }, [
                h('strong', item.name || item.existing_code || '未命名项目'),
                h('span', `置信度 ${formatConfidence(item.confidence)}`),
              ]),
              h('div', { class: 'qc-agent-coding-item__meta' }, [
                h('span', `已有编码：${item.existing_code || '-'}`),
                h('span', `来源：${sourceLabel(item.source)}`),
                item.low_confidence ? h('em', '低置信度') : null,
              ]),
              h(
                'div',
                { class: 'qc-agent-code-list qc-agent-code-list--compact' },
                safeArray(item.candidates)
                  .slice(0, 3)
                  .map((candidate) => renderCodeCandidate(candidate)),
              ),
            ]),
          ),
        )
      : h('div', { class: 'qc-agent-empty-note' }, '未返回候选。'),
  ])
}

function sourceLabel(source: string | undefined) {
  if (source === 'structured_context') return '病案首页/结构化上下文'
  if (source === 'explicit_record_field') return '诊断表/手术表/文书显式字段'
  return source || '-'
}

function renderQCRulesResult(result: QCAgentRunResult | undefined) {
  const rules = safeArray(result?.rules)
  const filters = result?.filters || {}
  const visibleRules = rules.slice(0, 8)
  const overflowRules = rules.slice(8)
  return [
    h('div', { class: 'qc-agent-rule-overview' }, [
      h('div', { class: 'qc-agent-rule-overview__main' }, [
        h('span', '规则目录'),
        h('strong', `${textValue(result?.returned ?? rules.length, '0')} 条匹配规则`),
        h('small', `规则库共 ${textValue(result?.total, '0')} 条`),
      ]),
      h('div', { class: 'qc-agent-rule-overview__filters' }, [
        metaPill('文书', ruleFilterLabel(filters.document_alias || filters.document_type)),
        metaPill('质控点', qcPointLabel(filters.qc_point_type)),
      ]),
    ]),
    h('div', { class: 'qc-agent-block' }, [
      h('div', { class: 'qc-agent-block__head' }, [
        h('div', { class: 'qc-agent-block__title' }, '质控规则'),
        h('div', { class: 'qc-agent-block__hint' }, '仅展示规则摘要，不包含 prompt 或病历正文'),
      ]),
      rules.length
        ? h(
            'ol',
            { class: 'qc-agent-catalog-rules' },
            visibleRules.map((rule, index) => renderCatalogRule(rule, index + 1)),
          )
        : h('div', { class: 'qc-agent-empty-note' }, '未返回匹配规则。'),
      overflowRules.length
        ? h('details', { class: 'qc-agent-more-rules' }, [
            h('summary', `展开其余 ${overflowRules.length} 条规则`),
            h(
              'ol',
              { class: 'qc-agent-catalog-rules qc-agent-catalog-rules--more' },
              overflowRules.map((rule, index) =>
                renderCatalogRule(rule, visibleRules.length + index + 1),
              ),
            ),
          ])
        : null,
    ]),
  ]
}

function renderCatalogRule(rule: Record<string, unknown>, rank: number) {
  const aliases = safeArray(rule.document_aliases as string[] | undefined)
  const severity = String(rule.severity || '').toLowerCase()
  return h('li', { class: 'qc-agent-catalog-rule' }, [
    h('div', { class: 'qc-agent-catalog-rule__rank' }, String(rank).padStart(2, '0')),
    h('div', { class: 'qc-agent-catalog-rule__body' }, [
      h('div', { class: 'qc-agent-catalog-rule__head' }, [
        h('div', { class: 'qc-agent-catalog-rule__identity' }, [
          h('span', { class: 'qc-agent-catalog-rule__id' }, textValue(rule.rule_id)),
          h('strong', textValue(rule.rule_name, '未命名规则')),
        ]),
        h(
          'em',
          { class: ['qc-agent-catalog-rule__severity', severityClass(severity)] },
          severityLabel(severity),
        ),
      ]),
      rule.description
        ? h('div', { class: 'qc-agent-catalog-rule__description' }, textValue(rule.description))
        : null,
      h('div', { class: 'qc-agent-catalog-rule__meta' }, [
        metaPill('质控点', qcPointLabel(rule.qc_point_type)),
        metaPill('文书', aliases.length ? aliases.map(docAliasLabel).join('、') : '未标注'),
        metaPill('执行', executionModeLabel(rule.execution_mode)),
        rule.requires_llm ? metaPill('能力', '需 LLM') : null,
      ]),
    ]),
  ])
}

function ruleFilterLabel(value: unknown) {
  if (Array.isArray(value)) return value.length ? value.join('、') : '全部'
  return docAliasLabel(textValue(value, '全部'))
}

function docAliasLabel(value: unknown) {
  const text = String(value || '').trim()
  const labels: Record<string, string> = {
    admission: '入院记录',
    first_course: '首次病程',
    ward_round: '查房记录',
    course: '病程记录',
    discharge: '出院记录',
    consultation: '会诊记录',
    mdt: '多学科会诊',
    lab_exam: '检查检验',
    surgery: '手术记录',
    anesthesia: '麻醉记录',
    daily_course: '日常病程',
  }
  return labels[text] || text || '全部'
}

function qcPointLabel(value: unknown) {
  const text = String(value || '').trim()
  const labels: Record<string, string> = {
    completeness: '完整性',
    timeliness: '时效性',
    consistency: '一致性',
    diagnosis_evidence: '诊断依据',
    clinical_reasoning: '临床推理',
    treatment_rationality: '治疗合理性',
    order_consistency: '医嘱一致性',
    coding: '编码',
    signature: '签名',
    critical_value: '危急值',
    special_risk: '特殊风险',
    documentation_quality: '文书质量',
  }
  return labels[text] || text || '全部'
}

function executionModeLabel(value: unknown) {
  const text = String(value || '').trim()
  const labels: Record<string, string> = {
    programmatic: '程序化',
    builtin: '内置',
    llm: 'LLM 判断',
    unknown: '未接入',
  }
  return labels[text] || text || '未接入'
}

function severityLabel(value: unknown) {
  const text = String(value || '')
    .trim()
    .toLowerCase()
  const labels: Record<string, string> = {
    error: '错误',
    warning: '警告',
    info: '提示',
    critical: '严重',
    high: '高风险',
    medium: '中风险',
    low: '低风险',
  }
  return labels[text] || textValue(value, '规则')
}

function severityClass(value: string) {
  if (['error', 'critical', 'high'].includes(value))
    return 'qc-agent-catalog-rule__severity--danger'
  if (['warning', 'medium'].includes(value)) return 'qc-agent-catalog-rule__severity--warning'
  return 'qc-agent-catalog-rule__severity--info'
}

function renderDRGResult(result: QCAgentRunResult | undefined) {
  const input = result?.input_summary || {}
  return [
    h('div', { class: 'qc-agent-result-summary' }, [
      fieldRow('主诊断编码', input.primary_diagnosis_code),
      fieldRow('其他诊断数量', input.secondary_diagnosis_count),
      fieldRow('手术操作数量', input.procedure_count),
      fieldRow('模拟状态', result?.fallback ? '降级模式' : result?.success ? '成功' : '未入组'),
    ]),
    h('div', { class: 'qc-agent-grouping-card' }, [
      fieldRow(
        'ADRG',
        `${textValue(result?.adrg_code)} ${textValue(result?.adrg_name, '')}`.trim(),
      ),
      fieldRow('DRG', `${textValue(result?.drg_code)} ${textValue(result?.drg_name, '')}`.trim()),
      fieldRow('权重', formatNumber(result?.weight)),
      fieldRow('基准支付', formatMoney(result?.baseline_payment)),
      fieldRow('盈亏/风险提示', formatMoney(result?.profit_margin)),
      fieldRow(
        '编码映射信息',
        `${textValue(result?.mapped_code)} ${textValue(result?.mapped_code_name, '')}`.trim(),
      ),
      fieldRow('入组逻辑摘要', result?.grouping_logic),
      result?.error_summary ? fieldRow('降级原因', result.error_summary) : null,
    ]),
  ]
}

function renderDIPResult(result: QCAgentRunResult | undefined) {
  const input = result?.input_summary || {}
  return [
    h('div', { class: 'qc-agent-result-summary' }, [
      fieldRow('城市', input.city_name),
      fieldRow('主诊断编码', input.pdx_code),
      fieldRow('手术编码数量', input.proc_count),
      fieldRow('预测状态', result?.success ? '成功' : '未入组'),
    ]),
    h('div', { class: 'qc-agent-grouping-card' }, [
      fieldRow('DIP 编码', result?.dip_code),
      fieldRow('DIP 名称', result?.dip_name),
      fieldRow('病种类型', result?.dip_type),
      fieldRow('入组路径', result?.grouping_path),
      fieldRow(
        '费用/住院日摘要',
        `${formatMoney(input.total_fee)} / ${formatNumber(input.los)} 天`,
      ),
    ]),
  ]
}

function renderStateNotice(response: QCAgentChatResponse) {
  const type = normalizeResultType(response)
  if (type === 'clarification') {
    return h('div', { class: 'qc-agent-state-note qc-agent-state-note--warning' }, [
      h('strong', '需要补充信息'),
      h('span', '请补充 visit_id、文书类型、诊断/手术名称或入组所需编码后继续。'),
      h('span', '建议问法：对 visit_id=xxxx 的查房记录做质控，或查询 2型糖尿病 ICD 编码。'),
    ])
  }
  if (type === 'unsupported') {
    return h('div', { class: 'qc-agent-state-note qc-agent-state-note--danger' }, [
      h('strong', '受控拒绝'),
      h('span', '当前助手只做只读分析，不执行删除、写入、导出或正式结果持久化。'),
    ])
  }
  return null
}

function recognizedTaskText(response: QCAgentChatResponse, resultType: NormalizedResultType) {
  const capability = currentCapabilityLabelFromResponse(response, resultType)
  const parts = [capability]
  if (resultType === 'qc_result') parts.push('文书质控')
  if (resultType === 'qc_rules_result') parts.push('规则目录')
  if (resultType === 'icd_search_result') parts.push('ICD 查询')
  if (resultType === 'coding_suggestion_result') parts.push('当前病历编码建议')
  if (resultType === 'drg_grouping_result') parts.push('DRG 模拟入组')
  if (resultType === 'dip_grouping_result') parts.push('DIP 入组预测')
  const visitId = String(
    response.parsed_intent?.visit_id || response.result?.record_summary?.visit_id || '',
  ).trim()
  if (visitId) parts.push(`visit_id=${visitId}`)
  return `已识别：${parts.filter(Boolean).join(' · ')}`
}

function currentCapabilityLabelFromResponse(
  response: QCAgentChatResponse,
  resultType: NormalizedResultType,
) {
  const capability = capabilityFromResponse(response)
  if (capability === 'coding') return '编码任务'
  if (capability === 'grouping') return '入组任务'
  if (capability === 'qc') return '质控任务'
  if (resultType === 'qc_rules_result') return '质控任务'
  if (resultType === 'icd_search_result' || resultType === 'coding_suggestion_result') {
    return '编码任务'
  }
  if (resultType === 'drg_grouping_result' || resultType === 'dip_grouping_result') {
    return '入组任务'
  }
  return '只读分析'
}

const AgentResponseCard = defineComponent({
  name: 'AgentResponseCard',
  props: {
    response: {
      type: Object as () => QCAgentChatResponse,
      required: true,
    },
  },
  emits: ['confirm-candidate'],
  setup(componentProps, { emit: componentEmit }) {
    return () => {
      const response = componentProps.response
      const result = response.result
      const resultType = normalizeResultType(response)
      const stats = executionStats(result)
      const resultContent =
        resultType === 'qc_result'
          ? renderQCResult(result)
          : resultType === 'qc_rules_result'
            ? renderQCRulesResult(result)
            : resultType === 'icd_search_result'
              ? renderICDSearchResult(result)
              : resultType === 'coding_suggestion_result'
                ? renderCodingSuggestionResult(result)
                : resultType === 'drg_grouping_result'
                  ? renderDRGResult(result)
                  : resultType === 'dip_grouping_result'
                    ? renderDIPResult(result)
                    : null

      return h('div', { class: 'qc-agent-result-card' }, [
        h('div', { class: 'qc-agent-result-card__header' }, [
          h('div', { class: 'qc-agent-result-card__identity' }, [
            h(
              'div',
              { class: 'qc-agent-result-card__eyebrow' },
              recognizedTaskText(response, resultType),
            ),
            h('div', { class: 'qc-agent-result-card__badges' }, [
              h(
                'span',
                { class: `qc-agent-status qc-agent-status--${response.status}` },
                statusLabel(response.status),
              ),
              h('span', { class: 'qc-agent-result-type' }, resultTypeLabel(resultType)),
              response.status === 'completed' && resultType === 'qc_result'
                ? h(
                    'span',
                    {
                      class: [
                        'qc-agent-execution-tag',
                        stats.isPartial
                          ? 'qc-agent-execution-tag--partial'
                          : 'qc-agent-execution-tag--complete',
                      ],
                    },
                    stats.isPartial ? '部分执行' : '完整执行',
                  )
                : null,
              resultType === 'drg_grouping_result' && result?.fallback
                ? h(
                    'span',
                    { class: 'qc-agent-execution-tag qc-agent-execution-tag--partial' },
                    '降级模式',
                  )
                : null,
            ]),
          ]),
          h(
            'span',
            { class: 'qc-agent-result-card__run' },
            response.run_id ? `run ${response.run_id.slice(0, 8)}` : '',
          ),
        ]),
        renderStateNotice(response),
        renderCandidates(response, componentEmit),
        resultContent,
        renderPlan(response),
        renderWarnings(response),
      ])
    }
  },
})
</script>

<style scoped>
.qc-agent-drawer__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.qc-agent-drawer__heading {
  color: var(--mq-text-primary);
  font-size: 16px;
  font-weight: 700;
}

.qc-agent-drawer__subtitle {
  margin-top: 2px;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 500;
}

.qc-agent-drawer__title-icon {
  color: var(--mq-brand-600);
  font-size: 18px;
}

.qc-agent-panel {
  display: flex;
  min-height: calc(100vh - 56px);
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
}

.qc-agent-context,
.qc-agent-shortcuts,
.qc-agent-commandbar,
.qc-agent-result-card {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 12px;
  background: var(--mq-bg-surface);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.qc-agent-context {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
}

.qc-agent-context__label {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-context__value {
  margin-top: 4px;
  color: var(--mq-text-primary);
  font-size: 13px;
  font-weight: 700;
}

.qc-agent-capabilities {
  display: flex;
  flex-shrink: 0;
  gap: 6px;
}

.qc-agent-capability {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 999px;
  background: var(--mq-bg-surface);
  padding: 5px 10px;
  color: var(--mq-text-tertiary);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-capability--active {
  border-color: var(--mq-brand-200);
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
}

.qc-agent-shortcuts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}

.qc-agent-shortcut-group__title {
  margin-bottom: 8px;
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-shortcut-group__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qc-agent-shortcuts__button {
  border-color: color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 8px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  font-weight: 700;
}

.qc-agent-workspace {
  display: flex;
  min-height: 360px;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 2px;
}

.qc-agent-empty {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.qc-agent-empty-card {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 12px;
  background: var(--mq-bg-surface);
  padding: 14px;
}

.qc-agent-empty-card__title {
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 700;
}

.qc-agent-empty-card__desc {
  margin-top: 6px;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  line-height: 1.55;
}

.qc-agent-empty-card__list {
  display: grid;
  gap: 5px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.qc-agent-empty-card__list li {
  color: var(--mq-neutral-text);
  font-size: 12px;
}

.qc-agent-message {
  display: flex;
}

.qc-agent-message--user {
  justify-content: flex-end;
}

.qc-agent-message--assistant,
.qc-agent-message--system {
  justify-content: flex-start;
}

.qc-agent-message__bubble {
  max-width: 94%;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.55;
}

.qc-agent-message--user .qc-agent-message__bubble {
  background: var(--mq-brand-600);
  color: var(--mq-bg-surface);
}

.qc-agent-message--assistant .qc-agent-message__bubble,
.qc-agent-message--system .qc-agent-message__bubble {
  width: 100%;
  background: var(--mq-bg-surface);
  color: var(--mq-text-primary);
}

.qc-agent-result-card {
  padding: 12px;
}

.qc-agent-result-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.qc-agent-result-card__badges {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.qc-agent-status,
.qc-agent-result-type,
.qc-agent-execution-tag {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-status--completed {
  background: color-mix(in srgb, var(--mq-success-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-success-text) 55%, var(--mq-text-primary));
}

.qc-agent-status--needs_confirmation,
.qc-agent-status--needs_clarification {
  background: color-mix(in srgb, var(--mq-warning-icon) 14%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.qc-agent-status--unsupported {
  background: color-mix(in srgb, var(--mq-danger-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
}

.qc-agent-result-type {
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
}

.qc-agent-execution-tag--partial {
  background: color-mix(in srgb, var(--mq-warning-icon) 17%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.qc-agent-execution-tag--complete {
  background: color-mix(in srgb, var(--mq-brand-600) 11%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-brand-700) 90%, var(--mq-text-primary));
}

.qc-agent-result-card__run {
  color: var(--mq-text-tertiary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.qc-agent-conclusion,
.qc-agent-state-note {
  margin-top: 12px;
  border: 1px solid color-mix(in srgb, var(--mq-warning-icon) 31%, var(--mq-bg-surface));
  border-radius: 12px;
  background: var(--mq-warning-bg);
  padding: 10px;
}

.qc-agent-conclusion__label,
.qc-agent-state-note strong {
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-conclusion__text,
.qc-agent-state-note span {
  display: block;
  margin-top: 4px;
  color: color-mix(in srgb, var(--mq-warning-text) 25%, var(--mq-text-primary));
  font-size: 13px;
  font-weight: 700;
  line-height: 1.55;
}

.qc-agent-state-note--danger {
  border-color: color-mix(in srgb, var(--mq-danger-icon) 23%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-danger-icon) 7%, var(--mq-bg-surface));
}

.qc-agent-state-note--danger strong,
.qc-agent-state-note--danger span {
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
}

.qc-agent-summary-grid,
.qc-agent-result-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.qc-agent-summary-item,
.qc-agent-field,
.qc-agent-grouping-card {
  border-radius: 10px;
  background: color-mix(in srgb, var(--mq-neutral-text) 3%, var(--mq-bg-surface));
  padding: 9px 8px;
}

.qc-agent-summary-item span,
.qc-agent-field__label {
  display: block;
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 700;
}

.qc-agent-summary-item strong,
.qc-agent-field__value {
  display: block;
  margin-top: 3px;
  color: var(--mq-text-primary);
  font-size: 15px;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.qc-agent-summary-item strong {
  font-size: 18px;
}

.qc-agent-grouping-card {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.qc-agent-block {
  margin-top: 12px;
}

.qc-agent-block__title {
  margin-bottom: 8px;
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-plan,
.qc-agent-warnings {
  margin: 0;
  padding: 0;
  list-style: none;
}

.qc-agent-plan__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 0;
}

.qc-agent-plan__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--mq-brand-600);
}

.qc-agent-plan__tool {
  color: var(--mq-text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-plan__status {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.qc-agent-warnings li {
  border-radius: 10px;
  background: color-mix(in srgb, var(--mq-warning-icon) 8%, var(--mq-bg-surface));
  padding: 7px 9px;
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
  font-size: 12px;
}

.qc-agent-candidates,
.qc-agent-issues,
.qc-agent-executed-rules,
.qc-agent-skipped-rules,
.qc-agent-code-list,
.qc-agent-coding-list {
  display: grid;
  gap: 8px;
}

.qc-agent-code-list--compact {
  margin-top: 8px;
}

.qc-agent-candidate,
.qc-agent-issue,
.qc-agent-executed-rule,
.qc-agent-skipped-rule,
.qc-agent-code-card,
.qc-agent-coding-item {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 10px;
  background: color-mix(in srgb, var(--mq-neutral-text) 3%, var(--mq-bg-surface));
  padding: 9px;
}

.qc-agent-candidate__main,
.qc-agent-issue__head,
.qc-agent-rule-card__head,
.qc-agent-skipped-rule__head,
.qc-agent-code-card__head,
.qc-agent-coding-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.qc-agent-candidate__main span,
.qc-agent-candidate__meta,
.qc-agent-empty-note,
.qc-agent-issue__evidence,
.qc-agent-issue__suggestion,
.qc-agent-rule-card__evidence,
.qc-agent-rule-card__meta,
.qc-agent-rule-card__text,
.qc-agent-skipped-rule__reason,
.qc-agent-code-card__meta,
.qc-agent-code-card__mapping,
.qc-agent-coding-item__meta {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.qc-agent-candidate__button {
  margin-top: 8px;
  border: 0;
  border-radius: 8px;
  background: var(--mq-brand-600);
  padding: 5px 9px;
  color: var(--mq-bg-surface);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-issue__head span,
.qc-agent-rule-card__id,
.qc-agent-skipped-rule__head span,
.qc-agent-code-card__code {
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-issue__head em,
.qc-agent-rule-status,
.qc-agent-code-card__head em,
.qc-agent-coding-item__meta em {
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-warning-icon) 14%, var(--mq-bg-surface));
  padding: 2px 7px;
  color: color-mix(in srgb, var(--mq-warning-text) 89%, var(--mq-text-primary));
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.qc-agent-rule-status--passed {
  background: color-mix(in srgb, var(--mq-success-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-success-text) 55%, var(--mq-text-primary));
}

.qc-agent-rule-status--failed {
  background: color-mix(in srgb, var(--mq-danger-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
}

.qc-agent-issue__message,
.qc-agent-rule-card__name,
.qc-agent-skipped-rule__head strong,
.qc-agent-code-card__name,
.qc-agent-coding-item__head strong {
  margin-top: 6px;
  color: var(--mq-text-primary);
  font-size: 13px;
  font-weight: 700;
}

.qc-agent-issue__evidence,
.qc-agent-issue__suggestion,
.qc-agent-rule-card__evidence,
.qc-agent-rule-card__meta,
.qc-agent-rule-card__text,
.qc-agent-skipped-rule__reason,
.qc-agent-code-card__meta,
.qc-agent-code-card__mapping,
.qc-agent-coding-item__meta {
  margin-top: 6px;
  line-height: 1.55;
}

.qc-agent-code-card__meta,
.qc-agent-coding-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qc-agent-issue__evidence strong,
.qc-agent-issue__suggestion strong,
.qc-agent-rule-card__evidence strong,
.qc-agent-skipped-rule__reason strong,
.qc-agent-code-card__mapping strong {
  margin-right: 4px;
  color: var(--mq-neutral-text);
}

.qc-agent-skipped-rule__reason {
  display: grid;
  gap: 2px;
}

.qc-agent-rule-overview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 12px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
  padding: 12px;
}

.qc-agent-rule-overview__main {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.qc-agent-rule-overview__main span,
.qc-agent-rule-overview__main small {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-rule-overview__main strong {
  color: var(--mq-text-primary);
  font-size: 18px;
  font-weight: 700;
}

.qc-agent-rule-overview__filters,
.qc-agent-catalog-rule__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qc-agent-catalog-rules {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.qc-agent-catalog-rule {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 10px;
  background: var(--mq-bg-surface);
  padding: 10px;
}

.qc-agent-catalog-rule__rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-catalog-rule__body {
  display: grid;
  gap: 7px;
  min-width: 0;
}

.qc-agent-catalog-rule__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.qc-agent-catalog-rule__identity {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.qc-agent-catalog-rule__id {
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-catalog-rule__identity strong {
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 850;
  line-height: 1.45;
}

.qc-agent-catalog-rule__severity {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  line-height: 1.2;
}

.qc-agent-catalog-rule__severity--danger {
  background: color-mix(in srgb, var(--mq-danger-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
}

.qc-agent-catalog-rule__severity--warning {
  background: color-mix(in srgb, var(--mq-warning-icon) 14%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-warning-text) 70%, var(--mq-text-primary));
}

.qc-agent-catalog-rule__severity--info {
  background: color-mix(in srgb, var(--mq-brand-600) 11%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-brand-700) 90%, var(--mq-text-primary));
}

.qc-agent-catalog-rule__description {
  color: var(--mq-neutral-text);
  font-size: 13px;
  line-height: 1.65;
}

.qc-agent-code-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.qc-agent-code-card__actions button {
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 8px;
  background: var(--mq-bg-surface);
  padding: 4px 8px;
  color: var(--mq-brand-600);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-more-rules {
  margin-top: 8px;
}

.qc-agent-more-rules summary {
  color: var(--mq-brand-600);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-executed-rules--more {
  margin-top: 8px;
}

.qc-agent-skipped-note {
  margin-bottom: 8px;
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.qc-agent-raw {
  margin-top: 12px;
  border-top: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  padding-top: 10px;
}

.qc-agent-raw summary {
  color: var(--mq-neutral-text);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-raw pre {
  max-height: 220px;
  overflow: auto;
  border-radius: 10px;
  background: var(--mq-text-primary);
  padding: 10px;
  color: color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  font-size: 11px;
}

.qc-agent-error {
  border-radius: 10px;
  background: color-mix(in srgb, var(--mq-danger-icon) 15%, var(--mq-bg-surface));
  padding: 8px 10px;
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
  font-size: 12px;
}

.qc-agent-commandbar {
  position: sticky;
  bottom: 0;
  padding: 10px;
}

.qc-agent-commandbar :deep(textarea) {
  border-radius: 10px;
}

.qc-agent-commandbar__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}

.qc-agent-commandbar__left {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qc-agent-commandbar__button {
  border-radius: 8px;
  color: var(--mq-neutral-text);
  font-weight: 700;
}

.qc-agent-drawer__safe {
  display: inline-flex;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--mq-success-icon) 33%, var(--mq-bg-surface));
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-success-icon) 4%, var(--mq-bg-surface));
  padding: 3px 8px;
  color: color-mix(in srgb, var(--mq-success-text) 83%, var(--mq-text-primary));
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-panel {
  gap: 10px;
  padding: 12px 14px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
}

.qc-agent-context {
  gap: 10px;
  border-radius: 14px;
  padding: 9px 12px;
  box-shadow: none;
}

.qc-agent-context__main {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.qc-agent-context__label {
  flex: 0 0 auto;
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.qc-agent-context__value {
  min-width: 0;
  margin-top: 0;
  overflow: hidden;
  color: var(--mq-text-primary);
  font-size: 13px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-agent-capability {
  padding: 4px 9px;
  font-size: 12px;
}

.qc-agent-workspace {
  min-height: 420px;
  gap: 14px;
  padding: 4px 2px 10px;
}

.qc-agent-message {
  align-items: flex-start;
  gap: 9px;
}

.qc-agent-message__avatar {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  align-items: center;
  justify-content: center;
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 50%;
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  font-size: 11px;
  font-weight: 700;
}

.qc-agent-message--user {
  justify-content: flex-end;
}

.qc-agent-message--user .qc-agent-message__bubble {
  max-width: min(78%, 520px);
  border: 1px solid var(--mq-brand-200);
  border-radius: 18px 18px 4px;
  background: var(--mq-brand-50);
  color: var(--mq-text-primary);
  font-size: 14px;
  line-height: 1.65;
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.08);
}

.qc-agent-message--assistant,
.qc-agent-message--system {
  justify-content: flex-start;
}

.qc-agent-message--assistant .qc-agent-message__bubble,
.qc-agent-message--system .qc-agent-message__bubble {
  width: auto;
  max-width: min(92%, 650px);
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  border-radius: 18px 18px 18px 4px;
  background: var(--mq-bg-surface);
  color: var(--mq-text-primary);
  font-size: 14px;
  line-height: 1.65;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
}

.qc-agent-message--system .qc-agent-message__bubble {
  border-color: color-mix(in srgb, var(--mq-danger-icon) 23%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-danger-icon) 7%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-danger-text) 66%, var(--mq-text-primary));
}

.qc-agent-message--welcome .qc-agent-message__bubble {
  width: min(92%, 650px);
}

.qc-agent-welcome__title {
  color: var(--mq-text-primary);
  font-size: 15px;
  font-weight: 700;
}

.qc-agent-welcome__desc {
  margin-top: 4px;
  color: var(--mq-text-tertiary);
  font-size: 13px;
  line-height: 1.6;
}

.qc-agent-sqlbot {
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 16px;
  background: var(--mq-bg-surface);
  box-shadow: 0 14px 34px rgba(37, 99, 235, 0.08);
}

.qc-agent-sqlbot__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  padding: 12px 14px;
}

.qc-agent-sqlbot__eyebrow {
  color: var(--mq-brand-600);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.qc-agent-sqlbot__title {
  margin-top: 2px;
  color: var(--mq-text-primary);
  font-size: 15px;
  font-weight: 850;
}

.qc-agent-sqlbot__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.qc-agent-sqlbot__status {
  border: 1px solid color-mix(in srgb, var(--mq-warning-icon) 31%, var(--mq-bg-surface));
  border-radius: 999px;
  background: var(--mq-warning-bg);
  padding: 4px 9px;
  color: color-mix(in srgb, var(--mq-warning-text) 89%, var(--mq-text-primary));
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-sqlbot__status--enabled {
  border-color: color-mix(in srgb, var(--mq-success-icon) 33%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-success-icon) 4%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-success-text) 83%, var(--mq-text-primary));
}

.qc-agent-sqlbot__close {
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
  padding: 4px 10px;
  color: var(--mq-brand-700);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-sqlbot__iframe {
  display: block;
  width: 100%;
  height: min(62vh, 620px);
  min-height: 420px;
  border: 0;
  border-radius: 0 0 16px 16px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
}

.qc-agent-sqlbot__placeholder {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 20px 22px;
  color: var(--mq-text-tertiary);
  font-size: 13px;
  line-height: 1.6;
}

.qc-agent-sqlbot__placeholder strong {
  color: var(--mq-text-primary);
  font-size: 15px;
}

.qc-agent-sqlbot__placeholder small {
  color: var(--mq-text-tertiary);
  font-size: 12px;
}

.qc-agent-prompt-chips,
.qc-agent-next-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.qc-agent-prompt-chip,
.qc-agent-next-action {
  border: 1px solid var(--mq-brand-200);
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
  padding: 6px 10px;
  color: var(--mq-brand-700);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  transition:
    border-color 0.18s ease,
    background 0.18s ease,
    color 0.18s ease;
}

.qc-agent-prompt-chip:hover,
.qc-agent-next-action:hover {
  border-color: var(--mq-brand-600);
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-brand-700) 78%, var(--mq-text-primary));
}

.qc-agent-next-actions {
  border-top: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  padding-top: 10px;
}

.qc-agent-result-card {
  border: 0;
  padding: 0;
  box-shadow: none;
}

.qc-agent-result-card__header {
  align-items: flex-start;
  border-bottom: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  padding-bottom: 10px;
}

.qc-agent-result-card__identity {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.qc-agent-result-card__eyebrow {
  color: var(--mq-text-primary);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
}

.qc-agent-status,
.qc-agent-result-type,
.qc-agent-execution-tag {
  padding: 3px 8px;
  font-size: 11px;
}

.qc-agent-conclusion,
.qc-agent-state-note {
  border-color: color-mix(in srgb, var(--mq-warning-icon) 31%, var(--mq-bg-surface));
  border-radius: 12px;
  background: var(--mq-warning-bg);
  padding: 9px 10px;
}

.qc-agent-summary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.qc-agent-result-summary {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.qc-agent-summary-item,
.qc-agent-field,
.qc-agent-grouping-card {
  border: 1px solid color-mix(in srgb, var(--mq-neutral-text) 9%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
}

.qc-agent-summary-item strong {
  font-size: 20px;
}

.qc-agent-block__title {
  font-size: 13px;
}

.qc-agent-candidate,
.qc-agent-issue,
.qc-agent-executed-rule,
.qc-agent-skipped-rule,
.qc-agent-code-card,
.qc-agent-coding-item {
  border-color: color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  background: var(--mq-bg-surface);
}

.qc-agent-issue,
.qc-agent-code-card,
.qc-agent-coding-item {
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.03);
}

.qc-agent-commandbar {
  position: sticky;
  bottom: 0;
  border-radius: 16px;
  padding: 10px;
  box-shadow: 0 -12px 28px rgba(15, 23, 42, 0.06);
}

.qc-agent-commandbar :deep(textarea) {
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.65;
}

.qc-agent-commandbar__button {
  border-radius: 999px;
  padding-inline: 10px;
}

.qc-agent-commandbar :deep(.ant-btn-primary) {
  height: 30px;
  border-radius: 999px;
  font-weight: 700;
}

@media (max-width: 860px) {
  .qc-agent-shortcuts,
  .qc-agent-empty {
    grid-template-columns: 1fr;
  }

  .qc-agent-context,
  .qc-agent-commandbar__actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .qc-agent-summary-grid,
  .qc-agent-result-summary,
  .qc-agent-grouping-card {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

<style>
.qc-agent-drawer .qc-agent-result-card {
  display: grid;
  gap: 12px;
  width: min(100%, 590px);
  color: var(--mq-text-primary);
}

.qc-agent-drawer .qc-agent-result-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid color-mix(in srgb, var(--mq-neutral-text) 13%, var(--mq-bg-surface));
  padding-bottom: 10px;
}

.qc-agent-drawer .qc-agent-result-card__identity {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.qc-agent-drawer .qc-agent-result-card__eyebrow {
  color: var(--mq-text-primary);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
}

.qc-agent-drawer .qc-agent-result-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.qc-agent-drawer .qc-agent-status,
.qc-agent-drawer .qc-agent-result-type,
.qc-agent-drawer .qc-agent-execution-tag {
  display: inline-flex;
  align-items: center;
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  padding: 3px 8px;
  color: var(--mq-brand-700);
  font-size: 11px;
  font-weight: 850;
  line-height: 1.2;
}

.qc-agent-drawer .qc-agent-result-card__run {
  flex: 0 0 auto;
  color: var(--mq-text-tertiary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  font-weight: 700;
}

.qc-agent-drawer .qc-agent-result-card__body {
  display: grid;
  gap: 12px;
}

.qc-agent-drawer .qc-agent-icd-overview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 12px;
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.98), rgba(255, 255, 255, 0.98));
  padding: 14px;
}

.qc-agent-drawer .qc-agent-icd-overview__main {
  min-width: 0;
}

.qc-agent-drawer .qc-agent-icd-overview__eyebrow {
  display: inline-flex;
  width: fit-content;
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  padding: 3px 8px;
  color: var(--mq-brand-700);
  font-size: 11px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-icd-overview__query {
  display: block;
  margin-top: 8px;
  color: var(--mq-text-primary);
  font-size: 20px;
  font-weight: 850;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.qc-agent-drawer .qc-agent-icd-overview__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.qc-agent-drawer .qc-agent-icd-overview__meta span {
  border: 1px solid var(--mq-brand-200);
  border-radius: 999px;
  background: var(--mq-bg-surface);
  padding: 4px 9px;
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 750;
}

.qc-agent-drawer .qc-agent-icd-overview__best {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  border-left: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  padding-left: 14px;
}

.qc-agent-drawer .qc-agent-icd-overview__best span {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-icd-overview__best strong {
  margin-top: 4px;
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 17px;
  font-weight: 700;
}

.qc-agent-drawer .qc-agent-icd-overview__best small {
  margin-top: 3px;
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.45;
}

.qc-agent-drawer .qc-agent-block {
  display: grid;
  gap: 9px;
}

.qc-agent-drawer .qc-agent-block__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.qc-agent-drawer .qc-agent-block__title {
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-block__hint {
  color: var(--mq-text-tertiary);
  font-size: 12px;
  font-weight: 650;
  text-align: right;
}

.qc-agent-drawer .qc-agent-code-list {
  display: grid;
  gap: 10px;
}

.qc-agent-drawer .qc-agent-code-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 14px;
  background: var(--mq-bg-surface);
  padding: 12px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.035);
}

.qc-agent-drawer .qc-agent-code-card__rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-drawer .qc-agent-code-card__body {
  min-width: 0;
}

.qc-agent-drawer .qc-agent-code-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.qc-agent-drawer .qc-agent-code-card__identity {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.qc-agent-drawer .qc-agent-code-card__code {
  color: var(--mq-brand-700);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0;
}

.qc-agent-drawer .qc-agent-code-card__head em {
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
  padding: 3px 8px;
  color: var(--mq-brand-700);
  font-size: 11px;
  font-style: normal;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-code-card__confidence {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-drawer .qc-agent-code-card__confidence--high {
  background: color-mix(in srgb, var(--mq-success-icon) 15%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-success-text) 71%, var(--mq-text-primary));
}

.qc-agent-drawer .qc-agent-code-card__confidence--medium {
  background: color-mix(in srgb, var(--mq-brand-600) 11%, var(--mq-bg-surface));
  color: var(--mq-brand-700);
}

.qc-agent-drawer .qc-agent-code-card__confidence--low {
  background: color-mix(in srgb, var(--mq-warning-icon) 14%, var(--mq-bg-surface));
  color: color-mix(in srgb, var(--mq-warning-text) 89%, var(--mq-text-primary));
}

.qc-agent-drawer .qc-agent-code-card__name {
  margin-top: 7px;
  color: var(--mq-text-primary);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
}

.qc-agent-drawer .qc-agent-code-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}

.qc-agent-drawer .qc-agent-meta-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--mq-neutral-text) 9%, var(--mq-bg-surface));
  padding: 4px 8px;
}

.qc-agent-drawer .qc-agent-meta-pill small {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 750;
}

.qc-agent-drawer .qc-agent-meta-pill strong {
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-drawer .qc-agent-code-card__mapping {
  display: grid;
  gap: 3px;
  margin-top: 9px;
  border-left: 2px solid var(--mq-brand-200);
  padding-left: 9px;
}

.qc-agent-drawer .qc-agent-code-card__mapping span {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-code-card__mapping strong {
  color: var(--mq-neutral-text);
  font-size: 12px;
  font-weight: 750;
  line-height: 1.45;
}

.qc-agent-drawer .qc-agent-code-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
}

.qc-agent-drawer .qc-agent-code-card__actions button {
  border: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
  border-radius: 999px;
  background: var(--mq-bg-surface);
  padding: 5px 10px;
  color: var(--mq-brand-600);
  cursor: pointer;
  font-size: 12px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-code-card__actions button:hover {
  border-color: color-mix(in srgb, var(--mq-brand-600) 46%, var(--mq-bg-surface));
  background: color-mix(in srgb, var(--mq-brand-600) 6%, var(--mq-bg-surface));
}

.qc-agent-drawer .qc-agent-more-codes {
  border: 1px dashed var(--mq-brand-200);
  border-radius: 14px;
  background: color-mix(in srgb, var(--mq-brand-600) 3%, var(--mq-bg-surface));
  padding: 9px;
}

.qc-agent-drawer .qc-agent-more-codes summary {
  color: var(--mq-brand-700);
  cursor: pointer;
  font-size: 12px;
  font-weight: 850;
}

.qc-agent-drawer .qc-agent-code-list--more {
  margin-top: 9px;
}

@media (max-width: 860px) {
  .qc-agent-drawer .qc-agent-icd-overview {
    grid-template-columns: 1fr;
  }

  .qc-agent-drawer .qc-agent-icd-overview__best {
    border-top: 1px solid color-mix(in srgb, var(--mq-brand-600) 14%, var(--mq-bg-surface));
    border-left: 0;
    padding-top: 10px;
    padding-left: 0;
  }

  .qc-agent-drawer .qc-agent-code-card {
    grid-template-columns: 34px minmax(0, 1fr);
    gap: 9px;
  }
}
</style>
