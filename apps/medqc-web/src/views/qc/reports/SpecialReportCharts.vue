<template>
  <div class="charts">
    <figure
      v-if="departments.length && departments.some((row) => row.count > 0)"
      class="chart-panel mq-inset"
    >
      <VChart :option="departmentOption" autoresize aria-label="科室数量Top5圆环图" />
    </figure>
    <figure
      v-if="grades.length && grades.some((row) => row.count > 0)"
      class="chart-panel mq-inset"
    >
      <VChart :option="gradeOption" autoresize aria-label="专用评分等级比例圆环图" />
    </figure>
    <figure
      v-if="defects.length && defects.some((row) => row.count > 0)"
      class="chart-panel chart-panel--bar mq-inset"
    >
      <VChart :option="defectOption" autoresize aria-label="缺陷Top10柱状图" />
    </figure>
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
// ECharts 画布读不到 CSS 变量，挂载时从 V7.1 Token 取值；单一蓝色系，全部保持白底高对比
function token(name: string, fallback: string) {
  const value =
    typeof document !== 'undefined'
      ? getComputedStyle(document.documentElement).getPropertyValue(name).trim()
      : ''
  return value || fallback
}
const palette = [
  token('--mq-brand-600', '#0a6cff'),
  token('--mq-brand-700', '#0a5fd6'),
  token('--mq-brand-400', '#3b8bff'),
  '#174ea6',
  token('--mq-text-tertiary', '#59595e'),
]
const textColor = token('--mq-text-secondary', '#515154')
const titleStyle = {
  fontSize: 14,
  fontWeight: 600,
  color: token('--mq-text-primary', '#1d1d1f'),
}
function donut(title: string, data: Array<{ name: string; value: number }>) {
  return {
    color: palette,
    title: { text: title, textStyle: titleStyle },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll', textStyle: { color: textColor } },
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
  title: { text: '缺陷 Top10', textStyle: titleStyle },
  tooltip: { trigger: 'axis' },
  grid: { left: 12, right: 20, top: 40, bottom: 20, containLabel: true },
  xAxis: { type: 'value', minInterval: 1, axisLabel: { color: textColor } },
  yAxis: {
    type: 'category',
    inverse: true,
    data: props.defects.map((row) => row.name),
    axisLabel: { width: 112, overflow: 'truncate', ellipsis: '…', color: textColor },
  },
  series: [{ type: 'bar', data: props.defects.map((row) => row.count) }],
}))
</script>
<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}
.chart-panel {
  min-width: 0;
  margin: 0;
  padding: 16px;
}
.chart-panel > * {
  width: 100%;
  height: 280px;
  min-width: 0;
}
@media (max-width: 1360px) {
  .charts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .chart-panel--bar,
  .chart-panel:last-child:nth-child(odd) {
    grid-column: 1 / -1;
  }
}
@media (max-width: 900px) {
  .charts {
    grid-template-columns: 1fr;
  }
}
</style>
