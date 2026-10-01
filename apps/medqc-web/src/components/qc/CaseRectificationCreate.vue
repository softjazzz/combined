<template>
  <section>
    <a-button @click="openForm"><Send :size="14" />派发整改</a-button>
    <a-modal
      v-model:open="open"
      title="派发缺陷整改"
      :confirm-loading="saving"
      :ok-button-props="{
        disabled: loading || uncertain || !targetKey || !doctorId || requirement.trim().length < 10,
      }"
      @ok="save"
    >
      <a-alert v-if="error" type="error" :message="error" show-icon />
      <a-button v-if="error" :disabled="saving" @click="load">重新核对候选</a-button>
      <a-spin :spinning="loading">
        <a-form layout="vertical">
          <a-form-item label="已确认缺陷">
            <a-select
              v-model:value="targetKey"
              :options="targets.map((item, index) => ({ value: String(index), label: item.label }))"
            />
          </a-form-item>
          <a-form-item label="受领医生">
            <a-select
              v-model:value="doctorId"
              :options="doctors.map((item) => ({ value: item.id, label: item.name }))"
            />
          </a-form-item>
          <a-form-item label="整改要求"
            ><a-textarea v-model:value="requirement" :maxlength="2000" :rows="4"
          /></a-form-item>
        </a-form>
      </a-spin>
    </a-modal>
  </section>
</template>
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { Send } from 'lucide-vue-next'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import {
  createRectification,
  getRectificationCandidates,
  type RectificationCandidates,
} from '@/api/defectRectifications'
const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
  jobId: string
}>()
const auth = useAuthStore()
const open = ref(false),
  loading = ref(false),
  saving = ref(false),
  uncertain = ref(false)
const error = ref(''),
  targetKey = ref<string>(),
  doctorId = ref<string>(),
  requirement = ref('')
const targets = ref<RectificationCandidates['targets']>([]),
  doctors = ref<RectificationCandidates['doctors']>([])
let generation = 0
const identity = () => ({
  institute_id: props.instituteId,
  patient_id: props.patientId,
  visit_id: props.visitId,
})
async function load() {
  const token = ++generation
  loading.value = true
  error.value = ''
  targetKey.value = undefined
  doctorId.value = undefined
  targets.value = []
  doctors.value = []
  try {
    const result = await getRectificationCandidates(identity(), props.jobId)
    if (token !== generation) return
    targets.value = result.targets
    doctors.value = result.doctors
    uncertain.value = false
  } catch (e) {
    if (token === generation) error.value = e instanceof Error ? e.message : '候选读取失败'
  } finally {
    if (token === generation) loading.value = false
  }
}
function openForm() {
  open.value = true
  requirement.value = ''
  void load()
}
async function save() {
  const item = targets.value[Number(targetKey.value)]
  if (
    !item ||
    !doctorId.value ||
    saving.value ||
    uncertain.value ||
    requirement.value.trim().length < 10
  )
    return
  const token = generation
  saving.value = true
  try {
    const { label: _label, ...target } = item
    await createRectification({
      ...identity(),
      ...target,
      assignee_id: doctorId.value,
      requirement: requirement.value.trim(),
    })
    if (token !== generation) return
    open.value = false
    message.success('整改已派发，受领医生可在站内待办处理')
  } catch (e) {
    if (token === generation) {
      error.value = e instanceof Error ? e.message : '派发结果待核对'
      uncertain.value = true
    }
  } finally {
    if (token === generation) saving.value = false
  }
}
function reset() {
  ++generation
  open.value = false
  saving.value = false
  loading.value = false
  targets.value = []
  doctors.value = []
}
watch(
  () => [
    props.instituteId,
    props.patientId,
    props.visitId,
    props.jobId,
    auth.user?.id,
    auth.user?.roles,
  ],
  reset,
  { deep: true },
)
watch(open, (value) => {
  if (!value) reset()
})
onUnmounted(reset)
</script>
