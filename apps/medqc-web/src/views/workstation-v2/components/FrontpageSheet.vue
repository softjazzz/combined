<template>
  <div class="fp-sheet-wrap">
    <div
      v-if="diagnosisGenerationPending"
      class="fp-pending"
      role="status"
      aria-live="polite"
    >
      <div class="fp-pending__top">
        <div class="fp-pending__title-wrap">
          <span class="fp-pending__icon">⚕</span>
          <div>
            <div class="fp-pending__title">
              正在生成诊断编码与证据
            </div>
            <div class="fp-pending__sub">
              AI 正在解析病历并构建证据链，请稍候片刻
            </div>
          </div>
        </div>
        <span class="fp-pending__badge">AI 处理中</span>
      </div>
      <div class="fp-pending__bar">
        <span class="fp-pending__bar-inner" />
      </div>
    </div>

    <!-- ===== 原生表格渲染的病案首页 ===== -->
    <div class="fp-wrapper">
      <!-- 标题 -->
      <h1 class="fp-title">
        住 院 病 案 首 页
      </h1>

      <!-- 顶部：医疗机构、付费方式、病案号 -->
      <table
        class="fp-tbl"
        style="border-top:none;"
      >
        <tr>
          <td style="width:50%; border-top:none;">
            医疗机构:<u class="fill">{{ d.hospitalization.hospital_name }}</u>
          </td>
          <td style="width:50%; border-top:none;">
            （组织机构代码:<u class="fill">{{ d.hospitalization.organization_code }}</u>）
          </td>
        </tr>
        <tr>
          <td colspan="2">
            医疗付费方式:<u class="fill">{{ d.hospitalization.payment_method_text }}</u>
          </td>
        </tr>
        <tr>
          <td>病案号:<u class="fill">{{ d.hospitalization.medical_record_no }}</u></td>
          <td>第<u class="fill">{{ d.hospitalization.admission_times_in_hospital }}</u>次住院</td>
        </tr>
      </table>

      <!-- ===== 基本信息 ===== -->
      <div class="fp-sec-hd">
        基本信息
      </div>
      <table class="fp-tbl">
        <tr>
          <td style="width:14%">
            姓名<u class="fill">{{ d.basic_info.patient_name }}</u>
          </td>
          <td style="width:16%">
            性别<u class="fill">{{ d.basic_info.gender }}</u>
          </td>
          <td style="width:20%">
            出生日期<u class="fill">{{ d.basic_info.birth_date }}</u>
          </td>
          <td style="width:14%">
            年龄<u class="fill">{{ d.basic_info.age_years }}</u>岁
          </td>
          <td style="width:12%">
            国籍<u class="fill">{{ d.basic_info.nationality }}</u>
          </td>
          <td style="width:12%">
            民族<u class="fill">{{ d.basic_info.ethnicity }}</u>
          </td>
        </tr>
        <tr>
          <td colspan="3">
            身份证号<u class="fill">{{ d.basic_info.id_number }}</u>
          </td>
          <td>职业<u class="fill">{{ d.basic_info.occupation }}</u></td>
          <td colspan="2">
            婚姻<u class="fill">{{ d.basic_info.marital_status }}</u>
          </td>
        </tr>
        <tr>
          <td colspan="6">
            现住址<u class="fill">{{ d.basic_info.current_address }}</u>
          </td>
        </tr>
        <tr>
          <td colspan="3">
            工作单位及地址<u class="fill">{{ d.basic_info.work_unit }}</u>
          </td>
          <td colspan="3">
            籍贯<u class="fill">{{ d.basic_info.nativeplace }}</u>
          </td>
        </tr>
        <tr>
          <td>联系人姓名<u class="fill">{{ d.basic_info.contact_name }}</u></td>
          <td>关系<u class="fill">{{ d.basic_info.contact_relation }}</u></td>
          <td colspan="2">
            地址<u class="fill">{{ d.basic_info.contact_address }}</u>
          </td>
          <td colspan="2">
            电话<u class="fill">{{ d.basic_info.contact_phone }}</u>
          </td>
        </tr>
      </table>

      <!-- ===== 住院信息 ===== -->
      <div class="fp-sec-hd">
        住院诊疗信息
      </div>
      <table class="fp-tbl">
        <tr>
          <td colspan="6">
            入院途径<u class="fill">{{ d.hospitalization.admission_way_text }}</u> □ 1.急诊 &nbsp; 2.门诊 &nbsp; 3.其他医疗机构转入 &nbsp; 9.其他
          </td>
        </tr>
        <tr>
          <td colspan="2">
            入院时间<u class="fill">{{ d.hospitalization.admission_datetime }}</u>
          </td>
          <td>入院科别<u class="fill">{{ d.hospitalization.admission_dept }}</u></td>
          <td>病房<u class="fill">{{ d.hospitalization.admission_ward }}</u></td>
          <td>转科科别<u class="fill">{{ d.hospitalization.transfer_dept }}</u></td>
          <td>&nbsp;</td>
        </tr>
        <tr>
          <td colspan="2">
            出院时间<u class="fill">{{ d.hospitalization.discharge_datetime }}</u>
          </td>
          <td>出院科别<u class="fill">{{ d.hospitalization.discharge_dept }}</u></td>
          <td>病房<u class="fill">{{ d.hospitalization.discharge_ward }}</u></td>
          <td>实际住院<u class="fill">{{ d.hospitalization.actual_hospital_days }}</u>天</td>
          <td>&nbsp;</td>
        </tr>
      </table>

      <!-- 门急诊诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="3">
            门(急)诊诊断<u class="fill">{{ mainDiag?.diagnosis_name || '' }}</u>
          </td>
          <td colspan="3">
            疾病编码<u class="fill">{{ mainDiag?.diagnosis_code || '' }}</u>
          </td>
        </tr>
      </table>

      <!-- 入院诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="3">
            入院诊断<u class="fill">{{ mainDiag?.diagnosis_name || '' }}</u>
          </td>
          <td colspan="3">
            疾病编码<u class="fill">{{ mainDiag?.diagnosis_code || '' }}</u>
          </td>
        </tr>
      </table>

      <!-- ===== 出院诊断（双列布局） ===== -->
      <table class="fp-tbl">
        <tr class="hd-row">
          <td style="width:25%">
            出院诊断
          </td>
          <td style="width:10%">
            疾病编码
          </td>
          <td style="width:8%">
            入院<br>病情
          </td>
          <td style="width:25%">
            出院诊断
          </td>
          <td style="width:10%">
            疾病编码
          </td>
          <td style="width:8%">
            入院<br>病情
          </td>
        </tr>
        <tr
          v-for="(row, i) in diagnosisPairedRows"
          :key="'d'+i"
          class="data-row"
        >
          <!-- 左列 -->
          <td>
            <div class="fp-diag-cell">
              <span class="fp-diag-text">{{ row.left.label }}{{ row.left.name }}</span>
              <span
                v-if="row.left.name && isSystemRecommendedDiagnosis(row.left.name)"
                class="fp-recommend-tag"
              >
                更适合作为主要诊断（系统推荐）
              </span>
              <button
                v-if="row.left.name && isMainDiagnosisName(row.left.name)"
                type="button"
                class="fp-inline-evidence"
                :disabled="!canOpenMainEvidence"
                @click="openDiagnosisEvidence(row.left.name)"
              >
                证据
              </button>
            </div>
          </td>
          <td class="center mono">
            {{ row.left.code }}
          </td>
          <td class="center">
            {{ row.left.condition }}
          </td>
          <!-- 右列 -->
          <td>
            <div class="fp-diag-cell">
              <span class="fp-diag-text">{{ row.right.label }}{{ row.right.name }}</span>
              <span
                v-if="row.right.name && isSystemRecommendedDiagnosis(row.right.name)"
                class="fp-recommend-tag"
              >
                更适合作为主要诊断（系统推荐）
              </span>
              <button
                v-if="row.right.name && isMainDiagnosisName(row.right.name)"
                type="button"
                class="fp-inline-evidence"
                :disabled="!canOpenMainEvidence"
                @click="openDiagnosisEvidence(row.right.name)"
              >
                证据
              </button>
            </div>
          </td>
          <td class="center mono">
            {{ row.right.code }}
          </td>
          <td class="center">
            {{ row.right.condition }}
          </td>
        </tr>
        <tr>
          <td colspan="3">
            入院病情：1.有，2.临床未确定，3.情况不明，4.无
          </td>
          <td colspan="3" />
        </tr>
      </table>

      <!-- 损伤中毒外因、病理诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="2">
            损伤、中毒的外部原因<u class="fill">{{ d.other_medical_info.injury_poison_cause_text || '' }}</u>
          </td>
          <td colspan="2">
            疾病编码<u class="fill">{{ d.other_medical_info.injury_poison_cause_icd || '' }}</u>
          </td>
        </tr>
        <tr>
          <td>病理诊断<u class="fill">{{ d.other_medical_info.pathology_text || '' }}</u></td>
          <td>疾病编码<u class="fill">{{ d.other_medical_info.pathology_icd || '' }}</u></td>
          <td>病理号<u class="fill">{{ d.other_medical_info.pathology_no || '' }}</u></td>
          <td>TNM分期<u class="fill" /></td>
        </tr>
      </table>

      <!-- ===== 手术信息 ===== -->
      <table class="fp-tbl">
        <tr class="hd-row">
          <td
            rowspan="2"
            style="width:20%"
          >
            手术及操作名称
          </td>
          <td
            rowspan="2"
            style="width:12%"
          >
            手术及操作编码
          </td>
          <td
            rowspan="2"
            style="width:12%"
          >
            手术操作日期
          </td>
          <td
            rowspan="2"
            style="width:8%"
          >
            手术级别
          </td>
          <td colspan="3">
            手术及操作医师
          </td>
          <td
            rowspan="2"
            style="width:8%"
          >
            切口愈合<br>等级
          </td>
          <td
            rowspan="2"
            style="width:8%"
          >
            麻醉方式
          </td>
          <td
            rowspan="2"
            style="width:8%"
          >
            麻醉医师
          </td>
        </tr>
        <tr class="hd-row">
          <td style="width:8%">
            术者
          </td>
          <td style="width:8%">
            I助
          </td>
          <td style="width:8%">
            II助
          </td>
        </tr>
        <tr
          v-for="(s, i) in paddedSurgeries"
          :key="'s'+i"
          class="data-row"
        >
          <td>{{ s.text || '' }}</td>
          <td class="center mono">
            {{ s.code || '' }}
          </td>
          <td class="center">
            {{ s.date || '' }}
          </td>
          <td class="center">
            {{ s.level || '' }}
          </td>
          <td class="center">
            {{ formatDoctorDisplay(s.surgeon, s.surgeonCode) }}
          </td>
          <td class="center">
            {{ formatDoctorDisplay(s.assistant1, s.assistant1Code) }}
          </td>
          <td class="center">
            {{ formatDoctorDisplay(s.assistant2, s.assistant2Code) }}
          </td>
          <td class="center">
            {{ s.healing || '' }}
          </td>
          <td class="center">
            {{ s.anesthesia || '' }}
          </td>
          <td class="center">
            {{ formatDoctorDisplay(s.anesthetist, s.anesthetistCode) }}
          </td>
        </tr>
      </table>

      <!-- ===== 其他医学信息 ===== -->
      <div class="fp-sec-hd">
        其他信息
      </div>
      <table class="fp-tbl">
        <tr>
          <td colspan="3">
            药物过敏<u class="fill">{{ d.other_medical_info.drug_allergy_flag }}</u> □ 1.无 &nbsp; 2.有
          </td>
          <td colspan="3">
            死亡患者尸检 □ 1.是 2.否
          </td>
        </tr>
        <tr>
          <td colspan="3">
            血型<u class="fill">{{ d.other_medical_info.abo_blood_type }}</u> □ 1.A &nbsp; 2.B &nbsp; 3.O &nbsp; 4.AB &nbsp; 5.不详 &nbsp; 6.未查
          </td>
          <td colspan="3">
            Rh<u class="fill">{{ d.other_medical_info.rh_blood_type }}</u> □ 1.阴 &nbsp; 2.阳 &nbsp; 3.不详 &nbsp; 4.未查
          </td>
        </tr>
        <tr>
          <td colspan="6">
            离院方式<u class="fill">{{ d.hospitalization.leaving_hospital_way }}</u>
            □ 1.医嘱离院 &nbsp; 2.医嘱转院 &nbsp; 3.非医嘱离院 &nbsp; 4.死亡 &nbsp; 9.其他
          </td>
        </tr>
        <tr>
          <td colspan="6">
            是否有出院31天内再住院计划<u class="fill">{{ d.hospitalization.rehospital_within_month }}</u>
            □ 1.无 &nbsp; 2.有
          </td>
        </tr>
      </table>

      <!-- ===== 签名区 ===== -->
      <div class="fp-sec-hd">
        签名
      </div>
      <table class="fp-tbl">
        <tr>
          <td>科主任<u class="fill">{{ d.staff.dept_director }}</u></td>
          <td>主(副主)任医师<u class="fill">{{ d.staff.chief_physician }}</u></td>
          <td>主治医师<u class="fill">{{ d.staff.attending_physician }}</u></td>
        </tr>
        <tr>
          <td>住院医师<u class="fill">{{ d.staff.resident_physician }}</u></td>
          <td>责任护士<u class="fill">{{ d.staff.responsible_nurse }}</u></td>
          <td>编码员<u class="fill">{{ d.staff.coder }}</u></td>
        </tr>
        <tr>
          <td colspan="3">
            病案质量<u class="fill">{{ d.staff.medical_record_quality }}</u>
          </td>
        </tr>
      </table>

      <div class="fp-footer">
        （注：本首页由 AI 自动提取生成，仅供参考，需人工审核确认）
      </div>
    </div>

    <!-- ===== 诊断证据区域（LLM 主导） ===== -->
    <section
      v-if="mainDiagnosisName"
      class="fp-evidence-section"
    >
      <div class="fp-evidence-title">
        诊断证据
      </div>
      <div
        v-if="riskChipItems.length"
        class="fp-risk-chip-row"
      >
        <span
          v-for="chip in riskChipItems"
          :key="chip.key"
          class="fp-risk-chip"
        >
          {{ chip.label }} {{ chip.count }}
        </span>
      </div>
      <div class="fp-evidence-list">
        <button
          type="button"
          class="fp-evidence-btn"
          :disabled="!canOpenMainEvidence"
          @click="openDiagnosisEvidence(mainDiagnosisName)"
        >
          <span class="fp-evidence-btn-name">{{ mainDiagnosisName }}</span>
          <span class="fp-evidence-btn-tag">LLM证据</span>
        </button>
      </div>
    </section>

    <teleport to="body">
      <div
        v-if="evidencePanel.visible"
        class="evidence-overlay"
        @click.self="closeDiagnosisEvidence"
      >
        <div class="evidence-card">
          <div class="evidence-title">
            主诊断 LLM 证据
          </div>
          <template v-if="mainDiagnosisLlmEvidence || codingAuditLlmEvidence">
            <div class="evidence-block">
              <div class="evidence-block-title">
                LLM主诊断结论
              </div>
              <div class="evidence-meta">
                医生填写主诊断：{{ mainDiagnosisLlmEvidence?.clinician_main_diagnosis || '-' }}
              </div>
              <div class="evidence-meta">
                LLM推荐主诊断：
                <span class="evidence-recommend-main">{{ mainDiagnosisLlmEvidence?.llm_recommended_main_diagnosis || '-' }}</span>
                <span
                  v-if="llmDiffersFromClinician"
                  class="evidence-recommend-label"
                >
                  更适合作为主要诊断（系统推荐）
                </span>
              </div>
              <div class="evidence-meta">
                置信度：{{ llmConfidenceText }}
              </div>
              <div class="evidence-logic">
                {{ mainDiagnosisLlmEvidence?.conclusion || 'LLM已完成主诊断语义裁决。' }}
              </div>
              <div class="evidence-logic">
                {{ mainDiagnosisLlmEvidence?.reasoning_summary || 'LLM推理摘要暂不可用。' }}
              </div>
            </div>

            <div class="evidence-block">
              <div class="evidence-block-title">
                审核风险（Top3）
              </div>
              <div
                v-if="!codingAuditLlmEvidence"
                class="evidence-logic"
              >
                LLM审核暂不可用
              </div>
              <div
                v-else-if="topAuditFindings.length === 0"
                class="evidence-logic"
              >
                {{ codingAuditLlmEvidence.summary || '当前未识别到高风险审核项。' }}
              </div>
              <template v-else>
                <div
                  v-for="(finding, idx) in topAuditFindings"
                  :key="`risk-${idx}`"
                  class="evidence-risk-card"
                >
                  <div class="evidence-risk-head">
                    <span class="evidence-risk-type">{{ formatFindingTypeLabel(finding.type) }}</span>
                    <span class="evidence-risk-severity">{{ formatFindingSeverityLabel(finding.severity) }}</span>
                  </div>
                  <div class="evidence-key-reason">
                    建议：{{ finding.llm_recommendation || '建议人工复核。' }}
                  </div>
                  <div class="evidence-key-meta">
                    原填写：{{ finding.clinician_text || '-' }}
                  </div>
                  <div class="evidence-key-meta">
                    理由：{{ finding.reason || '-' }}
                  </div>
                </div>
              </template>
            </div>

            <div class="evidence-block">
              <div class="evidence-block-title">
                关键证据
              </div>
              <div class="evidence-logic">
                {{ codingAuditLlmEvidence?.summary || 'LLM审核暂不可用' }}
              </div>
              <div
                v-if="!codingAuditLlmEvidence"
                class="evidence-logic"
              >
                LLM审核暂不可用
              </div>
              <div
                v-else-if="topAuditEvidenceGroups.length === 0"
                class="evidence-logic"
              >
                暂无可展示的关键证据。
              </div>
              <template v-else>
                <div
                  v-for="(group, idx) in topAuditEvidenceGroups"
                  :key="`group-${idx}`"
                  class="evidence-key-card"
                >
                  <div class="evidence-risk-head">
                    <span class="evidence-risk-type">{{ formatFindingTypeLabel(group.type) }}</span>
                    <span class="evidence-key-meta">{{ group.llm_recommendation || '建议人工复核' }}</span>
                  </div>
                  <div
                    v-for="(line, evIdx) in group.evidence"
                    :key="`group-${idx}-ev-${evIdx}`"
                    class="evidence-audit-quote"
                  >
                    <div class="evidence-quote">
                      {{ line.quote || '-' }}
                    </div>
                    <div class="evidence-key-meta">
                      来源：{{ line.source || '病历原文' }}
                    </div>
                    <div class="evidence-key-reason">
                      支持理由：{{ line.why_it_supports || '-' }}
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </template>
          <div
            v-else
            class="evidence-block"
          >
            <div class="evidence-block-title">
              LLM主诊断解释
            </div>
            <div class="evidence-logic">
              LLM解释暂不可用
            </div>
          </div>

          <div class="evidence-actions">
            <button
              type="button"
              class="evidence-close-btn"
              @click="closeDiagnosisEvidence"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'

interface DiagnosisItem {
  diagnosis_type?: string
  diagnosis_name?: string
  diagnosis_code?: string
  admission_condition?: string | number
}

interface MainDiagnosisKeyEvidence {
  quote?: string
  source?: string
  why_it_supports?: string
}

interface MainDiagnosisLLMEvidence {
  clinician_main_diagnosis?: string
  llm_recommended_main_diagnosis?: string
  is_consistent_with_clinician?: boolean
  confidence?: number
  conclusion?: string
  key_evidence?: MainDiagnosisKeyEvidence[]
  reasoning_summary?: string
}

type AuditFindingType =
  | 'diagnosis_missing'
  | 'procedure_missing'
  | 'diagnosis_inappropriate'
  | 'diagnosis_insufficient_evidence'

type AuditFindingSeverity = 'high' | 'medium' | 'low'

interface CodingAuditEvidenceLine {
  quote?: string
  source?: string
  why_it_supports?: string
}

interface CodingAuditFinding {
  type?: AuditFindingType
  severity?: AuditFindingSeverity
  clinician_text?: string
  llm_recommendation?: string
  reason?: string
  evidence?: CodingAuditEvidenceLine[]
}

interface CodingAuditLLMEvidence {
  version?: string
  summary?: string
  confidence?: number
  counts?: Partial<Record<AuditFindingType, number>>
  findings?: CodingAuditFinding[]
}

const props = defineProps<{
  data: any
  postProcessing?: boolean
}>()

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
  const hasEvidence = !!mainDiagnosisLlmEvidence.value || !!codingAuditLlmEvidence.value
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

/** 标准化后的首页数据（与之前的 normalizedDraft 相同） */
const d = computed(() => {
  const src = props.data || {}
  const basic = src.basic || {}
  const otherSrc = src.other_medical_info || {}
  const diags: DiagnosisItem[] = Array.isArray(src.diagnoses) ? src.diagnoses : []
  const surgeries: any[] = Array.isArray(src.surgeries) ? src.surgeries : []
  const cost = src.cost || {}

  const mainDiag = diags.find((dd) => String(dd?.diagnosis_type || '').includes('主要')) || first(diags, null)
  const otherDiags = diags.filter((dd) => dd !== mainDiag)

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
      discharge_other_diagnoses_texts: otherDiags.map((dd) => dd?.diagnosis_name || '').filter(Boolean),
      discharge_other_icds: otherDiags.map((dd) => dd?.diagnosis_code || '').filter(Boolean)
    },
    procedures: {
      main_procedure_text: mainProc?.surgery_name || null,
      main_procedure_code: mainProc?.surgery_code || null,
      main_procedure_date: normalizeDate(mainProc?.surgery_begin_datetime),
      main_procedure_level: mainProc?.surgical_level || null,
      surgeon_name: mainProc?.surgeon || null,
      surgeon_code: mainProc?.surgeon_code || null,
      assistant1_name: mainProc?.first_assistant || null,
      assistant1_code: mainProc?.first_assistant_code || null,
      assistant2_name: mainProc?.second_assistant || null,
      assistant2_code: mainProc?.second_assistant_code || null,
      anesthesia_method: mainProc?.anesthesia_method || null,
      anesthetist_name: mainProc?.anesthesiologist || null,
      anesthetist_code: mainProc?.anesthesiologist_code || null,
      incision_healing_grade: mainProc?.surgical_incisionheal_level || null,
      other_procedures: otherProcs.map((p) => ({
        text: p?.surgery_name || p?.text || '',
        code: p?.surgery_code || p?.code || '',
        date: normalizeDate(p?.surgery_begin_datetime || p?.date)
      }))
    },
    other_medical_info: {
      pathology_text: otherSrc.pathology_text || '',
      pathology_icd: otherSrc.pathology_icd || '',
      pathology_no: otherSrc.pathology_no || '',
      injury_poison_cause_text: otherSrc.injury_poison_cause_text || '',
      injury_poison_cause_icd: otherSrc.injury_poison_cause_icd || '',
      drug_allergy_flag: otherSrc.drug_allergy_flag || basic.allergy_sign || '',
      abo_blood_type: otherSrc.abo_blood_type || basic.abo_blood_code || '',
      rh_blood_type: otherSrc.rh_blood_type || basic.rh_blood_code || ''
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

/** 主诊断 */
const mainDiag = computed(() => {
  const list = diagnosisRows.value
  return list.find((dd) => String(dd?.diagnosis_type || '').includes('主要')) || first(list, null)
})

/** 诊断表格（双列布局：左列10行，右列10行，共20个诊断位） */
const diagnosisPairedRows = computed(() => {
  const allDiags = [...diagnosisRows.value]
  const ROWS_PER_COL = 10
  // 填充到至少 ROWS_PER_COL * 2 行
  while (allDiags.length < ROWS_PER_COL * 2) {
    allDiags.push({ diagnosis_name: '', diagnosis_code: '', admission_condition: '' })
  }
  const leftCol = allDiags.slice(0, ROWS_PER_COL)
  const rightCol = allDiags.slice(ROWS_PER_COL, ROWS_PER_COL * 2)
  return leftCol.map((leftItem, idx) => {
    const rightItem = rightCol[idx] || { diagnosis_name: '', diagnosis_code: '', admission_condition: '' }
    return {
      left: {
        label: idx === 0 ? '主要诊断：' : (leftItem.diagnosis_name ? '其他诊断：' : ''),
        name: leftItem.diagnosis_name || '',
        code: leftItem.diagnosis_code || '',
        condition: leftItem.admission_condition || ''
      },
      right: {
        label: idx === 0 ? '其他诊断：' : (rightItem.diagnosis_name ? '' : ''),
        name: rightItem.diagnosis_name || '',
        code: rightItem.diagnosis_code || '',
        condition: rightItem.admission_condition || ''
      }
    }
  })
})

/** 手术表格（至少 8 行） */
const paddedSurgeries = computed(() => {
  const surgeries: any[] = Array.isArray(props.data?.surgeries) ? props.data.surgeries : []
  const rows = surgeries.map((s: any) => ({
    text: s?.surgery_name || s?.text || '',
    code: s?.surgery_code || s?.code || '',
    date: normalizeDate(s?.surgery_begin_datetime || s?.date) || '',
    level: s?.surgical_level || '',
    surgeon: s?.surgeon || s?.surgeon_name || '',
    surgeonCode: s?.surgeon_code || '',
    assistant1: s?.first_assistant || s?.assistant1_name || '',
    assistant1Code: s?.first_assistant_code || s?.assistant1_code || '',
    assistant2: s?.second_assistant || s?.assistant2_name || '',
    assistant2Code: s?.second_assistant_code || s?.assistant2_code || '',
    healing: s?.surgical_incisionheal_level || '',
    anesthesia: s?.anesthesia_method || '',
    anesthetist: s?.anesthesiologist || s?.anesthetist_name || '',
    anesthetistCode: s?.anesthesiologist_code || s?.anesthetist_code || '',
  }))
  const minRows = Math.max(8, rows.length + 1)
  while (rows.length < minRows) {
    rows.push({
      text: '',
      code: '',
      date: '',
      level: '',
      surgeon: '',
      surgeonCode: '',
      assistant1: '',
      assistant1Code: '',
      assistant2: '',
      assistant2Code: '',
      healing: '',
      anesthesia: '',
      anesthetist: '',
      anesthetistCode: '',
    })
  }
  return rows
})

function formatDoctorDisplay(name: unknown, code: unknown): string {
  const doctorName = String(name || '').trim()
  const doctorCode = String(code || '').trim()
  if (doctorName && doctorCode) return `${doctorName}(${doctorCode})`
  return doctorName || doctorCode || ''
}

// ===== 诊断证据逻辑（LLM主导） =====
function normalizeEvidenceKey(text: string): string {
  const normalized = String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[\s\u3000，,。；;：:"'、()（）【】_—-]/g, '')
  return normalized.split('[').join('').split(']').join('')
}

const mainDiagnosisName = computed(() => {
  const main = diagnosisRows.value.find((dd) => String(dd?.diagnosis_type || '').includes('主要')) || first(diagnosisRows.value, null)
  return String(main?.diagnosis_name || '').trim()
})

const mainDiagnosisLlmEvidence = computed<MainDiagnosisLLMEvidence | null>(() => {
  const value = props.data?.evidence?.main_diagnosis_llm
  if (value && typeof value === 'object') return value as MainDiagnosisLLMEvidence
  return null
})

const codingAuditLlmEvidence = computed<CodingAuditLLMEvidence | null>(() => {
  const value = props.data?.evidence?.coding_audit_llm
  if (value && typeof value === 'object') return value as CodingAuditLLMEvidence
  return null
})

const riskTypeOrder: Record<string, number> = {
  diagnosis_inappropriate: 1,
  diagnosis_missing: 2,
  procedure_missing: 3,
  diagnosis_insufficient_evidence: 4,
}

const riskSeverityOrder: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
}

const riskChipItems = computed(() => {
  const counts = codingAuditLlmEvidence.value?.counts
  if (!counts || typeof counts !== 'object') return []
  const list = [
    { key: 'diagnosis_missing', label: '漏写诊断', count: Number(counts.diagnosis_missing || 0) },
    { key: 'procedure_missing', label: '漏写手术', count: Number(counts.procedure_missing || 0) },
    { key: 'diagnosis_inappropriate', label: '主诊断不当', count: Number(counts.diagnosis_inappropriate || 0) },
    { key: 'diagnosis_insufficient_evidence', label: '依据不足', count: Number(counts.diagnosis_insufficient_evidence || 0) },
  ]
  return list.filter((item) => item.count > 0)
})

const topAuditFindings = computed<CodingAuditFinding[]>(() => {
  const rows = codingAuditLlmEvidence.value?.findings
  if (!Array.isArray(rows)) return []
  return rows
    .filter((item) => item && typeof item === 'object')
    .slice()
    .sort((a, b) => {
      const severityDelta =
        (riskSeverityOrder[String(b?.severity || '').toLowerCase()] || 0)
        - (riskSeverityOrder[String(a?.severity || '').toLowerCase()] || 0)
      if (severityDelta !== 0) return severityDelta
      return (
        (riskTypeOrder[String(a?.type || '').toLowerCase()] || 99)
        - (riskTypeOrder[String(b?.type || '').toLowerCase()] || 99)
      )
    })
    .slice(0, 3)
})

const topAuditEvidenceGroups = computed(() => {
  return topAuditFindings.value
    .map((finding) => {
      const evidence = Array.isArray(finding.evidence)
        ? finding.evidence.filter((line) => line && typeof line === 'object')
        : []
      return {
        type: String(finding.type || ''),
        llm_recommendation: String(finding.llm_recommendation || '').trim(),
        evidence: evidence.slice(0, 2)
      }
    })
    .filter((group) => group.evidence.length > 0)
})

const canOpenMainEvidence = computed(() => !!mainDiagnosisName.value)

function isMainDiagnosisName(name: string): boolean {
  const key = normalizeEvidenceKey(name)
  const mainKey = normalizeEvidenceKey(mainDiagnosisName.value)
  if (!key || !mainKey) return false
  return key === mainKey || key.includes(mainKey) || mainKey.includes(key)
}

function isSystemRecommendedDiagnosis(name: string): boolean {
  const ev = mainDiagnosisLlmEvidence.value
  if (!ev || !llmDiffersFromClinician.value) return false
  const recommended = normalizeEvidenceKey(ev.llm_recommended_main_diagnosis || '')
  const current = normalizeEvidenceKey(name || '')
  if (!recommended || !current) return false
  return recommended === current || recommended.includes(current) || current.includes(recommended)
}

const llmDiffersFromClinician = computed(() => {
  const ev = mainDiagnosisLlmEvidence.value
  if (!ev) return false
  if (typeof ev.is_consistent_with_clinician === 'boolean') {
    return !ev.is_consistent_with_clinician
  }
  const clinician = normalizeEvidenceKey(ev.clinician_main_diagnosis || '')
  const recommended = normalizeEvidenceKey(ev.llm_recommended_main_diagnosis || '')
  if (!clinician || !recommended) return false
  return clinician !== recommended
})

const llmConfidenceText = computed(() => {
  const value = mainDiagnosisLlmEvidence.value?.confidence ?? codingAuditLlmEvidence.value?.confidence
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${Math.round(value * 100)}%`
})

function formatFindingTypeLabel(type: unknown): string {
  const key = String(type || '').toLowerCase()
  if (key === 'diagnosis_missing') return '漏写诊断'
  if (key === 'procedure_missing') return '漏写手术'
  if (key === 'diagnosis_inappropriate') return '主诊断不当'
  if (key === 'diagnosis_insufficient_evidence') return '依据不足'
  return '审核项'
}

function formatFindingSeverityLabel(severity: unknown): string {
  const key = String(severity || '').toLowerCase()
  if (key === 'high') return '高风险'
  if (key === 'medium') return '中风险'
  if (key === 'low') return '低风险'
  return '待复核'
}

const evidencePanel = reactive<{ visible: boolean; diagnosisName: string }>({
  visible: false,
  diagnosisName: '',
})

function openDiagnosisEvidence(name: string) {
  if (!isMainDiagnosisName(name)) return
  evidencePanel.diagnosisName = name
  evidencePanel.visible = true
}

function closeDiagnosisEvidence() {
  evidencePanel.visible = false
  evidencePanel.diagnosisName = ''
}
</script>

<style scoped>
/* ===== 住院病案首页 — 像素级还原官方格式（与结算清单风格统一） ===== */
.fp-sheet-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fp-pending {
  border: 1px solid #bfdbfe;
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-radius: 14px;
  padding: 12px 14px 10px;
  box-shadow: 0 8px 22px rgba(37, 99, 235, 0.12);
}

.fp-pending__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.fp-pending__title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.fp-pending__icon {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(37, 99, 235, 0.15);
  color: #1d4ed8;
  font-size: 13px;
  line-height: 1;
  margin-top: 1px;
}

.fp-pending__title {
  color: #1e3a8a;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.25;
}

.fp-pending__sub {
  margin-top: 3px;
  color: #334155;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.3;
}

.fp-pending__badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  border: 1px solid #93c5fd;
  background: #fff;
  color: #1d4ed8;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.fp-pending__bar {
  margin-top: 10px;
  height: 4px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.25);
  overflow: hidden;
}

.fp-pending__bar-inner {
  display: block;
  width: 40%;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb 0%, #38bdf8 100%);
  animation: fpPendingSlide 1.4s ease-in-out infinite;
}

@keyframes fpPendingSlide {
  0% {
    transform: translateX(-120%);
  }
  50% {
    transform: translateX(90%);
  }
  100% {
    transform: translateX(250%);
  }
}

.fp-wrapper {
  max-width: 900px;
  margin: 0 auto;
  font-family: "SimSun", "宋体", "Songti SC", serif;
  font-size: 12px;
  color: #000;
  line-height: 1.5;
  background: #fff;
  padding: 30px 40px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  box-sizing: border-box;
}

/* 主标题 */
.fp-title {
  text-align: center;
  font-size: 24px;
  font-weight: bold;
  letter-spacing: 6px;
  margin: 0 0 10px 0;
  font-family: "SimHei", "黑体", sans-serif;
}

/* 区间大标题（蓝底） */
.fp-sec-hd {
  background: #c5d9ed;
  font-size: 13px;
  font-weight: bold;
  text-align: center;
  padding: 4px 0;
  border: 1px solid #000;
  border-bottom: none;
  margin-top: -1px;
}

/* 通用表格 */
.fp-tbl {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #000;
  margin-top: -1px;
}
.fp-tbl td {
  border: 1px solid #000;
  padding: 3px 5px;
  font-size: 11.5px;
  vertical-align: middle;
  line-height: 1.4;
}

/* 表头行 */
.hd-row td {
  background: #f0f0f0;
  font-weight: bold;
  text-align: center;
  font-size: 11px;
}

/* 下划线填空 */
u.fill {
  border-bottom: 1px solid #000;
  text-decoration: none;
  display: inline;
  padding: 0 4px;
  font-weight: bold;
  min-width: 40px;
}

/* 辅助类 */
.bold { font-weight: bold; }
.center { text-align: center; }
.num { text-align: right; font-family: "Courier New", monospace; font-size: 11.5px; }
.mono { font-family: "Courier New", monospace; }
.fp-diag-cell {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.fp-diag-text {
  flex: 1;
  min-width: 0;
}
.fp-recommend-tag {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid #60a5fa;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  line-height: 1.2;
  white-space: normal;
  text-align: center;
  max-width: 150px;
}
.fp-inline-evidence {
  margin-left: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid #60a5fa;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
  line-height: 1;
  padding: 2px 7px;
  cursor: pointer;
}
.fp-inline-evidence:hover {
  background: #dbeafe;
}

/* 数据行最小高度 */
.data-row td { height: 26px; }

/* 底部注 */
.fp-footer {
  font-size: 10px;
  color: #666;
  text-align: left;
  margin-top: 6px;
  padding-left: 4px;
  font-weight: bold;
}

/* ===== 诊断证据样式（保持不变） ===== */
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

.fp-risk-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.fp-risk-chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1e3a8a;
  border-radius: 999px;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.3;
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
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.45;
  padding-top: 0;
  margin-top: 0;
  margin-bottom: 8px;
  overflow: visible;
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

.evidence-check-rule {
  margin-top: 4px;
  font-size: 12px;
  color: #475569;
}
.evidence-candidate-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.evidence-candidate-table th,
.evidence-candidate-table td {
  border: 1px solid #dbeafe;
  padding: 8px;
  vertical-align: top;
  line-height: 1.5;
}
.evidence-candidate-table th {
  background: #eff6ff;
  color: #1e3a8a;
  text-align: left;
  font-weight: 700;
}
.evidence-candidate-reject {
  margin-top: 4px;
  color: #9a3412;
}
.evidence-key-card {
  border: 1px solid #d7e7ff;
  background: #ffffff;
  border-radius: 10px;
  padding: 10px 10px 8px;
}
.evidence-key-card + .evidence-key-card {
  margin-top: 8px;
}
.evidence-key-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #475569;
  line-height: 1.4;
}
.evidence-key-reason {
  margin-top: 4px;
  font-size: 13px;
  color: #0f172a;
  line-height: 1.6;
}
.evidence-risk-card {
  border: 1px solid #d7e7ff;
  background: #fff;
  border-radius: 10px;
  padding: 10px;
}
.evidence-risk-card + .evidence-risk-card {
  margin-top: 8px;
}
.evidence-risk-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.evidence-risk-type {
  font-size: 13px;
  font-weight: 700;
  color: #1e3a8a;
}
.evidence-risk-severity {
  flex-shrink: 0;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  padding: 1px 7px;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  background: #f8fafc;
}
.evidence-audit-quote + .evidence-audit-quote {
  margin-top: 8px;
}
.evidence-candidate-recommended {
  background: #f0f9ff;
}
.evidence-recommend-main {
  font-weight: 700;
  color: #0f172a;
}
.evidence-recommend-label {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid #93c5fd;
  background: #dbeafe;
  color: #1e3a8a;
  font-size: 12px;
  font-weight: 700;
}
.evidence-recommend-reasons {
  margin-top: 6px;
}
.evidence-reason-line {
  font-size: 13px;
  line-height: 1.5;
}
.evidence-reason-line + .evidence-reason-line {
  margin-top: 3px;
}
.evidence-reason-line.is-support {
  color: #0f172a;
}
.evidence-reason-line.is-risk {
  color: #9a3412;
}
.evidence-toggle-btn {
  margin-bottom: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 8px;
  color: #334155;
  font-size: 12px;
  line-height: 1;
  padding: 4px 8px;
  cursor: pointer;
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

/* 打印样式 */
@media print {
  .fp-wrapper { padding: 0; max-width: none; }
}
</style>
