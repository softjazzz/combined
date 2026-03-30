<template>
  <div class="records-view min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <!-- 页面头部 -->
    <PageHeader
      title="病案管理"
      subtitle="上传、管理和分析医疗病案记录"
      :icon="FileTextOutlined"
      :actions="headerActions"
      :stats="headerStats"
      @action="handleHeaderAction"
    />

    <div class="max-w-7xl mx-auto px-6 pb-6">
      <!-- 上传区域 -->
      <div class="mb-8">
        <a-card
          title="上传病案"
          class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
          :bordered="false"
        >
          <RecordUploadForm
            :loading="isAnalyzing"
            @submit="handleRecordSubmit"
            @cancel="handleUploadCancel"
          />
        </a-card>
      </div>

      <!-- 记录列表 -->
      <a-card
        title="病案记录"
        class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
        :bordered="false"
      >
        <template #extra>
          <a-space>
            <a-select
              v-model:value="statusFilter"
              placeholder="筛选状态"
              style="width: 120px"
              allow-clear
            >
              <a-select-option value="">
                全部
              </a-select-option>
              <a-select-option value="pending">
                待分析
              </a-select-option>
              <a-select-option value="analyzing">
                分析中
              </a-select-option>
              <a-select-option value="completed">
                已完成
              </a-select-option>
              <a-select-option value="failed">
                失败
              </a-select-option>
            </a-select>

            <a-button
              type="primary"
              ghost
              :loading="isLoading"
              @click="refreshRecords"
            >
              <template #icon>
                <ReloadOutlined />
              </template>
              刷新
            </a-button>
          </a-space>
        </template>

        <!-- 加载状态 -->
        <div
          v-if="isLoading"
          class="py-8"
        >
          <LoadingSpinner
            type="medical"
            size="large"
            text="正在加载病案记录..."
          />
        </div>

        <!-- 数据表格 -->
        <a-table
          v-else-if="records.length > 0"
          :columns="tableColumns"
          :data-source="filteredRecords"
          :pagination="paginationConfig"
          row-key="id"
          class="medical-records-table"
        >
          <!-- 患者信息 -->
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'patient'">
              <div class="patient-info">
                <div class="font-medium text-gray-900">
                  {{ asMedicalRecord(record).patient_name }}
                </div>
                <div class="text-sm text-gray-500">
                  {{ asMedicalRecord(record).patient_age }}岁 ·
                  {{
                    asMedicalRecord(record).patient_gender === 'M'
                      ? '男'
                      : asMedicalRecord(record).patient_gender === 'F'
                        ? '女'
                        : '未知'
                  }}
                </div>
              </div>
            </template>

            <!-- 状态标签 -->
            <template v-else-if="column.key === 'status'">
              <a-tag
                :color="getStatusColor(asMedicalRecord(record).status)"
                class="status-tag"
              >
                {{ getStatusText(asMedicalRecord(record).status) }}
              </a-tag>
            </template>

            <!-- 质控评分 -->
            <template v-else-if="column.key === 'qc_score'">
              <div
                v-if="
                  asMedicalRecord(record).qc_score !== null &&
                    asMedicalRecord(record).qc_score !== undefined
                "
                class="score-display"
              >
                <a-progress
                  :percent="asMedicalRecord(record).qc_score"
                  :stroke-color="getScoreColor(asMedicalRecord(record).qc_score)"
                  size="small"
                  :show-info="false"
                  class="mb-1"
                />
                <div class="text-xs text-center">
                  <span class="font-medium">{{ asMedicalRecord(record).qc_score }}分</span>
                  <a-tag
                    v-if="asMedicalRecord(record).qc_grade"
                    :color="getGradeColor(asMedicalRecord(record).qc_grade)"
                    size="small"
                    class="ml-1"
                  >
                    {{ asMedicalRecord(record).qc_grade }}级
                  </a-tag>
                </div>
              </div>
              <span
                v-else
                class="text-gray-400"
              >-</span>
            </template>

            <!-- 操作按钮 -->
            <template v-else-if="column.key === 'actions'">
              <a-space size="small">
                <a-button
                  type="link"
                  size="small"
                  class="action-btn"
                  @click="viewRecord(asMedicalRecord(record))"
                >
                  查看
                </a-button>
                <a-button
                  v-if="asMedicalRecord(record).status === 'completed'"
                  type="link"
                  size="small"
                  class="action-btn"
                  @click="viewAnalysis(asMedicalRecord(record))"
                >
                  分析结果
                </a-button>
                <a-button
                  v-if="asMedicalRecord(record).status === 'failed'"
                  type="link"
                  size="small"
                  :loading="retryingId === asMedicalRecord(record).id"
                  class="action-btn"
                  @click="retryAnalysis(asMedicalRecord(record))"
                >
                  重新分析
                </a-button>
                <a-popconfirm
                  title="确定要删除这条记录吗？"
                  ok-text="确定"
                  cancel-text="取消"
                  @confirm="deleteRecord(asMedicalRecord(record).id)"
                >
                  <a-button
                    type="link"
                    size="small"
                    danger
                    class="action-btn"
                  >
                    删除
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>

        <!-- 空状态 -->
        <EmptyState
          v-else
          type="empty"
          title="暂无病案记录"
          description="还没有上传任何病案记录，立即开始上传吧！"
          :actions="[
            {
              key: 'upload',
              text: '立即上传病案',
              type: 'primary',
              icon: UploadOutlined,
              onClick: scrollToUpload,
            },
          ]"
        />
      </a-card>
    </div>

    <!-- 记录详情抽屉 -->
    <a-drawer
      v-model:open="detailDrawerVisible"
      title="病案详情"
      placement="right"
      :width="800"
      class="detail-drawer"
    >
      <RecordDetailPanel
        v-if="selectedRecord"
        :record="selectedRecord"
        @close="detailDrawerVisible = false"
      />
    </a-drawer>

    <!-- 分析结果抽屉 -->
    <a-drawer
      v-model:open="analysisDrawerVisible"
      title="质控分析结果"
      placement="right"
      :width="900"
      class="analysis-drawer"
    >
      <AnalysisResultPanel
        v-if="selectedRecord"
        :record="selectedRecord"
        @close="analysisDrawerVisible = false"
      />
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  FileTextOutlined,
  UploadOutlined,
  PlusOutlined,
  DownloadOutlined,
  BarChartOutlined,
} from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import RecordUploadForm from '../../components/forms/RecordUploadForm.vue'
import RecordDetailPanel from '../../components/medical/RecordDetailPanel.vue'
import AnalysisResultPanel from '../../components/medical/AnalysisResultPanel.vue'
import PageHeader from '../../components/common/PageHeader.vue'
import LoadingSpinner from '../../components/common/LoadingSpinner.vue'
import EmptyState from '../../components/common/EmptyState.vue'
import {
  getMedicalRecords,
  createMedicalRecord,
  deleteMedicalRecord,
} from '../../api/medical-records'
import { analyzeRecord } from '../../api/qc-analysis-api'
import type {
  MedicalRecord,
  CreateMedicalRecordRequest,
  MedicalRecordStatus,
} from '../../types/medical-records'

// 响应式数据
const records = ref<MedicalRecord[]>([])
const isLoading = ref(false)
const isAnalyzing = ref(false)
const statusFilter = ref<string>('')
const retryingId = ref<string | null>(null)
const asMedicalRecord = (record: Record<string, any>) => record as MedicalRecord

// 抽屉状态
const detailDrawerVisible = ref(false)
const analysisDrawerVisible = ref(false)
const selectedRecord = ref<MedicalRecord | null>(null)

// 页面头部配置
const headerActions = computed(() => [
  {
    key: 'upload',
    text: '上传病案',
    type: 'primary' as const,
    icon: PlusOutlined,
  },
  {
    key: 'export',
    text: '导出数据',
    icon: DownloadOutlined,
  },
  {
    key: 'statistics',
    text: '统计报表',
    icon: BarChartOutlined,
  },
])

const headerStats = computed(() => [
  {
    key: 'total',
    label: '总记录数',
    value: records.value.length,
    icon: FileTextOutlined,
    color: '#1890ff',
  },
  {
    key: 'pending',
    label: '待分析',
    value: records.value.filter((r) => r.status === 'pending').length,
    icon: FileTextOutlined,
    color: '#faad14',
  },
  {
    key: 'analyzing',
    label: '分析中',
    value: records.value.filter((r) => r.status === 'analyzing').length,
    icon: FileTextOutlined,
    color: '#13c2c2',
  },
  {
    key: 'completed',
    label: '已完成',
    value: records.value.filter((r) => r.status === 'completed').length,
    icon: FileTextOutlined,
    color: '#52c41a',
  },
])

// 表格列定义
const tableColumns: TableColumnsType<MedicalRecord> = [
  {
    title: '患者信息',
    key: 'patient',
    width: 150,
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 100,
  },
  {
    title: '记录类型',
    dataIndex: 'record_type',
    key: 'record_type',
    width: 100,
    customRender: ({ text }: { text?: string | null }) => {
      const typeMap = {
        inpatient: '住院',
        outpatient: '门诊',
        emergency: '急诊',
      }
      return (text && typeMap[text as keyof typeof typeMap]) || text || '-'
    },
  },
  {
    title: '入院日期',
    dataIndex: 'admission_date',
    key: 'admission_date',
    width: 120,
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
  },
  {
    title: '质控评分',
    key: 'qc_score',
    width: 150,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 150,
    customRender: ({ text }: { text?: string | null }) => {
      return text ? new Date(text).toLocaleString() : '-'
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right' as const,
  },
]

// 分页配置
const paginationConfig = {
  pageSize: 10,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
}

// 计算属性
const filteredRecords = computed(() => {
  if (!statusFilter.value) return records.value
  return records.value.filter((record) => record.status === statusFilter.value)
})

// 状态相关方法
const getStatusColor = (status: MedicalRecordStatus): string => {
  const colorMap = {
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red',
  }
  return colorMap[status] || 'default'
}

const getStatusText = (status: MedicalRecordStatus): string => {
  const textMap = {
    pending: '待分析',
    analyzing: '分析中',
    completed: '已完成',
    failed: '分析失败',
  }
  return textMap[status] || status
}

const getScoreColor = (score: number): string => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 70) return '#fa8c16'
  return '#f5222d'
}

const getGradeColor = (grade?: string): string => {
  const gradeColorMap = {
    A: 'green',
    B: 'orange',
    C: 'red',
  }
  return gradeColorMap[grade as keyof typeof gradeColorMap] || 'default'
}

// 页面头部操作处理
const handleHeaderAction = (action: { key: string }) => {
  switch (action.key) {
    case 'upload':
      scrollToUpload()
      break
    case 'export':
      // TODO: 导出功能
      message.info('导出功能开发中')
      break
    case 'statistics':
      // TODO: 跳转到统计页面
      message.info('统计功能开发中')
      break
  }
}

// 事件处理方法
const handleRecordSubmit = async (data: CreateMedicalRecordRequest) => {
  try {
    isAnalyzing.value = true

    // 1. 创建医疗记录
    const createResult = await createMedicalRecord(data)

    if (createResult.error || !createResult.data) {
      throw new Error(createResult.error?.message || '创建记录失败')
    }

    const newRecord = createResult.data
    records.value.unshift(newRecord)
    message.success('病案上传成功，正在进行质控分析...')

    // 2. 异步进行AI分析
    analyzeRecord(newRecord.id)
      .then((analysisResult) => {
        if (analysisResult.error) {
          console.error('分析失败:', analysisResult.error)
          message.error('质控分析失败')

          // 更新记录状态为失败
          const record = records.value.find((r) => r.id === newRecord.id)
          if (record) {
            record.status = 'failed'
          }
        } else {
          message.success('质控分析完成')

          // 更新记录信息
          const record = records.value.find((r) => r.id === newRecord.id)
          if (record && analysisResult.data) {
            record.status = 'completed'
            record.qc_score = analysisResult.data.overallScore
            record.qc_grade = analysisResult.data.grade
            record.updated_at = new Date().toISOString()
          }
        }
      })
      .catch((error) => {
        console.error('分析异常:', error)
        message.error('质控分析异常')
      })
  } catch (error) {
    console.error('提交失败:', error)
    message.error(error instanceof Error ? error.message : '病案提交失败，请重试')
  } finally {
    isAnalyzing.value = false
  }
}

const handleUploadCancel = () => {
  console.log('取消上传')
}

const viewRecord = (record: MedicalRecord) => {
  selectedRecord.value = record
  detailDrawerVisible.value = true
}

const viewAnalysis = (record: MedicalRecord) => {
  selectedRecord.value = record
  analysisDrawerVisible.value = true
}

const retryAnalysis = async (record: MedicalRecord) => {
  try {
    retryingId.value = record.id
    record.status = 'analyzing'

    // 调用重新分析API
    const analysisResult = await analyzeRecord(record.id)

    if (analysisResult.error) {
      throw new Error(analysisResult.error.message)
    }

    if (analysisResult.data) {
      record.status = 'completed'
      record.qc_score = analysisResult.data.overallScore
      record.qc_grade = analysisResult.data.grade
      record.updated_at = new Date().toISOString()
      message.success('重新分析完成')
    }
  } catch (error) {
    console.error('重新分析失败:', error)
    record.status = 'failed'
    message.error(error instanceof Error ? error.message : '重新分析失败')
  } finally {
    retryingId.value = null
  }
}

const deleteRecord = async (recordId: string) => {
  try {
    const result = await deleteMedicalRecord(recordId)

    if (result.error) {
      throw new Error(result.error.message)
    }

    // 从列表中移除
    records.value = records.value.filter((r) => r.id !== recordId)
    message.success('删除成功')
  } catch (error) {
    console.error('删除失败:', error)
    message.error(error instanceof Error ? error.message : '删除失败')
  }
}

const refreshRecords = async () => {
  try {
    isLoading.value = true

    const result = await getMedicalRecords({
      limit: 50,
      offset: 0,
    })

    if (result.error) {
      throw new Error(result.error.message)
    }

    records.value = result.data || []
    message.success('刷新成功')
  } catch (error) {
    console.error('刷新失败:', error)
    message.error(error instanceof Error ? error.message : '刷新失败')
  } finally {
    isLoading.value = false
  }
}

const scrollToUpload = () => {
  // 滚动到页面顶部的上传表单
  console.log('滚动到上传表单')
}

// 组件挂载时获取数据
onMounted(() => {
  refreshRecords()
})
</script>

<style scoped>
.records-view {
  min-height: 100vh;
}

:deep(.medical-records-table .ant-table-thead > tr > th) {
  @apply bg-gray-50 font-semibold text-gray-800;
}

:deep(.medical-records-table .ant-table-tbody > tr:hover > td) {
  @apply bg-blue-50;
}

:deep(.ant-drawer-header) {
  @apply border-b border-gray-200;
}

:deep(.ant-empty-description) {
  @apply text-gray-500;
}
</style>
