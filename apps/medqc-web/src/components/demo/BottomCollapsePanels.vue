<template>
  <div class="bottom-collapse-panels">
    <a-collapse
      v-model:active-key="activeKeys"
      :bordered="false"
      class="collapse-container"
    >
      <!-- 统计与进度面板 -->
      <a-collapse-panel
        key="stats"
        class="collapse-panel"
      >
        <template #header>
          <div class="panel-header">
            <BarChartOutlined class="panel-icon" />
            <span class="panel-title">统计与进度</span>
            <a-badge
              :count="demoStore.selectedRulesCount"
              :number-style="{ backgroundColor: '#52c41a' }"
              :offset="[10, 0]"
            />
          </div>
        </template>
        <StatisticsCards
          :selected-rules-count="demoStore.selectedRulesCount"
          :total-rules-count="demoStore.totalRulesCount"
          :analysis-completed-count="demoStore.analysisCompletedCount"
          :total-records-count="demoStore.totalRecordsCount"
          :unread-notifications-count="demoStore.unreadNotificationsCount"
          :total-notifications-count="demoStore.totalNotificationsCount"
          :pending-appeals-count="demoStore.pendingAppealsCount"
          :total-appeals-count="demoStore.totalAppealsCount"
          :average-q-c-score="demoStore.averageQCScore"
          :is-running="demoStore.isRunning"
          :start-time="demoStore.demoStartTime"
        />
      </a-collapse-panel>

      <!-- 演示日志面板 -->
      <a-collapse-panel
        key="logs"
        class="collapse-panel"
      >
        <template #header>
          <div class="panel-header">
            <FileTextOutlined class="panel-icon" />
            <span class="panel-title">演示日志</span>
            <a-badge
              :count="demoStore.demoLogs.length"
              :number-style="{ backgroundColor: '#2b6cf6' }"
              :offset="[10, 0]"
            />
          </div>
        </template>
        <EnhancedLogPanel
          :logs="demoStore.demoLogs"
          @clear="demoStore.clearDemoLogs"
        />
      </a-collapse-panel>

      <!-- 性能监控面板 -->
      <a-collapse-panel
        key="perf"
        class="collapse-panel"
      >
        <template #header>
          <div class="panel-header">
            <DashboardOutlined class="panel-icon" />
            <span class="panel-title">性能监控</span>
            <a-tag
              v-if="demoStore.performanceMonitorEnabled"
              color="success"
              size="small"
            >
              已启用
            </a-tag>
            <a-tag
              v-else
              color="default"
              size="small"
            >
              未启用
            </a-tag>
          </div>
        </template>
        <div v-if="demoStore.performanceMonitorEnabled">
          <PerformanceMonitor
            :step-timings="demoStore.stepTimings"
            :api-calls="demoStore.apiCalls"
            :memory-info="demoStore.memoryInfo"
            @export="handlePerformanceExport"
            @reset="demoStore.resetPerformanceData"
          />
        </div>
        <a-alert
          v-else
          type="info"
          message="性能监控未启用"
          description="默认不启用性能监控以提升性能，可通过演示配置开启后查看详细的性能数据"
          show-icon
        >
          <template #action>
            <a-button
              size="small"
              type="primary"
              @click="handleEnablePerformanceMonitor"
            >
              立即启用
            </a-button>
          </template>
        </a-alert>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { useQCDemoStore } from '@/stores/qcDemo'
import StatisticsCards from './StatisticsCards.vue'
import EnhancedLogPanel from './EnhancedLogPanel.vue'
import PerformanceMonitor from './PerformanceMonitor.vue'
import {
  BarChartOutlined,
  FileTextOutlined,
  DashboardOutlined
} from '@ant-design/icons-vue'

const demoStore = useQCDemoStore()

// 默认展开的面板（默认全部收起）
const activeKeys = ref<string[]>([])

// 处理性能数据导出
const handlePerformanceExport = () => {
  try {
    const performanceData = {
      stepTimings: demoStore.stepTimings,
      apiCalls: demoStore.apiCalls,
      memoryInfo: demoStore.memoryInfo,
      exportTime: new Date().toISOString()
    }

    const dataStr = JSON.stringify(performanceData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `performance-data-${Date.now()}.json`
    link.click()
    URL.revokeObjectURL(url)

    message.success('性能数据已导出')
  } catch (error) {
    console.error('导出性能数据失败:', error)
    message.error('导出失败，请重试')
  }
}

// 启用性能监控
const handleEnablePerformanceMonitor = () => {
  demoStore.performanceMonitorEnabled = true
  message.success('性能监控已启用')
  // 自动展开性能监控面板
  if (!activeKeys.value.includes('perf')) {
    activeKeys.value.push('perf')
  }
}
</script>

<style scoped lang="less">
.bottom-collapse-panels {
  margin-top: 24px;

  .collapse-container {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

    :deep(.ant-collapse-item) {
      border-bottom: 1px solid #f0f0f0;

      &:last-child {
        border-bottom: none;
      }
    }

    :deep(.ant-collapse-header) {
      padding: 16px 24px;
      background: #fafafa;
      transition: all 0.3s ease;

      &:hover {
        background: #f5f5f5;
      }
    }

    :deep(.ant-collapse-content-box) {
      padding: 24px;
    }
  }

  .collapse-panel {
    .panel-header {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 15px;
      font-weight: 500;
      color: #262626;

      .panel-icon {
        font-size: 18px;
        color: #2b6cf6;
      }

      .panel-title {
        flex: 1;
      }
    }
  }
}

// 响应式优化
@media (max-width: 768px) {
  .bottom-collapse-panels {
    margin-top: 16px;

    .collapse-container {
      :deep(.ant-collapse-header) {
        padding: 12px 16px;
      }

      :deep(.ant-collapse-content-box) {
        padding: 16px;
      }
    }

    .collapse-panel {
      .panel-header {
        font-size: 14px;

        .panel-icon {
          font-size: 16px;
        }
      }
    }
  }
}
</style>

