<template>
  <div class="fee-trend-chart">
    <VChart
      :option="chartOption"
      :autoresize="true"
      style="height: 320px"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkLineComponent
} from 'echarts/components'
import type { FeeTrendPoint } from '@/data/drg/mock-fee-monitoring'
import * as echarts from 'echarts/core'

use([
  CanvasRenderer,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkLineComponent
])

interface Props {
  trend: FeeTrendPoint[]
  baselinePayment?: number | null
}

const props = defineProps<Props>()

const chartOption = computed(() => {
  const days = props.trend.map(t => `D${t.day}`)
  const cumulative = props.trend.map(t => t.cumulative)
  
  const series: any[] = [
    {
      name: '累计费用',
      type: 'line',
      data: cumulative,
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      showSymbol: false,
      lineStyle: {
        width: 3,
        color: '#5B8FF9',
        shadowColor: 'rgba(91, 143, 249, 0.3)',
        shadowBlur: 10,
        shadowOffsetY: 5
      },
      itemStyle: {
        color: '#5B8FF9',
        borderWidth: 2,
        borderColor: '#fff'
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(91, 143, 249, 0.4)' },
          { offset: 0.8, color: 'rgba(91, 143, 249, 0.05)' }
        ])
      }
    }
  ]

  // 如果有付费标准，添加标准线
  if (props.baselinePayment) {
    series.push({
      name: '付费标准',
      type: 'line',
      data: Array(days.length).fill(props.baselinePayment),
      lineStyle: {
        type: 'dashed',
        width: 2,
        color: '#faad14'
      },
      itemStyle: {
        color: '#faad14'
      },
      symbol: 'none'
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
        lineStyle: {
          color: 'rgba(0,0,0,0.2)',
          width: 1,
          type: 'solid'
        }
      },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      padding: [10, 14],
      textStyle: {
        color: '#595959'
      },
      formatter: (params: any) => {
        let result = `<div style="font-weight:600;margin-bottom:4px;color:#1f1f1f">${params[0].axisValue}</div>`
        params.forEach((param: any) => {
          const color = typeof param.color === 'string' ? param.color : (param.color?.colorStops?.[0]?.color || '#5B8FF9')
          const marker = `<span style="display:inline-block;margin-right:8px;border-radius:50%;width:8px;height:8px;background-color:${color}"></span>`
          result += `
            <div style="display:flex;justify-content:space-between;align-items:center;min-width:140px;margin-top:4px">
              <span>${marker}${param.seriesName}</span>
              <span style="font-weight:600;font-family:Din Alternate">¥${param.value.toLocaleString()}</span>
            </div>
          `
        })
        return result
      }
    },
    legend: {
      data: props.baselinePayment ? ['累计费用', '付费标准'] : ['累计费用'],
      right: 10,
      top: 0,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: {
        color: '#8c8c8c'
      }
    },
    grid: {
      left: 10,
      right: 20,
      bottom: 20,
      top: 40,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: days,
      axisLine: {
        lineStyle: {
          color: '#f0f0f0'
        }
      },
      axisLabel: {
        color: '#8c8c8c',
        interval: 'auto'
      },
      axisTick: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      name: '费用(元)',
      nameTextStyle: {
        color: '#bfbfbf',
        align: 'right',
        padding: [0, 8, 0, 0]
      },
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#f5f5f5'
        }
      },
      axisLabel: {
        formatter: (value: number) => `¥${(value / 1000).toFixed(0)}k`,
        color: '#8c8c8c'
      }
    },
    series
  }
})
</script>

<style scoped lang="scss">
.fee-trend-chart {
  width: 100%;
}
</style>
