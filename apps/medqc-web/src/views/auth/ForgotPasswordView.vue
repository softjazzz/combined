<template>
  <div class="min-h-screen bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-950 via-slate-900 to-slate-950 text-white relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="pointer-events-none absolute inset-0">
      <!-- 远景星云与光晕 -->
      <div class="absolute -top-40 -left-40 w-[36rem] h-[36rem] rounded-full bg-gradient-to-br from-amber-500/10 via-orange-500/10 to-red-500/10 blur-3xl" />
      <div class="absolute -bottom-56 -right-56 w-[40rem] h-[40rem] rounded-full bg-gradient-to-tr from-purple-500/10 via-pink-500/10 to-rose-500/10 blur-3xl" />

      <!-- 线路网格 -->
      <div
        class="absolute inset-0 opacity-[0.06]"
        style="background-image: linear-gradient(rgba(255,255,255,.12) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.12) 1px, transparent 1px); background-size: 40px 40px;"
      />

      <!-- 粒子群组 -->
      <div class="absolute inset-0">
        <span class="ai-particle absolute left-1/5 top-1/3 w-1.5 h-1.5 bg-amber-400/80 rounded-full" />
        <span
          class="ai-particle absolute left-2/3 top-1/4 w-1 h-1 bg-orange-400/80 rounded-full"
          style="animation-delay:.3s"
        />
        <span
          class="ai-particle absolute left-1/3 top-2/3 w-1 h-1 bg-red-400/80 rounded-full"
          style="animation-delay:.6s"
        />
        <span
          class="ai-particle absolute left-3/4 top-1/2 w-1.5 h-1.5 bg-pink-400/80 rounded-full"
          style="animation-delay:.9s"
        />
      </div>
    </div>

    <!-- 顶部导航 -->
    <header class="relative z-10">
      <div class="mx-auto max-w-7xl px-6 py-6 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-400 via-orange-600 to-red-700 flex items-center justify-center shadow-lg ai-logo">
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
            <div class="text-xs text-amber-200/80 tracking-wider">
              密码重置 · Password Reset
            </div>
          </div>
        </div>
        <div class="flex items-center gap-4">
          <router-link 
            to="/auth/login" 
            class="text-sm text-slate-300 hover:text-white transition-colors"
          >
            返回登录
          </router-link>
        </div>
      </div>
    </header>

    <!-- 主体区域 -->
    <main class="relative z-10">
      <div class="mx-auto max-w-md px-6 py-20">
        <div class="text-center mb-10">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-amber-400/30 bg-amber-400/10 text-amber-200 text-xs mb-5">
            <KeyOutlined /> 密码重置 · 找回账户访问权限
          </div>
          <h1 class="text-3xl font-extrabold leading-tight tracking-tight">
            <span class="bg-gradient-to-r from-white via-amber-200 to-amber-400 bg-clip-text text-transparent">忘记密码？</span>
          </h1>
          <p class="mt-4 text-slate-300/90">
            输入您的邮箱地址，我们将发送重置密码的链接给您。
          </p>
        </div>

        <!-- 重置表单容器 -->
        <div class="relative">
          <!-- 背板光效 -->
          <div class="absolute -inset-1 rounded-[1.75rem] bg-gradient-to-r from-amber-500/30 via-orange-500/30 to-red-500/30 blur-xl" />
          <div class="relative rounded-[1.5rem] bg-slate-900/60 backdrop-blur-xl ring-1 ring-white/10 p-8 tech-border">
            <!-- 步骤指示器 -->
            <div class="flex items-center justify-center mb-8">
              <div class="flex items-center gap-4">
                <div 
                  class="flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold transition-all duration-300"
                  :class="currentStep >= 1 ? 'bg-amber-500 text-white' : 'bg-slate-700 text-slate-400'"
                >
                  1
                </div>
                <div class="w-12 h-0.5 bg-slate-700 relative overflow-hidden">
                  <div 
                    class="absolute inset-0 bg-amber-500 transition-all duration-500"
                    :style="{ width: currentStep >= 2 ? '100%' : '0%' }"
                  />
                </div>
                <div 
                  class="flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold transition-all duration-300"
                  :class="currentStep >= 2 ? 'bg-amber-500 text-white' : 'bg-slate-700 text-slate-400'"
                >
                  2
                </div>
              </div>
            </div>

            <!-- 步骤1：输入邮箱 -->
            <div
              v-if="currentStep === 1"
              class="step-content"
            >
              <a-form
                ref="emailFormRef"
                :model="emailForm"
                :rules="emailRules"
                layout="vertical"
                size="large"
                @finish="handleSendResetEmail"
              >
                <a-form-item
                  name="email"
                  class="mb-6"
                >
                  <label class="block text-xs font-medium text-slate-300 mb-2">邮箱地址</label>
                  <div class="relative">
                    <a-input
                      v-model:value="emailForm.email"
                      placeholder="请输入注册时使用的邮箱"
                      class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-amber-400"
                    />
                    <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
                      <MailOutlined />
                    </div>
                  </div>
                </a-form-item>

                <a-button
                  type="primary"
                  html-type="submit"
                  :loading="sendingEmail"
                  block
                  size="large"
                  class="h-12 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 border-none font-semibold shadow-lg hover:shadow-xl"
                >
                  <SendOutlined
                    v-if="!sendingEmail"
                    class="mr-2"
                  />
                  发送重置邮件
                </a-button>
              </a-form>
            </div>

            <!-- 步骤2：邮件发送成功 -->
            <div
              v-else-if="currentStep === 2"
              class="step-content text-center"
            >
              <div class="mb-6">
                <div class="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                  <CheckCircleOutlined class="text-emerald-400 text-2xl" />
                </div>
                <h3 class="text-lg font-semibold text-slate-100 mb-2">
                  邮件已发送
                </h3>
                <p class="text-slate-400 text-sm">
                  重置密码的邮件已发送至 
                  <span class="text-amber-300 font-medium">{{ emailForm.email }}</span>
                </p>
              </div>

              <div class="space-y-4 mb-6">
                <div class="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
                  <div class="flex items-start gap-3">
                    <InfoCircleOutlined class="text-blue-400 text-sm mt-0.5" />
                    <div class="text-xs text-blue-200">
                      <div class="font-medium mb-1">
                        请注意：
                      </div>
                      <ul class="space-y-1 text-blue-200/80">
                        <li>• 请检查您的邮箱收件箱和垃圾邮件文件夹</li>
                        <li>• 重置链接将在24小时后失效</li>
                        <li>• 如果没有收到邮件，请检查邮箱地址是否正确</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex gap-3">
                <a-button
                  block
                  size="large"
                  :loading="sendingEmail"
                  class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20"
                  @click="handleResendEmail"
                >
                  <ReloadOutlined class="mr-2" />
                  重新发送
                </a-button>
                
                <a-button
                  type="primary"
                  block
                  size="large"
                  class="h-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 border-none font-semibold shadow-lg hover:shadow-xl"
                  @click="$router.push('/auth/login')"
                >
                  <LoginOutlined class="mr-2" />
                  返回登录
                </a-button>
              </div>
            </div>

            <!-- 倒计时提示 -->
            <div
              v-if="currentStep === 2 && countdown > 0"
              class="mt-4 text-center"
            >
              <p class="text-xs text-slate-400">
                {{ countdown }} 秒后可重新发送邮件
              </p>
            </div>
          </div>
        </div>

        <!-- 帮助信息 -->
        <div class="mt-8 text-center">
          <p class="text-slate-400 text-sm mb-2">
            还是无法找回密码？
          </p>
          <a 
            href="mailto:support@medqc.com" 
            class="text-amber-300 hover:text-amber-200 text-sm font-medium"
          >
            联系技术支持
          </a>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { 
  KeyOutlined,
  MailOutlined,
  SendOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  ReloadOutlined,
  LoginOutlined
} from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'

// 路由
const router = useRouter()

// 状态
const currentStep = ref(1)
const sendingEmail = ref(false)
const countdown = ref(0)
let countdownTimer: NodeJS.Timeout | null = null

// 表单引用
const emailFormRef = ref<FormInstance>()

// 表单数据
const emailForm = reactive({
  email: ''
})

// 表单规则
const emailRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ]
}

// 发送重置邮件
const handleSendResetEmail = async () => {
  try {
    sendingEmail.value = true
    
    // 模拟发送邮件
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    message.success('重置邮件发送成功')
    currentStep.value = 2
    startCountdown()
    
  } catch (error) {
    console.error('发送重置邮件失败:', error)
    message.error('发送失败，请重试')
  } finally {
    sendingEmail.value = false
  }
}

// 重新发送邮件
const handleResendEmail = async () => {
  if (countdown.value > 0) {
    message.warning(`请等待 ${countdown.value} 秒后再重新发送`)
    return
  }
  
  await handleSendResetEmail()
}

// 开始倒计时
const startCountdown = () => {
  countdown.value = 60
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearInterval(countdownTimer!)
      countdownTimer = null
    }
  }, 1000)
}

// 清理定时器
onUnmounted(() => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
  }
})
</script>

<style scoped>
/* 复用之前的动画样式 */
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
    box-shadow: 0 0 5px rgba(245, 158, 11, 0.3);
  }
  50% {
    box-shadow: 0 0 20px rgba(245, 158, 11, 0.6), 0 0 30px rgba(245, 158, 11, 0.4);
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
  background: linear-gradient(90deg, transparent, rgba(245, 158, 11, 0.4), transparent);
  animation: borderScan 2s linear infinite;
}

/* 步骤内容动画 */
.step-content {
  animation: slideInUp 0.5s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 输入框样式 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding-left: 0 !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-btn-primary) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

/* 成功图标动画 */
.w-16.h-16 {
  animation: bounceIn 0.6s ease-out;
}

@keyframes bounceIn {
  0% {
    opacity: 0;
    transform: scale(0.3);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
  70% {
    transform: scale(0.9);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
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

/* 响应式设计 */
@media (max-width: 640px) {
  .mx-auto.max-w-md {
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
