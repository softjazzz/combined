<template>
  <div class="rectification-list">
    <a-page-header title="整改任务" sub-title="我的整改任务管理" class="bg-white mb-4 shadow-sm" />

    <div class="px-6 pb-6">
      <a-card :bordered="false" class="shadow-sm">
        <a-tabs v-model:activeKey="activeTab" @change="handleTabChange">
          <a-tab-pane key="my-tasks" tab="我的任务" />
          <a-tab-pane key="all" tab="所有任务" v-if="hasAdminPermission" />
        </a-tabs>
        
        <!-- 筛选区域 -->
        <a-form layout="inline" class="mb-4">
           <a-form-item label="状态">
             <a-select v-model:value="filters.status" placeholder="全部状态" allowClear style="width: 120px" @change="handleSearch">
                <a-select-option v-for="opt in TASK_STATUS_OPTIONS" :key="opt.value" :value="opt.value">
                  {{ opt.label }}
                </a-select-option>
              </a-select>
           </a-form-item>
           <a-form-item label="严重程度">
             <a-select v-model:value="filters.severity" placeholder="全部" allowClear style="width: 120px" @change="handleSearch">
               <a-select-option v-for="opt in TASK_SEVERITY_OPTIONS" :key="opt.value" :value="opt.value">
                 {{ opt.label }}
               </a-select-option>
             </a-select>
           </a-form-item>
           <a-form-item v-if="activeTab === 'all'" label="指派人">
               <a-input v-model:value="filters.assigneeId" placeholder="指派人ID/姓名" />
           </a-form-item>
           <a-form-item>
               <a-checkbox v-model:checked="filters.overdueOnly" @change="handleSearch">仅显示逾期</a-checkbox>
           </a-form-item>
           <a-form-item>
             <a-button type="primary" @click="handleSearch">查询</a-button>
             <a-button class="ml-2" @click="resetFilters">重置</a-button>
           </a-form-item>
        </a-form>

        <!-- 任务列表 -->
        <a-table
          :columns="columns"
          :data-source="tasks"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="getTaskStatusInfo(record.status).color">
                {{ getTaskStatusInfo(record.status).label }}
              </a-tag>
            </template>
            <template v-if="column.key === 'severity'">
                <a-tag :color="getTaskSeverityInfo(record.severity).color">
                    {{ getTaskSeverityInfo(record.severity).label }}
                </a-tag>
            </template>
            <template v-if="column.key === 'dueDate'">
                <span :class="{'text-red-500 font-bold': isTaskOverdue(record), 'text-gray-500': !isTaskOverdue(record)}">
                    {{ formatDate(record.dueDate) }}
                </span>
                 <a-tag v-if="isTaskOverdue(record)" color="red" class="ml-1">逾期</a-tag>
            </template>
             <template v-if="column.key === 'timeInfo'">
                <div class="text-xs text-gray-500">
                    <div>创建: {{ formatDate(record.createdAt) }}</div>
                    <div v-if="record.completedAt">完成: {{ formatDate(record.completedAt) }}</div>
                 </div>
            </template>
            <template v-if="column.key === 'action'">
              <a-space>
                <a-button 
                    v-if="canSubmit(record)" 
                    type="primary" 
                    size="small" 
                    @click="openSubmitModal(record)"
                >
                  整改
                </a-button>
                <a-button 
                    v-if="canReview(record)" 
                    type="primary" 
                    ghost 
                    size="small" 
                    @click="openReviewModal(record)"
                >
                  验收
                </a-button>
                 <a-button size="small" @click="viewDetail(record)">详情</a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- Modals -->
    <RectificationForm
        v-model:visible="showSubmitModal"
        :task="currentTask"
        @success="refresh"
    />

    <RectificationReviewModal
        v-model:visible="showReviewModal"
        :task="currentTask"
        @success="refresh"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import { 
    RectificationTask, TaskStatus, TaskSeverity,
    TASK_STATUS_OPTIONS, TASK_SEVERITY_OPTIONS,
    getTaskStatusInfo, getTaskSeverityInfo, isTaskOverdue
} from '@/types/rectification'
import { getRectificationTasks, getMyTasks } from '@/api/rectification'
import RectificationForm from '@/components/qc/RectificationForm.vue'
import RectificationReviewModal from '@/components/qc/RectificationReviewModal.vue'

// 模拟权限，实际应从store获取
const hasAdminPermission = ref(true) 
const currentUserId = ref('doctor_001') // 模拟当前用户ID

const activeTab = ref('my-tasks')
const loading = ref(false)
const tasks = ref<RectificationTask[]>([])
const showSubmitModal = ref(false)
const showReviewModal = ref(false)
const currentTask = ref<RectificationTask>()

const filters = reactive({
    status: undefined as TaskStatus | undefined,
    severity: undefined as TaskSeverity | undefined,
    assigneeId: '',
    overdueOnly: false
})

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showTotal: (total: number) => `共 ${total} 条`
})

const columns = [
  { title: '任务标题', dataIndex: 'taskTitle', key: 'title', width: 250 },
  { title: '状态', key: 'status', width: 100 },
  { title: '严重程度', key: 'severity', width: 100 },
  { title: '指派人', dataIndex: 'assigneeName', key: 'assignee', width: 120 },
  { title: '截止时间', key: 'dueDate', width: 150 },
  { title: '时间信息', key: 'timeInfo', width: 180 },
  { title: '操作', key: 'action', fixed: 'right', width: 180 }
]

onMounted(() => {
    fetchTasks()
})

const handleTabChange = () => {
    pagination.current = 1
    fetchTasks()
}

const handleSearch = () => {
    pagination.current = 1
    fetchTasks()
}

const resetFilters = () => {
    filters.status = undefined
    filters.severity = undefined
    filters.assigneeId = ''
    filters.overdueOnly = false
    handleSearch()
}

const handleTableChange = (pag: any) => {
    pagination.current = pag.current
    pagination.pageSize = pag.pageSize
    fetchTasks()
}

const fetchTasks = async () => {
    loading.value = true
    try {
        let res;
        if (activeTab.value === 'my-tasks') {
             // My Tasks API通常不带所有筛选，这里简单处理，实际可复用list API带 assigneeId
             // 为了演示完整筛选功能，我们在'my-tasks' tab下也调用通用查询，强制 assigneeId
             res = await getRectificationTasks({
                 ...filters,
                 assigneeId: currentUserId.value, // 强制限定自己
                 page: pagination.current,
                 pageSize: pagination.pageSize
             })
        } else {
             res = await getRectificationTasks({
                 ...filters,
                 page: pagination.current,
                 pageSize: pagination.pageSize
             })
        }
        
        tasks.value = res.items
        pagination.total = res.total
    } catch (error) {
        message.error('加载任务失败')
    } finally {
        loading.value = false
    }
}

const formatDate = (date: string | null) => {
    return date ? dayjs(date).format('YYYY-MM-DD HH:mm') : '-'
}

// 权限控制逻辑
const canSubmit = (task: RectificationTask) => {
    return (task.status === TaskStatus.PENDING || task.status === TaskStatus.IN_PROGRESS || task.status === TaskStatus.REJECTED) 
        // && task.assigneeId === currentUserId.value // 实际需要校验ID
}

const canReview = (task: RectificationTask) => {
    return task.status === TaskStatus.SUBMITTED && hasAdminPermission.value
}

const openSubmitModal = (task: RectificationTask) => {
    currentTask.value = task
    showSubmitModal.value = true
}

const openReviewModal = (task: RectificationTask) => {
    currentTask.value = task
    showReviewModal.value = true
}

const viewDetail = (task: RectificationTask) => {
    // 简单实现查看详情，可以用Modal或drawer
    message.info('查看详情: ' + task.taskTitle)
}

const refresh = () => {
    fetchTasks()
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
.ml-1 {
    margin-left: 4px;
}
</style>
