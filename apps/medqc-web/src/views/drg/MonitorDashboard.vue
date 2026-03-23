<template>
  <div class="monitor-dashboard">
    <a-page-header
      title="事中监控"
      sub-title="实时预警和编码建议"
      @back="() => $router.back()"
    />

    <div class="content-wrapper">
      <!-- 统计卡片 -->
      <a-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="预警总数"
              :value="statistics.totalAlerts"
              suffix="条"
            >
              <template #prefix>
                <WarningOutlined style="color: #faad14" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="严重预警"
              :value="statistics.criticalAlerts"
              suffix="条"
            >
              <template #prefix>
                <ExclamationCircleOutlined style="color: #cf1322" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="待处理建议"
              :value="statistics.pendingSuggestions"
              suffix="条"
            >
              <template #prefix>
                <BulbOutlined style="color: #1890ff" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic
              title="今日新增"
              :value="statistics.todayNew"
              suffix="条"
            >
              <template #prefix>
                <RiseOutlined style="color: #52c41a" />
              </template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- 趋势图表 -->
      <a-row
        :gutter="16"
        style="margin-bottom: 16px"
      >
        <a-col :span="12">
          <a-card
            title="CMI 实时趋势 (近7日)"
            :bordered="false"
          >
            <div class="chart-container">
              <v-chart
                class="chart"
                :option="cmiChartOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>
        <a-col :span="12">
          <a-card
            title="费用消耗指数 (标杆值 < 1.0)"
            :bordered="false"
          >
            <div class="chart-container">
              <v-chart
                class="chart"
                :option="costChartOption"
                autoresize
              />
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 预警列表 -->
      <a-card
        :bordered="false"
        style="margin-bottom: 16px"
        :body-style="{ padding: 0 }"
      >
        <DRGAlertList @update:stats="updateAlertStats" />
      </a-card>

      <!-- 编码建议列表 -->
      <a-card
        title="编码建议"
        :bordered="false"
      >
        <template #extra>
          <a-button @click="loadSuggestions">
            <ReloadOutlined />
          </a-button>
        </template>

        <a-table
          :columns="suggestionColumns"
          :data-source="suggestions"
          :loading="loadingSuggestions"
          :pagination="{ pageSize: 5 }"
          row-key="suggestion_id"
        >
          <template #type="{ record }">
            <a-tag>
              {{
                suggestionTypeMap[record.suggestion_type as keyof typeof suggestionTypeMap]
              }}
            </a-tag>
          </template>
          <template #severity="{ record }">
            <StatusTag
              type="severity"
              :value="record.severity"
            />
          </template>
          <template #action="{ record }">
            <a-space v-if="record.status === 'pending'">
              <a-button
                type="link"
                size="small"
                @click="handleSuggestion(record.suggestion_id, 'accept')"
              >
                接受
              </a-button>
              <a-button
                type="link"
                danger
                size="small"
                @click="handleSuggestion(record.suggestion_id, 'reject')"
              >
                拒绝
              </a-button>
            </a-space>
            <a-tag
              v-else
              :color="record.status === 'accepted' ? 'success' : 'default'"
            >
              {{ record.status === 'accepted' ? '已接受' : '已拒绝' }}
            </a-tag>
          </template>
        </a-table>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  BulbOutlined,
  RiseOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import DRGAlertList from '@/components/drg/DRGAlertList.vue'
import { suggestionTypeMap } from '@/utils/drg'
import type { CodingSuggestionItem } from '@/types/drg'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  MarkLineComponent,
])

/** 统计数据 */
const statistics = reactive({
  totalAlerts: 0,
  criticalAlerts: 0,
  pendingSuggestions: 0,
  todayNew: 12, // Mock value
})

// 图表配置 - CMI
const cmiChartOption = ref({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
  },
  yAxis: { type: 'value', min: 0.8 },
  series: [
    {
      name: 'CMI',
      type: 'line',
      smooth: true,
      data: [1.02, 1.05, 1.03, 1.08, 1.12, 1.1, 1.15],
      itemStyle: { color: '#1890ff' },
      areaStyle: { color: '#e6f7ff' },
    },
  ],
})

// 图表配置 - 费用
const costChartOption = ref({
  tooltip: { trigger: 'axis' },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: {
    type: 'category',
    data: ['心内科', '呼吸科', '骨科', '普外科', '神经内科'],
  },
  yAxis: { type: 'value', max: 1.5 },
  series: [
    {
      name: '费用消耗指数',
      type: 'bar',
      barWidth: '40%',
      data: [0.92, 0.98, 1.05, 0.88, 1.02],
      itemStyle: {
        color: (params: any) => {
          return params.value > 1 ? '#ff4d4f' : '#52c41a'
        },
      },
      markLine: {
        data: [{ yAxis: 1.0, name: '标杆', lineStyle: { color: '#faad14', type: 'dashed' } }],
      },
    },
  ],
})

/** 编码建议列表 */
const suggestions = ref<CodingSuggestionItem[]>([])
const loadingSuggestions = ref(false)

const suggestionColumns = [
  { title: '建议类型', dataIndex: 'type', width: 120, slots: { customRender: 'type' } },
  { title: '严重程度', dataIndex: 'severity', width: 100, slots: { customRender: 'severity' } },
  { title: '住院号', dataIndex: 'admission_id', width: 150 },
  { title: '建议消息', dataIndex: 'message' },
  { title: '操作', key: 'action', width: 150, slots: { customRender: 'action' } },
]

const updateAlertStats = (total: number, critical: number) => {
  statistics.totalAlerts = total
  statistics.criticalAlerts = critical
}

/** 加载建议 */
const loadSuggestions = async () => {
  loadingSuggestions.value = true
  try {
    const response = await drgApi.getCodingSuggestions({
      status: 'pending',
      limit: 50,
    })
    suggestions.value = response.suggestions
    statistics.pendingSuggestions = response.suggestions.filter(
      (s) => s.status === 'pending',
    ).length
  } catch (error) {
    console.error('加载建议失败:', error)
  } finally {
    loadingSuggestions.value = false
  }
}

/** 处理建议 */
const handleSuggestion = async (suggestionId: number, action: 'accept' | 'reject') => {
  try {
    await drgApi.handleCodingSuggestion({
      suggestion_id: suggestionId,
      action,
      handled_by: 'current_user',
    })
    message.success(action === 'accept' ? '已接受建议' : '已拒绝建议')
    loadSuggestions()
  } catch (error) {
    console.error('处理建议失败:', error)
    message.error('操作失败')
  }
}

onMounted(() => {
  loadSuggestions()
})
</script>

<style scoped lang="scss">
.monitor-dashboard {
  .content-wrapper {
    padding: 16px;
  }

  .chart-container {
    height: 300px;
    width: 100%;

    .chart {
      height: 100%;
      width: 100%;
    }
  }
}
</style>
