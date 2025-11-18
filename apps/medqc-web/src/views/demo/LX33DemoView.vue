<template>
  <div class="lx33-demo-view">
    <!-- 反馈统计面板 -->
    <a-card class="stats-panel" :loading="loadingStats">
      <template #title>
        <span><BarChartOutlined /> 反馈统计 (最近30天)</span>
      </template>
      <a-row :gutter="24">
        <a-col :span="4">
          <a-statistic
            title="总反馈数"
            :value="stats.total_feedbacks"
            :value-style="{ color: '#1890ff' }"
          >
            <template #prefix>
              <MessageOutlined />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="5">
          <a-statistic
            title="正确反馈"
            :value="stats.correct_feedbacks"
            :suffix="`(${(stats.accuracy_rate * 100).toFixed(0)}%)`"
            :value-style="{ color: '#52c41a' }"
          >
            <template #prefix>
              <CheckCircleOutlined />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="5">
          <a-statistic
            title="错误反馈"
            :value="stats.incorrect_feedbacks"
            :suffix="`(${((1 - stats.accuracy_rate) * 100).toFixed(0)}%)`"
            :value-style="{ color: '#ff4d4f' }"
          >
            <template #prefix>
              <CloseCircleOutlined />
            </template>
          </a-statistic>
        </a-col>
        <a-col :span="5">
          <div class="stat-item">
            <div class="stat-label">最高准确率规则</div>
            <div class="stat-value best-rule">
              {{ stats.best_rule || '-' }}
            </div>
          </div>
        </a-col>
        <a-col :span="5">
          <div class="stat-item">
            <div class="stat-label">最低准确率规则</div>
            <div class="stat-value worst-rule">
              {{ stats.worst_rule || '-' }}
            </div>
          </div>
        </a-col>
      </a-row>
    </a-card>

    <!-- 页面操作栏 -->
    <a-card class="action-bar">
      <a-space size="large">
        <a-button
          type="primary"
          size="large"
          class="batch-eval-button"
          @click="showBatchTestModal = true"
        >
          <template #icon><CheckSquareOutlined /></template>
          批量质控评估
        </a-button>
        <a-button type="primary" @click="ruleDocModalVisible = true">
          <FileTextOutlined /> 质控点说明
        </a-button>
        <a-button type="primary" @click="showFeedbacksPage">
          <HistoryOutlined /> 查看反馈记录
        </a-button>
        <a-button @click="exportFeedbacks">
          <ExportOutlined /> 导出反馈数据
        </a-button>
        <a-button type="primary" ghost @click="showCreateRulePage">
          <ThunderboltOutlined /> AI智能创建规则
        </a-button>
      </a-space>
    </a-card>

    <!-- 规则列表表格 -->
    <a-card title="泸县33条质控规则列表" :loading="loadingRules" class="rules-list-card">
      <template #extra>
        <span class="rule-count">共 {{ displayRules.length }} 条规则</span>
      </template>

      <a-table
        :dataSource="displayRules"
        :columns="columns"
        :pagination="{
          defaultPageSize: 33,
          pageSize: 33,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '33', '50'],
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条规则`
        }"
        class="rules-table"
        :scroll="{ x: 1000 }"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            {{ record._index || index + 1 }}
          </template>

          <template v-if="column.key === 'rule_id'">
            <a-tag color="blue">{{ record.rule_id || record.rule_code }}</a-tag>
          </template>

          <template v-if="column.key === 'name'">
            <a-tooltip :title="record.description">
              <span class="rule-name">{{ record.name }}</span>
            </a-tooltip>
          </template>

          <template v-if="column.key === 'category'">
            <a-tag :color="getCategoryColor(record.category)">
              {{ record.category }}
            </a-tag>
          </template>

          <template v-if="column.key === 'complexity'">
            <a-tag :color="getComplexityColor(record.complexity)">
              {{ record.complexity }}
            </a-tag>
          </template>

          <template v-if="column.key === 'defect_level'">
            <a-tag :color="getDefectLevelColor(record.defect_level)">
              {{ getDefectLevelText(record.defect_level) }}
            </a-tag>
          </template>

          <template v-if="column.key === 'source'">
            <a-tag :color="getSourceColor(record.source)">
              {{ getSourceText(record.source) }}
            </a-tag>
          </template>

          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" @click="viewRuleDetail(record)">
                详情
              </a-button>
              <a-button size="small" type="primary" @click="handleEvaluate(record)">
                质控评估
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 批量评估弹窗 -->
    <BatchEvaluationModal
      v-model:visible="evaluationModalVisible"
      :rule="selectedRule"
      @feedback="handleFeedback"
    />

    <!-- 反馈弹窗 -->
    <FeedbackModal
      v-model:visible="feedbackModalVisible"
      :evaluation-result="currentEvaluationResult"
      @submit="handleFeedbackSubmit"
    />

    <!-- 规则详情弹窗 -->
    <a-modal
      v-model:open="detailModalVisible"
      :title="`规则详情 · ${selectedRule?.rule_id || selectedRule?.rule_code || ''}`"
      width="800px"
      :footer="null"
    >
      <div v-if="selectedRule" class="rule-detail">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="规则编号">
            {{ selectedRule.rule_id || selectedRule.rule_code }}
          </a-descriptions-item>
          <a-descriptions-item label="规则名称">
            {{ selectedRule.name }}
          </a-descriptions-item>
          <a-descriptions-item label="规则描述">
            {{ selectedRule.description }}
          </a-descriptions-item>
          <a-descriptions-item label="文书类别">
            <a-tag :color="getCategoryColor(selectedRule.category)">
              {{ selectedRule.category }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="复杂度">
            <a-tag :color="getComplexityColor(selectedRule.complexity)">
              {{ selectedRule.complexity }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷级别">
            <a-tag :color="getDefectLevelColor(selectedRule.defect_level)">
              {{ getDefectLevelText(selectedRule.defect_level) }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="扣分" v-if="selectedRule.score_deduction || selectedRule.deduction_score">
            {{ selectedRule.score_deduction || selectedRule.deduction_score }} 分
          </a-descriptions-item>
          <a-descriptions-item label="适用文书" v-if="selectedRule.applicable_documents?.length">
            <a-space :size="4" wrap>
              <a-tag
                v-for="(doc, index) in selectedRule.applicable_documents"
                :key="index"
                color="blue"
              >
                {{ doc }}
              </a-tag>
            </a-space>
          </a-descriptions-item>
        </a-descriptions>
      </div>
    </a-modal>

    <!-- 质控点说明弹窗 -->
    <a-modal
      v-model:open="ruleDocModalVisible"
      title="质控点说明（规则逻辑总览）"
      width="90%"
      :footer="null"
    >
      <a-table
        :dataSource="ruleDocRows"
        :columns="ruleDocColumns"
        class="rule-doc-table"
        :pagination="{
          pageSize: 10,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '33', '50'],
          showTotal: (total) => `共 ${total} 条质控点`
        }"
        size="small"
        rowKey="rule_id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <a-tag color="blue">{{ record.rule_id }}</a-tag>
          </template>
          <template v-else-if="column.key === 'name'">
            <span class="rule-name">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'description'">
            <a-typography-paragraph :ellipsis="{ rows: 3, expandable: true }">
              {{ record.description }}
            </a-typography-paragraph>
          </template>
          <template v-else-if="column.key === 'check_points'">
            <a-typography-paragraph :ellipsis="{ rows: 5, expandable: true }">
              {{ record.check_points || '（提示词中未单独标注【检查要点】）' }}
            </a-typography-paragraph>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- 批量质控评估 Modal - 直接嵌入组件 -->
    <a-modal
      v-model:open="showBatchTestModal"
      title="批量质控评估"
      width="95%"
      :footer="null"
      :destroyOnClose="true"
      wrapClassName="batch-test-modal"
      :bodyStyle="{ padding: 0, height: '85vh', overflow: 'hidden' }"
    >
      <BatchRuleTest
        v-if="showBatchTestModal"
        :demo-mode="true"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  BarChartOutlined,
  MessageOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  FileTextOutlined,
  HistoryOutlined,
  ExportOutlined,
  ThunderboltOutlined,
  CheckSquareOutlined
} from '@ant-design/icons-vue'
import { useRouter, useRoute } from 'vue-router'
import BatchEvaluationModal from './components/BatchEvaluationModal.vue'
import FeedbackModal from './components/FeedbackModal.vue'
import BatchRuleTest from '@/components/BatchRuleTest.vue'
import type { QCRule, FeedbackStats, EvaluationResult } from '@/types/demo'

const router = useRouter()
const route = useRoute()

// 数据状态
const loadingRules = ref(false)
const loadingStats = ref(false)
const rules = ref<QCRule[]>([])
const stats = ref<FeedbackStats>({
  total_feedbacks: 0,
  correct_feedbacks: 0,
  incorrect_feedbacks: 0,
  accuracy_rate: 0,
  best_rule: '',
  worst_rule: ''
})

// 评估和反馈
const evaluationModalVisible = ref(false)
const feedbackModalVisible = ref(false)
const detailModalVisible = ref(false)
const selectedRule = ref<QCRule | null>(null)
const currentEvaluationResult = ref<EvaluationResult | null>(null)

// 批量质控评估Modal状态
const showBatchTestModal = ref(false)

// 质控点说明弹窗状态
const ruleDocModalVisible = ref(false)

onMounted(() => {
  if (route.query.ruleDoc === 'true') {
    ruleDocModalVisible.value = true
  }
})

// 表格列定义
const columns = computed(() => [
  {
    title: h('span', { class: 'th-enlarge' }, '序号'),
    key: 'index',
    width: 60,
    fixed: 'left'
  },
  {
    title: h('span', { class: 'th-enlarge' }, '编号'),
    dataIndex: 'rule_id',
    key: 'rule_id',
    width: 85,
    fixed: 'left'
  },
  {
    title: h('span', { class: 'th-enlarge' }, '规则名称'),
    dataIndex: 'name',
    key: 'name',
    width: 250,
    ellipsis: true
  },
  {
    title: h('span', { class: 'th-enlarge' }, '文书类别'),
    dataIndex: 'category',
    key: 'category',
    width: 95
  },
  {
    title: h('span', { class: 'th-enlarge' }, '复杂度'),
    dataIndex: 'complexity',
    key: 'complexity',
    width: 90
  },
  {
    title: h('span', { class: 'th-enlarge' }, '缺陷级别'),
    dataIndex: 'defect_level',
    key: 'defect_level',
    width: 100
  },
  {
    title: h('span', { class: 'th-enlarge' }, '来源'),
    dataIndex: 'source',
    key: 'source',
    width: 110
  },
  {
    title: h('span', { class: 'th-enlarge' }, '操作'),
    key: 'actions',
    width: 150,
    fixed: 'right'
  }
])

const normalizeSource = (rule: QCRule | null | undefined): string => {
  if (!rule) return 'baseline'
  if (rule.source) return rule.source
  const id = (rule.rule_id || rule.rule_code || '').toUpperCase()
  if (id.startsWith('CUSTOM-')) {
    return 'ai_generated'
  }
  if (id.startsWith('LX-')) {
    return 'baseline'
  }
  return 'other'
}

const displayRules = computed(() =>
  rules.value
    // 仅展示 LX- 开头的泸县33条规则，隐藏扩展规则（如 LXE-）
    .filter((rule) => {
      const id = (rule.rule_id || rule.rule_code || '').toUpperCase()
      return id.startsWith('LX-') && !id.startsWith('LXE-')
    })
    .map((rule, index) => ({
      ...rule,
      source: normalizeSource(rule),
      _index: index + 1
    }))
)

// 从 custom_prompt 中提取【检查要点】段落
const extractCheckPoints = (prompt?: string): string => {
  if (!prompt) return ''
  const marker = '【检查要点】'
  const start = prompt.indexOf(marker)
  if (start === -1) return ''
  const after = prompt.slice(start + marker.length)
  const nextHeaderIndex = after.indexOf('【')
  const section = nextHeaderIndex === -1 ? after : after.slice(0, nextHeaderIndex)
  return section.trim()
}

// 质控点说明表格数据
const ruleDocColumns = [
  {
    title: '质控点编号',
    dataIndex: 'rule_id',
    key: 'rule_id',
    width: 110,
    fixed: 'left'
  },
  {
    title: '质控点名称',
    dataIndex: 'name',
    key: 'name',
    width: 260
  },
  {
    title: '质控点描述',
    dataIndex: 'description',
    key: 'description',
    width: 360
  },
  {
    title: '检查要点',
    dataIndex: 'check_points',
    key: 'check_points'
  }
]

const ruleDocRows = computed(() =>
  rules.value
    .filter((rule) => {
      const id = (rule.rule_id || rule.rule_code || '').toUpperCase()
      return id.startsWith('LX-') && !id.startsWith('LXE-')
    })
    .map((rule) => ({
      rule_id: rule.rule_id || rule.rule_code,
      name: rule.name,
      description: rule.description,
      check_points: extractCheckPoints((rule as any).custom_prompt)
    }))
)

// 加载规则列表
const loadRules = async () => {
  loadingRules.value = true
  try {
    const response = await fetch('/api/v1/demo/custom-rules')
    const data = await response.json()

    const allRules = data.data?.rules || []
    rules.value = allRules
      .filter((rule: QCRule) => !!(rule.rule_id || rule.rule_code))
      .map((rule: QCRule) => ({
        ...rule,
        source: normalizeSource(rule)
      }))
  } catch (error) {
    console.error('加载规则失败:', error)
    message.error('加载规则失败，请稍后重试')
  } finally {
    loadingRules.value = false
  }
}

// 加载反馈统计
const loadStats = async () => {
  loadingStats.value = true
  try {
    const response = await fetch('/api/v1/demo/feedbacks/stats')
    const data = await response.json()

    if (data.success) {
      stats.value = data.data
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    loadingStats.value = false
  }
}

// 查看规则详情
const viewRuleDetail = (rule: QCRule) => {
  selectedRule.value = rule
  detailModalVisible.value = true
}

// 打开评估弹窗
const handleEvaluate = (rule: QCRule) => {
  selectedRule.value = rule
  evaluationModalVisible.value = true
}

// 打开反馈弹窗
const handleFeedback = (result: EvaluationResult) => {
  currentEvaluationResult.value = result
  feedbackModalVisible.value = true
}

// 提交反馈
const handleFeedbackSubmit = async (feedbackData: any) => {
  try {
    const response = await fetch('/api/v1/demo/feedbacks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedbackData)
    })

    const data = await response.json()

    if (data.success) {
      message.success('反馈提交成功')
      // 关闭反馈弹窗和测试弹窗
      feedbackModalVisible.value = false
      evaluationModalVisible.value = false
      // 重新加载统计数据
      loadStats()
    } else {
      message.error('反馈提交失败')
    }
  } catch (error) {
    console.error('提交反馈失败:', error)
    message.error('反馈提交失败，请稍后重试')
  }
}

// 查看反馈记录页面
const showFeedbacksPage = () => {
  router.push('/demo/lx33/feedbacks')
}

const showCreateRulePage = () => {
  router.push('/demo/lx33/create')
}

// 导出反馈数据
const exportFeedbacks = async () => {
  try {
    const response = await fetch('/api/v1/demo/feedbacks/export')
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `lx33_feedbacks_${new Date().toISOString().split('T')[0]}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    message.error('导出失败，请稍后重试')
  }
}

// 颜色辅助函数
const getCategoryColor = (category: string) => {
  const colorMap: Record<string, string> = {
    '入院记录': 'blue',
    '病程记录': 'cyan',
    '手术记录': 'purple',
    '出院记录': 'green',
    '会诊记录': 'orange'
  }
  return colorMap[category] || 'default'
}

const getComplexityColor = (complexity: string) => {
  const colorMap: Record<string, string> = {
    '高复杂度': 'red',
    '中复杂度': 'orange',
    '低复杂度': 'green'
  }
  return colorMap[complexity] || 'default'
}

const getDefectLevelColor = (level: string) => {
  const colorMap: Record<string, string> = {
    '严重缺陷': 'red',
    'critical': 'red',
    '一般缺陷': 'orange',
    'major': 'orange',
    '轻微缺陷': 'green',
    'minor': 'green'
  }
  return colorMap[level] || 'default'
}

const getDefectLevelText = (level: string) => {
  const textMap: Record<string, string> = {
    'critical': '严重缺陷',
    'major': '一般缺陷',
    'minor': '轻微缺陷'
  }
  return textMap[level] || level
}

const getSourceColor = (source: string) => {
  const map: Record<string, string> = {
    'ai_generated': 'purple',
    'baseline': 'blue',
    'other': 'default'
  }
  return map[source] || 'default'
}

const getSourceText = (source: string) => {
  const map: Record<string, string> = {
    'ai_generated': 'AI 生成',
    'baseline': '系统规则',
    'other': '其他'
  }
  return map[source] || '系统规则'
}

// 组件挂载时加载数据
onMounted(() => {
  loadRules()
  loadStats()
})
</script>

<style scoped lang="less">
.lx33-demo-view {
  .stats-panel {
    margin-bottom: 24px;

    .stat-item {
      .stat-label {
        font-size: 14px;
        color: rgba(0, 0, 0, 0.45);
        margin-bottom: 8px;
      }

      .stat-value {
        font-size: 20px;
        font-weight: 500;

        &.best-rule {
          color: #52c41a;
        }

        &.worst-rule {
          color: #ff4d4f;
        }
      }
    }
  }

  .action-bar {
    margin-bottom: 24px;

    :deep(.batch-eval-button) {
      background: linear-gradient(135deg, #ff9f43, #ff6b81);
      border: none;
      box-shadow: 0 8px 16px rgba(255, 107, 129, 0.35);
      font-weight: 600;
      letter-spacing: 0.5px;
      padding: 0 28px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.25s ease-out;

      .anticon {
        font-size: 16px;
      }

      &:hover {
        background: linear-gradient(135deg, #ffa94d, #ff4b6b);
        box-shadow: 0 10px 24px rgba(255, 107, 129, 0.5);
        transform: translateY(-1px);
      }

      &:active {
        transform: translateY(0);
        box-shadow: 0 4px 12px rgba(255, 107, 129, 0.4);
      }

      /* 轻微呼吸动画，让按钮更醒目但不过于晃眼 */
      animation: batch-eval-pulse 2.4s ease-in-out infinite;
    }

    @keyframes batch-eval-pulse {
      0% {
        transform: translateY(0);
        box-shadow: 0 8px 16px rgba(255, 107, 129, 0.35);
      }
      50% {
        transform: translateY(-1px);
        box-shadow: 0 12px 26px rgba(255, 107, 129, 0.55);
      }
      100% {
        transform: translateY(0);
        box-shadow: 0 8px 16px rgba(255, 107, 129, 0.35);
      }
    }
  }

  .rules-list-card {
    .rule-count {
      font-size: 14px;
      color: rgba(0, 0, 0, 0.65);
    }

    .rules-table {
      :deep(.rule-name) {
        color: rgba(0, 0, 0, 0.85);
        font-weight: 500;
      }

      :deep(.th-enlarge) {
        font-weight: 600;
        font-size: 14px;
      }

      // 表格行悬停效果增强
      :deep(.ant-table-tbody > tr) {
        transition: all 0.2s ease-in-out;
        cursor: pointer;

        &:hover {
          background: linear-gradient(90deg, #e6f7ff 0%, #f0f9ff 100%) !important;
          box-shadow: 0 2px 8px rgba(24, 144, 255, 0.15);
          transform: translateY(-1px);

          td {
            background: transparent !important;
          }
        }

        &:active {
          transform: translateY(0);
        }
      }
    }
  }

  .rule-detail {
    :deep(.ant-descriptions-item-label) {
      font-weight: 500;
    }
  }

  .rule-doc-table {
    :deep(.ant-table-thead > tr > th) {
      font-size: 15px;
      font-weight: 600;
    }
  }
}
</style>
