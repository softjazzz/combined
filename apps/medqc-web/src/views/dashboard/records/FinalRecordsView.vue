<template>
  <div class="final-records-page min-h-screen bg-slate-50/50 p-6">
    <!-- 1. 顶部 KPI 概览卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">总病历数</div>
          <div class="text-2xl font-bold text-blue-600 font-mono">1,247</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <FileTextOutlined class="text-lg" />
        </div>
      </div>
      
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">已归档</div>
          <div class="text-2xl font-bold text-emerald-600 font-mono">1,156</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <CheckCircleOutlined class="text-lg" />
        </div>
      </div>
      
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">待归档</div>
          <div class="text-2xl font-bold text-amber-600 font-mono">91</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <ClockCircleOutlined class="text-lg" />
        </div>
      </div>
      
      <div class="bg-white rounded-2xl p-4 border border-slate-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
        <div>
          <div class="text-slate-500 text-xs font-medium mb-1">质控通过率</div>
          <div class="text-2xl font-bold text-purple-600 font-mono">94.2%</div>
        </div>
        <div class="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center group-hover:scale-110 transition-transform">
          <TrophyOutlined class="text-lg" />
        </div>
      </div>
    </div>

    <!-- 2. 主内容区：工具栏 + 表格 -->
    <div class="bg-white rounded-2xl border border-slate-100 shadow-sm flex flex-col h-[calc(100vh-180px)]">
      
      <!-- 工具栏 Header -->
      <div class="px-6 py-4 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <!-- 左侧：搜索与筛选 -->
        <div class="flex items-center gap-3 flex-1">
          <div class="relative">
             <a-input
              v-model:value="searchKeyword"
              placeholder="搜索病历号/姓名..."
              class="w-64 !rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400 focus:!border-blue-500 !pl-10"
              @press-enter="handleSearch"
            >
            </a-input>
            <SearchOutlined class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>
          
          <a-select
            v-model:value="selectedDepartment"
            class="w-32 custom-select"
            placeholder="选择科室"
            :bordered="false"
            allowClear
          >
             <a-select-option v-for="dept in departmentOptions" :key="dept.value" :value="dept.value">{{ dept.label }}</a-select-option>
          </a-select>

          <a-select
            v-model:value="selectedQCStatus"
            class="w-32 custom-select"
            placeholder="质控状态"
            :bordered="false"
            allowClear
          >
             <a-select-option v-for="status in qcStatusOptions" :key="status.value" :value="status.value">{{ status.label }}</a-select-option>
          </a-select>
          
          <div class="h-6 w-px bg-slate-200 mx-1"></div>

          <a-range-picker
            v-model:value="dateRange"
            class="!rounded-xl !bg-slate-50 !border-slate-200 hover:!border-blue-400"
            :bordered="false"
          />
        </div>

        <!-- 右侧：操作按钮 -->
        <div class="flex items-center gap-3">
           <a-button type="primary" class="bg-blue-600 hover:bg-blue-500 border-none shadow-md shadow-blue-500/20 !rounded-xl !flex items-center gap-1 !h-9" @click="handleBatchArchive">
             <FolderOutlined /> 批量归档
           </a-button>
           
           <a-button class="!rounded-xl !border-slate-200 text-slate-600 hover:text-blue-600 !h-9 !flex items-center gap-1" @click="handleExport">
             <DownloadOutlined /> 导出
           </a-button>

           <a-tooltip title="刷新数据">
             <a-button class="!rounded-xl !border-slate-200 text-slate-500 hover:text-blue-600 !h-9 !w-9 !p-0 flex items-center justify-center" @click="handleRefresh">
               <ReloadOutlined :spin="loading" />
             </a-button>
           </a-tooltip>
        </div>
      </div>

      <!-- 表格区域 -->
      <div class="flex-1 overflow-hidden px-6 py-2">
        <a-table
          :columns="columns"
          :data-source="records"
          :loading="loading"
          :pagination="pagination"
          :row-selection="rowSelection"
          @change="handleTableChange"
          row-key="id"
          class="modern-table h-full"
          :scroll="{ y: 'calc(100vh - 320px)' }"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'recordNumber'">
              <div class="font-mono font-bold text-slate-700 text-sm group-hover:text-blue-600 transition-colors cursor-pointer" @click="handleView(record)">
                {{ record.recordNumber }}
              </div>
            </template>
            
            <template v-if="column.key === 'patientInfo'">
               <div class="flex items-center gap-2">
                 <div class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600 border border-slate-200">
                   {{ record.patientName.charAt(0) }}
                 </div>
                 <div class="text-sm font-medium text-slate-700">{{ record.patientName }}</div>
               </div>
            </template>

            <template v-if="column.key === 'qcStatus'">
              <span 
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-emerald-50 text-emerald-600 border-emerald-100': record.qcStatus === 'passed',
                  'bg-rose-50 text-rose-600 border-rose-100': record.qcStatus === 'failed',
                  'bg-amber-50 text-amber-600 border-amber-100': record.qcStatus === 'pending'
                }"
              >
                <span class="w-1.5 h-1.5 rounded-full" :class="{
                  'bg-emerald-500': record.qcStatus === 'passed',
                  'bg-rose-500': record.qcStatus === 'failed',
                  'bg-amber-500': record.qcStatus === 'pending'
                }"></span>
                {{ getQCStatusText(record.qcStatus) }}
              </span>
            </template>

            <template v-if="column.key === 'archiveStatus'">
              <span 
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border"
                :class="{
                  'bg-slate-100 text-slate-600 border-slate-200': record.archiveStatus === 'archived',
                  'bg-amber-50 text-amber-600 border-amber-100': record.archiveStatus === 'pending'
                }"
              >
                 <span class="w-1.5 h-1.5 rounded-full" :class="{
                  'bg-slate-500': record.archiveStatus === 'archived',
                  'bg-amber-500': record.archiveStatus === 'pending'
                }"></span>
                {{ getArchiveStatusText(record.archiveStatus) }}
              </span>
            </template>
            
            <template v-if="column.key === 'qcScore'">
               <div class="flex items-center gap-2">
                 <span class="font-mono font-bold text-slate-700">{{ record.qcScore || '-' }}</span>
                 <a-progress 
                   :percent="record.qcScore" 
                   :show-info="false" 
                   :stroke-color="getScoreColor(record.qcScore)" 
                   size="small" 
                   class="w-16"
                 />
               </div>
            </template>

            <template v-if="column.key === 'action'">
              <div class="flex items-center gap-1">
                <a-tooltip title="查看详情">
                  <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-blue-600 transition-all" @click="handleView(record)">
                    <EyeOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="质控报告">
                  <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-blue-50 hover:text-blue-600 transition-all" @click="handleQCReport(record)">
                    <FileSearchOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip title="归档" v-if="record.archiveStatus === 'pending'">
                  <button class="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-emerald-50 hover:text-emerald-600 transition-all" @click="handleArchive(record)">
                    <FolderOutlined />
                  </button>
                </a-tooltip>
              </div>
            </template>
          </template>
        </a-table>
      </div>
      
      <!-- 底部批量操作栏 (有选中时显示) -->
      <transition name="slide-up">
        <div v-if="selectedRowKeys.length > 0" class="absolute bottom-6 left-1/2 -translate-x-1/2 bg-slate-800 text-white px-6 py-3 rounded-full shadow-xl flex items-center gap-6 z-50">
           <span class="text-sm font-medium">已选择 <span class="text-blue-400 font-bold mx-1">{{ selectedRowKeys.length }}</span> 项</span>
           <div class="h-4 w-px bg-slate-600"></div>
           <div class="flex items-center gap-2">
             <button class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs font-medium transition-colors flex items-center gap-2" @click="handleBatchArchive">
               <FolderOutlined /> 批量归档
             </button>
             <button class="w-8 h-8 rounded-full bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors ml-2" @click="selectedRowKeys = []">
               <CloseOutlined />
             </button>
           </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
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
  TrophyOutlined,
  CloseOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const searchKeyword = ref('')
const selectedDepartment = ref(undefined)
const selectedQCStatus = ref(undefined)
const dateRange = ref([])
const records = ref([])
const selectedRowKeys = ref<string[]>([])

// 分页配置
const pagination = ref({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`
})

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  }
}))

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
    title: '患者信息',
    key: 'patientInfo',
    width: 150
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 120
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
    width: 120
  },
  {
    title: '归档状态',
    dataIndex: 'archiveStatus',
    key: 'archiveStatus',
    width: 120
  },
  {
    title: '质控得分',
    dataIndex: 'qcScore',
    key: 'qcScore',
    width: 150
  },
  {
    title: '操作',
    key: 'action',
    width: 140,
    fixed: 'right'
  }
]

const getQCStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    passed: '通过',
    failed: '未通过',
    pending: '待质控'
  }
  return textMap[status] || status
}

const getArchiveStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    archived: '已归档',
    pending: '待归档'
  }
  return textMap[status] || status
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#10b981' // emerald-500
  if (score >= 80) return '#3b82f6' // blue-500
  if (score >= 60) return '#f59e0b' // amber-500
  return '#f43f5e' // rose-500
}

// 事件处理函数
const handleSearch = () => {
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
  message.success(`批量归档 ${selectedRowKeys.value.length} 条病历成功`)
  selectedRowKeys.value = []
}

const handleExport = () => {
  message.loading('正在导出...', 1)
  setTimeout(() => {
    message.success('导出成功')
  }, 1000)
}

const handleView = (record) => {
  message.info(`查看病历: ${record.recordNumber}`)
}

const handleQCReport = (record) => {
  message.info(`查看质控报告: ${record.recordNumber}`)
}

const handleArchive = (record) => {
  message.success(`归档成功: ${record.recordNumber}`)
}

const handleTableChange = (pag) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  fetchRecords()
}

// 获取数据
const fetchRecords = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 600))
    
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
      },
      {
        id: 3,
        recordNumber: 'F2024003',
        patientName: '李四',
        department: '儿科',
        dischargeDate: '2024-01-15',
        qcStatus: 'passed',
        archiveStatus: 'pending',
        qcScore: 88
      },
      {
        id: 4,
        recordNumber: 'F2024004',
        patientName: '张三',
        department: '内科',
        dischargeDate: '2024-01-18',
        qcStatus: 'pending',
        archiveStatus: 'pending',
        qcScore: null
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
/* 自定义下拉框样式 */
:deep(.custom-select .ant-select-selector) {
  background-color: #f8fafc !important; /* slate-50 */
  border-radius: 0.75rem !important; /* rounded-xl */
  border: 1px solid #e2e8f0 !important; /* slate-200 */
  height: 36px !important;
  display: flex;
  align-items: center;
}

:deep(.custom-select:hover .ant-select-selector) {
  border-color: #60a5fa !important; /* blue-400 */
}

:deep(.custom-select .ant-select-selection-placeholder) {
  line-height: 34px !important;
  color: #94a3b8 !important; /* slate-400 */
}

:deep(.custom-select .ant-select-selection-item) {
  line-height: 34px !important;
  color: #334155 !important; /* slate-700 */
  font-weight: 500;
}

/* 表格样式优化 */
:deep(.modern-table .ant-table) {
  background: transparent;
}

:deep(.modern-table .ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f1f5f9;
}

:deep(.modern-table .ant-table-tbody > tr > td) {
  padding: 12px 16px;
  border-bottom: 1px solid #f8fafc;
  font-size: 13px;
}

:deep(.modern-table .ant-table-tbody > tr:hover > td) {
  background: #f8fafc;
}

/* 分页样式 */
:deep(.ant-pagination-item) {
  border-radius: 8px;
  background: white;
}

:deep(.ant-pagination-item-active) {
  background: #2563eb;
  border-color: #2563eb;
}

:deep(.ant-pagination-item-active a) {
  color: white;
}

/* 底部批量操作栏动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translate(-50%, 100%);
  opacity: 0;
}
</style>
