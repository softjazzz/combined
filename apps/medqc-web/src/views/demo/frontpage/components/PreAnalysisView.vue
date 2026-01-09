<template>
  <div class="h-full flex flex-col overflow-y-auto custom-scrollbar">
    <!-- Header -->
    <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-bold text-slate-800 dark:text-white mb-2 flex items-center gap-2">
            <FileSearchOutlined class="text-blue-500" />
            事前分析
          </h2>
          <p class="text-slate-500 dark:text-slate-400 text-sm">
            基于自然语言理解技术的病历信息自动抽取，可实现医生入院记录填写完成后即可自动生成入组结果推荐。
          </p>
        </div>
        <div class="flex items-center gap-3">
          <a-select 
            v-model:value="selectedCaseIndex" 
            placeholder="选择测试病历"
            style="width: 200px"
            @change="handleCaseChange"
          >
            <a-select-option v-for="(tc, idx) in testCases" :key="idx" :value="idx">
              {{ tc.name }}
            </a-select-option>
          </a-select>
          <button 
            @click="handleExtract"
            :disabled="!medicalText || extracting"
            class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <LoadingOutlined v-if="extracting" class="animate-spin" />
            <ThunderboltOutlined v-else />
            {{ extracting ? 'AI抽取中...' : 'AI智能抽取' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6">
      <!-- Left Column: Medical Record Input -->
      <div class="lg:col-span-5 flex flex-col gap-4">
        <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5 flex-1 flex flex-col">
          <h3 class="font-bold text-slate-800 dark:text-white mb-3 flex items-center gap-2">
            <FileTextOutlined class="text-slate-500" />
            病历文本
          </h3>
          <a-textarea
            v-model:value="medicalText"
            placeholder="请输入或粘贴病历文本，或从上方选择测试病历..."
            :rows="12"
            class="flex-1 !bg-slate-50 dark:!bg-slate-700/50 !border-slate-200 dark:!border-slate-600 !resize-none"
          />
        </div>
      </div>

      <!-- Right Column: Results (always visible) -->
      <div class="lg:col-span-7 flex flex-col gap-4">
        <!-- Diagnosis & Surgery Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- Diagnosis Codes -->
          <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5">
            <h3 class="font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
              <MedicineBoxOutlined class="text-blue-500" />
              诊断编码
              <span class="text-xs text-slate-400 font-normal ml-auto">国临版 / 医保版</span>
            </h3>
            <div class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
              <template v-if="hasExtractedData">
                <div v-if="mainDiagnosis" class="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-800">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="bg-blue-500 text-white text-xs px-2 py-0.5 rounded">主诊断</span>
                    <span class="font-mono text-blue-600 dark:text-blue-400 text-xs font-medium">{{ mainDiagnosis.code || '待编码' }}</span>
                    <span v-if="mainDiagnosis.mappedCode && mainDiagnosis.mappedCode !== mainDiagnosis.code" class="font-mono text-green-600 dark:text-green-400 text-xs">→ {{ mainDiagnosis.mappedCode }}</span>
                  </div>
                  <div class="text-slate-700 dark:text-slate-300 text-sm">{{ mainDiagnosis.text }}</div>
                </div>
                <div v-for="(diag, idx) in secondaryDiagnoses" :key="idx" class="p-2 bg-slate-50 dark:bg-slate-700/50 rounded-lg border border-slate-100 dark:border-slate-600">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="font-mono text-slate-500 text-xs">{{ diag.code || '-' }}</span>
                    <span v-if="diag.mappedCode && diag.mappedCode !== diag.code" class="font-mono text-green-600 dark:text-green-400 text-xs">→ {{ diag.mappedCode }}</span>
                    <span class="text-slate-600 dark:text-slate-400 text-sm truncate">{{ diag.text }}</span>
                  </div>
                </div>
                <div v-if="!mainDiagnosis && secondaryDiagnoses.length === 0" class="text-slate-400 text-sm text-center py-4">
                  暂无诊断数据
                </div>
              </template>
              <div v-else class="text-slate-400 text-sm text-center py-6">
                <FileTextOutlined class="text-2xl text-slate-300 mb-2 block" />
                等待AI抽取...
              </div>
            </div>
          </div>

          <!-- Surgery Codes -->
          <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5">
            <h3 class="font-bold text-slate-800 dark:text-white mb-4 flex items-center gap-2">
              <ScissorOutlined class="text-orange-500" />
              手术/操作编码
            </h3>
            <div class="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
              <template v-if="hasExtractedData">
                <div v-for="(proc, idx) in procedures" :key="idx" :class="['p-2 rounded-lg border', idx === 0 ? 'bg-orange-50 dark:bg-orange-900/20 border-orange-100 dark:border-orange-800' : 'bg-slate-50 dark:bg-slate-700/50 border-slate-100 dark:border-slate-600']">
                  <div class="flex items-center gap-2">
                    <span v-if="idx === 0" class="bg-orange-500 text-white text-xs px-1.5 py-0.5 rounded">主</span>
                    <span :class="['font-mono text-xs', idx === 0 ? 'text-orange-600 dark:text-orange-400' : 'text-slate-500']">{{ proc.code || '-' }}</span>
                    <span :class="['text-sm truncate', idx === 0 ? 'text-slate-700 dark:text-slate-300' : 'text-slate-600 dark:text-slate-400']">{{ proc.text }}</span>
                  </div>
                </div>
                <div v-if="procedures.length === 0" class="text-slate-400 text-sm text-center py-4">
                  暂无手术/操作数据
                </div>
              </template>
              <div v-else class="text-slate-400 text-sm text-center py-6">
                <ScissorOutlined class="text-2xl text-slate-300 mb-2 block" />
                等待AI抽取...
              </div>
            </div>
          </div>
        </div>

        <!-- DRG/DIP Grouping Result -->
        <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-5 flex-1">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-bold text-slate-800 dark:text-white flex items-center gap-2">
              <AppstoreOutlined class="text-blue-500" />
              DRG/DIP 入组预测
            </h3>
            <div class="flex items-center gap-2">
              <button 
                @click="handleDIPGrouping"
                :disabled="grouping || !hasExtractedData"
                class="px-3 py-1.5 text-xs bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                <LoadingOutlined v-if="grouping && groupingType === 'DIP'" class="animate-spin" />
                <SyncOutlined v-else />
                泸州市DIP
              </button>
              <button 
                @click="handleDRGGrouping"
                :disabled="grouping || !hasExtractedData"
                class="px-3 py-1.5 text-xs bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 transition-colors flex items-center gap-1"
              >
                <LoadingOutlined v-if="grouping && groupingType === 'DRG'" class="animate-spin" />
                <SyncOutlined v-else />
                四川省DRG
              </button>
            </div>
          </div>

          <!-- Grouping Result Display -->
          <div v-if="drgResult" class="space-y-4">
            <!-- Code Card -->
            <div :class="['rounded-xl p-5 text-white shadow-lg', groupingType === 'DIP' ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-blue-500 to-blue-600']">
              <div class="flex justify-between items-start">
                <div>
                  <div :class="['text-xs font-semibold uppercase tracking-wider mb-1', groupingType === 'DIP' ? 'text-green-100' : 'text-blue-100']">{{ groupingType }} 组编码</div>
                  <div class="text-3xl font-bold font-mono">{{ drgResult.code }}</div>
                  <div class="text-blue-100 mt-2 text-sm">{{ drgResult.name }}</div>
                </div>
                <div class="text-right">
                  <div class="bg-white/20 px-3 py-1 rounded-lg text-sm font-medium">RW: {{ drgResult.weight }}</div>
                </div>
              </div>
            </div>

            <!-- Payment & Profit Cards -->
            <div class="grid grid-cols-3 gap-4">
              <div class="bg-green-50 dark:bg-green-900/20 rounded-xl p-4 border border-green-100 dark:border-green-800">
                <div class="text-green-600 dark:text-green-400 text-xs font-semibold mb-1">预估支付</div>
                <div class="text-xl font-bold text-green-700 dark:text-green-300 font-mono">
                  ¥{{ drgResult.payment?.toLocaleString() }}
                </div>
              </div>
              <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-4 border border-slate-100 dark:border-slate-600">
                <div class="text-slate-500 dark:text-slate-400 text-xs font-semibold mb-1">实际费用</div>
                <div class="text-xl font-bold text-slate-700 dark:text-slate-300 font-mono">
                  ¥{{ drgResult.actual_cost?.toLocaleString() || '-' }}
                </div>
              </div>
              <div :class="['rounded-xl p-4 border', drgResult.profit >= 0 ? 'bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-800']">
                <div :class="['text-xs font-semibold mb-1', drgResult.profit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400']">预估盈亏</div>
                <div :class="['text-xl font-bold font-mono', drgResult.profit >= 0 ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-700 dark:text-red-300']">
                  {{ drgResult.profit >= 0 ? '+' : '' }}¥{{ drgResult.profit?.toLocaleString() }}
                </div>
              </div>
            </div>

            <!-- Messages -->
            <div v-if="drgResult.messages?.length" class="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-4">
              <div class="text-slate-500 text-xs font-semibold mb-2">入组说明</div>
              <ul class="space-y-1">
                <li v-for="(msg, idx) in drgResult.messages" :key="idx" class="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-2">
                  <CheckCircleOutlined class="text-green-500 text-xs" />
                  {{ msg }}
                </li>
              </ul>
            </div>
          </div>

          <!-- No DRG Result - Empty State -->
          <div v-else class="text-center py-8">
            <CalculatorOutlined class="text-4xl text-slate-300 dark:text-slate-600 mb-3" />
            <p class="text-slate-400 text-sm">{{ hasExtractedData ? '点击"重新计算"进行DRG入组预测' : 'AI抽取完成后将自动进行DRG入组预测' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { 
  FileSearchOutlined, 
  FileTextOutlined, 
  MedicineBoxOutlined, 
  ScissorOutlined, 
  AppstoreOutlined,
  CalculatorOutlined,
  SyncOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'

// Test cases
const testCases = [
  {
    name: '高血压合并冠心病',
    medical_text: `入院记录

患者张三，男，58岁，因"反复胸闷、心悸3年，加重1周"于2026年1月1日入院。

现病史：患者3年前开始出现胸闷、心悸症状，活动后加重，休息后可缓解。近1周上述症状加重，夜间阵发性呼吸困难，双下肢轻度水肿。

既往史：高血压病史10年，血压最高180/110mmHg，规律服用降压药物。无糖尿病史。

入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能III级
3. 高血压病3级（极高危）

手术情况：2026年1月3日行冠状动脉造影术+支架植入术。

出院诊断：冠心病、心力衰竭、高血压病3级`
  },
  {
    name: '急性阑尾炎手术',
    medical_text: `入院记录

患者李四，男，32岁，因"转移性右下腹痛6小时"入院。

现病史：6小时前无明显诱因出现脐周疼痛，后转移至右下腹，持续性疼痛，伴恶心、低热。

体格检查：T 37.8℃，右下腹麦氏点压痛、反跳痛阳性。

入院诊断：急性阑尾炎

手术情况：2026年1月2日行腹腔镜阑尾切除术，手术顺利。

出院诊断：急性化脓性阑尾炎`
  },
  {
    name: '肺炎住院治疗',
    medical_text: `入院记录

患者王五，女，65岁，因"咳嗽咳痰伴发热5天"入院。

现病史：5天前受凉后出现咳嗽，咳黄色粘痰，伴发热，体温最高39.2℃。

胸部CT：双下肺感染性病变。

入院诊断：社区获得性肺炎

治疗经过：予头孢曲松抗感染、氨溴索化痰治疗，症状好转。

出院诊断：社区获得性肺炎（双下肺）`
  }
]

// State
const selectedCaseIndex = ref<number | undefined>(undefined)
const medicalText = ref('')
const extracting = ref(false)
const grouping = ref(false)
const extractedData = ref<any>(null)
const drgResult = ref<any>(null)
const admissionId = ref<string | null>(null)
const groupingType = ref<'DIP' | 'DRG'>('DIP')  // 默认使用 DIP
const codeMappings = ref<Record<string, string>>({})  // 国临版 -> 医保版 编码映射

// Computed
const hasExtractedData = computed(() => !!extractedData.value)

const mainDiagnosis = computed(() => {
  if (!extractedData.value?.diagnoses) return null
  const code = extractedData.value.diagnoses.discharge_main_icd || extractedData.value.diagnoses.admission_main_icd
  const text = extractedData.value.diagnoses.discharge_main_diagnosis_text || extractedData.value.diagnoses.admission_main_diagnosis_text
  const mappedCode = codeMappings.value[code] || ''
  return code || text ? { code, text, mappedCode } : null
})

const secondaryDiagnoses = computed(() => {
  if (!extractedData.value?.diagnoses) return []
  const codes = extractedData.value.diagnoses.discharge_other_icds || extractedData.value.diagnoses.admission_other_icds || []
  const texts = extractedData.value.diagnoses.discharge_other_diagnoses_texts || extractedData.value.diagnoses.admission_other_diagnoses_texts || []
  return texts.map((text: string, i: number) => ({
    code: codes[i] || '',
    text,
    mappedCode: codeMappings.value[codes[i]] || ''
  })).slice(0, 5)
})

const procedures = computed(() => {
  // 支持两种数据结构: surgeries (旧) 和 procedures (新)
  const procs = extractedData.value?.procedures || extractedData.value?.surgeries
  if (!procs) return []
  
  // 新格式: procedures.main_procedure_code/main_procedure_text
  const mainCode = procs.main_procedure_code || procs.major_surgery_icd || ''
  const mainText = procs.main_procedure_text || procs.major_surgery_text || ''
  const otherCodes = procs.other_procedure_codes || procs.other_surgery_icds || []
  const otherTexts = procs.other_procedure_texts || procs.other_surgery_texts || []
  
  const result = []
  if (mainText) {
    result.push({ code: mainCode, text: mainText })
  }
  otherTexts.forEach((text: string, i: number) => {
    result.push({ code: otherCodes[i] || '', text })
  })
  return result.slice(0, 5)
})

// Methods
const handleCaseChange = (idx: number) => {
  medicalText.value = testCases[idx].medical_text
  extractedData.value = null
  drgResult.value = null
  admissionId.value = null
}

const handleExtract = async () => {
  if (!medicalText.value.trim()) {
    message.warning('请先输入病历文本')
    return
  }

  extracting.value = true
  try {
    // 使用正确的提取 API
    const response = await fetch('/api/v1/case-front-page/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ medical_text: medicalText.value })
    })

    const data = await response.json()
    if (response.ok && data.success && data.data) {
      extractedData.value = data.data
      // 保存 admission_id 用于 DRG 分组
      admissionId.value = data.data.admission_id
      message.success('AI智能抽取完成')
      // 默认触发 泸州市 DIP 分组
      handleDIPGrouping()
    } else {
      message.error(data.error || data.detail || '抽取失败')
    }
  } catch (error) {
    console.error('Extract error:', error)
    message.error('AI抽取服务暂不可用')
  } finally {
    extracting.value = false
  }
}

const handleDIPGrouping = async () => {
  if (!extractedData.value) {
    message.warning('请先完成AI抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DIP'
  
  try {
    // 从提取数据中获取分组所需信息
    const diagnoses = extractedData.value.diagnoses || {}
    const procedures = extractedData.value.procedures || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}
    
    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = procedures.main_procedure_code || ''
    
    // 计算年龄
    let patientAge = 50
    if (basicInfo.age_years) {
      patientAge = basicInfo.age_years
    }
    
    // 调用 DIP 分组 API
    const response = await fetch('/api/v1/dip/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        city_name: '泸州市',
        pdx_code: primaryDiagCode,
        adx_code: secondaryDiagCodes.length > 0 ? secondaryDiagCodes[0] : '',
        proc_code: mainProcCode,
        patient_gender: basicInfo.gender === '1' ? 'M' : 'F',
        patient_age: patientAge,
        los: 7,
        total_fee: costs.total_cost || 12000
      })
    })

    const data = await response.json()
    if (response.ok && data.data) {
      const actualCost = costs.total_cost || 12000
      
      drgResult.value = {
        code: data.data.dip_code,
        name: data.data.dip_name || data.data.dip_type,
        weight: '--',  // DIP 没有权重概念
        payment: '--',  // DIP 使用分值计算
        actual_cost: actualCost,
        profit: '--',
        messages: data.data.grouping_path ? [data.data.grouping_path] : ['主诊断匹配成功', 'DIP入组完成']
      }
      message.success('泸州市DIP入组预测完成')
    } else {
      message.error(data.detail || 'DIP分组失败')
      drgResult.value = null
    }
  } catch (error) {
    console.error('DIP grouping error:', error)
    message.error('DIP分组服务暂不可用')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}

const handleDRGGrouping = async () => {
  if (!extractedData.value) {
    message.warning('请先完成AI抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DRG'
  
  try {
    // 从提取数据中获取分组所需信息
    const diagnoses = extractedData.value.diagnoses || {}
    const procedures = extractedData.value.procedures || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}
    
    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || 'I10.x00'
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = procedures.main_procedure_code || ''
    const procedureCodes = mainProcCode ? [mainProcCode, ...(procedures.other_procedure_codes || [])] : []
    
    // 使用 predict-realtime 端点直接传入数据
    const response = await fetch('/api/v1/drg/predict-realtime', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        primary_diagnosis_code: primaryDiagCode,
        primary_diagnosis_text: diagnoses.discharge_main_diagnosis_text || '',
        secondary_diagnosis_codes: secondaryDiagCodes,
        procedure_codes: procedureCodes,
        patient_age: basicInfo.age_years || 50,
        patient_gender: basicInfo.gender === '2' ? 'F' : 'M',
        los: 7,
        total_cost: costs.total_cost || 12000,
        region: '四川省'
      })
    })

    const data = await response.json()
    if (response.ok && data.data) {
      const actualCost = costs.total_cost || 12000
      const baselinePayment = data.data.baseline_payment || 0
      
      // 更新编码映射（从 DRG 分组结果中提取）
      if (data.data.original_code && data.data.mapped_code) {
        codeMappings.value[data.data.original_code] = data.data.mapped_code
      }
      
      drgResult.value = {
        code: data.data.drg_code,
        name: data.data.drg_name,
        weight: data.data.weight,
        payment: baselinePayment,
        actual_cost: actualCost,
        profit: baselinePayment - actualCost,
        messages: data.data.grouping_logic ? [data.data.grouping_logic] : ['主诊断匹配成功', 'DRG入组完成']
      }
      message.success('四川省DRG入组预测完成')
    } else {
      message.error(data.detail || 'DRG分组失败')
      drgResult.value = null
    }
  } catch (error) {
    console.error('DRG grouping error:', error)
    message.error('DRG分组服务暂不可用')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
</style>
