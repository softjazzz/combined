<template>
  <div class="coding-advisor-container">
    <!-- Header / Action Bar -->
    <div class="advisor-header">
      <div class="title-section">
        <h3>
          <span class="icon">🤖</span> 编码完整性顾问
        </h3>
        <p class="subtitle">基于 AI 分析病历原文，发现潜在的编码遗漏与优化机会</p>
      </div>
      <div class="action-section">
        <button 
          @click="startAnalysis" 
          :disabled="loading"
          class="btn-analyze"
          :class="{ 'analyzing': loading }"
        >
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '智能分析中...' : '开始全面分析' }}
        </button>
      </div>
    </div>

    <!-- Content Area -->
    <div v-if="result" class="advisor-content">
      
      <!-- Layer A: Clinical Entities -->
      <div class="section-panel entities-panel">
        <div class="panel-header">
          <h4>临床实体抽取 (Layer A)</h4>
          <span class="badge">{{ totalEntities }} 个实体</span>
        </div>
        <div class="entities-grid">
          <!-- Diagnoses -->
          <div class="entity-group" v-if="result.structure_extraction.explicit_diagnoses.length">
            <h5 class="group-title">明确诊断</h5>
            <div class="tags">
              <div 
                v-for="(item, idx) in result.structure_extraction.explicit_diagnoses" 
                :key="idx"
                class="entity-tag diagnosis"
                :title="item.evidence.text"
              >
                {{ item.text }}
              </div>
            </div>
          </div>
          
          <!-- Indicators -->
          <div class="entity-group" v-if="result.structure_extraction.clinical_indicators.length">
            <h5 class="group-title">异常指标</h5>
            <div class="tags">
              <div 
                v-for="(item, idx) in result.structure_extraction.clinical_indicators" 
                :key="idx"
                class="entity-tag indicator"
                :title="item.evidence.text"
              >
                {{ item.text }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Layer B: Coding Suggestions -->
      <div class="section-panel suggestions-panel">
        <div class="panel-header">
          <h4>优化建议 (Layer B)</h4>
          <span class="badge warning">{{ result.suggestions.length }} 条建议</span>
        </div>
        
        <div class="suggestions-list">
          <div 
            v-for="suggestion in result.suggestions" 
            :key="suggestion.id" 
            class="suggestion-card"
          >
            <!-- Card Header -->
            <div class="card-header">
              <div class="suggestion-type">
                <span class="type-icon" v-if="suggestion.action === 'add_code'">➕</span>
                <span class="type-label">{{ getActionLabel(suggestion.action) }}</span>
              </div>
              <div class="risk-badge" :class="suggestion.risk_level">
                {{ getRiskLabel(suggestion.risk_level) }}
              </div>
            </div>

            <!-- Card Body -->
            <div class="card-body">
              <div class="target-info">
                <span class="label">建议编码:</span>
                <span class="code">{{ suggestion.target_code || '待定' }}</span>
                <span class="name">{{ suggestion.target_name }}</span>
              </div>
              
              <div class="evidence-box">
                <div class="evidence-title">依据:</div>
                <ul>
                  <li v-for="(point, pIdx) in suggestion.justification_points" :key="pIdx">
                    {{ point }}
                  </li>
                </ul>
              </div>
            </div>

            <!-- Card Footer / Action -->
            <div class="card-footer">
              <div class="confidence">
                 AI 置信度: {{ (suggestion.confidence * 100).toFixed(0) }}%
              </div>
              <button class="btn-accept" @click="handleAccept(suggestion)">采纳建议</button>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Empty State -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon">📊</div>
      <p>暂无分析结果，请点击上方按钮开始分析</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { analyzeCodingCompleteness } from '@/api/advisor'
import type { CodingCompletenessResponse } from '@/types/advisor'

const props = defineProps<{
  admissionId?: string
  currentData: any
}>()

const emit = defineEmits<{
  (e: 'accept', suggestion: any): void
}>()

const loading = ref(false)
const result = ref<CodingCompletenessResponse | null>(null)
const medicalRecordText = ref('')

const totalEntities = computed(() => {
  if (!result.value) return 0
  const ex = result.value.structure_extraction
  return ex.explicit_diagnoses.length + ex.clinical_indicators.length + ex.procedure_mentions.length
})

async function fetchMedicalRecord() {
  if (!props.admissionId) return
  // Mock 数据：为了演示一致性，使用与 MedicalRecordViewer 相同的模拟数据
  // 在实际生产中，应调用 api/medical-records.ts
  const mockNote = `
    入院记录
    主诉：反复胸闷、气促2年，加重1周。
    现病史：患者2年前无明显诱因出现胸闷、气促，活动后加重，休息可缓解。1周前受凉后上述症状加重，伴咳嗽、咳痰，为白色泡沫痰，夜间阵发性呼吸困难，遂来我院就诊。
    既往史：有"高血压病"史10年，最高血压180/100mmHg，长期口服降压药治疗，血压控制尚可。有"2型糖尿病"史5年。
    体格检查：T 36.5℃，P 88次/分，R 20次/分，BP 130/80mmHg。双肺呼吸音粗，双下肺可闻及湿性啰音。心率88次/分，律齐。
    辅助检查：心电图示：窦性心律，完全性左束支传导阻滞，ST-T改变。心脏彩超示：左室增大，室壁运动减弱，EF 35%。肌酐 450umol/L。
    初步诊断：1. 慢性心力衰竭 急性加重 心功能IV级；2. 原发性高血压 3级 很高危；3. 2型糖尿病。
  `
  medicalRecordText.value = mockNote
}

async function startAnalysis() {
  if (!props.admissionId) {
    alert('缺少 Admission ID')
    return
  }
  
  loading.value = true
  try {
    if (!medicalRecordText.value) {
      await fetchMedicalRecord()
    }
    
    result.value = await analyzeCodingCompleteness({
      medical_record: medicalRecordText.value,
      current_data: props.currentData
    })
  } catch (error) {
    console.error(error)
    alert('分析失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleAccept(suggestion: any) {
  emit('accept', suggestion)
}

function getActionLabel(action: string) {
  const map: Record<string, string> = {
    'add_code': '补充漏编',
    'code_refinement': '细化编码',
    'needs_doc_update': '需文档澄清'
  }
  return map[action] || action
}

function getRiskLabel(level: string) {
  const map: Record<string, string> = {
    'high': '高风险',
    'medium': '中风险',
    'low': '低风险'
  }
  return map[level] || level
}
</script>

<style scoped>
.coding-advisor-container {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  padding: 24px;
  font-family: 'Inter', sans-serif;
}

.advisor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eee;
}

.title-section h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1a1a1a;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.subtitle {
  color: #666;
  font-size: 0.875rem;
  margin-top: 4px;
}

.btn-analyze {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-analyze:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}

.btn-analyze:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.section-panel {
  background: #f8fafc;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
  border: 1px solid #e2e8f0;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.panel-header h4 {
  margin: 0;
  font-size: 1rem;
  color: #334155;
}

.badge {
  background: #e2e8f0;
  color: #475569;
  padding: 2px 8px;
  border-radius: 99px;
  font-size: 0.75rem;
}

.badge.warning {
  background: #fef3c7;
  color: #d97706;
}

.entities-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.group-title {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0 0 8px 0;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.875rem;
  border: 1px solid transparent;
}

.entity-tag.diagnosis {
  background: #eff6ff;
  color: #3b82f6;
  border-color: #dbeafe;
}

.entity-tag.indicator {
  background: #f0fdf4;
  color: #22c55e;
  border-color: #dcfce7;
}

.suggestion-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.2s ease;
}

.suggestion-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.suggestion-type {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #0f172a;
  font-weight: 500;
}

.risk-badge {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.risk-badge.high { background: #fee2e2; color: #ef4444; }
.risk-badge.medium { background: #ffedd5; color: #f97316; }
.risk-badge.low { background: #f1f5f9; color: #64748b; }

.target-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.target-info .code {
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 600;
}

.evidence-box {
  background: #fffbeb;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.875rem;
  color: #92400e;
}

.evidence-box ul {
  margin: 4px 0 0 0;
  padding-left: 20px;
}

.card-footer {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.confidence {
  font-size: 0.75rem;
  color: #94a3b8;
}

.btn-accept {
  background: #10b981;
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.875rem;
  cursor: pointer;
}

.btn-accept:hover {
  background: #059669;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #94a3b8;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 16px;
}

/* Spinner Animation */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #ffffff;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
