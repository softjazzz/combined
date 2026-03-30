<template>
  <div class="appeal-manager">
    <!-- 顶部操作栏 -->
    <div class="manager-header">
      <a-space
        direction="vertical"
        :size="12"
        style="width: 100%"
      >
        <!-- 状态筛选 -->
        <a-radio-group
          v-model:value="statusFilter"
          button-style="solid"
          size="small"
        >
          <a-radio-button value="">
            全部 ({{ demoStore.appeals.length }})
          </a-radio-button>
          <a-radio-button value="pending">
            待审核 ({{ getCountByStatus('pending') }})
          </a-radio-button>
          <a-radio-button value="reviewing">
            审核中 ({{ getCountByStatus('reviewing') }})
          </a-radio-button>
          <a-radio-button value="approved">
            已通过 ({{ getCountByStatus('approved') }})
          </a-radio-button>
          <a-radio-button value="rejected">
            已驳回 ({{ getCountByStatus('rejected') }})
          </a-radio-button>
        </a-radio-group>
      </a-space>
    </div>

    <!-- 申诉列表 -->
    <a-table
      :columns="columns"
      :data-source="filteredAppeals"
      :pagination="pagination"
      size="small"
      :scroll="{ y: 500 }"
      class="appeal-table"
    >
      <template #bodyCell="{ column, record }">
        <!-- 申诉类型 -->
        <template v-if="column.key === 'reason'">
          <a-tag :color="getReasonColor(record.reason)">
            {{ getReasonLabel(record.reason) }}
          </a-tag>
        </template>

        <!-- 状态 -->
        <template v-if="column.key === 'status'">
          <a-badge
            :status="getStatusBadge(record.status)"
            :text="getStatusLabel(record.status)"
          />

          <!-- 审核进度条（仅审核中状态） -->
          <a-progress
            v-if="record.status === 'reviewing'"
            :percent="getReviewProgress(asAppeal(record))"
            :show-info="false"
            size="small"
            style="margin-top: 4px"
          />
        </template>

        <!-- 提交时间 -->
        <template v-if="column.key === 'submittedAt'">
          {{ formatTime(record.submittedAt) }}
        </template>

        <!-- 操作 -->
        <template v-if="column.key === 'actions'">
          <a-space :size="4">
            <a-button
              type="link"
              size="small"
              @click="handleViewDetail(asAppeal(record))"
            >
              查看
            </a-button>
            <a-button
              v-if="record.status === 'pending'"
              type="link"
              size="small"
              danger
              @click="handleCancel(record.id)"
            >
              撤销
            </a-button>
            <a-popconfirm
              title="确认删除此申诉？"
              ok-text="确认"
              cancel-text="取消"
              @confirm="handleDelete(record.id)"
            >
              <a-button
                type="link"
                size="small"
                danger
              >
                删除
              </a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>

      <!-- 展开行：显示申诉详情 -->
      <template #expandedRowRender="{ record }">
        <a-descriptions
          :column="2"
          size="small"
          bordered
        >
          <a-descriptions-item label="申诉ID">
            {{ record.id }}
          </a-descriptions-item>
          <a-descriptions-item label="关联通知ID">
            {{ record.notificationId || '无' }}
          </a-descriptions-item>
          <a-descriptions-item
            label="申诉描述"
            :span="2"
          >
            {{ record.description }}
          </a-descriptions-item>
          <a-descriptions-item label="提交人">
            {{ record.submittedBy }}
          </a-descriptions-item>
          <a-descriptions-item label="提交时间">
            {{ formatTime(record.submittedAt) }}
          </a-descriptions-item>
          <a-descriptions-item
            v-if="record.reviewedAt"
            label="审核时间"
          >
            {{ formatTime(record.reviewedAt) }}
          </a-descriptions-item>
          <a-descriptions-item
            v-if="record.reviewedBy"
            label="审核人"
          >
            {{ record.reviewedBy }}
          </a-descriptions-item>
          <a-descriptions-item
            v-if="record.reviewerComment"
            label="审核意见"
            :span="2"
          >
            {{ record.reviewerComment }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-table>

    <!-- 空状态 -->
    <a-empty
      v-if="filteredAppeals.length === 0"
      description="暂无申诉记录"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message, Empty } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import type { BadgeProps } from 'ant-design-vue'
import { useQCDemoStore } from '@/stores/qcDemo'
import type { Appeal, AppealStatus } from '@/types/quality-control'
import dayjs from 'dayjs'

const demoStore = useQCDemoStore()

// 状态筛选
const statusFilter = ref<AppealStatus | ''>('')

// 计算属性
const filteredAppeals = computed(() => {
  if (!statusFilter.value) {
    return demoStore.appeals
  }
  return demoStore.appeals.filter((a) => a.status === statusFilter.value)
})

// 表格配置
const columns: TableColumnsType<Appeal> = [
  { title: '申诉ID', dataIndex: 'id', key: 'id', width: 150, ellipsis: true },
  { title: '申诉类型', key: 'reason', width: 120 },
  { title: '状态', key: 'status', width: 150 },
  { title: '提交人', dataIndex: 'submittedBy', key: 'submittedBy', width: 100 },
  { title: '提交时间', key: 'submittedAt', width: 180 },
  { title: '操作', key: 'actions', width: 150, fixed: 'right' as const },
]

const pagination = {
  pageSize: 10,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`,
}

// 工具函数
const getCountByStatus = (status: AppealStatus) => {
  return demoStore.appeals.filter((a) => a.status === status).length
}

const getReasonColor = (reason: string) => {
  const colors = {
    rule_misapplication: 'blue',
    data_error: 'orange',
    system_error: 'red',
    other: 'default',
  }
  return colors[reason as keyof typeof colors] || 'default'
}

const getReasonLabel = (reason: string) => {
  const labels = {
    rule_misapplication: '规则误用',
    data_error: '数据错误',
    system_error: '系统错误',
    other: '其他',
  }
  return labels[reason as keyof typeof labels] || reason
}

const getStatusBadge = (status: AppealStatus): BadgeProps['status'] => {
  const badges = {
    pending: 'default',
    reviewing: 'processing',
    approved: 'success',
    rejected: 'error',
    cancelled: 'warning',
  } as const
  return badges[status] || 'default'
}

const getStatusLabel = (status: AppealStatus) => {
  const labels = {
    pending: '待审核',
    reviewing: '审核中',
    approved: '已通过',
    rejected: '已驳回',
    cancelled: '已撤销',
  }
  return labels[status] || status
}

const getReviewProgress = (appeal: Appeal) => {
  // 模拟审核进度（5秒开始，8秒完成）
  if (appeal.status !== 'reviewing') return 0

  const now = Date.now()
  const submittedTime = new Date(appeal.submittedAt).getTime()
  const elapsed = now - submittedTime

  // 5秒开始审核，8秒完成
  if (elapsed < 5000) return 0
  if (elapsed > 13000) return 100

  return Math.floor(((elapsed - 5000) / 8000) * 100)
}

const asAppeal = (record: unknown) => record as Appeal

const formatTime = (timestamp: Date | string) => {
  return dayjs(timestamp).format('YYYY-MM-DD HH:mm:ss')
}

// 事件处理
const handleViewDetail = (appeal: Appeal) => {
  message.info(`查看申诉详情：${appeal.id}`)
  // 可以打开详情模态框或跳转到详情页
}

const handleCancel = (appealId: string) => {
  demoStore.handleAppealAction('cancel', { id: appealId })
  message.success('申诉已撤销')
}

const handleDelete = (appealId: string) => {
  demoStore.handleAppealAction('batch-delete', [appealId])
  message.success('申诉已删除')
}
</script>

<style scoped lang="less">
.appeal-manager {
  .manager-header {
    margin-bottom: 16px;
  }

  .appeal-table {
    :deep(.ant-table-expanded-row) {
      background-color: #fafafa;
    }
  }
}
</style>
