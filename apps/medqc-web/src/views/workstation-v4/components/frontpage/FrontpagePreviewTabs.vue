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
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.055);
  padding: 10px 10px 8px;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav) {
  margin: 0 0 12px;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav::before) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-nav-wrap) {
  background: rgba(245, 245, 247, 0.86);
  border: 1px solid rgba(0, 0, 0, 0.08);
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
  color: rgba(29, 29, 31, 0.58);
  font-weight: 600;
  transition:
    background-color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    color 250ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 250ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab:hover) {
  color: #1d1d1f;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active) {
  background: #ffffff;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 2px 8px rgba(0, 102, 204, 0.08);
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #0066cc;
  font-weight: 650;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-ink-bar) {
  display: none;
}

:deep(.frontpage-workspace-panel__tabs .ant-tabs-content-holder) {
  padding: 0 2px 2px;
}
</style>
