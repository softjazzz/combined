<template>
  <div class="radar-chart-container">
    <v-chart 
      :option="chartOption" 
      :style="{ width: width + 'px', height: height + 'px' }"
      autoresize
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

// 注册必要的组件
use([
  CanvasRenderer,
  RadarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

// Props 定义
interface Props {
  data: Array<{
    name: string
    value: number[]
    color?: string
  }>
  indicators: Array<{
    name: string
    max: number
    min?: number
  }>
  width?: number
  height?: number
  title?: string
  showLegend?: boolean
  theme?: 'light' | 'dark'
}

const props = withDefaults(defineProps<Props>(), {
  width: 400,
  height: 400,
  title: '',
  showLegend: true,
  theme: 'light'
})

interface RadarTooltipParams {
  name?: string
  value?: number[]
  color?: string
}

// 计算图表配置
const chartOption = computed(() => {
  const isDark = props.theme === 'dark'
  
  return {
    title: props.title ? {
      text: props.title,
      left: 'center',
      textStyle: {
        color: isDark ? '#fff' : '#333',
        fontSize: 16,
        fontWeight: 'bold'
      }
    } : undefined,
    
    tooltip: {
      trigger: 'item',
      formatter: (params: RadarTooltipParams) => {
        const name = params.name || ''
        const value = Array.isArray(params.value) ? params.value : []
        const color = color || '#1890ff'
        let content = `<div style="font-weight: bold; margin-bottom: 8px;">${name}</div>`
        
        value.forEach((val: number, index: number) => {
          const indicator = props.indicators[index]
          content += `<div style="margin: 4px 0;">
            <span style="color: ${color};">●</span> 
            ${indicator.name}: ${val}
          </div>`
        })
        
        return content
      },
      backgroundColor: isDark ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)',
      borderColor: isDark ? '#333' : '#ddd',
      textStyle: {
        color: isDark ? '#fff' : '#333'
      }
    },
    
    legend: props.showLegend ? {
      bottom: 20,
      data: props.data.map(item => item.name),
      textStyle: {
        color: isDark ? '#fff' : '#333'
      }
    } : undefined,
    
    radar: {
      indicator: props.indicators.map(indicator => ({
        name: indicator.name,
        max: indicator.max,
        min: indicator.min || 0
      })),
      radius: '65%',
      center: ['50%', '50%'],
      splitNumber: 5,
      name: {
        textStyle: {
          color: isDark ? '#fff' : '#333',
          fontSize: 12
        }
      },
      splitLine: {
        lineStyle: {
          color: isDark ? '#333' : '#e0e0e0'
        }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: isDark 
            ? ['rgba(255, 255, 255, 0.02)', 'rgba(255, 255, 255, 0.05)']
            : ['rgba(0, 0, 0, 0.02)', 'rgba(0, 0, 0, 0.05)']
        }
      },
      axisLine: {
        lineStyle: {
          color: isDark ? '#333' : '#e0e0e0'
        }
      }
    },
    
    series: [{
      type: 'radar',
      data: props.data.map(item => ({
        name: item.name,
        value: item.value,
        itemStyle: {
          color: item.color || '#1890ff'
        },
        lineStyle: {
          color: item.color || '#1890ff',
          width: 2
        },
        areaStyle: {
          color: item.color || '#1890ff',
          opacity: 0.1
        }
      }))
    }]
  }
})

// 监听数据变化
watch(() => props.data, () => {
  // 数据更新时会自动重新渲染
}, { deep: true })

// 暴露组件实例方法
defineExpose({
  // 可以暴露一些方法供父组件调用
  refresh: () => {
    // 刷新图表
  }
})
</script>

<style scoped>
.radar-chart-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
}

.radar-chart-container :deep(.echarts) {
  border-radius: 8px;
  background: transparent;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .radar-chart-container {
    transform: scale(0.8);
    transform-origin: center;
  }
}
</style> 

