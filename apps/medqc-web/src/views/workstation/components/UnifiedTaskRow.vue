<template>
  <div class="qc-task-row">
    <div class="qc-task-patient">
      <div class="qc-task-avatar">
        <img
          v-if="!avatarBroken"
          :src="avatarSrc"
          :alt="`${task.patient_name || '患者'}头像`"
          @error="avatarBroken = true"
        >
        <span v-else>{{ patientInitial }}</span>
      </div>
      <div class="min-w-0">
        <div class="qc-task-patient__name">
          {{ task.patient_name || '未知患者' }}
          <span>{{ patientMeta }}</span>
        </div>
        <div class="qc-task-patient__id">
          {{ task.visit_id || '--' }}
        </div>
      </div>
    </div>

    <div class="qc-task-cell qc-task-dept">
      {{ task.department || '未分科' }}
    </div>

    <div class="qc-task-cell">
      <span
        class="qc-task-risk"
        :class="riskClass"
      >
        {{ riskLabel }}
      </span>
    </div>

    <div class="qc-task-cell qc-task-reason">
      {{ riskReason }}
    </div>

    <div class="qc-task-deadline">
      <span>{{ deadlineText }}</span>
      <strong :class="deadlineClass">{{ deadlineStatus }}</strong>
    </div>

    <div class="qc-task-action">
      <button
        type="button"
        @click="handleClickAction"
      >
        <span
          v-if="isLoading"
          class="animate-spin"
        ><LoadingOutlined /></span>
        <span v-else>立即处理</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { LoadingOutlined } from '@ant-design/icons-vue'
import type { UnifiedTaskItem } from './legacyHomeTypes'
import avatarBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import avatarElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import avatarElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'
import avatarGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import avatarMan from '@/assets/avatar-icons/patient-icon-man.png'
import avatarWoman from '@/assets/avatar-icons/patient-icon-woman.png'

const props = defineProps<{
  task: UnifiedTaskItem
  formatDateTime: (value?: string | null) => string
}>()

const emit = defineEmits<{
  open: [task: UnifiedTaskItem]
}>()

const isLoading = ref(false)
const avatarBroken = ref(false)

function handleClickAction() {
  isLoading.value = true
  setTimeout(() => {
    emit('open', props.task)
    isLoading.value = false
  }, 150)
}

const patientInitial = computed(() => (props.task.patient_name || '患').slice(0, 1).toUpperCase())

const avatarSrc = computed(() => {
  const seed = getSeed(props.task.patient_name || props.task.visit_id || props.task.id)
  const gender = resolvePatientGender(seed)
  const age = resolvePatientAge()

  if (age !== null && age < 14) return gender === 'female' ? avatarGirl : avatarBoy
  if (age !== null && age >= 55) return gender === 'female' ? avatarElderWoman : avatarElderMan
  if (age !== null) return gender === 'female' ? avatarWoman : avatarMan

  return gender === 'female' ? avatarWoman : avatarMan
})

function getSeed(value: string): number {
  return [...value].reduce((sum, char) => sum + char.charCodeAt(0), 0)
}

function resolvePatientAge(): number | null {
  const value = props.task.patient_age
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value !== 'string') return null

  const normalized = value.trim()
  if (!normalized) return null
  if (/[月天日]/.test(normalized)) return 0

  const matched = normalized.match(/\d+(?:\.\d+)?/)
  if (!matched) return null
  const age = Number(matched[0])
  return Number.isFinite(age) ? age : null
}

function resolvePatientGender(seed: number): 'male' | 'female' {
  const value = `${props.task.patient_sex || props.task.patient_gender || ''}`.trim().toLowerCase()
  if (/女|female|^f$|^2$/.test(value)) return 'female'
  if (/男|male|^m$|^1$/.test(value)) return 'male'
  return seed % 2 === 0 ? 'male' : 'female'
}

const patientMeta = computed(() => {
  const score =
    typeof props.task.latest_qc_score === 'number' ? `${props.task.latest_qc_score}分` : ''
  return score || workflowLabel(props.task.workflow_type)
})

const riskLevel = computed(() => {
  const value = (props.task.severity || props.task.priority || '').toLowerCase()
  if (value === 'critical' || props.task.task_status === 'overdue') return 'high'
  if (value === 'high') return 'high'
  if (value === 'warning' || value === 'medium') return 'medium'
  return 'normal'
})

const riskLabel = computed(() => {
  if (riskLevel.value === 'high') return '高风险'
  if (riskLevel.value === 'medium') return '中风险'
  return '低风险'
})

const riskClass = computed(() => `qc-task-risk--${riskLevel.value}`)

const riskReason = computed(() => {
  const text = `${props.task.title || ''} ${props.task.summary || ''}`
  if (/(编码|icd|drg)/i.test(text)) return '编码规范风险'
  if (/(首页|字段|漏填|缺失|主诊断|手术)/i.test(text)) return '病历书写不规范'
  if (/(结算|费用|医保|支付|清单)/i.test(text)) return '结算费用风险'
  if (/(知情|同意|签字|麻醉)/i.test(text)) return '关键诊疗记录缺失'
  return props.task.summary || props.task.title || '质控风险待复核'
})

const deadlineText = computed(() => {
  const value = props.task.due_at || props.task.latest_created_at
  return props.formatDateTime(value)
})

const deadlineStatus = computed(() => {
  if (props.task.task_status === 'overdue') return '已超时 2小时'
  if (props.task.task_status === 'in_progress') return '处理中'
  return '剩余 2小时'
})

const deadlineClass = computed(() => {
  if (props.task.task_status === 'overdue') return 'is-overdue'
  if (props.task.task_status === 'in_progress') return 'is-progress'
  return 'is-pending'
})

function workflowLabel(value?: string) {
  if (value === 'frontpage') return '首页质控'
  if (value === 'coding') return '编码质控'
  if (value === 'settlement') return '结算质控'
  if (value === 'frontpage_generate') return '首页生成'
  return '质控任务'
}
</script>
