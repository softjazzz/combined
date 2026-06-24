<template>
  <div class="profile-view">
    <div class="max-w-4xl mx-auto p-6">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="flex items-center gap-3 mb-2">
          <div
            class="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center"
          >
            <UserOutlined class="text-white text-sm" />
          </div>
          <h1 class="text-2xl font-bold text-slate-100">
            个人资料
          </h1>
        </div>
        <p class="text-slate-400 text-sm">
          管理您的个人信息和账户设置
        </p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <!-- 左侧：个人信息卡片 -->
        <div class="lg:col-span-1">
          <div
            class="rounded-2xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6 sticky top-6"
          >
            <!-- 用户头像和基本信息 -->
            <div class="text-center mb-6">
              <div class="relative inline-block mb-4">
                <div
                  class="w-24 h-24 rounded-full overflow-hidden bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-600 flex items-center justify-center shadow-xl"
                >
                  <img
                    v-if="user?.avatar"
                    :src="user.avatar"
                    :alt="user.display_name || '用户头像'"
                    class="w-full h-full object-cover"
                  >
                  <div
                    v-else
                    class="text-white text-3xl font-bold"
                  >
                    {{ avatarInitial }}
                  </div>
                </div>
                <div
                  class="absolute -bottom-1 -right-1 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center border-4 border-slate-800"
                >
                  <CheckOutlined class="text-white text-xs" />
                </div>
              </div>

              <h2 class="text-xl font-semibold text-slate-100 mb-1">
                {{ user?.display_name || '未设置姓名' }}
              </h2>
              <p class="text-slate-400 text-sm mb-3">
                {{ user?.email }}
              </p>

              <!-- 角色标签 -->
              <div class="flex flex-wrap justify-center gap-2 mb-4">
                <div
                  v-for="role in userRoles"
                  :key="role"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium"
                  :class="getRoleStyle(role)"
                >
                  <div
                    class="w-3 h-3 rounded-full flex items-center justify-center text-white text-[8px] font-bold"
                    :class="getRoleColor(role)"
                  >
                    {{ getRoleInitial(role) }}
                  </div>
                  {{ getRoleLabel(role) }}
                </div>
              </div>
            </div>

            <!-- 账户统计 -->
            <div class="space-y-3">
              <div class="flex items-center justify-between p-3 rounded-lg bg-slate-700/30">
                <div class="flex items-center gap-2">
                  <CalendarOutlined class="text-slate-400" />
                  <span class="text-sm text-slate-300">注册时间</span>
                </div>
                <span class="text-sm text-slate-100">
                  {{ formatDate(user?.created_at) }}
                </span>
              </div>

              <div class="flex items-center justify-between p-3 rounded-lg bg-slate-700/30">
                <div class="flex items-center gap-2">
                  <ClockCircleOutlined class="text-slate-400" />
                  <span class="text-sm text-slate-300">最后登录</span>
                </div>
                <span class="text-sm text-slate-100">
                  {{ formatDate(user?.last_login) }}
                </span>
              </div>

              <div class="flex items-center justify-between p-3 rounded-lg bg-slate-700/30">
                <div class="flex items-center gap-2">
                  <TeamOutlined class="text-slate-400" />
                  <span class="text-sm text-slate-300">所属科室</span>
                </div>
                <span class="text-sm text-slate-100">
                  {{ user?.department || '未设置' }}
                </span>
              </div>
            </div>

            <!-- 快捷操作 -->
            <div class="mt-6 space-y-2">
              <a-button
                block
                size="large"
                class="bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30"
                @click="showChangePasswordModal = true"
              >
                <LockOutlined class="mr-2" />
                修改密码
              </a-button>

              <a-button
                block
                size="large"
                class="bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30"
                @click="handleLogout"
              >
                <LogoutOutlined class="mr-2" />
                退出登录
              </a-button>
            </div>
          </div>
        </div>

        <!-- 右侧：编辑表单 -->
        <div class="lg:col-span-2">
          <div class="rounded-2xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-lg font-semibold text-slate-100">
                编辑资料
              </h3>
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full bg-emerald-400" />
                <span class="text-xs text-slate-400">实时保存</span>
              </div>
            </div>

            <!-- 个人资料表单 -->
            <ProfileForm
              :user="profileUser || undefined"
              :loading="updateLoading"
              @update-profile="handleUpdateProfile"
              @change-password="showChangePasswordModal = true"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 修改密码模态框 -->
    <a-modal
      v-model:open="showChangePasswordModal"
      title="修改密码"
      :footer="null"
      width="500px"
      class="change-password-modal"
    >
      <ChangePasswordForm
        :loading="changePasswordLoading"
        @change-password="handleChangePassword"
        @cancel="showChangePasswordModal = false"
      />
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import {
  UserOutlined,
  CheckOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  TeamOutlined,
  LockOutlined,
  LogoutOutlined,
} from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import type { User, UserRole } from '@/types/auth'
import ProfileForm from '@/components/auth/ProfileForm.vue'
import ChangePasswordForm from '@/components/auth/ChangePasswordForm.vue'

type UserProfileModel = User & {
  avatar?: string
  phone?: string
  bio?: string
  notifications?: {
    email?: boolean
    sms?: boolean
    push?: boolean
  }
}

interface ProfileUpdatePayload {
  display_name?: string
  email?: string
  department?: string
  avatar?: string
  phone?: string
  bio?: string
  notifications?: {
    email?: boolean
    sms?: boolean
    push?: boolean
  }
}

interface PasswordUpdatePayload {
  new_password: string
}

// 路由和状态管理
const router = useRouter()
const authStore = useAuthStore()

// 状态
const updateLoading = ref(false)
const changePasswordLoading = ref(false)
const showChangePasswordModal = ref(false)

// 用户信息
const user = computed(() => authStore.user)
const profileUser = computed<UserProfileModel | null>(() => {
  if (!user.value) return null
  return {
    ...user.value,
    roles: [...(user.value.roles || [])],
    notifications: user.value.notifications ? { ...user.value.notifications } : undefined,
  } as UserProfileModel
})
const isUserRole = (role: string): role is UserRole =>
  ['admin', 'qc_manager', 'qc_staff', 'doctor', 'viewer'].includes(role)
const userRoles = computed<UserRole[]>(() =>
  ((profileUser.value?.roles || []) as string[]).filter((role): role is UserRole =>
    isUserRole(role),
  ),
)

// 头像首字母
const avatarInitial = computed(() => {
  if (user.value?.display_name) {
    return user.value.display_name.charAt(0).toUpperCase()
  }
  return 'U'
})

// 处理资料更新
const handleUpdateProfile = async (profileData: unknown) => {
  try {
    updateLoading.value = true
    const payload = (profileData ?? {}) as ProfileUpdatePayload

    // 调用认证存储的更新方法
    const result = await authStore.updateProfile(payload as Partial<User>)

    if (result.success) {
      message.success('个人资料更新成功')
    } else {
      message.error(result.error || '更新失败')
    }
  } catch (error) {
    console.error('更新个人资料失败:', error)
    message.error('更新失败，请重试')
  } finally {
    updateLoading.value = false
  }
}

// 处理密码修改
const handleChangePassword = async (passwordData: unknown) => {
  try {
    changePasswordLoading.value = true
    const payload = (passwordData ?? {}) as PasswordUpdatePayload
    if (!payload.new_password) {
      message.error('新密码不能为空')
      return
    }

    // 调用认证存储的密码更新方法
    const result = await authStore.updatePassword(payload.new_password)

    if (result.success) {
      message.success('密码修改成功')
      showChangePasswordModal.value = false
    } else {
      message.error(result.error || '密码修改失败')
    }
  } catch (error) {
    console.error('密码修改失败:', error)
    message.error('密码修改失败，请重试')
  } finally {
    changePasswordLoading.value = false
  }
}

// 处理退出登录
const handleLogout = async () => {
  try {
    const result = await authStore.signOut()
    if (result.success) {
      message.success('已安全退出')
      router.push('/auth/login')
    }
  } catch (error) {
    console.error('退出登录失败:', error)
    message.error('退出失败，请重试')
  }
}

// 格式化日期
const formatDate = (dateString?: string) => {
  if (!dateString) return '未知'

  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
  } catch {
    return '未知'
  }
}

// 获取角色样式
const getRoleStyle = (role: UserRole) => {
  const styles = {
    admin: 'bg-orange-500/20 text-orange-300 border border-orange-400/30',
    qc_manager: 'bg-blue-500/20 text-blue-300 border border-blue-400/30',
    qc_staff: 'bg-cyan-500/20 text-cyan-300 border border-cyan-400/30',
    doctor: 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30',
    viewer: 'bg-purple-500/20 text-purple-300 border border-purple-400/30',
  }
  return styles[role] || 'bg-gray-500/20 text-gray-300 border border-gray-400/30'
}

// 获取角色颜色
const getRoleColor = (role: UserRole) => {
  const colors = {
    admin: 'bg-orange-500',
    qc_manager: 'bg-blue-500',
    qc_staff: 'bg-cyan-500',
    doctor: 'bg-emerald-500',
    viewer: 'bg-purple-500',
  }
  return colors[role] || 'bg-gray-500'
}

// 获取角色首字母
const getRoleInitial = (role: UserRole) => {
  const initials = {
    admin: 'A',
    qc_manager: 'Q',
    qc_staff: 'S',
    doctor: 'D',
    viewer: 'V',
  }
  return initials[role] || 'U'
}

// 获取角色标签
const getRoleLabel = (role: UserRole) => {
  const labels = {
    admin: '管理员',
    qc_manager: '质控主管',
    qc_staff: '质控员',
    doctor: '医生',
    viewer: '查看者',
  }
  return labels[role] || '未知角色'
}
</script>

<style scoped>
.profile-view {
  @apply min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900;
}

/* 卡片悬浮效果 */
.rounded-2xl {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rounded-2xl:hover {
  transform: translateY(-2px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}

/* 头像动画 */
.w-24.h-24 {
  transition: all 0.3s ease-out;
}

.w-24.h-24:hover {
  transform: scale(1.05);
  box-shadow: 0 8px 25px rgba(6, 182, 212, 0.4);
}

/* 角色标签动画 */
.inline-flex {
  transition: all 0.2s ease-out;
}

.inline-flex:hover {
  transform: translateY(-1px);
}

/* 统计项动画 */
.space-y-3 > div {
  transition: all 0.2s ease-out;
}

.space-y-3 > div:hover {
  transform: translateX(4px);
  background: rgba(71, 85, 105, 0.5) !important;
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 模态框样式 */
:deep(.change-password-modal .ant-modal-content) {
  background: rgb(30 41 59);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.change-password-modal .ant-modal-header) {
  background: rgb(30 41 59);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.change-password-modal .ant-modal-title) {
  color: rgb(241 245 249);
}

:deep(.change-password-modal .ant-modal-close) {
  color: rgb(148 163 184);
}

:deep(.change-password-modal .ant-modal-close:hover) {
  color: rgb(241 245 249);
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .sticky {
    position: static;
  }

  .grid-cols-1.lg\\:grid-cols-3 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .p-6 {
    padding: 1rem;
  }

  .text-2xl {
    font-size: 1.5rem;
  }

  .w-24.h-24 {
    width: 5rem;
    height: 5rem;
  }
}
</style>
