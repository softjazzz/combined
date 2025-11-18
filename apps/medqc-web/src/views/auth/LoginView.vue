<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { useAuthStore } from '@/stores/auth'
import {
  LoginOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
  RobotOutlined,
  EyeOutlined,
  StarOutlined,
  CheckCircleOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons-vue'
import LoginForm from '@/components/auth/LoginForm.vue'

// 路由和状态管理
const router = useRouter()
const authStore = useAuthStore()

// 页面状态
const loading = ref(false)
const showDemoAccounts = ref(false)

// 切换演示账号显示状态
const toggleDemoAccounts = () => {
  showDemoAccounts.value = !showDemoAccounts.value
}



// 处理登录
const handleLogin = async (loginData) => {
  try {
    loading.value = true

    // 确保role是字符串而不是枚举
    const role = typeof loginData.role === 'string' ? loginData.role : String(loginData.role)

    console.log('🚀 登录请求:', {
      email: loginData.email,
      role: role,
      roleType: typeof role
    })

    const result = await authStore.signIn(loginData.email, loginData.password, role)

    if (result.success) {
      message.success('登录成功')
      console.log('✅ 登录成功，准备跳转到dashboard')
      const redirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
      await router.push(redirect)
    } else {
      console.error('❌ 登录失败:', result.error)
      message.error(result.error || '登录失败')
    }
  } catch (error: unknown) {
    console.error('Login error:', error)
    message.error('登录过程中发生错误')
  } finally {
    loading.value = false
  }
}

const handleForgotPassword = () => {
  router.push('/auth/forgot-password')
}

const handleDemoLogin = async (role: 'admin' | 'qc_manager' | 'doctor') => {
  const demoAccounts = {
    admin: { email: 'admin@medqc.com', password: 'admin888' },
    qc_manager: { email: 'qc@medqc.com', password: 'qc123456' },
    doctor: { email: 'doctor@medqc.com', password: 'doctor123' }
  } as const

  const account = demoAccounts[role]

  // 直接调用登录处理函数
  await handleLogin({
    email: account.email,
    password: account.password,
    role: role
  })
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50 relative overflow-hidden">
    <!-- 简洁的背景装饰 -->
    <div class="pointer-events-none absolute inset-0">
      <!-- 医疗主题的几何图案 -->
      <div class="absolute top-20 right-20 w-32 h-32 rounded-full bg-blue-100/50"></div>
      <div class="absolute bottom-32 left-16 w-24 h-24 rounded-full bg-green-100/50"></div>
      <div class="absolute top-1/2 left-1/4 w-16 h-16 rounded-full bg-blue-200/30"></div>

      <!-- 网格背景 -->
      <div class="absolute inset-0 opacity-[0.02]" style="background-image: linear-gradient(rgba(59, 130, 246, 0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59, 130, 246, 0.5) 1px, transparent 1px); background-size: 50px 50px;"></div>
    </div>

    <!-- 顶部品牌条 -->
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
            <div class="text-sm text-gray-600 font-medium tracking-wide">
              AI-Powered Medical Record QC System
            </div>
          </div>
        </div>
        <div class="hidden md:flex items-center gap-6 text-sm text-gray-600">
          <span class="flex items-center gap-2 hover:text-green-600 transition-colors"><CheckCircleOutlined class="text-green-500"/> 安全认证</span>
          <span class="flex items-center gap-2 hover:text-blue-600 transition-colors"><SafetyCertificateOutlined class="text-blue-500"/> 数据保护</span>
          <span class="flex items-center gap-2 hover:text-orange-600 transition-colors"><ThunderboltOutlined class="text-orange-500"/> 高效处理</span>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="relative z-10">
      <div class="mx-auto max-w-7xl px-6 py-12 grid grid-cols-1 lg:grid-cols-2 gap-20 items-start">
        <!-- 左：产品介绍 -->
        <section class="space-y-6 pt-8 pr-4">
          <h1 class="text-3xl md:text-4xl lg:text-5xl font-bold leading-tight animate-float whitespace-nowrap">
            <span class="bg-gradient-to-r from-blue-600 via-indigo-700 to-purple-800 bg-clip-text text-transparent animate-glow">
              DeepThink智能病案质控系统
            </span>
          </h1>
          <h2 class="text-xl md:text-2xl font-semibold mt-4 animate-fade-in-up">
            <span class="bg-gradient-to-r from-indigo-600 via-purple-600 to-blue-700 bg-clip-text text-transparent">
              大模型原生新一代病案质控系统
            </span>
          </h2>
          <div class="mt-3 animate-fade-in-up">
            <p class="text-xs md:text-sm lg:text-base font-medium tracking-wide whitespace-nowrap">
              <span class="bg-gradient-to-r from-blue-500/80 via-indigo-500/80 to-purple-500/80 bg-clip-text text-transparent">
                Next-Generation Medical Record QC System Powered by Large Language Models
              </span>
            </p>
          </div>

          <!-- 核心指标 -->
          <div class="grid grid-cols-3 gap-6">
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

          <!-- 核心特性 -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center">
                <SafetyCertificateOutlined class="text-blue-600 text-lg"/>
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">标准化质控</div>
                <div class="text-gray-600 text-sm">遵循医疗行业标准和规范</div>
              </div>
            </div>
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-green-100 flex items-center justify-center">
                <EyeOutlined class="text-green-600 text-lg"/>
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">智能分析</div>
                <div class="text-gray-600 text-sm">AI辅助的病案质量分析</div>
              </div>
            </div>
            <div class="flex items-start gap-4 p-6 bg-white rounded-xl shadow-sm border border-gray-100">
              <div class="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center">
                <StarOutlined class="text-orange-600 text-lg"/>
              </div>
              <div>
                <div class="font-semibold text-gray-900 mb-1">数据驱动</div>
                <div class="text-gray-600 text-sm">基于数据的质量改进建议</div>
              </div>
            </div>
          </div>
        </section>

        <!-- 右：登录表单 -->
        <section class="pl-4">
          <div class="relative max-w-md mx-auto">
            <!-- 优化的毛玻璃背景 -->
            <div class="absolute inset-0 rounded-2xl bg-gradient-to-br from-blue-400/10 via-indigo-400/10 to-purple-400/10 backdrop-blur-sm"></div>
            <div class="relative backdrop-blur-lg bg-white/85 rounded-2xl shadow-2xl border border-white/30 p-8">
              <div class="text-center mb-8">
                <h2 class="text-2xl font-bold text-gray-900 mb-2">用户登录</h2>
                <p class="text-gray-600">请输入您的账户信息</p>
              </div>

            <!-- 使用登录表单组件 -->
            <LoginForm
              :loading="loading"
              @login="handleLogin"
              @forgot-password="handleForgotPassword"
            />

            <!-- 演示账号折叠区域 -->
            <div class="mt-6">
              <!-- 可点击的标题栏 -->
              <div
                @click="toggleDemoAccounts"
                class="flex items-center justify-center gap-2 py-3 cursor-pointer hover:bg-gray-50 rounded-lg transition-colors group"
              >
                <div class="flex-1 flex items-center justify-center gap-2">
                  <div class="w-full border-t border-gray-200"></div>
                  <span class="px-4 text-sm text-gray-500 whitespace-nowrap group-hover:text-gray-700 transition-colors">
                    演示账号
                  </span>
                  <div class="w-full border-t border-gray-200"></div>
                </div>
                <div class="text-gray-400 group-hover:text-gray-600 transition-all duration-200"
                     :class="{ 'rotate-180': showDemoAccounts }">
                  <DownOutlined class="text-xs" />
                </div>
              </div>

              <!-- 可折叠的演示账号列表 -->
              <div
                class="overflow-hidden transition-all duration-300 ease-in-out"
                :class="showDemoAccounts ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'"
              >
                <div class="space-y-3 pt-4">
                  <button @click="handleDemoLogin('admin')" class="w-full group p-4 text-left rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors">
                    <div class="flex items-center gap-3">
                      <div class="w-10 h-10 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">管</div>
                      <div class="flex-1">
                        <div class="font-medium text-gray-900">系统管理员</div>
                        <div class="text-sm text-gray-500">admin@medqc.com / admin888</div>
                      </div>
                      <LoginOutlined class="text-gray-400 group-hover:text-blue-500"/>
                    </div>
                  </button>

                  <button @click="handleDemoLogin('qc_manager')" class="w-full group p-4 text-left rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors">
                    <div class="flex items-center gap-3">
                      <div class="w-10 h-10 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold">质</div>
                      <div class="flex-1">
                        <div class="font-medium text-gray-900">质控主管</div>
                        <div class="text-sm text-gray-500">qc@medqc.com / qc123456</div>
                      </div>
                      <LoginOutlined class="text-gray-400 group-hover:text-blue-500"/>
                    </div>
                  </button>

                  <button @click="handleDemoLogin('doctor')" class="w-full group p-4 text-left rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors">
                    <div class="flex items-center gap-3">
                      <div class="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center text-white font-bold">医</div>
                      <div class="flex-1">
                        <div class="font-medium text-gray-900">医务人员</div>
                        <div class="text-sm text-gray-500">doctor@medqc.com / doctor123</div>
                      </div>
                      <LoginOutlined class="text-gray-400 group-hover:text-blue-500"/>
                    </div>
                  </button>
                </div>
              </div>
            </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>



<style scoped>
/* 现代化医疗AI系统样式 */

/* 自定义动画效果 */
@keyframes fade-in-up {
  0% {
    opacity: 0;
    transform: translateY(20px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes glow {
  0%, 100% {
    text-shadow: 0 0 5px rgba(59, 130, 246, 0.3), 0 0 10px rgba(99, 102, 241, 0.2), 0 0 15px rgba(139, 92, 246, 0.1);
  }
  50% {
    text-shadow: 0 0 10px rgba(59, 130, 246, 0.4), 0 0 20px rgba(99, 102, 241, 0.3), 0 0 30px rgba(139, 92, 246, 0.2);
  }
}

@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-5px);
  }
}

.animate-fade-in-up {
  animation: fade-in-up 1s ease-out;
}

.animate-glow {
  animation: glow 3s ease-in-out infinite;
}

.animate-float {
  animation: float 6s ease-in-out infinite;
}

/* 输入框明亮主题优化 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding-left: 0 !important;
  color: rgb(55 65 81) !important;
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

:deep(.ant-input-password:focus),
:deep(.ant-input-password-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-input-password .ant-input) {
  padding-left: 0 !important;
  color: rgb(55 65 81) !important;
}

:deep(.ant-input-password .ant-input-suffix) {
  color: rgb(107 114 128) !important;
}

/* 按钮深色主题优化 */
:deep(.ant-btn-primary) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-btn-primary:hover) {
  border: none !important;
  box-shadow: none !important;
}

/* 复选框深色主题 */
:deep(.ant-checkbox-wrapper) {
  color: rgb(203 213 225) !important;
  font-weight: 500;
}

:deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #06b6d4 !important;
  border-color: #06b6d4 !important;
}

:deep(.ant-checkbox-inner) {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

/* 表单项深色主题 */
:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

:deep(.ant-form-item-label > label) {
  color: rgb(203 213 225) !important;
}

/* 现代化科技感动画效果 */
@keyframes float {
  0%, 100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(-10px);
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideInLeft {
  from {
    opacity: 0;
    transform: translateX(-30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* AI科技感动画 */
@keyframes dataFlow {
  0% {
    transform: translateX(-100%);
    opacity: 0;
  }
  50% {
    opacity: 1;
  }
  100% {
    transform: translateX(100%);
    opacity: 0;
  }
}

@keyframes circuitPulse {
  0%, 100% {
    box-shadow: 0 0 5px rgba(6, 182, 212, 0.3);
  }
  50% {
    box-shadow: 0 0 20px rgba(6, 182, 212, 0.6), 0 0 30px rgba(6, 182, 212, 0.4);
  }
}

@keyframes aiGlow {
  0%, 100% {
    filter: brightness(1) saturate(1);
  }
  50% {
    filter: brightness(1.2) saturate(1.3);
  }
}

@keyframes particleFloat {
  0%, 100% {
    transform: translateY(0px) translateX(0px);
  }
  25% {
    transform: translateY(-5px) translateX(2px);
  }
  50% {
    transform: translateY(-10px) translateX(0px);
  }
  75% {
    transform: translateY(-5px) translateX(-2px);
  }
}

/* 应用动画 */
.min-h-screen > div:first-child {
  animation: slideInLeft 0.8s ease-out;
}

.min-h-screen > div:last-child {
  animation: slideInRight 0.8s ease-out;
}

/* 悬浮效果 */
.group:hover .w-12 {
  animation: float 2s ease-in-out infinite;
}

/* 渐变文字效果增强 */
.bg-gradient-to-r.bg-clip-text {
  background-size: 200% 200%;
  animation: gradientShift 4s ease infinite;
}

@keyframes gradientShift {
  0%, 100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}

/* AI科技感特效 */
.ai-logo {
  animation: circuitPulse 3s ease-in-out infinite;
}

.ai-particle {
  animation: particleFloat 4s ease-in-out infinite;
}

.data-stream {
  animation: dataFlow 3s linear infinite;
}

/* 科技感边框效果 */
.tech-border {
  position: relative;
  overflow: hidden;
}

.tech-border::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.4), transparent);
  animation: borderScan 2s linear infinite;
}

@keyframes borderScan {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

/* 悬浮卡片增强效果 */
.hover-card {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.hover-card:hover {
  transform: translateY(-8px) scale(1.02);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1), 0 0 20px rgba(6, 182, 212, 0.1);
}

/* AI状态指示器动画 */
.ai-status {
  animation: aiGlow 2s ease-in-out infinite;
}

/* 脉冲效果增强 */
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* 玻璃态效果 */
.backdrop-blur-sm {
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

/* 阴影层次 */
.shadow-2xl {
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.hover\:shadow-xl:hover {
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

/* 响应式设计优化 */
@media (max-width: 1024px) {
  .lg\:w-1\/2 {
    width: 100%;
  }

  .lg\:flex {
    display: none;
  }

  /* 移动端动画调整 */
  .min-h-screen > div:last-child {
    animation: fadeInUp 0.6s ease-out;
  }
}

@media (max-width: 640px) {
  /* 小屏幕优化 */
  .bg-white\/90 {
    margin: 1rem;
    padding: 1.5rem !important;
  }

  .h-14 {
    height: 3rem !important;
  }

  .text-4xl {
    font-size: 2rem !important;
  }

  .text-3xl {
    font-size: 1.875rem !important;
  }
}

/* 加载状态优化 */
:deep(.ant-btn-loading-icon) {
  margin-right: 8px;
}

/* 焦点状态增强 */
.focus\:border-blue-500:focus {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
}

/* 过渡效果统一 */
* {
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
}

/* 选择状态优化 */
::selection {
  background-color: rgba(59, 130, 246, 0.2);
  color: inherit;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
