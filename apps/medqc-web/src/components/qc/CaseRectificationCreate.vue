<template>
  <section>
    <a-button class="rectification-launch" @click="openForm">
      <template #icon>
        <MqIcon name="task" :size="16" /> </template
      >派发整改 / 整改处理
    </a-button>
    <a-modal
      v-model:open="open"
      title="缺陷整改"
      wrap-class-name="mq-modal rectification-create-modal"
      ok-text="派发整改"
      cancel-text="取消"
      width="min(760px, 100vw)"
      :z-index="1200"
      :confirm-loading="saving"
      :ok-button-props="{
        disabled: loading || uncertain || !targetKey || !doctorId || requirement.trim().length < 10,
      }"
      @ok="save"
    >
      <div class="rectification-context mq-soft">
        <MqIcon name="task" :size="28" />
        <div>
          <strong>{{ visitId }}</strong
          ><span>{{ instituteId }} · {{ patientId }}</span>
        </div>
      </div>
      <a-alert v-if="error" type="error" :message="error" show-icon />
      <a-button v-if="error" :disabled="saving" @click="load"> 重新核对候选 </a-button>
      <a-spin :spinning="loading">
        <a-form layout="vertical" class="rectification-create-form">
          <a-form-item label="已确认缺陷">
            <a-select
              v-model:value="targetKey"
              :get-popup-container="popupContainer"
              :options="targets.map((item, index) => ({ value: String(index), label: item.label }))"
            />
          </a-form-item>
          <a-form-item label="受领医生">
            <a-select
              v-model:value="doctorId"
              :get-popup-container="popupContainer"
              :options="doctors.map((item) => ({ value: item.id, label: item.name }))"
            />
          </a-form-item>
          <a-form-item label="整改要求">
            <a-textarea v-model:value="requirement" :maxlength="2000" :rows="4" />
          </a-form-item>
        </a-form>
        <HomeRectificationTodos
          v-if="selectedSource"
          :scope="selectedSource"
          @changed="emit('changed')"
        />
      </a-spin>
    </a-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import HomeRectificationTodos from '@/views/workstation/HomeRectificationTodos.vue'
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
  initialTarget?: {
    source: 'auto' | 'manual'
    ruleId?: string
    defectId?: string
    rootJobId?: string
    envelopeId?: string
  } | null
  openIntent?: number
}>()
const auth = useAuthStore()
const popupContainer = (trigger: HTMLElement) => trigger.parentElement || trigger
const emit = defineEmits<{ created: []; changed: [] }>()
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
const selectedSource = computed(() => {
  if (targetKey.value === undefined) return undefined
  const target = targets.value[Number(targetKey.value)]
  if (!target) return undefined
  const { label: _label, ...source } = target
  return { ...identity(), ...source }
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
    if (
      props.initialTarget?.source === 'auto' &&
      (!props.initialTarget.rootJobId ||
        !props.initialTarget.envelopeId ||
        props.initialTarget.rootJobId !== props.jobId)
    )
      throw new Error('所选缺陷缺少可信结果版本或已换轮，请刷新缺陷列表')
    const result = await getRectificationCandidates(identity(), props.jobId)
    if (token !== generation) return
    targets.value = result.targets
    doctors.value = result.doctors
    if (props.initialTarget) {
      const expectedKind =
        props.initialTarget.source === 'auto' ? 'canonical_defect' : 'task_manual_defect'
      const expectedId =
        props.initialTarget.source === 'auto'
          ? props.initialTarget.ruleId
          : props.initialTarget.defectId
      targets.value = result.targets.filter(
        (target) =>
          target.target_kind === expectedKind &&
          target.target_id === expectedId &&
          (props.initialTarget?.source !== 'auto' ||
            target.envelope_id === props.initialTarget.envelopeId),
      )
      if (targets.value.length === 1) targetKey.value = '0'
      else {
        targets.value = []
        error.value = '所选缺陷已变化或不可用于整改，请刷新病例'
      }
    }
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
    emit('created')
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
  [
    () => props.instituteId,
    () => props.patientId,
    () => props.visitId,
    () => props.jobId,
    () => props.initialTarget?.source,
    () => props.initialTarget?.ruleId,
    () => props.initialTarget?.defectId,
    () => props.initialTarget?.rootJobId,
    () => props.initialTarget?.envelopeId,
    () => auth.user?.id,
    () => JSON.stringify(auth.user?.roles || []),
  ],
  reset,
)
watch(open, (value) => {
  if (!value) reset()
})
onUnmounted(reset)
watch(
  () => props.openIntent,
  (intent) => {
    if (intent && props.initialTarget) openForm()
  },
  { immediate: true },
)
</script>
<style scoped src="./styles/case-rectification-create.css"></style>
