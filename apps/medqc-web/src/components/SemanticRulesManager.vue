<template>
  <div class="semantic-rules-manager">
    <!-- 1. 核心数据卡片区 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      
      <!-- 卡片 1: 复杂度分布 (环形图) -->
      <div class="stats-card relative overflow-hidden flex flex-col">
        <div class="flex justify-between items-start mb-4">
          <h3 class="stats-title">规则复杂度分布</h3>
          <PieChartOutlined class="stats-icon" />
        </div>
        <div class="flex items-center flex-1">
          <!-- CSS 模拟环形图 (Donut Chart) -->
          <div 
            class="relative w-28 h-28 rounded-full mr-6 flex items-center justify-center flex-shrink-0"
            :style="complexityConicGradient"
          >
            <!-- 镂空遮罩 -->
            <div class="absolute w-20 h-20 bg-white rounded-full shadow-inner"></div>
            <!-- 中心文字 -->
            <div class="absolute flex flex-col items-center justify-center z-10">
              <span class="text-2xl font-bold text-slate-700 leading-none">{{ sichuanStats.total_rules }}</span>
              <span class="text-[10px] text-slate-400 mt-1">总规则</span>
            </div>
          </div>
          <div class="space-y-3 text-sm flex-1">
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-red-400 mr-2"></span>高复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-red-500 transition-colors">{{ sichuanStats.complexity_distribution?.['高复杂度'] || 0 }}</span>
            </div>
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-amber-400 mr-2"></span>中复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-amber-500 transition-colors">{{ sichuanStats.complexity_distribution?.['中复杂度'] || 0 }}</span>
            </div>
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>低复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-emerald-500 transition-colors">{{ sichuanStats.complexity_distribution?.['低复杂度'] || 0 }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 卡片 2: 缺陷级别 (进度条) -->
      <div class="stats-card flex flex-col">
        <div class="flex justify-between items-start mb-4">
          <h3 class="stats-title">缺陷级别分布</h3>
          <AlertOutlined class="stats-icon" />
        </div>
        <div class="space-y-5 flex-1 justify-center flex flex-col">
          <div>
            <div class="flex justify-between text-xs mb-1.5">
              <span class="text-slate-500 font-medium">严重缺陷 (阻断)</span>
              <span class="text-red-500 font-bold">{{ sichuanStats.defect_level_distribution?.['严重缺陷'] || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-red-500 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(239,68,68,0.2)]" :style="{ width: getPercentage(sichuanStats.defect_level_distribution?.['严重缺陷']) + '%' }"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1.5">
              <span class="text-slate-500 font-medium">一般缺陷 (警告)</span>
              <span class="text-orange-400 font-bold">{{ sichuanStats.defect_level_distribution?.['一般缺陷'] || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-orange-400 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(251,191,36,0.2)]" :style="{ width: getPercentage(sichuanStats.defect_level_distribution?.['一般缺陷']) + '%' }"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-xs mb-1.5">
              <span class="text-slate-500 font-medium">轻微缺陷 (提示)</span>
              <span class="text-emerald-500 font-bold">{{ sichuanStats.defect_level_distribution?.['轻微缺陷'] || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-emerald-500 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(16,185,129,0.2)]" :style="{ width: getPercentage(sichuanStats.defect_level_distribution?.['轻微缺陷']) + '%' }"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 卡片 3: 规则分类 (网格) -->
      <div class="stats-card flex flex-col">
        <div class="flex justify-between items-start mb-4">
          <h3 class="stats-title">规则分类统计</h3>
          <AppstoreOutlined class="stats-icon" />
        </div>
        <div class="grid grid-cols-3 gap-3 mt-2 flex-1">
          <div v-for="(cat, idx) in topCategories" :key="cat.name"
            :class="['stat-grid-item', categoryColors[idx % categoryColors.length]]"
          >
            <div class="text-xl font-bold mb-1">{{ cat.count }}</div>
            <div class="text-[10px] font-medium opacity-70 truncate w-full text-center" :title="cat.name">{{ cat.name }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 列表操作栏 -->
    <div class="flex flex-col sm:flex-row justify-between items-center mb-5 gap-4">
      <div class="relative w-full sm:w-96 search-wrapper group">
        <SearchOutlined class="search-icon group-hover:text-blue-500 transition-colors" />
        <input 
          type="text" 
          placeholder="搜索规则编号、名称..." 
          class="search-input"
          @input="e => handleSearch((e.target as HTMLInputElement).value)"
        >
      </div>
      <div class="flex gap-3 w-full sm:w-auto justify-end">
        <button class="modern-btn-ghost" @click="refreshSichuanRules">
          <ReloadOutlined :class="{ 'animate-spin': loading }" />
          <span class="hidden sm:inline ml-1">刷新</span>
        </button>
        <button class="modern-btn-ghost">
          <FilterOutlined />
          <span class="hidden sm:inline ml-1">筛选</span>
          </button>
        <button class="modern-btn-primary" @click="showQCEvaluation = true">
          <PlayCircleOutlined class="mr-1" />
          开始质控评估
        </button>
      </div>
    </div>

    <!-- 3. 数据表格 -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
      <a-table
        :dataSource="sichuanRules"
        :columns="sichuanColumns"
        :loading="loading"
        :pagination="tablePagination"
        class="modern-table"
        :scroll="{ x: 1200 }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <!-- 编号列：Mono字体 + 浅色背景 -->
          <template v-if="column.key === 'rule_id'">
            <span class="font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded text-xs font-semibold select-all border border-slate-200">
              {{ record.rule_code || record.rule_id }}
            </span>
          </template>

          <!-- 规则名称 + 分类标签 -->
          <template v-if="column.key === 'name'">
            <div class="pr-2">
              <div class="text-slate-800 font-semibold text-[13px] leading-snug mb-0.5">{{ record.name }}</div>
              <div class="flex items-center gap-1.5">
                <span
                  class="inline-flex items-center px-1.5 py-px rounded text-[10px] font-medium shrink-0"
                  :class="getDocTypeColorClass(record.category)"
                >
                  {{ getCategoryZh(record.category) }}
                </span>
                <span class="text-slate-400 text-[11px] truncate max-w-[240px]" :title="record.description">
                  {{ record.description }}
                </span>
              </div>
            </div>
          </template>

          <!-- 复杂度 -->
          <template v-if="column.key === 'complexity'">
            <span 
              class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold"
              :class="getComplexityClass(record.complexity)"
            >
              {{ record.complexity }}
            </span>
          </template>

          <!-- 缺陷级别 -->
          <template v-if="column.key === 'defect_level'">
             <span 
              class="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold"
              :class="getDefectLevelClass(record.defect_level)"
            >
              {{ getSeverityZh(record.defect_level) }}
            </span>
          </template>

          <!-- 适用文书 -->
          <template v-if="column.key === 'applicable_documents'">
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="docType in record.applicable_documents.slice(0, 2)"
                :key="docType"
                class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium"
                :class="getDocTypeColorClass(docType)"
              >
                {{ getDocTypeZh(docType) || '未知' }}
              </span>
              <a-tooltip v-if="record.applicable_documents.length > 2">
                <template #title>
                  {{ record.applicable_documents.slice(2).map(d => getDocTypeZh(d)).join(', ') }}
                </template>
                <span class="text-[10px] text-slate-400 px-1.5 py-0.5 cursor-help bg-slate-50 rounded border border-slate-100">
                  +{{ record.applicable_documents.length - 2 }}
                </span>
              </a-tooltip>
            </div>
          </template>

          <!-- 操作列 -->
          <template v-if="column.key === 'actions'">
            <div class="flex items-center justify-end gap-3">
              <a-tooltip title="查看详情">
                <button class="icon-btn text-slate-400 bg-slate-50 hover:text-blue-600 hover:bg-blue-50 border border-transparent hover:border-blue-100" @click="viewSichuanRuleDetail(record)">
                  <EyeOutlined />
                </button>
              </a-tooltip>
              <button class="table-action-btn" @click="startQCWithRule(record)">
                评估
              </button>
            </div>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 模态框保持不变，复用原有逻辑 -->
    <a-modal
      v-model:open="showRuleDetail"
      title="规则详情"
      width="800px"
      :footer="null"
      centered
      class="modern-modal"
    >
      <!-- 保持原有详情内容 -->
      <div v-if="selectedRule" class="rule-detail p-2">
        <div class="bg-slate-50 p-5 rounded-xl mb-6 border border-slate-100">
          <div class="flex justify-between items-start mb-3">
            <h3 class="text-lg font-bold text-slate-800">{{ selectedRule.name }}</h3>
            <span class="font-mono text-blue-600 bg-white px-2 py-1 rounded border border-blue-100 text-xs">{{ selectedRule.rule_id }}</span>
          </div>
          <p class="text-slate-600 text-sm leading-relaxed">{{ selectedRule.description }}</p>
        </div>
        
        <a-descriptions :column="2" size="small" class="mb-6">
          <a-descriptions-item label="分类">{{ getCategoryZh(selectedRule.category) }}</a-descriptions-item>
          <a-descriptions-item label="复杂度">
             <span :class="['px-2 py-0.5 rounded-md text-xs', getComplexityClass(selectedRule.complexity)]">{{ selectedRule.complexity }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷级别">
             <span :class="['px-2 py-0.5 rounded-md text-xs', getDefectLevelClass(selectedRule.defect_level)]">{{ getSeverityZh(selectedRule.defect_level) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="扣分">{{ selectedRule.score_deduction }}分</a-descriptions-item>
          <a-descriptions-item label="适用文书">
            <div class="flex gap-1 flex-wrap">
              <span v-for="d in selectedRule.applicable_documents" :key="d" class="bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded text-xs">
                {{ getDocTypeZh(d) }}
              </span>
            </div>
          </a-descriptions-item>
        </a-descriptions>

        <template v-if="isAdmin">
          <div class="pt-6 border-t border-slate-100">
            <div class="flex justify-between items-center mb-4">
              <h4 class="font-bold text-slate-700 flex items-center gap-2 text-sm">
                <CodeOutlined /> 提示词管理
                <span class="text-[10px] font-normal bg-amber-50 text-amber-600 px-2 py-0.5 rounded border border-amber-100">Admin</span>
              </h4>
              <a-button v-if="!isEditingPrompt" type="link" size="small" @click="startEditPrompt">编辑</a-button>
              <div v-else class="flex gap-2">
                <a-button size="small" @click="cancelEditPrompt">取消</a-button>
                <a-button type="primary" size="small" @click="savePrompt" :loading="promptLoading">保存</a-button>
              </div>
            </div>
            
            <div v-if="!isEditingPrompt" class="bg-slate-900 text-slate-300 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar border border-slate-800">
              {{ currentPrompt || '// 暂无自定义提示词，使用系统默认模板' }}
            </div>
            <a-textarea
              v-else
              v-model:value="editingPrompt"
              :rows="10"
              class="font-mono text-xs bg-white border-slate-200 rounded-lg"
              placeholder="输入自定义 Prompt..."
            />
          </div>
        </template>
      </div>
    </a-modal>

    <!-- 规则测试模态框 -->
    <a-modal
      v-model:open="showRuleTest"
      title="规则测试"
      width="900px"
      :footer="null"
      centered
      :destroyOnClose="true"
      class="modern-modal"
    >
      <div v-if="testingRule" class="p-2">
        <div class="flex items-center justify-between mb-6 bg-blue-50/50 p-4 rounded-xl border border-blue-100">
          <div>
            <div class="font-bold text-slate-800 mb-1">{{ testingRule.name }}</div>
            <div class="text-xs text-slate-500">测试该规则的 AI 识别准确性</div>
          </div>
          <div class="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
            <button 
              class="px-3 py-1.5 text-xs rounded-md transition-colors font-medium"
              :class="testExampleType === 'negative' ? 'bg-red-50 text-red-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="switchExampleType('negative')"
            >
              反例 (有缺陷)
            </button>
            <button 
              class="px-3 py-1.5 text-xs rounded-md transition-colors font-medium"
              :class="testExampleType === 'positive' ? 'bg-emerald-50 text-emerald-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
              @click="switchExampleType('positive')"
            >
              正例 (无缺陷)
            </button>
          </div>
        </div>

        <div class="mb-6">
         <a-textarea
            v-model:value="testMedicalText"
            :rows="8"
            class="text-sm text-slate-700 bg-white border-slate-200 focus:border-blue-500 rounded-xl p-4 shadow-sm"
            placeholder="输入病历文本..."
          />
        </div>

        <div class="flex justify-end mb-6">
          <button class="modern-btn-primary px-6 py-2" :disabled="testLoading" @click="executeRuleTest">
            <ThunderboltOutlined v-if="!testLoading" class="mr-2" />
            <ReloadOutlined v-else class="mr-2 animate-spin" />
              {{ testLoading ? '测试中...' : '开始测试' }}
            </button>
          </div>

        <transition name="fade">
          <div v-if="testResult" class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-md animate-fade-in-up">
            <div class="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <h4 class="font-bold text-slate-700">测试结果</h4>
              <div class="flex items-center gap-3">
                <span class="text-xs text-slate-500 font-medium">置信度</span>
                <div class="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div class="h-full bg-blue-500 rounded-full" :style="{ width: (testResult.confidence * 100) + '%' }"></div>
                </div>
                <span class="text-sm font-bold text-blue-600">{{ Math.round(testResult.confidence * 100) }}%</span>
              </div>
            </div>
            
            <div class="p-6">
              <div class="flex items-start gap-4 mb-5">
                <div 
                  class="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm"
                  :class="testResult.is_compliant ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'"
                >
                  <CheckCircleFilled v-if="testResult.is_compliant" class="text-2xl" />
                  <ExclamationCircleFilled v-else class="text-2xl" />
                </div>
                <div>
                  <div class="font-bold text-lg mb-1" :class="testResult.is_compliant ? 'text-emerald-700' : 'text-red-700'">
                    {{ testResult.is_compliant ? '符合规则要求' : '不符合规则要求' }}
                  </div>
                  <p class="text-sm text-slate-600 leading-relaxed">{{ testResult.findings }}</p>
                </div>
              </div>

              <div v-if="testResult.evidence" class="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-100">
                <div class="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider flex items-center gap-1">
                  <SearchOutlined /> 证据引用
                </div>
                <div class="text-sm text-slate-700 font-mono bg-white p-3 rounded-lg border border-slate-200 border-l-4 border-l-blue-400 shadow-sm">
                  {{ testResult.evidence }}
                </div>
              </div>

              <div v-if="testResult.suggestion" class="flex gap-3 items-start text-sm bg-blue-50 text-blue-800 p-4 rounded-xl border border-blue-100">
                <InfoCircleFilled class="mt-0.5 flex-shrink-0 text-blue-600" />
                <span class="font-medium">{{ testResult.suggestion }}</span>
              </div>
             </div>
          </div>
        </transition>
      </div>
    </a-modal>

    <!-- 占位模态框 -->
    <a-modal v-model:open="showQCEvaluation" title="质控评估" :footer="null" centered>
      <div class="text-center p-8">
        <a-result status="info" title="功能开发中" sub-title="请前往主质控评估页面进行完整操作" />
      </div>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  FilterOutlined,
  PieChartOutlined,
  AlertOutlined,
  AppstoreOutlined,
  CheckCircleFilled,
  ExclamationCircleFilled,
  InfoCircleFilled,
  ThunderboltOutlined,
  CodeOutlined
} from '@ant-design/icons-vue'
import { ApiService } from '@/services/apiService'
import type { User } from '@/types/auth'
import { UserRole } from '@/types/auth'
import { qcRuleCaseMap, buildCaseText } from '@/data/qcRuleCases'

// 接口定义
interface SichuanQCRule {
  rule_id: string
  rule_code?: string
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

// 状态
const loading = ref(false)
const sichuanRules = ref<SichuanQCRule[]>([])
const sichuanStats = ref<SichuanQCStats>({
  total_rules: 0,
  rule_categories: [],
  complexity_distribution: {},
  defect_level_distribution: {}
})
const searchText = ref('')
const currentUser = ref<User | null>(null)
const isAdmin = computed(() => currentUser.value?.roles?.includes(UserRole.ADMIN) || false)

// 分页
const tablePagination = ref({
  current: 1, 
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  pageSizeOptions: ['20', '50', '100'],
  showTotal: (total: number, range: [number, number]) => `共 ${total} 条`,
  size: 'small'
})

// 模态框状态
const showRuleDetail = ref(false)
const selectedRule = ref<SichuanQCRule | null>(null)
const showQCEvaluation = ref(false)
const showRuleTest = ref(false)
const testingRule = ref<SichuanQCRule | null>(null)
const testMedicalText = ref('')
const testLoading = ref(false)
const testExampleType = ref<'positive' | 'negative'>('negative')
const testResult = ref<any>(null)

// 提示词管理
const isEditingPrompt = ref(false)
const currentPrompt = ref('')
const editingPrompt = ref('')
const promptLoading = ref(false)

// 颜色计算属性
const complexityConicGradient = computed(() => {
  const stats = sichuanStats.value.complexity_distribution || {}
  const high = stats['高复杂度'] || 0
  const mid = stats['中复杂度'] || 0
  const low = stats['低复杂度'] || 0
  const total = high + mid + low || 1

  const p1 = (high / total) * 100
  const p2 = p1 + (mid / total) * 100

  return {
    background: `conic-gradient(#F87171 0% ${p1}%, #FBBF24 ${p1}% ${p2}%, #34D399 ${p2}% 100%)`
  }
})

const getPercentage = (count: number | undefined) => {
  if (!count) return 0
  const total = sichuanStats.value.total_rules || 1
  return (count / total) * 100
}

const getCategoryCount = (cat: string) => {
  return sichuanRules.value.filter(r => r.category === cat).length
}

// 动态获取 top 3 分类
const topCategories = computed(() => {
  const counts: Record<string, number> = {}
  sichuanRules.value.forEach(r => {
    counts[r.category] = (counts[r.category] || 0) + 1
  })
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name, count]) => ({ name, count }))
})

const categoryColors = [
  'bg-blue-50/50 border-blue-100 text-blue-600',
  'bg-cyan-50/50 border-cyan-100 text-cyan-600',
  'bg-purple-50/50 border-purple-100 text-purple-600'
]

// 表格列定义（去掉重复的"分类"列，该信息已融入规则名称行）
const sichuanColumns = [
  { title: '序号', key: 'index', width: 60, fixed: 'left', align: 'center', customRender: ({ index }: { index: number }) => (tablePagination.value.current - 1) * tablePagination.value.pageSize + index + 1 },
  { title: '编号', key: 'rule_id', width: 90, fixed: 'left' },
  { title: '规则名称', key: 'name', width: 360 },
  { title: '复杂度', key: 'complexity', width: 100 },
  { title: '缺陷级别', key: 'defect_level', width: 100 },
  { title: '适用文书', key: 'applicable_documents', width: 160 },
  { title: '操作', key: 'actions', width: 120, fixed: 'right', align: 'right' }
]

// 方法
const refreshSichuanRules = async () => {
  loading.value = true
  try {
    const response = await fetch(`/api/v1/qc/sichuan/rules?_ts=${Date.now()}`)
    if (response.ok) {
      const data = await response.json()
      const normalizeRule = (r: any): SichuanQCRule => ({
        rule_id: r.rule_id || r.id || '',
        rule_code: r.rule_code,
        name: r.name || r.rule_name || '未命名',
        description: r.description || r.desc || '',
        category: r.category || '基础',
        complexity: r.complexity || '中复杂度',
        defect_level: r.defect_level || '一般缺陷',
        score_deduction: r.score_deduction ?? 0,
        applicable_documents: r.applicable_documents || [],
        medical_domain: r.medical_domain || '通用',
        requires_rag: Boolean(r.requires_rag),
        requires_cot: Boolean(r.requires_cot)
      })
      
      sichuanRules.value = (data.rules || []).map(normalizeRule)

      // 从规则数据中计算统计分布（后端可能返回空对象）
      const rules = sichuanRules.value
      const computedComplexity: Record<string, number> = {}
      const computedDefect: Record<string, number> = {}
      rules.forEach(r => {
        computedComplexity[r.complexity] = (computedComplexity[r.complexity] || 0) + 1
        computedDefect[r.defect_level] = (computedDefect[r.defect_level] || 0) + 1
      })

      const apiComplexity = data.complexity_distribution || {}
      const apiDefect = data.defect_level_distribution || {}

      sichuanStats.value = {
        total_rules: data.total_rules || rules.length,
        rule_categories: data.rule_categories || [...new Set(rules.map(r => r.category))],
        complexity_distribution: Object.keys(apiComplexity).length > 0 ? apiComplexity : computedComplexity,
        defect_level_distribution: Object.keys(apiDefect).length > 0 ? apiDefect : computedDefect
      }
      tablePagination.value.total = sichuanRules.value.length
      message.success('刷新成功')
    }
  } catch (e) {
    message.error('加载失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 辅助方法
const handleSearch = (val: string) => {
  searchText.value = val
  // 实际项目中这里应调用后端搜索接口，或实现前端过滤
  // 此处仅演示 UI，未实现完整前端过滤逻辑
}

const handleTableChange = (pag: any) => {
  tablePagination.value.current = pag.current
  tablePagination.value.pageSize = pag.pageSize
}

const viewSichuanRuleDetail = async (rule: SichuanQCRule) => {
  selectedRule.value = rule
  showRuleDetail.value = true
  if (isAdmin.value) {
    // 模拟获取 Prompt
    promptLoading.value = true
    setTimeout(() => {
      currentPrompt.value = `你是一名专业的医疗质控专家...\n请检查以下规则：${rule.name}\n...`
      promptLoading.value = false
    }, 500)
  }
}

const startQCWithRule = (rule: SichuanQCRule) => {
  testingRule.value = rule
  testExampleType.value = 'negative'
  switchExampleType('negative')
  showRuleTest.value = true
  testResult.value = null
}

const switchExampleType = (type: 'positive' | 'negative') => {
  testExampleType.value = type
  if (testingRule.value) {
    const ruleId = testingRule.value.rule_id
    const ruleCase = qcRuleCaseMap[ruleId]
    if (ruleCase) {
      const example = type === 'positive' ? ruleCase.positive : ruleCase.negative
      testMedicalText.value = buildCaseText(example, { includeHints: false, includeTitle: false, includeAnalysis: false, includeFocusPoints: false })
    } else {
      testMedicalText.value = '暂无示例文本，请手动输入。'
    }
  }
}

const executeRuleTest = async () => {
    testLoading.value = true
  // 模拟 API 调用
    setTimeout(() => {
        testLoading.value = false
    const isCompliant = testExampleType.value === 'positive'
        testResult.value = {
      is_compliant: isCompliant,
      confidence: 0.95,
      findings: isCompliant ? '未发现明显缺陷。' : '发现患者入院记录中缺少现病史详细描述。',
      evidence: isCompliant ? '' : '现病史：[空白]',
      suggestion: isCompliant ? '' : '请补充现病史信息。'
        }
    }, 1500)
}

// Prompt 管理
const startEditPrompt = () => {
  editingPrompt.value = currentPrompt.value
  isEditingPrompt.value = true
}
const cancelEditPrompt = () => {
  isEditingPrompt.value = false
}
const savePrompt = () => {
  promptLoading.value = true
  setTimeout(() => {
    currentPrompt.value = editingPrompt.value
    isEditingPrompt.value = false
    promptLoading.value = false
    message.success('保存成功')
  }, 800)
}

// 样式映射 - 使用更柔和的微着色风格
const getComplexityClass = (val: string) => {
  if (val === '高复杂度') return 'bg-red-50 text-red-700 border border-red-100'
  if (val === '中复杂度') return 'bg-amber-50 text-amber-700 border border-amber-100'
  return 'bg-emerald-50 text-emerald-700 border border-emerald-100'
}

const getDefectLevelClass = (val: string) => {
  if (val?.includes('严重') || val === 'critical') return 'bg-rose-50 text-rose-700 border border-rose-100'
  if (val?.includes('一般') || val === 'major') return 'bg-orange-50 text-orange-700 border border-orange-100'
  return 'bg-slate-100 text-slate-600 border border-slate-200'
}

// 文本映射
const CANONICAL_LABEL_ZH: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  discharge_record: '出院记录',
  operation_record: '手术记录',
  examination_report: '辅助检查',
  consent_form: '知情同意书'
}
const getDocTypeZh = (val: string) => CANONICAL_LABEL_ZH[val] || val
const getSeverityZh = (val: string) => val
const getCategoryZh = (val: string) => val

// 文书类型颜色映射
const DOC_TYPE_COLORS: Record<string, string> = {
  '入院记录': 'bg-blue-50 text-blue-600 border border-blue-100',
  'admission_record': 'bg-blue-50 text-blue-600 border border-blue-100',
  '病程记录': 'bg-teal-50 text-teal-600 border border-teal-100',
  'progress_note': 'bg-teal-50 text-teal-600 border border-teal-100',
  '出院记录': 'bg-violet-50 text-violet-600 border border-violet-100',
  '(死亡)出院记录': 'bg-violet-50 text-violet-600 border border-violet-100',
  'discharge_record': 'bg-violet-50 text-violet-600 border border-violet-100',
  '手术记录': 'bg-rose-50 text-rose-600 border border-rose-100',
  '手术相关记录': 'bg-rose-50 text-rose-600 border border-rose-100',
  'operation_record': 'bg-rose-50 text-rose-600 border border-rose-100',
  '辅助检查': 'bg-amber-50 text-amber-600 border border-amber-100',
  'examination_report': 'bg-amber-50 text-amber-600 border border-amber-100',
  '知情同意书': 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  '知情同意': 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  'consent_form': 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  '医嘱': 'bg-indigo-50 text-indigo-600 border border-indigo-100',
  '会诊记录': 'bg-orange-50 text-orange-600 border border-orange-100',
  '输血记录': 'bg-pink-50 text-pink-600 border border-pink-100',
  '麻醉记录': 'bg-lime-50 text-lime-600 border border-lime-100',
}
const getDocTypeColorClass = (val: string) => DOC_TYPE_COLORS[val] || 'bg-slate-50 text-slate-600 border border-slate-100'

onMounted(() => {
  refreshSichuanRules()
  ApiService.getCurrentUser().then(res => {
    if (res.success) currentUser.value = res.data
  })
})
</script>

<style scoped>
.semantic-rules-manager {
  padding: 0;
}

/* 卡片样式 */
.stats-card {
  background: white;
  border-radius: 1.25rem; /* 20px */
  padding: 1.75rem;
  box-shadow: 0 4px 24px -4px rgba(0,0,0,0.04);
  border: 1px solid #f1f5f9;
  height: 100%;
  min-height: 240px;
}

.stats-title {
  color: #475569;
  font-weight: 600;
  font-size: 0.9rem;
}

.stats-icon {
  color: #cbd5e1;
  font-size: 1.25rem;
}

/* 统计网格项 */
.stat-grid-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 1rem;
  border-radius: 1rem;
  border-width: 1px;
  border-style: solid;
  height: 100%;
  transition: all 0.2s;
}
.stat-grid-item:hover {
  transform: translateY(-2px);
}

/* 搜索框 */
.search-wrapper {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
  font-size: 1rem;
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding-left: 2.75rem;
  padding-right: 1rem;
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  font-size: 0.9rem;
  color: #334155;
  transition: all 0.2s;
  outline: none;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

.search-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
}

/* 按钮样式 */
.modern-btn-ghost {
  padding: 0.6rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: #64748b;
  background: transparent;
  border: 1px solid transparent;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.modern-btn-ghost:hover {
  background-color: #white;
  color: #3b82f6;
  background: #eff6ff;
}

.modern-btn-primary {
  padding: 0.6rem 1.25rem;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
  color: white;
  font-size: 0.9rem;
  font-weight: 600;
  border: none;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.modern-btn-primary:hover {
  background: linear-gradient(135deg, #4338ca 0%, #2563eb 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(59, 130, 246, 0.35);
}

/* 表格样式 */
.modern-table :deep(.ant-table-thead > tr > th) {
  background: #f8fafc;
  color: #475569;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  border-bottom: 1px solid #e2e8f0;
  padding: 0.65rem 0.75rem;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.85rem;
}

.modern-table :deep(.ant-table-tbody > tr:hover > td) {
  background: #f8fafc !important;
}

/* 表格操作按钮 */
.table-action-btn {
  font-size: 0.75rem;
  font-weight: 600;
  color: #3b82f6;
  padding: 0.35rem 0.85rem;
  border: 1px solid #bfdbfe;
  border-radius: 0.5rem;
  background: #eff6ff;
  transition: all 0.2s;
}
.table-action-btn:hover {
  background: #3b82f6;
  color: white;
  border-color: #3b82f6;
}

.icon-btn {
  padding: 0.35rem;
  border-radius: 0.5rem;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.animate-fade-in-up {
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
