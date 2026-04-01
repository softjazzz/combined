<template>
  <div class="semantic-rules-manager">
    <section class="ops-context block-enter">
      <div>
        <p class="ops-eyebrow">
          四川省语义质控规则库
        </p>
        <h2 class="ops-title">
          规则运营总览
        </h2>
        <p class="ops-subtitle">
          面向病历质控运营与审计，统一管理规则复杂度、缺陷风险与执行入口。
        </p>
      </div>
      <div class="ops-kpis">
        <div class="ops-kpi">
          <span class="ops-kpi-label">总规则</span>
          <span class="ops-kpi-value">{{ sichuanStats.total_rules }}</span>
        </div>
        <div class="ops-kpi ops-kpi-warn">
          <span class="ops-kpi-label">严重缺陷</span>
          <span class="ops-kpi-value">{{ criticalDefectCount }}</span>
        </div>
        <div class="ops-kpi">
          <span class="ops-kpi-label">最近同步</span>
          <span class="ops-kpi-value">{{ lastRefreshedLabel }}</span>
        </div>
      </div>
    </section>

    <section class="insight-grid block-enter-delayed">
      <article class="insight-panel insight-panel-primary">
        <div class="insight-head">
          <h3 class="insight-title">
            规则复杂度结构
          </h3>
          <PieChartOutlined class="insight-icon" />
        </div>
        <div class="flex items-center flex-1">
          <div
            class="complexity-donut"
            :style="complexityConicGradient"
          >
            <div class="complexity-inner">
              <span class="complexity-total">{{ sichuanStats.total_rules }}</span>
              <span class="complexity-label">总规则</span>
            </div>
          </div>
          <div class="complexity-list">
            <div class="complexity-item">
              <span class="complexity-name"><span class="complexity-dot danger" />高复杂度</span>
              <span class="complexity-value">{{ complexityBreakdown.high }}</span>
            </div>
            <div class="complexity-item">
              <span class="complexity-name"><span class="complexity-dot warning" />中复杂度</span>
              <span class="complexity-value">{{ complexityBreakdown.medium }}</span>
            </div>
            <div class="complexity-item">
              <span class="complexity-name"><span class="complexity-dot safe" />低复杂度</span>
              <span class="complexity-value">{{ complexityBreakdown.low }}</span>
            </div>
          </div>
        </div>
      </article>

      <article class="insight-panel">
        <div class="insight-head">
          <h3 class="insight-title">
            缺陷风险分布
          </h3>
          <AlertOutlined class="insight-icon" />
        </div>
        <div class="risk-list">
          <div class="risk-row">
            <div class="risk-meta">
              <span>严重缺陷（阻断）</span>
              <span class="risk-count danger">{{ criticalDefectCount }}</span>
            </div>
            <div class="risk-track">
              <div
                class="risk-fill danger"
                :style="{ width: `${getDefectRate(criticalDefectCount)}%` }"
              />
            </div>
          </div>
          <div class="risk-row">
            <div class="risk-meta">
              <span>一般缺陷（警告）</span>
              <span class="risk-count warning">{{ majorDefectCount }}</span>
            </div>
            <div class="risk-track">
              <div
                class="risk-fill warning"
                :style="{ width: `${getDefectRate(majorDefectCount)}%` }"
              />
            </div>
          </div>
          <div class="risk-row">
            <div class="risk-meta">
              <span>轻微缺陷（提示）</span>
              <span class="risk-count safe">{{ minorDefectCount }}</span>
            </div>
            <div class="risk-track">
              <div
                class="risk-fill safe"
                :style="{ width: `${getDefectRate(minorDefectCount)}%` }"
              />
            </div>
          </div>
        </div>
        <div class="risk-footnote">
          风险密度 {{ riskDensity }}
        </div>
      </article>

      <article class="insight-panel">
        <div class="insight-head">
          <h3 class="insight-title">
            分类覆盖 Top3
          </h3>
          <AppstoreOutlined class="insight-icon" />
        </div>
        <div class="category-list">
          <div
            v-for="(cat, idx) in topCategories"
            :key="cat.name"
            class="category-item"
          >
            <div class="category-index">
              0{{ idx + 1 }}
            </div>
            <div class="category-meta">
              <span class="category-name">{{ cat.name }}</span>
              <span class="category-ratio">{{ getCategoryRatio(cat.count) }}</span>
            </div>
            <div class="category-count">
              {{ cat.count }}
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="ops-toolbar block-enter-delayed-2">
      <div class="relative w-full sm:w-[420px] search-wrapper group">
        <SearchOutlined class="search-icon group-hover:text-blue-500 transition-colors" />
        <input
          type="text"
          placeholder="搜索规则编号、名称或文书类型"
          class="search-input"
          @input="(e) => handleSearch((e.target as HTMLInputElement).value)"
        >
      </div>
      <div class="toolbar-actions">
        <button
          class="modern-btn-ghost"
          @click="refreshSichuanRules"
        >
          <ReloadOutlined :class="{ 'animate-spin': loading }" />
          <span class="hidden sm:inline ml-1">刷新</span>
        </button>
        <button class="modern-btn-ghost">
          <FilterOutlined />
          <span class="hidden sm:inline ml-1">筛选</span>
        </button>
        <button
          class="modern-btn-primary"
          @click="showQCEvaluation = true"
        >
          <PlayCircleOutlined class="mr-1" />
          开始质控评估
        </button>
        <button
          class="modern-btn-primary-alt"
          @click="openCustomWorkspace"
        >
          <AppstoreOutlined class="mr-1" />
          自定义规则工作台
        </button>
      </div>
    </section>

    <section class="table-shell block-enter-delayed-2">
      <div class="table-shell-head">
        <div>
          <p class="table-shell-eyebrow">
            Rule Workspace
          </p>
          <h3 class="table-shell-title">
            规则执行工作台
          </h3>
        </div>
        <div class="table-shell-meta">
          <span class="table-shell-count">{{ filteredRules.length }}</span>
          <span class="table-shell-label">当前结果</span>
        </div>
      </div>
      <a-table
        :data-source="filteredRules"
        :columns="sichuanColumns"
        :loading="loading"
        :pagination="tablePagination"
        class="modern-table"
        :scroll="{ x: 1200 }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'rule_id'">
            <span class="rule-code-pill">
              {{ record.rule_code || record.rule_id }}
            </span>
          </template>

          <template v-if="column.key === 'name'">
            <div class="rule-main">
              <div class="rule-main-title">
                {{ record.name }}
              </div>
              <div class="rule-main-meta">
                <span
                  class="rule-category-pill"
                  :class="getDocTypeColorClass(record.category)"
                >
                  {{ getCategoryZh(record.category) }}
                </span>
                <span
                  class="rule-main-desc"
                  :title="record.description"
                >
                  检查内容：{{ record.description }}
                </span>
              </div>
            </div>
          </template>

          <template v-if="column.key === 'complexity'">
            <span
              class="status-pill"
              :class="getComplexityClass(record.complexity)"
            >
              {{ record.complexity }}
            </span>
          </template>

          <template v-if="column.key === 'defect_level'">
            <span
              class="status-pill"
              :class="getDefectLevelClass(record.defect_level)"
            >
              {{ getSeverityZh(record.defect_level) }}
            </span>
          </template>

          <template v-if="column.key === 'applicable_documents'">
            <div class="doc-pill-stack">
              <span
                v-for="docType in record.applicable_documents.slice(0, 2)"
                :key="docType"
                class="doc-pill"
                :class="getDocTypeColorClass(docType)"
              >
                {{ getDocTypeZh(docType) || '未知' }}
              </span>
              <a-tooltip v-if="record.applicable_documents.length > 2">
                <template #title>
                  {{
                    record.applicable_documents
                      .slice(2)
                      .map((d: string) => getDocTypeZh(d))
                      .join(', ')
                  }}
                </template>
                <span class="doc-pill-more"> +{{ record.applicable_documents.length - 2 }} </span>
              </a-tooltip>
            </div>
          </template>

          <template v-if="column.key === 'actions'">
            <div class="table-actions">
              <a-tooltip title="查看详情">
                <button
                  class="icon-btn"
                  @click="viewSichuanRuleDetail(record as SichuanQCRule)"
                >
                  <EyeOutlined />
                </button>
              </a-tooltip>
              <button
                class="table-action-btn"
                @click="startQCWithRule(record as SichuanQCRule)"
              >
                评估
              </button>
            </div>
          </template>
        </template>
      </a-table>
    </section>

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
      <div
        v-if="selectedRule"
        class="rule-detail p-2"
      >
        <div class="bg-slate-50 p-5 rounded-xl mb-6 border border-slate-100">
          <div class="flex justify-between items-start mb-3">
            <h3 class="text-lg font-bold text-slate-800">
              {{ selectedRule.name }}
            </h3>
            <span
              class="font-mono text-blue-600 bg-white px-2 py-1 rounded border border-blue-100 text-xs"
            >{{ selectedRule.rule_id }}</span>
          </div>
          <p class="text-slate-600 text-sm leading-relaxed">
            {{ selectedRule.description }}
          </p>
        </div>

        <a-descriptions
          :column="2"
          size="small"
          class="mb-6"
        >
          <a-descriptions-item label="分类">
            {{ getCategoryZh(selectedRule.category) }}
          </a-descriptions-item>
          <a-descriptions-item label="复杂度">
            <span
              :class="[
                'px-2 py-0.5 rounded-md text-xs',
                getComplexityClass(selectedRule.complexity),
              ]"
            >{{ selectedRule.complexity }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="缺陷级别">
            <span
              :class="[
                'px-2 py-0.5 rounded-md text-xs',
                getDefectLevelClass(selectedRule.defect_level),
              ]"
            >{{ getSeverityZh(selectedRule.defect_level) }}</span>
          </a-descriptions-item>
          <a-descriptions-item label="扣分">
            {{ selectedRule.score_deduction }}分
          </a-descriptions-item>
          <a-descriptions-item label="适用文书">
            <div class="flex gap-1 flex-wrap">
              <span
                v-for="d in selectedRule.applicable_documents"
                :key="d"
                class="bg-blue-50 text-blue-700 border border-blue-100 px-2 py-0.5 rounded text-xs"
              >
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
                <span
                  class="text-[10px] font-normal bg-amber-50 text-amber-600 px-2 py-0.5 rounded border border-amber-100"
                >Admin</span>
              </h4>
              <a-button
                v-if="!isEditingPrompt"
                type="link"
                size="small"
                @click="startEditPrompt"
              >
                编辑
              </a-button>
              <div
                v-else
                class="flex gap-2"
              >
                <a-button
                  size="small"
                  @click="cancelEditPrompt"
                >
                  取消
                </a-button>
                <a-button
                  type="primary"
                  size="small"
                  :loading="promptLoading"
                  @click="savePrompt"
                >
                  保存
                </a-button>
              </div>
            </div>

            <div
              v-if="!isEditingPrompt"
              class="bg-slate-900 text-slate-300 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar border border-slate-800"
            >
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
      :destroy-on-close="true"
      class="modern-modal"
    >
      <div
        v-if="testingRule"
        class="p-2"
      >
        <div
          class="flex items-center justify-between mb-6 bg-blue-50/50 p-4 rounded-xl border border-blue-100"
        >
          <div>
            <div class="font-bold text-slate-800 mb-1">
              {{ testingRule.name }}
            </div>
            <div class="text-xs text-slate-500">
              测试该规则的 AI 识别准确性
            </div>
          </div>
          <div class="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
            <button
              class="px-3 py-1.5 text-xs rounded-md transition-colors font-medium"
              :class="
                testExampleType === 'negative'
                  ? 'bg-red-50 text-red-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              "
              @click="switchExampleType('negative')"
            >
              反例 (有缺陷)
            </button>
            <button
              class="px-3 py-1.5 text-xs rounded-md transition-colors font-medium"
              :class="
                testExampleType === 'positive'
                  ? 'bg-emerald-50 text-emerald-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              "
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
          <button
            class="modern-btn-primary px-6 py-2"
            :disabled="testLoading"
            @click="executeRuleTest"
          >
            <ThunderboltOutlined
              v-if="!testLoading"
              class="mr-2"
            />
            <ReloadOutlined
              v-else
              class="mr-2 animate-spin"
            />
            {{ testLoading ? '测试中...' : '开始测试' }}
          </button>
        </div>

        <transition name="fade">
          <div
            v-if="testResult"
            class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-md animate-fade-in-up"
          >
            <div
              class="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center"
            >
              <h4 class="font-bold text-slate-700">
                测试结果
              </h4>
              <div class="flex items-center gap-3">
                <span class="text-xs text-slate-500 font-medium">置信度</span>
                <div class="w-24 h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    class="h-full bg-blue-500 rounded-full"
                    :style="{ width: testResult.confidence * 100 + '%' }"
                  />
                </div>
                <span class="text-sm font-bold text-blue-600">{{ Math.round(testResult.confidence * 100) }}%</span>
              </div>
            </div>

            <div class="p-6">
              <div class="flex items-start gap-4 mb-5">
                <div
                  class="w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm"
                  :class="
                    testResult.is_compliant
                      ? 'bg-emerald-100 text-emerald-600'
                      : 'bg-red-100 text-red-600'
                  "
                >
                  <CheckCircleFilled
                    v-if="testResult.is_compliant"
                    class="text-2xl"
                  />
                  <ExclamationCircleFilled
                    v-else
                    class="text-2xl"
                  />
                </div>
                <div>
                  <div
                    class="font-bold text-lg mb-1"
                    :class="testResult.is_compliant ? 'text-emerald-700' : 'text-red-700'"
                  >
                    {{ testResult.is_compliant ? '符合规则要求' : '不符合规则要求' }}
                  </div>
                  <p class="text-sm text-slate-600 leading-relaxed">
                    {{ testResult.findings }}
                  </p>
                </div>
              </div>

              <div
                v-if="testResult.evidence"
                class="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-100"
              >
                <div
                  class="text-xs font-bold text-slate-400 mb-2 uppercase tracking-wider flex items-center gap-1"
                >
                  <SearchOutlined /> 证据引用
                </div>
                <div
                  class="text-sm text-slate-700 font-mono bg-white p-3 rounded-lg border border-slate-200 border-l-4 border-l-blue-400 shadow-sm"
                >
                  {{ testResult.evidence }}
                </div>
              </div>

              <div
                v-if="testResult.suggestion"
                class="flex gap-3 items-start text-sm bg-blue-50 text-blue-800 p-4 rounded-xl border border-blue-100"
              >
                <InfoCircleFilled class="mt-0.5 flex-shrink-0 text-blue-600" />
                <span class="font-medium">{{ testResult.suggestion }}</span>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </a-modal>

    <!-- 质控评估入口提示 -->
    <a-modal
      v-model:open="showQCEvaluation"
      title="质控评估"
      :footer="null"
      centered
    >
      <div class="text-center p-8">
        <a-result
          status="info"
          title="请前往质控评估页面"
          sub-title="在主导航中点击「质控评估」进入完整评估流程"
        >
          <template #extra>
            <a-button
              type="primary"
              @click="showQCEvaluation = false"
            >
              知道了
            </a-button>
          </template>
        </a-result>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
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
  CodeOutlined,
} from '@ant-design/icons-vue'
import { ApiService } from '@/services/apiService'
import { getAccessToken } from '@/utils/auth-token'
import type { User } from '@/types/auth'
import { UserRole } from '@/types/auth'
import type { TableColumnsType, TablePaginationConfig } from 'ant-design-vue'

const router = useRouter()

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
  defect_level_distribution: {},
})
const searchText = ref('')
const currentUser = ref<User | null>(null)
const isAdmin = computed(() => currentUser.value?.roles?.includes(UserRole.ADMIN) || false)

// 分页
const tablePagination = ref<TablePaginationConfig>({
  current: 1,
  pageSize: 20,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  pageSizeOptions: ['20', '50', '100'],
  showTotal: (total: number, range: [number, number]) => `共 ${total} 条`,
  size: 'small',
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
const qcRuleCaseMapRef = ref<Record<string, any>>({})
const buildCaseTextRef = ref<
  ((example: Record<string, any>, options?: Record<string, unknown>) => string) | null
>(null)

// 提示词管理
const isEditingPrompt = ref(false)
const currentPrompt = ref('')
const editingPrompt = ref('')
const promptLoading = ref(false)
const lastRefreshedAt = ref<Date | null>(null)

const buildAuthHeaders = (includeJson: boolean = false): Record<string, string> => {
  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  if (includeJson) {
    headers['Content-Type'] = 'application/json'
  }
  return headers
}

// 颜色计算属性
const complexityBreakdown = computed(() => {
  const stats = sichuanStats.value.complexity_distribution || {}
  return {
    high: stats['高复杂度'] || 0,
    medium: stats['中复杂度'] || 0,
    low: stats['低复杂度'] || 0,
  }
})

const criticalDefectCount = computed(
  () => sichuanStats.value.defect_level_distribution?.['严重缺陷'] || 0,
)
const majorDefectCount = computed(
  () => sichuanStats.value.defect_level_distribution?.['一般缺陷'] || 0,
)
const minorDefectCount = computed(
  () => sichuanStats.value.defect_level_distribution?.['轻微缺陷'] || 0,
)

const defectTotal = computed(
  () => criticalDefectCount.value + majorDefectCount.value + minorDefectCount.value,
)

const riskDensity = computed(() => {
  if (!sichuanStats.value.total_rules) return '0%'
  return `${Math.round((criticalDefectCount.value / sichuanStats.value.total_rules) * 100)}%`
})

const lastRefreshedLabel = computed(() => {
  if (!lastRefreshedAt.value) return '未同步'
  return lastRefreshedAt.value.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
})

const complexityConicGradient = computed(() => {
  const high = complexityBreakdown.value.high
  const mid = complexityBreakdown.value.medium
  const low = complexityBreakdown.value.low
  const total = high + mid + low || 1

  const p1 = (high / total) * 100
  const p2 = p1 + (mid / total) * 100

  return {
    background: `conic-gradient(#F87171 0% ${p1}%, #FBBF24 ${p1}% ${p2}%, #34D399 ${p2}% 100%)`,
  }
})

// 搜索过滤 computed（修复问题 #2）
const filteredRules = computed(() => {
  if (!searchText.value.trim()) return sichuanRules.value
  const keyword = searchText.value.trim().toLowerCase()
  return sichuanRules.value.filter(
    (r) =>
      r.rule_id.toLowerCase().includes(keyword) ||
      r.name.toLowerCase().includes(keyword) ||
      r.description.toLowerCase().includes(keyword) ||
      r.category.toLowerCase().includes(keyword) ||
      (r.applicable_documents || []).some((d: string) => {
        const zh = getDocTypeZh(d)
        return d.toLowerCase().includes(keyword) || zh.includes(keyword)
      }),
  )
})

const getDefectRate = (count: number | undefined) => {
  if (!count || defectTotal.value === 0) return 0
  return Math.round((count / defectTotal.value) * 100)
}

// 动态获取 top 3 分类
const topCategories = computed(() => {
  const counts: Record<string, number> = {}
  sichuanRules.value.forEach((r) => {
    counts[r.category] = (counts[r.category] || 0) + 1
  })
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([name, count]) => ({ name, count }))
})

const getCategoryRatio = (count: number) => {
  if (!sichuanStats.value.total_rules) return '0%'
  return `${Math.round((count / sichuanStats.value.total_rules) * 100)}%`
}

// 表格列定义（去掉重复的"分类"列，该信息已融入规则名称行）
const sichuanColumns = computed<TableColumnsType<SichuanQCRule>>(() => [
  {
    title: '序号',
    key: 'index',
    width: 60,
    fixed: 'left',
    align: 'center',
    customRender: ({ index }: { index: number }) =>
      (tablePagination.value.current - 1) * tablePagination.value.pageSize + index + 1,
  },
  { title: '编号', key: 'rule_id', width: 90, fixed: 'left' },
  { title: '适用文书', key: 'applicable_documents', width: 100 },
  { title: '规则名称', key: 'name', width: 360 },
  { title: '复杂度', key: 'complexity', width: 100 },
  { title: '缺陷级别', key: 'defect_level', width: 100 },
  { title: '操作', key: 'actions', width: 120, fixed: 'right', align: 'right' },
])

// 方法
const refreshSichuanRules = async () => {
  loading.value = true
  try {
    const response = await fetch(`/api/v1/qc/sichuan/rules?_ts=${Date.now()}`, {
      headers: buildAuthHeaders(),
    })
    if (response.ok) {
      const raw = await response.json()
      const data = raw?.data && typeof raw.data === 'object' ? raw.data : raw
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
        requires_cot: Boolean(r.requires_cot),
      })

      sichuanRules.value = (data.rules || []).map(normalizeRule)

      // 从规则数据中计算统计分布（后端可能返回空对象）
      const rules = sichuanRules.value
      const computedComplexity: Record<string, number> = {}
      const computedDefect: Record<string, number> = {}
      rules.forEach((r) => {
        computedComplexity[r.complexity] = (computedComplexity[r.complexity] || 0) + 1
        computedDefect[r.defect_level] = (computedDefect[r.defect_level] || 0) + 1
      })

      const apiComplexity = data.complexity_distribution || {}
      const apiDefect = data.defect_level_distribution || {}

      sichuanStats.value = {
        total_rules: data.total_rules || rules.length,
        rule_categories: data.rule_categories || [...new Set(rules.map((r) => r.category))],
        complexity_distribution:
          Object.keys(apiComplexity).length > 0 ? apiComplexity : computedComplexity,
        defect_level_distribution: Object.keys(apiDefect).length > 0 ? apiDefect : computedDefect,
      }
      lastRefreshedAt.value = new Date()
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
  // 搜索过滤由 filteredRules computed 自动处理
  tablePagination.value.current = 1
}

const handleTableChange = (pag: TablePaginationConfig) => {
  tablePagination.value.current = pag.current || 1
  tablePagination.value.pageSize = pag.pageSize || 20
}

const viewSichuanRuleDetail = async (rule: SichuanQCRule) => {
  selectedRule.value = rule
  showRuleDetail.value = true
  if (isAdmin.value) {
    // 从后端获取真实 Prompt
    promptLoading.value = true
    try {
      const resp = await fetch(
        `/api/v1/qc/sichuan/rules/${encodeURIComponent(rule.rule_id)}/prompt`,
        {
          headers: buildAuthHeaders(),
        },
      )
      if (resp.ok) {
        const data = await resp.json()
        currentPrompt.value = data.data?.prompt || '// 暂无提示词'
        isDefaultPrompt.value = data.data?.is_default ?? true
      } else {
        currentPrompt.value = '// 获取提示词失败'
      }
    } catch (e) {
      currentPrompt.value = '// 网络错误，无法获取提示词'
      console.error(e)
    } finally {
      promptLoading.value = false
    }
  }
}

const startQCWithRule = (rule: SichuanQCRule) => {
  testingRule.value = rule
  testExampleType.value = 'negative'
  switchExampleType('negative')
  showRuleTest.value = true
  testResult.value = null
}

const openCustomWorkspace = () => {
  router.push('/dashboard/rules/custom-workspace')
}

const switchExampleType = (type: 'positive' | 'negative') => {
  testExampleType.value = type
  if (testingRule.value) {
    const ruleId = testingRule.value.rule_id
    const ruleCase = qcRuleCaseMapRef.value[ruleId]
    const buildCaseText = buildCaseTextRef.value
    if (ruleCase && buildCaseText) {
      const example = type === 'positive' ? ruleCase.positive : ruleCase.negative
      testMedicalText.value = buildCaseText(example, {
        includeHints: false,
        includeTitle: false,
        includeAnalysis: false,
        includeFocusPoints: false,
      })
    } else {
      testMedicalText.value = '暂无示例文本，请手动输入。'
    }
  }
}

const executeRuleTest = async () => {
  if (!testingRule.value || !testMedicalText.value.trim()) {
    message.warning('请输入病历文本')
    return
  }
  testLoading.value = true
  testResult.value = null
  try {
    const resp = await fetch('/api/v1/qc/sichuan/test-rule', {
      method: 'POST',
      headers: buildAuthHeaders(true),
      body: JSON.stringify({
        rule_id: testingRule.value.rule_id,
        medical_text: testMedicalText.value,
      }),
    })
    if (resp.ok) {
      const data = await resp.json()
      const result = data.data || data
      testResult.value = {
        is_compliant: result.is_compliant ?? true,
        confidence: result.confidence ?? 0.7,
        findings: result.findings || '无详细发现',
        evidence: result.evidence || '',
        suggestion: result.suggestion || '',
      }
    } else {
      const errText = await resp.text()
      message.error(`测试请求失败: HTTP ${resp.status}`)
      console.error('Test rule error:', errText)
    }
  } catch (e) {
    message.error('网络错误，测试请求失败')
    console.error(e)
  } finally {
    testLoading.value = false
  }
}

// Prompt 管理（对接真实后端 API）
const isDefaultPrompt = ref(true)
const startEditPrompt = () => {
  editingPrompt.value = currentPrompt.value
  isEditingPrompt.value = true
}
const cancelEditPrompt = () => {
  isEditingPrompt.value = false
}
const savePrompt = async () => {
  if (!selectedRule.value) return
  promptLoading.value = true
  try {
    const resp = await fetch(
      `/api/v1/qc/sichuan/rules/${encodeURIComponent(selectedRule.value.rule_id)}/prompt`,
      {
        method: 'PUT',
        headers: buildAuthHeaders(true),
        body: JSON.stringify({
          custom_prompt: editingPrompt.value.trim() || null,
        }),
      },
    )
    if (resp.ok) {
      currentPrompt.value = editingPrompt.value
      isEditingPrompt.value = false
      isDefaultPrompt.value = !editingPrompt.value.trim()
      message.success('提示词保存成功')
    } else {
      const errText = await resp.text()
      message.error(`保存失败: ${errText}`)
    }
  } catch (e) {
    message.error('网络错误，保存失败')
    console.error(e)
  } finally {
    promptLoading.value = false
  }
}

// 样式映射 - 使用更柔和的微着色风格
const getComplexityClass = (val: string) => {
  if (val === '高复杂度') return 'bg-red-50 text-red-700 border border-red-100'
  if (val === '中复杂度') return 'bg-amber-50 text-amber-700 border border-amber-100'
  return 'bg-emerald-50 text-emerald-700 border border-emerald-100'
}

const getDefectLevelClass = (val: string) => {
  if (val?.includes('严重') || val === 'critical')
    return 'bg-rose-50 text-rose-700 border border-rose-100'
  if (val?.includes('一般') || val === 'major')
    return 'bg-orange-50 text-orange-700 border border-orange-100'
  return 'bg-slate-100 text-slate-600 border border-slate-200'
}

// 文本映射
const CANONICAL_LABEL_ZH: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  first_course_record: '首次病程记录',
  discharge_record: '出院记录',
  discharge_summary: '出院小结',
  operation_record: '手术记录',
  preop_summary: '术前小结',
  postop_first_record: '术后首次病程',
  examination_report: '辅助检查',
  consultation_record: '会诊记录',
  consent_form: '知情同意书',
  medical_order: '医嘱',
  case_discussion: '疑难病例讨论',
  transfusion_record: '输血记录',
  anesthesia_record: '麻醉记录',
}
const getDocTypeZh = (val: string) => CANONICAL_LABEL_ZH[val] || val
const getSeverityZh = (val: string) => val
const getCategoryZh = (val: string) => val

// 文书类型颜色映射
const DOC_TYPE_COLORS: Record<string, string> = {
  入院记录: 'bg-blue-50 text-blue-600 border border-blue-100',
  admission_record: 'bg-blue-50 text-blue-600 border border-blue-100',
  病程记录: 'bg-teal-50 text-teal-600 border border-teal-100',
  progress_note: 'bg-teal-50 text-teal-600 border border-teal-100',
  出院记录: 'bg-violet-50 text-violet-600 border border-violet-100',
  '(死亡)出院记录': 'bg-violet-50 text-violet-600 border border-violet-100',
  discharge_record: 'bg-violet-50 text-violet-600 border border-violet-100',
  手术记录: 'bg-rose-50 text-rose-600 border border-rose-100',
  手术相关记录: 'bg-rose-50 text-rose-600 border border-rose-100',
  operation_record: 'bg-rose-50 text-rose-600 border border-rose-100',
  辅助检查: 'bg-amber-50 text-amber-600 border border-amber-100',
  examination_report: 'bg-amber-50 text-amber-600 border border-amber-100',
  知情同意书: 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  知情同意: 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  consent_form: 'bg-cyan-50 text-cyan-600 border border-cyan-100',
  医嘱: 'bg-indigo-50 text-indigo-600 border border-indigo-100',
  会诊记录: 'bg-orange-50 text-orange-600 border border-orange-100',
  输血记录: 'bg-pink-50 text-pink-600 border border-pink-100',
  麻醉记录: 'bg-lime-50 text-lime-600 border border-lime-100',
}
const getDocTypeColorClass = (val: string) =>
  DOC_TYPE_COLORS[val] || 'bg-slate-50 text-slate-600 border border-slate-100'

onMounted(async () => {
  const [qcRuleCasesModule, userResp] = await Promise.all([
    import('@/data/qcRuleCases'),
    ApiService.getCurrentUser(),
  ])

  qcRuleCaseMapRef.value = qcRuleCasesModule.qcRuleCaseMap
  buildCaseTextRef.value = qcRuleCasesModule.buildCaseText

  refreshSichuanRules()
  if (userResp.success) {
    currentUser.value = userResp.data ?? null
  }
})
</script>

<style scoped>
.semantic-rules-manager {
  --panel-bg: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  --panel-border: #dbe7f5;
  --panel-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
  --ink-strong: #0f2747;
  --ink-main: #1f3b63;
  --ink-muted: #6a7d99;
  --accent: #2f6fee;
  --accent-strong: #1f5de0;
  --accent-soft: #eaf2ff;
  --focus-ring: 0 0 0 4px rgba(47, 111, 238, 0.16);
  padding: 0;
  color: var(--ink-main);
}

.ops-context {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  background: radial-gradient(circle at right top, #edf4ff 0%, #ffffff 52%);
  box-shadow: var(--panel-shadow);
  padding: 1.15rem 1.35rem;
  margin-bottom: 1rem;
}

.ops-eyebrow {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #597198;
  margin: 0 0 4px;
  font-weight: 600;
}

.ops-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--ink-strong);
  letter-spacing: -0.01em;
}

.ops-subtitle {
  margin: 6px 0 0;
  color: var(--ink-muted);
  font-size: 0.84rem;
}

.ops-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(84px, 1fr));
  gap: 0.75rem;
  width: min(420px, 100%);
}

.ops-kpi {
  border: 1px solid #dce8fb;
  border-radius: 12px;
  padding: 0.55rem 0.7rem;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ops-kpi-warn {
  border-color: #ffe0df;
  background: #fff9f9;
}

.ops-kpi-label {
  font-size: 11px;
  color: #6f82a0;
}

.ops-kpi-value {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--ink-strong);
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.insight-panel {
  min-height: 220px;
  border-radius: 18px;
  border: 1px solid var(--panel-border);
  background: var(--panel-bg);
  box-shadow: var(--panel-shadow);
  padding: 1.2rem;
  display: flex;
  flex-direction: column;
}

.insight-panel-primary {
  background: linear-gradient(165deg, #ffffff 0%, #eef5ff 100%);
}

.insight-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.95rem;
}

.insight-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--ink-strong);
}

.insight-icon {
  color: #9db3d2;
  font-size: 1.05rem;
}

.complexity-donut {
  width: 120px;
  height: 120px;
  border-radius: 999px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 0.9rem;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.75);
}

.complexity-inner {
  width: 88px;
  height: 88px;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: inset 0 0 0 1px #d8e6fb;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.complexity-total {
  font-size: 1.9rem;
  color: var(--ink-strong);
  font-weight: 700;
  line-height: 1;
}

.complexity-label {
  margin-top: 2px;
  font-size: 11px;
  color: #7084a3;
}

.complexity-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.complexity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.34rem 0.45rem;
  border: 1px solid #e8f0fd;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
}

.complexity-name {
  font-size: 12px;
  display: flex;
  align-items: center;
  color: #3d5579;
  gap: 0.36rem;
}

.complexity-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.complexity-dot.danger {
  background: #ef4444;
}

.complexity-dot.warning {
  background: #f59e0b;
}

.complexity-dot.safe {
  background: #10b981;
}

.complexity-value {
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-strong);
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  margin-top: 0.2rem;
}

.risk-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.risk-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #475f82;
}

.risk-count {
  font-weight: 700;
}

.risk-count.danger {
  color: #ef4444;
}

.risk-count.warning {
  color: #f97316;
}

.risk-count.safe {
  color: #10b981;
}

.risk-track {
  width: 100%;
  border-radius: 999px;
  background: #e5edf8;
  height: 9px;
  overflow: hidden;
}

.risk-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.45s ease;
}

.risk-fill.danger {
  background: linear-gradient(90deg, #f87171 0%, #ef4444 100%);
}

.risk-fill.warning {
  background: linear-gradient(90deg, #fb923c 0%, #f97316 100%);
}

.risk-fill.safe {
  background: linear-gradient(90deg, #34d399 0%, #10b981 100%);
}

.risk-footnote {
  margin-top: auto;
  font-size: 11px;
  color: #6f83a2;
  text-align: right;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.2rem;
}

.category-item {
  display: grid;
  grid-template-columns: 38px 1fr auto;
  align-items: center;
  gap: 0.65rem;
  border: 1px solid #e8f0fd;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  padding: 0.5rem 0.6rem;
}

.category-index {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  color: #6d86ab;
}

.category-meta {
  display: flex;
  flex-direction: column;
}

.category-name {
  font-size: 12px;
  font-weight: 600;
  color: #2f476a;
}

.category-ratio {
  font-size: 11px;
  color: #7b8faa;
}

.category-count {
  font-size: 16px;
  font-weight: 700;
  color: #1c3860;
}

.ops-toolbar {
  border: 1px solid var(--panel-border);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
  padding: 0.8rem;
  margin-bottom: 0.85rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.85rem;
}

.toolbar-actions {
  display: flex;
  gap: 0.6rem;
  width: 100%;
  justify-content: flex-end;
}

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
  background: #f9fbff;
  border: 1px solid #d6e4f8;
  border-radius: 0.75rem;
  font-size: 0.9rem;
  color: #27405f;
  transition: all 0.2s;
  outline: none;
  box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
}

.search-input:focus {
  border-color: var(--accent);
  box-shadow: var(--focus-ring);
}

/* 按钮样式 */
.modern-btn-ghost {
  padding: 0.6rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.9rem;
  font-weight: 500;
  color: #587196;
  background: #f8fbff;
  border: 1px solid #d4e2f7;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.modern-btn-ghost:hover {
  color: var(--accent);
  background: #eef4ff;
  border-color: #bfd3f3;
}

.modern-btn-primary {
  padding: 0.6rem 1.25rem;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #2f6fee 0%, #245fdb 100%);
  color: white;
  font-size: 0.9rem;
  font-weight: 600;
  border: none;
  box-shadow: 0 8px 18px rgba(47, 111, 238, 0.28);
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.modern-btn-primary:hover {
  background: linear-gradient(135deg, var(--accent-strong) 0%, #1f55c8 100%);
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.34);
}

.modern-btn-primary-alt {
  padding: 0.6rem 1.15rem;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #1f5de0 0%, #0f4ab8 100%);
  color: white;
  font-size: 0.86rem;
  font-weight: 600;
  border: none;
  box-shadow: 0 8px 18px rgba(31, 93, 224, 0.28);
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.modern-btn-primary-alt:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 20px rgba(31, 93, 224, 0.34);
}

.table-shell {
  border-radius: 16px;
  border: 1px solid var(--panel-border);
  overflow: hidden;
  background: #ffffff;
  box-shadow: var(--panel-shadow);
}

.table-shell-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.95rem 1rem;
  border-bottom: 1px solid #dce8f8;
  background: linear-gradient(180deg, #f7fbff 0%, #eef5ff 100%);
}

.table-shell-eyebrow {
  margin: 0 0 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6f86aa;
  font-weight: 700;
}

.table-shell-title {
  margin: 0;
  font-size: 1rem;
  line-height: 1.2;
  color: var(--ink-strong);
  font-weight: 700;
}

.table-shell-meta {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  padding: 0.45rem 0.7rem;
  border-radius: 999px;
  border: 1px solid #d5e3f7;
  background: rgba(255, 255, 255, 0.85);
}

.table-shell-count {
  font-size: 1rem;
  font-weight: 700;
  color: #1c3f72;
}

.table-shell-label {
  font-size: 11px;
  color: #748aa8;
}

/* 表格样式 */
.modern-table :deep(.ant-table-thead > tr > th) {
  background: #f2f7ff;
  color: #36547b;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  border-bottom: 1px solid #dbe7f5;
  padding: 0.72rem 0.78rem;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 0.58rem 0.78rem;
  border-bottom: 1px solid #edf3fc;
  font-size: 0.84rem;
  color: #334f76;
}

.modern-table :deep(.ant-table-tbody > tr:hover > td) {
  background: #f3f8ff !important;
}

.modern-table :deep(.ant-table-row) {
  transition: background-color 0.2s ease;
}

.rule-code-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 0.38rem 0.7rem;
  border-radius: 10px;
  background: linear-gradient(180deg, #f6faff 0%, #eaf2ff 100%);
  border: 1px solid #d3e0f5;
  color: #27456b;
  font-size: 12px;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.02em;
}

.rule-main {
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  padding-right: 0.5rem;
}

.rule-main-title {
  color: #102746;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.45;
}

.rule-main-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.rule-category-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.22rem 0.5rem;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  flex-shrink: 0;
}

.rule-main-desc {
  font-size: 11px;
  color: #7a90ad;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 82px;
  padding: 0.32rem 0.65rem;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.doc-pill-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
}

.doc-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.62rem;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.doc-pill-more {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.5rem;
  border-radius: 999px;
  font-size: 11px;
  color: #6d86a9;
  border: 1px solid #d8e5f7;
  background: #f7fbff;
  cursor: help;
}

/* 表格操作按钮 */
.table-action-btn {
  font-size: 0.75rem;
  font-weight: 600;
  color: #2563eb;
  padding: 0.35rem 0.85rem;
  border: 1px solid #bad0f5;
  border-radius: 0.5rem;
  background: #edf3ff;
  transition: all 0.2s;
}
.table-action-btn:hover {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
}

.table-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.55rem;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #6f86aa;
  background: #f7fbff;
  border: 1px solid #dbe7f6;
}

.icon-btn:hover {
  color: #2563eb;
  background: #edf4ff;
  border-color: #bed2f6;
}

.animate-fade-in-up {
  animation: fadeInUp 0.3s ease-out;
}

.block-enter {
  animation: blockFadeIn 0.35s ease-out;
}

.block-enter-delayed {
  animation: blockFadeIn 0.4s ease-out;
}

.block-enter-delayed-2 {
  animation: blockFadeIn 0.45s ease-out;
}

@keyframes blockFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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

@media (max-width: 1280px) {
  .insight-grid {
    grid-template-columns: 1fr;
  }

  .insight-panel {
    min-height: 190px;
  }
}

@media (max-width: 768px) {
  .ops-context {
    flex-direction: column;
  }

  .ops-kpis {
    width: 100%;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ops-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .table-shell-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .toolbar-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
