<template>
  <section
    class="user-department-panel"
    aria-labelledby="user-department-title"
  >
    <header class="panel-header">
      <div>
        <h2 id="user-department-title">
          账号科室
        </h2>
        <p>科室决定医生可查看和申诉的病例范围，只能由管理员在此维护；须与病历科室名称完全一致。</p>
      </div>
      <button
        type="button"
        class="secondary-button"
        data-testid="user-department-refresh"
        :disabled="loading || Boolean(savingId)"
        @click="refresh"
      >
        刷新
      </button>
    </header>

    <form
      class="filter-bar"
      @submit.prevent="search"
    >
      <input
        v-model="keyword"
        data-testid="user-department-keyword"
        maxlength="100"
        placeholder="账号 / 姓名 / 邮箱"
        aria-label="搜索账号"
      >
      <select
        v-model="departmentFilter"
        data-testid="user-department-filter"
        aria-label="按科室筛选"
      >
        <option value="">
          全部科室
        </option>
        <option :value="UNASSIGNED_DEPARTMENT">
          未分配科室
        </option>
        <option
          v-for="item in departments"
          :key="item"
          :value="item"
        >
          {{ item }}
        </option>
      </select>
      <button
        type="submit"
        class="primary-button"
        :disabled="loading"
      >
        查询
      </button>
    </form>

    <a-alert
      v-if="resultUnknown"
      type="warning"
      show-icon
      data-testid="user-department-unknown"
      message="上次保存结果无法确认"
      description="请先刷新列表核对该账号科室，勿盲目重复提交。"
    />
    <a-alert
      v-else-if="notice"
      :type="noticeType"
      show-icon
      data-testid="user-department-notice"
      :message="notice"
    />

    <div
      v-if="loading"
      class="list-state"
      role="status"
    >
      正在读取账号
    </div>
    <div
      v-else-if="loadError"
      class="list-state is-error"
      role="alert"
    >
      {{ loadError }}
    </div>
    <div
      v-else-if="users.length === 0"
      class="list-state"
    >
      没有符合条件的账号
    </div>
    <div
      v-else
      class="table-wrap"
    >
      <table>
        <thead>
          <tr>
            <th>账号 / 姓名</th>
            <th>角色</th>
            <th>状态</th>
            <th>科室</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="user in users"
            :key="user.id"
            :data-id="user.id"
          >
            <td>
              <strong>{{ user.display_name || '未知' }}</strong>
              <span>{{ user.username || '未知' }}</span>
            </td>
            <td>{{ user.roles.map(roleLabel).join('、') || '未知' }}</td>
            <td>{{ user.is_active ? '启用' : '停用' }}</td>
            <td>
              <template v-if="editingId === user.id">
                <input
                  v-model="editValue"
                  class="department-input"
                  :data-testid="`user-department-input-${user.id}`"
                  list="user-department-options"
                  :maxlength="DEPARTMENT_MAX_LENGTH"
                  aria-label="科室"
                  :disabled="Boolean(savingId)"
                >
              </template>
              <span
                v-else
                :class="{ 'is-unassigned': !user.department }"
              >{{ user.department || '未分配' }}</span>
            </td>
            <td class="op-col">
              <template v-if="editingId === user.id">
                <button
                  type="button"
                  class="text-button"
                  :data-testid="`user-department-save-${user.id}`"
                  :disabled="Boolean(savingId)"
                  @click="save(user)"
                >
                  {{ savingId === user.id ? '正在保存' : '保存' }}
                </button>
                <button
                  type="button"
                  class="text-button muted"
                  :disabled="Boolean(savingId)"
                  @click="cancelEdit"
                >
                  取消
                </button>
              </template>
              <button
                v-else
                type="button"
                class="text-button"
                :data-testid="`user-department-edit-${user.id}`"
                :disabled="Boolean(savingId) || Boolean(editingId) || resultUnknown"
                @click="startEdit(user)"
              >
                修改科室
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <datalist id="user-department-options">
        <option
          v-for="item in departments"
          :key="item"
          :value="item"
        />
      </datalist>
    </div>

    <div
      v-if="total !== null && total > PAGE_SIZE"
      class="pagination-row"
    >
      <button
        type="button"
        :disabled="page <= 1 || loading"
        @click="changePage(page - 1)"
      >
        上一页
      </button>
      <span>第 {{ page }} 页 / 共 {{ total }} 个账号</span>
      <button
        type="button"
        :disabled="page * PAGE_SIZE >= total || loading"
        @click="changePage(page + 1)"
      >
        下一页
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import {
  DEPARTMENT_MAX_LENGTH,
  UNASSIGNED_DEPARTMENT,
  listAdminUsers,
  updateUserDepartment,
  type AdminUser,
} from '@/api/adminUsers'

const PAGE_SIZE = 20
const ROLE_LABEL: Record<string, string> = {
  admin: '管理员', qc_manager: '质控管理员', qc_doctor: '质控员', doctor: '医生',
  sync_admin: '同步管理员', super_admin: '超级管理员',
}

const users = ref<AdminUser[]>([])
const departments = ref<string[]>([])
const total = ref<number | null>(null)
const page = ref(1)
const keyword = ref('')
const departmentFilter = ref('')
const appliedKeyword = ref('')
const appliedDepartment = ref('')
const loading = ref(false)
const loadError = ref('')
const editingId = ref('')
const editValue = ref('')
const savingId = ref('')
const resultUnknown = ref(false)
const notice = ref('')
const noticeType = ref<'success' | 'warning' | 'error'>('success')
let revision = 0
let disposed = false

function roleLabel(role: string) {
  return ROLE_LABEL[role] || role
}

async function load() {
  const request = ++revision
  loading.value = true
  loadError.value = ''
  users.value = []
  total.value = null
  editingId.value = ''
  const result = await listAdminUsers({
    page: page.value, page_size: PAGE_SIZE, q: appliedKeyword.value, department: appliedDepartment.value,
  })
  if (disposed || request !== revision) return
  loading.value = false
  if (result.success === false) {
    loadError.value = result.message
    return
  }
  users.value = result.data.items
  departments.value = result.data.departments
  total.value = result.data.total
  page.value = result.data.page
}

function search() {
  appliedKeyword.value = keyword.value.trim()
  appliedDepartment.value = departmentFilter.value
  page.value = 1
  void load()
}
function refresh() {
  if (savingId.value) return
  resultUnknown.value = false
  notice.value = ''
  void load()
}
function changePage(next: number) {
  if (next < 1 || loading.value) return
  page.value = next
  void load()
}
function startEdit(user: AdminUser) {
  editingId.value = user.id
  editValue.value = user.department || ''
  notice.value = ''
}
function cancelEdit() {
  editingId.value = ''
  editValue.value = ''
}

async function save(user: AdminUser) {
  if (savingId.value || resultUnknown.value) return
  const next = editValue.value.trim()
  if (next === (user.department || '')) {
    cancelEdit()
    return
  }
  const request = revision
  savingId.value = user.id
  notice.value = ''
  const result = await updateUserDepartment(user.id, { department: next, expected_updated_at: user.updated_at })
  if (disposed || request !== revision) return
  savingId.value = ''
  if (result.success === false) {
    resultUnknown.value = result.resultUnknown
    noticeType.value = result.conflict ? 'warning' : 'error'
    notice.value = result.message
    if (result.conflict) await load()
    return
  }
  users.value = users.value.map((item) => (item.id === user.id ? result.data : item))
  if (next && !departments.value.includes(next)) departments.value = [...departments.value, next].sort()
  cancelEdit()
  noticeType.value = 'success'
  notice.value = next
    ? `${result.data.display_name || result.data.username} 的科室已设为“${next}”`
    : `${result.data.display_name || result.data.username} 的科室已清空，该医生将无法查看病例数据`
}

onMounted(() => { void load() })
onUnmounted(() => { disposed = true; revision += 1 })
</script>

<style scoped>
.user-department-panel { display: grid; gap: 14px; padding: 20px; border: 1px solid rgba(0, 0, 0, .08); border-radius: 8px; background: #fff; box-shadow: 0 4px 18px rgba(38, 58, 86, .04); color: #1d1d1f; }
.panel-header, .filter-bar, .pagination-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.panel-header { justify-content: space-between; align-items: flex-start; }
.panel-header h2 { margin: 0; font-size: 17px; line-height: 24px; font-weight: 600; }
.panel-header p { margin: 4px 0 0; color: rgba(29, 29, 31, .6); font-size: 13px; }
.filter-bar input, .filter-bar select, .department-input { min-height: 34px; padding: 0 10px; border: 1px solid rgba(0, 0, 0, .14); border-radius: 8px; background: #fff; font: inherit; }
.filter-bar input { width: 240px; max-width: 100%; }
.department-input { width: 100%; }
button { min-height: 32px; border-radius: 8px; font: inherit; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .55; }
.primary-button { padding: 0 14px; border: 1px solid #007aff; background: #007aff; color: #fff; }
.secondary-button { padding: 0 12px; border: 1px solid rgba(0, 0, 0, .12); background: #fff; }
.text-button { min-height: 28px; padding: 0 6px; border: 0; background: transparent; color: #007aff; }
.text-button.muted { color: rgba(29, 29, 31, .6); }
.table-wrap { max-width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 720px; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 10px 12px; border-bottom: 1px solid rgba(0, 0, 0, .07); text-align: left; font-size: 14px; overflow-wrap: anywhere; vertical-align: middle; }
th { background: #f7f8fa; color: rgba(29, 29, 31, .6); font-weight: 500; }
td strong, td span { display: block; }
td span { color: rgba(29, 29, 31, .6); }
td span.is-unassigned { color: #b54708; }
.op-col { white-space: nowrap; }
.list-state { padding: 26px 12px; text-align: center; color: rgba(29, 29, 31, .6); }
.list-state.is-error { color: #b42318; }
.pagination-row { justify-content: flex-end; }
.pagination-row button { padding: 0 12px; border: 1px solid rgba(0, 0, 0, .12); background: #fff; }
.pagination-row span { color: rgba(29, 29, 31, .6); font-size: 13px; }
</style>
