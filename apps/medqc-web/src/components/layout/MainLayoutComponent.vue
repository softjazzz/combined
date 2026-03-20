<template>
  <!-- 医疗风格主布局 -->
  <a-layout class="min-h-screen bg-gray-50">
    <!-- 医疗风格侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      class="shadow-2xl border-r border-gray-200"
      :style="{
        background: 'linear-gradient(180deg, #1e40af 0%, #1e3a8a 50%, #1e40af 100%)'
      }"
      :width="280"
      :collapsed-width="80"
    >
      <!-- 医疗Logo区域 -->
      <div class="p-4 border-b border-blue-400/30 bg-white/10 backdrop-blur-sm">
        <div class="flex items-center justify-center">
          <div class="relative">
            <!-- 主Logo -->
            <div class="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
              <MedicineBoxOutlined class="text-xl text-white" />
            </div>
            <!-- 医疗十字装饰 -->
            <div class="absolute -top-1 -right-1 w-4 h-4 bg-green-500 rounded-full flex items-center justify-center">
              <div class="w-2 h-2 relative">
                <div class="absolute inset-x-0 top-1/2 h-0.5 bg-white transform -translate-y-1/2"></div>
                <div class="absolute inset-y-0 left-1/2 w-0.5 bg-white transform -translate-x-1/2"></div>
              </div>
            </div>
          </div>
          <div v-if="!collapsed" class="ml-3">
            <div class="text-white font-bold text-lg">病案质控</div>
            <div class="text-blue-200 text-xs">医疗质控平台</div>
          </div>
        </div>
      </div>

      <!-- 医疗风格导航菜单 -->
      <div class="p-2 mt-2">
        <!-- 医生角色专用菜单 -->
        <template v-if="authStore.hasRole('doctor')">
          <div class="space-y-1">
            <button
              @click="handleMenuClick('/dashboard/doctor-workstation')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/doctor-workstation')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-green-500/20 group-hover:bg-green-500/30 transition-colors duration-200">
                <UserOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">医生工作站</span>
            </button>
          </div>
        </template>

        <!-- 管理员和质控员菜单 -->
        <template v-else>
          <div class="space-y-1">
            <!-- 仪表板 -->
            <button
              @click="handleMenuClick('/dashboard')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-blue-500/20 group-hover:bg-blue-500/30 transition-colors duration-200">
                <DashboardOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">仪表板</span>
            </button>

            <!-- 病案管理 -->
            <button
              @click="handleMenuClick('/dashboard/records')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/records')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-purple-500/20 group-hover:bg-purple-500/30 transition-colors duration-200">
                <FileTextOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">病案管理</span>
            </button>

            <!-- 质控分析 -->
            <div class="space-y-1">
              <button
                @click="toggleQCSubmenu"
                :class="[
                  'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                  (selectedKeys.includes('/dashboard/qc') || selectedKeys.includes('/dashboard/qc/analysis'))
                    ? 'bg-white/20 text-white shadow-lg'
                    : 'text-white/80 hover:bg-white/10 hover:text-white'
                ]"
              >
                <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-green-500/20 group-hover:bg-green-500/30 transition-colors duration-200">
                  <SafetyCertificateOutlined class="text-lg" />
                </div>
                <span v-if="!collapsed" class="ml-3 font-medium flex-1 text-left">质控分析</span>
                <div v-if="!collapsed" class="ml-2 transition-transform duration-200" :class="{ 'rotate-90': qcSubmenuOpen }">
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                  </svg>
                </div>
              </button>

              <!-- 质控子菜单 -->
              <div v-if="qcSubmenuOpen && !collapsed" class="ml-4 space-y-1">
                <button
                  @click="handleMenuClick('/dashboard/qc')"
                  :class="[
                    'w-full flex items-center px-3 py-2 rounded-lg transition-all duration-200 text-sm',
                    selectedKeys.includes('/dashboard/qc')
                      ? 'bg-white/15 text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white'
                  ]"
                >
                  <div class="w-2 h-2 bg-current rounded-full mr-3"></div>
                  质控管理
                </button>
                <button
                  @click="handleMenuClick('/dashboard/qc/analysis')"
                  :class="[
                    'w-full flex items-center px-3 py-2 rounded-lg transition-all duration-200 text-sm',
                    selectedKeys.includes('/dashboard/qc/analysis')
                      ? 'bg-white/15 text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white'
                  ]"
                >
                  <div class="w-2 h-2 bg-current rounded-full mr-3"></div>
                  AI质控分析
                </button>
                <button
                  @click="handleMenuClick('/dashboard/qc/realtime')"
                  :class="[
                    'w-full flex items-center px-3 py-2 rounded-lg transition-all duration-200 text-sm',
                    selectedKeys.includes('/dashboard/qc/realtime')
                      ? 'bg-white/15 text-white'
                      : 'text-white/70 hover:bg-white/10 hover:text-white'
                  ]"
                >
                  <div class="w-2 h-2 bg-current rounded-full mr-3"></div>
                  实时质控监控
                </button>
              </div>
            </div>

            <!-- 质控规则 -->
            <button
              @click="handleMenuClick('/dashboard/rules')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/rules')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-orange-500/20 group-hover:bg-orange-500/30 transition-colors duration-200">
                <SettingOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">质控规则</span>
            </button>

            <!-- 统计报表 -->
            <button
              @click="handleMenuClick('/dashboard/statistics')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/statistics')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-indigo-500/20 group-hover:bg-indigo-500/30 transition-colors duration-200">
                <BarChartOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">统计报表</span>
            </button>

            <!-- 360度分析 (管理员和质控员) -->
            <button
              v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
              @click="handleMenuClick('/dashboard/analytics')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/analytics')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-pink-500/20 group-hover:bg-pink-500/30 transition-colors duration-200">
                <RadarChartOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">360度分析</span>
            </button>

            <!-- 系统设置 (仅管理员) -->
            <button
              v-if="authStore.hasRole('admin')"
              @click="handleMenuClick('/dashboard/settings')"
              :class="[
                'w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group',
                selectedKeys.includes('/dashboard/settings')
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/80 hover:bg-white/10 hover:text-white'
              ]"
            >
              <div class="w-8 h-8 flex items-center justify-center rounded-lg bg-gray-500/20 group-hover:bg-gray-500/30 transition-colors duration-200">
                <ToolOutlined class="text-lg" />
              </div>
              <span v-if="!collapsed" class="ml-3 font-medium">系统设置</span>
            </button>
          </div>
        </template>
      </div>
    </a-layout-sider>

    <!-- 主内容区域 -->
    <a-layout>
      <!-- 医疗风格顶部导航栏 -->
      <a-layout-header class="bg-white shadow-lg border-b border-gray-200 px-6 flex items-center justify-between h-16">
        <div class="flex items-center space-x-4">
          <!-- 折叠按钮 -->
          <button
            @click="collapsed = !collapsed"
            class="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-blue-50 hover:text-blue-600 transition-all duration-200 group"
          >
            <MenuUnfoldOutlined v-if="collapsed" class="text-lg group-hover:scale-110 transition-transform duration-200" />
            <MenuFoldOutlined v-else class="text-lg group-hover:scale-110 transition-transform duration-200" />
          </button>

          <!-- 医疗风格面包屑 -->
          <div class="flex items-center space-x-2 text-sm">
            <div class="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center">
              <HomeOutlined class="text-blue-600 text-xs" />
            </div>
            <template v-for="(item, index) in breadcrumbItems" :key="item.path">
              <div class="flex items-center space-x-2">
                <svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                </svg>
                <router-link
                  v-if="item.path"
                  :to="item.path"
                  class="text-gray-600 hover:text-blue-600 font-medium transition-colors duration-200"
                >
                  {{ item.title }}
                </router-link>
                <span v-else class="text-gray-800 font-semibold">{{ item.title }}</span>
              </div>
            </template>
          </div>
        </div>

        <!-- 右侧医疗风格用户信息 -->
        <div class="flex items-center space-x-4">
          <!-- 通知中心 -->
          <div class="relative">
            <button class="w-10 h-10 bg-gray-100 hover:bg-blue-50 rounded-full flex items-center justify-center transition-all duration-200 group">
              <BellOutlined class="text-gray-600 group-hover:text-blue-600 text-lg" />
            </button>
            <div class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
              <span class="text-xs text-white font-bold">5</span>
            </div>
          </div>

          <!-- 用户信息下拉菜单 -->
          <a-dropdown placement="bottomRight">
            <div class="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 cursor-pointer transition-all duration-200 group">
              <!-- 用户头像 -->
              <div class="relative">
                <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center shadow-md">
                  <UserOutlined class="text-white text-lg" />
                </div>
                <!-- 在线状态指示器 -->
                <div class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
              </div>

              <!-- 用户信息 -->
              <div class="flex flex-col">
                <span class="text-sm font-semibold text-gray-800">{{ authStore.userName }}</span>
                <div class="flex items-center space-x-1">
                  <div class="w-2 h-2 rounded-full" :class="{
                    'bg-orange-500': authStore.hasRole('admin'),
                    'bg-blue-500': authStore.hasRole('qc_manager'),
                    'bg-green-500': authStore.hasRole('doctor')
                  }"></div>
                  <span class="text-xs text-gray-500">{{ getRoleDisplayName(authStore.userRoles?.[0]) }}</span>
                </div>
              </div>

              <!-- 下拉箭头 -->
              <DownOutlined class="text-gray-400 text-xs group-hover:text-gray-600 transition-colors duration-200" />
            </div>

            <template #overlay>
              <div class="bg-white rounded-lg shadow-xl border border-gray-200 py-2 min-w-48">
                <div class="px-4 py-3 border-b border-gray-100">
                  <div class="text-sm font-semibold text-gray-800">{{ authStore.userName }}</div>
                  <div class="text-xs text-gray-500">{{ authStore.user?.email || '' }}</div>
                </div>

                <div class="py-1">
                  <button
                    @click="handleProfile"
                    class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2 transition-colors duration-200"
                  >
                    <UserOutlined class="text-gray-500" />
                    <span>个人资料</span>
                  </button>
                  <button
                    @click="handleSettings"
                    class="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2 transition-colors duration-200"
                  >
                    <SettingOutlined class="text-gray-500" />
                    <span>账户设置</span>
                  </button>
                </div>

                <div class="border-t border-gray-100 py-1">
                  <button
                    @click="handleLogout"
                    class="w-full px-4 py-2 text-left text-sm text-red-600 hover: bg-red-50 flex items-center space-x-2 transition-colors duration-200"
                  >
                    <LogoutOutlined class="text-red-500" />
                    <span>退出登录</span>
                  </button>
                </div>
              </div>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 医疗风格内容区域 -->
      <a-layout-content class="bg-gradient-to-br from-gray-50 to-blue-50/30 p-6 min-h-screen">
        <div class="bg-white rounded-2xl shadow-lg border border-gray-200 min-h-full overflow-hidden">
          <router-view />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { message, Modal } from 'ant-design-vue'
import {
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  DashboardOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  BarChartOutlined,
  RadarChartOutlined,
  ToolOutlined,
  HomeOutlined,
  BellOutlined,
  UserOutlined,
  DownOutlined,
  LogoutOutlined,
  MedicineBoxOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 响应式数据
const collapsed = ref(false)
const selectedKeys = ref<string[]>([])
const qcSubmenuOpen = ref(false)

// 计算属性
const breadcrumbItems = computed(() => {
  const items = []
  const pathSegments = route.path.split('/').filter(Boolean)

  // 根据路由路径生成面包屑
  if (pathSegments.length > 1) {
    switch (pathSegments[1]) {
      case 'records':
        items.push({ title: '病案管理', path: '/dashboard/records' })
        if (pathSegments.length > 2) {
          items.push({ title: '病案详情', path: null })
        }
        break
      case 'qc':
        items.push({ title: '质控分析', path: '/dashboard/qc' })
        if (pathSegments.length > 2) {
          items.push({ title: 'AI质控分析', path: null })
        }
        break
      case 'rules':
        items.push({ title: '质控规则', path: null })
        break
      case 'statistics':
        items.push({ title: '统计报表', path: null })
        break
      case 'analytics':
        items.push({ title: '360度分析', path: null })
        break
      case 'settings':
        items.push({ title: '系统设置', path: null })
        break
      case 'doctor-workstation':
        items.push({ title: '医生工作站', path: null })
        break
      default:
        items.push({ title: '仪表板', path: null })
    }
  } else {
    items.push({ title: '仪表板', path: null })
  }

  return items
})

// 方法
const handleMenuClick = (path: string) => {
  router.push(path)
}

const toggleQCSubmenu = () => {
  qcSubmenuOpen.value = !qcSubmenuOpen.value
}

const getRoleDisplayName = (role: string) => {
  const roleMap: Record<string, string> = {
    'admin': '系统管理员',
    'qc_manager': '质控管理员',
    'doctor': '医务人员'
  }
  return roleMap[role] || role
}

// 个人资料处理
const handleProfile = () => {
  message.loading('正在跳转到个人资料...', 0.5)
  router.push('/dashboard/profile')
}

// 账户设置处理
const handleSettings = () => {
  message.loading('正在跳转到账户设置...', 0.5)
  router.push('/dashboard/account-settings')
}

// 强制退出登录（备用方案）
const forceLogout = () => {
  console.log('执行强制退出登录...')
  // 清除所有本地存储
  localStorage.clear()
  sessionStorage.clear()

  // 重置认证状态
  ;(authStore as unknown as { resetState?: () => void }).resetState?.()

  // 强制跳转到登录页
  window.location.href = '/login'
}

const handleLogout = async () => {
  Modal.confirm({
    title: '退出登录', content: '确定要退出当前账户吗？', okText: '确定', cancelText: '取消', onOk: async () => {
      console.log('开始退出登录流程...')
      const loadingMessage = message.loading('正在退出...', 0)

      try {
        console.log('调用authStore.signOut()...')
        // 添加超时处理，防止无限等待
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => {
            console.log('退出登录超时')
            reject(new Error('退出登录超时'))
          }, 10000) // 10秒超时
        })

        const signOutPromise = authStore.signOut()
        const result = await Promise.race([signOutPromise, timeoutPromise]) as {
          success?: boolean
          error?: { message?: string }
        }

        console.log('signOut结果:', result)
        loadingMessage()

        if (result && result.success) {
          console.log('退出登录成功，跳转到登录页...')
          message.success('已成功退出登录')
          router.push('/login')
        } else {
          throw new Error(result?.error?.message || '退出登录失败')
        }
      } catch (error) {
        loadingMessage()
        console.error('登出失败:', error)

        const errorMessage = error instanceof Error ? error.message : '退出登录失败'
        message.error(errorMessage)

        // 即使登出失败，也应该清除本地状态并跳转到登录页
        console.log('正常退出失败，使用强制退出...')
        setTimeout(() => {
          forceLogout()
        }, 1500)
      }
    }
  })
}

// 监听路由变化更新选中的菜单
watch(
  () => route.path,
  (newPath: string) => {
    selectedKeys.value = [newPath]
    // 如果是质控相关路径，展开质控子菜单
    if (newPath.includes('/dashboard/qc')) {
      qcSubmenuOpen.value = true
    }
  },
  { immediate: true }
)
</script>

<style scoped>
/* 使用 Tailwind CSS 进行样式设计，移除所有自定义CSS */
</style>
