<template>
  <a-layout class="min-h-screen bg-gray-50">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      class="sidebar-container shadow-2xl border-r border-blue-200/50 relative overflow-hidden"
      :style="{
        background: 'linear-gradient(180deg, #3b82f6 0%, #1e40af 50%, #1d4ed8 100%)'
      }"
      width="280"
    >
      <!-- 背景装饰元素 -->
      <div class="absolute inset-0 pointer-events-none">
        <!-- 渐变光晕 -->
        <div class="absolute -top-20 -right-20 w-40 h-40 bg-white/5 rounded-full blur-3xl"></div>
        <div class="absolute top-1/3 -left-10 w-32 h-32 bg-cyan-400/10 rounded-full blur-2xl"></div>
        <div class="absolute bottom-20 -right-16 w-36 h-36 bg-indigo-300/8 rounded-full blur-2xl"></div>

        <!-- 医疗十字装饰 -->
        <div class="absolute top-16 right-8 w-3 h-3 opacity-10">
          <div class="absolute inset-0 bg-white transform rotate-45"></div>
          <div class="absolute top-1 left-1 w-1 h-1 bg-blue-600"></div>
        </div>
        <div class="absolute bottom-32 left-6 w-2 h-2 opacity-10">
          <div class="absolute inset-0 bg-white transform rotate-45"></div>
        </div>

        <!-- 微妙的网格纹理 -->
        <div class="absolute inset-0 opacity-[0.02]" style="background-image: linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px); background-size: 20px 20px;"></div>
      </div>
      <!-- Logo区域 -->
      <div class="logo-container relative p-6 text-center border-b border-white/20 backdrop-blur-sm">
        <!-- Logo背景光效 -->
        <div class="absolute inset-0 bg-gradient-to-r from-white/5 to-transparent"></div>

        <div class="relative flex items-center justify-center">
          <div class="w-12 h-12 bg-gradient-to-br from-white/25 to-white/10 rounded-2xl flex items-center justify-center mr-4 shadow-lg backdrop-blur-sm border border-white/20" v-if="!collapsed">
            <MedicineBoxOutlined class="text-2xl text-white drop-shadow-sm" />
          </div>
          <div class="w-10 h-10 bg-gradient-to-br from-white/25 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20" v-else>
            <MedicineBoxOutlined class="text-xl text-white drop-shadow-sm" />
          </div>
          <div v-if="!collapsed" class="text-left">
            <div class="text-white font-bold text-xl leading-tight drop-shadow-sm">
              医疗质控系统
            </div>
            <div class="text-blue-100 text-sm mt-1 font-medium">
              AI-Powered QC Platform
            </div>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <div class="relative z-10">
        <a-menu
          v-model:selectedKeys="selectedKeys"
          mode="inline"
          theme="dark"
          class="bg-transparent border-0 px-4 py-6 menu-container"
          style="background: transparent !important;"
          @select="handleMenuSelect"
        >
        <!-- 病案质控 -->
        <a-sub-menu key="/dashboard/records" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <FileTextOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <template #title>
            <span class="text-white font-semibold ml-3 drop-shadow-sm">病案质控</span>
          </template>
          <a-menu-item key="/dashboard/records/running" class="menu-item-secondary ml-6 mb-2 rounded-xl">
            <template #icon>
              <div class="w-7 h-7 bg-gradient-to-br from-blue-400/20 to-blue-500/10 rounded-lg flex items-center justify-center shadow-md border border-blue-300/20">
                <PlayCircleOutlined class="text-blue-100 text-sm" />
              </div>
            </template>
            <span class="text-blue-50 ml-3 font-medium">运行病历</span>
          </a-menu-item>
          <a-menu-item key="/dashboard/records/final" class="menu-item-secondary ml-6 mb-2 rounded-xl">
            <template #icon>
              <div class="w-7 h-7 bg-gradient-to-br from-green-400/20 to-green-500/10 rounded-lg flex items-center justify-center shadow-md border border-green-300/20">
                <CheckCircleOutlined class="text-green-100 text-sm" />
              </div>
            </template>
            <span class="text-blue-50 ml-3 font-medium">终末病历</span>
          </a-menu-item>
        </a-sub-menu>

        <!-- 任务管理 -->
        <a-sub-menu key="/dashboard/tasks" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <ProjectOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <template #title>
            <span class="text-white font-semibold ml-3 drop-shadow-sm">任务管理</span>
          </template>
          <a-menu-item key="/dashboard/tasks/my" class="menu-item-secondary ml-6 mb-2 rounded-xl">
            <template #icon>
              <div class="w-7 h-7 bg-gradient-to-br from-purple-400/20 to-purple-500/10 rounded-lg flex items-center justify-center shadow-md border border-purple-300/20">
                <UserOutlined class="text-purple-100 text-sm" />
              </div>
            </template>
            <span class="text-blue-50 ml-3 font-medium">我的任务</span>
          </a-menu-item>
          <a-menu-item key="/dashboard/tasks/all" class="menu-item-secondary ml-6 mb-2 rounded-xl" v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')">
            <template #icon>
              <div class="w-7 h-7 bg-gradient-to-br from-orange-400/20 to-orange-500/10 rounded-lg flex items-center justify-center shadow-md border border-orange-300/20">
                <TeamOutlined class="text-orange-100 text-sm" />
              </div>
            </template>
            <span class="text-blue-50 ml-3 font-medium">全部任务</span>
          </a-menu-item>
        </a-sub-menu>

        <!-- 统计分析 -->
        <a-menu-item key="/dashboard/statistics" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <BarChartOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">统计分析</span>
        </a-menu-item>

        <!-- 质控规则管理 - 仅admin可见 -->
        <a-menu-item key="/dashboard/rules" class="menu-item menu-item-primary mb-3 mx-2" v-if="authStore.hasRole('admin')">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <SettingOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">质控规则管理</span>
        </a-menu-item>

        <!-- 测试病历管理 -->
        <a-menu-item key="/dashboard/medical-records" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <FileTextOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">测试病历管理</span>
        </a-menu-item>

        <!-- 数据权限配置 - 仅admin可见 -->
        <a-menu-item key="/dashboard/permissions" class="menu-item menu-item-primary mb-3 mx-2" v-if="authStore.hasRole('admin')">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <SafetyCertificateOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">数据权限配置</span>
        </a-menu-item>

        <!-- 系统设置 - 仅admin可见 -->
        <a-menu-item key="/dashboard/settings" class="menu-item menu-item-primary mb-3 mx-2" v-if="authStore.hasRole('admin')">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <SettingOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">系统设置</span>
        </a-menu-item>

        <!-- 保留原有的LLM质控演示功能 - 仅admin可见 -->
        <a-menu-item key="/dashboard/llm-qc-demo" class="menu-item menu-item-primary mb-3 mx-2" v-if="authStore.hasRole('admin')">
          <template #icon>
            <div class="w-10 h-10 bg-gradient-to-br from-white/20 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
              <ExperimentOutlined class="text-white text-lg drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-3 drop-shadow-sm">LLM质控演示</span>
        </a-menu-item>
        </a-menu>
      </div>
    </a-layout-sider>

    <!-- 主内容区域 -->
    <a-layout>
      <!-- 顶部导航栏 -->
      <a-layout-header class="header bg-white shadow-sm border-b border-gray-100 px-6 flex items-center justify-between h-16">
        <div class="flex items-center">
          <a-button
            type="text"
            @click="collapsed = !collapsed"
            class="trigger hover:bg-blue-50 text-blue-600 border-0"
          >
            <MenuUnfoldOutlined v-if="collapsed" />
            <MenuFoldOutlined v-else />
          </a-button>

          <!-- 面包屑 -->
          <a-breadcrumb class="ml-6">
            <a-breadcrumb-item>
              <HomeOutlined class="text-blue-500" />
            </a-breadcrumb-item>
            <a-breadcrumb-item v-for="item in breadcrumbItems" :key="item.path">
              <router-link v-if="item.path" :to="item.path" class="text-gray-600 hover:text-blue-600">
                {{ item.title }}
              </router-link>
              <span v-else class="text-gray-800 font-medium">{{ item.title }}</span>
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <!-- 右侧用户信息 -->
        <div class="flex items-center space-x-4">
          <!-- 通知 -->
          <a-badge :count="5" class="mr-2">
            <a-button type="text" shape="circle" size="large" class="hover:bg-blue-50 text-gray-600 hover:text-blue-600">
              <BellOutlined />
            </a-button>
          </a-badge>

          <!-- 用户头像和菜单 -->
          <a-dropdown>
            <div class="flex items-center cursor-pointer hover:bg-gray-50 p-3 rounded-lg transition-colors duration-200">
              <a-avatar :size="36" class="mr-3 bg-blue-500">
                <template #icon>
                  <UserOutlined />
                </template>
              </a-avatar>
              <div class="flex flex-col">
                <span class="text-sm font-semibold text-gray-800">{{ authStore.userName }}</span>
                <span class="text-xs text-gray-500">{{ authStore.userRoles?.[0] }}</span>
              </div>
              <DownOutlined class="ml-3 text-xs text-gray-400" />
            </div>
            <template #overlay>
              <a-menu>
                <a-menu-item key="profile">
                  <UserOutlined />
                  <span>个人中心</span>
                </a-menu-item>
                <a-menu-item key="settings">
                  <SettingOutlined />
                  <span>账户设置</span>
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="logout" @click="handleLogout">
                  <LogoutOutlined />
                  <span>退出登录</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 内容区域 -->
      <a-layout-content class="bg-gray-50 p-8">
        <div class="bg-white rounded-xl shadow-sm min-h-full border border-gray-100">
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
  MedicineBoxOutlined,
  BranchesOutlined,
  ExperimentOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ProjectOutlined,
  TeamOutlined
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 开发环境检测
const isDevelopment = import.meta.env.DEV

// 响应式数据
const collapsed = ref(false)
const selectedKeys = ref<string[]>([])

// 计算属性
const breadcrumbItems = computed(() => {
  const items = []
  const pathSegments = route.path.split('/').filter(Boolean)
  
  // 根据路由路径生成面包屑
  if (pathSegments.length > 1) {
    switch (pathSegments[1]) {
      case 'records':
        items.push({ title: '病案质控', path: null })
        if (pathSegments[2] === 'running') {
          items.push({ title: '运行病历', path: null })
        } else if (pathSegments[2] === 'final') {
          items.push({ title: '终末病历', path: null })
        } else if (pathSegments.length > 2) {
          items.push({ title: '病案详情', path: null })
        }
        break
      case 'tasks':
        items.push({ title: '任务管理', path: null })
        if (pathSegments[2] === 'my') {
          items.push({ title: '我的任务', path: null })
        } else if (pathSegments[2] === 'all') {
          items.push({ title: '全部任务', path: null })
        }
        break
      case 'statistics':
        items.push({ title: '统计分析', path: null })
        break
      case 'rules':
        items.push({ title: '质控规则管理', path: null })
        break
      case 'medical-records':
        items.push({ title: '测试病历管理', path: '/dashboard/medical-records' })
        if (pathSegments.length > 2) {
          if (pathSegments[2] === 'create') {
            items.push({ title: '新建病历', path: null })
          } else if (pathSegments[2] === 'edit') {
            items.push({ title: '编辑病历', path: null })
          } else if (pathSegments[2] === 'smart-import') {
            items.push({ title: '智能导入病历', path: null })
          }
        }
        break
      case 'permissions':
        items.push({ title: '数据权限配置', path: null })
        break
      case 'llm-qc-demo':
        items.push({ title: 'LLM质控演示', path: null })
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
const handleMenuSelect = ({ key }: { key: string }) => {
  router.push(key)
}

const handleLogout = async () => {
  await authStore.signOut()
  router.push('/login')
}

// 监听路由变化更新选中的菜单
watch(
  () => route.path,
  (newPath) => {
    selectedKeys.value = [newPath]
  },
  { immediate: true }
)
</script>

<style scoped>
/* 侧边栏容器样式 */
.sidebar-container {
  position: relative;
  overflow: hidden;
}

.sidebar-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%, rgba(255,255,255,0.05) 100%);
  pointer-events: none;
  z-index: 1;
}

/* Logo区域样式 */
.logo-container {
  position: relative;
  z-index: 10;
}

/* 菜单容器样式 */
.menu-container {
  position: relative;
  z-index: 10;
}

/* 一级菜单项样式 */
.menu-item-primary {
  margin: 8px 0;
  border-radius: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.menu-item-primary::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
  border-radius: 16px;
}

.menu-item-primary:hover::before {
  opacity: 1;
}

.menu-item-primary:hover {
  background: rgba(255, 255, 255, 0.15) !important;
  transform: translateX(4px) scale(1.02);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(255, 255, 255, 0.1);
}

/* 二级菜单项样式 */
.menu-item-secondary {
  margin: 4px 0;
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  background: rgba(255, 255, 255, 0.05) !important;
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.menu-item-secondary:hover {
  background: rgba(255, 255, 255, 0.12) !important;
  transform: translateX(6px) scale(1.03);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(255, 255, 255, 0.15);
}

/* 选中状态样式 */
.menu-item.ant-menu-item-selected,
.menu-item.ant-menu-submenu-selected {
  background: rgba(255, 255, 255, 0.25) !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2), 0 0 0 2px rgba(255, 255, 255, 0.2);
  transform: translateX(4px);
}

.menu-item-secondary.ant-menu-item-selected {
  background: rgba(255, 255, 255, 0.2) !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15), 0 0 0 2px rgba(255, 255, 255, 0.25);
  transform: translateX(6px);
}

/* 头部样式 */
.header {
  height: 64px;
  line-height: 64px;
  padding: 0 32px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-bottom: 1px solid #f0f0f0;
}

.trigger {
  font-size: 18px;
  line-height: 64px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 8px;
}

.trigger:hover {
  color: #3b82f6;
  background-color: #eff6ff;
}

/* Ant Design 菜单样式覆盖 */
:deep(.ant-menu-dark) {
  background: transparent !important;
}

:deep(.ant-menu-dark .ant-menu-item) {
  color: rgba(255, 255, 255, 0.95);
  font-weight: 500;
  border-radius: 16px;
  margin: 8px 0;
  height: auto;
  line-height: 1.4;
  padding: 12px 16px;
}

:deep(.ant-menu-dark .ant-menu-item:hover) {
  color: #fff;
  background: rgba(255, 255, 255, 0.15) !important;
}

:deep(.ant-menu-dark .ant-menu-item-selected) {
  background: rgba(255, 255, 255, 0.25) !important;
  color: #fff;
}

:deep(.ant-menu-dark .ant-menu-submenu-title) {
  color: rgba(255, 255, 255, 0.95);
  font-weight: 600;
  border-radius: 16px;
  margin: 8px 0;
  height: auto;
  line-height: 1.4;
  padding: 12px 16px;
}

:deep(.ant-menu-dark .ant-menu-submenu-title:hover) {
  background: rgba(255, 255, 255, 0.15) !important;
  color: #fff;
}

:deep(.ant-menu-dark .ant-menu-submenu-open > .ant-menu-submenu-title) {
  background: rgba(255, 255, 255, 0.15) !important;
  color: #fff;
}

/* 二级菜单容器样式 */
:deep(.ant-menu-dark .ant-menu-sub) {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 100%) !important;
  backdrop-filter: blur(20px);
  border-radius: 12px !important;
  margin: 8px 0;
  padding: 8px 0;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 4px 20px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  position: relative;
  isolation: isolate;
  /* 确保毛玻璃效果严格限制在容器内 */
  -webkit-backdrop-filter: blur(20px);
  contain: layout style paint;
  /* 强制应用圆角到所有角 */
  -webkit-border-radius: 12px !important;
  -moz-border-radius: 12px !important;
  /* 确保圆角不被子元素影响 */
  border-top-left-radius: 12px !important;
  border-top-right-radius: 12px !important;
  border-bottom-left-radius: 12px !important;
  border-bottom-right-radius: 12px !important;
}

/* 为二级菜单容器添加伪元素来增强边界控制 */
:deep(.ant-menu-dark .ant-menu-sub::before) {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 12px !important;
  background: inherit;
  backdrop-filter: inherit;
  -webkit-backdrop-filter: inherit;
  z-index: -1;
  /* 强制应用圆角 */
  -webkit-border-radius: 12px !important;
  -moz-border-radius: 12px !important;
  border-top-left-radius: 12px !important;
  border-top-right-radius: 12px !important;
  border-bottom-left-radius: 12px !important;
  border-bottom-right-radius: 12px !important;
}

:deep(.ant-menu-dark .ant-menu-sub .ant-menu-item) {
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
  border-radius: 10px;
  margin: 4px 8px;
  height: auto;
  line-height: 1.4;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
  position: relative;
}

:deep(.ant-menu-dark .ant-menu-sub .ant-menu-item:hover) {
  background: rgba(255, 255, 255, 0.12) !important;
  color: #fff;
  transform: translateX(2px);
  /* 确保悬停时不会超出容器边界 */
  will-change: transform;
  backface-visibility: hidden;
}

:deep(.ant-menu-dark .ant-menu-sub .ant-menu-item-selected) {
  background: rgba(255, 255, 255, 0.2) !important;
  color: #fff;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

/* 菜单项图标样式 */
:deep(.ant-menu-item .anticon),
:deep(.ant-menu-submenu-title .anticon) {
  font-size: 16px;
  margin-right: 12px;
}

/* 移除默认的选中指示器 */
:deep(.ant-menu-dark .ant-menu-item-selected::after),
:deep(.ant-menu-dark .ant-menu-submenu-selected::after) {
  display: none;
}

/* 强制覆盖Ant Design的默认样式，确保圆角显示 */
:deep(.ant-menu-sub.ant-menu-inline) {
  border-radius: 12px !important;
  -webkit-border-radius: 12px !important;
  -moz-border-radius: 12px !important;
  overflow: hidden !important;
}

/* 针对特定的Ant Design类名进行样式覆盖 */
:deep(.ant-menu-inline .ant-menu-sub) {
  border-radius: 12px !important;
  -webkit-border-radius: 12px !important;
  -moz-border-radius: 12px !important;
  overflow: hidden !important;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .menu-item-primary:hover,
  .menu-item-secondary:hover {
    transform: none;
  }

  /* 移动端禁用毛玻璃效果以提升性能 */
  :deep(.ant-menu-dark .ant-menu-sub) {
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    background: rgba(255, 255, 255, 0.12) !important;
  }
}

/* 浏览器兼容性处理 */
@supports not (backdrop-filter: blur(20px)) {
  :deep(.ant-menu-dark .ant-menu-sub) {
    background: rgba(255, 255, 255, 0.15) !important;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
}

/* 动画关键帧 */
@keyframes menuItemGlow {
  0% {
    box-shadow: 0 0 5px rgba(255, 255, 255, 0.3);
  }
  50% {
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
  }
  100% {
    box-shadow: 0 0 5px rgba(255, 255, 255, 0.3);
  }
}

.menu-item-primary.ant-menu-item-selected,
.menu-item-primary.ant-menu-submenu-selected {
  animation: menuItemGlow 2s ease-in-out infinite;
}
</style>