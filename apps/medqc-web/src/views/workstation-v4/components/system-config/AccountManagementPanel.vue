<template>
  <section class="accounts-panel" aria-labelledby="accounts-title">
    <header class="accounts-head">
      <div>
        <h2 id="accounts-title" class="mq-card__title">账号管理</h2>
        <p v-if="managedInstitute" class="mq-card__desc">机构：{{ managedInstitute }}</p>
      </div>
      <div class="accounts-actions">
        <button type="button" class="mq-btn" :disabled="loading || saving" @click="load(page)">
          <RefreshCw :size="16" />刷新
        </button>
        <button
          type="button"
          class="mq-btn mq-btn--primary"
          :disabled="loading || saving || !ready"
          @click="openCreate"
        >
          <MqIcon name="add" :size="16" />新建账号
        </button>
      </div>
    </header>
    <form class="accounts-filters" @submit.prevent="load(1)">
      <label class="mq-field accounts-search">
        <span class="mq-field__label">账号 / 姓名 / 科室</span>
        <input
          v-model="keyword"
          class="mq-input"
          aria-label="账号搜索"
          placeholder="搜索用户名、姓名、邮箱或科室"
          maxlength="100"
        />
      </label>
      <label class="mq-field">
        <span class="mq-field__label">角色</span>
        <select v-model="role" class="mq-input" aria-label="筛选角色">
          <option value="">全部角色</option>
          <option v-for="item in roleOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
      </label>
      <label class="mq-field">
        <span class="mq-field__label">状态</span>
        <select v-model="active" class="mq-input" aria-label="筛选状态">
          <option value="">全部状态</option>
          <option value="active">启用</option>
          <option value="inactive">停用</option>
        </select>
      </label>
      <button type="submit" class="mq-btn" :disabled="loading || saving">
        <MqIcon name="search" :size="16" />查询
      </button>
    </form>
    <p v-if="error" class="accounts-error" role="alert">{{ error }}</p>
    <div class="accounts-table" :aria-busy="loading">
      <table class="mq-table">
        <colgroup>
          <col class="accounts-col-user" />
          <col class="accounts-col-login" />
          <col class="accounts-col-scope" />
          <col class="accounts-col-role" />
          <col class="accounts-col-state" />
          <col class="accounts-col-time" />
          <col class="accounts-col-action" />
        </colgroup>
        <thead>
          <tr>
            <th>用户</th>
            <th>用户名</th>
            <th>机构 / 科室</th>
            <th>角色</th>
            <th>状态</th>
            <th>最近登录</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="accounts-empty">正在读取账号</td>
          </tr>
          <tr v-else-if="!rows.length">
            <td colspan="7" class="accounts-empty">
              {{ error ? '账号未能加载' : '暂无匹配账号' }}
            </td>
          </tr>
          <tr v-for="row in loading ? [] : rows" :key="row.id">
            <td>
              <strong>{{ row.display_name }}</strong
              ><small>{{ row.email }}</small>
            </td>
            <td class="mq-mono">{{ row.username }}</td>
            <td>
              {{ row.institute_id || '未绑定机构'
              }}<small>{{ row.department || '未绑定科室' }}</small>
            </td>
            <td>
              <div class="accounts-roles">
                <span v-for="item in row.roles" :key="item" class="mq-status">{{
                  roleName(item)
                }}</span
                ><span v-if="!row.roles.length">角色未核实</span>
              </div>
            </td>
            <td>
              <span class="mq-status" :class="row.is_active ? 'mq-status--success' : ''">{{
                row.is_active ? '启用' : '停用'
              }}</span>
            </td>
            <td>{{ formatTime(row.last_login_at) }}</td>
            <td>
              <button
                type="button"
                class="mq-btn"
                :aria-label="`编辑${row.display_name}`"
                :disabled="saving || !editableRoles(row.roles)"
                :title="editableRoles(row.roles) ? '编辑账号' : '专用角色由原权限系统维护'"
                @click="openEdit(row)"
              >
                <Pencil :size="16" />编辑
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <footer class="accounts-pagination">
      <span>共 {{ total }} 个账号</span>
      <button
        type="button"
        class="mq-btn"
        aria-label="上一页账号"
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
        aria-label="下一页账号"
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
      :width="640"
      :z-index="1100"
      centered
      wrap-class-name="mq-modal"
      :mask-closable="!saving"
      :keyboard="!saving"
      @cancel="close"
    >
      <form class="accounts-editor" @submit.prevent="save">
        <header class="accounts-editor-head">
          <MqIconTile name="settings" tone="brand" :size="44" :icon-size="24" />
          <h2>{{ editing ? '编辑账号' : '新建账号' }}</h2>
        </header>
        <div class="accounts-editor-fields">
          <label class="mq-field"
            ><span class="mq-field__label">用户名</span
            ><input
              v-model="form.username"
              class="mq-input"
              :readonly="!!editing"
              :disabled="saving"
              required
              minlength="3"
              maxlength="50"
              pattern="[A-Za-z0-9][A-Za-z0-9_.-]+"
              aria-label="用户名"
              autocomplete="off"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">邮箱</span
            ><input
              v-model="form.email"
              class="mq-input"
              :readonly="!!editing"
              :disabled="saving"
              type="email"
              required
              maxlength="100"
              aria-label="邮箱"
              autocomplete="off"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">姓名</span
            ><input
              v-model="form.display_name"
              class="mq-input"
              :disabled="saving"
              required
              maxlength="100"
              aria-label="姓名"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">机构 ID</span
            ><input
              v-model="form.institute_id"
              class="mq-input"
              :readonly="!!managedInstitute || isSelf"
              :disabled="saving"
              required
              maxlength="128"
              aria-label="机构 ID"
          /></label>
          <label class="mq-field"
            ><span class="mq-field__label">科室</span
            ><input
              v-model="form.department"
              class="mq-input"
              :readonly="isSelf"
              :disabled="saving"
              required
              maxlength="100"
              aria-label="科室"
          /></label>
          <label v-if="!editing" class="mq-field"
            ><span class="mq-field__label">初始口令</span
            ><input
              v-model="form.password"
              class="mq-input"
              :disabled="saving"
              type="password"
              required
              minlength="12"
              maxlength="72"
              aria-label="初始口令"
              autocomplete="new-password"
            /><span class="mq-field__hint">至少12个字符，最多72字节</span></label
          >
        </div>
        <fieldset class="accounts-role-fields" :disabled="saving || isSelf">
          <legend>角色</legend>
          <label v-for="item in roleOptions" :key="item.value"
            ><input v-model="form.roles" type="checkbox" :value="item.value" />{{
              item.label
            }}</label
          >
        </fieldset>
        <label v-if="editing" class="accounts-enabled"
          ><input
            v-model="form.is_active"
            type="checkbox"
            :disabled="saving || isSelf"
          />账号启用</label
        >
        <p v-if="saveError" class="accounts-error" role="alert">{{ saveError }}</p>
        <footer class="accounts-editor-actions">
          <button type="button" class="mq-btn" :disabled="saving" @click="close">取消</button
          ><button type="submit" class="mq-btn mq-btn--primary" :disabled="saving">
            {{ saving ? '保存中' : '保存账号' }}
          </button>
        </footer>
      </form>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { ChevronLeft, ChevronRight, Pencil, RefreshCw } from 'lucide-vue-next'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { useAuthStore } from '@/stores/auth'
import {
  createManagedAccount,
  listManagedAccounts,
  updateManagedAccount,
  type AccountRole,
  type ManagedAccount,
} from '@/api/accountManagement'

const auth = useAuthStore()
const roleOptions: Array<{ value: AccountRole; label: string }> = [
  { value: 'doctor', label: '医生' },
  { value: 'qc_staff', label: '质控员' },
  { value: 'qc_manager', label: '质控主管' },
  { value: 'admin', label: '系统管理员' },
]
const roleName = (role: string) =>
  roleOptions.find((item) => item.value === role)?.label || '未知角色'
const editableRoles = (roles: string[]) =>
  roles.every((role) => roleOptions.some((item) => item.value === role))
const formatTime = (value: string | null) => {
  if (!value) return '尚未登录'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '时间未知'
    : new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'Asia/Shanghai',
        dateStyle: 'short',
        timeStyle: 'short',
        hour12: false,
      }).format(date)
}
const rows = ref<ManagedAccount[]>([]),
  total = ref(0),
  page = ref(1)
const loading = ref(false),
  ready = ref(false),
  saving = ref(false),
  error = ref(''),
  saveError = ref('')
const keyword = ref(''),
  role = ref<AccountRole | ''>(''),
  active = ref('')
const managedInstitute = ref<string | null>(null),
  actorId = ref(''),
  dialog = ref(false)
const editing = ref<ManagedAccount | null>(null)
const emptyForm = () => ({
  username: '',
  email: '',
  display_name: '',
  institute_id: '',
  department: '',
  password: '',
  roles: ['doctor'] as AccountRole[],
  is_active: true,
})
const form = reactive(emptyForm())
const isSelf = computed(() => !!editing.value && editing.value.id === actorId.value)
let generation = 0
async function load(next = 1) {
  if (saving.value) return
  const token = ++generation
  loading.value = true
  error.value = ''
  try {
    const data = await listManagedAccounts({
      keyword: keyword.value,
      role: role.value || undefined,
      active: active.value ? active.value === 'active' : undefined,
      page: next,
      page_size: 20,
    })
    if (token !== generation) return
    rows.value = data.items
    total.value = data.total
    page.value = data.page
    managedInstitute.value = data.managed_institute_id
    actorId.value = data.actor_id
    ready.value = true
  } catch (err) {
    if (token !== generation) return
    error.value = err instanceof Error ? err.message : '账号读取失败'
    rows.value = []
    total.value = 0
    ready.value = false
  } finally {
    if (token === generation) loading.value = false
  }
}
function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm(), { institute_id: managedInstitute.value || '' })
  saveError.value = ''
  dialog.value = true
}
function openEdit(row: ManagedAccount) {
  if (!editableRoles(row.roles)) return
  editing.value = row
  Object.assign(form, emptyForm(), row, {
    roles: [...row.roles],
    institute_id: row.institute_id || '',
    department: row.department || '',
  })
  saveError.value = ''
  dialog.value = true
}
function close() {
  if (saving.value) return
  dialog.value = false
  editing.value = null
  Object.assign(form, emptyForm())
  saveError.value = ''
}
async function save() {
  if (saving.value) return
  saveError.value = ''
  if (!form.roles.length) {
    saveError.value = '至少选择一个角色'
    return
  }
  if (
    !editing.value &&
    (new TextEncoder().encode(form.password).length > 72 || form.password.length < 12)
  ) {
    saveError.value = '口令至少12个字符，UTF-8长度最多72字节'
    return
  }
  const token = generation
  const nextPage = editing.value ? page.value : 1
  saving.value = true
  const binding = {
    display_name: form.display_name.trim(),
    institute_id: form.institute_id.trim(),
    department: form.department.trim(),
    roles: [...form.roles],
  }
  try {
    if (editing.value) {
      await updateManagedAccount(editing.value.id, {
        ...binding,
        is_active: form.is_active,
        expected_updated_at: editing.value.updated_at,
      })
    } else {
      await createManagedAccount({
        ...binding,
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
      })
    }
    if (token !== generation) return
    saving.value = false
    close()
    message.success('账号已保存')
    await load(nextPage)
  } catch (err) {
    if (token === generation)
      saveError.value = err instanceof Error ? err.message : '保存失败，请刷新核对'
  } finally {
    if (token === generation) saving.value = false
  }
}
watch(
  () => [auth.user?.id, auth.userRoles.join(',')],
  () => {
    generation++
    dialog.value = false
    saving.value = false
    ready.value = false
    rows.value = []
    Object.assign(form, emptyForm())
    if (auth.userRoles.includes('admin')) void load(1)
    else {
      error.value = '仅系统管理员可管理账号'
      loading.value = false
    }
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  generation++
  Object.assign(form, emptyForm())
})
</script>

<style scoped src="../../styles/account-management.css"></style>
