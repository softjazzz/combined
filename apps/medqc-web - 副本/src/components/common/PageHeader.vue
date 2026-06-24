<template>
  <div
    class="page-header"
    :class="headerClass"
  >
    <!-- 主要头部区域 -->
    <div class="header-main">
      <!-- 左侧内容 -->
      <div class="header-left">
        <!-- 返回按钮 -->
        <a-button
          v-if="showBack"
          type="text"
          :icon="h(ArrowLeftOutlined)"
          class="back-button"
          @click="handleBack"
        >
          {{ backText }}
        </a-button>
        
        <!-- 标题区域 -->
        <div class="title-section">
          <h1 class="page-title">
            <component
              :is="icon"
              v-if="icon"
              class="title-icon"
            />
            {{ title }}
          </h1>
          <p
            v-if="subtitle"
            class="page-subtitle"
          >
            {{ subtitle }}
          </p>
        </div>
      </div>
      
      <!-- 右侧操作区域 -->
      <div class="header-right">
        <slot name="actions">
          <a-space :size="12">
            <a-button
              v-for="action in actions"
              :key="action.key"
              :type="action.type || 'default'"
              :icon="action.icon ? h(action.icon) : undefined"
              :loading="action.loading"
              :disabled="action.disabled"
              @click="handleAction(action)"
            >
              {{ action.text }}
            </a-button>
          </a-space>
        </slot>
      </div>
    </div>
    
    <!-- 面包屑导航 -->
    <div
      v-if="showBreadcrumb && breadcrumbs.length > 0"
      class="breadcrumb-section"
    >
      <a-breadcrumb>
        <a-breadcrumb-item
          v-for="item in breadcrumbs"
          :key="item.path"
        >
          <component
            :is="item.icon"
            v-if="item.icon"
            class="breadcrumb-icon"
          />
          <router-link
            v-if="item.path && !item.disabled"
            :to="item.path"
          >
            {{ item.name }}
          </router-link>
          <span v-else>{{ item.name }}</span>
        </a-breadcrumb-item>
      </a-breadcrumb>
    </div>
    
    <!-- 标签页 -->
    <div
      v-if="tabs.length > 0"
      class="tabs-section"
    >
      <a-tabs
        v-model:active-key="activeTab"
        @change="handleTabChange"
      >
        <a-tab-pane
          v-for="tab in tabs"
          :key="tab.key"
          :tab="tab.label"
          :disabled="tab.disabled"
        >
          <template #tab>
            <component
              :is="tab.icon"
              v-if="tab.icon"
              class="tab-icon"
            />
            {{ tab.label }}
            <a-badge
              v-if="tab.badge"
              :count="tab.badge"
              class="tab-badge"
            />
          </template>
        </a-tab-pane>
      </a-tabs>
    </div>
    
    <!-- 统计信息 -->
    <div
      v-if="stats.length > 0"
      class="stats-section"
    >
      <a-row :gutter="[16, 16]">
        <a-col
          v-for="stat in stats"
          :key="stat.key"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
        >
          <div class="stat-item">
            <div
              class="stat-icon"
              :style="{ color: stat.color }"
            >
              <component
                :is="stat.icon"
                v-if="stat.icon"
              />
            </div>
            <div class="stat-content">
              <div class="stat-value">
                {{ stat.value }}
              </div>
              <div class="stat-label">
                {{ stat.label }}
              </div>
            </div>
          </div>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, computed, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeftOutlined } from '@ant-design/icons-vue'

interface BreadcrumbItem {
  name: string
  path?: string
  icon?: Component
  disabled?: boolean
}

interface ActionItem {
  key: string
  text: string
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link'
  icon?: Component
  loading?: boolean
  disabled?: boolean
  onClick?: () => void
}

interface TabItem {
  key: string
  label: string
  icon?: Component
  badge?: number
  disabled?: boolean
}

interface StatItem {
  key: string
  label: string
  value: string | number
  icon?: Component
  color?: string
}

interface Props {
  title: string
  subtitle?: string
  icon?: Component
  showBack?: boolean
  backText?: string
  showBreadcrumb?: boolean
  breadcrumbs?: BreadcrumbItem[]
  actions?: ActionItem[]
  tabs?: TabItem[]
  stats?: StatItem[]
  size?: 'small' | 'medium' | 'large'
  ghost?: boolean
}

interface Emits {
  (e: 'back'): void
  (e: 'action', action: ActionItem): void
  (e: 'tab-change', key: string): void
}

const props = withDefaults(defineProps<Props>(), { backText: '返回',
  showBack: false,
  showBreadcrumb: true,
  breadcrumbs: () => [],
  actions: () => [],
  tabs: () => [],
  stats: () => [],
  size: 'medium',
  ghost: false
})

const emit = defineEmits<Emits>()

const router = useRouter()

// 当前激活的标签页
const activeTab = computed({
  get: () => props.tabs.find(tab => !tab.disabled)?.key || '',
  set: (value: string) => {
    emit('tab-change', value)
  }
})

// 头部样式类
const headerClass = computed(() => [
  'page-header-container',
  `page-header-${props.size}`,
  {
    'page-header-ghost': props.ghost
  }
])

// 处理返回操作
const handleBack = () => {
  emit('back')
  // 默认返回上一页
  router.back()
}

// 处理操作按钮点击
const handleAction = (action: ActionItem) => {
  if (action.onClick) {
    action.onClick()
  }
  emit('action', action)
}

// 处理标签页切换
const handleTabChange = (key: string) => {
  emit('tab-change', key)
}
</script>

<style scoped>
.page-header-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 24px;
  transition: all 0.3s ease;
}

.page-header-ghost {
  background: transparent;
  box-shadow: none;
}

/* 尺寸变量 */
.page-header-small {
  --header-padding: 16px;
  --title-size: 20px;
  --subtitle-size: 14px;
}

.page-header-medium {
  --header-padding: 24px;
  --title-size: 24px;
  --subtitle-size: 16px;
}

.page-header-large {
  --header-padding: 32px;
  --title-size: 28px;
  --subtitle-size: 18px;
}

/* 主要头部区域 */
.header-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--header-padding);
  gap: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 返回按钮 */
.back-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.back-button:hover {
  background-color: #f5f5f5;
}

/* 标题区域 */
.title-section {
  flex: 1;
}

.page-title {
  font-size: var(--title-size);
  font-weight: 600;
  color: #1f2937;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  line-height: 1.2;
}

.title-icon {
  font-size: 1.2em;
  color: #1890ff;
}

.page-subtitle {
  font-size: var(--subtitle-size);
  color: #6b7280;
  margin: 8px 0 0 0;
  line-height: 1.4;
}

/* 面包屑导航 */
.breadcrumb-section {
  padding: 0 var(--header-padding) 16px;
  border-bottom: 1px solid #f0f0f0;
}

.breadcrumb-icon {
  margin-right: 4px;
  font-size: 14px;
}

:deep(.ant-breadcrumb) {
  font-size: 14px;
}

:deep(.ant-breadcrumb-link) {
  color: #6b7280;
  transition: color 0.2s ease;
}

:deep(.ant-breadcrumb-link:hover) {
  color: #1890ff;
}

/* 标签页 */
.tabs-section {
  padding: 0 var(--header-padding);
}

.tab-icon {
  margin-right: 6px;
  font-size: 14px;
}

.tab-badge {
  margin-left: 6px;
}

:deep(.ant-tabs-nav) {
  margin-bottom: 0;
}

:deep(.ant-tabs-tab) {
  padding: 12px 16px;
  font-weight: 500;
}

/* 统计信息 */
.stats-section {
  padding: 16px var(--header-padding) var(--header-padding);
  border-top: 1px solid #f0f0f0;
  background: #fafafa;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 0.2s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-icon {
  font-size: 24px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(24, 144, 255, 0.1);
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-content {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .header-main {
    flex-direction: column;
    gap: 16px;
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .header-right {
    width: 100%;
    justify-content: flex-end;
  }
  
  .page-title {
    font-size: 20px;
  }
  
  .page-subtitle {
    font-size: 14px;
  }
  
  .stats-section {
    padding: 12px var(--header-padding);
  }
  
  .stat-item {
    padding: 12px;
  }
  
  .stat-icon {
    width: 36px;
    height: 36px;
    font-size: 18px;
  }
  
  .stat-value {
    font-size: 18px;
  }
}

/* 动画效果 */
.page-header-container {
  animation: fadeInUp 0.4s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style> 
