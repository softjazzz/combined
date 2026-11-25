<template>
  <a-drawer
    :open="open"
    title="现代缺陷申诉"
    width="min(760px, 100vw)"
    :root-style="{ zIndex: 1400 }"
    :closable="!saving"
    :mask-closable="!saving"
    @close="emit('close')"
  >
    <section class="appeal-workflow" aria-label="现代缺陷申诉">
      <form v-if="source && doctor" class="appeal-form" @submit.prevent="create">
        <h3 class="mq-card__title">
          提交申诉 · {{ source.scene === 'running' ? '运行' : '终末' }} ·
          {{ source.target_kind === 'canonical_defect' ? '自动缺陷' : '人工缺陷' }}
        </h3>
        <p class="mq-mono appeal-identity">{{ source.visit_id }} · {{ source.target_id }}</p>
        <label class="mq-field"
          ><span class="mq-field__label">申诉原因</span>
          <textarea
            v-model="reason"
            class="mq-input"
            rows="3"
            minlength="10"
            maxlength="2000"
            placeholder="请输入申诉原因（至少 10 字）"
            :disabled="saving || uncertain"
            required
          />
          <span class="appeal-field-hint" data-testid="appeal-reason-hint">
            {{
              reason.trim().length >= 10
                ? `至少 10 字 · 当前已输入 ${reason.trim().length} 字`
                : `至少 10 字（当前 ${reason.trim().length}/10 字）`
            }}
          </span>
        </label>
        <button
          class="mq-btn mq-btn--primary"
          :disabled="saving || uncertain || reason.trim().length < 10"
        >
          提交申诉
        </button>
      </form>
      <div class="appeal-toolbar">
        <strong>待处理 {{ count ?? '未知' }}</strong>
        <label class="mq-field"
          ><span class="mq-field__label">质控场景</span>
          <select v-model="scene" class="mq-input" :disabled="saving" @change="query">
            <option value="">全部场景</option>
            <option value="running">运行</option>
            <option value="final">终末</option>
          </select></label
        >
        <label class="mq-field"
          ><span class="mq-field__label">申诉状态</span>
          <select v-model="state" class="mq-input" :disabled="saving" @change="query">
            <option value="open">待处理</option>
            <option value="">全部状态</option>
            <option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option>
          </select></label
        >
        <button class="mq-btn" :disabled="saving || loading" @click="refresh">
          <MqIcon name="sync" :size="16" />刷新核对
        </button>
      </div>
      <p v-if="error" class="appeal-error" role="alert">{{ error }}</p>
      <p v-if="notice" role="status">{{ notice }}</p>
      <p v-if="loading" role="status">正在核对申诉…</p>
      <template v-else>
        <ul class="appeal-list">
          <li v-for="item in items" :key="item.id">
            <button class="appeal-row" :disabled="saving" @click="show(item.id)">
              <span
                >{{ item.scene === 'running' ? '运行' : '终末' }} ·
                {{ item.target_kind === 'canonical_defect' ? '自动' : '人工' }} ·
                {{ item.visit_id }}</span
              >
              <span
                >{{ item.appellant_name }} · {{ item.target_id }}
                <span class="mq-status" :class="statusClass(item.status)">{{
                  labels[item.status]
                }}</span></span
              >
            </button>
          </li>
        </ul>
        <p v-if="!error && !items.length">没有符合条件的申诉</p>
        <nav v-if="total" class="appeal-toolbar" aria-label="申诉分页">
          <button class="mq-btn" :disabled="page === 1 || saving" @click="move(-1)">上一页</button>
          <span>第 {{ page }} 页 / {{ total }} 条</span>
          <button class="mq-btn" :disabled="page * 10 >= total || saving" @click="move(1)">
            下一页
          </button>
        </nav>
      </template>
      <article v-if="selected" class="appeal-detail" aria-label="申诉详情">
        <h3 class="mq-card__title">{{ selected.target_id }} · {{ labels[selected.status] }}</h3>
        <p>{{ selected.reason }}</p>
        <p class="mq-mono appeal-identity">
          {{ selected.institute_id }} / {{ selected.patient_id }} / {{ selected.visit_id }}
        </p>
        <p class="mq-mono appeal-identity">
          {{ selected.root_job_id }} / {{ selected.envelope_id }}
        </p>
        <p v-if="selected.resolution">处理意见：{{ selected.resolution }}</p>
        <form v-if="operations.length" class="appeal-form" @submit.prevent>
          <label class="mq-field"
            ><span class="mq-field__label">处理意见</span>
            <textarea
              v-model="comment"
              class="mq-input"
              rows="3"
              maxlength="2000"
              placeholder="请输入处理意见（至少 10 字）"
              :disabled="saving || uncertain"
            />
            <span class="appeal-field-hint" data-testid="appeal-comment-hint">
              {{
                comment.trim().length >= 10
                  ? `至少 10 字 · 当前已输入 ${comment.trim().length} 字`
                  : `至少 10 字（当前 ${comment.trim().length}/10 字）`
              }}
            </span>
          </label>
          <div class="appeal-toolbar">
            <button
              v-for="operation in operations"
              :key="operation.value"
              class="mq-btn"
              :class="{ 'mq-btn--primary': operation.value === 'approve' }"
              :disabled="saving || uncertain || comment.trim().length < 10"
              @click="act(operation.value)"
            >
              {{ operation.label }}
            </button>
          </div>
        </form>
        <h4>操作记录</h4>
        <ul>
          <li v-for="event in selected.events" :key="event.id">
            {{ actionLabels[event.action] || event.action }} · {{ event.reviewer_name }} · {{ event.comment
            }}<time class="appeal-time mq-mono">{{ formatTime(event.created_at) }}</time>
          </li>
        </ul>
      </article>
    </section>
  </a-drawer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'
import { parseQcTaskTime, QC_TASK_TIME_ZONE } from '@/views/workstation-v4/utils/qcTaskTime'
import {
  actOnModernAppeal,
  createModernAppeal,
  getModernAppeal,
  listModernAppeals,
  type AppealAction,
  type AppealDetail,
  type AppealState,
  type ModernAppeal,
} from '@/api/modernAppeals'
import type { Rectification } from '@/api/defectRectifications'

const props = defineProps<{ open: boolean; source?: Rectification | null; appealId?: string }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const auth = useAuthStore()
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
const doctor = computed(() => hasRole('doctor'))
const reviewer = computed(() =>
  ['admin', 'qc_manager', 'sync_admin', 'super_admin'].some((role) => hasRole(role)),
)
const labels: Record<AppealState, string> = {
  pending: '待审核',
  reviewing: '审核中',
  approved: '已通过',
  rejected: '已驳回',
  withdrawn: '已撤回',
  superseded: '已失效（重跑关闭）',
}
const actionLabels: Record<AppealAction, string> = {
  withdraw: '撤回申诉',
  approve: '审核通过',
  reject: '驳回申诉',
  close_stale: '重跑关闭',
  supersede: '新轮次替代关闭',
}
const statusClass = (status: AppealState) =>
  ({
    pending: 'mq-status--warning',
    reviewing: 'mq-status--info',
    approved: 'mq-status--success',
    rejected: 'mq-status--danger',
    withdrawn: 'mq-status--neutral',
    superseded: 'mq-status--neutral',
  })[status]
const items = ref<ModernAppeal[]>([]),
  selected = ref<AppealDetail | null>(null)
const count = ref<number | null>(null),
  total = ref(0),
  page = ref(1)
const scene = ref<'' | 'running' | 'final'>(''),
  state = ref<'' | 'open' | AppealState>('open')
const reason = ref(''),
  comment = ref(''),
  error = ref(''),
  notice = ref('')
const loading = ref(false),
  saving = ref(false),
  uncertain = ref(false)
let epoch = 0,
  listToken = 0,
  detailToken = 0
const operations = computed<Array<{ value: AppealAction; label: string }>>(() => {
  const row = selected.value
  if (!row || !['pending', 'reviewing'].includes(row.status)) return []
  if (doctor.value && row.appellant_id === auth.user?.id)
    return [{ value: 'withdraw', label: '撤回申诉' }]
  return reviewer.value && row.appellant_id !== auth.user?.id
    ? [
        { value: 'approve', label: '审核通过' },
        { value: 'reject', label: '驳回申诉' },
      ]
    : []
})
async function load() {
  const token = ++listToken
  loading.value = true
  items.value = []
  count.value = null
  total.value = 0
  try {
    const result = await listModernAppeals(
      state.value || undefined,
      scene.value || undefined,
      page.value,
    )
    if (token !== listToken) return
    items.value = result.items
    count.value = result.pending_count
    total.value = result.total
  } catch (e) {
    if (token === listToken) error.value = e instanceof Error ? e.message : '申诉待办不可用'
  } finally {
    if (token === listToken) loading.value = false
  }
}
async function show(id: string) {
  const token = ++detailToken
  selected.value = null
  comment.value = ''
  try {
    const result = await getModernAppeal(id)
    if (token === detailToken) selected.value = result
  } catch (e) {
    if (token === detailToken) error.value = e instanceof Error ? e.message : '申诉详情不可用'
  }
}
async function refresh() {
  if (saving.value) return
  error.value = ''
  const wasUncertain = uncertain.value
  const id = selected.value?.id
  await load()
  if (id) await show(id)
  uncertain.value = wasUncertain && !!error.value
}
function query() {
  selected.value = null
  ++detailToken
  page.value = 1
  error.value = ''
  void load()
}
function move(delta: number) {
  page.value += delta
  selected.value = null
  ++detailToken
  void load()
}
async function write(operation: () => Promise<ModernAppeal>) {
  if (saving.value || uncertain.value) return
  const token = epoch
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await operation()
    if (token !== epoch) return
    reason.value = ''
    notice.value = '申诉状态已更新'
    emit('changed')
    await load()
    await show(result.id)
  } catch (e) {
    if (token === epoch) {
      uncertain.value = true
      error.value = e instanceof Error ? e.message : '操作结果待核对'
    }
  } finally {
    if (token === epoch) saving.value = false
  }
}
function create() {
  if (!props.source || reason.value.trim().length < 10) return
  const id = props.source.id,
    value = reason.value.trim()
  void write(() => createModernAppeal(id, value))
}
function act(action: AppealAction) {
  const row = selected.value
  if (!row || comment.value.trim().length < 10) return
  const value = comment.value.trim()
  void write(() => actOnModernAppeal(row.id, row.status, action, value))
}
function reset() {
  ++epoch
  ++listToken
  ++detailToken
  items.value = []
  selected.value = null
  count.value = null
  total.value = 0
  reason.value = ''
  comment.value = ''
  error.value = ''
  notice.value = ''
  saving.value = false
  loading.value = false
  uncertain.value = false
}
watch(
  () => [props.open, props.appealId, auth.user?.id, auth.user?.roles, ...effectiveUserRoles.value],
  () => {
    reset()
    page.value = 1
    if (props.appealId) state.value = ''
    if (props.open) {
      void load()
      if (props.appealId) void show(props.appealId)
    }
  },
  { immediate: true, deep: true },
)
onUnmounted(reset)
</script>
<style scoped>
.appeal-workflow {
  display: grid;
  gap: 16px;
}
.appeal-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: end;
}
.appeal-form {
  display: grid;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--mq-border);
}
.appeal-form .mq-btn {
  justify-self: start;
}
.appeal-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.appeal-row {
  display: grid;
  gap: 6px;
  padding: 12px 0;
  border: 0;
  border-bottom: 1px solid var(--mq-border);
  background: transparent;
  color: inherit;
  text-align: left;
  width: 100%;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.appeal-detail {
  border-top: 1px solid var(--mq-border);
  padding-top: 16px;
}
.appeal-detail p,
.appeal-detail h3,
.appeal-detail li,
.appeal-identity {
  overflow-wrap: anywhere;
}
.appeal-error {
  color: var(--mq-danger);
}
.appeal-time {
  display: block;
  color: var(--mq-text-muted);
  font-size: 12px;
}
.appeal-field-hint {
  display: block;
  color: var(--mq-text-muted);
  font-size: 12px;
}
</style>
