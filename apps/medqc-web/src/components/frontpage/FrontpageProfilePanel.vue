<template>
  <div class="frontpage-profile-panel">
    <a-row :gutter="16">
      <!-- 左侧：首页预览 -->
      <a-col :span="14">
        <a-card size="small" title="病案首页预览">
          <template #extra>
            <a-space>
              <a-button size="small" type="primary" @click="handleAnalyze" :loading="analyzing">
                <template #icon><ScanOutlined /></template>
                画像分析
              </a-button>
              <a-button size="small" @click="handlePrint" :disabled="!draft">
                <template #icon><PrinterOutlined /></template>
                打印
              </a-button>
            </a-space>
          </template>
          
          <HmFrontpagePreview ref="previewRef" :draft="draft" />
        </a-card>
      </a-col>
      
      <!-- 右侧：画像分析 -->
      <a-col :span="10">
        <a-card size="small" title="诊断/手术画像">
          <template #extra>
            <a-tag v-if="profile" color="green">已分析</a-tag>
            <a-tag v-else color="default">待分析</a-tag>
          </template>
          
          <DiagnosisSurgeryTimeline
            v-if="profile"
            :diagnosisTimeline="profile.diagnosis_timeline || []"
            :surgeryVerification="profile.surgery_verification || []"
            :discrepancies="profile.discrepancies || []"
            :loading="analyzing"
          />
          
          <a-empty v-else description="点击'画像分析'按钮生成诊断/手术画像">
            <a-button type="primary" @click="handleAnalyze" :loading="analyzing">
              开始分析
            </a-button>
          </a-empty>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { ScanOutlined, PrinterOutlined } from '@ant-design/icons-vue'
import HmFrontpagePreview from './HmFrontpagePreview.vue'
import DiagnosisSurgeryTimeline from './DiagnosisSurgeryTimeline.vue'
import { frontpageApi } from '@/api/frontpage'

interface MedicalProfile {
  diagnosis_timeline: any[]
  surgery_verification: any[]
  discrepancies: any[]
}

const props = defineProps<{
  draft: any | null
  medicalText?: string
}>()

const emit = defineEmits<{
  (e: 'profile-analyzed', profile: MedicalProfile): void
}>()

const previewRef = ref<InstanceType<typeof HmFrontpagePreview> | null>(null)
const profile = ref<MedicalProfile | null>(null)
const analyzing = ref(false)

async function handleAnalyze() {
  if (!props.medicalText && !props.draft) {
    message.warning('需要病历文本或首页草稿才能进行画像分析')
    return
  }
  
  analyzing.value = true
  try {
    // 构建首页诊断/手术列表
    const frontpageDiagnoses: string[] = []
    const frontpageProcedures: string[] = []
    
    if (props.draft?.diagnoses) {
      if (props.draft.diagnoses.discharge_main_diagnosis_text) {
        frontpageDiagnoses.push(props.draft.diagnoses.discharge_main_diagnosis_text)
      }
      if (props.draft.diagnoses.discharge_other_diagnoses_texts) {
        frontpageDiagnoses.push(...props.draft.diagnoses.discharge_other_diagnoses_texts)
      }
    }
    
    if (props.draft?.procedures?.main_procedure_text) {
      frontpageProcedures.push(props.draft.procedures.main_procedure_text)
    }
    
    const response = await frontpageApi.analyzeProfile({
      medical_text: props.medicalText,
      frontpage_diagnoses: frontpageDiagnoses,
      frontpage_procedures: frontpageProcedures
    })
    
    if (response.success && response.data) {
      profile.value = response.data as MedicalProfile
      emit('profile-analyzed', profile.value)
      
      const issues = profile.value.discrepancies?.length || 0
      if (issues > 0) {
        message.warning(`画像分析完成，发现 ${issues} 个差异需关注`)
      } else {
        message.success('画像分析完成，未发现差异')
      }
    } else {
      message.error('画像分析失败')
    }
  } catch (error) {
    console.error('画像分析失败:', error)
    message.error('画像分析失败，请稍后重试')
  } finally {
    analyzing.value = false
  }
}

function handlePrint() {
  // 调用预览组件的打印方法
  const preview = previewRef.value as any
  if (preview?.printIframe) {
    preview.printIframe()
  }
}
</script>

<style scoped>
.frontpage-profile-panel {
  padding: 16px;
}
</style>
