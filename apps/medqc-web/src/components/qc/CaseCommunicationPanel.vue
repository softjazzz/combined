<template>
  <section class="case-communication">
    <header><strong>病例沟通</strong><a-button @click="open = true; load()">催办 / 新增质控意见</a-button></header>
    <a-modal v-model:open="open" title="病例沟通" :footer="null" :mask-closable="!saving" :closable="!saving" :keyboard="!saving">
      <a-alert v-if="error" :message="error" type="error" show-icon />
      <a-button v-if="error" :disabled="loading || saving" @click="load">刷新核对</a-button>
      <a-spin :spinning="loading">
        <a-form layout="vertical" @finish="save">
          <a-form-item label="操作"><a-radio-group v-model:value="action" :disabled="saving || uncertain"><a-radio-button value="urge">催办</a-radio-button><a-radio-button value="opinion">质控意见</a-radio-button></a-radio-group></a-form-item>
          <a-form-item label="受领医生"><a-select v-model:value="recipient" :options="candidates?.doctors.map(person => ({ value: person.id, label: person.name })) || []" :disabled="saving || uncertain" /></a-form-item>
          <a-form-item :label="action === 'urge' ? '催办说明' : '意见正文'"><a-textarea v-model:value="content" :maxlength="2000" :rows="4" :disabled="saving || uncertain" /></a-form-item>
          <a-button type="primary" html-type="submit" :loading="saving" :disabled="loading || uncertain || !candidates || !recipient || !content.trim()">发送站内通知</a-button>
        </a-form>
        <ul><li v-for="item in candidates?.items.filter(item => item.action !== 'withdraw')" :key="item.id">
          <span>{{ item.action === 'urge' ? '催办' : '意见' }} · {{ item.withdrawn ? '已撤回' : item.is_read === true ? '已读' : item.is_read === false ? '未读' : '通知未知' }}</span>
          <p>{{ item.content }}</p>
          <a-button v-if="item.action === 'urge' && !item.withdrawn" :disabled="saving || uncertain" @click="withdraw(item)">撤回催办</a-button>
        </li></ul>
      </a-spin>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { CommunicationError, createCommunication, getCommunicationCandidates } from '@/api/caseCommunications'
import type { Communication, CommunicationCandidates } from '@/api/caseCommunications'
const props = defineProps<{ instituteId: string; patientId: string; visitId: string; scene: 'running' | 'final'; jobId: string }>()
const emit = defineEmits<{ saved: [] }>()
const auth = useAuthStore()
const open = ref(false), loading = ref(false), saving = ref(false), uncertain = ref(false)
const error = ref(''), content = ref(''), recipient = ref<string>(), action = ref<'urge' | 'opinion'>('urge')
const candidates = ref<CommunicationCandidates>()
let generation = 0
let requestId = ''
const identity = () => ({ institute_id: props.instituteId, patient_id: props.patientId, visit_id: props.visitId, scene: props.scene, root_job_id: props.jobId })
async function load() {
  const token = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await getCommunicationCandidates(identity())
    if (token !== generation) return
    if (Object.entries(identity()).some(([key, value]) => data.source[key as keyof typeof data.source] !== value)) throw new Error('病例来源已变化，请刷新病例')
    candidates.value = data
    if (uncertain.value && data.items.some(item => item.request_id === requestId)) {
      uncertain.value = false
      content.value = ''
      requestId = ''
      emit('saved')
    } else if (uncertain.value) error.value = '写入结果尚未确认，请继续刷新核对，勿重复发送'
  } catch (reason) {
    if (token === generation) { error.value = reason instanceof Error ? reason.message : '读取沟通失败'; candidates.value = undefined }
  } finally { if (token === generation) loading.value = false }
}
async function send(itemAction: Communication['action'], body: string, doctor: string, related?: string) {
  if (!candidates.value || saving.value || uncertain.value) return
  const token = generation
  requestId = crypto.randomUUID()
  saving.value = true
  error.value = ''
  try {
    const payload = { ...identity(), envelope_id: candidates.value.source.envelope_id, action: itemAction, content: body, recipient_id: doctor, request_id: requestId, ...(related ? { related_event_id: related } : {}) }
    const result = await createCommunication(payload)
    if (token !== generation) return
    if (!result.id || Object.entries(payload).some(([key, value]) => result[key as keyof Communication] !== value)) throw new CommunicationError('保存结果与本次病例沟通不一致')
    content.value = ''
    requestId = ''
    emit('saved')
    saving.value = false
    await load()
  } catch (reason) {
    if (token === generation) {
      uncertain.value = reason instanceof CommunicationError ? reason.unknown : true
      error.value = `${reason instanceof Error ? reason.message : '发送失败'}${uncertain.value ? '；写入结果待核实，请刷新核对' : ''}`
    }
  } finally { if (token === generation) saving.value = false }
}
function save() { if (recipient.value && content.value.trim()) void send(action.value, content.value.trim(), recipient.value) }
function withdraw(item: Communication) { void send('withdraw', '撤回本次病例催办', item.recipient_id, item.id) }
watch(() => [props.instituteId, props.patientId, props.visitId, props.scene, props.jobId, auth.user?.id], () => {
  generation += 1; open.value = false; saving.value = false; loading.value = false; uncertain.value = false
  candidates.value = undefined; content.value = ''; recipient.value = undefined; requestId = ''; error.value = ''
})
</script>

<style scoped>
.case-communication header { display: flex; align-items: center; gap: 12px; }
.case-communication li { margin-top: 12px; padding-top: 12px; border-top: 1px solid #edf0f4; }
.case-communication p { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
