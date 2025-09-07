<template>
  <div class="all-tasks-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">全部任务</h1>
      <p class="text-gray-600">管理和监控系统中的所有质控任务</p>
    </div>

    <!-- 任务统计概览 -->
    <div class="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">总任务数</p>
            <p class="text-3xl font-bold text-gray-800">342</p>
          </div>
          <div class="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center">
            <ProjectOutlined class="text-gray-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">待分配</p>
            <p class="text-3xl font-bold text-orange-600">28</p>
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
            <p class="text-3xl font-bold text-blue-600">156</p>
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
            <p class="text-3xl font-bold text-green-600">158</p>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <CheckCircleOutlined class="text-green-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">逾期任务</p>
            <p class="text-3xl font-bold text-red-600">12</p>
          </div>
          <div class="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
            <ExclamationCircleOutlined class="text-red-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 管理操作区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">任务管理</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <a-button type="primary" size="large" @click="handleCreateTask" class="rounded-lg h-16">
          <PlusOutlined class="text-lg" />
          <span class="ml-2">创建任务</span>
        </a-button>
        <a-button size="large" @click="handleBatchAssign" class="rounded-lg h-16">
          <TeamOutlined class="text-lg" />
          <span class="ml-2">批量分配</span>
        </a-button>
        <a-button size="large" @click="handleTaskTemplate" class="rounded-lg h-16">
          <FileOutlined class="text-lg" />
          <span class="ml-2">任务模板</span>
        </a-button>
        <a-button size="large" @click="handleTaskAnalysis" class="rounded-lg h-16">
          <BarChartOutlined class="text-lg" />
          <span class="ml-2">任务分析</span>
        </a-button>
      </div>
    </div>

    <!-- 搜索和筛选区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <div class="grid grid-cols-1 md:grid-cols-6 gap-4">
        <a-input
          v-model:value="searchKeyword"
          placeholder="搜索任务名称、编号"
          class="rounded-lg"
        >
          <template #prefix>
            <SearchOutlined class="text-gray-400" />
          </template>
        </a-input>
        
        <a-select
          v-model:value="selectedStatus"
          placeholder="选择状态"
          class="rounded-lg"
          :options="statusOptions"
        />
        
        <a-select
          v-model:value="selectedAssignee"
          placeholder="选择负责人"
          class="rounded-lg"
          :options="assigneeOptions"
        />
        
        <a-select
          v-model:value="selectedDepartment"
          placeholder="选择科室"
          class="rounded-lg"
          :options="departmentOptions"
        />
        
        <a-range-picker
          v-model:value="dateRange"
          placeholder="选择日期范围"
          class="rounded-lg"
        />
        
        <div class="flex space-x-2">
          <a-button type="primary" @click="handleSearch" class="rounded-lg">
            <SearchOutlined />
            搜索
          </a-button>
          <a-button @click="handleReset" class="rounded-lg">
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
        <div class="flex space-x-2">
          <a-button type="primary" @click="handleRefresh" :loading="loading" class="rounded-lg">
            <ReloadOutlined />
            刷新
          </a-button>
          <a-button @click="handleExport" class="rounded-lg">
            <DownloadOutlined />
            导出
          </a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data-source="tasks"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
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
          <template v-if="column.key === 'assignee'">
            <div class="flex items-center">
              <a-avatar size="small" class="mr-2">
                {{ record.assignee?.charAt(0) }}
              </a-avatar>
              {{ record.assignee || '未分配' }}
            </div>
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button type="link" size="small" @click="handleViewDetail(record)">
                <EyeOutlined />
                详情
              </a-button>
              <a-button 
                type="link" 
                size="small" 
                @click="handleAssign(record)"
                v-if="!record.assignee"
              >
                <UserAddOutlined />
                分配
              </a-button>
              <a-button type="link" size="small" @click="handleEdit(record)">
                <EditOutlined />
                编辑
              </a-button>
              <a-button type="link" size="small" danger @click="handleDelete(record)">
                <DeleteOutlined />
                删除
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
  ProjectOutlined,
  ClockCircleOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  TeamOutlined,
  FileOutlined,
  BarChartOutlined,
  SearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  UserAddOutlined,
  EditOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const selectedStatus = ref(undefined)
const selectedAssignee = ref(undefined)
const selectedDepartment = ref(undefined)
const dateRange = ref([])
const tasks = ref([])
const selectedRowKeys = ref([])

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条任务`
})

// 行选择配置
const rowSelection = {
  selectedRowKeys: selectedRowKeys,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}

// 选项配置
const statusOptions = [
  { value: 'unassigned', label: '待分配' },
  { value: 'pending', label: '待处理' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'overdue', label: '已逾期' }
]

const assigneeOptions = [
  { value: 'zhang_san', label: '张三' },
  { value: 'li_si', label: '李四' },
  { value: 'wang_wu', label: '王五' }
]

const departmentOptions = [
  { value: 'internal', label: '内科' },
  { value: 'surgery', label: '外科' },
  { value: 'pediatrics', label: '儿科' },
  { value: 'obstetrics', label: '妇产科' }
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
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 100
  },
  {
    title: '负责人',
    dataIndex: 'assignee',
    key: 'assignee',
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
    title: '创建时间',
    dataIndex: 'createTime',
    key: 'createTime',
    width: 150
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
    width: 250,
    fixed: 'right'
  }
]

// 工具函数
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

const getStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    unassigned: 'gray',
    pending: 'orange',
    in_progress: 'blue',
    completed: 'green',
    overdue: 'red'
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    unassigned: '待分配',
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    overdue: '已逾期'
  }
  return textMap[status] || status
}

// 事件处理函数
const handleCreateTask = () => {
  message.info('创建新任务')
}

const handleBatchAssign = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要分配的任务')
    return
  }
  message.info(`批量分配 ${selectedRowKeys.value.length} 个任务`)
}

const handleTaskTemplate = () => {
  message.info('管理任务模板')
}

const handleTaskAnalysis = () => {
  message.info('查看任务分析')
}

const handleSearch = () => {
  pagination.value.current = 1
  fetchTasks()
}

const handleReset = () => {
  searchKeyword.value = ''
  selectedStatus.value = undefined
  selectedAssignee.value = undefined
  selectedDepartment.value = undefined
  dateRange.value = []
  pagination.value.current = 1
  fetchTasks()
}

const handleRefresh = () => {
  fetchTasks()
}

const handleExport = () => {
  message.info('导出任务数据')
}

const handleViewDetail = (record) => {
  message.info(`查看任务详情: ${record.taskName}`)
}

const handleAssign = (record) => {
  message.info(`分配任务: ${record.taskName}`)
}

const handleEdit = (record) => {
  message.info(`编辑任务: ${record.taskName}`)
}

const handleDelete = (record) => {
  message.info(`删除任务: ${record.taskName}`)
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
        department: '内科',
        assignee: '张三',
        priority: 'high',
        status: 'in_progress',
        progress: 75,
        createTime: '2024-01-15 09:00:00',
        deadline: '2024-01-20 18:00:00'
      },
      {
        id: 2,
        taskNumber: 'T2024002',
        taskName: '外科病历审核',
        recordNumber: 'R2024002',
        department: '外科',
        assignee: null,
        priority: 'medium',
        status: 'unassigned',
        progress: 0,
        createTime: '2024-01-16 10:00:00',
        deadline: '2024-01-22 18:00:00'
      }
    ]
    
    pagination.value.total = 100
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
