<template>
  <div class="medical-record-list">
    <!-- 搜索和筛选栏 -->
    <div class="mb-6 p-4 rounded-xl bg-white shadow-sm border border-gray-200">
      <div class="flex flex-col lg:flex-row gap-4">
        <!-- 搜索框 -->
        <div class="flex-1">
          <a-input-search
            v-model:value="searchParams.keyword"
            placeholder="搜索患者姓名、科室或诊断..."
            size="large"
            @search="handleSearch"
            class="search-input"
          >
            <template #prefix>
              <SearchOutlined class="text-gray-400" />
            </template>
          </a-input-search>
        </div>

        <!-- 筛选器 -->
        <div class="flex gap-3 flex-wrap">
          <!-- 科室筛选 -->
          <a-select
            v-model:value="searchParams.department"
            placeholder="选择科室"
            size="large"
            style="width: 150px"
            allow-clear
            @change="handleFilterChange"
          >
            <a-select-option 
              v-for="dept in DEPARTMENTS" 
              :key="dept" 
              :value="dept"
            >
              {{ dept }}
            </a-select-option>
          </a-select>

          <!-- 状态筛选 -->
          <a-select
            v-model:value="searchParams.status"
            placeholder="审核状态"
            size="large"
            style="width: 120px"
            allow-clear
            @change="handleFilterChange"
          >
            <a-select-option 
              v-for="status in STATUS_OPTIONS" 
              :key="status.value" 
              :value="status.value"
            >
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: status.color }"></div>
                {{ status.label }}
              </div>
            </a-select-option>
          </a-select>

          <!-- 医保类型筛选 -->
          <a-select
            v-model:value="searchParams.insurance_type"
            placeholder="医保类型"
            size="large"
            style="width: 120px"
            allow-clear
            @change="handleFilterChange"
          >
            <a-select-option 
              v-for="type in INSURANCE_TYPES" 
              :key="type.value" 
              :value="type.value"
            >
              {{ type.label }}
            </a-select-option>
          </a-select>

          <!-- 违规风险筛选 -->
          <a-select
            v-model:value="searchParams.violation_risk"
            placeholder="违规风险"
            size="large"
            style="width: 120px"
            allow-clear
            @change="handleFilterChange"
          >
            <a-select-option 
              v-for="risk in VIOLATION_RISK_OPTIONS" 
              :key="risk.value" 
              :value="risk.value"
            >
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: risk.color }"></div>
                {{ risk.label }}
              </div>
            </a-select-option>
          </a-select>

          <!-- 刷新按钮 -->
          <a-button 
            size="large" 
            @click="handleRefresh"
            :loading="loading"
          >
            <ReloadOutlined />
          </a-button>
        </div>
      </div>
    </div>

    <!-- 批量操作栏 -->
    <div v-if="selectedRowKeys.length > 0" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <div class="flex items-center justify-between">
        <span class="text-blue-700">已选择 {{ selectedRowKeys.length }} 条记录</span>
        <div class="flex gap-2">
          <a-button size="small" @click="handleBatchApprove" :loading="batchLoading">
            批量通过
          </a-button>
          <a-button size="small" @click="handleBatchReject" :loading="batchLoading">
            批量拒绝
          </a-button>
          <a-button size="small" @click="selectedRowKeys = []">
            取消选择
          </a-button>
        </div>
      </div>
    </div>

    <!-- 数据表格 -->
    <a-table
      :columns="columns"
      :data-source="records"
      :loading="loading"
      :pagination="paginationConfig"
      :row-selection="{ selectedRowKeys, onChange: onSelectChange }"
      row-key="id"
      @change="handleTableChange"
      class="medical-record-table"
    >
      <!-- 患者信息列 -->
      <template #patient="{ record }">
        <div>
          <div class="font-medium text-gray-900">{{ record.patient_name }}</div>
          <div class="text-sm text-gray-500">{{ record.patient_age }}岁 {{ record.patient_gender === 'M' ? '男' : '女' }}</div>
          <div class="text-xs text-gray-400">{{ record.insurance_number }}</div>
        </div>
      </template>

      <!-- 状态列 -->
      <template #status="{ record }">
        <a-tag :color="getStatusColor(record.status)">
          {{ getStatusLabel(record.status) }}
        </a-tag>
      </template>

      <!-- 违规风险列 -->
      <template #violation_risk="{ record }">
        <a-tag :color="getViolationRiskColor(record.violation_risk)">
          {{ getViolationRiskLabel(record.violation_risk) }}
        </a-tag>
      </template>

      <!-- 费用信息列 -->
      <template #cost="{ record }">
        <div>
          <div class="text-sm">总费用: ¥{{ record.total_cost.toLocaleString() }}</div>
          <div class="text-xs text-gray-500">医保: ¥{{ record.insurance_cost.toLocaleString() }}</div>
          <div class="text-xs text-gray-500">自费: ¥{{ record.self_pay_cost.toLocaleString() }}</div>
        </div>
      </template>

      <!-- 操作列 -->
      <template #action="{ record }">
        <div class="flex gap-2">
          <a-button size="small" @click="handleView(record)">
            查看
          </a-button>
          <a-button size="small" @click="handleEdit(record)">
            编辑
          </a-button>
          <a-dropdown>
            <a-button size="small">
              更多 <DownOutlined />
            </a-button>
            <template #overlay>
              <a-menu>
                <a-menu-item @click="handleApprove(record)">
                  <CheckOutlined /> 通过
                </a-menu-item>
                <a-menu-item @click="handleReject(record)">
                  <CloseOutlined /> 拒绝
                </a-menu-item>
                <a-menu-item @click="handleDelete(record)" danger>
                  <DeleteOutlined /> 删除
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { 
  SearchOutlined, 
  ReloadOutlined, 
  DownOutlined,
  CheckOutlined,
  CloseOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import type { 
  MedicalRecord, 
  SearchParams,
  PaginationParams
} from '@/types/medical-records'
import { 
  DEPARTMENTS, 
  STATUS_OPTIONS, 
  INSURANCE_TYPES, 
  VIOLATION_RISK_OPTIONS 
} from '@/types/medical-records'
import { 
  getMedicalRecords, 
  updateMedicalRecord, 
  deleteMedicalRecord,
  batchReviewRecords
} from '@/api/medical-records'

// Props
interface Props {
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  height: 600
})

// Emits
const emit = defineEmits<{
  view: [record: MedicalRecord]
  edit: [record: MedicalRecord]
}>()

// 响应式数据
const loading = ref(false)
const batchLoading = ref(false)
const records = ref<MedicalRecord[]>([])
const selectedRowKeys = ref<string[]>([])

const searchParams = reactive<SearchParams>({
  keyword: '',
  status: undefined,
  department: undefined,
  insurance_type: undefined,
  violation_risk: undefined
})

const pagination = reactive<PaginationParams>({
  page: 1,
  pageSize: 10,
  total: 0
})

// 表格列配置
const columns: TableColumnsType = [
  {
    title: '患者信息',
    key: 'patient',
    width: 200,
    slots: { customRender: 'patient' }
  },
  {
    title: '科室',
    dataIndex: 'department',
    width: 100
  },
  {
    title: '医保类型',
    dataIndex: 'insurance_type',
    width: 100,
    customRender: ({ record }) => {
      const type = INSURANCE_TYPES.find(t => t.value === record.insurance_type)
      return type?.label || record.insurance_type
    }
  },
  {
    title: '主要诊断',
    dataIndex: 'diagnosis_primary',
    width: 150
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    slots: { customRender: 'status' }
  },
  {
    title: '违规风险',
    key: 'violation_risk',
    width: 100,
    slots: { customRender: 'violation_risk' }
  },
  {
    title: '费用信息',
    key: 'cost',
    width: 150,
    slots: { customRender: 'cost' }
  },
  {
    title: '入院日期',
    dataIndex: 'admission_date',
    width: 100
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    fixed: 'right',
    slots: { customRender: 'action' }
  }
]

// 分页配置
const paginationConfig = computed(() => ({
  current: pagination.page,
  pageSize: pagination.pageSize,
  total: pagination.total,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) => 
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
}))

// 工具函数
function getStatusColor(status: string) {
  const option = STATUS_OPTIONS.find(s => s.value === status)
  return option?.color || '#666'
}

function getStatusLabel(status: string) {
  const option = STATUS_OPTIONS.find(s => s.value === status)
  return option?.label || status
}

function getViolationRiskColor(risk: string) {
  const option = VIOLATION_RISK_OPTIONS.find(r => r.value === risk)
  return option?.color || '#666'
}

function getViolationRiskLabel(risk: string) {
  const option = VIOLATION_RISK_OPTIONS.find(r => r.value === risk)
  return option?.label || risk
}

// 事件处理
async function loadRecords() {
  loading.value = true
  try {
    const { data, total } = await getMedicalRecords(searchParams, pagination)
    records.value = data
    pagination.total = total
  } catch (error) {
    message.error('加载数据失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadRecords()
}

function handleFilterChange() {
  pagination.page = 1
  loadRecords()
}

function handleRefresh() {
  loadRecords()
}

function handleTableChange(pag: any) {
  pagination.page = pag.current
  pagination.pageSize = pag.pageSize
  loadRecords()
}

function onSelectChange(keys: string[]) {
  selectedRowKeys.value = keys
}

function handleView(record: MedicalRecord) {
  emit('view', record)
}

function handleEdit(record: MedicalRecord) {
  emit('edit', record)
}

async function handleApprove(record: MedicalRecord) {
  try {
    await updateMedicalRecord(record.id, { status: 'approved' })
    message.success('审核通过')
    loadRecords()
  } catch (error) {
    message.error('操作失败')
  }
}

async function handleReject(record: MedicalRecord) {
  try {
    await updateMedicalRecord(record.id, { status: 'rejected' })
    message.success('审核拒绝')
    loadRecords()
  } catch (error) {
    message.error('操作失败')
  }
}

async function handleDelete(record: MedicalRecord) {
  try {
    await deleteMedicalRecord(record.id)
    message.success('删除成功')
    loadRecords()
  } catch (error) {
    message.error('删除失败')
  }
}

async function handleBatchApprove() {
  batchLoading.value = true
  try {
    await batchReviewRecords(selectedRowKeys.value, 'approved')
    message.success('批量审核通过')
    selectedRowKeys.value = []
    loadRecords()
  } catch (error) {
    message.error('批量操作失败')
  } finally {
    batchLoading.value = false
  }
}

async function handleBatchReject() {
  batchLoading.value = true
  try {
    await batchReviewRecords(selectedRowKeys.value, 'rejected')
    message.success('批量审核拒绝')
    selectedRowKeys.value = []
    loadRecords()
  } catch (error) {
    message.error('批量操作失败')
  } finally {
    batchLoading.value = false
  }
}

// 生命周期
onMounted(() => {
  loadRecords()
})

// 暴露方法
defineExpose({
  refresh: loadRecords
})
</script>

<style scoped>
.medical-record-table :deep(.ant-table-thead > tr > th) {
  background-color: #fafafa;
  font-weight: 600;
}

.search-input :deep(.ant-input-search-button) {
  background-color: #1890ff;
  border-color: #1890ff;
}
</style>
