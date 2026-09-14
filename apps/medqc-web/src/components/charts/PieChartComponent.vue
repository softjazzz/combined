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
import { computed, type PropType } from 'vue'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

// 注册ECharts组件
use([
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer
])

interface ChartDataItem {
  name: string
  value: number
  percentage?: number
  color?: string
}

interface PieTooltipParam {
  percent?: number
  name?: string
  color?: string
  value?: number | string
}

const props = defineProps({
  data: {
    type: Array as PropType<ChartDataItem[]>,
    required: true,
    default: () => []
  },
  title: {
    type: String,
    default: '分布统计'
  },
  height: {
    type: String,
    default: '400px'
  },
  showPercentage: {
    type: Boolean,
    default: true
  },
  radius: {
    type: Array as unknown as PropType<[string, string]>,
    default: (): [string, string] => ['40%', '70%']
  }
})

const chartOption = computed(() => {
  const colors = ['#2b6cf6', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96']
  
  const seriesData = props.data.map((item, index) => ({
    name: item.name,
    value: item.value,
    itemStyle: {
      color: item.color || colors[index % colors.length]
    }
  }))

  return {
    title: {
      text: props.title,
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: PieTooltipParam) => {
        const percentage = params.percent || 0
        return `
          <div style="font-weight: bold; margin-bottom: 8px;">${params.name}</div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${params.color}; border-radius: 50%; margin-right: 6px;"></span>
            数量: ${params.value}
          </div>
          <div>
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${params.color}; border-radius: 50%; margin-right: 6px;"></span>
            占比: ${percentage.toFixed(1)}%
          </div>
        `
      }
    },
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 10,
      top: 'middle',
      textStyle: {
        fontSize: 12
      },
      data: props.data.map(item => item.name)
    },
    series: [
      {
        name: props.title,
        type: 'pie',
        radius: props.radius,
        center: ['40%', '50%'],
        data: seriesData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        label: {
          show: true,
          position: 'outside',
          formatter: (params: PieTooltipParam) => {
            if (props.showPercentage) {
              return `${params.name}\n${params.percent}%`
            }
            return params.name
          },
          fontSize: 11,
          color: '#666'
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 10,
          smooth: true
        },
        animationType: 'scale',
        animationEasing: 'elasticOut',
        animationDelay: (idx: number) => Math.random() * 200
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
