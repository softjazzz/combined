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
import { BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

// 注册ECharts组件
use([
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  CanvasRenderer
])

interface ChartDataItem {
  department: string
  recordCount: number
  averageScore: number
  passRate: number
  color: string
}

const props = withDefaults(defineProps<{
  data?: ChartDataItem[]
  title?: string
  height?: string
  type?: 'recordCount' | 'averageScore' | 'passRate'
}>(), { data: () => [],
  title: '部门对比',
  height: '400px',
  type: 'recordCount'
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
  
  const departments = dataArray.map(item => item.department)
  const colors = dataArray.map(item => item.color)
  
  let data: number[]
  let unit: string
  let yAxisName: string
  
  switch (props.type) {
    case 'recordCount':
      data = dataArray.map(item => item.recordCount)
      unit = '个'
      yAxisName = '病案数量'
      break
    case 'averageScore':
      data = dataArray.map(item => item.averageScore)
      unit = '分'
      yAxisName = '平均评分'
      break
    case 'passRate':
      data = dataArray.map(item => item.passRate)
      unit = '%'
      yAxisName = '通过率'
      break
  }

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
        type: 'shadow'
      },
      formatter: (params: unknown) => {
        const param = params[0]
        const dataItem = props.data.find(item => item.department === param.name)
        if (!dataItem) return ''
        
        return `
          <div style="font-weight: bold; margin-bottom: 8px;">${param.name}</div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 2px; margin-right: 6px;"></span>
            病案数量: ${dataItem.recordCount}个
          </div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: #52c41a; border-radius: 2px; margin-right: 6px;"></span>
            平均评分: ${dataItem.averageScore}分
          </div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: #faad14; border-radius: 2px; margin-right: 6px;"></span>
            通过率: ${dataItem.passRate}%
          </div>
        `
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: departments,
      axisLabel: {
        fontSize: 11,
        color: '#666',
        rotate: departments.some(d => d.length > 4) ? 45 : 0
      },
      axisLine: {
        lineStyle: {
          color: '#e8e8e8'
        }
      }
    },
    yAxis: {
      type: 'value',
      name: yAxisName,
      axisLabel: {
        formatter: `{value}${unit}`,
        fontSize: 11,
        color: '#666'
      },
      axisLine: {
        lineStyle: {
          color: '#e8e8e8'
        }
      },
      splitLine: {
        lineStyle: {
          color: '#f0f0f0'
        }
      }
    },
    series: [
      {
        name: yAxisName,
        type: 'bar',
        data: data.map((value, index) => ({
          value,
          itemStyle: {
            color: colors[index]
          }
        })),
        barWidth: '60%',
        itemStyle: {
          borderRadius: [4, 4, 0, 0]
        },
        label: {
          show: true,
          position: 'top',
          formatter: `{c}${unit}`,
          fontSize: 11,
          color: '#666'
        }
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