<template>
  <a-modal
    v-model:open="visible"
    :title="isEdit ? '编辑病历' : '新建病历'"
    width="800px"
    :confirm-loading="loading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
      class="medical-record-form"
    >
      <!-- 患者基本信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">患者基本信息</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="患者姓名" name="patient_name">
              <a-input v-model:value="formData.patient_name" placeholder="请输入患者姓名" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="年龄" name="patient_age">
              <a-input-number 
                v-model:value="formData.patient_age" 
                :min="0" 
                :max="150" 
                placeholder="年龄"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="性别" name="patient_gender">
              <a-select v-model:value="formData.patient_gender" placeholder="选择性别">
                <a-select-option value="M">男</a-select-option>
                <a-select-option value="F">女</a-select-option>
                <a-select-option value="U">未知</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="身份证号" name="patient_id_card">
              <a-input v-model:value="formData.patient_id_card" placeholder="请输入身份证号" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="医保号" name="insurance_number">
              <a-input v-model:value="formData.insurance_number" placeholder="请输入医保号" />
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 医疗信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">医疗信息</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="科室" name="department">
              <a-select v-model:value="formData.department" placeholder="选择科室">
                <a-select-option v-for="dept in DEPARTMENTS" :key="dept" :value="dept">
                  {{ dept }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="主治医生" name="doctor_name">
              <a-input v-model:value="formData.doctor_name" placeholder="请输入主治医生" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="记录类型" name="record_type">
              <a-select v-model:value="formData.record_type" placeholder="选择记录类型">
                <a-select-option v-for="type in RECORD_TYPES" :key="type.value" :value="type.value">
                  {{ type.label }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="入院日期" name="admission_date">
              <a-date-picker 
                v-model:value="formData.admission_date" 
                style="width: 100%"
                placeholder="选择入院日期"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="出院日期" name="discharge_date">
              <a-date-picker 
                v-model:value="formData.discharge_date" 
                style="width: 100%"
                placeholder="选择出院日期"
              />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="医保类型" name="insurance_type">
              <a-select v-model:value="formData.insurance_type" placeholder="选择医保类型">
                <a-select-option v-for="type in INSURANCE_TYPES" :key="type.value" :value="type.value">
                  {{ type.label }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 诊断信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">诊断信息</h3>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="主要诊断" name="diagnosis_primary">
              <a-input v-model:value="formData.diagnosis_primary" placeholder="请输入主要诊断" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="次要诊断" name="diagnosis_secondary">
              <a-select
                v-model:value="formData.diagnosis_secondary"
                mode="tags"
                placeholder="请输入次要诊断（可多个）"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 费用信息 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">费用信息</h3>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-form-item label="总费用" name="total_cost">
              <a-input-number
                v-model:value="formData.total_cost"
                :min="0"
                :precision="2"
                placeholder="总费用"
                style="width: 100%"
                @change="calculateCosts"
              >
                <template #addonBefore>¥</template>
              </a-input-number>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="医保支付" name="insurance_cost">
              <a-input-number
                v-model:value="formData.insurance_cost"
                :min="0"
                :max="formData.total_cost"
                :precision="2"
                placeholder="医保支付"
                style="width: 100%"
                @change="calculateSelfPay"
              >
                <template #addonBefore>¥</template>
              </a-input-number>
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="自费金额" name="self_pay_cost">
              <a-input-number
                v-model:value="formData.self_pay_cost"
                :min="0"
                :precision="2"
                placeholder="自费金额"
                style="width: 100%"
                disabled
              >
                <template #addonBefore>¥</template>
              </a-input-number>
            </a-form-item>
          </a-col>
        </a-row>
      </div>

      <!-- 病历内容 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">病历内容</h3>
        <a-form-item label="病历详情" name="content">
          <a-textarea
            v-model:value="formData.content"
            :rows="6"
            placeholder="请输入病历详细内容..."
          />
        </a-form-item>
      </div>

      <!-- 文件上传 -->
      <div class="mb-6">
        <h3 class="text-lg font-semibold mb-4 text-gray-800 border-b border-gray-200 pb-2">附件上传</h3>
        <a-form-item label="病历文件" name="file">
          <a-upload
            v-model:file-list="fileList"
            :before-upload="beforeUpload"
            :remove="handleRemove"
            accept=".pdf,.doc,.docx,.txt"
          >
            <a-button>
              <UploadOutlined /> 选择文件
            </a-button>
            <div class="text-gray-500 text-sm mt-2">
              支持 PDF、Word、文本文件，大小不超过 10MB
            </div>
          </a-upload>
        </a-form-item>
      </div>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { UploadOutlined } from '@ant-design/icons-vue'
import type { FormInstance, UploadFile } from 'ant-design-vue'
import type { MedicalRecord, CreateMedicalRecordRequest } from '@/types/medical-records'
import { DEPARTMENTS, RECORD_TYPES, INSURANCE_TYPES } from '@/types/medical-records'
import { createMedicalRecord, updateMedicalRecord } from '@/api/medical-records'

// Props
interface Props {
  open: boolean
  record?: MedicalRecord | null
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  record: null
})

// Emits
const emit = defineEmits<{
  'update:open': [value: boolean]
  success: []
}>()

// 响应式数据
const loading = ref(false)
const formRef = ref<FormInstance>()
const fileList = ref<UploadFile[]>([])

const visible = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const isEdit = computed(() => !!props.record)

// 表单数据
const formData = reactive<CreateMedicalRecordRequest>({
  patient_name: '',
  patient_age: 0,
  patient_gender: 'M',
  patient_id_card: '',
  insurance_type: 'basic',
  insurance_number: '',
  department: '',
  doctor_name: '',
  admission_date: '',
  discharge_date: '',
  record_type: 'inpatient',
  diagnosis_primary: '',
  diagnosis_secondary: [],
  total_cost: 0,
  insurance_cost: 0,
  self_pay_cost: 0,
  content: ''
})

// 表单验证规则
const rules = {
  patient_name: [{ required: true, message: '请输入患者姓名' }],
  patient_age: [{ required: true, message: '请输入患者年龄' }],
  patient_gender: [{ required: true, message: '请选择性别' }],
  patient_id_card: [
    { required: true, message: '请输入身份证号' },
    { pattern: /^[1-9]\d{5}(18|19|20)\d{2}((0[1-9])|(1[0-2]))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$/, message: '身份证号格式不正确' }
  ],
  insurance_number: [{ required: true, message: '请输入医保号' }],
  department: [{ required: true, message: '请选择科室' }],
  doctor_name: [{ required: true, message: '请输入主治医生' }],
  admission_date: [{ required: true, message: '请选择入院日期' }],
  record_type: [{ required: true, message: '请选择记录类型' }],
  diagnosis_primary: [{ required: true, message: '请输入主要诊断' }],
  total_cost: [{ required: true, message: '请输入总费用' }],
  insurance_cost: [{ required: true, message: '请输入医保支付金额' }],
  content: [{ required: true, message: '请输入病历内容' }]
}

// 监听记录变化，填充表单
watch(() => props.record, (record) => {
  if (record) {
    Object.assign(formData, {
      ...record,
      admission_date: record.admission_date ? dayjs(record.admission_date) : '',
      discharge_date: record.discharge_date ? dayjs(record.discharge_date) : ''
    })
  } else {
    resetForm()
  }
}, { immediate: true })

// 工具函数
function resetForm() {
  Object.assign(formData, {
    patient_name: '',
    patient_age: 0,
    patient_gender: 'M',
    patient_id_card: '',
    insurance_type: 'basic',
    insurance_number: '',
    department: '',
    doctor_name: '',
    admission_date: '',
    discharge_date: '',
    record_type: 'inpatient',
    diagnosis_primary: '',
    diagnosis_secondary: [],
    total_cost: 0,
    insurance_cost: 0,
    self_pay_cost: 0,
    content: ''
  })
  fileList.value = []
}

function calculateCosts() {
  if (formData.total_cost && formData.insurance_cost) {
    formData.self_pay_cost = formData.total_cost - formData.insurance_cost
  }
}

function calculateSelfPay() {
  if (formData.total_cost && formData.insurance_cost) {
    formData.self_pay_cost = formData.total_cost - formData.insurance_cost
  }
}

function beforeUpload(file: UploadFile) {
  const isValidType = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'].includes(file.type || '')
  if (!isValidType) {
    message.error('只能上传 PDF、Word 或文本文件!')
    return false
  }
  const isLt10M = (file.size || 0) / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB!')
    return false
  }
  return false // 阻止自动上传
}

function handleRemove(file: UploadFile) {
  const index = fileList.value.indexOf(file)
  if (index > -1) {
    fileList.value.splice(index, 1)
  }
}

// 事件处理
async function handleSubmit() {
  try {
    await formRef.value?.validate()
    loading.value = true

    const submitData = {
      ...formData,
      admission_date: formData.admission_date ? dayjs(formData.admission_date).format('YYYY-MM-DD') : '',
      discharge_date: formData.discharge_date ? dayjs(formData.discharge_date).format('YYYY-MM-DD') : undefined,
      file: fileList.value[0]?.originFileObj
    }

    if (isEdit.value && props.record) {
      await updateMedicalRecord(props.record.id, submitData)
      message.success('病历更新成功')
    } else {
      await createMedicalRecord(submitData)
      message.success('病历创建成功')
    }

    emit('success')
  } catch (error) {
    console.error('提交失败:', error)
    message.error('提交失败，请检查表单数据')
  } finally {
    loading.value = false
  }
}

function handleCancel() {
  visible.value = false
  resetForm()
}
</script>

<style scoped>
.medical-record-form :deep(.ant-form-item-label) {
  font-weight: 500;
}

.medical-record-form :deep(.ant-input-number) {
  width: 100%;
}
</style>
