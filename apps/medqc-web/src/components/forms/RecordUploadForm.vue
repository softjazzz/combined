<template>
  <div class="record-upload-form">
    <a-card 
      title="病案上传" 
      class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
      :bordered="false"
    >
      <template #extra>
        <a-button 
          v-if="hasContent" 
          type="text" 
          @click="resetForm"
          class="text-gray-500"
        >
          <template #icon>
            <ReloadOutlined />
          </template>
          重置
        </a-button>
      </template>

      <a-form 
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
        @finish="handleSubmit"
        class="space-y-6"
      >
        <!-- 患者基本信息 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a-form-item 
            label="患者姓名" 
            name="patient_name"
            class="mb-4"
          >
            <a-input 
              v-model:value="formData.patient_name"
              placeholder="请输入患者姓名"
              class="h-10"
            />
          </a-form-item>

          <a-form-item 
            label="年龄" 
            name="patient_age"
            class="mb-4"
          >
            <a-input-number 
              v-model:value="formData.patient_age"
              :min="0"
              :max="150"
              placeholder="年龄"
              class="w-full h-10"
            />
          </a-form-item>

          <a-form-item 
            label="性别" 
            name="patient_gender"
            class="mb-4"
          >
            <a-select 
              v-model:value="formData.patient_gender"
              placeholder="请选择性别"
              class="h-10"
            >
              <a-select-option value="M">男</a-select-option>
              <a-select-option value="F">女</a-select-option>
              <a-select-option value="U">未知</a-select-option>
            </a-select>
          </a-form-item>
        </div>

        <!-- 医疗信息 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <a-form-item 
            label="科室" 
            name="department"
            class="mb-4"
          >
            <a-select 
              v-model:value="formData.department"
              placeholder="请选择科室"
              show-search
              class="h-10"
            >
              <a-select-option 
                v-for="dept in DEPARTMENTS" 
                :key="dept" 
                :value="dept"
              >
                {{ dept }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item 
            label="入院日期" 
            name="admission_date"
            class="mb-4"
          >
            <a-date-picker 
              v-model:value="formData.admission_date"
              placeholder="选择入院日期"
              class="w-full h-10"
              format="YYYY-MM-DD"
            />
          </a-form-item>

          <a-form-item 
            label="记录类型" 
            name="record_type"
            class="mb-4"
          >
            <a-select 
              v-model:value="formData.record_type"
              placeholder="请选择记录类型"
              class="h-10"
            >
              <a-select-option 
                v-for="type in RECORD_TYPES" 
                :key="type.value" 
                :value="type.value"
              >
                {{ type.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
        </div>

        <!-- 病案内容输入 -->
        <div class="bg-gray-50 rounded-lg p-6">
          <h3 class="text-lg font-semibold mb-4 text-gray-800">病案内容</h3>
          
          <!-- 输入方式切换 -->
          <a-radio-group 
            v-model:value="inputMode" 
            button-style="solid"
            class="mb-4"
          >
            <a-radio-button value="text">手动输入</a-radio-button>
            <a-radio-button value="file">文件上传</a-radio-button>
          </a-radio-group>

          <!-- 手动输入 -->
          <div v-if="inputMode === 'text'">
            <a-form-item 
              name="content"
              :rules="[{ required: true, message: '请输入病案内容' }]"
            >
              <a-textarea
                v-model:value="formData.content"
                placeholder="请输入病案内容..."
                :rows="12"
                show-count
                :maxlength="10000"
                class="font-mono text-sm"
              />
            </a-form-item>
          </div>

          <!-- 文件上传 -->
          <div v-else-if="inputMode === 'file'">
            <a-upload-dragger
              :file-list="fileList"
              :before-upload="handleBeforeUpload"
              @remove="handleFileRemove"
              :multiple="false"
              class="!bg-white border-2 border-dashed border-blue-300 hover:border-blue-500 transition-colors"
            >
              <div class="p-8">
                <p class="ant-upload-drag-icon">
                  <InboxOutlined class="text-4xl text-blue-500" />
                </p>
                <p class="ant-upload-text text-gray-700">
                  点击或拖拽文件到此区域上传
                </p>
                <p class="ant-upload-hint text-gray-500">
                  支持 .txt, .pdf, .doc, .docx 格式，单个文件不超过 10MB
                </p>
              </div>
            </a-upload-dragger>

            <!-- 文件内容预览 -->
            <div v-if="fileContent" class="mt-4">
              <a-divider orientation="left">
                <span class="text-gray-600">文件内容预览</span>
              </a-divider>
              <div class="bg-white p-4 rounded border min-h-[400px] max-h-[600px] overflow-y-auto">
                <pre class="whitespace-pre-wrap text-sm text-gray-800">{{ fileContent.substring(0, 2000) }}{{ fileContent.length > 2000 ? '...' : '' }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- 提交按钮 -->
        <div class="flex justify-end space-x-4 pt-6 border-t">
          <a-button 
            @click="resetForm"
            size="large"
          >
            取消
          </a-button>
          <a-button 
            type="primary" 
            html-type="submit"
            size="large"
            :loading="isSubmitting"
            :disabled="!hasValidContent"
            class="min-w-32"
          >
            <template #icon>
              <CloudUploadOutlined />
            </template>
            {{ isSubmitting ? '上传中...' : '开始分析' }}
          </a-button>
        </div>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message, type FormInstance } from 'ant-design-vue'
import { 
  InboxOutlined, 
  CloudUploadOutlined, 
  ReloadOutlined 
} from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import type { 
  CreateMedicalRecordRequest, 
  Department 
} from '../../types/medical-records'
import { DEPARTMENTS, RECORD_TYPES } from '../../types/medical-records'
import { useFileUpload } from '../../composables/useFileUpload'
import { AntdValidationRules, validateMedicalRecord } from '../../utils/validation'
import { handleValidationError } from '../../utils/error-handler'

// 组件属性
interface Props {
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// 组件事件
interface Emits {
  (e: 'submit', data: CreateMedicalRecordRequest): void
  (e: 'cancel'): void
}

const emit = defineEmits<Emits>()

// 响应式数据
const formRef = ref<FormInstance>()
const inputMode = ref<'text' | 'file'>('text')
const isSubmitting = ref(false)
const fileContent = ref('')
const fileList = ref<any[]>([])

// 表单数据
const formData = reactive({
  patient_name: '',
  patient_age: undefined as number | undefined,
  patient_gender: undefined as 'M' | 'F' | 'U' | undefined,
  department: undefined as Department | undefined,
  admission_date: undefined as Dayjs | undefined,
  record_type: 'inpatient' as 'inpatient' | 'outpatient' | 'emergency',
  content: ''
})

// 表单验证规则
const formRules = {
  patient_name: AntdValidationRules.patientName,
  patient_age: AntdValidationRules.patientAge,
  patient_gender: AntdValidationRules.required('患者性别'),
  department: AntdValidationRules.department,
  admission_date: AntdValidationRules.required('入院日期'),
  record_type: AntdValidationRules.required('记录类型'),
  content: AntdValidationRules.medicalContent
}

// 文件上传相关
const { formatFileSize } = useFileUpload()

// 计算属性
const hasContent = computed(() => {
  return formData.content.trim().length > 0 || fileContent.value.length > 0
})

const hasValidContent = computed(() => {
  const content = inputMode.value === 'text' ? formData.content : fileContent.value
  return content.trim().length >= 50 // 至少50个字符
})

// 监听输入模式变化
watch(inputMode,  (newMode: any) => {
  if (newMode === 'text') {
    fileList.value = []
    fileContent.value = ''
  } else {
    formData.content = ''
  }
})

// 文件上传处理
const handleBeforeUpload = (file: File) => {
  // 验证文件类型
  const allowedTypes = [
    'text/plain',
    'application/pdf', 
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ]
  
  if (!allowedTypes.includes(file.type)) {
    message.error('不支持的文件格式')
    return false
  }

  // 验证文件大小
  if (file.size > 10 * 1024 * 1024) {
    message.error('文件大小不能超过 10MB')
    return false
  }

  // 根据文件类型显示不同的信息
  if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
    // 文本文件可以预览
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      fileContent.value = content.substring(0, 1000) + (content.length > 1000 ? '\n\n...(内容已截断)' : '')
    }
    reader.onerror = () => {
      message.error('文件读取失败')
      fileContent.value = `文件读取失败: ${file.name}`
    }
    reader.readAsText(file, 'UTF-8')
  } else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
    fileContent.value = `📄 PDF文件已选择: ${file.name}
文件大小: ${formatFileSize(file.size)}

PDF文件将在提交后由AI系统自动解析提取文本内容。
预览功能暂不支持PDF格式。

💡 提示：系统支持从PDF中提取病历文本、患者信息、诊断结果等结构化数据。`
  } else if (file.type.includes('msword') || file.name.endsWith('.doc') || file.name.endsWith('.docx')) {
    fileContent.value = `📝 Word文件已选择: ${file.name}
文件大小: ${formatFileSize(file.size)}

Word文件将在提交后由AI系统自动解析提取文本内容。
预览功能暂不支持Word格式。

💡 提示：系统支持从Word文档中提取病历文本、患者信息、诊断结果等结构化数据。`
  } else {
    fileContent.value = `已选择文件: ${file.name}
文件大小: ${formatFileSize(file.size)}
文件类型: ${file.type}

注意: 文件内容将在提交时处理`
  }

  fileList.value = [file]
  return false // 阻止自动上传
}

const handleFileRemove = () => {
  fileList.value = []
  fileContent.value = ''
}

// 表单提交
const handleSubmit = async () => {
  try {
    // 1. Ant Design 表单验证
    await formRef.value?.validate()
    
    isSubmitting.value = true

    const submitData: CreateMedicalRecordRequest = {
      patient_name: formData.patient_name,
      patient_age: formData.patient_age!,
      patient_gender: formData.patient_gender!,
      department: formData.department!,
      admission_date: formData.admission_date!.format('YYYY-MM-DD'),
      record_type: formData.record_type,
      content: inputMode.value === 'text' ? formData.content : fileContent.value,
      file: inputMode.value === 'file' ? fileList.value[0] : undefined
    }

    // 2. 业务逻辑验证
    const validation = validateMedicalRecord(submitData)
    if (!validation.isValid) {
      validation.errors.forEach(error => {
        handleValidationError(error, { field: 'medical_record' })
      })
      return
    }

    // 3. 显示警告信息（如果有）
    if (validation.warnings && validation.warnings.length > 0) {
      validation.warnings.forEach(warning => {
        console.warn('表单警告:', warning)
      })
    }

    emit('submit', submitData)
    
  } catch (error) {
    console.error('表单验证失败:', error)
    if (error instanceof Error) {
      handleValidationError(error.message, { operation: 'form_submit' })
    }
  } finally {
    isSubmitting.value = false
  }
}

// 重置表单
const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(formData, {
    patient_name: '',
    patient_age: undefined,
    patient_gender: undefined,
    department: undefined,
    admission_date: undefined,
    record_type: 'inpatient',
    content: ''
  })
  inputMode.value = 'text'
  fileList.value = []
  fileContent.value = ''
  emit('cancel')
}
</script>

<style scoped>
.record-upload-form {
  @apply max-w-4xl mx-auto;
}

.ant-upload-drag-icon {
  @apply mb-4;
}

:deep(.ant-form-item-label > label) {
  @apply font-medium text-gray-700;
}

:deep(.ant-input), 
:deep(.ant-select-selector),
:deep(.ant-picker) {
  @apply transition-all duration-200;
}

:deep(.ant-input:focus),
:deep(.ant-select-focused .ant-select-selector),
:deep(.ant-picker:hover),
:deep(.ant-picker-focused) {
  @apply border-blue-400 shadow-sm;
}
</style> 