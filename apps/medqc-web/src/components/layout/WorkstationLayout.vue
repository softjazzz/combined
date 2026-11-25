<template>
  <!-- v7.1 主题只作用于工作台，旧版后台沿用 App.vue 的全局主题 -->
  <ConfigProvider :theme="WORKSTATION_THEME">
    <div class="ws-shell" :class="{ 'ws-shell--collapsed': collapsed }">
      <!-- 侧栏：分组标题 + 平铺入口（配置见 workstationNav.ts） -->
      <aside class="ws-sider">
        <div class="ws-sider__head">
          <RouterLink :to="homePath" class="ws-brand" aria-label="病案质控系统首页">
            <span class="ws-brand__mark" aria-hidden="true">
              <MqIcon name="rules" color="#FFFFFF" :size="18" />
            </span>
            <span v-if="!collapsed" class="ws-brand__copy">
              <span class="ws-brand__title">病案质控系统</span>
              <span class="ws-brand__subtitle">Medical Record QC</span>
            </span>
          </RouterLink>
          <button
            type="button"
            class="ws-sider__toggle"
            :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
            :aria-expanded="!collapsed"
            @click="toggleCollapsed"
          >
            <PanelLeftOpen v-if="collapsed" aria-hidden="true" />
            <PanelLeftClose v-else aria-hidden="true" />
          </button>
        </div>

        <nav class="ws-nav" aria-label="主导航">
          <section v-for="group in visibleNav" :key="group.key" class="ws-nav__group">
            <!-- 收起侧栏时分组标题退化为分隔线；展开时为可折叠的一级菜单 -->
            <div v-if="group.label && collapsed" class="ws-nav__group-label" aria-hidden="true" />
            <button
              v-else-if="group.label"
              type="button"
              class="ws-nav__group-label ws-nav__group-toggle"
              :aria-expanded="isGroupOpen(group.key)"
              :aria-controls="`ws-nav-group-${group.key}`"
              @click="toggleGroup(group.key)"
            >
              <span>{{ group.label }}</span>
              <ChevronDown
                :size="12"
                aria-hidden="true"
                class="ws-nav__group-chevron"
                :class="{ 'is-closed': !isGroupOpen(group.key) }"
              />
            </button>
            <div
              v-show="collapsed || !group.label || isGroupOpen(group.key)"
              :id="`ws-nav-group-${group.key}`"
              class="ws-nav__group-items"
            >
              <a-tooltip
                v-for="item in group.items"
                :key="item.key"
                :title="collapsed ? item.label : undefined"
                placement="right"
              >
                <RouterLink
                  :to="item.to"
                  class="ws-nav__item"
                  :class="{ 'ws-nav__item--active': activeKey === item.key }"
                  :aria-current="activeKey === item.key ? 'page' : undefined"
                  :aria-label="collapsed ? item.label : undefined"
                >
                  <MqIconTile
                    :name="item.iconName"
                    :tone="activeKey === item.key ? 'brand' : 'neutral'"
                    :size="24"
                    :icon-size="16"
                  />
                  <span v-if="!collapsed" class="ws-nav__label">{{ item.label }}</span>
                </RouterLink>
              </a-tooltip>
            </div>
          </section>
        </nav>

        <!-- 账号区：版本状态、通知、账号菜单（原顶栏内容） -->
        <div class="ws-sider__footer">
          <div v-if="!collapsed" class="ws-sider__build">
            <RuntimeBuildStatus placement="rightBottom" />
          </div>
          <div class="ws-account">
            <a-dropdown :trigger="['click']" placement="topLeft">
              <button type="button" class="ws-user" aria-label="账号菜单">
                <span class="ws-user__avatar" aria-hidden="true">{{ roleLabel.slice(0, 1) }}</span>
                <span v-if="!collapsed" class="ws-user__meta">
                  <span class="ws-user__role">{{ roleLabel }}</span>
                  <span class="ws-user__email">{{ authStore.user?.email || authStore.userName || '' }}</span>
                </span>
              </button>
              <template #overlay>
                <a-menu class="ws-user-menu">
                  <div class="ws-user-menu__who">
                    <div class="ws-user-menu__hint">当前账号</div>
                    <div class="ws-user-menu__email">
                      {{ authStore.user?.email || authStore.userName || '未登录' }}
                    </div>
                  </div>
                  <a-menu-divider />
                  <a-menu-item key="profile">
                    <User class="ws-user-menu__icon" />
                    个人中心
                  </a-menu-item>
                  <a-menu-item key="settings">
                    <Settings2 class="ws-user-menu__icon" />
                    账户设置
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="logout" class="ws-user-menu__logout" @click="handleLogout">
                    <LogOut class="ws-user-menu__icon" />
                    退出登录
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>

            <a-tooltip v-if="useFullMessageCenter" :title="messageCenterTooltip" placement="right">
              <router-link
                class="ws-icon-button ws-icon-button--messages"
                to="/workstation-v5/messages"
                :aria-label="messageCenterAriaLabel"
              >
                <Bell aria-hidden="true" />
                <span
                  v-if="messageUnreadBadge"
                  class="ws-icon-button__badge"
                  data-testid="ws-message-unread-badge"
                  aria-hidden="true"
                >
                  {{ messageUnreadBadge }}
                </span>
              </router-link>
            </a-tooltip>
            <a-popover v-else placement="rightBottom" trigger="click">
              <template #content>
                <div class="ws-notice">
                  <div class="ws-notice__title">通知</div>
                  <router-link class="ws-notice__empty" to="/workstation-v5/worklist?assist=message">查看消息与待办</router-link>
                </div>
              </template>
              <button type="button" class="ws-icon-button" aria-label="通知">
                <Bell aria-hidden="true" />
              </button>
            </a-popover>
          </div>
        </div>
      </aside>

      <div class="ws-main">
        <!-- DRG/DIP 分析：一个导航入口，子页在此切换，地址不变 -->
        <nav v-if="drgActiveTab" class="ws-section-tabs" aria-label="DRG/DIP 分析">
          <RouterLink
            v-for="tab in DRG_SECTION_TABS"
            :key="tab.key"
            :to="tab.path"
            class="ws-section-tabs__item"
            :class="{ 'ws-section-tabs__item--active': drgActiveTab.key === tab.key }"
            :aria-current="drgActiveTab.key === tab.key ? 'page' : undefined"
          >
            {{ tab.label }}
          </RouterLink>
        </nav>

        <main class="ws-content">
          <router-view v-slot="{ Component, route: currentRoute }">
            <div :key="currentRoute.path" class="workstation-route-view">
              <component :is="Component" v-if="Component" />
            </div>
          </router-view>
        </main>
      </div>
    </div>
    <GlobalAssistantHost />
    <WorkstationConfirmDialog :controller="workstationConfirmation" />
  </ConfigProvider>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ConfigProvider } from 'ant-design-vue'
import {
  Bell,
  ChevronDown,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Settings2,
  User,
} from 'lucide-vue-next'
import RuntimeBuildStatus from '@/components/layout/RuntimeBuildStatus.vue'
import MqIcon from '@/components/icons/MqIcon.vue'
import GlobalAssistantHost from '@/views/workstation-v4/components/GlobalAssistantHost.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { ApiService } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'
import { canUseMessageCenter } from '@/views/workstation/notificationNavigation'
import { canUseReminderPanel, WORKSTATION_REMINDER_PANEL } from '@/views/workstation/notificationNavigation'
import {
  getSharedMessageCenterUnreadVersion,
  MESSAGE_CENTER_UNREAD_EVENT,
  syncSharedMessageCenterUnreadCount,
  useSharedMessageCenterUnreadCount,
} from '@/views/workstation/useMessageCenter'
import {
  DRG_SECTION_TABS,
  WORKSTATION_NAV,
  filterVisibleNav,
  findActiveNav,
  findDrgSectionTab,
  resolveDefaultWorkstationPath,
  type NavLocation,
  type NavRouteLike,
} from './workstationNav'
import { WORKSTATION_THEME } from './workstationTheme'

import WorkstationConfirmDialog from './WorkstationConfirmDialog.vue'
import { createWorkstationConfirmation, WORKSTATION_CONFIRMATION } from './workstationConfirmation'

const workstationConfirmation = createWorkstationConfirmation()
provide(WORKSTATION_CONFIRMATION, workstationConfirmation)
onBeforeUnmount(workstationConfirmation.dispose)

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const homePath = computed(() => resolveDefaultWorkstationPath(authStore.userRoles ?? []))
const useFullMessageCenter = computed(() => canUseMessageCenter(authStore.userRoles))
provide(WORKSTATION_REMINDER_PANEL, computed(() => canUseReminderPanel(authStore.userRoles)))

const sharedMessageUnreadCount = useSharedMessageCenterUnreadCount()
const messageUnreadCount = computed(() =>
  useFullMessageCenter.value ? (sharedMessageUnreadCount.value ?? 0) : 0,
)
const messageUnreadBadge = computed(() => {
  const count = messageUnreadCount.value
  if (count <= 0) return ''
  return count > 99 ? '99+' : String(count)
})
const messageCenterTooltip = computed(() =>
  messageUnreadCount.value > 0 ? `消息中心（${messageUnreadCount.value} 条未读）` : '消息中心',
)
const messageCenterAriaLabel = computed(() =>
  messageUnreadCount.value > 0 ? `消息中心，${messageUnreadCount.value} 条未读` : '消息中心',
)

let unreadFetchSeq = 0
let fetchedUnreadForSessionKey = ''

function isApiAuthenticated(): boolean {
  return typeof ApiService?.isAuthenticated === 'function' ? ApiService.isAuthenticated() : false
}

async function fetchMessageUnreadCount(sessionKey: string) {
  if (
    !useFullMessageCenter.value ||
    !isApiAuthenticated() ||
    typeof ApiService?.get !== 'function'
  ) {
    return
  }
  const seq = ++unreadFetchSeq
  const versionBefore = getSharedMessageCenterUnreadVersion()
  try {
    const result = await ApiService.get<{ unread_count?: number }>(
      '/api/v1/notifications',
      { page: 1, page_size: 1, is_read: false },
      { skipErrorToast: true },
    )
    if (seq !== unreadFetchSeq || fetchedUnreadForSessionKey !== sessionKey) return
    if (versionBefore !== getSharedMessageCenterUnreadVersion()) return
    const unreadCount = result?.data?.unread_count
    if (
      result?.success &&
      typeof unreadCount === 'number' &&
      Number.isInteger(unreadCount) &&
      unreadCount >= 0
    ) {
      syncSharedMessageCenterUnreadCount(unreadCount, { emitEvent: false })
    }
  } catch {
    // 侧栏未读角标拉取失败时静默降级，不阻断工作台外壳渲染
  }
}

const messageUnreadSessionKey = computed(() => {
  if (!useFullMessageCenter.value) return ''
  const userId = String(authStore.user?.id || '').trim()
  return userId || (authStore.isAuthenticated ? 'authenticated' : '')
})

watch(
  messageUnreadSessionKey,
  (sessionKey, prevSessionKey) => {
    if (!sessionKey) {
      ++unreadFetchSeq
      fetchedUnreadForSessionKey = ''
      if (prevSessionKey) {
        syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
      }
      return
    }
    if (sessionKey === fetchedUnreadForSessionKey) return
    if (prevSessionKey && prevSessionKey !== sessionKey) {
      syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
    }
    fetchedUnreadForSessionKey = sessionKey
    void fetchMessageUnreadCount(sessionKey)
  },
  { immediate: true },
)

function handleUnreadCountEvent(event: Event) {
  const detail = (event as CustomEvent<{ unreadCount?: number | null }>).detail
  if (!detail || !('unreadCount' in detail)) return
  const nextCount = detail.unreadCount ?? null
  if (nextCount === sharedMessageUnreadCount.value) return
  syncSharedMessageCenterUnreadCount(nextCount, { emitEvent: false })
}

// 宽度小于 1280 时默认折叠；用户手动切换后以用户选择为准，直到下次跨越断点
const COLLAPSE_QUERY = '(max-width: 1279px)'
const collapsed = ref(false)
let collapseMedia: MediaQueryList | null = null

function syncCollapsedWithViewport(event: MediaQueryList | MediaQueryListEvent) {
  collapsed.value = event.matches
}

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

onMounted(() => {
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener(MESSAGE_CENTER_UNREAD_EVENT, handleUnreadCountEvent)
  }
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  collapseMedia = window.matchMedia(COLLAPSE_QUERY)
  syncCollapsedWithViewport(collapseMedia)
  collapseMedia.addEventListener('change', syncCollapsedWithViewport)
})

onBeforeUnmount(() => {
  ++unreadFetchSeq
  if (typeof window !== 'undefined' && typeof window.removeEventListener === 'function') {
    window.removeEventListener(MESSAGE_CENTER_UNREAD_EVENT, handleUnreadCountEvent)
  }
  collapseMedia?.removeEventListener('change', syncCollapsedWithViewport)
})

const ROLE_LABEL_MAP: Record<string, string> = {
  sync_admin: '超级管理员',
  super_admin: '超级管理员',
  admin: '系统管理员',
  qc_manager: '质控主管',
  QC_MANAGER: '质控主管',
  qc_staff: '质控员',
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

function resolvePermission(to: NavLocation): string[] | undefined {
  const permission = router.resolve(to).meta.permission
  return Array.isArray(permission) ? (permission as string[]) : undefined
}

const visibleNav = computed(() =>
  filterVisibleNav(WORKSTATION_NAV, {
    isDemoFeedbackAccount: isDemoFeedbackAccount.value,
    userRoles: authStore.userRoles ?? [],
    resolvePermission,
  }),
)

const navRoute = computed<NavRouteLike>(() => ({
  path: route.path,
  query: route.query as Record<string, unknown>,
  meta: route.meta as Record<string, unknown>,
}))

const activeNav = computed(() => findActiveNav(WORKSTATION_NAV, navRoute.value))
const activeKey = computed(() => activeNav.value?.item.key ?? '')

// 分组折叠：记在本机浏览器；当前页面所在分组总是自动展开
const GROUP_STORAGE_KEY = 'mq-sider-closed-groups'
const closedGroups = ref<Set<string>>(readClosedGroups())

function readClosedGroups(): Set<string> {
  try {
    const raw = window.localStorage.getItem(GROUP_STORAGE_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return new Set(
      Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === 'string') : [],
    )
  } catch {
    return new Set()
  }
}

function persistClosedGroups() {
  try {
    window.localStorage.setItem(GROUP_STORAGE_KEY, JSON.stringify([...closedGroups.value]))
  } catch {
    // 隐私模式等场景下无法写入，仅影响记忆，不影响折叠本身
  }
}

function isGroupOpen(key: string): boolean {
  return !closedGroups.value.has(key)
}

function toggleGroup(key: string) {
  const next = new Set(closedGroups.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  closedGroups.value = next
  persistClosedGroups()
}

watch(
  () => activeNav.value?.group.key,
  (groupKey) => {
    if (!groupKey || !closedGroups.value.has(groupKey)) return
    const next = new Set(closedGroups.value)
    next.delete(groupKey)
    closedGroups.value = next
    persistClosedGroups()
  },
  { immediate: true },
)
const drgActiveTab = computed(() => findDrgSectionTab(navRoute.value))

const handleLogout = async () => {
  ++unreadFetchSeq
  fetchedUnreadForSessionKey = ''
  syncSharedMessageCenterUnreadCount(null, { emitEvent: false })
  await authStore.signOut()
  router.push('/workstation-v5/login')
}
</script>

<style scoped>
@import '../../styles/source-han-sans-sc.css';

/* v7.1 液态玻璃外壳：光晕底 + 悬浮玻璃侧栏（无顶栏，账号区在侧栏底部） */
.ws-shell {
  display: flex;
  min-height: 100vh;
  background: var(--mq-bg-mesh);
  background-attachment: fixed;
  color: var(--mq-text-primary);
  font-family: var(--mq-font-family);
  -webkit-font-smoothing: antialiased;
}

.ws-sider {
  position: sticky;
  top: 14px;
  display: flex;
  flex: 0 0 var(--mq-sider-width);
  flex-direction: column;
  width: var(--mq-sider-width);
  height: calc(100vh - 28px);
  margin: 14px 0 14px 14px;
  padding: 16px 10px 10px;
  box-sizing: border-box;
  border: 1px solid var(--mq-glass-border);
  border-radius: 22px;
  background: var(--mq-glass-bg);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
  box-shadow: var(--mq-glass-shadow);
  overflow: hidden;
  transition:
    width 200ms ease,
    flex-basis 200ms ease;
  z-index: 30;
}

.ws-shell--collapsed .ws-sider {
  flex-basis: var(--mq-sider-collapsed-width);
  width: var(--mq-sider-collapsed-width);
  padding-inline: 8px;
}

.ws-sider__head {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 4px;
  min-width: 0;
  overflow: hidden;
  padding: 0 4px 14px 8px;
}

.ws-shell--collapsed .ws-sider__head {
  flex-direction: column;
  gap: 8px;
  padding-inline: 0;
}

.ws-brand {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  color: var(--mq-text-primary);
  text-decoration: none;
}

.ws-shell--collapsed .ws-brand {
  flex: 0 0 auto;
  justify-content: center;
}

.ws-brand__mark {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--mq-brand-gradient);
  box-shadow:
    inset 0 0.5px 0 rgba(255, 255, 255, 0.45),
    0 2px 6px rgba(10, 100, 230, 0.3);
}

.ws-brand__copy {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  line-height: 16px;
  animation: ws-sider-label-in 160ms ease 60ms both;
}

.ws-brand__title {
  overflow: hidden;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-brand__subtitle {
  overflow: hidden;
  color: var(--mq-text-tertiary);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-nav {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0 2px;
  /* 矮屏时导航需要滚动，保留细滚动条作为可滚动提示，避免末项被无提示地藏起来 */
  scrollbar-width: thin;
  scrollbar-color: rgba(60, 60, 80, 0.18) transparent;
}

.ws-nav::-webkit-scrollbar {
  width: 4px;
}

.ws-nav::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(60, 60, 80, 0.18);
}

.ws-nav__group-label {
  min-width: 0;
  overflow: hidden;
  padding: 8px 10px 2px;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  font-weight: 400;
  letter-spacing: 0.04em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-nav__group-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  height: 24px;
  margin-top: 8px;
  padding: 0 8px;
  overflow: hidden;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    background-color 140ms ease,
    color 140ms ease;
}

.ws-nav__group-toggle > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-nav__group-toggle:hover {
  background: rgba(255, 255, 255, 0.5);
  color: var(--mq-text-secondary);
}

.ws-nav__group-toggle:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: -2px;
}

.ws-nav__group-chevron {
  flex-shrink: 0;
  color: var(--mq-text-tertiary);
  opacity: 0.7;
  transition:
    transform 180ms ease,
    opacity 140ms ease;
}

.ws-nav__group-toggle:hover .ws-nav__group-chevron {
  opacity: 1;
}

.ws-nav__group-chevron.is-closed {
  transform: rotate(-90deg);
}

.ws-shell--collapsed .ws-nav__group-label {
  height: 0.5px;
  margin: 10px;
  padding: 0;
  background: var(--mq-border-strong);
}

.ws-nav__item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  height: 30px;
  margin: 0;
  padding: 0 8px;
  overflow: hidden;
  border-radius: 10px;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-14);
  text-decoration: none;
  white-space: nowrap;
  transition:
    background-color 140ms ease,
    box-shadow 140ms ease;
}

.ws-shell--collapsed .ws-nav__item {
  justify-content: center;
  height: 40px;
  padding: 0;
}

.ws-nav__item:hover {
  background: rgba(255, 255, 255, 0.5);
  color: var(--mq-text-primary);
}

.ws-nav__item--active,
.ws-nav__item--active:hover {
  background: var(--mq-glass-bg-strong);
  box-shadow: var(--mq-float-shadow);
  color: var(--mq-text-primary);
  font-weight: 600;
}

.ws-nav__item:focus-visible,
.ws-sider__toggle:focus-visible,
.ws-icon-button:focus-visible,
.ws-user:focus-visible,
.ws-section-tabs__item:focus-visible,
.ws-brand:focus-visible {
  outline: 2px solid var(--mq-brand-600);
  outline-offset: 2px;
}

.ws-nav__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  animation: ws-sider-label-in 160ms ease 60ms both;
}

.ws-sider__toggle {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--mq-text-tertiary);
  cursor: pointer;
}

.ws-sider__toggle svg {
  width: 16px;
  height: 16px;
}

.ws-sider__toggle:hover {
  background: rgba(255, 255, 255, 0.6);
  color: var(--mq-text-primary);
}

/* 侧栏底部账号区 */
.ws-sider__footer {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  margin-top: 4px;
  padding: 8px 2px 0;
  border-top: 0.5px solid var(--mq-border);
}

.ws-sider__build {
  display: flex;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  padding-left: 6px;
  animation: ws-sider-label-in 160ms ease 60ms both;
}

.ws-account {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  padding-right: 4px;
}

.ws-shell--collapsed .ws-account {
  flex-direction: column-reverse;
  gap: 8px;
  padding-right: 0;
}

/* 主区 */
.ws-main {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}

.ws-icon-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--mq-text-secondary);
  cursor: pointer;
}

.ws-icon-button__badge {
  position: absolute;
  top: -2px;
  right: -4px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  box-sizing: border-box;
  border: 1.5px solid #ffffff;
  border-radius: 999px;
  background: #ff3b30;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  pointer-events: none;
  box-shadow: 0 2px 6px rgba(255, 59, 48, 0.35);
}

.ws-icon-button:hover {
  background: rgba(255, 255, 255, 0.6);
  color: var(--mq-text-primary);
}

.ws-icon-button svg {
  width: 16px;
  height: 16px;
}

.ws-notice {
  width: 240px;
}

.ws-notice__title {
  margin-bottom: var(--mq-space-2);
  font-size: var(--mq-font-14);
  font-weight: 600;
}

.ws-notice__empty {
  margin: 0;
  padding: var(--mq-space-4) 0;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  text-align: center;
}

.ws-user {
  display: flex;
  flex: 1 1 0;
  align-items: center;
  gap: 10px;
  min-width: 0;
  height: 44px;
  padding: 0 6px;
  overflow: hidden;
  white-space: nowrap;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: var(--mq-text-primary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.ws-user:hover {
  background: rgba(255, 255, 255, 0.6);
}

.ws-shell--collapsed .ws-user {
  flex: 0 0 auto;
  width: 36px;
  justify-content: center;
  padding: 0;
}

.ws-user__avatar {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--mq-brand-50);
  color: var(--mq-brand-700);
  font-size: var(--mq-font-12);
  font-weight: 700;
}

.ws-user__meta {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  line-height: 16px;
  animation: ws-sider-label-in 160ms ease 60ms both;
}

.ws-user__role {
  overflow: hidden;
  max-width: 100%;
  font-size: var(--mq-font-13);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-user__email {
  overflow: hidden;
  max-width: 100%;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-user-menu {
  min-width: 200px;
}

.ws-user-menu__who {
  padding: var(--mq-space-2) var(--mq-space-3);
}

.ws-user-menu__hint {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.ws-user-menu__email {
  overflow: hidden;
  max-width: 220px;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ws-user-menu__icon {
  width: 14px;
  height: 14px;
  margin-right: var(--mq-space-2);
  vertical-align: -2px;
}

.ws-user-menu :deep(.ws-user-menu__logout) {
  color: var(--mq-danger-text);
}

/* DRG/DIP 页内切换：玻璃分段控件 */
.ws-section-tabs {
  display: inline-flex;
  flex-shrink: 0;
  align-self: flex-start;
  gap: 2px;
  margin: 26px 0 0 22px;
  padding: 3px;
  border-radius: 13px;
  background: var(--mq-bg-muted);
}

.ws-section-tabs__item {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 16px;
  border-radius: 10px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
  text-decoration: none;
}

.ws-section-tabs__item:hover {
  color: var(--mq-text-primary);
}

.ws-section-tabs__item--active,
.ws-section-tabs__item--active:hover {
  background: #ffffff;
  box-shadow: 0 2px 6px rgba(10, 55, 115, 0.12);
  color: var(--mq-text-primary);
  font-weight: 600;
}

.ws-content {
  flex: 1 1 auto;
  min-width: 0;
  padding-top: 18px;
  overflow-x: clip;
  background: transparent;
}

/*
 * 过渡期：旧页面根节点自带整页背景，这里统一透明以露出光晕底。
 */
.ws-content :deep(.workstation-route-view),
.ws-content :deep(.workstation-route-view > *),
.ws-content :deep(.record-pool-refined),
.ws-content :deep(.qc-home-shell),
.ws-content :deep(.running-qc-refined) {
  background: transparent !important;
}

@keyframes ws-sider-label-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ws-sider,
  .ws-nav__item {
    transition: none;
  }

  .ws-brand__copy,
  .ws-nav__label,
  .ws-sider__build,
  .ws-user__meta {
    animation: none;
  }
}
/* ---------- 侧栏精修：去图标灰块、淡蓝选中、滚动条与折叠箭头按需出现 ---------- */
.ws-sider {
  border: 0.5px solid rgba(255, 255, 255, 0.9);
  background: rgba(250, 251, 254, 0.72);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 10px 30px rgba(30, 55, 100, 0.08),
    0 1px 2px rgba(30, 55, 100, 0.04);
}

/* 菜单图标：非选中去掉灰色方块，只留线条图标 */
.ws-nav__item .mq-icon-tile {
  background: transparent !important;
  box-shadow: none !important;
  transition: background-color 140ms ease;
}

.ws-nav__item {
  gap: 8px;
  padding: 0 6px;
  border-radius: 8px;
  color: #2b2f38;
}

.ws-nav__item:hover {
  background: rgba(20, 40, 80, 0.05);
  color: var(--mq-text-primary);
}

/* 选中：淡蓝底 + 蓝色图标文字，无投影 */
.ws-nav__item--active,
.ws-nav__item--active:hover {
  background: rgba(10, 108, 255, 0.1);
  box-shadow: none;
  color: #0a58d0;
  font-weight: 500;
}

.ws-shell--collapsed .ws-nav__item--active .mq-icon-tile {
  background: transparent !important;
}

/* 分组折叠箭头：默认隐藏，悬停分组标签或该组已折叠时出现 */
.ws-nav__group-chevron {
  opacity: 0;
}

.ws-nav__group-toggle:hover .ws-nav__group-chevron,
.ws-nav__group-toggle:focus-visible .ws-nav__group-chevron,
.ws-nav__group-chevron.is-closed {
  opacity: 0.8;
}

.ws-nav__group-toggle:hover {
  background: transparent;
  color: var(--mq-text-secondary);
}

/* 滚动条：平时透明，鼠标移入侧栏才显示 */
.ws-nav {
  scrollbar-color: transparent transparent;
}

.ws-sider:hover .ws-nav {
  scrollbar-color: rgba(60, 60, 80, 0.2) transparent;
}

.ws-nav::-webkit-scrollbar-thumb {
  background: transparent;
}

.ws-sider:hover .ws-nav::-webkit-scrollbar-thumb {
  background: rgba(60, 60, 80, 0.2);
}

/* 底部环境标识：去掉胶囊边框，改为一行小字 */
.ws-sider__build :deep(.runtime-build-status) {
  height: auto;
  padding: 0;
  border: 0;
  background: transparent;
  box-shadow: none;
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
}

.ws-sider__footer {
  border-top-color: rgba(20, 40, 80, 0.08);
}
</style>
