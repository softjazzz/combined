<template>
  <Drawer
    v-if="record"
    open
    root-class-name="current-medical-record-drawer"
    width="min(1400px, 100vw)"
    :body-style="{ display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden', padding: '16px 0 0' }"
    @close="emit('close')"
  >
    <template #closeIcon>
      <RecordViewCloseIcon label="关闭病历" />
    </template>
    <template #title>
      <ReadonlyMedicalRecordHeader :context="recordContext" />
    </template>
    <HospitalLoading v-if="loading" label="正在读取病历文书" />
    <Alert v-else-if="loadError" type="error" show-icon :message="loadError" />
    <QCRecordCompareWorkbench
      v-else
      :provided-documents="documents"
      :key="JSON.stringify([record.instituteId, record.patientId, record.visitId])"
      :visit-id="record.visitId || ''"
      :institute-id="record.instituteId"
      :patient-id="record.patientId"
      :admission-time="record.admissionDate"
      :discharge-time="record.dischargeDate"
      :issues="[]"
      :feedback-available="false"
      source-view="current"
      document-only
      fill-available-height
    />
  </Drawer>
</template>

<script setup lang="ts">
import { Alert, Drawer } from 'ant-design-vue'
import { computed, ref, watch } from 'vue'
import HospitalLoading from '@/components/qc/HospitalLoading.vue'
import { loadCurrentMedicalRecord } from '@/services/current-medical-record'
import type { EditableMedicalRecordDocument } from '../customer-sample-validation/types'
import QCRecordCompareWorkbench from '../semantic-rules/components/QCRecordCompareWorkbench.vue'
import RecordViewCloseIcon from './RecordViewCloseIcon.vue'
import ReadonlyMedicalRecordHeader from './ReadonlyMedicalRecordHeader.vue'
import type { PatientRecord } from '../types'

const props = defineProps<{ record: PatientRecord | null }>()
const emit = defineEmits<{ close: [] }>()
const documents = ref<EditableMedicalRecordDocument[]>([])
const loading = ref(false)
const loadError = ref('')
const recordContext = computed(() => {
  const record = props.record
  if (!record) return null
  return {
    label: [record.name || '当前病历', record.department, record.visitId].filter(Boolean).join(' · '),
    patientName: record.name,
    patientSex: record.sex,
    patientAge: record.age,
    admissionTime: record.admissionDate,
    dischargeTime: record.dischargeDate,
  }
})

watch(
  () => props.record,
  async (record, _, onCleanup) => {
    let active = true
    onCleanup(() => { active = false })
    documents.value = []
    loadError.value = ''
    loading.value = false
    if (!record) return
    if (!record.visitId?.trim() || !record.instituteId?.trim() || !record.patientId?.trim()) {
      loadError.value = '无法确认当前病历身份，已停止读取病历文书'
      return
    }
    loading.value = true
    const result = await loadCurrentMedicalRecord(record.visitId, record)
    if (!active) return
    loading.value = false
    if (result.success && result.data) documents.value = result.data.documents
    else loadError.value = result.message || '读取病历文书失败'
  },
  { immediate: true },
)
</script>

<style scoped>
:global(.current-medical-record-drawer .ant-drawer-content) {
  background: var(--mq-bg-mesh);
}

:global(.current-medical-record-drawer .ant-drawer-header) {
  padding: 16px 20px;
  border-bottom-color: var(--mq-glass-border);
  background: var(--mq-glass-bg);
}

:global(.current-medical-record-drawer .ant-drawer-title) {
  min-width: 0;
}

:global(.current-medical-record-drawer .ant-drawer-close) {
  order: 1;
  flex: 0 0 38px;
  align-self: flex-start;
  margin: 0;
  margin-inline-start: 12px;
}
</style>
