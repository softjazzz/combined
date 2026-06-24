<template>
  <a-modal
    :open="open"
    title="质控评估"
    :footer="null"
    centered
    width="520px"
    @update:open="emit('update:open', $event)"
  >
    <div class="evaluation-modal-body">
      <a-result
        status="info"
        title="请前往质控评估页面"
        sub-title="在主导航中点击「质控评估」进入完整评估流程。"
      >
        <template #extra>
          <a-button
            type="primary"
            @click="emit('update:open', false)"
          >
            知道了
          </a-button>
        </template>
      </a-result>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()
</script>

<style scoped>
.evaluation-modal-body {
  padding: 10px 4px 2px;
}
</style>
