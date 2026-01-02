<template>
  <div class="coding-detail">
    <a-page-header
      :title="`编码详情 - ${caseFrontPage?.patient_name || ''}`"
      @back="() => $router.back()"
      style="padding: 16px 24px"
    >
      <template #tags>
        <StatusTag v-if="caseFrontPage" type="coding" :value="caseFrontPage.coding_status" />
      </template>
      <template #extra>
        <a-space>
          <a-button @click="handleValidate" :loading="validating">
            <template #icon><CheckOutlined /></template>
            校验编码
          </a-button>
          <a-button type="primary" @click="handleSave" :loading="saving">
            <template #icon><SaveOutlined /></template>
            保存
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-spin :spinning="loading">
        <a-row :gutter="16" style="height: calc(100vh - 120px)">
          <!-- 左侧：病历阅读区 (30%) -->
          <a-col :span="7" style="height: 100%">
            <a-card title="病历资料" :bordered="false" class="full-height-card" :bodyStyle="{ flex: 1, padding: 0, overflow: 'hidden' }">
              <MedicalRecordViewer 
                :admission-id="admissionId" 
                :highlight-keywords="recommendationKeywords"
              />
            </a-card>
          </a-col>

          <!-- 中间：编码工作区 (45%) -->
          <a-col :span="11" style="height: 100%; overflow-y: auto">
            <!-- 患者基本信息 (精简版) -->
            <a-card :bordered="false" style="margin-bottom: 12px" size="small">
              <a-descriptions :column="2" size="small">
                <a-descriptions-item label="住院号">{{ caseFrontPage?.admission_id }}</a-descriptions-item>
                <a-descriptions-item label="姓名">{{ caseFrontPage?.patient_name }} ({{ caseFrontPage?.patient_age }}岁)</a-descriptions-item>
                <a-descriptions-item label="总费用">{{ formatCurrency(caseFrontPage?.total_cost) }}</a-descriptions-item>
                <a-descriptions-item label="住院日">{{ caseFrontPage?.total_hospital_days || '-' }}天</a-descriptions-item>
              </a-descriptions>
            </a-card>

            <!-- 主诊断 -->
            <a-card title="主诊断" :bordered="false" style="margin-bottom: 12px" size="small">
              <a-form layout="vertical">
                <a-form-item label="ICD-10 编码" required style="margin-bottom: 0">
                  <ICDCodeSearch
                    v-model:value="caseFrontPage!.primary_diagnosis_code"
                    v-model:name="caseFrontPage!.primary_diagnosis_name"
                    category="diagnosis"
                    placeholder="搜索诊断编码或名称"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-form>
            </a-card>

            <!-- 次诊断 -->
            <a-card title="次诊断" :bordered="false" style="margin-bottom: 12px" size="small">
              <template #extra>
                <a-button type="link" size="small" @click="addSecondaryDiagnosis">
                  <template #icon><PlusOutlined /></template>
                  添加
                </a-button>
              </template>

              <div class="diagnosis-list">
                <div v-for="(item, index) in secondaryDiagnoses" :key="index" class="list-item">
                   <div class="item-index">{{ index + 1 }}</div>
                   <div class="item-content">
                     <ICDCodeSearch
                        v-model:value="item.code"
                        v-model:name="item.name"
                        category="diagnosis"
                        :placeholder="`次诊断`"
                        size="small"
                      />
                      <div class="item-options">
                        <a-checkbox v-model:checked="item.is_complication">并发症</a-checkbox>
                      </div>
                   </div>
                   <a-button type="text" danger size="small" @click="removeSecondaryDiagnosis(index)">
                     <template #icon><DeleteOutlined /></template>
                   </a-button>
                </div>
                <a-empty v-if="secondaryDiagnoses.length === 0" description="暂无次诊断" image="simple" />
              </div>
            </a-card>

            <!-- 手术操作 -->
            <a-card title="手术操作" :bordered="false" style="margin-bottom: 12px" size="small">
              <template #extra>
                <a-button type="link" size="small" @click="addProcedure">
                  <template #icon><PlusOutlined /></template>
                  添加
                </a-button>
              </template>
              
              <div class="procedure-list">
                <div v-for="(item, index) in procedures" :key="index" class="list-item">
                   <div class="item-index">{{ index + 1 }}</div>
                   <div class="item-content">
                     <ICDCodeSearch
                        v-model:value="item.code"
                        v-model:name="item.name"
                        category="procedure"
                        :placeholder="`手术操作`"
                        size="small"
                      />
                      <div class="item-options">
                        <a-date-picker v-model:value="item.procedure_date" size="small" placeholder="手术日期" style="width: 120px" value-format="YYYY-MM-DD" />
                      </div>
                   </div>
                   <a-button type="text" danger size="small" @click="removeProcedure(index)">
                     <template #icon><DeleteOutlined /></template>
                   </a-button>
                </div>
                <a-empty v-if="procedures.length === 0" description="暂无手术操作" image="simple" />
              </div>
            </a-card>
          </a-col>

          <!-- 右侧：智能助手 (25%) -->
          <a-col :span="6" style="height: 100%; overflow-y: auto">
            <!-- 编码完整性顾问 (New) -->
            <CodingCompletenessAdvisor
              :admission-id="admissionId"
              :current-data="currentCodingData"
              style="margin-bottom: 12px"
              @accept="handleAcceptSuggestion"
            />

            <!-- ICD 编码推荐 -->
            <CodingRecommendation
              style="margin-bottom: 12px"
              @select="handleSelectRecommendation"
            />

            <!-- 编码校验结果 -->
            <CodingValidation
              v-if="validationResult"
              :validation-result="validationResult"
            />
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
  DeleteOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'
import CodingRecommendation from '@/components/drg/CodingRecommendation.vue'
import CodingValidation from '@/components/drg/CodingValidation.vue'
import MedicalRecordViewer from '@/components/drg/MedicalRecordViewer.vue'
import CodingCompletenessAdvisor from '@/components/advisor/CodingCompletenessAdvisor.vue'
import { getGenderText, formatCurrency } from '@/utils/drg'
import type { CaseFrontPage, DiagnosisItem, ProcedureItem, ValidationResult } from '@/types/drg'

const route = useRoute()
const router = useRouter()

const admissionId = route.params.admissionId as string

/** 病案首页数据 */
const caseFrontPage = ref<CaseFrontPage>()
const loading = ref(false)
const saving = ref(false)
const validating = ref(false)

/** 次诊断列表 */
const secondaryDiagnoses = ref<DiagnosisItem[]>([])

/** 手术操作列表 */
const procedures = ref<ProcedureItem[]>([])

const currentCodingData = computed(() => ({
  primary_diagnosis: caseFrontPage.value ? {
    code: caseFrontPage.value.primary_diagnosis_code,
    name: caseFrontPage.value.primary_diagnosis_name
  } : undefined,
  secondary_diagnoses: secondaryDiagnoses.value.map(d => ({
    code: d.code,
    name: d.name
  })),
  procedures: procedures.value.map(p => ({
    code: p.code,
    name: p.name
  }))
}))

/** 校验结果 */
const validationResult = ref<ValidationResult>()

/** 推荐关键词（用于高亮病历） */
const recommendationKeywords = computed(() => {
  const keywords: string[] = []
  if (validationResult.value?.warnings) {
    validationResult.value.warnings.forEach(w => {
      // 简单提取警告中的关键医学名词（示例逻辑）
      if (w.evidence) {
        // 这里可以根据实际情况进行更复杂的关键词提取
        // 暂时只高亮提到的诊断名称
        const matches = w.message.match(/建议补充.*：(.*?)[（(]|建议标记(.*?)/)
        if (matches && matches[1]) keywords.push(matches[1])
      }
    })
  }
  return keywords
})

/** 加载病案详情 */
const loadCaseFrontPage = async () => {
  loading.value = true
  try {
    const data = await drgApi.getCaseFrontPageDetail(admissionId)
    caseFrontPage.value = data
    secondaryDiagnoses.value = data.secondary_diagnoses || []
    procedures.value = data.procedures || []
  } catch (error) {
    console.error('加载病案详情失败:', error)
    message.error('加载病案详情失败')
  } finally {
    loading.value = false
  }
}

/** 添加次诊断 */
const addSecondaryDiagnosis = () => {
  secondaryDiagnoses.value.push({
    code: '',
    name: '',
    sequence: secondaryDiagnoses.value.length + 1,
    is_complication: false
  })
}

/** 删除次诊断 */
const removeSecondaryDiagnosis = (index: number) => {
  secondaryDiagnoses.value.splice(index, 1)
  // 更新序号
  secondaryDiagnoses.value.forEach((item, idx) => {
    item.sequence = idx + 1
  })
}

/** 添加手术操作 */
const addProcedure = () => {
  procedures.value.push({
    code: '',
    name: '',
    sequence: procedures.value.length + 1
  })
}

/** 删除手术操作 */
const removeProcedure = (index: number) => {
  procedures.value.splice(index, 1)
  procedures.value.forEach((item, idx) => {
    item.sequence = idx + 1
  })
}

/** 选择推荐编码 */
const handleSelectRecommendation = (code: string, name: string) => {
  if (caseFrontPage.value) {
    caseFrontPage.value.primary_diagnosis_code = code
    caseFrontPage.value.primary_diagnosis_name = name
    message.success('已采用推荐编码')
  }
}

/** 校验编码 */
const handleValidate = async () => {
  if (!caseFrontPage.value) {
    return
  }

  validating.value = true
  try {
    const result = await drgApi.validateCoding({
      admission_id: admissionId,
      primary_diagnosis: {
        code: caseFrontPage.value.primary_diagnosis_code,
        name: caseFrontPage.value.primary_diagnosis_name
      },
      secondary_diagnoses: secondaryDiagnoses.value,
      procedures: procedures.value
    })

    validationResult.value = result
    if (result.is_valid) {
      message.success('编码校验通过')
    } else {
      message.warning('编码校验发现问题，请查看右侧校验结果')
    }
  } catch (error) {
    console.error('编码校验失败:', error)
    message.error('编码校验失败')
  } finally {
    validating.value = false
  }
}

/** 保存编码 */
const handleSave = async () => {
  if (!caseFrontPage.value) {
    return
  }

  // 验证必填字段
  if (!caseFrontPage.value.primary_diagnosis_code) {
    message.error('请填写主诊断编码')
    return
  }

  saving.value = true
  try {
    await drgApi.saveCaseFrontPage({
      ...caseFrontPage.value,
      secondary_diagnoses: secondaryDiagnoses.value.filter(d => d.code),
      procedures: procedures.value.filter(p => p.code)
    })

    message.success('保存成功')
    router.back()
  } catch (error) {
    console.error('保存失败:', error)
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadCaseFrontPage()
})
// 处理采纳建议
const handleAcceptSuggestion = (suggestion: any) => {
  if (suggestion.category === 'diagnosis' && suggestion.action === 'add_code') {
    // 检查是否已存在
    const exists = secondaryDiagnoses.value.some(d => d.code === suggestion.target_code)
    if (exists) {
      message.warning('该诊断已存在')
      return
    }
    
    // 添加到次诊断
    secondaryDiagnoses.value.push({
      code: suggestion.target_code,
      name: suggestion.target_name,
      sequence: secondaryDiagnoses.value.length + 2,
      is_complication: false // 默认为非并发症，或者根据 LLM 建议推断
    })
    
    message.success(`已采纳建议：添加 ${suggestion.target_name}`)
  } else {
    message.info('暂只支持自动添加诊断编码')
  }
}
</script>

<style scoped lang="scss">
.coding-detail {
  height: 100vh;
  display: flex;
  flex-direction: column;

  .content-wrapper {
    flex: 1;
    padding: 16px 24px;
    overflow: hidden;
    background-color: #f0f2f5;
  }
  
  .full-height-card {
    height: 100%;
    display: flex;
    flex-direction: column;
    
    :deep(.ant-card-head) {
      min-height: 48px;
    }
    
    :deep(.ant-card-body) {
      flex: 1;
      padding: 0; 
      overflow: hidden;
    }
  }
  
  .diagnosis-list, .procedure-list {
    .list-item {
      display: flex;
      align-items: flex-start;
      margin-bottom: 8px;
      padding-bottom: 8px;
      border-bottom: 1px dashed #f0f0f0;
      
      &:last-child {
        margin-bottom: 0;
        padding-bottom: 0;
        border-bottom: none;
      }
      
      .item-index {
        width: 24px;
        height: 24px;
        line-height: 24px;
        text-align: center;
        background-color: #f5f5f5;
        border-radius: 50%;
        margin-right: 8px;
        font-size: 12px;
        color: #999;
        margin-top: 4px;
      }
      
      .item-content {
        flex: 1;
        
        .item-options {
          margin-top: 4px;
          display: flex;
          align-items: center;
        }
      }
    }
  }
}
</style>
