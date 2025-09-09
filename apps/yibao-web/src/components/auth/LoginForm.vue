<template>
  <div class="login-form">
    <a-form
      ref="formRef"
      :model="loginForm"
      :rules="loginRules"
      @finish="handleLogin"
      layout="vertical"
      size="large"
    >
      <a-form-item name="email" class="mb-5">
        <label class="block text-sm font-medium text-gray-700 mb-2">邮箱</label>
        <div class="relative">
          <a-input
            v-model:value="loginForm.email"
            placeholder="请输入邮箱"
            class="h-12 rounded-lg border border-gray-300 text-gray-900 placeholder:text-gray-500 pl-11 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
            <UserOutlined />
          </div>
        </div>
      </a-form-item>

      <a-form-item name="password" class="mb-5">
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

      <a-form-item name="role" class="mb-6">
        <label class="block text-sm font-medium text-gray-700 mb-2">角色</label>
        <a-select
          v-model:value="loginForm.role"
          placeholder="选择角色"
          size="large"
          class="role-select w-full"
        >
          <a-select-option value="admin">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-orange-500 flex items-center justify-center text-white text-xs font-bold">管</div>
              系统管理员
            </div>
          </a-select-option>
          <a-select-option value="qc_manager">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-bold">质</div>
              质控主管
            </div>
          </a-select-option>
          <a-select-option value="doctor">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center text-white text-xs font-bold">医</div>
              医务人员
            </div>
          </a-select-option>
          <a-select-option value="viewer">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded-full bg-purple-500 flex items-center justify-center text-white text-xs font-bold">查</div>
              查看者
            </div>
          </a-select-option>
        </a-select>
      </a-form-item>

      <div class="flex items-center justify-between mb-6">
        <a-checkbox v-model:checked="loginForm.remember_me" class="text-sm text-gray-600">
          记住我
        </a-checkbox>
        <a class="text-sm text-blue-600 hover:text-blue-500 cursor-pointer transition-colors" @click="$emit('forgot-password')">
          忘记密码？
        </a>
      </div>

      <a-button
        type="primary"
        html-type="submit"
        :loading="loading"
        block
        size="large"
        class="h-12 rounded-lg bg-blue-600 hover:bg-blue-700 border-none font-medium shadow-sm hover:shadow-md transition-all"
      >
        <LoginOutlined v-if="!loading" class="mr-2" />
        立即登录
      </a-button>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'

interface LoginRequest {
  email: string
  password: string
  role?: string
  remember_me?: boolean
}

interface Props {
  loading?: boolean
  showPasswordStrength?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  showPasswordStrength: false
})

const emit = defineEmits<{
  login: [formData: LoginRequest]
  'forgot-password': []
}>()

const formRef = ref<FormInstance>()

const loginForm = reactive<LoginRequest>({
  email: '',
  password: '',
  role: undefined,
  remember_me: false
})

const loginRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位字符', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

const handleLogin = async () => {
  try {
    await formRef.value?.validate()
    emit('login', { ...loginForm })
  } catch (error) {
    if ((error as any)?.errorFields) {
      message.warning('请检查输入信息')
    }
  }
}

const isFormValid = computed(() => {
  return loginForm.email && loginForm.password && loginForm.role && loginForm.email.includes('@') && loginForm.password.length >= 6
})

defineExpose({
  resetForm: () => {
    formRef.value?.resetFields()
    Object.assign(loginForm, { email: '', password: '', role: undefined, remember_me: false })
  },
  setFormData: (data: Partial<LoginRequest>) => {
    Object.assign(loginForm, data)
  },
  validateForm: () => formRef.value?.validate(),
  isValid: isFormValid
})
</script>

<style scoped>
::deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding-left: 0 !important;
  color: rgb(55 65 81) !important;
}

::deep(.ant-input-password .ant-input) {
  padding-left: 0 !important;
  color: rgb(55 65 81) !important;
}

::deep(.ant-select-selector) {
  background: white !important;
  border: 1px solid #e5e7eb !important;
  border-radius: 0.75rem !important;
  height: 3rem !important;
  color: rgb(55 65 81) !important;
}
</style>
