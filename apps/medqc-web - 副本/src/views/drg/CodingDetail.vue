<template>
  <div class="coding-detail">
    <a-page-header
      :title="`编码详情`"
      sub-title="DRG/DIP 智能编码工作台"
      style="padding: 16px 32px; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,0.03);"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-space>
          <a-button
            :loading="validating"
            @click="handleValidate"
          >
            校验编码
          </a-button>
          <a-button
            type="primary"
            :loading="saving"
            @click="handleSave"
          >
            保存并提交
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-spin :spinning="loading">
        <a-row
          :gutter="24"
          style="height: calc(100vh - 120px)"
        >
          <!-- 左侧：患者病案信息与历史 (30%) -->
          <a-col
            :span="8"
            style="height: 100%"
          >
            <a-card
              title="患者病案信息与历史"
              :bordered="false"
              class="full-height-card patient-card"
            >
              <div class="patient-info-section">
                <div class="info-row">
                  <span class="label">患者姓名:</span>
                  <span class="value">{{ caseFrontPage?.patient_name }}</span>
                </div>
                <div class="info-row">
                  <span class="label">性别/年龄:</span>
                  <span class="value">{{ getGenderText(caseFrontPage?.patient_gender) }}/{{ caseFrontPage?.patient_age }}</span>
                </div>
                <div class="info-row">
                  <span class="label">住院号:</span>
                  <span class="value">{{ caseFrontPage?.admission_id }}</span>
                </div>
                <div class="info-row">
                  <span class="label">入院日期:</span>
                  <span class="value">2024-05-10</span> <!-- Mock Data as per request/image -->
                </div>
                <div class="info-row">
                  <span class="label">总费用:</span>
                  <span class="value">{{ formatCurrency(caseFrontPage?.total_cost) }}</span>
                </div>
                <div class="info-row">
                  <span class="label">出院日期:</span>
                  <span class="value">2024-05-20</span> <!-- Mock Data -->
                </div>
              </div>

              <a-divider style="margin: 16px 0" />

              <div class="history-summary">
                <div class="section-title">
                  病史摘要
                </div>
                <ul class="history-list">
                  <li>既往高血压史5年，2型糖尿病史3年，此次因胸痛入院。</li>
                  <li>既往冠心病史曾植入支架入院胸痛，化验均为胸痛入院。</li>
                  <li>此次高血压史伴冠脉病变，透析器中及面容于胸。</li>
                  <li>入院口烟入园，营养列性上控制火。</li>
                </ul>
              </div>

              <div class="card-bottom-action">
                <a-button
                  block
                  size="large"
                >
                  查看完整病历
                </a-button>
              </div>
            </a-card>
          </a-col>

          <!-- 右侧：DRG 编码修正与 AI 分析 (70%) -->
          <a-col
            :span="16"
            style="height: 100%; overflow-y: auto; padding-right: 8px;"
          >
            <div class="right-panel-header">
              DRG 编码修正与 AI 分析
            </div>

            <!-- 主诊断 -->
            <a-card
              :bordered="false"
              class="premium-card mb-4"
              :body-style="{ padding: '0' }"
            >
              <div class="section-header">
                <span>主要诊断 (Primary Diagnosis)</span>
                <span class="ai-confidence-label">AI 置信分度</span>
              </div>
              <div class="diagnosis-row primary-row">
                <div class="code-content">
                  <span class="code-label">ICD-10:</span>
                  <ICDCodeSearch
                    v-if="caseFrontPage"
                    v-model:value="caseFrontPage!.primary_diagnosis_code"
                    v-model:name="caseFrontPage!.primary_diagnosis_name"
                    category="diagnosis"
                    placeholder="搜索诊断编码"
                    variant="borderless"
                    class="custom-input"
                  />
                </div>
                <div class="actions">
                  <a-tag
                    color="#10b981"
                    class="confidence-tag"
                  >
                    95%
                  </a-tag>
                  <a-space
                    size="small"
                    class="action-links"
                  >
                    <a><EditOutlined /> 编辑</a>
                    <a><DeleteOutlined /> 删除</a>
                    <a><FileTextOutlined /> AI详情</a>
                  </a-space>
                </div>
              </div>
            </a-card>

            <!-- 次诊断 -->
            <a-card
              :bordered="false"
              class="premium-card mb-4"
              :body-style="{ padding: '0' }"
            >
              <div class="section-header">
                <span>次要诊断 (Secondary Diagnoses)</span>
                <span class="ai-confidence-label">AI 置信分度</span>
              </div>
               
              <div class="diagnosis-list">
                <div
                  v-for="(item, index) in secondaryDiagnoses"
                  :key="index"
                  class="diagnosis-row secondary-row"
                >
                  <div class="row-index">
                    {{ index + 1 }}.
                  </div>
                  <div class="code-content">
                    <ICDCodeSearch
                      v-model:value="item.code"
                      v-model:name="item.name"
                      category="diagnosis"
                      variant="borderless"
                      class="custom-input"
                    />
                  </div>
                  <div class="actions">
                    <a-tag
                      :color="getConfidenceColor(index)"
                      class="confidence-tag"
                    >
                      {{ getConfidenceScore(index) }}%
                    </a-tag>
                    <a-space
                      size="small"
                      class="action-links"
                    >
                      <a><EditOutlined /> 编辑</a>
                      <a
                        class="danger-text"
                        @click="removeSecondaryDiagnosis(index)"
                      ><DeleteOutlined /> 删除</a>
                      <a><FileTextOutlined /> AI详情</a>
                    </a-space>
                  </div>
                </div>
              </div>

              <div class="add-btn-wrapper">
                <a-button
                  type="dashed"
                  block
                  class="add-btn"
                  @click="addSecondaryDiagnosis"
                >
                  添加次要诊断
                </a-button>
              </div>
            </a-card>

            <!-- AI 验证与 DRG 分组结果 -->
            <a-card
              :bordered="false"
              class="premium-card"
              :body-style="{ padding: '24px' }"
            >
              <div class="section-header-simple">
                AI 验证与 DRG 分组结果
              </div>
              
              <div class="drg-result-banner">
                <div class="drg-info">
                  <span class="label">建议 DRG 组:</span>
                  <span class="value">F01A 冠状动脉相关手术</span>
                </div>
                <div class="drg-metrics">
                  <span class="metric">预期权重: <strong>2.35</strong></span>
                  <span class="metric">预计报销: <strong>¥25,000</strong></span>
                </div>
              </div>

              <div class="ai-analysis-box">
                <div class="box-title">
                  AI 分析理由
                </div>
                <div class="box-content">
                  主诊断与手术操作（冠脉支架植入术）高度匹配，次要并发症对分组影响显著。建议确认当前编码。
                </div>
              </div>

              <div class="footer-actions">
                <a-button
                  type="primary"
                  size="large"
                  class="submit-btn"
                  @click="handleSave"
                >
                  保存并提交
                </a-button>
                <a-button
                  size="large"
                  @click="handleValidate"
                >
                  重新分析
                </a-button>
              </div>
            </a-card>
          </a-col>
        </a-row>
      </a-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  SaveOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  FileTextOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'
import { getGenderText, formatCurrency } from '@/utils/drg'
import type { CaseFrontPage, DiagnosisItem, ProcedureItem } from '@/types/drg'

const route = useRoute()
const router = useRouter()
const admissionId = route.params.admissionId as string

// State
const caseFrontPage = ref<CaseFrontPage>()
const secondaryDiagnoses = ref<DiagnosisItem[]>([])
const loading = ref(true)
const saving = ref(false)
const validating = ref(false)

// Mock Confidence Data
const getConfidenceScore = (index: number) => {
  const scores = [92, 88, 90, 85, 95];
  return scores[index % scores.length];
}

const getConfidenceColor = (index: number) => {
  const score = getConfidenceScore(index);
  if (score >= 90) return '#10b981'; // Green
  if (score >= 80) return '#f59e0b'; // Orange
  return '#ef4444'; // Red
}

// Methods
const loadCaseFrontPage = async () => {
  loading.value = true
  try {
    const data = await drgApi.getCaseFrontPageDetail(admissionId)
    caseFrontPage.value = data
    secondaryDiagnoses.value = data.secondary_diagnoses || []
  } catch (error) {
    message.error('加载病案详情失败')
  } finally {
    loading.value = false
  }
}

const addSecondaryDiagnosis = () => {
  secondaryDiagnoses.value.push({
    code: '',
    name: '',
    sequence: secondaryDiagnoses.value.length + 1,
    is_complication: false
  })
}

const removeSecondaryDiagnosis = (index: number) => {
  secondaryDiagnoses.value.splice(index, 1)
}

const handleSave = async () => {
  message.success('保存成功')
}

const handleValidate = async () => {
  message.loading('正在进行 AI 分析...', 1)
}

onMounted(() => {
  loadCaseFrontPage()
})
</script>

<style scoped lang="scss">
.coding-detail {
  min-height: 100vh;
  background-color: #f1f5f9;
  display: flex;
  flex-direction: column;
}

.content-wrapper {
  flex: 1;
  padding: 24px 32px;
}

/* Mixins */
@mixin premium-card-style {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
}

.premium-card {
  @include premium-card-style;
}

.full-height-card {
  height: 100%;
  @include premium-card-style;
  display: flex;
  flex-direction: column;
  
  :deep(.ant-card-body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
  }
  
  :deep(.ant-card-head) {
    padding: 0 20px;
    min-height: 50px;
    border-bottom: 1px solid #e2e8f0;
    
    .ant-card-head-title {
      font-weight: 700;
      font-size: 15px;
      color: #1e293b;
    }
  }
}

.mb-4 {
  margin-bottom: 16px; 
}

/* Patient Card Styles */
.patient-info-section {
  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    font-size: 14px;
    border-bottom: 1px dashed #f1f5f9;
    
    &:last-child {
      border-bottom: none;
    }
    
    .label {
      color: #64748b;
      font-weight: 400;
    }
    
    .value {
      color: #0f172a;
      font-weight: 600;
      text-align: right;
    }
  }
}

.history-summary {
  flex: 1;
  margin-top: 8px;
  
  .section-title {
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 12px;
    color: #1e293b;
  }
  
  .history-list {
    padding-left: 18px;
    color: #475569;
    font-size: 13px;
    line-height: 1.7;
    margin: 0;
    
    li {
      margin-bottom: 6px;
      &::marker {
        color: #94a3b8;
      }
    }
  }
}

.card-bottom-action {
  margin-top: auto;
  padding-top: 16px;
}

/* Right Panel Styles */
.right-panel-header {
  font-size: 18px;
  font-weight: 800;
  color: #1e293b;
  margin-bottom: 20px;
}

/* Diagnosis Section Styles */
.section-header {
  padding: 14px 20px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 14px;
  color: #334155;
  
  .ai-confidence-label {
    font-size: 12px;
    color: #94a3b8;
    font-weight: 400;
  }
}

.diagnosis-row {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #f1f5f9;
  transition: background 0.15s;
  
  &:hover {
    background: #f8fafc;
  }
  
  &:last-child {
    border-bottom: none;
  }
  
  .code-content {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0; // Allow shrinking
    
    .code-label {
      color: #64748b;
      font-weight: 500;
      font-size: 13px;
      flex-shrink: 0;
    }
    
    // Style the ICD search component input
    :deep(.ant-select) {
      flex: 1;
      max-width: 400px;
    }
    
    :deep(.ant-select-selector) {
      padding: 0 !important;
      border: none !important;
      background: transparent !important;
      
      .ant-select-selection-search-input,
      .ant-select-selection-item {
        font-size: 14px !important;
        font-weight: 600;
        color: #0f172a !important;
      }
    }
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
    margin-left: 16px;
    
    .confidence-tag {
      border: none;
      font-weight: 600;
      font-size: 12px;
      padding: 2px 10px;
      border-radius: 4px;
    }
    
    .action-links {
      :deep(.ant-space-item) {
        a {
          color: #6366f1;
          font-size: 12px;
          display: inline-flex;
          align-items: center;
          gap: 4px;
          
          &:hover { 
            color: #4f46e5; 
            text-decoration: underline;
          }
        }
        
        .danger-text {
          color: #ef4444;
          &:hover { color: #dc2626; }
        }
      }
    }
  }
}

.diagnosis-list .secondary-row {
  .row-index {
    color: #94a3b8;
    font-weight: 500;
    font-size: 13px;
    margin-right: 8px;
    width: 20px;
    flex-shrink: 0;
  }
}

.add-btn-wrapper {
  padding: 12px 20px;
  border-top: 1px solid #f1f5f9;
  
  .add-btn {
    border-radius: 4px;
    color: #64748b;
    border-color: #cbd5e1;
    height: 36px;
    font-size: 13px;
    
    &:hover {
      color: #6366f1;
      border-color: #6366f1;
    }
  }
}

/* AI Analysis Result Styles */
.section-header-simple {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 16px;
  color: #1e293b;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.drg-result-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
  
  .drg-info {
    font-size: 15px;
    
    .label {
      color: #64748b;
      font-weight: 400;
    }
    
    .value {
      font-weight: 700;
      color: #0f172a;
    }
  }
  
  .drg-metrics {
    display: flex;
    gap: 20px;
    font-size: 13px;
    color: #64748b;
    
    strong {
      color: #0f172a;
      font-weight: 700;
    }
  }
}

.ai-analysis-box {
  background: #eff6ff;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  padding: 14px 16px;
  margin-bottom: 20px;
  
  .box-title {
    color: #1d4ed8;
    font-weight: 600;
    font-size: 13px;
    margin-bottom: 6px;
  }
  
  .box-content {
    color: #334155;
    font-size: 13px;
    line-height: 1.6;
  }
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  
  .submit-btn {
    background: #1d4ed8;
    border-color: #1d4ed8;
    font-weight: 600;
    &:hover { 
      background: #1e40af; 
      border-color: #1e40af;
    }
  }
}
</style>
