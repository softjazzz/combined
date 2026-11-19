<template>
  <div
    class="customer-record-result-title__context medical-record-context"
    :aria-label="recordContextAriaLabel"
  >
    <span class="customer-record-result-title__context-label">当前病历</span>
    <span class="customer-record-result-title__context-details">
      <img
        class="patient-context-avatar"
        :src="contextAvatar"
        :alt="`${context?.patientName || '患者'}头像`"
      >
      <span class="customer-record-result-title__context-value">
        <strong class="patient-context-part is-primary">{{ contextParts[0] }}</strong>
        <span v-if="contextParts.length > 1" class="patient-context-meta">
          <span v-for="(part, index) in contextParts.slice(1)" :key="index" class="patient-context-part">
            {{ part }}
          </span>
        </span>
      </span>
    </span>
    <span v-if="recordTimes.length" class="customer-record-result-title__context-time">
      <span v-for="time in recordTimes" :key="time.label" class="patient-context-time-entry">
        <span>{{ time.label }}</span>{{ ' ' }}<strong>{{ time.value }}</strong>
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
const contextParts = computed(() => (props.context?.label || '病历原文与质控结果对照').split(' · '))
const recordTimes = computed(() =>
  [
    { label: '入院时间', value: props.context?.admissionTime },
    { label: '出院时间', value: props.context?.dischargeTime },
  ].filter(({ value }) => Boolean(value)),
)
const recordContextAriaLabel = computed(() =>
  [
    `当前病历：${props.context?.label || '病历原文与质控结果对照'}`,
    ...recordTimes.value.map(({ label, value }) => `${label}：${value}`),
  ].join('，'),
)
</script>

<style scoped>
.medical-record-context {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 20px;
  padding-block: 4px;
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
  gap: 2px;
  text-align: left;
  overflow-wrap: anywhere;
}
.patient-context-part.is-primary {
  color: var(--mq-text-primary, #1d1d1f);
  font-size: 17px;
  font-weight: 700;
  line-height: 23px;
}
.patient-context-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 8px;
  color: var(--mq-text-secondary, #515154);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  line-height: 18px;
}
.patient-context-meta .patient-context-part + .patient-context-part {
  padding-inline-start: 8px;
  border-inline-start: 1px solid var(--mq-border-strong, rgba(0, 0, 0, 0.12));
}
.patient-context-avatar {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
}
.customer-record-result-title__context-time {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  min-width: 0;
  padding-inline-start: 16px;
  border-inline-start: 1px solid var(--mq-border, rgba(0, 0, 0, 0.07));
  color: var(--mq-text-tertiary, #6e6e73);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}
.patient-context-time-entry {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.patient-context-time-entry strong {
  color: var(--mq-text-secondary, #515154);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.customer-record-result-title__qc-time {
  margin-left: auto;
  color: var(--mq-text-tertiary, #6e6e73);
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
  .customer-record-result-title__context-time,
  .customer-record-result-title__qc-time {
    flex-basis: 100%;
    margin-inline-start: 46px;
    padding-inline-start: 0;
    border-inline-start: 0;
    white-space: normal;
  }
}
</style>
