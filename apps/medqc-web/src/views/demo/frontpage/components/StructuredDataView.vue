<template>
  <!-- Extracting state -->
  <div v-if="extracting" class="flex flex-col items-center justify-center h-64">
    <a-spin size="large" />
    <p class="mt-4 text-slate-500 dark:text-slate-400">AI 正在从病历原文中提取结构化信息...</p>
  </div>
  <!-- Has frontpage data -->
  <div v-else-if="frontpage" class="space-y-6 pb-10">
    <!-- 1. Basic Info & Hospitalization (Grid) -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <!-- Basic Info -->
      <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
          <UserOutlined class="text-blue-500" /> 患者基本信息
        </h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">姓名</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.patient_name }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">性别</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.gender_text }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">出生日期</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.birth_date }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">年龄</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.age_years }} 岁</div>
          </div>
          <div class="col-span-2">
            <div class="text-xs text-slate-500 dark:text-slate-400">身份证号</div>
            <div class="font-medium font-mono dark:text-slate-200">{{ frontpage.basic_info.id_number }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">籍贯</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.native_place || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">职业</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.job || '-' }}</div>
          </div>
        </div>
      </div>

      <!-- Hospitalization -->
      <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
          <HistoryOutlined class="text-blue-500" /> 住院过程信息
        </h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">入院日期</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.admission_date }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">出院日期</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.discharge_date }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">入院科室</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.admitted_dept }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">出院科室</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.discharged_dept }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">住院天数</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.hospital_days }} 天</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">离院方式</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.leaving_way || '医嘱离院' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Diagnoses (Dynamic: Admission and/or Discharge) -->
    <!-- Admission Diagnosis Table -->
    <div v-if="hasAdmissionDiagnosis" class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
      <div class="bg-blue-50/80 dark:bg-blue-900/20 px-4 py-3 border-b border-blue-100 dark:border-blue-800/30 flex justify-between items-center">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <MedicineBoxOutlined class="text-blue-600" /> 入院诊断
        </h4>
        <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full dark:bg-blue-900 dark:text-blue-300">ICD-10</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
            <tr>
              <th class="px-4 py-3 w-20">类型</th>
              <th class="px-4 py-3 w-32">ICD编码</th>
              <th class="px-4 py-3">诊断名称</th>
              <th class="px-4 py-3 w-24">入院病情</th>
              <th class="px-4 py-3 w-24 text-center">AI置信度</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50">
            <!-- Admission Main Diagnosis -->
            <tr v-if="frontpage.diagnoses.admission_main_diagnosis_text" class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
              <td class="px-4 py-3">
                <span class="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs font-medium dark:bg-blue-900/50 dark:text-blue-300">主要</span>
              </td>
              <td class="px-4 py-3">
                <input 
                  type="text" 
                  :value="frontpage.diagnoses.admission_main_icd || ''"
                  @change="(e) => handleCodeChange('admission_main_icd', (e.target as HTMLInputElement).value)"
                  placeholder="待编码"
                  class="font-mono text-sm w-28 px-2 py-1 border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                />
              </td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">{{ frontpage.diagnoses.admission_main_diagnosis_text }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.diagnoses.admission_main_conn || '-' }}</td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[95%]"></div>
                  </div>
                </div>
              </td>
            </tr>
            <!-- Admission Other Diagnoses -->
            <tr v-for="(diag, idx) in admissionOtherDiagnoses" :key="'adm-' + idx" class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
              <td class="px-4 py-3"><span class="text-slate-400 text-xs">其他</span></td>
              <td class="px-4 py-3 font-mono" :class="isValidIcdCode(diag.code) ? 'text-slate-600 dark:text-slate-300' : 'text-slate-400 dark:text-slate-500 italic'">{{ diag.code || '待编码' }}</td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ diag.name }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ diag.conn || '-' }}</td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[88%]"></div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Discharge Diagnosis Table -->
    <div v-if="hasDischargeDiagnosis" class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
      <div class="bg-green-50/80 dark:bg-green-900/20 px-4 py-3 border-b border-green-100 dark:border-green-800/30 flex justify-between items-center">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <MedicineBoxOutlined class="text-green-600" /> 出院诊断
        </h4>
        <span class="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full dark:bg-green-900 dark:text-green-300">ICD-10</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
            <tr>
              <th class="px-4 py-3 w-20">类型</th>
              <th class="px-4 py-3 w-32">ICD编码</th>
              <th class="px-4 py-3">诊断名称</th>
              <th class="px-4 py-3 w-24">入院病情</th>
              <th class="px-4 py-3 w-24 text-center">AI置信度</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50">
            <!-- Discharge Main Diagnosis -->
            <tr v-if="frontpage.diagnoses.discharge_main_diagnosis_text" class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
              <td class="px-4 py-3">
                <span class="bg-green-100 text-green-700 px-1.5 py-0.5 rounded text-xs font-medium dark:bg-green-900/50 dark:text-green-300">主要</span>
              </td>
              <td class="px-4 py-3">
                <input 
                  type="text" 
                  :value="frontpage.diagnoses.discharge_main_icd || ''"
                  @change="(e) => handleCodeChange('discharge_main_icd', (e.target as HTMLInputElement).value)"
                  placeholder="待编码"
                  class="font-mono text-sm w-28 px-2 py-1 border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
                />
              </td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">{{ frontpage.diagnoses.discharge_main_diagnosis_text }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.diagnoses.discharge_main_conn || '-' }}</td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[95%]"></div>
                  </div>
                </div>
              </td>
            </tr>
            <!-- Discharge Other Diagnoses -->
            <tr v-for="(diag, idx) in dischargeOtherDiagnoses" :key="'dis-' + idx" class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
              <td class="px-4 py-3"><span class="text-slate-400 text-xs">其他</span></td>
              <td class="px-4 py-3 font-mono" :class="isValidIcdCode(diag.code) ? 'text-slate-600 dark:text-slate-300' : 'text-slate-400 dark:text-slate-500 italic'">{{ diag.code || '待编码' }}</td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ diag.name }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ diag.conn || '-' }}</td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[88%]"></div>
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 3. Procedures (Table) -->
    <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
      <div class="bg-orange-50/80 dark:bg-orange-900/20 px-4 py-3 border-b border-orange-100 dark:border-orange-800/30 flex justify-between items-center">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <ScissorOutlined class="text-orange-600" /> 手术操作
        </h4>
        <span class="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full dark:bg-orange-900 dark:text-orange-300">ICD-9-CM-3</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
            <tr>
              <th class="px-4 py-3 w-32">手术编码</th>
              <th class="px-4 py-3">手术名称</th>
              <th class="px-4 py-3 w-32">手术日期</th>
              <th class="px-4 py-3 w-24">术者</th>
              <th class="px-4 py-3 w-24">麻醉方式</th>
              <th class="px-4 py-3 w-24">切口等级</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50">
            <tr v-if="frontpage.procedures.main?.code">
              <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ frontpage.procedures.main.code }}</td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">{{ frontpage.procedures.main.name }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.date }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.surgeon }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.anesthesia || '-' }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.level || '-' }}</td>
            </tr>
            <tr v-for="(proc, idx) in frontpage.procedures.others" :key="idx">
              <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ proc.code }}</td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ proc.name }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ proc.date }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ proc.surgeon }}</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">-</td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">-</td>
            </tr>
            <tr v-if="!frontpage.procedures.main?.code && (!frontpage.procedures.others || frontpage.procedures.others.length === 0)">
              <td colspan="6" class="px-4 py-8 text-center text-slate-400">无手术操作</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 4. Other Medical Info & Staff (Grid) -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <!-- Other Medical Info -->
      <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
          <HeartOutlined class="text-red-500" /> 其他医疗信息
        </h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">药物过敏</div>
            <div class="font-medium dark:text-slate-200">
              <span v-if="frontpage.other_medical_info?.drug_allergy_flag === 1" class="text-green-600">无</span>
              <span v-else-if="frontpage.other_medical_info?.drug_allergy_flag === 2" class="text-red-600">
                有: {{ frontpage.other_medical_info?.drug_allergy_drugs?.join(', ') || '未知' }}
              </span>
              <span v-else>-</span>
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">血型</div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.other_medical_info?.abo_blood_type || '-' }}
              <span v-if="frontpage.other_medical_info?.rh_blood_type_text"> (Rh{{ frontpage.other_medical_info?.rh_blood_type_text }})</span>
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">离院方式</div>
            <div class="font-medium dark:text-slate-200">{{ getDischargeMethodText(frontpage.other_medical_info?.discharge_method) }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">31天再住院计划</div>
            <div class="font-medium dark:text-slate-200">
              <span v-if="frontpage.other_medical_info?.readmission_plan === 1" class="text-orange-600">有</span>
              <span v-else-if="frontpage.other_medical_info?.readmission_plan === 2" class="text-green-600">无</span>
              <span v-else>-</span>
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.pathology_text">
            <div class="text-xs text-slate-500 dark:text-slate-400">病理诊断</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.other_medical_info?.pathology_text }}</div>
          </div>
          <div v-if="frontpage.other_medical_info?.pathology_no">
            <div class="text-xs text-slate-500 dark:text-slate-400">病理号</div>
            <div class="font-medium font-mono dark:text-slate-200">{{ frontpage.other_medical_info?.pathology_no }}</div>
          </div>
        </div>
      </div>

      <!-- Staff Info -->
      <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
        <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
          <TeamOutlined class="text-indigo-500" /> 人员信息
        </h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">科主任</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.dept_director || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">主任/副主任医师</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.chief_physician || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">主治医师</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.attending_physician || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">住院医师</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.resident_physician || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">责任护士</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.responsible_nurse || '-' }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">编码员</div>
            <div class="font-medium dark:text-slate-200">{{ frontpage.staff?.coder || '-' }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 5. Costs Info -->
    <div v-if="frontpage.costs?.total_cost" class="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 rounded-xl p-5 border border-emerald-100 dark:border-emerald-800/30">
      <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
        <DollarOutlined class="text-emerald-600" /> 费用信息
      </h4>
      <div class="flex flex-wrap gap-6">
        <div class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm">
          <div class="text-xs text-slate-500 dark:text-slate-400">住院总费用</div>
          <div class="text-xl font-bold text-emerald-600 dark:text-emerald-400">¥ {{ formatNumber(frontpage.costs?.total_cost) }}</div>
        </div>
        <div v-if="frontpage.costs?.self_paid" class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm">
          <div class="text-xs text-slate-500 dark:text-slate-400">自付金额</div>
          <div class="text-xl font-bold text-orange-600 dark:text-orange-400">¥ {{ formatNumber(frontpage.costs?.self_paid) }}</div>
        </div>
        <div v-if="frontpage.costs?.total_cost && frontpage.costs?.self_paid" class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm">
          <div class="text-xs text-slate-500 dark:text-slate-400">医保支付</div>
          <div class="text-xl font-bold text-blue-600 dark:text-blue-400">¥ {{ formatNumber(frontpage.costs?.total_cost - frontpage.costs?.self_paid) }}</div>
        </div>
      </div>
    </div>
  </div>
  <!-- Empty state: needs extraction -->
  <div v-else class="h-full flex flex-col items-center justify-start text-center p-6 pt-4">
    <div class="w-20 h-20 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-2xl mb-5 flex items-center justify-center">
      <RobotOutlined class="text-4xl text-blue-500" />
    </div>
    <h3 class="text-lg font-semibold text-slate-800 dark:text-white mb-2">AI 结构化提取</h3>
    <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">从病历原文中自动识别患者信息、诊断、手术操作，并映射到 ICD 标准编码。</p>
    <button
      @click="$emit('extract')"
      :disabled="!hasMedicalText"
      class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl text-sm font-medium transition-all shadow-lg shadow-blue-500/25 flex items-center gap-2"
    >
      <ThunderboltOutlined />
      开始 AI 提取
    </button>
    <p v-if="!hasMedicalText" class="text-xs text-orange-500 mt-3">请先在左侧加载病历原文</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { HistoryOutlined, MedicineBoxOutlined, RobotOutlined, ScissorOutlined, ThunderboltOutlined, UserOutlined, HeartOutlined, TeamOutlined, DollarOutlined } from '@ant-design/icons-vue'

const props = defineProps<{
  extracting: boolean
  frontpage: any | null
  hasMedicalText: boolean
}>()

const emit = defineEmits<{
  (e: 'extract'): void
  (e: 'codeChange', field: string, value: string): void
}>()

// 处理编码变更
const handleCodeChange = (field: string, value: string) => {
  emit('codeChange', field, value)
}

// 格式化数字
const formatNumber = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return '-'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 离院方式映射
const getDischargeMethodText = (code: number | null | undefined): string => {
  const map: Record<number, string> = {
    1: '医嘱离院',
    2: '医嘱转院',
    3: '医嘱转社区',
    4: '非医嘱离院',
    5: '死亡',
    9: '其他'
  }
  return code ? map[code] || '-' : '-'
}

// 检查是否有入院诊断
const hasAdmissionDiagnosis = computed(() => {
  if (!props.frontpage?.diagnoses) return false
  return !!(
    props.frontpage.diagnoses.admission_main_diagnosis_text ||
    (props.frontpage.diagnoses.admission_other_diagnoses_texts?.length > 0)
  )
})

// 检查是否有出院诊断
const hasDischargeDiagnosis = computed(() => {
  if (!props.frontpage?.diagnoses) return false
  return !!(
    props.frontpage.diagnoses.discharge_main_diagnosis_text ||
    (props.frontpage.diagnoses.discharge_other_diagnoses_texts?.length > 0)
  )
})

// 格式化入院其他诊断（合并名称和编码）
const admissionOtherDiagnoses = computed(() => {
  if (!props.frontpage?.diagnoses) return []
  const texts = props.frontpage.diagnoses.admission_other_diagnoses_texts || []
  const codes = props.frontpage.diagnoses.admission_other_icds || []
  
  return texts.map((name: string, index: number) => ({
    name,
    code: codes[index] || '待编码',
    conn: null
  }))
})

// 格式化出院其他诊断（合并名称和编码）
const dischargeOtherDiagnoses = computed(() => {
  if (!props.frontpage?.diagnoses) return []
  const texts = props.frontpage.diagnoses.discharge_other_diagnoses_texts || []
  const codes = props.frontpage.diagnoses.discharge_other_icds || []
  
  return texts.map((name: string, index: number) => ({
    name,
    code: codes[index] || '待编码',
    conn: null
  }))
})

// 验证 ICD 编码是否有效（不是待编码状态）
const isValidIcdCode = (code: string | null | undefined): boolean => {
  if (!code) return false
  if (code === '待编码' || code === '待人工编码') return false
  return true
}
</script>
