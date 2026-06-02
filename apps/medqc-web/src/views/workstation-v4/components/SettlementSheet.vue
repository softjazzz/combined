<template>
  <!-- 医疗保障基金结算清单 - 按官方 PDF 格式像素级还原 -->
  <div
    v-if="data"
    class="ss-wrapper"
  >
    <!-- ===== 标题 ===== -->
    <h1 class="ss-title">
      医 疗 保 障 基 金 结 算 清 单
    </h1>

    <!-- 顶部3行：机构名称、代码、医保结算等级、编号、病案号、申报时间 -->
    <table
      class="ss-tbl"
      style="border-top: none"
    >
      <tr>
        <td style="width: 38%; border-top: none">
          定点医疗机构名称<u class="fill">{{ v('designated_medical_institution') }}</u>
        </td>
        <td style="width: 38%; border-top: none">
          定点医疗机构代码<u class="fill">{{ v('institution_code') }}</u>
        </td>
        <td style="width: 24%; border-top: none">
          医保结算等级<u class="fill">{{ v('settlement_status') }}</u>
        </td>
      </tr>
      <tr>
        <td>
          医保编号<u class="fill">{{ v('insurance_no') }}</u>
        </td>
        <td>
          病案号<u class="fill">{{ v('mr_no') }}</u>
        </td>
        <td>
          申报时间<u class="fill">{{ v('declaration_time') }}</u>
        </td>
      </tr>
    </table>

    <!-- ===== 一、基本信息 ===== -->
    <div class="ss-sec-hd">
      一、基本信息
    </div>
    <table class="ss-tbl">
      <tr>
        <td style="width: 14%">
          姓名<u class="fill">{{ v('patient_name') }}</u>
        </td>
        <td style="width: 16%">
          性别□ 1.男 2.女 <span class="bold">{{ v('sex') }}</span>
        </td>
        <td style="width: 20%">
          出生日期<u class="fill">{{ v('patient_birthday') }}</u>
        </td>
        <td style="width: 14%">
          年龄<u class="fill">{{ v('patient_age') }}</u>岁
        </td>
        <td style="width: 12%">
          国籍<u class="fill">{{ v('nationality') || v('patient_nationality') }}</u>
        </td>
        <td style="width: 12%">
          民族<u class="fill">{{ v('patient_ethnicity') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          （年龄不足1周岁）年龄<u class="fill" />天 &nbsp; 患者证件类别<u class="fill">{{
            v('id_card_type')
          }}</u>
        </td>
        <td colspan="3">
          患者证件号码<u class="fill">{{ v('patient_id_card') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          职业<u class="fill">{{ v('occupation_category') }}</u>
        </td>
        <td colspan="4">
          现住址<u class="fill">{{ v('currentaddress') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          工作单位名称<u class="fill">{{ v('work_unit') }}</u>
        </td>
        <td colspan="2">
          工作单位地址<u class="fill">{{ v('workplace') }}</u>
        </td>
        <td>
          单位电话<u class="fill">{{ v('work_telephone') }}</u>
        </td>
        <td>
          邮编<u class="fill">{{ v('currentaddress_postcode') }}</u>
        </td>
      </tr>
      <tr>
        <td>
          联系人姓名<u class="fill">{{ v('contact_name') }}</u>
        </td>
        <td>
          关系<u class="fill">{{ v('contact_relationship') }}</u>
        </td>
        <td colspan="2">
          地址<u class="fill">{{ v('contact_address') }}</u>
        </td>
        <td colspan="2">
          电话<u class="fill">{{ v('contact_telephone') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          医保类型<u class="fill">{{ v('patient_insurance_type') || v('insurance_type') }}</u>
        </td>
        <td colspan="2">
          特殊人员类型<u class="fill">{{ v('special_personnel_type') }}</u>
        </td>
        <td colspan="2">
          参保地<u class="fill">{{ v('insured_place') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          新生儿入院类型<u class="fill">{{ v('newborn_admission_type') }}</u>
        </td>
        <td colspan="2">
          新生儿出生体重<u class="fill">{{ v('newborn_birthweight') }}</u>克
        </td>
        <td colspan="2">
          新生儿入院体重<u class="fill">{{ v('newborn_admitweigth') }}</u>克
        </td>
      </tr>
    </table>

    <!-- ===== 二、门诊慢特病诊疗信息 ===== -->
    <div class="ss-sec-hd">
      二、门诊慢特病诊疗信息
    </div>
    <table class="ss-tbl">
      <tr>
        <td style="width: 50%">
          诊断科别<u class="fill" />
        </td>
        <td style="width: 50%">
          就诊日期<u class="fill" />
        </td>
      </tr>
    </table>
    <table class="ss-tbl">
      <tr class="hd-row">
        <td style="width: 30%">
          诊断名称
        </td>
        <td style="width: 20%">
          诊断代码
        </td>
        <td style="width: 30%">
          手术及操作名称
        </td>
        <td style="width: 20%">
          手术及操作代码
        </td>
      </tr>
      <tr
        v-for="n in 4"
        :key="'op' + n"
        class="data-row"
      >
        <td>&nbsp;</td>
        <td />
        <td />
        <td />
      </tr>
    </table>

    <!-- ===== 三、住院诊疗信息 ===== -->
    <div class="ss-sec-hd">
      三、住院诊疗信息
    </div>
    <table class="ss-tbl">
      <tr>
        <td colspan="6">
          住院医疗类型□ 1.住院 &nbsp; 2.日间手术 &nbsp;
          <span class="bold">{{ v('inpat_type') || '住院' }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="6">
          入院途径□ 1.急诊 &nbsp; 2.门诊 &nbsp; 3.其他医疗机构转入 &nbsp; 9.其他 &nbsp;
          <span class="bold">{{ v('admission_route') }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="6">
          治疗类别□ 1.西医 &nbsp; 2.中医（2.1 中医 &nbsp; 2.2 民族医） &nbsp; 3.中西医 &nbsp;
          <span class="bold">{{ v('therapy_type') }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          入院时间<u class="fill">{{ v('admission_datetime') }}</u>
        </td>
        <td colspan="2">
          入院科别<u class="fill">{{ v('admission_dept_name') }}</u>
        </td>
        <td colspan="2">
          转科科别<u class="fill">{{ v('transfer_dept_name') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="2">
          出院时间<u class="fill">{{ v('discharge_datetime') }}</u>
        </td>
        <td colspan="2">
          出院科别<u class="fill">{{ v('discharge_dept_name') }}</u>
        </td>
        <td colspan="2">
          实际住院<u class="fill">{{ v('hospital_duration') }}</u>天
        </td>
      </tr>
    </table>

    <!-- 门急诊诊断 -->
    <table class="ss-tbl">
      <tr>
        <td colspan="3">
          门（急）诊诊断（西医诊断）<u class="fill">{{ firstDiag }}</u>
        </td>
        <td colspan="3">
          疾病代码<u class="fill">{{ firstDiagCode }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          门（急）诊诊断（中医诊断）<u class="fill">{{ firstTcmDiag }}</u>
        </td>
        <td colspan="3">
          疾病代码<u class="fill">{{ firstTcmDiagCode }}</u>
        </td>
      </tr>
    </table>

    <!-- 诊断表格（含西医+中医） -->
    <table
      v-if="data.diagnoses && data.diagnoses.length"
      class="ss-tbl"
    >
      <tr class="hd-row">
        <td
          rowspan="2"
          style="width: 6%"
        >
          序号
        </td>
        <td
          colspan="3"
          style="width: 47%"
        >
          出院西医诊断
        </td>
        <td
          colspan="3"
          style="width: 47%"
        >
          出院中医诊断
        </td>
      </tr>
      <tr class="hd-row">
        <td>疾病名称</td>
        <td>疾病代码</td>
        <td>入院病情</td>
        <td>疾病名称</td>
        <td>疾病代码</td>
        <td>入院病情</td>
      </tr>
      <tr
        v-for="(d, i) in paddedDiagnoses"
        :key="'d' + i"
        class="data-row"
      >
        <td class="center">
          {{ i === 0 ? '主要' : d.western_name || d.tcm_name ? '其他' : '' }}
        </td>
        <td>{{ d.western_name || '' }}</td>
        <td class="center mono">
          {{ d.western_code || '' }}
        </td>
        <td class="center">
          {{ d.western_condition || '' }}
        </td>
        <td>{{ d.tcm_name || '' }}</td>
        <td class="center mono">
          {{ d.tcm_code || '' }}
        </td>
        <td class="center">
          {{ d.tcm_condition || '' }}
        </td>
      </tr>
    </table>

    <!-- 手术信息 -->
    <table class="ss-tbl">
      <tr class="hd-row">
        <td
          rowspan="2"
          style="width: 5%"
        >
          序号
        </td>
        <td
          rowspan="2"
          style="width: 20%"
        >
          手术及操作名称
        </td>
        <td
          rowspan="2"
          style="width: 14%"
        >
          手术及操作代码
        </td>
        <td
          rowspan="2"
          style="width: 12%"
        >
          手术及操作日期
        </td>
        <td colspan="2">
          术者
        </td>
        <td
          rowspan="2"
          style="width: 8%"
        >
          切口等级
        </td>
        <td
          rowspan="2"
          style="width: 9%"
        >
          麻醉方式
        </td>
        <td colspan="2">
          麻醉医师
        </td>
      </tr>
      <tr class="hd-row">
        <td style="width: 8%">
          姓名
        </td>
        <td style="width: 8%">
          代码
        </td>
        <td style="width: 8%">
          姓名
        </td>
        <td style="width: 8%">
          代码
        </td>
      </tr>
      <tr
        v-for="(s, i) in paddedSurgeries"
        :key="'s' + i"
        class="data-row"
      >
        <td class="center">
          {{ s.name ? (i === 0 ? '主要' : '其他') : '' }}
        </td>
        <td>{{ s.name || '' }}</td>
        <td class="center mono">
          {{ s.code || '' }}
        </td>
        <td class="center">
          {{ s.date || '' }}
        </td>
        <td class="center">
          {{ s.surgeon || '' }}
        </td>
        <td class="center">
          {{ s.surgeon_code || '' }}
        </td>
        <td class="center">
          {{ s.incision_grade || s.level || '' }}
        </td>
        <td class="center">
          {{ s.anesthesia_method || '' }}
        </td>
        <td class="center">
          {{ s.anesthesiologist || '' }}
        </td>
        <td class="center">
          {{ s.anesthesiologist_code || '' }}
        </td>
      </tr>
    </table>

    <!-- 辅助信息（代码计数、呼吸机、昏迷、重症监护、输血等） -->
    <table class="ss-tbl">
      <tr>
        <td colspan="3">
          手术及操作代码计数<u class="fill">{{
            v('surgery_code_cnt') || data.surgeries?.length || ''
          }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          呼吸机使用时间<u class="fill">{{ ventilatorDuration.days }}</u>天<u class="fill">{{ ventilatorDuration.hours }}</u>小时<u class="fill">{{ ventilatorDuration.minutes }}</u>分钟
        </td>
      </tr>
      <tr>
        <td colspan="3">
          颅脑损伤患者昏迷时间：入院前<u class="fill">{{ v('coma_timebefadm_d') }}</u>天<u class="fill">{{ v('coma_timebefadm_h') }}</u>小时<u class="fill">{{ v('coma_timebefadm_min') }}</u>分钟
        </td>
      </tr>
      <tr>
        <td
          colspan="3"
          style="padding-left: 100px"
        >
          入院后<u class="fill">{{ v('coma_timeaftadm_d') }}</u>天<u class="fill">{{ v('coma_timeaftadm_h') }}</u>小时<u class="fill">{{ v('coma_timeaftadm_min') }}</u>分钟
        </td>
      </tr>
    </table>

    <!-- 重症监护 -->
    <table class="ss-tbl">
      <tr class="hd-row">
        <td style="width: 30%">
          重症监护病房类型<br><span style="font-size: 10px">(CCU、NICU、EICU、SICU、PICU、<br>RICU、其他)</span>
        </td>
        <td style="width: 25%">
          进重症监护室时间<br>（_年_月_日_时_分）
        </td>
        <td style="width: 25%">
          出重症监护室时间<br>（_年_月_日_时_分）
        </td>
        <td style="width: 20%">
          合计（小时）
        </td>
      </tr>
      <tr
        v-for="(icu, i) in paddedIcuRows"
        :key="'icu' + i"
        class="data-row"
      >
        <td>{{ icu.icu_type || '\u00A0' }}</td>
        <td>{{ icu.icu_enter_time || '\u00A0' }}</td>
        <td>{{ icu.icu_leave_time || '\u00A0' }}</td>
        <td>{{ icu.icu_total_hours || '\u00A0' }}</td>
      </tr>
    </table>

    <!-- 输血、护理、离院方式、再住院计划、主诊医师 -->
    <table class="ss-tbl">
      <tr>
        <td colspan="2">
          输血品种<u class="fill">{{ v('blood_type') }}</u>
        </td>
        <td colspan="2">
          输血量<u class="fill">{{ v('blood_volume') }}</u>
        </td>
        <td colspan="2">
          输血计量单位<u class="fill">{{ v('blood_unit') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          特级护理天数*<u class="fill">{{ v('intensive_care_days') }}</u> &nbsp; 一级护理天数*<u
            class="fill"
          >{{ v('primary_care_days') }}</u>
        </td>
        <td colspan="3">
          二级护理天数*<u class="fill">{{ v('secondary_care_days') }}</u> &nbsp; 三级护理天数*<u
            class="fill"
          >{{ v('tertiary_care_days') }}</u>
        </td>
      </tr>
      <tr>
        <td colspan="6">
          离院方式 □ 1.医嘱离院 &nbsp; 2.医嘱转院、转社区、转卫生院机构，拟接收机构名称<u
            class="fill"
          >{{ v('receiving_institution_name') }}</u>
          &nbsp; 拟接收机构代码<u class="fill" />
        </td>
      </tr>
      <tr>
        <td colspan="6">
          &nbsp; &nbsp; 3.非医嘱离院 &nbsp; 4.死亡 &nbsp; 9.其他 &nbsp;
          <span class="bold">{{ v('leaving_hospital_way') }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="6">
          是否有出院31天内再住院计划□ 1.无 &nbsp; 2.有，目的<u class="fill">{{
            v('rehospital_with_month_purpose')
          }}</u>
          <span class="bold">{{ v('rehospital_with_month') }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          主诊医师姓名*<u class="fill">{{ v('attending_physician') }}</u>
        </td>
        <td colspan="3">
          主诊医师代码*<u class="fill">{{ v('attending_physician_code') }}</u>
        </td>
      </tr>
    </table>

    <!-- ===== 四、医疗收费信息 ===== -->
    <div class="ss-sec-hd">
      四、医疗收费信息
    </div>
    <table class="ss-tbl">
      <tr>
        <td style="width: 40%">
          业务流水号<u class="fill">{{ v('business_serial_no') }}</u>
        </td>
        <td style="width: 60%">
          结算期间<u class="fill">{{ v('start_date') || '' }}</u> —
          <u class="fill">{{ v('end_date') || '' }}</u>
        </td>
      </tr>
    </table>

    <!-- 费用明细表 -->
    <table class="ss-tbl cost-tbl">
      <tr class="hd-row">
        <td style="width: 28%">
          项目名称
        </td>
        <td style="width: 15%">
          金额
        </td>
        <td style="width: 15%">
          甲类
        </td>
        <td style="width: 14%">
          乙类
        </td>
        <td style="width: 14%">
          自费
        </td>
        <td style="width: 14%">
          其他
        </td>
      </tr>
      <tr
        v-for="item in costRows"
        :key="item.type"
        :class="{ 'cat-row': item.isCat }"
      >
        <td :class="{ bold: item.isCat }">
          {{ item.type }}
        </td>
        <td class="num">
          {{ item.charge }}
        </td>
        <td class="num">
          {{ item.class_a }}
        </td>
        <td class="num">
          {{ item.class_b }}
        </td>
        <td class="num">
          {{ item.own_pay }}
        </td>
        <td class="num">
          {{ item.other }}
        </td>
      </tr>
      <tr class="total-row">
        <td class="bold">
          金额合计
        </td>
        <td class="num bold">
          {{ totalCharge }}
        </td>
        <td class="num bold">
          {{ totalClassA }}
        </td>
        <td class="num bold">
          {{ totalClassB }}
        </td>
        <td class="num bold">
          {{ totalOwnPay }}
        </td>
        <td class="num bold">
          {{ totalOther }}
        </td>
      </tr>
    </table>

    <!-- 基金支付 / 个人支付（按 PDF 竖排结构） -->
    <table class="ss-tbl fund-tbl">
      <tr class="hd-row">
        <td
          colspan="3"
          style="width: 50%"
        >
          基金支付
        </td>
        <td
          colspan="2"
          style="width: 50%"
        >
          个人支付
        </td>
      </tr>
      <tr>
        <td
          rowspan="8"
          class="center bold vert-label"
          style="width: 5%"
        >
          基<br>金<br>支<br>付
        </td>
        <td style="width: 25%">
          基金支付类型
        </td>
        <td style="width: 20%">
          金额
        </td>
        <td
          rowspan="8"
          class="center bold vert-label"
          style="width: 5%"
        >
          个<br>人<br>支<br>付
        </td>
        <td style="width: 45%">
          <div class="fund-item">
            <span>个人自付</span><span class="num">{{ fmtMoney(data.out_of_pocket_advance) }}</span>
          </div>
        </td>
      </tr>
      <tr>
        <td>医保统筹基金支付</td>
        <td class="num">
          {{ fmtMoney(data.insurance_fund_pay) || fmtMoney(data.insurance_type) }}
        </td>
        <td>
          <div class="fund-item">
            <span>个人自费</span><span class="num">{{ fmtMoney(data.out_of_pocket_amount) }}</span>
          </div>
        </td>
      </tr>
      <tr>
        <td>其他支付：</td>
        <td />
        <td>
          <div class="fund-item">
            <span>个人账户支付</span><span class="num">{{ fmtMoney(data.personal_account_expend) }}</span>
          </div>
        </td>
      </tr>
      <tr>
        <td>&nbsp; &nbsp; 大病保险</td>
        <td class="num" />
        <td>
          <div class="fund-item">
            <span>个人现金支付</span><span class="num">{{ fmtMoney(data.cash_payment_amount) }}</span>
          </div>
        </td>
      </tr>
      <tr>
        <td>&nbsp; &nbsp; 医疗救助</td>
        <td class="num" />
        <td />
      </tr>
      <tr>
        <td>&nbsp; &nbsp; 公务员医疗补助</td>
        <td class="num" />
        <td />
      </tr>
      <tr>
        <td>&nbsp; &nbsp; 大额补充</td>
        <td class="num" />
        <td />
      </tr>
      <tr>
        <td>&nbsp; &nbsp; 企业补充</td>
        <td class="num" />
        <td />
      </tr>
    </table>

    <!-- 底部签名区 -->
    <table class="ss-tbl">
      <tr>
        <td colspan="6">
          医保支付方式□ 1.按项目 &nbsp; 2.单病种 &nbsp; 3.按病种分值 &nbsp;
          4.疾病诊断相关分组（DRG） &nbsp; 5.按床日 &nbsp; 6.按人头 &nbsp; 9.其他 &nbsp;
          <span class="bold">{{ v('insurance_type') }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="3">
          医疗机构填报部门<u class="fill">{{ v('medical_insurance_record_dept') }}</u>
        </td>
        <td colspan="3">
          医疗机构填报人<u class="fill">{{ v('medical_insurance_recorder') }}</u>
        </td>
      </tr>
    </table>
    <div class="ss-footer">
      （注："*"代表选填数据指标）
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: any }>()

type Dict = Record<string, unknown>

/** 安全取值 */
function v(field: string): string {
  return props.data?.[field] || ''
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    if (value !== null && value !== undefined && String(value).trim()) {
      return String(value).trim()
    }
  }
  return ''
}

function parseNum(value: unknown): number | null {
  const text = firstText(value).replace(/,/g, '')
  const match = text.match(/-?\d+(?:\.\d+)?/)
  if (!match) return null
  const num = Number(match[0])
  return Number.isFinite(num) ? num : null
}

/** 格式化金额 */
function fmtMoney(val: any): string {
  if (!val || val === 'None') return ''
  const num = parseFloat(val)
  return isNaN(num) ? String(val) : num.toFixed(2)
}

function isTcmDiagnosis(d: Dict): boolean {
  return firstText(d.diagnosis_type, d.type).includes('中医')
}

function isEmergencyDiagnosis(d: Dict): boolean {
  return firstText(d.diagnosis_type, d.type).includes('门')
}

function normalizeDiagnosis(d: Dict) {
  return {
    type: firstText(d.diagnosis_type, d.type),
    name: firstText(d.name, d.diagnosis_name),
    code: firstText(d.code, d.diagnosis_code),
    condition: firstText(d.condition, d.admission_condition),
    isTcm: isTcmDiagnosis(d),
    isEmergency: isEmergencyDiagnosis(d),
  }
}

const normalizedDiagnoses = computed(() => {
  const list = Array.isArray(props.data?.diagnoses) ? props.data.diagnoses : []
  return list.map((item: Dict) => normalizeDiagnosis(item)).filter((item) => item.name)
})

const firstDiag = computed(() => {
  const d = normalizedDiagnoses.value.find((item) => item.isEmergency && !item.isTcm)
  return d?.name || ''
})
const firstDiagCode = computed(() => {
  const d = normalizedDiagnoses.value.find((item) => item.isEmergency && !item.isTcm)
  return d?.code || ''
})
const firstTcmDiag = computed(() => {
  const d = normalizedDiagnoses.value.find((item) => item.isEmergency && item.isTcm)
  return d?.name || ''
})
const firstTcmDiagCode = computed(() => {
  const d = normalizedDiagnoses.value.find((item) => item.isEmergency && item.isTcm)
  return d?.code || ''
})

/** 诊断表格（至少 6 行，最多展示实际数量+1 空行） */
const paddedDiagnoses = computed(() => {
  const discharge = normalizedDiagnoses.value.filter((item) => !item.isEmergency)
  const western = discharge.filter((item) => !item.isTcm)
  const tcm = discharge.filter((item) => item.isTcm)
  const rowCount = Math.max(western.length, tcm.length)
  const rows = Array.from({ length: rowCount }, (_, index) => ({
    western_name: western[index]?.name || '',
    western_code: western[index]?.code || '',
    western_condition: western[index]?.condition || '',
    tcm_name: tcm[index]?.name || '',
    tcm_code: tcm[index]?.code || '',
    tcm_condition: tcm[index]?.condition || '',
  }))
  const minRows = Math.max(6, rows.length + 1)
  while (rows.length < minRows) {
    rows.push({
      western_name: '',
      western_code: '',
      western_condition: '',
      tcm_name: '',
      tcm_code: '',
      tcm_condition: '',
    })
  }
  return rows
})

function normalizeSurgery(s: Dict) {
  return {
    name: firstText(s.name, s.surgery_name),
    code: firstText(s.code, s.surgery_code),
    date: firstText(s.date, s.surgery_date),
    surgeon: firstText(s.surgeon, s.surgeon_name),
    surgeon_code: firstText(s.surgeon_code, s.surgeon_physician_code),
    level: firstText(s.level, s.surgery_level),
    incision_grade: firstText(s.incision_grade, s.incisionGrade, s.incision_healing),
    anesthesia_method: firstText(s.anesthesia_method, s.anesthesiaMethod),
    anesthesiologist: firstText(s.anesthesiologist, s.anesthetist_name),
    anesthesiologist_code: firstText(s.anesthesiologist_code, s.anesthetist_code),
  }
}

/** 手术表格（至少 4 行，最多展示实际数量+1 空行） */
const paddedSurgeries = computed(() => {
  const list = Array.isArray(props.data?.surgeries) ? props.data.surgeries : []
  const rows = list.map((item: Dict) => normalizeSurgery(item))
  const minRows = Math.max(4, list.length + 1)
  while (rows.length < minRows) {
    rows.push({
      name: '',
      code: '',
      date: '',
      surgeon: '',
      surgeon_code: '',
      level: '',
      incision_grade: '',
      anesthesia_method: '',
      anesthesiologist: '',
      anesthesiologist_code: '',
    })
  }
  return rows
})

const ventilatorDuration = computed(() => {
  const explicitDays = firstText(props.data?.ventilator_usetime_d)
  const explicitHours = firstText(props.data?.ventilator_usetime_h)
  const explicitMinutes = firstText(props.data?.ventilator_usetime_min)
  if (explicitDays || explicitHours || explicitMinutes) {
    return { days: explicitDays, hours: explicitHours, minutes: explicitMinutes }
  }
  const totalHours = parseNum(
    props.data?.ventilator_usetime_total_hours ?? props.data?.ventilator_usetime,
  )
  if (totalHours === null) return { days: '', hours: '', minutes: '' }
  const totalMinutes = Math.round(totalHours * 60)
  const days = Math.floor(totalMinutes / (24 * 60))
  const remMinutes = totalMinutes % (24 * 60)
  const hours = Math.floor(remMinutes / 60)
  const minutes = remMinutes % 60
  return { days: String(days), hours: String(hours), minutes: String(minutes) }
})

const paddedIcuRows = computed(() => {
  const records = Array.isArray(props.data?.icu_records) ? props.data.icu_records : []
  const rows = records
    .map((item: Dict) => ({
      icu_type: firstText(item.icu_type, item.icu_name),
      icu_enter_time: firstText(item.icu_enter_time, item.icu_start_datetime),
      icu_leave_time: firstText(item.icu_leave_time, item.icu_end_datetime),
      icu_total_hours: firstText(item.icu_total_hours, item.icu_period),
    }))
    .filter(
      (item) => item.icu_type || item.icu_enter_time || item.icu_leave_time || item.icu_total_hours,
    )
  if (
    !rows.length &&
    (v('icu_type') || v('icu_enter_time') || v('icu_leave_time') || v('icu_total_hours'))
  ) {
    rows.push({
      icu_type: v('icu_type'),
      icu_enter_time: v('icu_enter_time'),
      icu_leave_time: v('icu_leave_time'),
      icu_total_hours: v('icu_total_hours'),
    })
  }
  while (rows.length < 3) {
    rows.push({ icu_type: '', icu_enter_time: '', icu_leave_time: '', icu_total_hours: '' })
  }
  return rows
})

// ---- 费用 ----
// 官方 14 大类费用项（对齐医保结算清单标准）
const COST_CATEGORIES = [
  { keys: ['general_medical_fee', 'general_medical_service_fee'], label: '一般医疗服务费' },
  { keys: ['general_treatment_fee'], label: '一般治疗操作费' },
  { keys: ['nursing_fee', 'nursing_care_fee'], label: '护理费' },
  { keys: ['other_service_fee', 'other_fee'], label: '其他费用' },
  { keys: ['pathology_diagnostic_fee', 'pathological_diagnostic_fee'], label: '病理诊断费' },
  { keys: ['lab_diagnostic_fee', 'laboratory_diagnostic_fee'], label: '实验室诊断费' },
  { keys: ['imaging_diagnostic_fee'], label: '影像学诊断费' },
  { keys: ['clinical_diagnostic_fee'], label: '临床诊断项目费' },
  {
    keys: ['treatment_fee', 'nonsurgical_treatment_fee', 'clinical_physical_therapy_fee'],
    label: '非手术治疗项目费',
  },
  { keys: ['surgery_fee', 'surgery_treatment_fee', 'anesthesia_fee'], label: '手术治疗费' },
  { keys: ['rehabilitation_fee'], label: '康复费' },
  { keys: ['chinese_medicine_fee', 'chinese_medicine_treatment_fee'], label: '中医治疗费' },
  { keys: ['western_medicine_fee'], label: '西药费' },
  { keys: ['chinese_patent_medicine_fee', 'chinese_patent_medcine_fee'], label: '中成药费' },
]

const costRows = computed(() => {
  const details = props.data?.cost_details || []
  return COST_CATEGORIES.map((cat) => {
    // 优先从 cost_details 数组匹配，其次从 data 顶层字段读取
    const matched = details.filter((d: any) => (d.type || '').includes(cat.label.replace('费', '')))
    if (matched.length > 0) {
      const sum = (field: string) => {
        const s = matched.reduce((acc: number, m: any) => acc + (parseFloat(m[field]) || 0), 0)
        return s > 0 ? s.toFixed(2) : ''
      }
      return {
        type: cat.label,
        charge: sum('charge'),
        class_a: sum('class_a_amount'),
        class_b: sum('class_b_amount'),
        own_pay: sum('own_pay_amount'),
        other: sum('other_amount'),
        isCat: false,
      }
    }
    // 从顶层字段读取（组装服务生成的草稿格式）
    const topSum = cat.keys.reduce((sum, key) => sum + (parseFloat(props.data?.[key]) || 0), 0)
    if (topSum > 0) {
      return {
        type: cat.label,
        charge: topSum.toFixed(2),
        class_a: '',
        class_b: '',
        own_pay: '',
        other: '',
        isCat: false,
      }
    }
    return {
      type: cat.label,
      charge: '',
      class_a: '',
      class_b: '',
      own_pay: '',
      other: '',
      isCat: false,
    }
  })
})

const sumCol = (field: string) => {
  const total = costRows.value.reduce(
    (s, r) => s + (parseFloat(r[field as keyof typeof r] as string) || 0),
    0,
  )
  return total > 0 ? total.toFixed(2) : ''
}
const totalCharge = computed(() => {
  // 优先使用 data.total_cost，否则从分项累加
  const top = parseFloat(props.data?.total_cost)
  if (!isNaN(top) && top > 0) return top.toFixed(2)
  return sumCol('charge')
})
const totalClassA = computed(() => sumCol('class_a'))
const totalClassB = computed(() => sumCol('class_b'))
const totalOwnPay = computed(() => sumCol('own_pay'))
const totalOther = computed(() => sumCol('other'))
</script>

<style scoped>
/* ===== 医保结算清单 — 像素级还原官方 PDF ===== */
.ss-wrapper {
  max-width: 900px;
  margin: 0 auto;
  font-family: 'SimSun', '宋体', 'Songti SC', serif;
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
.ss-title {
  text-align: center;
  font-size: 24px;
  font-weight: bold;
  letter-spacing: 6px;
  margin: 0 0 10px 0;
  font-family: 'SimHei', '黑体', sans-serif;
}

/* 区间大标题（蓝底白字） */
.ss-sec-hd {
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
.ss-tbl {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #000;
  margin-top: -1px; /* 合并相邻表格边框 */
}
.ss-tbl td {
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

/* 值加粗 */
.bold {
  font-weight: bold;
}
.center {
  text-align: center;
}
.num {
  text-align: right;
  font-family: 'Courier New', monospace;
  font-size: 11.5px;
}
.mono {
  font-family: 'Courier New', monospace;
}

/* 合计行 */
.total-row td {
  border-top: 2px solid #000;
  background: #fafafa;
}

/* 费用表行高 */
.cost-tbl td {
  height: 22px;
}

/* 诊断/手术/门诊慢特病表格数据行最小高度 */
.data-row td {
  height: 26px;
}

/* 分类小标题行 */
.cat-row td {
  background: #f8f8f8;
}

/* 基金支付表的竖排标题 */
.vert-label {
  writing-mode: vertical-lr;
  text-orientation: upright;
  letter-spacing: 4px;
  width: 24px;
  padding: 8px 2px;
  font-size: 13px;
}

/* 基金支付内部分项 */
.fund-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 底部注 */
.ss-footer {
  font-size: 10px;
  color: #666;
  text-align: left;
  margin-top: 6px;
  padding-left: 4px;
  font-weight: bold;
}

/* 打印样式 */
@media print {
  .ss-wrapper {
    padding: 0;
    max-width: none;
  }
}
</style>
