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
      wrap-class-name="mq-modal communication-dialog-modal"
      width="min(720px, 100vw)"
      :z-index="1200"
      :footer="null"
      :mask-closable="!saving"
      :closable="!saving"
      :keyboard="!saving"
      :style="{ top: '24px' }"
    >
      <template #title>
        <div class="communication-dialog__heading">
          <MqIconTile
            name="task"
            tone="brand"
            :size="36"
          />
          <div>
            <span>质控作业 · 病历反馈</span>
            <h2>病历沟通</h2>
          </div>
        </div>
      </template>
      <div class="communication-dialog">
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
        <a-spin
          :spinning="loading"
          tip="正在核对病历来源"
        >
          <a-form
            layout="vertical"
            :model="formModel"
            @finish="save"
          >
            <div class="communication-dialog__body">
              <div class="communication-dialog__object mq-soft">
                <div class="communication-dialog__object-head">
                  <MqIconTile
                    name="doc"
                    :size="36"
                    tone="brand"
                  />
                  <div>
                    <span class="communication-dialog__label">沟通病历</span>
                    <h3>{{ visitId }}</h3>
                  </div>
                </div>
                <div
                  v-if="candidates"
                  class="communication-dialog__context"
                >
                  <span>{{ candidates.source.scene === 'running' ? '运行病历' : '终末病历' }}</span><span>{{ candidates.department }}</span><span>规则版本 {{ candidates.source.rule_set_version }}</span>
                </div>
                <details
                  v-if="candidates"
                  class="communication-dialog__source"
                >
                  <summary>保存结果来源</summary>
                  <dl>
                    <div>
                      <dt>机构</dt>
                      <dd>{{ candidates.source.institute_id }}</dd>
                    </div>
                    <div>
                      <dt>患者</dt>
                      <dd>{{ candidates.source.patient_id }}</dd>
                    </div>
                    <div>
                      <dt>任务</dt>
                      <dd>{{ candidates.source.root_job_id }}</dd>
                    </div>
                    <div>
                      <dt>保存结果</dt>
                      <dd>{{ candidates.source.envelope_id }}</dd>
                    </div>
                    <div>
                      <dt>规则集</dt>
                      <dd>
                        {{ candidates.source.rule_set_key }} ·
                        {{ candidates.source.rule_set_version }}
                      </dd>
                    </div>
                  </dl>
                </details>
              </div>
              <div class="communication-dialog__fields">
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
                      candidates?.doctors.map((person) => ({
                        value: person.id,
                        label: person.name,
                      })) || []
                    "
                    :disabled="loading || saving || uncertain"
                  />
                </a-form-item>
              </div>
              <a-form-item :label="action === 'urge' ? '催办说明' : '意见正文'">
                <a-textarea
                  v-model:value="content"
                  :maxlength="2000"
                  :rows="4"
                  :disabled="loading || saving || uncertain"
                />
              </a-form-item>
              <section class="communication-dialog__history">
                <div class="communication-dialog__section-head">
                  <h3>
                    <MqIcon
                      name="history"
                      :size="18"
                    />操作历史
                  </h3>
                  <span>{{
                    candidates ? `${candidates.items.length} 条 · 北京时间` : '尚未核实'
                  }}</span>
                </div>
                <CaseCommunicationHistory
                  class="case-communication__history"
                  :items="candidates?.items || []"
                  :recipient-label="doctorName"
                >
                  <template #actions="{ event: item }">
                    <a-button
                      v-if="item.action === 'urge' && !item.withdrawn"
                      class="communication-dialog__withdraw"
                      :disabled="loading || saving || uncertain"
                      @click="withdraw(item)"
                    >
                      <template #icon>
                        <MqIcon
                          name="back"
                          :size="16"
                        />
                      </template>撤回本次催办
                    </a-button>
                  </template>
                </CaseCommunicationHistory>
                <p
                  v-if="candidates && !candidates.items.length"
                  class="communication-dialog__empty"
                >
                  暂无沟通记录
                </p>
              </section>
            </div>
            <div class="communication-dialog__actions">
              <a-button
                :disabled="saving"
                @click="open = false"
              >
                取消
              </a-button>
              <a-button
                type="primary"
                html-type="submit"
                :loading="saving"
                :disabled="loading || uncertain || !candidates || !recipient || !content.trim()"
              >
                <template #icon>
                  <MqIcon
                    name="task"
                    :size="16"
                  />
                </template>
                发送站内通知
              </a-button>
            </div>
          </a-form>
        </a-spin>
      </div>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import CaseCommunicationHistory from './CaseCommunicationHistory.vue'
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

<style scoped src="./styles/case-communication-dialog.css"></style>
