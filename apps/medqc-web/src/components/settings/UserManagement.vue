<template>
  <div class="ds-root">
    <!-- ══════════ Section 1: 用户列表 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">
          用户列表
        </h2>
        <p class="ds-section-desc">
          管理系统中所有用户账号。可按邮箱、角色、状态筛选，支持新增、编辑和停用操作。
        </p>
        <div style="margin-top: 16px;">
          <button
            class="ds-btn ds-btn--primary"
            @click="showCreateUserModal"
          >
            + 新增用户
          </button>
        </div>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <!-- 搜索栏 -->
          <div class="um-filter-bar">
            <input
              v-model="userSearch.email"
              class="um-filter-input"
              placeholder="搜索邮箱..."
              @input="handleUserSearch"
            >
            <select
              v-model="userSearch.role"
              class="ds-select-native"
              @change="handleUserSearch"
            >
              <option value="">
                全部角色
              </option>
              <option value="admin">
                管理员
              </option>
              <option value="qc_manager">
                质控管理员
              </option>
              <option value="qc_staff">
                质控人员
              </option>
              <option value="doctor">
                医务人员
              </option>
            </select>
            <select
              v-model="userSearch.status"
              class="ds-select-native"
              @change="handleUserSearch"
            >
              <option value="">
                全部状态
              </option>
              <option value="active">
                激活
              </option>
              <option value="inactive">
                停用
              </option>
            </select>
            <button
              class="ds-btn ds-btn--outline"
              :disabled="loading"
              @click="refreshUsers"
            >
              刷新
            </button>
          </div>

          <!-- 用户列表 -->
          <div class="ds-card__body ds-divide">
            <div
              v-for="user in filteredUsers"
              :key="user.id"
              class="ds-row um-user-row"
            >
              <div class="um-user-info">
                <div
                  class="um-avatar"
                  :style="{ background: getUserAvatarColor(user.email) }"
                >
                  {{ (user.display_name || user.email)?.charAt(0) }}
                </div>
                <div class="um-user-meta">
                  <div class="ds-row__label">
                    {{ user.display_name || user.email }}
                  </div>
                  <div class="ds-row__hint">
                    {{ user.email }}
                  </div>
                </div>
              </div>
              <div class="um-user-details">
                <span
                  class="ds-badge"
                  :class="getRoleBadgeClass(user.roles?.[0])"
                >
                  {{ getRoleText(user.roles?.[0]) }}
                </span>
                <span class="um-department">{{ user.department || '-' }}</span>
                <span
                  class="ds-badge"
                  :class="user.is_active ? 'ds-badge--ok' : 'ds-badge--off'"
                >
                  <span
                    class="ds-badge__dot"
                    :class="user.is_active ? 'ds-badge__dot--green' : 'ds-badge__dot--slate'"
                  />
                  {{ user.is_active ? '激活' : '停用' }}
                </span>
              </div>
              <div class="um-user-actions">
                <button
                  class="ds-btn ds-btn--ghost"
                  @click="$emit('edit-user', user)"
                >
                  编辑
                </button>
                <button
                  class="ds-btn ds-btn--ghost"
                  :class="user.is_active ? 'um-action--warn' : 'um-action--ok'"
                  @click="toggleUserStatus(user)"
                >
                  {{ user.is_active ? '停用' : '激活' }}
                </button>
              </div>
            </div>
            <div
              v-if="filteredUsers.length === 0"
              class="um-empty"
            >
              暂无匹配的用户
            </div>
          </div>
          <div class="ds-card__footer">
            <span class="ds-row__hint">共 {{ filteredUsers.length }} / {{ users.length }} 位用户</span>
            <span />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import '@/styles/settings-design-system.css'

const emit = defineEmits(['edit-user', 'create-user'])

const loading = ref(false)

const userSearch = reactive({
  email: '',
  role: '',
  status: ''
})

const users = ref([
  {
    id: '1',
    email: 'admin@demo.com',
    display_name: '系统管理员',
    roles: ['admin'],
    department: '信息科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date().toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: '2',
    email: 'qc@demo.com',
    display_name: '质控管理员',
    roles: ['qc_manager'],
    department: '质控科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: '3',
    email: 'doctor@demo.com',
    display_name: '医务人员',
    roles: ['doctor'],
    department: '内科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date(Date.now() - 3600000).toISOString(),
    created_at: new Date().toISOString()
  }
])

const filteredUsers = computed(() => {
  return users.value.filter(user => {
    if (userSearch.email && !user.email.includes(userSearch.email)) return false
    if (userSearch.role && !user.roles?.includes(userSearch.role)) return false
    if (userSearch.status === 'active' && !user.is_active) return false
    if (userSearch.status === 'inactive' && user.is_active) return false
    return true
  })
})

const refreshUsers = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('用户列表已刷新')
  } catch {
    message.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const handleUserSearch = () => {}

const showCreateUserModal = () => {
  emit('create-user')
}

const toggleUserStatus = (user: any) => {
  user.is_active = !user.is_active
  message.success(`用户已${user.is_active ? '激活' : '停用'}`)
}

const getUserAvatarColor = (email: string) => {
  const palette = ['#2b6cf6', '#2C8EAA', '#52C41A', '#FAAD14', '#13C2C2']
  return palette[email.charCodeAt(0) % palette.length]
}

const getRoleText = (role?: string) => {
  const map: Record<string, string> = {
    admin: '管理员', qc_manager: '质控管理员',
    qc_staff: '质控人员', doctor: '医务人员'
  }
  return map[role || ''] || role || '-'
}

const getRoleBadgeClass = (role?: string) => {
  const map: Record<string, string> = {
    admin: 'ds-badge--info', qc_manager: 'ds-badge--info',
    qc_staff: 'ds-badge--ok', doctor: 'ds-badge--off'
  }
  return map[role || ''] || 'ds-badge--off'
}
</script>

<style scoped>
/* 搜索栏 */
.um-filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  flex-wrap: wrap;
}
.um-filter-input {
  flex: 1;
  min-width: 160px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  font-size: 13px;
  color: #334155;
  background: #fff;
  outline: none;
  transition: border-color 0.2s;
}
.um-filter-input:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.1); }

/* 用户行 */
.um-user-row {
  padding: 12px 20px !important;
}
.um-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
}
.um-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 15px;
  flex-shrink: 0;
}
.um-user-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.um-user-details {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.um-department {
  font-size: 12px;
  color: #64748b;
  padding: 2px 8px;
  background: #f8fafc;
  border-radius: 4px;
  border: 1px solid #f1f5f9;
}
.um-user-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}
.um-action--warn { color: #d97706 !important; }
.um-action--warn:hover { background: #fffbeb !important; }
.um-action--ok { color: #15803d !important; }
.um-action--ok:hover { background: #f0fdf4 !important; }
.um-empty {
  padding: 40px 20px;
  text-align: center;
  color: #94a3b8;
  font-size: 13px;
}
</style>
