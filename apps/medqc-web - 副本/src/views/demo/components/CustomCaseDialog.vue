<!--
  自定义病例对话框（占位组件 - Step 2实现）
  用于创建和编辑自定义病例
-->
<template>
  <a-modal
    :open="visible"
    title="新建自定义病例"
    width="800px"
    :confirm-loading="false"
    @ok="handleOk"
    @cancel="handleCancel"
  >
    <a-alert
      message="功能开发中"
      description="自定义病例录入功能将在Step 2阶段实现，敬请期待！"
      type="info"
      show-icon
    />
  </a-modal>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import type { Case } from '@/types/clinical-workstation'

// ========== Props ==========
interface Props {
  visible: boolean
}

defineProps<Props>()

// ========== Emits ==========
const emit = defineEmits<{
  'update:visible': [value: boolean]
  'submit': [customCase: Case]
}>()

// ========== Methods ==========

function handleOk() {
  message.info('自定义病例录入功能将在Step 2阶段实现')
  emit('update:visible', false)
}

function handleCancel() {
  emit('update:visible', false)
}
</script>
