<template>
  <div class="empty-state" :class="containerClass">
    <div class="empty-content">
      <!-- 图标/图片 -->
      <div class="empty-icon" :class="iconClass">
        <component 
          v-if="icon" 
          :is="icon" 
          class="icon-component"
          :style="{ color: iconColor }"
        />
        <div v-else-if="image" class="empty-image">
          <img :src="image" :alt="title" />
        </div>
        <div v-else class="default-icon">
          <component 
            :is="getDefaultIcon()" 
            class="icon-component"
            :style="{ color: iconColor }"
          />
        </div>
      </div>
      
      <!-- 标题 -->
      <h3 class="empty-title">{{ title }}</h3>
      
      <!-- 描述 -->
      <p v-if="description" class="empty-description">{{ description }}</p>
      
      <!-- 操作按钮 -->
      <div v-if="actions.length > 0 || $slots.actions" class="empty-actions">
        <slot name="actions">
          <a-space :size="12">
            <a-button
              v-for="action in actions"
              :key="action.key"
              :type="action.type || 'primary'"
              :size="action.size || 'large'"
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
      
      <!-- 额外内容 -->
      <div v-if="$slots.extra" class="empty-extra">
        <slot name="extra" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, computed } from 'vue'
import {
  InboxOutlined,
  ExclamationCircleOutlined,
  DisconnectOutlined,
  SearchOutlined,
  FileTextOutlined,
  UserOutlined,
  SettingOutlined,
  CloudServerOutlined
} from '@ant-design/icons-vue'

interface ActionItem {
  key: string
  text: string
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link'
  size?: 'small' | 'middle' | 'large'
  icon?: Record<string, unknown>
  loading?: boolean
  disabled?: boolean
  onClick?: () => void
}

interface Props {
  type?: 'empty' | 'error' | 'network' | 'search' | 'permission' | 'maintenance' | 'custom'
  title?: string
  description?: string
  icon?: Record<string, unknown>
  image?: string
  iconColor?: string
  size?: 'small' | 'medium' | 'large'
  actions?: ActionItem[]
}

interface Emits {
  (e: 'action', action: ActionItem): void
}

const props = withDefaults(defineProps<Props>(), {
  type: 'empty',
  title: '',
  description: '',
  iconColor: '#d9d9d9',
  size: 'medium',
  actions: () => []
})

const emit = defineEmits<Emits>()

// 默认配置
const defaultConfig = {
  empty: {
    title: '暂无数据',
    description: '当前没有可显示的内容',
    icon: InboxOutlined
  },
  error: {
    title: '加载失败',
    description: '数据加载过程中发生错误，请稍后重试',
    icon: ExclamationCircleOutlined,
    iconColor: '#ff4d4f'
  },
  network: {
    title: '网络连接失败',
    description: '请检查网络连接后重试',
    icon: DisconnectOutlined,
    iconColor: '#faad14'
  },
  search: {
    title: '无搜索结果',
    description: '未找到符合条件的内容，请尝试其他关键词',
    icon: SearchOutlined
  },
  permission: {
    title: '无访问权限',
    description: '您没有权限查看此内容，请联系管理员',
    icon: UserOutlined,
    iconColor: '#faad14'
  },
  maintenance: {
    title: '系统维护中',
    description: '系统正在维护，请稍后再试',
    icon: SettingOutlined,
    iconColor: '#1890ff'
  },
  custom: {
    title: '自定义状态',
    description: '',
    icon: CloudServerOutlined
  }
}

// 计算样式类
const containerClass = computed(() => [
  'empty-state-container',
  `empty-state-${props.size}`,
  `empty-state-${props.type}`
])

const iconClass = computed(() => [
  'empty-icon-wrapper',
  `empty-icon-${props.size}`,
  `empty-icon-${props.type}`
])

// 获取配置
const config = computed(() => defaultConfig[props.type])

// 获取标题
const title = computed(() => props.title || config.value.title)

// 获取描述
const description = computed(() => props.description || config.value.description)

// 获取图标颜色
const iconColor = computed(() => {
  const configValue = config.value as any
  return props.iconColor || configValue.iconColor || '#d9d9d9'
})

// 获取默认图标
const getDefaultIcon = () => {
  return props.icon || config.value.icon || InboxOutlined
}

// 处理操作按钮点击
const handleAction = (action: ActionItem) => {
  if (action.onClick) {
    action.onClick()
  }
  emit('action', action)
}
</script>

<style scoped>
.empty-state-container {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 40px 20px;
  min-height: 200px;
}

.empty-content {
  max-width: 400px;
  width: 100%;
}

/* 尺寸变量 */
.empty-state-small {
  --icon-size: 64px;
  --title-size: 16px;
  --description-size: 14px;
  --spacing: 16px;
  min-height: 160px;
}

.empty-state-medium {
  --icon-size: 80px;
  --title-size: 18px;
  --description-size: 16px;
  --spacing: 20px;
  min-height: 200px;
}

.empty-state-large {
  --icon-size: 100px;
  --title-size: 20px;
  --description-size: 18px;
  --spacing: 24px;
  min-height: 240px;
}

/* 图标区域 */
.empty-icon-wrapper {
  margin-bottom: var(--spacing);
  display: flex;
  justify-content: center;
  align-items: center;
}

.icon-component {
  font-size: var(--icon-size);
  transition: all 0.3s ease;
}

.empty-image {
  width: var(--icon-size);
  height: var(--icon-size);
  margin: 0 auto;
}

.empty-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.default-icon {
  width: var(--icon-size);
  height: var(--icon-size);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

/* 标题 */
.empty-title {
  font-size: var(--title-size);
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
  line-height: 1.4;
}

/* 描述 */
.empty-description {
  font-size: var(--description-size);
  color: #6b7280;
  margin: 0 0 var(--spacing) 0;
  line-height: 1.6;
}

/* 操作按钮 */
.empty-actions {
  margin-bottom: var(--spacing);
}

/* 额外内容 */
.empty-extra {
  margin-top: var(--spacing);
}

/* 类型特定样式 */
.empty-state-error .icon-component {
  animation: shake 0.5s ease-in-out;
}

.empty-state-network .icon-component {
  animation: pulse 2s ease-in-out infinite;
}

.empty-state-maintenance .icon-component {
  animation: spin 3s linear infinite;
}

/* 动画效果 */
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 悬停效果 */
.empty-state-container:hover .icon-component {
  transform: scale(1.05);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .empty-state-container {
    padding: 24px 16px;
  }
  
  .empty-content {
    max-width: 300px;
  }
  
  .empty-state-large {
    --icon-size: 80px;
    --title-size: 18px;
    --description-size: 16px;
    --spacing: 20px;
    min-height: 200px;
  }
  
  .empty-state-medium {
    --icon-size: 64px;
    --title-size: 16px;
    --description-size: 14px;
    --spacing: 16px;
    min-height: 160px;
  }
}

/* 主题适配 */
.empty-state-container {
  transition: all 0.3s ease;
}

@media (prefers-color-scheme: dark) {
  .empty-title {
    color: #f9fafb;
  }
  
  .empty-description {
    color: #d1d5db;
  }
}

/* 加载状态 */
.empty-state-loading .icon-component {
  animation: spin 1s linear infinite;
}

/* 交互状态 */
.empty-state-interactive {
  cursor: pointer;
  transition: all 0.2s ease;
}

.empty-state-interactive:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style> 