<template>
  <div class="remediation-panel">
    <!-- KPI 卡片 -->
    <div class="grid grid-cols-5 gap-3 mb-4">
      <div class="bg-white rounded-xl p-3 border border-slate-100 text-center">
        <div class="text-xs text-slate-400 mb-1">
          总整改
        </div>
        <div class="text-lg font-bold text-slate-800 font-mono">
          {{ stats.total || 0 }}
        </div>
      </div>
      <div class="bg-white rounded-xl p-3 border border-amber-100 text-center">
        <div class="text-xs text-amber-500 mb-1">
          待整改
        </div>
        <div class="text-lg font-bold text-amber-600 font-mono">
          {{ stats.pending || 0 }}
        </div>
      </div>
      <div class="bg-white rounded-xl p-3 border border-blue-100 text-center">
        <div class="text-xs text-blue-500 mb-1">
          已提交
        </div>
        <div class="text-lg font-bold text-blue-600 font-mono">
          {{ stats.submitted || 0 }}
        </div>
      </div>
      <div class="bg-white rounded-xl p-3 border border-emerald-100 text-center">
        <div class="text-xs text-emerald-500 mb-1">
          已通过
        </div>
        <div class="text-lg font-bold text-emerald-600 font-mono">
          {{ stats.approved || 0 }}
        </div>
      </div>
      <div class="bg-white rounded-xl p-3 border border-rose-100 text-center">
        <div class="text-xs text-rose-500 mb-1">
          逾期
        </div>
        <div class="text-lg font-bold text-rose-600 font-mono">
          {{ stats.overdue || 0 }}
        </div>
      </div>
    </div>

    <!-- 筛选 + 操作区 -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <a-segmented
          v-model:value="statusFilter"
          :options="statusOptions"
          size="small"
          @change="fetchList"
        />
      </div>
      <a-button
        size="small"
        type="text"
        @click="fetchList"
      >
        <ReloadOutlined :spin="loading" /> 刷新
      </a-button>
    </div>

    <!-- 表格 -->
    <a-spin :spinning="loading">
      <div
        v-if="list.length === 0"
        class="text-center py-12 text-slate-400"
      >
        <InboxOutlined
          style="font-size: 40px"
          class="mb-2 block"
        />
        <p class="text-sm">
          暂无整改任务
        </p>
      </div>
      <div
        v-else
        class="space-y-3"
      >
        <div
          v-for="item in list"
          :key="item.id"
          class="bg-white rounded-xl border border-slate-100 p-4 hover:shadow-md transition-all"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-3">
              <span
                class="w-2 h-2 rounded-full"
                :class="getSeverityDot(item.severity)"
              />
              <span class="text-sm font-medium text-slate-800">{{ item.defect_type }}</span>
              <span class="text-xs text-slate-400">· {{ item.record_id }}</span>
            </div>
            <span
              class="text-xs px-2 py-0.5 rounded-md font-medium"
              :class="getStatusBadge(item.status)"
            >
              {{ getStatusText(item.status) }}
            </span>
          </div>
          <p class="text-xs text-slate-500 mb-2 line-clamp-1">
            {{ item.defect_description }}
          </p>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-4 text-xs text-slate-400">
              <span v-if="item.assignee_name">
                <UserOutlined class="mr-1" />{{ item.assignee_name }}
              </span>
              <span v-if="item.deadline">
                <ClockCircleOutlined class="mr-1" />截止: {{ item.deadline?.slice(0, 10) }}
              </span>
            </div>
            <div class="flex items-center gap-1">
              <a-button
                v-if="item.status === 'submitted'"
                size="small"
                type="primary"
                class="!text-xs !h-7"
                @click="handleReview(item, 'approve')"
              >
                通过
              </a-button>
              <a-button
                v-if="item.status === 'submitted'"
                size="small"
                danger
                class="!text-xs !h-7"
                @click="handleReview(item, 'reject')"
              >
                驳回
              </a-button>
              <a-button
                v-if="['approved', 'rejected'].includes(item.status)"
                size="small"
                class="!text-xs !h-7"
                @click="handleClose(item)"
              >
                关闭
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-spin>

    <!-- 分页 -->
    <div
      v-if="total > pageSize"
      class="flex justify-end mt-4"
    >
      <a-pagination
        v-model:current="currentPage"
        :total="total"
        :page-size="pageSize"
        size="small"
        show-quick-jumper
        @change="fetchList"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, InboxOutlined, UserOutlined, ClockCircleOutlined } from '@ant-design/icons-vue'
import {
  getRemediationList,
  getRemediationStats,
  reviewRemediation,
  closeRemediation,
  type RemediationItem,
} from '@/api/qcAdmin'

const loading = ref(false)
const list = ref<RemediationItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const statusFilter = ref('all')

const stats = ref<Record<string, number>>({})

const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '待整改', value: 'pending' },
  { label: '已提交', value: 'submitted' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' },
  { label: '逾期', value: 'overdue' },
]

const fetchList = async () => {
  loading.value = true
  try {
    const params: any = { page: currentPage.value, page_size: pageSize }
    if (statusFilter.value !== 'all') {
      params.status = statusFilter.value
    }
    const res = await getRemediationList(params)
    if (res.success && res.data) {
      list.value = (res.data as any).items || []
      total.value = (res.data as any).total || 0
    }
  } catch {
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  const res = await getRemediationStats()
  if (res.success && res.data) {
    stats.value = res.data
  }
}

const handleReview = async (item: RemediationItem, action: 'approve' | 'reject') => {
  const res = await reviewRemediation(item.id, { action })
  if (res.success) {
    message.success(action === 'approve' ? '验收通过' : '已驳回')
    fetchList()
    fetchStats()
  } else {
    message.error(res.message || '操作失败')
  }
}

const handleClose = async (item: RemediationItem) => {
  const res = await closeRemediation(item.id, '管理员关闭')
  if (res.success) {
    message.success('已关闭')
    fetchList()
    fetchStats()
  } else {
    message.error(res.message || '关闭失败')
  }
}

const getSeverityDot = (s: string) => ({
  'bg-rose-500': s === 'critical' || s === 'error',
  'bg-amber-500': s === 'warning',
  'bg-blue-500': s === 'info',
  'bg-slate-400': !s,
})

const getStatusBadge = (s: string) => ({
  'bg-amber-50 text-amber-600': s === 'pending' || s === 'in_progress',
  'bg-blue-50 text-blue-600': s === 'submitted',
  'bg-emerald-50 text-emerald-600': s === 'approved',
  'bg-rose-50 text-rose-600': s === 'rejected' || s === 'overdue',
  'bg-slate-100 text-slate-500': s === 'closed',
})

const getStatusText = (s: string) => {
  const map: Record<string, string> = {
    pending: '待整改', in_progress: '整改中', submitted: '待验收',
    approved: '已通过', rejected: '已驳回', overdue: '逾期', closed: '已关闭',
  }
  return map[s] || s
}

onMounted(() => {
  fetchList()
  fetchStats()
})
</script>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
