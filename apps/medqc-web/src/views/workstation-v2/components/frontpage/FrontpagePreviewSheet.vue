<template>
  <div
    class="mb-3 rounded-[12px] border border-blue-100/80 bg-blue-50/55 px-3 py-2 text-[12px] text-blue-700"
  >
    当前来源：LLM 抽取草稿（用于编辑、打印与对照）
  </div>
  <FrontpageSheet v-if="draftSheetData" :data="draftSheetData" :post-processing="postProcessing" />
  <div v-else class="py-12 text-center text-slate-400">
    尚未生成病案首页，请点击右上角"AI 生成首页"
  </div>
</template>

<script setup lang="ts">
import FrontpageSheet from '../FrontpageSheet.vue'

defineProps<{
  draftSheetData: any
  postProcessing: boolean
}>()
</script>
