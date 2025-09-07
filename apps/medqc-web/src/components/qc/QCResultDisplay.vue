<template>
  <div class="qc-result-display">
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- 左侧：总体评分和等级 -->
      <div class="xl:col-span-1">
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <div class="text-center">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center justify-center gap-2 mb-6">
              <TrophyOutlined class="text-cyan-400" />
              质控评分
            </h3>

            <!-- 评分圆环 -->
            <div class="relative inline-flex items-center justify-center w-32 h-32 mb-6">
              <svg class="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  stroke="currentColor"
                  stroke-width="6"
                  fill="none"
                  class="text-slate-700"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  stroke="currentColor"
                  stroke-width="6"
                  fill="none"
                  :stroke-dasharray="`${(result.overall_score / 100) * 251.2} 251.2`"
                  :class="getScoreCircleColor(result.overall_score)"
                  class="transition-all duration-2000 ease-out score-circle"
                />
              </svg>
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="text-center">
                  <div 
                    class="text-3xl font-bold mb-1"
                    :class="getScoreColor(result.overall_score)"
                  >
                    {{ result.overall_score }}
                  </div>
                  <div class="text-sm text-slate-400">分</div>
                </div>
              </div>
            </div>

            <!-- 等级标签 -->
            <div class="mb-6">
              <a-tag 
                :color="getGradeColor(result.overall_grade)" 
                size="large"
                class="px-6 py-2 text-lg font-bold grade-tag"
              >
                {{ result.overall_grade }}级质控
              </a-tag>
            </div>

            <!-- 评分说明 -->
            <div class="text-sm text-slate-400 space-y-2">
              <div class="font-medium">{{ getScoreDescription(result.overall_score) }}</div>
              <div class="text-xs">
                分析时间：{{ formatDate(result.analysis_date) }}
              </div>
            </div>

            <!-- 快速统计 -->
            <div class="mt-6 grid grid-cols-2 gap-4">
              <div class="text-center p-3 rounded-lg bg-slate-700/30">
                <div class="text-lg font-bold text-red-400">{{ criticalIssuesCount }}</div>
                <div class="text-xs text-slate-400">严重问题</div>
              </div>
              <div class="text-center p-3 rounded-lg bg-slate-700/30">
                <div class="text-lg font-bold text-amber-400">{{ totalIssuesCount }}</div>
                <div class="text-xs text-slate-400">总问题数</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：详细分析结果 -->
      <div class="xl:col-span-2 space-y-6">
        <!-- 问题列表 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <ExclamationCircleOutlined class="text-amber-400" />
              发现的问题 ({{ result.issues.length }})
            </h3>
            <div class="flex items-center gap-2">
              <a-select
                v-model:value="issueFilter"
                size="small"
                style="width: 120px"
                @change="filterIssues"
                class="filter-select"
              >
                <a-select-option value="all">全部问题</a-select-option>
                <a-select-option value="critical">严重</a-select-option>
                <a-select-option value="major">重要</a-select-option>
                <a-select-option value="minor">轻微</a-select-option>
              </a-select>
            </div>
          </div>

          <div class="space-y-3 max-h-96 overflow-y-auto">
            <div
              v-for="issue in filteredIssues"
              :key="issue.id"
              class="p-4 rounded-lg border transition-all duration-200 hover:shadow-lg cursor-pointer"
              :class="getIssueBorderClass(issue.severity)"
              @click="$emit('highlight-issue', issue)"
            >
              <div class="flex items-start gap-3">
                <div 
                  class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  :class="getSeverityIconClass(issue.severity)"
                >
                  <ExclamationOutlined class="text-xs" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-2">
                    <h4 class="font-medium text-slate-100 truncate">{{ issue.rule_name }}</h4>
                    <a-tag 
                      :color="getSeverityColor(issue.severity)" 
                      size="small"
                      class="severity-tag"
                    >
                      {{ getSeverityLabel(issue.severity) }}
                    </a-tag>
                  </div>
                  <p class="text-sm text-slate-300 mb-2">{{ issue.description }}</p>
                  <div class="flex items-center gap-4 text-xs text-slate-400">
                    <span class="flex items-center gap-1">
                      <TagOutlined />
                      {{ issue.category }}
                    </span>
                    <span class="flex items-center gap-1">
                      <EnvironmentOutlined />
                      {{ issue.location }}
                    </span>
                  </div>
                  <div class="mt-2 p-2 rounded bg-blue-500/10 border border-blue-500/20">
                    <div class="text-xs text-blue-200 font-medium mb-1">建议：</div>
                    <div class="text-xs text-blue-300">{{ issue.suggestion }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="filteredIssues.length === 0" class="text-center py-8">
            <div class="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-3">
              <CheckCircleOutlined class="text-emerald-400 text-2xl" />
            </div>
            <div class="text-slate-400">{{ issueFilter === 'all' ? '未发现质控问题' : '该级别无问题' }}</div>
          </div>
        </div>

        <!-- 改进建议 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <BulbOutlined class="text-yellow-400" />
            改进建议 ({{ result.suggestions.length }})
          </h3>

          <div class="space-y-3">
            <div
              v-for="suggestion in result.suggestions"
              :key="suggestion.id"
              class="p-4 rounded-lg bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 hover:border-yellow-500/40 transition-all duration-200"
            >
              <div class="flex items-start gap-3">
                <div 
                  class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                  :class="getPriorityIconClass(suggestion.priority)"
                >
                  <StarOutlined class="text-xs" />
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-2">
                    <h4 class="font-medium text-slate-100">{{ suggestion.title }}</h4>
                    <a-tag 
                      :color="getPriorityColor(suggestion.priority)" 
                      size="small"
                    >
                      {{ getPriorityLabel(suggestion.priority) }}
                    </a-tag>
                  </div>
                  <p class="text-sm text-slate-300 mb-2">{{ suggestion.description }}</p>
                  <div class="text-xs text-yellow-400 flex items-center gap-1">
                    <TagOutlined />
                    {{ suggestion.category }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="result.suggestions.length === 0" class="text-center py-8">
            <div class="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-3">
              <CheckCircleOutlined class="text-emerald-400 text-2xl" />
            </div>
            <div class="text-slate-400">暂无改进建议</div>
          </div>
        </div>

        <!-- 规则执行结果 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <SettingOutlined class="text-purple-400" />
            规则执行结果
          </h3>

          <div class="space-y-3">
            <div
              v-for="ruleResult in result.rule_results"
              :key="ruleResult.rule_id"
              class="p-4 rounded-lg border border-slate-600/30 bg-slate-700/20"
            >
              <div class="flex items-center justify-between mb-2">
                <div class="flex items-center gap-2">
                  <div 
                    class="w-4 h-4 rounded-full"
                    :class="ruleResult.passed ? 'bg-emerald-400' : 'bg-red-400'"
                  ></div>
                  <span class="font-medium text-slate-100">{{ ruleResult.rule_name }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span 
                    class="text-sm font-bold"
                    :class="getScoreColor(ruleResult.score)"
                  >
                    {{ ruleResult.score }}分
                  </span>
                  <a-tag 
                    :color="ruleResult.passed ? 'green' : 'red'" 
                    size="small"
                  >
                    {{ ruleResult.passed ? '通过' : '未通过' }}
                  </a-tag>
                </div>
              </div>
              <p class="text-sm text-slate-400">{{ ruleResult.details }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  TrophyOutlined,
  ExclamationCircleOutlined,
  ExclamationOutlined,
  CheckCircleOutlined,
  BulbOutlined,
  StarOutlined,
  SettingOutlined,
  TagOutlined,
  EnvironmentOutlined
} from '@ant-design/icons-vue'
import type { QCResult, QCIssue } from '@/types'

// Props
interface Props {
  result: QCResult
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  'highlight-issue': [issue: QCIssue]
}>()

// 状态
const issueFilter = ref('all')

// 计算属性
const criticalIssuesCount = computed(() => 
  props.result.issues.filter(issue => issue.severity === 'critical' || issue.severity === 'major').length
)

const totalIssuesCount = computed(() => props.result.issues.length)

const filteredIssues = computed(() => {
  if (issueFilter.value === 'all') {
    return props.result.issues
  }
  return props.result.issues.filter(issue => issue.severity === issueFilter.value)
})

// 方法
const filterIssues = () => {
  // 筛选逻辑已在 computed 中处理
}

const getScoreColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

const getScoreCircleColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

const getGradeColor = (grade: string) => {
  const colors = {
    A: 'green',
    B: 'blue',
    C: 'orange'
  }
  return colors[grade as keyof typeof colors] || 'default'
}

const getScoreDescription = (score: number) => {
  if (score >= 90) return '优秀 - 病案质量很高，符合所有质控标准'
  if (score >= 80) return '良好 - 病案质量较好，存在少量问题'
  if (score >= 70) return '合格 - 病案质量一般，需要改进'
  return '不合格 - 病案质量较差，存在严重问题'
}

const getSeverityColor = (severity: string) => {
  const colors = {
    critical: 'red',
    major: 'orange',
    minor: 'yellow',
    low: 'blue'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labels = {
    critical: '严重',
    major: '重要',
    minor: '轻微',
    low: '提示'
  }
  return labels[severity as keyof typeof labels] || severity
}

const getSeverityIconClass = (severity: string) => {
  const classes = {
    critical: 'bg-red-500 text-white',
    major: 'bg-orange-500 text-white',
    minor: 'bg-yellow-500 text-white',
    low: 'bg-blue-500 text-white'
  }
  return classes[severity as keyof typeof classes] || 'bg-gray-500 text-white'
}

const getIssueBorderClass = (severity: string) => {
  const classes = {
    critical: 'border-red-500/30 bg-red-500/5 hover:border-red-500/50',
    major: 'border-orange-500/30 bg-orange-500/5 hover:border-orange-500/50',
    minor: 'border-yellow-500/30 bg-yellow-500/5 hover:border-yellow-500/50',
    low: 'border-blue-500/30 bg-blue-500/5 hover:border-blue-500/50'
  }
  return classes[severity as keyof typeof classes] || 'border-slate-600/30 bg-slate-700/5'
}

const getPriorityColor = (priority: string) => {
  const colors = {
    high: 'red',
    medium: 'orange',
    low: 'blue'
  }
  return colors[priority as keyof typeof colors] || 'default'
}

const getPriorityLabel = (priority: string) => {
  const labels = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级'
  }
  return labels[priority as keyof typeof labels] || priority
}

const getPriorityIconClass = (priority: string) => {
  const classes = {
    high: 'bg-red-500 text-white',
    medium: 'bg-orange-500 text-white',
    low: 'bg-blue-500 text-white'
  }
  return classes[priority as keyof typeof classes] || 'bg-gray-500 text-white'
}

const formatDate = (dateString: string) => {
  try {
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateString
  }
}
</script>

<style scoped>
/* 评分圆环动画 */
.score-circle {
  stroke-linecap: round;
  animation: drawCircle 2s ease-out;
}

@keyframes drawCircle {
  from {
    stroke-dasharray: 0 251.2;
  }
}

/* 等级标签样式 */
.grade-tag {
  border: none !important;
  border-radius: 1rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
}

/* 严重程度标签样式 */
.severity-tag {
  border: none !important;
  border-radius: 0.5rem !important;
  font-weight: 600 !important;
  font-size: 10px !important;
}

/* 筛选选择器样式 */
:deep(.filter-select .ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: rgb(241 245 249) !important;
}

/* 滚动条样式 */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: rgba(71, 85, 105, 0.2);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}

/* 卡片悬浮效果 */
.rounded-xl {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rounded-xl:hover {
  transform: translateY(-1px);
}

/* 问题项动画 */
.space-y-3 > div {
  animation: slideInUp 0.3s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式设计 */
@media (max-width: 1280px) {
  .xl\\:col-span-1,
  .xl\\:col-span-2 {
    grid-column: span 1;
  }
}

@media (max-width: 640px) {
  .grid-cols-2 {
    grid-template-columns: 1fr;
  }
  
  .p-6 {
    padding: 1rem;
  }
  
  .w-32.h-32 {
    width: 7rem;
    height: 7rem;
  }
}
</style>
