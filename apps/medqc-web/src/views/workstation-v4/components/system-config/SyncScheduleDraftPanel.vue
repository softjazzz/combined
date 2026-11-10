<template>
  <section
    aria-labelledby="sync-drafts-title"
    class="sync-drafts"
  >
    <div class="pipeline-toolbar">
      <h3 id="sync-drafts-title">
        计划草稿
      </h3>
      <a-button
        :disabled="busy"
        @click="refresh"
      >
        读取计划草稿
      </a-button>
      <a-button
        :disabled="busy || !canSave || Boolean(pending)"
        @click="edit()"
      >
        新建禁用草稿
      </a-button>
    </div>
    <p>仅保存每日／每周回看设置，不开放启用或自动执行。已启用的服务端计划仅供查看。</p>
    <a-alert
      v-if="error"
      :message="error"
      type="warning"
      show-icon
    />
    <p
      v-if="saved"
      role="status"
    >
      草稿已保存且保持禁用，没有启动同步或质控。
    </p>
    <p v-if="rows !== null && !rows.length">
      暂无计划草稿。
    </p>
    <ul class="draft-list">
      <li
        v-for="row in rows"
        :key="row.schedule_id"
      >
        <strong>{{ row.config.frequency === 'daily' ? '每日' : '每周' }} {{ row.config.local_time }} · 回看 {{ row.config.window_days }} 天</strong>
        <span>版本 {{ row.version }} · {{ row.enabled ? '已启用（只读）' : '已禁用' }}</span>
        <a-button
          v-if="!row.enabled && canSave"
          :disabled="busy || Boolean(pending)"
          @click="edit(row)"
        >
          编辑禁用草稿
        </a-button>
      </li>
    </ul>
    <div
      v-if="editing"
      class="draft-editor"
    >
      <div class="pipeline-fields">
        <label>频率<select
          v-model="form.frequency"
          :disabled="locked"
        ><option value="daily">每日</option><option value="weekly">每周</option></select></label>
        <label>医院本地时间<input
          v-model="form.local_time"
          type="time"
          :disabled="locked"
        ></label>
        <label>回看天数<input
          v-model.number="form.window_days"
          type="number"
          min="1"
          :disabled="locked"
        ></label>
        <label v-if="form.frequency === 'weekly'">星期<select
          v-model.number="form.weekday"
          :disabled="locked"
        ><option
          v-for="(name, index) in weekdays"
          :key="index"
          :value="index"
        >{{ name }}</option></select></label>
      </div>
      <label>来源接口<a-select
        v-model:value="form.interfaces"
        mode="multiple"
        :disabled="locked"
        :options="catalog.interfaces.map(value => ({ value, label: value }))"
      /></label>
      <p v-if="pending">
        保存结果待确认，已锁定原草稿编号、版本和内容。
      </p>
      <p
        v-if="conflict"
        role="alert"
      >
        版本冲突：请核对服务器版本，再决定是否载入编辑。不会自动覆盖。
      </p>
      <div class="pipeline-toolbar">
        <a-button
          :disabled="busy || !canSave || conflict || !form.interfaces.length"
          @click="save"
        >
          {{ pending ? '使用原版本重试保存' : '保存禁用草稿' }}
        </a-button>
        <a-button
          v-if="pending"
          :disabled="busy"
          @click="loadLatest"
        >
          核对服务器版本
        </a-button>
        <a-button
          v-if="latest"
          :disabled="busy"
          @click="adoptLatest"
        >
          载入服务器版本
        </a-button>
        <a-button
          v-if="!pending"
          :disabled="busy"
          @click="editing = null"
        >
          关闭编辑
        </a-button>
      </div>
      <p v-if="latest">
        服务器版本 {{ latest.version }} · {{ latest.enabled ? '已启用，只读' : '已禁用' }} · {{ latest.config.frequency }} {{ latest.config.local_time }} · 回看 {{ latest.config.window_days }} 天 · {{ latest.config.request.interfaces.join('、') }}
      </p>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { dataPipelinesApi, type IndependentCatalog, type SyncSchedule, type ScheduleDraftConfig } from '@/api/dataPipelines'
const props = defineProps<{ catalog: IndependentCatalog }>()
const emit = defineEmits<{ lock: [value: boolean] }>()
const rows = ref<SyncSchedule[] | null>(null), busy = ref(false), error = ref(''), saved = ref(false)
const editing = ref<{ id: string; version: number | null } | null>(null)
const form = reactive<ScheduleDraftConfig>({ frequency: 'daily', local_time: '02:00', window_days: 1, weekday: 0, interfaces: [] })
const pending = ref<{ id: string; payload: { version: number | null; config: ScheduleDraftConfig } } | null>(null)
const latest = ref<SyncSchedule | null>(null), conflict = ref(false)
const weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const canSave = computed(() => props.catalog.session.permissions.includes('schedule') && props.catalog.session.features.schedule_drafts)
const locked = computed(() => busy.value || Boolean(pending.value))
watch(locked, value => emit('lock', value), { immediate: true })
let epoch = 0
function configOf(row: SyncSchedule): ScheduleDraftConfig {
  return { frequency: row.config.frequency, local_time: row.config.local_time, window_days: row.config.window_days,
    ...(row.config.frequency === 'weekly' ? { weekday: row.config.weekday } : {}), interfaces: [...row.config.request.interfaces] }
}
function edit(row?: SyncSchedule) {
  if (!canSave.value || busy.value || pending.value || row?.enabled) return
  editing.value = { id: row?.schedule_id || crypto.randomUUID(), version: row?.version ?? null }
  Object.assign(form, row ? configOf(row) : { frequency: 'daily', local_time: '02:00', window_days: 1, weekday: 0, interfaces: [] })
  latest.value = null; error.value = ''; saved.value = false; conflict.value = false
}
async function refresh() {
  const ticket = epoch
  busy.value = true; error.value = ''
  try { const value = await dataPipelinesApi.schedules(); if (ticket === epoch) rows.value = value }
  catch { if (ticket === epoch) error.value = '计划读取失败，保留上次结果。' }
  finally { if (ticket === epoch) busy.value = false }
}
async function save() {
  if (!editing.value || !canSave.value || busy.value || conflict.value) return
  const ticket = epoch
  pending.value ||= { id: editing.value.id, payload: { version: editing.value.version, config: {
    frequency: form.frequency, local_time: form.local_time, window_days: form.window_days,
    interfaces: [...form.interfaces], ...(form.frequency === 'weekly' ? { weekday: form.weekday } : {}),
  } } }
  busy.value = true; error.value = ''; saved.value = false
  try {
    const value = await dataPipelinesApi.saveDraft(pending.value.id, pending.value.payload)
    if (ticket !== epoch) return
    if (value.enabled || value.next_fire_at !== null) throw new Error('草稿状态未确认')
    rows.value = [value, ...(rows.value || []).filter(row => row.schedule_id !== value.schedule_id)]
    pending.value = null; editing.value = null; latest.value = null; saved.value = true
  } catch (cause) {
    if (ticket === epoch) {
      const status = isAxiosError(cause) ? cause.response?.status : undefined
      conflict.value = status === 409
      error.value = conflict.value ? '版本冲突，请先核对服务器版本。' : '保存尚未确认，请核对服务器版本；没有自动重试。'
      // 明确的权限/参数拒绝允许修正表单；超时与冲突保留完全相同的请求。
      if (status && [403, 404, 422].includes(status)) pending.value = null
    }
  } finally { if (ticket === epoch) busy.value = false }
}
async function loadLatest() {
  if (!pending.value || busy.value) return
  const ticket = epoch, id = pending.value.id
  busy.value = true
  try { const value = await dataPipelinesApi.schedule(id); if (ticket === epoch) latest.value = value }
  catch { if (ticket === epoch) error.value = '服务器版本未读到，原请求仍保留；请稍后核对。' }
  finally { if (ticket === epoch) busy.value = false }
}
function adoptLatest() {
  if (!latest.value || busy.value) return
  const value = latest.value
  pending.value = null; conflict.value = false
  editing.value = null
  if (!value.enabled) edit(value)
  else error.value = '服务器计划已启用，仅供查看，不能保存草稿覆盖。'
}
onUnmounted(() => { epoch++ })
</script>
<style scoped>
.sync-drafts { margin-top: var(--mq-space-6); border-top: 1px solid var(--mq-glass-border); padding-top: var(--mq-space-4); }
.pipeline-toolbar, .pipeline-fields { display: flex; flex-wrap: wrap; align-items: center; gap: var(--mq-space-3); }
.pipeline-fields label, .draft-editor > label { display: grid; gap: var(--mq-space-2); }
.draft-list { padding: 0; list-style: none; }
.draft-list li { display: flex; flex-wrap: wrap; align-items: center; gap: var(--mq-space-3); padding: var(--mq-space-3) 0; border-bottom: 1px solid var(--mq-glass-border); }
.draft-editor { display: grid; gap: var(--mq-space-4); margin-top: var(--mq-space-4); }
</style>
