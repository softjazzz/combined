<template>
  <div class="drg-alert-list">
    <div class="header">
      <span class="title">DRG 预警</span>
      <a-space>
        <a-select v-model:value="filterLevel" placeholder="预警级别" style="width: 120px" allowClear @change="handleFilterChange">
          <a-select-option value="">全部</a-select-option>
          <a-select-option value="info">信息</a-select-option>
          <a-select-option value="warning">警告</a-select-option>
          <a-select-option value="critical">严重</a-select-option>
        </a-select>
        <a-button @click="reloadData"><ReloadOutlined /></a-button>
      </a-space>
    </div>

    <a-table
      :columns="columns"
      :data-source="alerts"
      :loading="loading"
      :pagination="{ pageSize: 5 }"
      row-key="alert_id"
      size="small"
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
      <template #alertStatus="{ record }">
        <a-tag v-if="record.status === 'pending'" color="processing">待处理</a-tag>
        <a-tag v-else-if="record.status === 'acknowledged'" color="success">已确认</a-tag>
        <a-tag v-else color="default">已关闭</a-tag>
      </template>
      <template #alertAction="{ record }">
        <a-space v-if="record.status === 'pending'">
          <a-button type="link" size="small" @click="handleAction(record.alert_id, 'acknowledge')">确认</a-button>
          <a-button type="link" danger size="small" @click="handleAction(record.alert_id, 'resolve')">关闭</a-button>
        </a-space>
        <span v-else>-</span>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import { alertTypeMap, formatDateTime } from '@/utils/drg'
import type { DRGAlertItem } from '@/types/drg'

const props = defineProps<{
  limit?: number
}>()

const emit = defineEmits<{
  (e: 'update:stats', total: number, critical: number): void
}>()

const loading = ref(false)
const alerts = ref<DRGAlertItem[]>([])
const filterLevel = ref<string>('')

const columns = [
  { title: '预警级别', dataIndex: 'alert_level', width: 90, slots: { customRender: 'alertLevel' } },
  { title: '类型', dataIndex: 'alert_type', width: 110, slots: { customRender: 'alertType' } },
  { title: '住院号', dataIndex: 'admission_id', width: 130 },
  { title: '预警信息', dataIndex: 'message' },
  { title: '指标', dataIndex: 'metric', width: 100, slots: { customRender: 'metric' } },
  { title: '时间', dataIndex: 'time', width: 140, slots: { customRender: 'time' } },
  { title: '状态', dataIndex: 'status', width: 90, slots: { customRender: 'alertStatus' } },
  { title: '操作', key: 'action', width: 120, slots: { customRender: 'alertAction' } }
]

const loadAlerts = async () => {
  loading.value = true
  try {
    const response = await drgApi.getDRGAlerts({
      alert_level: filterLevel.value as any || undefined,
      limit: props.limit || 50
    })
    alerts.value = response.alerts
    
    // Calculate stats
    const total = response.total
    const critical = response.alerts.filter(a => a.alert_level === 'critical').length
    emit('update:stats', total, critical)
    
  } catch (error) {
    console.error('加载预警失败:', error)
  } finally {
    loading.value = false
  }
}

const handleAction = async (alertId: number, action: 'acknowledge' | 'resolve') => {
  try {
    await drgApi.handleDRGAlert({
      alert_id: alertId,
      action,
      handled_by: 'current_user'
    })
    message.success(action === 'acknowledge' ? '预警已确认' : '预警已关闭')
    loadAlerts()
  } catch (error) {
    console.error('处理预警失败:', error)
    message.error('操作失败')
  }
}

const handleFilterChange = () => {
  loadAlerts()
}

const reloadData = () => {
  loadAlerts()
}

onMounted(() => {
  loadAlerts()
})

defineExpose({ reloadData })
</script>

<style scoped lang="scss">
.drg-alert-list {
  background: #fff;
  padding: 16px;
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    
    .title {
      font-size: 16px;
      font-weight: bold;
      color: #000000d9;
    }
  }
}
</style>
