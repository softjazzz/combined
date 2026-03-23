<template>
  <div class="min-h-screen bg-gray-50">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm border-b border-gray-200 fixed w-full top-0 z-50">
      <div class="px-6 py-4">
        <div class="flex items-center justify-between">
          <!-- 左侧：Logo和系统名称 -->
          <div class="flex items-center">
            <button
              class="lg:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 mr-3"
              @click="toggleSidebar"
            >
              <MenuOutlined class="text-lg" />
            </button>
            
            <div class="flex items-center">
              <div class="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center mr-3">
                <MedicineBoxOutlined class="text-white text-sm" />
              </div>
              <div>
                <h1 class="text-lg font-semibold text-gray-900">
                  医疗质控系统
                </h1>
                <p class="text-xs text-gray-500 hidden sm:block">
                  Medical Quality Control System
                </p>
              </div>
            </div>
          </div>
          
          <!-- 右侧：用户信息和操作 -->
          <div class="flex items-center space-x-4">
            <!-- 通知 -->
            <a-badge
              :count="notificationCount"
              :offset="[10, 0]"
            >
              <button class="p-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                <BellOutlined class="text-lg" />
              </button>
            </a-badge>
            
            <!-- 用户菜单 -->
            <a-dropdown placement="bottomRight">
              <button class="flex items-center space-x-2 p-2 text-gray-700 hover:bg-gray-100 rounded-lg">
                <a-avatar
                  :size="32"
                  :src="currentUser?.avatar"
                >
                  <template #icon>
                    <UserOutlined />
                  </template>
                </a-avatar>
                <div class="hidden sm:block text-left">
                  <div class="text-sm font-medium">
                    {{ currentUser?.display_name || '用户' }}
                  </div>
                  <div class="text-xs text-gray-500">
                    {{ currentUser?.role || '医务人员' }}
                  </div>
                </div>
                <DownOutlined class="text-xs text-gray-400" />
              </button>
              
              <template #overlay>
                <a-menu>
                  <a-menu-item
                    key="profile"
                    @click="goToProfile"
                  >
                    <UserOutlined class="mr-2" />
                    个人资料
                  </a-menu-item>
                  <a-menu-item
                    key="settings"
                    @click="goToSettings"
                  >
                    <SettingOutlined class="mr-2" />
                    系统设置
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item
                    key="logout"
                    @click="handleLogout"
                  >
                    <LogoutOutlined class="mr-2" />
                    退出登录
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
        </div>
      </div>
    </header>
    
    <!-- 主体内容区域 -->
    <div class="flex pt-16">
      <!-- 侧边栏 -->
      <aside 
        :class="[
          'fixed lg:static inset-y-0 left-0 z-40 w-64 bg-white shadow-sm border-r border-gray-200 transform transition-transform duration-300 ease-in-out pt-16 lg:pt-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        ]"
      >
        <nav class="h-full overflow-y-auto py-6">
          <div class="px-4">
            <a-menu
              v-model:selected-keys="selectedKeys"
              v-model:open-keys="openKeys"
              mode="inline"
              :inline-collapsed="false"
              class="border-none"
            >
              <!-- 仪表板 -->
              <a-menu-item
                key="dashboard"
                @click="navigateTo('/dashboard')"
              >
                <template #icon>
                  <DashboardOutlined class="text-gray-600" />
                </template>
                <span class="text-gray-700">仪表板</span>
              </a-menu-item>
              
              <!-- 质控管理 -->
              <a-sub-menu key="qc-management">
                <template #icon>
                  <SafetyCertificateOutlined class="text-gray-600" />
                </template>
                <template #title>
                  <span class="text-gray-700">质控管理</span>
                </template>
                
                <a-menu-item
                  key="audit-tasks"
                  @click="navigateTo('/audit-tasks')"
                >
                  <span class="text-gray-600">审核任务</span>
                </a-menu-item>
                <a-menu-item
                  key="ai-assistance"
                  @click="navigateTo('/ai-assistance')"
                >
                  <span class="text-gray-600">AI辅助审核</span>
                </a-menu-item>
                <a-menu-item
                  key="batch-audit"
                  @click="navigateTo('/batch-audit')"
                >
                  <span class="text-gray-600">批量审核</span>
                </a-menu-item>
              </a-sub-menu>
              
              <!-- 规则配置 -->
              <a-sub-menu key="rules">
                <template #icon>
                  <SettingOutlined class="text-gray-600" />
                </template>
                <template #title>
                  <span class="text-gray-700">规则配置</span>
                </template>
                
                <a-menu-item
                  key="work-rules"
                  @click="navigateTo('/rules/work-rules')"
                >
                  <span class="text-gray-600">工作制度</span>
                </a-menu-item>
                <a-menu-item
                  key="enhanced-rules"
                  @click="navigateTo('/rules/enhanced-rules')"
                >
                  <span class="text-gray-600">增强规则</span>
                </a-menu-item>
                <a-menu-item
                  key="department-config"
                  @click="navigateTo('/department-config')"
                >
                  <span class="text-gray-600">专科配置</span>
                </a-menu-item>
              </a-sub-menu>
              
              <!-- 数据分析 -->
              <a-sub-menu key="analytics">
                <template #icon>
                  <BarChartOutlined class="text-gray-600" />
                </template>
                <template #title>
                  <span class="text-gray-700">数据分析</span>
                </template>
                
                <a-menu-item
                  key="qc-reports"
                  @click="navigateTo('/reports/qc-reports')"
                >
                  <span class="text-gray-600">质控报告</span>
                </a-menu-item>
                <a-menu-item
                  key="statistics"
                  @click="navigateTo('/statistics')"
                >
                  <span class="text-gray-600">统计分析</span>
                </a-menu-item>
              </a-sub-menu>
              
              <!-- 系统管理 -->
              <a-sub-menu
                v-if="isAdmin"
                key="system"
              >
                <template #icon>
                  <ControlOutlined class="text-gray-600" />
                </template>
                <template #title>
                  <span class="text-gray-700">系统管理</span>
                </template>
                
                <a-menu-item
                  key="user-management"
                  @click="navigateTo('/admin/users')"
                >
                  <span class="text-gray-600">用户管理</span>
                </a-menu-item>
                <a-menu-item
                  key="system-settings"
                  @click="navigateTo('/admin/settings')"
                >
                  <span class="text-gray-600">系统设置</span>
                </a-menu-item>
                <a-menu-item
                  key="logs"
                  @click="navigateTo('/admin/logs')"
                >
                  <span class="text-gray-600">系统日志</span>
                </a-menu-item>
              </a-sub-menu>
            </a-menu>
          </div>
        </nav>
      </aside>
      
      <!-- 遮罩层 (移动端) -->
      <div
        v-if="sidebarOpen"
        class="fixed inset-0 z-30 bg-black bg-opacity-50 lg:hidden"
        @click="closeSidebar"
      />
      
      <!-- 主内容区域 -->
      <main class="flex-1 lg: ml-0">
        <div class="p-6">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { message } from 'ant-design-vue'
import {
  MenuOutlined,
  MedicineBoxOutlined,
  BellOutlined,
  UserOutlined,
  DownOutlined,
  SettingOutlined,
  LogoutOutlined,
  DashboardOutlined,
  SafetyCertificateOutlined,
  BarChartOutlined,
  ControlOutlined
} from '@ant-design/icons-vue'

// 路由和状态管理
const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 响应式数据
const sidebarOpen = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])
const notificationCount = ref(3)

// 计算属性
const currentUser = computed(() => authStore.user)
const isAdmin = computed(() => authStore.user?.role === 'admin')

// 方法
const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const navigateTo = (path: string) => {
  router.push(path)
  closeSidebar()
}

const goToProfile = () => {
  router.push('/profile')
}

const goToSettings = () => {
  router.push('/settings')
}

const handleLogout = async () => {
  try {
    await authStore.signOut()
    message.success('已安全退出')
    router.push('/auth/login')
  } catch (error) {
    message.error('退出失败')
  }
}

// 根据当前路由设置菜单选中状态
const updateMenuState = () => {
  const path = route.path
  
  if (path.includes('/dashboard')) {
    selectedKeys.value = ['dashboard']
    openKeys.value = []
  } else if (path.includes('/audit-tasks')) {
    selectedKeys.value = ['audit-tasks']
    openKeys.value = ['qc-management']
  } else if (path.includes('/ai-assistance')) {
    selectedKeys.value = ['ai-assistance']
    openKeys.value = ['qc-management']
  } else if (path.includes('/batch-audit')) {
    selectedKeys.value = ['batch-audit']
    openKeys.value = ['qc-management']
  } else if (path.includes('/rules/work-rules')) {
    selectedKeys.value = ['work-rules']
    openKeys.value = ['rules']
  } else if (path.includes('/rules/enhanced-rules')) {
    selectedKeys.value = ['enhanced-rules']
    openKeys.value = ['rules']
  } else if (path.includes('/department-config')) {
    selectedKeys.value = ['department-config']
    openKeys.value = ['rules']
  } else if (path.includes('/reports')) {
    selectedKeys.value = ['qc-reports']
    openKeys.value = ['analytics']
  } else if (path.includes('/statistics')) {
    selectedKeys.value = ['statistics']
    openKeys.value = ['analytics']
  } else if (path.includes('/admin/users')) {
    selectedKeys.value = ['user-management']
    openKeys.value = ['system']
  } else if (path.includes('/admin/settings')) {
    selectedKeys.value = ['system-settings']
    openKeys.value = ['system']
  } else if (path.includes('/admin/logs')) {
    selectedKeys.value = ['logs']
    openKeys.value = ['system']
  }
}

// 生命周期
onMounted(() => {
  updateMenuState()
})

// 监听路由变化
watch(route, () => {
  updateMenuState()
})
</script>

<style scoped>
/* 自定义菜单样式 */
:deep(.ant-menu-inline) {
  border-right: none;
}

:deep(.ant-menu-item) {
  margin: 4px 0;
  border-radius: 8px;
  height: 40px;
  line-height: 40px;
}

:deep(.ant-menu-item:hover) {
  background-color: #f3f4f6;
}

:deep(.ant-menu-item-selected) {
  background-color: #eff6ff !important;
  color: #1890ff !important;
}

:deep(.ant-menu-item-selected::after) {
  display: none;
}

:deep(.ant-menu-submenu-title) {
  margin: 4px 0;
  border-radius: 8px;
  height: 40px;
  line-height: 40px;
}

:deep(.ant-menu-submenu-title:hover) {
  background-color: #f3f4f6;
}

:deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  background-color: #f3f4f6;
}

/* 响应式设计 */
@media (max-width: 1024px) {
  .lg\:ml-0 {
    margin-left: 0 !important;
  }
}
</style>
