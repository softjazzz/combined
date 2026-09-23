<template>
  <div class="appeal-list">
    <a-page-header
      title="质控申诉"
      sub-title="申诉记录管理"
      class="bg-white mb-4 shadow-sm"
    />

    <div class="px-6 pb-6">
      <a-card
        :bordered="false"
        class="shadow-sm"
      >
        <!-- 筛选区域 -->
        <a-form
          layout="inline"
          class="mb-4"
        >
          <a-form-item label="状态">
            <a-select
              v-model:value="filters.status"
              placeholder="全部状态"
              allow-clear
              style="width: 120px"
              @change="handleSearch"
            >
              <a-select-option
                v-for="opt in statusOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="申诉类型">
            <a-select
              v-model:value="filters.appealType"
              placeholder="全部类型"
              allow-clear
              style="width: 140px"
              @change="handleSearch"
            >
              <a-select-option
                v-for="opt in APPEAL_TYPE_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item>
            <a-button
              type="primary"
              @click="handleSearch"
            >
              查询
            </a-button>
            <a-button
              class="ml-2"
              @click="resetFilters"
            >
              重置
            </a-button>
          </a-form-item>
        </a-form>

        <a-alert
          v-if="listError"
          type="error"
          :message="listError"
          show-icon
          class="mb-4"
        >
          <template #action>
            <a-button
              size="small"
              @click="fetchAppeals"
            >
              重试
            </a-button>
          </template>
        </a-alert>

        <!-- 列表 -->
        <a-table
          v-if="!listError"
          :columns="columns"
          :data-source="appeals"
          :loading="loading"
          :pagination="pagination"
          :scroll="{ x: 1000 }"
          :locale="{ emptyText: listError || '暂无申诉记录' }"
          row-key="id"
          @change="handleTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getAppealStatusInfo(asAppeal(record).status).color">
                {{ getAppealStatusInfo(asAppeal(record).status).label }}
              </a-tag>
            </template>
            <template v-if="column.key === 'appealType'">
              {{ getAppealTypeLabel(asAppeal(record).appealType) }}
            </template>
            <template v-if="column.key === 'createdAt'">
              {{ formatDate(asAppeal(record).createdAt) }}
            </template>
            <template v-if="column.key === 'reviewer'">
              <div
                v-if="asAppeal(record).reviewerName"
                class="text-xs"
              >
                <div>{{ asAppeal(record).reviewerName }}</div>
                <div>{{ formatDate(asAppeal(record).reviewedAt) }}</div>
              </div>
              <span v-else>-</span>
            </template>
            <template v-if="column.key === 'action'">
              <a-space>
                <a-button
                  size="small"
                  @click="viewDetail(asAppeal(record))"
                >
                  详情
                </a-button>
                <a-button
                  v-if="canReview(asAppeal(record))"
                  type="primary"
                  ghost
                  size="small"
                  @click="openReviewModal(asAppeal(record))"
                >
                  审核
                </a-button>
                <a-popconfirm
                  v-if="canWithdraw(asAppeal(record))"
                  title="确定撤销此申诉吗？"
                  @confirm="handleWithdraw(asAppeal(record))"
                >
                  <a-button
                    size="small"
                    danger
                  >
                    撤销
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- Modals -->
    <AppealReviewModal
      v-model:visible="showReviewModal"
      :appeal="currentAppeal"
      @success="refresh"
    />
    <a-modal
      v-model:open="showDetailModal"
      title="申诉详情"
      :footer="null"
      :width="680"
    >
      <a-spin :spinning="detailLoading">
        <a-alert
          v-if="detailError"
          type="error"
          :message="detailError"
          show-icon
        />
        <a-descriptions
          v-else-if="detailAppeal"
          bordered
          :column="1"
          size="small"
        >
          <a-descriptions-item label="申诉编号">
            {{ detailAppeal.appealNumber || detailAppeal.id }}
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            {{ getAppealStatusInfo(detailAppeal.status).label }}
          </a-descriptions-item>
          <a-descriptions-item label="申诉类型">
            {{ getAppealTypeLabel(detailAppeal.appealType) }}
          </a-descriptions-item>
          <a-descriptions-item label="申诉人">
            {{ detailAppeal.appellantName || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="科室">
            {{ detailAppeal.appellantDepartment || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="缺陷项">
            {{ detailAppeal.defectItem || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="申诉理由">
            <span class="detail-text">{{ detailAppeal.appealReason }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="处理决定">
            <span class="detail-text">{{ detailAppeal.resolution || '-' }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="审核意见">
            {{ detailAppeal.reviewResult || '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="备注">
            <span class="detail-text">{{ detailAppeal.notes || '-' }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="提交时间">
            {{ formatDate(detailAppeal.createdAt) }}
          </a-descriptions-item>
          <a-descriptions-item label="审核历史">
            <div v-if="detailAppeal.reviews?.length">
              <div
                v-for="review in detailAppeal.reviews"
                :key="review.id"
                class="review-entry"
              >
                {{ review.reviewerName || '审核人' }} · {{ reviewActionLabel(review.action) }} · {{ formatDate(review.createdAt) }}
                <div
                  v-if="review.comment"
                  class="detail-text"
                >
                  {{ review.comment }}
                </div>
              </div>
            </div>
            <span v-else>暂无审核记录</span>
          </a-descriptions-item>
        </a-descriptions>
      </a-spin>
    </a-modal>
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { message } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  Appeal,
  type AppealStatusFilter,
  type AppealType,
  type AppealReviewAction,
  APPEAL_STATUS_OPTIONS,
  APPEAL_TYPE_OPTIONS,
  getAppealStatusInfo,
  getAppealTypeLabel,
  canReviewAppeal,
  canWithdrawAppeal,
} from '@/types/appeal'
import { getAppeal, getAppeals, withdrawAppeal } from '@/api/appeal'
import AppealReviewModal from '@/components/qc/AppealReviewModal.vue'

const authStore = useAuthStore()
const route = useRoute()
const hasReviewPermission = computed(() => authStore.userRoles.some((role) => role === 'admin' || role === 'qc_manager'))
const currentUserId = computed(() => authStore.user?.id)
const statusOptions = computed(() => hasReviewPermission.value ? APPEAL_STATUS_OPTIONS : APPEAL_STATUS_OPTIONS.filter((option) => option.value !== 'reviewable'))

const loading = ref(false)
const appeals = ref<Appeal[]>([])
const showReviewModal = ref(false)
const currentAppeal = ref<Appeal>()
const detailAppeal = ref<Appeal | null>(null)
const detailLoading = ref(false)
let detailRequestId = 0
const detailError = ref('')
const listError = ref('')
let listRequestId = 0
const showDetailModal = ref(false)

const asAppeal = (record: Record<string, unknown>) => record as unknown as Appeal

const filters = reactive({
  status: route.query.todo === 'review' && hasReviewPermission.value ? 'reviewable' as AppealStatusFilter : undefined as AppealStatusFilter | undefined,
  appealType: undefined as AppealType | undefined,
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total: number) => `共 ${total} 条`,
})

const columns: TableColumnsType<Appeal> = [
  { title: '申诉理由', dataIndex: 'appealReason', key: 'reason', ellipsis: true },
  { title: '类型', key: 'appealType', width: 120 },
  { title: '状态', key: 'status', width: 100 },
  { title: '申诉人', dataIndex: 'appellantName', key: 'appellant', width: 120 },
  { title: '提交时间', key: 'createdAt', width: 180 },
  { title: '审核信息', key: 'reviewer', width: 180 },
  { title: '操作', key: 'action', fixed: 'right' as const, width: 180 },
]

onMounted(() => {
  fetchAppeals()
})

watch([() => route.query.todo, hasReviewPermission], ([todo, mayReview]) => {
  filters.status = todo === 'review' && mayReview ? 'reviewable' : undefined
  handleSearch()
})

const handleSearch = () => {
  pagination.current = 1
  fetchAppeals()
}

const resetFilters = () => {
  filters.status = undefined
  filters.appealType = undefined
  handleSearch()
}

const handleTableChange = (pag: { current?: number; pageSize?: number }) => {
  pagination.current = pag.current ?? 1
  pagination.pageSize = pag.pageSize ?? 20
  fetchAppeals()
}

const fetchAppeals = async () => {
  const requestId = ++listRequestId
  loading.value = true
  listError.value = ''
  try {
    const res = await getAppeals({
      status: filters.status,
      appealType: filters.appealType,
      page: pagination.current,
      pageSize: pagination.pageSize,
    })

    if (requestId !== listRequestId) return
    appeals.value = res.items
    pagination.total = res.total
  } catch (error) {
    if (requestId !== listRequestId) return
    appeals.value = []
    listError.value = '加载失败，请重试'
    message.error('加载申诉列表失败')
  } finally {
    if (requestId === listRequestId) loading.value = false
  }
}

const formatDate = (date: string | null) => {
  return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

const canReview = (item: Appeal) => {
  return canReviewAppeal(item, authStore.userRoles)
}

const canWithdraw = (item: Appeal) => {
  return canWithdrawAppeal(item, currentUserId.value)
}

const openReviewModal = (item: Appeal) => {
  currentAppeal.value = item
  showReviewModal.value = true
}

const viewDetail = async (item: Appeal) => {
  const requestId = ++detailRequestId
  showDetailModal.value = true
  detailAppeal.value = null
  detailError.value = ''
  detailLoading.value = true
  try {
    const result = await getAppeal(item.id)
    if (requestId === detailRequestId) detailAppeal.value = result
  } catch (error) {
    if (requestId === detailRequestId) detailError.value = error instanceof Error ? error.message : '加载申诉详情失败'
  } finally {
    if (requestId === detailRequestId) detailLoading.value = false
  }
}

const reviewActionLabel = (action: AppealReviewAction) => ({
  approve: '通过', reject: '驳回', request_info: '要求补充信息', forward: '转交',
})[action]

const handleWithdraw = async (item: Appeal) => {
  try {
    await withdrawAppeal(item.id)
    message.success('已撤销')
    refresh()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '撤回失败')
  }
}

const refresh = () => {
  fetchAppeals()
}
</script>

<style scoped>
.bg-white {
  background-color: #fff;
}
.shadow-sm {
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}
.ml-2 {
  margin-left: 8px;
}
.detail-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.review-entry + .review-entry { border-top: 1px solid rgba(0, 0, 0, 0.08); margin-top: 8px; padding-top: 8px; }
</style>
