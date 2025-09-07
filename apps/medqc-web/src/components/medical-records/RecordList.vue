<template>
  <div class="record-list">
    <!-- 搜索和筛选栏 -->
    <div class="mb-6 p-4 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50">
      <div class="flex flex-col lg:flex-row gap-4">
        <!-- 搜索框 -->
        <div class="flex-1">
          <a-input-search
            v-model:value="searchParams.keyword"
            placeholder="搜索患者姓名、科室或记录内容..."
            size="large"
            @search="handleSearch"
            class="search-input"
          >
            <template #prefix>
              <SearchOutlined class="text-slate-400" />
            </template>
          </a-input-search>
        </div>

        <!-- 筛选器 -->
        <div class="flex gap-3">
          <!-- 科室筛选 -->
          <a-select
            v-model:value="searchParams.filters.department"
            placeholder="选择科室"
            size="large"
            style="width: 150px"
            allow-clear
            @change="handleFilterChange"
            class="filter-select"
          >
            <a-select-option 
              v-for="dept in departments" 
              :key="dept" 
              :value="dept"
            >
              {{ dept }}
            </a-select-option>
          </a-select>

          <!-- 状态筛选 -->
          <a-select
            v-model:value="searchParams.filters.status"
            placeholder="记录状态"
            size="large"
            style="width: 120px"
            allow-clear
            @change="handleFilterChange"
            class="filter-select"
          >
            <a-select-option value="pending">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-amber-400"></div>
                待处理
              </div>
            </a-select-option>
            <a-select-option value="analyzing">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-blue-400"></div>
                分析中
              </div>
            </a-select-option>
            <a-select-option value="completed">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
                已完成
              </div>
            </a-select-option>
            <a-select-option value="failed">
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-red-400"></div>
                失败
              </div>
            </a-select-option>
          </a-select>

          <!-- 记录类型筛选 -->
          <a-select
            v-model:value="searchParams.filters.record_type"
            placeholder="记录类型"
            size="large"
            style="width: 120px"
            allow-clear
            @change="handleFilterChange"
            class="filter-select"
          >
            <a-select-option value="inpatient">住院</a-select-option>
            <a-select-option value="outpatient">门诊</a-select-option>
            <a-select-option value="emergency">急诊</a-select-option>
          </a-select>

          <!-- 刷新按钮 -->
          <a-button 
            size="large" 
            @click="handleRefresh"
            :loading="loading"
            class="bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50"
          >
            <ReloadOutlined />
          </a-button>
        </div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <h3 class="text-lg font-semibold text-slate-100">
          医疗记录列表
          <span class="text-sm font-normal text-slate-400 ml-2">
            (共 {{ pagination.total }} 条记录)
          </span>
        </h3>
      </div>

      <div class="flex items-center gap-3">
        <!-- 批量操作 -->
        <a-dropdown v-if="selectedRowKeys.length > 0" :trigger="['click']">
          <a-button size="large" class="bg-blue-500/20 border-blue-400/30 text-blue-300">
            <MoreOutlined />
            批量操作 ({{ selectedRowKeys.length }})
          </a-button>
          <template #overlay>
            <a-menu @click="handleBatchAction">
              <a-menu-item key="analyze">
                <ThunderboltOutlined />
                批量分析
              </a-menu-item>
              <a-menu-item key="export">
                <ExportOutlined />
                导出记录
              </a-menu-item>
              <a-menu-divider />
              <a-menu-item key="delete" class="text-red-400">
                <DeleteOutlined />
                批量删除
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>

        <!-- 新增记录按钮 -->
        <a-button 
          type="primary" 
          size="large"
          @click="$emit('create-record')"
          class="bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none"
        >
          <PlusOutlined />
          新增记录
        </a-button>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 overflow-hidden">
      <a-table
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="paginationConfig"
        :row-selection="rowSelection"
        :scroll="{ x: 1200 }"
        size="middle"
        @change="handleTableChange"
        class="medical-records-table"
      >
        <!-- 患者信息列 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'patient'">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-semibold">
                {{ record.patient_name.charAt(0) }}
              </div>
              <div>
                <div class="font-medium text-slate-100">{{ record.patient_name }}</div>
                <div class="text-xs text-slate-400">
                  {{ record.patient_age }}岁 · {{ getGenderLabel(record.patient_gender) }}
                </div>
              </div>
            </div>
          </template>

          <!-- 状态列 -->
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)" class="status-tag">
              <div class="flex items-center gap-1">
                <div 
                  class="w-1.5 h-1.5 rounded-full"
                  :class="getStatusDotClass(record.status)"
                ></div>
                {{ getStatusLabel(record.status) }}
              </div>
            </a-tag>
          </template>

          <!-- 质控评分列 -->
          <template v-else-if="column.key === 'qc_score'">
            <div v-if="record.qc_score !== null" class="flex items-center gap-2">
              <div class="text-lg font-bold" :class="getScoreColor(record.qc_score)">
                {{ record.qc_score }}
              </div>
              <a-tag 
                :color="getGradeColor(record.qc_grade)" 
                size="small"
                v-if="record.qc_grade"
              >
                {{ record.qc_grade }}级
              </a-tag>
            </div>
            <span v-else class="text-slate-400 text-sm">未评分</span>
          </template>

          <!-- 记录类型列 -->
          <template v-else-if="column.key === 'record_type'">
            <a-tag :color="getRecordTypeColor(record.record_type)">
              {{ getRecordTypeLabel(record.record_type) }}
            </a-tag>
          </template>

          <!-- 操作列 -->
          <template v-else-if="column.key === 'actions'">
            <div class="flex items-center gap-2">
              <a-tooltip title="查看详情">
                <a-button 
                  size="small" 
                  type="text"
                  @click="$emit('view-record', record)"
                  class="text-blue-400 hover:text-blue-300"
                >
                  <EyeOutlined />
                </a-button>
              </a-tooltip>

              <a-tooltip title="查看详情">
                <a-button
                  size="small"
                  type="text"
                  @click="$emit('edit-record', record)"
                  class="text-emerald-400 hover:text-emerald-300"
                >
                  <EditOutlined />
                </a-button>
              </a-tooltip>

              <a-tooltip title="质控分析" v-if="record.status === 'pending'">
                <a-button 
                  size="small" 
                  type="text"
                  @click="$emit('analyze-record', record)"
                  class="text-amber-400 hover:text-amber-300"
                >
                  <ThunderboltOutlined />
                </a-button>
              </a-tooltip>

              <a-dropdown :trigger="['click']">
                <a-button size="small" type="text" class="text-slate-400 hover:text-slate-300">
                  <MoreOutlined />
                </a-button>
                <template #overlay>
                  <a-menu @click="({ key   }) => handleRecordAction(key, record)">
                    <a-menu-item key="download" v-if="record.file_url">
                      <DownloadOutlined />
                      下载文件
                    </a-menu-item>
                    <a-menu-item key="duplicate">
                      <CopyOutlined />
                      复制记录
                    </a-menu-item>
                    <a-menu-divider />
                    <a-menu-item key="delete" class="text-red-400">
                      <DeleteOutlined />
                      删除记录
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  ReloadOutlined,
  PlusOutlined,
  MoreOutlined,
  ThunderboltOutlined,
  ExportOutlined,
  DeleteOutlined,
  EyeOutlined,
  EditOutlined,
  DownloadOutlined,
  CopyOutlined
} from '@ant-design/icons-vue'
import type { 
  MedicalRecord, 
  SearchParams, 
  PaginationParams,
  TableColumn 
} from '@/types'
import { DEPARTMENTS } from '@/types/medical-records'

// Props
interface Props {
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Emits
const emit = defineEmits<{
  'create-record': []
  'view-record': [record: MedicalRecord]
  'edit-record': [record: MedicalRecord]
  'analyze-record': [record: MedicalRecord]
  'search': [params: SearchParams]
  'batch-action': [action: string, records: MedicalRecord[]]
  'record-action': [action: string, record: MedicalRecord]
}>()

// 状态
const loading = ref(false)
const records = ref<MedicalRecord[]>([])
const selectedRowKeys = ref<string[]>([])

// 搜索参数
const searchParams = reactive<SearchParams>({
  keyword: '',
  filters: {
    department: undefined,
    status: undefined,
    record_type: undefined
  },
  sort: {
    field: 'created_at',
    order: 'desc'
  },
  pagination: {
    page: 1,
    pageSize: 20
  }
})

// 分页配置
const pagination = reactive<PaginationParams>({
  page: 1,
  pageSize: 20,
  total: 0
})

// 科室列表
const departments = DEPARTMENTS

// 表格列配置
const columns: TableColumn[] = [
  {
    title: '患者信息',
    key: 'patient',
    width: 200,
    fixed: 'left'
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 120,
    filters: departments.map(dept => ({ text: dept, value: dept }))
  },
  {
    title: '记录类型',
    key: 'record_type',
    width: 100
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    filters: [
      { text: '待处理', value: 'pending' },
      { text: '分析中', value: 'analyzing' },
      { text: '已完成', value: 'completed' },
      { text: '失败', value: 'failed' }
    ]
  },
  {
    title: '质控评分',
    key: 'qc_score',
    width: 120,
    sorter: true
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 160,
    sorter: true,
    render: (value: string) => new Date(value).toLocaleString('zh-CN')
  },
  {
    title: '操作',
    key: 'actions',
    width: 150,
    fixed: 'right'
  }
]

// 表格分页配置
const paginationConfig = computed(() => ({
  current: pagination.page,
  pageSize: pagination.pageSize,
  total: pagination.total,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) => 
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条记录`
}))

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value, onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
  getCheckboxProps: (record: MedicalRecord) => ({
    disabled: record.status === 'analyzing'
  })
}))

// 处理搜索
const handleSearch = () => {
  searchParams.pagination!.page = 1
  emit('search', { ...searchParams })
}

// 处理筛选变化
const handleFilterChange = () => {
  handleSearch()
}

// 处理刷新
const handleRefresh = () => {
  emit('search', { ...searchParams })
}

// 处理表格变化
const handleTableChange = (pag, filters: any,  sorter: any) => {
  // 更新分页
  if (pag) {
    searchParams.pagination!.page = pag.current
    searchParams.pagination!.pageSize = pag.pageSize
  }

  // 更新排序
  if (sorter && sorter.field) {
    searchParams.sort = {
      field: sorter.field,
      order: sorter.order === 'ascend' ? 'asc' : 'desc'
    }
  }

  // 更新筛选
  if (filters) {
    Object.keys(filters).forEach(key => {
      if (filters[key]) {
        searchParams.filters![key] = filters[key][0]
      }
    })
  }

  emit('search', { ...searchParams })
}

// 处理批量操作
const handleBatchAction = ({ key }: { key: string }) => {
  const selectedRecords = records.value.filter(record => 
    selectedRowKeys.value.includes(record.id)
  )
  emit('batch-action', key, selectedRecords)
}

// 处理记录操作
const handleRecordAction = (action: string, record: MedicalRecord) => {
  emit('record-action', action, record)
}

// 获取状态颜色
const getStatusColor = (status: string) => {
  const colors = {
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

// 获取状态标签
const getStatusLabel = (status: string) => {
  const labels = {
    pending: '待处理',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

// 获取状态点样式
const getStatusDotClass = (status: string) => {
  const classes = {
    pending: 'bg-amber-400',
    analyzing: 'bg-blue-400 animate-pulse',
    completed: 'bg-emerald-400',
    failed: 'bg-red-400'
  }
  return classes[status as keyof typeof classes] || 'bg-gray-400'
}

// 获取评分颜色
const getScoreColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

// 获取等级颜色
const getGradeColor = (grade: string) => {
  const colors = {
    A: 'green',
    B: 'blue',
    C: 'orange'
  }
  return colors[grade as keyof typeof colors] || 'default'
}

// 获取记录类型颜色
const getRecordTypeColor = (type: string) => {
  const colors = {
    inpatient: 'blue',
    outpatient: 'green',
    emergency: 'red'
  }
  return colors[type as keyof typeof colors] || 'default'
}

// 获取记录类型标签
const getRecordTypeLabel = (type: string) => {
  const labels = {
    inpatient: '住院',
    outpatient: '门诊',
    emergency: '急诊'
  }
  return labels[type as keyof typeof labels] || type
}

// 获取性别标签
const getGenderLabel = (gender: string) => {
  const labels = {
    M: '男',
    F: '女',
    U: '未知'
  }
  return labels[gender as keyof typeof labels] || gender
}

// 暴露方法给父组件
defineExpose({
  refresh: handleRefresh, clearSelection: () => {
    selectedRowKeys.value = []
  },
  updateRecords: (newRecords: MedicalRecord[]) => {
    records.value = newRecords
  },
  updatePagination: (newPagination: PaginationParams) => {
    Object.assign(pagination, newPagination)
  }
})
</script>

<style scoped>
/* 搜索输入框样式 */
:deep(.search-input .ant-input) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

:deep(.search-input .ant-input:focus) {
  border-color: #06b6d4 !important;
  box-shadow: 0 0 0 2px rgba(6, 182, 212, 0.2) !important;
}

/* 筛选选择器样式 */
:deep(.filter-select .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

/* 表格样式 */
:deep(.medical-records-table) {
  background: transparent !important;
}

:deep(.medical-records-table .ant-table-thead > tr > th) {
  background: rgba(30, 41, 59, 0.8) !important;
  border-bottom: 1px solid rgba(71, 85, 105, 0.3) !important;
  color: rgb(203 213 225) !important;
}

:deep(.medical-records-table .ant-table-tbody > tr > td) {
  background: transparent !important;
  border-bottom: 1px solid rgba(71, 85, 105, 0.2) !important;
  color: rgb(241 245 249) !important;
}

:deep(.medical-records-table .ant-table-tbody > tr:hover > td) {
  background: rgba(71, 85, 105, 0.2) !important;
}

/* 状态标签样式 */
.status-tag {
  border: none !important;
  border-radius: 0.5rem !important;
  font-weight: 500 !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .flex-col.lg\\:flex-row {
    flex-direction: column;
  }
  
  .gap-3 {
    gap: 0.5rem;
  }
}
</style>
