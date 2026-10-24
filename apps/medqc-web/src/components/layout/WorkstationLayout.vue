<template>
  <a-layout
    class="workstation-layout workstation-layout--apple min-h-screen"
    :class="{
      'workstation-layout--overview': isQcOverviewRoute,
      'workstation-layout--mobile-menu-open': isNarrowScreen && mobileMenuOpen,
    }"
  >
    <ConfigProvider :theme="WORKSTATION_THEME">
      <button
        v-if="isNarrowScreen && mobileMenuOpen"
        type="button"
        class="mobile-menu-backdrop"
        aria-label="关闭导航菜单"
        @click="mobileMenuOpen = false"
      />
      <!-- 侧边栏 -->
      <a-layout-sider
        :collapsed="isNarrowScreen ? false : collapsed"
        collapsible
        class="sidebar-container relative overflow-hidden border-none"
        theme="light"
        width="240"
        :collapsed-width="72"
        :trigger="null"
        @update:collapsed="handleSiderCollapse"
      >
        <!-- Logo区域 -->
        <div class="logo-container" :class="{ 'logo-container--collapsed': collapsed }">
          <div class="brand-card" :class="{ 'brand-card--collapsed': collapsed }">
            <div class="brand-mark" aria-hidden="true">
              <MqIcon name="rules" color="#FFFFFF" :size="24" />
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

        <a-button
          type="text"
          class="sidebar-collapse-control"
          :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
          @click="collapsed = !collapsed"
        >
          <MenuUnfoldOutlined v-if="collapsed" /><MenuFoldOutlined v-else />
        </a-button>

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
            <a-sub-menu
              v-if="canSeeAny(WORKSTATION_MENU_TARGETS)"
              key="workstation-sub"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="overview" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <template #title>
                <span class="font-medium">工作台</span>
              </template>
              <a-menu-item v-if="canSee('/workstation-v5')" key="/workstation-v5">
                <template #icon>
                  <MqIconTile name="overview" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>工作台首页</span>
              </a-menu-item>
              <a-menu-item v-if="canSee('/workstation-v5/worklist')" key="/workstation-v5/worklist">
                <template #icon>
                  <MqIconTile name="pool" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>病历池</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/records/outpatient-emergency')"
                key="/workstation-v5/records/outpatient-emergency"
              >
                <template #icon>
                  <MqIconTile name="doc" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>门急诊病历</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/records/running')"
                key="/workstation-v5/records/running"
              >
                <template #icon>
                  <MqIconTile name="running" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>运行病历质控</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/records/final')"
                key="/workstation-v5/records/final"
              >
                <template #icon>
                  <MqIconTile name="final" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>已出院病历质控</span>
              </a-menu-item>
              <a-menu-item
                v-if="isDemoFeedbackAccount && canSee('/workstation-v5/qc-feedback-demo')"
                key="/workstation-v5/qc-feedback-demo"
              >
                <template #icon>
                  <MqIconTile name="settlement" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>质控反馈记录</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/customer-sample-validation')"
                key="/workstation-v5/customer-sample-validation"
              >
                <template #icon>
                  <MqIconTile name="sample" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>客户样本验证</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee(STAGE_MENU_TARGET)"
                key="ws-stage-frontpage-generate"
                @click="goStageMenu('frontpage_generate')"
              >
                <template #icon>
                  <MqIconTile name="fp_generate" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>生成首页</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee(STAGE_MENU_TARGET)"
                key="ws-stage-frontpage-qc"
                @click="goStageMenu('frontpage_qc')"
              >
                <template #icon>
                  <MqIconTile name="fp_qc" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>首页质控</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee(STAGE_MENU_TARGET)"
                key="ws-stage-settlement-qc"
                @click="goStageMenu('settlement_qc')"
              >
                <template #icon>
                  <MqIconTile name="settlement" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>结算清单质控</span>
              </a-menu-item>
            </a-sub-menu>

            <a-sub-menu
              v-if="canSeeAny(STATISTICS_MENU_TARGETS)"
              key="statistics-sub"
              class="menu-item-base statistics-menu"
            >
              <template #icon>
                <MqIconTile name="stats" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <template #title>
                <span class="font-medium">统计分析</span>
              </template>
              <a-menu-item v-if="canSee('/workstation-v5/stats')" key="/workstation-v5/stats">
                <template #icon>
                  <MqIconTile name="stats" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>质控统计总览</span>
              </a-menu-item>
              <template v-for="item in REPORT_MENU_ITEMS" :key="item.path">
                <a-menu-item
                  v-if="canSee(item.path)"
                  :key="item.path"
                  :title="item.title"
                  class="statistics-report-item"
                >
                  <template #icon>
                    <MqIconTile name="stats" :size="24" :icon-size="16" class="sidebar-icon" />
                  </template>
                  <span>{{ item.title }}</span>
                </a-menu-item>
              </template>
            </a-sub-menu>

            <!-- 质控规则 -->
            <a-sub-menu
              v-if="canSeeAny(RULES_MENU_TARGETS)"
              key="qc-rules-sub"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="rules" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <template #title>
                <span class="font-medium">质控规则</span>
              </template>
              <a-menu-item
                v-if="canSee('/workstation-v5/rules?tab=coding')"
                key="/workstation-v5/rules?tab=coding"
              >
                <template #icon>
                  <MqIconTile name="rules" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>编码质控规则</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/rules?tab=semantic&ruleSetKey=luxian_0609_qc_v1')"
                key="/workstation-v5/rules?tab=semantic&ruleSetKey=luxian_0609_qc_v1"
              >
                <template #icon>
                  <MqIconTile name="rules" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>全病历质控规则</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/rules?tab=frontpage')"
                key="/workstation-v5/rules?tab=frontpage"
              >
                <template #icon>
                  <MqIconTile name="doc" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>首页质控规则</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/rules?tab=settlement')"
                key="/workstation-v5/rules?tab=settlement"
              >
                <template #icon>
                  <MqIconTile name="settlement" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>医保结算清单规则</span>
              </a-menu-item>
            </a-sub-menu>

            <!-- ICD 编码查询 -->
            <a-menu-item
              v-if="canSee('/workstation-v5/icd')"
              key="/workstation-v5/icd"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="icd" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <span class="font-medium">ICD 编码查询</span>
            </a-menu-item>

            <!-- DRG/DIP 分析 -->
            <a-sub-menu v-if="canSeeAny(DRG_MENU_TARGETS)" key="drg-sub" class="menu-item-base">
              <template #icon>
                <MqIconTile name="drg" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <template #title>
                <span class="font-medium">DRG/DIP 分析</span>
              </template>
              <a-menu-item v-if="canSee('/workstation-v5/drg/pre')" key="/workstation-v5/drg/pre">
                <template #icon>
                  <MqIconTile name="stats" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>事前分析</span>
              </a-menu-item>
              <a-menu-item v-if="canSee('/workstation-v5/drg/mid')" key="/workstation-v5/drg/mid">
                <template #icon>
                  <MqIconTile name="drg" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>事中监控</span>
              </a-menu-item>
              <a-menu-item
                v-if="canSee('/workstation-v5/drg/payment')"
                key="/workstation-v5/drg/payment"
              >
                <template #icon>
                  <MqIconTile name="drg" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>付费监测</span>
              </a-menu-item>
              <a-menu-item v-if="canSee('/workstation-v5/drg/post')" key="/workstation-v5/drg/post">
                <template #icon>
                  <MqIconTile name="stats" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>事后分析</span>
              </a-menu-item>
              <a-menu-item v-if="canSee('/workstation-v5/grouper')" key="/workstation-v5/grouper">
                <template #icon>
                  <MqIconTile name="drg" :size="24" :icon-size="16" class="sidebar-icon" />
                </template>
                <span>分组器</span>
              </a-menu-item>
            </a-sub-menu>

            <a-menu-item
              v-if="canSee('/workstation-v5/rules/custom-workspace')"
              key="/workstation-v5/rules/custom-workspace"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="custom_rule" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <span class="font-medium">自定义质控点</span>
            </a-menu-item>

            <a-menu-item
              v-if="canSee('/workstation-v5/document-definitions')"
              key="/workstation-v5/document-definitions"
              class="menu-item-base"
              data-testid="document-definitions-menu"
            >
              <template #icon>
                <MqIconTile name="doc" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <span class="font-medium">文书管理</span>
            </a-menu-item>

            <!-- 数据上传 -->
            <a-menu-item
              v-if="canSee('/workstation-v5/upload')"
              key="/workstation-v5/upload"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="upload" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <span class="font-medium">数据上传</span>
            </a-menu-item>

            <!-- 系统配置 -->
            <a-menu-item
              v-if="canSee('/workstation-v5/system-config')"
              key="/workstation-v5/system-config"
              class="menu-item-base"
            >
              <template #icon>
                <MqIconTile name="settings" :size="24" :icon-size="16" class="sidebar-icon" />
              </template>
              <span class="font-medium">系统配置</span>
            </a-menu-item>
          </a-menu>
        </div>
        <div class="workstation-account-footer">
          <div class="workstation-build-row">
            <RuntimeBuildStatus />
            <a-popover placement="rightBottom" trigger="click">
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
                  <Bell :size="18" />
                </div>
              </a-badge>
            </a-popover>
          </div>
          <div class="workstation-account-menu">
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
        </div>
      </a-layout-sider>

      <a-button
        v-if="isNarrowScreen"
        type="text"
        class="mobile-menu-trigger"
        :aria-label="mobileMenuOpen ? '关闭导航菜单' : '打开导航菜单'"
        :aria-expanded="mobileMenuOpen"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <MenuFoldOutlined v-if="mobileMenuOpen" />
        <MenuUnfoldOutlined v-else />
      </a-button>

      <!-- 主内容区域 -->
      <a-layout>
        <!-- 内容区域 -->
        <a-layout-content
          class="workstation-content overflow-x-hidden"
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
    </ConfigProvider>
  </a-layout>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import RuntimeBuildStatus from '@/components/layout/RuntimeBuildStatus.vue'
import { useRouter, useRoute } from 'vue-router'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { useAuthStore } from '@/stores/auth'
import { canAccessPath } from '@/utils/routeAccess'
import {
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  UserOutlined,
  DownOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons-vue'
import { ConfigProvider } from 'ant-design-vue'
import { Bell } from 'lucide-vue-next'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { WORKSTATION_THEME } from './workstationTheme'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const REPORT_MENU_ITEMS = [
  { path: '/workstation-v5/reports/record-quality', title: '病历质量分析' },
  { path: '/workstation-v5/reports/special-records', title: '特殊病历报表' },
  { path: '/workstation-v5/reports/frontpage-quality', title: '病案首页统计分析' },
  { path: '/workstation-v5/reports/staff-analysis', title: '质控员工作分析' },
] as const

// 响应式数据
const collapsed = ref(false)
const mobileMediaQuery = '(max-width: 767px)'
const isNarrowScreen = ref(
  typeof window !== 'undefined' &&
    (window.matchMedia?.(mobileMediaQuery).matches ?? window.innerWidth <= 767),
)
const mobileMenuOpen = ref(false)
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>([])

let mediaQueryList: MediaQueryList | undefined
let compactMediaQueryList: MediaQueryList | undefined
function syncCompactScreen(event: MediaQueryListEvent) {
  if (!isNarrowScreen.value) collapsed.value = event.matches
}
function syncNarrowScreen(event: MediaQueryListEvent) {
  isNarrowScreen.value = event.matches
  collapsed.value = event.matches ? false : Boolean(compactMediaQueryList?.matches)
  mobileMenuOpen.value = false
}
onMounted(() => {
  mediaQueryList = window.matchMedia?.(mobileMediaQuery)
  mediaQueryList?.addEventListener('change', syncNarrowScreen)
  compactMediaQueryList = window.matchMedia?.('(max-width: 1279px)')
  if (!isNarrowScreen.value) collapsed.value = Boolean(compactMediaQueryList?.matches)
  compactMediaQueryList?.addEventListener('change', syncCompactScreen)
})
onBeforeUnmount(() => {
  mediaQueryList?.removeEventListener('change', syncNarrowScreen)
  compactMediaQueryList?.removeEventListener('change', syncCompactScreen)
})

function handleSiderCollapse(value: boolean) {
  if (!isNarrowScreen.value) collapsed.value = value
}

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
    '/workstation-v5/document-definitions': '文书管理',
    '/workstation-v5/rules': '质控规则管理',
    '/workstation-v5/rules/custom-workspace': '自定义质控点',
    '/workstation-v5/records/outpatient-emergency': '门急诊病历',
    '/workstation-v5/records/running': '运行病历',
    '/workstation-v5/records/final': '已出院病历质控',
    '/workstation-v5/qc-feedback-demo': '质控反馈记录',
    '/workstation-v5/customer-sample-validation': '客户样本验证',
    '/workstation-v5/system-config': '系统配置',
  }
  return REPORT_MENU_ITEMS.find((item) => item.path === path)?.title || titleMap[path] || '工作台'
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

// 菜单可见性：按目标路由 meta.permission 过滤（与路由守卫同一判断），分组无可访问子项时隐藏
const canSee = (target: string) => canAccessPath(router, target, authStore.userRoles ?? [])
const canSeeAny = (targets: readonly string[]) => targets.some(canSee)
/** 生成首页/首页质控/结算清单质控三个阶段入口均落到病历池 */
const STAGE_MENU_TARGET = '/workstation-v5/worklist'
const WORKSTATION_MENU_TARGETS = [
  '/workstation-v5',
  '/workstation-v5/worklist',
  '/workstation-v5/records/outpatient-emergency',
  '/workstation-v5/records/running',
  '/workstation-v5/records/final',
  '/workstation-v5/customer-sample-validation',
] as const
const STATISTICS_MENU_TARGETS = [
  '/workstation-v5/stats',
  ...REPORT_MENU_ITEMS.map((item) => item.path),
] as const
const RULES_MENU_TARGETS = [
  '/workstation-v5/rules?tab=coding',
  '/workstation-v5/rules?tab=semantic&ruleSetKey=luxian_0609_qc_v1',
  '/workstation-v5/rules?tab=frontpage',
  '/workstation-v5/rules?tab=settlement',
] as const
const DRG_MENU_TARGETS = [
  '/workstation-v5/drg/pre',
  '/workstation-v5/drg/mid',
  '/workstation-v5/drg/payment',
  '/workstation-v5/drg/post',
  '/workstation-v5/grouper',
] as const

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
  mobileMenuOpen.value = false
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
    mobileMenuOpen.value = false
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
      STATISTICS_MENU_TARGETS.some((path) => path === base) &&
      !openKeys.value.includes('statistics-sub')
    ) {
      openKeys.value = [...openKeys.value, 'statistics-sub']
    }
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

<style scoped src="@/components/layout/styles/workstation-v71.css"></style>
