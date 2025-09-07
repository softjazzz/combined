<template>
  <div class="record-form">
    <a-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      @finish="handleSubmit"
      layout="vertical"
      size="large"
    >
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 左侧：患者基本信息 -->
        <div class="space-y-4">
          <div class="mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
              <UserOutlined class="text-cyan-400" />
              患者基本信息
            </h3>
          </div>

          <!-- 患者姓名 -->
          <a-form-item name="patient_name" class="mb-4">
            <label class="block text-sm font-medium text-slate-300 mb-2">患者姓名</label>
            <a-input
              v-model:value="formData.patient_name"
              placeholder="请输入患者姓名"
              class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400"
            />
          </a-form-item>

          <!-- 年龄和性别 -->
          <div class="grid grid-cols-2 gap-4">
            <a-form-item name="patient_age" class="mb-4">
              <label class="block text-sm font-medium text-slate-300 mb-2">年龄</label>
              <a-input-number
                v-model:value="formData.patient_age"
                placeholder="年龄"
                :min="0"
                :max="150"
                class="w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400"
              />
            </a-form-item>

            <a-form-item name="patient_gender" class="mb-4">
              <label class="block text-sm font-medium text-slate-300 mb-2">性别</label>
              <a-select
                v-model:value="formData.patient_gender"
                placeholder="选择性别"
                class="gender-select"
              >
                <a-select-option value="M">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-blue-500 flex items-center justify-center text-white text-xs">♂</div>
                    男性
                  </div>
                </a-select-option>
                <a-select-option value="F">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-pink-500 flex items-center justify-center text-white text-xs">♀</div>
                    女性
                  </div>
                </a-select-option>
                <a-select-option value="U">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-gray-500 flex items-center justify-center text-white text-xs">?</div>
                    未知
                  </div>
                </a-select-option>
              </a-select>
            </a-form-item>
          </div>

          <!-- 科室 -->
          <a-form-item name="department" class="mb-4">
            <label class="block text-sm font-medium text-slate-300 mb-2">科室</label>
            <a-select
              v-model:value="formData.department"
              placeholder="选择科室"
              show-search
              :filter-option="filterDepartment"
              class="department-select"
            >
              <a-select-option 
                v-for="dept in departments" 
                :key="dept" 
                :value="dept"
              >
                {{ dept }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <!-- 入院时间和记录类型 -->
          <div class="grid grid-cols-2 gap-4">
            <a-form-item name="admission_date" class="mb-4">
              <label class="block text-sm font-medium text-slate-300 mb-2">入院时间</label>
              <a-date-picker
                v-model:value="formData.admission_date"
                placeholder="选择入院时间"
                class="w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400"
                format="YYYY-MM-DD"
              />
            </a-form-item>

            <a-form-item name="record_type" class="mb-4">
              <label class="block text-sm font-medium text-slate-300 mb-2">记录类型</label>
              <a-select
                v-model:value="formData.record_type"
                placeholder="选择记录类型"
                class="record-type-select"
              >
                <a-select-option value="inpatient">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-blue-500"></div>
                    住院记录
                  </div>
                </a-select-option>
                <a-select-option value="outpatient">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-green-500"></div>
                    门诊记录
                  </div>
                </a-select-option>
                <a-select-option value="emergency">
                  <div class="flex items-center gap-2">
                    <div class="w-4 h-4 rounded bg-red-500"></div>
                    急诊记录
                  </div>
                </a-select-option>
              </a-select>
            </a-form-item>
          </div>
        </div>

        <!-- 右侧：文件上传 -->
        <div class="space-y-4">
          <div class="mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
              <FileTextOutlined class="text-cyan-400" />
              文件上传
            </h3>
          </div>

          <!-- 文件上传区域 -->
          <a-form-item name="file" class="mb-4">
            <label class="block text-sm font-medium text-slate-300 mb-2">病案文件（可选）</label>
            <a-upload-dragger
              v-model:file-list="fileList"
              :custom-request="handleFileUpload"
              :before-upload="beforeUpload"
              :show-upload-list="true"
              accept=".pdf,.doc,.docx,.txt"
              class="upload-dragger"
            >
              <div class="p-6">
                <div class="mb-4">
                  <CloudUploadOutlined class="text-4xl text-cyan-400" />
                </div>
                <div class="text-lg text-slate-200 mb-2">点击或拖拽文件到此区域上传</div>
                <div class="text-sm text-slate-400">
                  支持 PDF、Word、TXT 格式，文件大小不超过 10MB
                </div>
              </div>
            </a-upload-dragger>
          </a-form-item>

          <!-- 上传进度 -->
          <div v-if="uploadProgress.show" class="mb-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-slate-300">上传进度</span>
              <span class="text-sm text-slate-400">{{ uploadProgress.percentage }}%</span>
            </div>
            <a-progress 
              :percent="uploadProgress.percentage" 
              :show-info="false"
              stroke-color="#06b6d4"
            />
          </div>
        </div>
      </div>

      <!-- 病案内容 -->
      <div class="mt-6">
        <a-form-item name="content" class="mb-6">
          <label class="block text-sm font-medium text-slate-300 mb-2">
            病案内容
            <span class="text-red-400 ml-1">*</span>
          </label>
          <a-textarea
            v-model:value="formData.content"
            placeholder="请输入详细的病案内容，包括主诉、现病史、既往史、体格检查、辅助检查、诊断、治疗方案等..."
            :rows="12"
            :max-length="10000"
            show-count
            class="rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400"
          />
        </a-form-item>
      </div>

      <!-- 操作按钮 -->
      <div class="flex justify-end gap-4 pt-6 border-t border-slate-700/50">
        <a-button
          size="large"
          @click="handleCancel"
          class="h-12 px-8 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20"
        >
          取消
        </a-button>
        
        <a-button
          type="primary"
          html-type="submit"
          :loading="loading"
          size="large"
          class="h-12 px-8 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl"
        >
          <SaveOutlined v-if="!loading" class="mr-2" />
          {{ isEdit ? '更新记录' : '创建记录' }}
        </a-button>
      </div>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  UserOutlined,
  FileTextOutlined,
  CloudUploadOutlined,
  SaveOutlined
} from '@ant-design/icons-vue'
import type { FormInstance, UploadRequestOption } from 'ant-design-vue'
import type { MedicalRecord, CreateMedicalRecordRequest } from '@/types'
import { DEPARTMENTS } from '@/types/medical-records'

// Props
interface Props {
  record?: MedicalRecord | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Emits
const emit = defineEmits<{
  'submit': [data: CreateMedicalRecordRequest]
  'cancel': []
}>()

// 表单引用
const formRef = ref<FormInstance>()

// 是否为编辑模式
const isEdit = computed(() => !!props.record)

// 表单数据
const formData = reactive<CreateMedicalRecordRequest>({
  patient_name: '',
  patient_age: 0,
  patient_gender: 'U',
  department: '',
  admission_date: '',
  record_type: 'inpatient',
  content: '',
  file: undefined
})

// 文件列表
const fileList = ref<any[]>([])

// 上传进度
const uploadProgress = reactive({
  show: false,
  percentage: 0
})

// 科室列表
const departments = DEPARTMENTS

// 表单验证规则
const formRules = {
  patient_name: [
    { required: true, message: '请输入患者姓名', trigger: 'blur' },
    { min: 2, message: '患者姓名至少2个字符', trigger: 'blur' },
    { max: 50, message: '患者姓名不能超过50个字符', trigger: 'blur' }
  ],
  patient_age: [
    { required: true, message: '请输入患者年龄', trigger: 'blur' },
    { type: 'number', min: 0, max: 150, message: '年龄必须在0-150之间', trigger: 'blur' }
  ],
  patient_gender: [
    { required: true, message: '请选择患者性别', trigger: 'change' }
  ],
  department: [
    { required: true, message: '请选择科室', trigger: 'change' }
  ],
  admission_date: [
    { required: true, message: '请选择入院时间', trigger: 'change' }
  ],
  record_type: [
    { required: true, message: '请选择记录类型', trigger: 'change' }
  ],
  content: [
    { required: true, message: '请输入病案内容', trigger: 'blur' },
    { min: 50, message: '病案内容至少50个字符', trigger: 'blur' },
    { max: 10000, message: '病案内容不能超过10000个字符', trigger: 'blur' }
  ]
}

// 初始化表单数据
const initializeForm = () => {
  if (props.record) {
    Object.assign(formData, {
      patient_name: props.record.patient_name,
      patient_age: props.record.patient_age,
      patient_gender: props.record.patient_gender,
      department: props.record.department,
      admission_date: props.record.admission_date,
      record_type: props.record.record_type,
      content: props.record.content
    })

    // 如果有文件，添加到文件列表
    if (props.record.file_url) {
      fileList.value = [{
        uid: '1',
        name: props.record.file_name || '病案文件',
        status: 'done',
        url: props.record.file_url
      }]
    }
  }
}

// 监听record变化
watch(() => props.record, () => {
  initializeForm()
}, { immediate: true, deep: true })

// 处理表单提交
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    
    // 转换日期格式
    const submitData = {
      ...formData,
      admission_date: dayjs(formData.admission_date).format('YYYY-MM-DD')
    }
    
    emit('submit', submitData)
  } catch (error: any) {
    if (error?.errorFields) {
      message.warning('请检查输入信息')
    }
  }
}

// 处理取消
const handleCancel = () => {
  emit('cancel')
}

// 文件上传前验证
const beforeUpload = (file: File) => {
  // 检查文件类型
  const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
  if (!allowedTypes.includes(file.type)) {
    message.error('只支持 PDF、Word、TXT 格式的文件')
    return false
  }

  // 检查文件大小（10MB）
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过 10MB')
    return false
  }

  return true
}

// 处理文件上传
const handleFileUpload = async (options: UploadRequestOption) => {
  const { file, onProgress, onSuccess, onError } = options
  
  try {
    uploadProgress.show = true
    uploadProgress.percentage = 0

    // 模拟上传进度
    const interval = setInterval(() => {
      uploadProgress.percentage += 10
      onProgress?.({ percent: uploadProgress.percentage })
      
      if (uploadProgress.percentage >= 100) {
        clearInterval(interval)
        
        // 模拟上传完成
        setTimeout(() => {
          formData.file = file as File
          uploadProgress.show = false
          onSuccess?.('上传成功')
          message.success('文件上传成功')
        }, 500)
      }
    }, 200)

  } catch (error) {
    uploadProgress.show = false
    onError?.(error as Error)
    message.error('文件上传失败')
  }
}

// 筛选科室选项
const filterDepartment = (input: string, option: any) => {
  return option.children.toLowerCase().includes(input.toLowerCase())
}

// 重置表单
const resetForm = () => {
  formRef.value?.resetFields()
  fileList.value = []
  uploadProgress.show = false
  uploadProgress.percentage = 0
  
  Object.assign(formData, {
    patient_name: '',
    patient_age: 0,
    patient_gender: 'U',
    department: '',
    admission_date: '',
    record_type: 'inpatient',
    content: '',
    file: undefined
  })
}

// 暴露方法给父组件
defineExpose({
  resetForm,
  validateForm: () => formRef.value?.validate()
})
</script>

<style scoped>
/* 表单样式 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-input-number) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.ant-input-number .ant-input-number-input) {
  color: rgb(241 245 249) !important;
}

:deep(.ant-textarea) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-textarea:focus),
:deep(.ant-textarea-focused) {
  border: none !important;
  box-shadow: none !important;
}

/* 选择器样式 */
:deep(.gender-select .ant-select-selector),
:deep(.department-select .ant-select-selector),
:deep(.record-type-select .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 0.75rem !important;
  height: 3rem !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-select-selection-placeholder) {
  color: rgb(100 116 139) !important;
}

/* 日期选择器样式 */
:deep(.ant-picker) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-picker:hover),
:deep(.ant-picker-focused) {
  border-color: #06b6d4 !important;
  box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2) !important;
}

/* 上传组件样式 */
:deep(.upload-dragger .ant-upload-drag) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 2px dashed rgba(255, 255, 255, 0.2) !important;
  border-radius: 0.75rem !important;
}

:deep(.upload-dragger .ant-upload-drag:hover) {
  border-color: #06b6d4 !important;
  background: rgba(6, 182, 212, 0.05) !important;
}

:deep(.upload-dragger .ant-upload-drag.ant-upload-drag-hover) {
  border-color: #06b6d4 !important;
}

/* 进度条样式 */
:deep(.ant-progress-bg) {
  background: linear-gradient(90deg, #06b6d4, #3b82f6) !important;
}

/* 表单错误提示 */
:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .grid-cols-1.lg\\:grid-cols-2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .grid-cols-2 {
    grid-template-columns: 1fr;
  }
  
  .px-8 {
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
