<script setup lang="ts">
import { computed, ref } from 'vue'
import '@/styles/source-han-sans-sc.css'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { AuditOutlined, LockOutlined } from '@ant-design/icons-vue'
import { ArrowRight, LoaderCircle, Sparkles } from 'lucide-vue-next'
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
    label: '演示账号快速登录',
    subtitle: '管理员视角 · 一键体验全流程质控',
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
            <!-- 演示账号：极简玻璃质感快捷体验卡片 -->
            <div class="login-demo-section mt-5">
              <div
                class="login-demo-divider"
                aria-hidden="true"
              >
                <span class="login-demo-divider__line" />
                <span class="login-demo-divider__label">快速体验</span>
                <span class="login-demo-divider__line" />
              </div>

              <div class="login-demo-list">
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
                    <Sparkles
                      :size="17"
                      :stroke-width="1.9"
                    />
                  </span>
                  <span class="login-demo__copy">
                    <span class="login-demo__head">
                      <span class="login-demo__title">{{ account.label }}</span>
                      <span class="login-demo__badge">{{ account.badge }}</span>
                    </span>
                    <span class="login-demo__subtitle">{{ account.subtitle }}</span>
                  </span>
                  <span
                    class="login-demo__go"
                    aria-hidden="true"
                  >
                    <LoaderCircle
                      v-if="loading"
                      :size="15"
                      class="login-demo__spin"
                    />
                    <template v-else>
                      <span>进入</span>
                      <ArrowRight
                        :size="13"
                        :stroke-width="2.1"
                        class="login-demo__arrow"
                      />
                    </template>
                  </span>
                </button>
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
.login-demo-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.login-demo-divider {
  display: flex;
  align-items: center;
  gap: 10px;
}

.login-demo-divider__line {
  flex: 1 1 auto;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(148, 163, 184, 0) 0%,
    rgba(148, 163, 184, 0.28) 50%,
    rgba(148, 163, 184, 0) 100%
  );
}

.login-demo-divider__label {
  flex-shrink: 0;
  color: #8a9bb0;
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.14em;
}

.login-demo-list {
  display: grid;
  gap: 8px;
}

.login-demo {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 11px 12px 11px 13px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(241, 247, 255, 0.78));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.96),
    0 6px 18px -12px rgba(15, 23, 42, 0.18),
    0 1px 2px rgba(15, 23, 42, 0.04);
  color: #0f172a;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 200ms cubic-bezier(0.22, 1, 0.36, 1),
    background 200ms cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-demo::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(
    260px 120px at 0% 0%,
    rgba(10, 108, 255, 0.08) 0%,
    rgba(10, 108, 255, 0) 70%
  );
  opacity: 0;
  pointer-events: none;
  transition: opacity 220ms ease;
}

.login-demo:hover:not(:disabled) {
  border-color: rgba(10, 108, 255, 0.34);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(235, 245, 255, 0.88));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 1),
    0 12px 26px -14px rgba(10, 108, 255, 0.38),
    0 2px 6px rgba(15, 23, 42, 0.04);
  transform: translateY(-1px);
}

.login-demo:hover:not(:disabled)::before {
  opacity: 1;
}

.login-demo:active:not(:disabled) {
  transform: translateY(0);
}

.login-demo:focus-visible {
  outline: 2px solid #0a6cff;
  outline-offset: 2px;
}

.login-demo:disabled {
  cursor: progress;
  opacity: 0.78;
}

.login-demo__icon {
  position: relative;
  z-index: 1;
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(145deg, #f0f6ff 0%, #ddebff 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 0 0 1px rgba(10, 108, 255, 0.14);
  color: #0a6cff;
  transition:
    background 200ms ease,
    box-shadow 200ms ease,
    color 200ms ease,
    transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-demo:hover:not(:disabled) .login-demo__icon {
  background: var(--mq-brand-gradient);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.35),
    0 6px 14px -6px rgba(10, 108, 255, 0.55);
  color: #ffffff;
  transform: scale(1.03);
}

.login-demo__copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.login-demo__head {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.login-demo__title {
  color: #0f172a;
  font-size: 13.5px;
  font-weight: 600;
  line-height: 19px;
  letter-spacing: -0.01em;
}

.login-demo__badge {
  display: inline-flex;
  align-items: center;
  height: 17px;
  padding: 0 5.5px;
  border: 1px solid rgba(10, 108, 255, 0.18);
  border-radius: 5px;
  background: rgba(10, 108, 255, 0.06);
  color: #0a6cff;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  line-height: 1;
}

.login-demo__subtitle {
  overflow: hidden;
  color: #64748b;
  font-size: 11.5px;
  font-weight: 400;
  line-height: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.login-demo__go {
  position: relative;
  z-index: 1;
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 11px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease,
    color 180ms ease;
}

.login-demo__arrow {
  transition: transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}

.login-demo:hover:not(:disabled) .login-demo__go {
  border-color: transparent;
  background: var(--mq-brand-gradient);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 6px 14px -6px rgba(10, 108, 255, 0.55);
  color: #ffffff;
}

.login-demo:hover:not(:disabled) .login-demo__arrow {
  transform: translateX(2px);
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
