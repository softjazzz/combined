<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  DownOutlined,
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
    class="login-form"
    @submit.prevent="handleSubmit"
  >
    <div class="login-form__field">
      <label for="login-account">用户名 / 手机号 / 邮箱</label>
      <div class="login-form__control">
        <MailOutlined
          class="login-form__prefix"
          aria-hidden="true"
        />
        <input
          id="login-account"
          v-model="form.account"
          type="text"
          autocomplete="username"
          placeholder="请输入账号"
        >
      </div>
    </div>

    <div class="login-form__field">
      <label for="login-password">密码</label>
      <div class="login-form__control">
        <LockOutlined
          class="login-form__prefix"
          aria-hidden="true"
        />
        <input
          id="login-password"
          v-model="form.password"
          :type="showPassword ? 'text' : 'password'"
          autocomplete="current-password"
          placeholder="请输入密码"
        >
        <button
          type="button"
          class="login-form__reveal"
          :aria-label="showPassword ? '隐藏密码' : '显示密码'"
          @click="showPassword = !showPassword"
        >
          <EyeOutlined v-if="showPassword" />
          <EyeInvisibleOutlined v-else />
        </button>
      </div>
    </div>

    <div class="login-form__field">
      <label for="login-role">角色</label>
      <div class="login-form__control">
        <select
          id="login-role"
          v-model="form.role"
        >
          <option
            v-for="option in roleOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
        <DownOutlined
          class="login-form__suffix"
          aria-hidden="true"
        />
      </div>
    </div>

    <div class="login-form__row">
      <label class="login-form__remember">
        <input
          v-model="form.remember_me"
          type="checkbox"
        >
        记住登录状态
      </label>
      <button
        type="button"
        class="login-form__link"
        @click="$emit('forgot-password')"
      >
        忘记密码
      </button>
    </div>

    <button
      type="submit"
      class="login-form__submit"
      :disabled="props.loading || !canSubmit"
    >
      <LoginOutlined aria-hidden="true" />
      {{ props.loading ? '正在进入系统…' : '登录' }}
    </button>
  </form>
</template>

<style scoped>
.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--mq-space-4);
}

.login-form__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.login-form__field > label {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  line-height: 20px;
}

.login-form__control {
  position: relative;
}

.login-form__control input,
.login-form__control select {
  width: 100%;
  height: 40px;
  box-sizing: border-box;
  padding: 0 12px 0 36px;
  border: 1px solid var(--mq-border-strong);
  border-radius: var(--mq-radius-control);
  background: var(--mq-bg-surface);
  color: var(--mq-text-primary);
  font-family: inherit;
  font-size: var(--mq-font-14);
  outline: none;
  transition:
    border-color 120ms ease,
    box-shadow 120ms ease;
}

.login-form__control input::placeholder {
  color: var(--mq-text-disabled);
}

.login-form__control select {
  padding-right: 36px;
  padding-left: 12px;
  appearance: none;
}

.login-form__control input:focus,
.login-form__control select:focus {
  border-color: var(--mq-brand-600);
  box-shadow: 0 0 0 3px var(--mq-brand-50);
}

.login-form__prefix,
.login-form__suffix {
  position: absolute;
  top: 50%;
  color: var(--mq-text-tertiary);
  font-size: 14px;
  pointer-events: none;
  transform: translateY(-50%);
}

.login-form__prefix {
  left: 12px;
}

.login-form__suffix {
  right: 12px;
  font-size: 12px;
}

.login-form__reveal {
  position: absolute;
  top: 50%;
  right: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: var(--mq-radius-control);
  background: transparent;
  color: var(--mq-text-tertiary);
  cursor: pointer;
  transform: translateY(-50%);
}

.login-form__reveal:hover {
  color: var(--mq-text-primary);
}

.login-form__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--mq-font-13);
}

.login-form__remember {
  display: inline-flex;
  align-items: center;
  gap: var(--mq-space-2);
  color: var(--mq-text-primary);
  cursor: pointer;
}

.login-form__remember input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--mq-brand-600);
}

.login-form__link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mq-brand-600);
  font: inherit;
  cursor: pointer;
}

.login-form__link:hover {
  color: var(--mq-brand-700);
}

.login-form__submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--mq-space-2);
  height: 40px;
  border: 1px solid var(--mq-brand-600);
  border-radius: var(--mq-radius-control);
  background: var(--mq-brand-600);
  color: #ffffff;
  font-family: inherit;
  font-size: var(--mq-font-14);
  font-weight: 500;
  cursor: pointer;
  transition: background-color 120ms ease;
}

.login-form__submit:hover:not(:disabled) {
  border-color: var(--mq-brand-700);
  background: var(--mq-brand-700);
}

/* 禁用态用灰底灰字，避免与浅色主按钮混淆 */
.login-form__submit:disabled {
  border-color: var(--mq-border);
  background: var(--mq-bg-muted);
  color: var(--mq-text-disabled);
  cursor: not-allowed;
}

.login-form__reveal:focus-visible,
.login-form__link:focus-visible,
.login-form__submit:focus-visible,
.login-form__remember input:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}
</style>
