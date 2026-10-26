<script setup lang="ts">
import { computed, ref } from 'vue'
import '@/styles/source-han-sans-sc.css'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { AuditOutlined, LockOutlined } from '@ant-design/icons-vue'
import { ArrowRight, LoaderCircle, MonitorPlay } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import WorkstationLoginForm from '@/views/workstation-v4/components/WorkstationLoginForm.vue'
import type { LoginRequest } from '@/types/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)

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
    <!-- 背景层次：三团缓慢漂移的蓝色光斑 + 卡片后方的光环 + 底部地平线高光 -->
    <div
      class="login-bg"
      aria-hidden="true"
    >
      <span class="login-bg__orb login-bg__orb--sky" />
      <span class="login-bg__orb login-bg__orb--brand" />
      <span class="login-bg__orb login-bg__orb--ice" />
      <span class="login-bg__horizon" />
    </div>
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
        <section class="login-card-stage w-full lg:-mt-8 xl:-mt-12">
          <!-- 卡片后方叠层玻璃：两张半透明卡错位倾斜，营造纵深 -->
          <span
            class="login-sheet login-sheet--back"
            aria-hidden="true"
          />
          <span
            class="login-sheet login-sheet--mid"
            aria-hidden="true"
          />
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
                class="login-version-badge flex h-9 w-9 items-center justify-center rounded-xl text-white"
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

            <div class="mt-4 flex justify-between text-sm">
              <router-link to="/auth/register">申请账号</router-link>
              <router-link to="/auth/register?mode=status">查询开通结果</router-link>
            </div>
            <!-- 演示账号：整行即按钮，点一次直接登录 -->
            <div class="login-demo-list mt-4">
              <button
                v-for="account in demoAccounts"
                :key="account.role"
                type="button"
                class="login-demo"
                :disabled="loading"
                aria-label="演示账号快速登录"
                @click="handleDemoLogin(account)"
              >
                <span
                  class="login-demo__icon"
                  aria-hidden="true"
                >
                  <MonitorPlay :size="18" />
                </span>
                <span class="login-demo__copy">
                  <span class="login-demo__title">演示账号快速登录</span>
                </span>
                <span
                  class="login-demo__go"
                  aria-hidden="true"
                >
                  <LoaderCircle
                    v-if="loading"
                    :size="16"
                    class="login-demo__spin"
                  />
                  <template v-else>
                    一键进入
                    <ArrowRight :size="14" />
                  </template>
                </span>
              </button>
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

/* ---------- 背景层次 ---------- */
.login-apple {
  background:
    radial-gradient(1200px 700px at 12% -10%, #d6e7ff 0%, transparent 60%),
    radial-gradient(900px 600px at 100% 110%, #d9ecff 0%, transparent 60%),
    linear-gradient(125deg, #e3eefb 0%, #f3f6fa 50%, #e6eef8 100%);
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

.login-bg__orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(90px);
  will-change: transform;
}

.login-bg__orb--sky {
  top: -18%;
  left: -12%;
  width: 720px;
  height: 720px;
  background: radial-gradient(circle, rgba(110, 176, 255, 0.55), rgba(110, 176, 255, 0) 70%);
  animation: login-drift-a 26s ease-in-out infinite alternate;
}

.login-bg__orb--brand {
  top: 12%;
  right: -8%;
  width: 640px;
  height: 640px;
  background: radial-gradient(circle, rgba(10, 108, 255, 0.34), rgba(10, 108, 255, 0) 70%);
  animation: login-drift-b 32s ease-in-out infinite alternate;
}

.login-bg__orb--ice {
  bottom: -22%;
  left: 24%;
  width: 760px;
  height: 560px;
  background: radial-gradient(ellipse, rgba(150, 214, 255, 0.5), rgba(150, 214, 255, 0) 70%);
  animation: login-drift-c 38s ease-in-out infinite alternate;
}

/* 卡片后方的同心光环：给玻璃卡一个可以透出来的层次 */
.login-card-stage {
  position: relative;
  isolation: isolate;
}

.login-card-stage > .login-glass-card {
  position: relative;
  z-index: 1;
}

.login-bg__horizon {
  position: absolute;
  right: -10%;
  bottom: -40%;
  left: -10%;
  height: 70%;
  border-radius: 50%;
  background: radial-gradient(ellipse at 50% 0%, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0) 60%);
  filter: blur(48px);
}

/* 叠层玻璃：两张半透明卡错位倾斜叠在登录卡后方 */
.login-sheet {
  position: absolute;
  z-index: 0;
  inset: 0;
  max-width: 480px;
  margin-left: auto;
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 24px;
  pointer-events: none;
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
}

.login-sheet--back {
  background: linear-gradient(160deg, rgba(10, 108, 255, 0.22), rgba(120, 190, 255, 0.12));
  box-shadow: 0 30px 60px -24px rgba(10, 70, 160, 0.3);
  transform: translate(46px, 26px) rotate(7deg) scale(0.94);
}

.login-sheet--mid {
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.5), rgba(214, 232, 255, 0.35));
  box-shadow: 0 20px 40px -20px rgba(10, 70, 160, 0.22);
  transform: translate(22px, 12px) rotate(3.5deg) scale(0.97);
}

@keyframes login-drift-a {
  to {
    transform: translate(80px, 60px) scale(1.08);
  }
}

@keyframes login-drift-b {
  to {
    transform: translate(-70px, 50px) scale(0.94);
  }
}

@keyframes login-drift-c {
  to {
    transform: translate(90px, -40px) scale(1.06);
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-bg__orb {
    animation: none;
  }
}

@media (max-width: 1023px) {
  .login-sheet {
    display: none;
  }
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
  border-radius: 24px;
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.72), rgba(232, 242, 255, 0.58));
  padding: 24px 32px;
  border: 1px solid rgba(255, 255, 255, 0.95);
  -webkit-backdrop-filter: blur(28px) saturate(160%);
  backdrop-filter: blur(28px) saturate(160%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 30px 70px -20px rgba(10, 70, 160, 0.28),
    0 8px 20px rgba(39, 62, 94, 0.06);
}

.login-version-badge {
  background: var(--mq-brand-gradient);
  font-size: 13px;
  font-weight: 600;
  box-shadow:
    inset 0 0.5px 0 rgba(255, 255, 255, 0.45),
    0 6px 14px -4px rgba(10, 108, 255, 0.5);
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
  height: 46px;
  border-radius: 12px;
  background: var(--mq-brand-gradient);
  font-size: 15px;
  font-weight: 500;
  letter-spacing: 0.04em;
  transform: none;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.35),
    0 10px 24px -8px rgba(10, 108, 255, 0.55);
  transition:
    box-shadow 180ms ease,
    transform 180ms ease,
    filter 180ms ease;
}
.login-glass-card :deep(button[type='submit']:hover:not(:disabled)) {
  transform: translateY(-1px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.35),
    0 14px 30px -8px rgba(10, 108, 255, 0.65);
  filter: brightness(1.04);
}
.login-glass-card :deep(input:not([type='checkbox']):focus),
.login-glass-card :deep(select:focus) {
  border-color: #6aa9ff;
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(10, 108, 255, 0.12);
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
/* ---------- 演示账号一键登录 ---------- */
.login-demo-list {
  display: grid;
  gap: 8px;
}

.login-demo {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(10, 108, 255, 0.14);
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.78), rgba(234, 243, 255, 0.7));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
  color: #1d2b3f;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease,
    transform 160ms ease;
}

.login-demo:hover:not(:disabled) {
  border-color: rgba(10, 108, 255, 0.4);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 8px 20px -10px rgba(10, 108, 255, 0.45);
  transform: translateY(-1px);
}

.login-demo:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 2px;
}

.login-demo:disabled {
  cursor: progress;
  opacity: 0.8;
}

.login-demo__icon {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(10, 108, 255, 0.1);
  color: #0a6cff;
}

.login-demo__copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.login-demo__title {
  font-size: 14px;
  font-weight: 500;
  line-height: 20px;
}

.login-demo__go {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(10, 108, 255, 0.1);
  color: #0a6cff;
  font-size: 13px;
  font-weight: 500;
  transition:
    background-color 160ms ease,
    color 160ms ease;
}

.login-demo:hover:not(:disabled) .login-demo__go {
  background: #0a6cff;
  color: #ffffff;
}

.login-demo__spin {
  animation: login-demo-spin 0.9s linear infinite;
}

@keyframes login-demo-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
