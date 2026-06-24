<template>
  <div class="grouping-predict">
    <a-page-header
      title="DRG 分组预测"
      sub-title="DRG 入组预测和模拟试算"
      class="page-header"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-button
          type="primary"
          :loading="predicting"
          :disabled="!canPredict"
          class="predict-btn"
          @click="handlePredict"
        >
          <template #icon>
            <ThunderboltOutlined />
          </template>
          开始预测
        </a-button>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-row :gutter="24">
        <!-- 左侧：模拟录入区 -->
        <a-col :span="14">
          <div class="input-card">
            <div class="card-header">
              <span class="card-title">病案信息录入</span>
            </div>
            
            <div class="card-body">
              <!-- 快速导入 -->
              <div class="quick-import">
                <span class="import-label">快速导入:</span>
                <a-select
                  v-model:value="selectedAdmissionId"
                  show-search
                  placeholder="从现有病案导入数据..."
                  class="import-select"
                  :options="caseOptions"
                  @change="handleImportCase"
                />
              </div>
              
              <!-- 分组引擎选择 -->
              <div class="engine-selector">
                <span class="engine-label">分组引擎:</span>
                <a-radio-group
                  v-model:value="engineType"
                  button-style="solid"
                  class="engine-radio-group"
                >
                  <a-radio-button value="DRG">
                    OpenDRG
                  </a-radio-button>
                  <a-radio-button value="DIP">
                    DIP (按病种分值)
                  </a-radio-button>
                </a-radio-group>
              </div>

              <a-divider class="section-divider" />
              
              <!-- 主诊断 & 费用 -->
              <a-row :gutter="16">
                <a-col :span="14">
                  <div class="form-group">
                    <label class="form-label required">主诊断</label>
                    <ICDCodeSearch
                      v-model:value="formData.primary_diagnosis_code"
                      v-model:name="formData.primary_diagnosis_name"
                      category="diagnosis"
                      class="icd-search"
                    />
                  </div>
                </a-col>
                <a-col :span="10">
                  <div class="form-group">
                    <label class="form-label">总费用 (预估)</label>
                    <a-input-number
                      v-model:value="formData.total_cost"
                      class="cost-input"
                      :formatter="(value: string | number | undefined) => `¥ ${value ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')"
                      :parser="(value: string | undefined) => (value || '').replace(/\¥\s?|(,*)/g, '')"
                    />
                  </div>
                </a-col>
              </a-row>

              <!-- 次诊断 -->
              <div class="section-block">
                <div class="section-header">
                  <span class="section-title">次诊断</span>
                  <a-button
                    type="link"
                    size="small"
                    class="add-btn"
                    @click="addSecondaryDiagnosis"
                  >
                    <PlusOutlined /> 添加
                  </a-button>
                </div>
                <div
                  v-if="formData.secondary_diagnoses.length === 0"
                  class="empty-hint"
                >
                  暂无次诊断，点击"添加"按钮添加
                </div>
                <div
                  v-for="(item, index) in formData.secondary_diagnoses"
                  :key="index"
                  class="dynamic-item"
                >
                  <ICDCodeSearch
                    v-model:value="item.code"
                    v-model:name="item.name"
                    category="diagnosis"
                    placeholder="次诊断"
                    class="flex-input"
                  />
                  <a-checkbox
                    v-model:checked="item.is_complication"
                    class="complication-check"
                  >
                    并发症
                  </a-checkbox>
                  <a-button
                    type="text"
                    danger
                    size="small"
                    class="delete-btn"
                    @click="removeSecondaryDiagnosis(index)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>

              <!-- 手术操作 -->
              <div class="section-block">
                <div class="section-header">
                  <span class="section-title">手术操作</span>
                  <a-button
                    type="link"
                    size="small"
                    class="add-btn"
                    @click="addProcedure"
                  >
                    <PlusOutlined /> 添加
                  </a-button>
                </div>
                <div
                  v-if="formData.procedures.length === 0"
                  class="empty-hint"
                >
                  暂无手术操作
                </div>
                <div
                  v-for="(item, index) in formData.procedures"
                  :key="index"
                  class="dynamic-item"
                >
                  <ICDCodeSearch
                    v-model:value="item.code"
                    v-model:name="item.name"
                    category="procedure"
                    placeholder="手术操作"
                    class="flex-input"
                  />
                  <a-button
                    type="text"
                    danger
                    size="small"
                    class="delete-btn"
                    @click="removeProcedure(index)"
                  >
                    <DeleteOutlined />
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </a-col>

        <!-- 右侧：预测结果 -->
        <a-col :span="10">
          <a-spin :spinning="predicting">
            <DRGResultCard
              v-if="groupingResult"
              :result="groupingResult"
              :engine-type="engineType"
              style="margin-bottom: 16px"
            />
            
            <!-- 结果占位符 -->
            <div
              v-else
              class="empty-result-card"
            >
              <div class="empty-icon">
                <FileSearchOutlined />
              </div>
              <div class="empty-text">
                点击"开始预测"获取分组结果
              </div>
            </div>

            <!-- 盈亏分析卡片 -->
            <div
              v-if="groupingResult"
              class="profit-card"
            >
              <div class="card-header">
                <span class="card-title">盈亏分析模拟</span>
              </div>
              <div class="card-body">
                <div class="profit-row">
                  <span class="profit-label">预估收入 (基准支付)</span>
                  <span class="profit-value">¥{{ (groupingResult.baseline_payment ?? 0).toLocaleString() }}</span>
                </div>
                <div class="profit-row">
                  <span class="profit-label">预估成本 (总费用)</span>
                  <span class="profit-value">¥{{ (formData.total_cost || 0).toLocaleString() }}</span>
                </div>
                <div class="profit-divider" />
                <div class="profit-row total">
                  <span class="profit-label">预计盈亏</span>
                  <span
                    class="profit-value"
                    :class="{ 'is-profit': profit > 0, 'is-loss': profit < 0 }"
                  >
                    {{ profit > 0 ? '+' : '' }}¥{{ profit.toLocaleString() }}
                  </span>
                </div>
              </div>
            </div>
          </a-spin>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ThunderboltOutlined, DeleteOutlined, PlusOutlined, FileSearchOutlined } from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'
import DRGResultCard from '@/components/drg/DRGResultCard.vue'
import type { CaseFrontPage, DRGGroupingResult, DIPGroupingResult, DiagnosisItem, ProcedureItem } from '@/types/drg'

const caseFrontPages = ref<CaseFrontPage[]>([])
const selectedAdmissionId = ref<string>()
const predicting = ref(false)
const groupingResult = ref<DRGGroupingResult | DIPGroupingResult>()
const engineType = ref<'DRG' | 'DIP'>('DRG')

// 表单数据
const formData = ref({
  primary_diagnosis_code: '',
  primary_diagnosis_name: '',
  total_cost: 0,
  secondary_diagnoses: [] as DiagnosisItem[],
  procedures: [] as ProcedureItem[]
})

const canPredict = computed(() => !!formData.value.primary_diagnosis_code)
const caseOptions = computed(() => caseFrontPages.value.map(c => ({ label: `${c.admission_id} - ${c.patient_name}`, value: c.admission_id })))
const profit = computed(() => {
  if (!groupingResult.value) return 0
  return (groupingResult.value.baseline_payment ?? 0) - (formData.value.total_cost || 0)
})

/** 加载病案列表 */
const loadCaseFrontPages = async () => {
  try {
    const data = await drgApi.getCaseFrontPages()
    caseFrontPages.value = data
  } catch (error) {
    console.error('加载病案列表失败:', error)
  }
}

/** 导入现有病案数据 */
const handleImportCase = async (admissionId: string) => {
  try {
    const detail = await drgApi.getCaseFrontPageDetail(admissionId)
    if (detail) {
      formData.value = {
        primary_diagnosis_code: detail.primary_diagnosis_code,
        primary_diagnosis_name: detail.primary_diagnosis_name,
        total_cost: detail.total_cost || 0,
        secondary_diagnoses: [...(detail.secondary_diagnoses || [])],
        procedures: [...(detail.procedures || [])]
      }
      message.success('数据已导入，请点击预测')
    }
  } catch (error) {
    message.error('导入失败')
  }
}

const addSecondaryDiagnosis = () => {
  formData.value.secondary_diagnoses.push({ code: '', name: '', is_complication: false })
}

const removeSecondaryDiagnosis = (index: number) => {
  formData.value.secondary_diagnoses.splice(index, 1)
}

const addProcedure = () => {
  formData.value.procedures.push({ code: '', name: '' })
}

const removeProcedure = (index: number) => {
  formData.value.procedures.splice(index, 1)
}

/** 预测分组 */
const handlePredict = async () => {
  predicting.value = true
  try {
    const mockId = selectedAdmissionId.value || caseFrontPages.value[0]?.admission_id || 'MOCK001'
    
    let result;
    if (engineType.value === 'DIP') {
       const adxCodes = formData.value.secondary_diagnoses.map(d => d.code).join(';')
       const procCodes = formData.value.procedures.map(p => p.code).join(';')
       
       result = await drgApi.predictDIPGrouping({
         city_name: '泸州市',
         pdx_code: formData.value.primary_diagnosis_code,
         adx_code: adxCodes,
         proc_code: procCodes,
         patient_gender: '女',
         patient_age: 30,
         los: 10,
         total_fee: formData.value.total_cost || 0
       })
    } else {
       result = await drgApi.predictDRGGrouping({
        admission_id: mockId,
        region: 'sichuan'
       })
    }
    
    groupingResult.value = result
    message.success('预测成功')
  } catch (error) {
    console.error('预测失败:', error)
    message.error('预测失败: ' + (error as any).message)
  } finally {
    predicting.value = false
  }
}

onMounted(() => {
  loadCaseFrontPages()
})
</script>

<style scoped lang="scss">
.grouping-predict {
  min-height: 100vh;
  background-color: #f1f5f9;
}

.page-header {
  background: #fff;
  padding: 16px 32px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  
  :deep(.ant-page-header-heading-title) {
    font-weight: 700;
    font-size: 18px;
    color: #1e293b;
  }
  
  :deep(.ant-page-header-heading-sub-title) {
    color: #64748b;
    font-size: 13px;
  }
  
  .predict-btn {
    border-radius: 6px;
    font-weight: 600;
    height: 36px;
    padding: 0 20px;
  }
}

.content-wrapper {
  padding: 24px 32px;
}

/* Card Styles */
.input-card, .profit-card, .empty-result-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
  
  .card-title {
    font-size: 15px;
    font-weight: 700;
    color: #1e293b;
  }
}

.card-body {
  padding: 20px;
}

/* Quick Import */
.quick-import {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  
  .import-label {
    color: #64748b;
    font-size: 13px;
    flex-shrink: 0;
  }
  
  .import-select {
    flex: 1;
    
    :deep(.ant-select-selector) {
      border-radius: 6px;
      border-color: #e2e8f0;
    }
  }
}

/* Engine Selector */
.engine-selector {
  background: #f8fafc;
  padding: 12px 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  
  .engine-label {
    font-weight: 600;
    color: #334155;
    font-size: 13px;
  }
  
  .engine-radio-group {
    :deep(.ant-radio-button-wrapper) {
      border-radius: 6px;
      border-color: #e2e8f0;
      font-size: 13px;
      
      &:first-child {
        border-radius: 6px 0 0 6px;
      }
      
      &:last-child {
        border-radius: 0 6px 6px 0;
      }
      
      &.ant-radio-button-wrapper-checked {
        background: #1d4ed8;
        border-color: #1d4ed8;
      }
    }
  }
}

.section-divider {
  margin: 20px 0;
  border-color: #e2e8f0;
}

/* Form Styles */
.form-group {
  margin-bottom: 16px;
  
  .form-label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: #334155;
    margin-bottom: 8px;
    
    &.required::before {
      content: '*';
      color: #ef4444;
      margin-right: 4px;
    }
  }
  
  .icd-search {
    width: 100%;
  }
  
  .cost-input {
    width: 100%;
    
    :deep(.ant-input-number-input) {
      font-weight: 600;
    }
  }
}

/* Section Block */
.section-block {
  margin-top: 20px;
  
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 8px;
    border-bottom: 1px dashed #e2e8f0;
    margin-bottom: 12px;
    
    .section-title {
      font-weight: 600;
      font-size: 14px;
      color: #1e293b;
    }
    
    .add-btn {
      color: #6366f1;
      padding: 0;
      font-size: 13px;
      
      &:hover {
        color: #4f46e5;
      }
    }
  }
  
  .empty-hint {
    color: #94a3b8;
    font-size: 13px;
    padding: 12px 0;
  }
}

.dynamic-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 6px;
  transition: all 0.2s;
  
  &:hover {
    background: #f1f5f9;
    
    .delete-btn {
      opacity: 1;
    }
  }
  
  .flex-input {
    flex: 1;
  }
  
  .complication-check {
    flex-shrink: 0;
    font-size: 12px;
    color: #64748b;
  }
  
  .delete-btn {
    opacity: 0.5;
    transition: opacity 0.2s;
    
    &:hover {
      opacity: 1;
    }
  }
}

/* Empty Result */
.empty-result-card {
  padding: 60px 20px;
  text-align: center;
  margin-bottom: 16px;
  
  .empty-icon {
    font-size: 48px;
    color: #cbd5e1;
    margin-bottom: 16px;
  }
  
  .empty-text {
    color: #64748b;
    font-size: 14px;
  }
}

/* Profit Card */
.profit-card {
  margin-top: 16px;
  
  .profit-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    
    .profit-label {
      color: #64748b;
      font-size: 13px;
    }
    
    .profit-value {
      font-weight: 600;
      font-size: 14px;
      font-family: 'SF Mono', Monaco, monospace;
      color: #0f172a;
    }
    
    &.total {
      padding-top: 16px;
      
      .profit-label {
        font-weight: 600;
        color: #334155;
      }
      
      .profit-value {
        font-size: 18px;
        
        &.is-profit {
          color: #10b981;
        }
        
        &.is-loss {
          color: #ef4444;
        }
      }
    }
  }
  
  .profit-divider {
    height: 1px;
    background: #e2e8f0;
    margin: 8px 0;
  }
}
</style>
