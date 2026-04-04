<template>
  <div class="drg-analysis">
    <a-page-header
      title="事后分析"
      sub-title="DRG 分组统计与绩效分析"
      @back="router.back"
    />

    <div class="content-wrapper">
      <!-- 数据集管理面板 -->
      <DatasetUploadPanel @data-changed="loadAnalysisData" />

      <!-- 维度与时间筛选 -->
      <a-card
        :bordered="false"
        style="margin-bottom: 16px"
      >
        <a-row
          justify="space-between"
          align="middle"
        >
          <a-col>
            <a-space size="large">
              <span style="font-weight: bold; margin-right: 8px">分析维度:</span>
              <a-radio-group
                v-model:value="dimension"
                button-style="solid"
                @change="loadAnalysisData"
              >
                <a-radio-button value="hospital">
                  全院概览
                </a-radio-button>
                <a-radio-button value="department">
                  科室分析
                </a-radio-button>
                <a-radio-button value="ward">
                  病区分析
                </a-radio-button>
                <a-radio-button value="drg">
                  DRG组分析
                </a-radio-button>
                <a-radio-button value="person">
                  个人绩效
                </a-radio-button>
              </a-radio-group>
            </a-space>
          </a-col>
          <a-col>
            <a-space>
              <span>统计时间：</span>
              <a-range-picker
                v-model:value="dateRange"
                :format="dateFormat"
                :allow-clear="false"
                @change="loadAnalysisData"
              />
              <a-dropdown>
                <template #overlay>
                  <a-menu @click="handleExportMenu">
                    <a-menu-item key="excel">
                      <FileExcelOutlined /> 导出 Excel
                    </a-menu-item>
                    <a-menu-item key="pdf">
                      <FilePdfOutlined /> 导出 PDF 报告
                    </a-menu-item>
                    <a-menu-item key="docx">
                      <FileWordOutlined /> 导出 DOCX 报告
                    </a-menu-item>
                  </a-menu>
                </template>
                <a-button :loading="exporting">
                  <DownloadOutlined /> 导出报表 <DownOutlined />
                </a-button>
              </a-dropdown>
              <a-button
                type="primary"
                :loading="loading"
                @click="loadAnalysisData"
              >
                <template #icon>
                  <ReloadOutlined />
                </template>
                刷新
              </a-button>
            </a-space>
          </a-col>
        </a-row>
      </a-card>

      <!-- 统计概览卡片 -->
      <a-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <a-col :span="6">
          <a-card :loading="loading">
            <a-statistic
              title="总病例数"
              :value="statistics.totalCases"
              suffix="例"
            >
              <template #prefix>
                <FileTextOutlined style="color: #1890ff" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card :loading="loading">
            <a-statistic
              title="总盈余"
              :value="statistics.totalProfit"
              :precision="2"
              suffix="元"
              :value-style="{ color: statistics.totalProfit >= 0 ? '#3f8600' : '#cf1322' }"
            >
              <template #prefix>
                <RiseOutlined v-if="statistics.totalProfit >= 0" />
                <FallOutlined v-else />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card :loading="loading">
            <a-statistic
              title="平均费用消耗率"
              :value="statistics.avgCostRate"
              suffix="%"
              :precision="1"
            >
              <template #prefix>
                <DollarOutlined style="color: #faad14" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card :loading="loading">
            <a-statistic
              title="DRG 分组数"
              :value="statistics.drgGroupCount"
              suffix="组"
            >
              <template #prefix>
                <AppstoreOutlined style="color: #52c41a" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <a-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <a-col :span="8">
          <a-card :loading="loading">
            <a-statistic
              title="低风险组死亡率"
              :value="statistics.lowRiskMortalityRate"
              :precision="2"
              suffix="%"
            />
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card :loading="loading">
            <a-statistic
              title="时间消耗指数"
              :value="statistics.timeConsumptionIndex"
              :precision="3"
            />
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card :loading="loading">
            <a-statistic
              title="医保盈亏"
              :value="statistics.insuranceProfitLoss"
              :precision="2"
              suffix="元"
              :value-style="{ color: statistics.insuranceProfitLoss >= 0 ? '#3f8600' : '#cf1322' }"
            />
          </a-card>
        </a-col>
      </a-row>

      <!-- 图表区域 -->
      <a-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <!-- DRG 分布饼图 -->
        <a-col :span="12">
          <a-card
            title="DRG 分组分布"
            :bordered="false"
            :loading="loading"
          >
            <div style="width: 100%; height: 400px">
              <v-chart
                class="chart"
                :option="drgDistributionOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>

        <!-- 盈亏分析柱状图 -->
        <a-col :span="12">
          <a-card
            title="费用构成分析"
            :bordered="false"
            :loading="loading"
          >
            <div style="width: 100%; height: 400px">
              <v-chart
                class="chart"
                :option="profitAnalysisOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 费用消耗率趋势 -->
      <a-card
        title="效能指标趋势"
        :bordered="false"
        style="margin-bottom: 16px"
        :loading="loading"
      >
        <div style="width: 100%; height: 300px">
          <v-chart
            class="chart"
            :option="costRateTrendOption"
            autoresize
          />
        </div>
      </a-card>

      <a-card
        title="分析结论（可追溯）"
        :bordered="false"
        style="margin-bottom: 16px"
        :loading="loading"
      >
        <a-empty
          v-if="conclusions.length === 0"
          description="暂无分析结论"
        />
        <a-list
          v-else
          size="small"
          :data-source="conclusions"
        >
          <template #renderItem="{ item }">
            <a-list-item>{{ item }}</a-list-item>
          </template>
        </a-list>
      </a-card>

      <!-- 医生绩效对比 (仅在医生维度显示) -->
      <a-row
        v-if="dimension === 'person'"
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <a-col :span="12">
          <a-card
            title="医生绩效雷达图"
            :bordered="false"
            :loading="loading"
          >
            <div style="width: 100%; height: 380px">
              <v-chart
                class="chart"
                :option="doctorRadarOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card
            title="医生 vs 科室平均对比"
            :bordered="false"
            :loading="loading"
          >
            <div style="width: 100%; height: 380px">
              <v-chart
                class="chart"
                :option="doctorBenchmarkOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 详细数据表格 -->
      <a-card
        :title="tableTitle"
        :bordered="false"
      >
        <template #extra>
          <a-button
            type="link"
            size="small"
            @click="handleExportClick"
          >
            <DownloadOutlined /> 导出Excel
          </a-button>
        </template>
        <a-table
          :columns="dynamicColumns"
          :data-source="tableData"
          :loading="loading"
          :pagination="{ pageSize: 10, showSizeChanger: true }"
          row-key="id"
        />
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'DrgAnalysisView' })
import { ref, reactive, computed, onMounted, nextTick, h } from 'vue'
import { useRouter } from 'vue-router'
import { message, Progress } from 'ant-design-vue'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import type { TableColumnsType } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  FileTextOutlined,
  DollarOutlined,
  AppstoreOutlined,
  RiseOutlined,
  FallOutlined,
  ReloadOutlined,
  DownloadOutlined,
  DownOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  FileWordOutlined,
} from '@ant-design/icons-vue'
import { saveAs } from 'file-saver'
import { exportComprehensiveReport } from '@/utils/export'

// ECharts imports
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart, RadarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import type { EChartsOption } from 'echarts'

import { formatCurrency, getChartColor } from '@/utils/drg'
import { drgApi } from '@/api/drg'
import type { AnalysisDimension, AnalysisTableItem } from '@/types/drg-analysis'
import DatasetUploadPanel from '@/components/drg/DatasetUploadPanel.vue'

// Register ECharts components
use([
  CanvasRenderer,
  PieChart,
  BarChart,
  LineChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
])

/** 日期范围格式 */
const dateFormat = 'YYYY-MM-DD'

/** Router 实例 */
const router = useRouter()

/** 选择的维度 */
const dimension = ref<AnalysisDimension>('hospital')

/** 选择的日期范围 */
const dateRange = ref<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()])

/** 加载状态 */
const loading = ref(false)

/** 统计概览数据 */
const statistics = reactive({
  totalCases: 0,
  totalProfit: 0,
  avgCostRate: 0,
  drgGroupCount: 0,
  lowRiskMortalityRate: 0,
  timeConsumptionIndex: 0,
  insuranceProfitLoss: 0,
})

/** 表格数据 */
const tableData = ref<AnalysisTableItem[]>([])
const conclusions = ref<string[]>([])

/** 图表配置 */
const drgDistributionOption = ref<EChartsOption>({})
const profitAnalysisOption = ref<EChartsOption>({})
const costRateTrendOption = ref<EChartsOption>({})
const doctorRadarOption = ref<EChartsOption>({})
const doctorBenchmarkOption = ref<EChartsOption>({})

/** 表格标题 */
const tableTitle = computed(() => {
  const map: Record<AnalysisDimension, string> = {
    hospital: '全院绩效概览',
    department: '科室明细数据',
    ward: '病区明细数据',
    drg: 'DRG组详细数据',
    person: '个人绩效排名',
  }
  return map[dimension.value]
})

/** 动态表格列定义 */
const dynamicColumns = computed<TableColumnsType<AnalysisTableItem>>(() => {
  const nameTitleMap: Record<AnalysisDimension, string> = {
    hospital: '科室名称',
    department: '项目名称',
    ward: '病区名称',
    drg: 'DRG组名称',
    person: '个人姓名',
  }

  return [
    { title: nameTitleMap[dimension.value], dataIndex: 'name', width: 180 },
    {
      title: '入组病例数',
      dataIndex: 'caseCount',
      width: 120,
      sorter: (a, b) => a.caseCount - b.caseCount,
    },
    { title: 'CMI值', dataIndex: 'cmi', width: 100, sorter: (a, b) => (a.cmi ?? 0) - (b.cmi ?? 0) },
    {
      title: '总收入',
      dataIndex: 'totalRevenue',
      width: 150,
      customRender: ({ record }) => formatCurrency(record.totalRevenue),
      sorter: (a, b) => a.totalRevenue - b.totalRevenue,
    },
    {
      title: '总成本',
      dataIndex: 'totalCost',
      width: 150,
      customRender: ({ record }) => formatCurrency(record.totalCost),
      sorter: (a, b) => a.totalCost - b.totalCost,
    },
    {
      title: '盈亏金额',
      dataIndex: 'profit',
      width: 150,
      customRender: ({ record }) =>
        h(
          'span',
          { style: { color: record.profit >= 0 ? '#3f8600' : '#cf1322' } },
          formatCurrency(record.profit),
        ),
      sorter: (a, b) => a.profit - b.profit,
    },
    {
      title: '费用消耗指数',
      dataIndex: 'costRate',
      width: 220,
      customRender: ({ record }) =>
        h(Progress, {
          percent: Math.min(record.costRate * 100, 100),
          format: () => `${(record.costRate * 100).toFixed(1)}%`,
          status:
            record.costRate > 1.2 ? 'exception' : record.costRate > 1.0 ? 'normal' : 'success',
          size: 'small',
        }),
      sorter: (a, b) => a.costRate - b.costRate,
    },
  ]
})

// ================== 导出逻辑 ==================

const exporting = ref(false)
type ExportFormat = 'excel' | 'pdf' | 'docx'
const useMockData = (import.meta as any).env?.VITE_USE_DRG_MOCK !== 'false'

const dimensionLabelMap: Record<string, string> = {
  hospital: '全院概览',
  department: '科室分析',
  ward: '病区分析',
  drg: 'DRG组分析',
  person: '个人绩效',
}

const handleExportMenu = ({ key }: MenuInfo): void => {
  void handleExport(key as ExportFormat)
}

const handleExportClick = (): void => {
  void handleExport()
}

const handleExport = async (format: ExportFormat = 'excel') => {
  if (tableData.value.length === 0) {
    message.warning('暂无数据可导出')
    return
  }

  exporting.value = true
  try {
    if (!useMockData) {
      const { blob, fileName } = await drgApi.exportAnalysisData({
        format,
        dimension: dimension.value,
        startDate: dateRange.value[0].format(dateFormat),
        endDate: dateRange.value[1].format(dateFormat),
      })
      saveAs(blob, fileName)
      message.success(`${format.toUpperCase()} 导出成功`)
      return
    }

    if (format === 'docx') {
      message.warning('Mock 模式不支持 DOCX，请切换真实 API 后导出')
      return
    }

    const dateStr = dateRange.value.map((d: any) => d.format('YYYYMMDD')).join('-')
    const title = 'DRG Analysis Report'

    // 构建表头配置
    const tableHeaders = [
      { key: 'name', label: dynamicColumns.value[0].title as string },
      { key: 'caseCount', label: 'Case Count' },
      { key: 'cmi', label: 'CMI' },
      { key: 'totalRevenue', label: 'Total Revenue' },
      { key: 'totalCost', label: 'Total Cost' },
      { key: 'profit', label: 'Profit/Loss' },
      { key: 'costRate', label: 'Cost Rate' },
    ]

    // 构建概览数据
    const overview = [
      { label: 'Total Cases', value: statistics.totalCases },
      { label: 'Total Profit', value: `¥${statistics.totalProfit.toLocaleString()}` },
      { label: 'Avg Cost Rate', value: `${statistics.avgCostRate.toFixed(1)}%` },
      { label: 'DRG Group Count', value: statistics.drgGroupCount },
    ]

    exportComprehensiveReport(
      {
        title,
        dateRange: dateStr,
        dimension: dimensionLabelMap[dimension.value] || dimension.value,
        overview,
        tableData: tableData.value,
        tableHeaders,
      },
      format as 'excel' | 'pdf',
    )

    message.success(`${format.toUpperCase()} 导出成功`)
  } catch (error) {
    console.error('导出失败:', error)
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// ================== 图表更新逻辑 ==================

const updateDRGDistributionChart = (data: { name: string; value: number }[]) => {
  drgDistributionOption.value = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { type: 'scroll', orient: 'vertical', right: 10, top: 20, bottom: 20 },
    series: [
      {
        name: '分布',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['30%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
        label: { show: false, position: 'center' },
        emphasis: { label: { show: true, fontSize: 18, fontWeight: 'bold' } },
        data: data.map((item, idx) => ({ ...item, itemStyle: { color: getChartColor(idx) } })),
      },
    ],
  }
}

const updateCostCompositionChart = (data: { name: string; value: number }[]) => {
  profitAnalysisOption.value = {
    tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
    xAxis: { type: 'category', data: data.map((i) => i.name) },
    yAxis: { type: 'value', name: '占比(%)' },
    series: [
      {
        data: data.map((i) => i.value),
        type: 'bar',
        itemStyle: { color: '#1890ff', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', formatter: '{c}%' },
      },
    ],
  }
}

const updateTrendChart = (trends: {
  cost: any[]
  cmi: any[]
  time?: any[]
  profit_loss?: any[]
}) => {
  const dates = trends.cost.map((i) => i.date)
  const hasProfit = Array.isArray(trends.profit_loss) && trends.profit_loss.length > 0
  const series: any[] = [
    {
      name: '费用消耗指数',
      type: 'line',
      data: trends.cost.map((i) => i.value),
      smooth: true,
      markLine: { data: [{ yAxis: 1, name: '基准线' }] },
    },
    {
      name: 'CMI值',
      type: 'line',
      yAxisIndex: 1,
      data: trends.cmi.map((i) => i.value),
      smooth: true,
      itemStyle: { color: '#faad14' },
    },
  ]
  if (hasProfit) {
    series.push({
      name: '医保盈亏',
      type: 'line',
      yAxisIndex: 2,
      data: (trends.profit_loss || []).map((i: any) => i.value),
      smooth: true,
      itemStyle: { color: '#10b981' },
    })
  }

  costRateTrendOption.value = {
    tooltip: { trigger: 'axis' },
    legend: { data: hasProfit ? ['费用消耗指数', 'CMI值', '医保盈亏'] : ['费用消耗指数', 'CMI值'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: dates },
    yAxis: [
      { type: 'value', name: '费用消耗指数', min: 0.5, max: 1.5 },
      { type: 'value', name: 'CMI值', min: 0 },
      { type: 'value', name: '医保盈亏', position: 'right', offset: 70 },
    ],
    series,
  }
}

// ================== 医生绩效对比图表 ==================

const updateDoctorRadarChart = (doctorData: AnalysisTableItem[]) => {
  // 取前5名医生进行对比
  const topDoctors = doctorData.slice(0, 5)

  doctorRadarOption.value = {
    tooltip: { trigger: 'item' },
    legend: {
      data: topDoctors.map((d) => d.name),
      bottom: 0,
    },
    radar: {
      indicator: [
        { name: '病例数', max: Math.max(...doctorData.map((d) => d.caseCount)) * 1.2 },
        { name: 'CMI值', max: 3 },
        { name: '费用控制', max: 100 },
        { name: '盈利能力', max: 100 },
        { name: '效率指数', max: 100 },
      ],
      center: ['50%', '45%'],
      radius: 100,
    },
    series: [
      {
        type: 'radar',
        data: topDoctors.map((d, idx) => ({
          value: [
            d.caseCount,
            d.cmi,
            Math.max(0, 100 - (d.costRate - 0.8) * 100),
            Math.min(100, 50 + d.profit / 10000),
            Math.max(0, 100 - Math.abs(d.costRate - 1) * 50),
          ],
          name: d.name,
          areaStyle: { opacity: 0.2 },
          itemStyle: { color: getChartColor(idx) },
        })),
      },
    ],
  }
}

const updateDoctorBenchmarkChart = (doctorData: AnalysisTableItem[]) => {
  // 计算科室平均值
  const avgCMI = doctorData.reduce((sum, d) => sum + (d.cmi ?? 0), 0) / doctorData.length
  const avgCostRate = doctorData.reduce((sum, d) => sum + d.costRate, 0) / doctorData.length
  const avgProfit = doctorData.reduce((sum, d) => sum + d.profit, 0) / doctorData.length

  // 取前8名医生
  const topDoctors = doctorData.slice(0, 8)

  doctorBenchmarkOption.value = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['医生CMI', '科室平均CMI'] },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: topDoctors.map((d) => d.name),
      axisLabel: { rotate: 30, fontSize: 11 },
    },
    yAxis: [
      { type: 'value', name: 'CMI', min: 0, max: 3 },
      { type: 'value', name: '盈亏(万)', position: 'right' },
    ],
    series: [
      {
        name: '医生CMI',
        type: 'bar',
        data: topDoctors.map((d) => d.cmi),
        itemStyle: { color: '#6366f1', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '科室平均CMI',
        type: 'line',
        data: topDoctors.map(() => avgCMI.toFixed(2)),
        itemStyle: { color: '#f59e0b' },
        lineStyle: { type: 'dashed' },
      },
      {
        name: '盈亏额',
        type: 'bar',
        yAxisIndex: 1,
        data: topDoctors.map((d) => (d.profit / 10000).toFixed(1)),
        itemStyle: {
          color: (params: any) => {
            return params.data >= 0 ? '#10b981' : '#ef4444'
          },
          borderRadius: [4, 4, 0, 0],
        },
      },
    ],
  }
}

// ================== 数据加载 ==================

const loadAnalysisData = async () => {
  loading.value = true
  try {
    const params = {
      dimension: dimension.value,
      startDate: dateRange.value[0].format(dateFormat),
      endDate: dateRange.value[1].format(dateFormat),
    }

    const res = await drgApi.getAnalysisData(params)

    // 更新概览
    statistics.totalCases = res.overview.totalCases
    statistics.totalProfit = res.overview.totalProfit
    statistics.avgCostRate = res.overview.avgCostRate * 100 // 转百分比
    statistics.drgGroupCount = res.overview.drgGroupCount
    statistics.lowRiskMortalityRate = res.overview.lowRiskMortalityRate ?? 0
    statistics.timeConsumptionIndex = res.overview.timeConsumptionIndex ?? 0
    statistics.insuranceProfitLoss =
      res.overview.insuranceProfitLoss ?? res.overview.totalProfit ?? 0

    // 更新图表
    updateDRGDistributionChart(res.distribution.drg)
    updateCostCompositionChart(res.distribution.cost)
    updateTrendChart(res.trends)

    // 更新表格
    tableData.value = res.tableData
    conclusions.value = res.conclusions || []

    // 如果是医生维度，更新医生对比图表
    if (dimension.value === 'person' && res.tableData.length > 0) {
      updateDoctorRadarChart(res.tableData)
      updateDoctorBenchmarkChart(res.tableData)
    }

    message.success('数据更新成功')
  } catch (error) {
    console.error('加载分析数据失败:', error)
    message.error('数据加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await nextTick()
  loadAnalysisData()
})
</script>

<style scoped lang="scss">
.drg-analysis {
  .content-wrapper {
    padding: 16px;
    background-color: #f0f2f5;
    min-height: calc(100vh - 64px);
  }

  .chart {
    height: 100%;
    width: 100%;
  }
}
</style>
