<template>
  <main class="mq-page registration-page">
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">账号服务</span>
        <h1 class="mq-page-title">{{ mode === 'apply' ? '注册申请' : '开通结果' }}</h1>
      </div>
      <router-link class="mq-btn" to="/workstation-v5/login"
        ><ArrowLeft :size="16" />返回登录</router-link
      >
    </header>
    <section class="mq-card mq-card--padded">
      <div class="mq-card__head registration-head">
        <h2 class="mq-card__title">{{ mode === 'apply' ? '申请账号' : '审核结果' }}</h2>
        <div class="mq-segmented mq-segmented--sm" role="tablist" aria-label="注册服务">
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': mode === 'apply' }"
            role="tab"
            :aria-selected="mode === 'apply'"
            :disabled="busy"
            @click="switchMode('apply')"
          >
            注册申请
          </button>
          <button
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': mode === 'status' }"
            role="tab"
            :aria-selected="mode === 'status'"
            :disabled="busy"
            @click="switchMode('status')"
          >
            查询结果
          </button>
        </div>
      </div>
      <form v-if="mode === 'apply'" class="registration-form" @submit.prevent="submit">
        <div class="registration-fields">
          <label class="mq-field"
            ><span class="mq-field__label">用户名</span
            ><input
              v-model="form.username"
              class="mq-input"
              aria-label="注册用户名"
              required
              minlength="3"
              maxlength="50"
              pattern="[A-Za-z0-9][A-Za-z0-9_.-]+"
              autocomplete="username"
              :disabled="busy"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">姓名</span
            ><input
              v-model="form.display_name"
              class="mq-input"
              aria-label="申请姓名"
              required
              maxlength="100"
              :disabled="busy"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">手机号（选填）</span
            ><input
              v-model="form.phone"
              class="mq-input"
              aria-label="手机号"
              type="tel"
              pattern="1[3-9][0-9]{9}"
              maxlength="11"
              autocomplete="tel"
              :disabled="busy"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">申请科室</span
            ><select
              v-model="form.department_key"
              class="mq-input mq-select"
              aria-label="申请科室"
              required
              :disabled="busy || departmentsLoading || departments.length === 0"
            >
              <option disabled value="">
                {{ departmentsLoading ? '正在读取科室…' : '请选择科室' }}
              </option>
              <option
                v-for="department in departments"
                :key="department.key"
                :value="department.key"
              >
                {{ department.label }}
              </option>
            </select>
            <span v-if="departmentsError" class="registration-error" role="alert">{{
              departmentsError
            }}</span>
            <button
              v-if="departmentsError"
              type="button"
              class="mq-btn"
              :disabled="departmentsLoading"
              @click="loadDepartments"
            >
              重新读取科室
            </button>
          </label>
          <label class="mq-field"
            ><span class="mq-field__label">登录口令</span
            ><input
              v-model="form.password"
              class="mq-input"
              aria-label="注册口令"
              type="password"
              required
              minlength="12"
              maxlength="72"
              autocomplete="new-password"
              :disabled="busy"
            /><span class="mq-field__hint">至少12个字符，最多72字节</span></label
          >
          <label class="mq-field"
            ><span class="mq-field__label">确认口令</span
            ><input
              v-model="confirmation"
              class="mq-input"
              aria-label="确认口令"
              type="password"
              required
              minlength="12"
              maxlength="72"
              autocomplete="new-password"
              :disabled="busy"
          /></label>
        </div>
        <p class="mq-card__desc">
          申请角色：医生。机构、科室及最终权限由管理员核定；审批通过前无法登录业务系统。
        </p>
        <footer class="registration-actions">
          <button
            type="submit"
            class="mq-btn mq-btn--primary"
            :disabled="busy || departmentsLoading || !form.department_key"
          >
            <Send :size="16" />{{ busy ? '提交中' : '提交申请' }}
          </button>
        </footer>
      </form>
      <form v-else-if="!auth.isAuthenticated" class="registration-form" @submit.prevent="query">
        <label class="mq-field"
          ><span class="mq-field__label">用户名 / 邮箱</span
          ><input
            v-model="lookup.account"
            class="mq-input"
            aria-label="查询账号"
            autocomplete="username"
            required
            maxlength="100"
            :disabled="busy"
        /></label>
        <label class="mq-field"
          ><span class="mq-field__label">申请时设置的口令</span
          ><input
            v-model="lookup.password"
            class="mq-input"
            aria-label="查询口令"
            type="password"
            autocomplete="current-password"
            required
            maxlength="72"
            :disabled="busy"
        /></label>
        <footer class="registration-actions">
          <button type="submit" class="mq-btn mq-btn--primary" :disabled="busy">
            <Search :size="16" />{{ busy ? '查询中' : '查询审核结果' }}
          </button>
        </footer>
      </form>
      <button
        v-else-if="mode === 'status'"
        type="button"
        class="mq-btn"
        :disabled="busy"
        @click="queryOwn"
      >
        <RefreshCw :size="16" />{{ busy ? '读取中' : '刷新开通结果' }}
      </button>
      <p v-if="error" class="registration-error" role="alert">{{ error }}</p>
      <section
        v-if="result"
        class="mq-soft registration-result"
        aria-label="申请结果"
        aria-live="polite"
      >
        <span class="mq-status" :class="statusClass">{{ statusLabel }}</span>
        <dl>
          <div>
            <dt>申请编号</dt>
            <dd class="mq-mono">{{ result.user_id }}</dd>
          </div>
          <div>
            <dt>申请机构 / 科室</dt>
            <dd>{{ result.requested_institute_id }} / {{ result.requested_department }}</dd>
          </div>
          <div>
            <dt>提交时间</dt>
            <dd>{{ formatTime(result.submitted_at) }}</dd>
          </div>
          <div v-if="result.reviewed_at">
            <dt>审核时间</dt>
            <dd>{{ formatTime(result.reviewed_at) }}</dd>
          </div>
          <div v-if="result.status === 'approved' && result.institute_id">
            <dt>当前授权范围</dt>
            <dd>{{ result.institute_id }} / {{ result.department || '未绑定科室' }}</dd>
          </div>
          <div v-if="result.review_comment">
            <dt>审核意见</dt>
            <dd>{{ result.review_comment }}</dd>
          </div>
        </dl>
        <p v-if="result.status === 'pending'" class="mq-card__desc">申请已保存，等待管理员审批。</p>
        <p v-else-if="result.status === 'rejected'" class="mq-card__desc">
          可修改申请信息后，使用原用户名和口令重新提交。
        </p>
        <router-link
          v-else-if="result.is_active !== false"
          class="mq-btn mq-btn--primary"
          to="/workstation-v5/login"
          ><LogIn :size="16" />前往工作台</router-link
        >
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, LogIn, RefreshCw, Search, Send } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import {
  getOwnRegistration,
  queryRegistrationStatus,
  submitRegistration,
  getRegistrationDepartments,
  type RegistrationDepartment,
  type RegistrationResult,
} from '@/api/accountRegistration'

const auth = useAuthStore()
const route = useRoute()
const mode = ref<'apply' | 'status'>(route.query.mode === 'status' ? 'status' : 'apply')
const busy = ref(false),
  error = ref(''),
  confirmation = ref('')
const form = reactive({
  username: '',
  display_name: '',
  department_key: '',
  phone: '',
  password: '',
})
const lookup = reactive({ account: '', password: '' })
const departments = ref<RegistrationDepartment[]>([])
const departmentsLoading = ref(false)
const departmentsError = ref('')
let departmentsGeneration = 0
async function loadDepartments() {
  const token = ++departmentsGeneration
  departmentsLoading.value = true
  departmentsError.value = ''
  form.department_key = ''
  departments.value = []
  try {
    const data = await getRegistrationDepartments()
    if (token !== departmentsGeneration) return
    departments.value = data.items
    if (!data.items.length) departmentsError.value = '暂无可用科室，请联系管理员同步科室数据'
  } catch (err) {
    if (token === departmentsGeneration)
      departmentsError.value = err instanceof Error ? err.message : '科室读取失败，请重试'
  } finally {
    if (token === departmentsGeneration) departmentsLoading.value = false
  }
}
onMounted(loadDepartments)
const result = ref<RegistrationResult | null>(null)
let generation = 0
const statusLabel = computed(() =>
  result.value?.status === 'approved'
    ? result.value.is_active === false
      ? '已审批 · 账号已停用'
      : '审批通过 · 已开通'
    : result.value?.status === 'rejected'
      ? '已驳回 · 尚未开通'
      : '待审批 · 尚未开通',
)
const statusClass = computed(() =>
  result.value?.status === 'approved' && result.value.is_active !== false
    ? 'mq-status--success'
    : result.value?.status === 'rejected'
      ? 'mq-status--danger'
      : 'mq-status--warning',
)
const formatTime = (value: string) =>
  new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    dateStyle: 'short',
    timeStyle: 'short',
    hour12: false,
  }).format(new Date(value))
function clearSecrets() {
  form.password = ''
  confirmation.value = ''
  lookup.password = ''
}
function switchMode(value: 'apply' | 'status') {
  if (busy.value) return
  generation++
  mode.value = value
  result.value = null
  error.value = ''
  clearSecrets()
  if (value === 'status' && auth.isAuthenticated) void queryOwn()
}
async function perform(action: () => Promise<RegistrationResult>) {
  if (busy.value) return
  const token = ++generation
  busy.value = true
  error.value = ''
  result.value = null
  try {
    const data = await action()
    if (token !== generation) return
    result.value = data
    clearSecrets()
  } catch (err) {
    if (token === generation) error.value = err instanceof Error ? err.message : '申请服务暂不可用'
  } finally {
    if (token === generation) busy.value = false
  }
}
async function submit() {
  if (busy.value) return
  if (
    departmentsLoading.value ||
    !departments.value.some((item) => item.key === form.department_key)
  ) {
    error.value = '请从已读取的科室列表中选择申请科室'
    return
  }
  if (form.password !== confirmation.value) {
    error.value = '两次口令不一致'
    return
  }
  if (form.password.length < 12 || new TextEncoder().encode(form.password).length > 72) {
    error.value = '口令至少12个字符，UTF-8长度最多72字节'
    return
  }
  lookup.account = form.username.trim()
  await perform(() =>
    submitRegistration({
      username: form.username.trim(),
      display_name: form.display_name.trim(),
      department_key: form.department_key,
      ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
      password: form.password,
    }),
  )
}
const query = () => perform(() => queryRegistrationStatus(lookup.account.trim(), lookup.password))
const queryOwn = () => perform(getOwnRegistration)
watch(
  () => [auth.user?.id, route.query.mode],
  () => {
    generation++
    busy.value = false
    result.value = null
    error.value = ''
    clearSecrets()
    if (route.query.mode === 'status') {
      mode.value = 'status'
      if (auth.isAuthenticated) void queryOwn()
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  generation++
  departmentsGeneration++
  clearSecrets()
})
</script>

<style scoped src="./registration.css"></style>
