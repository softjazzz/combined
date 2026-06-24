<template>
  <div class="coding-advisor-container">
    <!-- Header / Action Bar -->
    <div class="advisor-header">
      <div class="title-section">
        <h3>
          <span class="icon">🤖</span> 编码完整性顾问
        </h3>
        <p class="subtitle">
          基于 AI 分析病历原文，发现潜在的编码遗漏与优化机会
        </p>
      </div>
      <div class="action-section">
        <button 
          :disabled="loading" 
          class="btn-analyze"
          :class="{ 'analyzing': loading }"
          @click="startAnalysis"
        >
          <span
            v-if="loading"
            class="spinner"
          />
          {{ loading ? '智能分析中...' : '开始全面分析' }}
        </button>
      </div>
    </div>

    <!-- Content Area -->
    <div
      v-if="result"
      class="advisor-content"
    >
      <!-- Layer A: Clinical Entities -->
      <div class="section-panel entities-panel">
        <div class="panel-header">
          <h4>临床实体抽取 (Layer A)</h4>
          <span class="badge">{{ totalEntities }} 个实体</span>
        </div>
        <div class="entities-grid">
          <!-- Diagnoses -->
          <div
            v-if="result.structure_extraction.explicit_diagnoses.length"
            class="entity-group"
          >
            <h5 class="group-title">
              明确诊断
            </h5>
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
          <div
            v-if="result.structure_extraction.clinical_indicators.length"
            class="entity-group"
          >
            <h5 class="group-title">
              异常指标
            </h5>
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
                <span
                  v-if="suggestion.action === 'add_code'"
                  class="type-icon"
                >➕</span>
                <span class="type-label">{{ getActionLabel(suggestion.action) }}</span>
              </div>
              <div
                class="risk-badge"
                :class="suggestion.risk_level"
              >
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
                <div class="evidence-title">
                  依据:
                </div>
                <ul>
                  <li
                    v-for="(point, pIdx) in suggestion.justification_points"
                    :key="pIdx"
                  >
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
              <button
                class="btn-accept"
                @click="handleAccept(suggestion)"
              >
                采纳建议
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!loading"
      class="empty-state"
    >
      <div class="empty-icon">
        📊
      </div>
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
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
  padding: 0;
  font-family: 'Inter', sans-serif;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,0.02);
}

.advisor-header {
  background: linear-gradient(135deg, #f8fafc 0%, #fff 100%);
  padding: 20px 24px;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title-section h3 {
  font-size: 1.1rem;
  font-weight: 700;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
}

.title-section h3 .icon {
  font-size: 1.4rem;
}

.subtitle {
  color: #64748b;
  font-size: 0.8rem;
  margin-top: 4px;
  line-height: 1.4;
}

.action-section {
  flex-shrink: 0;
}

.btn-analyze {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-analyze:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
}

.btn-analyze:disabled {
  opacity: 0.8;
  cursor: default;
  transform: none;
  background: #94a3b8;
  box-shadow: none;
}

.advisor-content {
  padding: 20px 24px;
  background: #fcfcfd;
}

.section-panel {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  border: 1px solid #f1f5f9;
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  border-bottom: 1px dashed #f1f5f9;
  padding-bottom: 12px;
}

.panel-header h4 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #334155;
  display: flex;
  align-items: center;
}

.panel-header h4::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: #3b82f6;
  border-radius: 2px;
  margin-right: 8px;
}

.suggestions-panel .panel-header h4::before {
  background: #f59e0b;
}

.badge {
  background: #f1f5f9;
  color: #64748b;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge.warning {
  background: #fffbeb;
  color: #d97706;
}

.entities-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.group-title {
  font-size: 0.8rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 8px 0;
  font-weight: 600;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.entity-tag {
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  transition: transform 0.2s;
}

.entity-tag:hover {
  transform: translateY(-1px);
}

.entity-tag.diagnosis {
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #dbeafe;
}

.entity-tag.indicator {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #dcfce7;
}

.suggestion-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #adadad; /* Default level color */
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  transition: all 0.2s ease;
  position: relative;
}

.suggestion-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

/* Dynamic Left Border based on Risk */
.suggestion-card:has(.risk-badge.high) { border-left-color: #ef4444; }
.suggestion-card:has(.risk-badge.medium) { border-left-color: #f97316; }
.suggestion-card:has(.risk-badge.low) { border-left-color: #64748b; }

.card-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}

.suggestion-type {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
  font-weight: 700;
  font-size: 1rem;
}

.risk-badge {
  font-size: 0.75rem;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
  text-transform: uppercase;
}

.risk-badge.high { background: #fee2e2; color: #b91c1c; }
.risk-badge.medium { background: #ffedd5; color: #c2410c; }
.risk-badge.low { background: #f1f5f9; color: #475569; }

.target-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  background: #f8fafc;
  padding: 10px;
  border-radius: 8px;
}

.target-info .code {
  background: #fff;
  border: 1px solid #e2e8f0;
  padding: 4px 8px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #334155;
  font-size: 0.9rem;
}

.target-info .name {
  font-weight: 600;
  color: #1e293b;
}

.evidence-box {
  background: #fffbeb;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  color: #92400e;
  border: 1px solid #fcd34d;
}

.evidence-box ul {
  margin: 6px 0 0 0;
  padding-left: 20px;
}

.evidence-box ul li {
  margin-bottom: 4px;
}

.card-footer {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.confidence {
  font-size: 0.8rem;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 8px;
  border-radius: 4px;
}

.btn-accept {
  background: #10b981;
  color: white;
  border: none;
  padding: 8px 24px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.2);
  transition: all 0.2s;
}

.btn-accept:hover {
  background: #059669;
  box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3);
  transform: translateY(-1px);
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #94a3b8;
  background: #fcfcfd;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 20px;
  opacity: 0.8;
  filter: grayscale(100%);
}

.empty-state p {
  font-size: 1rem;
  max-width: 240px;
  margin: 0 auto;
  line-height: 1.6;
}

/* Spinner Animation */
.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(255,255,255,0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
