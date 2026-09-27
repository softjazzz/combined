<template>
  <div
    class="ws-shell"
    :class="{ 'ws-shell--collapsed': collapsed }"
  >
    <!-- 侧栏：分组标题 + 平铺入口（配置见 workstationNav.ts） -->
    <aside class="ws-sider">
      <RouterLink
        :to="WORKSTATION_BASE"
        class="ws-brand"
        aria-label="病案质控系统首页"
      >
        <span
          class="ws-brand__mark"
          aria-hidden="true"
        >
          <MqIcon
            name="rules"
            color="#FFFFFF"
            :size="18"
          />
        </span>
        <span
          v-if="!collapsed"
          class="ws-brand__copy"
        >
          <span class="ws-brand__title">病案质控系统</span>
          <span class="ws-brand__subtitle">Medical Record QC</span>
        </span>
      </RouterLink>

      <nav
        class="ws-nav"
        aria-label="主导航"
      >
        <section
          v-for="group in visibleNav"
          :key="group.key"
          class="ws-nav__group"
        >
          <div
            v-if="group.label"
            class="ws-nav__group-label"
            :aria-hidden="collapsed ? 'true' : undefined"
          >
            {{ collapsed ? '' : group.label }}
          </div>
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
              <span
                v-if="!collapsed"
                class="ws-nav__label"
              >{{ item.label }}</span>
            </RouterLink>
          </a-tooltip>
        </section>
      </nav>

      <button
        type="button"
        class="ws-sider__toggle"
        :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
        :aria-expanded="!collapsed"
        @click="toggleCollapsed"
      >
        <PanelLeftOpen
          v-if="collapsed"
          aria-hidden="true"
        />
        <PanelLeftClose
          v-else
          aria-hidden="true"
        />
        <span v-if="!collapsed">收起</span>
      </button>
    </aside>

    <div class="ws-main">
      <header class="ws-header">
        <nav
          class="ws-breadcrumb"
          aria-label="面包屑"
        >
          <ol>
            <li
              v-for="(crumb, index) in breadcrumb"
              :key="`${index}-${crumb}`"
              :aria-current="index === breadcrumb.length - 1 ? 'page' : undefined"
            >
              {{ crumb }}
            </li>
          </ol>
        </nav>

        <div class="ws-header__actions">
          <RuntimeBuildStatus />

          <a-popover
            placement="bottomRight"
            trigger="click"
          >
            <template #content>
              <div class="ws-notice">
                <div class="ws-notice__title">
                  通知
                </div>
                <p class="ws-notice__empty">
                  暂无通知
                </p>
              </div>
            </template>
            <button
              type="button"
              class="ws-icon-button"
              aria-label="通知"
            >
              <Bell aria-hidden="true" />
            </button>
          </a-popover>

          <a-dropdown :trigger="['click']">
            <button
              type="button"
              class="ws-user"
              aria-label="账号菜单"
            >
              <span
                class="ws-user__avatar"
                aria-hidden="true"
              >{{ roleLabel.slice(0, 1) }}</span>
              <span class="ws-user__meta">
                <span class="ws-user__role">{{ roleLabel }}</span>
                <span class="ws-user__email">{{ authStore.user?.email || '' }}</span>
              </span>
              <ChevronDown
                class="ws-user__caret"
                aria-hidden="true"
              />
            </button>
            <template #overlay>
              <a-menu class="ws-user-menu">
                <div class="ws-user-menu__who">
                  <div class="ws-user-menu__hint">
                    当前账号
                  </div>
                  <div class="ws-user-menu__email">
                    {{ authStore.user?.email || '未登录' }}
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
                <a-menu-item
                  key="logout"
                  class="ws-user-menu__logout"
                  @click="handleLogout"
                >
                  <LogOut class="ws-user-menu__icon" />
                  退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
      </header>

      <!-- DRG/DIP 分析：一个导航入口，子页在此切换，地址不变 -->
      <nav
        v-if="drgActiveTab"
        class="ws-section-tabs"
        aria-label="DRG/DIP 分析"
      >
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
        <router-view v-slot="{ Component }">
          <transition
            name="fade"
            mode="out-in"
          >
            <div
              :key="route.fullPath"
              class="workstation-route-view"
            >
              <component
                :is="Component"
                v-if="Component"
              />
            </div>
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
import MqIconTile from '@/components/icons/MqIconTile.vue'
import { useAuthStore } from '@/stores/auth'
import {
  DRG_SECTION_TABS,
  WORKSTATION_BASE,
  WORKSTATION_NAV,
  filterVisibleNav,
  findActiveNav,
  findDrgSectionTab,
  resolveBreadcrumb,
  type NavLocation,
  type NavRouteLike,
} from './workstationNav'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

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
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  collapseMedia = window.matchMedia(COLLAPSE_QUERY)
  syncCollapsedWithViewport(collapseMedia)
  collapseMedia.addEventListener('change', syncCollapsedWithViewport)
})

onBeforeUnmount(() => {
  collapseMedia?.removeEventListener('change', syncCollapsedWithViewport)
})

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

const activeKey = computed(() => findActiveNav(WORKSTATION_NAV, navRoute.value)?.item.key ?? '')
const breadcrumb = computed(() => resolveBreadcrumb(WORKSTATION_NAV, navRoute.value))
const drgActiveTab = computed(() => findDrgSectionTab(navRoute.value))

const handleLogout = async () => {
  await authStore.signOut()
  router.push('/workstation-v5/login')
}
</script>

<style scoped>
@import '../../styles/source-han-sans-sc.css';

/* v7.1 液态玻璃外壳：光晕底 + 悬浮玻璃侧栏 + 半透明顶栏 */
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

.ws-brand {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
  padding: 0 8px 14px;
  color: var(--mq-text-primary);
  text-decoration: none;
}

.ws-shell--collapsed .ws-brand {
  justify-content: center;
  padding-inline: 0;
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
  flex-direction: column;
  line-height: 16px;
}

.ws-brand__title {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.01em;
  white-space: nowrap;
}

.ws-brand__subtitle {
  color: var(--mq-text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}

.ws-nav {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  padding: 0 2px;
  scrollbar-width: none;
}

.ws-nav::-webkit-scrollbar {
  display: none;
}

.ws-nav__group-label {
  padding: 10px 10px 3px;
  color: var(--mq-text-tertiary);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
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
  height: 32px;
  margin: 0;
  padding: 0 8px;
  border-radius: 10px;
  color: var(--mq-text-primary);
  font-size: var(--mq-font-13);
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
  overflow: hidden;
  text-overflow: ellipsis;
}

.ws-sider__toggle {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  gap: var(--mq-space-2);
  height: 36px;
  margin-top: 6px;
  border: 0;
  border-top: 0.5px solid var(--mq-border);
  background: transparent;
  color: var(--mq-text-secondary);
  font: inherit;
  font-size: var(--mq-font-13);
  cursor: pointer;
}

.ws-sider__toggle svg {
  width: 16px;
  height: 16px;
}

.ws-sider__toggle:hover {
  color: var(--mq-text-primary);
}

/* 主区 */
.ws-main {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
}

.ws-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--mq-space-4);
  height: var(--mq-header-height);
  padding: 0 28px 0 24px;
  background: rgba(241, 243, 248, 0.55);
  -webkit-backdrop-filter: var(--mq-glass-blur);
  backdrop-filter: var(--mq-glass-blur);
}

.ws-breadcrumb ol {
  display: flex;
  align-items: center;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: var(--mq-font-13);
  white-space: nowrap;
}

.ws-breadcrumb li {
  color: var(--mq-text-tertiary);
}

.ws-breadcrumb li + li::before {
  content: '/';
  margin: 0 var(--mq-space-2);
  color: var(--mq-text-disabled);
}

.ws-breadcrumb li[aria-current='page'] {
  color: var(--mq-text-primary);
  font-weight: 600;
}

.ws-header__actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: var(--mq-space-3);
}

.ws-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--mq-glass-border);
  border-radius: 50%;
  background: var(--mq-bg-subtle);
  box-shadow: var(--mq-shadow-sm);
  color: var(--mq-text-secondary);
  cursor: pointer;
}

.ws-icon-button:hover {
  color: var(--mq-text-primary);
}

.ws-icon-button svg {
  width: 17px;
  height: 17px;
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
  align-items: center;
  gap: var(--mq-space-2);
  height: 40px;
  padding: 0 12px 0 4px;
  border: 1px solid var(--mq-glass-border);
  border-radius: 999px;
  background: var(--mq-bg-subtle);
  box-shadow: var(--mq-shadow-sm);
  color: var(--mq-text-primary);
  font: inherit;
  cursor: pointer;
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
  flex-direction: column;
  align-items: flex-start;
  line-height: 16px;
}

.ws-user__role {
  font-size: var(--mq-font-13);
  font-weight: 600;
  white-space: nowrap;
}

.ws-user__email {
  color: var(--mq-text-tertiary);
  font-size: var(--mq-font-12);
  white-space: nowrap;
}

.ws-user__caret {
  width: 14px;
  height: 14px;
  color: var(--mq-text-tertiary);
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
  margin: 4px 0 0 24px;
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
  overflow-x: hidden;
  background: transparent;
}

/*
 * 过渡期：旧页面根节点自带整页背景，这里统一透明以露出光晕底。
 * 质控结果列表（running-qc-refined）尚未迁移，保留原渐变画布。
 */
.ws-content :deep(.workstation-route-view),
.ws-content :deep(.workstation-route-view > *),
.ws-content :deep(.record-pool-refined),
.ws-content :deep(.qc-home-shell) {
  background: transparent !important;
}

.ws-content :deep(.running-qc-refined) {
  background: linear-gradient(125deg, #dce8f6 0%, #f1f3f7 48%, #e4eaf3 100%) !important;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 150ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .ws-sider,
  .ws-nav__item,
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
