<template>
  <a-modal
    :title="title"
    :open="visible"
    :confirm-loading="submitting"
    :width="600"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formState"
      :rules="rules"
      layout="vertical"
    >
      <a-alert
        v-if="defectInfo"
        type="info"
        show-icon
        class="mb-4"
      >
        <template #message>
          <span class="font-bold">质控问题：</span> {{ defectInfo.desc || defectInfo.code }}
        </template>
      </a-alert>

      <a-form-item
        label="申诉类型"
        name="appealType"
      >
        <a-select
          v-model:value="formState.appealType"
          placeholder="请选择申诉类型"
        >
          <a-select-option
            v-for="opt in APPEAL_TYPE_OPTIONS"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item
        label="申诉理由"
        name="appealReason"
      >
        <a-textarea
          v-model:value="formState.appealReason"
          :rows="4"
          placeholder="请详细描述申诉理由（至少10个字符）"
          show-count
          :maxlength="500"
        />
      </a-form-item>

      <!-- 这里预留上传组件位置，暂时只做UI展示 -->
      <a-form-item
        label="证据文件"
        name="evidenceUrls"
      >
        <a-upload
          v-model:file-list="fileList"
          action="/api/v1/upload"
          list-type="picture"
          :before-upload="() => false"
        >
          <a-button>
            <upload-outlined />
            上传证据
          </a-button>
        </a-upload>
        <div class="text-gray-400 text-xs mt-1">
          支持图片/PDF，单个文件不超过5MB
        </div>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { ref, reactive, watch } from 'vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { AppealType, APPEAL_TYPE_OPTIONS } from '@/types/appeal'
import { createAppeal } from '@/api/appeal'

const props = defineProps<{
  visible: boolean
  qcResultId: string
  defectId: string
  recordId: string
  defectInfo?: { code: string; desc: string }
}>()

const emit = defineEmits(['update:visible', 'success'])

const formRef = ref<FormInstance>()
const submitting = ref(false)
const fileList = ref([])

const title = '提交申诉'

interface FormState {
  appealType: AppealType | undefined
  appealReason: string
  evidenceUrls: string[]
}

const formState = reactive<FormState>({
  appealType: undefined,
  appealReason: '',
  evidenceUrls: [],
})

const rules = {
  appealType: [{ required: true, message: '请选择申诉类型', trigger: 'change' }],
  appealReason: [
    { required: true, message: '请输入申诉理由', trigger: 'blur' },
    { min: 10, message: '申诉理由至少10个字符', trigger: 'blur' },
  ],
} satisfies FormProps['rules']

const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    submitting.value = true

    // 模拟文件上传后的URL处理
    // 实际项目中应先上传文件获取URL
    const evidenceUrls = fileList.value.map((file: any) => file.url || file.name)

    await createAppeal({
      qcResultId: props.qcResultId,
      defectId: props.defectId,
      recordId: props.recordId,
      appealType: formState.appealType!,
      appealReason: formState.appealReason,
      evidenceUrls: evidenceUrls,
    })

    message.success('申诉提交成功')
    emit('success')
    handleCancel()
  } catch (error: any) {
    if (error?.errorFields) {
      // 表单校验失败，不做处理
    } else {
      message.error(error.message || '提交失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  formRef.value?.resetFields()
  fileList.value = []
  emit('update:visible', false)
}
</script>

<style scoped>
.mb-4 {
  margin-bottom: 16px;
}
</style>
