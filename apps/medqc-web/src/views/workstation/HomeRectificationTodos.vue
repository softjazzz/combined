<template>
  <section v-if="allowed" class="rectification-todos">
    <header>
      <h2>缺陷整改待办</h2>
      <a-select
        v-model:value="state"
        :options="states"
        style="width: 130px"
        @change="changeState"
      />
      <a-button :disabled="loading" aria-label="刷新整改待办" @click="load"
        ><RefreshCw :size="16"
      /></a-button>
    </header>
    <a-alert v-if="error" :message="error" type="error" show-icon />
    <a-spin :spinning="loading">
      <ul>
        <li v-for="item in items" :key="item.id">
          <button @click="show(item.id)">
            <span>{{ item.department }} · {{ item.visit_id }} · {{ item.target_id }}</span>
            <span>{{ item.assignee_name }} · {{ labels[item.status] }}</span>
            <span>{{ item.requirement }}</span>
          </button>
        </li>
      </ul>
      <p v-if="!loading && !error && !items.length">没有待处理整改</p>
      <a-pagination
        v-if="!error && total"
        v-model:current="page"
        :total="total"
        :page-size="10"
        :show-size-changer="false"
        @change="load"
      />
    </a-spin>
    <a-drawer v-model:open="open" title="缺陷整改" width="min(560px, 100vw)">
      <a-alert v-if="detailError" :message="detailError" type="error" show-icon />
      <a-button v-if="detailError" :disabled="saving" @click="activeId && show(activeId)"
        >刷新核对</a-button
      >
      <template v-if="selected">
        <a-descriptions :column="1" bordered>
          <a-descriptions-item label="就诊号">{{ selected.visit_id }}</a-descriptions-item>
          <a-descriptions-item label="缺陷">{{ selected.target_id }}</a-descriptions-item>
          <a-descriptions-item label="受领人">{{ selected.assignee_name }}</a-descriptions-item>
          <a-descriptions-item label="状态">{{ labels[selected.status] }}</a-descriptions-item>
          <a-descriptions-item label="整改要求">{{ selected.requirement }}</a-descriptions-item>
          <a-descriptions-item label="整改说明">{{
            selected.submission || '尚未提交'
          }}</a-descriptions-item>
          <a-descriptions-item label="验收意见">{{
            selected.review_comment || '尚未验收'
          }}</a-descriptions-item>
        </a-descriptions>
        <a-form v-if="actions.length" layout="vertical" class="rectification-todos__action">
          <a-form-item label="处理说明"
            ><a-textarea v-model:value="comment" :rows="4" :maxlength="2000"
          /></a-form-item>
          <a-space wrap>
            <a-button
              v-for="action in actions"
              :key="action.value"
              :disabled="saving || uncertain || comment.trim().length < 10"
              @click="submit(action.value)"
              >{{ action.label }}</a-button
            >
          </a-space>
        </a-form>
        <h3>操作记录</h3>
        <a-timeline>
          <a-timeline-item v-for="event in selected.events" :key="event.id">
            {{ eventLabels[event.action] || event.action }} · {{ event.comment }}
            <div>{{ event.created_at }}</div>
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
  listRectifications,
  type Rectification,
  type RectificationAction,
  type RectificationDetail,
  type RectificationState,
} from '@/api/defectRectifications'
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
}
const states = Object.entries(labels).map(([value, label]) => ({ value, label }))
const state = ref<RectificationState>('pending'),
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
    const result = await listRectifications(state.value, page.value)
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
  const token = ++detailToken
  activeId.value = id
  open.value = true
  selected.value = null
  detailError.value = ''
  comment.value = ''
  uncertain.value = false
  try {
    const result = await getRectification(id)
    if (token === detailToken) selected.value = result
  } catch (e) {
    if (token === detailToken) detailError.value = e instanceof Error ? e.message : '整改详情不可用'
  }
}
async function submit(action: RectificationAction) {
  if (!selected.value || saving.value || uncertain.value || comment.value.trim().length < 10) return
  const item = selected.value,
    token = detailToken
  saving.value = true
  try {
    await actOnRectification(item.id, item.version, action, comment.value.trim())
    if (token !== detailToken) return
    saving.value = false
    await show(item.id)
    void load()
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
    if (allowed.value) void load()
  },
  { immediate: true, deep: true },
)
watch(open, (value) => {
  if (!value) {
    ++detailToken
    selected.value = null
    saving.value = false
  }
})
onUnmounted(reset)
</script>
<style scoped>
.rectification-todos {
  padding: 20px 0;
  border-top: 1px solid #e5e7eb;
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
</style>
