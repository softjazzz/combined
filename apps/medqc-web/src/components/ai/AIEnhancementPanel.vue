<template>
  <div class="ai-enhancement-panel">
    <a-card
      title="AI增强功能管理"
      class="mb-6"
    >
      <template #extra>
        <a-space>
          <a-button
            type="primary"
            :loading="loading"
            @click="refreshData"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新数据
          </a-button>
          <a-button @click="showSettings = true">
            <template #icon>
              <SettingOutlined />
            </template>
            设置
          </a-button>
        </a-space>
      </template>

      <!-- 功能概览 -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <a-card
          size="small"
          class="stat-card"
        >
          <a-statistic
            title="学习记录"
            :value="stats.totalRecords"
            suffix="条"
            :value-style="{ color: '#1890ff' }"
          />
          <div class="mt-2">
            <a-progress
              :percent="stats.learningProgress"
              size="small"
            />
          </div>
        </a-card>

        <a-card
          size="small"
          class="stat-card"
        >
          <a-statistic
            title="知识库条目"
            :value="stats.knowledgeBaseSize"
            suffix="个"
            :value-style="{ color: '#52c41a' }"
          />
          <div class="mt-2">
            <a-tag color="green">
              活跃模式: {{ stats.activePatterns }}
            </a-tag>
          </div>
        </a-card>

        <a-card
          size="small"
          class="stat-card"
        >
          <a-statistic
            title="性能评分"
            :value="stats.performanceScore"
            suffix="%"
            :value-style="{ color: getPerformanceColor(stats.performanceScore) }"
          />
          <div class="mt-2">
            <a-badge
              :status="getPerformanceStatus(stats.performanceScore)"
              :text="getPerformanceText(stats.performanceScore)"
            />
          </div>
        </a-card>

        <a-card
          size="small"
          class="stat-card"
        >
          <a-statistic
            title="学习任务"
            :value="stats.pendingTasks"
            suffix="个"
            :value-style="{ color: '#faad14' }"
          />
          <div class="mt-2">
            <a-space>
              <a-tag color="processing">
                进行中: {{ stats.runningTasks }}
              </a-tag>
              <a-tag color="success">
                已完成: {{ stats.completedTasks }}
              </a-tag>
            </a-space>
          </div>
        </a-card>
      </div>

      <!-- 功能标签页 -->
      <a-tabs
        v-model:active-key="activeTab"
        type="card"
      >
        <!-- 智能学习 -->
        <a-tab-pane
          key="learning"
          tab="智能学习"
        >
          <div class="learning-panel">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold">
                学习记录管理
              </h3>
              <a-button
                type="primary"
                @click="showLearningDialog = true"
              >
                <template #icon>
                  <PlusOutlined />
                </template>
                添加学习记录
              </a-button>
            </div>

            <!-- 学习记录列表 -->
            <a-table
              :columns="learningColumns"
              :data-source="learningRecords"
              :pagination="paginationConfig"
              :loading="loading"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'improvement'">
                  <a-tag
                    :color="
                      record.improvement > 0 ? 'green' : record.improvement < 0 ? 'red' : 'blue'
                    "
                  >
                    {{ record.improvement > 0 ? '+' : '' }}{{ record.improvement }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'actions'">
                  <a-space>
                    <a-button
                      type="link"
                      size="small"
                      @click="viewLearningDetail(record)"
                    >
                      详情
                    </a-button>
                    <a-button
                      type="link"
                      size="small"
                      @click="analyzeLearningPattern(record)"
                    >
                      分析
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- 知识库管理 -->
        <a-tab-pane
          key="knowledge"
          tab="知识库"
        >
          <div class="knowledge-panel">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold">
                知识库管理
              </h3>
              <a-space>
                <a-select
                  v-model:value="selectedCategory"
                  placeholder="选择类别"
                  style="width: 150px"
                  @change="filterKnowledgeBase"
                >
                  <a-select-option value="">
                    全部
                  </a-select-option>
                  <a-select-option value="completeness">
                    完整性
                  </a-select-option>
                  <a-select-option value="consistency">
                    一致性
                  </a-select-option>
                  <a-select-option value="rationality">
                    合理性
                  </a-select-option>
                  <a-select-option value="timeliness">
                    时效性
                  </a-select-option>
                  <a-select-option value="compliance">
                    合规性
                  </a-select-option>
                </a-select>
                <a-button
                  type="primary"
                  @click="showKnowledgeDialog = true"
                >
                  <template #icon>
                    <PlusOutlined />
                  </template>
                  添加知识条目
                </a-button>
              </a-space>
            </div>

            <!-- 知识库列表 -->
            <a-table
              :columns="knowledgeColumns"
              :data-source="filteredKnowledgeBase"
              :pagination="paginationConfig"
              :loading="loading"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'confidence'">
                  <a-progress
                    :percent="Math.round(record.confidence * 100)"
                    size="small"
                    :stroke-color="getConfidenceColor(record.confidence)"
                  />
                </template>
                <template v-else-if="column.key === 'usage'">
                  <a-space>
                    <a-tag color="blue">
                      {{ record.usageCount }}次
                    </a-tag>
                    <a-tag color="green">
                      {{ Math.round(record.successRate * 100) }}%
                    </a-tag>
                  </a-space>
                </template>
                <template v-else-if="column.key === 'actions'">
                  <a-space>
                    <a-button
                      type="link"
                      size="small"
                      @click="editKnowledgeEntry(record)"
                    >
                      编辑
                    </a-button>
                    <a-button
                      type="link"
                      size="small"
                      @click="testKnowledgeEntry(record)"
                    >
                      测试
                    </a-button>
                    <a-popconfirm
                      title="确定删除此知识条目吗？"
                      @confirm="deleteKnowledgeEntry(record)"
                    >
                      <a-button
                        type="link"
                        size="small"
                        danger
                      >
                        删除
                      </a-button>
                    </a-popconfirm>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- 性能监控 -->
        <a-tab-pane
          key="performance"
          tab="性能监控"
        >
          <div class="performance-panel">
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <!-- 性能趋势图 -->
              <a-card
                title="性能趋势"
                size="small"
              >
                <div
                  ref="performanceChart"
                  class="h-64"
                />
              </a-card>

              <!-- 准确率分析 -->
              <a-card
                title="准确率分析"
                size="small"
              >
                <div
                  ref="accuracyChart"
                  class="h-64"
                />
              </a-card>

              <!-- 处理时间分析 -->
              <a-card
                title="处理时间分析"
                size="small"
              >
                <div
                  ref="timingChart"
                  class="h-64"
                />
              </a-card>

              <!-- 用户满意度 -->
              <a-card
                title="用户满意度"
                size="small"
              >
                <div
                  ref="satisfactionChart"
                  class="h-64"
                />
              </a-card>
            </div>

            <!-- 性能指标详情 -->
            <a-card
              title="详细指标"
              size="small"
              class="mt-6"
            >
              <a-table
                :columns="metricsColumns"
                :data-source="performanceMetrics"
                :pagination="false"
                size="small"
              >
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'value'">
                    <a-progress
                      :percent="getMetricPercent(record.value, record.type)"
                      size="small"
                      :stroke-color="getMetricColor(record.value, record.type)"
                    />
                    <span class="ml-2">{{ formatMetricValue(record.value, record.type) }}</span>
                  </template>
                  <template v-else-if="column.key === 'trend'">
                    <a-tag :color="record.trend > 0 ? 'green' : record.trend < 0 ? 'red' : 'blue'">
                      {{ record.trend > 0 ? '↑' : record.trend < 0 ? '↓' : '→' }}
                      {{ Math.abs(record.trend) }}%
                    </a-tag>
                  </template>
                </template>
              </a-table>
            </a-card>
          </div>
        </a-tab-pane>

        <!-- 学习任务 -->
        <a-tab-pane
          key="tasks"
          tab="学习任务"
        >
          <div class="tasks-panel">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold">
                学习任务管理
              </h3>
              <a-space>
                <a-select
                  v-model:value="selectedTaskType"
                  placeholder="任务类型"
                  style="width: 150px"
                  @change="filterTasks"
                >
                  <a-select-option value="">
                    全部
                  </a-select-option>
                  <a-select-option value="feedback_learning">
                    反馈学习
                  </a-select-option>
                  <a-select-option value="pattern_recognition">
                    模式识别
                  </a-select-option>
                  <a-select-option value="performance_optimization">
                    性能优化
                  </a-select-option>
                </a-select>
                <a-button
                  type="primary"
                  @click="createLearningTask"
                >
                  <template #icon>
                    <PlusOutlined />
                  </template>
                  创建任务
                </a-button>
              </a-space>
            </div>

            <!-- 任务列表 -->
            <a-table
              :columns="tasksColumns"
              :data-source="filteredTasks"
              :pagination="paginationConfig"
              :loading="loading"
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-badge
                    :status="getTaskStatus(record.status)"
                    :text="getTaskStatusText(record.status)"
                  />
                </template>
                <template v-else-if="column.key === 'priority'">
                  <a-tag :color="getPriorityColor(record.priority)">
                    {{ getPriorityText(record.priority) }}
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'actions'">
                  <a-space>
                    <a-button
                      type="link"
                      size="small"
                      @click="viewTaskDetail(record)"
                    >
                      详情
                    </a-button>
                    <a-button
                      type="link"
                      size="small"
                      :disabled="record.status !== 'pending'"
                      @click="executeTask(record)"
                    >
                      执行
                    </a-button>
                    <a-popconfirm
                      title="确定取消此任务吗？"
                      @confirm="cancelTask(record)"
                    >
                      <a-button
                        type="link"
                        size="small"
                        danger
                        :disabled="record.status !== 'pending'"
                      >
                        取消
                      </a-button>
                    </a-popconfirm>
                  </a-space>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 学习记录对话框 -->
    <a-modal
      v-model:open="showLearningDialog"
      title="添加学习记录"
      @ok="submitLearningRecord"
      @cancel="resetLearningForm"
    >
      <a-form
        :model="learningForm"
        layout="vertical"
      >
        <a-form-item
          label="病案记录ID"
          required
        >
          <a-input
            v-model:value="learningForm.recordId"
            placeholder="请输入病案记录ID"
          />
        </a-form-item>
        <a-form-item
          label="原始评分"
          required
        >
          <a-input-number
            v-model:value="learningForm.originalScore"
            :min="0"
            :max="100"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item
          label="修正评分"
          required
        >
          <a-input-number
            v-model:value="learningForm.reviewedScore"
            :min="0"
            :max="100"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="反馈内容">
          <a-textarea
            v-model:value="learningForm.feedback"
            placeholder="请输入反馈内容"
            :rows="4"
          />
        </a-form-item>
        <a-form-item label="纠正项目">
          <a-select
            v-model:value="learningForm.corrections"
            mode="tags"
            placeholder="选择或输入纠正项目"
            style="width: 100%"
          >
            <a-select-option value="评分调整">
              评分调整
            </a-select-option>
            <a-select-option value="问题识别">
              问题识别
            </a-select-option>
            <a-select-option value="建议优化">
              建议优化
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 知识库对话框 -->
    <a-modal
      v-model:open="showKnowledgeDialog"
      title="添加知识条目"
      @ok="submitKnowledgeEntry"
      @cancel="resetKnowledgeForm"
    >
      <a-form
        :model="knowledgeForm"
        layout="vertical"
      >
        <a-form-item
          label="类别"
          required
        >
          <a-select
            v-model:value="knowledgeForm.category"
            placeholder="选择类别"
          >
            <a-select-option value="completeness">
              完整性
            </a-select-option>
            <a-select-option value="consistency">
              一致性
            </a-select-option>
            <a-select-option value="rationality">
              合理性
            </a-select-option>
            <a-select-option value="timeliness">
              时效性
            </a-select-option>
            <a-select-option value="compliance">
              合规性
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item
          label="模式描述"
          required
        >
          <a-textarea
            v-model:value="knowledgeForm.pattern"
            placeholder="请输入模式描述"
            :rows="4"
          />
        </a-form-item>
        <a-form-item
          label="置信度"
          required
        >
          <a-slider
            v-model:value="knowledgeForm.confidence"
            :min="0"
            :max="1"
            :step="0.1"
            :marks="{ 0: '0%', 0.5: '50%', 1: '100%' }"
          />
        </a-form-item>
        <a-form-item label="元数据">
          <a-textarea
            v-model:value="knowledgeForm.metadata"
            placeholder="请输入JSON格式的元数据"
            :rows="3"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 设置对话框 -->
    <a-modal
      v-model:open="showSettings"
      title="AI增强功能设置"
      @ok="saveSettings"
      @cancel="resetSettings"
    >
      <a-form
        :model="settingsForm"
        layout="vertical"
      >
        <a-form-item label="反馈学习">
          <a-switch v-model:checked="settingsForm.enableFeedbackLearning" />
          <span class="ml-2">启用基于用户反馈的学习</span>
        </a-form-item>
        <a-form-item label="上下文学习">
          <a-switch v-model:checked="settingsForm.enableContextualLearning" />
          <span class="ml-2">启用上下文感知学习</span>
        </a-form-item>
        <a-form-item label="模式识别">
          <a-switch v-model:checked="settingsForm.enablePatternRecognition" />
          <span class="ml-2">启用自动模式识别</span>
        </a-form-item>
        <a-form-item label="自适应评分">
          <a-switch v-model:checked="settingsForm.adaptiveScoring" />
          <span class="ml-2">启用自适应评分调整</span>
        </a-form-item>
        <a-form-item label="个性化建议">
          <a-switch v-model:checked="settingsForm.personalizedRecommendations" />
          <span class="ml-2">启用个性化建议生成</span>
        </a-form-item>
        <a-form-item label="学习频率">
          <a-select v-model:value="settingsForm.learningFrequency">
            <a-select-option value="realtime">
              实时
            </a-select-option>
            <a-select-option value="hourly">
              每小时
            </a-select-option>
            <a-select-option value="daily">
              每天
            </a-select-option>
            <a-select-option value="weekly">
              每周
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { message } from 'ant-design-vue'
import { ReloadOutlined, SettingOutlined, PlusOutlined } from '@ant-design/icons-vue'
import * as echarts from 'echarts'

// 响应式数据
const loading = ref(false)
const activeTab = ref('learning')
const showLearningDialog = ref(false)
const showKnowledgeDialog = ref(false)
const showSettings = ref(false)
const selectedCategory = ref('')
const selectedTaskType = ref('')

// 统计数据
const stats = reactive({
  totalRecords: 1250,
  learningProgress: 85,
  knowledgeBaseSize: 156,
  activePatterns: 89,
  performanceScore: 88.5,
  pendingTasks: 12,
  runningTasks: 3,
  completedTasks: 145,
})

// 学习记录
const learningRecords = ref([
  {
    id: '1',
    recordId: 'REC001',
    originalScore: 85,
    reviewedScore: 92,
    improvement: 7,
    feedback: '诊断描述需要更详细',
    reviewerId: 'Dr. Zhang',
    timestamp: '2024-01-15 14:30:00',
  },
  {
    id: '2',
    recordId: 'REC002',
    originalScore: 78,
    reviewedScore: 75,
    improvement: -3,
    feedback: '治疗方案过于激进',
    reviewerId: 'Dr. Li',
    timestamp: '2024-01-15 13:45:00',
  },
])

// 知识库
const knowledgeBase = ref([
  {
    id: '1',
    category: 'completeness',
    pattern: '基本信息完整性检查',
    confidence: 0.95,
    usageCount: 120,
    successRate: 0.92,
    lastUpdated: '2024-01-15',
  },
  {
    id: '2',
    category: 'consistency',
    pattern: '诊断一致性验证',
    confidence: 0.88,
    usageCount: 85,
    successRate: 0.89,
    lastUpdated: '2024-01-14',
  },
])

// 学习任务
const learningTasks = ref([
  {
    id: '1',
    type: 'feedback_learning',
    status: 'pending',
    priority: 'high',
    createdAt: '2024-01-15 15:00:00',
    description: '处理用户反馈学习',
  },
  {
    id: '2',
    type: 'pattern_recognition',
    status: 'running',
    priority: 'medium',
    createdAt: '2024-01-15 14:30:00',
    description: '识别新的质控模式',
  },
])

// 性能指标
const performanceMetrics = ref([
  { name: '准确率', value: 0.885, type: 'percentage', trend: 2.3 },
  { name: '精确率', value: 0.862, type: 'percentage', trend: 1.8 },
  { name: '召回率', value: 0.841, type: 'percentage', trend: -0.5 },
  { name: '处理时间', value: 3200, type: 'time', trend: -5.2 },
  { name: '用户满意度', value: 0.875, type: 'percentage', trend: 3.1 },
])

// 表单数据
const learningForm = reactive({
  recordId: '',
  originalScore: 0,
  reviewedScore: 0,
  feedback: '',
  corrections: [],
})

const knowledgeForm = reactive({
  category: '',
  pattern: '',
  confidence: 0.8,
  metadata: '',
})

const settingsForm = reactive({
  enableFeedbackLearning: true,
  enableContextualLearning: true,
  enablePatternRecognition: true,
  adaptiveScoring: true,
  personalizedRecommendations: true,
  learningFrequency: 'hourly',
})

// 表格列定义
const learningColumns = [
  { title: '记录ID', dataIndex: 'recordId', key: 'recordId' },
  { title: '原始评分', dataIndex: 'originalScore', key: 'originalScore' },
  { title: '修正评分', dataIndex: 'reviewedScore', key: 'reviewedScore' },
  { title: '改进幅度', key: 'improvement' },
  { title: '审核人', dataIndex: 'reviewerId', key: 'reviewerId' },
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp' },
  { title: '操作', key: 'actions' },
]

const knowledgeColumns = [
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '模式', dataIndex: 'pattern', key: 'pattern' },
  { title: '置信度', key: 'confidence' },
  { title: '使用情况', key: 'usage' },
  { title: '更新时间', dataIndex: 'lastUpdated', key: 'lastUpdated' },
  { title: '操作', key: 'actions' },
]

const tasksColumns = [
  { title: '任务类型', dataIndex: 'type', key: 'type' },
  { title: '状态', key: 'status' },
  { title: '优先级', key: 'priority' },
  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt' },
  { title: '描述', dataIndex: 'description', key: 'description' },
  { title: '操作', key: 'actions' },
]

const metricsColumns = [
  { title: '指标', dataIndex: 'name', key: 'name' },
  { title: '数值', key: 'value' },
  { title: '趋势', key: 'trend' },
]

// 分页配置
const paginationConfig = {
  pageSize: 10,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`,
}

// 计算属性
const filteredKnowledgeBase = computed(() => {
  if (!selectedCategory.value) return knowledgeBase.value
  return knowledgeBase.value.filter((item) => item.category === selectedCategory.value)
})

const filteredTasks = computed(() => {
  if (!selectedTaskType.value) return learningTasks.value
  return learningTasks.value.filter((task) => task.type === selectedTaskType.value)
})

// 图表引用
const performanceChart = ref()
const accuracyChart = ref()
const timingChart = ref()
const satisfactionChart = ref()

// 方法
const refreshData = async () => {
  loading.value = true
  try {
    // 模拟数据刷新
    await new Promise((resolve) => setTimeout(resolve, 1000))
    message.success('数据刷新成功')
  } catch (error) {
    message.error('数据刷新失败')
  } finally {
    loading.value = false
  }
}

const getPerformanceColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  return '#f5222d'
}

const getPerformanceStatus = (score: number): 'success' | 'warning' | 'error' => {
  if (score >= 90) return 'success'
  if (score >= 80) return 'warning'
  return 'error'
}

const getPerformanceText = (score: number) => {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  return '需改进'
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#52c41a'
  if (confidence >= 0.6) return '#faad14'
  return '#f5222d'
}

const getTaskStatus = (
  status: string,
): 'success' | 'error' | 'warning' | 'default' | 'processing' => {
  const statusMap = {
    pending: 'default',
    running: 'processing',
    completed: 'success',
    failed: 'error',
  } as const
  return statusMap[status as keyof typeof statusMap] || 'default'
}

const getTaskStatusText = (status: string) => {
  const textMap = {
    pending: '待处理',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
  }
  return textMap[status as keyof typeof textMap] || status
}

const getPriorityColor = (priority: string) => {
  const colorMap = {
    critical: 'red',
    high: 'orange',
    medium: 'blue',
    low: 'green',
  }
  return colorMap[priority as keyof typeof colorMap] || 'default'
}

const getPriorityText = (priority: string) => {
  const textMap = {
    critical: '紧急',
    high: '高',
    medium: '中',
    low: '低',
  }
  return textMap[priority as keyof typeof textMap] || priority
}

const getMetricPercent = (value: number, type: string) => {
  if (type === 'percentage') return Math.round(value * 100)
  if (type === 'time') return Math.min(100, Math.max(0, 100 - (value - 1000) / 50))
  return Math.round(value * 100)
}

const getMetricColor = (value: number, type: string) => {
  const percent = getMetricPercent(value, type)
  if (percent >= 80) return '#52c41a'
  if (percent >= 60) return '#faad14'
  return '#f5222d'
}

const formatMetricValue = (value: number, type: string) => {
  if (type === 'percentage') return `${Math.round(value * 100)}%`
  if (type === 'time') return `${value}ms`
  return value.toString()
}

// 学习记录相关方法
const submitLearningRecord = async () => {
  try {
    // 模拟提交学习记录
    console.log('提交学习记录:', learningForm)
    message.success('学习记录添加成功')
    showLearningDialog.value = false
    resetLearningForm()
  } catch (error) {
    message.error('添加学习记录失败')
  }
}

const resetLearningForm = () => {
  Object.assign(learningForm, {
    recordId: '',
    originalScore: 0,
    reviewedScore: 0,
    feedback: '',
    corrections: [],
  })
}

const viewLearningDetail = (record: Record<string, unknown>) => {
  console.log('查看学习详情:', record)
}

const analyzeLearningPattern = (record: Record<string, unknown>) => {
  console.log('分析学习模式:', record)
}

// 知识库相关方法
const submitKnowledgeEntry = async () => {
  try {
    // 模拟提交知识条目
    console.log('提交知识条目:', knowledgeForm)
    message.success('知识条目添加成功')
    showKnowledgeDialog.value = false
    resetKnowledgeForm()
  } catch (error) {
    message.error('添加知识条目失败')
  }
}

const resetKnowledgeForm = () => {
  Object.assign(knowledgeForm, {
    category: '',
    pattern: '',
    confidence: 0.8,
    metadata: '',
  })
}

const filterKnowledgeBase = () => {
  // 过滤知识库已通过计算属性实现
}

const editKnowledgeEntry = (record: Record<string, unknown>) => {
  console.log('编辑知识条目:', record)
}

const testKnowledgeEntry = (record: Record<string, unknown>) => {
  console.log('测试知识条目:', record)
}

const deleteKnowledgeEntry = async (record: Record<string, unknown>) => {
  try {
    // 模拟删除知识条目
    console.log('删除知识条目:', record)
    message.success('知识条目删除成功')
  } catch (error) {
    message.error('删除知识条目失败')
  }
}

// 任务相关方法
const filterTasks = () => {
  // 过滤任务已通过计算属性实现
}

const createLearningTask = () => {
  console.log('创建学习任务')
}

const viewTaskDetail = (record: Record<string, unknown>) => {
  console.log('查看任务详情:', record)
}

const executeTask = async (record: Record<string, unknown>) => {
  try {
    // 模拟执行任务
    console.log('执行任务:', record)
    message.success('任务执行成功')
  } catch (error) {
    message.error('任务执行失败')
  }
}

const cancelTask = async (record: Record<string, unknown>) => {
  try {
    // 模拟取消任务
    console.log('取消任务:', record)
    message.success('任务取消成功')
  } catch (error) {
    message.error('任务取消失败')
  }
}

// 设置相关方法
const saveSettings = async () => {
  try {
    // 模拟保存设置
    console.log('保存设置:', settingsForm)
    message.success('设置保存成功')
    showSettings.value = false
  } catch (error) {
    message.error('设置保存失败')
  }
}

const resetSettings = () => {
  // 重置设置表单
  Object.assign(settingsForm, {
    enableFeedbackLearning: true,
    enableContextualLearning: true,
    enablePatternRecognition: true,
    adaptiveScoring: true,
    personalizedRecommendations: true,
    learningFrequency: 'hourly',
  })
}

// 图表初始化
const initCharts = () => {
  nextTick(() => {
    // 性能趋势图
    if (performanceChart.value) {
      const chart = echarts.init(performanceChart.value)
      chart.setOption({
        title: { text: '性能趋势', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
        yAxis: { type: 'value' },
        series: [
          {
            name: '性能评分',
            type: 'line',
            data: [82, 85, 88, 87, 90, 88],
            smooth: true,
          },
        ],
      })
    }

    // 准确率分析图
    if (accuracyChart.value) {
      const chart = echarts.init(accuracyChart.value)
      chart.setOption({
        title: { text: '准确率分析', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'item' },
        series: [
          {
            name: '准确率',
            type: 'pie',
            data: [
              { value: 88.5, name: '准确识别' },
              { value: 11.5, name: '误识别' },
            ],
          },
        ],
      })
    }

    // 处理时间分析图
    if (timingChart.value) {
      const chart = echarts.init(timingChart.value)
      chart.setOption({
        title: { text: '处理时间分析', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ['AI分析', '规则引擎', '结果合并', '后处理'] },
        yAxis: { type: 'value' },
        series: [
          {
            name: '处理时间(ms)',
            type: 'bar',
            data: [3200, 800, 200, 100],
          },
        ],
      })
    }

    // 用户满意度图
    if (satisfactionChart.value) {
      const chart = echarts.init(satisfactionChart.value)
      chart.setOption({
        title: { text: '用户满意度', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: ['很满意', '满意', '一般', '不满意', '很不满意'] },
        yAxis: { type: 'value' },
        series: [
          {
            name: '用户数量',
            type: 'bar',
            data: [45, 32, 15, 5, 3],
          },
        ],
      })
    }
  })
}

// 生命周期
onMounted(() => {
  initCharts()
})
</script>

<style scoped>
.ai-enhancement-panel {
  padding: 20px;
}

.stat-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.stat-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
  transition: all 0.3s ease;
}

.learning-panel,
.knowledge-panel,
.performance-panel,
.tasks-panel {
  padding: 16px;
}

:deep(.ant-table-tbody > tr > td) {
  padding: 8px 16px;
}

:deep(.ant-card-head) {
  border-bottom: 2px solid #f0f0f0;
}

:deep(.ant-tabs-card > .ant-tabs-content) {
  margin-top: 16px;
}
</style>
