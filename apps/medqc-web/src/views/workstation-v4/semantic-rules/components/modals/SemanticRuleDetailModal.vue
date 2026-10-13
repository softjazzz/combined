<template>
  <a-modal
    :open="open"
    title="规则详情"
    width="960px"
    :footer="null"
    centered
    class="semantic-modal"
    @update:open="emit('update:open', $event)"
  >
    <div
      v-if="rule"
      class="detail-wrap"
    >
      <div class="detail-summary">
        <div class="detail-summary-head">
          <div class="detail-title-block">
            <span class="detail-kicker">质控规则</span>
            <h3 class="detail-title">
              {{ isLuxianRule ? luxianPolicyTitle : rule.name }}
            </h3>
          </div>
          <span class="detail-code">{{ rule.rule_code || rule.rule_id }}</span>
        </div>
        <p
          v-if="!isLuxianRule"
          class="detail-desc"
        >
          {{ rule.description || '暂无描述' }}
        </p>
      </div>

      <a-descriptions
        v-if="!isLuxianRule"
        :column="2"
        size="small"
        class="detail-descriptions"
      >
        <a-descriptions-item label="分类">
          {{ getCategoryZh(rule.category) }}
        </a-descriptions-item>
        <a-descriptions-item label="复杂度">
          <span class="tag tag-plain">{{ rule.complexity }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="缺陷级别">
          <span class="tag tag-danger">{{ getSeverityZh(rule.defect_level) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="扣分">
          {{ rule.score_deduction }} 分
        </a-descriptions-item>
        <a-descriptions-item label="适用文书">
          <div class="doc-list">
            <span
              v-for="doc in rule.applicable_documents"
              :key="doc"
              class="doc-pill"
            >
              {{ getDocTypeZh(doc) }}
            </span>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div
        v-if="isLuxianRule"
        class="luxian-panel"
      >
        <div class="luxian-section">
          <h4>客户规则口径</h4>
          <p v-if="customerPolicy">
            {{ customerPolicy.summary }}
          </p>
          <p
            v-else
            class="muted"
          >
            规则口径暂未同步
          </p>
        </div>

        <div
          v-if="engineJudgment"
          class="luxian-section engine-section"
        >
          <h4>引擎判定说明</h4>
          <p
            v-if="engineWithheldReason"
            class="engine-withheld"
          >
            {{ engineWithheldReason }}
          </p>
          <template v-else-if="engineDetail">
            <p
              v-if="engineDetail.method"
              class="engine-method"
            >
              {{ engineDetail.method }}
            </p>
            <div class="engine-block">
              <span class="engine-label">何时判定</span>
              <p>{{ engineDetail.trigger }}</p>
            </div>
            <div class="engine-block">
              <span class="engine-label">判定步骤</span>
              <ol class="engine-steps">
                <li
                  v-for="(step, index) in engineDetail.steps"
                  :key="index"
                >
                  {{ step }}
                </li>
              </ol>
            </div>
            <div
              v-if="engineOutcomes.length"
              class="engine-block"
            >
              <span class="engine-label">结论含义</span>
              <ul class="engine-outcomes">
                <li
                  v-for="outcome in engineOutcomes"
                  :key="outcome.key"
                >
                  <span
                    class="engine-outcome-tag"
                    :class="outcome.tagClass"
                  >{{ outcome.label }}</span>
                  <span class="engine-outcome-text">{{ outcome.text }}</span>
                </li>
              </ul>
            </div>
            <p
              v-for="(note, index) in engineDetail.extra_notes"
              :key="'note-' + index"
              class="engine-note"
            >
              {{ note }}
            </p>
            <p
              v-if="engineDetail.data_gap_note"
              class="muted"
            >
              {{ engineDetail.data_gap_note }}
            </p>
          </template>
        </div>

        <div
          v-if="customerPolicy"
          class="luxian-section"
        >
          <h4>政策依据</h4>
          <div class="policy-source-list">
            <span
              v-for="source in customerPolicy.sources"
              :key="source"
              class="policy-source"
            >
              {{ formatPolicySource(source) }}
            </span>
          </div>
        </div>

        <div class="luxian-section">
          <h4>执行映射（实现信息）</h4>
          <div class="rule-chip-list">
            <span
              v-for="ruleId in executionRuleIds"
              :key="ruleId"
              class="rule-chip"
              :class="{ primary: ruleId === rule.primary_execution_rule_id }"
            >
              {{ ruleId }}{{ ruleId === rule.primary_execution_rule_id ? ' · 主执行' : '' }}
            </span>
            <span
              v-if="!executionRuleIds.length"
              class="mapping-empty"
            > 未提供映射规则 </span>
          </div>
        </div>
      </div>

      <div
        v-if="isAdmin && !isLuxianRule"
        class="prompt-panel"
      >
        <div class="prompt-header">
          <div>
            <h4 class="prompt-title">
              检查模板管理
            </h4>
          </div>
          <div class="prompt-actions">
            <a-button
              v-if="!isEditingPrompt"
              type="link"
              size="small"
              @click="emit('startEditPrompt')"
            >
              编辑
            </a-button>
            <template v-else>
              <a-button
                size="small"
                @click="emit('cancelEditPrompt')"
              >
                取消
              </a-button>
              <a-button
                type="primary"
                size="small"
                :loading="promptLoading"
                @click="emit('savePrompt')"
              >
                保存
              </a-button>
            </template>
          </div>
        </div>

        <div
          v-if="!isEditingPrompt"
          class="prompt-content"
        >
          {{ currentPrompt || '// 暂无检查模板，使用系统默认逻辑' }}
        </div>
        <a-textarea
          v-else
          :value="editingPrompt"
          :rows="10"
          class="prompt-editor"
          placeholder="请输入自定义检查模板"
          @update:value="emit('update:editingPrompt', String($event || ''))"
        />
      </div>

      <div class="detail-footer">
        <a-button
          class="detail-secondary-btn"
          @click="emit('update:open', false)"
        >
          关闭
        </a-button>
        <a-button
          type="primary"
          class="detail-primary-btn"
          @click="emit('startTest')"
        >
          开始测试
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type {
  SemanticRuleEngineJudgmentDetail,
  SemanticRuleEngineJudgmentWithheld,
  SemanticRuleEngineOutcomeKey,
  SemanticRuleItem,
} from '../../types'
import { getCategoryZh, getDocTypeZh, getSeverityZh } from '../../types'

const props = defineProps<{
  open: boolean
  rule: SemanticRuleItem | null
  isAdmin: boolean
  promptLoading: boolean
  isEditingPrompt: boolean
  currentPrompt: string
  editingPrompt: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  startEditPrompt: []
  cancelEditPrompt: []
  savePrompt: []
  'update:editingPrompt': [value: string]
  startTest: []
}>()

const isLuxianRule = computed(() => props.rule?.rule_id.startsWith('LX0609-') || false)

const customerPolicy = computed(() =>
  isLuxianRule.value ? props.rule?.customer_policy : undefined,
)

const engineJudgment = computed(() =>
  isLuxianRule.value ? props.rule?.engine_judgment : undefined,
)

const ENGINE_OUTCOME_LABELS: Array<[SemanticRuleEngineOutcomeKey, string]> = [
  ['compliant', '合规'],
  ['non_compliant', '不合规'],
  ['data_gap', '资料不足'],
  ['not_applicable', '不适用'],
]

const engineWithheldReason = computed(() => {
  const judgment = engineJudgment.value
  return judgment?.withheld === true
    ? (judgment as SemanticRuleEngineJudgmentWithheld).withheld_reason
    : ''
})

const engineDetail = computed<SemanticRuleEngineJudgmentDetail | null>(() => {
  const judgment = engineJudgment.value
  return judgment && judgment.withheld === false
    ? (judgment as SemanticRuleEngineJudgmentDetail)
    : null
})

const engineOutcomes = computed(() => {
  const judgment = engineDetail.value
  if (!judgment) return []
  return ENGINE_OUTCOME_LABELS.flatMap(([key, label]) => {
    const text = judgment.outcomes[key]
    return text ? [{ key, label, text, tagClass: 'is-' + key }] : []
  })
})

const luxianPolicyTitle = computed(() => {
  const policy = customerPolicy.value
  if (!policy) return props.rule?.name || '规则详情'
  return `${policy.source_document}：${policy.qc_point}`
})

const executionRuleIds = computed(() => {
  const rule = props.rule
  if (!rule) return []
  return [
    ...new Set([rule.primary_execution_rule_id, ...(rule.mapped_rule_ids || [])].filter(Boolean)),
  ]
})

const POLICY_SOURCE_LABELS: Record<string, string> = {
  sichuan_2026_handbook: '四川省病案管理质量控制指标检查要点指导手册（2026版）',
  sichuan_2023_standard: '四川省住院病历评定标准',
  customer_confirmed: '客户确认口径',
  hospital_local_extension: '本院扩展口径',
}

function formatPolicySource(value: string): string {
  return POLICY_SOURCE_LABELS[value] || '未识别政策来源'
}
</script>

<style scoped>
:global(.semantic-modal .ant-modal-content) {
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.14);
}

:global(.semantic-modal .ant-modal-header) {
  margin: 0;
  padding: 18px 22px 12px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
}

:global(.semantic-modal .ant-modal-title) {
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
  font-size: 17px;
  font-weight: 600;
}

:global(.semantic-modal .ant-modal-body) {
  max-height: min(78vh, 760px);
  overflow-y: auto;
  padding: 18px 22px 20px;
  background: #f5f5f7;
}

.detail-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: #1d1d1f;
  font-family:
    'San Francisco', 'SF Pro Text', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei UI',
    system-ui, sans-serif;
}

.detail-summary {
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
  padding: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.045);
}

.detail-summary-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.detail-title-block {
  min-width: 0;
}

.detail-kicker {
  display: block;
  margin-bottom: 5px;
  color: #0a6cff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.detail-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 650;
  line-height: 1.35;
}

.detail-code {
  display: inline-flex;
  align-items: center;
  flex: none;
  border-radius: 999px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  background: rgba(10, 108, 255, 0.08);
  padding: 5px 10px;
  color: #0a6cff;
  font-size: 12px;
  font-weight: 700;
}

.detail-desc {
  margin: 12px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  line-height: 1.6;
}

.detail-descriptions {
  padding: 12px 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.detail-descriptions :deep(.ant-descriptions-item-label) {
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
}

.detail-descriptions :deep(.ant-descriptions-item-content) {
  color: rgba(29, 29, 31, 0.78);
  font-size: 13px;
}

.tag {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  padding: 0 8px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 600;
}

.tag-plain {
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.62);
  border-color: rgba(0, 0, 0, 0.08);
}

.tag-danger {
  background: rgba(255, 69, 58, 0.1);
  color: #d92d20;
  border-color: rgba(255, 69, 58, 0.18);
}

.doc-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.doc-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  border-radius: 999px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
}

.luxian-panel {
  display: grid;
  gap: 12px;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.72);
  padding: 14px;
}

.luxian-section {
  border-radius: 14px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  padding: 12px;
}

.luxian-section h4 {
  margin: 0 0 8px;
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 650;
}

.luxian-section p {
  margin: 0;
  color: rgba(29, 29, 31, 0.62);
  font-size: 13px;
  line-height: 1.65;
}

.luxian-section .muted {
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.38);
  font-size: 12px;
}

.engine-section {
  display: grid;
  gap: 10px;
}

.engine-section h4 {
  margin-bottom: 0;
}

.engine-method {
  border-left: 3px solid rgba(10, 108, 255, 0.35);
  padding-left: 8px;
}

.engine-block {
  display: grid;
  gap: 4px;
}

.engine-label {
  color: rgba(29, 29, 31, 0.5);
  font-size: 12px;
  font-weight: 600;
}

.engine-steps,
.engine-outcomes {
  margin: 0;
  padding-left: 18px;
  color: rgba(29, 29, 31, 0.72);
  font-size: 13px;
  line-height: 1.65;
}

.engine-steps {
  list-style: decimal;
}

.engine-steps li::marker {
  color: rgba(10, 108, 255, 0.7);
  font-weight: 600;
}

.engine-outcomes {
  display: grid;
  gap: 4px;
  padding-left: 0;
  list-style: none;
}

.engine-outcomes li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.engine-outcome-tag {
  flex: none;
  min-width: 56px;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.6;
  text-align: center;
  white-space: nowrap;
}

.engine-outcome-tag.is-compliant {
  background: rgba(52, 199, 89, 0.12);
  color: #1f8a3e;
}

.engine-outcome-tag.is-non_compliant {
  background: rgba(255, 59, 48, 0.1);
  color: #c4291f;
}

.engine-outcome-tag.is-data_gap {
  background: rgba(255, 149, 0, 0.12);
  color: #a35d00;
}

.engine-outcome-tag.is-not_applicable {
  background: rgba(0, 0, 0, 0.05);
  color: rgba(29, 29, 31, 0.6);
}

.engine-outcome-text {
  min-width: 0;
}

.engine-note {
  border-radius: 10px;
  background: rgba(10, 108, 255, 0.05);
  padding: 6px 10px;
}

.engine-withheld {
  color: rgba(29, 29, 31, 0.62);
}

.policy-source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.policy-source {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border: 1px solid rgba(10, 108, 255, 0.14);
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.06);
  padding: 3px 8px;
  color: rgba(29, 29, 31, 0.68);
  font-size: 12px;
  line-height: 1.4;
}

.rule-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rule-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  padding: 0 9px;
  color: rgba(29, 29, 31, 0.62);
  font-size: 12px;
  font-weight: 600;
}

.rule-chip.primary {
  border-color: rgba(10, 108, 255, 0.18);
  background: rgba(10, 108, 255, 0.08);
  color: #0a6cff;
}

.mapping-empty {
  color: rgba(29, 29, 31, 0.46);
  font-size: 12px;
}

.prompt-panel {
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82);
  padding: 14px;
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.prompt-title {
  margin: 0;
  color: #1d1d1f;
  font-size: 15px;
  font-weight: 650;
}

.prompt-actions {
  display: inline-flex;
  gap: 8px;
}

.prompt-content {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(29, 29, 31, 0.94);
  color: rgba(255, 255, 255, 0.78);
  padding: 12px;
  white-space: pre-wrap;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New',
    monospace;
  font-size: 12px;
  max-height: 260px;
  overflow-y: auto;
}

.prompt-editor {
  margin-top: 10px;
}

.detail-footer {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.detail-primary-btn,
.detail-secondary-btn {
  height: 34px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
}

.detail-primary-btn {
  background: #0a6cff;
  border-color: #0a6cff;
  box-shadow: 0 2px 8px rgba(10, 108, 255, 0.16);
}

.detail-secondary-btn {
  border-color: rgba(0, 0, 0, 0.08);
  color: rgba(29, 29, 31, 0.66);
}
</style>
