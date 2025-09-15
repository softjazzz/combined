<template>
  <div class="trend-chart">
    <div class="chart-header">
      <h4>{{ title }}</h4>
      <div class="chart-controls">
        <a-radio-group v-model:value="chartType" @change="updateChart" size="small">
          <a-radio-button value="line">折线</a-radio-button>
          <a-radio-button value="bar">柱状</a-radio-button>
          <a-radio-button value="area">面积</a-radio-button>
        </a-radio-group>
        <a-switch 
          v-model:checked="showDataLabels" 
          @change="updateChart"
          size="small"
          style="margin-left: 8px"
        />
        <span style="margin-left: 4px; font-size: 12px">数据标签</span>
      </div>
    </div>
    <div ref="chartRef" :style="{ height: `${height}px` }" class="chart-container"></div>
    <div v-if="showSummary" class="chart-summary">
      <div class="summary-item">
        <span class="label">总计:</span>
        <span class="value">{{ summary.total }}</span>
      </div>
      <div class="summary-item">
        <span class="label">平均:</span>
        <span class="value">{{ summary.average }}</span>
      </div>
      <div class="summary-item">
        <span class="label">峰值:</span>
        <span class="value">{{ summary.peak }}</span>
      </div>
      <div class="summary-item">
        <span class="label">趋势:</span>
        <span class="value" :class="getTrendClass(summary.trend)">{{ getTrendText(summary.trend) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

interface ChartDataItem {
  date: string;
  [key: string]: any;
}

interface ChartSeries {
  name: string;
  key: string;
  color?: string;
  type?: 'line' | 'bar' | 'area';
}

const props = withDefaults(defineProps<{
  title?: string;
  data: ChartDataItem[];
  series: ChartSeries[];
  height?: number;
  showSummary?: boolean;
  xAxisKey?: string;
  smooth?: boolean;
  stack?: boolean;
}>(), {
  title: '趋势图表',
  height: 300,
  showSummary: true,
  xAxisKey: 'date',
  smooth: false,
  stack: false
})

const chartRef = ref<HTMLDivElement>()
const chartType = ref<'line' | 'bar' | 'area'>('line')
const showDataLabels = ref(false)

let chart: echarts.ECharts | null = null

// 计算汇总数据
const summary = computed(() => {
  if (!props.data.length || !props.series.length) {
    return { total: 0, average: 0, peak: 0, trend: 'stable' }
  }

  const firstSeries = props.series[0]
  const values = props.data.map(item => item[firstSeries.key] || 0)
  const total = values.reduce((sum, val) => sum + val, 0)
  const average = Math.round(total / values.length * 100) / 100
  const peak = Math.max(...values)
  
  // 简单趋势计算
  const firstHalf = values.slice(0, Math.floor(values.length / 2))
  const secondHalf = values.slice(Math.floor(values.length / 2))
  const firstAvg = firstHalf.reduce((sum, val) => sum + val, 0) / firstHalf.length
  const secondAvg = secondHalf.reduce((sum, val) => sum + val, 0) / secondHalf.length
  
  let trend = 'stable'
  if (secondAvg > firstAvg * 1.1) trend = 'increasing'
  else if (secondAvg < firstAvg * 0.9) trend = 'decreasing'

  return { total, average, peak, trend }
})

// 初始化图表
const initChart = async () => {
  await nextTick()
  if (!chartRef.value) return

  if (chart) {
    chart.dispose()
  }

  chart = echarts.init(chartRef.value)
  updateChart()
}

// 更新图表
const updateChart = () => {
  if (!chart || !props.data.length) return

  const xAxisData = props.data.map(item => item[props.xAxisKey])
  
  const series = props.series.map(seriesConfig => {
    const data = props.data.map(item => item[seriesConfig.key] || 0)
    
    return {
      name: seriesConfig.name,
      type: seriesConfig.type || chartType.value,
      data,
      smooth: props.smooth,
      stack: props.stack ? 'total' : undefined,
      areaStyle: (seriesConfig.type || chartType.value) === 'area' ? {} : undefined,
      itemStyle: {
        color: seriesConfig.color
      },
      label: {
        show: showDataLabels.value,
        position: 'top'
      },
      emphasis: {
        focus: 'series'
      }
    }
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      },
      formatter: (params: any) => {
        let tooltip = `${params[0].axisValue}<br/>`
        params.forEach((param: any) => {
          tooltip += `${param.marker}${param.seriesName}: ${param.value}<br/>`
        })
        return tooltip
      }
    },
    legend: {
      data: props.series.map(s => s.name),
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: chartType.value === 'bar',
      data: xAxisData,
      axisLabel: {
        rotate: xAxisData.length > 10 ? 45 : 0
      }
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed'
        }
      }
    },
    series,
    animation: true,
    animationDuration: 1000
  }

  chart.setOption(option, true)
}

// 工具函数
const getTrendClass = (trend: string) => {
  return {
    'trend-up': trend === 'increasing',
    'trend-down': trend === 'decreasing',
    'trend-stable': trend === 'stable'
  }
}

const getTrendText = (trend: string) => {
  const trendMap: Record<string, string> = {
    increasing: '↗ 上升',
    decreasing: '↘ 下降',
    stable: '→ 平稳'
  }
  return trendMap[trend] || '→ 平稳'
}

// 响应式处理
const handleResize = () => {
  chart?.resize()
}

// 监听数据变化
watch(() => props.data, () => {
  updateChart()
}, { deep: true })

watch(() => props.series, () => {
  updateChart()
}, { deep: true })

// 生命周期
onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chart) {
    chart.dispose()
    chart = null
  }
})

// 暴露方法
defineExpose({
  refreshChart: updateChart,
  getChartInstance: () => chart
})
</script>

<style scoped>
.trend-chart {
  width: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}

.chart-controls {
  display: flex;
  align-items: center;
}

.chart-container {
  width: 100%;
  border-radius: 4px;
}

.chart-summary {
  display: flex;
  justify-content: space-around;
  margin-top: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 4px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.summary-item .label {
  font-size: 12px;
  color: #666;
}

.summary-item .value {
  font-size: 14px;
  font-weight: 500;
}

.trend-up {
  color: #ff4d4f;
}

.trend-down {
  color: #52c41a;
}

.trend-stable {
  color: #1890ff;
}
</style>
