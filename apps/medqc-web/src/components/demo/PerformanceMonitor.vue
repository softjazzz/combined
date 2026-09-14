<template>
  <div class="performance-monitor">
    <a-card
      title="性能监控"
      :bordered="false"
    >
      <template #extra>
        <a-space>
          <a-button
            size="small"
            @click="handleExport"
          >
            <DownloadOutlined />
            导出数据
          </a-button>
          <a-button
            size="small"
            danger
            @click="handleReset"
          >
            <ReloadOutlined />
            重置
          </a-button>
        </a-space>
      </template>

      <!-- 性能评分 -->
      <div class="performance-score">
        <a-statistic
          title="性能评分"
          :value="performanceScore"
          suffix="/ 100"
        >
          <template #prefix>
            <TrophyOutlined :style="{ color: scoreColor }" />
          </template>
        </a-statistic>
        <a-tag
          :color="scoreColor"
          size="large"
          class="score-tag"
        >
          {{ scoreRating }}
        </a-tag>
      </div>

      <a-divider />

      <!-- 步骤耗时统计 -->
      <div class="step-timings">
        <h4>步骤耗时</h4>
        <a-timeline>
          <a-timeline-item
            v-for="step in stepTimings"
            :key="step.name"
            :color="getStepColor(step.duration)"
          >
            <div class="timeline-content">
              <div class="step-info">
                <span class="step-name">{{ step.name }}</span>
                <span class="step-duration">{{ formatDuration(step.duration) }}</span>
              </div>
              <a-progress
                :percent="getStepProgress(step.duration)"
                :stroke-color="getStepColor(step.duration)"
                :show-info="false"
                size="small"
              />
            </div>
          </a-timeline-item>
        </a-timeline>
      </div>

      <a-divider />

      <!-- API 调用统计 -->
      <div class="api-stats">
        <h4>API 调用统计</h4>
        <a-table
          :columns="apiColumns"
          :data-source="apiCalls"
          :pagination="false"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'duration'">
              <a-tag :color="getApiDurationColor(record.duration)">
                {{ record.duration }}ms
              </a-tag>
            </template>
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === 'success' ? 'green' : 'red'">
                {{ record.status === 'success' ? '成功' : '失败' }}
              </a-tag>
            </template>
          </template>
        </a-table>
      </div>

      <a-divider />

      <!-- 内存使用情况（如果可获取） -->
      <div
        v-if="memoryInfo"
        class="memory-usage"
      >
        <h4>内存使用情况</h4>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic
              title="已使用"
              :value="memoryInfo.usedJSHeapSize"
              suffix="MB"
              :precision="2"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="总分配"
              :value="memoryInfo.totalJSHeapSize"
              suffix="MB"
              :precision="2"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic
              title="使用率"
              :value="memoryUsagePercent"
              suffix="%"
              :precision="1"
            />
          </a-col>
        </a-row>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  TrophyOutlined,
  DownloadOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'

// 步骤耗时接口
export interface StepTiming {
  name: string
  startTime: number
  endTime?: number
  duration: number
}

// API 调用接口
export interface ApiCall {
  name: string
  duration: number
  status: 'success' | 'error'
  timestamp: string
}

// 内存信息接口
export interface MemoryInfo {
  usedJSHeapSize: number
  totalJSHeapSize: number
  jsHeapSizeLimit: number
}

// Props
interface Props {
  stepTimings: StepTiming[]
  apiCalls: ApiCall[]
  memoryInfo?: MemoryInfo | null
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  export: []
  reset: []
}>()

// API 表格列
const apiColumns = [
  {
    title: 'API 名称',
    dataIndex: 'name',
    key: 'name'
  },
  {
    title: '耗时',
    dataIndex: 'duration',
    key: 'duration'
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status'
  },
  {
    title: '时间',
    dataIndex: 'timestamp',
    key: 'timestamp'
  }
]

// 性能评分计算
const performanceScore = computed(() => {
  let score = 100

  // 基于步骤耗时扣分
  props.stepTimings.forEach(step => {
    if (step.duration > 5000) {
      score -= 10
    } else if (step.duration > 3000) {
      score -= 5
    } else if (step.duration > 2000) {
      score -= 2
    }
  })

  // 基于 API 调用耗时扣分
  props.apiCalls.forEach(api => {
    if (api.status === 'error') {
      score -= 5
    } else if (api.duration > 2000) {
      score -= 3
    } else if (api.duration > 1000) {
      score -= 1
    }
  })

  return Math.max(score, 0)
})

// 性能评级
const scoreRating = computed(() => {
  const score = performanceScore.value
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '一般'
  return '较差'
})

// 评分颜色
const scoreColor = computed(() => {
  const score = performanceScore.value
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#2b6cf6'
  if (score >= 70) return '#faad14'
  return '#f5222d'
})

// 内存使用百分比
const memoryUsagePercent = computed(() => {
  if (!props.memoryInfo) return 0
  return (props.memoryInfo.usedJSHeapSize / props.memoryInfo.totalJSHeapSize) * 100
})

// 格式化时长
const formatDuration = (ms: number): string => {
  if (ms < 1000) {
    return `${ms}ms`
  }
  return `${(ms / 1000).toFixed(2)}s`
}

// 获取步骤进度（用于进度条）
const getStepProgress = (duration: number): number => {
  const maxDuration = 10000 // 假设最大10秒
  return Math.min((duration / maxDuration) * 100, 100)
}

// 获取步骤颜色
const getStepColor = (duration: number): string => {
  if (duration < 1000) return '#52c41a'
  if (duration < 3000) return '#2b6cf6'
  if (duration < 5000) return '#faad14'
  return '#f5222d'
}

// 获取 API 耗时颜色
const getApiDurationColor = (duration: number): string => {
  if (duration < 500) return 'green'
  if (duration < 1000) return 'blue'
  if (duration < 2000) return 'orange'
  return 'red'
}

// 导出性能数据
const handleExport = () => {
  const data = {
    exportTime: new Date().toISOString(),
    performanceScore: performanceScore.value,
    scoreRating: scoreRating.value,
    stepTimings: props.stepTimings,
    apiCalls: props.apiCalls,
    memoryInfo: props.memoryInfo
  }

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `performance-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)

  message.success('性能数据已导出')
  emit('export')
}

// 重置性能数据
const handleReset = () => {
  emit('reset')
  message.success('性能数据已重置')
}
</script>

<style scoped lang="less">
.performance-monitor {
  margin-bottom: 24px;
}

.performance-score {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  padding: 24px 0;
}

.score-tag {
  font-size: 18px;
  font-weight: 600;
  padding: 8px 16px;
}

.step-timings,
.api-stats,
.memory-usage {
  h4 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #262626;
  }
}

.timeline-content {
  width: 100%;
}

.step-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.step-name {
  font-weight: 500;
  color: #262626;
}

.step-duration {
  font-family: 'Courier New', monospace;
  color: #8c8c8c;
}
</style>

