<template>
  <div class="h-full w-full flex flex-col bg-slate-50 dark:bg-slate-900 p-6 overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
        <ArrowLeftOutlined class="text-lg" />
      </button>
      <h2 class="text-xl font-semibold text-slate-800 dark:text-white">事后分析</h2>
      <span class="text-sm text-slate-400">基于大数据的病案质量分析与趋势预测</span>
    </div>

    <!-- Time Range Selector -->
    <div class="flex items-center gap-4 mb-6">
      <div v-if="!batchId" class="text-orange-500 text-sm flex items-center gap-2">
        <WarningOutlined />
        <span>当前为演示数据，请先自行上传Excel进行分析</span>
      </div>
      <a-range-picker v-if="batchId" v-model:value="dateRange" class="w-80" />
      <a-select v-model:value="analysisType" class="w-40">
        <a-select-option value="quality">质量分析</a-select-option>
        <a-select-option value="cost">费用分析</a-select-option>
        <a-select-option value="drg">DRG分析</a-select-option>
      </a-select>
      <a-dropdown>
        <template #overlay>
          <a-menu @click="handleExport">
            <a-menu-item key="excel">
              <FileExcelOutlined /> 导出 Excel
            </a-menu-item>
            <a-menu-item key="pdf">
              <FilePdfOutlined /> 导出 PDF
            </a-menu-item>
            <a-menu-item key="word">
              <FileWordOutlined /> 导出 Word
            </a-menu-item>
          </a-menu>
        </template>
        <button class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center gap-2">
          <DownloadOutlined />
          导出报告
        </button>
      </a-dropdown>
    </div>

    <!-- KPI Cards -->
    <div class="grid grid-cols-5 gap-4 mb-6">
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">病案总数</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.summary.total_records }}</div>
        <div class="text-xs text-slate-400 mt-1">入组率: {{ (stats.summary.grouping_success_rate * 100).toFixed(1) }}%</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">平均CMI</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.summary.avg_cmi.toFixed(2) }}</div>
        <div class="text-xs text-green-600 mt-1">benchmark: 1.0</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">总权重</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">{{ stats.summary.total_weight.toFixed(1) }}</div>
        <div class="text-xs text-slate-400 mt-1">-</div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">总和盈亏</div>
        <div class="text-2xl font-bold" :class="stats.summary.total_profit >= 0 ? 'text-green-600' : 'text-red-500'">
          {{ stats.summary.total_profit.toLocaleString() }}
        </div>
        <div class="text-xs mt-1" :class="stats.summary.total_profit >= 0 ? 'text-green-600' : 'text-red-500'">
          {{ stats.summary.total_profit >= 0 ? '盈余' : '亏损' }}
        </div>
      </div>
      
      <div class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-200 dark:border-slate-700">
        <div class="text-xs text-slate-500 dark:text-slate-400 mb-1">费用消耗指数</div>
        <div class="text-2xl font-bold text-slate-800 dark:text-white">0.95</div>
        <div class="text-xs text-green-600 mt-1">↓ 0.05</div>
      </div>
    </div>

    <!-- Charts Grid -->
    <div class="grid grid-cols-2 gap-4 mb-6">
      <!-- Quality Trend -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">质量趋势分析</h3>
        <div ref="qualityTrendRef" class="h-64"></div>
      </div>
      
      <!-- Department Comparison -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">科室对比分析</h3>
        <div ref="deptComparisonRef" class="h-64"></div>
      </div>

      <!-- DRG Distribution -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">DRG 分组占比</h3>
        <div ref="drgPieRef" class="h-64"></div>
      </div>

      <!-- Cost Analysis -->
      <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
        <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">费用结构分析</h3>
        <div ref="costStructureRef" class="h-64"></div>
      </div>
    </div>

    <!-- Issue Summary -->
    <div class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700">
      <h3 class="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-4">问题汇总与建议</h3>
      <div class="space-y-3">
        <div class="flex items-start gap-3 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30">
          <ExclamationCircleOutlined class="text-red-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-red-700 dark:text-red-300 mb-1">编码准确性问题</div>
            <div class="text-sm text-red-600/80 dark:text-red-400/80">发现23例主诊断编码与临床诊断不符，建议加强编码培训</div>
          </div>
        </div>
        
        <div class="flex items-start gap-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30">
          <WarningOutlined class="text-yellow-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-yellow-700 dark:text-yellow-300 mb-1">费用消耗异常</div>
            <div class="text-sm text-yellow-600/80 dark:text-yellow-400/80">骨科和神经内科费用消耗指数偏高，需关注成本控制</div>
          </div>
        </div>
        
        <div class="flex items-start gap-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-100 dark:border-blue-900/30">
          <InfoCircleOutlined class="text-blue-500 text-lg mt-0.5" />
          <div class="flex-1">
            <div class="font-medium text-blue-700 dark:text-blue-300 mb-1">优化建议</div>
            <div class="text-sm text-blue-600/80 dark:text-blue-400/80">建议优化心内科和呼吸科的诊疗路径，可提升CMI约5%</div>
          </div>
        </div>
      </div>
    </div>
	  </div>

	  <!-- Drill Down Modal -->
	  <DrillDownModal
	    v-model:open="drillVisible"
	    :title="drillTitle"
	    :dimension="drillDimension"
	    :value="drillValue"
	    :batch-id="batchId"
	  />
	</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import DrillDownModal from './DrillDownModal.vue'
import {
  ArrowLeftOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'

const props = defineProps<{
  batchId?: string
}>()

const qualityTrendRef = ref<HTMLElement | null>(null)
const deptComparisonRef = ref<HTMLElement | null>(null)
const drgPieRef = ref<HTMLElement | null>(null)
const costStructureRef = ref<HTMLElement | null>(null)

const dateRange = ref<any>(null)
const analysisType = ref('quality')

// Drill Down State
const drillVisible = ref(false)
const drillTitle = ref('')
const drillDimension = ref('')
const drillValue = ref('')

// Statistics Data
const stats = ref({
  summary: {
    total_records: 0,
    grouping_success_rate: 0,
    avg_cmi: 0,
    total_weight: 0,
    total_fee: 0,
    total_profit: 0
  },
  mdc_distribution: [],
  drg_distribution: [], // Top 10 High Risk/Cost DRGs
  department_stats: [],
  doctor_stats: [],
  daily_trends: [],
  cost_structure: []
})

let qualityChart: echarts.ECharts | null = null
let deptChart: echarts.ECharts | null = null
let drgChart: echarts.ECharts | null = null
let costChart: echarts.ECharts | null = null

const fetchStatistics = async () => {
	    if (!props.batchId) return

	    try {
	        const res = await axios.get('/api/v1/drg/statistics', {
	            params: { batch_id: props.batchId }
	        })
	        const payload = res.data?.data ?? res.data
	        if (payload && typeof payload === 'object') {
	            stats.value = {
	                ...stats.value,
	                ...payload,
	                summary: {
	                    ...stats.value.summary,
	                    ...(payload as any).summary
	                }
	            } as any
	        }
	        updateCharts()
	    } catch (e) {
	        console.error('Failed to fetch statistics:', e)
	    }
	}

const updateCharts = () => {
    // 1. Quality/Daily Trend Chart
    if (qualityChart && stats.value.daily_trends) {
        const dates = stats.value.daily_trends.map((d: any) => d.date)
        const counts = stats.value.daily_trends.map((d: any) => d.count)
        const avgCmis = stats.value.daily_trends.map((d: any) => d.avg_cmi)
        
        qualityChart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['入组例数', 'CMI'] },
            xAxis: { data: dates },
            yAxis: [
                { type: 'value', name: '例数' },
                { type: 'value', name: 'CMI', min: 0 }
            ],
            series: [
                { name: '入组例数', type: 'bar', data: counts, yAxisIndex: 0, itemStyle: { color: '#3b82f6' } },
                { name: 'CMI', type: 'line', data: avgCmis, yAxisIndex: 1, itemStyle: { color: '#22c55e' } }
            ]
        })
    }

    // 2. Department Comparison (Profit/Cost)
    if (deptChart && stats.value.department_stats) {
        const depts = stats.value.department_stats.map((d: any) => d.dept_name)
        const profits = stats.value.department_stats.map((d: any) => d.total_profit)
        const cmis = stats.value.department_stats.map((d: any) => d.avg_cmi)
        
        deptChart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['总盈亏', '平均CMI'] },
            xAxis: { data: depts, axisLabel: { interval: 0, rotate: 30 } },
            yAxis: [
                { type: 'value', name: '盈亏' },
                { type: 'value', name: 'CMI' }
            ],
            series: [
                { 
                    name: '总盈亏', 
                    type: 'bar', 
                    data: profits, 
                    itemStyle: { 
                        color: (params: any) => {
                            return params.value >= 0 ? '#22c55e' : '#ef4444'
                        }
                    } 
                },
                { name: '平均CMI', type: 'line', data: cmis, yAxisIndex: 1, itemStyle: { color: '#f59e0b' } }
            ]
        })
    }

    // 3. DRG Distribution (Top 10) -> Changed to MDC Pie for simpler view as per PRD
    if (drgChart && stats.value.mdc_distribution) {
        const data = stats.value.mdc_distribution.map((d: any) => ({
            value: d.count,
            name: d.mdc
        }))
        
        drgChart.setOption({
            tooltip: { trigger: 'item' },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                data: data
            }]
        })
    }
    
    // 4. Cost Structure
    if (costChart && stats.value.cost_structure) {
        const labels = ['药品', '耗材', '检查', '治疗']
        const s = stats.value.cost_structure
        const data = [s.drug, s.material, s.exam, s.treatment]
        
        costChart.setOption({
             xAxis: { type: 'value' },
             yAxis: { type: 'category', data: labels },
             series: [{
                 type: 'bar',
                 data: data,
                 itemStyle: { color: '#8b5cf6' }
             }]
        })
    }
}

// Event Handlers for Drill Down
const setupChartEvents = () => {
    if (deptChart) {
        deptChart.on('click', (params: any) => {
            openDrillDown('department', params.name)
        })
    }
    if (drgChart) {
        drgChart.on('click', (params: any) => {
             // params.name is MDC code like "MDCA"
            openDrillDown('mdc', params.name)
        })
    }
}

const openDrillDown = (dimension: string, value: string) => {
    drillDimension.value = dimension
    drillValue.value = value
    drillTitle.value = `${value} - 病例明细`
    drillVisible.value = true
}

onMounted(() => {
  // Initialize Charts
  if (qualityTrendRef.value) qualityChart = echarts.init(qualityTrendRef.value)
  if (deptComparisonRef.value) deptChart = echarts.init(deptComparisonRef.value)
  if (drgPieRef.value) drgChart = echarts.init(drgPieRef.value)
  if (costStructureRef.value) costChart = echarts.init(costStructureRef.value)
  
  setupChartEvents()

  // Initial Fetch if batchId exists
  if (props.batchId) {
      fetchStatistics()
  } else {
      // Load mock data if no batchId provided? 
      // Or just leave empty. For now we leave empty/zeros but charts might need empty option
      stats.value.summary.total_records = 1258 // Mock fallback for demo look if user opens page directly without upload
      initMockCharts() // Keep original mock look if no upload
  }
})

watch(() => props.batchId, (newVal) => {
    if (newVal) {
        fetchStatistics()
    }
})

const initMockCharts = () => {
    // Original mock initialization code (simplified for brevity, assumes original functionality if needed)
    // But since we are replacing it, we can just clear it or show empty state.
    // However, to keep the UI looking good before upload, maybe we keep the static data?
    // Let's keep the user experience smooth: if no batchId, show the static data I replaced.
    // Actually, I replaced the template bindings to use `stats.value`. 
    // So I should populate `stats.value` with mock data if no batchId.
    
    stats.value = {
        summary: {
           total_records: 1258,
           grouping_success_rate: 0.98,
           avg_cmi: 1.08,
           total_weight: 1540.5,
           total_fee: 5400000,
           total_profit: 125000
        },
        mdc_distribution: [
            { mdc: 'MDCA', count: 125 },
            { mdc: 'MDCB', count: 98 },
            { mdc: 'MDCC', count: 87 }
        ],
        drg_distribution: [],
        department_stats: [
            { dept_name: '心内科', total_profit: 25000, avg_cmi: 1.15 },
             { dept_name: '呼吸科', total_profit: -5000, avg_cmi: 0.98 }
        ],
        doctor_stats: [],
        daily_trends: [
            { date: '1月', count: 120, avg_cmi: 1.02 },
            { date: '2月', count: 135, avg_cmi: 1.05 }
        ],
        cost_structure: {
            drug: 3500, material: 3200, exam: 2800, treatment: 2200
        }
    } as any
    updateCharts()
}

// Export handler - use fetch to properly go through proxy
const handleExport = async ({ key }: { key: string }) => {
    const formatMap: Record<string, { ext: string; mime: string; name: string }> = {
        excel: { ext: 'xlsx', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', name: 'Excel' },
        pdf: { ext: 'pdf', mime: 'application/pdf', name: 'PDF' },
        word: { ext: 'docx', mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', name: 'Word' }
    }
    
    const format = formatMap[key]
    if (!format) return
    
    // Build URL with optional batch_id parameter
    let url = `/api/v1/drg/export/${key}`
    if (props.batchId) {
        url += `?batch_id=${props.batchId}`
    }
    
    const hideLoading = message.loading(`正在生成 ${format.name} 报告...`, 0)
    
    try {
        const response = await axios.get(url, { responseType: 'blob' })
        const blob = new Blob([response.data], { type: format.mime })
        const downloadUrl = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = downloadUrl
        link.download = `drg_report_${props.batchId || 'all'}.${format.ext}`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(downloadUrl)
        message.success(`${format.name} 报告导出成功`)
    } catch (error: any) {
        console.error('Export failed:', error)
        message.error(error.response?.data?.detail || `${format.name} 导出失败`)
    } finally {
        hideLoading()
    }
}

onUnmounted(() => {
  qualityChart?.dispose()
  deptChart?.dispose()
  drgChart?.dispose()
  costChart?.dispose()
})
</script>
