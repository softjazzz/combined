<template>
  <div class="feedbacks-view">
    <!-- 页面头部 -->
    <a-page-header
      title="反馈记录"
      sub-title="查看所有质控评估反馈"
      @back="() => $router.push('/demo/lx33')"
    >
      <template #extra>
        <a-button
          type="primary"
          @click="() => $router.push('/demo/lx33')"
        >
          <LeftOutlined /> 返回规则列表
        </a-button>
      </template>
    </a-page-header>

    <!-- 统计卡片 -->
    <a-row
      :gutter="16"
      class="stats-row"
    >
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="总反馈数"
            :value="stats.total_feedbacks"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix>
              <MessageOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="正确反馈"
            :value="stats.correct_feedbacks"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix>
              <CheckCircleOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="错误反馈"
            :value="stats.incorrect_feedbacks"
            :value-style="{ color: '#ff4d4f' }"
          >
            <template #prefix>
              <CloseCircleOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card>
          <a-statistic
            title="准确率"
            :value="(stats.accuracy_rate * 100).toFixed(1)"
            suffix="%"
            :value-style="{ color: stats.accuracy_rate >= 0.8 ? '#52c41a' : '#faad14' }"
          >
            <template #prefix>
              <TrophyOutlined />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 筛选和搜索 -->
    <a-card class="filter-card">
      <a-form layout="inline">
        <a-form-item label="反馈类型">
          <a-select
            v-model:value="filters.feedbackType"
            placeholder="全部"
            style="width: 150px"
            @change="handleSearch"
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="correct">
              正确
            </a-select-option>
            <a-select-option value="incorrect">
              错误
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="错误类别">
          <a-select
            v-model:value="filters.errorCategory"
            placeholder="全部"
            style="width: 200px"
            @change="handleSearch"
          >
            <a-select-option value="">
              全部
            </a-select-option>
            <a-select-option value="false_positive">
              误报
            </a-select-option>
            <a-select-option value="false_negative">
              漏报
            </a-select-option>
            <a-select-option value="wrong_reasoning">
              推理错误
            </a-select-option>
            <a-select-option value="incomplete_check">
              检查不完整
            </a-select-option>
            <a-select-option value="rule_ambiguity">
              规则歧义
            </a-select-option>
            <a-select-option value="other">
              其他
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="规则编号">
          <a-input
            v-model:value="filters.ruleCode"
            placeholder="输入规则编号"
            style="width: 150px"
            @press-enter="handleSearch"
          />
        </a-form-item>

        <a-form-item>
          <a-space>
            <a-button
              type="primary"
              @click="handleSearch"
            >
              <SearchOutlined /> 搜索
            </a-button>
            <a-button @click="handleReset">
              <ReloadOutlined /> 重置
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 反馈记录表格 -->
    <a-card class="table-card">
      <a-table
        :columns="columns"
        :data-source="feedbacks"
        :loading="loading"
        :pagination="pagination"
        :scroll="{ x: 1500 }"
        row-key="feedback_id"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'feedback_type'">
            <a-tag :color="record.feedback_type === 'correct' ? 'success' : 'error'">
              <CheckCircleOutlined v-if="record.feedback_type === 'correct'" />
              <CloseCircleOutlined v-else />
              {{ record.feedback_type === 'correct' ? '正确' : '错误' }}
            </a-tag>
          </template>

          <template v-if="column.key === 'error_category'">
            <a-tag
              v-if="record.error_category"
              color="orange"
            >
              {{ errorCategoryText(record.error_category) }}
            </a-tag>
            <span v-else>-</span>
          </template>

          <template v-if="column.key === 'evaluation_result'">
            <a-tag :color="record.evaluation_result ? 'success' : 'error'">
              {{ record.evaluation_result ? '合规' : '不合规' }}
            </a-tag>
          </template>

          <template v-if="column.key === 'error_detail'">
            <a-typography-paragraph
              v-if="record.error_detail"
              :ellipsis="{ rows: 2, expandable: true, symbol: '展开' }"
              :content="record.error_detail"
              style="margin-bottom: 0"
            />
            <span v-else>-</span>
          </template>

          <template v-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>

          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button
                type="link"
                size="small"
                @click="handleViewDetail(record)"
              >
                <EyeOutlined /> 查看详情
              </a-button>
              <a-button
                type="link"
                size="small"
                danger
                @click="handleDelete(record)"
              >
                <DeleteOutlined /> 删除
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情弹窗 -->
    <a-modal
      v-model:open="detailVisible"
      width="900px"
      :footer="null"
      :body-style="{ padding: '24px' }"
    >
      <template #title>
        <div class="modal-header">
          <FileTextOutlined class="modal-icon" />
          <span>反馈详情</span>
        </div>
      </template>

      <div
        v-if="currentFeedback"
        class="feedback-detail"
      >
        <!-- 基本信息卡片 -->
        <a-card
          class="detail-card basic-info-card"
          :bordered="false"
        >
          <template #title>
            <div class="card-header">
              <InfoCircleOutlined class="card-icon" />
              <span>基本信息</span>
            </div>
          </template>

          <div class="info-content">
            <div class="info-row">
              <div class="info-item">
                <span class="info-label">规则编号</span>
                <a-tag
                  color="blue"
                  class="info-tag"
                >
                  {{ currentFeedback.rule_code }}
                </a-tag>
              </div>
              <div class="info-item">
                <span class="info-label">评估结果</span>
                <a-tag
                  :color="currentFeedback.evaluation_result ? 'success' : 'error'"
                  class="info-tag result-tag"
                >
                  <CheckCircleOutlined v-if="currentFeedback.evaluation_result" />
                  <CloseCircleOutlined v-else />
                  {{ currentFeedback.evaluation_result ? '合规' : '不合规' }}
                </a-tag>
              </div>
              <div class="info-item">
                <span class="info-label">反馈类型</span>
                <a-tag
                  :color="currentFeedback.feedback_type === 'correct' ? 'success' : 'error'"
                  class="info-tag result-tag"
                >
                  <CheckCircleOutlined v-if="currentFeedback.feedback_type === 'correct'" />
                  <CloseCircleOutlined v-else />
                  {{ currentFeedback.feedback_type === 'correct' ? '正确' : '错误' }}
                </a-tag>
              </div>
            </div>

            <div class="info-row">
              <div class="info-item full-width">
                <span class="info-label">规则名称</span>
                <span class="info-value">{{ currentFeedback.rule_name }}</span>
              </div>
            </div>

            <div class="info-row">
              <div class="info-item full-width">
                <span class="info-label">文档名称</span>
                <span class="info-value">{{ currentFeedback.document_name }}</span>
              </div>
            </div>

            <div
              v-if="currentFeedback.error_category"
              class="info-row"
            >
              <div class="info-item">
                <span class="info-label">错误类别</span>
                <a-tag
                  color="orange"
                  class="info-tag"
                >
                  {{ errorCategoryText(currentFeedback.error_category) }}
                </a-tag>
              </div>
              <div
                v-if="currentFeedback.feedback_by"
                class="info-item"
              >
                <span class="info-label">反馈人</span>
                <span class="info-value">{{ currentFeedback.feedback_by }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">创建时间</span>
                <span class="info-value">{{ formatDate(currentFeedback.created_at) }}</span>
              </div>
            </div>

            <div
              v-else
              class="info-row"
            >
              <div
                v-if="currentFeedback.feedback_by"
                class="info-item"
              >
                <span class="info-label">反馈人</span>
                <span class="info-value">{{ currentFeedback.feedback_by }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">创建时间</span>
                <span class="info-value">{{ formatDate(currentFeedback.created_at) }}</span>
              </div>
            </div>

            <div class="info-row">
              <div class="info-item full-width">
                <span class="info-label">反馈ID</span>
                <span class="info-value feedback-id">{{ currentFeedback.feedback_id }}</span>
              </div>
            </div>
          </div>
        </a-card>

        <!-- 错误详情 -->
        <a-card
          v-if="currentFeedback.error_detail"
          class="detail-card"
          :bordered="false"
        >
          <template #title>
            <div class="card-header">
              <ExclamationCircleOutlined class="card-icon" />
              <span>错误详情</span>
            </div>
          </template>
          <div class="detail-section">
            <div class="section-content error-detail-box">
              {{ currentFeedback.error_detail }}
            </div>
          </div>
        </a-card>

        <!-- 补充证据 -->
        <a-card
          v-if="currentFeedback.evidence"
          class="detail-card"
          :bordered="false"
        >
          <template #title>
            <div class="card-header">
              <FileSearchOutlined class="card-icon" />
              <span>补充证据</span>
            </div>
          </template>
          <div class="detail-section">
            <div class="section-content evidence-box">
              {{ currentFeedback.evidence }}
            </div>
          </div>
        </a-card>

        <!-- 病历原文 -->
        <a-card
          v-if="currentFeedback.medical_text"
          class="detail-card"
          :bordered="false"
        >
          <template #title>
            <div class="card-header">
              <FileTextOutlined class="card-icon" />
              <span>病历原文</span>
            </div>
          </template>
          <div class="detail-section">
            <div class="section-content medical-text-box">
              {{ currentFeedback.medical_text }}
            </div>
          </div>
        </a-card>
      </div>
    </a-modal>

    <!-- 管理员密码验证弹窗 -->
    <a-modal
      v-model:open="passwordVisible"
      title="管理员身份验证"
      :confirm-loading="passwordLoading"
      @ok="handlePasswordSubmit"
      @cancel="handlePasswordCancel"
    >
      <a-alert
        message="权限验证"
        description="删除反馈记录需要管理员权限，请输入管理员密码进行验证。"
        type="warning"
        show-icon
        style="margin-bottom: 16px"
      />
      <a-form layout="vertical">
        <a-form-item label="管理员密码">
          <a-input-password
            v-model:value="adminPassword"
            placeholder="请输入管理员密码"
            @press-enter="handlePasswordSubmit"
          />
        </a-form-item>
      </a-form>
      <template v-if="pendingDeleteRecord">
        <a-divider style="margin: 12px 0" />
        <a-descriptions
          :column="1"
          size="small"
        >
          <a-descriptions-item label="即将删除">
            <a-tag color="red">
              {{ pendingDeleteRecord.rule_code }}
            </a-tag>
            {{ pendingDeleteRecord.rule_name }}
          </a-descriptions-item>
        </a-descriptions>
      </template>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  LeftOutlined,
  MessageOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  TrophyOutlined,
  SearchOutlined,
  ReloadOutlined,
  EyeOutlined,
  DeleteOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined
} from '@ant-design/icons-vue'
import type { FeedbackRecord, FeedbackStats, ErrorCategory } from '@/types/demo'
import type { TablePaginationConfig } from 'ant-design-vue'

const router = useRouter()

// 数据状态
const loading = ref(false)
const feedbacks = ref<FeedbackRecord[]>([])
const stats = ref<FeedbackStats>({
  total_feedbacks: 0,
  correct_feedbacks: 0,
  incorrect_feedbacks: 0,
  accuracy_rate: 0
})

// 筛选条件
const filters = reactive({
  feedbackType: '',
  errorCategory: '',
  ruleCode: ''
})

// 分页配置
const pagination = ref<TablePaginationConfig>({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total) => `共 ${total} 条记录`
})

// 详情弹窗
const detailVisible = ref(false)
const currentFeedback = ref<FeedbackRecord | null>(null)

// 密码验证弹窗
const passwordVisible = ref(false)
const adminPassword = ref('')
const passwordLoading = ref(false)
const pendingDeleteRecord = ref<FeedbackRecord | null>(null)

// 表格列配置
const columns = [
  {
    title: '规则编号',
    dataIndex: 'rule_code',
    key: 'rule_code',
    width: 120
  },
  {
    title: '规则名称',
    dataIndex: 'rule_name',
    key: 'rule_name',
    width: 200,
    ellipsis: true
  },
  {
    title: '文档名称',
    dataIndex: 'document_name',
    key: 'document_name',
    width: 150,
    ellipsis: true
  },
  {
    title: '评估结果',
    key: 'evaluation_result',
    width: 100,
    align: 'center'
  },
  {
    title: '反馈类型',
    key: 'feedback_type',
    width: 100,
    align: 'center'
  },
  {
    title: '错误类别',
    key: 'error_category',
    width: 120,
    align: 'center'
  },
  {
    title: '错误详情',
    key: 'error_detail',
    width: 250
  },
  {
    title: '反馈人',
    dataIndex: 'feedback_by',
    key: 'feedback_by',
    width: 100
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 150
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    align: 'center',
    fixed: 'right'
  }
]

// 错误类别文本映射
const errorCategoryText = (category: ErrorCategory) => {
  const textMap = {
    false_positive: '误报',
    false_negative: '漏报',
    wrong_reasoning: '推理错误',
    incomplete_check: '检查不完整',
    rule_ambiguity: '规则歧义',
    other: '其他'
  }
  return textMap[category] || category
}

// 格式化日期
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 加载反馈数据
const loadFeedbacks = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: pagination.value.current?.toString() || '1',
      page_size: pagination.value.pageSize?.toString() || '10',
      ...(filters.feedbackType && { feedback_type: filters.feedbackType }),
      ...(filters.errorCategory && { error_category: filters.errorCategory }),
      ...(filters.ruleCode && { rule_code: filters.ruleCode })
    })

    const response = await fetch(`/api/v1/demo/feedbacks?${params}`)
    const data = await response.json()

    if (data.success) {
      feedbacks.value = data.data || []
      pagination.value.total = data.total || 0
    } else {
      message.error('加载反馈数据失败')
    }
  } catch (error) {
    console.error('加载反馈数据失败:', error)
    message.error('加载反馈数据失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    const response = await fetch('/api/v1/demo/feedbacks/stats')
    const data = await response.json()

    if (data.success) {
      stats.value = data.data
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 搜索
const handleSearch = () => {
  pagination.value.current = 1
  loadFeedbacks()
}

// 重置筛选
const handleReset = () => {
  filters.feedbackType = ''
  filters.errorCategory = ''
  filters.ruleCode = ''
  pagination.value.current = 1
  loadFeedbacks()
}

// 表格变化处理
const handleTableChange = (pag: TablePaginationConfig) => {
  pagination.value.current = pag.current
  pagination.value.pageSize = pag.pageSize
  loadFeedbacks()
}

// 查看详情
const handleViewDetail = (record: FeedbackRecord) => {
  currentFeedback.value = record
  detailVisible.value = true
}

// 删除反馈记录
const handleDelete = (record: FeedbackRecord) => {
  pendingDeleteRecord.value = record
  adminPassword.value = ''
  passwordVisible.value = true
}

// 验证管理员密码
const handlePasswordSubmit = async () => {
  if (!adminPassword.value) {
    message.error('请输入管理员密码')
    return
  }

  passwordLoading.value = true
  try {
    // 硬编码验证密码
    if (adminPassword.value === 'admin888') {
      // 密码验证成功，执行删除
      passwordVisible.value = false
      await confirmDelete()
    } else {
      message.error('管理员密码错误')
    }
  } catch (error) {
    console.error('密码验证失败:', error)
    message.error('密码验证失败，请稍后重试')
  } finally {
    passwordLoading.value = false
  }
}

// 确认删除
const confirmDelete = async () => {
  if (!pendingDeleteRecord.value) return

  const record = pendingDeleteRecord.value
  try {
    const response = await fetch(`/api/v1/demo/feedbacks/${record.feedback_id}`, {
      method: 'DELETE'
    })

    const data = await response.json()

    if (data.success) {
      message.success('删除成功')
      // 刷新列表和统计
      await loadFeedbacks()
      await loadStats()
    } else {
      message.error(data.error || '删除失败')
    }
  } catch (error) {
    console.error('删除失败:', error)
    message.error('删除失败，请稍后重试')
  } finally {
    pendingDeleteRecord.value = null
  }
}

// 取消密码验证
const handlePasswordCancel = () => {
  passwordVisible.value = false
  adminPassword.value = ''
  pendingDeleteRecord.value = null
}

// 组件挂载时加载数据
onMounted(() => {
  loadFeedbacks()
  loadStats()
})
</script>

<style scoped lang="less">
.feedbacks-view {
  .stats-row {
    margin-bottom: 24px;
  }

  .filter-card {
    margin-bottom: 24px;
  }

  .table-card {
    :deep(.ant-table) {
      font-size: 13px;
    }
  }
}

// 详情弹窗样式
.modal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;

  .modal-icon {
    font-size: 18px;
    color: #1890ff;
    -webkit-text-fill-color: #1890ff;
  }
}

.feedback-detail {
  .detail-card {
    margin-bottom: 16px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    transition: all 0.3s ease;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    &:last-child {
      margin-bottom: 0;
    }

    :deep(.ant-card-head) {
      background: linear-gradient(135deg, #f0f5ff 0%, #e6f4ff 100%);
      border-bottom: 2px solid #1890ff;
      padding: 12px 20px;
      border-radius: 8px 8px 0 0;
    }

    :deep(.ant-card-body) {
      padding: 20px;
    }
  }

  .basic-info-card {
    :deep(.ant-card-head) {
      background: linear-gradient(135deg, #f0f9ff 0%, #e6f7ff 100%);
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 600;
    color: #1890ff;

    .card-icon {
      font-size: 16px;
    }
  }

  .info-content {
    .info-row {
      display: flex;
      gap: 24px;
      margin-bottom: 16px;
      flex-wrap: wrap;

      &:last-child {
        margin-bottom: 0;
      }
    }

    .info-item {
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      min-width: 200px;

      &.full-width {
        flex: 1 1 100%;
      }

      .info-label {
        font-size: 14px;
        color: #666;
        font-weight: 500;
        min-width: 70px;
      }

      .info-value {
        font-size: 14px;
        color: #262626;
        font-weight: 500;

        &.feedback-id {
          font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
          font-size: 12px;
          color: #8c8c8c;
          word-break: break-all;
        }
      }

      .info-tag {
        font-size: 13px;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: 500;

        &.result-tag {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 6px 16px;
          font-size: 14px;
          font-weight: 600;
        }
      }
    }
  }

  .detail-section {
    .section-content {
      padding: 16px;
      border-radius: 6px;
      font-size: 14px;
      line-height: 1.8;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .error-detail-box {
      background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
      border: 1px solid #ffd591;
      color: #ad6800;
    }

    .evidence-box {
      background: linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%);
      border: 1px solid #ffd591;
      color: #ad6800;
    }

    .medical-text-box {
      background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%);
      border: 1px solid #d9d9d9;
      color: #595959;
      font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
      font-size: 13px;
      max-height: 400px;
      overflow-y: auto;

      &::-webkit-scrollbar {
        width: 8px;
      }

      &::-webkit-scrollbar-track {
        background: #f0f0f0;
        border-radius: 4px;
      }

      &::-webkit-scrollbar-thumb {
        background: #bfbfbf;
        border-radius: 4px;

        &:hover {
          background: #999;
        }
      }
    }
  }
}
</style>
