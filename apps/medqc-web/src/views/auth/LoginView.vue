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
  <div class="min-h-screen relative overflow-hidden bg-[#0f172a] flex flex-col">
    <!-- 动态深空背景 -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <!-- 主渐变光斑 -->
      <div class="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] rounded-full bg-blue-600/20 blur-[120px] animate-pulse-slow"></div>
      <div class="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] rounded-full bg-indigo-600/20 blur-[100px] animate-pulse-slow delay-1000"></div>
      <div class="absolute top-[20%] right-[20%] w-[40%] h-[40%] rounded-full bg-purple-600/10 blur-[80px] animate-float-slow"></div>
      
      <!-- 科技感网格 -->
      <div class="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-soft-light"></div>
      <div class="absolute inset-0" 
           style="background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px); background-size: 60px 60px; mask-image: radial-gradient(circle at center, black 40%, transparent 80%); -webkit-mask-image: radial-gradient(circle at center, black 40%, transparent 80%);">
      </div>
    </div>

    <!-- 顶部品牌条 -->
    <header class="relative z-10 w-full">
      <div class="mx-auto max-w-7xl px-6 py-6 flex items-center justify-between">
        <div class="flex items-center gap-3 group cursor-pointer">
          <div class="relative w-10 h-10 flex items-center justify-center">
            <div class="absolute inset-0 bg-blue-500/30 rounded-xl blur-lg group-hover:bg-blue-400/40 transition-all duration-500"></div>
            <div class="relative w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-lg border border-white/10">
               <MedicineBoxOutlined class="text-white text-xl" />
            </div>
          </div>
          <div>
            <div class="text-xl font-bold text-white tracking-tight">DeepThink</div>
            <div class="text-xs text-blue-200/60 font-medium tracking-wider uppercase">AI Medical QC</div>
          </div>
        </div>
        <div class="hidden md:flex items-center gap-8 text-sm font-medium">
          <span class="flex items-center gap-2 text-slate-300 hover:text-white transition-colors cursor-pointer group">
            <SafetyCertificateOutlined class="text-blue-400 group-hover:scale-110 transition-transform"/> 安全认证
          </span>
          <span class="flex items-center gap-2 text-slate-300 hover:text-white transition-colors cursor-pointer group">
            <ThunderboltOutlined class="text-indigo-400 group-hover:scale-110 transition-transform"/> 高效处理
          </span>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="relative z-10 flex-1 flex items-center">
      <div class="mx-auto max-w-7xl px-6 w-full grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        
        <!-- 左：产品价值主张 (占据 7 列) -->
        <section class="lg:col-span-7 space-y-10 text-white">
          <div class="space-y-4">
            <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-400/20 text-blue-300 text-xs font-semibold tracking-wide uppercase animate-fade-in-up">
              <span class="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
              Next-Gen Medical AI
            </div>
            <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold leading-tight tracking-tight animate-fade-in-up delay-100">
              <span class="block">智能重塑</span>
              <span class="bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">病案质控新范式</span>
            </h1>
            <p class="text-lg text-slate-300/80 max-w-xl leading-relaxed animate-fade-in-up delay-200">
              DeepThink 利用大语言模型技术，为您提供深度语义理解、精准缺陷识别与实时修正建议，将病案质量管理提升至全新高度。
            </p>
          </div>

          <!-- 悬浮数据卡片 -->
          <div class="grid grid-cols-3 gap-6 animate-fade-in-up delay-300">
            <div class="relative group">
              <div class="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <div class="relative p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-all duration-300">
                <div class="text-3xl font-bold text-white mb-1">99%</div>
                <div class="text-xs text-slate-400">AI 识别准确率</div>
              </div>
            </div>
            <div class="relative group">
              <div class="absolute inset-0 bg-gradient-to-br from-indigo-500/10 to-transparent rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <div class="relative p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-all duration-300">
                <div class="text-3xl font-bold text-white mb-1">500<span class="text-lg">万+</span></div>
                <div class="text-xs text-slate-400">已处理病案数</div>
              </div>
            </div>
            <div class="relative group">
              <div class="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-transparent rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              <div class="relative p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-all duration-300">
                <div class="text-3xl font-bold text-white mb-1">0.3<span class="text-lg">s</span></div>
                <div class="text-xs text-slate-400">平均响应速度</div>
              </div>
            </div>
          </div>

          <!-- 简化的特性列表 -->
          <div class="flex flex-wrap gap-4 animate-fade-in-up delay-400">
            <div class="flex items-center gap-3 px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-sm text-slate-300">
              <CheckCircleOutlined class="text-blue-400" /> 标准化质控流程
            </div>
            <div class="flex items-center gap-3 px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-sm text-slate-300">
              <RobotOutlined class="text-indigo-400" /> 智能缺陷修正
            </div>
            <div class="flex items-center gap-3 px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-sm text-slate-300">
              <BarChartOutlined class="text-purple-400" /> 数据驱动决策
            </div>
          </div>
        </section>

        <!-- 右：登录卡片 (占据 5 列) -->
        <section class="lg:col-span-5 w-full max-w-md mx-auto animate-fade-in-right">
          <div class="relative">
            <!-- 卡片背后的光晕 -->
            <div class="absolute -inset-1 bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl blur opacity-30 animate-tilt"></div>
            
            <!-- 玻璃态卡片 -->
            <div class="relative bg-slate-900/60 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
              <!-- 顶部高光 -->
              <div class="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent"></div>

              <div class="p-8 md:p-10">
                <div class="text-center mb-8">
                  <h2 class="text-2xl font-bold text-white mb-2">欢迎回来</h2>
                  <p class="text-slate-400 text-sm">登录 DeepThink 开始智能质控之旅</p>
                </div>

                <!-- 登录表单 -->
                <LoginForm
                  :loading="loading"
                  @login="handleLogin"
                  @forgot-password="handleForgotPassword"
                  class="login-form-dark"
                />

                <!-- 演示账号折叠 -->
                <div class="mt-8 pt-6 border-t border-white/5">
                  <div
                    @click="toggleDemoAccounts"
                    class="flex items-center justify-between cursor-pointer group select-none"
                  >
                    <span class="text-xs font-medium text-slate-500 group-hover:text-blue-400 transition-colors">演示账号快速通道</span>
                    <DownOutlined 
                      class="text-xs text-slate-600 transition-transform duration-300" 
                      :class="{ 'rotate-180': showDemoAccounts }"
                    />
                  </div>
                  
                  <div
                    class="overflow-hidden transition-all duration-300 ease-out"
                    :style="{ maxHeight: showDemoAccounts ? '200px' : '0px', opacity: showDemoAccounts ? 1 : 0 }"
                  >
                    <div class="grid grid-cols-1 gap-2 mt-4">
                      <button @click="handleDemoLogin('admin')" class="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 border border-transparent hover:border-blue-500/30 transition-all group text-left">
                        <div class="w-8 h-8 rounded bg-blue-500/20 text-blue-400 flex items-center justify-center text-xs font-bold">Admin</div>
                        <div>
                           <div class="text-sm text-slate-200 font-medium">系统管理员</div>
                           <div class="text-[10px] text-slate-500">admin@medqc.com / admin888</div>
                        </div>
                      </button>
                      <button @click="handleDemoLogin('qc_manager')" class="flex items-center gap-3 p-3 rounded-lg bg-white/5 hover:bg-white/10 border border-transparent hover:border-indigo-500/30 transition-all group text-left">
                        <div class="w-8 h-8 rounded bg-indigo-500/20 text-indigo-400 flex items-center justify-center text-xs font-bold">QC</div>
                        <div>
                           <div class="text-sm text-slate-200 font-medium">病案编码员</div>
                           <div class="text-[10px] text-slate-500">qc@medqc.com / qc123456</div>
                        </div>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
    
    <!-- 底部版权 -->
    <footer class="relative z-10 py-6 text-center text-xs text-slate-500/60">
      &copy; {{ new Date().getFullYear() }} DeepThink Medical AI. All rights reserved.
    </footer>
  </div>
</template>



<style scoped>
/* 基础动画 */
@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes fade-in-right {
  from { opacity: 0; transform: translateX(20px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse-slow {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.1); }
}

@keyframes float-slow {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-20px) rotate(5deg); }
}

@keyframes tilt {
  0%, 50%, 100% { transform: rotate(0deg); }
  25% { transform: rotate(1deg); }
  75% { transform: rotate(-1deg); }
}

.animate-fade-in-up { animation: fade-in-up 0.8s ease-out forwards; opacity: 0; }
.animate-fade-in-right { animation: fade-in-right 0.8s ease-out forwards; opacity: 0; }
.animate-pulse-slow { animation: pulse-slow 8s ease-in-out infinite; }
.animate-float-slow { animation: float-slow 10s ease-in-out infinite; }
.animate-tilt { animation: tilt 10s infinite linear; }

.delay-100 { animation-delay: 100ms; }
.delay-200 { animation-delay: 200ms; }
.delay-300 { animation-delay: 300ms; }
.delay-400 { animation-delay: 400ms; }

/* 登录表单暗色主题适配 */
:deep(.login-form-dark .ant-form-item-label > label) {
  color: #94a3b8 !important; /* Slate-400 */
}

:deep(.login-form-dark .ant-input),
:deep(.login-form-dark .ant-input-password) {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  color: #f1f5f9 !important; /* Slate-100 */
  border-radius: 8px;
  padding: 10px 12px !important;
}

:deep(.login-form-dark .ant-input::placeholder) {
  color: #64748b !important; /* Slate-500 */
}

:deep(.login-form-dark .ant-input:focus),
:deep(.login-form-dark .ant-input-password:focus-within) {
  border-color: #3b82f6 !important;
  background-color: rgba(255, 255, 255, 0.1) !important;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
}

:deep(.login-form-dark .ant-input-password .ant-input) {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

:deep(.login-form-dark .ant-input-suffix) {
  color: #64748b !important;
}

/* 按钮样式覆盖 */
:deep(.login-form-dark .ant-btn-primary) {
  background: linear-gradient(135deg, #3b82f6 0%, #4f46e5 100%) !important;
  border: none !important;
  height: 44px;
  border-radius: 8px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  transition: all 0.3s ease;
}

:deep(.login-form-dark .ant-btn-primary:hover) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
  filter: brightness(1.1);
}

/* Checkbox 样式 */
:deep(.login-form-dark .ant-checkbox-inner) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

:deep(.login-form-dark .ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #3b82f6 !important;
  border-color: #3b82f6 !important;
}

:deep(.login-form-dark .ant-checkbox-wrapper) {
  color: #94a3b8 !important;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: #0f172a;
}
::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #475569;
}
</style>
