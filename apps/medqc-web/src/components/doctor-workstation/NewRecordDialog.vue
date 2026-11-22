<template>
  <div
    class="new-record-overlay"
    @click="handleOverlayClick"
  >
    <div
      class="new-record-modal"
      @click.stop
    >
      <!-- 模态框头部 -->
      <div class="modal-header">
        <h3 class="modal-title">
          <i class="fas fa-plus-circle" />
          新建病历
        </h3>
        <button
          class="close-btn"
          @click="$emit('close')"
        >
          <i class="fas fa-times" />
        </button>
      </div>

      <!-- 表单内容 -->
      <div class="modal-body">
        <form @submit.prevent="handleSubmit">
          <!-- 患者基本信息 -->
          <div class="form-section">
            <h4 class="section-title">
              <i class="fas fa-user" />
              患者基本信息
            </h4>
            
            <div class="form-row">
              <div class="form-group">
                <label
                  class="form-label"
                  for="patient_name"
                >
                  患者姓名 <span class="required">*</span>
                </label>
                <input
                  id="patient_name"
                  v-model="formData.patient_name"
                  type="text"
                  class="form-input"
                  placeholder="请输入患者姓名"
                  required
                >
              </div>
              
              <div class="form-group">
                <label
                  class="form-label"
                  for="patient_age"
                >
                  年龄 <span class="required">*</span>
                </label>
                <input
                  id="patient_age"
                  v-model.number="formData.patient_age"
                  type="number"
                  class="form-input"
                  placeholder="年龄"
                  min="0"
                  max="150"
                  required
                >
              </div>
              
              <div class="form-group">
                <label
                  class="form-label"
                  for="patient_gender"
                >
                  性别 <span class="required">*</span>
                </label>
                <select
                  id="patient_gender"
                  v-model="formData.patient_gender"
                  class="form-select"
                  required
                >
                  <option value="">
                    请选择
                  </option>
                  <option value="M">
                    男
                  </option>
                  <option value="F">
                    女
                  </option>
                  <option value="U">
                    未知
                  </option>
                </select>
              </div>
            </div>
          </div>

          <!-- 就诊信息 -->
          <div class="form-section">
            <h4 class="section-title">
              <i class="fas fa-hospital" />
              就诊信息
            </h4>
            
            <div class="form-row">
              <div class="form-group">
                <label
                  class="form-label"
                  for="department"
                >
                  科室 <span class="required">*</span>
                </label>
                <select
                  id="department"
                  v-model="formData.department"
                  class="form-select"
                  required
                >
                  <option value="">
                    请选择科室
                  </option>
                  <option
                    v-for="dept in departments"
                    :key="dept"
                    :value="dept"
                  >
                    {{ dept }}
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label
                  class="form-label"
                  for="record_type"
                >
                  病历类型 <span class="required">*</span>
                </label>
                <select
                  id="record_type"
                  v-model="formData.record_type"
                  class="form-select"
                  required
                >
                  <option value="">
                    请选择类型
                  </option>
                  <option value="inpatient">
                    住院
                  </option>
                  <option value="outpatient">
                    门诊
                  </option>
                  <option value="emergency">
                    急诊
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label
                  class="form-label"
                  for="admission_date"
                >
                  入院日期 <span class="required">*</span>
                </label>
                <a-date-picker
                  id="admission_date"
                  :value="formData.admission_date"
                  @update:value="formData.admission_date = typeof $event === 'string' ? $event : ''"
                  value-format="YYYY-MM-DD"
                  class="form-input"
                  :disabled-date="(date) => date.format('YYYY-MM-DD') > today"
                  aria-required="true"
                />
              </div>
            </div>
          </div>

          <!-- 快速模板选择 -->
          <div class="form-section">
            <h4 class="section-title">
              <i class="fas fa-file-medical" />
              快速模板（可选）
            </h4>
            
            <div class="template-options">
              <label
                v-for="template in quickTemplates"
                :key="template.id"
                class="template-option"
              >
                <input
                  v-model="selectedTemplate"
                  type="radio"
                  :value="template.id"
                  class="template-radio"
                >
                <div class="template-card">
                  <div class="template-name">{{ template.template_name }}</div>
                  <div class="template-description">{{ template.category }}</div>
                </div>
              </label>
            </div>
          </div>
        </form>
      </div>

      <!-- 模态框底部 -->
      <div class="modal-footer">
        <button
          type="button"
          class="btn btn-secondary"
          @click="$emit('close')"
        >
          <i class="fas fa-times" />
          取消
        </button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="!isFormValid"
          @click="handleSubmit"
        >
          <i class="fas fa-plus" />
          创建病历
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { DatePicker as ADatePicker } from 'ant-design-vue'
import { ref, computed, onMounted } from 'vue'
import type { MedicalRecord } from '@/api/medical-records'

// Emits
const emit = defineEmits<{
  create: [recordData: Partial<MedicalRecord>]
  close: []
}>()

// 响应式数据
const formData = ref({
  patient_name: '',
  patient_age: null as number | null,
  patient_gender: '' as 'M' | 'F' | 'U' | '',
  department: '',
  record_type: '' as 'inpatient' | 'outpatient' | 'emergency' | '',
  admission_date: '',
  content: ''
})

const selectedTemplate = ref<string>('')

// 科室列表
const departments = [
  '内科', '外科', '妇产科', '儿科', '眼科', '耳鼻喉科',
  '皮肤科', '神经科', '精神科', '康复科', '急诊科', '麻醉科'
]

// 快速模板
const quickTemplates = ref([
  {
    id: 'template-admission',
    template_name: '入院记录',
    category: '住院病历',
    content: '主诉：\n现病史：\n既往史：\n体格检查：\n辅助检查：\n初步诊断：\n诊疗计划：'
  },
  {
    id: 'template-outpatient',
    template_name: '门诊记录',
    category: '门诊病历',
    content: '主诉：\n现病史：\n体格检查：\n诊断：\n处理：'
  },
  {
    id: 'template-emergency',
    template_name: '急诊记录',
    category: '急诊病历',
    content: '主诉：\n现病史：\n体格检查：\n辅助检查：\n诊断：\n处理：'
  }
])

// 计算属性
const today = computed(() => {
  return new Date().toISOString().split('T')[0]
})

const isFormValid = computed(() => {
  return formData.value.patient_name &&
         formData.value.patient_age &&
         formData.value.patient_gender &&
         formData.value.department &&
         formData.value.record_type &&
         formData.value.admission_date
})

// 方法
const handleOverlayClick = () => {
  emit('close')
}

const handleSubmit = () => {
  if (!isFormValid.value) {
    return
  }

  // 如果选择了模板，添加模板内容
  if (selectedTemplate.value) {
    const template = quickTemplates.value.find(t => t.id === selectedTemplate.value)
    if (template) {
      formData.value.content = template.content
    }
  }

  // 创建病历数据
  const recordData: Partial<MedicalRecord> = {
    patient_name: formData.value.patient_name,
    patient_age: formData.value.patient_age!,
    patient_gender: formData.value.patient_gender as 'M' | 'F' | 'U',
    department: formData.value.department,
    record_type: formData.value.record_type as 'inpatient' | 'outpatient' | 'emergency',
    admission_date: formData.value.admission_date,
    content: formData.value.content,
    status: 'pending'
  }

  emit('create', recordData)
}

// 组件挂载时设置默认日期
onMounted(() => {
  formData.value.admission_date = today.value
})
</script>

<style scoped>
.new-record-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.new-record-modal {
  width: 90%;
  max-width: 700px;
  max-height: 90vh;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.modal-title {
  margin: 0;
  color: #495057;
  font-size: 1.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.close-btn {
  padding: 0.5rem;
  border: none;
  background: none;
  color: #6c757d;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #e9ecef;
  color: #495057;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.form-section {
  margin-bottom: 2rem;
}

.form-section:last-child {
  margin-bottom: 0;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1rem 0;
  color: #495057;
  font-size: 1rem;
  font-weight: 600;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-label {
  margin-bottom: 0.5rem;
  color: #495057;
  font-weight: 500;
  font-size: 0.875rem;
}

.required {
  color: #dc3545;
}

.form-input,
.form-select {
  padding: 0.75rem;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.875rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
}

.form-input::placeholder {
  color: #adb5bd;
}

.template-options {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.template-option {
  cursor: pointer;
}

.template-radio {
  display: none;
}

.template-card {
  padding: 1rem;
  border: 2px solid #e1e8ed;
  border-radius: 6px;
  transition: all 0.2s;
  background: white;
}

.template-option:hover .template-card {
  border-color: #007bff;
  background: #f8f9ff;
}

.template-radio:checked + .template-card {
  border-color: #007bff;
  background: #e7f3ff;
}

.template-name {
  font-weight: 500;
  color: #495057;
  margin-bottom: 0.25rem;
}

.template-description {
  font-size: 0.875rem;
  color: #6c757d;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #545b62;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}
</style>
