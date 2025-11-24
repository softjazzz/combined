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
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  GraphicComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

// 注册ECharts组件
use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  GraphicComponent,
  CanvasRenderer
])

interface ChartDataItem {
  period: string
  recordCount: number
  averageScore: number
  passRate: number
}

const props = defineProps({
  data: {
    type: Array as PropType<ChartDataItem[]>,
    required: true,
    default: () => []
  },
  title: {
    type: String,
    default: '趋势分析'
  },
  height: {
    type: String,
    default: '400px'
  },
  showDataZoom: {
    type: Boolean,
    default: false
  }
})

const chartOption = computed(() => {
  // 确保 data 是数组
  const dataArray = Array.isArray(props.data) ? props.data : []
  
  if (dataArray.length === 0) {
    return {
      title: {
        text: props.title,
        left: 'center'
      },
      graphic: {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: '暂无数据',
          fontSize: 16,
          fill: '#999'
        }
      }
    }
  }
  
  const periods = dataArray.map(item => item.period)
  const recordCounts = dataArray.map(item => item.recordCount)
  const averageScores = dataArray.map(item => item.averageScore)
  const passRates = dataArray.map(item => item.passRate)

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
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: (params: unknown) => {
        let result = `<div style="font-weight: bold; margin-bottom: 8px;">${params[0].axisValue}</div>`
        params.forEach((param: unknown) => {
          const value = param.seriesName === '病案数量' 
            ? `${param.value}个`
            : param.seriesName === '平均评分'
            ? `${param.value}分`
            : `${param.value}%`
          result += `
            <div style="margin-bottom: 4px;">
              <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 50%; margin-right: 6px;"></span>
              ${param.seriesName}: ${value}
            </div>
          `
        })
        return result
      }
    },
    legend: {
      data: ['病案数量', '平均评分', '通过率'],
      top: 40,
      textStyle: {
        fontSize: 12
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: props.showDataZoom ? '15%' : '8%',
      top: '20%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: periods,
      axisLabel: {
        fontSize: 11,
        color: '#666'
      },
      axisLine: {
        lineStyle: {
          color: '#e8e8e8'
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '病案数量',
        position: 'left',
        axisLabel: {
          formatter: '{value}个',
          fontSize: 11,
          color: '#666'
        },
        axisLine: {
          lineStyle: {
            color: '#1890ff'
          }
        },
        splitLine: {
          lineStyle: {
            color: '#f0f0f0'
          }
        }
      },
      {
        type: 'value',
        name: '评分/通过率',
        position: 'right',
        axisLabel: {
          formatter: '{value}',
          fontSize: 11,
          color: '#666'
        },
        axisLine: {
          lineStyle: {
            color: '#52c41a'
          }
        },
        splitLine: {
          show: false
        }
      }
    ],
    series: [
      {
        name: '病案数量',
        type: 'line',
        yAxisIndex: 0,
        data: recordCounts,
        smooth: true,
        lineStyle: {
          width: 3,
          color: '#1890ff'
        },
        itemStyle: {
          color: '#1890ff'
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
              { offset: 1, color: 'rgba(24, 144, 255, 0.1)' }
            ]
          }
        }
      },
      {
        name: '平均评分',
        type: 'line',
        yAxisIndex: 1,
        data: averageScores,
        smooth: true,
        lineStyle: {
          width: 3,
          color: '#52c41a'
        },
        itemStyle: {
          color: '#52c41a'
        }
      },
      {
        name: '通过率',
        type: 'line',
        yAxisIndex: 1,
        data: passRates,
        smooth: true,
        lineStyle: {
          width: 3,
          color: '#faad14'
        },
        itemStyle: {
          color: '#faad14'
        }
      }
    ],
    dataZoom: props.showDataZoom ? [
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 20,
        bottom: 20
      }
    ] : undefined
  }
})
</script>

<style scoped>
.chart-container {
  @apply w-full h-full;
}
</style> 