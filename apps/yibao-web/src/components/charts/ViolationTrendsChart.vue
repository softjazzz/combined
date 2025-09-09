<template>
  <div class="qc-trend-chart">
    <div class="chart-controls mb-4">
      <div class="flex justify-between items-center">
        <div class="flex items-center space-x-4">
          <a-radio-group v-model:value="chartType" button-style="solid" size="small">
            <a-radio-button value="line">折线</a-radio-button>
            <a-radio-button value="bar">堆叠柱</a-radio-button>
          </a-radio-group>
        </div>
        <div class="flex items-center space-x-2">
          <a-tooltip title="刷新数据">
            <a-button type="text" size="small" :loading="loading" @click="reload">刷新</a-button>
          </a-tooltip>
        </div>
      </div>
    </div>

    <div class="chart-container" :style="{ height: height + 'px' }">
      <div v-if="loading" class="chart-loading"><a-spin /></div>
      <div v-else-if="error" class="chart-error">
        <a-alert type="error" show-icon :message="error" />
      </div>
      <div v-else class="chart-content">
        <div ref="chartEl" class="w-full h-full"></div>
      </div>
    </div>
  </div>
  </template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { fetchViolationTrends } from '@/services/supabaseSdk'

const props = withDefaults(defineProps<{ days?: number; height?: number }>(), { days: 30, height: 320 })

const loading = ref(false)
const error = ref('')
const chartType = ref<'line' | 'bar'>('line')
const data = ref<Array<{ date: string; block: number; warn: number; info: number }>>([])
const chartEl = ref<HTMLDivElement | null>(null)
let chart: any = null

const categories = computed(() => data.value.map(d => d.date))
const seriesBlock = computed(() => data.value.map(d => d.block))
const seriesWarn = computed(() => data.value.map(d => d.warn))
const seriesInfo = computed(() => data.value.map(d => d.info))

function getOption() {
  const base: any = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['拦截', '警告', '提醒'] },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories.value },
    yAxis: { type: 'value' }
  }
  if (chartType.value === 'bar') {
    base.series = [
      { name: '拦截', type: 'bar', stack: 'sev', data: seriesBlock.value, itemStyle: { color: '#f5222d' } },
      { name: '警告', type: 'bar', stack: 'sev', data: seriesWarn.value, itemStyle: { color: '#faad14' } },
      { name: '提醒', type: 'bar', stack: 'sev', data: seriesInfo.value, itemStyle: { color: '#1890ff' } }
    ]
  } else {
    base.series = [
      { name: '拦截', type: 'line', smooth: true, data: seriesBlock.value, itemStyle: { color: '#f5222d' } },
      { name: '警告', type: 'line', smooth: true, data: seriesWarn.value, itemStyle: { color: '#faad14' } },
      { name: '提醒', type: 'line', smooth: true, data: seriesInfo.value, itemStyle: { color: '#1890ff' } }
    ]
  }
  return base
}

async function ensureEcharts() {
  // 动态加载 ECharts（CDN），避免安装失败
  if ((window as any).echarts) return (window as any).echarts
  await new Promise<void>((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js'
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('加载 ECharts 失败'))
    document.head.appendChild(s)
  })
  return (window as any).echarts
}

async function render() {
  const echarts = await ensureEcharts()
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(getOption())
}

async function load() {
  loading.value = true; error.value = ''
  try {
    data.value = await fetchViolationTrends(props.days)
    await render()
  } catch (e: any) {
    error.value = e?.message || '加载趋势失败'
  } finally {
    loading.value = false
  }
}

function reload() { load() }

onMounted(async () => {
  await load()
  window.addEventListener('resize', onResize)
})

function onResize() { try { chart?.resize() } catch {}
}

onBeforeUnmount(() => { try { chart?.dispose() } catch {} window.removeEventListener('resize', onResize) })
</script>

<style scoped>
.chart-container { @apply relative w-full bg-white rounded-lg border; }
.chart-loading, .chart-error { @apply flex items-center justify-center h-full; }
</style>


