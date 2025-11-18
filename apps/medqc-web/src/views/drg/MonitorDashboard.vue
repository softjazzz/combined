<template>
  <div class="monitor-dashboard">
    <a-page-header
      title="事中监控"
      sub-title="实时预警和编码建议"
      @back="() => $router.back()"
    />

    <div class="content-wrapper">
      <!-- 统计卡片 -->
      <a-row :gutter="16" style="margin-bottom: 16px">
        <a-col :span="6">
          <a-card>
            <a-statistic title="预警总数" :value="statistics.totalAlerts" suffix="条">
              <template #prefix><WarningOutlined style="color: #faad14" /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic title="严重预警" :value="statistics.criticalAlerts" suffix="条">
              <template #prefix><ExclamationCircleOutlined style="color: #cf1322" /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic title="待处理建议" :value="statistics.pendingSuggestions" suffix="条">
              <template #prefix><BulbOutlined style="color: #1890ff" /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card>
            <a-statistic title="今日新增" :value="statistics.todayNew" suffix="条">
              <template #prefix><RiseOutlined style="color: #52c41a" /></template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- 预警列表 -->
      <a-card title="DRG 预警" :bordered="false" style="margin-bottom: 16px">
        <template #extra>
          <a-space>
            <a-select v-model:value="alertFilters.level" placeholder="预警级别" style="width: 120px" allowClear @change="loadAlerts">
              <a-select-option value="">全部</a-select-option>
              <a-select-option value="info">信息</a-select-option>
              <a-select-option value="warning">警告</a-select-option>
              <a-select-option value="critical">严重</a-select-option>
            </a-select>
            <a-button @click="loadAlerts"><ReloadOutlined /></a-button>
          </a-space>
        </template>

        <a-table
          :columns="alertColumns"
          :data-source="alerts"
          :loading="loadingAlerts"
          :pagination="{ pageSize: 10 }"
          row-key="alert_id"
        >
          <template #alertLevel="{ record }">
            <StatusTag type="alert" :value="record.alert_level" />
          </template>
          <template #alertType="{ record }">
            <a-tag>{{ alertTypeMap[record.alert_type] }}</a-tag>
          </template>
          <template #metric="{ record }">
            <span v-if="record.metric_value">
              {{ record.metric_value.toFixed(1) }}
              <span v-if="record.threshold_value">/ {{ record.threshold_value.toFixed(1) }}</span>
            </span>
            <span v-else>-</span>
          </template>
          <template #time="{ record }">
            {{ formatDateTime(record.triggered_at) }}
          </template>
        </a-table>
      </a-card>

      <!-- 编码建议列表 -->
      <a-card title="编码建议" :bordered="false">
        <template #extra>
          <a-button @click="loadSuggestions"><ReloadOutlined /></a-button>
        </template>

        <a-table
          :columns="suggestionColumns"
          :data-source="suggestions"
          :loading="loadingSuggestions"
          :pagination="{ pageSize: 10 }"
          row-key="suggestion_id"
        >
          <template #type="{ record }">
            <a-tag>{{ suggestionTypeMap[record.suggestion_type] }}</a-tag>
          </template>
          <template #severity="{ record }">
            <StatusTag type="severity" :value="record.severity" />
          </template>
          <template #action="{ record }">
            <a-space v-if="record.status === 'pending'">
              <a-button type="link" size="small" @click="handleSuggestion(record.suggestion_id, 'accept')">
                接受
              </a-button>
              <a-button type="link" danger size="small" @click="handleSuggestion(record.suggestion_id, 'reject')">
                拒绝
              </a-button>
            </a-space>
            <a-tag v-else :color="record.status === 'accepted' ? 'success' : 'default'">
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
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  BulbOutlined,
  RiseOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import { alertTypeMap, suggestionTypeMap, formatDateTime } from '@/utils/drg'
import type { DRGAlertItem, CodingSuggestionItem } from '@/types/drg'

/** 统计数据 */
const statistics = reactive({
  totalAlerts: 0,
  criticalAlerts: 0,
  pendingSuggestions: 0,
  todayNew: 0
})

/** 预警列表 */
const alerts = ref<DRGAlertItem[]>([])
const loadingAlerts = ref(false)
const alertFilters = reactive({
  level: ''
})

const alertColumns = [
  { title: '预警级别', dataIndex: 'alert_level', width: 100, slots: { customRender: 'alertLevel' } },
  { title: '预警类型', dataIndex: 'alert_type', width: 120, slots: { customRender: 'alertType' } },
  { title: '住院号', dataIndex: 'admission_id', width: 150 },
  { title: '预警信息', dataIndex: 'message' },
  { title: '指标值', dataIndex: 'metric', width: 120, slots: { customRender: 'metric' } },
  { title: '触发时间', dataIndex: 'time', width: 150, slots: { customRender: 'time' } }
]

/** 编码建议列表 */
const suggestions = ref<CodingSuggestionItem[]>([])
const loadingSuggestions = ref(false)

const suggestionColumns = [
  { title: '建议类型', dataIndex: 'type', width: 120, slots: { customRender: 'type' } },
  { title: '严重程度', dataIndex: 'severity', width: 100, slots: { customRender: 'severity' } },
  { title: '住院号', dataIndex: 'admission_id', width: 150 },
  { title: '建议消息', dataIndex: 'message' },
  { title: '操作', key: 'action', width: 150, slots: { customRender: 'action' } }
]

/** 加载预警 */
const loadAlerts = async () => {
  loadingAlerts.value = true
  try {
    const response = await drgApi.getDRGAlerts({
      alert_level: alertFilters.level || undefined,
      limit: 50
    })
    alerts.value = response.alerts
    statistics.totalAlerts = response.total
    statistics.criticalAlerts = response.alerts.filter(a => a.alert_level === 'critical').length
  } catch (error) {
    console.error('加载预警失败:', error)
  } finally {
    loadingAlerts.value = false
  }
}

/** 加载建议 */
const loadSuggestions = async () => {
  loadingSuggestions.value = true
  try {
    const response = await drgApi.getCodingSuggestions('', 'pending')
    suggestions.value = response.suggestions
    statistics.pendingSuggestions = response.suggestions.filter(s => s.status === 'pending').length
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
      handled_by: 'current_user' // TODO: 从用户信息获取
    })
    message.success(action === 'accept' ? '已接受建议' : '已拒绝建议')
    loadSuggestions()
  } catch (error) {
    console.error('处理建议失败:', error)
    message.error('操作失败')
  }
}

onMounted(() => {
  loadAlerts()
  loadSuggestions()
})
</script>

<style scoped lang="scss">
.monitor-dashboard {
  .content-wrapper {
    padding: 16px;
  }
}
</style>
