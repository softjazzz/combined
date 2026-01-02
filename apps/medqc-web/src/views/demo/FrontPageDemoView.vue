<template>
  <div class="frontpage-demo page-container min-h-screen bg-gray-50 p-2 lg:p-3">
    <a-card class="mb-3" :bordered="false">
      <template #title>
        <div class="flex items-center gap-3">
          <div class="p-2 bg-blue-100 rounded-md">
            <FileTextOutlined class="text-lg text-blue-600" />
          </div>
          <div>
            <h1 class="text-lg font-semibold text-gray-900">病案首页 & 医保清单自动生成 Demo</h1>
            <p class="text-xs text-gray-500">
              基于模拟病案全文，演示自动生成住院病案首页和医保结算清单的结构化结果（静态示例，不调用真实 LLM）。
            </p>
          </div>
        </div>
      </template>

      <a-row :gutter="16">
        <!-- 左侧：病历文本 -->
        <a-col :xs="24" :lg="12">
          <a-card size="small" title="模拟病历全文" :loading="loading">
            <a-alert
              v-if="demoCase?.description"
              type="info"
              :message="demoCase.description"
              show-icon
              class="mb-2"
            />
            <a-skeleton v-if="loading" active :paragraph="{ rows: 8 }" />
            <div v-else class="medical-text">
              <pre v-if="demoCase?.medical_text">{{ demoCase.medical_text }}</pre>
              <pre v-else>（当前为 Demo 模式，病历全文由后端示例数据生成。后续将从真实病历文书自动抽取并在此展示。）</pre>
            </div>
          </a-card>
        </a-col>

        <!-- 右侧：自动生成结果 -->
        <a-col :xs="24" :lg="12">
          <a-card size="small" title="自动生成的病案首页与医保清单" :loading="loading">
            <a-tabs size="small">
              <a-tab-pane key="frontpage" tab="病案首页">
                <div v-if="frontpage">
                  <a-descriptions
                    title="一、患者基本信息"
                    :column="1"
                    size="small"
                    bordered
                    class="mb-3"
                  >
                    <a-descriptions-item label="姓名">{{ frontpage.basic_info.patient_name }}</a-descriptions-item>
                    <a-descriptions-item label="性别">{{ frontpage.basic_info.gender_text }}</a-descriptions-item>
                    <a-descriptions-item label="出生日期">{{ frontpage.basic_info.birth_date }}</a-descriptions-item>
                    <a-descriptions-item label="年龄">{{ frontpage.basic_info.age_years }} 岁</a-descriptions-item>
                    <a-descriptions-item label="身份证号">{{ frontpage.basic_info.id_number }}</a-descriptions-item>
                    <a-descriptions-item label="婚姻">{{ frontpage.basic_info.marital_status_text }}</a-descriptions-item>
                    <a-descriptions-item label="现住址">{{ frontpage.basic_info.current_address }}</a-descriptions-item>
                    <a-descriptions-item label="联系人">{{ frontpage.basic_info.contact_name }}（{{ frontpage.basic_info.contact_relation }}）</a-descriptions-item>
                    <a-descriptions-item label="联系电话">{{ frontpage.basic_info.contact_phone }}</a-descriptions-item>
                  </a-descriptions>

                  <a-descriptions
                    title="二、住院相关信息"
                    :column="1"
                    size="small"
                    bordered
                    class="mb-3"
                  >
                    <a-descriptions-item label="医院">{{ frontpage.hospitalization.hospital_name }}</a-descriptions-item>
                    <a-descriptions-item label="病案号">{{ frontpage.hospitalization.medical_record_no }}</a-descriptions-item>
                    <a-descriptions-item label="付费方式">{{ frontpage.hospitalization.payment_method_text }}</a-descriptions-item>
                    <a-descriptions-item label="入院科别">{{ frontpage.hospitalization.admission_dept }}</a-descriptions-item>
                    <a-descriptions-item label="出院科别">{{ frontpage.hospitalization.discharge_dept }}</a-descriptions-item>
                    <a-descriptions-item label="入院时间">{{ frontpage.hospitalization.admission_datetime }}</a-descriptions-item>
                    <a-descriptions-item label="出院时间">{{ frontpage.hospitalization.discharge_datetime }}</a-descriptions-item>
                    <a-descriptions-item label="实际住院日">{{ frontpage.hospitalization.actual_hospital_days }} 天</a-descriptions-item>
                  </a-descriptions>

                  <a-descriptions
                    title="三、诊断及手术操作"
                    :column="1"
                    size="small"
                    bordered
                    class="mb-3"
                  >
                    <a-descriptions-item label="门/急诊诊断">
                      <div v-for="(text, idx) in frontpage.diagnoses.ed_diagnosis_texts" :key="idx">
                        {{ text }}
                      </div>
                    </a-descriptions-item>
                    <a-descriptions-item label="出院主要诊断">
                      {{ frontpage.diagnoses.discharge_main_diagnosis_text || ' ' }}
                    </a-descriptions-item>
                    <a-descriptions-item label="入院病情">
                      {{ frontpage.diagnoses.admission_condition || ' ' }}
                    </a-descriptions-item>
                    <a-descriptions-item label="主要手术">
                      {{ frontpage.procedures.main_procedure_date }}：
                      {{ frontpage.procedures.main_procedure_text }}
                    </a-descriptions-item>
                    <a-descriptions-item label="术者/助手">
                      术者：{{ frontpage.procedures.surgeon_name || ' ' }}；
                      I 助：{{ frontpage.procedures.assistant1_name || ' ' }}；
                      II 助：{{ frontpage.procedures.assistant2_name || ' ' }}
                    </a-descriptions-item>
                    <a-descriptions-item label="麻醉/切口">
                      麻醉方式：{{ frontpage.procedures.anesthesia_method || ' ' }}；
                      麻醉医师：{{ frontpage.procedures.anesthetist_name || ' ' }}；
                      切口愈合等级：{{ frontpage.procedures.incision_healing_grade || ' ' }}
                    </a-descriptions-item>
                  </a-descriptions>

                  <a-descriptions
                    title="四、其他住院医疗信息"
                    :column="1"
                    size="small"
                    bordered
                    class="mb-3"
                  >
                    <a-descriptions-item label="病理诊断">
                      {{ frontpage.other_medical_info.pathology_text || ' ' }}
                      <template v-if="frontpage.other_medical_info.pathology_no">
                        （病理号：{{ frontpage.other_medical_info.pathology_no }}）
                      </template>
                    </a-descriptions-item>
                    <a-descriptions-item label="药物过敏">无</a-descriptions-item>
                    <a-descriptions-item label="血型">
                      ABO：{{ frontpage.other_medical_info.abo_blood_type || ' ' }}；
                      Rh：{{ frontpage.other_medical_info.rh_blood_type_text || ' ' }}
                    </a-descriptions-item>
                    <a-descriptions-item label="呼吸机使用时间">
                      机械通气 {{ frontpage.other_medical_info.ventilation_hours ?? '' }} 小时
                    </a-descriptions-item>
                    <a-descriptions-item label="ICU 情况">
                      {{ frontpage.other_medical_info.icu_type || ' ' }}，
                      {{ frontpage.other_medical_info.icu_enter_time || ' ' }} 入，
                      {{ frontpage.other_medical_info.icu_leave_time || ' ' }} 出
                    </a-descriptions-item>
                  </a-descriptions>

                  <a-descriptions
                    title="五、人员信息"
                    :column="1"
                    size="small"
                    bordered
                    class="mb-3"
                  >
                    <a-descriptions-item label="科主任">{{ frontpage.staff.dept_director }}</a-descriptions-item>
                    <a-descriptions-item label="主任医师">{{ frontpage.staff.chief_physician }}</a-descriptions-item>
                    <a-descriptions-item label="主治医师">{{ frontpage.staff.attending_physician }}</a-descriptions-item>
                    <a-descriptions-item label="住院医师">{{ frontpage.staff.resident_physician }}</a-descriptions-item>
                    <a-descriptions-item label="责任护士">{{ frontpage.staff.responsible_nurse }}</a-descriptions-item>
                    <a-descriptions-item label="编码员">{{ frontpage.staff.coder }}</a-descriptions-item>
                  </a-descriptions>
                </div>
                <a-empty v-else description="暂无首页数据" />
              </a-tab-pane>

              <a-tab-pane key="insurance" tab="医保结算清单">
                <div v-if="insuranceClaim">
                  <a-descriptions :column="1" size="small" bordered>
                    <a-descriptions-item label="结算单号">{{ insuranceClaim.settlement_id }}</a-descriptions-item>
                    <a-descriptions-item label="医保类型">{{ insuranceClaim.insurance_type }}</a-descriptions-item>
                    <a-descriptions-item label="总费用">{{ insuranceClaim.total_cost }} 元</a-descriptions-item>
                    <a-descriptions-item label="基金支付">{{ insuranceClaim.fund_pay }} 元</a-descriptions-item>
                    <a-descriptions-item label="个人自付">{{ insuranceClaim.patient_pay }} 元</a-descriptions-item>
                    <a-descriptions-item label="药品费用">{{ insuranceClaim.drug_cost }} 元</a-descriptions-item>
                    <a-descriptions-item label="治疗费用">{{ insuranceClaim.treatment_cost }} 元</a-descriptions-item>
                    <a-descriptions-item label="耗材费用">{{ insuranceClaim.material_cost }} 元</a-descriptions-item>
                    <a-descriptions-item label="其他费用">{{ insuranceClaim.other_cost }} 元</a-descriptions-item>
                  </a-descriptions>
                </div>
                <a-empty v-else description="暂无清单数据" />
              </a-tab-pane>
              <a-tab-pane key="print" tab="首页打印版">
                <div v-if="frontpage" class="frontpage-print-container">
                  <!-- 页面 1 -->
                  <div class="frontpage-a4">
                    <div class="frontpage-header">
                      <div class="header-left">附件 1</div>
                      <div class="header-center">
                        <div class="line">
                          <span class="label">医疗机构</span>
                          <span class="underline wide">{{ frontpage.hospitalization.hospital_name || ' ' }}</span>
                          <span class="label" style="margin-left: 24px;">（组织机构代码：</span>
                          <span class="underline short"></span>
                          <span>）</span>
                        </div>
                        <div class="title">住 院 病 案 首 页</div>
                      </div>
                    </div>

                    <div class="frontpage-body">
                      <div class="row">
                        <span class="label">医疗付费方式：</span>
                        <span class="underline mid">{{ frontpage.hospitalization.payment_method_text || ' ' }}</span>
                        <span class="label" style="margin-left: 24px;">健康卡号：</span>
                        <span class="underline long"></span>
                        <span class="label" style="margin-left: 24px;">第</span>
                        <span class="underline tiny">{{ frontpage.hospitalization.admission_times_in_hospital || 1 }}</span>
                        <span class="label">次住院</span>
                        <span class="label" style="margin-left: 24px;">病案号：</span>
                        <span class="underline mid">{{ frontpage.hospitalization.medical_record_no || ' ' }}</span>
                      </div>

                      <div class="row">
                        <span class="label">姓名</span>
                        <span class="underline mid">{{ frontpage.basic_info.patient_name }}</span>
                        <span class="label">性别 □ 1.男 2.女</span>
                        <span class="underline tiny">{{ frontpage.basic_info.gender_text }}</span>
                        <span class="label">出生日期</span>
                        <span class="underline mid">{{ frontpage.basic_info.birth_date }}</span>
                        <span class="label">年龄</span>
                        <span class="underline tiny">{{ frontpage.basic_info.age_years }}</span>
                        <span class="label">国籍</span>
                        <span class="underline tiny">{{ frontpage.basic_info.nationality || ' ' }}</span>
                      </div>

                      <div class="row">
                        <span class="label">身份证号</span>
                        <span class="underline wide">{{ frontpage.basic_info.id_number }}</span>
                        <span class="label">职业</span>
                        <span class="underline mid">{{ frontpage.basic_info.occupation || ' ' }}</span>
                        <span class="label">婚姻 □1.未婚 2.已婚 3.丧偶 4.离婚 9.其他</span>
                        <span class="underline tiny">{{ frontpage.basic_info.marital_status_text }}</span>
                      </div>

                      <div class="row">
                        <span class="label">现住址</span>
                        <span class="underline long">{{ frontpage.basic_info.current_address }}</span>
                        <span class="label">电话</span>
                        <span class="underline mid">{{ frontpage.basic_info.contact_phone }}</span>
                      </div>

                      <div class="row">
                        <span class="label">联系人姓名</span>
                        <span class="underline mid">{{ frontpage.basic_info.contact_name }}</span>
                        <span class="label">关系</span>
                        <span class="underline tiny">{{ frontpage.basic_info.contact_relation }}</span>
                        <span class="label">地址</span>
                        <span class="underline long"></span>
                        <span class="label">电话</span>
                        <span class="underline mid">{{ frontpage.basic_info.contact_phone }}</span>
                      </div>

                      <div class="row">
                        <span class="label">入院途径 □ 1.急诊 2.门诊 3.其他医疗机构转入 9.其他</span>
                        <span class="underline tiny"></span>
                      </div>

                      <div class="row">
                        <span class="label">入院时间</span>
                        <span class="underline mid">{{ frontpage.hospitalization.admission_datetime }}</span>
                        <span class="label">入院科别</span>
                        <span class="underline mid">{{ frontpage.hospitalization.admission_dept }}</span>
                        <span class="label">病房</span>
                        <span class="underline tiny">{{ frontpage.hospitalization.admission_ward || ' ' }}</span>
                      </div>

                      <div class="row">
                        <span class="label">出院时间</span>
                        <span class="underline mid">{{ frontpage.hospitalization.discharge_datetime }}</span>
                        <span class="label">出院科别</span>
                        <span class="underline mid">{{ frontpage.hospitalization.discharge_dept }}</span>
                        <span class="label">病房</span>
                        <span class="underline tiny">{{ frontpage.hospitalization.discharge_ward || ' ' }}</span>
                        <span class="label">实际住院</span>
                        <span class="underline tiny">{{ frontpage.hospitalization.actual_hospital_days }}</span>
                        <span class="label">天</span>
                      </div>

                      <!-- 诊断表格 -->
                      <table class="diag-table">
                        <thead>
                          <tr>
                            <th class="col-name">出院诊断</th>
                            <th class="col-code">疾病编码</th>
                            <th class="col-condition">入院病情</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td class="cell-left">主要诊断：{{ frontpage.diagnoses.discharge_main_diagnosis_text || ' ' }}</td>
                            <td>{{ frontpage.diagnoses.discharge_main_icd || '' }}</td>
                            <td>{{ frontpage.diagnoses.admission_condition || '' }}</td>
                          </tr>
                          <tr v-for="(text, idx) in frontpage.diagnoses.discharge_other_diagnoses_texts || []" :key="idx">
                            <td class="cell-left">其他诊断：{{ text }}</td>
                            <td></td>
                            <td></td>
                          </tr>
                          <tr v-for="i in 4" :key="'empty-' + i">
                            <td class="cell-left">&nbsp;</td>
                            <td></td>
                            <td></td>
                          </tr>
                        </tbody>
                      </table>

                      <div class="row mt-2">
                        <span class="label">病理诊断：</span>
                        <span class="underline long">
                          {{ frontpage.other_medical_info.pathology_text || ' ' }}
                          <template v-if="frontpage.other_medical_info.pathology_no">
                            （病理号：{{ frontpage.other_medical_info.pathology_no }}）
                          </template>
                        </span>
                      </div>

                      <div class="row">
                        <span class="label">药物过敏 □1.无 2.有，过敏药物：</span>
                        <span class="underline long"></span>
                      </div>

                      <div class="row">
                        <span class="label">血型 □ 1.A 2.B 3.O 4.AB 5.不详 6.未查</span>
                        <span class="label" style="margin-left: 24px;">Rh □ 1.阴 2.阳 3.不详 4.未查</span>
                      </div>

                      <div class="row mt-4">
                        <span class="label">科主任</span>
                        <span class="underline tiny">{{ frontpage.staff.dept_director }}</span>
                        <span class="label">主任（副主任）医师</span>
                        <span class="underline tiny">{{ frontpage.staff.chief_physician }}</span>
                        <span class="label">主治医师</span>
                        <span class="underline tiny">{{ frontpage.staff.attending_physician }}</span>
                        <span class="label">住院医师</span>
                        <span class="underline tiny">{{ frontpage.staff.resident_physician }}</span>
                      </div>

                      <div class="row mt-1">
                        <span class="label">责任护士</span>
                        <span class="underline tiny">{{ frontpage.staff.responsible_nurse }}</span>
                        <span class="label">编码员</span>
                        <span class="underline tiny">{{ frontpage.staff.coder }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- 页面 2：手术及费用，做简化展示 -->
                  <div class="frontpage-a4 mt-4">
                    <table class="surgery-table">
                      <thead>
                        <tr>
                          <th>手术及<br>操作编码</th>
                          <th>手术及<br>操作日期</th>
                          <th>手术<br>级别</th>
                          <th>手术及操作名称</th>
                          <th colspan="3">手术及操作医师</th>
                          <th>切口愈<br>合等级</th>
                          <th>麻醉方式</th>
                          <th>麻醉医师</th>
                        </tr>
                        <tr>
                          <th></th><th></th><th></th><th></th>
                          <th>术者</th><th>I 助</th><th>II 助</th>
                          <th></th><th></th><th></th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>{{ frontpage.procedures.main_procedure_code || '' }}</td>
                          <td>{{ frontpage.procedures.main_procedure_date || '' }}</td>
                          <td>{{ frontpage.procedures.main_procedure_level || '' }}</td>
                          <td class="cell-left">{{ frontpage.procedures.main_procedure_text || '' }}</td>
                          <td>{{ frontpage.procedures.surgeon_name || '' }}</td>
                          <td>{{ frontpage.procedures.assistant1_name || '' }}</td>
                          <td>{{ frontpage.procedures.assistant2_name || '' }}</td>
                          <td>{{ frontpage.procedures.incision_healing_grade || '' }}</td>
                          <td>{{ frontpage.procedures.anesthesia_method || '' }}</td>
                          <td>{{ frontpage.procedures.anesthetist_name || '' }}</td>
                        </tr>
                        <tr v-for="i in 4" :key="'proc-empty-' + i">
                          <td colspan="10">&nbsp;</td>
                        </tr>
                      </tbody>
                    </table>

                    <div class="row mt-2">
                      <span class="label">住院费用（元）：总费用</span>
                      <span class="underline mid">{{ frontpage.costs.total_cost }}</span>
                      <span class="label">（自付金额：</span>
                      <span class="underline mid">{{ frontpage.costs.self_paid }}</span>
                      <span>）</span>
                    </div>

                    <!-- 费用分类，这里仅展示几项示例 -->
                    <div class="row mt-1">
                      <span class="label">1.综合医疗服务类：</span>
                      <span class="label">（1）一般医疗服务费：</span>
                      <span class="underline tiny">{{ frontpage.costs.categories['1'] || '' }}</span>
                      <span class="label" style="margin-left: 8px;">（3）护理费：</span>
                      <span class="underline tiny">{{ frontpage.costs.categories['3'] || '' }}</span>
                    </div>
                    <div class="row mt-1">
                      <span class="label">2.诊断类：（6）实验室诊断费：</span>
                      <span class="underline tiny">{{ frontpage.costs.categories['6'] || '' }}</span>
                      <span class="label" style="margin-left: 8px;">（7）影像学诊断费：</span>
                      <span class="underline tiny">{{ frontpage.costs.categories['7'] || '' }}</span>
                    </div>
                    <div class="row mt-1">
                      <span class="label">6.西药类：</span>
                      <span class="underline tiny">{{ frontpage.costs.categories['13'] || '' }}</span>
                      <span class="label" style="margin-left: 8px;">（抗菌药物费用：</span>
                      <span class="underline tiny"></span>
                      <span>）</span>
                    </div>
                  </div>
                </div>
                <a-empty v-else description="暂无首页数据" />
              </a-tab-pane>
              <a-tab-pane key="hm" tab="HM 模板版">
                <HmFrontpagePreview :draft="frontpage" />
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </a-col>
      </a-row>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import HmFrontpagePreview from '@/components/frontpage/HmFrontpagePreview.vue'

interface DemoCase {
  case_id: string
  description?: string
  medical_text?: string
  frontpage?: any
  insurance_claim?: any
}

const loading = ref(false)
const demoCase = ref<DemoCase | null>(null)

const frontpage = computed(() => demoCase.value?.frontpage || null)
const insuranceClaim = computed(() => demoCase.value?.insurance_claim || null)

const loadDemoCase = async () => {
  loading.value = true
  try {
    // 1) 调用新的首页自动生成接口，获取结构化 frontpage 草稿
    const fpResp = await fetch('/api/v1/frontpage/auto-generate-draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ visit_id: 'demo' })
    })
    const fpData = await fpResp.json()
    if (!fpResp.ok || fpData.success === false) {
      throw new Error(fpData?.message || fpData?.error || '自动生成病案首页失败')
    }

    const frontpageDraft = fpData.data?.frontpage

    // 2) 为了展示“病历全文”，继续复用原来的 demo 接口（只要拿 medical_text 即可）
    let medicalText: string | undefined
    let description: string | undefined
    try {
      const demoResp = await fetch('/api/v1/demo/frontpage-demo')
      const demoData = await demoResp.json()
      if (demoResp.ok && demoData.success !== false) {
        medicalText = demoData.data?.medical_text
        description = demoData.data?.description
      }
    } catch {
      // 忽略 demo 接口错误，仅影响左侧病历文本展示
    }

    demoCase.value = {
      case_id: 'demo_case_from_api',
      description,
      medical_text: medicalText,
      frontpage: frontpageDraft,
      insurance_claim: null
    }
  } catch (error: any) {
    console.error('加载病案首页草稿失败:', error)
    message.error(error?.message || '加载病案首页草稿失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadDemoCase()
})
</script>

<style scoped>
.medical-text {
  max-height: 520px;
  overflow: auto;
  background: #f9fafb;
  border-radius: 4px;
  padding: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.medical-text pre {
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.frontpage-print-container {
  max-height: 520px;
  overflow: auto;
  padding: 4px;
  background: #f9fafb;
}

.frontpage-a4 {
  width: 794px; /* 96dpi 下接近 A4 宽度 */
  min-height: 1123px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid #d4d4d4;
  padding: 16px 24px;
  box-sizing: border-box;
  font-size: 12px;
  line-height: 1.4;
  color: #000;
}

.frontpage-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}

.header-left {
  font-size: 12px;
}

.header-center {
  flex: 1;
  text-align: center;
}

.header-center .line {
  font-size: 12px;
  text-align: left;
}

.header-center .title {
  font-size: 18px;
  font-weight: 600;
  margin-top: 4px;
}

.frontpage-body {
  margin-top: 4px;
}

.frontpage-body .row {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.frontpage-body .label {
  font-size: 12px;
  white-space: nowrap;
}

.underline {
  border-bottom: 1px solid #000;
  min-height: 16px;
  padding: 0 2px;
  font-size: 12px;
}

.underline.tiny {
  min-width: 40px;
}
.underline.mid {
  min-width: 80px;
}
.underline.wide {
  min-width: 160px;
}
.underline.long {
  flex: 1;
}
.underline.short {
  min-width: 80px;
}

.diag-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
  font-size: 12px;
}

.diag-table th,
.diag-table td {
  border: 1px solid #000;
  padding: 2px 4px;
  text-align: center;
}

.diag-table .col-name {
  width: 60%;
}

.diag-table .cell-left {
  text-align: left;
}

.surgery-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.surgery-table th,
.surgery-table td {
  border: 1px solid #000;
  padding: 2px 4px;
  text-align: center;
}

.surgery-table .cell-left {
  text-align: left;
}
</style>
