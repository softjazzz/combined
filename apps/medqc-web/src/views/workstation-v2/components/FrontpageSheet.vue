<template>
  <!-- 住院病案首页 — 官方格式（参照卫健委标准） -->
  <div class="frontpage-sheet">
    <h2 class="sheet-subtitle">医疗机构：<u>{{ b('institute_county_desc') }}</u>（组织机构代码：<u>{{ b('institute_code') }}</u>）</h2>

    <!-- 顶部行：付费方式 / 标题 / 健康卡号 -->
    <div class="top-row">
      <span>医疗付费方式：<u>{{ b('medical_payment_method') }}</u></span>
      <h1 class="sheet-title">住 院 病 案 首 页</h1>
      <span>健康卡号：<u>{{ b('insurance_no') }}</u>　第 <u>{{ b('visit_cnt') || '1' }}</u> 次住院　病案号：<u>{{ b('document_id') }}</u></span>
    </div>

    <!-- ===== 第一节：患者身份信息 ===== -->
    <table class="fp-table">
      <tr>
        <td class="label" style="width:4%">姓名</td>
        <td style="width:10%"><b>{{ b('name') }}</b></td>
        <td class="label" style="width:4%">性别</td>
        <td style="width:6%"><b>{{ b('sex') }}</b></td>
        <td class="hint" style="width:10%">1.男 2.女</td>
        <td class="label" style="width:6%">出生日期</td>
        <td style="width:14%"><b>{{ b('birthday') }}</b></td>
        <td class="label" style="width:4%">年龄</td>
        <td style="width:6%"><b>{{ computedAge }}</b></td>
        <td class="label" style="width:4%">国籍</td>
        <td style="width:8%"><b>{{ b('nationality') || '中国' }}</b></td>
      </tr>
    </table>

    <table class="fp-table">
      <tr>
        <td class="label" style="width:8%">身份证号</td>
        <td style="width:18%"><b>{{ b('id_card_no') }}</b></td>
        <td class="label" style="width:4%">职业</td>
        <td style="width:12%"><b>{{ b('occupation_category') }}</b></td>
        <td class="label" style="width:4%">婚姻</td>
        <td style="width:6%"><b>{{ b('marital_status') }}</b></td>
        <td class="hint" style="width:24%">10.未婚 20.已婚 30.丧偶 40.离婚 90.其他</td>
      </tr>
    </table>

    <table class="fp-table">
      <tr>
        <td class="label" style="width:6%">现住址</td>
        <td style="width:50%"><b>{{ b('currentaddress') }}</b></td>
        <td class="label" style="width:4%">电话</td>
        <td style="width:14%"><b>{{ b('contact_number') }}</b></td>
        <td class="label" style="width:4%">民族</td>
        <td style="width:10%"><b>{{ b('ethnicity') }}</b></td>
      </tr>
    </table>

    <table class="fp-table">
      <tr>
        <td class="label" style="width:10%">工作单位及地址</td>
        <td style="width:50%"><b>{{ b('work_unit') }}</b></td>
        <td class="label" style="width:6%">籍贯</td>
        <td style="width:20%"><b>{{ b('nativeplace') }}</b></td>
      </tr>
    </table>

    <table class="fp-table dashed-top">
      <tr>
        <td class="label" style="width:8%">联系人姓名</td>
        <td style="width:10%"><b>{{ b('contact_name') }}</b></td>
        <td class="label" style="width:4%">关系</td>
        <td style="width:14%"><b>{{ b('contact_relationship') }}</b></td>
        <td class="label" style="width:4%">地址</td>
        <td style="width:24%"><b>{{ b('contact_address') }}</b></td>
        <td class="label" style="width:4%">电话</td>
        <td style="width:14%"><b>{{ b('contact_telephone') }}</b></td>
      </tr>
    </table>

    <!-- ===== 第二节：入院/出院信息 ===== -->
    <table class="fp-table">
      <tr>
        <td class="label" style="width:8%">入院途径</td>
        <td style="width:12%"><b>{{ b('admission_route') }}</b></td>
        <td class="hint" style="width:36%">1.急诊 2.门诊 3.其他医疗机构转入 9.其他</td>
        <td class="label" style="width:8%">入院情况</td>
        <td style="width:8%"><b>{{ b('admission_condition') }}</b></td>
        <td class="hint" style="width:20%">1.危 2.急 3.一般</td>
      </tr>
    </table>

    <table class="fp-table">
      <tr>
        <td class="label" style="width:8%">入院时间</td>
        <td style="width:20%"><b>{{ b('admission_datetime') }}</b></td>
        <td class="label" style="width:6%">入院科别</td>
        <td style="width:10%"><b>{{ b('admission_dept_name') }}</b></td>
        <td class="label" style="width:4%">病房</td>
        <td style="width:8%"><b>{{ b('admission_ward_name') }}</b></td>
        <td class="label" style="width:6%">转科科别</td>
        <td style="width:12%"><b>{{ b('transfer_dept_name') }}</b></td>
      </tr>
      <tr>
        <td class="label">出院时间</td>
        <td><b>{{ b('discharge_datetime') }}</b></td>
        <td class="label">出院科别</td>
        <td><b>{{ b('discharge_dept_name') }}</b></td>
        <td class="label">病房</td>
        <td><b>{{ b('discharge_ward_name') }}</b></td>
        <td class="label">实际住院</td>
        <td><b>{{ b('hospital_duration') }}</b> 天</td>
      </tr>
    </table>

    <!-- ===== 第三节：出院诊断表 ===== -->
    <table class="fp-table diagnosis-table">
      <thead>
        <tr>
          <th style="width:35%">出院诊断</th>
          <th style="width:12%">疾病编码</th>
          <th style="width:6%">入院病情</th>
          <th style="width:6%">出院情况</th>
          <th style="width:29%">出院诊断</th>
          <th style="width:12%">疾病编码</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(pair, idx) in diagnosisPairs" :key="idx">
          <!-- 左列 -->
          <td>
            <span v-if="pair.left" :class="{ 'text-red-600 font-bold': pair.left._isMain }">
              {{ pair.left._isMain ? '主要诊断: ' : '' }}{{ pair.left.diagnosis_name }}
            </span>
          </td>
          <td class="mono">{{ pair.left?.diagnosis_code }}</td>
          <td class="center">{{ pair.left?.admission_condition }}</td>
          <td class="center">{{ pair.left?.discharge_condition }}</td>
          <!-- 右列 -->
          <td>{{ pair.right?.diagnosis_name }}</td>
          <td class="mono">{{ pair.right?.diagnosis_code }}</td>
        </tr>
        <tr v-if="diagnosisPairs.length === 0">
          <td colspan="6" class="center hint">暂无诊断记录</td>
        </tr>
      </tbody>
    </table>

    <!-- 入院病情/出院情况说明行 -->
    <table class="fp-table">
      <tr>
        <td class="hint" style="width:50%">入院病情: 1.有 2.临床未确定 3.情况不明 4.无</td>
        <td class="hint" style="width:50%">出院情况: 1.治愈 2.好转 3.未愈 4.死亡 5.其他</td>
      </tr>
    </table>

    <!-- ===== 病理诊断 / 药物过敏 / 血型 ===== -->
    <table class="fp-table">
      <tr>
        <td class="label" style="width:8%">病理诊断</td>
        <td style="width:30%"><b>{{ b('pathology_id') ? '病理号: ' + b('pathology_id') : '' }}</b></td>
        <td class="label" style="width:8%">药物过敏</td>
        <td style="width:16%"><b>{{ b('allergy_sign') === '2' ? '有: ' + (b('allergy_history') || '') : '无' }}</b></td>
        <td class="label" style="width:12%">死亡患者尸检</td>
        <td style="width:8%"><b>{{ b('death_autopsy_sign') }}</b></td>
      </tr>
    </table>

    <table class="fp-table">
      <tr>
        <td class="label" style="width:4%">血型</td>
        <td style="width:8%"><b>{{ b('abo_blood_code') }}</b></td>
        <td class="hint" style="width:28%">1.A 2.B 3.O 4.AB 5.不详 6.未查</td>
        <td class="label" style="width:3%">Rh</td>
        <td style="width:6%"><b>{{ b('rh_blood_code') }}</b></td>
        <td class="hint" style="width:24%">1.阴 2.阳 3.不详 4.未查</td>
      </tr>
    </table>

    <!-- ===== 第四节：手术及操作 ===== -->
    <table class="fp-table surgery-table">
      <thead>
        <tr>
          <th style="width:12%">手术及操作编码</th>
          <th style="width:10%">手术及操作日期</th>
          <th style="width:5%">手术级别</th>
          <th style="width:25%">手术及操作名称</th>
          <th style="width:8%">术者</th>
          <th style="width:7%">Ⅰ助</th>
          <th style="width:7%">Ⅱ助</th>
          <th style="width:8%">切口愈合等级</th>
          <th style="width:8%">麻醉方式</th>
          <th style="width:8%">麻醉医师</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(s, idx) in paddedSurgeries" :key="idx">
          <td class="mono">{{ s.surgery_code }}</td>
          <td>{{ s.surgery_begin_datetime }}</td>
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

    <!-- ===== 第五节：离院方式 ===== -->
    <table class="fp-table">
      <tr>
        <td class="label" style="width:8%">离院方式</td>
        <td style="width:14%"><b>{{ b('leaving_hospital_way') }}</b></td>
        <td class="hint" style="width:50%">1.医嘱离院 2.医嘱转院 3.医嘱转社区卫生服务机构/乡镇卫生院 4.非医嘱离院 5.死亡 9.其他</td>
        <td class="label" style="width:14%">31天内再住院</td>
        <td style="width:10%"><b>{{ b('rehospital_with_month') }}</b></td>
      </tr>
    </table>

    <!-- ===== 第六节：住院费用 ===== -->
    <div class="section-header">住院费用</div>
    <table class="fp-table cost-table" v-if="data.cost">
      <tr>
        <td class="label" style="width:20%">应收总费用（元）</td>
        <td style="width:14%"><b>{{ c('total_cost') }}</b></td>
        <td class="label" style="width:14%">自付金额（元）</td>
        <td style="width:14%"><b>{{ c('self_pay') }}</b></td>
        <td colspan="2"></td>
      </tr>
      <!-- 综合医疗服务类 -->
      <tr>
        <td class="label bg-gray">（一）综合医疗服务类</td>
        <td></td>
        <td class="label bg-gray">（二）诊断类</td>
        <td></td>
        <td colspan="2"></td>
      </tr>
      <tr>
        <td class="sub-label">1.一般医疗服务费</td>
        <td><b>{{ c('general_medical_service_fee') }}</b></td>
        <td class="sub-label">5.病理诊断费</td>
        <td><b>{{ c('pathological_diagnostic_fee') }}</b></td>
        <td class="label bg-gray">（五）中医类</td>
        <td></td>
      </tr>
      <tr>
        <td class="sub-label">2.一般治疗操作费</td>
        <td><b>{{ c('general_treatment_fee') }}</b></td>
        <td class="sub-label">6.实验室诊断费</td>
        <td><b>{{ c('laboratory_diagnostic_fee') }}</b></td>
        <td class="sub-label">14.中成药费</td>
        <td><b>{{ c('chinese_patent_medcine_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">3.护理费</td>
        <td><b>{{ c('nursing_care_fee') }}</b></td>
        <td class="sub-label">7.影像学诊断费</td>
        <td><b>{{ c('imaging_diagnostic_fee') }}</b></td>
        <td class="sub-label">15.中草药费</td>
        <td><b>{{ c('chinese_herbal_medicine_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">4.其他费用</td>
        <td><b>{{ c('other_service_fee') }}</b></td>
        <td class="sub-label">8.临床诊断项目费</td>
        <td><b>{{ c('clinical_diagnostic_fee') }}</b></td>
        <td class="label bg-gray">（六）西药类</td>
        <td></td>
      </tr>
      <!-- 治疗类 -->
      <tr>
        <td class="label bg-gray">（三）治疗类</td>
        <td></td>
        <td class="label bg-gray">（四）康复类</td>
        <td></td>
        <td class="sub-label">16.西药费</td>
        <td><b>{{ c('western_medicine_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">9.非手术治疗项目费</td>
        <td><b>{{ c('nonsurgical_treatment_fee') }}</b></td>
        <td class="sub-label">13.康复费</td>
        <td><b>{{ c('rehabilitation_fee') }}</b></td>
        <td class="sub-label">其中：抗菌药物费</td>
        <td><b>{{ c('antibacterial_drug_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">　其中：临床物理治疗费</td>
        <td><b>{{ c('clinical_physical_therapy_fee') }}</b></td>
        <td class="label bg-gray">（七）血液和血液制品类</td>
        <td></td>
        <td class="label bg-gray">（八）耗材类</td>
        <td></td>
      </tr>
      <tr>
        <td class="sub-label">10.手术治疗费</td>
        <td><b>{{ c('surgery_treatment_fee') }}</b></td>
        <td class="sub-label">17.血费</td>
        <td><b>{{ c('blood_fee') }}</b></td>
        <td class="sub-label">19.检查用一次性医用材料费</td>
        <td><b>{{ c('exam_disposable_mat_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">　其中：麻醉费</td>
        <td><b>{{ c('anesthesia_fee') }}</b></td>
        <td class="label bg-gray">（九）其他类</td>
        <td></td>
        <td class="sub-label">20.治疗用一次性医用材料费</td>
        <td><b>{{ c('treat_disposable_mat_fee') }}</b></td>
      </tr>
      <tr>
        <td class="sub-label">　　　 手术费</td>
        <td><b>{{ c('surgery_fee') }}</b></td>
        <td class="sub-label">18.其他费</td>
        <td><b>{{ c('other_fee') }}</b></td>
        <td class="sub-label">21.手术用一次性医用材料费</td>
        <td><b>{{ c('surgery_disposable_mat_fee') }}</b></td>
      </tr>
    </table>
    <div v-else class="no-data">暂无费用数据</div>

    <!-- ===== 签名区 ===== -->
    <table class="fp-table sign-table">
      <tr>
        <td class="label">科主任 <b>{{ b('deptdirector_sign') }}</b></td>
        <td class="label">主任(副主任)医师 <b>{{ b('chief_physician_sign') }}</b></td>
        <td class="label">主治医师 <b>{{ b('attending_physician_sign') }}</b></td>
        <td class="label">住院医师 <b>{{ b('resident_physician_sign') }}</b></td>
      </tr>
      <tr>
        <td class="label">责任护士 <b>{{ b('responsible_nurse_sign') }}</b></td>
        <td class="label">编码员 <b>{{ b('coder_sign') }}</b></td>
        <td class="label">质控医师 <b>{{ b('QC_physician_sign') }}</b></td>
        <td class="label">质控护士 <b>{{ b('QC_nurse_sign') }}</b></td>
      </tr>
      <tr>
        <td class="label" colspan="2">病案质量 <b>{{ b('medicalrecord_quality') }}</b>　1.甲 2.乙 3.丙</td>
        <td class="label" colspan="2">质控日期 <b>{{ b('QC_date') }}</b></td>
      </tr>
    </table>
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

// 诊断分左右两列（每列10行，主要诊断在左上角）
const diagnosisPairs = computed(() => {
  const diags = props.data?.diagnoses || []
  // 分类
  const mainDiag = diags.filter(d => d.diagnosis_type?.includes('主要'))
  const otherDiag = diags.filter(d => !d.diagnosis_type?.includes('主要'))
  
  // 合并：主要诊断在最前
  const all = [
    ...mainDiag.map(d => ({ ...d, _isMain: true })),
    ...otherDiag
  ]
  
  // 分成左右两列
  const half = Math.max(Math.ceil(all.length / 2), 5)
  const pairs = []
  for (let i = 0; i < half; i++) {
    pairs.push({
      left: all[i] || null,
      right: all[i + half] || null
    })
  }
  return pairs
})

// 手术列表（至少4行）
const paddedSurgeries = computed(() => {
  const s = props.data?.surgeries || []
  const rows = [...s]
  while (rows.length < 4) {
    rows.push({ surgery_code: '', surgery_name: '', surgeon: '' })
  }
  return rows
})

// 切口愈合等级格式化
function formatIncision(s) {
  if (!s.surgial_incision_level && !s.surgical_incisionheal_level) return ''
  return `${s.surgial_incision_level || ''} / ${s.surgical_incisionheal_level || ''}`
}
</script>

<style scoped>
/* ===== 住院病案首页 — 官方格式样式 ===== */
.frontpage-sheet {
  font-family: "SimSun", "宋体", "Songti SC", serif;
  font-size: 12px;
  line-height: 1.6;
  color: #000;
  background: #fff;
  padding: 24px 20px;
  max-width: 900px;
  margin: 0 auto;
}

.sheet-title {
  font-size: 20px;
  font-weight: bold;
  text-align: center;
  letter-spacing: 6px;
  margin: 0;
}

.sheet-subtitle {
  font-size: 13px;
  font-weight: normal;
  margin: 0 0 4px 0;
}

.top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 11px;
}

.top-row u {
  text-decoration-thickness: 1px;
  min-width: 40px;
  display: inline-block;
}

/* === 核心表格样式 === */
.fp-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  margin-bottom: -1px; /* 合并相邻表格边框 */
}

.fp-table td,
.fp-table th {
  border: 1px solid #000;
  padding: 2px 4px;
  vertical-align: middle;
  word-break: break-all;
  font-size: 11px;
  line-height: 1.5;
}

.fp-table th {
  background: #f5f5f0;
  font-weight: bold;
  text-align: center;
  font-size: 11px;
}

.fp-table td.label {
  font-weight: bold;
  white-space: nowrap;
}

.fp-table td.hint {
  font-size: 10px;
  color: #666;
}

.fp-table td.sub-label {
  padding-left: 8px;
  font-size: 11px;
}

.fp-table td.center,
.fp-table th.center {
  text-align: center;
}

.fp-table td.mono {
  font-family: "Courier New", monospace;
  font-size: 11px;
}

.fp-table td.bg-gray {
  background: #f5f5f0;
}

.fp-table b {
  font-weight: 600;
}

.dashed-top td {
  border-top-style: dashed;
}

/* 诊断表 */
.diagnosis-table thead th {
  font-size: 11px;
  padding: 3px 4px;
}

/* 手术表 */
.surgery-table thead th {
  font-size: 10px;
  padding: 2px 3px;
}

/* 费用表 */
.cost-table td {
  height: 22px;
}

/* 签名表 */
.sign-table td {
  height: 26px;
  border-top-style: dashed;
}

.section-header {
  font-weight: bold;
  font-size: 13px;
  border: 1px solid #000;
  border-bottom: none;
  padding: 3px 6px;
  background: #f5f5f0;
  text-align: center;
}

.no-data {
  text-align: center;
  color: #999;
  padding: 12px;
  border: 1px solid #000;
  font-size: 12px;
}

/* 打印优化 */
@media print {
  .frontpage-sheet {
    padding: 0;
    font-size: 11px;
  }
}
</style>
