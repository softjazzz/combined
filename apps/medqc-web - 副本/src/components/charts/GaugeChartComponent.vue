<template>
  <div class="chart-container">
    <v-chart
      :option="chartOption"
      :style="{ width: '100%', height: height }"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

// 注册ECharts组件
use([
  GaugeChart,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer
])

const props = defineProps({
  value: {
    type: Number,
    required: true,
    default: 0
  },
  title: {
    type: String,
    default: '评分'
  },
  height: {
    type: String,
    default: '300px'
  },
  max: {
    type: Number,
    default: 100
  },
  unit: {
    type: String,
    default: '分'
  }
})

const chartOption = computed(() => {
  // 根据分数确定颜色
  const getColor = (value: number) => {
    if (value >= 90) return '#52c41a'
    if (value >= 80) return '#faad14'
    if (value >= 60) return '#ff7875'
    return '#ff4d4f'
  }

  const color = getColor(props.value)

  return {
    title: {
      text: props.title,
      left: 'center',
      top: '10%',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      formatter: `{a} <br/>{b} : {c}${props.unit}`
    },
    series: [
      {
        name: props.title,
        type: 'gauge',
        center: ['50%', '60%'],
        radius: '80%',
        min: 0,
        max: props.max,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 20,
            color: [
              [0.6, '#ff4d4f'],
              [0.8, '#ff7875'],
              [0.9, '#faad14'],
              [1, '#52c41a']
            ]
          }
        },
        pointer: {
          itemStyle: {
            color: color
          }
        },
        axisTick: {
          distance: -20,
          length: 8,
          lineStyle: {
            color: '#fff',
            width: 2
          }
        },
        splitLine: {
          distance: -20,
          length: 20,
          lineStyle: {
            color: '#fff',
            width: 4
          }
        },
        axisLabel: {
          color: '#666',
          fontSize: 12,
          distance: -40,
          formatter: (value: number) => {
            return value.toString()
          }
        },
        detail: {
          valueAnimation: true,
          formatter: `{value}${props.unit}`,
          color: color,
          fontSize: 28,
          fontWeight: 'bold',
          offsetCenter: [0, '20%']
        },
        data: [
          {
            value: props.value,
            name: props.title
          }
        ]
      }
    ]
  }
})
</script>

<style scoped>
.chart-container {
  @apply w-full;
}
</style> 