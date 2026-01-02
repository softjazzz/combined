<template>
  <div class="lx33-demo-view min-h-screen bg-slate-50/80 relative overflow-hidden p-6 lg:p-8">
    <!-- 背景装饰：极淡的点阵 -->
    <div class="absolute inset-0 pointer-events-none" style="background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 32px 32px; opacity: 0.25;"></div>
    
    <div class="relative z-10">
      <!-- 1. 页面头部 & 全局操作 -->
      <header class="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div>
          <h1 class="text-2xl font-bold text-slate-800 flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
              <MedicineBoxOutlined class="text-xl" />
            </div>
            泸县33条质控规则测试
          </h1>
          <p class="text-slate-500 mt-2 text-sm ml-1">基于真实病历数据的 AI 质控规则验证与评估中心</p>
        </div>
        <div class="flex flex-wrap gap-3">
          <button 
            @click="ruleDocModalVisible = true"
            class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 hover:border-blue-300 hover:text-blue-600 transition-all text-sm font-medium flex items-center shadow-sm"
          >
            <FileTextOutlined class="mr-2" /> 规则说明
          </button>
          <button 
            @click="showFeedbacksPage"
            class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 hover:border-blue-300 hover:text-blue-600 transition-all text-sm font-medium flex items-center shadow-sm"
          >
            <HistoryOutlined class="mr-2" /> 反馈记录
          </button>
          <button 
            @click="exportFeedbacks"
            class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 hover:border-blue-300 hover:text-blue-600 transition-all text-sm font-medium flex items-center shadow-sm"
          >
            <ExportOutlined class="mr-2" /> 导出数据
          </button>
          <button
            @click="showCreateRulePage"
            class="px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 hover:border-blue-300 hover:text-blue-600 transition-all text-sm font-medium flex items-center shadow-sm"
          >
            <ThunderboltOutlined class="mr-2" /> AI 创建规则
          </button>
        </div>
      </header>

      <!-- 2. 核心指标卡片 (KPI Cards) - 纯净风格 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <!-- 卡片 1 -->
        <div class="bg-white p-6 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-all relative group">
          <div class="flex justify-between items-center">
            <div>
              <div class="text-slate-500 text-xs font-medium mb-1 uppercase tracking-wider">总反馈数</div>
              <div class="text-3xl font-bold text-slate-800 tracking-tight font-mono">{{ stats.total_feedbacks }}</div>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-slate-50 text-blue-600 flex items-center justify-center group-hover:bg-blue-50 transition-colors">
              <MessageOutlined class="text-xl" />
            </div>
          </div>
        </div>

        <!-- 卡片 2 -->
        <div class="bg-white p-6 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-all relative group">
          <div class="flex justify-between items-center">
            <div>
              <div class="text-slate-500 text-xs font-medium mb-1 uppercase tracking-wider">正确反馈</div>
              <div class="flex items-baseline gap-3">
                <div class="text-3xl font-bold text-slate-800 tracking-tight font-mono">{{ stats.correct_feedbacks }}</div>
                <div class="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-md">
                  {{ (stats.accuracy_rate * 100).toFixed(0) }}% 准确率
                </div>
              </div>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-slate-50 text-emerald-600 flex items-center justify-center group-hover:bg-emerald-50 transition-colors">
              <CheckCircleOutlined class="text-xl" />
            </div>
          </div>
        </div>

        <!-- 卡片 3 -->
        <div class="bg-white p-6 rounded-xl border border-slate-100 shadow-sm hover:shadow-md transition-all relative group">
          <div class="flex justify-between items-center">
            <div>
              <div class="text-slate-500 text-xs font-medium mb-1 uppercase tracking-wider">错误反馈</div>
              <div class="flex items-baseline gap-3">
                <div class="text-3xl font-bold text-slate-800 tracking-tight font-mono">{{ stats.incorrect_feedbacks }}</div>
                <div class="text-xs font-medium text-rose-600 bg-rose-50 px-2 py-0.5 rounded-md">
                  {{ ((1 - stats.accuracy_rate) * 100).toFixed(0) }}% 错误率
                </div>
              </div>
            </div>
            <div class="w-12 h-12 rounded-2xl bg-slate-50 text-rose-600 flex items-center justify-center group-hover:bg-rose-50 transition-colors">
              <CloseCircleOutlined class="text-xl" />
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 规则列表表格 -->
      <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <!-- 表格头部工具栏 -->
        <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <h3 class="font-bold text-slate-800 text-base flex items-center gap-2">
            <AppstoreOutlined class="text-blue-500" />
            规则列表
          </h3>
          <span class="text-slate-500 text-xs font-medium bg-white border border-slate-200 px-2.5 py-1 rounded-md shadow-sm">
            共 {{ displayRules.length }} 条规则
          </span>
        </div>
        
        <a-table
          :dataSource="displayRules"
          :columns="columns"
          :pagination="{
            defaultPageSize: 33,
            pageSize: 33,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '33', '50'],
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`
          }"
          class="modern-table"
          :scroll="{ x: 1000 }"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'index'">
              <span class="text-slate-400 font-mono text-xs">{{ String(record._index || index + 1).padStart(2, '0') }}</span>
            </template>

            <template v-if="column.key === 'rule_id'">
              <span class="font-mono text-blue-700 font-medium bg-blue-50/50 px-2 py-0.5 rounded text-xs border border-blue-100/50">{{ record.rule_id || record.rule_code }}</span>
            </template>

            <template v-if="column.key === 'name'">
              <div class="flex flex-col">
                <span class="font-medium text-slate-700 group-hover:text-blue-700 transition-colors">{{ record.name }}</span>
                <span class="text-xs text-slate-400 truncate max-w-[240px]" :title="record.description">{{ record.description }}</span>
              </div>
            </template>

            <template v-if="column.key === 'category'">
              <span class="text-slate-600 text-xs font-medium">
                {{ record.category }}
              </span>
            </template>

            <template v-if="column.key === 'complexity'">
              <div class="flex items-center gap-1.5">
                <div class="w-1.5 h-1.5 rounded-full" :class="{
                  'bg-rose-500': record.complexity === '高复杂度',
                  'bg-amber-500': record.complexity === '中复杂度',
                  'bg-emerald-500': record.complexity === '低复杂度'
                }"></div>
                <span class="text-xs text-slate-600">{{ record.complexity }}</span>
              </div>
            </template>

            <template v-if="column.key === 'defect_level'">
              <span class="text-xs font-medium px-2 py-0.5 rounded-full" :class="{
                'bg-rose-50 text-rose-600': record.defect_level === 'critical' || record.defect_level === '严重缺陷',
                'bg-amber-50 text-amber-600': record.defect_level === 'major' || record.defect_level === '一般缺陷',
                'bg-slate-100 text-slate-500': record.defect_level === 'minor' || record.defect_level === '轻微缺陷'
              }">
                {{ getDefectLevelText(record.defect_level) }}
              </span>
            </template>

            <template v-if="column.key === 'source'">
              <span class="text-xs" :class="record.source === 'ai_generated' ? 'text-indigo-600 font-medium' : 'text-slate-400'">
                {{ getSourceText(record.source) }}
              </span>
            </template>

            <template v-if="column.key === 'actions'">
              <div class="flex gap-2">
                <a-tooltip title="查看详情">
                  <button @click="viewRuleDetail(record)" class="w-7 h-7 rounded-md flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-all">
                    <EyeOutlined class="text-sm" />
                  </button>
                </a-tooltip>
                <a-tooltip title="开始质控评估">
                  <button @click="showBatchTestModal = true" class="w-7 h-7 rounded-md flex items-center justify-center text-blue-600 bg-blue-50 hover:bg-blue-600 hover:text-white transition-all">
                    <PlayCircleOutlined class="text-sm" />
                  </button>
                </a-tooltip>
              </div>
            </template>
          </template>
        </a-table>
      </div>
    </div>

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
      :title="null"
      :footer="null"
      width="600px"
      class="modern-modal"
    >
      <div v-if="selectedRule" class="p-2">
         <div class="flex items-center gap-3 mb-6">
           <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
             <FileTextOutlined />
           </div>
           <div>
             <div class="text-xs text-slate-400 uppercase font-bold tracking-wide mb-0.5">{{ selectedRule.rule_id || selectedRule.rule_code }}</div>
             <h3 class="text-lg font-bold text-slate-800">{{ selectedRule.name }}</h3>
           </div>
         </div>
         
         <div class="space-y-4">
           <div class="p-4 bg-slate-50 rounded-xl border border-slate-100">
             <div class="text-xs text-slate-400 font-medium mb-2">规则描述</div>
             <div class="text-slate-700 text-sm leading-relaxed">{{ selectedRule.description }}</div>
           </div>
           
           <div class="grid grid-cols-2 gap-4">
             <div class="p-3 border border-slate-100 rounded-xl">
               <div class="text-xs text-slate-400 mb-1">文书类别</div>
               <div class="font-medium text-slate-700">{{ selectedRule.category }}</div>
             </div>
             <div class="p-3 border border-slate-100 rounded-xl">
               <div class="text-xs text-slate-400 mb-1">缺陷级别</div>
               <div class="font-medium" :class="{
                  'text-red-600': selectedRule.defect_level === 'critical',
                  'text-orange-500': selectedRule.defect_level === 'major',
                  'text-green-600': selectedRule.defect_level === 'minor'
               }">{{ getDefectLevelText(selectedRule.defect_level) }}</div>
             </div>
           </div>
         </div>
      </div>
    </a-modal>

    <!-- 质控点说明弹窗 -->
    <a-modal
      v-model:open="ruleDocModalVisible"
      title="质控点说明（规则逻辑总览）"
      width="90%"
      :footer="null"
      wrapClassName="rule-doc-modal"
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
        size="middle"
        rowKey="rule_id"
        :scroll="{ y: 600 }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <a-tag :color="record.rule_id.includes('LX-') ? 'blue' : 'cyan'" class="font-medium">
              {{ record.rule_id }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'name'">
            <div class="flex items-start gap-2">
              <FileTextOutlined class="mt-1 text-blue-500" />
              <span class="font-bold text-slate-700">{{ record.name }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'description'">
            <div class="text-slate-600 leading-relaxed whitespace-pre-wrap text-sm">
              {{ record.description }}
            </div>
          </template>
          <template v-else-if="column.key === 'check_points'">
            <div class="text-slate-600 leading-relaxed text-sm">
              <template v-if="record.check_points">
                <!-- 尝试简单解析序号，如果没有序号则直接显示 -->
                <div v-if="record.check_points.match(/\d+\./)" class="space-y-1">
                  <div 
                    v-for="(point, idx) in record.check_points.split(/(?=\d+\.)/).filter(p => p.trim())" 
                    :key="idx"
                    class="flex gap-2"
                  >
                    <span class="flex-shrink-0 text-blue-500 font-medium mt-0.5">
                      {{ point.match(/^\d+\./)?.[0] }}
                    </span>
                    <span>{{ point.replace(/^\d+\./, '').trim() }}</span>
                  </div>
                </div>
                <div v-else class="whitespace-pre-wrap">
                  {{ record.check_points }}
                </div>
              </template>
              <span v-else class="text-slate-400 italic">（提示词中未单独标注【检查要点】）</span>
            </div>
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
  /* 表格样式优化 */
  .modern-table {
    :deep(.ant-table-thead > tr > th) {
      background: transparent;
      color: #64748b;
      font-weight: 600;
      font-size: 13px;
      padding: 16px 24px;
      border-bottom: 1px solid #f1f5f9;
    }

    :deep(.ant-table-tbody > tr > td) {
      padding: 16px 24px;
      border-bottom: 1px solid #f1f5f9;
    }

    :deep(.ant-table-tbody > tr:hover > td) {
      background: #f8fafc;
    }
  }

  /* 规则文档表格样式 */
  .rule-doc-table {
    :deep(.ant-table-thead > tr > th) {
      background-color: #f8fafc;
      color: #334155;
      font-size: 14px;
      font-weight: 600;
      padding: 16px 16px;
      border-bottom: 1px solid #e2e8f0;
    }

    :deep(.ant-table-tbody > tr > td) {
      padding: 16px 16px;
      border-bottom: 1px solid #f1f5f9;
      vertical-align: top;
    }

    :deep(.ant-table-tbody > tr:nth-child(even) > td) {
      background-color: #f8fafc;
    }

    :deep(.ant-table-tbody > tr:hover > td) {
      background-color: #eff6ff !important;
    }
  }
}

/* 全局 Modal 样式覆盖 (为了让 Modal 更干净) */
:global(.modern-modal .ant-modal-content),
:global(.rule-doc-modal .ant-modal-content) {
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

:global(.modern-modal .ant-modal-header),
:global(.rule-doc-modal .ant-modal-header) {
  border-bottom: none;
  margin-bottom: 0;
}

:global(.batch-test-modal .ant-modal-content) {
  border-radius: 16px;
  overflow: hidden;
}
</style>
