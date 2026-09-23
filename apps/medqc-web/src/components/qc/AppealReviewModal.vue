<template>
  <a-modal
    title="审核申诉"
    :open="visible"
    :confirm-loading="submitting"
    :width="600"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-descriptions
      bordered
      :column="1"
      size="small"
      class="mb-4"
    >
      <a-descriptions-item label="申诉人">
        {{ appeal?.appellantName || '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="申诉类型">
        {{ appeal ? getAppealTypeLabel(appeal.appealType) : '-' }}
      </a-descriptions-item>
      <a-descriptions-item label="申诉时间">
        {{ formatDate(appeal?.createdAt) }}
      </a-descriptions-item>
      <a-descriptions-item label="申诉理由">
        <div class="whitespace-pre-wrap">
          {{ appeal?.appealReason }}
        </div>
      </a-descriptions-item>
      <a-descriptions-item
        v-if="appeal?.defectItem"
        label="缺陷项"
      >
        {{ appeal.defectItem }}
      </a-descriptions-item>
      <a-descriptions-item
        v-if="appeal?.evidence?.length"
        label="证据材料"
      >
        <div
          v-for="(item, idx) in appeal.evidence"
          :key="idx"
        >
          {{ item.name || item.url || `材料 ${idx + 1}` }}
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
      <a-form-item
        label="审核结果"
        name="action"
      >
        <a-radio-group v-model:value="formState.action">
          <a-radio
            value="approve"
            class="text-green-600"
          >
            <template #default>
              通过
            </template>
          </a-radio>
          <a-radio
            value="reject"
            class="text-red-600"
          >
            <template #default>
              驳回
            </template>
          </a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item
        label="审核意见"
        name="comment"
      >
        <a-textarea
          v-model:value="formState.comment"
          :rows="3"
          placeholder="请输入审核意见"
        />
      </a-form-item>
      <a-form-item
        v-if="formState.action === 'approve' || formState.action === 'reject'"
        label="处理决定"
      >
        <a-textarea
          v-model:value="formState.resolution"
          :rows="2"
          placeholder="可填写处理决定"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { ref, reactive, watch } from 'vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { type Appeal, type AppealReviewAction, getAppealTypeLabel } from '@/types/appeal'
import { reviewAppeal } from '@/api/appeal'
import dayjs from 'dayjs'

const props = defineProps<{
  visible: boolean
  appeal?: Appeal
}>()

const emit = defineEmits(['update:visible', 'success'])

const formRef = ref<FormInstance>()
const submitting = ref(false)

interface FormState {
  action: AppealReviewAction
  comment: string
  resolution: string
}

const formState = reactive<FormState>({
  action: 'approve',
  comment: '',
  resolution: '',
})

const rules = {
  action: [{ required: true, message: '请选择审核结果', trigger: 'change' }],
  comment: [{ required: true, message: '请输入审核意见', trigger: 'blur' }],
} satisfies FormProps['rules']

// 监听弹窗打开，重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      formState.action = 'approve'
      formState.comment = ''
      formState.resolution = ''
    }
  },
)

const formatDate = (dateStr?: string) => {
  return dateStr ? dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss') : '-'
}

const handleSubmit = async () => {
  if (!props.appeal?.id) return

  try {
    await formRef.value?.validate()
    submitting.value = true

    await reviewAppeal(props.appeal.id, {
      action: formState.action,
      comment: formState.comment.trim(),
      resolution: formState.resolution.trim() || undefined,
    })

    message.success('审核完成')
    emit('success')
    handleCancel()
  } catch (error) {
    if (typeof error === 'object' && error !== null && 'errorFields' in error) {
      // 校验失败
    } else {
      message.error(error instanceof Error ? error.message : '操作失败')
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
