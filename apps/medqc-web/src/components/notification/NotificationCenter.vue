<!-- 消息通知中心组件 -->
<template>
  <div class="notification-center">
    <!-- 消息中心头部 -->
    <div class="notification-header">
      <div class="header-left">
        <h3 class="header-title">
          <BellOutlined />
          消息中心
          <a-badge :count="unreadCount" :offset="[10, 0]" />
        </h3>
        <div class="header-stats">
          <span>共 {{ totalMessages }} 条消息</span>
          <span v-if="unreadCount > 0">，{{ unreadCount }} 条未读</span>
        </div>
      </div>
      
      <div class="header-actions">
        <a-space>
          <a-button 
            @click="markAllAsRead"
            :disabled="unreadCount === 0"
            size="small"
          >
            全部已读
          </a-button>
          
          <a-button 
            @click="refreshMessages"
            :loading="loading"
            size="small"
          >
            <ReloadOutlined />
            刷新
          </a-button>
          
          <a-dropdown>
            <a-button size="small">
              <FilterOutlined />
              筛选
              <DownOutlined />
            </a-button>
            <template #overlay>
              <a-menu @click="handleFilterChange">
                <a-menu-item key="all">全部消息</a-menu-item>
                <a-menu-item key="unread">未读消息</a-menu-item>
                <a-menu-item key="urgent">紧急消息</a-menu-item>
                <a-menu-item key="today">今日消息</a-menu-item>
                <a-menu-divider />
                <a-menu-item key="rectification_required">整改要求</a-menu-item>
                <a-menu-item key="audit_result">审核结果</a-menu-item>
                <a-menu-item key="task_assigned">任务分配</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </a-space>
      </div>
    </div>

    <!-- 消息列表 -->
    <div class="notification-list">
      <a-spin :spinning="loading">
        <a-list
          :data-source="filteredMessages"
          item-layout="vertical"
          :pagination="paginationConfig"
          @change="handlePageChange"
        >
          <template #renderItem="{ item }">
            <a-list-item
              :class="[
                'message-item',
                `priority-${item.priority}`,
                { 
                  'unread': item.status !== 'read' && item.status !== 'processed',
                  'processed': item.status === 'processed',
                  'urgent': item.priority === 'urgent'
                }
              ]"
              @click="handleMessageClick(item)"
            >
              <!-- 优先级指示器 -->
              <div class="priority-indicator">
                <div :class="`priority-dot priority-${item.priority}`"></div>
              </div>

              <!-- 消息内容 -->
              <a-list-item-meta>
                <template #title>
                  <div class="message-title">
                    <span class="title-text">{{ item.title }}</span>
                    <div class="message-meta">
                      <a-tag 
                        :color="getMessageTypeColor(item.type)" 
                        size="small"
                      >
                        {{ getMessageTypeLabel(item.type) }}
                      </a-tag>
                      <span class="message-time">
                        {{ formatRelativeTime(item.created_at) }}
                      </span>
                    </div>
                  </div>
                </template>
                
                <template #description>
                  <div class="message-content">
                    <p class="content-text">
                      {{ item.summary || item.content.substring(0, 120) + '...' }}
                    </p>
                    
                    <!-- 关联信息 -->
                    <div class="related-info" v-if="hasRelatedInfo(item)">
                      <a-space size="small">
                        <span v-if="item.related_data.patient_id">
                          <UserOutlined />
                          患者: {{ item.related_data.patient_name || item.related_data.patient_id }}
                        </span>
                        <span v-if="item.related_data.medical_record_id">
                          <FileTextOutlined />
                          病历: {{ item.related_data.medical_record_id.substring(0, 8) }}...
                        </span>
                        <span v-if="item.related_data.task_name">
                          <ProjectOutlined />
                          任务: {{ item.related_data.task_name }}
                        </span>
                      </a-space>
                    </div>
                  </div>
                </template>
              </a-list-item-meta>

              <!-- 消息操作按钮 -->
              <template #actions>
                <div class="message-actions">
                  <a-space size="small">
                    <!-- 主要操作按钮 -->
                    <a-button 
                      v-for="action in getPrimaryActions(item)" 
                      :key="action.id"
                      :type="action.type"
                      size="small"
                      @click.stop="executeAction(action, item)"
                    >
                      {{ action.label }}
                    </a-button>
                    
                    <!-- 更多操作下拉菜单 -->
                    <a-dropdown v-if="hasSecondaryActions(item)">
                      <a-button size="small" type="text">
                        <MoreOutlined />
                      </a-button>
                      <template #overlay>
                        <a-menu>
                          <a-menu-item 
                            v-for="action in getSecondaryActions(item)"
                            :key="action.id"
                            @click="executeAction(action, item)"
                          >
                            {{ action.label }}
                          </a-menu-item>
                          <a-menu-divider />
                          <a-menu-item 
                            @click="markAsRead(item.id)" 
                            v-if="item.status !== 'read'"
                          >
                            <CheckOutlined />
                            标记已读
                          </a-menu-item>
                          <a-menu-item 
                            @click="markAsProcessed(item.id)" 
                            v-if="item.status !== 'processed'"
                          >
                            <CheckCircleOutlined />
                            标记已处理
                          </a-menu-item>
                          <a-menu-item 
                            @click="deleteMessage(item.id)"
                            danger
                          >
                            <DeleteOutlined />
                            删除消息
                          </a-menu-item>
                        </a-menu>
                      </template>
                    </a-dropdown>
                  </a-space>
                </div>
              </template>
            </a-list-item>
          </template>

          <!-- 空状态 -->
          <template #empty>
            <a-empty description="暂无消息">
              <a-button @click="refreshMessages" type="primary">
                刷新消息
              </a-button>
            </a-empty>
          </template>
        </a-list>
      </a-spin>
    </div>

    <!-- 消息详情抽屉 -->
    <a-drawer
      v-model:open="detailDrawerVisible"
      title="消息详情"
      width="600"
      placement="right"
    >
      <MessageDetail
        v-if="selectedMessage"
        :message="selectedMessage"
        @action-executed="handleActionExecuted"
        @close="detailDrawerVisible = false"
      />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  BellOutlined,
  ReloadOutlined,
  FilterOutlined,
  DownOutlined,
  UserOutlined,
  FileTextOutlined,
  ProjectOutlined,
  MoreOutlined,
  CheckOutlined,
  CheckCircleOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

import type { 
  QCNotification, 
  MessageType, 
  MessageAction,
  RecipientType
} from '@/types/audit-module'

import { useAuthStore } from '@/stores/auth'
import { notificationService } from '@/services/notification-service'
import { formatRelativeTime } from '@/utils/date-utils'
// import MessageDetail from './MessageDetail.vue'

// 状态管理
const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const messages = ref<QCNotification[]>([])
const currentFilter = ref('all')
const currentPage = ref(1)
const pageSize = ref(20)

// 消息详情
const detailDrawerVisible = ref(false)
const selectedMessage = ref<QCNotification | null>(null)

// 计算属性
const unreadCount = computed(() => 
  messages.value.filter(m => m.status !== 'read' && m.status !== 'processed').length
)

const totalMessages = computed(() => messages.value.length)

const filteredMessages = computed(() => {
  let filtered = messages.value

  switch (currentFilter.value) {
    case 'unread':
      filtered = filtered.filter(m => m.status !== 'read' && m.status !== 'processed')
      break
    case 'urgent':
      filtered = filtered.filter(m => m.priority === 'urgent')
      break
    case 'today':
      const today = new Date().toDateString()
      filtered = filtered.filter(m => 
        new Date(m.created_at).toDateString() === today
      )
      break
    default:
      if (currentFilter.value !== 'all') {
        // 按消息类型筛选
        filtered = filtered.filter(m => m.type === currentFilter.value)
      }
  }

  return filtered
})

const paginationConfig = computed(() => ({
  current: currentPage.value,
  pageSize: pageSize.value,
  total: filteredMessages.value.length,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) => 
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
}))

// 方法
const loadMessages = async () => {
  try {
    loading.value = true
    
    const userMessages = await notificationService.getUserNotifications(
      authStore.user.id,
      {
        limit: 100,
        offset: 0
      }
    )
    
    messages.value = userMessages
    
  } catch (error) {
    message.error(`加载消息失败: ${error.message}`)
  } finally {
    loading.value = false
  }
}

const refreshMessages = async () => {
  await loadMessages()
  message.success('消息已刷新')
}

const markAllAsRead = async () => {
  try {
    const unreadMessages = messages.value.filter(m => 
      m.status !== 'read' && m.status !== 'processed'
    )
    
    for (const msg of unreadMessages) {
      await notificationService.markAsRead(msg.id)
    }
    
    await loadMessages()
    message.success('所有消息已标记为已读')
    
  } catch (error) {
    message.error(`操作失败: ${error.message}`)
  }
}

const markAsRead = async (messageId: string) => {
  try {
    await notificationService.markAsRead(messageId)
    await loadMessages()
    message.success('已标记为已读')
  } catch (error: unknown) {
    message.error('操作失败')
  }
}

const markAsProcessed = async (messageId: string) => {
  try {
    await notificationService.markAsProcessed(messageId)
    await loadMessages()
    message.success('已标记为已处理')
  } catch (error: unknown) {
    message.error('操作失败')
  }
}

const deleteMessage = async (messageId: string) => {
  Modal.confirm({
    title: '确认删除', content: '确定要删除这条消息吗？', onOk: async () => {
      try {
        // 实现删除逻辑
        messages.value = messages.value.filter(m => m.id !== messageId)
        message.success('消息已删除')
      } catch (error) {
        message.error('删除失败')
      }
    }
  })
}

const handleFilterChange = ({ key }: { key: string }) => {
  currentFilter.value = key
  currentPage.value = 1
}

const handlePageChange = (page: number, size: number) => {
  currentPage.value = page
  pageSize.value = size
}

const handleMessageClick = (notification: QCNotification) => {
  selectedMessage.value = notification
  detailDrawerVisible.value = true
  
  // 自动标记为已读
  if (notification.status === 'pending' || notification.status === 'delivered') {
    markAsRead(notification.id)
  }
}

const executeAction = async (action: MessageAction, notification: QCNotification) => {
  try {
    switch (action.action) {
      case 'navigate':
        if (action.config.url) {
          await router.push({
            path: action.config.url,
            query: action.config.params
          })
        }
        break
        
      case 'api_call':
        if (action.config.api_endpoint) {
          // 实现API调用
          message.success('操作已执行')
        }
        break
        
      case 'modal':
        // 实现模态框打开
        break
        
      case 'confirm':
        Modal.confirm({
          title: '确认操作', content: action.config.confirm_message || '确定要执行此操作吗？', onOk: () => {
            // 执行确认后的操作
          }
        })
        break
    }
    
    // 标记消息为已处理
    await markAsProcessed(notification.id)
    
  } catch (error: unknown) {
    message.error('操作失败')
  }
}

const getPrimaryActions = (notification: QCNotification): MessageAction[] => {
  return (notification.actions || []).filter(action => 
    action.type === 'primary'
  ).slice(0, 2) // 最多显示2个主要操作
}

const getSecondaryActions = (notification: QCNotification): MessageAction[] => {
  return (notification.actions || []).filter(action => 
    action.type !== 'primary'
  )
}

const hasSecondaryActions = (notification: QCNotification): boolean => {
  return getSecondaryActions(notification).length > 0
}

const hasRelatedInfo = (notification: QCNotification): boolean => {
  const data = notification.related_data
  return !!(data.patient_id || data.medical_record_id || data.task_name)
}

const getMessageTypeColor = (type: MessageType): string => {
  const colorMap: Record<MessageType, string> = {
    'qc_completed': 'green',
    'rectification_required': 'orange',
    'audit_result': 'blue',
    'appeal_result': 'purple',
    'deadline_reminder': 'red',
    'system_announcement': 'cyan',
    'rectification_submitted': 'geekblue',
    'appeal_submitted': 'magenta',
    'task_assigned': 'volcano',
    'task_overdue': 'red',
    'batch_completed': 'lime',
    'expert_consultation': 'gold'
  }
  return colorMap[type] || 'default'
}

const getMessageTypeLabel = (type: MessageType): string => {
  const labelMap: Record<MessageType, string> = {
    'qc_completed': '质控完成',
    'rectification_required': '整改要求',
    'audit_result': '审核结果',
    'appeal_result': '申诉结果',
    'deadline_reminder': '截止提醒',
    'system_announcement': '系统公告',
    'rectification_submitted': '整改提交',
    'appeal_submitted': '申诉提交',
    'task_assigned': '任务分配',
    'task_overdue': '任务超期',
    'batch_completed': '批量完成',
    'expert_consultation': '专家会诊'
  }
  return labelMap[type] || type
}

const handleActionExecuted = () => {
  loadMessages()
}

const resolveRecipientType = (): RecipientType => {
  const roles = authStore.user?.roles || []
  if (roles.includes('admin')) return 'admin'
  if (roles.includes('reviewer')) return 'reviewer'
  return 'clinician'
}

// 实时消息监听
const setupRealTimeListener = () => {
  // 监听新消息事件
  window.addEventListener('new-notification', (event: Event) => {
    const newNotification = (event as CustomEvent<QCNotification>).detail
    messages.value.unshift(newNotification)
    
    // 显示通知提示
    if (newNotification.priority === 'urgent') {
      message.warning({
        content: `紧急消息：${newNotification.title}`,
        duration: 5
      })
    }
  })
  
  // 监听消息更新事件
  window.addEventListener('notification-updated', (event: Event) => {
    const updatedNotification = (event as CustomEvent<QCNotification>).detail
    const index = messages.value.findIndex(m => m.id === updatedNotification.id)
    if (index !== -1) {
      messages.value[index] = updatedNotification
    }
  })
}

const cleanupRealTimeListener = () => {
  window.removeEventListener('new-notification', () => {})
  window.removeEventListener('notification-updated', () => {})
}

// 生命周期
onMounted(async () => {
  await loadMessages()
  setupRealTimeListener()
  
  // 初始化实时通信
  await notificationService.initializeRealTime(
    authStore.user.id,
    resolveRecipientType()
  )
})

onUnmounted(() => {
  cleanupRealTimeListener()
  notificationService.cleanup()
})
</script>

<style scoped>
.notification-center {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px 8px 0 0;
}

.header-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
}

.header-stats {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 4px;
}

.header-actions :deep(.ant-btn) {
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
}

.header-actions :deep(.ant-btn:hover) {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.5);
}

.notification-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.message-item {
  position: relative;
  border-radius: 8px;
  margin-bottom: 12px;
  padding: 16px;
  border: 1px solid #f0f0f0;
  transition: all 0.3s ease;
  cursor: pointer;
}

.message-item:hover {
  background-color: #fafafa;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}

.message-item.unread {
  background-color: #fff7e6;
  border-left: 4px solid #faad14;
}

.message-item.urgent {
  border-left: 4px solid #ff4d4f;
  animation: pulse 2s infinite;
}

.message-item.processed {
  opacity: 0.7;
}

.priority-indicator {
  position: absolute;
  left: 12px;
  top: 20px;
}

.priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.priority-dot.priority-urgent {
  background-color: #ff4d4f;
}

.priority-dot.priority-high {
  background-color: #faad14;
}

.priority-dot.priority-normal {
  background-color: #52c41a;
}

.priority-dot.priority-low {
  background-color: #d9d9d9;
}

.message-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-left: 20px;
}

.title-text {
  font-weight: 500;
  color: #262626;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.message-time {
  color: #999;
  font-size: 12px;
}

.message-content {
  margin-left: 20px;
}

.content-text {
  color: #595959;
  line-height: 1.5;
  margin-bottom: 8px;
}

.related-info {
  color: #8c8c8c;
  font-size: 12px;
}

.message-actions {
  margin-left: 20px;
  margin-top: 12px;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(255, 77, 79, 0); }
  100% { box-shadow: 0 0 0 0 rgba(255, 77, 79, 0); }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .notification-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .header-actions {
    align-self: flex-end;
  }
  
  .message-title {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .message-meta {
    align-self: flex-start;
  }
}
</style>
