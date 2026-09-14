<template>
  <div class="qc-analysis-demo-panel">
    <a-card
      title="质控分析过程"
      class="analysis-panel"
    >
      <template #extra>
        <a-tooltip title="分析状态">
          <LoadingOutlined
            v-if="isRunning"
            spin
          />
          <CheckCircleOutlined
            v-else-if="analysisResult"
            style="color: #52c41a"
          />
          <ClockCircleOutlined v-else />
        </a-tooltip>
      </template>
      
      <!-- 分析步骤（运行中时显示） -->
      <div
        v-if="isRunning && analysisSteps.length > 0"
        class="analysis-steps"
      >
        <h4>分析步骤</h4>
        <a-steps 
          :current="getCurrentStepIndex()" 
          direction="vertical" 
          size="small"
          :status="getStepsStatus()"
        >
          <a-step 
            v-for="step in analysisSteps" 
            :key="step.id"
            :title="step.name"
            :description="step.description"
            :status="getStepStatus(step)"
          >
            <template #icon>
              <LoadingOutlined v-if="step.status === 'running'" />
              <CheckCircleOutlined v-else-if="step.status === 'completed'" />
              <ExclamationCircleOutlined v-else-if="step.status === 'error'" />
              <ClockCircleOutlined v-else />
            </template>
          </a-step>
        </a-steps>
      </div>
      
      <!-- 分析结果汇总（完成后显示） -->
      <div
        v-if="analysisResult && !isRunning"
        class="analysis-result-summary"
      >
        <h4>分析结果汇总</h4>
        <a-row :gutter="16">
          <a-col :span="6">
            <a-statistic 
              title="总体评分" 
              :value="analysisResult.overallScore" 
              suffix="分"
              :value-style="{ color: getScoreColor(analysisResult.overallScore), fontSize: '24px', fontWeight: 'bold' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="质控等级" 
              :value="analysisResult.overallGrade"
              :value-style="{ color: getGradeColor(analysisResult.overallGrade), fontSize: '24px', fontWeight: 'bold' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="发现问题" 
              :value="analysisResult.issues.length" 
              suffix="个"
              :value-style="{ color: analysisResult.issues.length > 0 ? '#cf1322' : '#52c41a', fontSize: '20px' }"
            />
          </a-col>
          <a-col :span="6">
            <a-statistic 
              title="改进建议" 
              :value="analysisResult.suggestions.length" 
              suffix="条"
              :value-style="{ color: '#2b6cf6', fontSize: '20px' }"
            />
          </a-col>
        </a-row>
        
        <!-- 查看详细报告按钮 -->
        <div class="view-detail-section">
          <a-button
            type="primary"
            size="large"
            block
            @click="handleViewDetail"
          >
            <FileTextOutlined />
            查看完整质控报告
          </a-button>
          <p class="hint-text">
            点击查看详细的分析步骤、问题列表和规则明细
          </p>
        </div>
      </div>

      <!-- 空状态 -->
      <div
        v-else-if="!isRunning"
        class="empty-state"
      >
        <a-empty description="暂无分析结果">
          <a-button
            type="primary"
            @click="handleStartAnalysis"
          >
            开始分析
          </a-button>
        </a-empty>
      </div>
      
      <!-- 加载状态 -->
      <div
        v-else
        class="loading-state"
      >
        <a-spin size="large">
          <div class="loading-content">
            <p>正在进行质控分析...</p>
            <p class="loading-tip">
              请稍候，这可能需要几分钟时间
            </p>
          </div>
        </a-spin>
      </div>
    </a-card>

    <!-- 质控结果详情弹窗 -->
    <QCResultDetailModal
      v-model:visible="showDetailModal"
      :result="analysisResult"
      :analysis-steps="analysisSteps"
      @close="showDetailModal = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  LoadingOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import type { QCResult, AnalysisStep } from '@/types/quality-control'
import QCResultDetailModal from './QCResultDetailModal.vue'

// Props
const props = defineProps<{
  analysisSteps: AnalysisStep[]
  analysisResult: QCResult | null
  isRunning: boolean
}>()

// Emits
const emit = defineEmits<{
  analysisComplete: [result: QCResult]
}>()

// State
const showDetailModal = ref(false)

// 计算属性
const getCurrentStepIndex = () => {
  const runningIndex = props.analysisSteps.findIndex(step => step.status === 'running')
  if (runningIndex !== -1) return runningIndex
  
  const completedCount = props.analysisSteps.filter(step => step.status === 'completed').length
  return completedCount - 1
}

const getStepsStatus = () => {
  if (props.analysisSteps.some(step => step.status === 'error')) return 'error'
  if (props.isRunning) return 'process'
  if (props.analysisResult) return 'finish'
  return 'wait'
}

// 方法
const getStepStatus = (step: AnalysisStep) => {
  switch (step.status) {
    case 'completed': return 'finish'
    case 'running': return 'process'
    case 'error': return 'error'
    default: return 'wait'
  }
}

const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const getGradeColor = (grade: string) => {
  const colors: Record<string, string> = {
    'A': '#52c41a',
    'B': '#faad14',
    'C': '#fa8c16',
    'D': '#f5222d'
  }
  return colors[grade] || '#2b6cf6'
}

const handleStartAnalysis = () => {
  message.info('请在左侧配置面板中开始演示')
}

const handleViewDetail = () => {
  showDetailModal.value = true
}
</script>

<style scoped lang="less">
.qc-analysis-demo-panel {
  .analysis-panel {
    .analysis-steps {
      margin-bottom: 24px;
      
      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
      }
    }
    
    .analysis-result-summary {
      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
      }

      .view-detail-section {
        margin-top: 24px;
        text-align: center;

        .hint-text {
          margin-top: 12px;
          color: #8c8c8c;
          font-size: 14px;
        }
      }
    }
    
    .empty-state {
      text-align: center;
      padding: 60px 0;
    }
    
    .loading-state {
      text-align: center;
      padding: 60px 0;
      
      .loading-content {
        margin-top: 16px;
        
        p {
          margin: 8px 0;
          
          &.loading-tip {
            color: #666;
            font-size: 14px;
          }
        }
      }
    }
  }
}
</style>

