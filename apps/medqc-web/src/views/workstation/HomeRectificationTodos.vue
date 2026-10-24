<template>
  <section v-if="allowed" class="rectification-todos">
    <header>
      <h2>{{ scope ? '该缺陷整改' : '缺陷整改待办' }}</h2>
      <a-select
        v-model:value="state"
        :options="states"
        style="width: 130px"
        @change="changeState"
      />
      <a-button :disabled="loading" aria-label="刷新整改待办" @click="load">
        <RefreshCw :size="16" />
      </a-button>
    </header>
    <a-alert v-if="error" :message="error" type="error" show-icon />
    <a-spin :spinning="loading">
      <ul>
        <li v-for="item in items" :key="item.id">
          <button type="button" @click="show(item.id)">
            <span>{{ item.department }} · {{ item.visit_id }} · {{ item.target_id }}</span>
            <span>{{ item.assignee_name }} · {{ labels[item.status] }}</span>
            <span>{{ item.requirement }}</span>
          </button>
        </li>
      </ul>
      <p v-if="!loading && !error && !items.length">
        {{ scope ? '该缺陷尚无整改记录' : '没有待处理整改' }}
      </p>
      <a-pagination
        v-if="!error && total"
        v-model:current="page"
        :total="total"
        :page-size="10"
        :show-size-changer="false"
        @change="load"
      />
    </a-spin>
    <a-drawer
      v-model:open="open"
      title="缺陷整改"
      width="min(560px, 100vw)"
      :root-style="{ zIndex: 1300 }"
    >
      <a-alert v-if="detailError" :message="detailError" type="error" show-icon />
      <a-button v-if="detailError" :disabled="saving" @click="activeId && show(activeId)">
        刷新核对
      </a-button>
      <template v-if="selected">
        <a-descriptions class="rectification-detail" :column="1" bordered>
          <a-descriptions-item label="就诊号">
            {{ selected.visit_id }}
          </a-descriptions-item>
          <a-descriptions-item label="缺陷">
            {{ selected.target_id }}
          </a-descriptions-item>
          <a-descriptions-item label="冻结结果">
            {{ selected.root_job_id }} / {{ selected.envelope_id }}
          </a-descriptions-item>
          <a-descriptions-item label="受领人">
            {{ selected.assignee_name }}
          </a-descriptions-item>
          <a-descriptions-item label="状态">
            {{ labels[selected.status] }}
          </a-descriptions-item>
          <a-descriptions-item label="整改要求">
            {{ selected.requirement }}
          </a-descriptions-item>
          <a-descriptions-item label="整改说明">
            {{ selected.submission || '尚未提交' }}
          </a-descriptions-item>
          <a-descriptions-item label="验收意见">
            {{ selected.review_comment || '尚未验收' }}
          </a-descriptions-item>
        </a-descriptions>
        <a-form v-if="actions.length" layout="vertical" class="rectification-todos__action">
          <a-form-item label="处理说明">
            <a-textarea v-model:value="comment" :rows="4" :maxlength="2000" />
          </a-form-item>
          <a-space wrap>
            <a-button
              v-for="action in actions"
              :key="action.value"
              :disabled="saving || uncertain || comment.trim().length < 10"
              @click="submit(action.value)"
            >
              {{ action.label }}
            </a-button>
          </a-space>
        </a-form>
        <h3>操作记录</h3>
        <a-alert v-if="comparisonError" :message="comparisonError" type="error" show-icon />
        <section v-if="comparison" class="document-comparison">
          <h3>派发时 / 本次提交时正文</h3>
          <p v-if="!comparison.available">
            {{ comparison.reason }}
          </p>
          <template v-else>
            <p>{{ comparison.before_at }} / {{ comparison.after_at }}</p>
            <p v-if="comparison.unavailable_documents">
              {{ comparison.unavailable_documents }} 份文书缺少稳定标识或完整正文，不可比较
            </p>
            <article v-for="document in comparison.documents" :key="document.key.join(':')">
              <h4>
                {{ document.before?.label || document.after?.label }} ·
                {{ comparisonStates[document.state] }}
              </h4>
              <template v-if="document.state === 'matched'">
                <div
                  v-for="field in compareFields(document.before!, document.after!)"
                  :key="field.key"
                  :class="['comparison-row', { changed: field.changed }]"
                >
                  <strong>{{ field.label }}</strong>
                  <pre>{{ field.before }}</pre>
                  <pre>{{ field.after }}</pre>
                </div>
              </template>
              <div v-else class="comparison-row">
                <pre>{{ document.before?.content || '无可比较正文' }}</pre>
                <pre>{{ document.after?.content || '无可比较正文' }}</pre>
              </div>
            </article>
          </template>
        </section>
        <a-timeline>
          <a-timeline-item v-for="event in selected.events" :key="event.id">
            {{ eventLabels[event.action] || event.action }} · {{ event.comment }}
            <div>{{ event.created_at }}</div>
            <a-button
              v-if="event.action === 'submit'"
              :loading="comparisonLoading"
              @click="compare(event.id)"
            >
              查看本次正文比较
            </a-button>
            <a-button
              v-if="manager && event.can_withdraw"
              :disabled="saving || uncertain || comment.trim().length < 10"
              @click="submit('withdraw_urge', event.id)"
            >
              撤回该催办
            </a-button>
          </a-timeline-item>
        </a-timeline>
      </template>
    </a-drawer>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  actOnRectification,
  getRectification,
  getRectificationComparison,
  type RectificationComparison,
  type RectificationDocumentSnapshot,
  listRectifications,
  type Rectification,
  type RectificationAction,
  type RectificationDetail,
  type RectificationState,
  type RectificationSource,
} from '@/api/defectRectifications'
const props = defineProps<{ scope?: RectificationSource; refreshKey?: number }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const manager = computed(() =>
  ['admin', 'qc_manager', 'qc_staff'].some((role) => auth.hasRole(role)),
)
const allowed = computed(() => manager.value || auth.hasRole('doctor'))
const labels: Record<RectificationState, string> = {
  pending: '待整改',
  submitted: '待验收',
  approved: '已通过',
  rejected: '已驳回',
}
const eventLabels: Record<string, string> = {
  assign: '派发',
  submit: '提交整改',
  approve: '验收通过',
  reject: '驳回整改',
  urge: '催办提醒',
  withdraw_urge: '撤回催办',
}
const states = [
  { value: '', label: '全部状态' },
  ...Object.entries(labels).map(([value, label]) => ({ value, label })),
]
const state = ref<RectificationState | ''>(
    props.scope ? '' : manager.value ? 'submitted' : 'pending',
  ),
  page = ref(1),
  total = ref(0)
const items = ref<Rectification[]>([]),
  selected = ref<RectificationDetail | null>(null)
const loading = ref(false),
  open = ref(false),
  saving = ref(false),
  uncertain = ref(false)
const error = ref(''),
  detailError = ref(''),
  comment = ref('')
const activeId = ref('')
const comparison = ref<RectificationComparison | null>(null)
const comparisonError = ref(''),
  comparisonLoading = ref(false)
let comparisonToken = 0
const comparisonStates = {
  added: '仅提交时快照存在',
  missing: '仅派发时快照存在',
  empty: '空正文不可比较',
  matched: '同文书',
}
function compareFields(
  before: RectificationDocumentSnapshot,
  after: RectificationDocumentSnapshot,
) {
  const index = (document: RectificationDocumentSnapshot) => {
    const fields = new Map<string, { label: string; text: string }>()
    for (const section of document.sections) {
      if (!section.source_field || fields.has(section.source_field)) return null
      fields.set(section.source_field, section)
    }
    return fields.size ? fields : null
  }
  const old = index(before),
    current = index(after)
  if (!old || !current)
    return [
      {
        key: 'content',
        label: '完整正文',
        before: before.content,
        after: after.content,
        changed: before.content !== after.content,
      },
    ]
  const fields = [...new Set([...old.keys(), ...current.keys()])].map((key) => ({
    key: `field:${key}`,
    label: old.get(key)?.label || current.get(key)?.label || key,
    before: old.get(key)?.text ?? '字段缺失',
    after: current.get(key)?.text ?? '字段缺失',
    changed: old.get(key)?.text !== current.get(key)?.text,
  }))
  return [
    ...fields,
    {
      key: 'content',
      label: '完整正文',
      before: before.content,
      after: after.content,
      changed: before.content !== after.content,
    },
  ]
}
async function compare(eventId: string) {
  if (!selected.value) return
  const token = ++comparisonToken
  comparison.value = null
  comparisonError.value = ''
  comparisonLoading.value = true
  try {
    const result = await getRectificationComparison(selected.value.id, eventId)
    if (token === comparisonToken) comparison.value = result
  } catch (e) {
    if (token === comparisonToken)
      comparisonError.value = e instanceof Error ? e.message : '文书比较不可用'
  } finally {
    if (token === comparisonToken) comparisonLoading.value = false
  }
}
function resetComparison() {
  ++comparisonToken
  comparison.value = null
  comparisonError.value = ''
  comparisonLoading.value = false
}
let listToken = 0,
  detailToken = 0
const actions = computed<Array<{ value: RectificationAction; label: string }>>(() => {
  const item = selected.value
  if (!item) return []
  const pending = item.status === 'pending' || item.status === 'rejected'
  if (item.assignee_id === auth.user?.id && auth.hasRole('doctor') && pending)
    return [{ value: 'submit', label: '提交整改' }]
  if (!manager.value || item.assignee_id === auth.user?.id) return []
  if (item.status === 'submitted')
    return [
      { value: 'approve', label: '验收通过' },
      { value: 'reject', label: '驳回' },
    ]
  return pending ? [{ value: 'urge', label: '催办' }] : []
})
function changeState() {
  page.value = 1
  void load()
}
async function load() {
  const token = ++listToken
  if (!allowed.value) return
  loading.value = true
  error.value = ''
  items.value = []
  total.value = 0
  try {
    const result = props.scope
      ? await listRectifications(state.value || undefined, page.value, props.scope)
      : await listRectifications(state.value || undefined, page.value)
    if (token !== listToken) return
    items.value = result.items
    total.value = result.total
  } catch (e) {
    if (token === listToken) error.value = e instanceof Error ? e.message : '整改待办不可用'
  } finally {
    if (token === listToken) loading.value = false
  }
}
async function show(id: string) {
  resetComparison()
  const token = ++detailToken
  activeId.value = id
  open.value = true
  selected.value = null
  detailError.value = ''
  comment.value = ''
  uncertain.value = false
  try {
    const result = await getRectification(id)
    if (
      props.scope &&
      Object.entries(props.scope).some(
        ([key, value]) => result[key as keyof RectificationSource] !== value,
      )
    )
      throw new Error('整改来源与所选缺陷不一致，请刷新核对')
    if (token === detailToken) selected.value = result
  } catch (e) {
    if (token === detailToken) detailError.value = e instanceof Error ? e.message : '整改详情不可用'
  }
}
async function submit(action: RectificationAction, urgeEventId?: string) {
  if (!selected.value || saving.value || uncertain.value || comment.value.trim().length < 10) return
  const item = selected.value,
    token = detailToken
  saving.value = true
  try {
    if (urgeEventId)
      await actOnRectification(item.id, item.version, action, comment.value.trim(), urgeEventId)
    else await actOnRectification(item.id, item.version, action, comment.value.trim())
    if (token !== detailToken) return
    saving.value = false
    await show(item.id)
    void load()
    emit('changed')
  } catch (e) {
    if (token === detailToken) {
      detailError.value = e instanceof Error ? e.message : '操作结果待核对'
      uncertain.value = true
    }
  } finally {
    if (token === detailToken) saving.value = false
  }
}
function reset() {
  resetComparison()
  ++listToken
  ++detailToken
  items.value = []
  selected.value = null
  open.value = false
  error.value = ''
  loading.value = false
  saving.value = false
}
watch(
  () => [auth.user?.id, auth.user?.roles, allowed.value],
  () => {
    reset()
    page.value = 1
    state.value = props.scope ? '' : manager.value ? 'submitted' : 'pending'
    if (allowed.value) void load()
  },
  { immediate: true, deep: true },
)
watch(open, (value) => {
  if (!value) {
    resetComparison()
    ++detailToken
    selected.value = null
    saving.value = false
  }
})
watch(
  () => [props.scope, props.refreshKey],
  () => {
    reset()
    page.value = 1
    state.value = props.scope ? '' : manager.value ? 'submitted' : 'pending'
    if (allowed.value) void load()
  },
  { deep: true },
)
onUnmounted(reset)
</script>
<style scoped>
.rectification-todos {
  padding: 24px;
  min-width: 0;
  color: var(--mq-text-primary);
}
header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}
h2 {
  font-size: 18px;
  margin: 0 auto 0 0;
}
ul {
  list-style: none;
  padding: 0;
}
li {
  border-bottom: 1px solid #e5e7eb;
}
li button {
  display: grid;
  gap: 6px;
  width: 100%;
  text-align: left;
  padding: 12px 0;
  background: transparent;
  border: 0;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.rectification-todos__action {
  margin: 20px 0;
}
.rectification-detail :deep(.ant-descriptions-item-label) {
  width: 104px;
  white-space: nowrap;
}
.rectification-detail :deep(.ant-descriptions-item-content) {
  overflow-wrap: anywhere;
}
.document-comparison article {
  border-top: 1px solid #e5e7eb;
}
.comparison-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
  padding: 8px 0;
}
.comparison-row strong {
  grid-column: 1 / -1;
}
.comparison-row pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 0;
  font: inherit;
}
.comparison-row.changed {
  background: #fff7d6;
}
@media (max-width: 480px) {
  .rectification-detail :deep(.ant-descriptions-item-label),
  .rectification-detail :deep(.ant-descriptions-item-content) {
    padding: 12px;
  }
  .comparison-row {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
