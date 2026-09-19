<template>
  <section
    v-if="hasContent"
    class="qc-remediation"
    :class="{ 'qc-remediation--dense': dense }"
    data-testid="qc-remediation-suggestion"
  >
    <div class="qc-remediation-head">
      <span class="qc-remediation-title">{{ title }}</span>
    </div>
    <dl
      v-if="parsed.structured"
      class="qc-remediation-sections"
    >
      <div
        v-for="(section, index) in parsed.sections"
        :key="`qc-remediation-section-${index}`"
        class="qc-remediation-section"
        :class="{ 'qc-remediation-section--plain': !section.label }"
      >
        <dt
          v-if="section.label"
          class="qc-remediation-label"
        >
          {{ section.label }}
        </dt>
        <dd class="qc-remediation-body">
          {{ section.body }}
        </dd>
      </div>
    </dl>
    <p
      v-else
      class="qc-remediation-plain"
    >
      {{ parsed.plain }}
    </p>
    <div
      v-if="canRequestDraft"
      class="qc-remediation-draft"
      data-testid="qc-remediation-draft"
    >
      <div class="qc-remediation-draft-head">
        <span class="qc-remediation-draft-title">AI 整改草稿</span>
        <span class="qc-remediation-draft-badge">待医师确认</span>
      </div>
      <p
        v-if="draftText"
        class="qc-remediation-draft-body"
        data-testid="qc-remediation-draft-text"
      >
        {{ draftText }}
      </p>
      <p
        v-if="draftError"
        class="qc-remediation-draft-error"
      >
        {{ draftError }}
      </p>
      <div class="qc-remediation-draft-actions">
        <button
          type="button"
          class="qc-remediation-draft-action"
          :disabled="draftLoading"
          data-testid="qc-remediation-draft-request"
          @click="requestDraft"
        >
          {{ draftLoading ? '生成中…' : draftText ? '重新生成' : '生成草稿' }}
        </button>
        <button
          v-if="draftText"
          type="button"
          class="qc-remediation-draft-action"
          data-testid="qc-remediation-draft-copy"
          @click="copyDraft"
        >
          {{ draftCopied ? '已复制' : '复制草稿' }}
        </button>
      </div>
    </div>
  </section>
</template>

<script lang="ts">
export interface QcRemediationSection {
  label: string
  body: string
}

export interface ParsedQcRemediationSuggestion {
  structured: boolean
  sections: QcRemediationSection[]
  plain: string
}

// 仅识别后端四段式建议的固定标签，不做任何同义改写。
const QC_REMEDIATION_LABELS = ['修改对象', '需要补充', '推荐写法', '注意事项'] as const
const QC_REMEDIATION_LABEL_PATTERN = QC_REMEDIATION_LABELS.join('|')

/** 与后端 REMEDIATION_DRAFT_RULE_IDS 保持一致：只在这三个会诊规则上提供草稿。 */
export const QC_REMEDIATION_DRAFT_RULE_IDS = ['LX0609-020', 'LX0609-022', 'LX0609-023'] as const

export interface QcRemediationDraftContext {
  instituteId?: string
  patientId?: string
  visitId?: string
}

export function canRequestQcRemediationDraft(
  ruleId?: string,
  status?: string,
  context?: QcRemediationDraftContext,
): boolean {
  const normalizedRuleId = String(ruleId || '')
    .trim()
    .toUpperCase()
  if (!QC_REMEDIATION_DRAFT_RULE_IDS.includes(normalizedRuleId as never)) return false
  if (
    String(status || '')
      .trim()
      .toLowerCase() !== 'non_compliant'
  )
    return false
  return Boolean(
    String(context?.instituteId || '').trim() &&
      String(context?.patientId || '').trim() &&
      String(context?.visitId || '').trim(),
  )
}

export function resolveQcRemediationTitle(status?: string): string {
  const normalized = String(status || '')
    .trim()
    .toLowerCase()
  if (normalized === 'non_compliant' || normalized === 'confirmed_issue') return '修改建议'
  if (normalized === 'data_gap' || normalized === 'uncertain') return '核对建议'
  if (normalized === 'evaluation_unknown') return '复核建议'
  if (normalized === 'technical_error') return '排查建议'
  return '处理建议'
}

/**
 * 按明确标签切段，只保留原文内容；非四段式旧建议整体作为纯文本返回。
 */
export function parseQcRemediationSuggestion(text?: string): ParsedQcRemediationSuggestion {
  const plain = String(text || '').trim()
  if (!plain) return { structured: false, sections: [], plain: '' }
  const sections = plain
    .split(new RegExp(`\\n+|(?=(?:${QC_REMEDIATION_LABEL_PATTERN})[：:])`, 'u'))
    .map((segment) => segment.trim())
    .filter(Boolean)
    .map((segment) => {
      const matched = new RegExp(
        `^(${QC_REMEDIATION_LABEL_PATTERN})\\s*[：:]\\s*([\\s\\S]*)$`,
        'u',
      ).exec(segment)
      if (!matched) return { label: '', body: segment }
      return { label: matched[1], body: matched[2].trim() }
    })
  const structured = sections.some((section) => Boolean(section.label))
  return { structured, sections, plain }
}
</script>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { requestLuxian0609RemediationDraft } from '@/services/sichuan-rule-workspace-service'

const props = withDefaults(
  defineProps<{
    suggestion: string
    status?: string
    /** 紧凑排版：仅收紧间距，字号与字重保持不变。 */
    dense?: boolean
    /** 提供病历三坐标与规则号后，本条才会出现按需草稿入口。 */
    ruleId?: string
    recordContext?: QcRemediationDraftContext
  }>(),
  {
    status: '',
    dense: false,
    ruleId: '',
    recordContext: undefined,
  },
)

const parsed = computed(() => parseQcRemediationSuggestion(props.suggestion))
const hasContent = computed(() => parsed.value.plain.length > 0)
const title = computed(() => resolveQcRemediationTitle(props.status))

const draftText = ref('')
const draftLoading = ref(false)
const draftError = ref('')
const draftCopied = ref(false)

const canRequestDraft = computed(() =>
  canRequestQcRemediationDraft(props.ruleId, props.status, props.recordContext),
)

async function requestDraft() {
  if (draftLoading.value || !canRequestDraft.value) return
  const context = props.recordContext
  const ruleId = String(props.ruleId || '')
    .trim()
    .toUpperCase()
  draftLoading.value = true
  draftError.value = ''
  draftCopied.value = false
  try {
    const result = await requestLuxian0609RemediationDraft(
      {
        instituteId: String(context?.instituteId || '').trim(),
        patientId: String(context?.patientId || '').trim(),
        visitId: String(context?.visitId || '').trim(),
      },
      ruleId,
    )
    const draft = result.data?.draft
    if (result.success && result.data?.available && draft) {
      draftText.value = draft
      return
    }
    draftText.value = ''
    draftError.value = result.message || '本次未能生成草稿，请稍后重试。'
  } catch {
    draftText.value = ''
    draftError.value = '本次未能生成草稿，请稍后重试。'
  } finally {
    draftLoading.value = false
  }
}

async function copyDraft() {
  if (!draftText.value) return
  try {
    await navigator.clipboard.writeText(draftText.value)
    draftCopied.value = true
  } catch {
    draftCopied.value = false
  }
}
</script>

<style scoped>
.qc-remediation {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.qc-remediation-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qc-remediation-title {
  color: #465366;
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.qc-remediation-sections {
  display: grid;
  margin: 0;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 10px;
  background: #f8fafc;
  overflow: hidden;
}

.qc-remediation-section {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 10px;
  padding: 8px 12px;
}

.qc-remediation-section + .qc-remediation-section {
  border-top: 1px solid rgba(15, 23, 42, 0.05);
}

.qc-remediation-label {
  color: #6b7684;
  font-size: 12px;
  font-weight: 600;
  line-height: 22px;
}

.qc-remediation-body {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 400;
  line-height: 22px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.qc-remediation-section--plain .qc-remediation-body {
  grid-column: 1 / -1;
}

.qc-remediation-plain {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 400;
  line-height: 22px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.qc-remediation--dense {
  gap: 6px;
}

.qc-remediation--dense .qc-remediation-section {
  padding: 6px 10px;
}

.qc-remediation-draft {
  display: grid;
  gap: 8px;
  margin-top: 4px;
  padding: 10px 12px;
  border: 1px dashed rgba(37, 99, 235, 0.28);
  border-radius: 10px;
  background: #f6f9ff;
}

.qc-remediation-draft-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.qc-remediation-draft-title {
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.qc-remediation-draft-badge {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
}

.qc-remediation-draft-body {
  margin: 0;
  color: #1d1d1f;
  font-size: 14px;
  line-height: 22px;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.qc-remediation-draft-error {
  margin: 0;
  color: #b42318;
  font-size: 12px;
  line-height: 18px;
}

.qc-remediation-draft-actions {
  display: flex;
  gap: 8px;
}

.qc-remediation-draft-action {
  padding: 4px 10px;
  border: 1px solid rgba(37, 99, 235, 0.32);
  border-radius: 8px;
  background: #fff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  line-height: 18px;
  cursor: pointer;
}

.qc-remediation-draft-action:hover:not(:disabled) {
  background: #eef4ff;
}

.qc-remediation-draft-action:disabled {
  cursor: default;
  opacity: 0.6;
}

@media (max-width: 640px) {
  .qc-remediation-section {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .qc-remediation-label {
    line-height: 18px;
  }
}
</style>
