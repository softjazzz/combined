<template>
  <div class="fp-wrapper">
    <!-- ============== 第一页 ============== -->
    <div class="fp-page">
      <!-- 附件标记 -->
      <div class="fp-top-attachment">附件 1</div>
      
      <!-- 顶部 Header -->
      <div class="fp-header">
        <div class="header-line">
          <span style="display:inline-block; width: 220px;">医疗机构<u class="fill">{{ b('institute_county_desc') }}</u></span>
          <span style="flex:1; text-align:right;">（组织机构代码：<u class="fill" style="width:120px; text-align:left;">{{ b('institute_code') }}</u>）</span>
        </div>
        
        <div class="header-line" style="position: relative; margin: 4px 0;">
          <span style="position: absolute; left: 0; bottom: 4px;">医疗付费方式：<span class="val-box">{{ b('medical_payment_method') }}</span></span>
          <h1 class="fp-title">住 院 病 案 首 页</h1>
        </div>
        
        <div class="header-line" style="display: flex; justify-content: space-between;">
          <span>健康卡号：<u class="fill" style="width:120px">{{ b('insurance_no') }}</u></span>
          <span>第 <u class="fill" style="width:40px">{{ b('visit_cnt') || '1' }}</u> 次住院</span>
          <span>病案号：<u class="fill" style="width:120px">{{ b('document_id') }}</u></span>
        </div>
      </div>

      <!-- 大黑框1 -->
      <div class="fp-main-box">
        <!-- 身份信息区 -->
        <div class="fp-row">
          <span>姓名</span><u class="fill flex-1"><b>{{ b('name') }}</b></u>
          <span class="ml-2">性别</span><span class="val-box">{{ b('sex') }}</span><span class="hint">1.男 2.女</span>
          <span class="ml-4">出生日期</span><u class="fill w-10">{{ dateParts(b('birthday')).year }}</u><span>年</span><u class="fill w-8">{{ dateParts(b('birthday')).month }}</u><span>月</span><u class="fill w-8">{{ dateParts(b('birthday')).day }}</u><span>日</span>
          <span class="ml-4">年龄</span><u class="fill w-10">{{ computedAge }}</u>
          <span class="ml-4">国籍</span><u class="fill w-12">{{ b('nationality') || '中国' }}</u>
        </div>
        
        <div class="fp-row">
          <span class="hint">（年龄不足1周岁的）</span>
          <span>年龄</span><u class="fill w-10"></u><span>月</span>
          <span class="ml-4">新生儿出生体重</span><u class="fill w-12"></u><span>克</span>
          <span class="ml-4">新生儿入院体重</span><u class="fill w-12"></u><span>克</span>
        </div>
        
        <div class="fp-row">
          <span>出生地</span><u class="fill flex-1"></u><span>省(区、市)</span><u class="fill flex-1"></u><span>市</span><u class="fill flex-1"></u><span>县</span>
          <span class="ml-4">籍贯</span><u class="fill flex-1">{{ parseProvCity(b('nativeplace')).prov }}</u><span>省(区、市)</span><u class="fill flex-1">{{ parseProvCity(b('nativeplace')).city }}</u><span>市</span>
          <span class="ml-4">民族</span><u class="fill w-16">{{ b('ethnicity') }}</u>
        </div>
        
        <div class="fp-row">
          <span>身份证号</span><u class="fill flex-1">{{ b('id_card_no') }}</u>
          <span class="ml-4">职业</span><u class="fill flex-1">{{ b('occupation_category') }}</u>
          <span class="ml-4">婚姻</span><span class="val-box">{{ b('marital_status') }}</span><span class="hint">1.未婚 2.已婚 3.丧偶 4.离婚 9.其他</span>
        </div>
        
        <div class="fp-row">
          <span>现住址</span><u class="fill flex-1">{{ parseAddress(b('currentaddress')).prov }}</u><span>省(区、市)</span><u class="fill flex-1">{{ parseAddress(b('currentaddress')).city }}</u><span>市</span><u class="fill flex-1">{{ parseAddress(b('currentaddress')).county }}</u><span>县</span>
          <span class="ml-4">电话</span><u class="fill w-24">{{ b('contact_number') }}</u>
          <span class="ml-4">邮编</span><u class="fill w-16"></u>
        </div>
        
        <div class="fp-row">
          <span>户口地址</span><u class="fill flex-1"></u><span>省(区、市)</span><u class="fill flex-1"></u><span>市</span><u class="fill flex-1"></u><span>县</span>
          <span class="ml-4">邮编</span><u class="fill w-16"></u>
        </div>
        
        <div class="fp-row">
          <span>工作单位及地址</span><u class="fill flex-1">{{ b('work_unit') }}</u>
          <span class="ml-4">单位电话</span><u class="fill w-24"></u>
          <span class="ml-4">邮编</span><u class="fill w-16"></u>
        </div>
        
        <div class="fp-row">
          <span>联系人姓名</span><u class="fill flex-1">{{ b('contact_name') }}</u>
          <span class="ml-4">关系</span><u class="fill w-16">{{ b('contact_relationship') }}</u>
          <span class="ml-4">地址</span><u class="fill flex-1">{{ b('contact_address') }}</u>
          <span class="ml-4">电话</span><u class="fill w-24">{{ b('contact_telephone') }}</u>
        </div>
        
        <div class="fp-row">
          <span>入院途径</span><span class="val-box">{{ b('admission_route') }}</span><span class="hint">1.急诊 2.门诊 3.其他医疗机构转入 9.其他</span>
        </div>
        
        <div class="fp-row">
          <span>入院时间</span><u class="fill w-10">{{ dateParts(b('admission_datetime')).year }}</u><span>年</span><u class="fill w-8">{{ dateParts(b('admission_datetime')).month }}</u><span>月</span><u class="fill w-8">{{ dateParts(b('admission_datetime')).day }}</u><span>日</span><u class="fill w-8">{{ dateParts(b('admission_datetime')).hour }}</u><span>时</span>
          <span class="ml-4">入院科别</span><u class="fill flex-1">{{ b('admission_dept_name') }}</u>
          <span class="ml-4">病房</span><u class="fill flex-1">{{ b('admission_ward_name') }}</u>
          <span class="ml-4">转科科别</span><u class="fill flex-1">{{ b('transfer_dept_name') }}</u>
        </div>
        
        <div class="fp-row">
          <span>出院时间</span><u class="fill w-10">{{ dateParts(b('discharge_datetime')).year }}</u><span>年</span><u class="fill w-8">{{ dateParts(b('discharge_datetime')).month }}</u><span>月</span><u class="fill w-8">{{ dateParts(b('discharge_datetime')).day }}</u><span>日</span><u class="fill w-8">{{ dateParts(b('discharge_datetime')).hour }}</u><span>时</span>
          <span class="ml-4">出院科别</span><u class="fill flex-1">{{ b('discharge_dept_name') }}</u>
          <span class="ml-4">病房</span><u class="fill flex-1">{{ b('discharge_ward_name') }}</u>
          <span class="ml-4">实际住院</span><u class="fill w-10">{{ b('hospital_duration') }}</u><span>天</span>
        </div>
        
        <div class="fp-row" style="border-bottom: none;">
          <span>门（急）诊诊断</span><u class="fill flex-1"></u>
          <span class="ml-4">疾病编码</span><u class="fill w-32"></u>
        </div>
        
        <!-- 诊断表格 (内外边框均需控制) -->
        <table class="fp-table diag-table" style="border-left:none; border-right:none; width: 100%;">
          <thead>
            <tr>
              <th style="width:28%; border-left:none;">出院诊断</th>
              <th style="width:12%">疾病编码</th>
              <th style="width:8%">入院<br/>病情</th>
              <th style="width:28%">出院诊断</th>
              <th style="width:12%">疾病编码</th>
              <th style="width:8%; border-right:none;">入院<br/>病情</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(pair, idx) in diagnosisPairs" :key="idx">
              <td style="border-left:none;">
                <span v-if="pair.left">
                  <b v-if="idx === 0">主要诊断：</b>
                  <span v-else-if="idx === 1">其他诊断：</span>
                  {{ pair.left.diagnosis_name }}
                </span>
                <span v-else-if="idx === 0">主要诊断：</span>
                <span v-else-if="idx === 1">其他诊断：</span>
              </td>
              <td class="mono center">{{ pair.left?.diagnosis_code }}</td>
              <td class="center">{{ pair.left?.admission_condition }}</td>
              <td>
                <span v-if="pair.right">
                  <span v-if="idx === 0">其他诊断：</span>
                  {{ pair.right.diagnosis_name }}
                </span>
                <span v-else-if="idx === 0">其他诊断：</span>
              </td>
              <td class="mono center">{{ pair.right?.diagnosis_code }}</td>
              <td class="center" style="border-right:none;">{{ pair.right?.admission_condition }}</td>
            </tr>
          </tbody>
        </table>
        
        <div class="fp-row">
          <span>入院病情：</span><span class="hint">1.有, 2.临床未确定, 3.情况不明, 4.无</span>
        </div>
        
        <div class="fp-row">
          <span>损伤、中毒的外部原因</span><u class="fill flex-1"></u>
          <span class="ml-4">疾病编码</span><u class="fill w-32"></u>
        </div>
        
        <div class="fp-row" style="border-bottom: none;">
          <span>病理诊断：</span><u class="fill flex-1"></u>
          <span class="ml-4">疾病编码</span><u class="fill w-32"></u>
        </div>
        
        <div class="fp-row text-right-align">
          <span style="flex:1;"></span>
          <span class="ml-4">病理号</span><u class="fill w-32">{{ t('pathology_id') }}</u>
        </div>
        
        <div class="fp-row">
          <span>药物过敏</span><span class="val-box">{{ b('allergy_sign') === '2' ? '2' : '1' }}</span><span class="hint">1.无 2.有，过敏药物：</span>
          <u class="fill flex-1">{{ b('allergy_sign') === '2' ? t('allergy_history') : '' }}</u>
          <span class="ml-4">死亡患者尸检</span><span class="val-box">{{ b('death_autopsy_sign') }}</span><span class="hint">1.是 2.否</span>
        </div>
        
        <div class="fp-row">
          <span>血型</span><span class="val-box">{{ b('abo_blood_code') }}</span><span class="hint">1.A 2.B 3.O 4.AB 5.不详 6.未查</span>
          <span class="ml-8">Rh</span><span class="val-box">{{ b('rh_blood_code') }}</span><span class="hint">1.阴 2.阳 3.不详 4.未查</span>
        </div>
        
        <div class="fp-row" style="border-top: 2px solid #000; padding-top: 6px;">
          <span>科主任</span><u class="fill flex-1">{{ b('deptdirector_sign') }}</u>
          <span class="ml-2">主任（副主任）医师</span><u class="fill flex-1">{{ b('chief_physician_sign') }}</u>
          <span class="ml-2">主治医师</span><u class="fill flex-1">{{ b('attending_physician_sign') }}</u>
          <span class="ml-2">住院医师</span><u class="fill flex-1">{{ b('resident_physician_sign') }}</u>
        </div>
        
        <div class="fp-row">
          <span>责任护士</span><u class="fill flex-1">{{ b('responsible_nurse_sign') }}</u>
          <span class="ml-2">进修医师</span><u class="fill flex-1"></u>
          <span class="ml-2">实习医师</span><u class="fill flex-1"></u>
          <span class="ml-2">编码员</span><u class="fill flex-1">{{ b('coder_sign') }}</u>
        </div>
        
        <div class="fp-row">
          <span>病案质量</span><span class="val-box">{{ b('medicalrecord_quality') }}</span><span class="hint">1.甲 2.乙 3.丙</span>
          <span class="ml-8">质控医师</span><u class="fill flex-1">{{ t('QC_physician_sign') }}</u>
          <span class="ml-4">质控护士</span><u class="fill flex-1">{{ t('QC_nurse_sign') }}</u>
        </div>
        
        <div class="fp-row" style="border-bottom: none;">
          <span>期</span><u class="fill w-10"></u><span>年</span><u class="fill w-8"></u><span>月</span><u class="fill w-8"></u><span>日</span>
        </div>

      </div>
    </div>

    <!-- ============== 第二页 ============== -->
    <div class="fp-page" style="margin-top: 30px;">
      <!-- 大黑框2 -->
      <div class="fp-main-box">
        
        <!-- 手术表格 -->
        <table class="fp-table surgery-table" style="border-left:none; border-right:none; border-top:none; width: 100%;">
          <thead>
            <tr>
              <th rowspan="2" style="width:10%; border-left:none; border-top:none;">手术及<br/>操作编码</th>
              <th rowspan="2" style="width:9%; border-top:none;">手术及<br/>操作日期</th>
              <th rowspan="2" style="width:5%; border-top:none;">手术<br/>级别</th>
              <th rowspan="2" style="width:20%; border-top:none;">手术及操作名称</th>
              <th colspan="3" style="border-top:none;">手术及操作医师</th>
              <th rowspan="2" style="width:7%; border-top:none;">切口愈<br/>合等级</th>
              <th rowspan="2" style="width:8%; border-top:none;">麻醉方式</th>
              <th rowspan="2" style="width:8%; border-right:none; border-top:none;">麻醉医师</th>
            </tr>
            <tr>
              <th style="width:7%">术者</th>
              <th style="width:6%">Ⅰ助</th>
              <th style="width:6%">Ⅱ助</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(s, idx) in paddedSurgeries" :key="idx">
              <td class="mono center" style="border-left:none;">{{ s.surgery_code }}</td>
              <td class="center">{{ formatDateShort(s.surgery_begin_datetime) }}</td>
              <td class="center">{{ s.surgical_level }}</td>
              <td>{{ s.surgery_name }}</td>
              <td class="center">{{ s.surgeon }}</td>
              <td class="center">{{ s.first_assistant }}</td>
              <td class="center">{{ s.second_assistant }}</td>
              <td class="center">{{ formatIncision(s) }}</td>
              <td class="center">{{ s.anesthesia_method }}</td>
              <td class="center" style="border-right:none;">{{ s.anesthesiologist }}</td>
            </tr>
          </tbody>
        </table>

        <!-- 离院等信息 -->
        <div class="fp-row" style="border-bottom: none; padding-bottom: 0; min-height: auto;">
          <span>离院方式</span><span class="val-box">{{ b('leaving_hospital_way') }}</span><span class="hint">1.医嘱离院 2.医嘱转院，拟接收医疗机构名称：</span>
          <u class="fill flex-1">{{ t('planned_transder_to') }}</u>
        </div>
        
        <div class="fp-row" style="padding-top: 4px; min-height: auto;">
          <span class="hint">3.医嘱转社区卫生服务机构/乡镇卫生院，拟接收医疗机构名称：</span>
          <u class="fill flex-1"></u>
          <span class="hint ml-2">4.非医嘱离院 5.死亡 9.其他</span>
        </div>
        
        <div class="fp-row">
          <span>是否有出院31天内再住院计划</span><span class="val-box">{{ b('rehospital_with_month') }}</span><span class="hint">1.无 2.有，目的：</span>
          <u class="fill flex-1">{{ t('rehospital_with_month_purpose') }}</u>
        </div>
        
        <div class="fp-row">
          <span class="hint">颅脑损伤患者昏迷时间：入院前</span><u class="fill w-10"></u><span>天</span><u class="fill w-8"></u><span>小时</span><u class="fill w-8"></u><span>分钟</span>
          <span class="hint ml-8">入院后</span><u class="fill w-10"></u><span>天</span><u class="fill w-8"></u><span>小时</span><u class="fill w-8"></u><span>分钟</span>
        </div>

        <!-- 费用明细 (粗横线分割) -->
        <div class="fp-row" style="border-top: 2px solid #000; font-weight: bold; padding-top: 6px;">
          <span>住院费用（元）：总费用</span><u class="fill flex-1 cost-val">{{ c('total_cost') }}</u>
          <span class="ml-4">（自付金额：</span><u class="fill flex-1 cost-val">{{ c('self_pay') }}</u><span>）</span>
        </div>
        
        <div class="fp-row">
          <b>1.综合医疗服务类：</b>
          <span>（1）一般医疗服务费：</span><u class="fill flex-1 cost-val">{{ c('general_medical_service_fee') }}</u>
          <span>（2）一般治疗操作费：</span><u class="fill flex-1 cost-val">{{ c('general_treatment_fee') }}</u>
          <span>（3）护理费：</span><u class="fill flex-1 cost-val">{{ c('nursing_care_fee') }}</u>
        </div>
        <div class="fp-row">
          <span>（4）其他费用：</span><u class="fill flex-1 cost-val">{{ c('other_service_fee') }}</u>
        </div>
        
        <div class="fp-row">
          <b>2.诊断类：</b>
          <span>（5）病理诊断费：</span><u class="fill flex-1 cost-val">{{ c('pathological_diagnostic_fee') }}</u>
          <span>（6）实验室诊断费：</span><u class="fill flex-1 cost-val">{{ c('laboratory_diagnostic_fee') }}</u>
          <span>（7）影像学诊断费：</span><u class="fill flex-1 cost-val">{{ c('imaging_diagnostic_fee') }}</u>
        </div>
        <div class="fp-row">
          <span>（8）临床诊断项目费：</span><u class="fill flex-1 cost-val">{{ c('clinical_diagnostic_fee') }}</u>
        </div>
        
        <div class="fp-row">
          <b>3.治疗类：</b>
          <span>（9）非手术治疗项目费：</span><u class="fill flex-1 cost-val">{{ c('nonsurgical_treatment_fee') }}</u>
          <span>（临床物理治疗费：</span><u class="fill flex-1 cost-val">{{ c('clinical_physical_therapy_fee') }}</u><span>）</span>
        </div>
        <div class="fp-row">
          <span>（10）手术治疗费：</span><u class="fill flex-1 cost-val">{{ c('surgery_treatment_fee') }}</u>
          <span>（麻醉费：</span><u class="fill flex-1 cost-val">{{ c('anesthesia_fee') }}</u>
          <span>手术费：</span><u class="fill flex-1 cost-val">{{ c('surgery_fee') }}</u><span>）</span>
        </div>
        
        <div class="fp-row">
          <b>4.康复类：</b>
          <span>（11）康复费：</span><u class="fill flex-1 cost-val">{{ c('rehabilitation_fee') }}</u>
        </div>
        
        <div class="fp-row">
          <b>5.中医类：</b>
          <span>（12）中医治疗费：</span><u class="fill flex-1 cost-val"></u>
        </div>
        
        <div class="fp-row">
          <b>6.西药类：</b>
          <span>（13）西药费：</span><u class="fill flex-1 cost-val">{{ c('western_medicine_fee') }}</u>
          <span>（抗菌药物费用：</span><u class="fill flex-1 cost-val">{{ c('antibacterial_drug_fee') }}</u><span>）</span>
        </div>
        
        <div class="fp-row">
          <b>7.中药类：</b>
          <span>（14）中成药费：</span><u class="fill flex-1 cost-val">{{ c('chinese_patent_medcine_fee') }}</u>
          <span>（15）中草药费：</span><u class="fill flex-1 cost-val">{{ c('chinese_herbal_medicine_fee') }}</u>
        </div>
        
        <div class="fp-row">
          <b>8.血液和血液制品类：</b>
          <span>（16）血费：</span><u class="fill flex-1 cost-val">{{ c('blood_fee') }}</u>
          <span>（17）白蛋白类制品费：</span><u class="fill flex-1 cost-val"></u>
          <span>（18）球蛋白类制品费：</span><u class="fill flex-1 cost-val"></u>
        </div>
        <div class="fp-row">
          <span>（19）凝血因子类制品费：</span><u class="fill flex-1 cost-val"></u>
          <span>（20）细胞因子类制品费：</span><u class="fill flex-1 cost-val"></u>
        </div>
        
        <div class="fp-row">
          <b>9.耗材类：</b>
          <span>（21）检查用一次性医用材料费：</span><u class="fill flex-1 cost-val">{{ c('exam_disposable_mat_fee') }}</u>
          <span>（22）治疗用一次性医用材料费：</span><u class="fill flex-1 cost-val">{{ c('treat_disposable_mat_fee') }}</u>
        </div>
        <div class="fp-row">
          <span>（23）手术用一次性医用材料费：</span><u class="fill flex-1 cost-val">{{ c('surgery_disposable_mat_fee') }}</u>
        </div>
        
        <div class="fp-row" style="border-bottom: none;">
          <b>10.其他类：</b>
          <span>（24）其他费：</span><u class="fill flex-1 cost-val">{{ c('other_fee') }}</u>
        </div>

      </div>

      <!-- 底部说明文字 -->
      <div class="fp-footer-desc">
        <div>说明：（一）医疗付费方式 1.城镇职工基本医疗保险 2.城镇居民基本医疗保险 3.新型农村合作医疗 4.贫困救助 5.商业医疗保险 6.全公费 7.全自费 8.其他社会保险 9.其他</div>
        <div style="padding-left: 38px;">（二）凡可由医院信息系统提供住院费用清单的，住院病案首页中可不填写“住院费用”。</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true }
})

function b(field) {
  return props.data?.basic?.[field] || ''
}

// t() 用于纯粹长下划线填空，过滤掉数据库里的 '/' 或 '-'，避免打印在下划线上显得突兀
function t(field) {
  const v = props.data?.basic?.[field]
  return (!v || v === '/' || v === '-') ? '' : v
}

function c(field) {
  const val = props.data?.cost?.[field]
  if (!val || val === 'None') return ''
  const num = parseFloat(val)
  return isNaN(num) ? val : num.toFixed(2)
}

function dateParts(val) {
  if (!val) return { year: '', month: '', day: '', hour: '' }
  const m = val.match(/(\d{4})-(\d{2})-(\d{2})\s*(\d{2})?/)
  if (m) {
    return { year: m[1], month: m[2], day: m[3], hour: m[4] || '' }
  }
  return { year: '', month: '', day: '', hour: '' }
}

function formatDateShort(val) {
  if (!val) return ''
  const m = val.match(/(\d{4})-(\d{2})-(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]}`
  return val
}

function parseProvCity(val) {
  if (!val) return { prov: '', city: '' }
  // 简化的省市提取
  let prov = val, city = ''
  if (val.includes('省')) {
    const parts = val.split('省')
    prov = parts[0]
    city = parts[1]?.replace('市', '') || ''
  } else if (val.includes('市')) {
    prov = val.split('市')[0]
  }
  return { prov, city }
}

function parseAddress(val) {
  if (!val) return { prov: '', city: '', county: '' }
  let prov = '', city = '', county = ''
  let remain = val
  if (remain.includes('省')) {
    prov = remain.split('省')[0]
    remain = remain.split('省')[1]
  }
  if (remain.includes('市')) {
    city = remain.split('市')[0]
    remain = remain.split('市')[1]
  }
  if (remain.includes('县')) {
    county = remain.split('县')[0]
  } else if (remain.includes('区')) {
    county = remain.split('区')[0]
  }
  if (!prov && !city && !county) prov = val
  return { prov, city, county }
}

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
    return age >= 1 ? `${age}` : `${Math.floor((now - birth) / (1000*60*60*24*30))}月`
  } catch { return '' }
})

const diagnosisPairs = computed(() => {
  const diags = props.data?.diagnoses || []
  const mainDiag = diags.filter(d => d.diagnosis_type?.includes('主要'))
  const otherDiag = diags.filter(d => !d.diagnosis_type?.includes('主要'))

  const leftItems = [...mainDiag, ...otherDiag.slice(0, Math.ceil(otherDiag.length / 2))]
  const rightItems = otherDiag.slice(Math.ceil(otherDiag.length / 2))

  const rowCount = Math.max(leftItems.length, rightItems.length, 10) 
  const pairs = []
  for (let i = 0; i < rowCount; i++) {
    pairs.push({
      left: leftItems[i] || null,
      right: rightItems[i] || null
    })
  }
  return pairs
})

const paddedSurgeries = computed(() => {
  const s = props.data?.surgeries || []
  const rows = [...s]
  while (rows.length < 8) {
    rows.push({ surgery_code: '', surgery_name: '', surgeon: '' })
  }
  return rows
})

function formatIncision(s) {
  if (!s.surgery_name && !s.surgery_code) return ''
  if (!s.surgial_incision_level && !s.surgical_incisionheal_level) return '/'
  return `${s.surgial_incision_level || ''} / ${s.surgical_incisionheal_level || ''}`
}
</script>

<style scoped>
/* ===== 住院病案首页 — 像素级还原官方PDF长相 ===== */
.fp-wrapper {
  background: #f1f5f9; /* 外层背景，模拟看纸张 */
  padding: 30px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.fp-page {
  font-family: "SimSun", "宋体", "Songti SC", serif;
  font-size: 13.5px;
  color: #000;
  background: #fff;
  width: 794px; /* A4 宽度 210mm 以 96dpi 计算 */
  min-height: 1123px; /* A4 高度 */
  padding: 30px 40px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  position: relative;
  box-sizing: border-box;
}

/* 顶部文号标记 */
.fp-top-attachment {
  position: absolute;
  top: 15px;
  left: 40px;
  font-size: 15px;
  font-family: "SimHei", "黑体", sans-serif;
}

/* === 顶部 Header === */
.fp-header {
  margin-top: 25px;
  margin-bottom: 5px;
}

.header-line {
  line-height: 1.6;
}

.fp-title {
  font-size: 26px;
  font-weight: bold;
  letter-spacing: 12px;
  margin: 0;
  text-align: center;
  font-family: "SimHei", "黑体", sans-serif;
}

/* === 大黑框 === */
.fp-main-box {
  border: 2px solid #000; /* 粗黑外边框 */
  display: flex;
  flex-direction: column;
}

/* 每一行 */
.fp-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: flex-end; /* 底部对齐，让所有字在同一基线上 */
  border-bottom: 1px solid #000;
  padding: 5px 6px 3px 6px; /* 控制行高和留白 */
  min-height: 28px;
  line-height: 1.1;
  box-sizing: border-box;
}

.fp-row > span {
  white-space: nowrap;
  flex-shrink: 0;
}

/* 下划线填空 */
u.fill {
  border-bottom: 1px solid #000;
  text-decoration: none;
  display: inline-block;
  text-align: center;
  margin: 0 2px;
  flex-shrink: 0;
  min-height: 18px;
}

.flex-1 { flex: 1; min-width: 10px; }
.w-8 { width: 32px; }
.w-10 { width: 40px; }
.w-12 { width: 48px; }
.w-16 { width: 64px; }
.w-24 { width: 96px; }
.w-32 { width: 128px; }

/* 费用数字靠右 */
u.fill.cost-val {
  text-align: right;
  padding-right: 4px;
}

/* 方框选择符 (显示数字在里面，或者为空) */
.val-box {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 1px solid #000;
  margin: 0 4px;
  text-align: center;
  line-height: 14px;
  font-size: 12px;
  vertical-align: middle;
  background: transparent;
}

/* 提示文字 */
.hint {
  font-size: 12px;
}

/* 常用留白 */
.ml-2 { margin-left: 8px; }
.ml-4 { margin-left: 16px; }
.ml-8 { margin-left: 32px; }

/* 文本右对齐补充行 */
.text-right-align {
  justify-content: flex-end;
}

/* === 表格 === */
.fp-table {
  border-collapse: collapse;
  table-layout: fixed;
  border-bottom: 1px solid #000;
}

.fp-table th, .fp-table td {
  border: 1px solid #000;
  padding: 3px 4px;
  font-size: 13px;
  line-height: 1.4;
  vertical-align: middle;
}

.fp-table th {
  font-weight: normal;
  text-align: center;
}

.center { text-align: center; }
.mono { font-family: "Courier New", monospace; font-size: 12px; }

.diag-table td { height: 26px; }
.surgery-table td { height: 24px; }


/* 第二页底部说明文字 */
.fp-footer-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
}

@media print {
  .fp-wrapper { padding: 0; background: #fff; }
  .fp-page { box-shadow: none; margin: 0; padding: 20px 0; page-break-after: always; }
}
</style>
