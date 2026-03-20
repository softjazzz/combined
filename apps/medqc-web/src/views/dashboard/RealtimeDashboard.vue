<script setup lang="ts">
import { h, ref, onMounted, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import { useNotificationStore } from '../../stores/notification'
import { getRealtimeService } from '../../lib/realtime/realtime-service'
import type { RealtimeEvent } from '../../lib/realtime/realtime-service'
import { supabase } from '../../lib/supabase'
import { 
  ThunderboltOutlined, 
  BellOutlined, 
  EyeOutlined,
  ReloadOutlined,
  PlusOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

// 状态管理
const notificationStore = useNotificationStore()
const realtimeService = getRealtimeService()

// 响应式数据
const realtimeEvents = ref<RealtimeEvent[]>([])
const isConnected = ref(false)
const connectionStatus = ref('未连接')
const autoScroll = ref(true)
const maxEvents = ref(50)

// 统计数据
const eventStats = ref({
  total: 0,
  inserts: 0,
  updates: 0,
  deletes: 0
})

// 检查连接状态
const checkConnection = () => {
  isConnected.value = realtimeService.getConnectionStatus()
  connectionStatus.value = isConnected.value ? '已连接' : '未连接'
}

// 处理实时事件
const handleRealtimeEvent = (event: RealtimeEvent) => {
  console.log('收到实时事件:', event)
  
  // 添加到事件列表
  realtimeEvents.value.unshift({
    ...event,
    timestamp: new Date().toISOString()
  })
  
  // 限制事件数量
  if (realtimeEvents.value.length > maxEvents.value) {
    realtimeEvents.value = realtimeEvents.value.slice(0, maxEvents.value)
  }
  
  // 更新统计
  eventStats.value.total++
  switch (event.eventType) {
    case 'INSERT':
      eventStats.value.inserts++
      break
    case 'UPDATE':
      eventStats.value.updates++
      break
    case 'DELETE':
      eventStats.value.deletes++
      break
  }
  
  // 自动滚动
  if (autoScroll.value) {
    setTimeout(() => {
      const container = document.querySelector('.events-container')
      if (container) {
        container.scrollTop = 0
      }
    }, 100)
  }
}

// 清空事件日志
const clearEvents = () => {
  realtimeEvents.value = []
  eventStats.value = {
    total: 0,
    inserts: 0,
    updates: 0,
    deletes: 0
  }
  message.success('事件日志已清空')
}

// 创建测试记录
const createTestRecord = async () => {
  try {
    const { data, error } = await supabase
      .from('medical_records')
      .insert({
        patient_name: `测试患者${Date.now()}`,
        patient_age: Math.floor(Math.random() * 50) + 20,
        patient_gender: Math.random() > 0.5 ? 'M' : 'F',
        department: ['内科', '外科', '儿科', '妇科'][Math.floor(Math.random() * 4)],
        admission_date: new Date().toISOString().split('T')[0],
        record_type: 'inpatient',
        content: `这是一条测试记录，创建时间：${new Date().toLocaleString()}`,
        status: 'pending'
      })
      .select()
      .single()
    
    if (error) {
      throw error
    }
    
    message.success('测试记录创建成功')
  } catch (error) {
    console.error('创建测试记录失败:', error)
    message.error('创建测试记录失败')
  }
}

// 更新最近的记录
const updateLatestRecord = async () => {
  try {
    const { data: records, error: fetchError } = await supabase
      .from('medical_records')
      .select('id')
      .order('created_at', { ascending: false })
      .limit(1)
    
    if (fetchError || !records || records.length === 0) {
      message.warning('没有找到可更新的记录')
      return
    }
    
    const { error: updateError } = await supabase
      .from('medical_records')
      .update({ 
        status: ['pending', 'analyzing', 'completed'][Math.floor(Math.random() * 3)],
        qc_score: Math.floor(Math.random() * 100)
      })
      .eq('id', records[0].id)
    
    if (updateError) {
      throw updateError
    }
    
    message.success('记录更新成功')
  } catch (error) {
    console.error('更新记录失败:', error)
    message.error('更新记录失败')
  }
}

// 删除测试记录
const deleteTestRecord = async () => {
  try {
    const { data: records, error: fetchError } = await supabase
      .from('medical_records')
      .select('id, patient_name')
      .ilike('patient_name', '%测试患者%')
      .order('created_at', { ascending: false })
      .limit(1)
    
    if (fetchError || !records || records.length === 0) {
      message.warning('没有找到测试记录')
      return
    }
    
    const { error: deleteError } = await supabase
      .from('medical_records')
      .delete()
      .eq('id', records[0].id)
    
    if (deleteError) {
      throw deleteError
    }
    
    message.success('测试记录删除成功')
  } catch (error) {
    console.error('删除记录失败:', error)
    message.error('删除记录失败')
  }
}

// 重新连接
const reconnect = async () => {
  try {
    await realtimeService.reconnect()
    message.success('重新连接成功')
  } catch (error) {
    console.error('重新连接失败:', error)
    message.error('重新连接失败')
  }
}

// 格式化时间
const formatTime = (timestamp: string) => {
  return new Date(timestamp).toLocaleString()
}

// 获取事件类型颜色
const getEventTypeColor = (eventType: string) => {
  const colorMap = {
    'INSERT': '#52c41a',
    'UPDATE': '#faad14',
    'DELETE': '#ff4d4f'
  }
  return colorMap[eventType as keyof typeof colorMap] || '#1890ff'
}

// 获取事件类型文本
const getEventTypeText = (eventType: string) => {
  const textMap = {
    'INSERT': '新增',
    'UPDATE': '更新',
    'DELETE': '删除'
  }
  return textMap[eventType as keyof typeof textMap] || eventType
}

// 生命周期
onMounted(() => {
  checkConnection()
  
  // 添加实时事件监听器
  realtimeService.addEventListener('medical_records', handleRealtimeEvent)
  realtimeService.addEventListener('qc_results', handleRealtimeEvent)
  
  // 定时检查连接状态
  const statusInterval = setInterval(checkConnection, 5000)
  
  onUnmounted(() => {
    clearInterval(statusInterval)
    realtimeService.removeEventListener('medical_records', handleRealtimeEvent)
    realtimeService.removeEventListener('qc_results', handleRealtimeEvent)
  })
})
</script>

<template>
  <div class="realtime-dashboard">
    <!-- 头部 -->
    <div class="dashboard-header">
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <ThunderboltOutlined class="text-2xl text-blue-500 mr-3" />
          <div>
            <h1 class="text-2xl font-bold text-gray-900">实时数据监控</h1>
            <p class="text-sm text-gray-600">监控数据库实时变化和系统通知</p>
          </div>
        </div>
        
        <div class="flex items-center space-x-4">
          <!-- 连接状态 -->
          <div class="flex items-center space-x-2">
            <div 
              class="w-3 h-3 rounded-full"
              :class="isConnected ? 'bg-green-500' : 'bg-red-500'"
            ></div>
            <span class="text-sm font-medium">{{ connectionStatus }}</span>
          </div>
          
          <!-- 重连按钮 -->
          <a-button 
            v-if="!isConnected"
            type="primary"
            :icon="h(ReloadOutlined)"
            @click="reconnect"
          >
            重新连接
          </a-button>
        </div>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
      <a-card class="text-center">
        <div class="text-2xl font-bold text-blue-600">{{ eventStats.total }}</div>
        <div class="text-sm text-gray-600">总事件数</div>
      </a-card>
      
      <a-card class="text-center">
        <div class="text-2xl font-bold text-green-600">{{ eventStats.inserts }}</div>
        <div class="text-sm text-gray-600">新增事件</div>
      </a-card>
      
      <a-card class="text-center">
        <div class="text-2xl font-bold text-yellow-600">{{ eventStats.updates }}</div>
        <div class="text-sm text-gray-600">更新事件</div>
      </a-card>
      
      <a-card class="text-center">
        <div class="text-2xl font-bold text-red-600">{{ eventStats.deletes }}</div>
        <div class="text-sm text-gray-600">删除事件</div>
      </a-card>
    </div>

    <!-- 操作区域 -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- 测试操作 -->
      <a-card title="测试操作" class="mb-6">
        <div class="space-y-4">
          <div class="flex flex-wrap gap-2">
            <a-button 
              type="primary" 
              :icon="h(PlusOutlined)"
              @click="createTestRecord"
            >
              创建测试记录
            </a-button>
            
            <a-button 
              :icon="h(ReloadOutlined)"
              @click="updateLatestRecord"
            >
              更新最新记录
            </a-button>
            
            <a-button 
              danger
              :icon="h(DeleteOutlined)"
              @click="deleteTestRecord"
            >
              删除测试记录
            </a-button>
          </div>
          
          <div class="text-sm text-gray-600">
            点击按钮可以触发数据库操作，观察实时事件变化
          </div>
        </div>
      </a-card>

      <!-- 事件控制 -->
      <a-card title="事件控制" class="mb-6">
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm">自动滚动</span>
            <a-switch v-model:checked="autoScroll" />
          </div>
          
          <div class="flex items-center justify-between">
            <span class="text-sm">最大事件数</span>
            <a-input-number 
              v-model:value="maxEvents"
              :min="10"
              :max="200"
              :step="10"
              size="small"
            />
          </div>
          
          <a-button 
            block
            @click="clearEvents"
            :disabled="realtimeEvents.length === 0"
          >
            清空事件日志
          </a-button>
        </div>
      </a-card>
    </div>

    <!-- 实时事件日志 -->
    <a-card title="实时事件日志" class="mb-6">
      <div 
        class="events-container"
        style="height: 400px; overflow-y: auto;"
      >
        <div 
          v-if="realtimeEvents.length === 0"
          class="text-center py-8 text-gray-500"
        >
          <BellOutlined class="text-4xl mb-2" />
          <p>暂无实时事件</p>
        </div>
        
        <div 
          v-else
          class="space-y-2"
        >
          <div
            v-for="event in realtimeEvents"
            :key="`${event.timestamp}-${Math.random()}`"
            class="event-item"
          >
            <div class="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
              <div 
                class="w-3 h-3 rounded-full mt-1 flex-shrink-0"
                :style="{ backgroundColor: getEventTypeColor(event.eventType) }"
              ></div>
              
              <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between">
                  <div class="flex items-center space-x-2">
                    <span 
                      class="text-sm font-medium px-2 py-1 rounded"
                      :style="{ 
                        color: getEventTypeColor(event.eventType),
                        backgroundColor: getEventTypeColor(event.eventType) + '20'
                      }"
                    >
                      {{ getEventTypeText(event.eventType) }}
                    </span>
                    <span class="text-sm text-gray-600">{{ event.table }}</span>
                  </div>
                  <span class="text-xs text-gray-400">
                    {{ formatTime(event.timestamp) }}
                  </span>
                </div>
                
                <div class="mt-2 text-sm text-gray-700">
                  <div v-if="event.new && event.new.patient_name">
                    患者: {{ event.new.patient_name }}
                    <span v-if="event.new.status" class="ml-2">
                      状态: {{ event.new.status }}
                    </span>
                  </div>
                  <div v-else-if="event.old && event.old.patient_name">
                    患者: {{ event.old.patient_name }}
                  </div>
                  <div v-else>
                    {{ event.eventType }} 操作
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-card>
  </div>
</template>

<style scoped>
.realtime-dashboard {
  @apply p-6;
}

.dashboard-header {
  @apply mb-8;
}

.events-container {
  @apply border border-gray-200 rounded-lg p-4;
}

.event-item {
  @apply transition-all duration-200;
}

.event-item:hover {
  @apply transform scale-105;
}

/* 滚动条样式 */
.events-container::-webkit-scrollbar {
  width: 6px;
}

.events-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.events-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.events-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style> 
