<template>
  <div class="demo-accounts mt-6">
    <!-- 演示账号触发按钮 -->
    <div class="text-center">
      <div
        @click="toggleExpanded"
        class="demo-trigger-btn inline-flex items-center gap-2 px-4 py-3 text-gray-600 hover:text-blue-600 cursor-pointer transition-all duration-200 rounded-lg hover:bg-blue-50 border border-transparent hover:border-blue-200"
      >
        <UserOutlined class="text-base" />
        <span class="font-medium">演示账号</span>
        <DownOutlined
          :class="[
            'text-sm transition-transform duration-300',
            { 'rotate-180': isExpanded }
          ]"
        />
      </div>
    </div>

    <!-- 账号列表 - 使用 Transition 组件添加动画 -->
    <Transition
      name="demo-accounts"
      enter-active-class="transition-all duration-300 ease-out"
      leave-active-class="transition-all duration-200 ease-in"
      enter-from-class="opacity-0 transform -translate-y-2 scale-95"
      enter-to-class="opacity-100 transform translate-y-0 scale-100"
      leave-from-class="opacity-100 transform translate-y-0 scale-100"
      leave-to-class="opacity-0 transform -translate-y-2 scale-95"
    >
      <div v-if="isExpanded" class="mt-4">
        <div class="bg-white border border-gray-200 rounded-2xl p-4 shadow-lg">
          <div class="text-center mb-4">
            <span class="text-sm text-gray-600 font-medium">演示账号</span>
          </div>

          <div class="space-y-2">
            <div
              v-for="account in demoAccounts"
              :key="account.email"
              @click="selectAccount(account)"
              :class="[
                'demo-account-item flex items-center gap-4 p-4 bg-gray-50 rounded-xl transition-all duration-200 group border border-transparent',
                {
                  'hover:bg-blue-50 cursor-pointer hover:border-blue-200': !isLoggingIn,
                  'opacity-50 cursor-not-allowed': isLoggingIn,
                  'bg-blue-50 border-blue-200': isLoggingIn && selectedAccount?.email === account.email
                }
              ]"
            >
              <!-- 角色图标 -->
              <div
                :class="[
                  'w-12 h-12 rounded-full flex items-center justify-center text-white text-lg font-bold flex-shrink-0 shadow-sm',
                  account.bgColor
                ]"
              >
                {{ account.icon }}
              </div>

              <!-- 账号信息 -->
              <div class="flex-1 min-w-0">
                <div class="font-semibold text-gray-900 text-base mb-1">{{ account.name }}</div>
                <div class="text-sm text-gray-600">
                  {{ account.email }} / {{ account.password }}
                </div>
              </div>

              <!-- 选择图标/加载状态 -->
              <div class="flex-shrink-0 transition-opacity duration-200">
                <div v-if="isLoggingIn && selectedAccount?.email === account.email" class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                  <LoadingOutlined class="text-white text-sm animate-spin" />
                </div>
                <div v-else class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center opacity-0 group-hover:opacity-100">
                  <LoginOutlined class="text-white text-sm" />
                </div>
              </div>
            </div>
          </div>

          <!-- 提示信息 -->
          <div class="mt-4 text-center">
            <span class="text-xs text-gray-500">点击账号可直接完成登录并跳转</span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UserOutlined, DownOutlined, LoginOutlined, LoadingOutlined } from '@ant-design/icons-vue'

interface DemoAccount {
  email: string
  password: string
  role: string
  name: string
  permission: string
  icon: string
  bgColor: string
}

interface Props {
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

const emit = defineEmits<{
  'select-account': [account: { email: string, password: string, role: string }]
}>()

const isExpanded = ref(false)
const isLoggingIn = ref(false)
const selectedAccount = ref<DemoAccount | null>(null)

// 演示账号数据
const demoAccounts: DemoAccount[] = [
  {
    email: 'admin@yibao.com',
    password: 'admin123',
    role: 'admin',
    name: '系统管理员',
    permission: '完整权限',
    icon: '管',
    bgColor: 'bg-orange-500'
  },
  {
    email: 'doctor@yibao.com',
    password: 'doctor123',
    role: 'doctor',
    name: '医务人员',
    permission: '基础权限',
    icon: '医',
    bgColor: 'bg-green-500'
  },
  {
    email: 'auditor@yibao.com',
    password: 'auditor123',
    role: 'qc_manager',
    name: '质控审核员',
    permission: '审核权限',
    icon: '质',
    bgColor: 'bg-blue-500'
  }
]

const toggleExpanded = () => {
  isExpanded.value = !isExpanded.value
}

const selectAccount = (account: DemoAccount) => {
  // 如果正在登录中，忽略点击
  if (isLoggingIn.value) return

  // 设置加载状态
  isLoggingIn.value = true
  selectedAccount.value = account

  emit('select-account', {
    email: account.email,
    password: account.password,
    role: account.role
  })

  // 选择账号后自动收起
  isExpanded.value = false

  // 重置加载状态（在父组件登录完成后会重置）
  setTimeout(() => {
    isLoggingIn.value = false
    selectedAccount.value = null
  }, 3000) // 3秒后自动重置，防止卡住
}
</script>

<style scoped>
.demo-trigger-btn {
  user-select: none;
  transition: all 0.2s ease;
}

.demo-trigger-btn:active {
  transform: scale(0.98);
}

.demo-account-item {
  user-select: none;
  transition: all 0.2s ease;
}

.demo-account-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.demo-account-item:active {
  transform: translateY(0);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 自定义过渡动画 */
.demo-accounts-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.demo-accounts-leave-active {
  transition: all 0.2s ease-in;
}

.demo-accounts-enter-from {
  opacity: 0;
  transform: translateY(-15px) scale(0.9);
}

.demo-accounts-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}
</style>
