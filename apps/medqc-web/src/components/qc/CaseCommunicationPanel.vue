<template>
  <section
    v-if="allowed"
    class="case-communication"
  >
    <a-button @click="openForm">
      <template #icon>
        <MqIcon
          name="task"
          :size="16"
        />
      </template>病历催办 / 质控意见
    </a-button>
    <a-modal
      v-model:open="open"
      title="病历沟通"
      wrap-class-name="mq-modal"
      width="min(720px, 100vw)"
      :z-index="1200"
      :footer="null"
      :mask-closable="!saving"
      :closable="!saving"
      :keyboard="!saving"
    >
      <p class="case-communication__context">
        {{ visitId }}<span v-if="candidates"> · {{ candidates.source.scene === 'running' ? '运行病历' : '终末病历' }}</span>
      </p>
      <a-alert
        v-if="error"
        :message="error"
        type="error"
        show-icon
      />
      <a-button
        v-if="error"
        :disabled="loading || saving"
        @click="load"
      >
        刷新核对
      </a-button>
      <a-spin :spinning="loading">
        <a-form
          layout="vertical"
          :model="formModel"
          @finish="save"
        >
          <a-form-item label="操作">
            <a-radio-group
              v-model:value="action"
              :disabled="loading || saving || uncertain"
            >
              <a-radio-button value="urge">
                催办
              </a-radio-button><a-radio-button value="opinion">
                质控意见
              </a-radio-button>
            </a-radio-group>
          </a-form-item>
          <a-form-item label="受领医生">
            <a-select
              v-model:value="recipient"
              :get-popup-container="popupContainer"
              :options="
                candidates?.doctors.map((person) => ({ value: person.id, label: person.name })) ||
                  []
              "
              :disabled="loading || saving || uncertain"
            />
          </a-form-item>
          <a-form-item :label="action === 'urge' ? '催办说明' : '意见正文'">
            <a-textarea
              v-model:value="content"
              :maxlength="2000"
              :rows="4"
              :disabled="loading || saving || uncertain"
            />
          </a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            :loading="saving"
            :disabled="loading || uncertain || !candidates || !recipient || !content.trim()"
          >
            发送站内通知
          </a-button>
        </a-form>
        <h3>操作历史</h3>
        <ul class="case-communication__history">
          <li
            v-for="item in candidates?.items"
            :key="item.id"
          >
            <div class="case-communication__meta">
              <strong>{{ labels[item.action] }}</strong><span>{{ doctorName(item.recipient_id) }}</span><span>{{ item.withdrawn ? '已撤回' : item.is_read ? '已读' : '未读' }}</span><time>{{ formatTime(item.created_at) }}</time>
            </div>
            <p>{{ item.content }}</p>
            <p
              v-if="item.related_event_id"
              class="case-communication__relation"
            >
              原催办：{{ item.related_event_id }}
            </p>
            <a-button
              v-if="item.action === 'urge' && !item.withdrawn"
              :disabled="loading || saving || uncertain"
              @click="withdraw(item)"
            >
              撤回本次催办
            </a-button>
          </li>
        </ul>
        <p v-if="candidates && !candidates.items.length">
          暂无沟通记录
        </p>
      </a-spin>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { formatDateTime as formatTime } from '@/utils/date'
import { useAuthStore } from '@/stores/auth'
import {
  CommunicationError,
  createCommunication,
  getCommunicationCandidates,
} from '@/api/caseCommunications'
import type {
  Communication,
  CommunicationCandidates,
  CommunicationCreate,
} from '@/api/caseCommunications'

const props = defineProps<{
  instituteId: string
  patientId: string
  visitId: string
  scene: 'running' | 'final'
  jobId: string
}>()
const emit = defineEmits<{ saved: [] }>()
const auth = useAuthStore()
const allowed = computed(() =>
  auth.userRoles.some((role) => ['admin', 'qc_manager', 'qc_staff'].includes(role)),
)
const open = ref(false),
  loading = ref(false),
  saving = ref(false),
  uncertain = ref(false)
const error = ref(''),
  content = ref(''),
  recipient = ref<string>(),
  action = ref<'urge' | 'opinion'>('urge')
const formModel = computed(() => ({
  action: action.value,
  recipient: recipient.value,
  content: content.value,
}))
const candidates = ref<CommunicationCandidates>()
let generation = 0
let pending: CommunicationCreate | undefined
const labels = { urge: '催办', opinion: '质控意见', withdraw: '撤回催办' }
const popupContainer = (trigger: HTMLElement) => trigger.parentElement || trigger
const doctorName = (id: string) =>
  candidates.value?.doctors.find((person) => person.id === id)?.name || id
const identity = () => ({
  institute_id: props.instituteId,
  patient_id: props.patientId,
  visit_id: props.visitId,
  root_job_id: props.jobId,
})
const matches = (item: Communication, payload: CommunicationCreate) =>
  !!item.id &&
  !!item.notification_id &&
  Object.entries(payload).every(([key, value]) => item[key as keyof Communication] === value)
async function load() {
  if (saving.value) return
  const token = ++generation
  loading.value = true
  error.value = ''
  candidates.value = undefined
  try {
    const data = await getCommunicationCandidates(identity())
    if (token !== generation) return
    if (
      Object.entries(identity()).some(
        ([key, value]) => data.source[key as keyof typeof data.source] !== value,
      ) ||
      !data.source.envelope_id ||
      !['running', 'final'].includes(data.source.scene) ||
      !data.source.rule_set_key ||
      !data.source.rule_set_version
    )
      throw new Error('病历来源已变化，请刷新病历')
    candidates.value = data
    if (recipient.value && !data.doctors.some((person) => person.id === recipient.value))
      recipient.value = undefined
    if (uncertain.value && pending && data.items.some((item) => matches(item, pending!))) {
      uncertain.value = false
      content.value = ''
      pending = undefined
      emit('saved')
    } else if (uncertain.value) error.value = '写入结果尚未确认，请继续刷新核对，勿重复发送'
  } catch (reason) {
    if (token === generation) {
      error.value = reason instanceof Error ? reason.message : '读取沟通失败'
      candidates.value = undefined
    }
  } finally {
    if (token === generation) loading.value = false
  }
}
function openForm() {
  open.value = true
  void load()
}
async function send(
  itemAction: Communication['action'],
  body: string,
  doctor: string,
  related?: string,
) {
  if (!candidates.value || saving.value || loading.value || uncertain.value) return
  const token = generation
  const payload: CommunicationCreate = {
    ...candidates.value.source,
    action: itemAction,
    content: body,
    recipient_id: doctor,
    request_id: crypto.randomUUID(),
    ...(related ? { related_event_id: related } : {}),
  }
  pending = payload
  saving.value = true
  error.value = ''
  try {
    const result = await createCommunication(payload)
    if (token !== generation) return
    if (!matches(result, payload)) throw new CommunicationError('保存结果与本次病历沟通不一致')
    content.value = ''
    pending = undefined
    emit('saved')
    saving.value = false
    await load()
  } catch (reason) {
    if (token === generation) {
      uncertain.value = reason instanceof CommunicationError ? reason.unknown : true
      error.value = `${reason instanceof Error ? reason.message : '发送失败'}${uncertain.value ? '；写入结果待核实，请刷新核对' : ''}`
    }
  } finally {
    if (token === generation) saving.value = false
  }
}
function save() {
  if (recipient.value && content.value.trim())
    void send(action.value, content.value.trim(), recipient.value)
}
function withdraw(item: Communication) {
  void send('withdraw', '撤回本次病历催办', item.recipient_id, item.id)
}
function reset() {
  generation += 1
  open.value = false
  saving.value = false
  loading.value = false
  uncertain.value = false
  candidates.value = undefined
  content.value = ''
  recipient.value = undefined
  pending = undefined
  error.value = ''
}
watch(
  () => [
    props.instituteId,
    props.patientId,
    props.visitId,
    props.scene,
    props.jobId,
    auth.user?.id,
    auth.user?.institute_id,
    auth.user?.department,
    ...auth.userRoles,
  ],
  reset,
)
onUnmounted(reset)
</script>

<style scoped>
.case-communication__context {
  color: var(--mq-text-secondary, #667085);
  overflow-wrap: anywhere;
}
.case-communication h3 {
  margin: 24px 0 8px;
  font-size: 16px;
}
.case-communication__history {
  margin: 0;
  padding: 0;
  list-style: none;
}
.case-communication__history li {
  padding: 14px 0;
  border-top: 1px solid var(--mq-border, #edf0f4);
}
.case-communication__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-size: 13px;
}
.case-communication__history p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 8px 0;
}
.case-communication__relation {
  color: var(--mq-text-secondary, #667085);
  font-size: 12px;
}
</style>
