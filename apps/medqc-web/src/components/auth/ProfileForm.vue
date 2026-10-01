<template>
  <div class="profile-form">
    <a-form
      ref="formRef"
      :model="profileForm"
      :rules="profileRules"
      layout="vertical"
      size="large"
      @finish="handleSubmit"
    >
      <!-- 头像上传区域 -->
      <div class="mb-6">
        <AvatarUpload
          v-model="profileForm.avatar"
          :user-name="profileForm.display_name"
          @upload-success="handleAvatarSuccess"
          @upload-error="handleAvatarError"
        />
      </div>

      <!-- 基本信息 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <!-- 姓名 -->
        <a-form-item name="display_name" class="mb-4">
          <label class="block text-xs font-medium text-slate-300 mb-2">姓名</label>
          <a-input
            v-model:value="profileForm.display_name"
            placeholder="请输入真实姓名"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400"
          />
        </a-form-item>

        <!-- 邮箱（只读） -->
        <a-form-item name="email" class="mb-4">
          <label class="block text-xs font-medium text-slate-300 mb-2">邮箱</label>
          <a-input
            v-model:value="profileForm.email"
            placeholder="邮箱地址"
            disabled
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500"
          />
        </a-form-item>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <!-- 医院：数据范围依据，只读，由管理员维护 -->
        <div class="mb-4">
          <label class="block text-xs font-medium text-slate-300 mb-2">医院编号</label>
          <p class="department-readonly" data-testid="profile-institute">
            {{ props.user?.institute_id || '未分配' }}
          </p>
          <p class="text-xs text-slate-400 mt-1">医院由管理员维护。</p>
        </div>

        <!-- 科室：数据范围依据，只读，由管理员维护 -->
        <div class="mb-4">
          <label class="block text-xs font-medium text-slate-300 mb-2">科室</label>
          <p class="department-readonly" data-testid="profile-department">
            {{ props.user?.department || '未分配' }}
          </p>
          <p class="text-xs text-slate-400 mt-1">科室由管理员维护，如需调整请联系管理员。</p>
        </div>

        <!-- 手机号 -->
        <a-form-item name="phone" class="mb-4">
          <label class="block text-xs font-medium text-slate-300 mb-2">手机号</label>
          <a-input
            v-model:value="profileForm.phone"
            placeholder="请输入手机号"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400"
          />
        </a-form-item>
      </div>

      <!-- 角色信息（只读） -->
      <div class="mb-6">
        <label class="block text-xs font-medium text-slate-300 mb-2">当前角色</label>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="role in userRoles"
            :key="role"
            class="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-400/30"
          >
            <div
              class="w-5 h-5 rounded bg-gradient-to-br flex items-center justify-center text-white text-xs font-bold"
              :class="getRoleColor(role)"
            >
              {{ getRoleInitial(role) }}
            </div>
            <span class="text-cyan-200 text-sm font-medium">{{ getRoleLabel(role) }}</span>
          </div>
        </div>
      </div>

      <!-- 个人简介 -->
      <a-form-item name="bio" class="mb-6">
        <label class="block text-xs font-medium text-slate-300 mb-2">个人简介</label>
        <a-textarea
          v-model:value="profileForm.bio"
          placeholder="简单介绍一下自己..."
          :rows="4"
          :max-length="200"
          show-count
          class="rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400"
        />
      </a-form-item>

      <!-- 通知设置 -->
      <div class="mb-6">
        <label class="block text-xs font-medium text-slate-300 mb-3">通知设置</label>
        <div class="space-y-3">
          <div
            class="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10"
          >
            <div>
              <div class="text-sm text-slate-200">邮件通知</div>
              <div class="text-xs text-slate-400">接收系统重要通知邮件</div>
            </div>
            <a-switch v-model:checked="profileForm.notifications.email" class="bg-slate-600" />
          </div>

          <div
            class="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10"
          >
            <div>
              <div class="text-sm text-slate-200">短信通知</div>
              <div class="text-xs text-slate-400">接收紧急事件短信提醒</div>
            </div>
            <a-switch v-model:checked="profileForm.notifications.sms" class="bg-slate-600" />
          </div>

          <div
            class="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10"
          >
            <div>
              <div class="text-sm text-slate-200">系统推送</div>
              <div class="text-xs text-slate-400">接收浏览器推送通知</div>
            </div>
            <a-switch v-model:checked="profileForm.notifications.push" class="bg-slate-600" />
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex gap-3">
        <a-button
          type="primary"
          html-type="submit"
          :loading="loading"
          size="large"
          class="flex-1 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl"
        >
          <SaveOutlined v-if="!loading" class="mr-2" />
          保存更改
        </a-button>

        <a-button
          size="large"
          class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20"
          @click="handleReset"
        >
          <ReloadOutlined class="mr-2" />
          重置
        </a-button>
      </div>
    </a-form>

    <!-- 账户安全区域 -->
    <div class="mt-8 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
      <div class="flex items-center justify-between">
        <div>
          <h4 class="text-sm font-medium text-amber-200 mb-1">账户安全</h4>
          <p class="text-xs text-amber-200/80">管理密码和安全设置</p>
        </div>
        <a-button
          size="small"
          class="bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30"
          @click="$emit('change-password')"
        >
          <LockOutlined class="mr-1" />
          修改密码
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { FormProps } from 'ant-design-vue'
import { SaveOutlined, ReloadOutlined, LockOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'
import type { User, UserRole } from '@/types/auth'
import AvatarUpload from './AvatarUpload.vue'

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

// Props
interface Props {
  user?: UserProfileModel | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

// Emits
const emit = defineEmits<{
  'update-profile': [data: unknown]
  'change-password': []
}>()

// Form reference
const formRef = ref<FormInstance>()

// Form data
const profileForm = reactive({
  avatar: '',
  display_name: '',
  email: '',
  phone: '',
  bio: '',
  notifications: {
    email: true,
    sms: false,
    push: true,
  },
})

// 用户角色
const userRoles = computed(() => props.user?.roles || [])

// Form validation rules
const profileRules = {
  display_name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, message: '姓名至少2个字符', trigger: 'blur' },
    { max: 20, message: '姓名不能超过20个字符', trigger: 'blur' },
  ],
  phone: [
    {
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()
        if (!/^1[3-9]\d{9}$/.test(value)) {
          return Promise.reject('手机号格式不正确')
        }
        return Promise.resolve()
      },
      trigger: 'blur',
    },
  ],
  bio: [{ max: 200, message: '个人简介不能超过200个字符', trigger: 'blur' }],
} satisfies NonNullable<FormProps['rules']>

// 初始化表单数据
const initializeForm = () => {
  if (props.user) {
    Object.assign(profileForm, {
      avatar: props.user.avatar || '',
      display_name: props.user.display_name || '',
      email: props.user.email || '',
      phone: props.user.phone || '',
      bio: props.user.bio || '',
      notifications: {
        email: props.user.notifications?.email ?? true,
        sms: props.user.notifications?.sms ?? false,
        push: props.user.notifications?.push ?? true,
      },
    })
  }
}

// Handle form submit
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    emit('update-profile', { ...profileForm })
  } catch (error: unknown) {
    if (typeof error === 'object' && error && 'errorFields' in error) {
      message.warning('请检查输入信息')
    }
  }
}

// Handle form reset
const handleReset = () => {
  initializeForm()
  message.info('表单已重置')
}

// Handle avatar upload success
const handleAvatarSuccess = (url: string) => {
  profileForm.avatar = url
}

// Handle avatar upload error
const handleAvatarError = (error: string) => {
  console.error('头像上传失败:', error)
}

// Get role color
const getRoleColor = (role: UserRole) => {
  const colors = {
    admin: 'from-orange-400 to-amber-500',
    qc_manager: 'from-blue-400 to-indigo-500',
    qc_staff: 'from-cyan-400 to-teal-500',
    doctor: 'from-emerald-400 to-teal-500',
    viewer: 'from-purple-400 to-pink-500',
  }
  return colors[role] || 'from-gray-400 to-gray-500'
}

// Get role initial
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

// Get role label
const getRoleLabel = (role: UserRole) => {
  const labels = {
    admin: '系统管理员',
    qc_manager: '质控管理员',
    qc_staff: '质控员',
    doctor: '医生',
    viewer: '查看者',
  }
  return labels[role] || '未知角色'
}

// Initialize on mount
onMounted(() => {
  initializeForm()
})

// Watch user changes
watch(
  () => props.user,
  () => {
    initializeForm()
  },
  { deep: true },
)
</script>

<style scoped>
/* 复用之前的样式 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-input:disabled) {
  background: rgba(255, 255, 255, 0.02) !important;
  color: rgb(148 163 184) !important;
}

:deep(.ant-textarea) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-textarea:focus),
:deep(.ant-textarea-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 0.75rem !important;
  height: 3rem !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-switch-checked) {
  background-color: #06b6d4 !important;
}

:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

.department-readonly {
  margin: 0;
  color: rgb(241 245 249);
  font-size: 15px;
}

/* 通知设置项动画 */
.space-y-3 > div {
  transition: all 0.2s ease-out;
}

.space-y-3 > div:hover {
  transform: translateX(4px);
  background: rgba(255, 255, 255, 0.08) !important;
}
</style>
