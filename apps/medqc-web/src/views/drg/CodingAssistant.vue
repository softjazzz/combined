<template>
  <div class="coding-assistant">
    <a-page-header
      title="编码辅助"
      sub-title="ICD 编码推荐和校验"
      @back="() => $router.back()"
      class="page-header"
    >
      <template #extra>
        <a-button type="primary" @click="refreshList" class="refresh-btn">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <!-- 筛选条件 -->
      <div class="filter-bar">
        <a-form layout="inline" class="filter-form">
          <a-form-item label="编码状态">
            <a-select
              v-model:value="filters.codingStatus"
              style="width: 140px"
              placeholder="全部"
              allowClear
              @change="handleFilterChange"
            >
              <a-select-option value="">全部</a-select-option>
              <a-select-option value="draft">草稿</a-select-option>
              <a-select-option value="completed">已完成</a-select-option>
              <a-select-option value="reviewed">已审核</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="审核状态">
            <a-select
              v-model:value="filters.reviewStatus"
              style="width: 140px"
              placeholder="全部"
              allowClear
              @change="handleFilterChange"
            >
              <a-select-option value="">全部</a-select-option>
              <a-select-option value="pending">待审核</a-select-option>
              <a-select-option value="approved">已通过</a-select-option>
              <a-select-option value="rejected">已拒绝</a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item label="患者姓名">
            <a-input
              v-model:value="filters.patientName"
              placeholder="输入患者姓名"
              style="width: 140px"
              allowClear
              @change="handleFilterChange"
            />
          </a-form-item>

          <a-form-item label="住院号">
            <a-input
              v-model:value="filters.admissionId"
              placeholder="输入住院号"
              style="width: 160px"
              allowClear
              @change="handleFilterChange"
            />
          </a-form-item>
        </a-form>
      </div>

      <!-- 病案列表 -->
      <div class="table-card">
        <TableSkeleton v-if="loading" :rows="10" :columns="8" />
        <a-table
          v-else
          :columns="columns"
          :data-source="dataSource"
          :pagination="pagination"
          :scroll="{ x: 1200 }"
          @change="handleTableChange"
          row-key="front_page_id"
          class="premium-table"
        >
          <template #bodyCell="{ column, record }">
            <!-- 患者信息 -->
            <template v-if="column.dataIndex === 'patient'">
              <div class="patient-cell">
                <div class="patient-name">{{ record.patient_name }}</div>
                <div class="patient-meta">
                  {{ getGenderText(record.patient_gender) }} / {{ record.patient_age }}岁
                </div>
              </div>
            </template>

            <!-- 主诊断 -->
            <template v-else-if="column.dataIndex === 'diagnosis'">
              <div class="diagnosis-cell">
                <a-tag color="blue" class="code-tag">{{ record.primary_diagnosis_code }}</a-tag>
                <div class="diagnosis-name">{{ record.primary_diagnosis_name }}</div>
              </div>
            </template>

            <!-- 住院天数 -->
            <template v-else-if="column.dataIndex === 'total_hospital_days'">
              <span class="days-text">{{ record.total_hospital_days ? `${record.total_hospital_days}天` : '-' }}</span>
            </template>

            <!-- 编码状态 -->
            <template v-else-if="column.dataIndex === 'coding_status'">
              <StatusTag type="coding" :value="record.coding_status" />
            </template>

            <!-- 审核状态 -->
            <template v-else-if="column.dataIndex === 'review_status'">
              <StatusTag type="review" :value="record.review_status" />
            </template>

            <!-- 编码员 -->
            <template v-else-if="column.dataIndex === 'coder_id'">
              <span class="coder-text">{{ record.coder_id || '-' }}</span>
            </template>

            <!-- 操作 -->
            <template v-else-if="column.key === 'action'">
              <a-space size="small">
                <a-button type="link" size="small" class="action-link" @click="goToDetail(record.admission_id)">
                  <EditOutlined /> 编码
                </a-button>
                <a-button type="link" size="small" class="action-link review-link" v-if="record.coding_status === 'completed'">
                  <CheckCircleOutlined /> 审核
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined, EditOutlined, CheckCircleOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import TableSkeleton from '@/components/common/TableSkeleton.vue'
import { getGenderText } from '@/utils/drg'
import type { CaseFrontPage } from '@/types/drg'
import type { TableProps } from 'ant-design-vue'

const router = useRouter()

/** 表格列定义 - Updated to remove deprecated slots */
const columns = [
  {
    title: '住院号',
    dataIndex: 'admission_id',
    width: 150,
    fixed: 'left'
  },
  {
    title: '患者信息',
    dataIndex: 'patient',
    width: 140
  },
  {
    title: '主诊断',
    dataIndex: 'diagnosis',
    width: 280
  },
  {
    title: '住院天数',
    dataIndex: 'total_hospital_days',
    width: 90,
    align: 'center'
  },
  {
    title: '编码状态',
    dataIndex: 'coding_status',
    width: 100,
    align: 'center'
  },
  {
    title: '审核状态',
    dataIndex: 'review_status',
    width: 100,
    align: 'center'
  },
  {
    title: '编码员',
    dataIndex: 'coder_id',
    width: 100
  },
  {
    title: '操作',
    key: 'action',
    width: 140,
    fixed: 'right'
  }
]

/** 筛选条件 */
const filters = reactive({
  codingStatus: '',
  reviewStatus: '',
  patientName: '',
  admissionId: ''
})

/** 表格数据 */
const dataSource = ref<CaseFrontPage[]>([])
const loading = ref(false)

/** 分页配置 */
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showTotal: (total: number) => `共 ${total} 条`
})

/** 加载病案列表 */
const loadCaseFrontPages = async () => {
  loading.value = true
  try {
    const response = await drgApi.getCaseFrontPages()

    // 应用筛选
    let filteredData = response

    if (filters.codingStatus) {
      filteredData = filteredData.filter(item => item.coding_status === filters.codingStatus)
    }
    if (filters.reviewStatus) {
      filteredData = filteredData.filter(item => item.review_status === filters.reviewStatus)
    }
    if (filters.patientName) {
      filteredData = filteredData.filter(item =>
        item.patient_name.includes(filters.patientName)
      )
    }
    if (filters.admissionId) {
      filteredData = filteredData.filter(item =>
        item.admission_id.includes(filters.admissionId)
      )
    }

    dataSource.value = filteredData
    pagination.total = filteredData.length
  } catch (error) {
    console.error('加载病案列表失败:', error)
    message.error('加载病案列表失败')
  } finally {
    loading.value = false
  }
}

/** 刷新列表 */
const refreshList = () => {
  loadCaseFrontPages()
}

/** 筛选条件变化 */
const handleFilterChange = () => {
  pagination.current = 1
  loadCaseFrontPages()
}

/** 表格变化 */
const handleTableChange: TableProps['onChange'] = (pag) => {
  pagination.current = pag.current || 1
  pagination.pageSize = pag.pageSize || 10
  loadCaseFrontPages()
}

/** 跳转到编码详情页 */
const goToDetail = (admissionId: string) => {
  router.push(`/dashboard/drg/coding/${admissionId}`)
}

onMounted(() => {
  loadCaseFrontPages()
})
</script>

<style scoped lang="scss">
.coding-assistant {
  min-height: 100vh;
  background-color: #f1f5f9;
}

.page-header {
  background: #fff;
  padding: 16px 32px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  
  :deep(.ant-page-header-heading-title) {
    font-weight: 700;
    font-size: 18px;
    color: #1e293b;
  }
  
  :deep(.ant-page-header-heading-sub-title) {
    color: #64748b;
    font-size: 13px;
  }
  
  .refresh-btn {
    border-radius: 6px;
    font-weight: 500;
  }
}

.content-wrapper {
  padding: 24px 32px;
}

.filter-bar {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
  
  .filter-form {
    :deep(.ant-form-item) {
      margin-bottom: 0;
      margin-right: 24px;
    }
    
    :deep(.ant-form-item-label > label) {
      color: #64748b;
      font-size: 13px;
    }
    
    :deep(.ant-select-selector),
    :deep(.ant-input) {
      border-radius: 6px;
      border-color: #e2e8f0;
      
      &:hover, &:focus {
        border-color: #6366f1;
      }
    }
  }
}

.table-card {
  background: #fff;
  border-radius: 8px;
  padding: 0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.premium-table {
  :deep(.ant-table) {
    font-size: 13px;
  }
  
  :deep(.ant-table-thead > tr > th) {
    background: #f8fafc;
    font-weight: 600;
    color: #334155;
    border-bottom: 1px solid #e2e8f0;
    padding: 14px 16px;
    font-size: 13px;
  }
  
  :deep(.ant-table-tbody > tr > td) {
    padding: 14px 16px;
    border-bottom: 1px solid #f1f5f9;
  }
  
  :deep(.ant-table-tbody > tr:hover > td) {
    background: #f8fafc;
  }
  
  :deep(.ant-table-tbody > tr:last-child > td) {
    border-bottom: none;
  }
  
  // Fixed columns styling
  :deep(.ant-table-cell-fix-left),
  :deep(.ant-table-cell-fix-right) {
    background: #fff;
  }
  
  :deep(.ant-table-tbody > tr:hover .ant-table-cell-fix-left),
  :deep(.ant-table-tbody > tr:hover .ant-table-cell-fix-right) {
    background: #f8fafc;
  }
}

/* Cell Styles */
.patient-cell {
  .patient-name {
    font-weight: 600;
    color: #0f172a;
    font-size: 14px;
  }
  
  .patient-meta {
    color: #94a3b8;
    font-size: 12px;
    margin-top: 2px;
  }
}

.diagnosis-cell {
  .code-tag {
    font-weight: 600;
    border-radius: 4px;
    font-size: 12px;
  }
  
  .diagnosis-name {
    margin-top: 4px;
    color: #475569;
    font-size: 13px;
    line-height: 1.4;
  }
}

.days-text {
  color: #0f172a;
  font-weight: 500;
}

.coder-text {
  color: #64748b;
}

.action-link {
  color: #6366f1;
  font-weight: 500;
  font-size: 12px;
  padding: 0 4px;
  
  &:hover {
    color: #4f46e5;
  }
  
  :deep(.anticon) {
    margin-right: 4px;
  }
}

.review-link {
  color: #10b981;
  
  &:hover {
    color: #059669;
  }
}
</style>
