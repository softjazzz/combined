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
        {{ appeal?.appellantName || '未知' }}
      </a-descriptions-item>
      <a-descriptions-item label="申诉类型">
        {{ getAppealTypeLabelStr(appeal?.appealType) }}
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
        v-if="appeal?.evidenceUrls?.length"
        label="证据文件"
      >
        <div
          v-for="(url, idx) in appeal.evidenceUrls"
          :key="idx"
        >
          <a
            :href="url"
            target="_blank"
            class="text-blue-500"
          >附件 {{ idx + 1 }}</a>
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
        name="decision"
      >
        <a-radio-group v-model:value="formState.decision">
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
        <div
          v-if="formState.decision === 'approve'"
          class="text-gray-400 text-xs mt-1"
        >
          通过后该质控问题将被标记为已解决。
        </div>
        <div
          v-if="formState.decision === 'reject'"
          class="text-gray-400 text-xs mt-1"
        >
          驳回后将自动创建整改任务并分配给申诉人。
        </div>
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
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { ref, reactive, watch } from 'vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { Appeal, getAppealTypeLabel } from '@/types/appeal'
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
  decision: 'approve' | 'reject'
  comment: string
}

const formState = reactive<FormState>({
  decision: 'approve',
  comment: '',
})

const rules = {
  decision: [{ required: true, message: '请选择审核结果', trigger: 'change' }],
  comment: [{ required: true, message: '请输入审核意见', trigger: 'blur' }],
} satisfies FormProps['rules']

// 监听弹窗打开，重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      formState.decision = 'approve'
      formState.comment = ''
    }
  },
)

const getAppealTypeLabelStr = (type?: string) => {
  return type ? getAppealTypeLabel(type as any) : '-'
}

const formatDate = (dateStr?: string) => {
  return dateStr ? dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss') : '-'
}

const handleSubmit = async () => {
  if (!props.appeal?.id) return

  try {
    await formRef.value?.validate()
    submitting.value = true

    await reviewAppeal(props.appeal.id, {
      decision: formState.decision,
      comment: formState.comment,
    })

    message.success('审核完成')
    emit('success')
    handleCancel()
  } catch (error: any) {
    if (error?.errorFields) {
      // 校验失败
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
