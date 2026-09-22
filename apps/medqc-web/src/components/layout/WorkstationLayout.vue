<template>
  <a-layout
    class="workstation-layout workstation-layout--apple min-h-screen"
    :class="{
      'workstation-layout--overview': isQcOverviewRoute,
    }"
  >
    <!-- 侧边栏 -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      class="sidebar-container relative overflow-hidden border-none"
      theme="light"
      width="220"
    >
      <!-- Logo区域 -->
      <div class="logo-container" :class="{ 'logo-container--collapsed': collapsed }">
        <div class="brand-card" :class="{ 'brand-card--collapsed': collapsed }">
          <div class="brand-mark" aria-hidden="true">
            <svg
              class="brand-mark-svg"
              viewBox="0 0 40 40"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M20 5.4 30.2 9.1v9.7c0 7.1-4.2 13.2-10.2 15.8C14 32 9.8 25.9 9.8 18.8V9.1L20 5.4Z"
                fill="white"
                fill-opacity=".18"
                stroke="white"
                stroke-width="2.2"
                stroke-linejoin="round"
              />
              <path
                d="M20 13.2v13.6M13.2 20h13.6"
                stroke="white"
                stroke-width="3"
                stroke-linecap="round"
              />
              <path
                d="M15.2 30.2c1.4 1.3 3 2.4 4.8 3.2 1.8-.8 3.4-1.9 4.8-3.2"
                stroke="white"
                stroke-opacity=".55"
                stroke-width="1.6"
                stroke-linecap="round"
              />
            </svg>
          </div>
          <div v-if="!collapsed" class="brand-copy">
            <span class="brand-title">病案质控系统</span>
            <span class="brand-subtitle">
              <span>质量</span>
              <i />
              <span>安全</span>
              <i />
              <span>改进</span>
            </span>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <div class="flex-1 overflow-y-auto py-4 custom-scrollbar">
        <a-menu
          v-model:selected-keys="selectedKeys"
          mode="inline"
          theme="light"
          class="workstation-sidebar-menu border-none px-3 space-y-1 bg-transparent"
          :open-keys="openKeys"
          @click="handleMenuSelect"
          @open-change="handleMenuOpenChange"
        >
          <!-- 工作台 -->
          <a-sub-menu key="workstation-sub" class="menu-item-base">
            <template #icon>
              <MonitorCog class="sidebar-icon" />
            </template>
            <template #title>
              <span class="font-medium">工作台</span>
            </template>
            <a-menu-item key="/workstation-v5">
              <template #icon>
                <House class="sidebar-icon" />
              </template>
              <span>工作台首页</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/worklist">
              <template #icon>
                <FolderKanban class="sidebar-icon" />
              </template>
              <span>病历池</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/stats">
              <template #icon>
                <ChartNoAxesColumnIncreasing class="sidebar-icon" />
              </template>
              <span>统计分析</span>
            </a-menu-item>
            <a-menu-item
              v-if="canAccessOutpatientEmergency"
              key="/workstation-v5/records/outpatient-emergency"
            >
              <template #icon>
                <Stethoscope class="sidebar-icon" />
              </template>
              <span>门急诊病历</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/records/running">
              <template #icon>
                <PlayCircle class="sidebar-icon" />
              </template>
              <span>运行病历质控</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/records/final">
              <template #icon>
                <CircleCheck class="sidebar-icon" />
              </template>
              <span>终末病历质控</span>
            </a-menu-item>
            <a-menu-item v-if="isDemoFeedbackAccount" key="/workstation-v5/qc-feedback-demo">
              <template #icon>
                <ReceiptText class="sidebar-icon" />
              </template>
              <span>质控反馈记录</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/customer-sample-validation">
              <template #icon>
                <FileSearch class="sidebar-icon" />
              </template>
              <span>客户样本验证</span>
            </a-menu-item>
            <a-menu-item
              key="ws-stage-frontpage-generate"
              @click="goStageMenu('frontpage_generate')"
            >
              <template #icon>
                <FilePlus2 class="sidebar-icon" />
              </template>
              <span>生成首页</span>
            </a-menu-item>
            <a-menu-item key="ws-stage-frontpage-qc" @click="goStageMenu('frontpage_qc')">
              <template #icon>
                <ShieldCheck class="sidebar-icon" />
              </template>
              <span>首页质控</span>
            </a-menu-item>
            <a-menu-item key="ws-stage-settlement-qc" @click="goStageMenu('settlement_qc')">
              <template #icon>
                <ReceiptText class="sidebar-icon" />
              </template>
              <span>结算清单质控</span>
            </a-menu-item>
          </a-sub-menu>

          <!-- 质控规则 -->
          <a-sub-menu key="qc-rules-sub" class="menu-item-base">
            <template #icon>
              <Shield class="sidebar-icon" />
            </template>
            <template #title>
              <span class="font-medium">质控规则</span>
            </template>
            <a-menu-item key="/workstation-v5/rules?tab=coding">
              <template #icon>
                <Pill class="sidebar-icon" />
              </template>
              <span>编码质控规则</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/rules?tab=semantic&ruleSetKey=luxian_0609_qc_v1">
              <template #icon>
                <Workflow class="sidebar-icon" />
              </template>
              <span>全病历质控规则</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/rules?tab=frontpage">
              <template #icon>
                <FileText class="sidebar-icon" />
              </template>
              <span>首页质控规则</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/rules?tab=settlement">
              <template #icon>
                <ReceiptText class="sidebar-icon" />
              </template>
              <span>医保结算清单规则</span>
            </a-menu-item>
          </a-sub-menu>

          <!-- ICD 编码查询 -->
          <a-menu-item key="/workstation-v5/icd" class="menu-item-base">
            <template #icon>
              <Search class="sidebar-icon" />
            </template>
            <span class="font-medium">ICD 编码查询</span>
          </a-menu-item>

          <!-- DRG/DIP 分析 -->
          <a-sub-menu key="drg-sub" class="menu-item-base">
            <template #icon>
              <Network class="sidebar-icon" />
            </template>
            <template #title>
              <span class="font-medium">DRG/DIP 分析</span>
            </template>
            <a-menu-item key="/workstation-v5/drg/pre">
              <template #icon>
                <FileChartColumn class="sidebar-icon" />
              </template>
              <span>事前分析</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/drg/mid">
              <template #icon>
                <Activity class="sidebar-icon" />
              </template>
              <span>事中监控</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/drg/payment">
              <template #icon>
                <BadgeDollarSign class="sidebar-icon" />
              </template>
              <span>付费监测</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/drg/post">
              <template #icon>
                <ChartNoAxesColumnIncreasing class="sidebar-icon" />
              </template>
              <span>事后分析</span>
            </a-menu-item>
            <a-menu-item key="/workstation-v5/grouper">
              <template #icon>
                <GitFork class="sidebar-icon" />
              </template>
              <span>分组器</span>
            </a-menu-item>
          </a-sub-menu>

          <a-menu-item key="/workstation-v5/rules/custom-workspace" class="menu-item-base">
            <template #icon>
              <Bolt class="sidebar-icon" />
            </template>
            <span class="font-medium">自定义质控点</span>
          </a-menu-item>

          <!-- 数据上传 -->
          <a-menu-item key="/workstation-v5/upload" class="menu-item-base">
            <template #icon>
              <CloudUpload class="sidebar-icon" />
            </template>
            <span class="font-medium">数据上传</span>
          </a-menu-item>

          <!-- 系统配置 -->
          <a-menu-item key="/workstation-v5/system-config" class="menu-item-base">
            <template #icon>
              <Settings class="sidebar-icon" />
            </template>
            <span class="font-medium">系统配置</span>
          </a-menu-item>
        </a-menu>
      </div>
    </a-layout-sider>

    <!-- 主内容区域 -->
    <a-layout>
      <!-- 顶部导航栏 -->
      <a-layout-header
        v-if="!isQcOverviewRoute"
        class="header bg-white/90 backdrop-blur-sm sticky top-0 z-20 shadow-sm border-b border-slate-200/60 px-6 flex items-center justify-between h-16 transition-all duration-300"
      >
        <div class="flex items-center">
          <a-button
            type="text"
            class="trigger hover:bg-slate-100 text-slate-500 hover:text-slate-700 border-0 mr-4 rounded-lg w-9 h-9 flex items-center justify-center transition-colors"
            @click="collapsed = !collapsed"
          >
            <MenuUnfoldOutlined v-if="collapsed" class="text-lg" />
            <MenuFoldOutlined v-else class="text-lg" />
          </a-button>

          <!-- 面包屑 -->
          <a-breadcrumb class="hidden md:flex items-center whitespace-nowrap" separator="">
            <a-breadcrumb-item>
              <router-link
                to="/workstation-v5"
                class="flex items-center gap-2 text-slate-700 hover:text-[#2b6cf6] transition-colors px-2 py-1 rounded-md hover:bg-slate-50"
              >
                <HomeOutlined class="text-base" />
                <span class="font-semibold text-sm">工作台</span>
              </router-link>
            </a-breadcrumb-item>
            <a-breadcrumb-item v-if="currentPageTitle !== '工作台'">
              <span class="mx-1 text-slate-300">/</span>
            </a-breadcrumb-item>
            <a-breadcrumb-item v-if="currentPageTitle !== '工作台'">
              <span class="text-slate-800 font-semibold text-sm px-1">{{ currentPageTitle }}</span>
            </a-breadcrumb-item>
          </a-breadcrumb>
        </div>

        <!-- 右侧用户信息 -->
        <div class="flex items-center space-x-3 shrink-0">
          <RuntimeBuildStatus />
          <!-- 通知 -->
          <a-popover placement="bottomRight" trigger="click">
            <template #content>
              <div class="w-72 p-2">
                <div class="flex justify-between items-center mb-2 px-2">
                  <span class="font-bold text-slate-700">通知中心</span>
                  <span class="text-xs text-[#2b6cf6] cursor-pointer">全部已读</span>
                </div>
                <div class="space-y-1">
                  <div
                    class="p-3 hover:bg-slate-50 rounded-lg cursor-pointer transition-colors flex gap-3 items-start"
                  >
                    <div class="w-2 h-2 rounded-full bg-[#2b6cf6] mt-1.5 shrink-0" />
                    <div>
                      <div class="text-sm text-slate-700 font-medium">系统升级通知</div>
                      <div class="text-xs text-slate-400 mt-0.5">系统将于今晚进行维护升级...</div>
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
              class="flex items-center cursor-pointer hover:bg-slate-100 p-1.5 pr-4 rounded-xl transition-all duration-200 group select-none"
            >
              <a-avatar
                :size="36"
                class="mr-2 bg-[#2b6cf6] text-white shadow-sm group-hover:shadow-md transition-shadow border-2 border-white"
              >
                <template #icon>
                  <UserOutlined />
                </template>
              </a-avatar>
              <div class="flex flex-col mr-1 hidden sm:flex shrink-0">
                <span
                  class="text-sm font-bold text-slate-700 leading-tight group-hover:text-[#2b6cf6] transition-colors whitespace-nowrap"
                  >{{ roleLabel }}</span
                >
                <span
                  class="text-[10px] text-slate-400 font-medium tracking-wider leading-tight whitespace-nowrap"
                  >{{ authStore.user?.email || '' }}</span
                >
              </div>
              <DownOutlined
                class="ml-2 text-xs text-slate-400 group-hover:text-slate-600 transition-colors shrink-0"
              />
            </div>
            <template #overlay>
              <a-menu
                class="min-w-[180px] p-2 rounded-2xl border border-slate-100 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.1)]"
              >
                <div class="px-3 py-2 mb-1">
                  <div class="text-xs text-slate-400">Signed in as</div>
                  <div class="font-bold text-slate-700 truncate">
                    {{ authStore.user?.email || 'user@example.com' }}
                  </div>
                </div>
                <div class="h-px bg-slate-100 my-1" />
                <a-menu-item key="profile" class="rounded-lg mb-1 !py-2">
                  <UserOutlined />
                  <span class="ml-2 font-medium">个人中心</span>
                </a-menu-item>
                <a-menu-item key="settings" class="rounded-lg mb-1 !py-2">
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

      <!-- 内容区域 -->
      <a-layout-content
        class="bg-slate-100 overflow-x-hidden"
        :class="{ 'workstation-overview-content': isQcOverviewRoute }"
      >
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <div :key="route.fullPath" class="workstation-route-view">
              <component :is="Component" v-if="Component" />
            </div>
          </transition>
        </router-view>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import RuntimeBuildStatus from '@/components/layout/RuntimeBuildStatus.vue'
import { useRouter, useRoute } from 'vue-router'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { useAuthStore } from '@/stores/auth'
import {
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  HomeOutlined,
  BellOutlined,
  UserOutlined,
  DownOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons-vue'
import {
  Activity,
  BadgeDollarSign,
  Bolt,
  ChartNoAxesColumnIncreasing,
  CircleCheck,
  CloudUpload,
  FileChartColumn,
  FilePlus2,
  FileSearch,
  FileText,
  FolderKanban,
  GitFork,
  House,
  MonitorCog,
  Network,
  Pill,
  PlayCircle,
  ReceiptText,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  Stethoscope,
  Workflow,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 响应式数据
const collapsed = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])

// 当前页面标题
const currentPageTitle = computed(() => {
  const path = route.path
  const titleMap: Record<string, string> = {
    '/workstation-v5': '工作台',
    '/workstation-v5/qc-overview': '工作台',
    '/workstation-v5/worklist': '病历池',
    '/workstation-v5/icd': 'ICD 编码查询',
    '/workstation-v5/upload': '数据上传',
    '/workstation-v5/stats': '统计分析',
    '/workstation-v5/drg/pre': '事前分析',
    '/workstation-v5/drg/mid': '事中监控',
    '/workstation-v5/drg/payment': '付费监测',
    '/workstation-v5/drg/post': '事后分析',
    '/workstation-v5/grouper': '医保分组器',
    '/workstation-v5/data': '数据管理',
    '/workstation-v5/rules': '质控规则管理',
    '/workstation-v5/rules/custom-workspace': '自定义质控点',
    '/workstation-v5/records/outpatient-emergency': '门急诊病历',
    '/workstation-v5/records/running': '运行病历',
    '/workstation-v5/records/final': '终末病历质控',
    '/workstation-v5/qc-feedback-demo': '质控反馈记录',
    '/workstation-v5/customer-sample-validation': '客户样本验证',
    '/workstation-v5/system-config': '系统配置',
  }
  return titleMap[path] || '工作台'
})

// 角色中文映射
const ROLE_LABEL_MAP: Record<string, string> = {
  admin: '系统管理员',
  qc_manager: '质控主管',
  QC_MANAGER: '质控主管',
  coder: '病案编码员',
  doctor: '临床医生',
  reviewer: '审核员',
  nurse: '护士',
}
const roleLabel = computed(() => {
  const raw = authStore.userRoles?.[0] || ''
  return ROLE_LABEL_MAP[raw] || raw || '用户'
})

const isDemoFeedbackAccount = computed(
  () =>
    authStore.user?.is_demo_account === true &&
    String(authStore.user?.id || '').trim() === 'admin-001' &&
    String(authStore.user?.email || '')
      .trim()
      .toLowerCase() === 'admin@medqc.com',
)

const isQcOverviewRoute = computed(() => route.path === '/workstation-v5/qc-overview')
const canAccessOutpatientEmergency = computed(() =>
  authStore.userRoles.some((role) => ['admin', 'qc_manager'].includes(role)),
)

// 方法
async function navigateTo(path: string, query?: Record<string, string>) {
  try {
    if (query) {
      await router.push({ path, query })
      return
    }
    await router.push(path)
  } catch (error) {
    console.warn('[WorkstationLayout] router.push failed, fallback to location.assign', error)
    if (query) {
      const queryString = new URLSearchParams(query).toString()
      window.location.assign(queryString ? `${path}?${queryString}` : path)
      return
    }
    window.location.assign(path)
  }
}

const handleMenuSelect = async ({ key }: MenuInfo) => {
  const keyStr = String(key)
  if (keyStr.startsWith('ws-stage-')) return
  if (keyStr.includes('?')) {
    const [path, queryStr] = keyStr.split('?')
    const params = new URLSearchParams(queryStr)
    const query: Record<string, string> = {}
    params.forEach((v, k) => {
      query[k] = v
    })
    await navigateTo(path, query)
  } else {
    await navigateTo(keyStr)
  }
}

const handleMenuOpenChange = (keys: string[]) => {
  openKeys.value = keys
}

function goStageMenu(stage: 'frontpage_generate' | 'frontpage_qc' | 'settlement_qc') {
  navigateTo('/workstation-v5/worklist', { stage })
}

const handleLogout = async () => {
  await authStore.signOut()
  if (route.path.startsWith('/workstation-v5')) {
    router.push('/workstation-v5/login')
    return
  }
  router.push('/auth/login')
}

// 监听路由变化更新选中的菜单
watch(
  () => route.fullPath,
  () => {
    const base = route.path === '/workstation-v5/qc-overview' ? '/workstation-v5' : route.path
    const tab = String(route.query.tab || '').trim()
    if (
      base === '/workstation-v5/rules' &&
      ['coding', 'semantic', 'frontpage', 'settlement'].includes(tab)
    ) {
      selectedKeys.value = [`/workstation-v5/rules?tab=${tab}`]
      return
    }
    if (base === '/workstation-v5/rules') {
      selectedKeys.value = ['/workstation-v5/rules?tab=coding']
      return
    }
    const stage = String(route.query.stage || '').trim()
    if (
      (base === '/workstation-v5' || base === '/workstation-v5/worklist') &&
      stage === 'frontpage_generate'
    ) {
      selectedKeys.value = ['ws-stage-frontpage-generate']
      return
    }
    if (
      (base === '/workstation-v5' || base === '/workstation-v5/worklist') &&
      stage === 'frontpage_qc'
    ) {
      selectedKeys.value = ['ws-stage-frontpage-qc']
      return
    }
    if (
      (base === '/workstation-v5' || base === '/workstation-v5/worklist') &&
      stage === 'settlement_qc'
    ) {
      selectedKeys.value = ['ws-stage-settlement-qc']
      return
    }
    selectedKeys.value = [base]
    if (
      base === '/workstation-v5/records/outpatient-emergency' &&
      !openKeys.value.includes('workstation-sub')
    ) {
      openKeys.value = [...openKeys.value, 'workstation-sub']
    }
  },
  { immediate: true },
)
</script>

<style scoped>
@import '../../styles/source-han-sans-sc.css';
.logo-container {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  padding: 12px 12px 10px;
  transition: padding 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.logo-container--collapsed {
  padding: 12px 8px 10px;
}

.brand-card {
  align-items: center;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 18px;
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.04),
    0 12px 28px rgba(15, 23, 42, 0.06);
  display: flex;
  gap: 12px;
  min-height: 64px;
  overflow: hidden;
  padding: 11px 12px;
  transition:
    background 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.brand-card:hover {
  background: rgba(255, 255, 255, 0.9);
  border-color: rgba(43, 108, 246, 0.18);
  box-shadow:
    0 2px 12px rgba(0, 0, 0, 0.08),
    0 14px 30px rgba(43, 108, 246, 0.09);
  transform: translateY(-1px);
}

.brand-card--collapsed {
  justify-content: center;
  min-height: 56px;
  padding: 9px 8px;
}

.brand-mark {
  align-items: center;
  background:
    radial-gradient(circle at 28% 18%, rgba(255, 255, 255, 0.72), transparent 24%),
    linear-gradient(135deg, #2997ff 0%, #0a84ff 48%, #5ac8fa 100%);
  border-radius: 15px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.46),
    0 8px 18px rgba(43, 108, 246, 0.22);
  display: inline-flex;
  flex: 0 0 auto;
  height: 42px;
  justify-content: center;
  position: relative;
  width: 42px;
}

.brand-mark::after {
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: inherit;
  content: '';
  inset: 0;
  pointer-events: none;
  position: absolute;
}

.brand-mark-svg {
  height: 29px;
  width: 29px;
}

.brand-copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}

.brand-title {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'SF Pro Display', 'SF Pro Text', 'San Francisco', 'PingFang SC',
    'Microsoft YaHei UI', system-ui, sans-serif;
  font-size: 16px;
  font-weight: 760;
  letter-spacing: -0.01em;
  line-height: 20px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-subtitle {
  align-items: center;
  color: rgba(29, 29, 31, 0.5);
  display: inline-flex;
  font-size: 11px;
  font-weight: 600;
  gap: 6px;
  letter-spacing: 0.08em;
  line-height: 16px;
  margin-top: 3px;
  white-space: nowrap;
}

.brand-subtitle i {
  background: rgba(43, 108, 246, 0.32);
  border-radius: 999px;
  display: inline-block;
  height: 3px;
  width: 3px;
}

.sidebar-icon {
  color: currentColor;
  height: 17px;
  stroke-width: 2.15;
  width: 17px;
}

/* Ant Design 菜单样式重写 */
:deep(.ant-menu-dark) {
  background: transparent !important;
}

.sidebar-container :deep(.ant-menu) {
  background: transparent !important;
  font-family:
    'Source Han Sans SC', 'SF Pro Text', 'SF Pro Display', 'San Francisco', 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

/* 菜单项通用样式 */
.sidebar-container :deep(.ant-menu-item),
.sidebar-container :deep(.ant-menu-submenu-title) {
  align-items: center;
  border: 1px solid transparent;
  border-radius: 10px;
  color: rgba(29, 29, 31, 0.72);
  display: flex;
  height: 42px !important;
  line-height: 42px !important;
  margin: 4px 0;
  overflow: hidden;
  position: relative;
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    color 0.18s ease,
    transform 0.18s ease;
  width: 100%;
}

.sidebar-container :deep(.ant-menu-item .ant-menu-item-icon),
.sidebar-container :deep(.ant-menu-submenu-title .ant-menu-item-icon) {
  align-items: center;
  color: currentColor;
  display: inline-flex;
  justify-content: center;
  margin-inline-end: 10px;
  min-width: 18px;
}

.sidebar-container :deep(.ant-menu-item .ant-menu-item-icon svg),
.sidebar-container :deep(.ant-menu-submenu-title .ant-menu-item-icon svg) {
  display: block;
}

.sidebar-container :deep(.ant-menu-title-content) {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0;
}

/* 菜单项悬停 */
.sidebar-container :deep(.ant-menu-item:hover),
.sidebar-container :deep(.ant-menu-submenu-title:hover) {
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
  background: rgba(0, 0, 0, 0.05) !important;
  border-color: transparent !important;
  box-shadow: none;
  color: #1d1d1f !important;
  transform: translateX(1px);
}

/* 菜单项选中 */
.sidebar-container :deep(.ant-menu-item-selected),
.sidebar-container :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title) {
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  background: rgba(43, 108, 246, 0.1) !important;
  border-color: transparent !important;
  box-shadow: none !important;
  color: #2b6cf6 !important;
  font-weight: 700;
  position: relative;
}

.sidebar-container :deep(.ant-menu-item-selected .ant-menu-title-content),
.sidebar-container
  :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title .ant-menu-title-content),
.sidebar-container :deep(.ant-menu-item-selected .ant-menu-item-icon),
.sidebar-container :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title .ant-menu-item-icon) {
  color: #2b6cf6 !important;
}

.sidebar-container :deep(.ant-menu-item-selected::before),
.sidebar-container :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title::before) {
  content: '';
  position: absolute;
  top: 18%;
  left: 0;
  width: 4px;
  height: 64%;
  background-color: #2b6cf6;
  border-radius: 4px;
  box-shadow: none;
}

/* 选中项高亮条 */
.sidebar-container :deep(.ant-menu-item-selected::after) {
  display: none;
}

/* 子菜单容器 */
.sidebar-container :deep(.ant-menu-sub.ant-menu-inline) {
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  background: rgba(255, 255, 255, 0.58) !important;
  border: 1px solid rgba(0, 0, 0, 0.045);
  border-radius: 12px;
  margin: 0 8px 4px 8px;
  padding: 4px 0 4px 0 !important;
  margin-left: 24px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.62);
}

/* 子菜单项 — 更紧凑、缩进更深、字体更小 */
.sidebar-container :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item) {
  border: 1px solid transparent !important;
  height: 36px !important;
  line-height: 36px !important;
  font-size: 14px !important;
  padding-left: 20px !important;
  margin: 1px 4px !important;
  border-radius: 6px;
  color: rgba(29, 29, 31, 0.52) !important;
}

/* 子菜单项图标缩小 */
.sidebar-container :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item .sidebar-icon) {
  height: 15px;
  width: 15px;
}

/* 子菜单项悬停 */
.sidebar-container :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item:hover) {
  color: #1d1d1f !important;
  background: rgba(0, 0, 0, 0.05) !important;
  border-color: transparent !important;
}

/* 子菜单项选中 */
.sidebar-container :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected) {
  background: rgba(43, 108, 246, 0.1) !important;
  border-color: transparent !important;
  color: #2b6cf6 !important;
  font-weight: 700;
  box-shadow: none;
  position: relative;
}

.sidebar-container
  :deep(
    .ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected .ant-menu-title-content
  ),
.sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected .ant-menu-item-icon) {
  color: #2b6cf6 !important;
}

.sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected::before) {
  content: '';
  position: absolute;
  top: 20%;
  left: -4px;
  width: 3px;
  height: 60%;
  background-color: #2b6cf6;
  border-radius: 4px;
  box-shadow: none;
}

/* 展开的父菜单标题高亮 */
.sidebar-container :deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  color: #1d1d1f !important;
}

.sidebar-container :deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  background: rgba(43, 108, 246, 0.07) !important;
  border-color: transparent !important;
}

/* 展开箭头 */
.sidebar-container :deep(.ant-menu-submenu-arrow) {
  color: #64748b !important;
}
.sidebar-container :deep(.ant-menu-submenu-open > .ant-menu-submenu-title .ant-menu-submenu-arrow) {
  color: #2b6cf6 !important;
}

/* 图标样式 */
.sidebar-container :deep(.anticon) {
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
  background: rgba(29, 29, 31, 0.16);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(29, 29, 31, 0.24);
}

/* 头部样式 */
.header {
  height: 64px;
}

.workstation-layout--overview {
  min-height: 100vh;
  background: #f5f5f7;
}

.workstation-layout--overview :deep(.ant-layout) {
  background: transparent;
}

.workstation-layout--overview :deep(.ant-layout-sider) {
  margin: 32px 0 32px 32px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-right-color: rgba(203, 213, 225, 0.72);
  border-radius: 18px 0 0 18px;
  background: #ffffff !important;
  box-shadow: 0 18px 42px rgba(50, 82, 120, 0.1);
}

.workstation-layout--overview .logo-container {
  border-bottom-color: rgba(203, 213, 225, 0.56) !important;
}

.workstation-layout--overview .sidebar-container :deep(.ant-layout-sider-trigger) {
  border-top: 1px solid rgba(203, 213, 225, 0.5);
  background: rgba(255, 255, 255, 0.72) !important;
  color: #64748b;
}

.workstation-layout--overview :deep(.ant-menu) {
  background: transparent !important;
}

.workstation-layout--overview :deep(.ant-menu-item),
.workstation-layout--overview :deep(.ant-menu-submenu-title) {
  color: #64748b !important;
}

.workstation-layout--overview :deep(.ant-menu-item:hover),
.workstation-layout--overview :deep(.ant-menu-submenu-title:hover) {
  background: rgba(43, 108, 246, 0.07) !important;
  color: #0057b8 !important;
}

.workstation-layout--overview :deep(.ant-menu-item-selected) {
  background: rgba(43, 108, 246, 0.1) !important;
  color: #2b6cf6 !important;
}

.workstation-layout--overview :deep(.ant-menu-sub.ant-menu-inline) {
  border-left-color: rgba(43, 108, 246, 0.16);
  background: rgba(248, 250, 252, 0.72) !important;
}

.workstation-layout--overview :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item) {
  color: #64748b !important;
}

.workstation-layout--overview
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected) {
  background: rgba(43, 108, 246, 0.1) !important;
  color: #2b6cf6 !important;
}

.workstation-layout--overview :deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  color: #0057b8 !important;
}

.workstation-overview-content {
  background: transparent !important;
}

/* Apple light workstation shell */
.workstation-layout--apple {
  min-height: 100vh;
  background: linear-gradient(155deg, #cbdcf1 0%, #e3e8f0 32%, #f5f5f7 65%, #dbe5f1 100%);
  color: #1d1d1f;
}

.workstation-layout--apple :deep(.ant-layout) {
  background: #f5f5f7;
}

.workstation-layout--apple :deep(.ant-layout-content) {
  background: #f5f5f7 !important;
}

.workstation-route-view {
  display: flex;
  min-height: 100%;
  min-width: 0;
  flex: 1 1 auto;
  flex-direction: column;
}

.workstation-layout--apple .sidebar-container {
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border-right: 1px solid rgba(0, 0, 0, 0.08) !important;
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
  box-shadow: none !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-layout-sider-trigger) {
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.82) !important;
  color: rgba(29, 29, 31, 0.6);
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu),
.workstation-layout--apple .sidebar-container :deep(.ant-menu-light),
.workstation-layout--apple .sidebar-container :deep(.ant-menu-inline) {
  background: transparent !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-item),
.workstation-layout--apple .sidebar-container :deep(.ant-menu-submenu-title) {
  height: 40px !important;
  line-height: 40px !important;
  margin: 3px 0 !important;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  color: rgba(29, 29, 31, 0.72) !important;
  font-weight: 400;
  box-shadow: none !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-title-content) {
  color: currentColor;
  font-size: 14px;
  font-weight: 400;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-item:hover),
.workstation-layout--apple .sidebar-container :deep(.ant-menu-submenu-title:hover) {
  background: rgba(0, 0, 0, 0.05) !important;
  border-color: transparent !important;
  box-shadow: none !important;
  color: #1d1d1f !important;
  transform: none !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-item-selected),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title) {
  background: rgba(0, 122, 255, 0.1) !important;
  border-color: transparent !important;
  box-shadow: none !important;
  color: #007aff !important;
  font-weight: 500;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-item-selected .ant-menu-title-content),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title .ant-menu-title-content),
.workstation-layout--apple .sidebar-container :deep(.ant-menu-item-selected .ant-menu-item-icon),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title .ant-menu-item-icon) {
  color: #007aff !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-item-selected::before),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title::before) {
  top: 50%;
  left: 0;
  width: 3px;
  height: 18px;
  background: #007aff;
  border-radius: 0 2px 2px 0;
  box-shadow: none;
  transform: translateY(-50%);
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-sub.ant-menu-inline) {
  margin: 2px 0 10px 16px !important;
  padding: 5px 5px 5px 6px !important;
  border: 0 !important;
  border-radius: 12px !important;
  background: rgba(255, 255, 255, 0.16) !important;
  box-shadow: none !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item) {
  height: 34px !important;
  line-height: 34px !important;
  margin: 1px 0 !important;
  padding-left: 14px !important;
  border-radius: 8px !important;
  color: rgba(29, 29, 31, 0.7) !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item .ant-menu-title-content) {
  font-size: 14px;
  font-weight: 400;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item .ant-menu-item-icon),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item .sidebar-icon) {
  color: rgba(29, 29, 31, 0.42) !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item:hover) {
  background: rgba(0, 0, 0, 0.05) !important;
  color: #1d1d1f !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected) {
  background: rgba(0, 122, 255, 0.1) !important;
  border-color: transparent !important;
  box-shadow: none !important;
  color: #007aff !important;
  font-weight: 500;
}

.workstation-layout--apple
  .sidebar-container
  :deep(
    .ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected .ant-menu-title-content
  ),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected .ant-menu-item-icon),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected .sidebar-icon) {
  color: #007aff !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-sub.ant-menu-inline > .ant-menu-item.ant-menu-item-selected::before) {
  left: 0;
  width: 3px;
  height: 18px;
  background: #007aff;
  box-shadow: none;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-open > .ant-menu-submenu-title) {
  background: rgba(0, 122, 255, 0.07) !important;
  border-color: transparent !important;
  color: #1d1d1f !important;
  font-weight: 500;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-open > .ant-menu-submenu-title .ant-menu-title-content),
.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-open > .ant-menu-submenu-title .ant-menu-item-icon) {
  color: #1d1d1f !important;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu-submenu-arrow) {
  color: rgba(29, 29, 31, 0.38) !important;
}

.workstation-layout--apple
  .sidebar-container
  :deep(.ant-menu-submenu-open > .ant-menu-submenu-title .ant-menu-submenu-arrow) {
  color: #007aff !important;
}

.workstation-layout--apple .custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(29, 29, 31, 0.16);
}

.workstation-layout--apple .custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(29, 29, 31, 0.24);
}

.workstation-layout--apple .header {
  height: 54px !important;
  background: rgba(255, 255, 255, 0.82) !important;
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08) !important;
  box-shadow: none !important;
}

.workstation-layout--apple .trigger:hover,
.workstation-layout--apple .header :deep(.ant-btn-text:hover) {
  background: rgba(0, 0, 0, 0.05) !important;
}
/* 工作台共用侧栏材质，切换业务路由仅改变选中项。 */
.workstation-layout--apple .sidebar-container {
  background: rgba(255, 255, 255, 0.38) !important;
  -webkit-backdrop-filter: blur(28px) saturate(140%);
  backdrop-filter: blur(28px) saturate(140%);
  margin: 0 12px 12px 12px;
  height: calc(100vh - 12px);
  position: sticky;
  top: 0;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.8) !important;
  border-right-color: rgba(112, 137, 168, 0.24) !important;
  box-shadow:
    0 12px 32px rgba(39, 62, 94, 0.12),
    0 2px 6px rgba(39, 62, 94, 0.05),
    inset 0 1px 0 rgba(255, 255, 255, 0.9) !important;
}

.workstation-layout--apple .brand-card {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.workstation-layout--apple .logo-container {
  padding-top: 24px;
  padding-bottom: 24px;
}

.workstation-layout--apple .sidebar-container :deep(.ant-menu),
.workstation-layout--apple .sidebar-container :deep(.ant-layout-sider-trigger) {
  background: transparent !important;
}

.workstation-layout--apple .brand-title {
  font-family: 'Source Han Sans SC', 'Microsoft YaHei UI', 'PingFang SC', sans-serif;
  font-size: 18px;
  font-weight: 600;
}
.workstation-layout--apple .brand-subtitle {
  font-family: inherit;
  font-size: 12px;
  font-weight: 400;
  color: #86868b;
}
.workstation-layout--apple .brand-card:hover {
  transform: none;
}

.workstation-layout--apple .sidebar-container :deep(.ant-layout-sider-trigger) {
  position: absolute;
  bottom: 0;
  width: 100% !important;
}

/* 折叠控制独占底部 48px，菜单在剩余空间内滚动。 */
.workstation-layout--apple .sidebar-container :deep(.ant-layout-sider-children) {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  padding-bottom: 48px;
  box-sizing: border-box;
}
.workstation-layout--apple .sidebar-container .logo-container {
  flex-shrink: 0;
}
.workstation-layout--apple .sidebar-container .custom-scrollbar {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: none;
}
.workstation-layout--apple .sidebar-container .custom-scrollbar::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}
.workstation-layout--apple .sidebar-container :deep(.ant-layout-sider-trigger) {
  height: 48px;
  line-height: 48px;
  background: rgba(255, 255, 255, 0.7) !important;
  z-index: 1;
}

/* 顶部导航沿用工作区冷灰蓝玻璃材质。 */
.workstation-layout--apple .header {
  background: rgba(231, 239, 249, 0.72) !important;
  -webkit-backdrop-filter: blur(24px) saturate(135%) !important;
  backdrop-filter: blur(24px) saturate(135%) !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.6) !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65) !important;
}

/* 工作台共用画布：与运行病历质控一致，内容卡片维持各自表面。 */
.workstation-layout--apple {
  --medqc-workspace-canvas: linear-gradient(125deg, #dce8f6 0%, #f1f3f7 48%, #e4eaf3 100%);
}
.workstation-layout--apple :deep(.ant-layout-content),
.workstation-layout--apple :deep(.workstation-route-view),
.workstation-layout--apple :deep(.workstation-route-view > *) {
  background: var(--medqc-workspace-canvas) !important;
}
.workstation-layout--apple :deep(.record-pool-refined),
.workstation-layout--apple :deep(.qc-home-shell),
.workstation-layout--apple :deep(.running-qc-refined) {
  background: var(--medqc-workspace-canvas) !important;
}
</style>
