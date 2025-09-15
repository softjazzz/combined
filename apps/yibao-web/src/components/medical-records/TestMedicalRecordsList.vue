<template>
  <div class="test-medical-records-list">
    <!-- 搜索和筛选区域 -->
    <div class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-4">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索病历名称、患者姓名..."
          style="width: 300px"
          @search="handleSearch"
        />
        <a-select
          v-model:value="statusFilter"
          placeholder="状态筛选"
          style="width: 120px"
          @change="handleFilterChange"
        >
          <a-select-option value="">全部状态</a-select-option>
          <a-select-option value="draft">草稿</a-select-option>
          <a-select-option value="pending">待审核</a-select-option>
          <a-select-option value="analyzing">分析中</a-select-option>
          <a-select-option value="completed">已完成</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
        <a-select
          v-model:value="departmentFilter"
          placeholder="科室筛选"
          style="width: 120px"
          @change="handleFilterChange"
        >
          <a-select-option value="">全部科室</a-select-option>
          <a-select-option value="内科">内科</a-select-option>
          <a-select-option value="外科">外科</a-select-option>
          <a-select-option value="外二科">外二科</a-select-option>
          <a-select-option value="儿科">儿科</a-select-option>
        </a-select>
      </div>
      <div class="text-sm text-gray-500">
        共 {{ filteredRecords.length }} 条记录
      </div>
    </div>

    <!-- 病历列表 -->
    <div class="space-y-3">
      <div v-if="loading" class="text-center py-8">
        <a-spin size="large" />
        <p class="text-gray-500 mt-2">加载中...</p>
      </div>
      
      <div v-else-if="filteredRecords.length === 0" class="text-center py-8">
        <div class="text-gray-400 text-lg mb-2">📋</div>
        <p class="text-gray-500">暂无病历数据</p>
      </div>
      
      <div
        v-else
        v-for="record in paginatedRecords"
        :key="record.id"
        class="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all duration-200 cursor-pointer"
        @click="$emit('view-record', record)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-2">
              <h4 class="font-semibold text-gray-800">{{ record.name }}</h4>
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusLabel(record.status) }}
              </a-tag>
              <a-tag v-if="record.violation_risk" :color="getRiskColor(record.violation_risk)">
                {{ getRiskLabel(record.violation_risk) }}
              </a-tag>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
              <div>
                <span class="text-gray-500">患者：</span>
                <span class="font-medium">{{ record.patient_name }}</span>
              </div>
              <div>
                <span class="text-gray-500">科室：</span>
                <span>{{ record.department }}</span>
              </div>
              <div>
                <span class="text-gray-500">类型：</span>
                <span>{{ record.record_type }}</span>
              </div>
              <div v-if="record.qc_score">
                <span class="text-gray-500">质控评分：</span>
                <span class="font-medium" :class="getScoreClass(record.qc_score)">
                  {{ record.qc_score }}分
                </span>
              </div>
            </div>
            
            <div class="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>创建时间：{{ record.created_at }}</span>
              <span v-if="record.medical_insurance_type">医保类型：{{ record.medical_insurance_type }}</span>
              <span v-if="record.cost_amount">费用：¥{{ record.cost_amount.toLocaleString() }}</span>
            </div>
          </div>
          
          <div class="flex items-center gap-2 ml-4">
            <a-button size="small" @click.stop="$emit('edit-record', record)">
              编辑
            </a-button>
            <a-button size="small" type="primary" @click.stop="$emit('analyze-record', record)">
              分析
            </a-button>
            <a-dropdown>
              <a-button size="small">
                更多
                <DownOutlined />
              </a-button>
              <template #overlay>
                <a-menu>
                  <a-menu-item @click="$emit('view-record', record)">
                    <EyeOutlined /> 查看详情
                  </a-menu-item>
                  <a-menu-item @click="handleDuplicate(record)">
                    <CopyOutlined /> 复制病历
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item @click="$emit('delete-record', record)" class="text-red-600">
                    <DeleteOutlined /> 删除
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="filteredRecords.length > pageSize" class="mt-6 flex justify-center">
      <a-pagination
        v-model:current="currentPage"
        :total="filteredRecords.length"
        :page-size="pageSize"
        :show-size-changer="false"
        :show-quick-jumper="true"
        :show-total="(total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { DownOutlined, EyeOutlined, CopyOutlined, DeleteOutlined } from '@ant-design/icons-vue'

// 测试病历类型定义
interface TestMedicalRecord {
  id: string
  name: string
  patient_name: string
  patient_id: string
  department: string
  record_type: string
  disease_type: string
  complexity_level: string
  status: 'draft' | 'pending' | 'analyzing' | 'completed' | 'failed'
  qc_score?: number
  expected_grade?: string
  expected_score?: number
  content: string
  created_at: string
  updated_at: string
  created_by: string
  tags?: string[]
  medical_insurance_type?: string
  cost_amount?: number
  violation_risk?: 'low' | 'medium' | 'high'
}

// Props
const props = defineProps<{
  records: TestMedicalRecord[]
  loading?: boolean
}>()

// Emits
const emit = defineEmits<{
  'view-record': [record: TestMedicalRecord]
  'edit-record': [record: TestMedicalRecord]
  'delete-record': [record: TestMedicalRecord]
  'analyze-record': [record: TestMedicalRecord]
}>()

// 响应式数据
const searchKeyword = ref('')
const statusFilter = ref('')
const departmentFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(5)

// 计算属性
const filteredRecords = computed(() => {
  let filtered = props.records

  // 搜索过滤
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    filtered = filtered.filter(record => 
      record.name.toLowerCase().includes(keyword) ||
      record.patient_name.toLowerCase().includes(keyword)
    )
  }

  // 状态过滤
  if (statusFilter.value) {
    filtered = filtered.filter(record => record.status === statusFilter.value)
  }

  // 科室过滤
  if (departmentFilter.value) {
    filtered = filtered.filter(record => record.department === departmentFilter.value)
  }

  return filtered
})

const paginatedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredRecords.value.slice(start, end)
})

// 方法
function handleSearch() {
  currentPage.value = 1
}

function handleFilterChange() {
  currentPage.value = 1
}

function handleDuplicate(record: TestMedicalRecord) {
  message.info(`复制病历: ${record.name}`)
}

function getStatusColor(status: string) {
  const colors = {
    draft: 'default',
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

function getStatusLabel(status: string) {
  const labels = {
    draft: '草稿',
    pending: '待审核',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

function getRiskColor(risk: string) {
  const colors = {
    low: 'green',
    medium: 'orange',
    high: 'red'
  }
  return colors[risk as keyof typeof colors] || 'default'
}

function getRiskLabel(risk: string) {
  const labels = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return labels[risk as keyof typeof labels] || risk
}

function getScoreClass(score: number) {
  if (score >= 90) return 'text-green-600'
  if (score >= 80) return 'text-blue-600'
  if (score >= 70) return 'text-orange-600'
  return 'text-red-600'
}
</script>

<style scoped>
.test-medical-records-list {
  /* 自定义样式 */
}
</style>
