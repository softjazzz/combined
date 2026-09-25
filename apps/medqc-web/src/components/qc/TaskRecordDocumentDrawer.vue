<template>
  <a-drawer
    :open="open"
    :width="'min(960px, 100vw)'"
    title="病历文书"
    placement="right"
    class="task-record-document-drawer"
    @close="emit('update:open', false)"
  >
    <div v-if="record" class="task-record-document-drawer__identity">
      <span>机构 {{ record.institute_id }}</span>
      <span>患者 {{ record.patient_id }}</span>
      <span>就诊 {{ record.visit_id }}</span>
    </div>
    <a-spin v-if="loading" class="task-record-document-drawer__loading" />
    <a-alert v-else-if="error" type="error" show-icon :message="error">
      <template #action><a-button size="small" @click="void loadDocuments()">重试</a-button></template>
    </a-alert>
    <a-empty v-else-if="!documents.length" description="暂无已保存文书" />
    <div v-else class="task-record-document-drawer__workspace">
      <nav class="task-record-document-drawer__list" aria-label="文书目录">
        <button
          v-for="document in documents"
          :key="document.key"
          type="button"
          :class="{ 'is-selected': document.key === selectedKey }"
          @click="void selectDocument(document)"
        >
          <strong>{{ document.title || document.document_type || '未命名文书' }}</strong>
          <span>{{ document.record_time || '时间未记录' }}</span>
        </button>
      </nav>
      <section class="task-record-document-drawer__content" aria-label="文书正文">
        <a-spin v-if="documentLoading" />
        <a-alert v-else-if="documentError" type="error" show-icon :message="documentError">
          <template #action>
            <a-button v-if="selectedSummary" size="small" @click="void selectDocument(selectedSummary)">重试</a-button>
          </template>
        </a-alert>
        <ReadonlyMedicalDocumentContent v-else-if="selectedDocument" :document="selectedDocument" />
        <a-empty v-else description="请选择文书" />
      </section>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TaskRecordItem } from '@/api/tasks'
import {
  getEditableMedicalRecordDocument,
  getEditableMedicalRecordDocuments,
} from '@/services/manual-case-sample-service'
import ReadonlyMedicalDocumentContent from '@/views/workstation-v4/customer-sample-validation/ReadonlyMedicalDocumentContent.vue'
import type { EditableMedicalRecordDocument } from '@/views/workstation-v4/customer-sample-validation/types'

const props = defineProps<{ open: boolean; taskId: string; record: TaskRecordItem | null }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()
const loading = ref(false)
const error = ref('')
const documents = ref<EditableMedicalRecordDocument[]>([])
const selectedKey = ref('')
const selectedDocument = ref<EditableMedicalRecordDocument | null>(null)
const documentLoading = ref(false)
const documentError = ref('')
let requestSequence = 0
let documentSequence = 0

const selectedSummary = computed(() => documents.value.find((item) => item.key === selectedKey.value) || null)

function context() {
  const record = props.record
  if (!props.open || !props.taskId || !record || record.task_id !== props.taskId
    || record.record_id !== record.id || !record.institute_id || !record.patient_id || !record.visit_id) return null
  return {
    task_id: props.taskId,
    task_record_id: record.id,
    institute_id: record.institute_id,
    patient_id: record.patient_id,
    visit_id: record.visit_id,
    source_view: 'saved' as const,
  }
}

async function loadDocuments() {
  const sequence = ++requestSequence
  documentSequence += 1
  documents.value = []
  selectedKey.value = ''
  selectedDocument.value = null
  documentError.value = ''
  const params = context()
  if (!params) {
    loading.value = false
    error.value = props.open ? '任务病历身份不完整，无法读取文书' : ''
    return
  }
  loading.value = true
  error.value = ''
  const response = await getEditableMedicalRecordDocuments(params.visit_id, { ...params, view: 'summary' })
  if (sequence !== requestSequence || !context()) return
  loading.value = false
  if (!response.success || !response.data || !Array.isArray(response.data.documents)) {
    error.value = response.message || '读取病历文书失败'
    return
  }
  documents.value = response.data.documents
  if (documents.value[0]) void selectDocument(documents.value[0])
}

async function selectDocument(summary: EditableMedicalRecordDocument) {
  const params = context()
  if (!params || !documents.value.some((item) => item.key === summary.key)) return
  const sequence = ++documentSequence
  selectedKey.value = summary.key
  selectedDocument.value = null
  documentLoading.value = true
  documentError.value = ''
  const response = await getEditableMedicalRecordDocument(params.visit_id, summary, params)
  if (sequence !== documentSequence || !context()) return
  documentLoading.value = false
  if (!response.success || !response.data) {
    documentError.value = response.message || '读取文书正文失败'
    return
  }
  selectedDocument.value = response.data
}

watch(
  [() => props.open, () => props.taskId, () => props.record?.id,
    () => props.record?.institute_id, () => props.record?.patient_id, () => props.record?.visit_id],
  () => { void loadDocuments() },
  { immediate: true },
)
</script>

<style scoped>
.task-record-document-drawer__identity {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  padding: 0 0 16px;
  color: #555b66;
  font-size: 14px;
  border-bottom: 1px solid rgba(0, 0, 0, .08);
}
.task-record-document-drawer__loading { margin: 24px; }
.task-record-document-drawer__workspace {
  display: grid;
  grid-template-columns: minmax(190px, 240px) minmax(0, 1fr);
  min-height: min(70vh, 700px);
}
.task-record-document-drawer__list {
  overflow: auto;
  border-right: 1px solid rgba(0, 0, 0, .08);
}
.task-record-document-drawer__list button {
  display: grid;
  width: 100%;
  gap: 4px;
  padding: 12px;
  border: 0;
  border-bottom: 1px solid rgba(0, 0, 0, .06);
  background: #fff;
  color: #1d1d1f;
  text-align: left;
  cursor: pointer;
}
.task-record-document-drawer__list button:hover,
.task-record-document-drawer__list button.is-selected { background: #eaf2ff; }
.task-record-document-drawer__list strong { font-size: 14px; font-weight: 600; }
.task-record-document-drawer__list span { color: #68717e; font-size: 12px; }
.task-record-document-drawer__content { min-width: 0; padding: 20px; overflow: auto; }
@media (max-width: 640px) {
  .task-record-document-drawer__workspace { grid-template-columns: 1fr; }
  .task-record-document-drawer__list { max-height: 180px; border-right: 0; border-bottom: 1px solid rgba(0, 0, 0, .08); }
}
</style>
