<template>
  <a-layout class="min-h-screen">
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      breakpoint="md"
      :collapsed-width="0"
      class="sidebar-container shadow-xl relative overflow-hidden border-none bg-slate-900"
      theme="dark"
      width="260"
    >
      <!-- Logo区域 -->
      <div
        class="logo-container relative px-4 py-5 flex items-center justify-center transition-all duration-300 border-b border-slate-800"
        :class="collapsed ? 'px-2' : 'px-6'"
      >
        <div class="flex items-center gap-3 overflow-hidden whitespace-nowrap">
          <div
            class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/20 flex-shrink-0 transition-all duration-300"
          >
            <MedicineBoxOutlined class="text-white text-xl" />
          </div>
          <div
            v-if="!collapsed"
            class="flex flex-col transition-all duration-300 opacity-100"
          >
            <span class="text-white font-bold text-lg leading-tight tracking-tight">病案质控系统</span>
            <span class="text-slate-400 text-xs font-medium tracking-wide">AI-Powered QC Platform</span>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <div class="flex-1 overflow-y-auto py-4 custom-scrollbar">
        <a-menu
          v-model:selected-keys="selectedKeys"
          mode="inline"
          theme="dark"
          class="border-none px-3 space-y-1 bg-slate-900"
          :open-keys="['/dashboard/records', '/dashboard/drg', '/dashboard/rules']"
          @select="handleMenuSelect"
        >
          <!-- 仪表板 -->
          <a-menu-item
            key="/dashboard"
            class="menu-item-base"
          >
            <template #icon>
              <DashboardOutlined />
            </template>
            <span class="font-medium">仪表板</span>
          </a-menu-item>

          <!-- 智能质控工作站 -->
          <a-menu-item
            key="/dashboard/workstation"
            class="menu-item-base"
          >
            <template #icon>
              <DesktopOutlined />
            </template>
            <span class="font-medium">智能质控工作站</span>
          </a-menu-item>

          <a-menu-item
            v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
            key="/workstation-v5"
            class="menu-item-base"
          >
            <template #icon>
              <AlertOutlined />
            </template>
            <span class="font-medium">工作台首页</span>
          </a-menu-item>

          <!-- 病案质控 -->
          <a-sub-menu
            key="/dashboard/records"
            class="menu-item-base"
          >
            <template #icon>
              <FileTextOutlined />
            </template>
            <template #title>
              <span class="font-medium">病案质控</span>
            </template>
            <a-menu-item key="/dashboard/records/running">
              <template #icon>
                <PlayCircleOutlined />
              </template>
              <span>运行病历</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/records/final">
              <template #icon>
                <CheckCircleOutlined />
              </template>
              <span>已出院病历</span>
            </a-menu-item>
          </a-sub-menu>

          <!-- 质控规则管理（改为子菜单，与V4工作站保持一致） -->
          <a-sub-menu
            v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
            key="/dashboard/rules"
            class="menu-item-base"
          >
            <template #icon>
              <SafetyCertificateOutlined />
            </template>
            <template #title>
              <span class="font-medium">质控规则</span>
            </template>
            <a-menu-item key="/dashboard/rules?tab=coding">
              <template #icon>
                <MedicineBoxOutlined />
              </template>
              <span>编码质控规则</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/rules?tab=semantic">
              <template #icon>
                <BranchesOutlined />
              </template>
              <span>全病历质控规则</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/rules?tab=frontpage">
              <template #icon>
                <FileTextOutlined />
              </template>
              <span>首页质控规则</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/rules?tab=settlement">
              <template #icon>
                <DollarOutlined />
              </template>
              <span>医保结算清单规则</span>
            </a-menu-item>
          </a-sub-menu>

          <a-menu-item
            v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
            key="/workstation-v5/rules/custom-workspace"
            class="menu-item-base"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            <span class="font-medium">自定义质控点</span>
          </a-menu-item>

          <!-- 任务管理 -->
          <a-sub-menu
            key="/dashboard/tasks"
            class="menu-item-base"
          >
            <template #icon>
              <ProjectOutlined />
            </template>
            <template #title>
              <span class="font-medium">任务管理</span>
            </template>
            <a-menu-item key="/dashboard/tasks/my">
              <template #icon>
                <UserOutlined />
              </template>
              <span>我的任务</span>
            </a-menu-item>
            <a-menu-item
              v-if="authStore.hasRole('admin') || authStore.hasRole('qc_manager')"
              key="/dashboard/tasks/all"
            >
              <template #icon>
                <TeamOutlined />
              </template>
              <span>全部任务</span>
            </a-menu-item>
          </a-sub-menu>

          <!-- 统计分析 -->
          <a-menu-item
            key="/dashboard/statistics"
            class="menu-item-base"
          >
            <template #icon>
              <BarChartOutlined />
            </template>
            <span class="font-medium">统计分析</span>
          </a-menu-item>

          <!-- DRG/DIP -->
          <a-sub-menu
            key="/dashboard/drg"
            class="menu-item-base"
          >
            <template #icon>
              <MedicineBoxOutlined />
            </template>
            <template #title>
              <span class="font-medium">DRG/DIP</span>
            </template>
            <a-menu-item key="/dashboard/drg/index">
              <template #icon>
                <HomeOutlined />
              </template>
              <span>DRG 首页</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/drg/coding">
              <template #icon>
                <FileTextOutlined />
              </template>
              <span>编码辅助</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/drg/grouping">
              <template #icon>
                <BranchesOutlined />
              </template>
              <span>分组预测</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/drg/monitor">
              <template #icon>
                <RadarChartOutlined />
              </template>
              <span>事中监控</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/drg/fee-monitoring">
              <template #icon>
                <DollarOutlined />
              </template>
              <span>付费监测</span>
            </a-menu-item>
            <a-menu-item key="/dashboard/drg/analysis">
              <template #icon>
                <BarChartOutlined />
              </template>
              <span>事后分析</span>
            </a-menu-item>
          </a-sub-menu>

          <!-- 系统管理（与 DRG/DIP 平级） -->
          <a-sub-menu
            key="/dashboard/system"
            class="menu-item-base"
          >
            <template #icon>
              <ToolOutlined />
            </template>
            <template #title>
              <span class="font-medium">系统管理</span>
            </template>

            <!-- 系统设置 -->
            <a-menu-item
              v-if="authStore.hasRole('admin')"
              key="/dashboard/settings"
            >
              <template #icon>
                <SettingOutlined />
              </template>
              <span>系统设置</span>
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
      </div>
    </a-layout-sider>

    <!-- 主内容区域 -->
    <a-layout>
      <!-- 顶部导航栏 (极简白风格) -->
      <a-layout-header
        class="header bg-white/90 backdrop-blur-sm sticky top-0 z-20 shadow-sm border-b border-slate-200/60 px-6 flex items-center justify-between h-16 transition-all duration-300"
      >
        <div class="flex items-center">
          <a-button
            type="text"
            class="trigger hover:bg-slate-100 text-slate-500 hover:text-slate-700 border-0 mr-4 rounded-lg w-9 h-9 flex items-center justify-center transition-colors"
            @click="collapsed = !collapsed"
          >
            <MenuUnfoldOutlined
              v-if="collapsed"
              class="text-lg"
            />
            <MenuFoldOutlined
              v-else
              class="text-lg"
            />
          </a-button>

          <!-- 面包屑 (胶囊风格) -->
          <a-breadcrumb class="hidden md:flex items-center">
            <a-breadcrumb-item>
              <router-link
                to="/dashboard"
                class="flex items-center text-slate-400 hover:text-blue-600 transition-colors px-2 py-1 rounded-md hover:bg-slate-50"
              >
                <HomeOutlined class="text-base" />
              </router-link>
            </a-breadcrumb-item>
            <a-breadcrumb-item
              v-for="item in breadcrumbItems"
              :key="item.path"
            >
              <router-link
                v-if="item.path"
                :to="item.path"
                class="text-slate-500 hover:text-blue-600 transition-colors text-sm font-medium px-2 py-1 rounded-md hover:bg-slate-50"
              >
                {{ item.title }}
              </router-link>
              <span
                v-else
                class="text-slate-800 font-semibold text-sm px-2 py-1"
              >{{
                item.title
              }}</span>
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <!-- 右侧用户信息 -->
        <div class="flex items-center space-x-3">
          <!-- 通知 -->
          <a-popover
            placement="bottomRight"
            trigger="click"
          >
            <template #content>
              <div class="w-72 p-2">
                <div class="flex justify-between items-center mb-2 px-2">
                  <span class="font-bold text-slate-700">通知中心</span>
                  <span class="text-xs text-blue-600 cursor-pointer">全部已读</span>
                </div>
                <div class="space-y-1">
                  <div
                    class="p-3 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors flex gap-3 items-start"
                  >
                    <div class="w-2 h-2 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                    <div>
                      <div class="text-sm text-slate-700 font-medium">
                        系统升级通知
                      </div>
                      <div class="text-xs text-slate-400 mt-0.5">
                        系统将于今晚进行维护升级...
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <a-badge
              count="5"
              :number-style="{ backgroundColor: '#ef4444', boxShadow: '0 0 0 1px #fff' }"
              class="cursor-pointer"
            >
              <div
                class="w-10 h-10 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
              >
                <BellOutlined class="text-xl" />
              </div>
            </a-badge>
          </a-popover>

          <div class="w-px h-6 bg-slate-200 mx-2" />

          <!-- 用户头像和菜单 -->
          <a-dropdown :trigger="['click']">
            <div
              class="flex items-center cursor-pointer hover:bg-slate-100 p-1.5 pr-3 rounded-full transition-all duration-200 group select-none"
            >
              <a-avatar
                :size="36"
                class="mr-2 bg-[#2563eb] text-white shadow-sm group-hover:shadow-md transition-shadow border-2 border-white"
              >
                <template #icon>
                  <UserOutlined />
                </template>
              </a-avatar>
              <div class="flex flex-col mr-1 hidden sm:flex">
                <span
                  class="text-sm font-bold text-slate-700 leading-tight group-hover:text-blue-600 transition-colors"
                >{{ authStore.userName }}</span>
                <span class="text-[10px] text-slate-400 font-medium uppercase tracking-wider">{{
                  authStore.userRoles?.[0] || 'User'
                }}</span>
              </div>
              <DownOutlined
                class="ml-2 text-xs text-slate-400 group-hover:text-slate-600 transition-colors"
              />
            </div>
            <template #overlay>
              <a-menu
                class="min-w-[180px] p-2 rounded-2xl border border-slate-100 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.1)]"
              >
                <div class="px-3 py-2 mb-1">
                  <div class="text-xs text-slate-400">
                    Signed in as
                  </div>
                  <div class="font-bold text-slate-700 truncate">
                    {{ authStore.user?.email || 'user@example.com' }}
                  </div>
                </div>
                <div class="h-px bg-slate-100 my-1" />
                <a-menu-item
                  key="profile"
                  class="rounded-lg mb-1 !py-2"
                >
                  <UserOutlined />
                  <span class="ml-2 font-medium">个人中心</span>
                </a-menu-item>
                <a-menu-item
                  key="settings"
                  class="rounded-lg mb-1 !py-2"
                >
                  <SettingOutlined />
                  <span class="ml-2 font-medium">账户设置</span>
                </a-menu-item>
                <div class="h-px bg-slate-100 my-1" />
                <a-menu-item
                  key="logout"
                  class="rounded-lg !text-red-500 hover:!bg-red-50 hover:!text-red-600 !py-2"
                  @click="handleLogout"
                >
                  <LogoutOutlined />
                  <span class="ml-2 font-medium">退出登录</span>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </a-layout-header>

      <!-- 内容区域 (移除原有内层卡片，由页面自行控制布局) -->
      <a-layout-content class="bg-slate-100 overflow-x-hidden">
        <router-view v-slot="{ Component }">
          <transition
            name="fade"
            mode="out-in"
          >
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
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
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
  AlertOutlined,
  UserOutlined,
  DownOutlined,
  LogoutOutlined,
  MedicineBoxOutlined,
  BranchesOutlined,
  DollarOutlined,
  ExperimentOutlined,
  PlayCircleOutlined,
  CheckCircleOutlined,
  ProjectOutlined,
  TeamOutlined,
  DesktopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

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
          items.push({ title: '已出院病历', path: null })
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
        items.push({ title: '病历管理', path: '/dashboard/medical-records' })
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
      case 'llm-qc-demo-enhanced':
        items.push({ title: 'LLM质控样例增强版', path: null })
        break
      case 'llm-qc-demo-new':
        items.push({ title: 'LLM质控样例新版', path: null })
        break
      case 'drg':
        items.push({ title: 'DRG/DIP', path: '/dashboard/drg' })
        if (pathSegments.length > 2) {
          if (pathSegments[2] === 'index') {
            items.push({ title: 'DRG 首页', path: null })
          } else if (pathSegments[2] === 'coding') {
            items.push({ title: '编码辅助', path: null })
            if (pathSegments.length > 3) {
              items.push({ title: '编码详情', path: null })
            }
          } else if (pathSegments[2] === 'grouping') {
            items.push({ title: '分组预测', path: null })
          } else if (pathSegments[2] === 'monitor') {
            items.push({ title: '事中监控', path: null })
          } else if (pathSegments[2] === 'fee-monitoring') {
            items.push({ title: '付费监测', path: null })
          } else if (pathSegments[2] === 'analysis') {
            items.push({ title: '事后分析', path: null })
          }
        }
        break
      case 'workstation':
        items.push({ title: '智能质控工作站', path: null })
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
const handleMenuSelect = ({ key }: MenuInfo) => {
  const keyStr = String(key)
  // 支持 key 包含 query 参数，如 /dashboard/rules?tab=coding
  if (keyStr.includes('?')) {
    const [path, queryStr] = keyStr.split('?')
    const params = new URLSearchParams(queryStr)
    const query: Record<string, string> = {}
    params.forEach((v, k) => {
      query[k] = v
    })
    router.push({ path, query })
  } else {
    router.push(keyStr)
  }
}

const handleLogout = async () => {
  await authStore.signOut()
  router.push('/login')
}

// 监听路由变化更新选中的菜单
watch(
  () => route.fullPath,
  () => {
    // 保持 query 参数以匹配子菜单项
    const base = route.path
    const tab = route.query.tab as string | undefined
    if (tab && base === '/dashboard/rules') {
      selectedKeys.value = [`${base}?tab=${tab}`]
    } else {
      selectedKeys.value = [base]
    }
  },
  { immediate: true },
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

/* 选中项高亮条 (移除右侧条，改用整体背景) */
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
  background: #334155; /* Slate-700 */
  border-radius: 4px;
}

.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #475569; /* Slate-600 */
}

/* 头部样式 */
.header {
  height: 64px;
  line-height: 64px;
}
</style>
