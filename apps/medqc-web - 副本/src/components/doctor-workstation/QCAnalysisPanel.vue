<template>
  <div class="qc-analysis-panel">
    <!-- 面板头部 -->
    <div class="panel-header">
      <h3 class="panel-title">
        <i class="fas fa-shield-alt" />
        质控分析
      </h3>
      <button 
        class="refresh-btn"
        :disabled="isAnalyzing"
        title="刷新分析"
        @click="$emit('refresh')"
      >
        <i
          class="fas fa-sync-alt"
          :class="{ 'fa-spin': isAnalyzing }"
        />
      </button>
    </div>

    <!-- 分析状态 -->
    <div
      v-if="isAnalyzing"
      class="analysis-loading"
    >
      <div class="loading-spinner">
        <i class="fas fa-spinner fa-spin" />
      </div>
      <p>正在进行质控分析...</p>
    </div>

    <!-- 分析结果 -->
    <div
      v-else-if="normalizedResult"
      class="analysis-results"
    >
      <!-- 总体评分 -->
      <div class="score-section">
        <div class="score-card">
          <div class="score-value">
            {{ normalizedResult.overall_score }}
          </div>
          <div class="score-total">
            / {{ normalizedResult.max_score }}
          </div>
          <div class="score-label">
            总分
          </div>
        </div>
        
        <div class="score-details">
          <div class="score-percentage">
            {{ Math.round((normalizedResult.overall_score / normalizedResult.max_score) * 100) }}%
          </div>
          <div
            class="score-grade"
            :class="getGradeClass(normalizedResult.overall_score)"
          >
            {{ getGrade(normalizedResult.overall_score) }}
          </div>
        </div>
      </div>

      <!-- 评分进度条 -->
      <div class="score-progress">
        <div class="progress-bar">
          <div 
            class="progress-fill"
            :class="getGradeClass(normalizedResult.overall_score)"
            :style="{ width: `${(normalizedResult.overall_score / normalizedResult.max_score) * 100}%` }"
          />
        </div>
        <div class="progress-labels">
          <span>0</span>
          <span>{{ normalizedResult.max_score }}</span>
        </div>
      </div>

      <!-- 规则检查结果 -->
      <div class="rules-section">
        <h4 class="section-title">
          <i class="fas fa-list-check" />
          规则检查结果
        </h4>
        
        <div class="rules-list">
          <div 
            v-for="rule in normalizedResult.analysis_results" 
            :key="rule.rule_id"
            class="rule-item"
            :class="{ 'rule-failed': !rule.passed }"
          >
            <div class="rule-header">
              <div class="rule-status">
                <i 
                  class="fas"
                  :class="rule.passed ? 'fa-check-circle text-success' : 'fa-times-circle text-danger'"
                />
              </div>
              <div class="rule-info">
                <div class="rule-name">
                  {{ rule.rule_name }}
                </div>
                <div class="rule-category">
                  {{ getCategoryName(rule.category) }}
                </div>
              </div>
              <div class="rule-score">
                <span class="score">{{ rule.score }}</span>
                <span class="max-score">/ {{ rule.max_score }}</span>
              </div>
            </div>
            
            <!-- 问题详情 -->
            <div
              v-if="rule.issues.length > 0"
              class="rule-issues"
            >
              <div 
                v-for="issue in rule.issues" 
                :key="issue.code"
                class="issue-item"
                :class="`issue-${issue.severity}`"
              >
                <div class="issue-header">
                  <i 
                    class="fas fa-exclamation-triangle"
                    :class="{
                      'text-danger': issue.severity === 'critical',
                      'text-warning': issue.severity === 'major',
                      'text-info': issue.severity === 'minor'
                    }"
                  />
                  <span class="issue-description">{{ issue.description }}</span>
                </div>
                <div class="issue-details">
                  <div class="issue-location">
                    位置：{{ issue.location }}
                  </div>
                  <div class="issue-suggestion">
                    建议：{{ issue.suggestion }}
                    <button 
                      class="apply-suggestion-btn"
                      title="应用建议"
                      @click="$emit('apply-suggestion', issue.suggestion)"
                    >
                      <i class="fas fa-magic" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 改进建议 -->
      <div
        v-if="structuredAnalysisSuggestions.length > 0"
        class="suggestions-section"
      >
        <h4 class="section-title">
          <i class="fas fa-lightbulb" />
          改进建议
        </h4>
        
        <div class="suggestions-list">
          <div 
            v-for="(suggestion, index) in structuredAnalysisSuggestions" 
            :key="suggestion.id || index"
            class="suggestion-item"
          >
            <div class="suggestion-content">
              <i class="fas fa-arrow-right" />
              <div class="suggestion-steps">
                <div
                  v-if="suggestion.title"
                  class="suggestion-title"
                >
                  {{ suggestion.title }}
                </div>
                <ol class="pl-5 list-decimal space-y-1">
                  <li
                    v-for="(step, index) in suggestion.steps"
                    :key="index"
                  >
                    {{ step }}
                  </li>
                </ol>
              </div>
            </div>
            <button 
              class="apply-suggestion-btn"
              title="应用建议"
              @click="$emit('apply-suggestion', suggestion.description || suggestion.steps.join(' '))"
            >
              <i class="fas fa-magic" />
            </button>
          </div>
        </div>
      </div>

      <!-- 严重问题警告 -->
      <div
        v-if="normalizedResult.critical_issues.length > 0"
        class="critical-issues-section"
      >
        <h4 class="section-title critical">
          <i class="fas fa-exclamation-triangle" />
          严重问题
        </h4>
        
        <div class="critical-issues-list">
          <div 
            v-for="issue in normalizedResult.critical_issues" 
            :key="issue.code"
            class="critical-issue-item"
          >
            <div class="critical-issue-header">
              <i class="fas fa-times-circle text-danger" />
              <span class="critical-issue-description">{{ issue.description }}</span>
            </div>
            <div class="critical-issue-suggestion">
              {{ issue.suggestion }}
            </div>
          </div>
        </div>
      </div>

      <!-- 分析时间 -->
      <div class="analysis-timestamp">
        <i class="fas fa-clock" />
        分析时间：{{ formatTimestamp(normalizedResult.analysis_timestamp) }}
      </div>
    </div>

    <!-- 无分析结果 -->
    <div
      v-else
      class="no-analysis"
    >
      <div class="no-analysis-icon">
        <i class="fas fa-search" />
      </div>
      <p>暂无质控分析结果</p>
      <p class="no-analysis-hint">
        请输入病历内容后点击"质控分析"按钮
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { QCAnalysisResult } from '@/api/medical-records'
import { structureSuggestions } from '@/utils/suggestionFormatter'

// Props
interface Props {
  analysisResult: QCAnalysisResult | null
  isAnalyzing: boolean
}

const props = defineProps<Props>()

// Emits
defineEmits<{
  refresh: []
  'apply-suggestion': [suggestion: string]
}>()

interface NormalizedIssue {
  code: string
  description: string
  severity: 'critical' | 'major' | 'minor'
  location: string
  suggestion: string
}

interface NormalizedRuleResult {
  rule_id: string
  rule_name: string
  category: string
  passed: boolean
  score: number
  max_score: number
  issues: NormalizedIssue[]
}

interface NormalizedQCAnalysisResult {
  overall_score: number
  max_score: number
  analysis_results: NormalizedRuleResult[]
  critical_issues: NormalizedIssue[]
  analysis_timestamp: string
}

const normalizedResult = computed<NormalizedQCAnalysisResult | null>(() => {
  if (!props.analysisResult) return null

  const score = Number(props.analysisResult.score ?? 0)
  const normalizedIssues: NormalizedIssue[] = (props.analysisResult.issues || []).map((issue, index) => {
    const rawSeverity = String(issue.severity || '').toLowerCase()
    const severity = rawSeverity === 'critical' || rawSeverity === 'major' || rawSeverity === 'minor'
      ? rawSeverity
      : 'minor'
    return {
      code: `ISSUE_${index + 1}`,
      description: issue.description || '检测到潜在问题',
      severity,
      location: '病历内容',
      suggestion: '请根据质控规范补充和修正内容'
    }
  })

  return {
    overall_score: score,
    max_score: 100,
    analysis_results: [{
      rule_id: 'QC_SUMMARY',
      rule_name: '综合质量评估',
      category: 'completeness',
      passed: normalizedIssues.length === 0,
      score,
      max_score: 100,
      issues: normalizedIssues
    }],
    critical_issues: normalizedIssues.filter(issue => issue.severity === 'critical'),
    analysis_timestamp: new Date().toISOString()
  }
})

// 计算属性和方法
const getGrade = (score: number): string => {
  if (score >= 90) return 'A'
  if (score >= 80) return 'B'
  if (score >= 70) return 'C'
  return 'D'
}

const getGradeClass = (score: number): string => {
  if (score >= 90) return 'grade-a'
  if (score >= 80) return 'grade-b'
  if (score >= 70) return 'grade-c'
  return 'grade-d'
}

const getCategoryName = (category: string): string => {
  const categoryMap: Record<string, string> = {
    completeness: '完整性',
    consistency: '一致性',
    rationality: '合理性',
    timeliness: '及时性',
    accuracy: '准确性'
  }
  return categoryMap[category] || category
}

const formatTimestamp = (timestamp: string): string => {
  return new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const structuredAnalysisSuggestions = computed(() => {
  const suggestions = props.analysisResult?.suggestions || []
  if (suggestions.length === 0) return []
  if (typeof suggestions[0] === 'string') {
    const normalized = (suggestions as string[]).map((desc, idx) => ({
      id: `suggestion-${idx}`,
      title: '',
      description: desc,
      category: '',
      priority: 'medium' as const,
      actionRequired: false
    }))
    return structureSuggestions(normalized as any)
  }
  return structureSuggestions(suggestions as any)
})
</script>

<style scoped>
.qc-analysis-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: #f8f9fa;
  border-bottom: 1px solid #e1e8ed;
}

.panel-title {
  margin: 0;
  color: #495057;
  font-size: 1.1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.refresh-btn {
  padding: 0.5rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  color: #6c757d;
  transition: all 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #e9ecef;
  color: #495057;
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.analysis-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: #6c757d;
}

.loading-spinner {
  font-size: 2rem;
  margin-bottom: 1rem;
  color: #007bff;
}

.analysis-results {
  flex: 1;
  padding: 1rem;
  overflow-y: auto;
}

.score-section {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.score-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.score-value {
  font-size: 2.5rem;
  font-weight: bold;
  color: #007bff;
  line-height: 1;
}

.score-total {
  font-size: 1rem;
  color: #6c757d;
  margin-top: -0.5rem;
}

.score-label {
  font-size: 0.875rem;
  color: #495057;
  margin-top: 0.25rem;
}

.score-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.score-percentage {
  font-size: 1.5rem;
  font-weight: bold;
  color: #495057;
}

.score-grade {
  font-size: 1.25rem;
  font-weight: bold;
  padding: 0.25rem 0.75rem;
  border-radius: 20px;
  text-align: center;
  width: fit-content;
}

.grade-a { background: #d4edda; color: #155724; }
.grade-b { background: #d1ecf1; color: #0c5460; }
.grade-c { background: #fff3cd; color: #856404; }
.grade-d { background: #f8d7da; color: #721c24; }

.score-progress {
  margin-bottom: 1.5rem;
}

.progress-bar {
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.progress-fill.grade-a { background: #28a745; }
.progress-fill.grade-b { background: #17a2b8; }
.progress-fill.grade-c { background: #ffc107; }
.progress-fill.grade-d { background: #dc3545; }

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: #6c757d;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #495057;
}

.section-title.critical {
  color: #dc3545;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.rule-item {
  border: 1px solid #e1e8ed;
  border-radius: 6px;
  overflow: hidden;
}

.rule-item.rule-failed {
  border-color: #f5c6cb;
  background: #fdf2f2;
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: white;
}

.rule-item.rule-failed .rule-header {
  background: #fefefe;
}

.rule-status {
  font-size: 1.25rem;
}

.rule-info {
  flex: 1;
}

.rule-name {
  font-weight: 500;
  color: #495057;
  margin-bottom: 0.25rem;
}

.rule-category {
  font-size: 0.875rem;
  color: #6c757d;
}

.rule-score {
  font-weight: 500;
  color: #495057;
}

.max-score {
  color: #6c757d;
}

.rule-issues {
  border-top: 1px solid #e1e8ed;
  background: #f8f9fa;
}

.issue-item {
  padding: 0.75rem;
  border-bottom: 1px solid #e1e8ed;
}

.issue-item:last-child {
  border-bottom: none;
}

.issue-header {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.issue-description {
  font-weight: 500;
  color: #495057;
}

.issue-details {
  margin-left: 1.5rem;
  font-size: 0.875rem;
  color: #6c757d;
}

.issue-location {
  margin-bottom: 0.25rem;
}

.issue-suggestion {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.apply-suggestion-btn {
  padding: 0.25rem 0.5rem;
  border: 1px solid #007bff;
  background: white;
  color: #007bff;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.apply-suggestion-btn:hover {
  background: #007bff;
  color: white;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.suggestion-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #e7f3ff;
  border-radius: 6px;
  border-left: 4px solid #007bff;
}

.suggestion-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #495057;
}

.critical-issues-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.critical-issue-item {
  padding: 0.75rem;
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 6px;
  border-left: 4px solid #dc3545;
}

.critical-issue-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #721c24;
}

.critical-issue-suggestion {
  font-size: 0.875rem;
  color: #721c24;
  margin-left: 1.5rem;
}

.analysis-timestamp {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #6c757d;
  margin-top: auto;
}

.no-analysis {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  text-align: center;
  color: #6c757d;
  flex: 1;
}

.no-analysis-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.no-analysis-hint {
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.text-success { color: #28a745; }
.text-danger { color: #dc3545; }
.text-warning { color: #ffc107; }
.text-info { color: #17a2b8; }
</style>
