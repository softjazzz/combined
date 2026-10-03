<template>
  <div class="charts">
    <VChart
      v-if="departments.length && departments.some((row) => row.count > 0)"
      :option="departmentOption"
      autoresize
      aria-label="科室数量Top5圆环图"
    />
    <VChart
      v-if="grades.length && grades.some((row) => row.count > 0)"
      :option="gradeOption"
      autoresize
      aria-label="专用评分等级比例圆环图"
    />
    <VChart
      v-if="defects.length && defects.some((row) => row.count > 0)"
      :option="defectOption"
      autoresize
      aria-label="缺陷Top10柱状图"
    />
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import type { SpecialDefectRow } from '@/api/specialRecordReports'
use([
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer,
])
const props = defineProps<{
  departments: Array<{ name: string; count: number }>
  grades: Array<{ grade: string; count: number; ratio: number }>
  defects: SpecialDefectRow[]
}>()
const palette = ['#2b6cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4']
function donut(title: string, data: Array<{ name: string; value: number }>) {
  return {
    color: palette,
    title: { text: title, textStyle: { fontSize: 14 } },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      { type: 'pie', radius: ['42%', '65%'], center: ['50%', '45%'], label: { show: false }, data },
    ],
  }
}
const departmentOption = computed(() =>
  donut(
    '科室数量 Top5',
    props.departments.map((row) => ({ name: row.name || '未知科室', value: row.count })),
  ),
)
const gradeOption = computed(() =>
  donut(
    '专用评分等级比例',
    props.grades.map((row) => ({ name: row.grade, value: row.count })),
  ),
)
const defectOption = computed(() => ({
  color: [palette[0]],
  title: { text: '缺陷 Top10', textStyle: { fontSize: 14 } },
  tooltip: { trigger: 'axis' },
  grid: { left: 140, right: 20, top: 40, bottom: 20 },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: {
    type: 'category',
    inverse: true,
    data: props.defects.map((row) => row.name),
    axisLabel: { width: 120, overflow: 'truncate' },
  },
  series: [{ type: 'bar', data: props.defects.map((row) => row.count) }],
}))
</script>
<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}
.charts > * {
  width: 100%;
  height: 300px;
  min-width: 0;
}
@media (max-width: 900px) {
  .charts {
    grid-template-columns: 1fr;
  }
}
</style>
