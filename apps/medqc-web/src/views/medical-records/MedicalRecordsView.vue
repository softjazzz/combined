<template>
  <div class="page-container">
    <!-- 页面标题和操作按钮 -->
    <div class="page-header">
      <h1 class="page-title">测试病历管理</h1>
      <!-- 调试信息 -->
      <div class="debug-info" style="background: #f0f0f0; padding: 8px; margin: 8px 0; border-radius: 4px; font-size: 12px;">
        <span class="inline-flex items-center gap-1">
          <ToolOutlined />
          调试: 记录数={{ records.length }}, 加载中={{ loading }}, 总数={{ pagination.total }}, 视图={{ viewMode }}
        </span>
      </div>
      <div class="header-actions">
        <a-space>
          <a-button size="small" @click="toggleViewMode">
            {{ viewMode === 'card' ? '切换表格视图' : '切换卡片视图' }}
          </a-button>
          <a-button @click="handleCreateRecord">
            <template #icon><PlusOutlined /></template>
            新建病历
          </a-button>
          <a-button type="primary" @click="handleSmartImport">
            <template #icon><RobotOutlined /></template>
            智能导入
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="ui-gradient-wrap from-sky-400/40 via-blue-400/30 to-indigo-400/40">
        <a-card class="ui-card ui-card-muted ui-card-hover stat-card">
        <a-statistic
          title="总病历数"
          :value="stats.totalRecords"
          :value-style="{ color: '#1890ff' }"
        >
          <template #prefix>
            <FileTextOutlined />
          </template>
        </a-statistic>
      </a-card>
      </div>
      <div class="ui-gradient-wrap from-emerald-400/40 via-teal-400/30 to-green-400/40">
        <a-card class="ui-card ui-card-muted ui-card-hover stat-card">
        <a-statistic
          title="本月新增"
          :value="stats.monthlyNew"
          :value-style="{ color: '#52c41a' }"
        >
          <template #prefix>
            <PlusCircleOutlined />
          </template>
        </a-statistic>
      </a-card>
      </div>
      <div class="ui-gradient-wrap from-amber-400/40 via-orange-400/30 to-yellow-400/40">
        <a-card class="ui-card ui-card-muted ui-card-hover stat-card">
        <a-statistic
          title="待审核"
          :value="stats.pendingReview"
          :value-style="{ color: '#faad14' }"
        >
          <template #prefix>
            <ClockCircleOutlined />
          </template>
        </a-statistic>
      </a-card>
      </div>
      <div class="ui-gradient-wrap from-violet-400/40 via-purple-400/30 to-fuchsia-400/40">
        <a-card class="ui-card ui-card-muted ui-card-hover stat-card">
        <a-statistic
          title="已关联质控点"
          :value="stats.withQualityPoints"
          :value-style="{ color: '#722ed1' }"
        >
          <template #prefix>
            <CheckCircleOutlined />
          </template>
        </a-statistic>
      </a-card>
      </div>
    </div>

    <!-- 筛选和搜索 -->
    <div class="ui-gradient-wrap from-sky-400/30 via-blue-400/20 to-indigo-400/30">
      <a-card class="ui-card ui-card-primary ui-card-hover filter-card">
      <a-row :gutter="16">
        <a-col :span="6">
          <a-input-search
            v-model:value="searchForm.recordName"
            placeholder="搜索患者姓名"
            @search="handleSearch"
            @change="handleSearch"
          />
        </a-col>
        <a-col :span="4">
          <a-select
            v-model:value="searchForm.department"
            placeholder="出院科室"
            allow-clear
            @change="handleSearch"
          >
            <a-select-option value="">全部科室</a-select-option>
            <a-select-option value="内科">内科</a-select-option>
            <a-select-option value="外科">外科</a-select-option>
            <a-select-option value="妇产科">妇产科</a-select-option>
            <a-select-option value="儿科">儿科</a-select-option>
            <a-select-option value="急诊科">急诊科</a-select-option>
          </a-select>
        </a-col>
        <a-col :span="4">
          <a-select
            v-model:value="searchForm.diagnosis"
            placeholder="主诊断"
            allow-clear
            @change="handleSearch"
          >
            <a-select-option value="">全部诊断</a-select-option>
            <a-select-option value="高血压">高血压</a-select-option>
            <a-select-option value="糖尿病">糖尿病</a-select-option>
            <a-select-option value="冠心病">冠心病</a-select-option>
            <a-select-option value="肺炎">肺炎</a-select-option>
            <a-select-option value="阑尾炎">阑尾炎</a-select-option>
          </a-select>
        </a-col>
        <a-col :span="4">
          <a-select
            v-model:value="searchForm.creator"
            placeholder="创建人"
            allow-clear
            @change="handleSearch"
          >
            <a-select-option value="">全部创建人</a-select-option>
            <a-select-option value="张医生">张医生</a-select-option>
            <a-select-option value="李医生">李医生</a-select-option>
            <a-select-option value="王医生">王医生</a-select-option>
          </a-select>
        </a-col>
        <a-col :span="6">
          <a-space>
            <a-range-picker
              v-model:value="searchForm.dateRange"
              @change="handleSearch"
            />
            <a-button @click="handleReset">重置</a-button>
          </a-space>
        </a-col>
      </a-row>
    </a-card>
    </div>

    <!-- 病历列表：卡片视图 + 表格视图 -->
    <div class="ui-gradient-wrap from-slate-400/30 via-gray-400/20 to-zinc-400/30">
      <a-card class="ui-card ui-card-muted ui-card-hover records-table-card">
      <div class="table-header">
        <div class="table-title">
          <h3>病历列表</h3>
          <span class="record-count">共 {{ pagination.total }} 条记录</span>
        </div>
        <div class="table-actions">
          <a-button size="small" @click="handleRefresh">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </div>
      </div>

      <!-- 卡片视图 -->
      <div v-if="viewMode === 'card'" class="grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        <!-- 调试信息 -->
        <div v-if="records.length === 0" class="col-span-full text-center p-8">
          <div class="text-gray-500">
            <p class="debug-info-title">
              <BarChartOutlined class="mr-1" />
              调试信息:
            </p>
            <p>记录数量: {{ records.length }}</p>
            <p>加载状态: {{ loading ? '加载中...' : '已完成' }}</p>
            <p>视图模式: {{ viewMode }}</p>
            <p>分页总数: {{ pagination.total }}</p>
          </div>
        </div>

        <div
          v-for="rec in records"
          :key="rec.id"
          class="record-card ui-card ui-card-muted ui-card-hover p-3 transition-colors transition-shadow duration-200 ease-out hover:bg-[#e8f4fd] hover:shadow-md hover:border-blue-200"
        >
          <div class="flex items-start justify-between">
            <div>
              <div class="text-xs text-gray-500">编号</div>
              <div class="text-sm font-semibold text-gray-900 record-number-text">{{ rec.recordNumber }}</div>
            </div>
            <a-tag :color="rec.status === 'active' ? 'blue' : 'default'">{{ rec.status || '—' }}</a-tag>
          </div>

          <div class="mt-2">
            <div class="text-xs text-gray-500">患者姓名</div>
            <div class="text-gray-800 font-medium patient-name-text">{{ rec.patientName || rec.recordName }}</div>
          </div>

          <div class="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600">
            <div>科室：<span class="text-gray-800">{{ rec.department || '—' }}</span></div>
            <div>文书：<span class="text-gray-800">{{ rec.documentsCount ?? 0 }}</span> 份</div>
            <div class="col-span-2 truncate">主诊断：<span class="text-gray-800">{{ rec.primaryDiagnosis || '—' }}</span></div>
          </div>

          <div class="mt-3 flex items-center justify-between text-xs text-gray-500">
            <div>
              创建：{{ formatDateTime(rec.createdAt) }}
            </div>
            <div class="flex items-center gap-2">
              <a-button type="link" size="small" class="p-0" @click="handleViewDetail(rec.id)">详情</a-button>
              <a-divider type="vertical" />
              <a-button type="link" size="small" class="p-0" @click="handleCopy(rec.id)">复制</a-button>
              <a-divider type="vertical" />
              <a-popconfirm title="确定要删除这条病历吗？" ok-text="确定" cancel-text="取消" @confirm="handleDelete(rec.id)">
                <a-button type="link" size="small" danger class="p-0">删除</a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <!-- 表格视图 -->
      <a-table
        v-else
        :columns="columns"
        :data-source="records"
        :loading="loading"
        :pagination="pagination"
        :row-selection="rowSelection"
        size="middle"
        @change="handleTableChange"
      >
        <template #recordNumber="{ text }">
          <span class="record-number">{{ text }}</span>
        </template>
        <template #patientName="{ record }">
          <span class="patient-name">{{ record.patientName || record.recordName || '未知' }}</span>
        </template>
        <template #qualityPoints="{ record }">
          <a-button type="link" size="small" @click="showQualityPointsModal(record)">
            查看质控点 ({{ record.qualityPointIds?.length || 0 }})
          </a-button>
        </template>
        <template #createdAt="{ text }">
          <span>{{ formatDateTime(text) }}</span>
        </template>
        <template #action="{ record }">
          <a-space size="small">
            <a-button type="link" size="small" @click="handleViewDetail(record.id)">详情</a-button>
            <a-button type="link" size="small" @click="handleCopy(record.id)">复制</a-button>
            <a-popconfirm title="确定要删除这条病历吗？" ok-text="确定" cancel-text="取消" @confirm="handleDelete(record.id)">
              <a-button type="link" size="small" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </a-table>
    </a-card>
    </div>

    <!-- 质控点详情弹窗 -->
    <a-modal
      v-model:open="qualityPointsModalVisible"
      title="质控点详情"
      :footer="null"
      width="600px"
    >
      <div v-if="selectedRecord">
        <div class="modal-record-info">
          <p><strong>病历编号：</strong>{{ selectedRecord.recordNumber }}</p>
          <p><strong>患者姓名：</strong>{{ selectedRecord.patientName || selectedRecord.recordName }}</p>
        </div>
        <a-divider />
        <div class="quality-points-list">
          <h4>应用的质控点：</h4>
          <div v-if="qualityPointsData.length === 0" class="no-data">
            暂无关联的质控点
          </div>
          <div v-else>
            <div
              v-for="point in qualityPointsData"
              :key="point.id"
              class="quality-point-item"
            >
              <div class="point-header">
                <span class="point-id">{{ point.id }}</span>
                <span class="point-name">{{ point.name }}</span>
              </div>
              <div class="point-details">
                <a-tag :color="getCategoryColor(point.category)">
                  {{ point.category }}
                </a-tag>
                <a-tag :color="getSeverityColor(point.severity)">
                  {{ point.severity }}
                </a-tag>
                <span class="applied-time">
                  应用时间: {{ formatDateTime(point.appliedAt) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-modal>


  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import {
  FileTextOutlined,
  PlusCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  RobotOutlined,
  PlusOutlined,
  BarChartOutlined,
  ToolOutlined
} from '@ant-design/icons-vue'
import type { TableColumnsType, TableProps } from 'ant-design-vue'
import dayjs from 'dayjs'
// 添加API配置 - 支持外部IP访问
const getApiBaseUrl = () => {
  // 开发环境使用Vite代理，生产环境使用完整URL
  if (import.meta.env.DEV) {
    return '' // 开发环境使用Vite代理
  }
  // 检测是否从外部IP访问，如果是则使用服务器IP
  if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return 'http://124.220.6.136:8001'
  }
  return 'http://localhost:8001'
}
const API_BASE_URL = getApiBaseUrl()
console.log('🌐 病历列表页面使用API地址:', API_BASE_URL)

const router = useRouter()
const authStore = useAuthStore()

// 响应式数据
const loading = ref(false)
const records = ref([])
const selectedRowKeys = ref<string[]>([])
const qualityPointsModalVisible = ref(false)
const selectedRecord = ref(null)
const qualityPointsData = ref([])

// 统计数据
const stats = reactive({
  totalRecords: 156,
  monthlyNew: 23,
  pendingReview: 5,
  withQualityPoints: 89
})

// 搜索表单
const searchForm = reactive({
  recordName: '',
  department: '',
  diagnosis: '',
  creator: '',
  dateRange: null
})

// 分页配置
const viewMode = ref<'card' | 'table'>('card')

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number, range: [number, number]) =>
    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
})

// 表格列配置
const columns: TableColumnsType = [
  {
    title: '病历编号',
    dataIndex: 'recordNumber',
    key: 'recordNumber',
    width: 100,
    sorter: true,
    slots: { customRender: 'recordNumber' }
  },
  {
    title: '患者姓名',
    dataIndex: 'patientName',
    key: 'patientName',
    width: 200,
    slots: { customRender: 'patientName' }
  },
  {
    title: '出院科室',
    dataIndex: 'department',
    key: 'department',
    width: 120
  },
  {
    title: '主诊断名称',
    dataIndex: 'primaryDiagnosis',
    key: 'primaryDiagnosis',
    width: 150
  },
  {
    title: '主要手术及操作',
    dataIndex: 'majorSurgery',
    key: 'majorSurgery',
    width: 180,
    ellipsis: true
  },
  {
    title: '文书数量',
    dataIndex: 'documentsCount',
    key: 'documentsCount',
    width: 80,
    align: 'center'
  },
  {
    title: '应用质控点',
    key: 'qualityPoints',
    width: 120,
    slots: { customRender: 'qualityPoints' }
  },
  {
    title: '病历创建人',
    dataIndex: 'createdBy',
    key: 'createdBy',
    width: 100
  },
  {
    title: '最后操作人',
    dataIndex: 'lastModifiedBy',
    key: 'lastModifiedBy',
    width: 100
  },
  {
    title: '创建时间',
    dataIndex: 'createdAt',
    key: 'createdAt',
    width: 120,
    sorter: true,
    slots: { customRender: 'createdAt' }
  },
  {
    title: '操作',
    key: 'action',
    width: 120,
    fixed: 'right',
    slots: { customRender: 'action' }
  }
]

// 行选择配置
const rowSelection = computed(() => ({
  selectedRowKeys: selectedRowKeys.value, onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
  onSelectAll: (selected: boolean, selectedRows: unknown[], changeRows: unknown[]) => {
    console.log('Select all:', selected, selectedRows, changeRows)
  }
}))

// 生命周期
onMounted(async () => {
  console.log('🚀 MedicalRecordsView 组件挂载')

  // 添加全局调试接口
  ;(window as any).debugMedicalRecords = {
    loadRecords,
    loadStats,
    records,
    loading,
    pagination,
    authStore
  }
  console.log('🔧 全局调试接口已添加: window.debugMedicalRecords')

  // 初始化认证状态
  if (!authStore.initialized) {
    console.log('🔐 初始化认证状态...')
    await authStore.initialize()
  }

  console.log('📊 认证状态:', {
    isAuthenticated: authStore.isAuthenticated,
    user: authStore.user
  })

  // 加载数据
  loadRecords()
  loadStats()
})

// 方法定义
const loadRecords = async () => {
  loading.value = true
  console.log('🚀 开始加载病历记录...')

  try {
    // 简化认证逻辑 - 直接获取token，不依赖store状态
    const token = localStorage.getItem('medqc_access_token') || localStorage.getItem('token') || localStorage.getItem('access_token')
    console.log('🔑 Token检查:', token ? `找到token: ${token.substring(0, 20)}...` : '未找到token')

    if (!token) {
      console.log('❌ 没有找到token')
      message.error('请先登录')
      // 暂时不跳转，先让页面显示，方便调试
      // router.push('/login')
      // return
    }

    // 构建查询参数
    const params = new URLSearchParams()
    if (searchForm.recordName) {
      params.append('keyword', searchForm.recordName)
    }
    if (searchForm.department) {
      params.append('department', searchForm.department)
    }
    params.append('page', pagination.current.toString())
    params.append('page_size', pagination.pageSize.toString())

    // 处理日期范围
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.append('start_date', searchForm.dateRange[0].format('YYYY-MM-DD'))
      params.append('end_date', searchForm.dateRange[1].format('YYYY-MM-DD'))
    }

    // 调用后端病历列表接口（现在使用medical_records_test表）
    const apiUrl = `${API_BASE_URL}/api/records?${params.toString()}`
    console.log('📡 API调用URL:', apiUrl)

    const headers = {
      'Content-Type': 'application/json'
    }

    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    console.log('📋 请求头:', headers)

    const response = await fetch(apiUrl, {
      method: 'GET',
      headers
    })

    console.log(`📊 API响应状态: ${response.status} ${response.statusText}`)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('❌ API调用失败:', errorText)
      throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`)
    }

    const result = await response.json()
    console.log('📊 API返回的数据:', result)

    // 检查数据结构 - 适配后端的分页响应格式
    // 后端返回格式: { success: true, data: { items: [...], total: 100, page: 1, page_size: 10 } }
    if (!result.data) {
      console.error('❌ API返回的数据格式不正确:', result)
      message.error('数据格式错误')
      return
    }

    // 兼容两种格式：
    // 1. 新格式: { data: { items: [...], total: 100 } }
    // 2. 旧格式: { data: [...], total: 100 }
    const items = result.data.items || result.data
    const total = result.data.total || result.total || 0

    if (!Array.isArray(items)) {
      console.error('❌ API返回的数据不是数组:', result)
      message.error('数据格式错误')
      return
    }

    console.log(`📋 获取到 ${items.length} 条记录`)

    // 转换数据格式以适配现有UI - 适配medical_records表结构
    records.value = items.map((record: unknown) => ({
      id: record.id,
      recordNumber: record.record_number || record.id,
      recordName: record.record_name || `${record.patient_info?.name || '未知患者'}的病历记录`,
      patientName: record.patient_info?.name || '未知患者',
      department: record.department || '未知科室',
      primaryDiagnosis: record.primary_diagnosis || '未知诊断',
      majorSurgery: record.major_surgery || '无',
      qualityPointIds: [], // 暂时为空，后续可以从关联表获取
      createdBy: record.created_by || '系统',
      lastModifiedBy: record.updated_by || record.created_by || '系统',
      createdAt: record.created_at,
      status: record.status,
      importMethod: record.import_method || 'smart_import',
      aiConfidence: record.ai_confidence_score || 0,
      documentsCount: record.document_count || (Array.isArray(record.documents) ? record.documents.length : 0)
    }))

    console.log('🔄 转换后的记录数据:', records.value)
    console.log(`📊 设置分页总数: ${total}`)

    pagination.total = total

    console.log('✅ 数据加载完成!')
    console.log('📊 最终状态:', {
      recordsCount: records.value.length,
      paginationTotal: pagination.total,
      loading: loading.value
    })
  } catch (error) {
    console.error('❌ 加载病历列表失败:', error)
    console.error('错误详情:', {
      message: error.message,
      stack: error.stack
    })
    message.error(`加载病历列表失败: ${error.message}`)

    // 如果Supabase调用失败，使用模拟数据作为后备
    const mockData = [
      {
        id: '1',
        recordNumber: 'TEST20240827001',
        recordName: '张三测试病历',
        patientName: '张三',
        department: '内科',
        primaryDiagnosis: '高血压病',
        majorSurgery: '无',
        qualityPointIds:  [],
        createdBy: '系统',
        lastModifiedBy: '系统',
        createdAt: '2024-08-27T10:30:00Z',
        status: 'active',
        importMethod: 'smart_import',
        aiConfidence: 89.5,
        documentsCount: 2
      }
    ]

    records.value = mockData
    pagination.total = mockData.length
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    // 获取认证token
    const token = localStorage.getItem('token')
    if (!token) {
      return // 如果没有token，使用默认统计数据
    }

    // 调用后端病历列表接口获取统计数据
    const apiUrl = `${API_BASE_URL}/api/records?page=1&page_size=1000` // 获取大量数据用于统计
    const response = await fetch(apiUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const result = await response.json()
      const allRecords = result.data || []

      // 计算统计数据
      const totalRecords = result.total || allRecords.length
      const currentMonth = new Date().getMonth()
      const currentYear = new Date().getFullYear()

      const monthlyNew = allRecords.filter(record => {
        const createdDate = new Date(record.created_at)
        return createdDate.getMonth() === currentMonth && createdDate.getFullYear() === currentYear
      }).length

      const pendingReview = allRecords.filter(record => record.status === 'pending').length
      const withQualityPoints = allRecords.filter(record => record.record_type === 'LLM解析结果').length

      Object.assign(stats, {
        totalRecords,
        monthlyNew,
        pendingReview,
        withQualityPoints
      })
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    // 保持默认的模拟数据
  }
}

const formatDateTime = (dateString: string) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

const getCategoryColor = (category: string) => {
  const colorMap: Record<string, string> = {
    '完整性': 'blue',
    '一致性': 'green',
    '合理性': 'orange',
    '及时性': 'purple'
  }
  return colorMap[category] || 'default'
}

const getSeverityColor = (severity: string) => {
  const colorMap: Record<string, string> = {
    '严重': 'red',
    '重要': 'orange',
    '轻微': 'green'
  }
  return colorMap[severity] || 'default'
}

// 事件处理
const handleCreateRecord = () => {
  router.push('/dashboard/medical-records/create')
}

const handleSmartImport = () => {
  router.push('/dashboard/medical-records/smart-import')
}

const handleViewDetail = (id: string) => {
  router.push(`/dashboard/medical-records/${id}`)
}

const handleCopy = async (id: string) => {
  try {
    // 模拟复制操作
    await new Promise(resolve => setTimeout(resolve, 500))
    message.success('病历复制成功')
    loadRecords()
  } catch (error) {
    message.error('复制失败')
  }
}

const handleDelete = async (id: string) => {
  try {
    // 获取认证token - 支持多种token键名
    const token = localStorage.getItem('medqc_access_token') || localStorage.getItem('token') || localStorage.getItem('access_token')
    if (!token) {
      message.error('请先登录')
      return
    }

    // 调用后端删除API
    const apiUrl = `${API_BASE_URL}/api/records/${id}`
    const response = await fetch(apiUrl, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(`删除失败: ${response.statusText}`)
    }

    message.success('删除成功')
    // 重新加载列表数据
    loadRecords()
  } catch (error) {
    console.error('删除失败:', error)
    message.error(error instanceof Error ? error.message : '删除失败')
  }
}

const handleSearch = () => {
  pagination.current = 1
  loadRecords()
}

const handleReset = () => {
  Object.assign(searchForm, {
    recordName: '',
    department: '',
    diagnosis: '',
    creator: '',
    dateRange: null
  })
  handleSearch()
}

const handleRefresh = () => {
  loadRecords()
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'card' ? 'table' : 'card'
}

const handleTableChange: TableProps['onChange'] = (pag: unknown,  filters: unknown, sorter: unknown) => {
  pagination.current = pag?.current || 1
  pagination.pageSize = pag?.pageSize || 10
  loadRecords()
}



const showQualityPointsModal = async (record) => {
  selectedRecord.value = record
  qualityPointsModalVisible.value = true

  // 模拟加载质控点数据
  qualityPointsData.value = [
    {
      id: 'QC001',
      name: '完整性检查',
      category: '完整性',
      severity: '重要',
      appliedAt: '2024-08-27T10:30:00Z'
    },
    {
      id: 'QC002',
      name: '一致性检查',
      category: '一致性',
      severity: '严重',
      appliedAt: '2024-08-27T10:35:00Z'
    }
  ]
}


</script>

<style scoped>
/* 整体布局优化 - 遵循UI设计规范 */
.page-container {
  @apply p-3;
}

.page-header {
  @apply flex items-center justify-between mb-3;
}

.page-title {
  @apply text-lg font-bold text-gray-900;
  font-size: 16px;
}

.header-actions {
  @apply flex items-center gap-2;
}

.stats-grid {
  @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2 mb-3;
}

.stat-card {
  @apply shadow-sm hover:shadow-md transition-shadow;
}

/* 统计卡片内部间距优化 */
:deep(.stat-card .ant-card-body) {
  padding: 12px 16px !important;
}

.filter-card {
  @apply mb-3;
}

/* 筛选卡片内部间距优化 */
:deep(.filter-card .ant-card-body) {
  padding: 10px 14px !important;
}

.records-table-card {
  @apply shadow-sm;
}

.debug-info-title {
  @apply flex items-center justify-center gap-1 text-sm font-medium mb-2;
}

/* 表格卡片内部间距优化 */
:deep(.records-table-card .ant-card-body) {
  padding: 8px !important;
}

/* 卡片视图内按钮更小更紧凑 */
:deep(.ant-card .ant-btn-link) {
  padding: 0 !important;
}

/* 卡片视图栅格间距 */
.card-grid {
  @apply grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3;
}

/* 表格标题区域 */
.table-header {
  @apply flex items-center justify-between mb-3;
}

.table-title {
  @apply flex items-center gap-2;
}

.table-title h3 {
  @apply text-sm font-semibold text-gray-900 m-0;
}

.record-count {
  @apply text-xs text-gray-500;
}

.table-actions {
  @apply flex items-center gap-2;
}

/* 统计卡片标题优化 */
:deep(.ant-statistic-title) {
  @apply text-gray-700 font-bold;
  font-size: 15px !important;
  font-weight: 700 !important;
  margin-bottom: 4px !important;
}

:deep(.ant-statistic-content) {
  @apply font-bold;
  font-size: 20px !important;
}

:deep(.ant-statistic-content-value) {
  font-size: 20px !important;
}

/* 表格标题行优化 */
:deep(.ant-table-thead > tr > th) {
  @apply bg-gray-50 font-semibold;
  font-size: 11px !important;
  padding: 4px 3px !important;
  white-space: nowrap !important;
  font-weight: 600 !important;
  height: 28px !important;
  line-height: 1.1 !important;
}

/* 表格行优化 */
:deep(.ant-table-tbody > tr > td) {
  font-size: 13px !important;
  padding: 4px 6px !important;
  vertical-align: middle !important;
  line-height: 1.2 !important;
}

:deep(.ant-table-tbody > tr:hover > td) {
  @apply bg-blue-50;
}

/* 表格行高调整 */
:deep(.ant-table-tbody > tr) {
  height: 30px !important;
}

/* 表格内容垂直居中 */
:deep(.ant-table-tbody > tr > td .ant-space) {
  align-items: center !important;
  gap: 3px !important;
}

:deep(.ant-table-tbody > tr > td .ant-space-item) {
  display: flex !important;
  align-items: center !important;
}

/* 表格整体紧凑化 */
:deep(.ant-table) {
  font-size: 11px !important;
}

:deep(.ant-table-container) {
  border-radius: 4px !important;
}

/* 表格外层容器优化 */
:deep(.ant-table-wrapper) {
  margin: 0 !important;
}

/* 病历编号和名称样式 */
.record-number {
  @apply font-medium text-gray-900;
  font-size: 12px !important;
}

.record-name {
  @apply text-gray-700;
  font-size: 12px !important;
}

/* 质控点详情弹窗样式 */
.modal-record-info {
  @apply mb-4;
}

.modal-record-info p {
  @apply mb-2 text-sm;
}

.quality-points-list h4 {
  @apply text-sm font-semibold mb-3;
}

.no-data {
  @apply text-center text-gray-500 py-4;
}

.quality-point-item {
  @apply border border-gray-200 rounded p-3 mb-2;
}

.point-header {
  @apply flex items-center gap-2 mb-2;
}

.point-id {
  @apply font-mono text-xs bg-gray-100 px-2 py-1 rounded;
}

.point-name {
  @apply font-medium text-sm;
}

.point-details {
  @apply flex items-center gap-2;
}

.applied-time {
  @apply text-xs text-gray-500 ml-auto;
}

/* 导入弹窗样式 */
.import-actions {
  @apply mt-4 text-right;
}

/* 按钮尺寸优化 */
:deep(.ant-btn) {
  font-size: 12px !important;
  height: 28px !important;
  padding: 3px 12px !important;
}

/***** Medical record card hover *****/
.record-card {
  border: 1px solid rgba(226,232,240,0.8); /* slate-200 */
  border-radius: 12px;
}
.record-card:hover {
  /* backup in case Tailwind classes don’t apply in some contexts */
  background: #e8f4fd; /* soft blue */
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.12);
  border-color: #bfdbfe; /* blue-200 */
}

/* 避免文字模糊：取消导致重绘模糊的 transform */
.record-card {
  transform: none; /* 避免子元素抗锯齿问题 */
  will-change: background, box-shadow, border-color; /* 提示仅在这几项上过渡 */
}

/* 病历编号/患者姓名在悬停时轻微放大并保持清晰 */
.record-card .record-number-text,
.record-card .patient-name-text {
  transition: transform 0.24s ease, color 0.24s ease;
  transform-origin: left center;
}

.record-card:hover .record-number-text,
.record-card:hover .patient-name-text {
  transform: scale(1.12);
}

/* 避免因父级滤镜或强阴影导致的字体发糊，给文本开启亚像素抗锯齿优化 */
.record-card .record-number-text,
.record-card .patient-name-text {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}



/* 头部操作按钮保持稍大尺寸 */
:deep(.header-actions .ant-btn) {
  font-size: 13px !important;
  height: 30px !important;
  padding: 4px 14px !important;
}

/* 表格内小按钮 */
:deep(.ant-btn-sm) {
  font-size: 11px !important;
  height: 20px !important;
  padding: 0px 5px !important;
  line-height: 1.1 !important;
}
</style>

