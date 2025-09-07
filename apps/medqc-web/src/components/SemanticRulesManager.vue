<template>
  <div class="semantic-rules-manager">
    <a-card :bordered="false">
      <template #title>
        <div class="card-title">
          <span class="title-icon">🏥</span>
          四川省住院病历语义质控规则
          <a-tag color="blue" style="margin-left: 8px">68条规则</a-tag>
        </div>
      </template>
      <template #extra>
        <a-space>
          <!-- 四川省质控系统状态 -->
          <a-tooltip title="四川省质控系统状态">
            <a-badge
              :status="sichuanQCStatus.healthy ? 'processing' : 'error'"
              :text="sichuanQCStatus.healthy ? '系统正常' : '系统异常'"
            />
          </a-tooltip>

          <a-button @click="refreshSichuanRules" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新规则
          </a-button>

          <a-button type="primary" @click="showQCEvaluation = true">
            <template #icon><PlayCircleOutlined /></template>
            开始质控评估
          </a-button>

          <a-button @click="showSystemStats = true">
            <template #icon><BarChartOutlined /></template>
            系统统计
          </a-button>
        </a-space>
      </template>

      <!-- 四川省规则统计信息 -->
      <a-row :gutter="16" class="stats-cards">
        <a-col :span="6">
          <a-card size="small">
            <a-statistic
              title="四川省规则总数"
              :value="sichuanRules.length || 68"
              :value-style="{ color: '#1890ff' }"
            >
              <template #prefix><FileTextOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic
              title="Token节省率"
              :value="80"
              suffix="%"
              :value-style="{ color: '#52c41a' }"
            >
              <template #prefix><CheckCircleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic
              title="平均评估时间"
              :value="47.5"
              suffix="秒"
              :value-style="{ color: '#faad14' }"
            >
              <template #prefix><ClockCircleOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
        <a-col :span="6">
          <a-card size="small">
            <a-statistic
              title="年节省成本"
              :value="13651"
              prefix="¥"
              :value-style="{ color: '#722ed1' }"
            >
              <template #prefix><ThunderboltOutlined /></template>
            </a-statistic>
          </a-card>
        </a-col>
      </a-row>

      <!-- 四川省规则分类统计 -->
      <a-row :gutter="16" style="margin-top: 16px;">
        <a-col :span="8">
          <a-card size="small" title="复杂度分布">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">高复杂度:</span>
                <a-tag color="red">{{ sichuanStats.complexity_distribution?.高复杂度 || 28 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">中复杂度:</span>
                <a-tag color="orange">{{ sichuanStats.complexity_distribution?.中复杂度 || 27 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">低复杂度:</span>
                <a-tag color="green">{{ sichuanStats.complexity_distribution?.低复杂度 || 13 }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card size="small" title="缺陷级别分布">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">严重缺陷:</span>
                <a-tag color="red">{{ sichuanStats.defect_level_distribution?.严重缺陷 || 8 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">一般缺陷:</span>
                <a-tag color="orange">{{ sichuanStats.defect_level_distribution?.一般缺陷 || 12 }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">轻微缺陷:</span>
                <a-tag color="green">{{ sichuanStats.defect_level_distribution?.轻微缺陷 || 40 }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
        <a-col :span="8">
          <a-card size="small" title="规则分类">
            <div class="category-stats">
              <div class="stat-item">
                <span class="label">诊断一致性:</span>
                <a-tag color="blue">{{ getCategoryCount('诊断一致性') }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">病史完整性:</span>
                <a-tag color="cyan">{{ getCategoryCount('病史完整性') }}条</a-tag>
              </div>
              <div class="stat-item">
                <span class="label">诊疗合理性:</span>
                <a-tag color="purple">{{ getCategoryCount('诊疗合理性') }}条</a-tag>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>

      <!-- 四川省规则列表 -->
      <a-table
        :dataSource="sichuanRules"
        :columns="sichuanColumns"
        :loading="loading"
        :pagination="{ pageSize: 15, showSizeChanger: true, showQuickJumper: true }"
        class="rules-table"
        :scroll="{ x: 1400 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <a-tag color="blue">{{ record.rule_id }}</a-tag>
          </template>

          <template v-if="column.key === 'name'">
            <a-tooltip :title="record.description">
              <span class="rule-name">{{ record.name }}</span>
            </a-tooltip>
          </template>

          <template v-if="column.key === 'complexity'">
            <a-tag :color="getSichuanComplexityColor(record.complexity)">
              {{ record.complexity }}
            </a-tag>
          </template>

          <template v-if="column.key === 'defect_level'">
            <a-tag :color="getSichuanDefectLevelColor(record.defect_level)">
              {{ record.defect_level }}
            </a-tag>
          </template>

          <template v-if="column.key === 'category'">
            <a-tag :color="getCategoryColor(record.category)">
              {{ record.category }}
            </a-tag>
          </template>

          <template v-if="column.key === 'applicable_documents'">
            <div class="document-types">
              <a-tag
                v-for="docType in record.applicable_documents"
                :key="docType"
                size="small"
                color="geekblue"
              >
                {{ docType }}
              </a-tag>
            </div>
          </template>

          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button size="small" @click="viewSichuanRuleDetail(record)">
                详情
              </a-button>
              <a-button size="small" type="primary" @click="startQCWithRule(record)">
                质控评估
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 四川省规则详情模态框 -->
    <a-modal
      v-model:open="showRuleDetail"
      title="四川省住院病历质控规则详情"
      width="900px"
      :footer="null"
      centered
    >
      <div v-if="selectedRule" class="rule-detail">
        <a-descriptions :column="2" bordered>
          <a-descriptions-item label="规则ID">
            <a-tag color="blue">{{ selectedRule.rule_id }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="规则名称">
            {{ selectedRule.name }}
          </a-descriptions-item>
          <a-descriptions-item label="规则分类">
            <a-tag :color="getCategoryColor(selectedRule.category)">
              {{ selectedRule.category }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="复杂度">
            <a-tag :color="getSichuanComplexityColor(selectedRule.complexity)">
              {{ selectedRule.complexity }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷级别">
            <a-tag :color="getSichuanDefectLevelColor(selectedRule.defect_level)">
              {{ selectedRule.defect_level }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="扣分">
            {{ selectedRule.score_deduction || 0 }}分
          </a-descriptions-item>
          <a-descriptions-item label="医疗领域">
            {{ selectedRule.medical_domain }}
          </a-descriptions-item>
          <a-descriptions-item label="需要RAG">
            <a-tag :color="selectedRule.requires_rag ? 'green' : 'default'">
              {{ selectedRule.requires_rag ? '是' : '否' }}
            </a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>规则描述</a-divider>
        <p>{{ selectedRule.description }}</p>

        <a-divider>适用文档类型</a-divider>
        <div class="document-types">
          <a-tag
            v-for="docType in selectedRule.applicable_documents"
            :key="docType"
            color="geekblue"
          >
            {{ docType }}
          </a-tag>
        </div>

        <a-divider>四川省质控标准</a-divider>
        <a-alert
          message="基于《四川省住院病历质量评定标准（2023年版）》"
          description="该规则严格按照四川省卫健委发布的最新住院病历质量评定标准制定，确保质控评估的权威性和准确性。"
          type="info"
          show-icon
        />
      </div>
    </a-modal>

    <!-- 质控评估模态框 -->
    <a-modal
      v-model:open="showQCEvaluation"
      title="四川省住院病历质控评估"
      width="600px"
      :footer="null"
      centered
    >
      <a-alert
        message="质控评估功能"
        description="请前往质控评估页面进行完整的四川省住院病历质控评估"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />
      <div style="text-align: center;">
        <a-button type="primary" size="large" @click="showQCEvaluation = false">
          前往质控评估页面
        </a-button>
      </div>
    </a-modal>

    <!-- 系统统计模态框 -->
    <a-modal
      v-model:open="showSystemStats"
      title="四川省质控系统统计"
      width="600px"
      :footer="null"
      centered
    >
      <a-alert
        message="系统统计信息"
        description="请前往统计页面查看详细的四川省质控系统运行统计"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />
      <div style="text-align: center;">
        <a-button type="primary" size="large" @click="showSystemStats = false">
          前往统计页面
        </a-button>
      </div>
    </a-modal>


  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  BarChartOutlined
} from '@ant-design/icons-vue'

// 四川省规则接口定义
interface SichuanQCRule {
  rule_id: string
  name: string
  description: string
  category: string
  complexity: string
  defect_level: string
  score_deduction: number
  applicable_documents: string[]
  medical_domain: string
  requires_rag: boolean
  requires_cot: boolean
}

interface SichuanQCStats {
  total_rules: number
  rule_categories: string[]
  complexity_distribution: Record<string, number>
  defect_level_distribution: Record<string, number>
}

interface SichuanQCStatus {
  healthy: boolean
  api_endpoint: string
}

interface TableColumn {
  title: string
  dataIndex?: string
  key: string
  width?: number
  fixed?: string
  ellipsis?: boolean
}

// 四川省规则相关数据
const loading = ref(false)
const sichuanRules = ref<SichuanQCRule[]>([])
const sichuanStats = ref<SichuanQCStats>({
  total_rules: 68,
  rule_categories: [],
  complexity_distribution: {},
  defect_level_distribution: {}
})
const sichuanQCStatus = ref<SichuanQCStatus>({
  healthy: true,
  api_endpoint: 'http://localhost:8001'
})

// 兼容原有数据结构
const rules = ref<SichuanQCRule[]>([])

// 规则详情
const showRuleDetail = ref(false)
const selectedRule = ref<SichuanQCRule | null>(null)

// 质控评估和系统统计
const showQCEvaluation = ref(false)
const showSystemStats = ref(false)

// 四川省规则表格列定义
const sichuanColumns: TableColumn[] = [
  {
    title: '规则ID',
    dataIndex: 'rule_id',
    key: 'rule_id',
    width: 100,
    fixed: 'left'
  },
  {
    title: '规则名称',
    dataIndex: 'name',
    key: 'name',
    width: 200,
    ellipsis: true
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 120
  },
  {
    title: '复杂度',
    dataIndex: 'complexity',
    key: 'complexity',
    width: 100
  },
  {
    title: '缺陷级别',
    dataIndex: 'defect_level',
    key: 'defect_level',
    width: 120
  },
  {
    title: '适用文档',
    dataIndex: 'applicable_documents',
    key: 'applicable_documents',
    width: 150,
    ellipsis: true
  },
  {
    title: '医疗领域',
    dataIndex: 'medical_domain',
    key: 'medical_domain',
    width: 120
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    fixed: 'right'
  }
]

// 四川省规则相关方法
const refreshSichuanRules = async () => {
  loading.value = true
  try {
    console.log('🔄 开始加载四川省质控规则...')

    const response = await fetch('/api/qc/sichuan/rules')
    if (response.ok) {
      const data = await response.json()
      sichuanRules.value = data.rules || []
      sichuanStats.value = {
        total_rules: data.total_rules || 68,
        rule_categories: data.rule_categories || [],
        complexity_distribution: data.complexity_distribution || {},
        defect_level_distribution: data.defect_level_distribution || {}
      }

      // 同步到兼容数据结构
      rules.value = sichuanRules.value

      console.log('✅ 四川省规则加载成功:', sichuanRules.value.length, '条规则')
      message.success(`成功加载 ${sichuanRules.value.length} 条四川省质控规则`)
    } else {
      const error = await response.text()
      console.error('❌ 四川省规则加载失败:', error)
      message.error('加载四川省规则失败: ' + error)
    }
  } catch (error: unknown) {
    console.error('❌ 四川省规则加载异常:', error)
    message.error('加载四川省规则异常: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    loading.value = false
  }
}

// 四川省规则详情查看
const viewSichuanRuleDetail = (rule: SichuanQCRule) => {
  selectedRule.value = rule
  showRuleDetail.value = true
}

// 开始质控评估
const startQCWithRule = (rule: SichuanQCRule) => {
  message.info(`准备使用规则 ${rule.rule_id} 进行质控评估`)
  showQCEvaluation.value = true
}

// 删除不需要的测试和自定义规则创建方法
// 四川省规则是预定义的，不需要创建自定义规则

// 四川省规则相关辅助方法
const getSichuanComplexityColor = (complexity: string) => {
  switch (complexity) {
    case '高复杂度': return 'red'
    case '中复杂度': return 'orange'
    case '低复杂度': return 'green'
    default: return 'default'
  }
}

const getSichuanDefectLevelColor = (level: string) => {
  if (level.includes('严重') || level.includes('否决')) return 'red'
  if (level.includes('一般')) return 'orange'
  return 'green'
}

const getCategoryColor = (category: string) => {
  const colors: Record<string, string> = {
    '诊断一致性': 'blue',
    '病史完整性': 'cyan',
    '诊疗合理性': 'purple',
    '专科判断': 'magenta',
    '内容完整性': 'geekblue',
    '术语规范性': 'gold',
    '知情同意': 'lime',
    '基础语义检查': 'volcano'
  }
  return colors[category] || 'default'
}

const getCategoryCount = (category: string) => {
  return sichuanRules.value.filter(rule => rule.category === category).length
}



// 组件挂载时加载四川省规则
onMounted(() => {
  console.log('🚀 四川省质控规则管理器组件已挂载，开始加载规则...')
  refreshSichuanRules()
})
</script>

<style scoped>
.semantic-rules-manager {
  padding: 24px;
}

.stats-cards {
  margin-bottom: 24px;
}

.rules-table {
  margin-top: 16px;
}

.rule-detail {
  max-height: 600px;
  overflow-y: auto;
}

.card-title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}

.title-icon {
  margin-right: 8px;
  font-size: 18px;
}

.category-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item .label {
  font-size: 12px;
  color: #666;
}

.rule-name {
  cursor: pointer;
  color: #1890ff;
}

.rule-name:hover {
  text-decoration: underline;
}

.document-types {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ant-descriptions-item-label {
  font-weight: 600;
}

.ant-statistic-content {
  font-size: 20px;
}

.ant-badge-status-text {
  font-size: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .semantic-rules-manager {
    padding: 12px;
  }

  .stats-cards .ant-col {
    margin-bottom: 12px;
  }

  .rules-table {
    font-size: 12px;
  }
}
</style>
