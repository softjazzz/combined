<script setup lang="ts">
import { computed, ref } from 'vue'
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
  return typeof raw === 'string' && raw.startsWith('/workstation-v4') ? raw : '/workstation-v4'
})

const featurePills = ['首页生成', '编码校验', '证据溯源', 'DRG 预分组']

const demoAccounts = [
  {
    label: '功能演示账号',
    role: 'admin' as const,
    account: 'admin',
    password: 'admin888',
    badge: 'DEMO',
  },
]

const navigateAfterLogin = async () => {
  const target = redirectTarget.value
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
    const signInAccount = isDemoLogin ? 'admin@medqc.com' : account
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
  <div class="relative min-h-screen overflow-hidden bg-slate-50">
    <!-- 背景光晕 (Tech Glassmorphism Background) -->
    <div
      class="pointer-events-none absolute -left-[20%] -top-[10%] h-[800px] w-[800px] rounded-full bg-sky-400/20 mix-blend-multiply blur-[120px]"
    />
    <div
      class="pointer-events-none absolute -bottom-[10%] -right-[10%] h-[700px] w-[700px] rounded-full bg-blue-500/15 mix-blend-multiply blur-[120px]"
    />
    <!-- 极细微的网格肌理 -->
    <div
      class="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:40px_40px] [mask-image:linear-gradient(to_bottom,white,transparent)] opacity-40"
    />

    <div
      class="relative z-10 mx-auto flex min-h-screen max-w-[1400px] flex-col px-6 py-8 lg:px-12 xl:px-16 animate-in fade-in duration-700"
    >
      <header class="mb-6 flex items-center justify-between border-b border-slate-200/50 pb-6">
        <div class="flex items-center">
          <img
            src="@/assets/images/lx-logo.png"
            alt="泸县人民医院"
            class="h-[60px] w-auto object-contain drop-shadow-sm"
          />
        </div>
      </header>

      <main class="grid flex-1 items-center gap-12 lg:grid-cols-[1fr_480px]">
        <!-- 左侧：产品介绍与标语 -->
        <section class="max-w-[720px] self-start pt-10 lg:pt-24 xl:pt-32">
          <!-- Tag removed per user request -->
          <h1
            class="mt-4 text-[54px] font-black leading-[1.05] tracking-[-0.04em] text-slate-800 xl:text-[64px]"
          >
            基于大模型的
            <span
              class="mt-2 block bg-gradient-to-r from-sky-600 to-blue-600 bg-clip-text text-transparent pb-2"
              >AI驱动病案质控平台</span
            >
          </h1>

          <!-- 核心特性列表（优化版 Tag） -->
          <div class="mt-10 flex flex-wrap gap-4">
            <div
              v-for="pill in featurePills"
              :key="pill"
              class="flex items-center gap-2 rounded-xl border border-white/60 bg-white/40 px-5 py-2.5 text-[15px] font-semibold text-slate-700 shadow-sm backdrop-blur-md transition-all hover:-translate-y-0.5 hover:bg-white/60 hover:shadow-md"
            >
              <div class="h-1.5 w-1.5 rounded-full bg-sky-500" />
              {{ pill }}
            </div>
          </div>
        </section>

        <!-- 右侧：登录卡片 (Glassmorphism) -->
        <section class="w-full lg:-mt-8 xl:-mt-12">
          <div
            class="mx-auto w-full max-w-[480px] rounded-[32px] border border-white/60 bg-white/50 px-8 pb-8 pt-6 shadow-[0_24px_80px_-24px_rgba(15,23,42,0.15)] ring-1 ring-white/80 backdrop-blur-xl lg:ml-auto lg:mr-0 sm:px-12 sm:pb-12 sm:pt-8"
          >
            <div class="flex items-start justify-between gap-4">
              <div>
                <h2 class="text-[40px] font-black leading-tight tracking-[-0.05em] text-slate-800">
                  登录工作台
                </h2>
              </div>
              <!-- V4 高亮角标 -->
              <div
                class="flex h-12 w-12 items-center justify-center rounded-[18px] bg-gradient-to-br from-sky-500 to-blue-600 font-black text-white shadow-[0_8px_20px_-6px_rgba(14,165,233,0.5)]"
              >
                V4
              </div>
            </div>

            <!-- 登录表单区 -->
            <div class="mt-6">
              <WorkstationLoginForm
                :loading="loading"
                @login="handleLogin"
                @forgot-password="handleForgotPassword"
              />
            </div>

            <!-- 演示账号区块 (内嵌卡片风格) -->
            <div
              class="mt-6 overflow-hidden rounded-[24px] border border-slate-200/50 bg-slate-50/50 transition-all duration-300"
            >
              <button
                type="button"
                class="flex w-full items-center justify-between px-6 py-5 text-left transition hover:bg-slate-100/50"
                @click="showDemoAccounts = !showDemoAccounts"
              >
                <div>
                  <div class="text-[15px] font-bold text-slate-800">演示账号快速登录</div>
                  <div class="mt-0.5 text-xs text-slate-500">功能演示：admin / admin888</div>
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

            <div class="mt-6 flex justify-center text-[13px] text-slate-400">
              <span class="flex items-center gap-1.5">
                <LockOutlined class="text-[11px]" />
                登录即代表同意系统安全与隐私协议
              </span>
            </div>

            <div class="mt-4 flex justify-center">
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
