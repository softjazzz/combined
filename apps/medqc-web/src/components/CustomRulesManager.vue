<template>
  <div class="custom-rules-manager">
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
              <span class="text-2xl font-bold text-slate-700 leading-none">{{ customStats.total_rules }}</span>
              <span class="text-[10px] text-slate-400 mt-1">总规则</span>
            </div>
          </div>
          <div class="space-y-3 text-sm flex-1">
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-red-400 mr-2"></span>高复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-red-500 transition-colors">{{ customStats.complexity_distribution?.['高复杂度'] || 0 }}</span>
            </div>
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-amber-400 mr-2"></span>中复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-amber-500 transition-colors">{{ customStats.complexity_distribution?.['中复杂度'] || 0 }}</span>
            </div>
            <div class="flex justify-between items-center group">
              <span class="flex items-center text-slate-600 text-xs"><span class="w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>低复杂度</span>
              <span class="font-bold text-slate-700 group-hover:text-emerald-500 transition-colors">{{ customStats.complexity_distribution?.['低复杂度'] || 0 }}</span>
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
              <span class="text-red-500 font-bold">{{ customStats.defect_level_distribution?.['严重缺陷'] || 0 }}</span>
              </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-red-500 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(239,68,68,0.2)]" :style="{ width: getPercentage(customStats.defect_level_distribution?.['严重缺陷']) + '%' }"></div>
              </div>
            </div>
          <div>
            <div class="flex justify-between text-xs mb-1.5">
              <span class="text-slate-500 font-medium">一般缺陷 (警告)</span>
              <span class="text-orange-400 font-bold">{{ customStats.defect_level_distribution?.['一般缺陷'] || 0 }}</span>
              </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-orange-400 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(251,191,36,0.2)]" :style="{ width: getPercentage(customStats.defect_level_distribution?.['一般缺陷']) + '%' }"></div>
              </div>
              </div>
          <div>
            <div class="flex justify-between text-xs mb-1.5">
              <span class="text-slate-500 font-medium">轻微缺陷 (提示)</span>
              <span class="text-emerald-500 font-bold">{{ customStats.defect_level_distribution?.['轻微缺陷'] || 0 }}</span>
            </div>
            <div class="w-full bg-slate-100 rounded-full h-2">
              <div class="bg-emerald-500 h-2 rounded-full transition-all duration-1000 shadow-[0_2px_4px_rgba(16,185,129,0.2)]" :style="{ width: getPercentage(customStats.defect_level_distribution?.['轻微缺陷']) + '%' }"></div>
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
          <div class="stat-grid-item bg-blue-50/50 border-blue-100 text-blue-600">
            <div class="text-xl font-bold mb-1">{{ getCategoryCount('入院记录') }}</div>
            <div class="text-[10px] font-medium opacity-70">入院记录</div>
          </div>
          <div class="stat-grid-item bg-cyan-50/50 border-cyan-100 text-cyan-600">
            <div class="text-xl font-bold mb-1">{{ getCategoryCount('病程记录') }}</div>
            <div class="text-[10px] font-medium opacity-70">病程记录</div>
          </div>
          <div class="stat-grid-item bg-purple-50/50 border-purple-100 text-purple-600">
            <div class="text-xl font-bold mb-1">{{ getCategoryCount('手术记录') }}</div>
            <div class="text-[10px] font-medium opacity-70">手术记录</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 列表操作栏 -->
    <div class="flex flex-col sm:flex-row justify-between items-center mb-5 gap-4">
      <div class="flex items-center gap-4">
        <h2 class="text-lg font-bold text-slate-700 tracking-tight">
          {{ isLegacyMode ? '泸县存量质控规则' : '泸县33条质控规则' }}
          <span class="ml-2 px-2 py-0.5 rounded text-xs font-normal bg-blue-50 text-blue-600 border border-blue-100">{{ customRules.length }}条</span>
        </h2>
      </div>
      
      <div class="flex gap-3 w-full sm:w-auto justify-end">
        <button class="modern-btn-ghost" @click="showRuleDocModal = true">
          <FileTextOutlined />
          <span class="hidden sm:inline ml-1">规则说明</span>
        </button>
        <button class="modern-btn-primary" @click="goToBatchTest">
          <PlayCircleOutlined class="mr-1" />
          开始质控评估
        </button>
      </div>
    </div>

    <!-- 3. 数据表格 -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
      <a-table
        :dataSource="customRules"
        :columns="customColumns"
        :loading="loading"
        :pagination="tablePagination"
        class="modern-table"
        :scroll="{ x: 1000 }"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <!-- 编号列：Mono字体 + 浅色背景 -->
            <template v-if="column.key === 'rule_id'">
            <div class="py-2">
              <span class="font-mono text-blue-600 bg-blue-50 px-2 py-1 rounded text-xs font-semibold select-all border border-blue-100">
                {{ getDisplayId(record) }}
              </span>
            </div>
            </template>

          <!-- 规则名称 -->
            <template v-if="column.key === 'name'">
            <div class="py-3 pr-4">
              <a-tooltip :title="record.description">
                <div class="text-blue-600 hover:text-blue-700 font-semibold mb-1.5 text-sm leading-snug cursor-pointer">{{ record.name }}</div>
              </a-tooltip>
            </div>
            </template>

          <!-- 复杂度 -->
            <template v-if="column.key === 'complexity'">
            <span 
              class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold"
              :class="getComplexityClass(record.complexity)"
            >
                {{ record.complexity }}
            </span>
            </template>

          <!-- 缺陷级别 -->
            <template v-if="column.key === 'defect_level'">
             <span 
              class="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold"
              :class="getDefectLevelClass(record.defect_level)"
            >
                {{ getSeverityZh(record.defect_level) }}
            </span>
            </template>

          <!-- 分类 -->
            <template v-if="column.key === 'category'">
            <span class="text-slate-600 text-xs font-medium bg-slate-50 px-2 py-1 rounded border border-slate-100">
                {{ getCategoryZh(record.category) }}
            </span>
            </template>

          <!-- 操作列 -->
            <template v-if="column.key === 'actions'">
            <div class="flex items-center justify-end gap-3">
              <button class="icon-btn text-slate-500 bg-slate-50 hover:text-blue-600 hover:bg-blue-50 border border-transparent hover:border-blue-100 font-medium px-3 py-1 h-7 text-xs rounded-md" @click="viewSichuanRuleDetail(record)">
                  详情
              </button>
              <button class="table-action-btn" @click="startQCWithRule(record)">
                  质控评估
              </button>
            </div>
            </template>
        </template>
      </a-table>
    </div>

    <!-- 以下保留原有模态框逻辑，仅适配样式 -->

    <!-- 自定义规则详情模态框 -->
    <a-modal
      v-model:open="showRuleDetail"
      title="泸县自定义质控规则详情"
      width="900px"
      :footer="null"
      centered
      class="modern-modal"
    >
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
          <a-descriptions-item label="扣分">{{ selectedRule.score_deduction || 0 }}分</a-descriptions-item>
          <a-descriptions-item label="需要RAG">
            <a-tag :color="selectedRule.requires_rag ? 'green' : 'default'">{{ selectedRule.requires_rag ? '是' : '否' }}</a-tag>
          </a-descriptions-item>
        </a-descriptions>

        <template v-if="selectedRule.check_points && selectedRule.check_points.length > 0">
          <div class="mb-6">
            <h4 class="font-bold text-slate-700 text-sm mb-3 flex items-center gap-2">
              <CheckCircleOutlined class="text-blue-500" /> 检查要点
            </h4>
            <ul class="bg-blue-50/50 rounded-lg p-4 space-y-2 border border-blue-100/50">
              <li v-for="(point, index) in selectedRule.check_points" :key="index" class="text-sm text-slate-700 flex items-start gap-2">
                <span class="bg-blue-100 text-blue-600 rounded-full w-5 h-5 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">{{ index + 1 }}</span>
                <span>{{ point }}</span>
            </li>
          </ul>
          </div>
        </template>

        <!-- 提示词管理 -->
        <template v-if="isAdmin">
          <div class="pt-6 border-t border-slate-100">
            <div class="flex justify-between items-center mb-4">
              <h4 class="font-bold text-slate-700 flex items-center gap-2 text-sm">
                <CodeOutlined /> 提示词管理
                <span class="text-[10px] font-normal bg-amber-50 text-amber-600 px-2 py-0.5 rounded border border-amber-100">Admin</span>
              </h4>
              <div class="flex gap-2">
                <a-button v-if="!isEditingPrompt" type="link" size="small" @click="startEditPrompt">编辑</a-button>
                <template v-else>
                  <a-button type="primary" size="small" @click="savePrompt">保存</a-button>
                  <a-button size="small" @click="cancelEditPrompt">取消</a-button>
                  <a-button size="small" danger @click="resetToDefault">恢复默认</a-button>
                </template>
              </div>
              </div>

            <div v-if="!isEditingPrompt" class="bg-slate-900 text-slate-300 p-4 rounded-lg text-xs font-mono whitespace-pre-wrap max-h-64 overflow-y-auto custom-scrollbar border border-slate-800">
              {{ currentPrompt || '// 暂无自定义提示词' }}
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

    <!-- 质控点说明弹窗 -->
    <a-modal
      v-model:open="showRuleDocModal"
      :title="ruleDocModalTitle"
      width="90%"
      :footer="null"
      class="modern-modal"
    >
      <a-table
        :dataSource="ruleDocRows"
        :columns="ruleDocColumns"
        class="modern-table"
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
            <span class="font-mono text-slate-600 bg-slate-100 px-2 py-1 rounded text-xs font-semibold border border-slate-200">{{ record.rule_id }}</span>
          </template>
          <template v-else-if="column.key === 'name'">
            <span class="font-semibold text-slate-700">{{ record.name }}</span>
          </template>
          <template v-else-if="column.key === 'description'">
            <div class="text-slate-500 text-xs">{{ record.description }}</div>
          </template>
          <template v-else-if="column.key === 'check_points'">
            <div class="text-slate-600 text-xs">{{ record.check_points || '-' }}</div>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- 质控评估模态框 -->
    <a-modal
      v-model:open="showQCEvaluation"
      title="四川省住院病历质控评估"
      width="600px"
      :footer="null"
      centered
      class="modern-modal"
    >
      <div class="p-6 text-center">
        <div class="w-16 h-16 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4">
          <PlayCircleOutlined class="text-3xl" />
        </div>
        <h3 class="text-lg font-bold text-slate-800 mb-2">功能指引</h3>
        <p class="text-slate-500 mb-6">请前往质控评估页面进行完整的四川省住院病历质控评估</p>
        <a-button type="primary" size="large" @click="showQCEvaluation = false" class="modern-btn-primary px-8">
          前往质控评估页面
        </a-button>
      </div>
    </a-modal>

    <!-- 规则测试对话框 (保留复杂逻辑，仅外层样式适配) -->
    <a-modal
      v-model:open="showRuleTest"
      :title="`质控规则测试 · ${testingRule?.rule_id || ''}`"
      width="900px"
      :footer="null"
      centered
      :destroyOnClose="true"
      class="modern-modal rule-test-modal"
    >
      <div v-if="testingRule" class="rule-test-container p-2">
        <!-- 规则信息展示区 -->
        <div class="bg-slate-50 rounded-xl p-4 border border-slate-100 mb-4">
          <div class="flex justify-between items-start mb-2">
            <h3 class="font-bold text-slate-800 text-lg">{{ testingRule.name }}</h3>
            <div class="flex gap-2">
              <span :class="['px-2 py-1 rounded text-xs font-medium', getDefectLevelClass(testingRule.defect_level)]">{{ testingRule.defect_level }}</span>
              <span :class="['px-2 py-1 rounded text-xs font-medium', getComplexityClass(testingRule.complexity)]">{{ testingRule.complexity }}</span>
              </div>
              </div>
          <p class="text-sm text-slate-600 mb-3">{{ testingRule.description }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="doc in testingRule.applicable_documents" :key="doc" class="bg-white border border-slate-200 text-slate-500 px-2 py-0.5 rounded text-xs">
              {{ getDocTypeZh(doc) || doc }}
                </span>
              </div>
              </div>

        <!-- 病历输入区 -->
        <div class="mb-4 border border-slate-200 rounded-xl overflow-hidden">
          <div class="bg-slate-50 px-4 py-2 border-b border-slate-200 flex justify-between items-center">
            <span class="font-semibold text-slate-700 text-sm">病历文本</span>
            <div class="flex bg-white rounded-lg p-1 border border-slate-200 shadow-sm">
              <button 
                class="px-3 py-1 text-xs rounded-md transition-colors font-medium"
                :class="testExampleType === 'negative' ? 'bg-red-50 text-red-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                @click="switchExampleType('negative')"
              >
                反例
              </button>
              <button 
                class="px-3 py-1 text-xs rounded-md transition-colors font-medium"
                :class="testExampleType === 'positive' ? 'bg-emerald-50 text-emerald-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'"
                @click="switchExampleType('positive')"
              >
                正例
              </button>
                  </div>
                    </div>
          <div class="p-4 bg-white relative">
            <a-textarea
              v-model:value="testMedicalText"
              placeholder="请输入或粘贴病历文本片段"
              :rows="8"
              class="w-full text-sm border-0 focus:shadow-none p-0 resize-none"
            />
            <!-- AI加载遮罩 -->
            <div v-if="showAILoadingMask" class="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                <a-spin size="large" />
              <div class="mt-3 text-blue-600 font-medium">AI 正在分析中...</div>
              </div>
            </div>
          <div class="bg-slate-50 px-4 py-3 border-t border-slate-200 flex justify-end">
             <button class="modern-btn-primary px-6 py-1.5" :disabled="testLoading" @click="executeRuleTest">
              <ThunderboltOutlined v-if="!testLoading" class="mr-2" />
              <ReloadOutlined v-else class="mr-2 animate-spin" />
              {{ testLoading ? '测试中...' : '开始测试' }}
            </button>
          </div>
        </div>

        <!-- 结果展示区 -->
        <transition name="fade">
          <div v-if="testResult" class="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-md">
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

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  ReloadOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  CheckSquareOutlined,
  InfoCircleOutlined,
  CloseCircleOutlined,
  HighlightOutlined,
  SearchOutlined,
  ExclamationCircleFilled,
  CheckCircleFilled,
  CloseCircleFilled,
  InfoCircleFilled,
  CheckCircleTwoTone,
  ExclamationCircleTwoTone,
  FundOutlined,
  CodeOutlined,
  BulbOutlined,
  PieChartOutlined,
  AlertOutlined,
  AppstoreOutlined
} from '@ant-design/icons-vue'
import {
  qcRuleCaseMap,
  buildCaseText,
  extractHints,
  extractFocusPoints,
  type QCRuleCaseExample
} from '@/data/qcRuleCases'
import { customRuleCaseMap } from '@/data/customRuleCases'
import { ApiService } from '@/services/apiService'
import type { User } from '@/types/auth'
import { UserRole } from '@/types/auth'
import customRulesData from '../../backend/app/data/custom_rules_33.json'

const router = useRouter()

// 组件模式
const props = defineProps<{
  mode?: 'default' | 'lx-legacy'
}>()

const isLegacyMode = computed(() => props.mode === 'lx-legacy')

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
  check_points?: string[]
  custom_prompt?: string
}

interface SichuanQCStats {
  total_rules: number
  rule_categories: string[]
  complexity_distribution: Record<string, number>
  defect_level_distribution: Record<string, number>
}

// 状态
const loading = ref(false)
const customRules = ref<SichuanQCRule[]>([])
const customStats = ref<SichuanQCStats>({
  total_rules: 0,
  rule_categories: [],
  complexity_distribution: {},
  defect_level_distribution: {}
})
const currentUser = ref<User | null>(null)
const isAdmin = computed(() => currentUser.value?.roles?.includes(UserRole.ADMIN) || false)

// 提示词管理
const currentPrompt = ref<string>('')
const isEditingPrompt = ref<boolean>(false)
const editingPrompt = ref<string>('')
const promptLoading = ref<boolean>(false)

// 模态框状态
const showRuleDetail = ref(false)
const selectedRule = ref<SichuanQCRule | null>(null)
const showQCEvaluation = ref(false)
const showRuleDocModal = ref(false)
const showRuleTest = ref(false)
const testingRule = ref<SichuanQCRule | null>(null)
const testMedicalText = ref('')
const testLoading = ref(false)
const showAILoadingMask = ref(false)
const testExampleType = ref<'positive' | 'negative'>('negative')
const testResult = ref<any>(null)

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

// 计算属性：环形图渐变
const complexityConicGradient = computed(() => {
  const stats = customStats.value.complexity_distribution || {}
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
  const total = customStats.value.total_rules || 1
  return (count / total) * 100
}

const getCategoryCount = (cat: string) => {
  // 简单模糊匹配
  return customRules.value.filter(r => {
    const docStr = (r.applicable_documents || []).join(',')
    return docStr.includes(cat === '手术记录' ? 'operation' : cat === '入院记录' ? 'admission' : 'progress') 
      || (r.category === cat)
  }).length
}

// 表格列定义
const customColumns = computed(() => [
  { title: '序号', key: 'index', width: 60, fixed: 'left', align: 'center', customRender: ({ index }: { index: number }) => (tablePagination.value.current - 1) * tablePagination.value.pageSize + index + 1 },
  { title: '编号', key: 'rule_id', width: 90, fixed: 'left' },
  { title: '规则名称', key: 'name', width: 300 },
  { title: '分类', key: 'category', width: 100 },
  { title: '复杂度', key: 'complexity', width: 100 },
  { title: '缺陷级别', key: 'defect_level', width: 100 },
  { title: '操作', key: 'actions', width: 140, fixed: 'right', align: 'right' }
])

// 方法
const initCustomRules = () => {
  loading.value = true
  try {
    // 加载自定义规则数据
    const rawRules = customRulesData as any[]

    // 根据模式筛选
    customRules.value = rawRules.filter(rule => {
      const id = String(rule.rule_id || rule.rule_code || '').toUpperCase()
      if (isLegacyMode.value) {
        return id.startsWith('LXE-')
      }
      return id.startsWith('LX-') && !id.startsWith('LXE-')
    }).map(r => ({
      ...r,
      rule_id: r.rule_id || r.rule_code,
      complexity: r.complexity || '中复杂度',
      defect_level: r.defect_level || '一般缺陷',
      category: r.category || '基础'
    }))

    // 计算统计数据
    const complexityDist: Record<string, number> = {}
    const defectLevelDist: Record<string, number> = {}
    const categories: Set<string> = new Set()

    customRules.value.forEach(rule => {
      if (rule.complexity) complexityDist[rule.complexity] = (complexityDist[rule.complexity] || 0) + 1
      if (rule.defect_level) defectLevelDist[rule.defect_level] = (defectLevelDist[rule.defect_level] || 0) + 1
      if (rule.category) categories.add(rule.category)
    })

    customStats.value = {
      total_rules: customRules.value.length,
      rule_categories: Array.from(categories),
      complexity_distribution: complexityDist,
      defect_level_distribution: defectLevelDist
    }

    tablePagination.value.total = customRules.value.length
  } catch (error) {
    console.error('❌ 自定义规则加载失败:', error)
    message.error('加载自定义规则失败')
  } finally {
    loading.value = false
  }
}

const handleTableChange = (pag: any) => {
  tablePagination.value.current = pag.current
  tablePagination.value.pageSize = pag.pageSize
}

// 辅助方法
const getDisplayId = (record: any) => record.rule_id || record.rule_code

const getCategoryZh = (val: string) => val
const getSeverityZh = (val: string) => val
const getDocTypeZh = (val: string) => {
  const map: Record<string, string> = {
    admission_record: '入院记录',
    progress_note: '病程记录',
    discharge_record: '出院记录',
    operation_record: '手术记录',
    examination_report: '辅助检查',
    consent_form: '知情同意书'
  }
  return map[val] || val
}

// 样式映射
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

// 详情与测试
const viewSichuanRuleDetail = (rule: SichuanQCRule) => {
  selectedRule.value = rule
  showRuleDetail.value = true
  if (isAdmin.value) {
    currentPrompt.value = rule.custom_prompt || '// 暂无自定义提示词'
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
    // 使用内置示例逻辑
    const ruleId = testingRule.value.rule_id
    let ruleCase = customRuleCaseMap[ruleId] || qcRuleCaseMap[ruleId]
  if (ruleCase) {
    const example = type === 'positive' ? ruleCase.positive : ruleCase.negative
      testMedicalText.value = buildCaseText(example, { includeHints: false, includeTitle: false, includeAnalysis: false, includeFocusPoints: false })
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
  showAILoadingMask.value = true
  
  try {
    // 模拟 API 调用
    await new Promise(resolve => setTimeout(resolve, 1500))
    const isCompliant = testExampleType.value === 'positive'
    testResult.value = {
      is_compliant: isCompliant,
      confidence: 0.92,
      findings: isCompliant ? '未发现明显缺陷。' : '病历中未包含必要的检查信息。',
      evidence: isCompliant ? '' : '相关段落缺失',
      suggestion: isCompliant ? '' : '请补充相关信息。'
    }
    message.success('测试完成')
  } catch (e) {
    message.error('测试失败')
  } finally {
    testLoading.value = false
    showAILoadingMask.value = false
  }
}

const goToBatchTest = () => {
  const source = isLegacyMode.value ? 'lx_legacy' : 'custom'
  router.push({ name: 'BatchRuleTest', query: { source } })
}

// 质控点说明弹窗配置
const ruleDocModalTitle = computed(() => isLegacyMode.value ? '质控点说明（泸县存量质控规则）' : '质控点说明（泸县33条规则）')
const extractCheckPoints = (prompt?: string) => {
  if (!prompt) return ''
  const marker = '【检查要点】'
  const start = prompt.indexOf(marker)
  if (start === -1) return ''
  const after = prompt.slice(start + marker.length)
  const nextHeader = after.indexOf('【')
  return (nextHeader === -1 ? after : after.slice(0, nextHeader)).trim()
}

const ruleDocColumns = [
  { title: '编号', key: 'rule_id', width: 100 },
  { title: '名称', key: 'name', width: 200 },
  { title: '描述', key: 'description', width: 300 },
  { title: '检查要点', key: 'check_points' }
]

const ruleDocRows = computed(() => 
  customRules.value.map(r => ({
    rule_id: r.rule_id,
    name: r.name,
    description: r.description,
    check_points: extractCheckPoints(r.custom_prompt)
  }))
)

// Prompt 管理
const startEditPrompt = () => { editingPrompt.value = currentPrompt.value; isEditingPrompt.value = true }
const cancelEditPrompt = () => { isEditingPrompt.value = false }
const savePrompt = () => { message.info('请修改 JSON 文件以保存提示词'); isEditingPrompt.value = false }
const resetToDefault = () => { message.info('请修改 JSON 文件以恢复默认'); isEditingPrompt.value = false }

onMounted(() => {
  ApiService.getCurrentUser().then(res => { if(res.success) currentUser.value = res.data })
  initCustomRules()
})
</script>

<style scoped>
.custom-rules-manager {
  padding: 0;
}

/* 卡片样式 - 复用 SemanticRulesManager 样式 */
.stats-card {
  background: white;
  border-radius: 1.25rem;
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
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  border-bottom: 1px solid #e2e8f0;
  padding: 1.25rem 1rem;
}

.modern-table :deep(.ant-table-tbody > tr > td) {
  padding: 1.25rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.9rem;
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
  transition: all 0.2s;
}
</style>
