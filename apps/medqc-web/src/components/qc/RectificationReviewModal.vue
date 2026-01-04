<template>
  <a-modal
    title="验收整改"
    :open="visible"
    @ok="handleSubmit"
    @cancel="handleCancel"
    :confirmLoading="submitting"
    width="600px"
  >
    <a-descriptions bordered column="1" size="small" class="mb-4">
      <a-descriptions-item label="任务">{{ task?.taskTitle }}</a-descriptions-item>
      <a-descriptions-item label="整改人">{{ task?.assigneeName }}</a-descriptions-item>
       <a-descriptions-item label="整改说明">
           <div class="whitespace-pre-wrap">{{ task?.rectificationContent }}</div>
       </a-descriptions-item>
        <a-descriptions-item label="附件" v-if="task?.rectificationFiles?.length">
        <div v-for="(url, idx) in task.rectificationFiles" :key="idx">
          <a :href="url" target="_blank" class="text-blue-500">文件 {{ idx + 1 }}</a>
        </div>
      </a-descriptions-item>
    </a-descriptions>

    <a-divider />

    <a-form
      ref="formRef"
      :model="formState"
      :rules="rules"
      layout="vertical"
    >
      <a-form-item label="验收结果" name="reviewResult">
        <a-radio-group v-model:value="formState.reviewResult">
            <a-radio value="pass" class="text-green-600">通过</a-radio>
            <a-radio value="fail" class="text-red-600">不通过</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item label="验收意见" name="reviewComment">
        <a-textarea
          v-model:value="formState.reviewComment"
          :rows="3"
          placeholder="请输入验收意见"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { ref, reactive, watch } from 'vue'
import type { FormInstance } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { RectificationTask, ReviewResult } from '@/types/rectification'
import { reviewRectification } from '@/api/rectification'

const props = defineProps<{
  visible: boolean
  task?: RectificationTask
}>()

const emit = defineEmits(['update:visible', 'success'])

const formRef = ref<FormInstance>()
const submitting = ref(false)

interface FormState {
  reviewResult: ReviewResult
  reviewComment: string
}

const formState = reactive<FormState>({
  reviewResult: ReviewResult.PASS,
  reviewComment: ''
})

const rules = {
  reviewResult: [{ required: true, message: '请选择验收结果', trigger: 'change' }],
  reviewComment: [{ required: true, message: '请输入验收意见', trigger: 'blur' }]
}

watch(() => props.visible, (val) => {
    if (val) {
        formState.reviewResult = ReviewResult.PASS
        formState.reviewComment = ''
    }
})

const handleSubmit = async () => {
  if (!props.task?.id) return

  try {
    await formRef.value?.validate()
    submitting.value = true

    await reviewRectification(props.task.id, {
        reviewResult: formState.reviewResult,
        reviewComment: formState.reviewComment
    })

    message.success('验收完成')
    emit('success')
    handleCancel()
  } catch (error: any) {
     if (error?.errorFields) {
    } else {
      message.error(error.message || '操作失败')
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
.whitespace-pre-wrap {
    white-space: pre-wrap;
}
</style>
