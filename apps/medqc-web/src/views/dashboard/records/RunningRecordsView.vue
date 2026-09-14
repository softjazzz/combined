<template>
  <div class="running-records-page bg-gray-50 min-h-screen">
    <!-- 主要内容区域 -->
    <div class="content-container">
      <div class="bg-white border-b border-gray-200">
        <!-- 查询条件区域 -->
        <div class="query-section px-6 py-4 border-b border-gray-100">
          <div class="flex flex-wrap items-end justify-between gap-6">
            <!-- 左侧查询条件组 -->
            <div class="flex flex-wrap items-end gap-6">
              <!-- 时间周期查询 -->
              <div class="query-item flex-shrink-0">
                <label class="block text-sm font-medium text-gray-700 mb-2">时间周期</label>
                <a-select
                  v-model:value="queryConditions.timeRange"
                  placeholder="选择时间周期"
                  class="w-40"
                  size="middle"
                  @change="handleTimeRangeChange"
                >
                  <a-select-option value="all">
                    全部
                  </a-select-option>
                  <a-select-option value="recent7">
                    近7日
                  </a-select-option>
                  <a-select-option value="month">
                    月
                  </a-select-option>
                  <a-select-option value="quarter">
                    季度
                  </a-select-option>
                  <a-select-option value="year">
                    年
                  </a-select-option>
                  <a-select-option value="custom">
                    自定义周期
                  </a-select-option>
                </a-select>
                <a-range-picker
                  v-if="queryConditions.timeRange === 'custom'"
                  v-model:value="customTimeRange"
                  class="w-64 mt-2"
                  size="middle"
                  @change="handleCustomTimeChange"
                />
              </div>

              <!-- 评分标准查询 -->
              <div class="query-item flex-shrink-0">
                <label class="block text-sm font-medium text-gray-700 mb-2">评分标准</label>
                <a-select
                  v-model:value="queryConditions.scoringStandard"
                  placeholder="选择评分标准"
                  class="w-40"
                  size="middle"
                  @change="handleQuery"
                >
                  <a-select-option value="all">
                    全部
                  </a-select-option>
                  <a-select-option value="standard1">
                    标准评分1
                  </a-select-option>
                  <a-select-option value="standard2">
                    标准评分2
                  </a-select-option>
                  <a-select-option value="standard3">
                    标准评分3
                  </a-select-option>
                </a-select>
              </div>
            </div>

            <!-- 右侧病历信息查询 -->
            <div class="query-item flex-shrink-0">
              <label class="block text-sm font-medium text-gray-700 mb-2">病历信息</label>
              <a-input-group
                compact
                class="w-80"
              >
                <a-select
                  v-model:value="queryConditions.searchType"
                  style="width: 40%"
                  size="middle"
                >
                  <a-select-option value="registrationNo">
                    病历登记号
                  </a-select-option>
                  <a-select-option value="serialNo">
                    病历流水号
                  </a-select-option>
                  <a-select-option value="caseNo">
                    病案号
                  </a-select-option>
                  <a-select-option value="patientName">
                    患者姓名
                  </a-select-option>
                  <a-select-option value="doctorName">
                    临床医生
                  </a-select-option>
                </a-select>
                <a-input
                  v-model:value="queryConditions.searchValue"
                  style="width: 60%"
                  placeholder="输入查询内容"
                  size="middle"
                  @press-enter="handleQuery"
                >
                  <template #suffix>
                    <SearchOutlined
                      class="cursor-pointer text-gray-400 hover:text-blue-500"
                      @click="handleQuery"
                    />
                  </template>
                </a-input>
              </a-input-group>
            </div>
          </div>
        </div>

        <!-- 缺陷列表和快速筛选区域 -->
        <div class="defect-filter-section bg-white border-b border-gray-100">
          <div class="px-6 py-2">
            <!-- 标签页切换 -->
            <div class="flex items-center mb-2">
              <a-tabs
                v-model:active-key="activeTab"
                class="defect-tabs"
                size="middle"
              >
                <a-tab-pane
                  key="defects"
                  tab="缺陷列表"
                />
                <a-tab-pane
                  key="records"
                  tab="病历列表"
                />
              </a-tabs>
            </div>

            <!-- 快速筛选标签 -->
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-medium text-gray-700">快速筛选:</span>
              <div class="flex flex-wrap gap-1">
                <a-tag
                  v-for="filter in quickFilters"
                  :key="filter.key"
                  :color="filter.active ? 'blue' : ''"
                  class="quick-filter-tag-compact"
                  @click="handleQuickFilterClick(filter)"
                >
                  {{ filter.label }}
                </a-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 筛选条件区域 -->
        <div class="filter-section px-6 py-3 bg-gray-50 border-b border-gray-100">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <span class="text-sm font-medium text-gray-700">筛选条件</span>

              <!-- 快捷筛选 -->
              <a-dropdown placement="bottomLeft">
                <a-button
                  size="small"
                  class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
                >
                  <FilterOutlined class="mr-1" />
                  快捷筛选
                  <DownOutlined class="ml-1 text-xs" />
                </a-button>
                <template #overlay>
                  <a-menu
                    class="min-w-[160px]"
                    @click="handleQuickFilter"
                  >
                    <a-menu-item
                      v-for="template in filterTemplates"
                      :key="template.id"
                      class="text-sm"
                    >
                      <template #icon>
                        <TagOutlined class="text-xs" />
                      </template>
                      {{ template.name }}
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>

              <a-button
                size="small"
                type="primary"
                class="bg-blue-600 border-blue-600"
                @click="showFilterModal = true"
              >
                <PlusOutlined class="mr-1" />
                新建筛选
              </a-button>

              <a-button
                size="small"
                class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
                @click="showFilterModal = true"
              >
                <EditOutlined class="mr-1" />
                修改筛选
              </a-button>

              <a-button
                size="small"
                class="border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300"
                @click="handleResetFilter"
              >
                <ClearOutlined class="mr-1" />
                重置筛选
              </a-button>
            </div>

            <div class="flex items-center space-x-3">
              <span class="text-sm text-gray-500">{{
                currentView === 'defects' ? '缺陷列表' : '病历列表'
              }}</span>
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
            <div
              v-if="activeFilterConditions.length > 0"
              class="flex flex-wrap gap-2"
            >
              <a-tag
                v-for="(condition, index) in activeFilterConditions"
                :key="index"
                closable
                color="blue"
                class="px-2 py-1 text-xs"
                @close="removeFilterCondition(index)"
              >
                <span class="font-medium">{{ condition.label }}</span>: {{ condition.value }}
              </a-tag>
            </div>
            <div
              v-else
              class="text-xs text-gray-400 py-1"
            >
              暂无筛选条件，点击上方按钮添加筛选条件
            </div>
          </div>
        </div>

        <!-- 操作按钮区域 -->
        <div class="action-section px-6 py-4 border-b border-gray-100">
          <div class="flex items-center justify-between">
            <!-- 左侧批量操作 -->
            <div class="flex items-center space-x-3">
              <div
                v-if="selectedRowKeys.length > 0"
                class="flex items-center space-x-2"
              >
                <span class="text-sm text-gray-600">已选择 {{ selectedRowKeys.length }} 项</span>
                <a-divider
                  type="vertical"
                  class="mx-2"
                />
              </div>

              <!-- 批量操作按钮 -->
              <a-button
                v-if="selectedRowKeys.length > 0"
                type="primary"
                size="small"
                :disabled="!canBatchUrge"
                class="bg-blue-600 border-blue-600"
                @click="handleBatchUrge"
              >
                <SendOutlined class="mr-1" />
                批量催办 ({{ selectedRowKeys.length }})
              </a-button>

              <a-button
                v-if="selectedRowKeys.length > 0 && currentView === 'records'"
                size="small"
                class="border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400"
                @click="handleBatchRecheck"
              >
                <ReloadOutlined class="mr-1" />
                批量重新质控
              </a-button>

              <a-button
                v-if="selectedRowKeys.length > 0 && currentView === 'records'"
                size="small"
                class="border-green-300 text-green-600 hover:text-green-700 hover:border-green-400"
                @click="handleBatchPass"
              >
                <CheckOutlined class="mr-1" />
                批量通过
              </a-button>

              <!-- 无选择时的提示 -->
              <div
                v-if="selectedRowKeys.length === 0"
                class="text-sm text-gray-400"
              >
                请选择需要操作的记录
              </div>
            </div>

            <!-- 右侧功能按钮 -->
            <div class="flex items-center space-x-2">
              <a-button
                size="small"
                :loading="exportLoading"
                class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
                @click="handleExportAll"
              >
                <DownloadOutlined class="mr-1" />
                导出全部列表
              </a-button>

              <a-button
                v-if="currentView === 'records'"
                size="small"
                :loading="exportLoading"
                class="border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300"
                @click="handleExportQCDetails"
              >
                <FileExcelOutlined class="mr-1" />
                导出质控详情
              </a-button>

              <a-button
                size="small"
                :loading="loading"
                class="border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300"
                @click="handleRefresh"
              >
                <ReloadOutlined class="mr-1" />
                刷新
              </a-button>

              <!-- 自定义列设置 -->
              <a-button
                size="small"
                class="border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300"
                @click="showColumnSettings = true"
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
            row-key="id"
            size="small"
            @change="handleTableChange"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'registrationNo'">
                <a
                  class="text-blue-600 hover:text-blue-800"
                  @click="handleViewDetail(record as RunningRecord)"
                >
                  {{ (record as RunningRecord).registrationNo }}
                </a>
              </template>
              <template v-if="column.key === 'serialNo'">
                <a
                  class="text-blue-600 hover:text-blue-800"
                  @click="handleViewDetail(record as RunningRecord)"
                >
                  {{ (record as RunningRecord).serialNo }}
                </a>
              </template>
              <template v-if="column.key === 'caseNo'">
                <a
                  class="text-blue-600 hover:text-blue-800"
                  @click="handleViewDetail(record as RunningRecord)"
                >
                  {{ (record as RunningRecord).caseNo }}
                </a>
              </template>
              <template v-if="column.key === 'auditStatus'">
                <a-tag :color="getAuditStatusColor((record as RunningRecord).auditStatus)">
                  {{ getAuditStatusText((record as RunningRecord).auditStatus) }}
                </a-tag>
              </template>
              <template v-if="column.key === 'action'">
                <div class="flex space-x-1">
                  <a-button
                    type="link"
                    size="small"
                    @click="handleViewDetail(record as RunningRecord)"
                  >
                    详情
                  </a-button>
                  <a-button
                    v-if="!(record as RunningRecord).isUrgent"
                    type="link"
                    size="small"
                    @click="handleUrgeRecord(record as RunningRecord)"
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

    <!-- 新建筛选弹窗 -->
    <a-modal
      v-model:open="showFilterModal"
      title="新建筛选"
      width="900px"
      :footer="null"
      class="filter-modal"
      :mask-closable="false"
    >
      <div class="filter-form-container">
        <!-- 基础设置 -->
        <div class="filter-section mb-6">
          <h3 class="section-title">
            基础设置
          </h3>
          <div class="form-row">
            <div class="form-item">
              <label class="form-label">筛选类型选择模式：</label>
              <a-radio-group
                v-model:value="filterForm.selectionMode"
                class="ml-2"
              >
                <a-radio value="single">
                  单选
                </a-radio>
                <a-radio value="multiple">
                  不支持多选
                </a-radio>
                <a-radio value="multipleSupported">
                  支持多选
                </a-radio>
              </a-radio-group>
            </div>
          </div>
          <div class="form-row">
            <div class="form-item">
              <label class="form-label">筛选条件名称：</label>
              <a-input
                v-model:value="filterForm.filterName"
                placeholder="请输入"
                class="filter-name-input"
                :maxlength="50"
              />
            </div>
          </div>
        </div>

        <!-- 基本信息类 -->
        <div class="filter-section mb-6">
          <h3 class="section-title">
            基本信息类
          </h3>
          <div class="filter-grid">
            <div class="filter-column">
              <div class="filter-item">
                <label class="filter-label">病历科室</label>
                <a-select
                  v-model:value="filterForm.department"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="internal">
                    内科
                  </a-select-option>
                  <a-select-option value="surgery">
                    外科
                  </a-select-option>
                  <a-select-option value="pediatrics">
                    儿科
                  </a-select-option>
                </a-select>
              </div>
              <div class="filter-item">
                <label class="filter-label">患者性别</label>
                <a-select
                  v-model:value="filterForm.gender"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="male">
                    男
                  </a-select-option>
                  <a-select-option value="female">
                    女
                  </a-select-option>
                </a-select>
              </div>
              <div class="filter-item">
                <label class="filter-label">入院科室</label>
                <a-select
                  v-model:value="filterForm.admissionDept"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="emergency">
                    急诊科
                  </a-select-option>
                  <a-select-option value="internal">
                    内科
                  </a-select-option>
                </a-select>
              </div>
            </div>
            <div class="filter-column">
              <div class="filter-item">
                <label class="filter-label">病历状态</label>
                <a-select
                  v-model:value="filterForm.recordStatus"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="draft">
                    草稿
                  </a-select-option>
                  <a-select-option value="completed">
                    已完成
                  </a-select-option>
                </a-select>
              </div>
              <div class="filter-item">
                <label class="filter-label">人员类型</label>
                <a-select
                  v-model:value="filterForm.staffType"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="doctor">
                    医生
                  </a-select-option>
                  <a-select-option value="nurse">
                    护士
                  </a-select-option>
                </a-select>
              </div>
              <div class="filter-item">
                <label class="filter-label">出院时间</label>
                <a-date-picker
                  v-model:value="filterForm.dischargeDate"
                  placeholder="请选择日期"
                  class="filter-date"
                />
              </div>
            </div>
            <div class="filter-column">
              <div class="filter-item">
                <label class="filter-label">在院状态</label>
                <a-select
                  v-model:value="filterForm.hospitalStatus"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="inpatient">
                    住院
                  </a-select-option>
                  <a-select-option value="outpatient">
                    门诊
                  </a-select-option>
                </a-select>
              </div>
              <div class="filter-item">
                <label class="filter-label">出院科室</label>
                <a-select
                  v-model:value="filterForm.dischargeDept"
                  placeholder="请选择"
                  class="filter-select"
                  allow-clear
                >
                  <a-select-option value="internal">
                    内科
                  </a-select-option>
                  <a-select-option value="surgery">
                    外科
                  </a-select-option>
                </a-select>
              </div>
            </div>
          </div>
          <div class="date-range-row">
            <div class="filter-item">
              <label class="filter-label">入院时间</label>
              <a-date-picker
                v-model:value="filterForm.admissionStartDate"
                placeholder="开始日期"
                class="filter-date-range"
              />
              <span class="date-separator">至</span>
              <a-date-picker
                v-model:value="filterForm.admissionEndDate"
                placeholder="结束日期"
                class="filter-date-range"
              />
            </div>
          </div>
        </div>

        <!-- 底部按钮 -->
        <div class="modal-footer">
          <a-button
            class="cancel-btn"
            @click="handleCancel"
          >
            取消
          </a-button>
          <a-button
            class="reset-btn"
            @click="handleReset"
          >
            清空
          </a-button>
          <a-button
            type="primary"
            class="confirm-btn"
            @click="handleConfirm"
          >
            确定
          </a-button>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import type { Dayjs } from 'dayjs'
import {
  SearchOutlined,
  DownOutlined,
  DownloadOutlined,
  ReloadOutlined,
  SettingOutlined,
  FilterOutlined,
  TagOutlined,
  PlusOutlined,
  EditOutlined,
  ClearOutlined,
  ExclamationCircleOutlined,
  SendOutlined,
  CheckOutlined,
  FileExcelOutlined,
  FileTextOutlined,
} from '@ant-design/icons-vue'

type TimeRangeValue = [Dayjs, Dayjs] | null

interface QuickFilterItem {
  key: string
  label: string
  active: boolean
}

interface FilterConditionItem {
  key: string
  label: string
  checked: boolean
}

interface ActiveFilterCondition {
  label: string
  value: string
}

interface RunningRecord {
  id: string
  registrationNo: string
  serialNo: string
  caseNo: string
  patientName: string
  doctorName: string
  department: string
  auditStatus: string
  isUrgent: boolean
  disabled?: boolean
}

interface PaginationLike {
  current?: number
  pageSize?: number
}

type FilterForm = {
  selectionMode: 'single' | 'multiple' | 'multipleSupported'
  filterName: string
  department?: string
  recordStatus?: string
  gender?: string
  staffType?: string
  hospitalStatus?: string
  dischargeDept?: string
  admissionDept?: string
  dischargeDate?: Dayjs | string
  admissionStartDate?: Dayjs | string
  admissionEndDate?: Dayjs | string
  submitMethod?: string
  scoreContent?: string
  scoreItem?: string
  testCategory?: string
  qcType?: string
  testType?: string
  coreQcCategory?: string
  qcResultType?: string
  comprehensiveName?: string
  scoreValue: string
  testName?: string
}

type FilterFormKey = keyof FilterForm
type ResettableFilterKey = Exclude<FilterFormKey, 'selectionMode' | 'filterName' | 'scoreValue'>
type LabelFilterKey = Exclude<FilterFormKey, 'selectionMode' | 'filterName'>

// 响应式数据
const loading = ref(false)
const exportLoading = ref(false)
const showFilterModal = ref(false)
const showColumnSettings = ref(false)
const currentView = ref('records')
const selectedRowKeys = ref<string[]>([])
const customTimeRange = ref<TimeRangeValue>(null)
const activeTab = ref('defects')

// 查询条件
const queryConditions = reactive({
  timeRange: 'all',
  scoringStandard: 'all',
  searchType: 'registrationNo',
  searchValue: '',
})

// 筛选条件
const activeFilterConditions = ref<ActiveFilterCondition[]>([
  { label: '科室', value: '内科' },
  { label: '状态', value: '待审核' },
])

const filterTemplates = ref([
  { id: 1, name: '今日待审核' },
  { id: 2, name: '本周超时' },
  { id: 3, name: '高风险病历' },
  { id: 4, name: '重点科室' },
])

// 快速筛选标签
const quickFilters = ref<QuickFilterItem[]>([
  { key: 'all', label: '全部', active: true },
  { key: 'pending', label: '待审核缺陷', active: false },
  { key: 'reviewing', label: '核心质控缺陷', active: false },
  { key: 'internal', label: '内涵质控缺陷', active: false },
  { key: 'critical', label: '重点病历缺陷', active: false },
  { key: 'completed', label: '已修正未审核缺陷', active: false },
  { key: 'approved', label: '核查申请未审核缺陷', active: false },
])

// 当前筛选条件
const currentFilterConditions = ref(['核查申请: 行政查房'])

// 多选框筛选条件
const filterConditions = ref<FilterConditionItem[]>([
  { key: 'pending', label: '待审核病历', checked: false },
  { key: 'reviewing', label: '核查申请中', checked: true },
  { key: 'overtime', label: '超时病历', checked: false },
])

// 新建筛选表单数据
const filterForm = reactive<FilterForm>({
  selectionMode: 'single',
  filterName: '',
  department: undefined,
  recordStatus: undefined,
  gender: undefined,
  staffType: undefined,
  hospitalStatus: undefined,
  dischargeDept: undefined,
  admissionDept: undefined,
  dischargeDate: undefined,
  admissionStartDate: undefined,
  admissionEndDate: undefined,
  submitMethod: undefined,
  scoreContent: undefined,
  scoreItem: undefined,
  testCategory: undefined,
  qcType: undefined,
  testType: undefined,
  coreQcCategory: undefined,
  qcResultType: undefined,
  comprehensiveName: undefined,
  scoreValue: '',
  testName: undefined,
})

// 表格数据
const records = ref<RunningRecord[]>([
  {
    id: '1',
    registrationNo: 'R2024001',
    serialNo: 'S2024001',
    caseNo: 'C2024001',
    patientName: '张三',
    doctorName: '李医生',
    department: '内科',
    auditStatus: 'pending',
    isUrgent: false,
  },
])

// 表格列配置
const recordColumns: TableColumnsType<RunningRecord> = [
  { title: '登记号', dataIndex: 'registrationNo', key: 'registrationNo', width: 120 },
  { title: '流水号', dataIndex: 'serialNo', key: 'serialNo', width: 120 },
  { title: '病案号', dataIndex: 'caseNo', key: 'caseNo', width: 120 },
  { title: '患者姓名', dataIndex: 'patientName', key: 'patientName', width: 100 },
  { title: '临床医生', dataIndex: 'doctorName', key: 'doctorName', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
  { title: '审核状态', dataIndex: 'auditStatus', key: 'auditStatus', width: 100 },
  { title: '操作', key: 'action', width: 120, fixed: 'right' as const },
]

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 100,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
})

// 行选择配置
const rowSelection = computed<TableProps['rowSelection']>(() => ({
  selectedRowKeys: selectedRowKeys.value,
  onChange: (keys: Array<string | number>) => {
    selectedRowKeys.value = keys.map((key) => String(key))
  },
  getCheckboxProps: (record: RunningRecord) => ({
    disabled: Boolean(record.disabled),
  }),
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

const handleCustomTimeChange = (dates: TimeRangeValue) => {
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

const handleQuickFilter = ({ key }: MenuInfo) => {
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

const handleQuickFilterClick = (filter: QuickFilterItem) => {
  // 重置所有筛选状态
  quickFilters.value.forEach((f) => (f.active = false))
  // 激活当前筛选
  filter.active = true

  console.log('Quick filter clicked:', filter.key)
  message.info(`应用筛选: ${filter.label}`)

  // 这里可以添加实际的筛选逻辑
  handleQuery()
}

const removeCurrentFilterCondition = (index: number) => {
  currentFilterConditions.value.splice(index, 1)
  message.info('筛选条件已移除')
}

const handleFilterConditionChange = (condition: FilterConditionItem) => {
  console.log('Filter condition changed:', condition.key, condition.checked)
  // 这里可以添加实际的筛选逻辑
}

const handleClearFilters = () => {
  filterConditions.value.forEach((condition) => {
    condition.checked = false
  })
  message.info('筛选条件已清空')
}

// 新建筛选弹窗相关方法
const handleCancel = () => {
  showFilterModal.value = false
}

const handleReset = () => {
  // 重置表单数据
  ;(Object.keys(filterForm) as FilterFormKey[]).forEach((key) => {
    if (key === 'selectionMode') {
      filterForm.selectionMode = 'single'
    } else if (key === 'filterName') {
      filterForm.filterName = ''
    } else if (key === 'scoreValue') {
      filterForm.scoreValue = ''
    } else {
      filterForm[key as ResettableFilterKey] = undefined
    }
  })
  message.info('表单已清空')
}

const handleConfirm = () => {
  // 验证必填字段
  if (!filterForm.filterName.trim()) {
    message.error('请输入筛选条件名称')
    return
  }

  // 收集已选择的筛选条件
  const selectedConditions: Array<{ key: string; value: unknown; label: string }> = []
  ;(Object.keys(filterForm) as FilterFormKey[]).forEach((key) => {
    const value = filterForm[key]
    if (value !== undefined && value !== '' && key !== 'selectionMode' && key !== 'filterName') {
      selectedConditions.push({
        key,
        value,
        label: getFieldLabel(key),
      })
    }
  })

  if (selectedConditions.length === 0) {
    message.error('请至少选择一个筛选条件')
    return
  }

  // 应用筛选条件
  console.log('应用筛选条件:', {
    name: filterForm.filterName,
    mode: filterForm.selectionMode,
    conditions: selectedConditions,
  })

  message.success(`筛选条件"${filterForm.filterName}"已创建`)
  showFilterModal.value = false
}

// 获取字段标签
const getFieldLabel = (key: string) => {
  const labelMap: Record<LabelFilterKey, string> = {
    department: '病历科室',
    recordStatus: '病历状态',
    gender: '患者性别',
    staffType: '人员类型',
    hospitalStatus: '在院状态',
    dischargeDept: '出院科室',
    admissionDept: '入院科室',
    dischargeDate: '出院时间',
    admissionStartDate: '入院开始时间',
    admissionEndDate: '入院结束时间',
    submitMethod: '提交方式',
    scoreContent: '评分内容',
    scoreItem: '评分项目',
    testCategory: '检验大类',
    qcType: '质控类型',
    testType: '检验类型',
    coreQcCategory: '核心质控分类',
    qcResultType: '质控结果类型',
    comprehensiveName: '综合名称',
    scoreValue: '分值',
    testName: '检验名称',
  }
  return key in labelMap ? labelMap[key as LabelFilterKey] : key
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

const handleTableChange = (pag: PaginationLike, filters: unknown, sorter: unknown) => {
  void filters
  void sorter
  pagination.current = pag.current ?? pagination.current
  pagination.pageSize = pag.pageSize ?? pagination.pageSize
  handleQuery()
}

const handleViewDetail = (record: RunningRecord) => {
  console.log('View detail:', record)
  message.info('查看详情')
}

const handleUrgeRecord = (record: RunningRecord) => {
  console.log('Urge record:', record)
  message.info('催办成功')
}

const getAuditStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    approved: 'green',
    rejected: 'red',
    reviewing: 'blue',
  }
  return colorMap[status] || 'default'
}

const getAuditStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝',
    reviewing: '审核中',
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

/* 内容区域样式 */
.content-container {
  padding: 0;
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

.query-section .flex {
  align-items: flex-end;
}

.query-section .query-item.flex-shrink-0 {
  min-width: 160px;
}

.query-section .w-80 {
  width: 320px;
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

/* 缺陷筛选区域 */
.defect-filter-section {
  background: white;
}

.defect-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0;
}

.defect-tabs :deep(.ant-tabs-tab) {
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #666666;
}

.defect-tabs :deep(.ant-tabs-tab-active) {
  color: #2b6cf6;
  font-weight: 600;
}

.defect-tabs :deep(.ant-tabs-ink-bar) {
  background: #2b6cf6;
}

/* 快速筛选标签样式 */
.defect-filter-section :deep(.ant-tag) {
  margin: 0 4px 4px 0;
  padding: 4px 12px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

/* 非激活状态的快速筛选标签 */
.defect-filter-section :deep(.ant-tag:not(.ant-tag-blue)) {
  background: #f5f5f5;
  color: #666666;
  border-color: #d9d9d9;
}

/* 激活状态的快速筛选标签 */
.defect-filter-section :deep(.ant-tag-blue) {
  background: #2b6cf6;
  color: #ffffff;
  border-color: #2b6cf6;
}

/* 悬停状态的快速筛选标签 */
.defect-filter-section :deep(.ant-tag:not(.ant-tag-blue):hover) {
  background: #e6f7ff;
  color: #2b6cf6;
  border-color: #91d5ff;
}

.defect-filter-section :deep(.ant-tag-blue:hover) {
  background: #40a9ff;
  border-color: #40a9ff;
}

/* 快速筛选标签专用样式 */
.quick-filter-tag {
  margin: 0 2px 4px 0 !important;
  padding: 4px 12px !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  border-radius: 4px !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  border: 1px solid transparent !important;
  line-height: 1.4 !important;
}

/* 非激活状态 */
.quick-filter-tag:not(.ant-tag-blue) {
  background: #f5f5f5 !important;
  color: #666666 !important;
  border-color: #d9d9d9 !important;
}

/* 激活状态 */
.quick-filter-tag.ant-tag-blue {
  background: #2b6cf6 !important;
  color: #ffffff !important;
  border-color: #2b6cf6 !important;
}

/* 悬停状态 */
.quick-filter-tag:not(.ant-tag-blue):hover {
  background: #e6f7ff !important;
  color: #2b6cf6 !important;
  border-color: #91d5ff !important;
}

.quick-filter-tag.ant-tag-blue:hover {
  background: #40a9ff !important;
  border-color: #40a9ff !important;
}

/* 紧凑版快速筛选标签样式 */
.quick-filter-tag-compact {
  margin: 0 1px 2px 0 !important;
  padding: 2px 8px !important;
  font-size: 12px !important;
  font-weight: 500 !important;
  border-radius: 3px !important;
  cursor: pointer !important;
  transition: all 0.2s ease !important;
  border: 1px solid transparent !important;
  line-height: 1.3 !important;
  height: 22px !important;
}

/* 非激活状态 */
.quick-filter-tag-compact:not(.ant-tag-blue) {
  background: #f5f5f5 !important;
  color: #666666 !important;
  border-color: #d9d9d9 !important;
}

/* 激活状态 */
.quick-filter-tag-compact.ant-tag-blue {
  background: #2b6cf6 !important;
  color: #ffffff !important;
  border-color: #2b6cf6 !important;
}

/* 悬停状态 */
.quick-filter-tag-compact:not(.ant-tag-blue):hover {
  background: #e6f7ff !important;
  color: #2b6cf6 !important;
  border-color: #91d5ff !important;
}

.quick-filter-tag-compact.ant-tag-blue:hover {
  background: #40a9ff !important;
  border-color: #40a9ff !important;
}

/* 多选框筛选条件样式 */
.filter-checkbox {
  font-size: 13px !important;
  font-weight: 400 !important;
}

.filter-checkbox :deep(.ant-checkbox) {
  margin-right: 6px;
}

.filter-checkbox :deep(.ant-checkbox-wrapper) {
  color: #666666;
  font-size: 13px;
  line-height: 1.4;
}

.filter-checkbox :deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #2b6cf6;
  border-color: #2b6cf6;
}

.filter-checkbox :deep(.ant-checkbox-wrapper:hover .ant-checkbox-inner) {
  border-color: #2b6cf6;
}

/* 筛选操作按钮样式 */
.filter-action-btn {
  height: 28px !important;
  padding: 0 12px !important;
  font-size: 12px !important;
  border-radius: 4px !important;
  font-weight: 500 !important;
}

.filter-action-btn.ant-btn-primary {
  background: #2b6cf6 !important;
  border-color: #2b6cf6 !important;
  box-shadow: 0 2px 4px rgba(43, 108, 246, 0.15) !important;
}

.filter-action-btn.ant-btn-primary:hover {
  background: #40a9ff !important;
  border-color: #40a9ff !important;
}

.filter-action-btn:not(.ant-btn-primary) {
  background: #ffffff !important;
  border-color: #d9d9d9 !important;
  color: #666666 !important;
}

.filter-action-btn:not(.ant-btn-primary):hover {
  border-color: #2b6cf6 !important;
  color: #2b6cf6 !important;
}

/* 新建筛选弹窗样式 */
.filter-modal :deep(.ant-modal-content) {
  padding: 0;
}

.filter-modal :deep(.ant-modal-header) {
  padding: 16px 24px;
  border-bottom: 1px solid #f0f0f0;
}

.filter-modal :deep(.ant-modal-body) {
  padding: 0;
  max-height: 70vh;
  overflow-y: auto;
}

.filter-form-container {
  padding: 24px;
}

.filter-section {
  border-left: 3px solid #2b6cf6;
  padding-left: 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #2b6cf6;
  margin: 0 0 16px 0;
}

.form-row {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.form-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  color: #666666;
  white-space: nowrap;
  min-width: 120px;
}

.filter-name-input {
  width: 200px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.filter-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: #666666;
  font-weight: 500;
}

.filter-select,
.filter-date {
  width: 100%;
}

.date-range-row {
  margin-top: 16px;
}

.filter-date-range {
  width: 140px;
}

.date-separator {
  font-size: 13px;
  color: #666666;
  margin: 0 8px;
}

.comprehensive-select {
  width: 150px;
}

.score-input {
  width: 100px;
}

.test-name-select {
  width: 150px;
}

.form-separator {
  font-size: 13px;
  color: #666666;
  margin: 0 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 24px;
  border-top: 1px solid #f0f0f0;
  margin-top: 24px;
}

.cancel-btn,
.reset-btn {
  padding: 0 16px;
  height: 32px;
  font-size: 13px;
}

.confirm-btn {
  padding: 0 24px;
  height: 32px;
  font-size: 13px;
  background: #2b6cf6;
  border-color: #2b6cf6;
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
    padding: 0;
  }

  .query-section .flex {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }

  .query-section .query-item {
    flex: none;
    width: 100%;
  }

  .query-section .w-40 {
    width: 100%;
  }

  .query-section .w-64 {
    width: 100%;
  }

  .query-section .w-80 {
    width: 100%;
  }

  .query-section :deep(.ant-input-group.w-40),
  .query-section :deep(.ant-input-group.w-80) {
    width: 100%;
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

  .defect-filter-section .flex {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .defect-filter-section .flex:has(.filter-checkbox) {
    flex-direction: column;
    align-items: stretch;
  }

  .defect-filter-section .flex:has(.filter-checkbox) .ml-auto {
    margin-left: 0 !important;
    margin-top: 12px;
  }

  .defect-tabs :deep(.ant-tabs-tab) {
    padding: 6px 12px;
    font-size: 13px;
  }

  .quick-filter-tag {
    margin: 0 1px 3px 0 !important;
    padding: 3px 8px !important;
    font-size: 12px !important;
  }

  .quick-filter-tag-compact {
    margin: 0 1px 2px 0 !important;
    padding: 1px 6px !important;
    font-size: 11px !important;
    height: 20px !important;
  }

  /* 新建筛选弹窗移动端适配 */
  .filter-modal :deep(.ant-modal) {
    width: 95% !important;
    max-width: 95% !important;
  }

  .filter-grid {
    grid-template-columns: 1fr !important;
    gap: 12px !important;
  }

  .form-row {
    flex-direction: column !important;
    align-items: flex-start !important;
    gap: 8px !important;
  }

  .form-label {
    min-width: auto !important;
  }

  .filter-name-input {
    width: 100% !important;
  }

  .date-range-row .filter-item {
    flex-direction: column !important;
    align-items: flex-start !important;
  }

  .filter-date-range {
    width: 100% !important;
  }

  .comprehensive-select,
  .score-input,
  .test-name-select {
    width: 100% !important;
  }

  .modal-footer {
    flex-direction: column !important;
    gap: 8px !important;
  }

  .cancel-btn,
  .reset-btn,
  .confirm-btn {
    width: 100% !important;
  }

  .filter-checkbox {
    font-size: 12px !important;
    margin-bottom: 8px;
  }

  .filter-action-btn {
    height: 26px !important;
    padding: 0 10px !important;
    font-size: 11px !important;
  }
}

@media (max-width: 768px) {
  .content-container {
    padding: 0;
  }

  .query-section,
  .filter-section,
  .action-section,
  .defect-filter-section {
    padding: 16px;
  }
}
</style>
