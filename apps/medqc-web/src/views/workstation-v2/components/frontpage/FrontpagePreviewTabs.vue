<template>
  <div class="frontpage-workspace-panel__tabs-shell">
    <a-tabs
      class="frontpage-workspace-panel__tabs"
      :active-key="frontpageTab"
      size="small"
      @update:active-key="onTabChange"
      @change="onTabChange"
    >
      <a-tab-pane
        key="fields"
        tab="提取结果"
      >
        <slot name="fields" />
      </a-tab-pane>
      <a-tab-pane
        key="preview"
        tab="首页预览/打印"
      >
        <slot name="preview" />
      </a-tab-pane>
      <a-tab-pane
        key="official"
        tab="系统首页"
      >
        <slot name="official" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  frontpageTab: 'fields' | 'preview' | 'official'
}>()

const emit = defineEmits<{
  'update:frontpageTab': [value: 'fields' | 'preview' | 'official']
}>()

function onTabChange(tab: string) {
  if (tab === 'preview') {
    emit('update:frontpageTab', 'preview')
    return
  }
  if (tab === 'official') {
    emit('update:frontpageTab', 'official')
    return
  }
  emit('update:frontpageTab', 'fields')
}
</script>

<style scoped>
.frontpage-workspace-panel__tabs-shell {
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: linear-gradient(180deg, rgba(250, 252, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.03);
  padding: 10px 10px 8px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav) {
  margin: 0 0 12px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav::before) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav-wrap) {
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(226, 232, 240, 0.88);
  border-radius: 999px;
  padding: 4px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav-list) {
  gap: 4px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab) {
  margin: 0 !important;
  border-radius: 999px;
  padding: 8px 14px;
  color: #64748b;
  transition: all 0.18s ease;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab:hover) {
  color: #1e293b;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active) {
  background: #ffffff;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #0f172a;
  font-weight: 700;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-ink-bar) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-content-holder) {
  padding: 0 2px 2px;
}
</style>
