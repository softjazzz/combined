<template>
  <div class="statistics-cards">
    <!-- 演示模式 -->
    <a-row v-if="mode === 'demo'" :gutter="[16, 16]">
      <!-- 规则统计 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="已选规则"
            :value="selectedRulesCount"
            :suffix="`/ ${totalRulesCount}`"
          >
            <template #prefix>
              <CheckCircleOutlined class="stat-icon rules" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">规则覆盖率</span>
            <span class="stat-value">{{ rulesCoverage }}%</span>
          </div>
        </a-card>
      </a-col>

      <!-- 分析统计 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="分析完成"
            :value="analysisCompletedCount"
            :suffix="`/ ${totalRecordsCount}`"
          >
            <template #prefix>
              <FileSearchOutlined class="stat-icon analysis" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">完成率</span>
            <span class="stat-value">{{ analysisCompletionRate }}%</span>
          </div>
        </a-card>
      </a-col>

      <!-- 通知统计 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="未读通知"
            :value="unreadNotificationsCount"
            :suffix="`/ ${totalNotificationsCount}`"
          >
            <template #prefix>
              <BellOutlined class="stat-icon notifications" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">未读率</span>
            <span class="stat-value">{{ unreadNotificationsRate }}%</span>
            <span v-if="notificationsTrend !== 0" class="trend">
              <ArrowUpOutlined v-if="notificationsTrend > 0" class="trend-up" />
              <ArrowDownOutlined v-else class="trend-down" />
            </span>
          </div>
        </a-card>
      </a-col>

      <!-- 申诉统计 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="待处理申诉"
            :value="pendingAppealsCount"
            :suffix="`/ ${totalAppealsCount}`"
          >
            <template #prefix>
              <ExclamationCircleOutlined class="stat-icon appeals" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">处理率</span>
            <span class="stat-value">{{ appealsProcessedRate }}%</span>
          </div>
        </a-card>
      </a-col>

      <!-- 质控得分 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="平均质控得分"
            :value="averageQCScore"
            :precision="1"
            suffix="分"
          >
            <template #prefix>
              <TrophyOutlined class="stat-icon score" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">评级</span>
            <span class="stat-value" :class="scoreRatingClass">{{ scoreRating }}</span>
            <span v-if="scoreTrend !== 0" class="trend">
              <ArrowUpOutlined v-if="scoreTrend > 0" class="trend-up" />
              <ArrowDownOutlined v-else class="trend-down" />
            </span>
          </div>
        </a-card>
      </a-col>

      <!-- 运行时长 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="6">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="演示运行时长"
            :value="demoRuntime"
          >
            <template #prefix>
              <ClockCircleOutlined class="stat-icon runtime" />
            </template>
          </a-statistic>
          <div class="stat-footer">
            <span class="stat-label">状态</span>
            <span class="stat-value" :class="runtimeStatusClass">{{ runtimeStatus }}</span>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 四川质控模式 -->
    <a-row v-else-if="mode === 'sichuan'" :gutter="[16, 16]">
      <!-- 总规则数 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="总规则数"
            :value="totalRulesCount"
            suffix="条"
          >
            <template #prefix>
              <FileTextOutlined class="stat-icon rules" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>

      <!-- 合规率 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="合规率"
            :value="complianceRate"
            :precision="1"
            suffix="%"
            :value-style="{ color: complianceRateColor }"
          >
            <template #prefix>
              <CheckCircleOutlined class="stat-icon" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>

      <!-- 严重违规 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="严重违规"
            :value="criticalViolations"
            suffix="项"
            :value-style="{ color: violationsColor }"
          >
            <template #prefix>
              <ExclamationCircleOutlined class="stat-icon" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>

      <!-- 处理时间 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="处理时间"
            :value="processingTime"
            :precision="2"
            suffix="秒"
          >
            <template #prefix>
              <ClockCircleOutlined class="stat-icon runtime" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>

      <!-- Token 使用 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="Token 使用"
            :value="tokenUsage"
          >
            <template #prefix>
              <DatabaseOutlined class="stat-icon token" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>

      <!-- 成本节省 -->
      <a-col :xs="24" :sm="12" :md="8" :lg="4">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="成本节省"
            :value="tokenSavingsRate * 100"
            :precision="1"
            suffix="%"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix>
              <DollarOutlined class="stat-icon savings" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import {
  CheckCircleOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  BellOutlined,
  ExclamationCircleOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  DatabaseOutlined,
  DollarOutlined
} from '@ant-design/icons-vue'

// Props
interface Props {
  // 模式：'demo' = 演示模式（原有），'sichuan' = 四川质控模式
  mode?: 'demo' | 'sichuan'

  // 演示模式的 props
  selectedRulesCount?: number
  totalRulesCount?: number
  analysisCompletedCount?: number
  totalRecordsCount?: number
  unreadNotificationsCount?: number
  totalNotificationsCount?: number
  pendingAppealsCount?: number
  totalAppealsCount?: number
  averageQCScore?: number
  isRunning?: boolean
  startTime?: Date | null

  // 四川质控模式的 props
  complianceRate?: number  // 合规率
  criticalViolations?: number  // 严重违规数
  processingTime?: number  // 处理时间（秒）
  tokenUsage?: number  // Token 使用量
  tokenSavingsRate?: number  // Token 节省率
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'demo',
  selectedRulesCount: 0,
  totalRulesCount: 0,
  analysisCompletedCount: 0,
  totalRecordsCount: 0,
  unreadNotificationsCount: 0,
  totalNotificationsCount: 0,
  pendingAppealsCount: 0,
  totalAppealsCount: 0,
  averageQCScore: 0,
  isRunning: false,
  complianceRate: 0,
  criticalViolations: 0,
  processingTime: 0,
  tokenUsage: 0,
  tokenSavingsRate: 0
})

// 规则覆盖率
const rulesCoverage = computed(() => {
  if (props.totalRulesCount === 0) return 0
  return Math.round((props.selectedRulesCount / props.totalRulesCount) * 100)
})

// 分析完成率
const analysisCompletionRate = computed(() => {
  if (props.totalRecordsCount === 0) return 0
  return Math.round((props.analysisCompletedCount / props.totalRecordsCount) * 100)
})

// 未读通知率
const unreadNotificationsRate = computed(() => {
  if (props.totalNotificationsCount === 0) return 0
  return Math.round((props.unreadNotificationsCount / props.totalNotificationsCount) * 100)
})

// 申诉处理率
const appealsProcessedRate = computed(() => {
  if (props.totalAppealsCount === 0) return 0
  const processed = props.totalAppealsCount - props.pendingAppealsCount
  return Math.round((processed / props.totalAppealsCount) * 100)
})

// 质控得分评级
const scoreRating = computed(() => {
  const score = props.averageQCScore
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '中等'
  if (score >= 60) return '及格'
  return '不及格'
})

const scoreRatingClass = computed(() => {
  const score = props.averageQCScore
  if (score >= 90) return 'rating-excellent'
  if (score >= 80) return 'rating-good'
  if (score >= 70) return 'rating-medium'
  if (score >= 60) return 'rating-pass'
  return 'rating-fail'
})

// 四川质控模式的计算属性

// 合规率颜色
const complianceRateColor = computed(() => {
  const rate = props.complianceRate || 0
  if (rate >= 95) return '#52c41a'  // 绿色
  if (rate >= 85) return '#1890ff'  // 蓝色
  if (rate >= 75) return '#faad14'  // 橙色
  if (rate >= 60) return '#ff7a45'  // 深橙色
  return '#f5222d'  // 红色
})

// 违规数颜色
const violationsColor = computed(() => {
  const count = props.criticalViolations || 0
  if (count === 0) return '#52c41a'  // 绿色
  if (count <= 3) return '#faad14'   // 橙色
  return '#f5222d'  // 红色
})

// 趋势指示器（简化版，实际应该基于历史数据）
const notificationsTrend = ref(0)
const scoreTrend = ref(0)

// 运行时长
const demoRuntime = ref('00:00:00')
let runtimeTimer: number | null = null

const updateRuntime = () => {
  if (!props.startTime || !props.isRunning) {
    demoRuntime.value = '00:00:00'
    return
  }

  const now = new Date()
  const diff = now.getTime() - props.startTime.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  const h = String(hours).padStart(2, '0')
  const m = String(minutes % 60).padStart(2, '0')
  const s = String(seconds % 60).padStart(2, '0')

  demoRuntime.value = `${h}:${m}:${s}`
}

// 运行状态
const runtimeStatus = computed(() => {
  return props.isRunning ? '运行中' : '已停止'
})

const runtimeStatusClass = computed(() => {
  return props.isRunning ? 'status-running' : 'status-stopped'
})

// 监听运行状态
watch(() => props.isRunning, (newVal) => {
  if (newVal) {
    runtimeTimer = window.setInterval(updateRuntime, 1000)
    updateRuntime()
  } else {
    if (runtimeTimer) {
      clearInterval(runtimeTimer)
      runtimeTimer = null
    }
  }
})

onMounted(() => {
  if (props.isRunning) {
    runtimeTimer = window.setInterval(updateRuntime, 1000)
    updateRuntime()
  }
})

onUnmounted(() => {
  if (runtimeTimer) {
    clearInterval(runtimeTimer)
  }
})
</script>

<style scoped lang="less">
.statistics-cards {
  margin-bottom: 24px;
}

.stat-card {
  background: linear-gradient(135deg, var(--primary-color-light) 0%, var(--primary-color) 100%);
  border-radius: 8px;
  color: #fff;
  box-shadow: 0 2px 8px rgba(14, 110, 209, 0.18);
  transition: all 0.3s;
  position: relative;
  overflow: hidden;

  :deep(.ant-card-body) {
    padding: 12px 16px 14px;
  }

  &::after {
    content: '';
    position: absolute;
    width: 140px;
    height: 140px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.12);
    right: -50px;
    top: -40px;
  }

  &:hover {
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
    transform: translateY(-2px);
  }

  :deep(.ant-statistic-title) {
    font-size: 14px;
    color: rgba(255, 255, 255, 0.85);
    margin-bottom: 8px;
  }

  :deep(.ant-statistic-content) {
    font-size: 24px;
    font-weight: 600;
    color: #fff;
  }
}

.stat-icon {
  font-size: 20px;
  margin-right: 8px;
  color: rgba(255, 255, 255, 0.9);
}

.stat-footer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
}

.stat-value {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}

.trend {
  margin-left: 8px;
  font-size: 12px;

  .trend-up {
    color: #52c41a;
  }

  .trend-down {
    color: #f5222d;
  }
}

.rating-excellent {
  color: #52c41a;
}

.rating-good {
  color: #1890ff;
}

.rating-medium {
  color: #faad14;
}

.rating-pass {
  color: #fa8c16;
}

.rating-fail {
  color: #f5222d;
}

.status-running {
  color: #52c41a;
}

.status-stopped {
  color: #8c8c8c;
}
</style>
