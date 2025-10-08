<template>
  <div class="running-records-page bg-gray-50 min-h-screen">
    <!-- 页面头部 -->
    <div class="page-header bg-white border-b border-gray-200">
      <!-- 面包屑导航 -->
      <div class="breadcrumb-container px-6 py-3 bg-gray-50 border-b border-gray-100">
        <a-breadcrumb class="text-sm">
          <a-breadcrumb-item>
            <HomeOutlined class="mr-1" />
            <router-link to="/dashboard" class="text-gray-600 hover:text-blue-600">首页</router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <FileTextOutlined class="mr-1" />
            <span class="text-gray-600">病案质控</span>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <PlayCircleOutlined class="mr-1" />
            <span class="text-gray-900 font-medium">运行病历</span>
          </a-breadcrumb-item>
        </a-breadcrumb>
      </div>

      <!-- 页面标题区域 -->
      <div class="title-container px-6 py-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
              <PlayCircleOutlined class="text-blue-600 text-lg" />
            </div>
            <div>
              <h1 class="text-xl font-semibold text-gray-900 mb-0">运行病历</h1>
              <p class="text-sm text-gray-500 mt-1">实时监控运行中的病历质控状态</p>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <a-badge :count="12" :offset="[10, 0]">
              <a-button type="text" size="small" class="text-gray-500">
                <BellOutlined />
              </a-button>
            </a-badge>
            <a-button type="text" size="small" class="text-gray-500">
              <QuestionCircleOutlined />
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="content-container p-6">
      <div class="bg-white rounded-lg shadow-sm border border-gray-200">
        <!-- 查询条件区域 -->
        <div class="query-section px-6 py-4 border-b border-gray-100">
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <!-- 时间周期查询 -->
            <div class="query-item">
              <label class="block text-sm font-medium text-gray-700 mb-2">时间周期</label>
              <a-select
                v-model:value="queryConditions.timeRange"
                placeholder="选择时间周期"
                class="w-full"
                size="middle"
                @change="handleTimeRangeChange"
              >
                <a-select-option value="all">全部</a-select-option>
                <a-select-option value="recent7">近7日</a-select-option>
                <a-select-option value="month">月</a-select-option>
                <a-select-option value="quarter">季度</a-select-option>
                <a-select-option value="year">年</a-select-option>
                <a-select-option value="custom">自定义周期</a-select-option>
              </a-select>
              <a-range-picker
                v-if="queryConditions.timeRange === 'custom'"
                v-model:value="customTimeRange"
                class="w-full mt-2"
                size="middle"
                @change="handleCustomTimeChange"
              />
            </div>

            <!-- 评分标准查询 -->
            <div class="query-item">
              <label class="block text-sm font-medium text-gray-700 mb-2">评分标准</label>
              <a-select
                v-model:value="queryConditions.scoringStandard"
                placeholder="选择评分标准"
                class="w-full"
                size="middle"
                @change="handleQuery"
              >
                <a-select-option value="all">全部</a-select-option>
                <a-select-option value="standard1">标准评分1</a-select-option>
                <a-select-option value="standard2">标准评分2</a-select-option>
                <a-select-option value="standard3">标准评分3</a-select-option>
              </a-select>
            </div>

            <!-- 病历信息查询 -->
            <div class="query-item">
              <label class="block text-sm font-medium text-gray-700 mb-2">病历信息</label>
              <a-input-group compact>
                <a-select
                  v-model:value="queryConditions.searchType"
                  style="width: 35%"
                  size="middle"
                >
                  <a-select-option value="registrationNo">登记号</a-select-option>
                  <a-select-option value="serialNo">流水号</a-select-option>
                  <a-select-option value="caseNo">病案号</a-select-option>
                  <a-select-option value="patientName">患者姓名</a-select-option>
                  <a-select-option value="doctorName">临床医生</a-select-option>
                </a-select>
                <a-input
                  v-model:value="queryConditions.searchValue"
                  style="width: 65%"
                  placeholder="输入查询内容"
                  size="middle"
                  @press-enter="handleQuery"
                >
                  <template #suffix>
                    <SearchOutlined @click="handleQuery" class="cursor-pointer text-gray-400 hover:text-blue-500" />
                  </template>
                </a-input>
              </a-input-group>
            </div>
          </div>
        </div>

        <!-- 筛选条件区域 -->
        <div class="filter-section px-6 py-4 bg-gray-50 border-b border-gray-100">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center space-x-3">
              <span class="text-sm font-medium text-gray-700">筛选条件</span>
              
              <!-- 快捷筛选 -->
              <a-dropdown placement="bottomLeft">
                <a-button size="small" class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300">
                  <FilterOutlined class="mr-1" />
                  快捷筛选
                  <DownOutlined class="ml-1 text-xs" />
                </a-button>
                <template #overlay>
                  <a-menu @click="handleQuickFilter" class="min-w-[160px]">
                    <a-menu-item v-for="template in filterTemplates" :key="template.id" class="text-sm">
                      <template #icon>
                        <TagOutlined class="text-xs" />
                      </template>
                      {{ template.name }}
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>

              <a-button size="small" type="primary" @click="showFilterModal = true" class="bg-blue-600 border-blue-600">
                <PlusOutlined class="mr-1" />
                新建筛选
              </a-button>

              <a-button size="small" @click="showFilterModal = true" class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300">
                <EditOutlined class="mr-1" />
                修改筛选
              </a-button>

              <a-button size="small" @click="handleResetFilter" class="border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300">
                <ClearOutlined class="mr-1" />
                重置筛选
              </a-button>
            </div>

            <div class="flex items-center space-x-3">
              <span class="text-sm text-gray-500">{{ currentView === 'defects' ? '缺陷列表' : '病历列表' }}</span>
              <a-switch
                v-model:checked="currentView"
                checked-value="records"
                un-checked-value="defects"
                size="small"
                @change="handleViewChange"
              >
                <template #checkedChildren>
                  <FileTextOutlined class="text-xs" />
                </template>
                <template #unCheckedChildren>
                  <ExclamationCircleOutlined class="text-xs" />
                </template>
              </a-switch>
            </div>
          </div>

          <!-- 当前筛选条件显示 -->
          <div class="filter-tags-container">
            <div class="flex flex-wrap gap-2" v-if="activeFilterConditions.length > 0">
              <a-tag
                v-for="(condition, index) in activeFilterConditions"
                :key="index"
                closable
                @close="removeFilterCondition(index)"
                color="blue"
                class="px-2 py-1 text-xs"
              >
                <span class="font-medium">{{ condition.label }}</span>: {{ condition.value }}
              </a-tag>
            </div>
            <div v-else class="text-xs text-gray-400 py-1">
              暂无筛选条件，点击上方按钮添加筛选条件
            </div>
          </div>
        </div>

        <!-- 操作按钮区域 -->
        <div class="action-section px-6 py-4 border-b border-gray-100">
          <div class="flex items-center justify-between">
            <!-- 左侧批量操作 -->
            <div class="flex items-center space-x-3">
              <div class="flex items-center space-x-2" v-if="selectedRowKeys.length > 0">
                <span class="text-sm text-gray-600">已选择 {{ selectedRowKeys.length }} 项</span>
                <a-divider type="vertical" class="mx-2" />
              </div>
              
              <!-- 批量操作按钮 -->
              <a-button
                v-if="selectedRowKeys.length > 0"
                type="primary"
                size="small"
                @click="handleBatchUrge"
                :disabled="!canBatchUrge"
                class="bg-blue-600 border-blue-600"
              >
                <SendOutlined class="mr-1" />
                批量催办 ({{ selectedRowKeys.length }})
              </a-button>

              <a-button
                v-if="selectedRowKeys.length > 0 && currentView === 'records'"
                size="small"
                @click="handleBatchRecheck"
                class="border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400"
              >
                <ReloadOutlined class="mr-1" />
                批量重新质控
              </a-button>

              <a-button
                v-if="selectedRowKeys.length > 0 && currentView === 'records'"
                size="small"
                @click="handleBatchPass"
                class="border-green-300 text-green-600 hover:text-green-700 hover:border-green-400"
              >
                <CheckOutlined class="mr-1" />
                批量通过
              </a-button>

              <!-- 无选择时的提示 -->
              <div v-if="selectedRowKeys.length === 0" class="text-sm text-gray-400">
                请选择需要操作的记录
              </div>
            </div>

            <!-- 右侧功能按钮 -->
            <div class="flex items-center space-x-2">
              <a-button 
                size="small" 
                @click="handleExportAll" 
                :loading="exportLoading"
                class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
              >
                <DownloadOutlined class="mr-1" />
                导出全部列表
              </a-button>

              <a-button
                v-if="currentView === 'records'"
                size="small"
                @click="handleExportQCDetails"
                :loading="exportLoading"
                class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
              >
                <FileExcelOutlined class="mr-1" />
                导出质控详情
              </a-button>

              <a-button 
                size="small" 
                @click="handleRefresh" 
                :loading="loading"
                class="border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300"
              >
                <ReloadOutlined class="mr-1" />
                刷新
              </a-button>

              <!-- 自定义列设置 -->
              <a-button 
                size="small" 
                @click="showColumnSettings = true"
                class="border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300"
              >
                <SettingOutlined />
              </a-button>
            </div>
          </div>
        </div>

        <!-- 数据列表区域 -->
        <div class="data-section p-6">
          <a-table
            :columns="recordColumns"
            :data-source="records"
            :loading="loading"
            :pagination="pagination"
            :row-selection="rowSelection"
            @change="handleTableChange"
            row-key="id"
            size="small"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'registrationNo'">
                <a @click="handleViewDetail(record)" class="text-blue-600 hover:text-blue-800">
                  {{ record.registrationNo }}
                </a>
              </template>
              <template v-if="column.key === 'serialNo'">
                <a @click="handleViewDetail(record)" class="text-blue-600 hover:text-blue-800">
                  {{ record.serialNo }}
                </a>
              </template>
              <template v-if="column.key === 'caseNo'">
                <a @click="handleViewDetail(record)" class="text-blue-600 hover:text-blue-800">
                  {{ record.caseNo }}
                </a>
              </template>
              <template v-if="column.key === 'auditStatus'">
                <a-tag :color="getAuditStatusColor(record.auditStatus)">
                  {{ getAuditStatusText(record.auditStatus) }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <div class="flex space-x-1">
                  <a-button type="link" size="small" @click="handleViewDetail(record)">
                    详情
                  </a-button>
                  <a-button
                    v-if="!record.isUrgent"
                    type="link"
                    size="small"
                    @click="handleUrgeRecord(record)"
                  >
                    催办
                  </a-button>
                </div>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  DownOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SettingOutlined,
  HomeOutlined,
  FileTextOutlined,
  PlayCircleOutlined,
  BellOutlined,
  QuestionCircleOutlined,
  FilterOutlined,
  TagOutlined,
  PlusOutlined,
  EditOutlined,
  ClearOutlined,
  ExclamationCircleOutlined,
  SendOutlined,
  CheckOutlined,
  FileExcelOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const exportLoading = ref(false)
const showFilterModal = ref(false)
const showColumnSettings = ref(false)
const currentView = ref('records')
const selectedRowKeys = ref<string[]>([])
const customTimeRange = ref()

// 查询条件
const queryConditions = reactive({
  timeRange: 'all',
  scoringStandard: 'all',
  searchType: 'registrationNo',
  searchValue: ''
})

// 筛选条件
const activeFilterConditions = ref([
  { label: '科室', value: '内科' },
  { label: '状态', value: '待审核' }
])

const filterTemplates = ref([
  { id: 1, name: '今日待审核' },
  { id: 2, name: '本周超时' },
  { id: 3, name: '高风险病历' },
  { id: 4, name: '重点科室' }
])

// 表格数据
const records = ref([
  {
    id: '1',
    registrationNo: 'R2024001',
    serialNo: 'S2024001',
    caseNo: 'C2024001',
    patientName: '张三',
    doctorName: '李医生',
    department: '内科',
    auditStatus: 'pending',
    isUrgent: false
  }
])

// 表格列配置
const recordColumns = [
  { title: '登记号', dataIndex: 'registrationNo', key: 'registrationNo', width: 120 },
  { title: '流水号', dataIndex: 'serialNo', key: 'serialNo', width: 120 },
  { title: '病案号', dataIndex: 'caseNo', key: 'caseNo', width: 120 },
  { title: '患者姓名', dataIndex: 'patientName', key: 'patientName', width: 100 },
  { title: '临床医生', dataIndex: 'doctorName', key: 'doctorName', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
  { title: '审核状态', dataIndex: 'auditStatus', key: 'auditStatus', width: 100 },
  { title: '操作', key: 'action', width: 120, fixed: 'right' }
]

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 100,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
})

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value, onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
  getCheckboxProps: (record: unknown) => ({
    disabled: record.disabled
  })
}))

// 计算属性
const canBatchUrge = computed(() => {
  return selectedRowKeys.value.length > 0
})

// 方法
const handleTimeRangeChange = (value: string) => {
  console.log('Time range changed:', value)
  handleQuery()
}

const handleCustomTimeChange = (dates) => {
  console.log('Custom time range:', dates)
  handleQuery()
}

const handleQuery = () => {
  loading.value = true
  // 模拟查询
  setTimeout(() => {
    loading.value = false
    message.success('查询完成')
  }, 1000)
}

const handleQuickFilter = ({ key }: { key: string }) => {
  console.log('Quick filter:', key)
  message.info('应用快捷筛选')
}

const handleResetFilter = () => {
  activeFilterConditions.value = []
  message.info('筛选条件已重置')
}

const removeFilterCondition = (index: number) => {
  activeFilterConditions.value.splice(index, 1)
}

const handleViewChange = (checked: boolean) => {
  console.log('View changed:', checked)
}

const handleBatchUrge = () => {
  message.info(`批量催办 ${selectedRowKeys.value.length} 条记录`)
}

const handleBatchRecheck = () => {
  message.info(`批量重新质控 ${selectedRowKeys.value.length} 条记录`)
}

const handleBatchPass = () => {
  message.info(`批量通过 ${selectedRowKeys.value.length} 条记录`)
}

const handleExportAll = () => {
  exportLoading.value = true
  setTimeout(() => {
    exportLoading.value = false
    message.success('导出完成')
  }, 2000)
}

const handleExportQCDetails = () => {
  exportLoading.value = true
  setTimeout(() => {
    exportLoading.value = false
    message.success('质控详情导出完成')
  }, 2000)
}

const handleRefresh = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    message.success('刷新完成')
  }, 1000)
}

const handleTableChange = (pag, filters: unknown,  sorter: unknown) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  handleQuery()
}

const handleViewDetail = (record) => {
  console.log('View detail:', record)
  message.info('查看详情')
}

const handleUrgeRecord = (record) => {
  console.log('Urge record:', record)
  message.info('催办成功')
}

const getAuditStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    approved: 'green',
    rejected: 'red',
    reviewing: 'blue'
  }
  return colorMap[status] || 'default'
}

const getAuditStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝',
    reviewing: '审核中'
  }
  return textMap[status] || '未知'
}

// 生命周期
onMounted(() => {
  handleQuery()
})
</script>

<style scoped>
/* 页面整体布局 */
.running-records-page {
  background-color: #f8fafc;
}

/* 页面头部样式 */
.page-header {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.breadcrumb-container {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.title-container {
  background: white;
}

/* 内容区域样式 */
.content-container {
  padding: 24px;
}

/* 查询条件区域 */
.query-section {
  background: white;
}

.query-item label {
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

/* 筛选条件区域 */
.filter-section {
  background: #f9fafb;
  border-top: 1px solid #f3f4f6;
}

.filter-tags-container {
  min-height: 32px;
  display: flex;
  align-items: center;
}

/* 操作按钮区域 */
.action-section {
  background: white;
  border-top: 1px solid #f3f4f6;
}

/* 表格样式 */
:deep(.ant-table-thead > tr > th) {
  background-color: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  color: #374151;
}

:deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid #f3f4f6;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc;
}

/* 按钮样式增强 */
:deep(.ant-btn-sm) {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
  border-radius: 6px;
  font-weight: 500;
}

:deep(.ant-btn-primary) {
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.15);
}

/* 选择器样式 */
:deep(.ant-select-selector) {
  border-radius: 6px;
  border-color: #d1d5db;
}

:deep(.ant-select-focused .ant-select-selector) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

:deep(.ant-input) {
  border-radius: 6px;
  border-color: #d1d5db;
}

:deep(.ant-input:focus) {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

/* 标签样式 */
:deep(.ant-tag) {
  border-radius: 4px;
  font-size: 12px;
  line-height: 20px;
}

/* 面包屑样式 */
:deep(.ant-breadcrumb) {
  font-size: 13px;
}

:deep(.ant-breadcrumb-link) {
  color: #6b7280;
  text-decoration: none;
  transition: color 0.2s ease;
}

:deep(.ant-breadcrumb-link:hover) {
  color: #3b82f6;
}

/* 开关样式 */
:deep(.ant-switch-small) {
  min-width: 36px;
  height: 18px;
}

/* 下拉菜单样式 */
:deep(.ant-dropdown-menu) {
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

:deep(.ant-dropdown-menu-item) {
  padding: 8px 16px;
  font-size: 13px;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .content-container {
    padding: 16px;
  }

  .query-section .grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .filter-section .flex {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .action-section .flex {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}

@media (max-width: 768px) {
  .title-container .flex {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .breadcrumb-container {
    padding: 12px 16px;
  }

  .title-container {
    padding: 16px;
  }

  .query-section,
  .filter-section,
  .action-section {
    padding: 16px;
  }
}
</style>
