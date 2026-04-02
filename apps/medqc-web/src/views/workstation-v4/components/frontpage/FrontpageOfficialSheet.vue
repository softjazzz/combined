<template>
  <div
    class="mb-3 rounded-[12px] border border-emerald-100/80 bg-emerald-50/60 px-3 py-2 text-[12px] text-emerald-700"
  >
    当前来源：官方首页（CDM/数据表，Mongo 同步入库）
  </div>
  <div
    v-if="sheetLoading"
    class="flex items-center justify-center py-12"
  >
    <a-spin />
  </div>
  <FrontpageSheet
    v-else-if="sheetData"
    :data="sheetData"
    :post-processing="false"
  />
  <div
    v-else
    class="space-y-3"
  >
    <div
      class="rounded-[12px] border border-slate-200/80 bg-slate-50/80 px-3 py-2 text-xs text-slate-500"
    >
      系统首页暂无数据，以下展示官方首页空表样式（数据表当前为空或尚未同步）。
    </div>
    <FrontpageSheet
      :data="officialEmptySheetData"
      :post-processing="false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import FrontpageSheet from '../FrontpageSheet.vue'

defineProps<{
  sheetLoading: boolean
  sheetData: any
}>()

const officialEmptySheetData = computed(() => ({
  basic: {},
  diagnoses: [],
  surgeries: [],
  cost: {},
  evidence: {},
  other_medical_info: {},
}))
</script>
