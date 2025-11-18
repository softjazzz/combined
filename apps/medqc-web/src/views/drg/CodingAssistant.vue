<template>
  <div class="coding-assistant">
    <a-page-header
      title="编码辅助"
      sub-title="ICD 编码推荐和校验"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-button type="primary" @click="refreshList">
          <template #icon><ReloadOutlined /></template>
          刷新
        </a-button>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <!-- 筛选条件 -->
      <a-card class="filter-card" :bordered="false">
        <a-form layout="inline">
          <a-form-item label="编码状态">
            <a-select
              v-model:value="filters.codingStatus"
              style="width: 150px"
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
              style="width: 150px"
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
              style="width: 150px"
              allowClear
              @change="handleFilterChange"
            />
          </a-form-item>

          <a-form-item label="住院号">
            <a-input
              v-model:value="filters.admissionId"
              placeholder="输入住院号"
              style="width: 180px"
              allowClear
              @change="handleFilterChange"
            />
          </a-form-item>
        </a-form>
      </a-card>

      <!-- 病案列表 -->
      <a-card :bordered="false" style="margin-top: 16px">
        <a-table
          :columns="columns"
          :data-source="dataSource"
          :loading="loading"
          :pagination="pagination"
          @change="handleTableChange"
          row-key="front_page_id"
        >
          <!-- 患者信息 -->
          <template #patient="{ record }">
            <div>
              <div><strong>{{ record.patient_name }}</strong></div>
              <div style="color: #999; font-size: 12px">
                {{ getGenderText(record.patient_gender) }} / {{ record.patient_age }}岁
              </div>
            </div>
          </template>

          <!-- 主诊断 -->
          <template #diagnosis="{ record }">
            <div>
              <a-tag color="blue">{{ record.primary_diagnosis_code }}</a-tag>
              <div style="margin-top: 4px">{{ record.primary_diagnosis_name }}</div>
            </div>
          </template>

          <!-- 编码状态 -->
          <template #codingStatus="{ record }">
            <StatusTag type="coding" :value="record.coding_status" />
          </template>

          <!-- 审核状态 -->
          <template #reviewStatus="{ record }">
            <StatusTag type="review" :value="record.review_status" />
          </template>

          <!-- 操作 -->
          <template #action="{ record }">
            <a-space>
              <a-button type="link" size="small" @click="goToDetail(record.admission_id)">
                编码
              </a-button>
              <a-button type="link" size="small" v-if="record.coding_status === 'completed'">
                审核
              </a-button>
            </a-space>
          </template>
        </a-table>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import { getGenderText } from '@/utils/drg'
import type { CaseFrontPage } from '@/types/drg'
import type { TableProps } from 'ant-design-vue'

const router = useRouter()

/** 表格列定义 */
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
    width: 150,
    slots: { customRender: 'patient' }
  },
  {
    title: '主诊断',
    dataIndex: 'diagnosis',
    width: 250,
    slots: { customRender: 'diagnosis' }
  },
  {
    title: '住院天数',
    dataIndex: 'total_hospital_days',
    width: 100,
    customRender: ({ text }: any) => text ? `${text}天` : '-'
  },
  {
    title: '编码状态',
    dataIndex: 'coding_status',
    width: 100,
    slots: { customRender: 'codingStatus' }
  },
  {
    title: '审核状态',
    dataIndex: 'review_status',
    width: 100,
    slots: { customRender: 'reviewStatus' }
  },
  {
    title: '编码员',
    dataIndex: 'coder_id',
    width: 120,
    customRender: ({ text }: any) => text || '-'
  },
  {
    title: '操作',
    key: 'action',
    width: 150,
    fixed: 'right',
    slots: { customRender: 'action' }
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
  .content-wrapper {
    padding: 16px;
  }

  .filter-card {
    :deep(.ant-card-body) {
      padding: 16px;
    }
  }
}
</style>
