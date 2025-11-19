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
              <pre>{{ demoCase?.medical_text }}</pre>
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
                      <div v-for="d in frontpage.diagnosis_and_procedures.ed_diagnosis" :key="d.text">
                        {{ d.text }}（ICD-10: {{ d.icd10 }}）
                      </div>
                    </a-descriptions-item>
                    <a-descriptions-item label="出院主要诊断">
                      {{ frontpage.diagnosis_and_procedures.discharge_main_diagnosis.text }}
                      （ICD-10: {{ frontpage.diagnosis_and_procedures.discharge_main_diagnosis.icd10 }}）
                    </a-descriptions-item>
                    <a-descriptions-item label="入院病情">
                      {{ frontpage.diagnosis_and_procedures.discharge_main_diagnosis.admission_condition_text }}
                    </a-descriptions-item>
                    <a-descriptions-item label="主要手术">
                      {{ frontpage.diagnosis_and_procedures.main_procedure.date }}：
                      {{ frontpage.diagnosis_and_procedures.main_procedure.name }}
                      （编码：{{ frontpage.diagnosis_and_procedures.main_procedure.code }}）
                    </a-descriptions-item>
                    <a-descriptions-item label="术者/助手">
                      术者：{{ frontpage.diagnosis_and_procedures.main_procedure.surgeon_name }}
                      （{{ frontpage.diagnosis_and_procedures.main_procedure.surgeon_code }}）；
                      I 助：{{ frontpage.diagnosis_and_procedures.main_procedure.assistant1_name }}；
                      II 助：{{ frontpage.diagnosis_and_procedures.main_procedure.assistant2_name }}
                    </a-descriptions-item>
                    <a-descriptions-item label="麻醉/切口">
                      麻醉方式：{{ frontpage.diagnosis_and_procedures.main_procedure.anesthesia_method }}；
                      麻醉医师：{{ frontpage.diagnosis_and_procedures.main_procedure.anesthetist_name }}；
                      切口愈合等级：{{ frontpage.diagnosis_and_procedures.main_procedure.incision_healing_grade }}
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
                      {{ frontpage.other_medical_info.pathology_diagnosis.text }}
                      （病理号：{{ frontpage.other_medical_info.pathology_diagnosis.pathology_no }}）
                    </a-descriptions-item>
                    <a-descriptions-item label="药物过敏">无</a-descriptions-item>
                    <a-descriptions-item label="血型">
                      ABO：{{ frontpage.other_medical_info.abo_blood_type }}；
                      Rh：{{ frontpage.other_medical_info.rh_blood_type_text }}
                    </a-descriptions-item>
                    <a-descriptions-item label="呼吸机使用时间">
                      机械通气 {{ frontpage.other_medical_info.ventilation_hours }} 小时
                    </a-descriptions-item>
                    <a-descriptions-item label="ICU 情况">
                      {{ frontpage.other_medical_info.icu_stay.icu_type }}，
                      {{ frontpage.other_medical_info.icu_stay.enter_time }} 入，
                      {{ frontpage.other_medical_info.icu_stay.leave_time }} 出
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
            </a-tabs>
          </a-card>
        </a-col>
      </a-row>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { FileTextOutlined } from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

interface DemoCase {
  case_id: string
  description?: string
  medical_text: string
  frontpage: any
  insurance_claim: any
}

const loading = ref(false)
const demoCase = ref<DemoCase | null>(null)

const frontpage = computed(() => demoCase.value?.frontpage || null)
const insuranceClaim = computed(() => demoCase.value?.insurance_claim || null)

const loadDemoCase = async () => {
  loading.value = true
  try {
    const resp = await fetch('/api/v1/demo/frontpage-demo')
    const data = await resp.json()
    if (!resp.ok || data.success === false) {
      throw new Error(data?.message || data?.error || '加载 Demo 数据失败')
    }
    demoCase.value = data.data as DemoCase
  } catch (error: any) {
    console.error('加载病案首页 Demo 数据失败:', error)
    message.error(error?.message || '加载 Demo 数据失败')
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
</style>

