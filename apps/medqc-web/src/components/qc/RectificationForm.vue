<template>
  <a-modal
    title="提交整改"
    :open="visible"
    :confirm-loading="submitting"
    :width="600"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-descriptions
      bordered
      column="1"
      size="small"
      class="mb-4"
    >
      <a-descriptions-item label="整改任务">
        {{ task?.taskTitle }}
      </a-descriptions-item>
      <a-descriptions-item label="任务描述">
        {{ task?.taskDescription }}
      </a-descriptions-item>
      <a-descriptions-item label="严重程度">
        <a-tag :color="getSeverityColor(task?.severity)">
          {{ getSeverityLabel(task?.severity) }}
        </a-tag>
      </a-descriptions-item>
    </a-descriptions>

    <a-divider />

    <a-form
      ref="formRef"
      :model="formState"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item
        label="整改说明"
        name="rectificationContent"
      >
        <a-textarea
          v-model:value="formState.rectificationContent"
          :rows="4"
          placeholder="请详细描述整改内容..."
          show-count
          :maxlength="1000"
        />
      </a-form-item>

      <a-form-item
        label="附件材料"
        name="rectificationFiles"
      >
        <a-upload
          v-model:file-list="fileList"
          action="/api/v1/upload"
          list-type="picture"
          :before-upload="() => false"
        >
          <a-button>
            <upload-outlined />
            上传附件
          </a-button>
        </a-upload>
        <div class="text-gray-400 text-xs mt-1">
          支持截图或PDF文档
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
import { RectificationTask, getTaskSeverityInfo } from '@/types/rectification'
import { submitRectification } from '@/api/rectification'

const props = defineProps<{
  visible: boolean
  task?: RectificationTask
}>()

const emit = defineEmits(['update:visible', 'success'])

const formRef = ref<FormInstance>()
const submitting = ref(false)
const fileList = ref([])

interface FormState {
  rectificationContent: string
  rectificationFiles: string[]
}

const formState = reactive<FormState>({
  rectificationContent: '',
  rectificationFiles: [],
})

const rules = {
  rectificationContent: [
    { required: true, message: '请输入整改说明', trigger: 'blur' },
    { min: 5, message: '说明过短', trigger: 'blur' },
  ],
} satisfies FormProps['rules']

const getSeverityLabel = (severity: any) => getTaskSeverityInfo(severity).label
const getSeverityColor = (severity: any) => getTaskSeverityInfo(severity).color

watch(
  () => props.visible,
  (val) => {
    if (val) {
      formState.rectificationContent = ''
      fileList.value = []
    }
  },
)

const handleSubmit = async () => {
  if (!props.task?.id) return

  try {
    await formRef.value?.validate()
    submitting.value = true

    const files = fileList.value.map((file: any) => file.url || file.name)

    await submitRectification(props.task.id, {
      rectificationContent: formState.rectificationContent,
      rectificationFiles: files,
    })

    message.success('整改已提交')
    emit('success')
    handleCancel()
  } catch (error: any) {
    if (error?.errorFields) {
      return
    } else {
      message.error(error.message || '提交失败')
    }
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  emit('update:visible', false)
}
</script>

<style scoped>
.mb-4 {
  margin-bottom: 16px;
}
</style>
