<template>
  <section class="clinical-completeness-panel">
    <header class="clinical-completeness-header">
      <div>
        <p>完整性分析</p>
        <h2>诊断与手术画像辅助</h2>
        <span>基于全病历形成疾病诊断画像、手术操作画像、诊断时间轴和执行验证，作为首页书写辅助对照。</span>
      </div>
      <button
        type="button"
        :disabled="loading || !visitId"
        @click="loadCompleteness(true)"
      >
        {{ loading ? '分析中' : '重新分析' }}
      </button>
    </header>

    <div
      v-if="error"
      class="clinical-state clinical-state--error"
    >
      {{ error }}
    </div>
    <div
      v-else-if="loading"
      class="clinical-state"
    >
      正在读取全病历文书并生成诊断/手术完整性分析...
    </div>
    <div
      v-else-if="!result"
      class="clinical-state"
    >
      请选择病历后查看诊疗完整性分析。
    </div>

    <template v-else>
      <div class="clinical-summary-grid">
        <article>
          <span>疾病诊断画像</span>
          <strong>{{ result.diagnoses.length }}</strong>
          <small>诊断证据与状态归集</small>
        </article>
        <article>
          <span>手术操作画像</span>
          <strong>{{ result.procedures.length }}</strong>
          <small>计划与执行证据归集</small>
        </article>
        <article>
          <span>完整性问题</span>
          <strong>{{ result.issues.length }}</strong>
          <small>仅作为草稿建议</small>
        </article>
        <article>
          <span>正式写入</span>
          <strong>否</strong>
          <small>不写首页/结算/正式质控</small>
        </article>
      </div>

      <div class="clinical-grid">
        <section class="clinical-card">
          <div class="clinical-card-title">
            <h3>疾病诊断画像</h3>
            <span>{{ result.diagnoses.length }} 项</span>
          </div>
          <div class="clinical-list">
            <div
              v-for="item in result.diagnoses"
              :key="`${item.diagnosis_name}-${item.first_mention_time}`"
              class="clinical-list-item"
            >
              <div>
                <strong>{{ item.diagnosis_name }}</strong>
                <span>{{ item.icd_code || '未编码' }} · {{ statusText(item.status) }}</span>
              </div>
              <small>{{ item.first_mention_time || '-' }} ·
                {{ item.first_mention_source || '-' }}</small>
            </div>
            <div
              v-if="!result.diagnoses.length"
              class="clinical-empty"
            >
              暂未形成疾病诊断画像。
            </div>
          </div>
        </section>

        <section class="clinical-card">
          <div class="clinical-card-title">
            <h3>手术操作画像</h3>
            <span>{{ result.procedures.length }} 项</span>
          </div>
          <div class="clinical-list">
            <div
              v-for="item in result.procedures"
              :key="`${item.procedure_name}-${item.execution_time}`"
              class="clinical-list-item"
            >
              <div>
                <strong>{{ item.procedure_name }}</strong>
                <span>{{ item.icd9_code || '未编码' }} · {{ procedureStatusText(item.status) }}</span>
              </div>
              <small>
                计划 {{ item.plan_time || '-' }} / 执行 {{ item.execution_time || '-' }}
              </small>
            </div>
            <div
              v-if="!result.procedures.length"
              class="clinical-empty"
            >
              暂未形成手术操作画像。
            </div>
          </div>
        </section>

        <section class="clinical-card">
          <div class="clinical-card-title">
            <h3>诊断发生发展时间轴</h3>
            <span>{{ result.diagnoses.length }} 项</span>
          </div>
          <div class="clinical-list clinical-timeline-list">
            <div
              v-for="item in result.diagnoses"
              :key="`timeline-${item.diagnosis_name}-${item.first_mention_time}`"
              class="clinical-list-item clinical-timeline-item"
            >
              <small>{{ item.first_mention_time || '时间待确认' }}</small>
              <strong>{{ item.diagnosis_name }}</strong>
              <span>{{ item.first_mention_source || '来源待确认' }} ·
                {{ statusText(item.status) }}</span>
            </div>
            <div
              v-if="!result.diagnoses.length"
              class="clinical-empty"
            >
              暂未形成诊断发生发展时间轴。
            </div>
          </div>
        </section>

        <section class="clinical-card">
          <div class="clinical-card-title">
            <h3>手术操作执行与否验证</h3>
            <span>{{ result.procedures.length }} 项</span>
          </div>
          <div class="clinical-list">
            <div
              v-for="item in result.procedures"
              :key="`verify-${item.procedure_name}-${item.execution_time}`"
              class="clinical-list-item"
            >
              <div>
                <strong>{{ item.procedure_name }}</strong>
                <span>{{ procedureStatusText(item.status) }}</span>
              </div>
              <small>
                计划来源 {{ item.plan_time || '-' }} / 执行来源 {{ item.execution_time || '-' }}
              </small>
            </div>
            <div
              v-if="!result.procedures.length"
              class="clinical-empty"
            >
              暂未形成手术操作执行验证。
            </div>
          </div>
        </section>
      </div>

      <section class="clinical-card clinical-issues-card">
        <div class="clinical-card-title">
          <h3>首页书写提示</h3>
          <span>{{ result.issues.length }} 条</span>
        </div>
        <div class="clinical-issue-list">
          <div
            v-for="issue in result.issues"
            :key="`${issue.item_category}-${issue.item_name}-${issue.issue_type}`"
            class="clinical-issue"
          >
            <b>{{ issue.item_name }}</b>
            <span>{{ issue.suggestion || issue.evidence_summary || issue.issue_type }}</span>
            <i>{{ issueCategoryText(issue.item_category) }} · {{ issue.severity }}</i>
          </div>
          <div
            v-if="!result.issues.length"
            class="clinical-empty"
          >
            当前未发现诊断或手术操作漏填、错填风险。
          </div>
        </div>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ApiService } from '@/services/apiService'
import type { PatientRecord } from '../types'

interface DiagnosisTimelineItem {
  diagnosis_name: string
  icd_code?: string
  first_mention_time?: string
  first_mention_source?: string
  status?: string
}

interface ProcedureTimelineItem {
  procedure_name: string
  icd9_code?: string
  plan_time?: string
  execution_time?: string
  status?: string
}

interface ClinicalCompletenessIssue {
  issue_type: string
  item_category: string
  item_name: string
  severity: string
  suggestion?: string
  evidence_summary?: string
}

interface ClinicalCompletenessResult {
  visit_id: string
  diagnoses: DiagnosisTimelineItem[]
  procedures: ProcedureTimelineItem[]
  issues: ClinicalCompletenessIssue[]
  data_quality_flags?: string[]
}

const props = defineProps<{
  record?: PatientRecord
}>()

const loading = ref(false)
const error = ref('')
const result = ref<ClinicalCompletenessResult | null>(null)

const visitId = computed(() => props.record?.visitId || props.record?.id || '')

async function loadCompleteness(forceRefresh = false) {
  if (!visitId.value) return
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | boolean> = {
      force_refresh: forceRefresh,
    }
    if (props.record?.patientId) params.patient_id = props.record.patientId
    if (props.record?.instituteId) params.institute_id = props.record.instituteId
    const response = await ApiService.get<ClinicalCompletenessResult>(
      `/api/v1/clinical-completeness/${encodeURIComponent(visitId.value)}`,
      params,
    )
    result.value = response.data || null
  } catch (loadError) {
    result.value = null
    error.value = loadError instanceof Error ? loadError.message : '诊疗完整性分析失败'
  } finally {
    loading.value = false
  }
}

function statusText(status?: string): string {
  if (status === 'confirmed') return '已确认'
  if (status === 'ruled_out') return '已排除'
  return '疑似/待确认'
}

function procedureStatusText(status?: string): string {
  if (status === 'verified') return '计划与执行一致'
  if (status === 'planned_only') return '仅见计划'
  return '仅见执行'
}

function issueCategoryText(category: string): string {
  return category === 'procedure' ? '手术操作' : '诊断'
}

onMounted(() => {
  void loadCompleteness()
})

watch(visitId, () => {
  result.value = null
  void loadCompleteness()
})
</script>

<style scoped>
.clinical-completeness-panel {
  min-height: 100%;
  padding: 18px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.clinical-completeness-header,
.clinical-card,
.clinical-summary-grid article {
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

.clinical-completeness-header:hover,
.clinical-card:hover,
.clinical-summary-grid article:hover {
  border-color: rgba(0, 0, 0, 0.14);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.1),
    0 6px 22px rgba(0, 0, 0, 0.075);
  transform: translateY(-2px);
}

.clinical-completeness-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-radius: 18px;
  padding: 20px 22px;
}

.clinical-completeness-header p {
  margin: 0 0 6px;
  color: #0066cc;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.clinical-completeness-header h2 {
  margin: 0;
  color: #1d1d1f;
  font-size: 24px;
  font-weight: 700;
  line-height: 30px;
}

.clinical-completeness-header span {
  display: block;
  margin-top: 4px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
  font-weight: 500;
}

.clinical-completeness-header button {
  min-height: 38px;
  border: 0;
  border-radius: 10px;
  background: #0066cc;
  color: #ffffff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 0 16px;
}

.clinical-completeness-header button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.clinical-state {
  margin-top: 14px;
  border: 1px dashed rgba(0, 102, 204, 0.24);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  font-weight: 500;
  padding: 20px;
}

.clinical-state--error {
  border-color: #fecaca;
  background: #fff1f2;
  color: #b91c1c;
}

.clinical-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.clinical-summary-grid article,
.clinical-card {
  border-radius: 16px;
  padding: 16px;
}

.clinical-summary-grid span,
.clinical-summary-grid small {
  display: block;
  color: rgba(29, 29, 31, 0.56);
  font-size: 12px;
  font-weight: 600;
}

.clinical-summary-grid strong {
  display: block;
  color: #0066cc;
  font-size: 28px;
  font-weight: 700;
  line-height: 34px;
}

.clinical-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.clinical-card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.clinical-card-title h3 {
  margin: 0;
  color: #1d1d1f;
  font-size: 17px;
  font-weight: 600;
}

.clinical-card-title span {
  border-radius: 999px;
  background: rgba(0, 102, 204, 0.08);
  color: #0066cc;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 10px;
}

.clinical-list,
.clinical-issue-list {
  display: grid;
  gap: 8px;
}

.clinical-list-item,
.clinical-issue {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  padding: 12px;
}

.clinical-list-item strong,
.clinical-issue b {
  display: block;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}

.clinical-list-item span,
.clinical-list-item small,
.clinical-issue span,
.clinical-issue i {
  display: block;
  margin-top: 3px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
  line-height: 18px;
}

.clinical-issues-card {
  margin-top: 14px;
}

.clinical-empty {
  border: 1px dashed rgba(0, 0, 0, 0.12);
  border-radius: 12px;
  color: rgba(29, 29, 31, 0.42);
  font-size: 13px;
  font-weight: 500;
  padding: 14px;
}

@media (max-width: 1100px) {
  .clinical-summary-grid,
  .clinical-grid {
    grid-template-columns: 1fr;
  }
}
</style>
