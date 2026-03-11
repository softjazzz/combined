<template>
  <!-- 医疗保障基金结算清单 - 按官方 PDF 格式渲染 -->
  <div class="settlement-sheet" v-if="data">
    <!-- ===== 标题区 ===== -->
    <h1 class="sheet-title">医疗保障基金结算清单</h1>

    <table class="sheet-table">
      <!-- 顶部3列：机构名称 / 机构代码 / 医保结算等级 -->
      <tr>
        <td colspan="3" class="fw">定点医疗机构名称 <span class="val">{{ data.designated_medical_institution || '' }}</span></td>
        <td colspan="3" class="fw">定点医疗机构代码 <span class="val">{{ data.designated_medical_institution || '' }}</span></td>
        <td colspan="2" class="fw">医保结算等级 <span class="val">{{ data.settlement_status || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="3" class="fw">医保编号 <span class="val">{{ data.insurance_no || '' }}</span></td>
        <td colspan="3" class="fw">病案号 <span class="val">{{ data.mr_no || '' }}</span></td>
        <td colspan="2" class="fw">申报时间 <span class="val">{{ data.declaration_time || '' }}</span></td>
      </tr>
    </table>

    <!-- ===== 一、基本信息 ===== -->
    <div class="section-header">一、基本信息</div>
    <table class="sheet-table">
      <tr>
        <td class="fw" style="width:15%">姓名 <span class="val">{{ data.patient_name || '' }}</span></td>
        <td class="fw" style="width:15%">性别 <span class="val">{{ genderText }}</span></td>
        <td class="fw" style="width:20%">出生日期 <span class="val">{{ data.patient_birthday || '' }}</span></td>
        <td class="fw" style="width:12%">年龄 <span class="val">{{ data.patient_age || '' }}岁</span></td>
        <td class="fw" style="width:12%">国籍 <span class="val">{{ data.nationality || data.patient_nationality || '' }}</span></td>
        <td class="fw" style="width:13%">民族 <span class="val">{{ data.patient_ethnicity || '' }}</span></td>
        <td class="fw" style="width:13%">证件号码 <span class="val">{{ data.patient_id_card || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="2" class="fw">职业 <span class="val">{{ data.occupation_category || '' }}</span></td>
        <td colspan="5" class="fw">现住址 <span class="val">{{ data.currentaddress || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="3" class="fw">工作单位名称 <span class="val">{{ data.work_unit || '' }}</span></td>
        <td colspan="2" class="fw">工作单位地址 <span class="val">{{ data.workplace || '' }}</span></td>
        <td class="fw">单位电话 <span class="val">{{ data.work_telephone || '' }}</span></td>
        <td class="fw">邮编 <span class="val">{{ data.currentaddress_postcode || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="2" class="fw">联系人姓名 <span class="val">{{ data.contact_name || '' }}</span></td>
        <td class="fw">关系 <span class="val">{{ data.contact_relationship || '' }}</span></td>
        <td colspan="2" class="fw">地址 <span class="val">{{ data.contact_address || '' }}</span></td>
        <td colspan="2" class="fw">电话 <span class="val">{{ data.contact_telephone || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="2" class="fw">医保类型 <span class="val">{{ data.patient_insurance_type || data.insurance_type || '' }}</span></td>
        <td colspan="2" class="fw">特殊人员类型 <span class="val">{{ data.special_personnel_type || '' }}</span></td>
        <td colspan="3" class="fw">参保地 <span class="val">{{ data.insured_place || '' }}</span></td>
      </tr>
      <tr v-if="data.newborn_admission_type">
        <td colspan="2" class="fw">新生儿入院类型 <span class="val">{{ data.newborn_admission_type }}</span></td>
        <td colspan="2" class="fw">新生儿出生体重 <span class="val">{{ data.newborn_birthweight }}克</span></td>
        <td colspan="3" class="fw">新生儿入院体重 <span class="val">{{ data.newborn_admitweigth }}克</span></td>
      </tr>
    </table>

    <!-- ===== 三、住院诊疗信息 ===== -->
    <div class="section-header">三、住院诊疗信息</div>
    <table class="sheet-table">
      <tr>
        <td colspan="4" class="fw">住院医疗类型 <span class="val">{{ data.inpat_type || '住院' }}</span></td>
        <td colspan="4" class="fw">入院途径 <span class="val">{{ data.admission_route || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="8" class="fw">治疗类别 <span class="val">{{ data.therapy_type || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="3" class="fw">入院时间 <span class="val">{{ data.admission_datetime || '' }}</span></td>
        <td colspan="2" class="fw">入院科别 <span class="val">{{ data.admission_dept_name || '' }}</span></td>
        <td colspan="3" class="fw">转科科别 <span class="val">{{ data.transfer_dept_name || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="3" class="fw">出院时间 <span class="val">{{ data.discharge_datetime || '' }}</span></td>
        <td colspan="2" class="fw">出院科别 <span class="val">{{ data.discharge_dept_name || '' }}</span></td>
        <td colspan="3" class="fw">实际住院 <span class="val">{{ data.hospital_duration || '' }}天</span></td>
      </tr>
    </table>

    <!-- 诊断信息 -->
    <table class="sheet-table" v-if="data.diagnoses && data.diagnoses.length">
      <tr class="header-row">
        <td style="width:8%">类型</td>
        <td style="width:8%">序号</td>
        <td style="width:42%">出院诊断</td>
        <td style="width:22%">疾病代码</td>
        <td style="width:20%">入院病情</td>
      </tr>
      <tr v-for="(d, i) in data.diagnoses" :key="'d'+i">
        <td class="center">{{ i === 0 ? '主要' : '其他' }}</td>
        <td class="center">{{ i + 1 }}</td>
        <td>{{ d.name }}</td>
        <td class="center mono">{{ d.code }}</td>
        <td class="center">{{ d.condition || '' }}</td>
      </tr>
    </table>

    <!-- 手术信息 -->
    <table class="sheet-table" v-if="data.surgeries && data.surgeries.length">
      <tr class="header-row">
        <td style="width:8%">类型</td>
        <td style="width:35%">手术及操作名称</td>
        <td style="width:17%">手术及操作代码</td>
        <td style="width:15%">手术日期</td>
        <td style="width:12%">术者姓名</td>
        <td style="width:13%">手术级别</td>
      </tr>
      <tr v-for="(s, i) in data.surgeries" :key="'s'+i">
        <td class="center">{{ i === 0 ? '主要' : '其他' }}</td>
        <td>{{ s.name }}</td>
        <td class="center mono">{{ s.code }}</td>
        <td class="center">{{ s.date || '' }}</td>
        <td class="center">{{ s.surgeon || '' }}</td>
        <td class="center">{{ s.level || '' }}</td>
      </tr>
    </table>

    <!-- 辅助信息 -->
    <table class="sheet-table">
      <tr>
        <td colspan="2" class="fw">诊断代码计数 <span class="val">{{ data.diagnosis_code_cnt || data.diagnoses?.length || '' }}</span></td>
        <td colspan="2" class="fw">手术操作代码计数 <span class="val">{{ data.surgery_code_cnt || data.surgeries?.length || '' }}</span></td>
        <td colspan="2" class="fw">呼吸机使用时间 <span class="val">{{ data.ventilator_usetime || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="3" class="fw">特级护理天数 <span class="val">{{ data.intensive_care_days || '' }}</span> &nbsp; 一级护理天数 <span class="val">{{ data.primary_care_days || '' }}</span></td>
        <td colspan="3" class="fw">二级护理天数 <span class="val">{{ data.secondary_care_days || '' }}</span> &nbsp; 三级护理天数 <span class="val">{{ data.tertiary_care_days || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="4" class="fw">离院方式 <span class="val">{{ data.leaving_hospital_way || '' }}</span></td>
        <td colspan="2" class="fw">拟接收机构 <span class="val">{{ data.receiving_institution_name || '' }}</span></td>
      </tr>
      <tr>
        <td colspan="4" class="fw">是否有出院31天内再住院计划 <span class="val">{{ data.rehospital_with_month || '无' }}</span></td>
        <td colspan="2" class="fw">目的 <span class="val">{{ data.rehospital_with_month_purpose || '' }}</span></td>
      </tr>
    </table>

    <!-- ===== 四、医疗收费信息 ===== -->
    <div class="section-header">四、医疗收费信息</div>
    <table class="sheet-table">
      <tr>
        <td colspan="3" class="fw">业务流水号 <span class="val">{{ data.business_serial_no || '' }}</span></td>
        <td colspan="3" class="fw">结算期间 <span class="val">{{ data.start_date || '' }} — {{ data.end_date || '' }}</span></td>
      </tr>
    </table>

    <!-- 费用明细表 -->
    <table class="sheet-table cost-table">
      <tr class="header-row">
        <td style="width:25%">项目名称</td>
        <td style="width:15%">金额</td>
        <td style="width:15%">甲类</td>
        <td style="width:15%">乙类</td>
        <td style="width:15%">自费</td>
        <td style="width:15%">其他</td>
      </tr>
      <tr v-for="item in costRows" :key="item.type">
        <td>{{ item.type }}</td>
        <td class="num">{{ item.charge || '' }}</td>
        <td class="num">{{ item.class_a || '' }}</td>
        <td class="num">{{ item.class_b || '' }}</td>
        <td class="num">{{ item.own_pay || '' }}</td>
        <td class="num">{{ item.other || '' }}</td>
      </tr>
      <tr class="total-row">
        <td><strong>金额合计</strong></td>
        <td class="num"><strong>{{ totalCharge }}</strong></td>
        <td class="num"><strong>{{ totalClassA }}</strong></td>
        <td class="num"><strong>{{ totalClassB }}</strong></td>
        <td class="num"><strong>{{ totalOwnPay }}</strong></td>
        <td class="num"><strong>{{ totalOther }}</strong></td>
      </tr>
    </table>

    <!-- 基金支付 / 个人支付 -->
    <table class="sheet-table">
      <tr class="header-row">
        <td colspan="3" style="width:50%">基金支付</td>
        <td colspan="3" style="width:50%">个人支付</td>
      </tr>
      <tr>
        <td>医保统筹基金支付</td>
        <td colspan="2" class="num val">{{ data.insurance_type || '' }}</td>
        <td>个人自付</td>
        <td colspan="2" class="num val">{{ data.out_of_pocket_advance || '' }}</td>
      </tr>
      <tr>
        <td>大病保险</td>
        <td colspan="2" class="num val"></td>
        <td>个人自费</td>
        <td colspan="2" class="num val">{{ data.out_of_pocket_amount || '' }}</td>
      </tr>
      <tr>
        <td>医疗救助</td>
        <td colspan="2" class="num val"></td>
        <td>个人账户支付</td>
        <td colspan="2" class="num val">{{ data.personal_account_expend || '' }}</td>
      </tr>
      <tr>
        <td>公务员医疗补助</td>
        <td colspan="2" class="num val"></td>
        <td>个人现金支付</td>
        <td colspan="2" class="num val">{{ data.cash_payment_amount || '' }}</td>
      </tr>
    </table>

    <!-- 底部 -->
    <table class="sheet-table">
      <tr>
        <td colspan="8" class="fw">
          医保支付方式 <span class="val">{{ data.insurance_type || '' }}</span>
        </td>
      </tr>
      <tr>
        <td colspan="4" class="fw">医疗机构填报部门 <span class="val">{{ data.medical_insurance_record_dept || '' }}</span></td>
        <td colspan="4" class="fw">医疗机构填报人 <span class="val">{{ data.medical_insurance_recorder || '' }}</span></td>
      </tr>
    </table>
    <div class="sheet-footer">（注："*"代表选填数据指标）</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: any }>()

const genderText = computed(() => {
  const s = props.data?.patient_sex || props.data?.sex || ''
  if (s === '男' || s === '1') return '男'
  if (s === '女' || s === '2') return '女'
  return s
})

// 费用类型列表（按官方顺序）
const COST_TYPES = [
  '床位费', '诊察费', '检查费', '化验费', '治疗费', '手术费',
  '护理费', '卫生材料费', '西药费', '中药饮片费', '中成药费',
  '一般诊疗费', '挂号费', '其他费',
]

const costRows = computed(() => {
  const details = props.data?.cost_details || []
  // 按官方费用类别映射
  return COST_TYPES.map(type => {
    const matched = details.filter((d: any) => (d.type || '').includes(type.replace('费', '')))
    if (matched.length > 0) {
      const sum = (field: string) => {
        const v = matched.reduce((s: number, m: any) => s + (parseFloat(m[field]) || 0), 0)
        return v > 0 ? v.toFixed(2) : ''
      }
      return {
        type,
        charge: sum('charge'),
        class_a: sum('class_a_amount'),
        class_b: sum('class_b_amount'),
        own_pay: sum('own_pay_amount'),
        other: sum('other_amount'),
      }
    }
    return { type, charge: '', class_a: '', class_b: '', own_pay: '', other: '' }
  })
})

const sumCol = (field: string) => {
  const total = costRows.value.reduce((s, r) => s + (parseFloat(r[field as keyof typeof r] as string) || 0), 0)
  return total > 0 ? total.toFixed(2) : ''
}
const totalCharge = computed(() => sumCol('charge'))
const totalClassA = computed(() => sumCol('class_a'))
const totalClassB = computed(() => sumCol('class_b'))
const totalOwnPay = computed(() => sumCol('own_pay'))
const totalOther = computed(() => sumCol('other'))
</script>

<style scoped>
.settlement-sheet {
  max-width: 900px;
  margin: 0 auto;
  font-family: 'SimSun', 'Songti SC', serif;
  font-size: 12px;
  color: #000;
  line-height: 1.6;
  background: #fff;
  padding: 32px 40px;
}

.sheet-title {
  text-align: center;
  font-size: 22px;
  font-weight: bold;
  letter-spacing: 6px;
  margin-bottom: 12px;
  padding-bottom: 8px;
}

.section-header {
  font-size: 13px;
  font-weight: bold;
  padding: 6px 4px 4px;
  border-bottom: 2px solid #000;
  margin-top: 8px;
  margin-bottom: 0;
}

.sheet-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #000;
  margin-bottom: -1px; /* 合并相邻表格边框 */
}

.sheet-table td {
  border: 1px solid #000;
  padding: 4px 6px;
  font-size: 11.5px;
  vertical-align: middle;
}

.sheet-table .fw {
  font-size: 11px;
}

.sheet-table .val {
  font-weight: bold;
  color: #1a1a1a;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.sheet-table .center {
  text-align: center;
}

.sheet-table .num {
  text-align: right;
  font-family: 'Courier New', monospace;
  font-size: 11.5px;
}

.sheet-table .mono {
  font-family: 'Courier New', monospace;
}

.header-row td {
  background: #f0f0f0;
  font-weight: bold;
  text-align: center;
  font-size: 11px;
}

.total-row td {
  background: #fafafa;
  border-top: 2px solid #000;
}

.cost-table td {
  height: 24px;
}

.sheet-footer {
  font-size: 10px;
  color: #666;
  text-align: right;
  margin-top: 8px;
  padding-right: 4px;
}

/* 打印样式 */
@media print {
  .settlement-sheet {
    padding: 0;
    max-width: none;
  }
}
</style>
