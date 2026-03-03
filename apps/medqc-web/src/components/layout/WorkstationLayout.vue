<template>
  <a-layout class="min-h-screen">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      class="sidebar-container shadow-xl relative overflow-hidden border-none bg-slate-900"
      theme="dark"
      width="260"
    >
      <!-- Logo区域 -->
      <div class="logo-container relative px-4 py-5 flex items-center justify-center transition-all duration-300 border-b border-slate-800" :class="collapsed ? 'px-2' : 'px-6'">
        <div class="flex items-center gap-3 overflow-hidden whitespace-nowrap">
          <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20 flex-shrink-0 transition-all duration-300">
             <MedicineBoxOutlined class="text-white text-xl" />
          </div>
          <div v-if="!collapsed" class="flex flex-col transition-all duration-300 opacity-100">
            <span class="text-white font-bold text-lg leading-tight tracking-tight">病案质控系统</span>
            <span class="text-slate-400 text-xs font-medium tracking-wide">AI-Powered QC Platform</span>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <div class="flex-1 overflow-y-auto py-4 custom-scrollbar">
        <a-menu
          v-model:selectedKeys="selectedKeys"
          mode="inline"
          theme="dark"
          class="border-none px-3 space-y-1 bg-slate-900"
          @select="handleMenuSelect"
        >
        <!-- 工作台 -->
        <a-menu-item key="/workstation-v2" class="menu-item-base">
          <template #icon>
            <ThunderboltOutlined />
          </template>
          <span class="font-medium">工作台</span>
        </a-menu-item>

        <!-- ICD 编码查询 -->
        <a-menu-item key="/workstation-v2/icd" class="menu-item-base">
          <template #icon>
            <SearchOutlined />
          </template>
          <span class="font-medium">ICD 编码查询</span>
        </a-menu-item>

        <!-- DRG/DIP 分析 -->
        <a-sub-menu key="drg-sub" class="menu-item-base">
          <template #icon>
            <ClusterOutlined />
          </template>
          <template #title>
            <span class="font-medium">DRG/DIP 分析</span>
          </template>
          <a-menu-item key="/workstation-v2/drg/pre">
             <template #icon><FileSearchOutlined /></template>
            <span>事前分析</span>
          </a-menu-item>
          <a-menu-item key="/workstation-v2/drg/mid">
             <template #icon><DashboardOutlined /></template>
            <span>事中监控</span>
          </a-menu-item>
          <a-menu-item key="/workstation-v2/drg/payment">
             <template #icon><DollarOutlined /></template>
            <span>付费监测</span>
          </a-menu-item>
          <a-menu-item key="/workstation-v2/drg/post">
             <template #icon><BarChartOutlined /></template>
            <span>事后分析</span>
          </a-menu-item>
        </a-sub-menu>

        <!-- 数据上传 -->
        <a-menu-item key="/workstation-v2/upload" class="menu-item-base">
          <template #icon>
            <CloudUploadOutlined />
          </template>
          <span class="font-medium">数据上传</span>
        </a-menu-item>

        <!-- 统计分析 -->
        <a-menu-item key="/workstation-v2/stats" class="menu-item-base">
          <template #icon>
            <BarChartOutlined />
          </template>
          <span class="font-medium">统计分析</span>
        </a-menu-item>

        <!-- 数据管理 -->
        <a-menu-item key="/workstation-v2/data" class="menu-item-base">
          <template #icon>
            <DatabaseOutlined />
          </template>
          <span class="font-medium">数据管理</span>
        </a-menu-item>

        </a-menu>
      </div>
    </a-layout-sider>

    <!-- 主内容区域 -->
    <a-layout>
      <!-- 顶部导航栏 -->
      <a-layout-header class="header bg-white/90 backdrop-blur-sm sticky top-0 z-20 shadow-sm border-b border-slate-200/60 px-6 flex items-center justify-between h-16 transition-all duration-300">
        <div class="flex items-center">
          <a-button
            type="text"
            @click="collapsed = !collapsed"
            class="trigger hover:bg-slate-100 text-slate-500 hover:text-slate-700 border-0 mr-4 rounded-lg w-9 h-9 flex items-center justify-center transition-colors"
          >
            <MenuUnfoldOutlined v-if="collapsed" class="text-lg" />
            <MenuFoldOutlined v-else class="text-lg" />
          </a-button>

          <!-- 面包屑 -->
          <a-breadcrumb class="hidden md:flex items-center">
            <a-breadcrumb-item>
              <router-link to="/workstation-v2" class="flex items-center text-slate-400 hover:text-blue-600 transition-colors px-2 py-1 rounded-md hover:bg-slate-50">
                <HomeOutlined class="text-base" />
              </router-link>
            </a-breadcrumb-item>
            <a-breadcrumb-item v-for="item in breadcrumbItems" :key="item.title">
              <span class="text-slate-800 font-semibold text-sm px-2 py-1">{{ item.title }}</span>
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <!-- 右侧用户信息 -->
        <div class="flex items-center space-x-3">
          <!-- 通知 -->
          <a-popover placement="bottomRight" trigger="click">
            <template #content>
              <div class="w-72 p-2">
                <div class="flex justify-between items-center mb-2 px-2">
                  <span class="font-bold text-slate-700">通知中心</span>
                  <span class="text-xs text-blue-600 cursor-pointer">全部已读</span>
                </div>
                <div class="space-y-1">
                  <div class="p-3 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors flex gap-3 items-start">
                    <div class="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0"></div>
                    <div>
                      <div class="text-sm text-slate-700 font-medium">系统升级通知</div>
                      <div class="text-xs text-slate-400 mt-0.5">系统将于今晚进行维护升级...</div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <a-badge count="5" :numberStyle="{ backgroundColor: '#ef4444', boxShadow: '0 0 0 1px #fff' }" class="cursor-pointer">
              <div class="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors">
                <BellOutlined class="text-xl" />
              </div>
            </a-badge>
          </a-popover>

          <div class="w-px h-6 bg-slate-200 mx-2"></div>

          <!-- 用户头像和菜单 -->
          <a-dropdown :trigger="['click']">
            <div class="flex items-center cursor-pointer hover:bg-slate-100 p-1.5 pr-3 rounded-full transition-all duration-200 group select-none">
              <a-avatar :size="36" class="mr-2 bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm group-hover:shadow-md transition-shadow border-2 border-white">
                <template #icon><UserOutlined /></template>
              </a-avatar>
              <div class="flex flex-col mr-1 hidden sm:flex">
                <span class="text-sm font-bold text-slate-700 leading-tight group-hover:text-blue-600 transition-colors">{{ authStore.userName }}</span>
                <span class="text-[10px] text-slate-400 font-medium uppercase tracking-wider">{{ authStore.userRoles?.[0] || 'User' }}</span>
              </div>
              <DownOutlined class="ml-2 text-xs text-slate-400 group-hover:text-slate-600 transition-colors" />
            </div>
            <template #overlay>
              <a-menu class="min-w-[180px] p-2 rounded-2xl border border-slate-100 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.1)]">
                <div class="px-3 py-2 mb-1">
                  <div class="text-xs text-slate-400">Signed in as</div>
                  <div class="font-bold text-slate-700 truncate">
                    {{ authStore.user?.email || 'user@example.com' }}
                  </div>
                </div>
                <div class="h-px bg-slate-100 my-1"></div>
                <a-menu-item key="profile" class="rounded-lg mb-1 !py-2">
                  <UserOutlined />
                  <span class="ml-2 font-medium">个人中心</span>
                </a-menu-item>
                <a-menu-item key="settings" class="rounded-lg mb-1 !py-2">
                  <SettingOutlined />
                  <span class="ml-2 font-medium">账户设置</span>
                </a-menu-item>
                <div class="h-px bg-slate-100 my-1"></div>
                <a-menu-item key="logout" @click="handleLogout" class="rounded-lg !text-red-500 hover:!bg-red-50 hover:!text-red-600 !py-2">
                  <LogoutOutlined />
                  <span class="ml-2 font-medium">退出登录</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 内容区域 -->
      <a-layout-content class="bg-slate-100 overflow-x-hidden">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
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
  ThunderboltOutlined,
  SearchOutlined,
  CloudUploadOutlined,
  ClusterOutlined,
  FileSearchOutlined,
  DashboardOutlined,
  DollarOutlined,
  BarChartOutlined,
  HomeOutlined,
  BellOutlined,
  UserOutlined,
  DownOutlined,
  SettingOutlined,
  LogoutOutlined,
  MedicineBoxOutlined,
  DatabaseOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 响应式数据
const collapsed = ref(false)
const selectedKeys = ref<string[]>([])

// 面包屑
const breadcrumbItems = computed(() => {
  const path = route.path
  const titleMap: Record<string, string> = {
    '/workstation-v2': '工作台',
    '/workstation-v2/icd': 'ICD 编码查询',
    '/workstation-v2/upload': '数据上传',
    '/workstation-v2/stats': '统计分析',
    '/workstation-v2/drg/pre': '事前分析',
    '/workstation-v2/drg/mid': '事中监控',
    '/workstation-v2/drg/payment': '付费监测',
    '/workstation-v2/drg/post': '事后分析',
    '/workstation-v2/data': '数据管理',
  }
  const title = titleMap[path] || '工作台'
  return [{ title }]
})

// 方法
const handleMenuSelect = ({ key }: { key: string }) => {
  router.push(key)
}

const handleLogout = async () => {
  await authStore.signOut()
  router.push('/auth/login')
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
/* Ant Design 菜单样式重写 */
:deep(.ant-menu-dark) {
  background: transparent !important;
}

/* 菜单项通用样式 */
:deep(.ant-menu-item),
:deep(.ant-menu-submenu-title) {
  border-radius: 8px;
  margin: 4px 0;
  width: 100%;
  color: #94a3b8; /* Slate-400 */
  transition: all 0.2s ease;
  height: 42px !important;
  line-height: 42px !important;
}

/* 菜单项悬停 */
:deep(.ant-menu-item:hover),
:deep(.ant-menu-submenu-title:hover) {
  color: #fff !important;
  background-color: rgba(255, 255, 255, 0.1) !important;
}

/* 菜单项选中 */
:deep(.ant-menu-item-selected) {
  background-color: #2563eb !important; /* Blue-600 */
  color: #fff !important;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
}

/* 选中项高亮条 */
:deep(.ant-menu-item-selected::after) {
  display: none;
}

/* 子菜单容器 */
:deep(.ant-menu-sub.ant-menu-inline) {
  background: rgba(0, 0, 0, 0.2) !important;
}

/* 子菜单项缩进 */
:deep(.ant-menu-inline .ant-menu-item) {
  padding-left: 48px !important;
}

/* 图标样式 */
:deep(.anticon) {
  font-size: 18px;
  vertical-align: middle;
}

/* 滚动条 */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #475569;
}

/* 头部样式 */
.header {
  height: 64px;
  line-height: 64px;
}
</style>
