<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50 relative overflow-hidden">
    <!-- 顶部品牌与优势点（去掉全局黑条后，这里自带品牌） -->
    <header class="relative z-10">
      <div class="mx-auto max-w-7xl px-6 py-8 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 via-indigo-600 to-purple-700 flex items-center justify-center shadow-lg">
            <svg class="w-7 h-7 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              <circle cx="12" cy="12" r="3" fill="currentColor"/>
            </svg>
          </div>
          <div>
            <div class="text-lg font-bold text-gray-800">DeepThink</div>
            <div class="text-sm text-gray-600 font-medium tracking-wide">AI-Powered Medical Record QC System</div>
          </div>
        </div>

        <div class="hidden md:flex items-center gap-6 text-sm text-gray-600">
          <span class="flex items-center gap-2"><CheckCircleOutlined class="text-green-500" /> 安全认证</span>
          <span class="flex items-center gap-2"><SafetyCertificateOutlined class="text-blue-500" /> 数据保护</span>
          <span class="flex items-center gap-2"><ThunderboltOutlined class="text-orange-500" /> 高效处理</span>
        </div>
      </div>
    </header>

    <!-- 主体：左侧介绍 + 右侧登录卡片 -->
    <main class="relative z-10">
      <div class="mx-auto max-w-7xl px-6 py-12 grid grid-cols-1 lg:grid-cols-2 gap-20 items-start">
        <!-- 左侧产品介绍（医保智能审核版本） -->
        <section class="space-y-8">
          <h1 class="text-4xl md:text-5xl font-bold leading-tight">
            <span class="bg-gradient-to-r from-blue-600 via-indigo-700 to-purple-800 bg-clip-text text-transparent">智慧医保临床实时质控系统</span>
          </h1>
          <div class="text-xl md:text-2xl font-semibold text-gray-700 whitespace-nowrap">
            将医保与院内质控规则嵌入临床流程，实现事中提醒与干预
          </div>

          <!-- 关键指标 -->
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div class="text-center p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="text-3xl font-bold text-blue-600">98.5%</div>
              <div class="text-sm text-gray-600 mt-2">质控准确率</div>
            </div>
            <div class="text-center p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="text-3xl font-bold text-green-600">500万+</div>
              <div class="text-sm text-gray-600 mt-2">处理病案数</div>
            </div>
            <div class="text-center p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="text-3xl font-bold text-orange-600">0.3秒</div>
              <div class="text-sm text-gray-600 mt-2">平均响应时间</div>
            </div>
          </div>

          <!-- 核心功能（来自 PRD 摘要） -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center">
                <SafetyCertificateOutlined class="text-blue-600 text-lg" />
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">医生端实时提醒</div>
                <div class="text-gray-600 text-sm">医嘱保存/签署瞬间识别违规，提醒/警告/拦截三级处置</div>
              </div>
            </div>
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center">
                <EyeOutlined class="text-green-600 text-lg" />
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">规则引擎与管理后台</div>
                <div class="text-gray-600 text-sm">规则数字化、版本管理、沙箱测试与在线发布</div>
              </div>
            </div>
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center">
                <StarOutlined class="text-orange-600 text-lg" />
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">数据分析与监控看板</div>
                <div class="text-gray-600 text-sm">违规趋势、科室/医生排行、追溯与报表导出</div>
              </div>
            </div>
          </div>
        </section>

        <!-- 右侧登录卡片 -->
        <section class="pl-4">
          <div class="relative max-w-md ml-auto w-full">
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-400/10 via-indigo-400/10 to-purple-400/10 backdrop-blur-sm"></div>
            <div class="relative backdrop-blur-lg bg-white/85 rounded-2xl shadow-2xl border border-white/30 p-8">
              <div class="mb-6">
                <h2 class="text-2xl font-bold text-gray-900">用户登录</h2>
                <p class="text-gray-600 text-sm">请输入您的账户信息</p>
              </div>

              <LoginForm ref="loginFormRef" :loading="loading" @login="onLogin" @forgot-password="onForgot" />

              <!-- 演示账号模块 -->
              <DemoAccounts :loading="loading" @select-account="onSelectDemoAccount" />
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
  </template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginForm from '@/components/auth/LoginForm.vue'
import DemoAccounts from '@/components/auth/DemoAccounts.vue'
import { CheckCircleOutlined, SafetyCertificateOutlined, ThunderboltOutlined, EyeOutlined, StarOutlined } from '@ant-design/icons-vue'

const router = useRouter()
const auth = useAuthStore()
const loading = computed(() => auth.loading)
const error = computed(() => auth.error)
const loginFormRef = ref()

async function onLogin(payload: { email: string, password: string }) {
  const result = await auth.signInWithPassword(payload.email, payload.password)
  if (result && result.success) {
    let redirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
    if (!redirect || redirect === '/' || redirect === '/login') {
      redirect = '/dashboard'
    }
    router.push(redirect)
  }
}

function onForgot() {}

async function onSelectDemoAccount(account: { email: string, password: string, role: string }) {
  // 使用 LoginForm 的 setFormData 方法填充表单
  if (loginFormRef.value) {
    loginFormRef.value.setFormData({
      email: account.email,
      password: account.password,
      role: account.role
    })

    // 自动触发登录流程
    await onLogin({
      email: account.email,
      password: account.password
    })
  }
}
</script>



