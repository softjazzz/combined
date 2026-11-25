<template>
  <section v-if="allowed" class="rectification-todos" :class="{ 'mq-page': !scope }">
    <header class="rectification-todos__header" :class="{ 'mq-page-head': !scope }">
      <div class="rectification-heading mq-page-head__copy">
        <span v-if="!scope" class="mq-page-eyebrow">质控作业 · 整改处理</span>
        <h2 class="rectification-heading__title" :class="scope ? 'mq-card__title' : 'mq-page-title'">
          {{ scope ? '该缺陷整改' : '缺陷整改待办' }}
        </h2>
      </div>
      <div class="mq-page-head__actions rectification-todos__actions">
        <button v-if="!scope && manager" class="mq-btn" type="button" @click="manualOpen = true">
          <MqIcon name="task" :size="16" />人工缺陷处理
        </button>
        <button v-if="!scope && appealAllowed" class="mq-btn" type="button" @click="openAppeals()">
          <MqIcon name="task" :size="16" />申诉处理
        </button>
        <button v-if="!scope && manager" class="mq-btn" type="button" @click="reviewOpen = true">
          <MqIcon name="task" :size="16" />病历审核
        </button>
        <router-link v-if="!scope && hasRole('doctor')" class="mq-btn" to="/workstation-v5/case-communications">
          <MqIcon name="task" :size="16" />病历沟通
        </router-link>
        <router-link
          v-if="!scope && hasRole('doctor')"
          class="mq-btn"
          to="/workstation-v5/worklist?assist=message"
          >消息面板</router-link
        >
        <label class="sr-only" :for="scope ? 'defect-rectification-status' : 'rectification-status'"
          >整改状态</label
        >
        <a-select
          :id="scope ? 'defect-rectification-status' : 'rectification-status'"
          :value="state"
          :get-popup-container="popupContainer"
          :options="states"
          style="width: 130px"
          @change="changeState"
        />
        <a-button
          class="rectification-todos__refresh"
          shape="circle"
          :disabled="loading"
          aria-label="刷新整改待办"
          @click="load"
        >
          <template #icon>
            <MqIcon name="sync" :size="16" />
          </template>
        </a-button>
      </div>
    </header>
    <p v-if="error" class="state-error" role="alert">
      <MqIcon name="issue" :size="16" />{{ error }}
    </p>
    <a-spin :spinning="loading">
      <ul class="rectification-task-list" :class="{ 'mq-card': !scope && items.length > 0 }">
        <li v-for="item in items" :key="item.id">
          <button type="button" @click="show(item.id)">
            <span>{{ item.department }} · {{ item.visit_id }} · {{ item.target_id }}</span>
            <span
              >{{ item.assignee_name }} ·
              <span class="mq-status" :class="statusClass(item.status)">{{
                labels[item.status]
              }}</span></span
            >
            <span class="rectification-task-requirement">{{ item.requirement }}</span>
          </button>
        </li>
      </ul>
      <p v-if="!loading && !error && !items.length" class="rectification-empty">
        {{ scope ? '该缺陷尚无整改记录' : '没有待处理整改' }}
      </p>
      <a-pagination
        v-if="!error && total"
        :current="page"
        :total="total"
        :page-size="10"
        :show-size-changer="false"
        @change="handlePageChange"
      />
    </a-spin>
    <ManualDefectWorkflowDrawer
      v-if="!scope && manager && manualOpen"
      :open="manualOpen"
      @close="manualOpen = false"
      @changed="emit('changed')"
    />
    <ModernAppealWorkflowDrawer
      v-if="appealOpen"
      :open="appealOpen"
      :source="appealSource"
      :appeal-id="appealId"
      @close="closeAppeals"
      @changed="emit('changed')"
    />
    <RecordReviewWorkflowDrawer
      v-if="!scope && manager && reviewOpen"
      :open="reviewOpen"
      @close="reviewOpen = false"
      @changed="emit('changed')"
    />
    <a-drawer
      v-model:open="open"
      title="缺陷整改"
      width="min(560px, 100vw)"
      :root-style="{ zIndex: 1300 }"
      root-class-name="rectification-detail-drawer"
    >
      <p v-if="detailError" class="state-error" role="alert">
        <MqIcon name="issue" :size="16" />{{ detailError }}
      </p>
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
            <span class="mq-status" :class="statusClass(selected.status)">{{
              labels[selected.status]
            }}</span>
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
        <button
          v-if="
            hasRole('doctor') &&
            selected.assignee_id === auth.user?.id &&
            ['running', 'final'].includes(selected.scene)
          "
          class="mq-btn"
          type="button"
          @click="openAppeals(selected)"
        >
          申诉该缺陷
        </button>
        <a-form v-if="showCommentForm" layout="vertical" class="rectification-todos__action">
          <a-form-item label="处理说明">
            <a-textarea
              v-model:value="comment"
              :rows="4"
              :maxlength="2000"
              placeholder="请输入处理说明（至少 10 字）"
            />
            <p class="rectification-comment-hint" data-testid="rectification-comment-hint">
              {{
                commentLength >= 10
                  ? `至少 10 字 · 当前已输入 ${commentLength} 字`
                  : `至少 10 字（当前 ${commentLength}/10 字）`
              }}
            </p>
          </a-form-item>
          <a-space v-if="actions.length" wrap>
            <a-button
              v-for="action in actions"
              :key="action.value"
              :type="
                action.value === 'submit' || action.value === 'approve' ? 'primary' : 'default'
              "
              :danger="action.value === 'reject'"
              :disabled="saving || uncertain || commentLength < 10"
              @click="submit(action.value)"
            >
              {{ action.label }}
            </a-button>
          </a-space>
        </a-form>
        <h3 class="rectification-section-title">操作记录</h3>
        <p v-if="comparisonError" class="state-error" role="alert">
          <MqIcon name="issue" :size="16" />{{ comparisonError }}
        </p>
        <section v-if="comparison" class="document-comparison">
          <h3 class="rectification-section-title">派发时 / 本次提交时正文</h3>
          <p v-if="!comparison.available">
            {{ comparison.reason }}
          </p>
          <template v-else>
            <p>{{ formatTime(comparison.before_at) }} / {{ formatTime(comparison.after_at) }}</p>
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
            <div class="rectification-event-time mq-mono">
              {{ formatTime(event.created_at) }}
            </div>
            <a-button
              v-if="event.action === 'submit'"
              :loading="comparisonLoading"
              @click="compare(event.id)"
            >
              查看本次正文比较
            </a-button>
            <a-button
              v-if="canWithdrawUrge(event)"
              :disabled="saving || uncertain || commentLength < 10"
              @click="submit('withdraw_urge', event.id)"
            >
              撤回该催办
            </a-button>
          </a-timeline-item>
        </a-timeline>
      </template>
    </a-drawer>
  </section>
  <section
    v-else
    class="rectification-todos rectification-todos--denied"
    :class="{ 'mq-page': !scope }"
    role="status"
    aria-label="无权访问缺陷整改待办"
  >
    <header v-if="!scope" class="rectification-todos__header mq-page-head">
      <div class="rectification-heading mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 整改处理</span>
        <h2 class="rectification-heading__title mq-page-title">缺陷整改待办</h2>
      </div>
    </header>
    <div class="rectification-empty" :class="{ 'mq-card': !scope }">
      当前账号无权访问缺陷整改待办，请联系管理员核对角色权限。
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import * as vueRouter from 'vue-router'
import MqIcon from '@/components/icons/MqIcon.vue'
import ManualDefectWorkflowDrawer from '@/components/qc/ManualDefectWorkflowDrawer.vue'
import ModernAppealWorkflowDrawer from '@/components/qc/ModernAppealWorkflowDrawer.vue'
import RecordReviewWorkflowDrawer from '@/components/qc/RecordReviewWorkflowDrawer.vue'
import { useAuthStore } from '@/stores/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'
import { parseQcTaskTime, QC_TASK_TIME_ZONE } from '@/views/workstation-v4/utils/qcTaskTime'
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
function safeUseRoute() {
  try {
    return typeof vueRouter.useRoute === 'function' ? vueRouter.useRoute() : undefined
  } catch {
    return undefined
  }
}
function safeUseRouter() {
  try {
    return typeof vueRouter.useRouter === 'function' ? vueRouter.useRouter() : undefined
  } catch {
    return undefined
  }
}
const route = safeUseRoute()
const router = safeUseRouter()
const manualOpen = ref(false)
const reviewOpen = ref(false)
const appealOpen = ref(false),
  appealSource = ref<Rectification | null>(null)
const appealId = ref<string>()
let disposed = false
const shanghaiDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: QC_TASK_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})
function formatTime(value?: string | null): string {
  if (!value) return '时间未知'
  const parsed = parseQcTaskTime(value)
  if (!parsed) return value
  return shanghaiDateTimeFormatter.format(parsed)
}
const effectiveUserRoles = computed(() => {
  const raw = Array.isArray(auth.userRoles)
    ? auth.userRoles
    : Array.isArray(auth.user?.roles)
      ? auth.user.roles
      : auth.user?.role
        ? [auth.user.role]
        : []
  return effectiveRoles(raw)
})
const hasRole = (role: string) =>
  effectiveUserRoles.value.includes(role) ||
  (typeof auth.hasRole === 'function' && auth.hasRole(role))
const appealAllowed = computed(() =>
  ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin'].some((role) => hasRole(role)),
)
function clearRouteQueryKeys(...keys: string[]) {
  if (props.scope || disposed || !route || typeof router?.replace !== 'function') return
  const hasAny = keys.some((key) => route.query[key] !== undefined)
  if (!hasAny) return
  const nextQuery = { ...route.query }
  for (const key of keys) delete nextQuery[key]
  void router.replace({ path: route.path, query: nextQuery })
}
function openAppeals(source: Rectification | null = null) {
  appealId.value = undefined
  appealSource.value = source
  open.value = false
  appealOpen.value = true
}
function closeAppeals() {
  appealOpen.value = false
  appealId.value = undefined
  appealSource.value = null
  clearRouteQueryKeys('appeal_id')
}
const popupContainer = (trigger: HTMLElement) => trigger.parentElement || trigger
const manager = computed(() =>
  ['admin', 'qc_manager', 'qc_staff', 'sync_admin', 'super_admin'].some((role) => hasRole(role)),
)
const allowed = computed(() => manager.value || hasRole('doctor'))
const labels: Record<RectificationState, string> = {
  pending: '待整改',
  submitted: '待验收',
  approved: '已通过',
  rejected: '已驳回',
}
const statusClasses: Record<RectificationState, string> = {
  pending: 'mq-status--warning',
  submitted: 'mq-status--info',
  approved: 'mq-status--success',
  rejected: 'mq-status--danger',
}
const statusClass = (state: RectificationState) => statusClasses[state]
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
const VALID_STATES = new Set<RectificationState>(['pending', 'submitted', 'approved', 'rejected'])
function normalizeStateValue(value: unknown): RectificationState | '' {
  if (typeof value !== 'string') return ''
  const normalized = value.trim()
  if (!normalized || normalized === 'all') return ''
  return VALID_STATES.has(normalized as RectificationState)
    ? (normalized as RectificationState)
    : ''
}
function defaultState(): RectificationState | '' {
  return props.scope ? '' : manager.value ? 'submitted' : 'pending'
}
function readStateFromQuery(): RectificationState | '' {
  if (props.scope || !route) return defaultState()
  const raw = Array.isArray(route.query.status) ? route.query.status[0] : route.query.status
  if (typeof raw !== 'string') return defaultState()
  const normalized = raw.trim()
  if (normalized === 'all') return ''
  if (VALID_STATES.has(normalized as RectificationState)) return normalized as RectificationState
  return defaultState()
}
function readPageFromQuery(): number {
  if (props.scope || !route) return 1
  const raw = Array.isArray(route.query.page) ? route.query.page[0] : route.query.page
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1
}
const state = ref<RectificationState | ''>(readStateFromQuery()),
  page = ref(readPageFromQuery()),
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
const commentLength = computed(() => comment.value.trim().length)
function canWithdrawUrge(event: RectificationDetail['events'][number]): boolean {
  return Boolean(
    manager.value &&
      selected.value &&
      selected.value.assignee_id !== auth.user?.id &&
      event.can_withdraw,
  )
}
const actions = computed<Array<{ value: RectificationAction; label: string }>>(() => {
  const item = selected.value
  if (!item) return []
  const pending = item.status === 'pending' || item.status === 'rejected'
  if (item.assignee_id === auth.user?.id && hasRole('doctor') && pending)
    return [{ value: 'submit', label: '提交整改' }]
  if (!manager.value || item.assignee_id === auth.user?.id) return []
  if (item.status === 'submitted')
    return [
      { value: 'approve', label: '验收通过' },
      { value: 'reject', label: '驳回' },
    ]
  return pending ? [{ value: 'urge', label: '催办' }] : []
})
const hasWithdrawableUrge = computed(() =>
  Boolean(selected.value?.events.some((event) => canWithdrawUrge(event))),
)
const showCommentForm = computed(() => actions.value.length > 0 || hasWithdrawableUrge.value)
let routeSyncToken = 0
let pendingRouteSync: { state: RectificationState | ''; page: number } | null = null
async function applyFilters(nextState: RectificationState | '', nextPage: number) {
  if (disposed || !allowed.value) return
  if (props.scope || !route || typeof router?.replace !== 'function') {
    state.value = nextState
    page.value = nextPage
    void load()
    return
  }
  const nextStatus = nextState === '' ? 'all' : nextState
  const nextPageQuery = nextPage > 1 ? String(nextPage) : undefined
  const curStatus = Array.isArray(route.query.status) ? route.query.status[0] : route.query.status
  const curPage = Array.isArray(route.query.page) ? route.query.page[0] : route.query.page

  state.value = nextState
  page.value = nextPage

  if (curStatus === nextStatus && curPage === nextPageQuery) {
    void load()
    return
  }

  const token = ++routeSyncToken
  pendingRouteSync = { state: nextState, page: nextPage }
  const nextQuery = { ...route.query }
  nextQuery.status = nextStatus
  if (nextPageQuery) nextQuery.page = nextPageQuery
  else delete nextQuery.page

  try {
    await router.replace({ path: route.path, query: nextQuery })
  } finally {
    if (token === routeSyncToken) {
      pendingRouteSync = null
    }
  }

  if (disposed || token !== routeSyncToken || !allowed.value) return
  void load()
}
function changeState(nextValue?: unknown) {
  const nextState = normalizeStateValue(nextValue)
  if (nextState === state.value && page.value === 1) return
  void applyFilters(nextState, 1)
}
function handlePageChange(nextPage: number) {
  if (!Number.isInteger(nextPage) || nextPage < 1) return
  if (nextPage === page.value) return
  void applyFilters(state.value, nextPage)
}
async function load() {
  const token = ++listToken
  if (!allowed.value) return
  loading.value = true
  error.value = ''
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
  reviewOpen.value = false
  appealId.value = undefined
  appealOpen.value = false
  appealSource.value = null
  manualOpen.value = false
  resetComparison()
  ++listToken
  ++detailToken
  ++routeSyncToken
  pendingRouteSync = null
  items.value = []
  selected.value = null
  open.value = false
  error.value = ''
  loading.value = false
  saving.value = false
}
const authIdentityKey = computed(() =>
  [
    auth.user?.id ?? '',
    auth.user?.role ?? '',
    Array.isArray(auth.user?.roles) ? auth.user.roles.join(',') : '',
    effectiveUserRoles.value.join(','),
    allowed.value ? '1' : '0',
  ].join('|'),
)
let authInitialized = false
watch(
  authIdentityKey,
  () => {
    reset()
    if (!authInitialized) {
      authInitialized = true
      state.value = readStateFromQuery()
      page.value = readPageFromQuery()
    } else {
      page.value = 1
      state.value = defaultState()
    }
    if (allowed.value) void load()
  },
  { immediate: true },
)
watch(open, (value) => {
  if (!value) {
    resetComparison()
    ++detailToken
    selected.value = null
    saving.value = false
    clearRouteQueryKeys('rectification_id')
  }
})
watch(
  () => [route?.query?.status, route?.query?.page],
  () => {
    if (props.scope || !allowed.value || pendingRouteSync) return
    const nextState = readStateFromQuery()
    const nextPage = readPageFromQuery()
    if (nextState === state.value && nextPage === page.value) return
    state.value = nextState
    page.value = nextPage
    void load()
  },
)
watch(
  () => [props.scope, props.refreshKey],
  () => {
    reset()
    page.value = 1
    state.value = defaultState()
    if (allowed.value) void load()
  },
  { deep: true },
)
onUnmounted(() => {
  disposed = true
  reset()
})
watch(
  () => [route?.query.rectification_id, route?.query.appeal_id, auth.user?.id],
  () => {
    if (props.scope) return
    const rectification = route?.query.rectification_id,
      appeal = route?.query.appeal_id
    if (!rectification && !appeal) return
    if (
      (rectification && appeal) ||
      [rectification, appeal].some(
        (value) =>
          value !== undefined && (typeof value !== 'string' || !value.trim() || value.length > 36),
      )
    ) {
      error.value = '消息处理对象无效，请从消息面板重新打开'
      return
    }
    if (typeof rectification === 'string') void show(rectification)
    if (typeof appeal === 'string' && appealAllowed.value) {
      appealSource.value = null
      appealId.value = appeal
      appealOpen.value = true
    }
  },
  { immediate: true },
)
</script>
<style scoped src="./styles/rectification-todos.css"></style>
