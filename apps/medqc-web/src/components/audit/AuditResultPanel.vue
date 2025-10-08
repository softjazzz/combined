<!-- 审核结果面板组件 -->
<template>
  <div class="audit-result-panel">
    <!-- 审核状态头部 -->
    <div class="panel-header">
      <div class="header-left">
        <h3 class="panel-title">
          {{ getLevelTitle(auditLevel) }}
          <a-tag :color="getStatusColor(auditResult?.status)">
            {{ getStatusText(auditResult?.status) }}
          </a-tag>
        </h3>
        <div class="reviewer-info" v-if="reviewerInfo">
          <UserOutlined />
          <span>审核员：{{ reviewerInfo }}</span>
          <span v-if="auditResult?.review_duration" class="duration">
            耗时：{{ auditResult.review_duration }}分钟
          </span>
        </div>
      </div>
      
      <div class="header-actions">
        <a-space>
          <a-button 
            v-if="canModifyLowerLevel && lowerLevelResults?.length"
            @click="showModifyLowerModal"
            type="dashed"
            size="small"
          >
            <EditOutlined />
            修改下级结果
          </a-button>
          
          <a-button 
            v-if="editable && auditResult?.status === 'draft'"
            @click="handleSave"
            type="primary"
            :loading="saving"
          >
            <SaveOutlined />
            保存
          </a-button>
          
          <a-button 
            v-if="editable && auditResult?.status === 'draft'"
            @click="handleSubmit"
            type="primary"
            :loading="submitting"
          >
            <CheckOutlined />
            提交
          </a-button>
        </a-space>
      </div>
    </div>

    <!-- 审核内容 -->
    <div class="panel-content">
      <a-row :gutter="24">
        <!-- 左侧：审核表单 -->
        <a-col :span="16">
          <a-card title="审核评分" class="audit-form-card">
            <a-form
              ref="auditFormRef"
              :model="formData"
              :rules="formRules"
              layout="vertical"
              @finish="handleFormSubmit"
            >
              <!-- 总体评分 -->
              <a-form-item label="总体评分" name="audit_score">
                <a-slider
                  v-model:value="formData.audit_score"
                  :min="0"
                  :max="100"
                  :marks="scoreMarks"
                  :disabled="!editable"
                  @change="handleScoreChange"
                />
                <div class="score-display">
                  <span class="score-value">{{ formData.audit_score }}</span>
                  <span class="score-level">{{ getScoreLevel(formData.audit_score) }}</span>
                </div>
              </a-form-item>

              <!-- 审核结论 -->
              <a-form-item label="审核结论" name="audit_conclusion">
                <a-textarea
                  v-model:value="formData.audit_conclusion"
                  :rows="4"
                  :disabled="!editable"
                  placeholder="请输入审核结论..."
                />
              </a-form-item>

              <!-- AI辅助缺陷识别 -->
              <a-form-item label="缺陷识别">
                <div class="defect-section">
                  <div class="section-header">
                    <span>发现的缺陷</span>
                    <a-space>
                      <a-button 
                        @click="triggerAIAssistance"
                        :loading="aiAnalyzing"
                        size="small"
                        type="dashed"
                      >
                        <RobotOutlined />
                        AI辅助识别
                      </a-button>
                      <a-button 
                        @click="addManualDefect"
                        size="small"
                        type="primary"
                        ghost
                      >
                        <PlusOutlined />
                        手动添加
                      </a-button>
                    </a-space>
                  </div>

                  <!-- 缺陷列表 -->
                  <div class="defects-list">
                    <a-empty v-if="formData.defects.length === 0" description="暂无发现缺陷" />
                    
                    <div 
                      v-for="(defect, index) in formData.defects" 
                      :key="index"
                      class="defect-item"
                    >
                      <DefectCard
                        :defect="defect"
                        :editable="editable"
                        @update="handleDefectUpdate(index, $event)"
                        @remove="handleDefectRemove(index)"
                      />
                    </div>
                  </div>
                </div>
              </a-form-item>
            </a-form>
          </a-card>
        </a-col>

        <!-- 右侧：统计信息和历史 -->
        <a-col :span="8">
          <!-- 统计卡片 -->
          <a-card title="审核统计" class="stats-card" size="small">
            <a-statistic-group>
              <a-statistic
                title="缺陷数量"
                :value="formData.defects.length"
                suffix="个"
              />
              <a-statistic
                title="严重缺陷"
                :value="criticalDefectsCount"
                suffix="个"
                :value-style="{ color: criticalDefectsCount > 0 ? '#cf1322' : '#52c41a' }"
              />
              <a-statistic
                title="扣分总计"
                :value="totalScoreDeduction"
                suffix="分"
                :value-style="{ color: '#faad14' }"
              />
            </a-statistic-group>
          </a-card>

          <!-- 下级结果预览 -->
          <a-card 
            v-if="lowerLevelResults?.length"
            title="下级审核结果"
            class="lower-results-card"
            size="small"
          >
            <div 
              v-for="lowerResult in lowerLevelResults"
              :key="lowerResult.id"
              class="lower-result-item"
            >
              <div class="result-header">
                <span class="level-name">{{ getLevelTitle(lowerResult.audit_level) }}</span>
                <span class="result-score">{{ lowerResult.audit_score }}分</span>
              </div>
              <div class="result-summary">
                {{ lowerResult.audit_conclusion || '无结论' }}
              </div>
              <a-button 
                v-if="canModifyLowerLevel"
                @click="modifyLowerResult(lowerResult)"
                size="small"
                type="link"
              >
                修改
              </a-button>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- AI建议对话框 -->
    <a-modal
      v-model:open="aiSuggestionsVisible"
      title="AI缺陷识别建议"
      width="800px"
      @ok="applyAISuggestions"
    >
      <AISuggestionsPanel
        v-if="aiSuggestionsVisible"
        :suggestions="aiSuggestions"
        @selection-change="handleAISelectionChange"
      />
    </a-modal>

    <!-- 手动添加缺陷对话框 -->
    <a-modal
      v-model:open="addDefectVisible"
      title="添加缺陷"
      @ok="confirmAddDefect"
    >
      <DefectForm
        v-if="addDefectVisible"
        ref="defectFormRef"
        @change="handleNewDefectChange"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  UserOutlined,
  EditOutlined,
  SaveOutlined,
  CheckOutlined,
  RobotOutlined,
  PlusOutlined
} from '@ant-design/icons-vue'

import type { 
  QCAuditResult, 
  QCDefect, 
  AuditLevel,
  AIDefectSuggestion 
} from '@/types/audit-module'

import { auditResultService } from '@/services/audit-result-service'
// import DefectCard from './DefectCard.vue'
// import AISuggestionsPanel from './AISuggestionsPanel.vue'
// import DefectForm from './DefectForm.vue'

// Props
interface Props {
  auditResult?: QCAuditResult | null
  auditLevel: AuditLevel
  editable?: boolean
  reviewerInfo?: string
  canModifyLowerLevel?: boolean
  lowerLevelResults?: QCAuditResult[]
  isFinalLevel?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  editable: false,
  canModifyLowerLevel: false,
  isFinalLevel: false
})

// Emits
const emit = defineEmits<{
  'update': [data: any]
  'submit': [auditResultId: string]
  'modify-lower': [result: QCAuditResult]
}>()

// 状态管理
const auditFormRef = ref()
const defectFormRef = ref()
const saving = ref(false)
const submitting = ref(false)
const aiAnalyzing = ref(false)

// 表单数据
const formData = ref({
  audit_score: 85,
  audit_conclusion: '',
  defects: [] as Partial<QCDefect>[]
})

// 对话框状态
const aiSuggestionsVisible = ref(false)
const addDefectVisible = ref(false)
const aiSuggestions = ref<AIDefectSuggestion[]>([])
const selectedSuggestions = ref<AIDefectSuggestion[]>([])

// 表单验证规则
const formRules = {
  audit_score: [
    { required: true, message: '请设置审核评分' },
    { type: 'number', min: 0, max: 100, message: '评分范围为0-100' }
  ]
}

// 评分标记
const scoreMarks = {
  0: '0',
  60: '60',
  80: '80',
  90: '90',
  100: '100'
}

// 计算属性
const criticalDefectsCount = computed(() => 
  formData.value.defects.filter(d => d.severity === 'critical').length
)

const totalScoreDeduction = computed(() => 
  formData.value.defects.reduce((sum, d) => sum + (d.score_deduction || 0), 0)
)

// 方法
const getLevelTitle = (level: AuditLevel): string => {
  const titles = {
    department: '科室级',
    hospital: '院级',
    expert: '专家级'
  }
  return titles[level]
}

const getStatusColor = (status?: string): string => {
  const colors = {
    draft: 'default',
    submitted: 'processing',
    approved: 'success',
    rejected: 'error',
    modified: 'warning'
  }
  return colors[status || 'draft'] || 'default'
}

const getStatusText = (status?: string): string => {
  const texts = {
    draft: '草稿',
    submitted: '已提交',
    approved: '已通过',
    rejected: '已拒绝',
    modified: '已修改'
  }
  return texts[status || 'draft'] || '未知'
}

const getScoreLevel = (score: number): string => {
  if (score >= 90) return '优秀'
  if (score >= 80) return '良好'
  if (score >= 70) return '合格'
  if (score >= 60) return '基本合格'
  return '不合格'
}

const handleScoreChange = (value: number) => {
  // 根据评分自动调整结论
  if (value >= 90) {
    formData.value.audit_conclusion = '病历质量优秀，符合规范要求。'
  } else if (value >= 80) {
    formData.value.audit_conclusion = '病历质量良好，存在少量问题。'
  } else if (value >= 70) {
    formData.value.audit_conclusion = '病历质量合格，需要改进。'
  } else {
    formData.value.audit_conclusion = '病历质量不合格，存在严重问题。'
  }
}

const handleSave = async () => {
  try {
    saving.value = true
    
    const formValid = await auditFormRef.value?.validate()
    if (!formValid) return
    
    emit('update', {
      audit_score: formData.value.audit_score,
      audit_conclusion: formData.value.audit_conclusion,
      defects: formData.value.defects
    })
    
  } catch (error: unknown) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleSubmit = async () => {
  try {
    submitting.value = true
    
    if (!props.auditResult?.id) {
      message.error('请先保存审核结果')
      return
    }
    
    emit('submit', props.auditResult.id)
    
  } catch (error) {
    message.error('提交失败')
  } finally {
    submitting.value = false
  }
}

const triggerAIAssistance = async () => {
  try {
    aiAnalyzing.value = true
    
    // 调用AI辅助缺陷识别
    // const suggestions = await auditResultService.getAIDefectSuggestions(...)
    // aiSuggestions.value = suggestions
    
    // 模拟AI建议
    aiSuggestions.value = [
      {
        suggested_type: '内容缺失',
        suggested_category: '完整性',
        suggested_severity: 'major',
        suggested_title: '缺少出院小结',
        suggested_description: '患者病历中未发现出院小结文档',
        confidence: 85,
        supporting_evidence: ['文档列表检查'],
        rectification_suggestions: ['请补充完整的出院小结']
      }
    ]
    
    aiSuggestionsVisible.value = true
    
  } catch (error) {
    message.error('AI分析失败')
  } finally {
    aiAnalyzing.value = false
  }
}

const applyAISuggestions = () => {
  formData.value.defects.push(...selectedSuggestions.value.map(s => ({
    defect_type: s.suggested_type,
    defect_category: s.suggested_category,
    severity: s.suggested_severity,
    title: s.suggested_title,
    description: s.suggested_description,
    ai_assisted: true,
    ai_confidence: s.confidence,
    score_deduction: s.suggested_severity === 'critical' ? 20 : 
                    s.suggested_severity === 'major' ? 10 : 5
  })))
  
  aiSuggestionsVisible.value = false
  message.success(`已添加 ${selectedSuggestions.value.length} 个AI建议的缺陷`)
}

const addManualDefect = () => {
  addDefectVisible.value = true
}

const confirmAddDefect = async () => {
  try {
    const defectData = await defectFormRef.value?.validateAndGetData()
    if (defectData) {
      formData.value.defects.push(defectData)
      addDefectVisible.value = false
      message.success('缺陷添加成功')
    }
  } catch (error) {
    message.error('请完善缺陷信息')
  }
}

const handleDefectUpdate = (index: number, defectData: Partial<QCDefect>) => {
  formData.value.defects[index] = { ...formData.value.defects[index], ...defectData }
}

const handleDefectRemove = (index: number) => {
  formData.value.defects.splice(index, 1)
  message.success('缺陷已删除')
}

const modifyLowerResult = (result: QCAuditResult) => {
  emit('modify-lower', result)
}

const showModifyLowerModal = () => {
  // 显示修改下级结果的选择
}

const handleAISelectionChange = (selected: AIDefectSuggestion[]) => {
  selectedSuggestions.value = selected
}

const handleNewDefectChange = (data) => {
  // 处理新缺陷数据变化
}

const handleFormSubmit = () => {
  handleSave()
}

// 监听审核结果变化
watch(() => props.auditResult, (newResult) => {
  if (newResult) {
    formData.value = {
      audit_score: newResult.audit_score,
      audit_conclusion: newResult.audit_conclusion || '',
      defects: newResult.defects_found || []
    }
  }
}, { immediate: true, deep: true })

onMounted(() => {
  // 初始化
})
</script>

<style scoped>
.audit-result-panel {
  background: white;
  border-radius: 8px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.panel-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: 600;
}

.reviewer-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
  font-size: 14px;
  margin-top: 8px;
}

.duration {
  color: #999;
}

.audit-form-card {
  margin-bottom: 16px;
}

.score-display {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.score-value {
  font-size: 24px;
  font-weight: bold;
  color: #1890ff;
}

.score-level {
  font-size: 14px;
  color: #666;
}

.defect-section {
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 500;
}

.defects-list {
  min-height: 100px;
}

.defect-item {
  margin-bottom: 12px;
}

.defect-item:last-child {
  margin-bottom: 0;
}

.stats-card,
.lower-results-card {
  margin-bottom: 16px;
}

.lower-result-item {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 4px;
  margin-bottom: 8px;
}

.lower-result-item:last-child {
  margin-bottom: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.level-name {
  font-weight: 500;
}

.result-score {
  color: #1890ff;
  font-weight: bold;
}

.result-summary {
  color: #666;
  font-size: 12px;
  line-height: 1.4;
}
</style>
