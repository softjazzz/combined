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
const showDemoAccounts = ref(false)

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
    badge: 'DEMO',
  },
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
  <div class="login-apple relative min-h-screen overflow-hidden bg-slate-50">
    <!-- 背景光晕 (Tech Glassmorphism Background) -->
    <div
      class="pointer-events-none absolute -left-[20%] -top-[10%] h-[800px] w-[800px] rounded-full bg-sky-400/20 mix-blend-multiply blur-[120px]"
    />
    <div
      class="pointer-events-none absolute -bottom-[10%] -right-[10%] h-[700px] w-[700px] rounded-full bg-blue-500/15 mix-blend-multiply blur-[120px]"
    />
    <!-- 极细微的网格肌理 -->
    <div
      class="login-background-grid pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:40px_40px] opacity-40"
    />

    <div
      class="relative z-10 mx-auto flex min-h-screen max-w-[1400px] flex-col px-6 py-8 lg:px-12 xl:px-16 animate-in fade-in duration-700"
    >
      <header class="login-brand-header mb-6 flex items-center justify-between pb-6">
        <div class="flex items-center">
          <img
            src="@/assets/images/lx-logo-dimensional-v2.png"
            alt="泸县人民医院"
            class="login-hospital-logo"
            width="2172"
            height="724"
          >
        </div>
      </header>

      <main class="grid flex-1 items-center gap-12 lg:grid-cols-[1fr_480px]">
        <!-- 左侧：产品介绍与标语 -->
        <section class="login-intro max-w-[720px]">
          <h1 class="login-intro-title">
            <img
              src="@/assets/images/login-slogan-calligraphy-v3.png"
              alt="让病案质控，更智能，更清晰。基于大模型的医疗质控工作台"
              class="login-slogan-art"
            >
          </h1>
        </section>

        <!-- 右侧：登录卡片 (Glassmorphism) -->
        <section class="w-full lg:-mt-8 xl:-mt-12">
          <div
            class="login-glass-card mx-auto w-full max-w-[480px] rounded-[32px] border border-white/60 bg-white/50 px-8 pb-8 pt-6 shadow-[0_24px_80px_-24px_rgba(15,23,42,0.15)] ring-1 ring-white/80 backdrop-blur-xl lg:ml-auto lg:mr-0 sm:px-12 sm:pb-12 sm:pt-8"
          >
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-[40px] font-black leading-tight tracking-[-0.05em] text-slate-800">
                  登录工作台
                </h2>
              </div>
              <!-- 登录页版本角标 -->
              <div
                class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-blue-600 font-black text-white shadow-[0_8px_20px_-6px_rgba(14,165,233,0.5)]"
              >
                V5
              </div>
            </div>

            <!-- 登录表单区 -->
            <div class="mt-4">
              <WorkstationLoginForm
                :loading="loading"
                @login="handleLogin"
                @forgot-password="handleForgotPassword"
              />
            </div>

            <!-- 演示账号区块 (内嵌卡片风格) -->
            <div
              class="mt-4 overflow-hidden rounded-xl border border-slate-200/50 bg-slate-50/50 transition-all duration-300"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between px-4 py-3 text-left transition hover:bg-slate-100/50"
                @click="showDemoAccounts = !showDemoAccounts"
              >
                <div>
                  <div class="text-[15px] font-bold text-slate-800">
                    演示账号快速登录
                  </div>
                  <div class="mt-0.5 text-xs text-slate-500">
                    功能演示：admin / admin888
                  </div>
                </div>
                <div
                  class="flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-slate-200/50"
                >
                  <svg
                    class="h-4 w-4 text-slate-500 transition-transform duration-300"
                    :class="{ 'rotate-180': showDemoAccounts }"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>
              </button>

              <!-- 平滑展开容器 -->
              <div
                class="grid transition-all duration-300 ease-in-out"
                :class="
                  showDemoAccounts ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                "
              >
                <div class="overflow-hidden">
                  <div class="border-t border-slate-200/50 p-4 pt-2">
                    <div class="space-y-2">
                      <button
                        v-for="account in demoAccounts"
                        :key="account.role"
                        type="button"
                        class="group flex w-full items-center justify-between rounded-xl border border-transparent bg-white/60 px-4 py-3 text-left transition hover:border-sky-200/50 hover:bg-white hover:shadow-sm"
                        @click="handleDemoLogin(account)"
                      >
                        <div class="flex items-center gap-3">
                          <div
                            class="flex h-10 w-10 items-center justify-center rounded-[14px] bg-sky-50 text-xs font-bold text-sky-700 transition group-hover:bg-sky-100"
                          >
                            {{ account.badge }}
                          </div>
                          <div>
                            <div class="text-[14px] font-bold text-slate-800">
                              {{ account.label }}
                            </div>
                            <div class="text-xs text-slate-500">
                              {{ account.account }}
                            </div>
                          </div>
                        </div>
                        <div class="text-xs font-medium text-slate-400">
                          {{ account.password }}
                        </div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-3 flex justify-center text-[13px] text-slate-400">
              <span class="flex items-center gap-1.5">
                <LockOutlined class="text-[11px]" />
                登录即代表同意系统安全与隐私协议
              </span>
            </div>

            <div class="mt-2 flex justify-center">
              <a
                href="/tender-coverage.html"
                target="_blank"
                rel="noopener noreferrer"
                class="inline-flex items-center gap-2 rounded-xl border border-sky-200/70 bg-white/70 px-4 py-2 text-[13px] font-bold text-sky-700 shadow-sm transition hover:border-sky-300 hover:bg-sky-50 hover:text-blue-700"
              >
                <AuditOutlined class="text-[14px]" />
                招标参数满足度说明
              </a>
            </div>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<style scoped>
.login-brand-header {
  padding-top: 8px;
  padding-bottom: 32px;
}
.login-hospital-logo {
  display: block;
  width: 270px;
  height: auto;
  max-width: 100%;
  object-fit: contain;
}
.login-background-grid {
  mask-image: linear-gradient(
    to bottom,
    transparent 0,
    transparent 130px,
    rgba(0, 0, 0, 0.45) 300px,
    transparent 80%
  );
  -webkit-mask-image: linear-gradient(
    to bottom,
    transparent 0,
    transparent 130px,
    rgba(0, 0, 0, 0.45) 300px,
    transparent 80%
  );
}
.login-apple {
  background: linear-gradient(125deg, #dce8f6 0%, #f1f3f7 48%, #e4eaf3 100%);
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}
.login-apple > .pointer-events-none {
  opacity: 0.15;
}
.login-intro {
  align-self: center;
  padding: 24px 0 60px;
}
.login-intro h1 {
  font-size: clamp(32px, 3.2vw, 46px);
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: -0.025em;
}
.login-intro h1 span {
  background: none;
  color: #0a6cff;
}
.login-intro .flex-wrap > div {
  font-size: 14px;
  font-weight: 400;
  padding: 10px 14px;
  border-radius: 10px;
  box-shadow: none;
  transform: none;
}
.login-glass-card {
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(220, 239, 250, 0.88), rgba(230, 237, 253, 0.82));
  padding: 24px 32px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(24px) saturate(135%);
  box-shadow: 0 16px 44px rgba(39, 62, 94, 0.1);
}
.login-glass-card h2 {
  font-size: 26px;
  font-weight: 600;
  letter-spacing: 0;
}
.login-glass-card :deep(input),
.login-glass-card :deep(select),
.login-glass-card :deep(option),
.login-glass-card :deep(button),
.login-glass-card :deep(label) {
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
}
.login-glass-card :deep(select),
.login-glass-card :deep(option) {
  font-size: 14px;
  font-weight: 400;
}
.login-glass-card :deep(form > * + *) {
  margin-top: 12px;
  margin-bottom: 0;
}
.login-glass-card :deep(form > .pt-2) {
  padding-top: 0;
}
.login-glass-card :deep(label) {
  font-size: 14px;
  font-weight: 400;
  letter-spacing: 0;
}
.login-glass-card :deep(input:not([type='checkbox'])),
.login-glass-card :deep(select) {
  height: 44px;
  padding-block: 10px;
  border-radius: 8px;
  border: 1px solid #e0e6ee;
  background: rgba(255, 255, 255, 0.85);
  font-size: 14px;
  font-family: inherit;
}
.login-glass-card :deep(select) {
  padding-block: 0;
  line-height: normal;
}
.login-glass-card :deep(button[type='submit']) {
  height: 44px;
  border-radius: 8px;
  background: #0a6cff;
  font-size: 14px;
  font-weight: 500;
  transform: none;
  box-shadow: 0 3px 8px rgba(10, 108, 255, 0.18);
}
@media (max-width: 1023px) {
  .login-intro {
    padding: 12px 0;
  }
  .login-glass-card {
    padding: 24px;
  }
}

.login-intro {
  align-self: start;
  padding-top: 64px;
}
.login-intro-positioning {
  margin: 14px 0 0;
  color: #526780;
  font-size: clamp(15px, 1.3vw, 18px);
  font-weight: 400;
  line-height: 28px;
  letter-spacing: 0.12em;
}
.login-intro-positioning strong {
  color: inherit;
  font-weight: 500;
}
.login-intro h1.login-intro-title {
  margin: 0;
  font-size: clamp(34px, 3.5vw, 48px) !important;
  font-weight: 500 !important;
  line-height: 1.4 !important;
  letter-spacing: -0.025em;
  color: #23364d;
}
.login-slogan-art {
  display: block;
  width: 100%;
  max-width: 528px;
  height: auto;
  margin: -36px 0 -12px -12px;
  filter: saturate(0.78) brightness(0.94);
}
@media (max-width: 1023px) {
  .login-intro {
    padding-top: 16px;
  }
}
</style>
