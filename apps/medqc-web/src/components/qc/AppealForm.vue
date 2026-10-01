<template>
  <a-modal
    title="发起质控申诉"
    :open="visible"
    :confirm-loading="submitting"
    :ok-button-props="{ disabled: !selectedTarget || candidatesLoading }"
    :width="680"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-alert
      type="info"
      show-icon
      class="mb-4"
      message="仅可申诉系统已确认的 LX0609 缺陷，或已审核通过且仍有效的任务人工缺陷。"
    />
    <a-form ref="formRef" :model="formState" :rules="rules" layout="vertical">
      <div class="identity-grid">
        <a-form-item label="机构编号" name="instituteId">
          <a-input v-model:value="formState.instituteId" :disabled="identityLocked" />
        </a-form-item>
        <a-form-item label="患者编号" name="patientId">
          <a-input v-model:value="formState.patientId" :disabled="identityLocked" />
        </a-form-item>
        <a-form-item label="就诊编号" name="visitId">
          <a-input v-model:value="formState.visitId" :disabled="identityLocked" />
        </a-form-item>
      </div>
      <div class="candidate-tools">
        <a-button :loading="candidatesLoading" @click="loadCandidates"> 读取可申诉问题 </a-button>
        <span v-if="candidates?.caseDepartment">病例科室：{{ candidates.caseDepartment }}</span>
      </div>
      <a-alert
        v-if="candidatesError"
        type="error"
        show-icon
        class="mb-4"
        :message="candidatesError"
      />
      <a-alert
        v-else-if="candidates?.canonical.state === 'unavailable'"
        type="warning"
        show-icon
        class="mb-4"
        message="自动质控结果暂不可用，请稍后重试"
      />
      <a-alert
        v-if="candidates && !targetOptions.length && candidates.canonical.state !== 'unavailable'"
        type="info"
        show-icon
        class="mb-4"
        :message="candidateEmptyText"
      />
      <a-form-item v-if="targetOptions.length" label="申诉问题" name="targetKey">
        <a-select v-model:value="formState.targetKey" placeholder="请选择要申诉的已反馈问题">
          <a-select-opt-group v-if="canonicalOptions.length" label="系统已确认缺陷">
            <a-select-option
              v-for="option in canonicalOptions"
              :key="option.key"
              :value="option.key"
            >
              {{ option.label }}
            </a-select-option>
          </a-select-opt-group>
          <a-select-opt-group v-if="manualOptions.length" label="已审核人工缺陷">
            <a-select-option v-for="option in manualOptions" :key="option.key" :value="option.key">
              {{ option.label }}
            </a-select-option>
          </a-select-opt-group>
        </a-select>
      </a-form-item>
      <a-form-item label="申诉理由" name="appealReason">
        <a-textarea
          v-model:value="formState.appealReason"
          :rows="5"
          placeholder="请说明原判定与病历事实不一致的具体原因（10至2000字）"
          show-count
          :maxlength="2000"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script lang="ts" setup>
import { computed, reactive, ref, watch } from 'vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import { message } from 'ant-design-vue'
import { createAppeal, getAppealCandidates } from '@/api/appeal'
import type { AppealCandidates } from '@/types/appeal'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(
  defineProps<{
    visible: boolean
    instituteId?: string
    patientId?: string
    visitId?: string
  }>(),
  { instituteId: '', patientId: '', visitId: '' },
)
const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void
  (event: 'success'): void
}>()
const authStore = useAuthStore()
const authKey = computed(() =>
  [
    authStore.user?.id?.trim() || '',
    authStore.user?.institute_id?.trim() || '',
    authStore.user?.department?.trim() || '',
    [...authStore.userRoles].sort().join(','),
  ].join('|'),
)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const candidatesLoading = ref(false)
const candidatesError = ref('')
const candidates = ref<AppealCandidates | null>(null)
let candidatesRequest = 0
let submitRequest = 0
const formState = reactive({
  instituteId: '',
  patientId: '',
  visitId: '',
  targetKey: '',
  appealReason: '',
})
const identityLocked = computed(() =>
  Boolean(props.instituteId && props.patientId && props.visitId),
)
const rules = {
  instituteId: [{ required: true, whitespace: true, message: '请输入机构编号', trigger: 'blur' }],
  patientId: [{ required: true, whitespace: true, message: '请输入患者编号', trigger: 'blur' }],
  visitId: [{ required: true, whitespace: true, message: '请输入就诊编号', trigger: 'blur' }],
  targetKey: [{ required: true, message: '请选择可申诉问题', trigger: 'change' }],
  appealReason: [
    { required: true, whitespace: true, message: '请输入申诉理由', trigger: 'blur' },
    { min: 10, message: '申诉理由至少10个字符', trigger: 'blur' },
    { max: 2000, message: '申诉理由不能超过2000个字符', trigger: 'blur' },
  ],
} satisfies FormProps['rules']
const canonicalOptions = computed(
  () =>
    candidates.value?.canonical.items.map((item) => ({
      key: `canonical:${item.ruleId}`,
      label: `${item.ruleName || item.ruleId}${item.conclusion ? `：${item.conclusion}` : ''}`,
    })) ?? [],
)
const manualOptions = computed(
  () =>
    candidates.value?.manualDefects.map((item) => ({
      key: `manual:${item.defectId}`,
      label: `${item.ruleName || item.ruleCode || '人工缺陷'}${item.description ? `：${item.description}` : ''}`,
    })) ?? [],
)
const targetOptions = computed(() => [...canonicalOptions.value, ...manualOptions.value])
const selectedTarget = computed(() =>
  targetOptions.value.some((item) => item.key === formState.targetKey),
)
const candidateEmptyText = computed(() => '当前病例没有可申诉的已反馈问题。')

function currentIdentity() {
  return {
    instituteId: formState.instituteId.trim(),
    patientId: formState.patientId.trim(),
    visitId: formState.visitId.trim(),
  }
}
async function loadCandidates() {
  const identity = currentIdentity()
  if (!identity.instituteId || !identity.patientId || !identity.visitId) {
    candidatesError.value = '请先完整填写病例三坐标'
    return
  }
  const request = ++candidatesRequest
  const identityKey = JSON.stringify(identity)
  const account = authKey.value
  candidatesLoading.value = true
  candidatesError.value = ''
  candidates.value = null
  formState.targetKey = ''
  try {
    const result = await getAppealCandidates(identity)
    if (
      request !== candidatesRequest ||
      account !== authKey.value ||
      identityKey !== JSON.stringify(currentIdentity())
    )
      return
    candidates.value = result
  } catch (error) {
    if (
      request !== candidatesRequest ||
      account !== authKey.value ||
      identityKey !== JSON.stringify(currentIdentity())
    )
      return
    candidatesError.value = error instanceof Error ? error.message : '读取可申诉问题失败'
  } finally {
    if (request === candidatesRequest) candidatesLoading.value = false
  }
}
async function handleSubmit() {
  if (submitting.value) return
  const request = ++submitRequest
  const account = authKey.value
  try {
    if (typeof formRef.value?.validate === 'function') await formRef.value.validate()
    const source = candidates.value
    const identity = currentIdentity()
    const identityKey = JSON.stringify(identity)
    if (!source || !selectedTarget.value) throw new Error('可申诉问题已变更，请重新读取')
    if (
      source.instituteId !== identity.instituteId ||
      source.patientId !== identity.patientId ||
      source.visitId !== identity.visitId
    ) {
      throw new Error('病例坐标已变更，请重新读取可申诉问题')
    }
    const reason = formState.appealReason.trim()
    submitting.value = true
    if (formState.targetKey.startsWith('canonical:')) {
      const ruleId = formState.targetKey.slice('canonical:'.length)
      const canonical = source.canonical
      if (
        canonical.state !== 'ready' ||
        !canonical.scene ||
        !canonical.jobId ||
        !canonical.envelopeId
      )
        throw new Error('自动质控来源不完整，请重新读取')
      await createAppeal({
        ...identity,
        targetKind: 'canonical_defect',
        scene: canonical.scene,
        expectedJobId: canonical.jobId,
        expectedEnvelopeId: canonical.envelopeId,
        ruleId,
        appealReason: reason,
        evidence: [],
      })
    } else {
      const defectId = formState.targetKey.slice('manual:'.length)
      const manual = source.manualDefects.find((item) => item.defectId === defectId)
      if (!manual) throw new Error('人工缺陷来源已变更，请重新读取')
      await createAppeal({
        ...identity,
        targetKind: 'task_manual_defect',
        scene: manual.scene,
        defectId,
        appealReason: reason,
        evidence: [],
      })
    }
    if (
      request !== submitRequest ||
      account !== authKey.value ||
      identityKey !== JSON.stringify(currentIdentity()) ||
      !props.visible
    )
      return
    message.success('申诉已提交')
    emit('success')
    handleCancel()
  } catch (error) {
    if (request !== submitRequest || account !== authKey.value || !props.visible) return
    if (!(typeof error === 'object' && error !== null && 'errorFields' in error))
      message.error(error instanceof Error ? error.message : '提交失败，请核对后重试')
  } finally {
    if (request === submitRequest) submitting.value = false
  }
}
function reset() {
  ++candidatesRequest
  ++submitRequest
  submitting.value = false
  candidatesLoading.value = false
  candidatesError.value = ''
  candidates.value = null
  formState.instituteId = props.instituteId || authStore.user?.institute_id || ''
  formState.patientId = props.patientId
  formState.visitId = props.visitId
  formState.targetKey = ''
  formState.appealReason = ''
  if (typeof formRef.value?.clearValidate === 'function') formRef.value.clearValidate()
}
function handleCancel() {
  reset()
  emit('update:visible', false)
}
watch(
  () => props.visible,
  (open) => {
    reset()
    if (open && identityLocked.value) void loadCandidates()
  },
  { immediate: true },
)
watch(
  () => [props.instituteId, props.patientId, props.visitId],
  () => {
    if (!props.visible) return
    reset()
    if (identityLocked.value) void loadCandidates()
  },
)
watch(
  () => [formState.instituteId, formState.patientId, formState.visitId],
  () => {
    if (
      !props.visible ||
      identityLocked.value ||
      (!candidates.value && !candidatesLoading.value && !candidatesError.value)
    )
      return
    ++candidatesRequest
    ++submitRequest
    submitting.value = false
    candidatesLoading.value = false
    candidatesError.value = ''
    candidates.value = null
    formState.targetKey = ''
  },
)
watch(authKey, () => {
  if (!props.visible) return
  reset()
  if (identityLocked.value) void loadCandidates()
})
</script>

<style scoped>
.mb-4 {
  margin-bottom: 16px;
}
.identity-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.candidate-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 16px;
  color: rgba(29, 29, 31, 0.6);
  font-size: 13px;
}
@media (max-width: 640px) {
  .identity-grid {
    grid-template-columns: 1fr;
    gap: 0;
  }
}
</style>
