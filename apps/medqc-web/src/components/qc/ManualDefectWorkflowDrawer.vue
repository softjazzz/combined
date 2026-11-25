<template>
  <a-drawer
    :open="open"
    title="人工缺陷处理"
    width="min(820px, 100vw)"
    :root-style="{ zIndex: 1100 }"
    :closable="!saving && !pending"
    :mask-closable="!saving && !pending"
    @close="emit('close')"
  >
    <section class="manual-workflow" aria-label="人工缺陷处理">
      <div class="workflow-toolbar">
        <div class="mq-segmented" role="tablist" aria-label="人工缺陷工作">
          <button
            id="manual-defect-tab-entry"
            ref="entryTabRef"
            type="button"
            class="mq-segmented__item"
            role="tab"
            :aria-selected="tab === 'entry'"
            aria-controls="manual-defect-panel-entry"
            :tabindex="tab === 'entry' ? 0 : -1"
            :class="{ 'is-active': tab === 'entry' }"
            :disabled="saving || !!pending"
            @click="switchTab('entry')"
            @keydown="handleTabKeydown"
          >
            受领病例录入
          </button>
          <button
            v-if="canReview"
            id="manual-defect-tab-review"
            ref="reviewTabRef"
            type="button"
            class="mq-segmented__item"
            role="tab"
            :aria-selected="tab === 'review'"
            aria-controls="manual-defect-panel-review"
            :tabindex="tab === 'review' ? 0 : -1"
            :class="{ 'is-active': tab === 'review' }"
            :disabled="saving || !!pending"
            @click="switchTab('review')"
            @keydown="handleTabKeydown"
          >
            待审核 {{ count ?? '未知' }}
          </button>
        </div>
        <label class="mq-field"
          ><span class="mq-field__label">质控场景</span>
          <select v-model="scene" class="mq-input" :disabled="saving || !!pending" @change="query">
            <option value="all">全部场景</option>
            <option value="running">运行</option>
            <option value="final">终末</option>
          </select>
        </label>
        <button type="button" class="mq-btn" :disabled="busy || saving || !!pending" @click="reload()">
          <MqIcon name="sync" :size="16" />刷新
        </button>
      </div>
      <p v-if="error" class="workflow-error" role="alert">{{ error }}</p>
      <p v-if="notice" role="status">{{ notice }}</p>
      <p v-if="busy" role="status">正在核对人工缺陷…</p>
      <div
        id="manual-defect-panel-entry"
        role="tabpanel"
        aria-labelledby="manual-defect-tab-entry"
        class="workflow-panel"
        :hidden="tab !== 'entry'"
        :tabindex="tab === 'entry' ? 0 : -1"
      >
        <template v-if="!busy && tab === 'entry'">
        <label class="mq-field"
          ><span class="mq-field__label">本人受领病例</span>
          <select
            v-model="contextId"
            class="mq-input"
            :disabled="saving || !!pending"
            @change="selectContext"
          >
            <option value="">选择受领病例</option>
            <option
              v-for="item in contexts"
              :key="item.task_record_id"
              :value="item.task_record_id"
              :disabled="!item.available"
            >
              {{ item.task_name }} · {{ item.visit_id }} ·
              {{ item.available ? `第${item.run_number}次` : item.reason }}
            </option>
          </select>
        </label>
        <p v-if="!contexts.length">没有可录入的受领任务病历</p>
        <nav v-if="page > 1 || moreContexts" aria-label="受领病例分页" class="workflow-actions">
          <button
            type="button"
            class="mq-btn"
            :disabled="page === 1 || saving || !!pending"
            @click="movePage(-1)"
          >
            上一页
          </button>
          <span>第 {{ page }} 页</span
          ><button
            type="button"
            class="mq-btn"
            :disabled="!moreContexts || saving || !!pending"
            @click="movePage(1)"
          >
            下一页
          </button>
        </nav>
        <template v-if="context">
          <p class="mq-soft workflow-identity">
            {{ context.institute_id }} / {{ context.patient_id }} / {{ context.visit_id }}
          </p>
          <form class="workflow-form" @submit.prevent="submit">
            <label class="mq-field"
              ><span class="mq-field__label">问题名称</span
              ><input
                v-model="draft.rule_name"
                class="mq-input"
                maxlength="200"
                required
                :disabled="saving || !!pending"
            /></label>
            <label class="mq-field"
              ><span class="mq-field__label">问题描述</span
              ><textarea
                v-model="draft.description"
                class="mq-input"
                rows="3"
                maxlength="4000"
                required
                :disabled="saving || !!pending"
              />
            </label>
            <label class="mq-field"
              ><span class="mq-field__label">严重程度</span
              ><select v-model="draft.severity" class="mq-input" :disabled="saving || !!pending">
                <option value="info">提示</option>
                <option value="warning">警告</option>
                <option value="error">错误</option>
                <option value="critical">严重</option>
              </select></label
            >
            <label class="mq-field"
              ><span class="mq-field__label">整改建议</span
              ><textarea
                v-model="draft.suggestion"
                class="mq-input"
                rows="2"
                maxlength="2000"
                :disabled="saving || !!pending"
              />
            </label>
            <label class="mq-field"
              ><span class="mq-field__label">证据说明</span
              ><textarea
                v-model="draft.evidence"
                class="mq-input"
                rows="2"
                maxlength="2000"
                :disabled="saving || !!pending"
              />
            </label>
            <div class="workflow-actions">
              <button
                class="mq-btn mq-btn--primary"
                :disabled="saving || !draft.rule_name.trim() || !draft.description.trim()"
                type="submit"
              >
                {{ pending ? '按原请求重试提交' : '提交人工缺陷' }}
              </button>
              <button
                v-if="pending"
                class="mq-btn"
                type="button"
                :disabled="saving"
                @click="verify"
              >
                核对提交状态
              </button>
            </div>
          </form>
          <h3>本病例本人录入</h3>
          <p v-if="ownBusy" role="status">正在读取录入记录…</p>
          <p v-else-if="ownError" role="alert" class="workflow-error">{{ ownError }}</p>
          <ul v-else class="workflow-list">
            <li v-for="item in own" :key="item.id">
              <strong>{{ item.rule_name }}</strong
              ><span class="mq-status">{{ labels[item.manual_review_status] }}</span>
              <p>{{ item.description }}</p>
            </li>
            <li v-if="!own.length">暂无本人录入记录</li>
          </ul>
          <button
            v-if="own.length < ownTotal"
            type="button"
            class="mq-btn"
            :disabled="ownBusy"
            @click="loadOwn(true)"
          >
            加载更多
          </button>
        </template>
        </template>
      </div>
      <div
        v-if="canReview"
        id="manual-defect-panel-review"
        role="tabpanel"
        aria-labelledby="manual-defect-tab-review"
        class="workflow-panel"
        :hidden="tab !== 'review'"
        :tabindex="tab === 'review' ? 0 : -1"
      >
        <template v-if="!busy && tab === 'review'">
        <label class="mq-field"
          ><span class="mq-field__label">审核状态</span
          ><select v-model="status" class="mq-input" :disabled="saving" @change="query">
            <option value="pending">待审核</option>
            <option value="approved">审核通过</option>
            <option value="rejected">审核驳回</option>
          </select></label
        >
        <p>共 {{ total ?? '未知' }} 条 · 待审核 {{ count ?? '未知' }}</p>
        <ul class="workflow-list">
          <li v-for="item in queue" :key="item.id">
            <strong>{{ item.rule_name || '问题名称未知' }}</strong
            ><span class="mq-status">{{ labels[item.manual_review_status] }}</span>
            <p>{{ item.description || '描述未知' }}</p>
            <small>{{ item.institute_id }} / {{ item.patient_id }} / {{ item.visit_id }}</small>
            <template v-if="item.manual_review_status === 'pending'">
              <label class="mq-field"
                ><span class="mq-field__label">审核意见</span
                ><textarea
                  v-model="reasons[item.id]"
                  class="mq-input"
                  rows="2"
                  maxlength="2000"
                  :disabled="saving || self(item)"
                />
              </label>
              <p v-if="self(item)">本人录入的缺陷不能自审</p>
              <div class="workflow-actions">
                <button
                  type="button"
                  class="mq-btn mq-btn--primary"
                  :disabled="saving || self(item)"
                  @click="decide(item, 'approved')"
                >
                  审核通过
                </button>
                <button
                  type="button"
                  class="mq-btn"
                  :disabled="saving || self(item) || !reasons[item.id]?.trim()"
                  @click="decide(item, 'rejected')"
                >
                  驳回缺陷
                </button>
              </div>
            </template>
          </li>
          <li v-if="total === 0">没有匹配的人工缺陷</li>
        </ul>
        <nav aria-label="人工审核分页" class="workflow-actions">
          <button type="button" class="mq-btn" :disabled="page === 1 || saving" @click="movePage(-1)">
            上一页
          </button>
          <span>第 {{ page }} 页</span
          ><button
            type="button"
            class="mq-btn"
            :disabled="total === null || page * 20 >= total || saving"
            @click="movePage(1)"
          >
            下一页
          </button>
        </nav>
        </template>
      </div>
    </section>
  </a-drawer>
</template>
<script setup lang="ts">
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { effectiveRoles } from '@/utils/effectiveRoles'
import {
  createManualEntry,
  decideManualDefect,
  getEntryContexts,
  getManualPendingCount,
  getManualReviewQueue,
  getOwnManualEntries,
  type EntryContext,
  type EntryPayload,
  type ManualItem,
  type ManualScene,
  type ReviewStatus,
} from '@/api/manualDefectWorkflow'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const auth = useAuthStore()
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
const canReview = computed(() =>
  ['admin', 'qc_manager', 'sync_admin', 'super_admin'].some(
    (role) =>
      effectiveUserRoles.value.includes(role) ||
      (typeof auth.hasRole === 'function' && auth.hasRole(role)),
  ),
)
const tab = ref<'entry' | 'review'>('entry'),
  scene = ref<ManualScene>('all'),
  status = ref<ReviewStatus>('pending')
const page = ref(1),
  moreContexts = ref(false),
  count = ref<number | null>(null),
  total = ref<number | null>(null)
const busy = ref(false),
  saving = ref(false),
  error = ref(''),
  notice = ref(''),
  contextId = ref('')
const contexts = ref<EntryContext[]>([]),
  queue = ref<ManualItem[]>([]),
  own = ref<ManualItem[]>([])
const ownTotal = ref(0),
  ownBusy = ref(false),
  ownError = ref(''),
  pending = ref<EntryPayload | null>(null)
const reasons = reactive<Record<string, string>>({})
const defaults = () => ({
  rule_name: '',
  description: '',
  severity: 'warning' as EntryPayload['severity'],
  suggestion: '',
  evidence: '',
})
const draft = reactive(defaults())
const labels = { pending: '待审核', approved: '审核通过', rejected: '审核驳回' }
const context = computed(() =>
  contexts.value.find((item) => item.task_record_id === contextId.value && item.available),
)
const self = (item: ManualItem) =>
  !item.manual_created_by || item.manual_created_by === auth.user?.id
let generation = 0,
  ownGeneration = 0,
  writeGeneration = 0
const message = (e: unknown) => (e instanceof Error ? e.message : '操作失败，请刷新核对')

function query() {
  page.value = 1
  void reload()
}
function movePage(delta: number) {
  page.value += delta
  void reload()
}
async function reload() {
  const token = ++generation
  busy.value = true
  error.value = ''
  queue.value = []
  total.value = null
  count.value = null
  try {
    const pendingCount = canReview.value ? await getManualPendingCount(scene.value) : null
    if (token !== generation) return
    count.value = pendingCount
    if (tab.value === 'entry') {
      const result = await getEntryContexts(scene.value, page.value)
      if (token !== generation) return
      contexts.value = result.items
      moreContexts.value = result.has_more
      if (
        !contexts.value.some((item) => item.task_record_id === contextId.value && item.available)
      ) {
        contextId.value = ''
        own.value = []
        ++ownGeneration
      } else await loadOwn()
    } else {
      const result = await getManualReviewQueue(scene.value, status.value, page.value)
      if (token !== generation) return
      queue.value = result.items
      total.value = result.total
      if (result.total > 0 && page.value > Math.ceil(result.total / 20)) {
        page.value = Math.ceil(result.total / 20)
        await reload()
      }
    }
  } catch (e) {
    if (token === generation) {
      error.value = message(e)
      contexts.value = []
      count.value = null
    }
  } finally {
    if (token === generation) busy.value = false
  }
}
const entryTabRef = ref<HTMLButtonElement | null>(null)
const reviewTabRef = ref<HTMLButtonElement | null>(null)

function switchTab(value: 'entry' | 'review') {
  tab.value = value
  page.value = 1
  notice.value = ''
  void reload()
}
function handleTabKeydown(event: KeyboardEvent) {
  if (saving.value || !!pending.value) return
  const tabs: Array<'entry' | 'review'> = canReview.value ? ['entry', 'review'] : ['entry']
  if (tabs.length < 2) return
  const currentIndex = tabs.indexOf(tab.value)
  let nextIndex: number | null = null
  if (event.key === 'ArrowRight') {
    nextIndex = (currentIndex + 1) % tabs.length
  } else if (event.key === 'ArrowLeft') {
    nextIndex = (currentIndex - 1 + tabs.length) % tabs.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = tabs.length - 1
  }
  if (nextIndex === null) return
  event.preventDefault()
  const nextTab = tabs[nextIndex]
  if (nextTab !== tab.value) {
    switchTab(nextTab)
  }
  const targetEl = nextTab === 'entry' ? entryTabRef.value : reviewTabRef.value
  targetEl?.focus()
}
function selectContext() {
  Object.assign(draft, defaults())
  notice.value = ''
  void loadOwn()
}
async function loadOwn(more = false) {
  const selected = context.value
  const token = ++ownGeneration
  ownBusy.value = true
  ownError.value = ''
  if (!more) {
    own.value = []
    ownTotal.value = 0
  }
  try {
    if (!selected) return
    const result = await getOwnManualEntries(selected, more ? own.value.length : 0)
    if (token !== ownGeneration) return
    own.value = more ? [...own.value, ...result.items] : result.items
    ownTotal.value = result.total
  } catch (e) {
    if (token === ownGeneration) ownError.value = message(e)
  } finally {
    if (token === ownGeneration) ownBusy.value = false
  }
}
async function saved() {
  pending.value = null
  Object.assign(draft, defaults())
  notice.value = '人工缺陷已保存，等待独立审核'
  emit('changed')
  await reload()
  await loadOwn()
}
async function submit() {
  const selected = context.value
  if (!selected || !selected.run_number || saving.value) return
  pending.value ??= {
    ...draft,
    rule_name: draft.rule_name.trim(),
    description: draft.description.trim(),
    task_id: selected.task_id,
    task_record_id: selected.task_record_id,
    run_number: selected.run_number,
    defect_id: crypto.randomUUID(),
  }
  const token = generation,
    write = ++writeGeneration
  saving.value = true
  error.value = ''
  try {
    await createManualEntry(pending.value)
    if (token === generation) await saved()
  } catch (e) {
    if (token === generation) error.value = `${message(e)}；提交结果待核对，请核对或使用原请求重试`
  } finally {
    if (write === writeGeneration) saving.value = false
  }
}
async function verify() {
  const selected = context.value,
    payload = pending.value
  if (!selected || !payload || saving.value) return
  const token = generation,
    write = ++writeGeneration
  saving.value = true
  try {
    const result = await getOwnManualEntries(selected)
    if (token !== generation) return
    if (result.items.some((item) => item.id === payload.defect_id)) await saved()
    else error.value = '暂未核实保存结果，可使用原请求重试，不要另建重复缺陷'
  } catch (e) {
    if (token === generation) error.value = message(e)
  } finally {
    if (write === writeGeneration) saving.value = false
  }
}
async function decide(item: ManualItem, decision: 'approved' | 'rejected') {
  if (saving.value || self(item)) return
  const token = generation,
    write = ++writeGeneration
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    await decideManualDefect(item.id, decision, reasons[item.id]?.trim() || '')
    if (token !== generation) return
    notice.value = decision === 'approved' ? '审核通过已保存' : '审核驳回已保存'
    delete reasons[item.id]
    emit('changed')
    await reload()
  } catch (e) {
    if (token === generation) {
      error.value = message(e)
      queue.value = []
      count.value = null
      total.value = null
    }
  } finally {
    if (write === writeGeneration) saving.value = false
  }
}
watch(
  () => [props.open, auth.user?.id, JSON.stringify(auth.user?.roles), JSON.stringify(effectiveUserRoles.value)],
  () => {
    ++generation
    ++ownGeneration
    ++writeGeneration
    ownBusy.value = false
    ownError.value = ''
    contexts.value = []
    queue.value = []
    own.value = []
    contextId.value = ''
    pending.value = null
    saving.value = false
    notice.value = ''
    error.value = ''
    count.value = null
    total.value = null
    Object.assign(draft, defaults())
    for (const key of Object.keys(reasons)) delete reasons[key]
    if (props.open && auth.user?.id) {
      tab.value = 'entry'
      page.value = 1
      void reload()
    }
  },
  { immediate: true },
)
onUnmounted(() => {
  ++generation
  ++ownGeneration
  ++writeGeneration
})
</script>
<style scoped>
.manual-workflow,
.workflow-form,
.workflow-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
}
.workflow-panel[hidden] {
  display: none;
}
.workflow-toolbar,
.workflow-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: end;
}
.workflow-identity {
  padding: 12px;
  overflow-wrap: anywhere;
}
.workflow-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.workflow-list > li {
  padding: 16px 0;
  border-bottom: 1px solid var(--mq-glass-border);
  overflow-wrap: anywhere;
}
.workflow-list .mq-status {
  margin-left: 10px;
}
.workflow-list .mq-field {
  margin: 12px 0;
}
.workflow-error {
  color: var(--mq-danger-text);
  background: var(--mq-danger-bg);
  padding: 12px;
  border-radius: var(--mq-radius-control);
}
.mq-input {
  width: 100%;
  min-width: 0;
}
@media (max-width: 480px) {
  .workflow-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .mq-segmented {
    display: flex;
  }
  .mq-segmented__item {
    flex: 1;
  }
}
</style>
