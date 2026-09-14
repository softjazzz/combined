<template>
  <a-textarea
    :value="modelValue"
    :rows="rows"
    :auto-size="autoSizeConfig"
    class="code-editor"
    @update:value="onUpdate"
  />
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue: string
  rows?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const autoSizeConfig = { minRows: props.rows ?? 8, maxRows: Math.max((props.rows ?? 8) + 12, 12) }

const onUpdate = (value: string) => {
  emit('update:modelValue', value)
}
</script>

<style scoped lang="less">
.code-editor {
  font-family: 'Fira Code', 'JetBrains Mono', Menlo, Consolas, monospace;
  background-color: #f8fafc;
  color: #1e293b;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  line-height: 1.6;
  font-size: 14px;

  :deep(textarea) {
    background-color: #f8fafc;
    color: #1e293b;

    &:hover {
      border-color: #94a3b8;
    }

    &:focus {
      background-color: #ffffff;
      border-color: #2b6cf6;
      box-shadow: 0 0 0 2px rgba(43, 108, 246, 0.1);
    }
  }
}
</style>
