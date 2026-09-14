<template>
  <div class="qc-appeal-demo-panel">
    <a-card
      title="申诉功能演示"
      class="appeal-panel"
    >
      <template #extra>
        <a-space>
          <a-badge
            :count="pendingCount"
            :offset="[10, 0]"
          >
            <FormOutlined />
          </a-badge>
          <a-button
            type="primary"
            size="small"
            :icon="h(PlusOutlined)"
            :disabled="!activeNotification"
            @click="handleCreateAppeal"
          >
            新建申诉
          </a-button>
        </a-space>
      </template>

      <!-- 申诉控制和筛选 -->
      <div class="appeal-controls">
        <a-row
          :gutter="16"
          align="middle"
        >
          <a-col :span="6">
            <a-input-search
              v-model:value="searchKeyword"
              placeholder="搜索申诉编号或描述"
              @search="handleSearch"
              @change="handleSearch"
            />
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="filterStatus"
              placeholder="申诉状态"
              style="width: 100%"
              @change="handleFilterChange"
            >
              <a-select-option value="">
                全部状态
              </a-select-option>
              <a-select-option value="pending">
                待审核
              </a-select-option>
              <a-select-option value="reviewing">
                审核中
              </a-select-option>
              <a-select-option value="approved">
                已通过
              </a-select-option>
              <a-select-option value="rejected">
                已驳回
              </a-select-option>
              <a-select-option value="cancelled">
                已撤销
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-select
              v-model:value="filterReason"
              placeholder="申诉理由"
              style="width: 100%"
              @change="handleFilterChange"
            >
              <a-select-option value="">
                全部理由
              </a-select-option>
              <a-select-option value="rule_misapplication">
                规则误用
              </a-select-option>
              <a-select-option value="data_inaccuracy">
                数据不准确
              </a-select-option>
              <a-select-option value="context_missing">
                缺少上下文
              </a-select-option>
              <a-select-option value="technical_error">
                技术错误
              </a-select-option>
              <a-select-option value="other">
                其他原因
              </a-select-option>
            </a-select>
          </a-col>
          <a-col :span="4">
            <a-range-picker
              v-model:value="dateRange"
              style="width: 100%"
              @change="handleFilterChange"
            />
          </a-col>
          <a-col :span="6">
            <a-space>
              <a-button
                :icon="h(ReloadOutlined)"
                @click="handleRefresh"
              >
                刷新
              </a-button>
              <a-button
                :icon="h(DownloadOutlined)"
                @click="handleExport"
              >
                导出
              </a-button>
              <a-dropdown>
                <template #overlay>
                  <a-menu @click="handleBatchAction">
                    <a-menu-item key="approve">
                      批量通过
                    </a-menu-item>
                    <a-menu-item key="reject">
                      批量驳回
                    </a-menu-item>
                    <a-menu-item key="delete">
                      批量删除
                    </a-menu-item>
                  </a-menu>
                </template>
                <a-button>
                  批量操作
                  <DownOutlined />
                </a-button>
              </a-dropdown>
            </a-space>
          </a-col>
        </a-row>
      </div>

      <!-- 申诉统计 -->
      <div
        v-if="appeals.length > 0"
        class="appeal-stats"
      >
        <a-row :gutter="16">
          <a-col :span="4">
            <a-statistic
              title="总申诉"
              :value="appeals.length"
            />
          </a-col>
          <a-col :span="4">
            <a-statistic
              title="待审核"
              :value="pendingCount"
              :value-style="{ color: '#faad14' }"
            />
          </a-col>
          <a-col :span="4">
            <a-statistic
              title="审核中"
              :value="reviewingCount"
              :value-style="{ color: '#2b6cf6' }"
            />
          </a-col>
          <a-col :span="4">
            <a-statistic
              title="已通过"
              :value="approvedCount"
              :value-style="{ color: '#52c41a' }"
            />
          </a-col>
          <a-col :span="4">
            <a-statistic
              title="已驳回"
              :value="rejectedCount"
              :value-style="{ color: '#f5222d' }"
            />
          </a-col>
          <a-col :span="4">
            <a-statistic
              title="通过率"
              :value="approvalRate"
              suffix="%"
              :value-style="{ color: '#52c41a' }"
            />
          </a-col>
        </a-row>
      </div>

      <!-- 申诉列表 -->
      <div class="appeals-section">
        <div
          v-if="filteredAppeals.length === 0"
          class="empty-appeals"
        >
          <a-empty :description="appeals.length === 0 ? '暂无申诉记录' : '没有符合条件的申诉'">
            <a-button
              v-if="appeals.length === 0"
              type="primary"
              :disabled="!activeNotification"
              @click="handleCreateAppeal"
            >
              创建申诉
            </a-button>
          </a-empty>
        </div>

        <div
          v-else
          class="appeals-list"
        >
          <!-- 批量操作选择 -->
          <div
            v-if="filteredAppeals.length > 1"
            class="batch-selection"
          >
            <a-checkbox
              :indeterminate="
                selectedAppeals.length > 0 && selectedAppeals.length < filteredAppeals.length
              "
              :checked="selectedAppeals.length === filteredAppeals.length"
              @change="handleSelectAll"
            >
              全选 ({{ selectedAppeals.length }}/{{ filteredAppeals.length }})
            </a-checkbox>
          </div>

          <!-- 申诉项目列表 -->
          <div
            v-for="appeal in filteredAppeals"
            :key="appeal.id"
            class="appeal-item"
            :class="{
              active: currentAppeal?.id === appeal.id,
              selected: selectedAppeals.includes(appeal.id),
            }"
          >
            <!-- 选择框 -->
            <div
              v-if="filteredAppeals.length > 1"
              class="appeal-checkbox"
            >
              <a-checkbox
                :checked="selectedAppeals.includes(appeal.id)"
                @change="(e) => handleSelectAppealChange(appeal.id, e)"
              />
            </div>
            <div class="appeal-header">
              <div class="appeal-info">
                <a-tag :color="getStatusColor(appeal.status)">
                  {{ getStatusText(appeal.status) }}
                </a-tag>
                <span class="appeal-id">申诉编号: {{ appeal.id }}</span>
              </div>
              <div class="appeal-time">
                {{ formatTime(appeal.submittedAt) }}
              </div>
            </div>

            <div class="appeal-content">
              <h5>申诉理由: {{ getReasonText(appeal.reason) }}</h5>
              <p class="appeal-description">
                {{ appeal.description }}
              </p>
            </div>

            <div class="appeal-actions">
              <a-space>
                <a-button
                  size="small"
                  @click="handleViewAppeal(appeal)"
                >
                  查看详情
                </a-button>
                <a-button
                  v-if="appeal.status === 'pending'"
                  size="small"
                  @click="handleEditAppeal(appeal)"
                >
                  编辑
                </a-button>
                <a-button
                  v-if="appeal.status === 'pending'"
                  size="small"
                  danger
                  @click="handleCancelAppeal(appeal)"
                >
                  撤销
                </a-button>
              </a-space>
            </div>
          </div>
        </div>
      </div>

      <!-- 当前申诉详情 -->
      <div
        v-if="currentAppeal"
        class="current-appeal"
      >
        <a-divider>申诉详情</a-divider>
        <div class="appeal-details">
          <a-descriptions
            title="申诉信息"
            :column="2"
            bordered
            size="small"
          >
            <a-descriptions-item label="申诉编号">
              {{ currentAppeal.id }}
            </a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="getStatusColor(currentAppeal.status)">
                {{ getStatusText(currentAppeal.status) }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="申诉理由">
              {{ getReasonText(currentAppeal.reason) }}
            </a-descriptions-item>
            <a-descriptions-item label="提交时间">
              {{ formatTime(currentAppeal.submittedAt) }}
            </a-descriptions-item>
            <a-descriptions-item
              label="申诉描述"
              :span="2"
            >
              {{ currentAppeal.description }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="currentAppeal.reviewerComment"
              label="审核意见"
              :span="2"
            >
              {{ currentAppeal.reviewerComment }}
            </a-descriptions-item>
          </a-descriptions>

          <!-- 附件列表 -->
          <div
            v-if="currentAppeal.attachments.length > 0"
            class="attachments"
          >
            <h5>附件</h5>
            <a-list
              :data-source="currentAppeal.attachments"
              size="small"
            >
              <template #renderItem="{ item }">
                <a-list-item>
                  <a-list-item-meta>
                    <template #title>
                      <a-space>
                        <FileOutlined />
                        {{ item.name }}
                      </a-space>
                    </template>
                    <template #description>
                      大小: {{ formatFileSize(item.size) }}
                    </template>
                  </a-list-item-meta>
                </a-list-item>
              </template>
            </a-list>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="panel-actions">
        <a-space>
          <a-button
            type="primary"
            :disabled="!activeNotification"
            @click="handleCreateAppeal"
          >
            <PlusOutlined />
            创建申诉
          </a-button>
          <a-button @click="handleRefreshAppeals">
            <ReloadOutlined />
            刷新状态
          </a-button>
        </a-space>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h } from 'vue'
import { message } from 'ant-design-vue'
import type { MenuProps } from 'ant-design-vue'
import {
  FormOutlined,
  PlusOutlined,
  ReloadOutlined,
  FileOutlined,
  DownloadOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import type { CheckboxChangeEvent } from 'ant-design-vue/es/checkbox/interface'
import type { Appeal, QCNotification, AppealReason } from '@/types/quality-control'
import type { Dayjs } from 'dayjs'

// Props
const props = defineProps<{
  appeals: Appeal[]
  currentAppeal: Appeal | null
  activeNotification: QCNotification | null
}>()

// Emits
const emit = defineEmits<{
  appealCreated: [appeal: Appeal]
  appealAction: [action: string, appeal?: Appeal]
}>()

// 响应式数据
const searchKeyword = ref('')
const filterStatus = ref('')
const filterReason = ref('')
const dateRange = ref<[Dayjs, Dayjs] | null>(null)
const selectedAppeals = ref<string[]>([])

// 计算属性
const pendingCount = computed(() => props.appeals.filter((a) => a.status === 'pending').length)

const reviewingCount = computed(() => props.appeals.filter((a) => a.status === 'reviewing').length)

const approvedCount = computed(() => props.appeals.filter((a) => a.status === 'approved').length)

const rejectedCount = computed(() => props.appeals.filter((a) => a.status === 'rejected').length)

const approvalRate = computed(() => {
  const total = approvedCount.value + rejectedCount.value
  if (total === 0) return 0
  return Math.round((approvedCount.value / total) * 100)
})

const filteredAppeals = computed(() => {
  let filtered = [...props.appeals]

  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    filtered = filtered.filter(
      (appeal) =>
        appeal.id.toLowerCase().includes(keyword) ||
        appeal.description.toLowerCase().includes(keyword),
    )
  }

  // 状态筛选
  if (filterStatus.value) {
    filtered = filtered.filter((appeal) => appeal.status === filterStatus.value)
  }

  // 理由筛选
  if (filterReason.value) {
    filtered = filtered.filter((appeal) => appeal.reason === filterReason.value)
  }

  // 日期范围筛选
  if (dateRange.value && dateRange.value.length === 2) {
    const [start, end] = dateRange.value
    filtered = filtered.filter((appeal) => {
      const appealDate = new Date(appeal.submittedAt)
      return appealDate >= start.toDate() && appealDate <= end.toDate()
    })
  }

  return filtered.sort(
    (a, b) => new Date(b.submittedAt).getTime() - new Date(a.submittedAt).getTime(),
  )
})

// 方法
const getStatusColor = (status: string) => {
  const colors = {
    pending: 'orange',
    reviewing: 'blue',
    approved: 'green',
    rejected: 'red',
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getStatusText = (status: string) => {
  const texts = {
    pending: '待审核',
    reviewing: '审核中',
    approved: '已通过',
    rejected: '已拒绝',
  }
  return texts[status as keyof typeof texts] || status
}

const getReasonText = (reason: AppealReason) => {
  const texts = {
    rule_misapplication: '规则误用',
    data_inaccuracy: '数据不准确',
    context_missing: '缺少上下文',
    technical_error: '技术错误',
    other: '其他',
  }
  return texts[reason] || reason
}

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 事件处理
const handleSearch = () => {
  // 搜索逻辑已在计算属性中实现
}

const handleFilterChange = () => {
  // 筛选逻辑已在计算属性中实现
}

const handleRefresh = () => {
  emit('appealAction', 'refresh')
  message.success('申诉列表已刷新')
}

const handleExport = () => {
  emit('appealAction', 'export')
  message.info('导出申诉数据')
}

const handleBatchAction: MenuProps['onClick'] = ({ key }) => {
  if (selectedAppeals.value.length === 0) {
    message.warning('请先选择要操作的申诉')
    return
  }

  emit('appealAction', `batch-${String(key)}`)

  switch (key) {
    case 'approve':
      message.success(`已批量通过 ${selectedAppeals.value.length} 个申诉`)
      break
    case 'reject':
      message.success(`已批量驳回 ${selectedAppeals.value.length} 个申诉`)
      break
    case 'delete':
      message.success(`已批量删除 ${selectedAppeals.value.length} 个申诉`)
      break
  }

  selectedAppeals.value = []
}

const handleSelectAll = (e: CheckboxChangeEvent) => {
  const checked = e.target.checked
  if (checked) {
    selectedAppeals.value = filteredAppeals.value.map((appeal) => appeal.id)
  } else {
    selectedAppeals.value = []
  }
}

const handleSelectAppealChange = (appealId: string, e: CheckboxChangeEvent) => {
  handleSelectAppeal(appealId, e.target.checked)
}

const handleSelectAppeal = (appealId: string, checked: boolean) => {
  if (checked) {
    if (!selectedAppeals.value.includes(appealId)) {
      selectedAppeals.value.push(appealId)
    }
  } else {
    const index = selectedAppeals.value.indexOf(appealId)
    if (index > -1) {
      selectedAppeals.value.splice(index, 1)
    }
  }
}

const handleCreateAppeal = () => {
  if (!props.activeNotification) {
    message.warning('请先选择一个通知进行申诉')
    return
  }
  emit('appealAction', 'create')
}

const handleViewAppeal = (appeal: Appeal) => {
  message.info(`查看申诉详情: ${appeal.id}`)
}

const handleEditAppeal = (appeal: Appeal) => {
  message.info(`编辑申诉: ${appeal.id}`)
}

const handleCancelAppeal = (appeal: Appeal) => {
  message.info(`撤销申诉: ${appeal.id}`)
}

const handleRefreshAppeals = () => {
  message.info('刷新申诉状态')
}
</script>

<style scoped lang="less">
.qc-appeal-demo-panel {
  .appeal-panel {
    .appeals-section {
      margin-bottom: 24px;

      .empty-appeals {
        text-align: center;
        padding: 40px 0;
      }

      .appeals-list {
        .appeal-item {
          border: 1px solid #f0f0f0;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 12px;
          transition: all 0.3s;

          &:hover {
            border-color: #2b6cf6;
            box-shadow: 0 2px 8px rgba(43, 108, 246, 0.1);
          }

          &.active {
            border-color: #2b6cf6;
            background: #e6f7ff;
          }

          .appeal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;

            .appeal-info {
              display: flex;
              align-items: center;
              gap: 8px;

              .appeal-id {
                font-size: 12px;
                color: #666;
              }
            }

            .appeal-time {
              font-size: 12px;
              color: #666;
            }
          }

          .appeal-content {
            margin-bottom: 12px;

            h5 {
              font-weight: 600;
              margin: 0 0 4px 0;
              color: #333;
            }

            .appeal-description {
              margin: 0;
              color: #666;
              font-size: 14px;
            }
          }

          .appeal-actions {
            text-align: right;
          }
        }
      }
    }

    .current-appeal {
      .appeal-details {
        .attachments {
          margin-top: 16px;

          h5 {
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
          }
        }
      }
    }

    .panel-actions {
      text-align: center;
      padding-top: 16px;
      border-top: 1px solid #f0f0f0;
    }
  }
}
</style>
