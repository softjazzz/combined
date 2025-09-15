<template>
  <a-modal
    v-model:visible="modalVisible"
    :title="modalTitle"
    width="1000px"
    :footer="null"
    @cancel="handleCancel"
    :body-style="{ padding: '24px' }"
  >
    <div v-if="notification" class="notification-modal-content">
      <!-- 通知头部信息 -->
      <div class="notification-header">
        <div class="header-left">
          <div class="notification-type-info">
            <a-tag :color="getNotificationColor(notification.type)" size="large">
              <component :is="getNotificationIcon(notification.type)" />
              {{ getNotificationTypeText(notification.type) }}
            </a-tag>
            <a-tag
              v-if="notification.severity"
              :color="getSeverityColor(notification.severity)"
              size="large"
            >
              {{ getSeverityText(notification.severity) }}
            </a-tag>
            <a-tag v-if="!notification.isRead" color="red">
              未读
            </a-tag>
          </div>
          <h2 class="notification-title">{{ notification.title }}</h2>
        </div>
        <div class="header-right">
          <div class="notification-time">
            <a-tooltip :title="formatFullTime(notification.timestamp)">
              {{ formatRelativeTime(notification.timestamp) }}
            </a-tooltip>
          </div>
          <div class="notification-actions">
            <a-space>
              <a-tooltip title="标记已读">
                <a-button
                  type="text"
                  :icon="h(CheckOutlined)"
                  @click="handleMarkAsRead"
                  v-if="!notification.isRead"
                />
              </a-tooltip>
              <a-tooltip title="分享">
                <a-button
                  type="text"
                  :icon="h(ShareAltOutlined)"
                  @click="handleShare"
                />
              </a-tooltip>
            </a-space>
          </div>
        </div>
      </div>

      <!-- 通知内容 -->
      <div class="notification-content">
        <p class="notification-message">{{ notification.message }}</p>

        <!-- 病历信息卡片 -->
        <div v-if="notification.recordInfo" class="record-info-card">
          <a-card size="small" title="相关病历信息">
            <a-descriptions :column="3" size="small">
              <a-descriptions-item label="患者姓名">
                {{ notification.recordInfo.patientName }}
              </a-descriptions-item>
              <a-descriptions-item label="病历号">
                {{ notification.recordInfo.recordNumber }}
              </a-descriptions-item>
              <a-descriptions-item label="科室">
                {{ notification.recordInfo.department }}
              </a-descriptions-item>
              <a-descriptions-item label="主治医生">
                {{ notification.recordInfo.doctor }}
              </a-descriptions-item>
              <a-descriptions-item label="入院日期">
                {{ notification.recordInfo.admissionDate }}
              </a-descriptions-item>
              <a-descriptions-item label="病历状态">
                <a-tag color="blue">{{ notification.recordInfo.status }}</a-tag>
              </a-descriptions-item>
            </a-descriptions>
          </a-card>
        </div>
      </div>

      <!-- 质控结果详情 -->
      <div class="qc-result-details" v-if="notification.qcResult">
        <a-divider>
          <span style="font-size: 16px; font-weight: 600;">质控分析结果</span>
        </a-divider>

        <!-- 总体评分和统计 -->
        <div class="score-section">
          <a-row :gutter="24">
            <a-col :span="6">
              <div class="score-card">
                <a-statistic
                  title="总体评分"
                  :value="notification.qcResult.overallScore"
                  suffix="分"
                  :value-style="{
                    color: getScoreColor(notification.qcResult.overallScore),
                    fontSize: '32px',
                    fontWeight: 'bold'
                }"
                />
                <div class="score-indicator">
                  <a-progress
                    :percent="notification.qcResult.overallScore"
                    :stroke-color="getScoreColor(notification.qcResult.overallScore)"
                    :show-info="false"
                    stroke-width="8"
                  />
                </div>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="stat-card">
                <a-statistic
                  title="质控等级"
                  :value="getQualityGrade(notification.qcResult.overallScore)"
                  :value-style="{
                    fontSize: '20px',
                    color: getScoreColor(notification.qcResult.overallScore)
                  }"
                />
                <div class="grade-description">
                  {{ getGradeDescription(notification.qcResult.overallScore) }}
                </div>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="stat-card">
                <a-statistic
                  title="发现问题"
                  :value="notification.qcResult.issues?.length || 0"
                  suffix="个"
                  :value-style="{ color: '#cf1322', fontSize: '20px' }"
                />
                <div class="stat-description">
                  需要关注和处理
                </div>
              </div>
            </a-col>
            <a-col :span="6">
              <div class="stat-card">
                <a-statistic
                  title="改进建议"
                  :value="notification.qcResult.suggestions?.length || 0"
                  suffix="条"
                  :value-style="{ color: '#1890ff', fontSize: '20px' }"
                />
                <div class="stat-description">
                  优化建议
                </div>
              </div>
            </a-col>
          </a-row>
        </div>

        <!-- 详细分析标签页 -->
        <div class="analysis-tabs">
          <a-tabs v-model:activeKey="activeTab" type="card">
            <a-tab-pane key="issues" tab="问题详情">
              <div v-if="notification.qcResult.issues && notification.qcResult.issues.length > 0" class="issues-section">
                <a-list
                  :data-source="notification.qcResult.issues"
                  :pagination="{ pageSize: 3, size: 'small' }"
                >
                  <template #renderItem="{ item, index }">
                    <a-list-item class="issue-item">
                      <a-list-item-meta>
                        <template #avatar>
                          <a-avatar
                            :style="{ backgroundColor: getSeverityColor(item.severity) }"
                            :size="40"
                          >
                            {{ index + 1 }}
                          </a-avatar>
                        </template>
                        <template #title>
                          <a-space>
                            <a-tag :color="getSeverityColor(item.severity)">
                              {{ getSeverityText(item.severity) }}
                            </a-tag>
                            <span class="issue-rule">{{ item.ruleName }}</span>
                          </a-space>
                        </template>
                        <template #description>
                          <div class="issue-description">
                            <p>{{ item.description }}</p>
                            <div v-if="item.location" class="issue-location">
                              <a-tag color="blue" size="small">
                                <EnvironmentOutlined />
                                {{ item.location }}
                              </a-tag>
                            </div>
                            <div v-if="item.suggestion" class="issue-suggestion">
                              <a-alert
                                :message="item.suggestion"
                                type="info"
                                size="small"
                                show-icon
                              />
                            </div>
                          </div>
                        </template>
                      </a-list-item-meta>
                      <template #actions>
                        <a-space>
                          <a-tooltip title="查看详情">
                            <a-button size="small" type="text" :icon="h(EyeOutlined)" />
                          </a-tooltip>
                          <a-tooltip title="申诉此问题" v-if="item.canAppeal">
                            <a-button
                              size="small"
                              type="text"
                              :icon="h(FormOutlined)"
                              @click="handleAppealIssue(item)"
                            />
                          </a-tooltip>
                        </a-space>
                      </template>
                    </a-list-item>
                  </template>
                </a-list>
              </div>
              <div v-else class="no-issues">
                <a-empty description="未发现质控问题">
                  <template #image>
                    <CheckCircleOutlined style="font-size: 48px; color: #52c41a;" />
                  </template>
                </a-empty>
              </div>
            </a-tab-pane>

            <a-tab-pane key="suggestions" tab="改进建议">
              <div v-if="notification.qcResult.suggestions && notification.qcResult.suggestions.length > 0" class="suggestions-section">
                <a-list
                  :data-source="notification.qcResult.suggestions"
                  :pagination="{ pageSize: 5, size: 'small' }"
                >
                  <template #renderItem="{ item, index }">
                    <a-list-item class="suggestion-item">
                      <a-list-item-meta>
                        <template #avatar>
                          <a-avatar :style="{ backgroundColor: '#1890ff' }">
                            <BulbOutlined />
                          </a-avatar>
                        </template>
                        <template #title>
                          <span class="suggestion-title">建议 {{ index + 1 }}</span>
                        </template>
                        <template #description>
                          <div class="suggestion-content">
                            <p>{{ item.description }}</p>
                            <div v-if="item.priority" class="suggestion-priority">
                              <a-tag :color="getPriorityColor(item.priority)">
                                {{ getPriorityText(item.priority) }}
                              </a-tag>
                            </div>
                          </div>
                        </template>
                      </a-list-item-meta>
                    </a-list-item>
                  </template>
                </a-list>
              </div>
              <div v-else class="no-suggestions">
                <a-empty description="暂无改进建议" />
              </div>
            </a-tab-pane>

            <a-tab-pane key="timeline" tab="分析时间线">
              <div class="timeline-section">
                <a-timeline>
                  <a-timeline-item color="blue">
                    <template #dot>
                      <PlayCircleOutlined />
                    </template>
                    <div class="timeline-content">
                      <h5>开始质控分析</h5>
                      <p>{{ formatFullTime(notification.qcResult.analysisStartTime || notification.timestamp) }}</p>
                    </div>
                  </a-timeline-item>
                  <a-timeline-item color="orange">
                    <template #dot>
                      <ScanOutlined />
                    </template>
                    <div class="timeline-content">
                      <h5>规则匹配完成</h5>
                      <p>应用了 {{ notification.qcResult.appliedRules?.length || 0 }} 条质控规则</p>
                    </div>
                  </a-timeline-item>
                  <a-timeline-item color="green">
                    <template #dot>
                      <CheckCircleOutlined />
                    </template>
                    <div class="timeline-content">
                      <h5>分析完成</h5>
                      <p>{{ formatFullTime(notification.qcResult.analysisEndTime || notification.timestamp) }}</p>
                    </div>
                  </a-timeline-item>
                </a-timeline>
              </div>
            </a-tab-pane>
          </a-tabs>
        </div>
      </div>

      <!-- 操作按钮区域 -->
      <div class="modal-actions">
        <a-divider />
        <a-row :gutter="16">
          <a-col :span="12">
            <a-space direction="vertical" style="width: 100%;">
              <h4>通知操作</h4>
              <a-space wrap>
                <a-button
                  type="primary"
                  :icon="h(CheckOutlined)"
                  @click="handleConfirm"
                >
                  确认已知
                </a-button>
                <a-button
                  :icon="h(EyeInvisibleOutlined)"
                  @click="handleIgnore"
                >
                  忽略通知
                </a-button>
                <a-button
                  :icon="h(ShareAltOutlined)"
                  @click="handleShare"
                >
                  分享
                </a-button>
              </a-space>
            </a-space>
          </a-col>
          <a-col :span="12">
            <a-space direction="vertical" style="width: 100%;">
              <h4>质控申诉</h4>
              <a-space wrap>
                <a-button
                  v-if="notification.canAppeal"
                  type="primary"
                  danger
                  :icon="h(FormOutlined)"
                  @click="handleAppeal"
                >
                  提交申诉
                </a-button>
                <a-button
                  :icon="h(HistoryOutlined)"
                  @click="handleViewHistory"
                >
                  查看历史
                </a-button>
                <a-button
                  :icon="h(PrinterOutlined)"
                  @click="handlePrint"
                >
                  打印报告
                </a-button>
              </a-space>
            </a-space>
          </a-col>
        </a-row>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-notification">
      <a-empty description="未选择通知" />
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  FormOutlined,
  WarningOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  ShareAltOutlined,
  HistoryOutlined,
  PrinterOutlined,
  EnvironmentOutlined,
  BulbOutlined,
  PlayCircleOutlined,
  ScanOutlined
} from '@ant-design/icons-vue'
import type { QCNotification } from '@/types/quality-control'

// Props
const props = defineProps<{
  visible: boolean
  notification: QCNotification | null
}>()

// Emits
const emit = defineEmits<{
  'update:visible': [visible: boolean]
  action: [action: string, notification: QCNotification]
}>()

// 响应式数据
const activeTab = ref('issues')

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

const modalTitle = computed(() => {
  if (!props.notification) return '质控通知详情'
  return `质控通知详情 - ${props.notification.type === 'error' ? '错误' :
    props.notification.type === 'warning' ? '警告' :
    props.notification.type === 'info' ? '信息' : '成功'}`
})

// 方法
const getNotificationColor = (type: string) => {
  const colors = {
    success: 'green',
    info: 'blue',
    warning: 'orange',
    error: 'red'
  }
  return colors[type as keyof typeof colors] || 'default'
}

const getNotificationIcon = (type: string) => {
  const icons = {
    success: 'CheckCircleOutlined',
    info: 'InfoCircleOutlined',
    warning: 'WarningOutlined',
    error: 'ExclamationCircleOutlined'
  }
  return icons[type as keyof typeof icons] || 'InfoCircleOutlined'
}

const getNotificationTypeText = (type: string) => {
  const texts = {
    success: '成功',
    info: '信息',
    warning: '警告',
    error: '错误'
  }
  return texts[type as keyof typeof texts] || type
}

const getSeverityColor = (severity: string) => {
  const colors = {
    low: 'green',
    medium: 'orange',
    high: 'red',
    critical: 'red'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityText = (severity: string) => {
  const texts = {
    low: '轻微',
    medium: '中等',
    high: '严重',
    critical: '紧急'
  }
  return texts[severity as keyof typeof texts] || severity
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const getQualityGrade = (score: number) => {
  if (score >= 95) return '优秀'
  if (score >= 90) return '良好'
  if (score >= 80) return '合格'
  if (score >= 60) return '待改进'
  return '不合格'
}

const getGradeDescription = (score: number) => {
  if (score >= 95) return '质量优秀，无需改进'
  if (score >= 90) return '质量良好，可继续保持'
  if (score >= 80) return '质量合格，建议优化'
  if (score >= 60) return '质量待改进，需要关注'
  return '质量不合格，需要立即改进'
}

const getPriorityColor = (priority: string) => {
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'green'
  }
  return colors[priority as keyof typeof colors] || 'default'
}

const getPriorityText = (priority: string) => {
  const texts = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级'
  }
  return texts[priority as keyof typeof texts] || priority
}

const formatRelativeTime = (timestamp: Date) => {
  const now = new Date()
  const diff = now.getTime() - new Date(timestamp).getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (days > 0) return `${days}天前`
  if (hours > 0) return `${hours}小时前`
  if (minutes > 0) return `${minutes}分钟前`
  return '刚刚'
}

const formatFullTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

// 事件处理方法
const handleCancel = () => {
  modalVisible.value = false
}

const handleConfirm = () => {
  if (props.notification) {
    emit('action', 'confirm', props.notification)
    message.success('已确认通知')
  }
}

const handleIgnore = () => {
  if (props.notification) {
    emit('action', 'ignore', props.notification)
    message.info('已忽略通知')
  }
}

const handleMarkAsRead = () => {
  if (props.notification) {
    emit('action', 'markRead', props.notification)
    message.success('已标记为已读')
  }
}

const handleAppeal = () => {
  if (props.notification) {
    emit('action', 'appeal', props.notification)
    message.info('开始申诉流程')
  }
}

const handleAppealIssue = (issue: any) => {
  if (props.notification) {
    emit('action', 'appealIssue', { ...props.notification, selectedIssue: issue })
    message.info('开始针对此问题的申诉')
  }
}

const handleShare = () => {
  if (props.notification) {
    emit('action', 'share', props.notification)
    message.info('分享功能开发中')
  }
}

const handleViewHistory = () => {
  if (props.notification) {
    emit('action', 'viewHistory', props.notification)
    message.info('查看历史记录')
  }
}

const handlePrint = () => {
  if (props.notification) {
    emit('action', 'print', props.notification)
    message.info('打印功能开发中')
  }
}
</script>

<style scoped lang="less">
.notification-modal-content {
  .notification-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 2px solid #f0f0f0;

    .header-left {
      flex: 1;

      .notification-type-info {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
        flex-wrap: wrap;
      }

      .notification-title {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: #333;
        line-height: 1.4;
      }
    }

    .header-right {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;

      .notification-time {
        color: #666;
        font-size: 14px;
        white-space: nowrap;
      }

      .notification-actions {
        display: flex;
        gap: 4px;
      }
    }
  }

  .notification-content {
    margin-bottom: 24px;

    .notification-message {
      font-size: 16px;
      line-height: 1.6;
      color: #666;
      margin-bottom: 16px;
    }

    .record-info-card {
      margin-top: 16px;

      :deep(.ant-card-head) {
        padding: 12px 16px;
        min-height: auto;
      }

      :deep(.ant-card-body) {
        padding: 16px;
      }
    }
  }

  .qc-result-details {
    .score-section {
      margin-bottom: 24px;
      padding: 20px;
      background: linear-gradient(135deg, #f6ffed 0%, #f0f9ff 100%);
      border-radius: 8px;
      border: 1px solid #d9f7be;

      .score-card {
        text-align: center;

        .score-indicator {
          margin-top: 8px;
        }
      }

      .stat-card {
        text-align: center;

        .grade-description,
        .stat-description {
          font-size: 12px;
          color: #666;
          margin-top: 4px;
        }
      }
    }

    .analysis-tabs {
      margin-top: 20px;

      :deep(.ant-tabs-card .ant-tabs-tab) {
        border-radius: 6px 6px 0 0;
      }

      .issues-section {
        .issue-item {
          margin-bottom: 16px;
          padding: 16px;
          border: 1px solid #f0f0f0;
          border-radius: 8px;
          transition: all 0.3s;

          &:hover {
            border-color: #1890ff;
            box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
          }

          .issue-description {
            .issue-location {
              margin: 8px 0;
            }

            .issue-suggestion {
              margin-top: 12px;
            }
          }
        }
      }

      .suggestions-section {
        .suggestion-item {
          margin-bottom: 12px;
          padding: 12px;
          border: 1px solid #f0f0f0;
          border-radius: 6px;

          .suggestion-content {
            .suggestion-priority {
              margin-top: 8px;
            }
          }
        }
      }

      .timeline-section {
        padding: 16px;

        .timeline-content {
          h5 {
            margin: 0 0 4px 0;
            font-weight: 600;
          }

          p {
            margin: 0;
            color: #666;
            font-size: 14px;
          }
        }
      }

      .no-issues,
      .no-suggestions {
        text-align: center;
        padding: 40px 0;
      }
    }
  }

  .modal-actions {
    margin-top: 24px;

    h4 {
      margin-bottom: 12px;
      font-weight: 600;
      color: #333;
    }
  }

  .empty-notification {
    text-align: center;
    padding: 60px 0;
  }
}

</style>
