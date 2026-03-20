<template>
  <div class="fp-sheet-wrap">
    <div v-if="diagnosisGenerationPending" class="fp-pending">
      正在生成诊断编码与证据，请稍候...
    </div>

    <div class="fp-frame-wrap">
      <iframe ref="iframeRef" class="fp-frame" :srcdoc="srcdoc" />
    </div>

    <section v-if="diagnosisRows.length" class="fp-evidence-section">
      <div class="fp-evidence-title">诊断证据</div>
      <div class="fp-evidence-list">
        <button
          v-for="(item, idx) in diagnosisRows"
          :key="`${item.diagnosis_name || ''}-${idx}`"
          type="button"
          class="fp-evidence-btn"
          :disabled="!findDiagnosisEvidence(item.diagnosis_name)"
          @click="openDiagnosisEvidence(item.diagnosis_name)"
        >
          <span class="fp-evidence-btn-name">{{ item.diagnosis_name || '未命名诊断' }}</span>
          <span class="fp-evidence-btn-tag">证据</span>
        </button>
      </div>
    </section>

    <div
      v-if="evidencePanel.visible && evidencePanel.item"
      class="evidence-overlay"
      @click.self="closeDiagnosisEvidence"
    >
      <div class="evidence-card">
        <div class="evidence-title">诊断原文证据</div>
        <div class="evidence-meta">诊断：{{ evidencePanel.item.diagnosis_text || '-' }}</div>
        <div class="evidence-meta">章节：{{ evidencePanel.item.section || '-' }}</div>
        <div class="evidence-meta">
          匹配：{{ evidencePanel.item.match_mode || '-' }}
          置信度：{{ evidencePanel.item.confidence ?? '-' }}
        </div>

        <div class="evidence-block">
          <div class="evidence-block-title">诊断条目原文</div>
          <div class="evidence-quote">{{ evidencePanel.item.quote || '未命中诊断原文' }}</div>
        </div>

        <div class="evidence-block">
          <div class="evidence-block-title">主要诊断选择依据</div>
          <div class="evidence-logic">{{ evidencePanel.item.selection_logic || '暂无' }}</div>
        </div>

        <div
          v-if="Array.isArray(evidencePanel.item.reasoning_checks) && evidencePanel.item.reasoning_checks.length"
          class="evidence-block"
        >
          <div class="evidence-block-title">判定清单（医学逻辑）</div>
          <div v-for="(ck, idx) in evidencePanel.item.reasoning_checks" :key="idx" class="evidence-check">
            <div class="evidence-check-head">
              <span>{{ ck.item || `规则${idx + 1}` }}</span>
              <span :class="['evidence-pill', ck.status ? 'ok' : 'pending']">
                {{ ck.status ? '满足' : '待确认' }}
              </span>
            </div>
            <div class="evidence-check-exp">{{ ck.explain || '' }}</div>
            <div v-if="ck.evidence_quote" class="evidence-check-quote">{{ ck.evidence_quote }}</div>
          </div>
        </div>

        <div
          v-if="Array.isArray(evidencePanel.item.raw_evidence_lines) && evidencePanel.item.raw_evidence_lines.length"
          class="evidence-block"
        >
          <div class="evidence-block-title">已用病历原文</div>
          <div v-for="(line, idx) in evidenceRawLinesToShow" :key="idx" class="evidence-raw-line">
            <span class="evidence-raw-tag">[{{ line.source || '病历原文' }} | {{ line.role || '证据' }}]</span>
            <span>{{ line.text }}</span>
          </div>
          <button v-if="hasMoreRawEvidence" type="button" class="evidence-btn-inline" @click="toggleRawEvidenceExpand">
            {{ showAllRawEvidence ? '收起' : '展开更多' }}
          </button>
        </div>

        <div class="evidence-actions">
          <button type="button" class="evidence-close-btn" @click="closeDiagnosisEvidence">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'

import templateBodyHtml from '@/assets/templates/hm-frontpage/inpatient_record.html?raw'
import contentsCss from '@/assets/templates/hm-frontpage/contents.css?raw'
import printCss from '@/assets/templates/hm-frontpage/print.css?raw'
import { frontPageDraftToDeMap } from '@/utils/hm-frontpage/frontPageDraftToDeMap'
import { applyDeValuesToHmTemplateBody, buildHmTemplateSrcdoc } from '@/utils/hm-frontpage/templateRefill'

interface DiagnosisItem {
  diagnosis_type?: string
  diagnosis_name?: string
  diagnosis_code?: string
  admission_condition?: string | number
}

const props = defineProps<{
  data: any
  postProcessing?: boolean
}>()

const iframeRef = ref<HTMLIFrameElement | null>(null)

const diagnosisRows = computed<DiagnosisItem[]>(() => {
  const arr = props.data?.diagnoses
  return Array.isArray(arr) ? arr : []
})

const diagnosisGenerationPending = computed(() => {
  if (!props.postProcessing) return false
  const list = diagnosisRows.value
  if (!list.length) return true
  const meaningful = list.filter((d) => String(d?.diagnosis_name || '').trim().length > 0)
  if (!meaningful.length) return true
  const hasMissingCode = meaningful.some((d) => String(d?.diagnosis_code || '').trim().length === 0)
  const hasEvidence = diagnosisEvidenceList.value.length > 0
  return hasMissingCode || !hasEvidence
})

function first(arr: any[], fallback: any = undefined) {
  return Array.isArray(arr) && arr.length ? arr[0] : fallback
}

function normalizeDate(value: any): string | null {
  if (!value) return null
  const s = String(value).trim()
  if (!s) return null
  const m = s.match(/\d{4}-\d{2}-\d{2}/)
  return m ? m[0] : s
}

const normalizedDraft = computed(() => {
  const src = props.data || {}
  const basic = src.basic || {}
  const diags: DiagnosisItem[] = Array.isArray(src.diagnoses) ? src.diagnoses : []
  const surgeries: any[] = Array.isArray(src.surgeries) ? src.surgeries : []
  const cost = src.cost || {}

  const mainDiag = diags.find((d) => String(d?.diagnosis_type || '').includes('主要')) || first(diags, null)
  const otherDiags = diags.filter((d) => d !== mainDiag)

  const mainProc = first(surgeries, null)
  const otherProcs = Array.isArray(surgeries) ? surgeries.slice(1) : []

  return {
    basic_info: {
      patient_name: basic.name || '',
      gender: basic.sex || '',
      birth_date: basic.birthday || '',
      age_years: basic.age || '',
      id_number: basic.id_card_no || '',
      marital_status: basic.marital_status || '',
      nationality: basic.nationality || '中国',
      ethnicity: basic.ethnicity || '',
      occupation: basic.occupation_category || '',
      nativeplace: basic.nativeplace || '',
      current_address: basic.currentaddress || '',
      work_unit: basic.work_unit || '',
      contact_name: basic.contact_name || '',
      contact_relation: basic.contact_relationship || '',
      contact_phone: basic.contact_telephone || '',
      contact_address: basic.contact_address || ''
    },
    hospitalization: {
      hospital_name: basic.institute_county_desc || '',
      organization_code: basic.institute_code || '',
      medical_record_no: basic.document_id || '',
      admission_times_in_hospital: basic.visit_cnt || '',
      payment_method_text: basic.medical_payment_method || '',
      admission_way_text: basic.admission_route || '',
      admission_dept: basic.admission_dept_name || '',
      discharge_dept: basic.discharge_dept_name || '',
      admission_ward: basic.admission_ward_name || '',
      discharge_ward: basic.discharge_ward_name || '',
      transfer_dept: basic.transfer_dept_name || '',
      admission_datetime: basic.admission_datetime || '',
      discharge_datetime: basic.discharge_datetime || '',
      actual_hospital_days: basic.hospital_duration || '',
      leaving_hospital_way: basic.leaving_hospital_way || '',
      rehospital_within_month: basic.rehospital_with_month || ''
    },
    diagnoses: {
      discharge_main_diagnosis_text: mainDiag?.diagnosis_name || null,
      discharge_main_icd: mainDiag?.diagnosis_code || null,
      admission_condition: mainDiag?.admission_condition || null,
      discharge_other_diagnoses_texts: otherDiags.map((d) => d?.diagnosis_name || '').filter(Boolean),
      discharge_other_icds: otherDiags.map((d) => d?.diagnosis_code || '').filter(Boolean)
    },
    procedures: {
      main_procedure_text: mainProc?.surgery_name || null,
      main_procedure_code: mainProc?.surgery_code || null,
      main_procedure_date: normalizeDate(mainProc?.surgery_begin_datetime),
      main_procedure_level: mainProc?.surgical_level || null,
      anesthesia_method: mainProc?.anesthesia_method || null,
      incision_healing_grade: mainProc?.surgical_incisionheal_level || null,
      other_procedures: otherProcs.map((p) => ({
        text: p?.surgery_name || p?.text || '',
        code: p?.surgery_code || p?.code || '',
        date: normalizeDate(p?.surgery_begin_datetime || p?.date)
      }))
    },
    other_medical_info: {
      drug_allergy_flag: basic.allergy_sign || '',
      abo_blood_type: basic.abo_blood_code || '',
      rh_blood_type: basic.rh_blood_code || ''
    },
    staff: {
      dept_director: basic.deptdirector_sign || '',
      chief_physician: basic.chief_physician_sign || '',
      attending_physician: basic.attending_physician_sign || '',
      resident_physician: basic.resident_physician_sign || '',
      responsible_nurse: basic.responsible_nurse_sign || '',
      coder: basic.coder_sign || '',
      medical_record_quality: basic.medicalrecord_quality || ''
    },
    costs: {
      total_cost: cost.total_cost || '',
      self_paid: cost.self_pay || ''
    }
  }
})

const srcdoc = computed(() => {
  const { deMap, diagnosisRows, procedureRows } = frontPageDraftToDeMap(normalizedDraft.value)
  const filledBodyHtml = applyDeValuesToHmTemplateBody(templateBodyHtml, deMap, diagnosisRows, procedureRows)
  return buildHmTemplateSrcdoc({ filledBodyHtml, contentsCss, printCss })
})

function normalizeEvidenceKey(text: string): string {
  return String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[\s\u3000，,。；;：:“”"'‘’、()（）【】\[\]\-—_]/g, '')
}

const diagnosisEvidenceList = computed(() => {
  const arr = props.data?.evidence?.diagnoses
  return Array.isArray(arr) ? arr : []
})

const diagnosisEvidenceMap = computed(() => {
  const map = new Map<string, any>()
  diagnosisEvidenceList.value.forEach((item: any) => {
    const key = normalizeEvidenceKey(item?.diagnosis_text)
    if (key && !map.has(key)) map.set(key, item)
  })
  return map
})

function findDiagnosisEvidence(name: string): any {
  const key = normalizeEvidenceKey(name)
  if (!key) return null
  const direct = diagnosisEvidenceMap.value.get(key)
  if (direct) return direct
  return diagnosisEvidenceList.value.find((item: any) => {
    const k = normalizeEvidenceKey(item?.diagnosis_text)
    return k && (k.includes(key) || key.includes(k))
  }) || null
}

const evidencePanel = reactive<{ visible: boolean; item: any | null }>({
  visible: false,
  item: null
})

const showAllRawEvidence = ref(false)

const evidenceRawLines = computed(() => {
  const lines = evidencePanel.item?.raw_evidence_lines
  return Array.isArray(lines) ? lines : []
})

const hasMoreRawEvidence = computed(() => evidenceRawLines.value.length > 3)

const evidenceRawLinesToShow = computed(() => {
  if (showAllRawEvidence.value) return evidenceRawLines.value
  return evidenceRawLines.value.slice(0, 3)
})

function toggleRawEvidenceExpand() {
  showAllRawEvidence.value = !showAllRawEvidence.value
}

function openDiagnosisEvidence(name: string) {
  const item = findDiagnosisEvidence(name)
  if (!item) return
  evidencePanel.item = item
  evidencePanel.visible = true
  showAllRawEvidence.value = false
}

function closeDiagnosisEvidence() {
  evidencePanel.visible = false
  evidencePanel.item = null
  showAllRawEvidence.value = false
}
</script>

<style scoped>
.fp-sheet-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fp-pending {
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #1e3a8a;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
}

.fp-frame-wrap {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  overflow: auto;
  max-height: calc(100vh - 220px);
}

.fp-frame {
  width: 100%;
  min-height: 2500px;
  border: 0;
  background: #fff;
}

.fp-evidence-section {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 14px;
  padding: 12px;
}

.fp-evidence-title {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 8px;
}

.fp-evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fp-evidence-btn {
  border: 1px solid #bfdbfe;
  background: #f8fbff;
  border-radius: 999px;
  padding: 6px 10px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.fp-evidence-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fp-evidence-btn-name {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #1e293b;
}

.fp-evidence-btn-tag {
  font-size: 12px;
  color: #2563eb;
  border: 1px solid #93c5fd;
  border-radius: 999px;
  padding: 1px 7px;
}

.evidence-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  background: rgba(15, 23, 42, 0.24);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}

.evidence-card {
  width: min(860px, calc(100vw - 32px));
  max-height: calc(100vh - 60px);
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #dbe2f0;
  padding: 16px;
}

.evidence-title {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
  margin-bottom: 8px;
}

.evidence-meta {
  font-size: 14px;
  color: #334155;
  margin-bottom: 6px;
}

.evidence-block {
  margin-top: 10px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  background: #f8fbff;
}

.evidence-block-title {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
  margin-bottom: 8px;
}

.evidence-quote,
.evidence-logic,
.evidence-check-exp,
.evidence-check-quote,
.evidence-raw-line {
  font-size: 14px;
  color: #1e293b;
  line-height: 1.65;
}

.evidence-check + .evidence-check {
  margin-top: 10px;
}

.evidence-check-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 4px;
}

.evidence-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  height: 24px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.evidence-pill.ok {
  color: #047857;
  background: #d1fae5;
  border: 1px solid #86efac;
}

.evidence-pill.pending {
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fde68a;
}

.evidence-raw-tag {
  display: inline-block;
  margin-right: 8px;
  color: #475569;
  font-weight: 600;
}

.evidence-btn-inline {
  margin-top: 8px;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  background: #fff;
  border-radius: 999px;
  padding: 2px 10px;
  cursor: pointer;
}

.evidence-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.evidence-close-btn {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: 10px;
  min-width: 76px;
  height: 34px;
  font-size: 14px;
  cursor: pointer;
}
</style>
