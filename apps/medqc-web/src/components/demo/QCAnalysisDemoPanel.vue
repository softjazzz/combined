<template>
  <div class="qc-analysis-demo-panel">
    <a-card title="质控分析过程" class="analysis-panel">
      <template #extra>
        <a-tooltip title="分析状态">
          <LoadingOutlined v-if="isRunning" spin />
          <CheckCircleOutlined v-else-if="analysisResult" style="color: #52c41a" />
          <ClockCircleOutlined v-else />
        </a-tooltip>
      </template>
      
      <!-- 分析步骤 -->
      <div class="analysis-steps" v-if="analysisSteps.length > 0">
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
      
      <!-- 分析结果 -->
      <div class="analysis-result" v-if="analysisResult">
        <h4>分析结果</h4>
        <a-row :gutter="16">
          <a-col :span="8">
            <a-statistic 
              title="总体评分" 
              :value="analysisResult.overallScore" 
              suffix="分"
              :value-style="{ color: getScoreColor(analysisResult.overallScore) }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic 
              title="发现问题" 
              :value="analysisResult.issues.length" 
              suffix="个"
              :value-style="{ color: '#cf1322' }"
            />
          </a-col>
          <a-col :span="8">
            <a-statistic 
              title="改进建议" 
              :value="analysisResult.suggestions.length" 
              suffix="条"
              :value-style="{ color: '#1890ff' }"
            />
          </a-col>
        </a-row>
        
        <!-- 问题列表 -->
        <div class="issues-section" v-if="analysisResult.issues.length > 0">
          <h5>发现的问题</h5>
          <a-list 
            :data-source="analysisResult.issues" 
            size="small"
          >
            <template #renderItem="{ item }">
              <a-list-item>
                <a-list-item-meta>
                  <template #title>
                    <a-space>
                      <a-tag :color="getSeverityColor(item.severity)">
                        {{ getSeverityText(item.severity) }}
                      </a-tag>
                      {{ item.ruleName }}
                    </a-space>
                  </template>
                  <template #description>
                    {{ item.description }}
                  </template>
                </a-list-item-meta>
              </a-list-item>
            </template>
          </a-list>
        </div>
      </div>
      
      <!-- 空状态 -->
      <div v-else-if="!isRunning" class="empty-state">
        <a-empty description="暂无分析结果">
          <a-button type="primary" @click="handleStartAnalysis">
            开始分析
          </a-button>
        </a-empty>
      </div>
      
      <!-- 加载状态 -->
      <div v-else class="loading-state">
        <a-spin size="large">
          <div class="loading-content">
            <p>正在进行质控分析...</p>
            <p class="loading-tip">请稍候，这可能需要几分钟时间</p>
          </div>
        </a-spin>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  LoadingOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons-vue'
import type { QCResult, AnalysisStep } from '@/types/quality-control'

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

const getSeverityColor = (severity: string) => {
  const colors = {
    low: 'green',
    medium: 'orange',
    high: 'red',
    critical: 'red'
  }
  return colors[severity as keyof typeof colors] || 'default'
}

const getSeverityText = (severity: string) => {
  const texts = {
    low: '轻微',
    medium: '中等',
    high: '严重',
    critical: '严重'
  }
  return texts[severity as keyof typeof texts] || severity
}

const handleStartAnalysis = () => {
  message.info('请在左侧配置面板中开始演示')
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
    
    .analysis-result {
      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
      }
      
      .issues-section {
        margin-top: 24px;
        
        h5 {
          font-weight: 600;
          margin-bottom: 12px;
          color: #333;
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
