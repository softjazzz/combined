<template>
  <section aria-labelledby="registration-queue-title">
    <header class="accounts-head">
      <h2 id="registration-queue-title" class="mq-card__title">注册审批</h2>
      <button type="button" class="mq-btn" :disabled="loading || saving" @click="load(page)">
        <RefreshCw :size="16" />刷新
      </button>
    </header>
    <form class="accounts-filters" @submit.prevent="load(1)">
      <label class="mq-field"
        ><span class="mq-field__label">申请状态</span
        ><select
          v-model="state"
          class="mq-input"
          aria-label="申请状态"
          :disabled="loading || saving"
        >
          <option value="pending">待审批</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
        </select></label
      >
      <button type="submit" class="mq-btn" :disabled="loading || saving">
        <Search :size="16" />查询
      </button>
    </form>
    <p v-if="error" class="accounts-error" role="alert">{{ error }}</p>
    <div class="accounts-table registration-table" :aria-busy="loading">
      <table class="mq-table">
        <thead>
          <tr>
            <th>申请人</th>
            <th>用户名</th>
            <th>申请机构 / 科室</th>
            <th>状态</th>
            <th>提交时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6" class="accounts-empty">正在读取注册申请</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="6" class="accounts-empty">
              {{ error ? '申请未能加载' : '暂无匹配申请' }}
            </td>
          </tr>
          <tr v-for="row in loading ? [] : rows" :key="row.user_id">
            <td>
              <strong>{{ row.display_name }}</strong
              ><small>{{ row.email }}</small>
            </td>
            <td class="mq-mono">{{ row.username }}</td>
            <td>
              {{ row.requested_institute_id }}<small>{{ row.requested_department }}</small>
            </td>
            <td>
              <span class="mq-status" :class="statusClass(row.status)">{{
                statusName(row.status)
              }}</span>
            </td>
            <td>{{ formatTime(row.submitted_at) }}</td>
            <td>
              <button
                type="button"
                class="mq-btn"
                :disabled="saving"
                :aria-label="`查看申请${row.display_name}`"
                @click="open(row.user_id)"
              >
                <ClipboardCheck :size="16" />{{ row.status === 'pending' ? '审批' : '详情' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer class="accounts-pagination">
      <span>共 {{ total }} 条申请</span>
      <button
        type="button"
        class="mq-btn"
        aria-label="上一页申请"
        title="上一页"
        :disabled="loading || saving || page <= 1"
        @click="load(page - 1)"
      >
        <ChevronLeft :size="16" />
      </button>
      <span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span>
      <button
        type="button"
        class="mq-btn"
        aria-label="下一页申请"
        title="下一页"
        :disabled="loading || saving || page * 20 >= total"
        @click="load(page + 1)"
      >
        <ChevronRight :size="16" />
      </button>
    </footer>
    <a-modal
      :open="dialog"
      :footer="null"
      :width="720"
      :z-index="1100"
      centered
      wrap-class-name="mq-modal"
      :mask-closable="!saving"
      :keyboard="!saving"
      @cancel="close"
    >
      <div class="accounts-editor">
        <header class="accounts-editor-head">
          <MqIconTile name="settings" tone="brand" :size="44" :icon-size="24" />
          <h2>注册申请审批</h2>
        </header>
        <p v-if="detailLoading" class="accounts-empty">正在核对申请与历史</p>
        <p v-if="detailError" class="accounts-error" role="alert">{{ detailError }}</p>
        <button
          v-if="detailError && detail"
          type="button"
          class="mq-btn"
          :disabled="saving"
          @click="open(detail.user_id)"
        >
          <RefreshCw :size="16" />重新核对申请
        </button>
        <template v-if="detail && !detailLoading">
          <div class="mq-soft registration-summary">
            <strong>{{ detail.display_name }}</strong
            ><span class="mq-status" :class="statusClass(detail.status)">{{
              statusName(detail.status)
            }}</span>
            <dl>
              <div>
                <dt>账号</dt>
                <dd>{{ detail.username }} · {{ detail.email }}</dd>
              </div>
              <div>
                <dt>申请范围</dt>
                <dd>{{ detail.requested_institute_id }} / {{ detail.requested_department }}</dd>
              </div>
              <div>
                <dt>申请编号</dt>
                <dd class="mq-mono">{{ detail.user_id }}</dd>
              </div>
            </dl>
          </div>
          <form
            v-if="detail.status === 'pending'"
            class="registration-review"
            @submit.prevent="save"
          >
            <label class="mq-field"
              ><span class="mq-field__label">审批决定</span
              ><select v-model="decision" class="mq-input" aria-label="审批决定" :disabled="saving">
                <option value="approve">通过并开通</option>
                <option value="reject">驳回申请</option>
              </select></label
            >
            <template v-if="decision === 'approve'">
              <div class="accounts-editor-fields">
                <label class="mq-field"
                  ><span class="mq-field__label">核定机构 ID</span
                  ><input
                    v-model="binding.institute_id"
                    class="mq-input"
                    aria-label="核定机构"
                    required
                    maxlength="128"
                    :disabled="saving"
                /></label>
                <label class="mq-field"
                  ><span class="mq-field__label">核定科室</span
                  ><input
                    v-model="binding.department"
                    class="mq-input"
                    aria-label="核定科室"
                    required
                    maxlength="100"
                    :disabled="saving"
                /></label>
              </div>
              <fieldset class="accounts-role-fields" :disabled="saving">
                <legend>授权角色</legend>
                <label v-for="role in roles" :key="role.value"
                  ><input v-model="binding.roles" type="checkbox" :value="role.value" />{{
                    role.label
                  }}</label
                >
              </fieldset>
            </template>
            <label class="mq-field"
              ><span class="mq-field__label">{{
                decision === 'reject' ? '驳回原因' : '审核意见'
              }}</span
              ><textarea
                v-model="comment"
                class="mq-input"
                aria-label="审核意见"
                rows="3"
                required
                maxlength="1000"
                :disabled="saving"
              />
            </label>
            <footer class="accounts-editor-actions">
              <button type="button" class="mq-btn" :disabled="saving" @click="close">取消</button
              ><button
                type="submit"
                class="mq-btn mq-btn--primary"
                :disabled="saving || !!detailError"
              >
                <Check :size="16" />{{
                  saving ? '提交中' : decision === 'approve' ? '确认开通' : '确认驳回'
                }}
              </button>
            </footer>
          </form>
          <h3 class="registration-history-title">操作历史</h3>
          <ol class="registration-history">
            <li v-for="event in detail.history" :key="event.id">
              <div>
                <strong>{{
                  event.action === 'submit'
                    ? '提交申请'
                    : event.action === 'approve'
                      ? '审批通过'
                      : '审批驳回'
                }}</strong
                ><time>{{ formatTime(event.created_at) }}</time>
              </div>
              <p>{{ event.comment }}</p>
              <small>操作账号 {{ event.actor_id }} · 版本 {{ event.version }}</small>
            </li>
          </ol>
        </template>
      </div>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  RefreshCw,
  Search,
} from 'lucide-vue-next'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { useAuthStore } from '@/stores/auth'
import {
  getRegistrationDetail,
  listRegistrations,
  reviewRegistration,
  type RegistrationDetail,
  type RegistrationItem,
  type RegistrationState,
} from '@/api/accountRegistration'
import type { AccountRole } from '@/api/accountManagement'

const props = defineProps<{ registrationId?: string }>()
const auth = useAuthStore()
const canReviewRegistrations = computed(() =>
  auth.userRoles.some((role) => role === 'admin' || role === 'super_admin'),
)
const rows = ref<RegistrationItem[]>([]),
  total = ref(0),
  page = ref(1)
const state = ref<RegistrationState>('pending'),
  loading = ref(false),
  saving = ref(false)
const error = ref(''),
  detailError = ref(''),
  dialog = ref(false),
  detailLoading = ref(false)
const detail = ref<RegistrationDetail | null>(null)
const decision = ref<'approve' | 'reject'>('approve'),
  comment = ref('')
const binding = reactive({ institute_id: '', department: '', roles: ['doctor'] as AccountRole[] })
const roles: Array<{ value: AccountRole; label: string }> = [
  { value: 'doctor', label: '医生' },
  { value: 'qc_staff', label: '质控员' },
  { value: 'qc_manager', label: '质控主管' },
  { value: 'admin', label: '系统管理员' },
]
const statusName = (value: RegistrationState) =>
  ({ pending: '待审批', approved: '已通过', rejected: '已驳回' })[value]
const statusClass = (value: RegistrationState) =>
  ({
    pending: 'mq-status--warning',
    approved: 'mq-status--success',
    rejected: 'mq-status--danger',
  })[value]
const formatTime = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'short',
    timeStyle: 'short',
    hour12: false,
  }).format(new Date(value))
let listGeneration = 0,
  detailGeneration = 0
let listAbortController: AbortController | null = null
let detailAbortController: AbortController | null = null
async function load(next = 1) {
  if (saving.value) return
  const token = ++listGeneration
  listAbortController?.abort()
  const controller = new AbortController()
  listAbortController = controller
  loading.value = true
  error.value = ''
  try {
    const result = await listRegistrations({ status: state.value, page: next, page_size: 20 })
    if (token !== listGeneration || controller.signal.aborted) return
    rows.value = result.items
    total.value = result.total
    page.value = result.page
  } catch (err) {
    if (token !== listGeneration || controller.signal.aborted) return
    error.value = err instanceof Error ? err.message : '申请读取失败'
    rows.value = []
    total.value = 0
  } finally {
    if (token === listGeneration && listAbortController === controller) {
      loading.value = false
      listAbortController = null
    }
  }
}
async function open(id: string) {
  if (saving.value) return
  const token = ++detailGeneration
  detailAbortController?.abort()
  const controller = new AbortController()
  detailAbortController = controller
  dialog.value = true
  detailLoading.value = true
  detail.value = null
  detailError.value = ''
  try {
    const result = await getRegistrationDetail(id)
    if (token !== detailGeneration || controller.signal.aborted) return
    detail.value = result
    decision.value = 'approve'
    comment.value = ''
    Object.assign(binding, {
      institute_id: result.requested_institute_id,
      department: result.requested_department,
      roles: ['doctor'],
    })
  } catch (err) {
    if (token === detailGeneration && !controller.signal.aborted)
      detailError.value = err instanceof Error ? err.message : '申请详情读取失败'
  } finally {
    if (token === detailGeneration && detailAbortController === controller) {
      detailLoading.value = false
      detailAbortController = null
    }
  }
}
function close() {
  if (saving.value) return
  detailGeneration++
  detailAbortController?.abort()
  detailAbortController = null
  dialog.value = false
  detail.value = null
  detailError.value = ''
  comment.value = ''
}
async function save() {
  if (!detail.value || detail.value.status !== 'pending' || saving.value || detailError.value)
    return
  if (!comment.value.trim() || (decision.value === 'approve' && !binding.roles.length)) {
    detailError.value = '请填写审核意见并核定授权角色'
    return
  }
  const id = detail.value.user_id,
    token = detailGeneration
  saving.value = true
  try {
    await reviewRegistration(id, {
      expected_version: detail.value.version,
      decision: decision.value,
      comment: comment.value.trim(),
      ...(decision.value === 'approve'
        ? {
            institute_id: binding.institute_id.trim(),
            department: binding.department.trim(),
            roles: [...binding.roles],
          }
        : {}),
    })
    if (token !== detailGeneration) return
    message.success(
      decision.value === 'approve' ? '账号已开通，结果通知已发送' : '申请已驳回，结果已记录',
    )
    saving.value = false
    await open(id)
    await load(page.value)
  } catch (err) {
    if (token === detailGeneration)
      detailError.value = err instanceof Error ? err.message : '审批失败，请刷新核对'
  } finally {
    if (token === detailGeneration) saving.value = false
  }
}
watch(
  [
    decision,
    comment,
    () => binding.institute_id,
    () => binding.department,
    () => binding.roles.join(','),
  ],
  () => {
    if (detail.value && detailError.value) detailError.value = ''
  },
)
watch(
  () => [auth.user?.id, auth.userRoles.join(',')],
  () => {
    listGeneration++
    detailGeneration++
    listAbortController?.abort()
    listAbortController = null
    detailAbortController?.abort()
    detailAbortController = null
    rows.value = []
    total.value = 0
    dialog.value = false
    saving.value = false
    detail.value = null
    if (canReviewRegistrations.value) {
      void load(1)
      if (props.registrationId) void open(props.registrationId)
    } else {
      error.value = '仅持久系统管理员可审批'
      loading.value = false
    }
  },
  { immediate: true },
)
watch(
  () => props.registrationId,
  (id) => {
    if (id && canReviewRegistrations.value) void open(id)
  },
)
onBeforeUnmount(() => {
  listGeneration++
  detailGeneration++
  listAbortController?.abort()
  listAbortController = null
  detailAbortController?.abort()
  detailAbortController = null
})
</script>

<style scoped src="../../styles/account-management.css"></style>
<style scoped src="../../styles/registration-review.css"></style>
