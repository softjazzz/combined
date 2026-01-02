<template>
  <div class="grouping-predict">
    <a-page-header
      title="DRG 分组预测"
      sub-title="DRG 入组预测和模拟试算"
      @back="() => $router.back()"
    >
      <template #extra>
         <a-button type="primary" @click="handlePredict" :loading="predicting" :disabled="!canPredict">
           <template #icon><ThunderboltOutlined /></template>
           开始预测
         </a-button>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-row :gutter="16">
        <!-- 左侧：模拟录入区 -->
        <a-col :span="14">
          <a-card title="病案信息录入" :bordered="false">
             <!-- 快速导入 -->
             <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
               <span>快速导入:</span>
               <a-select
                 v-model:value="selectedAdmissionId"
                 show-search
                 placeholder="从现有病案导入数据..."
                 style="flex: 1"
                 @change="handleImportCase"
                 :options="caseOptions"
               />
             </div>
             
             <div style="margin-bottom: 16px; background: #f5f5f5; padding: 12px; border-radius: 4px;">
               <span style="margin-right: 12px; font-weight: bold">分组引擎:</span>
               <a-radio-group v-model:value="engineType" button-style="solid">
                 <a-radio-button value="DRG">OpenDRG</a-radio-button>
                 <a-radio-button value="DIP">DIP (按病种分值)</a-radio-button>
               </a-radio-group>
             </div>

             <a-divider />
             
             <a-form layout="vertical">
               <!-- 主诊断 -->
               <a-row :gutter="16">
                 <a-col :span="12">
                   <a-form-item label="主诊断" required>
                     <ICDCodeSearch
                       v-model:value="formData.primary_diagnosis_code"
                       v-model:name="formData.primary_diagnosis_name"
                       category="diagnosis"
                     />
                   </a-form-item>
                 </a-col>
                 <a-col :span="12">
                   <a-form-item label="总费用 (预估)">
                     <a-input-number
                        v-model:value="formData.total_cost"
                        style="width: 100%"
                        :formatter="value => `¥ ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')"
                        :parser="value => value.replace(/\¥\s?|(,*)/g, '')"
                     />
                   </a-form-item>
                 </a-col>
               </a-row>

               <!-- 次诊断 -->
               <div class="section-label">
                 <span>次诊断</span>
                 <a-button type="link" size="small" @click="addSecondaryDiagnosis">添加</a-button>
               </div>
               <div v-for="(item, index) in formData.secondary_diagnoses" :key="index" class="dynamic-item">
                 <ICDCodeSearch
                    v-model:value="item.code"
                    v-model:name="item.name"
                    category="diagnosis"
                    placeholder="次诊断"
                    style="flex: 1"
                  />
                  <a-checkbox v-model:checked="item.is_complication">并发症</a-checkbox>
                  <DeleteOutlined class="delete-icon" @click="removeSecondaryDiagnosis(index)" />
               </div>

               <!-- 手术操作 -->
               <div class="section-label" style="margin-top: 16px">
                 <span>手术操作</span>
                 <a-button type="link" size="small" @click="addProcedure">添加</a-button>
               </div>
               <div v-for="(item, index) in formData.procedures" :key="index" class="dynamic-item">
                 <ICDCodeSearch
                    v-model:value="item.code"
                    v-model:name="item.name"
                    category="procedure"
                    placeholder="手术操作"
                    style="flex: 1"
                  />
                  <DeleteOutlined class="delete-icon" @click="removeProcedure(index)" />
               </div>
             </a-form>
          </a-card>
        </a-col>

        <!-- 右侧：预测结果 -->
        <a-col :span="10">
          <a-spin :spinning="predicting">
            <DRGResultCard v-if="groupingResult" :result="groupingResult" :engineType="engineType" style="margin-bottom: 16px" />
            
            <!-- 结果占位符 -->
            <a-card v-else :bordered="false" class="empty-result">
              <a-empty description="点击“开始预测”获取分组结果" />
            </a-card>

            <!-- 盈亏分析卡片 -->
            <a-card title="盈亏分析模拟" :bordered="false" v-if="groupingResult">
              <div class="profit-analysis">
                 <div class="profit-item">
                   <span class="label">预估收入 (基准支付):</span>
                   <span class="value">¥{{ groupingResult.baseline_payment.toLocaleString() }}</span>
                 </div>
                 <div class="profit-item">
                   <span class="label">预估成本 (总费用):</span>
                   <span class="value">¥{{ (formData.total_cost || 0).toLocaleString() }}</span>
                 </div>
                 <a-divider style="margin: 12px 0" />
                 <div class="profit-item total">
                   <span class="label">预计盈亏:</span>
                   <span class="value" :class="{ 'profit': profit > 0, 'loss': profit < 0 }">
                     {{ profit > 0 ? '+' : '' }}¥{{ profit.toLocaleString() }}
                   </span>
                 </div>
              </div>
            </a-card>
          </a-spin>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons-vue'
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
  return groupingResult.value.baseline_payment - (formData.value.total_cost || 0)
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
    // 模拟API调用：实际上我们需要把表单数据传给后端
    // 由于predictDRGGrouping接口设计目前主要接收 admission_id，
    // 这里我们假设后端有一个支持直接传数据的重载或新接口
    // 为了演示 Mock 效果，我们仍使用 admission_id 调用，但逻辑上这应该是一个"模拟预测"
    
    // 如果没有选 admission_id，我们就用第一个做 Mock
    const mockId = selectedAdmissionId.value || caseFrontPages.value[0]?.admission_id || 'MOCK001'
    
    let result;
    if (engineType.value === 'DIP') {
       // DIP 预测
       const adxCodes = formData.value.secondary_diagnoses.map(d => d.code).join(';')
       const procCodes = formData.value.procedures.map(p => p.code).join(';')
       
       result = await drgApi.predictDIPGrouping({
         city_name: '泸州市', // 默认城市，后续可开放选择
         pdx_code: formData.value.primary_diagnosis_code,
         adx_code: adxCodes,
         proc_code: procCodes,
         patient_gender: '女', // 暂略，实际应从表单取
         patient_age: 30,      // 暂略
         los: 10,              // 暂略
         total_fee: formData.value.total_cost || 0
       })
    } else {
       // DRG 预测
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
  .content-wrapper {
    padding: 16px 24px;
    background-color: #f0f2f5;
    min-height: calc(100vh - 120px);
  }
  
  .section-label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: bold;
    color: #333;
    margin-bottom: 8px;
    border-bottom: 1px dashed #e8e8e8;
    padding-bottom: 4px;
  }
  
  .dynamic-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    
    .delete-icon {
      color: #999;
      cursor: pointer;
      &:hover {
        color: #ff4d4f;
      }
    }
  }
  
  .empty-result {
    height: 300px;
    display: flex;
    justify-content: center;
    align-items: center;
  }
  
  .profit-analysis {
    .profit-item {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8px;
      font-size: 14px;
      
      .label { color: #666; }
      .value { font-family: monospace; font-weight: bold; }
      
      &.total {
        font-size: 16px;
        .value.profit { color: #52c41a; }
        .value.loss { color: #cf1322; }
      }
    }
  }
}
</style>
