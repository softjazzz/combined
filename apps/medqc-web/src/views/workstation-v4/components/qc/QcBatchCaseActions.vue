<template>
  <div class="batch-case-actions">
    <button type="button" :disabled="disabled" @click="prepare('approve')"><Check :size="15" />批量通过</button>
    <button type="button" :disabled="disabled" @click="prepare('urge')"><Bell :size="15" />批量催办</button>
    <span v-if="recordRefs.length > 100" role="alert">每批最多处理100份病历，请减少勾选。</span>
    <Modal :open="open" :title="action === 'approve' ? '确认批量审核通过' : '确认批量病历催办'" :footer="null" :closable="!busy" :mask-closable="false" @cancel="open = false">
      <p>本批 {{ items.length }} 份，已准备 {{ readyCount }} 份。未准备成功的病例不会提交。</p>
      <label v-if="action === 'urge'">催办内容<textarea v-model="content" maxlength="2000" :disabled="busy || submitted" /></label>
      <ul>
        <li v-for="item in items" :key="JSON.stringify(item.identity)">
          <strong>{{ item.identity.visit_id }}</strong> · {{ item.identity.patient_id }} · {{ item.identity.institute_id }}
          <span role="status">{{ item.message }}</span>
          <select v-if="action === 'urge' && item.prepared && item.state === 'ready'" v-model="item.recipient" :disabled="busy || submitted" aria-label="催办接收医生">
            <option value="">选择接收医生</option>
            <option v-for="doctor in item.prepared.doctors" :key="doctor.id" :value="doctor.id">{{ doctor.name }}</option>
          </select>
        </li>
      </ul>
      <button type="button" :disabled="busy || submitted || readyCount === 0 || !canConfirm" @click="submit">确认提交 {{ readyCount }} 份</button>
      <p v-if="submitted">本批已结束。结果未知的病例请打开详情核对后再操作。</p>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Modal } from 'ant-design-vue'
import { Bell, Check } from 'lucide-vue-next'
import { approveBatchCase, prepareBatchCase, type BatchCaseIdentity, type PreparedBatchCase } from '@/api/batchCaseActions'
import { CommunicationError, createCommunication } from '@/api/caseCommunications'
import type { CaseRecordReviewIdentity } from '@/api/recordReviews'

const props = defineProps<{ recordRefs: CaseRecordReviewIdentity[]; actorKey: string; carePhase: 'inpatient' | 'discharged'; allowed: boolean }>()
const emit = defineEmits<{ completed: [] }>()
type Item = { identity: BatchCaseIdentity; requestId: string; prepared?: PreparedBatchCase; recipient: string; state: 'preparing' | 'ready' | 'failed' | 'success' | 'unknown' | 'cancelled'; message: string }
const items = ref<Item[]>([])
const open = ref(false)
const busy = ref(false)
const submitted = ref(false)
const action = ref<'approve' | 'urge'>('approve')
const content = ref('请及时查看并处理该病历。')
let generation = 0
onBeforeUnmount(() => { generation++ })
const disabled = computed(() => busy.value || !props.allowed || !props.actorKey || props.recordRefs.length === 0 || props.recordRefs.length > 100)
const readyCount = computed(() => items.value.filter(item => item.state === 'ready').length)
const canConfirm = computed(() => action.value === 'approve' || (Boolean(content.value.trim()) && items.value.filter(item => item.state === 'ready').every(item => item.recipient)))

watch(() => [props.actorKey, props.carePhase, props.allowed], () => {
  generation++
  open.value = false
  items.value = []
  busy.value = false
})

async function prepare(nextAction: 'approve' | 'urge') {
  if (disabled.value) return
  const token = ++generation
  action.value = nextAction
  submitted.value = false
  items.value = props.recordRefs.map(identity => ({ identity: { ...identity, scene: props.carePhase === 'inpatient' ? 'running' : 'final' }, requestId: crypto.randomUUID(), recipient: '', state: 'preparing', message: '正在核验来源和权限' }))
  open.value = true
  busy.value = true
  for (const item of items.value) {
    if (token !== generation) return
    try {
      const prepared = await prepareBatchCase(item.identity)
      if (token !== generation) return
      if (nextAction === 'approve' && !prepared.review.can_submit) throw new Error('当前结果不可审核，请刷新查看审核状态')
      if (nextAction === 'urge' && prepared.doctors.length === 0) throw new Error('当前科室没有可接收催办的医生')
      item.prepared = prepared
      item.state = 'ready'
      item.message = '已冻结当前质控结果，等待确认'
    } catch (error) {
      item.state = 'failed'
      item.message = error instanceof Error ? error.message : '准备失败'
    }
  }
  if (token === generation) busy.value = false
}

async function submit() {
  if (busy.value || submitted.value || !canConfirm.value) return
  const token = generation
  const frozen = items.value.filter(item => item.state === 'ready' && item.prepared)
  submitted.value = true
  busy.value = true
  for (const item of frozen) {
    if (token !== generation) return
    const source = item.prepared!.source
    try {
      if (action.value === 'approve') {
        await approveBatchCase({ ...item.identity, job_id: source.root_job_id, envelope_id: source.envelope_id, request_id: item.requestId })
      } else {
        await createCommunication({ ...source, action: 'urge', content: content.value.trim(), recipient_id: item.recipient, request_id: item.requestId })
      }
      if (token !== generation) return
      item.state = 'success'
      item.message = action.value === 'approve' ? '审核通过已保存' : '病历催办已发送'
    } catch (error) {
      if (token !== generation) return
      const unknown = !(error instanceof CommunicationError) || error.unknown
      item.state = unknown ? 'unknown' : 'failed'
      item.message = `${unknown ? '结果未知，请核对' : '未完成'}：${error instanceof Error ? error.message : '请求异常'}`
    }
  }
  if (token === generation) {
    busy.value = false
    emit('completed')
  }
}
</script>

<style scoped>
.batch-case-actions { display: flex; gap: 8px; }
button { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border: 1px solid #d9d9df; border-radius: 8px; background: white; color: #1d1d1f; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
ul { max-height: 360px; overflow: auto; padding-left: 20px; }
li { padding: 8px 0; overflow-wrap: anywhere; }
li span { display: block; }
textarea { display: block; width: 100%; min-height: 72px; }
select { max-width: 100%; margin-top: 6px; }
</style>
