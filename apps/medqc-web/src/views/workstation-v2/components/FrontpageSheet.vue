<template>
  <!-- 住院病案首页 — 严格按照卫健委官方PDF格式 -->
  <div class="fp-sheet">

    <!-- ===== 顶部标题区 ===== -->
    <div class="fp-line" style="margin-bottom: 2px;">
      <span>医疗机构</span>
      <u class="fill wide">{{ b('institute_county_desc') }}</u>
      <span>（组织机构代码：</span>
      <u class="fill">{{ b('institute_code') }}</u>
      <span>）</span>
    </div>

    <div class="fp-line title-line">
      <span>医疗付费方式：□ <b>{{ b('medical_payment_method') }}</b></span>
      <h1 class="fp-title">住 院 病 案 首 页</h1>
      <span></span>
    </div>

    <div class="fp-line">
      <span>健康卡号：</span>
      <u class="fill">{{ b('insurance_no') }}</u>
      <span style="margin-left:24px;">第</span>
      <u class="fill short">{{ b('visit_cnt') || '1' }}</u>
      <span>次住院</span>
      <span style="margin-left:24px;">病案号：</span>
      <u class="fill">{{ b('document_id') }}</u>
    </div>

    <!-- ===== 身份信息区（下划线填空式） ===== -->
    <div class="fp-line">
      <span>姓名</span>
      <u class="fill"><b>{{ b('name') }}</b></u>
      <span>性别 □</span>
      <u class="fill short">{{ b('sex') }}</u>
      <span class="hint">1.男 2.女</span>
      <span>出生日期</span>
      <u class="fill">{{ b('birthday') }}</u>
      <span>年龄</span>
      <u class="fill short">{{ computedAge }}</u>
      <span>国籍</span>
      <u class="fill short">{{ b('nationality') || '中国' }}</u>
    </div>

    <div class="fp-line">
      <span class="hint">（年龄不足1周岁的）</span>
      <span>年龄</span>
      <u class="fill short"></u>
      <span>月</span>
      <span style="margin-left:16px;">新生儿出生体重</span>
      <u class="fill short"></u>
      <span>克</span>
      <span style="margin-left:16px;">新生儿入院体重</span>
      <u class="fill short"></u>
      <span>克</span>
    </div>

    <div class="fp-line">
      <span>出生地</span>
      <u class="fill wide"></u>
      <span>籍贯</span>
      <u class="fill">{{ b('nativeplace') }}</u>
      <span>民族</span>
      <u class="fill short">{{ b('ethnicity') }}</u>
    </div>

    <div class="fp-line">
      <span>身份证号</span>
      <u class="fill wide">{{ b('id_card_no') }}</u>
      <span>职业</span>
      <u class="fill">{{ b('occupation_category') }}</u>
      <span>婚姻 □</span>
      <u class="fill short">{{ b('marital_status') }}</u>
      <span class="hint">1.未婚 2.已婚 3.丧偶 4.离婚 9.其他</span>
    </div>

    <div class="fp-line">
      <span>现住址</span>
      <u class="fill wide">{{ b('currentaddress') }}</u>
      <span>电话</span>
      <u class="fill">{{ b('contact_number') }}</u>
      <span>邮编</span>
      <u class="fill short"></u>
    </div>

    <div class="fp-line">
      <span>户口地址</span>
      <u class="fill wide"></u>
      <span>邮编</span>
      <u class="fill short"></u>
    </div>

    <div class="fp-line">
      <span>工作单位及地址</span>
      <u class="fill wide">{{ b('work_unit') }}</u>
      <span>单位电话</span>
      <u class="fill"></u>
      <span>邮编</span>
      <u class="fill short"></u>
    </div>

    <div class="fp-line">
      <span>联系人姓名</span>
      <u class="fill">{{ b('contact_name') }}</u>
      <span>关系</span>
      <u class="fill short">{{ b('contact_relationship') }}</u>
      <span>地址</span>
      <u class="fill wide">{{ b('contact_address') }}</u>
      <span>电话</span>
      <u class="fill">{{ b('contact_telephone') }}</u>
    </div>

    <!-- ===== 入院/出院信息 ===== -->
    <div class="fp-line">
      <span>入院途径 □</span>
      <u class="fill short">{{ b('admission_route') }}</u>
      <span class="hint">1.急诊 2.门诊 3.其他医疗机构转入 9.其他</span>
    </div>

    <div class="fp-line">
      <span>入院时间</span>
      <u class="fill">{{ formatDateFull(b('admission_datetime')) }}</u>
      <span>入院科别</span>
      <u class="fill">{{ b('admission_dept_name') }}</u>
      <span>病房</span>
      <u class="fill short">{{ b('admission_ward_name') }}</u>
      <span>转科科别</span>
      <u class="fill">{{ b('transfer_dept_name') }}</u>
    </div>

    <div class="fp-line">
      <span>出院时间</span>
      <u class="fill">{{ formatDateFull(b('discharge_datetime')) }}</u>
      <span>出院科别</span>
      <u class="fill">{{ b('discharge_dept_name') }}</u>
      <span>病房</span>
      <u class="fill short">{{ b('discharge_ward_name') }}</u>
      <span>实际住院</span>
      <u class="fill short">{{ b('hospital_duration') }}</u>
      <span>天</span>
    </div>

    <div class="fp-line">
      <span>门（急）诊诊断</span>
      <u class="fill wide"></u>
      <span>疾病编码</span>
      <u class="fill"></u>
    </div>

    <!-- ===== 出院诊断表（表格） ===== -->
    <table class="fp-table diag-table">
      <thead>
        <tr>
          <th style="width:28%">出院诊断</th>
          <th style="width:12%">疾病编码</th>
          <th style="width:8%">入院<br/>病情</th>
          <th style="width:28%">出院诊断</th>
          <th style="width:12%">疾病编码</th>
          <th style="width:8%">入院<br/>病情</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(pair, idx) in diagnosisPairs" :key="idx">
          <td>
            <span v-if="pair.left">
              <b v-if="idx === 0">主要诊断：</b>
              <span v-else-if="idx === 1" class="hint">其他诊断：</span>
              {{ pair.left.diagnosis_name }}
            </span>
            <span v-else-if="idx === 0">主要诊断：</span>
            <span v-else-if="idx === 1" class="hint">其他诊断：</span>
          </td>
          <td class="mono center">{{ pair.left?.diagnosis_code }}</td>
          <td class="center">{{ pair.left?.admission_condition }}</td>
          <td>
            <span v-if="pair.right">
              <span v-if="idx === 0" class="hint">其他诊断：</span>
              {{ pair.right.diagnosis_name }}
            </span>
            <span v-else-if="idx === 0" class="hint">其他诊断：</span>
          </td>
          <td class="mono center">{{ pair.right?.diagnosis_code }}</td>
          <td class="center">{{ pair.right?.admission_condition }}</td>
        </tr>
      </tbody>
    </table>

    <!-- 入院病情说明 -->
    <div class="fp-line" style="margin-top: 4px;">
      <span><b>入院病情：</b></span>
      <span class="hint">1.有，2.临床未确定，3.情况不明，4.无</span>
    </div>

    <!-- ===== 损伤/病理/过敏/血型（下划线式） ===== -->
    <div class="fp-line">
      <span>损伤、中毒的外部原因</span>
      <u class="fill wide"></u>
      <span>疾病编码</span>
      <u class="fill"></u>
    </div>

    <div class="fp-line">
      <span>病理诊断：</span>
      <u class="fill wide">{{ b('pathology_id') ? '病理号: ' + b('pathology_id') : '' }}</u>
      <span>疾病编码</span>
      <u class="fill"></u>
    </div>

    <div class="fp-line">
      <span>药物过敏 □</span>
      <u class="fill short">{{ b('allergy_sign') === '2' ? '2' : '1' }}</u>
      <span class="hint">1.无 2.有，过敏药物：</span>
      <u class="fill">{{ b('allergy_sign') === '2' ? b('allergy_history') : '' }}</u>
      <span style="margin-left:20px;">死亡患者尸检 □</span>
      <u class="fill short">{{ b('death_autopsy_sign') }}</u>
      <span class="hint">1.是 2.否</span>
    </div>

    <div class="fp-line">
      <span><b>血型</b> □</span>
      <u class="fill short">{{ b('abo_blood_code') }}</u>
      <span class="hint">1.A 2.B 3.O 4.AB 5.不详 6.未查</span>
      <span style="margin-left:16px;">Rh □</span>
      <u class="fill short">{{ b('rh_blood_code') }}</u>
      <span class="hint">1.阴 2.阳 3.不详 4.未查</span>
    </div>

    <!-- ===== 签名区（第一页底部） ===== -->
    <div class="fp-line">
      <span>科主任</span>
      <u class="fill">{{ b('deptdirector_sign') }}</u>
      <span>主任（副主任）医师</span>
      <u class="fill">{{ b('chief_physician_sign') }}</u>
      <span>主治医师</span>
      <u class="fill">{{ b('attending_physician_sign') }}</u>
      <span>住院医师</span>
      <u class="fill">{{ b('resident_physician_sign') }}</u>
    </div>

    <div class="fp-line">
      <span>责任护士</span>
      <u class="fill">{{ b('responsible_nurse_sign') }}</u>
      <span>进修医师</span>
      <u class="fill"></u>
      <span>实习医师</span>
      <u class="fill"></u>
      <span>编码员</span>
      <u class="fill">{{ b('coder_sign') }}</u>
    </div>

    <div class="fp-line">
      <span><b>病案质量</b> □</span>
      <u class="fill short">{{ b('medicalrecord_quality') }}</u>
      <span class="hint">1.甲 2.乙 3.丙</span>
      <span style="margin-left:20px;">质控医师</span>
      <u class="fill">{{ b('QC_physician_sign') }}</u>
      <span>质控护士</span>
      <u class="fill">{{ b('QC_nurse_sign') }}</u>
    </div>

    <div class="fp-line">
      <span>期</span>
      <u class="fill">{{ b('QC_date') }}</u>
      <span>年</span>
      <u class="fill short"></u>
      <span>月</span>
      <u class="fill short"></u>
      <span>日</span>
    </div>

    <!-- ========== 第二页分割线 ========== -->
    <div class="page-break"></div>

    <!-- ===== 手术及操作表（表格） ===== -->
    <table class="fp-table surgery-table">
      <thead>
        <tr>
          <th rowspan="2" style="width:10%">手术及<br/>操作编码</th>
          <th rowspan="2" style="width:9%">手术及<br/>操作日期</th>
          <th rowspan="2" style="width:5%">手术<br/>级别</th>
          <th rowspan="2" style="width:20%">手术及操作名称</th>
          <th colspan="3">手术及操作医师</th>
          <th rowspan="2" style="width:7%">切口愈<br/>合等级</th>
          <th rowspan="2" style="width:8%">麻醉方式</th>
          <th rowspan="2" style="width:8%">麻醉医师</th>
        </tr>
        <tr>
          <th style="width:7%">术者</th>
          <th style="width:6%">Ⅰ助</th>
          <th style="width:6%">Ⅱ助</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(s, idx) in paddedSurgeries" :key="idx">
          <td class="mono">{{ s.surgery_code }}</td>
          <td>{{ formatDateShort(s.surgery_begin_datetime) }}</td>
          <td class="center">{{ s.surgical_level }}</td>
          <td>{{ s.surgery_name }}</td>
          <td>{{ s.surgeon }}</td>
          <td>{{ s.first_assistant }}</td>
          <td>{{ s.second_assistant }}</td>
          <td class="center">{{ formatIncision(s) }}</td>
          <td>{{ s.anesthesia_method }}</td>
          <td>{{ s.anesthesiologist }}</td>
        </tr>
      </tbody>
    </table>

    <!-- ===== 离院方式（下划线式） ===== -->
    <div class="fp-line" style="margin-top:8px;">
      <span>离院方式 □</span>
      <u class="fill short">{{ b('leaving_hospital_way') }}</u>
      <span class="hint">1.医嘱离院 2.医嘱转院，拟接收医疗机构名称：</span>
      <u class="fill">{{ b('planned_transder_to') }}</u>
    </div>

    <div class="fp-line">
      <span class="hint">3.医嘱转社区卫生服务机构/乡镇卫生院，拟接收医疗机构名称：</span>
      <u class="fill"></u>
      <span class="hint">4.非医嘱离院 5.死亡 9.其他</span>
    </div>

    <div class="fp-line">
      <span>是否有出院31天内再住院计划 □</span>
      <u class="fill short">{{ b('rehospital_with_month') }}</u>
      <span class="hint">1.无 2.有，目的：</span>
      <u class="fill">{{ b('rehospital_with_month_purpose') }}</u>
    </div>

    <div class="fp-line">
      <span>颅脑损伤患者昏迷时间：入院前</span>
      <u class="fill short"></u>
      <span>天</span>
      <u class="fill short"></u>
      <span>小时</span>
      <u class="fill short"></u>
      <span>分钟</span>
      <span style="margin-left:16px;">入院后</span>
      <u class="fill short"></u>
      <span>天</span>
      <u class="fill short"></u>
      <span>小时</span>
      <u class="fill short"></u>
      <span>分钟</span>
    </div>

    <!-- ===== 住院费用（流式编号文本，非表格） ===== -->
    <div class="fp-line cost-header">
      <span><b>住院费用（元）：总费用</b></span>
      <u class="fill cost-val"><b>{{ c('total_cost') }}</b></u>
      <span>（自付金额</span>
      <u class="fill cost-val">{{ c('self_pay') }}</u>
      <span>）</span>
    </div>

    <div class="cost-section">
      <div class="fp-line">
        <b>1.综合医疗服务类：</b>
        <span>（1）一般医疗服务费：</span><u class="fill cost-val">{{ c('general_medical_service_fee') }}</u>
        <span>（2）一般治疗操作费：</span><u class="fill cost-val">{{ c('general_treatment_fee') }}</u>
        <span>（3）护理费：</span><u class="fill cost-val">{{ c('nursing_care_fee') }}</u>
      </div>
      <div class="fp-line">
        <span>（4）其他费用：</span><u class="fill cost-val">{{ c('other_service_fee') }}</u>
      </div>

      <div class="fp-line">
        <b>2.诊断类：</b>
        <span>（5）病理诊断费：</span><u class="fill cost-val">{{ c('pathological_diagnostic_fee') }}</u>
        <span>（6）实验室诊断费：</span><u class="fill cost-val">{{ c('laboratory_diagnostic_fee') }}</u>
        <span>（7）影像学诊断费：</span><u class="fill cost-val">{{ c('imaging_diagnostic_fee') }}</u>
      </div>
      <div class="fp-line">
        <span>（8）临床诊断项目费：</span><u class="fill cost-val">{{ c('clinical_diagnostic_fee') }}</u>
      </div>

      <div class="fp-line">
        <b>3.治疗类：</b>
        <span>（9）非手术治疗项目费：</span><u class="fill cost-val">{{ c('nonsurgical_treatment_fee') }}</u>
        <span>（临床物理治疗费：</span><u class="fill cost-val">{{ c('clinical_physical_therapy_fee') }}</u>
        <span>）</span>
      </div>
      <div class="fp-line">
        <span>（10）手术治疗费：</span><u class="fill cost-val">{{ c('surgery_treatment_fee') }}</u>
        <span>（麻醉费：</span><u class="fill cost-val">{{ c('anesthesia_fee') }}</u>
        <span>手术费：</span><u class="fill cost-val">{{ c('surgery_fee') }}</u>
        <span>）</span>
      </div>

      <div class="fp-line">
        <b>4.康复类：</b>
        <span>（11）康复费：</span><u class="fill cost-val">{{ c('rehabilitation_fee') }}</u>
      </div>

      <div class="fp-line">
        <b>5.中医类：</b>
        <span>（12）中医治疗费：</span><u class="fill cost-val"></u>
      </div>

      <div class="fp-line">
        <b>6.西药类：</b>
        <span>（13）西药费：</span><u class="fill cost-val">{{ c('western_medicine_fee') }}</u>
        <span>（抗菌药物费用：</span><u class="fill cost-val">{{ c('antibacterial_drug_fee') }}</u>
        <span>）</span>
      </div>

      <div class="fp-line">
        <b>7.中药类：</b>
        <span>（14）中成药费：</span><u class="fill cost-val">{{ c('chinese_patent_medcine_fee') }}</u>
        <span>（15）中草药费：</span><u class="fill cost-val">{{ c('chinese_herbal_medicine_fee') }}</u>
      </div>

      <div class="fp-line">
        <b>8.血液和血液制品类：</b>
        <span>（16）血费：</span><u class="fill cost-val">{{ c('blood_fee') }}</u>
        <span>（17）白蛋白类制品费：</span><u class="fill cost-val"></u>
        <span>（18）球蛋白类制品费：</span><u class="fill cost-val"></u>
      </div>
      <div class="fp-line">
        <span>（19）凝血因子类制品费：</span><u class="fill cost-val"></u>
        <span>（20）细胞因子类制品费：</span><u class="fill cost-val"></u>
      </div>

      <div class="fp-line">
        <b>9.耗材类：</b>
        <span>（21）检查用一次性医用材料费：</span><u class="fill cost-val">{{ c('exam_disposable_mat_fee') }}</u>
        <span>（22）治疗用一次性医用材料费：</span><u class="fill cost-val">{{ c('treat_disposable_mat_fee') }}</u>
      </div>
      <div class="fp-line">
        <span>（23）手术用一次性医用材料费：</span><u class="fill cost-val">{{ c('surgery_disposable_mat_fee') }}</u>
      </div>

      <div class="fp-line">
        <b>10.其他类：</b>
        <span>（24）其他费：</span><u class="fill cost-val">{{ c('other_fee') }}</u>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true }
  // data = { basic: {}, diagnoses: [], surgeries: [], cost: {} }
})

// 辅助函数：获取基本信息字段
function b(field) {
  return props.data?.basic?.[field] || ''
}

// 辅助函数：获取费用字段
function c(field) {
  const val = props.data?.cost?.[field]
  if (!val || val === 'None') return ''
  const num = parseFloat(val)
  return isNaN(num) ? val : num.toFixed(2)
}

// 日期完整格式
function formatDateFull(val) {
  if (!val) return ''
  // 2026-01-29 00:00:00 -> 2026年01月29日 00时
  const m = val.match(/(\d{4})-(\d{2})-(\d{2})\s*(\d{2})?/)
  if (m) return `${m[1]}年${m[2]}月${m[3]}日${m[4] ? ' ' + m[4] + '时' : ''}`
  return val
}

// 日期短格式
function formatDateShort(val) {
  if (!val) return ''
  const m = val.match(/(\d{4})-(\d{2})-(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]}`
  return val
}

// 计算年龄
const computedAge = computed(() => {
  const bd = b('birthday')
  if (!bd) return ''
  try {
    const birth = new Date(bd)
    const now = new Date()
    let age = now.getFullYear() - birth.getFullYear()
    if (now.getMonth() < birth.getMonth() ||
        (now.getMonth() === birth.getMonth() && now.getDate() < birth.getDate())) {
      age--
    }
    return age >= 1 ? `${age}岁` : `${Math.floor((now - birth) / (1000*60*60*24*30))}月`
  } catch { return '' }
})

// 诊断分左右两列（左列：主要诊断+其他前半，右列：其他后半）
const diagnosisPairs = computed(() => {
  const diags = props.data?.diagnoses || []
  const mainDiag = diags.filter(d => d.diagnosis_type?.includes('主要'))
  const otherDiag = diags.filter(d => !d.diagnosis_type?.includes('主要'))

  // 左列：主要诊断(1行) + 其他诊断(若干行)
  const leftItems = [...mainDiag, ...otherDiag.slice(0, Math.ceil(otherDiag.length / 2))]
  // 右列：其他诊断(剩余)
  const rightItems = otherDiag.slice(Math.ceil(otherDiag.length / 2))

  const rowCount = Math.max(leftItems.length, rightItems.length, 8) // 至少8行
  const pairs = []
  for (let i = 0; i < rowCount; i++) {
    pairs.push({
      left: leftItems[i] || null,
      right: rightItems[i] || null
    })
  }
  return pairs
})

// 手术列表（至少7行，与官方PDF一致）
const paddedSurgeries = computed(() => {
  const s = props.data?.surgeries || []
  const rows = [...s]
  while (rows.length < 7) {
    rows.push({ surgery_code: '', surgery_name: '', surgeon: '' })
  }
  return rows
})

// 切口愈合等级格式化
function formatIncision(s) {
  if (!s.surgial_incision_level && !s.surgical_incisionheal_level) return '/'
  return `${s.surgial_incision_level || ''} / ${s.surgical_incisionheal_level || ''}`
}
</script>

<style scoped>
/* ===== 住院病案首页 — 官方PDF下划线填空式样式 ===== */
.fp-sheet {
  font-family: "SimSun", "宋体", "Songti SC", serif;
  font-size: 13px;
  line-height: 2;
  color: #000;
  background: #fff;
  padding: 32px 28px;
  max-width: 880px;
  margin: 0 auto;
}

/* === 标题 === */
.fp-title {
  font-size: 22px;
  font-weight: bold;
  letter-spacing: 8px;
  margin: 0;
  text-align: center;
}

.title-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* === 每一行（流式文本+下划线填空） === */
.fp-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2px;
  line-height: 2.2;
}

/* === 下划线填空区 === */
u.fill {
  text-decoration: none;
  border-bottom: 1px solid #000;
  min-width: 80px;
  display: inline-block;
  padding: 0 4px;
  text-align: center;
  flex-shrink: 0;
}

u.fill.short {
  min-width: 40px;
}

u.fill.wide {
  min-width: 160px;
  flex: 1;
}

u.fill.cost-val {
  min-width: 60px;
  max-width: 100px;
  text-align: right;
  padding-right: 4px;
}

/* === 提示文字 === */
.hint {
  font-size: 11px;
  color: #666;
}

/* === 表格（仅用于诊断和手术） === */
.fp-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  margin: 6px 0;
}

.fp-table td,
.fp-table th {
  border: 1px solid #000;
  padding: 2px 4px;
  font-size: 12px;
  line-height: 1.6;
  vertical-align: middle;
}

.fp-table th {
  background: transparent;
  font-weight: bold;
  text-align: center;
  font-size: 12px;
}

.fp-table td.center { text-align: center; }
.fp-table td.mono { font-family: "Courier New", monospace; font-size: 11px; }

/* 诊断表 */
.diag-table td {
  height: 24px;
}

/* 手术表 */
.surgery-table td {
  height: 22px;
}

/* === 费用区（流式文本） === */
.cost-header {
  margin-top: 12px;
  padding-top: 4px;
  border-top: 1px solid #000;
}

.cost-section {
  padding-left: 0;
}

.cost-section .fp-line {
  line-height: 2;
}

/* === 页面分隔 === */
.page-break {
  border-top: 2px dashed #ccc;
  margin: 20px 0;
  position: relative;
}

.page-break::after {
  content: '— 第二页 —';
  position: absolute;
  top: -10px;
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  padding: 0 12px;
  color: #ccc;
  font-size: 11px;
}

/* === 打印优化 === */
@media print {
  .fp-sheet {
    padding: 0;
    font-size: 12px;
  }
  .page-break {
    page-break-before: always;
    border: none;
    margin: 0;
  }
  .page-break::after {
    display: none;
  }
}
</style>
