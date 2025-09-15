<template>
  <div class="report-scheduler">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-content">
        <h1>报表调度管理</h1>
        <p>自动化报表生成与邮件推送</p>
      </div>
      <div class="header-actions">
        <a-space>
          <a-button type="primary" @click="showCreateModal">
            <template #icon><PlusOutlined /></template>
            新建调度
          </a-button>
          <a-button @click="refreshData" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <a-row :gutter="[16, 16]">
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="stat-card">
            <a-statistic
              title="总调度任务"
              :value="stats.totalJobs"
              :value-style="{ color: '#1890ff' }"
            >
              <template #prefix><ScheduleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="stat-card">
            <a-statistic
              title="活跃任务"
              :value="stats.activeJobs"
              :value-style="{ color: '#52c41a' }"
            >
              <template #prefix><PlayCircleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="stat-card">
            <a-statistic
              title="今日执行"
              :value="stats.todayExecutions"
              :value-style="{ color: '#faad14' }"
            >
              <template #prefix><ThunderboltOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :xs="24" :sm="12" :md="6">
          <a-card class="stat-card">
            <a-statistic
              title="成功率"
              :value="stats.successRate"
              :precision="1"
              suffix="%"
              :value-style="{ color: stats.successRate >= 90 ? '#52c41a' : '#faad14' }"
            >
              <template #prefix><CheckCircleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 调度任务列表 -->
    <a-card title="调度任务" class="jobs-table-card">
      <template #extra>
        <a-space>
          <a-input-search
            v-model:value="searchText"
            placeholder="搜索任务"
            style="width: 200px"
            @search="filterJobs"
          />
          <a-select v-model:value="statusFilter" @change="filterJobs" style="width: 120px">
            <a-select-option value="">全部状态</a-select-option>
            <a-select-option value="enabled">已启用</a-select-option>
            <a-select-option value="disabled">已禁用</a-select-option>
          </a-select>
        </a-space>
      </template>

      <a-table
        :dataSource="filteredJobs"
        :columns="jobColumns"
        :pagination="{ pageSize: 10, showSizeChanger: true }"
        :loading="loading"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'enabled'">
            <a-switch
              v-model:checked="record.enabled"
              @change="toggleJobStatus(record)"
              :loading="record.updating"
            />
          </template>
          <template v-if="column.key === 'schedule_type'">
            <a-tag :color="getScheduleTypeColor(record.schedule_type)">
              {{ getScheduleTypeText(record.schedule_type) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'next_execution'">
            <span v-if="record.next_execution">
              {{ formatDateTime(record.next_execution) }}
            </span>
            <span v-else class="text-muted">未设置</span>
          </template>
          <template v-if="column.key === 'last_execution'">
            <span v-if="record.last_execution">
              {{ formatDateTime(record.last_execution) }}
            </span>
            <span v-else class="text-muted">未执行</span>
          </template>
          <template v-if="column.key === 'recipients'">
            <a-tooltip>
              <template #title>
                <div v-for="recipient in record.recipients" :key="recipient.email">
                  {{ recipient.name || recipient.email }}
                </div>
              </template>
              <a-tag>{{ record.recipients.length }} 人</a-tag>
            </a-tooltip>
          </template>
          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button type="link" size="small" @click="executeJob(record)">
                立即执行
              </a-button>
              <a-button type="link" size="small" @click="editJob(record)">
                编辑
              </a-button>
              <a-button type="link" size="small" @click="viewHistory(record)">
                历史
              </a-button>
              <a-popconfirm
                title="确定要删除这个调度任务吗？"
                @confirm="deleteJob(record)"
              >
                <a-button type="link" size="small" danger>
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 创建/编辑调度任务模态框 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingJob ? '编辑调度任务' : '新建调度任务'"
      @ok="handleSubmit"
      :confirm-loading="submitting"
      width="800px"
      :destroy-on-close="true"
    >
      <a-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        layout="vertical"
      >
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="任务名称" name="name">
              <a-input v-model:value="formData.name" placeholder="输入任务名称" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="报表模板" name="template_id">
              <a-select v-model:value="formData.template_id" placeholder="选择报表模板">
                <a-select-option v-for="template in templates" :key="template.id" :value="template.id">
                  {{ template.name }}
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="任务描述" name="description">
          <a-textarea v-model:value="formData.description" placeholder="输入任务描述" :rows="2" />
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="调度类型" name="schedule_type">
              <a-select v-model:value="formData.schedule_type" @change="onScheduleTypeChange">
                <a-select-option value="daily">每日</a-select-option>
                <a-select-option value="weekly">每周</a-select-option>
                <a-select-option value="monthly">每月</a-select-option>
                <a-select-option value="custom">自定义</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="输出格式" name="output_format">
              <a-select v-model:value="formData.output_format">
                <a-select-option value="excel">Excel</a-select-option>
                <a-select-option value="csv">CSV</a-select-option>
                <a-select-option value="pdf">PDF</a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <!-- 调度配置 -->
        <a-form-item label="调度配置">
          <div class="schedule-config">
            <a-row :gutter="16">
              <a-col :span="12" v-if="formData.schedule_type !== 'custom'">
                <a-form-item label="执行时间">
                  <a-time-picker
                    v-model:value="scheduleTime"
                    format="HH:mm"
                    placeholder="选择时间"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12" v-if="formData.schedule_type === 'weekly'">
                <a-form-item label="星期几">
                  <a-select v-model:value="formData.schedule_config.day_of_week">
                    <a-select-option :value="0">星期日</a-select-option>
                    <a-select-option :value="1">星期一</a-select-option>
                    <a-select-option :value="2">星期二</a-select-option>
                    <a-select-option :value="3">星期三</a-select-option>
                    <a-select-option :value="4">星期四</a-select-option>
                    <a-select-option :value="5">星期五</a-select-option>
                    <a-select-option :value="6">星期六</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12" v-if="formData.schedule_type === 'monthly'">
                <a-form-item label="每月几号">
                  <a-input-number
                    v-model:value="formData.schedule_config.day_of_month"
                    :min="1"
                    :max="31"
                    placeholder="1-31"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="24" v-if="formData.schedule_type === 'custom'">
                <a-form-item label="Cron 表达式">
                  <a-input
                    v-model:value="formData.schedule_config.cron_expression"
                    placeholder="0 9 * * 1-5"
                  />
                  <div class="cron-help">
                    <small>格式: 分 时 日 月 周，例如 "0 9 * * 1-5" 表示工作日上午9点</small>
                  </div>
                </a-form-item>
              </a-col>
            </a-row>
          </div>
        </a-form-item>

        <!-- 收件人配置 -->
        <a-form-item label="收件人" name="recipients">
          <div class="recipients-config">
            <div v-for="(recipient, index) in formData.recipients" :key="index" class="recipient-item">
              <a-row :gutter="8" align="middle">
                <a-col :span="8">
                  <a-input v-model:value="recipient.name" placeholder="姓名（可选）" />
                </a-col>
                <a-col :span="10">
                  <a-input v-model:value="recipient.email" placeholder="邮箱地址" />
                </a-col>
                <a-col :span="4">
                  <a-select v-model:value="recipient.type" style="width: 100%">
                    <a-select-option value="to">收件人</a-select-option>
                    <a-select-option value="cc">抄送</a-select-option>
                    <a-select-option value="bcc">密送</a-select-option>
                  </a-select>
                </a-col>
                <a-col :span="2">
                  <a-button type="text" danger @click="removeRecipient(index)">
                    <template #icon><DeleteOutlined /></template>
                  </a-button>
                </a-col>
              </a-row>
            </div>
            <a-button type="dashed" @click="addRecipient" style="width: 100%; margin-top: 8px">
              <template #icon><PlusOutlined /></template>
              添加收件人
            </a-button>
          </div>
        </a-form-item>

        <!-- 报表参数 -->
        <a-form-item label="报表参数">
          <div class="parameters-config">
            <a-row :gutter="16">
              <a-col :span="12">
                <a-form-item label="时间范围">
                  <a-select v-model:value="formData.parameters.timeRange">
                    <a-select-option value="7d">最近7天</a-select-option>
                    <a-select-option value="30d">最近30天</a-select-option>
                    <a-select-option value="90d">最近90天</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="数据粒度">
                  <a-select v-model:value="formData.parameters.granularity">
                    <a-select-option value="day">按天</a-select-option>
                    <a-select-option value="week">按周</a-select-option>
                    <a-select-option value="month">按月</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>
          </div>
        </a-form-item>

        <a-form-item>
          <a-checkbox v-model:checked="formData.enabled">启用调度任务</a-checkbox>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 执行历史模态框 -->
    <a-modal
      v-model:open="historyModalVisible"
      title="执行历史"
      :footer="null"
      width="1000px"
    >
      <a-table
        :dataSource="executionHistory"
        :columns="historyColumns"
        :pagination="{ pageSize: 10 }"
        :loading="historyLoading"
        row-key="id"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="getStatusColor(record.status)">
              {{ getStatusText(record.status) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'duration_ms'">
            <span v-if="record.duration_ms">
              {{ formatDuration(record.duration_ms) }}
            </span>
            <span v-else>-</span>
          </template>
          <template v-if="column.key === 'output_size'">
            <span v-if="record.output_size">
              {{ formatFileSize(record.output_size) }}
            </span>
            <span v-else>-</span>
          </template>
          <template v-if="column.key === 'execution_time'">
            {{ formatDateTime(record.execution_time) }}
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import dayjs, { Dayjs } from 'dayjs'
import {
  PlusOutlined,
  ReloadOutlined,
  ScheduleOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const loading = ref(false)
const submitting = ref(false)
const modalVisible = ref(false)
const historyModalVisible = ref(false)
const historyLoading = ref(false)
const searchText = ref('')
const statusFilter = ref('')

// 数据状态
const jobs = ref([])
const templates = ref([])
const executionHistory = ref([])
const editingJob = ref(null)

// 统计数据
const stats = reactive({
  totalJobs: 0,
  activeJobs: 0,
  todayExecutions: 0,
  successRate: 0
})

// 表单数据
const formRef = ref()
const scheduleTime = ref<Dayjs>()
const formData = reactive({
  name: '',
  description: '',
  template_id: '',
  schedule_type: 'daily',
  schedule_config: {},
  parameters: {
    timeRange: '30d',
    granularity: 'day'
  },
  output_format: 'excel',
  recipients: [],
  enabled: true
})

// 表单验证规则
const formRules = {
  name: [{ required: true, message: '请输入任务名称' }],
  template_id: [{ required: true, message: '请选择报表模板' }],
  schedule_type: [{ required: true, message: '请选择调度类型' }],
  output_format: [{ required: true, message: '请选择输出格式' }],
  recipients: [
    { 
      validator: (rule, value) => {
        if (!value || value.length === 0) {
          return Promise.reject('请至少添加一个收件人')
        }
        for (const recipient of value) {
          if (!recipient.email || !/\S+@\S+\.\S+/.test(recipient.email)) {
            return Promise.reject('请输入有效的邮箱地址')
          }
        }
        return Promise.resolve()
      }
    }
  ]
}

// 表格列定义
const jobColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '描述', dataIndex: 'description', key: 'description', width: 200, ellipsis: true },
  { title: '调度类型', dataIndex: 'schedule_type', key: 'schedule_type', width: 100 },
  { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 80 },
  { title: '收件人', dataIndex: 'recipients', key: 'recipients', width: 80 },
  { title: '下次执行', dataIndex: 'next_execution', key: 'next_execution', width: 150 },
  { title: '上次执行', dataIndex: 'last_execution', key: 'last_execution', width: 150 },
  { title: '操作', key: 'actions', width: 200, fixed: 'right' }
]

const historyColumns = [
  { title: '执行时间', dataIndex: 'execution_time', key: 'execution_time', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '耗时', dataIndex: 'duration_ms', key: 'duration_ms', width: 80 },
  { title: '文件大小', dataIndex: 'output_size', key: 'output_size', width: 100 },
  { title: '收件人数', dataIndex: 'recipients_count', key: 'recipients_count', width: 80 },
  { title: '错误信息', dataIndex: 'error_message', key: 'error_message', ellipsis: true }
]

// 计算属性
const filteredJobs = computed(() => {
  let filtered = jobs.value

  if (searchText.value) {
    filtered = filtered.filter(job => 
      job.name.includes(searchText.value) || 
      job.description?.includes(searchText.value)
    )
  }

  if (statusFilter.value) {
    filtered = filtered.filter(job => 
      statusFilter.value === 'enabled' ? job.enabled : !job.enabled
    )
  }

  return filtered
})

// 方法
const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([
      loadJobs(),
      loadTemplates(),
      loadStats()
    ])
  } catch (error) {
    message.error('数据加载失败')
    console.error('Failed to refresh data:', error)
  } finally {
    loading.value = false
  }
}

const loadJobs = async () => {
  // 模拟加载调度任务数据
  jobs.value = [
    {
      id: '1',
      name: '日报-违规汇总',
      description: '每日违规数据汇总报告',
      template_id: 'violations_summary',
      schedule_type: 'daily',
      schedule_config: { time: '09:00' },
      parameters: { timeRange: '1d', granularity: 'day' },
      output_format: 'excel',
      recipients: [
        { email: 'admin@hospital.com', name: '管理员', type: 'to' }
      ],
      enabled: true,
      created_at: '2024-12-01T00:00:00Z',
      next_execution: '2024-12-11T09:00:00Z',
      last_execution: '2024-12-10T09:00:00Z'
    }
  ]
}

const loadTemplates = async () => {
  // 模拟加载报表模板数据
  templates.value = [
    { id: 'violations_summary', name: '违规汇总报告' },
    { id: 'department_performance', name: '科室质控绩效报告' },
    { id: 'doctor_quality_profile', name: '医生质控档案' }
  ]
}

const loadStats = async () => {
  // 模拟加载统计数据
  stats.totalJobs = jobs.value.length
  stats.activeJobs = jobs.value.filter(job => job.enabled).length
  stats.todayExecutions = 5
  stats.successRate = 95.2
}

const showCreateModal = () => {
  editingJob.value = null
  resetForm()
  modalVisible.value = true
}

const editJob = (job) => {
  editingJob.value = job
  Object.assign(formData, job)
  if (job.schedule_config.time) {
    scheduleTime.value = dayjs(job.schedule_config.time, 'HH:mm')
  }
  modalVisible.value = true
}

const resetForm = () => {
  Object.assign(formData, {
    name: '',
    description: '',
    template_id: '',
    schedule_type: 'daily',
    schedule_config: {},
    parameters: {
      timeRange: '30d',
      granularity: 'day'
    },
    output_format: 'excel',
    recipients: [],
    enabled: true
  })
  scheduleTime.value = undefined
}

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true

    // 处理调度配置
    if (scheduleTime.value) {
      formData.schedule_config.time = scheduleTime.value.format('HH:mm')
    }

    // 模拟提交
    await new Promise(resolve => setTimeout(resolve, 1000))

    if (editingJob.value) {
      message.success('调度任务更新成功')
    } else {
      message.success('调度任务创建成功')
    }

    modalVisible.value = false
    refreshData()
  } catch (error) {
    console.error('Submit failed:', error)
  } finally {
    submitting.value = false
  }
}

const toggleJobStatus = async (job) => {
  job.updating = true
  try {
    // 模拟状态切换
    await new Promise(resolve => setTimeout(resolve, 500))
    message.success(`任务已${job.enabled ? '启用' : '禁用'}`)
  } catch (error) {
    job.enabled = !job.enabled // 回滚状态
    message.error('状态更新失败')
  } finally {
    job.updating = false
  }
}

const executeJob = async (job) => {
  try {
    message.loading('正在执行任务...', 0)
    // 模拟执行
    await new Promise(resolve => setTimeout(resolve, 2000))
    message.destroy()
    message.success('任务执行成功')
    refreshData()
  } catch (error) {
    message.destroy()
    message.error('任务执行失败')
  }
}

const deleteJob = async (job) => {
  try {
    // 模拟删除
    await new Promise(resolve => setTimeout(resolve, 500))
    message.success('调度任务删除成功')
    refreshData()
  } catch (error) {
    message.error('删除失败')
  }
}

const viewHistory = async (job) => {
  historyLoading.value = true
  historyModalVisible.value = true
  
  try {
    // 模拟加载执行历史
    await new Promise(resolve => setTimeout(resolve, 1000))
    executionHistory.value = [
      {
        id: '1',
        execution_time: '2024-12-10T09:00:00Z',
        status: 'success',
        duration_ms: 2500,
        output_size: 1024000,
        recipients_count: 1
      },
      {
        id: '2',
        execution_time: '2024-12-09T09:00:00Z',
        status: 'failed',
        duration_ms: 1200,
        error_message: '邮件发送失败'
      }
    ]
  } catch (error) {
    message.error('加载执行历史失败')
  } finally {
    historyLoading.value = false
  }
}

const onScheduleTypeChange = () => {
  formData.schedule_config = {}
  scheduleTime.value = undefined
}

const addRecipient = () => {
  formData.recipients.push({
    email: '',
    name: '',
    type: 'to'
  })
}

const removeRecipient = (index) => {
  formData.recipients.splice(index, 1)
}

const filterJobs = () => {
  // 过滤逻辑已在计算属性中实现
}

// 工具函数
const formatDateTime = (dateTime) => {
  return dayjs(dateTime).format('YYYY-MM-DD HH:mm:ss')
}

const formatDuration = (ms) => {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

const getScheduleTypeColor = (type) => {
  const colors = {
    daily: 'blue',
    weekly: 'green',
    monthly: 'orange',
    custom: 'purple'
  }
  return colors[type] || 'default'
}

const getScheduleTypeText = (type) => {
  const texts = {
    daily: '每日',
    weekly: '每周',
    monthly: '每月',
    custom: '自定义'
  }
  return texts[type] || type
}

const getStatusColor = (status) => {
  const colors = {
    success: 'green',
    failed: 'red',
    running: 'blue'
  }
  return colors[status] || 'default'
}

const getStatusText = (status) => {
  const texts = {
    success: '成功',
    failed: '失败',
    running: '运行中'
  }
  return texts[status] || status
}

// 生命周期
onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.report-scheduler {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 24px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #262626;
}

.header-content p {
  margin: 4px 0 0 0;
  color: #8c8c8c;
}

.stats-cards {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.jobs-table-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.schedule-config,
.recipients-config,
.parameters-config {
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #f0f0f0;
}

.recipient-item {
  margin-bottom: 8px;
}

.cron-help {
  margin-top: 4px;
  color: #8c8c8c;
}

.text-muted {
  color: #8c8c8c;
}
</style>
