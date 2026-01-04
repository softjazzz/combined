<template>
  <div class="appeal-list">
    <a-page-header title="质控申诉" sub-title="申诉记录管理" class="bg-white mb-4 shadow-sm" />

    <div class="px-6 pb-6">
      <a-card :bordered="false" class="shadow-sm">
        <!-- 筛选区域 -->
        <a-form layout="inline" class="mb-4">
           <a-form-item label="状态">
             <a-select v-model:value="filters.status" placeholder="全部状态" allowClear style="width: 120px" @change="handleSearch">
                <a-select-option v-for="opt in APPEAL_STATUS_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-select-option>
              </a-select>
           </a-form-item>
            <a-form-item label="申诉类型">
             <a-select v-model:value="filters.appealType" placeholder="全部类型" allowClear style="width: 140px" @change="handleSearch">
                <a-select-option v-for="opt in APPEAL_TYPE_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-select-option>
              </a-select>
           </a-form-item>
           <a-form-item>
             <a-button type="primary" @click="handleSearch">查询</a-button>
             <a-button class="ml-2" @click="resetFilters">重置</a-button>
           </a-form-item>
        </a-form>

        <!-- 列表 -->
        <a-table
          :columns="columns"
          :data-source="appeals"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getAppealStatusInfo(record.status).color">
                {{ getAppealStatusInfo(record.status).label }}
              </a-tag>
            </template>
            <template v-if="column.key === 'appealType'">
               {{ getAppealTypeLabel(record.appealType) }}
            </template>
            <template v-if="column.key === 'createdAt'">
                {{ formatDate(record.createdAt) }}
            </template>
             <template v-if="column.key === 'reviewer'">
                <div v-if="record.reviewerName" class="text-xs">
                    <div>{{ record.reviewerName }}</div>
                    <div>{{ formatDate(record.reviewedAt) }}</div>
                </div>
                <span v-else>-</span>
            </template>
            <template v-if="column.key === 'action'">
              <a-space>
                 <a-button size="small" @click="viewDetail(record)">详情</a-button>
                 <a-button 
                    v-if="canReview(record)" 
                    type="primary" 
                    ghost 
                    size="small" 
                    @click="openReviewModal(record)"
                >
                  审核
                </a-button>
                 <a-popconfirm
                    v-if="canWithdraw(record)"
                    title="确定撤销此申诉吗？"
                    @confirm="handleWithdraw(record)"
                  >
                    <a-button size="small" danger>撤销</a-button>
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
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { 
    Appeal, AppealStatus,
    APPEAL_STATUS_OPTIONS, APPEAL_TYPE_OPTIONS,
    getAppealStatusInfo, getAppealTypeLabel
} from '@/types/appeal'
import { getAppeals, withdrawAppeal } from '@/api/appeal'
import AppealReviewModal from '@/components/qc/AppealReviewModal.vue'

const hasAdminPermission = ref(true) 
const currentUserId = ref('doctor_001') // 模拟当前用户ID

const loading = ref(false)
const appeals = ref<Appeal[]>([])
const showReviewModal = ref(false)
const currentAppeal = ref<Appeal>()

const filters = reactive({
    status: undefined as AppealStatus | undefined,
    appealType: undefined,
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total: number) => `共 ${total} 条`
})

const columns = [
  { title: '申诉理由', dataIndex: 'appealReason', key: 'reason', ellipsis: true },
  { title: '类型', key: 'appealType', width: 120 },
  { title: '状态', key: 'status', width: 100 },
  { title: '申诉人', dataIndex: 'appellantName', key: 'appellant', width: 120 },
  { title: '提交时间', key: 'createdAt', width: 180 },
  { title: '审核信息', key: 'reviewer', width: 180 },
  { title: '操作', key: 'action', fixed: 'right', width: 180 }
]

onMounted(() => {
    fetchAppeals()
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

const handleTableChange = (pag: any) => {
    pagination.current = pag.current
    pagination.pageSize = pag.pageSize
    fetchAppeals()
}

const fetchAppeals = async () => {
    loading.value = true
    try {
        const res = await getAppeals({
             status: filters.status,
             appealType: filters.appealType,
             page: pagination.current,
             pageSize: pagination.pageSize
        })
        
        appeals.value = res.items
        pagination.total = res.total
    } catch (error) {
        message.error('加载申诉列表失败')
    } finally {
        loading.value = false
    }
}

const formatDate = (date: string | null) => {
    return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

const canReview = (item: Appeal) => {
    return item.status === AppealStatus.PENDING && hasAdminPermission.value
}

const canWithdraw = (item: Appeal) => {
    return item.status === AppealStatus.PENDING && item.appellantId === currentUserId.value
}

const openReviewModal = (item: Appeal) => {
    currentAppeal.value = item
    showReviewModal.value = true
}

const viewDetail = (item: Appeal) => {
    message.info('查看详情: ' + item.id)
}

const handleWithdraw = async (item: Appeal) => {
    try {
        await withdrawAppeal(item.id)
        message.success('已撤销')
        refresh()
    } catch (e: any) {
        message.error(e.message || '撤销失败')
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
</style>
