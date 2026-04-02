<template>
  <div class="sync-overview">
    <div class="overview-header">
      <div>
        <h1 class="overview-title">
          数据对接控制台
        </h1>
        <div class="overview-meta">
          <a-tag color="blue">
            Workstation V4
          </a-tag>
          <a-tag :color="envTagColor">
            环境：{{ envLabel }}
          </a-tag>
          <span class="dot">·</span>
          <span>来源：真实接口</span>
        </div>
      </div>
      <div class="action-row">
        <a-select
          v-model:value="state.selectedTier"
          style="width: 132px"
          :options="tierOptions"
          :disabled="true"
        />
        <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '测试远端 PG + 本地 PG'">
          <a-button
            :loading="state.isTestingAll"
            :disabled="isReadonly"
            @click="handleTestAll"
          >
            测试全连接
          </a-button>
        </a-tooltip>
        <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '执行前预检，不落库'">
          <a-button
            :loading="state.isPreflighting"
            :disabled="isReadonly"
            @click="handlePreflight"
          >
            试运行
          </a-button>
        </a-tooltip>
        <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '预检通过后可执行同步'">
          <a-button
            type="primary"
            :loading="state.isSyncing"
            :disabled="isReadonly || !hasPreflightPass"
            @click="handleExecute"
          >
            执行同步
          </a-button>
        </a-tooltip>
      </div>
    </div>

    <div class="health-strip">
      <div class="health-left">
        <span class="health-title">连接健康度</span>
        <span class="health-value">{{ healthPercent }}%</span>
      </div>
      <a-progress
        :percent="healthPercent"
        :show-info="false"
        :stroke-color="healthColor"
      />
      <div
        class="health-right"
        :style="{ color: healthColor }"
      >
        {{ healthLabel }}
      </div>
    </div>

    <div class="stats-grid">
      <a-card
        size="small"
        class="stat-card"
      >
        <div class="stat-label">
          连接状态
        </div>
        <div class="stat-value">
          {{ connectedCountDisplay }} / {{ totalSources }}
        </div>
      </a-card>
      <a-card
        size="small"
        class="stat-card"
      >
        <div class="stat-label">
          上次同步
        </div>
        <div class="stat-value time">
          {{ formattedLastSyncTime }}
        </div>
      </a-card>
      <a-card
        size="small"
        class="stat-card"
      >
        <div class="stat-label">
          待处理
        </div>
        <div class="stat-value">
          {{ state.stats.pendingRecords.toLocaleString() }}
        </div>
      </a-card>
      <a-card
        size="small"
        class="stat-card danger"
      >
        <div class="stat-label">
          异常
        </div>
        <div class="stat-value">
          {{ state.stats.failedRecords }}
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Modal, message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { useDataSync } from '../../composables/useDataSync'

const { state, isReadonly, hasPreflightPass, testAllConnections, runPreflight, executeSync } =
  useDataSync()
const totalSources = 2
const connectedCountDisplay = computed(() =>
  Math.max(0, Math.min(totalSources, Number(state.stats.connectedCount || 0))),
)

const formattedLastSyncTime = computed(() => {
  if (!state.stats.lastSyncTime) return '—'
  return dayjs(state.stats.lastSyncTime).format('YYYY-MM-DD HH:mm:ss')
})

const envTagColor = computed(() => {
  if (envLabel.value === '生产') return 'red'
  if (envLabel.value === '测试') return 'gold'
  return 'green'
})

const activeSource = computed(() => 'pg' as const)
const envLabel = computed(() => {
  const mode = (import.meta.env.MODE || 'unknown').toLowerCase()
  if (mode === 'production') return '生产'
  if (mode === 'development') return '开发'
  if (mode === 'test') return '测试'
  return mode
})

const healthPercent = computed(() => {
  if (!totalSources) return 0
  return Math.max(0, Math.min(100, Math.round((connectedCountDisplay.value / totalSources) * 100)))
})

const healthColor = computed(() => {
  if (healthPercent.value >= 100) return '#16a34a'
  if (healthPercent.value >= 67) return '#d97706'
  return '#dc2626'
})

const healthLabel = computed(() => {
  if (healthPercent.value >= 100) return '稳定'
  if (healthPercent.value >= 67) return '部分可用'
  return '高风险'
})
const tierOptions = [
  { label: '全部 Tier', value: 'all' },
  { label: 'Tier1', value: 'tier1' },
  { label: 'Tier2', value: 'tier2' },
  { label: 'Tier3', value: 'tier3' },
]

function parseMinuteOfDay(timeValue: string): number | null {
  const matched = /^(\d{2}):(\d{2})$/.exec(timeValue)
  if (!matched) {
    return null
  }
  const hour = Number(matched[1])
  const minute = Number(matched[2])
  if (Number.isNaN(hour) || Number.isNaN(minute) || hour > 23 || minute > 59) {
    return null
  }
  return hour * 60 + minute
}

function isNowInWindow(start: string, end: string): boolean {
  const startMinute = parseMinuteOfDay(start)
  const endMinute = parseMinuteOfDay(end)
  if (startMinute === null || endMinute === null) {
    return true
  }
  const now = new Date()
  const current = now.getHours() * 60 + now.getMinutes()
  if (startMinute <= endMinute) {
    return current >= startMinute && current <= endMinute
  }
  return current >= startMinute || current <= endMinute
}

const handleTestAll = async () => {
  try {
    const result = await testAllConnections()
    if (result.all_connected) {
      message.success('全连接测试通过')
    } else {
      message.warning(`全连接测试完成：${result.connected_count}/${result.total_sources} 可用`)
    }
  } catch {
    message.error('全连接测试失败')
  }
}

const handlePreflight = async () => {
  try {
    const result = await runPreflight(activeSource.value)
    if (result.executable) {
      message.success(`预检通过，预计影响 ${result.estimated_impact} 条记录`)
    } else {
      message.warning(`预检未通过：${result.blockers.join('；') || '存在阻断项'}`)
    }
  } catch {
    message.error('试运行失败')
  }
}

const handleExecute = async () => {
  try {
    const messages: string[] = []
    if (state.selectedTier === 'tier3' && activeSource.value === 'mongo') {
      const inWindow = isNowInWindow(
        state.policyForm.night_window_start,
        state.policyForm.night_window_end,
      )
      if (!inWindow) {
        messages.push(
          `当前不在夜间窗口 ${state.policyForm.night_window_start}-${state.policyForm.night_window_end}，执行 Tier3 可能影响线上性能。`,
        )
      }
    }

    if (state.stats.failedRecords > 0) {
      messages.push(`当前存在 ${state.stats.failedRecords} 条失败记录，建议先排查后执行。`)
    }

    if (messages.length > 0) {
      const confirmed = await new Promise<boolean>((resolve) => {
        Modal.confirm({
          title: '执行前确认',
          content: messages.join(' '),
          okText: '继续执行',
          cancelText: '取消',
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        })
      })
      if (!confirmed) {
        return
      }
    }

    const result = await executeSync(activeSource.value)
    if (result.success) {
      message.success('同步任务已启动')
    } else {
      message.warning(result.error || result.message || '同步任务未启动')
    }
  } catch {
    message.error('执行同步失败')
  }
}
</script>

<style scoped>
.sync-overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.overview-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.overview-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
}

.dot {
  color: #9ca3af;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.health-strip {
  display: grid;
  grid-template-columns: 180px 1fr 80px;
  align-items: center;
  gap: 12px;
  background: linear-gradient(90deg, #eff6ff 0%, #ffffff 100%);
  border: 1px solid #dbeafe;
  border-radius: 10px;
  padding: 8px 12px;
}

.health-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.health-title {
  font-size: 12px;
  color: #4b5563;
}

.health-value {
  font-size: 18px;
  line-height: 22px;
  font-weight: 700;
  color: #111827;
}

.health-right {
  text-align: right;
  font-size: 12px;
  font-weight: 700;
}

.stat-card :deep(.ant-card-body) {
  padding: 12px;
}

.stat-label {
  color: #6b7280;
  font-size: 12px;
  line-height: 18px;
}

.stat-value {
  margin-top: 4px;
  font-size: 24px;
  line-height: 30px;
  font-weight: 700;
  color: #111827;
}

.stat-value.time {
  font-size: 18px;
}

.danger .stat-value {
  color: #dc2626;
}

@media (max-width: 1366px) {
  .health-strip {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .health-right {
    text-align: left;
  }

  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
