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
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { ref, reactive, watch } from 'vue'
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

const title = '提交申诉'

interface FormState {
  appealType: AppealType | undefined
  appealReason: string
}

const formState = reactive<FormState>({
  appealType: undefined,
  appealReason: '',
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

    await createAppeal({
      qcResultId: props.qcResultId,
      defectId: props.defectId,
      recordId: props.recordId,
      appealType: formState.appealType!,
      appealReason: formState.appealReason,
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
  emit('update:visible', false)
}
</script>

<style scoped>
.mb-4 {
  margin-bottom: 16px;
}
</style>
