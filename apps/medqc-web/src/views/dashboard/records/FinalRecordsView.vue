<template>
  <div class="final-records-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">终末病历</h1>
      <p class="text-gray-600">管理和查看已完成的终末病历记录</p>
    </div>

    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">总病历数</p>
            <p class="text-3xl font-bold text-gray-800">1,247</p>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <FileTextOutlined class="text-blue-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">已归档</p>
            <p class="text-3xl font-bold text-gray-800">1,156</p>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <CheckCircleOutlined class="text-green-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">待归档</p>
            <p class="text-3xl font-bold text-gray-800">91</p>
          </div>
          <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
            <ClockCircleOutlined class="text-orange-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">质控通过率</p>
            <p class="text-3xl font-bold text-gray-800">94.2%</p>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
            <TrophyOutlined class="text-purple-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 搜索和筛选区域 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8">
      <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
        <a-input
          v-model:value="searchKeyword"
          placeholder="搜索病历号、患者姓名"
          class="rounded-lg"
        >
          <template #prefix>
            <SearchOutlined class="text-gray-400" />
          </template>
        </a-input>
        
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
        
        <a-select
          v-model:value="selectedQCStatus"
          placeholder="质控状态"
          class="rounded-lg"
          :options="qcStatusOptions"
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

    <!-- 数据表格 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold text-gray-800">终末病历列表</h2>
        <div class="flex space-x-2">
          <a-button type="primary" @click="handleRefresh" :loading="loading" class="rounded-lg">
            <ReloadOutlined />
            刷新
          </a-button>
          <a-button @click="handleBatchArchive" class="rounded-lg">
            <FolderOutlined />
            批量归档
          </a-button>
          <a-button @click="handleExport" class="rounded-lg">
            <DownloadOutlined />
            导出
          </a-button>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        @change="handleTableChange"
        row-key="id"
        class="rounded-lg"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'qcStatus'">
            <a-tag :color="getQCStatusColor(record.qcStatus)">
              {{ getQCStatusText(record.qcStatus) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'archiveStatus'">
            <a-tag :color="getArchiveStatusColor(record.archiveStatus)">
              {{ getArchiveStatusText(record.archiveStatus) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'action'">
            <div class="flex space-x-2">
              <a-button type="link" size="small" @click="handleView(record)">
                <EyeOutlined />
                查看
              </a-button>
              <a-button type="link" size="small" @click="handleQCReport(record)">
                <FileSearchOutlined />
                质控报告
              </a-button>
              <a-button 
                type="link" 
                size="small" 
                @click="handleArchive(record)"
                v-if="record.archiveStatus === 'pending'"
              >
                <FolderOutlined />
                归档
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
  SearchOutlined,
  ReloadOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileSearchOutlined,
  FolderOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  TrophyOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const selectedDepartment = ref(undefined)
const selectedQCStatus = ref(undefined)
const dateRange = ref([])
const records = ref([])
const selectedRowKeys = ref([])

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`
})

// 行选择配置
const rowSelection = {
  selectedRowKeys: selectedRowKeys,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}

// 科室选项
const departmentOptions = [
  { value: 'internal', label: '内科' },
  { value: 'surgery', label: '外科' },
  { value: 'pediatrics', label: '儿科' },
  { value: 'obstetrics', label: '妇产科' },
  { value: 'emergency', label: '急诊科' }
]

// 质控状态选项
const qcStatusOptions = [
  { value: 'passed', label: '通过' },
  { value: 'failed', label: '未通过' },
  { value: 'pending', label: '待质控' }
]

// 表格列配置
const columns = [
  {
    title: '病历号',
    dataIndex: 'recordNumber',
    key: 'recordNumber',
    width: 120
  },
  {
    title: '患者姓名',
    dataIndex: 'patientName',
    key: 'patientName',
    width: 100
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 100
  },
  {
    title: '出院日期',
    dataIndex: 'dischargeDate',
    key: 'dischargeDate',
    width: 120
  },
  {
    title: '质控状态',
    dataIndex: 'qcStatus',
    key: 'qcStatus',
    width: 100
  },
  {
    title: '归档状态',
    dataIndex: 'archiveStatus',
    key: 'archiveStatus',
    width: 100
  },
  {
    title: '质控得分',
    dataIndex: 'qcScore',
    key: 'qcScore',
    width: 100
  },
  {
    title: '操作',
    key: 'action',
    width: 200,
    fixed: 'right'
  }
]

// 获取质控状态颜色和文本
const getQCStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    passed: 'green',
    failed: 'red',
    pending: 'orange'
  }
  return colorMap[status] || 'default'
}

const getQCStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    passed: '通过',
    failed: '未通过',
    pending: '待质控'
  }
  return textMap[status] || status
}

// 获取归档状态颜色和文本
const getArchiveStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    archived: 'green',
    pending: 'orange'
  }
  return colorMap[status] || 'default'
}

const getArchiveStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    archived: '已归档',
    pending: '待归档'
  }
  return textMap[status] || status
}

// 事件处理函数
const handleSearch = () => {
  pagination.value.current = 1
  fetchRecords()
}

const handleReset = () => {
  searchKeyword.value = ''
  selectedDepartment.value = undefined
  selectedQCStatus.value = undefined
  dateRange.value = []
  pagination.value.current = 1
  fetchRecords()
}

const handleRefresh = () => {
  fetchRecords()
}

const handleBatchArchive = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要归档的病历')
    return
  }
  message.info(`批量归档 ${selectedRowKeys.value.length} 条病历`)
}

const handleExport = () => {
  message.info('导出功能开发中...')
}

const handleView = (record) => {
  message.info(`查看病历: ${record.recordNumber}`)
}

const handleQCReport = (record) => {
  message.info(`查看质控报告: ${record.recordNumber}`)
}

const handleArchive = (record) => {
  message.info(`归档病历: ${record.recordNumber}`)
}

const handleTableChange = (pag) => {
  pagination.value = { ...pagination.value, ...pag }
  fetchRecords()
}

// 获取数据
const fetchRecords = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 模拟数据
    records.value = [
      {
        id: 1,
        recordNumber: 'F2024001',
        patientName: '王五',
        department: '内科',
        dischargeDate: '2024-01-10',
        qcStatus: 'passed',
        archiveStatus: 'archived',
        qcScore: 95
      },
      {
        id: 2,
        recordNumber: 'F2024002',
        patientName: '赵六',
        department: '外科',
        dischargeDate: '2024-01-12',
        qcStatus: 'failed',
        archiveStatus: 'pending',
        qcScore: 72
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
  fetchRecords()
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
