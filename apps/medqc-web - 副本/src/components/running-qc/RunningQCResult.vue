<template>
  <div class="running-qc-result">
    <!-- 概览信息 -->
    <a-card
      title="质控概览"
      class="mb-4"
    >
      <a-row :gutter="24">
        <a-col :span="6">
          <a-statistic
            title="总体评分"
            :value="result.summary.totalScore"
            suffix="分"
            :value-style="{ color: getScoreColor(result.summary.totalScore) }"
          />
        </a-col>
        <a-col :span="6">
          <a-statistic
            title="质控等级"
            :value="result.summary.grade"
            :value-style="{ color: getGradeColor(result.summary.grade) }"
          />
        </a-col>
        <a-col :span="6">
          <a-statistic
            title="风险等级"
            :value="getRiskText(result.summary.riskLevel)"
            :value-style="{ color: getRiskColor(result.summary.riskLevel) }"
          />
        </a-col>
        <a-col :span="6">
          <a-statistic
            title="下次检查"
            :value="formatTime(result.nextCheckTime)"
            :value-style="{ fontSize: '14px' }"
          />
        </a-col>
      </a-row>
    </a-card>
    
    <!-- 实时问题 -->
    <a-card
      v-if="result.realTimeIssues.length > 0"
      title="实时质控问题"
      class="mb-4"
    >
      <a-list
        :data-source="result.realTimeIssues"
        item-layout="horizontal"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <a-tag :color="getSeverityColor(item.severity)">
                    {{ getSeverityText(item.severity) }}
                  </a-tag>
                  <span>{{ item.qualityPointName }}</span>
                  <a-tag
                    v-if="item.isUrgent"
                    color="red"
                  >
                    紧急
                  </a-tag>
                  <a-tag
                    v-if="item.requiresImmediateAction"
                    color="orange"
                  >
                    需立即处理
                  </a-tag>
                </a-space>
              </template>
              <template #description>
                <div class="mb-2">
                  <strong>问题描述：</strong>{{ item.content }}
                </div>
                <div class="mb-2">
                  <strong>改进建议：</strong>{{ item.suggestion }}
                </div>
                <div>
                  <strong>扣分：</strong>{{ item.deductionScore }}分
                  <a-divider type="vertical" />
                  <strong>科室：</strong>{{ item.department }}
                  <a-divider type="vertical" />
                  <strong>质控点ID：</strong>{{ item.qualityPointId }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
    
    <!-- 科室特定问题 -->
    <a-card
      v-if="result.departmentSpecificIssues.length > 0"
      title="科室特定问题"
      class="mb-4"
    >
      <a-list
        :data-source="result.departmentSpecificIssues"
        item-layout="horizontal"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <span>{{ item.qualityPointName }}</span>
                  <a-tag
                    v-if="item.isEffectiveToDoctor"
                    color="blue"
                  >
                    医生端生效
                  </a-tag>
                </a-space>
              </template>
              <template #description>
                <div class="mb-2">
                  <strong>问题描述：</strong>{{ item.content }}
                </div>
                <div>
                  <strong>改进建议：</strong>{{ item.suggestion }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
    
    <!-- 时效性检查 -->
    <a-card
      v-if="result.timelinessChecks.length > 0"
      title="时效性检查"
      class="mb-4"
    >
      <a-list
        :data-source="result.timelinessChecks"
        item-layout="horizontal"
      >
        <template #renderItem="{ item }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-space>
                  <span>{{ getCheckTypeText(item.checkType) }}</span>
                  <a-tag
                    v-if="item.isOverdue"
                    color="red"
                  >
                    已超时
                  </a-tag>
                  <a-tag
                    v-else
                    color="green"
                  >
                    正常
                  </a-tag>
                </a-space>
              </template>
              <template #description>
                <div class="mb-2">
                  <strong>预期时间：</strong>{{ formatTime(item.expectedTime) }}
                  <span
                    v-if="item.actualTime"
                    class="ml-4"
                  >
                    <strong>实际时间：</strong>{{ formatTime(item.actualTime) }}
                  </span>
                </div>
                <div
                  v-if="item.isOverdue"
                  class="mb-2"
                >
                  <strong>超时时长：</strong>{{ item.overdueHours }}小时
                </div>
                <div>
                  <strong>建议：</strong>{{ item.suggestion }}
                </div>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
    
    <!-- 改进建议 -->
    <a-card
      v-if="result.recommendations.length > 0"
      title="改进建议"
      class="mb-4"
    >
      <a-list
        :data-source="result.recommendations"
        size="small"
      >
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-typography-text>
              <strong>{{ index + 1 }}. </strong>{{ item }}
            </a-typography-text>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
    
    <!-- 分析信息 -->
    <a-card
      title="分析信息"
      class="mb-4"
    >
      <a-descriptions
        :column="2"
        size="small"
      >
        <a-descriptions-item label="病历ID">
          {{ result.recordId }}
        </a-descriptions-item>
        <a-descriptions-item label="患者ID">
          {{ result.patientId }}
        </a-descriptions-item>
        <a-descriptions-item label="分析类型">
          {{ getAnalysisTypeText(result.analysisType) }}
        </a-descriptions-item>
        <a-descriptions-item label="分析时间">
          {{ formatTime(result.analysisTime) }}
        </a-descriptions-item>
        <a-descriptions-item
          label="总体评估"
          :span="2"
        >
          {{ result.summary.overallAssessment }}
        </a-descriptions-item>
      </a-descriptions>
    </a-card>
    
    <!-- 操作按钮 -->
    <div class="text-center">
      <a-space>
        <a-button @click="$emit('close')">
          关闭
        </a-button>
        <a-button
          type="primary"
          @click="exportReport"
        >
          导出报告
        </a-button>
        <a-button @click="scheduleRecheck">
          安排复查
        </a-button>
      </a-space>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'

// 定义接口
interface RunningQCResult {
  recordId: string
  patientId: string
  analysisType: 'real-time' | 'scheduled' | 'triggered'
  analysisTime: string
  summary: {
    totalScore: number
    grade: '甲级' | '乙级' | '丙级'
    overallAssessment: string
    riskLevel: 'low' | 'medium' | 'high' | 'critical'
  }
  realTimeIssues: Array<{
    qualityPointId: string
    qualityPointName: string
    content: string
    severity: 'low' | 'medium' | 'high' | 'critical'
    deductionScore: number
    department: string
    alertLevel: string
    isUrgent: boolean
    requiresImmediateAction: boolean
    suggestion: string
  }>
  departmentSpecificIssues: Array<{
    qualityPointId: string
    qualityPointName: string
    content: string
    isEffectiveToDoctor: boolean
    suggestion: string
  }>
  timelinessChecks: Array<{
    checkType: 'admission_record' | 'progress_note' | 'surgery_record' | 'discharge_record'
    expectedTime: string
    actualTime?: string
    isOverdue: boolean
    overdueHours?: number
    suggestion: string
  }>
  recommendations: string[]
  nextCheckTime: string
}

// Props
const props = defineProps<{
  result: RunningQCResult
}>()

// Emits
const emit = defineEmits<{
  close: []
}>()

// 辅助函数
const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 75) return '#faad14'
  return '#ff4d4f'
}

const getGradeColor = (grade: string) => {
  switch (grade) {
    case '甲级': return '#52c41a'
    case '乙级': return '#faad14'
    case '丙级': return '#ff4d4f'
    default: return '#666'
  }
}

const getRiskColor = (level: string) => {
  switch (level) {
    case 'low': return '#52c41a'
    case 'medium': return '#faad14'
    case 'high': return '#ff7875'
    case 'critical': return '#ff4d4f'
    default: return '#666'
  }
}

const getRiskText = (level: string) => {
  switch (level) {
    case 'low': return '低风险'
    case 'medium': return '中风险'
    case 'high': return '高风险'
    case 'critical': return '严重风险'
    default: return '未知'
  }
}

const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'low': return 'default'
    case 'medium': return 'orange'
    case 'high': return 'red'
    case 'critical': return 'red'
    default: return 'default'
  }
}

const getSeverityText = (severity: string) => {
  switch (severity) {
    case 'low': return '轻微'
    case 'medium': return '中等'
    case 'high': return '严重'
    case 'critical': return '危急'
    default: return '未知'
  }
}

const getCheckTypeText = (checkType: string) => {
  switch (checkType) {
    case 'admission_record': return '入院记录'
    case 'progress_note': return '病程记录'
    case 'surgery_record': return '手术记录'
    case 'discharge_record': return '出院记录'
    default: return '未知检查'
  }
}

const getAnalysisTypeText = (analysisType: string) => {
  switch (analysisType) {
    case 'real-time': return '实时分析'
    case 'scheduled': return '定时分析'
    case 'triggered': return '触发分析'
    default: return '未知'
  }
}

const formatTime = (timeString: string) => {
  return dayjs(timeString).format('YYYY-MM-DD HH:mm:ss')
}

// 操作方法
const exportReport = () => {
  // 实现导出报告功能
  message.success('报告导出功能开发中...')
}

const scheduleRecheck = () => {
  // 实现安排复查功能
  message.success('复查安排功能开发中...')
}
</script>

<style scoped>
.running-qc-result {
  max-height: 70vh;
  overflow-y: auto;
}

.mb-2 {
  margin-bottom: 8px;
}

.mb-4 {
  margin-bottom: 16px;
}

.ml-4 {
  margin-left: 16px;
}

.text-center {
  text-align: center;
}
</style> 