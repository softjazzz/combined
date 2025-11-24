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
    default: (): [string, string] => ['35%', '55%'] // 减小默认半径
  }
})

const chartOption = computed(() => {
  const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96']
  
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
      formatter: (params: any) => {
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
      bottom: 0,
      left: 'center',
      orient: 'horizontal',
      textStyle: {
        fontSize: 11
      },
      data: props.data.map(item => item.name),
      itemWidth: 12,
      itemHeight: 12
    },
    series: [
      {
        name: props.title,
        type: 'pie',
        radius: props.radius,
        center: ['50%', '45%'], // 向上偏移，给底部图例留空间
        data: seriesData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        },
        avoidLabelOverlap: true,
        label: {
          show: true,
          position: 'outside',
          formatter: (params: any) => {
            if (props.showPercentage) {
              return `${params.name}\n${params.percent}%`
            }
            return params.name
          },
          fontSize: 11,
          color: '#666',
          overflow: 'none',
          padding: [0, -4] // 稍微减小padding
        },
        labelLine: {
          show: true,
          length: 15,
          length2: 20, // 进一步增加第二段长度
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
  @apply w-full h-full;
}
</style>