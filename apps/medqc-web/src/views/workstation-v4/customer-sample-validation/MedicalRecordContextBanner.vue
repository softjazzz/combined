<template>
  <div
    class="customer-record-result-title__context medical-record-context"
    :aria-label="recordContextAriaLabel"
  >
    <img
      class="patient-context-avatar"
      :src="contextAvatar"
      :alt="`${context?.patientName || '患者'}头像`"
    >
    <span class="customer-record-result-title__context-label">当前病历</span>
    <span class="customer-record-result-title__context-details">
      <span class="customer-record-result-title__context-value">
        <span
          v-for="(part, index) in (context?.label || '病历原文与质控结果对照').split(' · ')"
          :key="index"
          class="patient-context-part"
          :class="{ 'is-primary': index === 0 }"
        >{{ part }}</span>
      </span>
      <span
        v-if="hospitalizationTimeText"
        class="customer-record-result-title__context-time"
      >
        {{ hospitalizationTimeText }}
      </span>
    </span>
    <span
      v-if="qcTimeText"
      class="customer-record-result-title__qc-time"
    >
      {{ qcTimeText }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import avatarBoy from '@/assets/avatar-icons/patient-icon-boy.png'
import avatarGirl from '@/assets/avatar-icons/patient-icon-girl.png'
import avatarMan from '@/assets/avatar-icons/patient-icon-man.png'
import avatarWoman from '@/assets/avatar-icons/patient-icon-woman.png'
import avatarElderMan from '@/assets/avatar-icons/patient-icon-elder-man.png'
import avatarElderWoman from '@/assets/avatar-icons/patient-icon-elder-woman.png'

export interface MedicalRecordBannerContext {
  label: string
  patientName?: string
  patientSex?: string
  patientAge?: number
  admissionTime?: string
  dischargeTime?: string
}

const props = withDefaults(
  defineProps<{
    context: MedicalRecordBannerContext | null
    qcTimeText?: string
  }>(),
  { qcTimeText: '' },
)

const contextAvatar = computed(() => {
  const female = /女|female|^f$/i.test(String(props.context?.patientSex || '').trim())
  const age = Number(props.context?.patientAge || 0)
  if (age > 0 && age < 14) return female ? avatarGirl : avatarBoy
  if (age >= 55) return female ? avatarElderWoman : avatarElderMan
  return female ? avatarWoman : avatarMan
})
const hospitalizationTimeText = computed(() => {
  const admissionTime = props.context?.admissionTime
  const dischargeTime = props.context?.dischargeTime
  if (admissionTime && dischargeTime) return `住院时间 ${admissionTime} → ${dischargeTime}`
  if (admissionTime) return `入院时间 ${admissionTime}`
  if (dischargeTime) return `出院时间 ${dischargeTime}`
  return ''
})
const recordContextAriaLabel = computed(() =>
  [
    `当前病历：${props.context?.label || '病历原文与质控结果对照'}`,
    props.context?.admissionTime ? `入院时间：${props.context.admissionTime}` : '',
    props.context?.dischargeTime ? `出院时间：${props.context.dischargeTime}` : '',
  ]
    .filter(Boolean)
    .join('，'),
)
</script>

<style scoped>
.medical-record-context {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 12px;
  padding: 8px 14px;
  border: 1px solid rgba(213, 223, 236, 0.65);
  border-radius: 10px;
  background: rgba(246, 249, 253, 0.72);
}
.customer-record-result-title__context-label {
  display: none;
}
.customer-record-result-title__context-details {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.customer-record-result-title__context-value {
  min-width: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: baseline;
  gap: 2px 14px;
  overflow: hidden;
  color: #465366;
  font-size: 13px;
  font-weight: 400;
  line-height: 22px;
  text-align: left;
  overflow-wrap: anywhere;
}
.patient-context-part {
  color: #727b87;
  font-size: 12px;
  font-weight: 400;
  line-height: 22px;
}
.patient-context-part.is-primary {
  color: #303640;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.2px;
}
.patient-context-part:nth-child(2) {
  color: #526174;
  font-size: 13px;
}
.patient-context-part:nth-child(n + 3) {
  color: #8792a2;
  font-size: 12px;
}
.patient-context-avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
}
.customer-record-result-title__context-time {
  flex: none;
  padding-left: 10px;
  border-left: 1px solid rgba(10, 108, 255, 0.14);
  color: rgba(29, 29, 31, 0.58);
  font-size: 12px;
  font-weight: 500;
  line-height: 20px;
  white-space: nowrap;
}
.customer-record-result-title__qc-time {
  margin-left: auto;
  color: #8792a2;
  font-size: 12px;
  font-weight: 400;
  line-height: 20px;
  white-space: nowrap;
}
@media (max-width: 1000px) {
  .medical-record-context {
    flex-basis: 100%;
    order: 2;
  }
}
@media (max-width: 700px) {
  .customer-record-result-title__context-details {
    flex: 1;
    flex-wrap: wrap;
    gap: 2px 10px;
  }
  .customer-record-result-title__context-time {
    flex-basis: 100%;
    padding-left: 0;
    border-left: 0;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .customer-record-result-title__qc-time {
    flex-basis: 100%;
    margin-left: 48px;
    white-space: normal;
  }
}
</style>
