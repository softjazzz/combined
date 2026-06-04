<template>
  <a-drawer
    :open="open"
    width="620"
    placement="right"
    class="qc-agent-drawer"
    :body-style="{ padding: 0, background: '#f8fbff' }"
    @close="handleClose"
  >
    <template #title>
      <div class="qc-agent-drawer__title">
        <div>
          <div class="qc-agent-drawer__heading">
            质控助手
          </div>
          <div class="qc-agent-drawer__subtitle">
            单病历只读质控，不写正式结果表
          </div>
        </div>
        <SafetyCertificateOutlined class="qc-agent-drawer__title-icon" />
      </div>
    </template>

    <div class="qc-agent-drawer__layout">
      <section class="qc-agent-context">
        <div class="qc-agent-context__label">
          当前上下文
        </div>
        <div class="qc-agent-context__value">
          {{ contextSummary }}
        </div>
      </section>

      <section class="qc-agent-shortcuts">
        <a-button
          v-for="shortcut in shortcutItems"
          :key="shortcut"
          size="small"
          class="qc-agent-shortcuts__button"
          @click="applyShortcut(shortcut)"
        >
          {{ shortcut }}
        </a-button>
      </section>

      <section
        class="qc-agent-chat"
        data-testid="qc-agent-chat-messages"
      >
        <div
          v-if="!hasMessages"
          class="qc-agent-empty"
        >
          <RobotOutlined class="qc-agent-empty__icon" />
          <div class="qc-agent-empty__title">
            输入一句质控请求
          </div>
          <div class="qc-agent-empty__desc">
            例如：对 visit_id=2298532 的查房记录做质控
          </div>
        </div>

        <article
          v-for="message in messages"
          :key="message.id"
          :class="['qc-agent-message', `qc-agent-message--${message.role}`]"
        >
          <div class="qc-agent-message__bubble">
            <template v-if="message.response">
              <AgentResponseCard
                :response="message.response"
                @confirm-candidate="handleConfirmCandidate"
              />
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

      <section class="qc-agent-input">
        <a-textarea
          v-model:value="draftMessage"
          data-testid="qc-agent-message-input"
          :auto-size="{ minRows: 3, maxRows: 5 }"
          placeholder="请输入自然语言质控请求，支持 visit_id、住院号、姓名或科室"
          :disabled="loading"
          @keydown.enter.exact.prevent="handleSend"
        />
        <div class="qc-agent-input__actions">
          <a-button
            size="small"
            :disabled="loading"
            @click="clear"
          >
            <ClearOutlined />
            清空
          </a-button>
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
import { computed, defineComponent, h, ref } from 'vue'
import {
  ClearOutlined,
  RobotOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'

import type {
  QCAgentCandidate,
  QCAgentChatResponse,
  QCAgentRuleIssue,
  QCAgentSkippedRule,
  QCAgentUserContext,
} from '@/api/qcAgent'
import { sanitizeQcAgentPayload, useQcAgentChat } from '../composables/useQcAgentChat'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  userContext?: QCAgentUserContext
  contextLabel?: string
}>()

const emit = defineEmits<{
  close: []
}>()

const shortcutItems = ['查房记录质控', '出院记录完整性', '用 WR-001 检查查房记录', '查看执行计划']
const draftMessage = ref('')

const { messages, loading, error, hasMessages, chat, confirmCandidate, clear } = useQcAgentChat()

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
  return '请输入 visit_id、住院号、姓名或科室'
})

function buildMessageFromShortcut(shortcut: string) {
  const visitId = String(safeUserContext.value.visit_id || '').trim()
  if (shortcut === '查看执行计划') return '对当前病历说明可执行的质控计划'
  if (shortcut === '出院记录完整性') {
    return visitId ? `对 visit_id=${visitId} 的出院记录做完整性质控` : '对出院记录做完整性质控'
  }
  if (shortcut === '用 WR-001 检查查房记录') {
    return visitId ? `用 WR-001 检查 visit_id=${visitId} 的查房记录` : '用 WR-001 检查查房记录'
  }
  return visitId ? `对 visit_id=${visitId} 的查房记录做质控` : '对查房记录做质控'
}

function applyShortcut(shortcut: string) {
  draftMessage.value = buildMessageFromShortcut(shortcut)
}

async function handleSend() {
  const message = draftMessage.value.trim()
  if (!message) return
  draftMessage.value = ''
  await chat(message, { userContext: safeUserContext.value })
}

async function handleConfirmCandidate(candidate: QCAgentCandidate) {
  await confirmCandidate(candidate, { userContext: safeUserContext.value })
}

function handleClose() {
  open.value = false
  emit('close')
}

function statusLabel(status: string) {
  if (status === 'completed') return '完成'
  if (status === 'needs_confirmation') return '待确认'
  if (status === 'needs_clarification') return '需澄清'
  if (status === 'unsupported') return '不支持'
  return status || '未知'
}

function safeArray<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value : []
}

function issueMessage(issue: QCAgentRuleIssue) {
  return issue.message || issue.description || issue.evidence_summary || '未返回问题描述'
}

function rawSummary(response: QCAgentChatResponse) {
  return JSON.stringify(
    sanitizeQcAgentPayload({
      status: response.status,
      parsed_intent: response.parsed_intent,
      plan: response.plan,
      result: response.result
        ? {
            qc_summary: response.result.qc_summary,
            document_selection_summary: response.result.document_selection_summary,
            selected_rule_count: response.result.selected_rules?.length,
            skipped_rule_count: response.result.skipped_rules?.length,
          }
        : undefined,
      warnings: response.warnings,
    }),
    null,
    2,
  )
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
      const result = response.result || {}
      const qcSummary = result.qc_summary || {}
      const issues = safeArray(result.issues?.length ? result.issues : result.results)
      const skippedRules = safeArray(result.skipped_rules)
      const warnings = [...safeArray(response.warnings), ...safeArray(result.warnings)]
      const plan = safeArray(response.plan)
      const candidates = safeArray(response.candidates)

      return h('div', { class: 'qc-agent-result-card' }, [
        h('div', { class: 'qc-agent-result-card__header' }, [
          h(
            'span',
            { class: `qc-agent-status qc-agent-status--${response.status}` },
            statusLabel(response.status),
          ),
          h(
            'span',
            { class: 'qc-agent-result-card__run' },
            response.run_id ? `run ${response.run_id.slice(0, 8)}` : '',
          ),
        ]),
        response.status === 'completed'
          ? h('div', { class: 'qc-agent-summary-grid' }, [
              h('div', { class: 'qc-agent-summary-item' }, [
                h('span', '问题数'),
                h('strong', String(qcSummary.issue_count ?? 0)),
              ]),
              h('div', { class: 'qc-agent-summary-item' }, [
                h('span', '通过数'),
                h('strong', String(qcSummary.passed_count ?? qcSummary.passed ?? 0)),
              ]),
              h('div', { class: 'qc-agent-summary-item' }, [
                h('span', '跳过数'),
                h('strong', String(qcSummary.skipped_count ?? skippedRules.length)),
              ]),
              h('div', { class: 'qc-agent-summary-item' }, [
                h('span', '规则数'),
                h('strong', String(qcSummary.rule_count ?? qcSummary.total_rules ?? 0)),
              ]),
            ])
          : null,
        plan.length
          ? h('div', { class: 'qc-agent-block' }, [
              h('div', { class: 'qc-agent-block__title' }, '执行计划'),
              h(
                'ol',
                { class: 'qc-agent-plan' },
                plan.map((item) =>
                  h('li', { class: 'qc-agent-plan__item' }, [
                    h('span', { class: 'qc-agent-plan__dot' }),
                    h('span', { class: 'qc-agent-plan__tool' }, item.tool_name || '-'),
                    h('span', { class: 'qc-agent-plan__status' }, item.status || ''),
                  ]),
                ),
              ),
            ])
          : null,
        candidates.length
          ? h('div', { class: 'qc-agent-block' }, [
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
                      ]
                        .filter(Boolean)
                        .join(' / '),
                    ),
                    h(
                      'button',
                      {
                        class: 'qc-agent-candidate__button',
                        type: 'button',
                        onClick: () => componentEmit('confirm-candidate', candidate),
                      },
                      '选择并继续',
                    ),
                  ]),
                ),
              ),
            ])
          : null,
        warnings.length
          ? h('div', { class: 'qc-agent-block' }, [
              h('div', { class: 'qc-agent-block__title' }, '提示'),
              h(
                'ul',
                { class: 'qc-agent-warnings' },
                warnings.map((item) => h('li', item)),
              ),
            ])
          : null,
        issues.length
          ? h('div', { class: 'qc-agent-block' }, [
              h('div', { class: 'qc-agent-block__title' }, '问题摘要'),
              h(
                'div',
                { class: 'qc-agent-issues' },
                issues.map((issue) =>
                  h('div', { class: 'qc-agent-issue' }, [
                    h('div', { class: 'qc-agent-issue__head' }, [
                      h('span', issue.rule_id || '-'),
                      h('em', issue.severity || 'normal'),
                    ]),
                    h('div', { class: 'qc-agent-issue__message' }, issueMessage(issue)),
                    issue.suggestion
                      ? h('div', { class: 'qc-agent-issue__suggestion' }, issue.suggestion)
                      : null,
                  ]),
                ),
              ),
            ])
          : null,
        skippedRules.length
          ? h('div', { class: 'qc-agent-block' }, [
              h('div', { class: 'qc-agent-block__title' }, '跳过规则'),
              h('div', { class: 'qc-agent-skipped-note' }, '当前只读 Agent 仅执行安全程序化规则。'),
              h(
                'div',
                { class: 'qc-agent-skipped-rules' },
                skippedRules
                  .slice(0, 8)
                  .map((rule) =>
                    h('div', { class: 'qc-agent-skipped-rule' }, [
                      h('span', rule.rule_id || '-'),
                      h('strong', rule.reason || '执行边界限制'),
                    ]),
                  ),
              ),
            ])
          : null,
        response.status === 'needs_clarification'
          ? h(
              'div',
              { class: 'qc-agent-suggestion' },
              '建议问法：对 visit_id=xxxx 的查房记录做质控',
            )
          : null,
        h('details', { class: 'qc-agent-raw' }, [
          h('summary', '查看原始摘要'),
          h('pre', rawSummary(response)),
        ]),
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
  color: #0f172a;
  font-size: 16px;
  font-weight: 800;
}

.qc-agent-drawer__subtitle {
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
}

.qc-agent-drawer__title-icon {
  color: #2563eb;
  font-size: 18px;
}

.qc-agent-drawer__layout {
  display: flex;
  min-height: calc(100vh - 56px);
  flex-direction: column;
  gap: 12px;
  padding: 14px;
}

.qc-agent-context,
.qc-agent-input,
.qc-agent-result-card {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
}

.qc-agent-context {
  padding: 12px 14px;
}

.qc-agent-context__label {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-context__value {
  margin-top: 4px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
}

.qc-agent-shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.qc-agent-shortcuts__button {
  border-color: #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
}

.qc-agent-chat {
  display: flex;
  min-height: 320px;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 4px;
}

.qc-agent-empty {
  display: flex;
  min-height: 220px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #64748b;
}

.qc-agent-empty__icon {
  color: #2563eb;
  font-size: 28px;
}

.qc-agent-empty__title {
  margin-top: 10px;
  color: #0f172a;
  font-size: 14px;
  font-weight: 800;
}

.qc-agent-empty__desc {
  margin-top: 4px;
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
  max-width: 92%;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.55;
}

.qc-agent-message--user .qc-agent-message__bubble {
  background: #2563eb;
  color: #ffffff;
}

.qc-agent-message--assistant .qc-agent-message__bubble,
.qc-agent-message--system .qc-agent-message__bubble {
  width: 100%;
  background: #ffffff;
  color: #0f172a;
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

.qc-agent-status {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 3px 9px;
  font-size: 12px;
  font-weight: 800;
}

.qc-agent-status--completed {
  background: #dcfce7;
  color: #166534;
}

.qc-agent-status--needs_confirmation,
.qc-agent-status--needs_clarification {
  background: #fef3c7;
  color: #92400e;
}

.qc-agent-status--unsupported {
  background: #fee2e2;
  color: #991b1b;
}

.qc-agent-result-card__run {
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
}

.qc-agent-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.qc-agent-summary-item {
  border-radius: 8px;
  background: #f8fafc;
  padding: 9px 8px;
}

.qc-agent-summary-item span {
  display: block;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.qc-agent-summary-item strong {
  color: #0f172a;
  font-size: 18px;
}

.qc-agent-block {
  margin-top: 12px;
}

.qc-agent-block__title {
  margin-bottom: 8px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
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
  background: #2563eb;
}

.qc-agent-plan__tool {
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 700;
}

.qc-agent-plan__status {
  color: #64748b;
  font-size: 12px;
}

.qc-agent-warnings li {
  border-radius: 8px;
  background: #fffbeb;
  padding: 7px 9px;
  color: #92400e;
  font-size: 12px;
}

.qc-agent-candidates,
.qc-agent-issues,
.qc-agent-skipped-rules {
  display: grid;
  gap: 8px;
}

.qc-agent-candidate,
.qc-agent-issue,
.qc-agent-skipped-rule {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 9px;
}

.qc-agent-candidate__main,
.qc-agent-issue__head,
.qc-agent-skipped-rule {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.qc-agent-candidate__main span,
.qc-agent-candidate__meta,
.qc-agent-issue__suggestion,
.qc-agent-skipped-rule strong {
  color: #64748b;
  font-size: 12px;
}

.qc-agent-candidate__button {
  margin-top: 8px;
  border: 0;
  border-radius: 7px;
  background: #2563eb;
  padding: 5px 9px;
  color: #ffffff;
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.qc-agent-issue__head span,
.qc-agent-skipped-rule span {
  color: #1d4ed8;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 800;
}

.qc-agent-issue__head em {
  color: #b45309;
  font-size: 12px;
  font-style: normal;
}

.qc-agent-issue__message {
  margin-top: 6px;
  color: #0f172a;
  font-size: 13px;
}

.qc-agent-skipped-note,
.qc-agent-suggestion {
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
}

.qc-agent-raw {
  margin-top: 12px;
  border-top: 1px solid #e2e8f0;
  padding-top: 10px;
}

.qc-agent-raw summary {
  color: #475569;
  cursor: pointer;
  font-size: 12px;
  font-weight: 800;
}

.qc-agent-raw pre {
  max-height: 220px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  padding: 10px;
  color: #dbeafe;
  font-size: 11px;
}

.qc-agent-error {
  border-radius: 8px;
  background: #fee2e2;
  padding: 8px 10px;
  color: #991b1b;
  font-size: 12px;
}

.qc-agent-input {
  padding: 10px;
}

.qc-agent-input__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
