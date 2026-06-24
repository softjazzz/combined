<template>
  <div class="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-950 via-slate-900 to-slate-950 text-white relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="pointer-events-none absolute inset-0">
      <!-- 远景星云与光晕 -->
      <div class="absolute -top-40 -left-40 w-[36rem] h-[36rem] rounded-full bg-gradient-to-br from-emerald-500/10 via-teal-500/10 to-cyan-500/10 blur-3xl" />
      <div class="absolute -bottom-56 -right-56 w-[40rem] h-[40rem] rounded-full bg-gradient-to-tr from-blue-500/10 via-indigo-500/10 to-purple-500/10 blur-3xl" />

      <!-- 线路网格 -->
      <div
        class="absolute inset-0 opacity-[0.06]"
        style="background-image: linear-gradient(rgba(255,255,255,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.12) 1px, transparent 1px); background-size: 40px 40px;"
      />

      <!-- 粒子群组 -->
      <div class="absolute inset-0">
        <span class="ai-particle absolute left-1/5 top-1/3 w-1.5 h-1.5 bg-emerald-400/80 rounded-full" />
        <span
          class="ai-particle absolute left-2/3 top-1/4 w-1 h-1 bg-teal-400/80 rounded-full"
          style="animation-delay:.3s"
        />
        <span
          class="ai-particle absolute left-1/3 top-2/3 w-1 h-1 bg-cyan-400/80 rounded-full"
          style="animation-delay:.6s"
        />
        <span
          class="ai-particle absolute left-3/4 top-1/2 w-1.5 h-1.5 bg-blue-400/80 rounded-full"
          style="animation-delay:.9s"
        />
      </div>
    </div>

    <!-- 顶部导航 -->
    <header class="relative z-10">
      <div class="mx-auto max-w-7xl px-6 py-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 via-teal-600 to-cyan-700 flex items-center justify-center shadow-lg ai-logo">
            <svg
              class="w-6 h-6 text-white"
              viewBox="0 0 24 24"
              fill="currentColor"
            ><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></svg>
          </div>
          <div>
            <div class="text-lg font-semibold tracking-wide">
              大模型病案质控系统
            </div>
            <div class="text-xs text-emerald-200/80 tracking-wider">
              用户注册 · User Registration
            </div>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <router-link 
            to="/auth/login" 
            class="text-sm text-slate-300 hover:text-white transition-colors"
          >
            已有账号？立即登录
          </router-link>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="relative z-10">
      <div class="mx-auto max-w-4xl px-6 py-10">
        <div class="text-center mb-10">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-200 text-xs mb-5">
            <UserAddOutlined /> 账户注册 · 加入医疗质控团队
          </div>
          <h1 class="text-3xl md:text-4xl font-extrabold leading-tight tracking-tight">
            <span class="bg-gradient-to-r from-white via-emerald-200 to-emerald-400 bg-clip-text text-transparent">申请加入</span>
            <br>
            <span class="bg-gradient-to-r from-emerald-300 via-teal-400 to-cyan-500 bg-clip-text text-transparent">智能质控平台</span>
          </h1>
          <p class="mt-4 text-slate-300/90 max-w-2xl mx-auto">
            填写以下信息提交注册申请，管理员审核通过后您将收到邮件通知。
          </p>
        </div>

        <!-- 注册表单容器 -->
        <div class="relative max-w-2xl mx-auto">
          <!-- 背板光效 -->
          <div class="absolute -inset-1 rounded-[1.75rem] bg-gradient-to-r from-emerald-500/30 via-teal-500/30 to-cyan-500/30 blur-xl" />
          <div class="relative rounded-[1.5rem] bg-slate-900/60 backdrop-blur-xl ring-1 ring-white/10 p-8 tech-border">
            <!-- 注册表单 -->
            <RegisterForm 
              :loading="loading"
              @register="handleRegister"
              @show-terms="showTermsModal = true"
              @show-privacy="showPrivacyModal = true"
            />
          </div>
        </div>
      </div>
    </main>

    <!-- 服务条款模态框 -->
    <a-modal
      v-model:open="showTermsModal"
      title="服务条款"
      :footer="null"
      width="800px"
      class="terms-modal"
    >
      <div class="max-h-96 overflow-y-auto text-sm space-y-4">
        <h3 class="font-semibold">
          1. 服务说明
        </h3>
        <p>本系统为医疗质控管理平台，提供病案质量控制、分析和管理服务。</p>
        
        <h3 class="font-semibold">
          2. 用户责任
        </h3>
        <p>用户应确保提供信息的真实性，遵守医疗数据安全规范，不得滥用系统功能。</p>
        
        <h3 class="font-semibold">
          3. 数据安全
        </h3>
        <p>系统采用严格的数据加密和访问控制措施，确保医疗数据的安全性和隐私性。</p>
        
        <h3 class="font-semibold">
          4. 服务变更
        </h3>
        <p>我们保留随时修改或终止服务的权利，重要变更将提前通知用户。</p>
      </div>
    </a-modal>

    <!-- 隐私政策模态框 -->
    <a-modal
      v-model:open="showPrivacyModal"
      title="隐私政策"
      :footer="null"
      width="800px"
      class="privacy-modal"
    >
      <div class="max-h-96 overflow-y-auto text-sm space-y-4">
        <h3 class="font-semibold">
          1. 信息收集
        </h3>
        <p>我们收集您的基本信息、使用记录和操作日志，用于提供和改进服务。</p>
        
        <h3 class="font-semibold">
          2. 信息使用
        </h3>
        <p>收集的信息仅用于系统功能实现、安全监控和服务优化，不会用于其他商业目的。</p>
        
        <h3 class="font-semibold">
          3. 信息保护
        </h3>
        <p>我们采用行业标准的安全措施保护您的个人信息，防止未经授权的访问、使用或泄露。</p>
        
        <h3 class="font-semibold">
          4. 信息共享
        </h3>
        <p>除法律要求外，我们不会与第三方共享您的个人信息。</p>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { UserAddOutlined } from '@ant-design/icons-vue'
import type { RegisterRequest } from '@/types/auth'
import RegisterForm from '@/components/auth/RegisterForm.vue'

// 路由
const router = useRouter()

// 状态
const loading = ref(false)
const showTermsModal = ref(false)
const showPrivacyModal = ref(false)

// 处理注册
const handleRegister = async (formData: RegisterRequest) => {
  try {
    loading.value = true
    
    // 模拟注册API调用
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    // 模拟注册成功
    message.success('注册申请已提交，请等待管理员审核')
    
    // 显示成功提示并跳转到登录页
    setTimeout(() => {
      router.push('/auth/login')
    }, 2000)
    
  } catch (error) {
    console.error('注册失败:', error)
    message.error('注册申请提交失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 复用登录页面的样式 */
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

@keyframes circuitPulse {
  0%, 100% {
    box-shadow: 0 0 5px rgba(16, 185, 129, 0.3);
  }
  50% {
    box-shadow: 0 0 20px rgba(16, 185, 129, 0.6), 0 0 30px rgba(16, 185, 129, 0.4);
  }
}

@keyframes borderScan {
  0% {
    left: -100%;
  }
  100% {
    left: 100%;
  }
}

.ai-logo {
  animation: circuitPulse 3s ease-in-out infinite;
}

.ai-particle {
  animation: particleFloat 4s ease-in-out infinite;
}

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
  background: linear-gradient(90deg, transparent, rgba(16, 185, 129, 0.4), transparent);
  animation: borderScan 2s linear infinite;
}

/* 渐变文字效果 */
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

/* 模态框样式 */
:deep(.terms-modal .ant-modal-content),
:deep(.privacy-modal .ant-modal-content) {
  background: rgb(15 23 42);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.terms-modal .ant-modal-header),
:deep(.privacy-modal .ant-modal-header) {
  background: rgb(15 23 42);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.terms-modal .ant-modal-title),
:deep(.privacy-modal .ant-modal-title) {
  color: rgb(241 245 249);
}

:deep(.terms-modal .ant-modal-body),
:deep(.privacy-modal .ant-modal-body) {
  color: rgb(203 213 225);
}

:deep(.terms-modal .ant-modal-close),
:deep(.privacy-modal .ant-modal-close) {
  color: rgb(148 163 184);
}

:deep(.terms-modal .ant-modal-close:hover),
:deep(.privacy-modal .ant-modal-close:hover) {
  color: rgb(241 245 249);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .mx-auto.max-w-4xl {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  
  .text-3xl {
    font-size: 1.875rem;
  }
  
  .p-8 {
    padding: 1.5rem;
  }
}
</style>
