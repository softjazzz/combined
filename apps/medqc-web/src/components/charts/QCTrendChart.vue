<template>
  <div class="w-full h-full">
    <v-chart class="chart" :option="option" :autoresize="true" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineProps } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  GraphicComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import * as echarts from 'echarts/core'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  GraphicComponent
])

interface Props {
  period: string
  height?: number
  autoRefresh?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  period: 'month',
  height: 320,
  autoRefresh: false
})

// 模拟数据 (可以根据 period prop 调整数据粒度)
const chartData = {
  dates: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
  counts: [156, 189, 234, 198, 267, 301, 278, 245, 289, 324, 298, 312],
  scores: [85.2, 87.1, 88.5, 86.8, 89.2, 90.1, 88.9, 87.6, 89.8, 91.2, 90.5, 91.8],
  passRates: [92.3, 94.1, 95.2, 93.7, 96.1, 97.2, 95.8, 94.5, 96.7, 98.1, 97.4, 98.6]
}

// ECharts 配置
const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'line',
      lineStyle: {
        color: '#cbd5e1',
        width: 1,
        type: 'dashed'
      }
    },
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderColor: '#f1f5f9',
    borderWidth: 1,
    borderRadius: 12,
    extraCssText: 'box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.1); backdrop-filter: blur(8px);',
    textStyle: {
      color: '#334155',
      fontSize: 12,
      fontFamily: 'Inter, sans-serif'
    },
    padding: [12, 16],
    formatter: (params: any) => {
      let html = `<div class="font-bold mb-3 text-slate-800 text-sm border-b border-slate-100 pb-2">${params[0].axisValue}</div>`
      html += '<div class="flex flex-col gap-2">'
      params.forEach((item: any) => {
        const value = item.value
        let unit = ''
        if (item.seriesName === '病案数量') unit = '份'
        if (item.seriesName === '平均评分') unit = '分'
        if (item.seriesName === '通过率') unit = '%'
        
        // 自定义 marker 样式
        let marker = ''
        if (item.seriesType === 'line') {
          marker = `<span style="display:inline-block;margin-right:6px;border-radius:50%;width:8px;height:8px;background-color:${item.color}"></span>`
        } else {
          marker = `<span style="display:inline-block;margin-right:6px;border-radius:2px;width:8px;height:8px;background: linear-gradient(to bottom, #3b82f6, #60a5fa)"></span>`
        }
        
        html += `<div class="flex justify-between items-center gap-8 text-xs">
                  <span class="text-slate-500 flex items-center gap-2">${marker}${item.seriesName}</span>
                  <span class="font-mono font-bold text-slate-700">${value}${unit}</span>
                 </div>`
      })
      html += '</div>'
      return html
    }
  },
  legend: {
    top: 0,
    right: 0,
    itemWidth: 12,
    itemHeight: 12,
    icon: 'circle',
    textStyle: {
      color: '#64748b',
      fontSize: 12
    }
  },
  grid: {
    left: '2%',
    right: '2%',
    bottom: '5%',
    top: '15%',
    containLabel: true
  },
  xAxis: {
    type: 'category',
    data: chartData.dates,
    axisLine: {
      show: false
    },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
      interval: 0,
      margin: 16
    },
    axisTick: {
      show: false
    }
  },
  yAxis: [
    {
      type: 'value',
      name: '数量',
      min: 0,
      max: 400,
      interval: 100,
      nameTextStyle: {
        color: '#94a3b8',
        align: 'right',
        padding: [0, 8, 0, 0]
      },
      splitLine: {
        lineStyle: {
          color: '#f1f5f9',
          type: 'dashed'
        }
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11
      }
    },
    {
      type: 'value',
      name: '评分/通过率',
      min: 80,
      max: 100,
      interval: 5,
      nameTextStyle: {
        color: '#94a3b8',
        align: 'left',
        padding: [0, 0, 0, 8]
      },
      splitLine: {
        show: false
      },
      axisLabel: {
        color: '#94a3b8',
        fontSize: 11,
        formatter: '{value}'
      }
    }
  ],
  series: [
    {
      name: '病案数量',
      type: 'bar',
      barWidth: 12,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.8)' }, // Blue-500
          { offset: 1, color: 'rgba(59, 130, 246, 0.1)' }  // Fade out
        ]),
        borderRadius: [6, 6, 0, 0]
      },
      data: chartData.counts
    },
    {
      name: '通过率',
      type: 'line',
      yAxisIndex: 1,
      smooth: true,
      showSymbol: false,
      symbolSize: 8,
      lineStyle: {
        width: 3,
        color: '#10b981', // Emerald-500
        shadowColor: 'rgba(16, 185, 129, 0.3)',
        shadowBlur: 10
      },
      itemStyle: {
        color: '#10b981',
        borderWidth: 2,
        borderColor: '#fff'
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(16, 185, 129, 0.15)' },
          { offset: 1, color: 'rgba(16, 185, 129, 0)' }
        ])
      },
      data: chartData.passRates
    },
    {
      name: '平均评分',
      type: 'line',
      yAxisIndex: 1,
      smooth: true,
      showSymbol: false,
      symbolSize: 8,
      lineStyle: {
        width: 3,
        color: '#6366f1', // Indigo-500 (changed from Amber to Indigo for better harmony)
        shadowColor: 'rgba(99, 102, 241, 0.3)',
        shadowBlur: 10
      },
      itemStyle: {
        color: '#6366f1',
        borderWidth: 2,
        borderColor: '#fff'
      },
      data: chartData.scores
    }
  ]
}))
</script>

<style scoped>
.chart {
  height: 100%;
  width: 100%;
}
</style>