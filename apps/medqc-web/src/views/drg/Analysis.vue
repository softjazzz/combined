<template>
  <div class="drg-analysis">
    <a-page-header
      title="事后分析"
      sub-title="DRG 分组统计与绩效分析"
      @back="() => $router.back()"
    />

    <div class="content-wrapper">
      <!-- 时间范围选择 -->
      <a-card :bordered="false" style="margin-bottom: 16px">
        <a-space>
          <span>统计时间范围：</span>
          <a-range-picker
            v-model:value="dateRange"
            :format="dateFormat"
            :placeholder="['开始日期', '结束日期']"
            @change="loadAnalysisData"
          />
          <a-button type="primary" @click="loadAnalysisData">
            <ReloadOutlined />
            刷新数据
          </a-button>
        </a-space>
      </a-card>

      <!-- 统计概览卡片 -->
      <a-row :gutter="16" style="margin-bottom: 16px">
        <a-col :span="6">
          <a-card>
            <a-statistic title="总病例数" :value="statistics.totalCases" suffix="例">
              <template #prefix><FileTextOutlined style="color: #1890ff" /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="总盈余"
              :value="statistics.totalProfit"
              :precision="2"
              suffix="元"
              :value-style="{ color: statistics.totalProfit >= 0 ? '#3f8600' : '#cf1322' }"
            >
              <template #prefix>
                <component :is="statistics.totalProfit >= 0 ? RiseOutlined : FallOutlined" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic title="平均费用消耗率" :value="statistics.avgCostRate" suffix="%" :precision="1">
              <template #prefix><DollarOutlined style="color: #faad14" /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic title="DRG 分组数" :value="statistics.drgGroupCount" suffix="组">
              <template #prefix><AppstoreOutlined style="color: #52c41a" /></template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- 图表区域 -->
      <a-row :gutter="16" style="margin-bottom: 16px">
        <!-- DRG 分布饼图 -->
        <a-col :span="12">
          <a-card title="DRG 分组分布" :bordered="false">
            <div ref="drgDistributionChart" style="width: 100%; height: 400px"></div>
          </a-card>
        </a-col>

        <!-- 盈亏分析柱状图 -->
        <a-col :span="12">
          <a-card title="TOP10 DRG 盈亏分析" :bordered="false">
            <div ref="profitAnalysisChart" style="width: 100%; height: 400px"></div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 费用消耗率趋势 -->
      <a-card title="费用消耗率趋势" :bordered="false" style="margin-bottom: 16px">
        <div ref="costRateTrendChart" style="width: 100%; height: 300px"></div>
      </a-card>

      <!-- 科室绩效排名 -->
      <a-card title="科室绩效排名" :bordered="false">
        <a-table
          :columns="departmentColumns"
          :data-source="departmentPerformance"
          :loading="loading"
          :pagination="{ pageSize: 10 }"
          row-key="department"
        >
          <template #profitMargin="{ record }">
            <span :style="{ color: record.profitMargin >= 0 ? '#3f8600' : '#cf1322' }">
              {{ formatCurrency(record.profitMargin) }}
            </span>
          </template>
          <template #costRate="{ record }">
            <a-progress
              :percent="record.costRate"
              :status="record.costRate > 120 ? 'exception' : record.costRate > 100 ? 'normal' : 'success'"
            />
          </template>
        </a-table>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import type { Dayjs } from 'dayjs'
import {
  FileTextOutlined,
  DollarOutlined,
  AppstoreOutlined,
  RiseOutlined,
  FallOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { formatCurrency, getChartColor } from '@/utils/drg'
import { drgApi } from '@/api/drg'

/** 日期范围格式 */
const dateFormat = 'YYYY-MM-DD'

/** 选择的日期范围 */
const dateRange = ref<[Dayjs, Dayjs] | null>(null)

/** 加载状态 */
const loading = ref(false)

/** 统计数据 */
const statistics = reactive({
  totalCases: 0,
  totalProfit: 0,
  avgCostRate: 0,
  drgGroupCount: 0
})

/** ECharts 实例 */
const drgDistributionChart = ref<HTMLElement>()
const profitAnalysisChart = ref<HTMLElement>()
const costRateTrendChart = ref<HTMLElement>()
let drgDistributionChartInstance: echarts.ECharts | null = null
let profitAnalysisChartInstance: echarts.ECharts | null = null
let costRateTrendChartInstance: echarts.ECharts | null = null

/** DRG 分布数据 */
interface DRGDistributionItem {
  drg_code: string
  drg_name: string
  case_count: number
  percentage: number
}
const drgDistribution = ref<DRGDistributionItem[]>([])

/** 盈亏分析数据 */
interface ProfitAnalysisItem {
  drg_code: string
  drg_name: string
  total_profit: number
  case_count: number
  avg_profit: number
}
const profitAnalysis = ref<ProfitAnalysisItem[]>([])

/** 费用消耗率趋势数据 */
interface CostRateTrendItem {
  date: string
  cost_rate: number
}
const costRateTrend = ref<CostRateTrendItem[]>([])

/** 科室绩效数据 */
interface DepartmentPerformanceItem {
  department: string
  caseCount: number
  totalRevenue: number
  totalCost: number
  profitMargin: number
  costRate: number
}
const departmentPerformance = ref<DepartmentPerformanceItem[]>([])

/** 科室绩效表格列定义 */
const departmentColumns = [
  { title: '科室', dataIndex: 'department', width: 150 },
  { title: '病例数', dataIndex: 'caseCount', width: 100, sorter: (a: any, b: any) => a.caseCount - b.caseCount },
  {
    title: '总收入',
    dataIndex: 'totalRevenue',
    width: 150,
    customRender: ({ text }: any) => formatCurrency(text),
    sorter: (a: any, b: any) => a.totalRevenue - b.totalRevenue
  },
  {
    title: '总成本',
    dataIndex: 'totalCost',
    width: 150,
    customRender: ({ text }: any) => formatCurrency(text),
    sorter: (a: any, b: any) => a.totalCost - b.totalCost
  },
  {
    title: '盈亏',
    dataIndex: 'profitMargin',
    width: 150,
    slots: { customRender: 'profitMargin' },
    sorter: (a: any, b: any) => a.profitMargin - b.profitMargin
  },
  {
    title: '费用消耗率',
    dataIndex: 'costRate',
    width: 200,
    slots: { customRender: 'costRate' },
    sorter: (a: any, b: any) => a.costRate - b.costRate
  }
]

/** 初始化 DRG 分布饼图 */
const initDRGDistributionChart = () => {
  if (!drgDistributionChart.value) return

  drgDistributionChartInstance = echarts.init(drgDistributionChart.value)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      type: 'scroll'
    },
    series: [
      {
        name: 'DRG 分组',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 20,
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: []
      }
    ]
  }

  drgDistributionChartInstance.setOption(option)
}

/** 更新 DRG 分布饼图数据 */
const updateDRGDistributionChart = () => {
  if (!drgDistributionChartInstance) return

  const data = drgDistribution.value.map((item, index) => ({
    name: `${item.drg_code} ${item.drg_name}`,
    value: item.case_count,
    itemStyle: { color: getChartColor(index) }
  }))

  drgDistributionChartInstance.setOption({
    series: [{ data }]
  })
}

/** 初始化盈亏分析柱状图 */
const initProfitAnalysisChart = () => {
  if (!profitAnalysisChart.value) return

  profitAnalysisChartInstance = echarts.init(profitAnalysisChart.value)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: (params: any) => {
        const item = params[0]
        return `${item.name}<br/>总盈亏: ${formatCurrency(item.value)}`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: [],
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
      name: '盈亏金额(元)',
      axisLabel: {
        formatter: (value: number) => {
          if (Math.abs(value) >= 10000) {
            return `${(value / 10000).toFixed(1)}万`
          }
          return value.toString()
        }
      }
    },
    series: [
      {
        name: '盈亏',
        type: 'bar',
        data: [],
        itemStyle: {
          color: (params: any) => {
            return params.value >= 0 ? '#3f8600' : '#cf1322'
          }
        }
      }
    ]
  }

  profitAnalysisChartInstance.setOption(option)
}

/** 更新盈亏分析柱状图数据 */
const updateProfitAnalysisChart = () => {
  if (!profitAnalysisChartInstance) return

  const xData = profitAnalysis.value.map(item => `${item.drg_code}\n${item.drg_name}`)
  const yData = profitAnalysis.value.map(item => item.total_profit)

  profitAnalysisChartInstance.setOption({
    xAxis: { data: xData },
    series: [{ data: yData }]
  })
}

/** 初始化费用消耗率趋势折线图 */
const initCostRateTrendChart = () => {
  if (!costRateTrendChart.value) return

  costRateTrendChartInstance = echarts.init(costRateTrendChart.value)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const item = params[0]
        return `${item.name}<br/>费用消耗率: ${item.value}%`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: []
    },
    yAxis: {
      type: 'value',
      name: '费用消耗率(%)',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    visualMap: {
      show: false,
      pieces: [
        { lte: 100, color: '#3f8600' },
        { gt: 100, lte: 120, color: '#faad14' },
        { gt: 120, color: '#cf1322' }
      ],
      outOfRange: {
        color: '#999'
      }
    },
    series: [
      {
        name: '费用消耗率',
        type: 'line',
        smooth: true,
        data: [],
        markLine: {
          data: [
            { yAxis: 100, label: { formatter: '基准线' }, lineStyle: { color: '#3f8600' } }
          ]
        },
        areaStyle: {
          opacity: 0.3
        }
      }
    ]
  }

  costRateTrendChartInstance.setOption(option)
}

/** 更新费用消耗率趋势折线图数据 */
const updateCostRateTrendChart = () => {
  if (!costRateTrendChartInstance) return

  const xData = costRateTrend.value.map(item => item.date)
  const yData = costRateTrend.value.map(item => item.cost_rate)

  costRateTrendChartInstance.setOption({
    xAxis: { data: xData },
    series: [{ data: yData }]
  })
}

/** 加载分析数据 */
const loadAnalysisData = async () => {
  loading.value = true
  try {
    // 模拟数据（实际应调用后端 API）
    // TODO: 待后端 API 实现后替换为真实调用

    // 统计概览
    statistics.totalCases = 1250
    statistics.totalProfit = 3250000
    statistics.avgCostRate = 95.8
    statistics.drgGroupCount = 45

    // DRG 分布（TOP 10）
    drgDistribution.value = [
      { drg_code: 'FB19', drg_name: '急性心肌梗死伴严重并发症', case_count: 156, percentage: 12.48 },
      { drg_code: 'IR15', drg_name: '肺炎伴合并症', case_count: 132, percentage: 10.56 },
      { drg_code: 'EB13', drg_name: '脑梗死伴合并症', case_count: 98, percentage: 7.84 },
      { drg_code: 'JR25', drg_name: '肠梗阻手术', case_count: 87, percentage: 6.96 },
      { drg_code: 'IB13', drg_name: 'COPD伴感染', case_count: 76, percentage: 6.08 },
      { drg_code: 'GB19', drg_name: '胆囊炎手术', case_count: 65, percentage: 5.2 },
      { drg_code: 'RB11', drg_name: '泌尿系感染', case_count: 54, percentage: 4.32 },
      { drg_code: 'HB11', drg_name: '高血压并发症', case_count: 43, percentage: 3.44 },
      { drg_code: 'KC25', drg_name: '骨折手术', case_count: 38, percentage: 3.04 },
      { drg_code: '其他', drg_name: '', case_count: 501, percentage: 40.08 }
    ]

    // 盈亏分析（TOP 10）
    profitAnalysis.value = [
      { drg_code: 'FB19', drg_name: '心肌梗死', total_profit: 850000, case_count: 156, avg_profit: 5448.72 },
      { drg_code: 'IR15', drg_name: '肺炎', total_profit: 420000, case_count: 132, avg_profit: 3181.82 },
      { drg_code: 'EB13', drg_name: '脑梗死', total_profit: 650000, case_count: 98, avg_profit: 6632.65 },
      { drg_code: 'JR25', drg_name: '肠梗阻', total_profit: -120000, case_count: 87, avg_profit: -1379.31 },
      { drg_code: 'IB13', drg_name: 'COPD', total_profit: 180000, case_count: 76, avg_profit: 2368.42 },
      { drg_code: 'GB19', drg_name: '胆囊炎', total_profit: 320000, case_count: 65, avg_profit: 4923.08 },
      { drg_code: 'RB11', drg_name: '泌尿系感染', total_profit: 95000, case_count: 54, avg_profit: 1759.26 },
      { drg_code: 'HB11', drg_name: '高血压', total_profit: -85000, case_count: 43, avg_profit: -1976.74 },
      { drg_code: 'KC25', drg_name: '骨折', total_profit: 450000, case_count: 38, avg_profit: 11842.11 },
      { drg_code: 'MD31', drg_name: '糖尿病', total_profit: 220000, case_count: 32, avg_profit: 6875.0 }
    ]

    // 费用消耗率趋势（最近30天）
    const today = new Date()
    costRateTrend.value = []
    for (let i = 29; i >= 0; i--) {
      const date = new Date(today)
      date.setDate(date.getDate() - i)
      const dateStr = date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
      const baseRate = 95 + Math.sin(i / 5) * 10 + (Math.random() - 0.5) * 5
      costRateTrend.value.push({
        date: dateStr,
        cost_rate: parseFloat(baseRate.toFixed(1))
      })
    }

    // 科室绩效
    departmentPerformance.value = [
      {
        department: '心内科',
        caseCount: 245,
        totalRevenue: 8500000,
        totalCost: 7200000,
        profitMargin: 1300000,
        costRate: 84.7
      },
      {
        department: '神经内科',
        caseCount: 198,
        totalRevenue: 6800000,
        totalCost: 6500000,
        profitMargin: 300000,
        costRate: 95.6
      },
      {
        department: '呼吸内科',
        caseCount: 187,
        totalRevenue: 5200000,
        totalCost: 4800000,
        profitMargin: 400000,
        costRate: 92.3
      },
      {
        department: '普外科',
        caseCount: 156,
        totalRevenue: 7200000,
        totalCost: 6000000,
        profitMargin: 1200000,
        costRate: 83.3
      },
      {
        department: '骨科',
        caseCount: 142,
        totalRevenue: 9800000,
        totalCost: 8200000,
        profitMargin: 1600000,
        costRate: 83.7
      },
      {
        department: '消化内科',
        caseCount: 128,
        totalRevenue: 3800000,
        totalCost: 3600000,
        profitMargin: 200000,
        costRate: 94.7
      },
      {
        department: '泌尿外科',
        caseCount: 95,
        totalRevenue: 4200000,
        totalCost: 4500000,
        profitMargin: -300000,
        costRate: 107.1
      },
      {
        department: '肾内科',
        caseCount: 78,
        totalRevenue: 2800000,
        totalCost: 3200000,
        profitMargin: -500000,
        costRate: 114.3
      }
    ].sort((a, b) => b.profitMargin - a.profitMargin)

    // 更新图表
    await nextTick()
    updateDRGDistributionChart()
    updateProfitAnalysisChart()
    updateCostRateTrendChart()

    message.success('数据加载成功')
  } catch (error) {
    console.error('加载分析数据失败:', error)
    message.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

/** 窗口尺寸变化时调整图表大小 */
const handleResize = () => {
  drgDistributionChartInstance?.resize()
  profitAnalysisChartInstance?.resize()
  costRateTrendChartInstance?.resize()
}

onMounted(async () => {
  // 初始化图表
  await nextTick()
  initDRGDistributionChart()
  initProfitAnalysisChart()
  initCostRateTrendChart()

  // 加载数据
  loadAnalysisData()

  // 监听窗口尺寸变化
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  // 销毁图表实例
  drgDistributionChartInstance?.dispose()
  profitAnalysisChartInstance?.dispose()
  costRateTrendChartInstance?.dispose()

  // 移除事件监听
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped lang="scss">
.drg-analysis {
  .content-wrapper {
    padding: 16px;
  }
}
</style>
