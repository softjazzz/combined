<template>
  <div class="login-form">
    <a-form
      ref="formRef"
      :model="loginForm"
      :rules="loginRules"
      layout="vertical"
      size="large"
      @finish="handleLogin"
    >
      <!-- 登录标识输入 -->
      <a-form-item
        name="account"
        class="mb-5"
      >
        <label class="block text-sm font-medium text-gray-700 mb-2">用户名 / 手机号 / 邮箱</label>
        <div class="relative">
          <a-input
            v-model:value="loginForm.account"
            placeholder="请输入用户名、手机号或邮箱"
            class="h-12 rounded-lg border border-gray-300 text-gray-900 placeholder:text-gray-500 pl-11 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
            <UserOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 密码输入 -->
      <a-form-item
        name="password"
        class="mb-5"
      >
        <label class="block text-sm font-medium text-gray-700 mb-2">密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="loginForm.password"
            placeholder="请输入密码"
            class="h-12 rounded-lg border border-gray-300 text-gray-900 placeholder:text-gray-500 pl-11 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
            <LockOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 角色选择 -->
      <a-form-item
        name="role"
        class="mb-6"
      >
        <label class="block text-sm font-medium text-gray-700 mb-2">角色（可选）</label>
        <a-select
          v-model:value="loginForm.role"
          placeholder="选择角色"
          size="large"
          class="role-select w-full"
        >
          <a-select-option value="admin">
            <div class="flex items-center gap-2">
              <div
                class="w-6 h-6 rounded-full bg-orange-500 flex items-center justify-center text-white text-xs font-bold"
              >
                管
              </div>
              系统管理员
            </div>
          </a-select-option>
          <a-select-option value="qc_manager">
            <div class="flex items-center gap-2">
              <div
                class="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold"
              >
                质
              </div>
              质控主管
            </div>
          </a-select-option>
          <a-select-option value="doctor">
            <div class="flex items-center gap-2">
              <div
                class="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-bold"
              >
                医
              </div>
              医务人员
            </div>
          </a-select-option>
          <a-select-option value="viewer">
            <div class="flex items-center gap-2">
              <div
                class="w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white text-xs font-bold"
              >
                查
              </div>
              查看者
            </div>
          </a-select-option>
        </a-select>
      </a-form-item>

      <!-- 记住我和忘记密码 -->
      <div class="flex items-center justify-between mb-6">
        <a-checkbox
          v-model:checked="loginForm.remember_me"
          class="text-sm text-gray-600"
        >
          记住我
        </a-checkbox>
        <a
          class="text-sm text-blue-600 hover:text-blue-500 cursor-pointer transition-colors"
          @click="$emit('forgot-password')"
        >
          忘记密码？
        </a>
      </div>
      <p class="mb-5 text-xs text-slate-500">
        手机号为同一账号的备用登录标识，忘记用户名时可直接使用手机号登录。
      </p>

      <!-- 登录按钮 -->
      <a-button
        type="primary"
        html-type="submit"
        :loading="loading"
        block
        size="large"
        class="h-12 rounded-lg bg-blue-600 hover:bg-blue-700 border-none font-medium shadow-sm hover:shadow-md transition-all"
      >
        <LoginOutlined
          v-if="!loading"
          class="mr-2"
        />
        立即登录
      </a-button>
    </a-form>

    <!-- 密码强度提示 -->
    <PasswordStrength
      v-if="showPasswordStrength"
      :password="loginForm.password"
      class="mt-4"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import type { FormProps } from 'ant-design-vue'
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'
import type { LoginRequest } from '@/types/auth'
import PasswordStrength from './PasswordStrength.vue'

// Props
interface Props {
  loading?: boolean
  showPasswordStrength?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  showPasswordStrength: false,
})

// Emits
const emit = defineEmits<{
  login: [formData: LoginRequest]
  'forgot-password': []
}>()

// Form reference
const formRef = ref<FormInstance>()

// Form data
const loginForm = reactive<LoginRequest>({
  account: '',
  password: '',
  role: undefined,
  remember_me: false,
})

// Form validation rules
const loginRules = {
  account: [{ required: true, message: '请输入用户名、手机号或邮箱', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位字符', trigger: 'blur' },
  ],
} satisfies NonNullable<FormProps['rules']>

// Handle login
const handleLogin = async () => {
  try {
    await formRef.value?.validate()
    emit('login', { ...loginForm })
  } catch (error) {
    const validateError = error as { errorFields?: unknown[] }
    if (validateError?.errorFields) {
      message.warning('请检查输入信息')
    }
  }
}

// Computed
const isFormValid = computed(() => {
  return loginForm.account && loginForm.password && loginForm.password.length >= 6
})

// Expose methods for parent component
defineExpose({
  resetForm: () => {
    formRef.value?.resetFields()
    Object.assign(loginForm, {
      account: '',
      password: '',
      role: undefined,
      remember_me: false,
    })
  },
  setFormData: (data: Partial<LoginRequest>) => {
    Object.assign(loginForm, data)
  },
  validateForm: () => formRef.value?.validate(),
  isValid: isFormValid,
})
</script>

<style scoped>
/* 深色主题样式优化 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding-left: 0 !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-input-password) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.ant-input-password .ant-input) {
  padding-left: 0 !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input-password .ant-input-suffix) {
  color: rgb(148 163 184) !important;
}

:deep(.ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 0.75rem !important;
  height: 3rem !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-select-selection-placeholder) {
  color: rgb(100 116 139) !important;
}

:deep(.ant-checkbox-wrapper) {
  color: rgb(203 213 225) !important;
}

:deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #06b6d4 !important;
  border-color: #06b6d4 !important;
}

:deep(.ant-checkbox-inner) {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

:deep(.ant-btn-primary) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

.role-select :deep(.ant-select-dropdown) {
  background: rgb(15 23 42) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

.role-select :deep(.ant-select-item) {
  color: rgb(241 245 249) !important;
}

.role-select :deep(.ant-select-item-option-selected) {
  background: rgba(6, 182, 212, 0.2) !important;
}
</style>
