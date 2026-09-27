<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  LockOutlined,
  LoginOutlined,
  MailOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { LoginRequest } from '@/types/auth'

interface Props {
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<{
  login: [formData: LoginRequest]
  'forgot-password': []
}>()

const showPassword = ref(false)

const form = reactive<LoginRequest>({
  account: '',
  password: '',
  role: 'qc_manager',
  remember_me: true,
})

const roleOptions = [
  { value: 'qc_manager', label: '病案编码员' },
  { value: 'admin', label: '系统管理员' },
  { value: 'doctor', label: '临床医生' },
]

const canSubmit = computed(() => {
  return !!form.account.trim() && !!form.password.trim() && !!form.role
})

const validate = () => {
  if (!form.account.trim()) {
    message.warning('请输入用户名 / 手机号 / 邮箱')
    return false
  }

  if (!form.password.trim()) {
    message.warning('请输入密码')
    return false
  }

  if (form.password.trim().length < 6) {
    message.warning('密码至少 6 位')
    return false
  }

  if (!form.role) {
    message.warning('请选择角色')
    return false
  }

  return true
}

const handleSubmit = () => {
  if (!validate()) return
  emit('login', { ...form, account: form.account.trim(), password: form.password.trim() })
}
</script>

<template>
  <form
    class="workstation-login-form"
    @submit.prevent="handleSubmit"
  >
    <div class="space-y-2">
      <label class="text-[13px] font-bold tracking-[0.02em] text-slate-700">用户名 / 手机号 / 邮箱</label>
      <div class="group relative">
        <MailOutlined
          class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[15px] text-slate-400 transition group-focus-within:text-sky-500"
        />
        <input
          v-model="form.account"
          type="text"
          autocomplete="username"
          placeholder="请输入用户名 / 手机号 / 邮箱"
          class="h-13 w-full rounded-2xl border-none bg-slate-100/70 px-12 py-3.5 text-[15px] font-medium tracking-[-0.01em] text-slate-800 outline-none transition-all placeholder:font-normal placeholder:text-slate-400 focus:bg-white focus:ring-[3px] focus:ring-sky-500/20"
        >
      </div>
    </div>

    <div class="space-y-2">
      <label class="text-[13px] font-bold tracking-[0.02em] text-slate-700">登录密码</label>
      <div class="group relative">
        <LockOutlined
          class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[15px] text-slate-400 transition group-focus-within:text-sky-500"
        />
        <input
          v-model="form.password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          placeholder="请输入密码"
          class="h-13 w-full rounded-2xl border-none bg-slate-100/70 px-12 py-3.5 pr-12 text-[15px] font-medium tracking-[-0.01em] text-slate-800 outline-none transition-all placeholder:font-normal placeholder:text-slate-400 focus:bg-white focus:ring-[3px] focus:ring-sky-500/20"
        >
        <button
          type="button"
          class="absolute right-4 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-200/50 hover:text-slate-600 focus:outline-none"
          @click="showPassword = !showPassword"
        >
          <EyeOutlined
            v-if="showPassword"
            class="text-[16px]"
          />
          <EyeInvisibleOutlined
            v-else
            class="text-[16px]"
          />
        </button>
      </div>
    </div>

    <div class="space-y-2">
      <label class="text-[13px] font-bold tracking-[0.02em] text-slate-700">选择角色</label>
      <div class="group relative">
        <select
          v-model="form.role"
          class="h-13 w-full appearance-none rounded-2xl border-none bg-slate-100/70 px-4 py-3.5 text-[15px] font-medium tracking-[-0.01em] text-slate-800 outline-none transition-all focus:bg-white focus:ring-[3px] focus:ring-sky-500/20"
        >
          <option
            v-for="option in roleOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <span
          class="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-xs text-slate-400 transition group-focus-within:text-sky-500"
        >▼</span>
      </div>
    </div>

    <div class="flex items-center justify-between pt-2">
      <label
        class="inline-flex cursor-pointer items-center gap-2.5 text-[14px] font-medium text-slate-500 transition hover:text-slate-700"
      >
        <div class="relative flex items-center">
          <input
            v-model="form.remember_me"
            type="checkbox"
            class="peer h-4 w-4 cursor-pointer appearance-none rounded-[4px] border-2 border-slate-300 bg-white transition-all checked:border-sky-500 checked:bg-sky-500 hover:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-500/30"
          >
          <svg
            class="pointer-events-none absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 text-white opacity-0 transition-opacity peer-checked:opacity-100"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="3"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        记住登录状态
      </label>
      <button
        type="button"
        class="text-[14px] font-bold text-sky-600 transition-colors hover:text-blue-700 focus:outline-none"
        @click="$emit('forgot-password')"
      >
        忘记密码？
      </button>
    </div>

    <div class="pt-2">
      <button
        type="submit"
        :disabled="props.loading || !canSubmit"
        class="group relative flex h-14 w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-gradient-to-r from-sky-500 to-blue-600 text-[16px] font-bold tracking-[0.02em] text-white shadow-[0_12px_24px_-8px_rgba(14,165,233,0.5)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_20px_32px_-12px_rgba(14,165,233,0.7)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
      >
        <!-- Button Shine Effect -->
        <div
          class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent transition-transform duration-700 group-hover:translate-x-full group-disabled:hidden"
        />
        <LoginOutlined class="text-[16px]" />
        {{ props.loading ? '正在进入系统...' : '立即登录工作台' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.workstation-login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.workstation-login-form > div {
  margin: 0 !important;
  padding-top: 0;
}
.workstation-login-form > div > label {
  display: block;
  margin-bottom: 6px;
  color: #526176;
  font-size: 13px;
  font-weight: 400;
  line-height: 20px;
  letter-spacing: 0;
}
.workstation-login-form > div > .group {
  margin-top: 0;
}
.workstation-login-form input:not([type='checkbox']),
.workstation-login-form select {
  box-sizing: border-box;
  height: 44px;
  border: 1px solid rgba(93, 116, 147, 0.16);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.8);
  padding-top: 10px;
  padding-bottom: 10px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 400;
  line-height: 22px;
  color: #26364b;
}
.workstation-login-form select {
  padding-block: 0;
  padding-right: 36px;
  line-height: normal;
}
.workstation-login-form input:not([type='checkbox']):focus,
.workstation-login-form select:focus {
  border-color: #80baff;
  box-shadow: 0 0 0 3px rgba(10, 108, 255, 0.1);
}
.workstation-login-form > .flex > label {
  display: inline-flex;
  margin: 0;
}
.workstation-login-form button[type='submit'] {
  height: 44px;
  border-radius: 8px;
  background: #0a6cff;
  font-size: 14px;
  font-weight: 500;
  transform: none;
  box-shadow: 0 3px 8px rgba(10, 108, 255, 0.16);
}
</style>
