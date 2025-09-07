<template>
  <div class="my-tasks-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">我的任务</h1>
      <p class="text-gray-600">管理和处理分配给我的质控任务</p>
    </div>

    <!-- 任务统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">待处理</p>
            <p class="text-3xl font-bold text-orange-600">12</p>
          </div>
          <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
            <ClockCircleOutlined class="text-orange-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">进行中</p>
            <p class="text-3xl font-bold text-blue-600">8</p>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <SyncOutlined class="text-blue-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">已完成</p>
            <p class="text-3xl font-bold text-green-600">156</p>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <CheckCircleOutlined class="text-green-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">完成率</p>
            <p class="text-3xl font-bold text-purple-600">88.6%</p>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
            <TrophyOutlined class="text-purple-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">快捷操作</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <a-button type="primary" size="large" @click="handleStartTask" class="rounded-lg h-16">
          <PlayCircleOutlined class="text-lg" />
          <span class="ml-2">开始任务</span>
        </a-button>
        <a-button size="large" @click="handleViewPending" class="rounded-lg h-16">
          <ClockCircleOutlined class="text-lg" />
          <span class="ml-2">待处理任务</span>
        </a-button>
        <a-button size="large" @click="handleViewCompleted" class="rounded-lg h-16">
          <CheckCircleOutlined class="text-lg" />
          <span class="ml-2">已完成任务</span>
        </a-button>
        <a-button size="large" @click="handleTaskReport" class="rounded-lg h-16">
          <BarChartOutlined class="text-lg" />
          <span class="ml-2">任务报告</span>
        </a-button>
      </div>
    </div>

    <!-- 筛选区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <a-select
          v-model:value="selectedStatus"
          placeholder="选择状态"
          class="rounded-lg"
          :options="statusOptions"
        />
        
        <a-select
          v-model:value="selectedPriority"
          placeholder="选择优先级"
          class="rounded-lg"
          :options="priorityOptions"
        />
        
        <a-range-picker
          v-model:value="dateRange"
          placeholder="选择日期范围"
          class="rounded-lg"
        />
        
        <div class="flex space-x-2">
          <a-button type="primary" @click="handleFilter" class="rounded-lg">
            <FilterOutlined />
            筛选
          </a-button>
          <a-button @click="handleResetFilter" class="rounded-lg">
            <ReloadOutlined />
            重置
          </a-button>
        </div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold text-gray-800">任务列表</h2>
        <a-button type="primary" @click="handleRefresh" :loading="loading" class="rounded-lg">
          <ReloadOutlined />
          刷新
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
        class="rounded-lg"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'priority'">
            <a-tag :color="getPriorityColor(record.priority)">
              {{ getPriorityText(record.priority) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'progress'">
            <a-progress :percent="record.progress" size="small" />
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button 
                type="link" 
                size="small" 
                @click="handleStartWork(record)"
                v-if="record.status === 'pending'"
              >
                <PlayCircleOutlined />
                开始
              </a-button>
              <a-button 
                type="link" 
                size="small" 
                @click="handleContinueWork(record)"
                v-if="record.status === 'in_progress'"
              >
                <EditOutlined />
                继续
              </a-button>
              <a-button type="link" size="small" @click="handleViewDetail(record)">
                <EyeOutlined />
                详情
              </a-button>
              <a-button 
                type="link" 
                size="small" 
                @click="handleSubmit(record)"
                v-if="record.status === 'in_progress'"
              >
                <CheckOutlined />
                提交
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  TrophyOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  FilterOutlined,
  ReloadOutlined,
  EditOutlined,
  EyeOutlined,
  CheckOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const selectedStatus = ref(undefined)
const selectedPriority = ref(undefined)
const dateRange = ref([])
const tasks = ref([])

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条任务`
})

// 状态选项
const statusOptions = [
  { value: 'pending', label: '待处理' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'overdue', label: '已逾期' }
]

// 优先级选项
const priorityOptions = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' }
]

// 表格列配置
const columns = [
  {
    title: '任务编号',
    dataIndex: 'taskNumber',
    key: 'taskNumber',
    width: 120
  },
  {
    title: '任务名称',
    dataIndex: 'taskName',
    key: 'taskName',
    width: 200
  },
  {
    title: '病历号',
    dataIndex: 'recordNumber',
    key: 'recordNumber',
    width: 120
  },
  {
    title: '优先级',
    dataIndex: 'priority',
    key: 'priority',
    width: 80
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100
  },
  {
    title: '进度',
    dataIndex: 'progress',
    key: 'progress',
    width: 120
  },
  {
    title: '截止时间',
    dataIndex: 'deadline',
    key: 'deadline',
    width: 150
  },
  {
    title: '操作',
    key: 'action',
    width: 200,
    fixed: 'right'
  }
]

// 获取优先级颜色和文本
const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    high: 'red',
    medium: 'orange',
    low: 'green'
  }
  return colorMap[priority] || 'default'
}

const getPriorityText = (priority: string) => {
  const textMap: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return textMap[priority] || priority
}

// 获取状态颜色和文本
const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    in_progress: 'blue',
    completed: 'green',
    overdue: 'red'
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    overdue: '已逾期'
  }
  return textMap[status] || status
}

// 事件处理函数
const handleStartTask = () => {
  message.info('开始新任务')
}

const handleViewPending = () => {
  selectedStatus.value = 'pending'
  handleFilter()
}

const handleViewCompleted = () => {
  selectedStatus.value = 'completed'
  handleFilter()
}

const handleTaskReport = () => {
  message.info('查看任务报告')
}

const handleFilter = () => {
  pagination.value.current = 1
  fetchTasks()
}

const handleResetFilter = () => {
  selectedStatus.value = undefined
  selectedPriority.value = undefined
  dateRange.value = []
  pagination.value.current = 1
  fetchTasks()
}

const handleRefresh = () => {
  fetchTasks()
}

const handleStartWork = (record) => {
  message.info(`开始任务: ${record.taskName}`)
}

const handleContinueWork = (record) => {
  message.info(`继续任务: ${record.taskName}`)
}

const handleViewDetail = (record) => {
  message.info(`查看任务详情: ${record.taskName}`)
}

const handleSubmit = (record) => {
  message.info(`提交任务: ${record.taskName}`)
}

const handleTableChange = (pag) => {
  pagination.value = { ...pagination.value, ...pag }
  fetchTasks()
}

// 获取数据
const fetchTasks = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 模拟数据
    tasks.value = [
      {
        id: 1,
        taskNumber: 'T2024001',
        taskName: '内科病历质控',
        recordNumber: 'R2024001',
        priority: 'high',
        status: 'pending',
        progress: 0,
        deadline: '2024-01-20 18:00:00'
      },
      {
        id: 2,
        taskNumber: 'T2024002',
        taskName: '外科病历审核',
        recordNumber: 'R2024002',
        priority: 'medium',
        status: 'in_progress',
        progress: 65,
        deadline: '2024-01-22 18:00:00'
      }
    ]
    
    pagination.value.total = 50
  } catch (error) {
    message.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchTasks()
})
</script>

<style scoped>
:deep(.ant-table-thead > tr > th) {
  background-color: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc;
}

:deep(.ant-btn-link) {
  padding: 0 4px;
}
</style>
