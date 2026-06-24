<template>
  <teleport to="body">
    <div
      v-if="visible"
      class="evidence-overlay"
      @click.self="emit('close')"
    >
      <div class="evidence-card">
        <div class="evidence-title">
          主诊断 LLM 证据
        </div>
        <template v-if="mainDiagnosisLlmEvidence || codingAuditLlmEvidence">
          <div
            class="evidence-hero"
            :class="formatSeverityClass(topAlert?.severity)"
          >
            <div class="evidence-hero__left">
              <span class="evidence-hero__badge">{{
                formatFindingSeverityLabel(topAlert?.severity)
              }}</span>
              <strong class="evidence-hero__title">{{
                formatFindingTypeLabel(topAlert?.type)
              }}</strong>
            </div>
            <div class="evidence-hero__summary">
              {{
                topAlert?.summary || codingAuditLlmEvidence?.summary || '当前未识别到高风险审核项。'
              }}
            </div>
            <div class="evidence-hero__meta">
              <span>置信度 {{ llmConfidenceText }}</span>
              <span>问题 {{ totalRiskCount }} 项</span>
            </div>
          </div>

          <div class="evidence-details">
            <section class="evidence-block">
              <div class="evidence-block-title">
                主诊断决策
              </div>
              <div class="evidence-decision-grid">
                <div class="evidence-decision-col">
                  <div class="evidence-meta">
                    临床主诊断
                  </div>
                  <div class="evidence-decision-main">
                    {{ mainDiagnosisLlmEvidence?.clinician_main_diagnosis || '-' }}
                  </div>
                </div>
                <div class="evidence-decision-col">
                  <div class="evidence-meta">
                    LLM 推荐主诊断
                  </div>
                  <div class="evidence-decision-main">
                    {{ mainDiagnosisLlmEvidence?.llm_recommended_main_diagnosis || '-' }}
                  </div>
                  <div
                    v-if="mainDiagnosisLlmEvidence?.recommendation_label"
                    class="evidence-recommend-label"
                  >
                    {{ mainDiagnosisLlmEvidence.recommendation_label }}
                  </div>
                </div>
              </div>
              <div class="evidence-logic">
                {{ mainDiagnosisLlmEvidence?.conclusion || 'LLM已完成主诊断语义裁决。' }}
              </div>
              <button
                v-if="mainDiagnosisLlmEvidence?.reasoning_summary"
                type="button"
                class="evidence-toggle-btn"
                @click="reasoningExpanded = !reasoningExpanded"
              >
                {{ reasoningExpanded ? '收起推理摘要' : '展开推理摘要' }}
              </button>
              <div class="evidence-collapsed-snippet">
                {{ mainDiagnosisLlmEvidence?.reasoning_summary || 'LLM推理摘要暂不可用。' }}
              </div>
            </section>

            <section class="evidence-block">
              <div class="evidence-block-title">
                审核风险（Top3）
              </div>
              <div
                v-if="riskTimelineItems.length === 0"
                class="evidence-logic"
              >
                {{ codingAuditLlmEvidence?.summary || '当前未识别到高风险审核项。' }}
              </div>
              <template v-else>
                <div
                  v-for="(risk, idx) in riskTimelineItems"
                  :key="`risk-${idx}`"
                  class="evidence-risk-card"
                >
                  <div class="evidence-risk-head">
                    <span class="evidence-risk-type">{{ formatFindingTypeLabel(risk.type) }}（{{
                      formatFindingSeverityLabel(risk.severity)
                    }}）</span>
                    <span
                      class="evidence-risk-severity"
                      :class="formatSeverityClass(risk.severity)"
                    >{{
                      risk.confidence ? `置信度 ${Math.round(risk.confidence * 100)}%` : '待复核'
                    }}</span>
                  </div>
                  <div class="evidence-key-reason">
                    {{ risk.reason || risk.summary || '未提供风险摘要。' }}
                  </div>
                  <div class="evidence-collapsed-snippet">
                    {{ buildEvidenceGroupCollapsedText(risk.evidence) }}
                  </div>
                  <button
                    type="button"
                    class="evidence-toggle-btn"
                    @click="toggleRiskExpanded(idx)"
                  >
                    {{ isRiskExpanded(idx) ? '收起证据' : '展开证据' }}
                  </button>
                  <template v-if="isRiskExpanded(idx)">
                    <div class="evidence-key-meta">
                      证据条数：{{ Array.isArray(risk.evidence) ? risk.evidence.length : 0 }}
                    </div>
                    <div class="evidence-key-meta">
                      问题类型：{{ formatFindingTypeLabel(risk.type) }}
                    </div>
                    <div
                      v-for="(line, evIdx) in risk.evidence || []"
                      :key="`risk-${idx}-${evIdx}`"
                      class="evidence-audit-quote"
                    >
                      <div class="evidence-quote">
                        {{ line.quote || line.text || '未提供原文证据。' }}
                      </div>
                      <div class="evidence-key-meta">
                        来源：{{ line.source_document || line.document || '未标注文书' }}
                      </div>
                      <div class="evidence-key-reason">
                        {{ line.reason || line.rationale || '未提供证据解释。' }}
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </section>

            <section class="evidence-block">
              <div class="evidence-block-title">
                关键证据
              </div>
              <div class="evidence-logic">
                {{ codingAuditLlmEvidence?.summary || 'LLM审核暂不可用' }}
              </div>
              <div
                v-if="keyEvidenceGroups.length === 0"
                class="evidence-logic"
              >
                当前未返回可展示的关键证据。
              </div>
              <template v-else>
                <div
                  v-for="(group, idx) in keyEvidenceGroups"
                  :key="`group-${idx}`"
                  class="evidence-key-card"
                >
                  <div class="evidence-risk-head">
                    <span class="evidence-risk-type">{{ formatFindingTypeLabel(group.type) }}</span>
                    <span class="evidence-key-meta">{{
                      formatFindingSeverityLabel(group.severity)
                    }}</span>
                  </div>
                  <div class="evidence-key-meta">
                    证据条数：{{ group.evidence.length }}
                  </div>
                  <div class="evidence-collapsed-snippet">
                    {{ buildEvidenceGroupCollapsedText(group.evidence) }}
                  </div>
                  <button
                    type="button"
                    class="evidence-toggle-btn"
                    @click="toggleEvidenceGroupExpanded(idx)"
                  >
                    {{ isEvidenceGroupExpanded(idx) ? '收起明细' : '展开明细' }}
                  </button>
                  <template v-if="isEvidenceGroupExpanded(idx)">
                    <div
                      v-for="(line, evIdx) in group.evidence"
                      :key="`group-${idx}-${evIdx}`"
                      class="evidence-audit-quote"
                    >
                      <div class="evidence-quote">
                        {{ line.quote || line.text || '未提供原文证据。' }}
                      </div>
                      <div class="evidence-key-meta">
                        来源：{{ line.source_document || line.document || '未标注文书' }}
                      </div>
                      <div class="evidence-key-reason">
                        {{ line.reason || line.rationale || '未提供证据解释。' }}
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </section>
          </div>
        </template>
        <section
          v-else-if="evidenceGenerationPending"
          class="evidence-block evidence-loading"
        >
          <div class="evidence-loading__icon">
            AI
          </div>
          <div class="evidence-loading__content">
            <div class="evidence-block-title">
              正在生成主诊断 LLM 证据
            </div>
            <div class="evidence-logic">
              AI 正在读取诊断、手术和病程片段，构建主诊断依据与编码审核风险。生成完成后这里会自动展示结果。
            </div>
            <div class="evidence-loading__steps">
              <span>提取关键片段</span>
              <span>判断主诊断一致性</span>
              <span>生成审核证据</span>
            </div>
          </div>
        </section>
        <section
          v-else
          class="evidence-block"
        >
          <div class="evidence-block-title">
            暂未生成 LLM 证据
          </div>
          <div class="evidence-logic">
            当前病历尚未返回可用的主诊断证据数据，请稍后重试。
          </div>
        </section>
        <div class="evidence-actions">
          <button
            type="button"
            class="evidence-close-btn"
            @click="emit('close')"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  visible: boolean
  mainDiagnosisLlmEvidence?: Record<string, any> | null
  codingAuditLlmEvidence?: Record<string, any> | null
  topAlert?: Record<string, any> | null
  riskTimelineItems: Array<Record<string, any>>
  keyEvidenceGroups: Array<Record<string, any>>
  totalRiskCount: number
  llmConfidenceText: string
  evidenceGenerationPending?: boolean
}>()

const emit = defineEmits<{ close: [] }>()

const reasoningExpanded = ref(false)
const expandedRiskKeys = ref<number[]>([])
const expandedEvidenceKeys = ref<number[]>([])

function formatSeverityClass(severity?: string | null) {
  const normalized = String(severity || '').toLowerCase()
  if (normalized === 'error' || normalized === 'high' || normalized === 'critical')
    return 'is-danger'
  if (normalized === 'warning' || normalized === 'medium') return 'is-warning'
  return 'is-neutral'
}

function formatFindingSeverityLabel(severity?: string | null) {
  const normalized = String(severity || '').toLowerCase()
  if (normalized === 'error' || normalized === 'high' || normalized === 'critical') return '高风险'
  if (normalized === 'warning' || normalized === 'medium') return '提示'
  return '一般'
}

function formatFindingTypeLabel(type?: string | null) {
  const key = String(type || '').toLowerCase()
  if (key === 'diagnosis_inappropriate') return '主诊断不当'
  if (key === 'diagnosis_insufficient_evidence') return '依据不足'
  if (key === 'coding_conflict') return '编码冲突'
  if (key === 'missing_main_diagnosis') return '主诊断缺失'
  return '风险提示'
}

function buildEvidenceGroupCollapsedText(evidence: Array<Record<string, any>> | undefined) {
  if (!Array.isArray(evidence) || evidence.length === 0) return '暂无证据摘录。'
  return (
    evidence
      .slice(0, 2)
      .map((line) => String(line?.quote || line?.text || '').trim())
      .filter(Boolean)
      .join('；') || '暂无证据摘录。'
  )
}

function toggleRiskExpanded(index: number) {
  expandedRiskKeys.value = expandedRiskKeys.value.includes(index)
    ? expandedRiskKeys.value.filter((item) => item !== index)
    : [...expandedRiskKeys.value, index]
}

function isRiskExpanded(index: number) {
  return expandedRiskKeys.value.includes(index)
}

function toggleEvidenceGroupExpanded(index: number) {
  expandedEvidenceKeys.value = expandedEvidenceKeys.value.includes(index)
    ? expandedEvidenceKeys.value.filter((item) => item !== index)
    : [...expandedEvidenceKeys.value, index]
}

function isEvidenceGroupExpanded(index: number) {
  return expandedEvidenceKeys.value.includes(index)
}
</script>

<style scoped>
.evidence-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.28);
  padding: 24px;
}
.evidence-card {
  width: min(1080px, calc(100vw - 48px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.18);
  padding: 24px;
}
.evidence-title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 16px;
}
.evidence-hero {
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 20px;
  padding: 18px;
  background: #f8fafc;
  margin-bottom: 16px;
}
.evidence-hero.is-danger {
  border-color: rgba(248, 113, 113, 0.5);
  background: rgba(254, 242, 242, 0.9);
}
.evidence-hero.is-warning {
  border-color: rgba(251, 191, 36, 0.5);
  background: rgba(255, 251, 235, 0.9);
}
.evidence-hero__left {
  display: flex;
  align-items: center;
  gap: 10px;
}
.evidence-hero__badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 700;
  background: #fff;
  color: #ef4444;
}
.evidence-hero__title {
  font-size: 20px;
  color: #991b1b;
}
.evidence-hero__summary {
  margin-top: 12px;
  color: #1f2937;
  font-size: 15px;
}
.evidence-hero__meta {
  margin-top: 10px;
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #64748b;
}
.evidence-details {
  display: grid;
  gap: 14px;
}
.evidence-block {
  border: 1px solid rgba(226, 232, 240, 0.85);
  border-radius: 18px;
  background: #fff;
  padding: 16px;
}
.evidence-loading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  border-color: rgba(147, 197, 253, 0.75);
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}
.evidence-loading__icon {
  display: flex;
  width: 42px;
  height: 42px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  border: 1px solid rgba(191, 219, 254, 0.9);
  background: #eff6ff;
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.08);
}
.evidence-loading__content {
  min-width: 0;
  flex: 1;
}
.evidence-loading__steps {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.evidence-loading__steps span {
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 999px;
  background: #ffffff;
  padding: 5px 10px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}
.evidence-loading__steps span:first-child {
  border-color: rgba(147, 197, 253, 0.8);
  background: #eff6ff;
  color: #2563eb;
}
.evidence-block-title {
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  margin-bottom: 10px;
}
.evidence-decision-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.evidence-decision-col {
  border: 1px solid rgba(226, 232, 240, 0.7);
  border-radius: 14px;
  padding: 12px;
  background: rgba(248, 250, 252, 0.72);
}
.evidence-meta,
.evidence-key-meta {
  font-size: 12px;
  color: #64748b;
}
.evidence-decision-main {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.evidence-recommend-label {
  margin-top: 8px;
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 10px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
}
.evidence-logic,
.evidence-quote,
.evidence-collapsed-snippet,
.evidence-key-reason {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
}
.evidence-risk-card,
.evidence-key-card {
  border: 1px solid rgba(226, 232, 240, 0.75);
  border-radius: 16px;
  padding: 12px;
  background: rgba(248, 250, 252, 0.72);
}
.evidence-risk-card + .evidence-risk-card,
.evidence-key-card + .evidence-key-card,
.evidence-audit-quote + .evidence-audit-quote {
  margin-top: 10px;
}
.evidence-risk-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.evidence-risk-type {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.evidence-risk-severity {
  font-size: 12px;
  font-weight: 700;
}
.evidence-risk-severity.is-danger {
  color: #dc2626;
}
.evidence-risk-severity.is-warning {
  color: #d97706;
}
.evidence-risk-severity.is-neutral {
  color: #64748b;
}
.evidence-toggle-btn {
  margin-top: 10px;
  border: none;
  background: transparent;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}
.evidence-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.evidence-close-btn {
  height: 40px;
  padding: 0 24px;
  border-radius: 999px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: #fff;
  color: #334155;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
@media (max-width: 900px) {
  .evidence-decision-grid {
    grid-template-columns: 1fr;
  }
}
</style>
