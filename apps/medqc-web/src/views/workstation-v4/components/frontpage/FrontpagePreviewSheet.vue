<template>
  <div class="frontpage-preview-sheet">
    <div class="frontpage-preview-sheet__notice">
      当前来源：LLM 抽取草稿（用于编辑、打印与对照）
    </div>
    <FrontpageSheet
      v-if="draftSheetData"
      :data="draftSheetData"
      :display-source="systemSheetData"
      :post-processing="postProcessing"
    />
    <div
      v-else
      class="frontpage-preview-sheet__empty"
    >
      尚未生成病案首页，请点击右上角"AI 生成首页"
    </div>
  </div>
</template>

<script setup lang="ts">
import FrontpageSheet from '../FrontpageSheet.vue'

defineProps<{
  draftSheetData: any
  systemSheetData?: any
  postProcessing: boolean
}>()
</script>

<style scoped>
.frontpage-preview-sheet {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.frontpage-preview-sheet__notice {
  margin-bottom: 12px;
  border: 1px solid rgba(10, 108, 255, 0.16);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  color: #0a6cff;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.frontpage-preview-sheet__empty {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  color: rgba(29, 29, 31, 0.5);
  padding: 48px 16px;
  text-align: center;
}
</style>
