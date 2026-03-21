<template>
  <div class="fp-sheet-wrap">
    <div v-if="diagnosisGenerationPending" class="fp-pending">
      正在生成诊断编码与证据，请稍候...
    </div>

    <!-- ===== 原生表格渲染的病案首页 ===== -->
    <div class="fp-wrapper">
      <!-- 标题 -->
      <h1 class="fp-title">住 院 病 案 首 页</h1>

      <!-- 顶部：医疗机构、付费方式、病案号 -->
      <table class="fp-tbl" style="border-top:none;">
        <tr>
          <td style="width:50%; border-top:none;">医疗机构:<u class="fill">{{ d.hospitalization.hospital_name }}</u></td>
          <td style="width:50%; border-top:none;">（组织机构代码:<u class="fill">{{ d.hospitalization.organization_code }}</u>）</td>
        </tr>
        <tr>
          <td colspan="2">医疗付费方式:<u class="fill">{{ d.hospitalization.payment_method_text }}</u></td>
        </tr>
        <tr>
          <td>病案号:<u class="fill">{{ d.hospitalization.medical_record_no }}</u></td>
          <td>第<u class="fill">{{ d.hospitalization.admission_times_in_hospital }}</u>次住院</td>
        </tr>
      </table>

      <!-- ===== 基本信息 ===== -->
      <div class="fp-sec-hd">基本信息</div>
      <table class="fp-tbl">
        <tr>
          <td style="width:14%">姓名<u class="fill">{{ d.basic_info.patient_name }}</u></td>
          <td style="width:16%">性别<u class="fill">{{ d.basic_info.gender }}</u></td>
          <td style="width:20%">出生日期<u class="fill">{{ d.basic_info.birth_date }}</u></td>
          <td style="width:14%">年龄<u class="fill">{{ d.basic_info.age_years }}</u>岁</td>
          <td style="width:12%">国籍<u class="fill">{{ d.basic_info.nationality }}</u></td>
          <td style="width:12%">民族<u class="fill">{{ d.basic_info.ethnicity }}</u></td>
        </tr>
        <tr>
          <td colspan="3">身份证号<u class="fill">{{ d.basic_info.id_number }}</u></td>
          <td>职业<u class="fill">{{ d.basic_info.occupation }}</u></td>
          <td colspan="2">婚姻<u class="fill">{{ d.basic_info.marital_status }}</u></td>
        </tr>
        <tr>
          <td colspan="6">现住址<u class="fill">{{ d.basic_info.current_address }}</u></td>
        </tr>
        <tr>
          <td colspan="3">工作单位及地址<u class="fill">{{ d.basic_info.work_unit }}</u></td>
          <td colspan="3">籍贯<u class="fill">{{ d.basic_info.nativeplace }}</u></td>
        </tr>
        <tr>
          <td>联系人姓名<u class="fill">{{ d.basic_info.contact_name }}</u></td>
          <td>关系<u class="fill">{{ d.basic_info.contact_relation }}</u></td>
          <td colspan="2">地址<u class="fill">{{ d.basic_info.contact_address }}</u></td>
          <td colspan="2">电话<u class="fill">{{ d.basic_info.contact_phone }}</u></td>
        </tr>
      </table>

      <!-- ===== 住院信息 ===== -->
      <div class="fp-sec-hd">住院诊疗信息</div>
      <table class="fp-tbl">
        <tr>
          <td colspan="6">入院途径<u class="fill">{{ d.hospitalization.admission_way_text }}</u> □ 1.急诊 &nbsp; 2.门诊 &nbsp; 3.其他医疗机构转入 &nbsp; 9.其他</td>
        </tr>
        <tr>
          <td colspan="2">入院时间<u class="fill">{{ d.hospitalization.admission_datetime }}</u></td>
          <td>入院科别<u class="fill">{{ d.hospitalization.admission_dept }}</u></td>
          <td>病房<u class="fill">{{ d.hospitalization.admission_ward }}</u></td>
          <td>转科科别<u class="fill">{{ d.hospitalization.transfer_dept }}</u></td>
          <td>&nbsp;</td>
        </tr>
        <tr>
          <td colspan="2">出院时间<u class="fill">{{ d.hospitalization.discharge_datetime }}</u></td>
          <td>出院科别<u class="fill">{{ d.hospitalization.discharge_dept }}</u></td>
          <td>病房<u class="fill">{{ d.hospitalization.discharge_ward }}</u></td>
          <td>实际住院<u class="fill">{{ d.hospitalization.actual_hospital_days }}</u>天</td>
          <td>&nbsp;</td>
        </tr>
      </table>

      <!-- 门急诊诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="3">门(急)诊诊断<u class="fill">{{ mainDiag?.diagnosis_name || '' }}</u></td>
          <td colspan="3">疾病编码<u class="fill">{{ mainDiag?.diagnosis_code || '' }}</u></td>
        </tr>
      </table>

      <!-- 入院诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="3">入院诊断<u class="fill">{{ mainDiag?.diagnosis_name || '' }}</u></td>
          <td colspan="3">疾病编码<u class="fill">{{ mainDiag?.diagnosis_code || '' }}</u></td>
        </tr>
      </table>

      <!-- ===== 出院诊断（双列布局） ===== -->
      <table class="fp-tbl">
        <tr class="hd-row">
          <td style="width:25%">出院诊断</td>
          <td style="width:10%">疾病编码</td>
          <td style="width:8%">入院<br/>病情</td>
          <td style="width:25%">出院诊断</td>
          <td style="width:10%">疾病编码</td>
          <td style="width:8%">入院<br/>病情</td>
        </tr>
        <tr v-for="(row, i) in diagnosisPairedRows" :key="'d'+i" class="data-row">
          <!-- 左列 -->
          <td>
            {{ row.left.label }}{{ row.left.name }}
            <button
              v-if="row.left.name && findDiagnosisEvidence(row.left.name)"
              type="button"
              class="fp-inline-evidence"
              @click="openDiagnosisEvidence(row.left.name)"
            >
              证据
            </button>
          </td>
          <td class="center mono">{{ row.left.code }}</td>
          <td class="center">{{ row.left.condition }}</td>
          <!-- 右列 -->
          <td>
            {{ row.right.label }}{{ row.right.name }}
            <button
              v-if="row.right.name && findDiagnosisEvidence(row.right.name)"
              type="button"
              class="fp-inline-evidence"
              @click="openDiagnosisEvidence(row.right.name)"
            >
              证据
            </button>
          </td>
          <td class="center mono">{{ row.right.code }}</td>
          <td class="center">{{ row.right.condition }}</td>
        </tr>
        <tr>
          <td colspan="3">入院病情：1.有，2.临床未确定，3.情况不明，4.无</td>
          <td colspan="3"></td>
        </tr>
      </table>

      <!-- 损伤中毒外因、病理诊断 -->
      <table class="fp-tbl">
        <tr>
          <td colspan="2">损伤、中毒的外部原因<u class="fill"></u></td>
          <td colspan="2">疾病编码<u class="fill"></u></td>
        </tr>
        <tr>
          <td>病理诊断<u class="fill"></u></td>
          <td>疾病编码<u class="fill"></u></td>
          <td>病理号<u class="fill"></u></td>
          <td>TNM分期<u class="fill"></u></td>
        </tr>
      </table>

      <!-- ===== 手术信息 ===== -->
      <table class="fp-tbl">
        <tr class="hd-row">
          <td rowspan="2" style="width:20%">手术及操作名称</td>
          <td rowspan="2" style="width:12%">手术及操作编码</td>
          <td rowspan="2" style="width:12%">手术操作日期</td>
          <td rowspan="2" style="width:8%">手术级别</td>
          <td colspan="3">手术及操作医师</td>
          <td rowspan="2" style="width:8%">切口愈合<br/>等级</td>
          <td rowspan="2" style="width:8%">麻醉方式</td>
          <td rowspan="2" style="width:8%">麻醉医师</td>
        </tr>
        <tr class="hd-row">
          <td style="width:8%">术者</td>
          <td style="width:8%">I助</td>
          <td style="width:8%">II助</td>
        </tr>
        <tr v-for="(s, i) in paddedSurgeries" :key="'s'+i" class="data-row">
          <td>{{ s.text || '' }}</td>
          <td class="center mono">{{ s.code || '' }}</td>
          <td class="center">{{ s.date || '' }}</td>
          <td class="center">{{ s.level || '' }}</td>
          <td class="center"></td>
          <td class="center"></td>
          <td class="center"></td>
          <td class="center">{{ s.healing || '' }}</td>
          <td class="center">{{ s.anesthesia || '' }}</td>
          <td class="center"></td>
        </tr>
      </table>

      <!-- ===== 其他医学信息 ===== -->
      <div class="fp-sec-hd">其他信息</div>
      <table class="fp-tbl">
        <tr>
          <td colspan="3">药物过敏<u class="fill">{{ d.other_medical_info.drug_allergy_flag }}</u> □ 1.无 &nbsp; 2.有</td>
          <td colspan="3">死亡患者尸检 □ 1.是 2.否</td>
        </tr>
        <tr>
          <td colspan="3">血型<u class="fill">{{ d.other_medical_info.abo_blood_type }}</u> □ 1.A &nbsp; 2.B &nbsp; 3.O &nbsp; 4.AB &nbsp; 5.不详 &nbsp; 6.未查</td>
          <td colspan="3">Rh<u class="fill">{{ d.other_medical_info.rh_blood_type }}</u> □ 1.阴 &nbsp; 2.阳 &nbsp; 3.不详 &nbsp; 4.未查</td>
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
      <div class="fp-sec-hd">签名</div>
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
          <td colspan="3">病案质量<u class="fill">{{ d.staff.medical_record_quality }}</u></td>
        </tr>
      </table>

      <div class="fp-footer">（注：本首页由 AI 自动提取生成，仅供参考，需人工审核确认）</div>
    </div>

    <!-- ===== 诊断证据区域（保持不变） ===== -->
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
        <div class="evidence-meta">定位：{{ evidencePanel.item.quote_location || '-' }}</div>
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

        <div v-if="evidencePanel.item.coder_summary" class="evidence-block">
          <div class="evidence-block-title">编码员裁决摘要</div>
          <div class="evidence-logic">{{ evidencePanel.item.coder_summary }}</div>
        </div>

        <div
          v-if="evidencePanel.item.candidate_analysis && Array.isArray(evidencePanel.item.candidate_analysis.candidates)"
          class="evidence-block"
        >
          <div class="evidence-block-title">候选诊断对比（主诊断判定）</div>
          <table class="evidence-candidate-table">
            <thead>
              <tr>
                <th>候选诊断</th>
                <th>评分</th>
                <th>来源定位</th>
                <th>入选/淘汰依据</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(cand, idx) in evidencePanel.item.candidate_analysis.candidates"
                :key="`${cand.diagnosis_text || ''}-${idx}`"
              >
                <td>{{ cand.diagnosis_text || '-' }}</td>
                <td>{{ cand.score ?? '-' }}</td>
                <td>{{ cand.quote_location || cand.section || '-' }}</td>
                <td>
                  <div v-if="Array.isArray(cand.reasons) && cand.reasons.length">
                    <div v-for="(r, i) in cand.reasons" :key="`r-${i}`">+ {{ r }}</div>
                  </div>
                  <div v-if="Array.isArray(cand.reject_reasons) && cand.reject_reasons.length" class="evidence-candidate-reject">
                    <div v-for="(r, i) in cand.reject_reasons" :key="`x-${i}`">- {{ r }}</div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
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
            <div v-if="ck.rule_ref" class="evidence-check-rule">{{ ck.rule_ref }}</div>
            <div v-if="ck.evidence_quote" class="evidence-check-quote">{{ ck.evidence_quote }}</div>
          </div>
        </div>

        <div
          v-if="Array.isArray(evidencePanel.item.manual_review_points) && evidencePanel.item.manual_review_points.length"
          class="evidence-block"
        >
          <div class="evidence-block-title">人工复核要点</div>
          <div v-for="(p, i) in evidencePanel.item.manual_review_points" :key="`manual-${i}`" class="evidence-raw-line">
            {{ i + 1 }}. {{ p }}
          </div>
        </div>

        <div
          v-if="Array.isArray(evidencePanel.item.raw_evidence_lines) && evidencePanel.item.raw_evidence_lines.length"
          class="evidence-block"
        >
          <div class="evidence-block-title">已用病历原文</div>
          <div v-for="(line, idx) in evidenceRawLines" :key="idx" class="evidence-raw-line">
            <span class="evidence-raw-tag">[{{ line.source || '病历原文' }} | {{ line.role || '证据' }}]</span>
            <span>{{ line.text }}</span>
          </div>

        </div>

        <div class="evidence-actions">
          <button type="button" class="evidence-close-btn" @click="closeDiagnosisEvidence">关闭</button>
        </div>
      </div>
    </div>
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

/** 标准化后的首页数据（与之前的 normalizedDraft 相同） */
const d = computed(() => {
  const src = props.data || {}
  const basic = src.basic || {}
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
    healing: s?.surgical_incisionheal_level || '',
    anesthesia: s?.anesthesia_method || '',
  }))
  const minRows = Math.max(8, rows.length + 1)
  while (rows.length < minRows) rows.push({ text: '', code: '', date: '', level: '', healing: '', anesthesia: '' })
  return rows
})

// ===== 诊断证据逻辑（保持不变） =====
function normalizeEvidenceKey(text: string): string {
  return String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[\s\u3000，,。；;：:""\"'''、()（）【】\[\]\-—_]/g, '')
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


const evidenceRawLines = computed(() => {
  const lines = evidencePanel.item?.raw_evidence_lines
  return Array.isArray(lines) ? lines : []
})

const hasMoreRawEvidence = computed(() => evidenceRawLines.value.length > 3)

const evidenceRawLines = computed(() => {
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
}

function closeDiagnosisEvidence() {
  evidencePanel.visible = false
  evidencePanel.item = null
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
  border: 1px solid #c7d2fe;
  background: #eef2ff;
  color: #1e3a8a;
  border-radius: 12px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 600;
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
.fp-inline-evidence {
  margin-left: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
