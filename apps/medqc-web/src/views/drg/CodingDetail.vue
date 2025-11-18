<template>
  <div class="coding-detail">
    <a-page-header
      :title="`编码详情 - ${caseFrontPage?.patient_name || ''}`"
      @back="() => $router.back()"
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
        <a-row :gutter="16">
          <!-- 左侧：患者信息和编码表单 -->
          <a-col :span="16">
            <!-- 患者基本信息 -->
            <a-card title="患者基本信息" :bordered="false" style="margin-bottom: 16px">
              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="住院号">
                  {{ caseFrontPage?.admission_id }}
                </a-descriptions-item>
                <a-descriptions-item label="患者ID">
                  {{ caseFrontPage?.patient_id }}
                </a-descriptions-item>
                <a-descriptions-item label="患者姓名">
                  {{ caseFrontPage?.patient_name }}
                </a-descriptions-item>
                <a-descriptions-item label="性别/年龄">
                  {{ getGenderText(caseFrontPage?.patient_gender) }} / {{ caseFrontPage?.patient_age }}岁
                </a-descriptions-item>
                <a-descriptions-item label="住院天数">
                  {{ caseFrontPage?.total_hospital_days || '-' }}天
                </a-descriptions-item>
                <a-descriptions-item label="总费用">
                  {{ formatCurrency(caseFrontPage?.total_cost) }}
                </a-descriptions-item>
              </a-descriptions>
            </a-card>

            <!-- 主诊断 -->
            <a-card title="主诊断" :bordered="false" style="margin-bottom: 16px">
              <a-form layout="vertical">
                <a-form-item label="ICD-10 编码" required>
                  <ICDCodeSearch
                    v-model:value="caseFrontPage!.primary_diagnosis_code"
                    v-model:name="caseFrontPage!.primary_diagnosis_name"
                    category="diagnosis"
                    placeholder="搜索诊断编码或名称"
                  />
                </a-form-item>
              </a-form>
            </a-card>

            <!-- 次诊断 -->
            <a-card title="次诊断" :bordered="false" style="margin-bottom: 16px">
              <a-button type="dashed" block @click="addSecondaryDiagnosis" style="margin-bottom: 16px">
                <template #icon><PlusOutlined /></template>
                添加次诊断
              </a-button>

              <a-list
                v-if="secondaryDiagnoses.length > 0"
                :data-source="secondaryDiagnoses"
                item-layout="horizontal"
              >
                <template #renderItem="{ item, index }">
                  <a-list-item>
                    <template #actions>
                      <a-checkbox v-model:checked="item.is_complication">
                        并发症
                      </a-checkbox>
                      <a-button type="link" danger size="small" @click="removeSecondaryDiagnosis(index)">
                        删除
                      </a-button>
                    </template>
                    <a-list-item-meta>
                      <template #title>
                        <ICDCodeSearch
                          v-model:value="item.code"
                          v-model:name="item.name"
                          category="diagnosis"
                          :placeholder="`次诊断 ${index + 1}`"
                        />
                      </template>
                    </a-list-item-meta>
                  </a-list-item>
                </template>
              </a-list>
            </a-card>

            <!-- 手术操作 -->
            <a-card title="手术操作" :bordered="false">
              <a-button type="dashed" block @click="addProcedure" style="margin-bottom: 16px">
                <template #icon><PlusOutlined /></template>
                添加手术操作
              </a-button>

              <a-list
                v-if="procedures.length > 0"
                :data-source="procedures"
                item-layout="horizontal"
              >
                <template #renderItem="{ item, index }">
                  <a-list-item>
                    <template #actions>
                      <a-button type="link" danger size="small" @click="removeProcedure(index)">
                        删除
                      </a-button>
                    </template>
                    <a-list-item-meta>
                      <template #title>
                        <ICDCodeSearch
                          v-model:value="item.code"
                          v-model:name="item.name"
                          category="procedure"
                          :placeholder="`手术操作 ${index + 1}`"
                        />
                      </template>
                    </a-list-item-meta>
                  </a-list-item>
                </template>
              </a-list>
            </a-card>
          </a-col>

          <!-- 右侧：编码推荐和校验结果 -->
          <a-col :span="8">
            <!-- ICD 编码推荐 -->
            <CodingRecommendation
              style="margin-bottom: 16px"
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  CheckOutlined,
  SaveOutlined,
  PlusOutlined
} from '@ant-design/icons-vue'
import { drgApi } from '@/api/drg'
import StatusTag from '@/components/drg/StatusTag.vue'
import ICDCodeSearch from '@/components/drg/ICDCodeSearch.vue'
import CodingRecommendation from '@/components/drg/CodingRecommendation.vue'
import CodingValidation from '@/components/drg/CodingValidation.vue'
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

/** 校验结果 */
const validationResult = ref<ValidationResult>()

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
</script>

<style scoped lang="scss">
.coding-detail {
  .content-wrapper {
    padding: 16px;
  }
}
</style>
