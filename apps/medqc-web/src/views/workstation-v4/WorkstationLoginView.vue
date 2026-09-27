<script setup lang="ts">
import { computed, ref } from 'vue'
import '@/styles/source-han-sans-sc.css'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { AuditOutlined, LockOutlined } from '@ant-design/icons-vue'
import { useAuthStore } from '@/stores/auth'
import WorkstationLoginForm from '@/views/workstation-v4/components/WorkstationLoginForm.vue'
import type { LoginRequest } from '@/types/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)

// 演示入口默认保留（兼容现有演示部署）；正式环境可用 VITE_HIDE_DEMO_LOGIN=true 隐藏
const showDemoLogin = import.meta.env.VITE_HIDE_DEMO_LOGIN !== 'true'

const redirectTarget = computed(() => {
  const raw = route.query.redirect
  if (typeof raw !== 'string') return '/workstation-v5'
  if (raw.startsWith('/workstation-v5')) return raw
  if (raw.startsWith('/workstation-v4')) {
    return `/workstation-v5${raw.slice('/workstation-v4'.length)}`
  }
  return '/workstation-v5'
})

const loginAccountAliases: Record<string, string> = {
  admin: 'admin@medqc.com',
  sync_admin: 'sync_admin@medqc.com',
}

const demoAccounts = [
  {
    label: '功能演示账号',
    role: 'admin' as const,
    account: 'admin',
    password: 'admin888',
  },
]

const capabilities = [
  { title: '病历池', desc: '按范围发起质控' },
  { title: '结果复核', desc: '证据定位到文书' },
  { title: '规则管理', desc: '按规则集维护' },
]

const navigateAfterLogin = async (target = redirectTarget.value) => {
  try {
    await router.replace(target)
  } catch (error) {
    console.warn('[WorkstationLoginV4] router.replace 失败，回退到 location.assign', error)
    window.location.assign(target)
  }
}

const handleLogin = async (loginData: LoginRequest) => {
  try {
    loading.value = true
    // 演示账号映射到后端真实管理员账号
    const account = loginData.account?.trim() || ''
    const isDemoLogin = account === 'admin' && loginData.password?.trim() === 'admin888'
    const signInAccount = loginAccountAliases[account] || account
    const signInPassword = isDemoLogin ? 'admin888' : loginData.password
    const role = isDemoLogin
      ? 'admin'
      : typeof loginData.role === 'string'
        ? loginData.role
        : undefined
    const result = await authStore.signIn(signInAccount, signInPassword, role)

    if (!result.success) {
      message.error(result.error || '登录失败，请检查账号密码')
      return
    }

    message.success('登录成功')
    await navigateAfterLogin()
  } catch (error) {
    console.error('workstation 登录失败:', error)
    message.error('登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

const handleForgotPassword = () => {
  router.push('/auth/forgot-password')
}

const handleDemoLogin = async (account: (typeof demoAccounts)[number]) => {
  await handleLogin({
    account: account.account,
    password: account.password,
    role: account.role,
    remember_me: true,
  })
}
</script>

<template>
  <div class="login-page">
    <section class="login-intro">
      <img
        src="@/assets/images/lx-logo-dimensional-v2.png"
        alt="泸县人民医院"
        class="login-intro__logo"
        width="2172"
        height="724"
      >

      <div class="login-intro__body">
        <h1 class="login-intro__title">
          病案质控系统
        </h1>
        <p class="login-intro__desc">
          运行病历、终末病历、病案首页与结算清单的质控工作台。
        </p>
        <ul class="login-intro__caps">
          <li
            v-for="cap in capabilities"
            :key="cap.title"
          >
            <span class="login-intro__cap-title">{{ cap.title }}</span>
            <span class="login-intro__cap-desc">{{ cap.desc }}</span>
          </li>
        </ul>
      </div>

      <p class="login-intro__foot">
        V5
      </p>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <h2 class="login-card__title">
          登录工作台
        </h2>

        <WorkstationLoginForm
          :loading="loading"
          @login="handleLogin"
          @forgot-password="handleForgotPassword"
        />

        <div
          v-if="showDemoLogin"
          class="login-demo"
        >
          <div class="login-demo__copy">
            <span class="login-demo__title">演示账号快速登录</span>
            <span class="login-demo__hint">用于功能演示，无需输入账号密码</span>
          </div>
          <button
            v-for="account in demoAccounts"
            :key="account.role"
            type="button"
            class="login-demo__button"
            :disabled="loading"
            @click="handleDemoLogin(account)"
          >
            {{ account.label }}
          </button>
        </div>

        <p class="login-card__privacy">
          <LockOutlined aria-hidden="true" />
          登录即表示同意系统安全与隐私协议
        </p>

        <a
          href="/tender-coverage.html"
          target="_blank"
          rel="noopener noreferrer"
          class="login-card__tender"
        >
          <AuditOutlined aria-hidden="true" />
          招标参数满足度说明
        </a>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 560px);
  min-height: 100vh;
  background: var(--mq-bg-page);
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
}

.login-intro {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--mq-space-8);
  padding: 56px 72px;
  background: var(--mq-bg-surface);
  border-right: 1px solid var(--mq-border);
}

.login-intro__logo {
  display: block;
  width: 240px;
  max-width: 100%;
  height: auto;
  object-fit: contain;
}

.login-intro__body {
  display: flex;
  flex-direction: column;
  gap: var(--mq-space-4);
  max-width: 560px;
}

.login-intro__title {
  margin: 0;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.35;
}

.login-intro__desc {
  margin: 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-16);
  line-height: 1.8;
}

.login-intro__caps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--mq-space-3);
  margin: var(--mq-space-4) 0 0;
  padding: 0;
  list-style: none;
}

.login-intro__caps li {
  display: flex;
  flex-direction: column;
  gap: var(--mq-space-1);
  padding: 14px;
  border: 1px solid var(--mq-border);
  border-radius: var(--mq-radius-card);
}

.login-intro__cap-title {
  font-size: var(--mq-font-14);
  font-weight: 500;
}

.login-intro__cap-desc {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}

.login-intro__foot {
  margin: 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.login-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.login-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 100%;
  max-width: 400px;
  box-sizing: border-box;
  padding: 32px;
  background: var(--mq-bg-surface);
  border: 1px solid var(--mq-border);
  border-radius: var(--mq-radius-overlay);
}

.login-card__title {
  margin: 0;
  font-size: var(--mq-font-20);
  font-weight: 700;
}

.login-demo {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mq-space-3);
  padding: var(--mq-space-3) 14px;
  border: 1px dashed var(--mq-border-strong);
  border-radius: var(--mq-radius-card);
  background: var(--mq-bg-subtle);
}

.login-demo__copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.login-demo__title {
  font-size: var(--mq-font-13);
  font-weight: 500;
}

.login-demo__hint {
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-12);
}

.login-demo__button {
  flex-shrink: 0;
  height: 28px;
  padding: 0 var(--mq-space-3);
  border: 1px solid var(--mq-border-strong);
  border-radius: var(--mq-radius-control);
  background: var(--mq-bg-surface);
  color: var(--mq-text-primary);
  font-family: inherit;
  font-size: var(--mq-font-12);
  cursor: pointer;
}

.login-demo__button:hover:not(:disabled) {
  border-color: var(--mq-brand-600);
  color: var(--mq-brand-700);
}

.login-demo__button:disabled {
  color: var(--mq-text-disabled);
  cursor: not-allowed;
}

.login-card__privacy {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 0;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.login-card__tender {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--mq-brand-600);
  font-size: var(--mq-font-13);
  text-decoration: none;
}

.login-card__tender:hover {
  color: var(--mq-brand-700);
}

.login-demo__button:focus-visible,
.login-card__tender:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

@media (max-width: 1023px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-intro {
    gap: var(--mq-space-4);
    padding: 32px 24px;
    border-right: 0;
    border-bottom: 1px solid var(--mq-border);
  }

  .login-intro__caps,
  .login-intro__foot {
    display: none;
  }

  .login-panel {
    padding: 24px 16px 48px;
  }
}
</style>
