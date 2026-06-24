<script setup lang="ts">
import { computed } from 'vue'
import { usePermissions } from '@/composables/usePermissions'

interface Props {
  // 权限资源类型
  resource?: string
  // 权限操作
  action?: string
  // 权限上下文
  context?: Record<string, unknown>
  // 用户角色（可选，用于简单的角色检查）
  roles?: string[]
  // 权限检查模式：'all' 表示需要所有权限，'any' 表示需要任意一个权限
  mode?: 'all' | 'any'
  // 无权限时的显示模式：'hide' 隐藏，'disabled' 禁用，'placeholder' 显示占位符
  fallback?: 'hide' | 'disabled' | 'placeholder'
  // 占位符内容
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'all',
  fallback: 'hide',
  placeholder: '暂无权限访问此内容'
})

const { hasPermission, checkPermission, hasRole, hasAnyRole, ResourceType, PermissionAction } = usePermissions()

// 权限检查结果
const permissionResult = computed(() => {
  // 如果指定了角色，进行角色检查
  if (props.roles && props.roles.length > 0) {
    const roleEnums = props.roles.map(role => role as any)
    return hasAnyRole(roleEnums) ? { allowed: true } : { allowed: false, reason: '用户角色不足' }
  }
  
  // 如果指定了资源和操作，进行权限检查
  if (props.resource && props.action) {
    const resource = props.resource as any
    const action = props.action as any
    return checkPermission(resource, action, props.context)
  }
  
  // 默认允许
  return { allowed: true }
})

// 是否显示内容
const shouldShow = computed(() => {
  return permissionResult.value.allowed
})

// 是否禁用
const isDisabled = computed(() => {
  return !permissionResult.value.allowed && props.fallback === 'disabled'
})

// 是否显示占位符
const showPlaceholder = computed(() => {
  return !permissionResult.value.allowed && props.fallback === 'placeholder'
})
</script>

<template>
  <div
    v-if="shouldShow || showPlaceholder"
    class="permission-guard"
  >
    <!-- 有权限时显示正常内容 -->
    <div
      v-if="shouldShow"
      :class="{ 'permission-disabled': isDisabled }"
    >
      <slot />
    </div>
    
    <!-- 无权限时显示占位符 -->
    <div
      v-else-if="showPlaceholder"
      class="permission-placeholder"
    >
      <div class="permission-placeholder-content">
        <div class="permission-placeholder-icon">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M12 15v2" />
            <path d="M12 7v2" />
            <circle
              cx="12"
              cy="12"
              r="10"
            />
          </svg>
        </div>
        <p class="permission-placeholder-text">
          {{ placeholder }}
        </p>
        <p
          v-if="permissionResult.reason"
          class="permission-placeholder-reason"
        >
          {{ permissionResult.reason }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.permission-guard {
  position: relative;
}

.permission-disabled {
  opacity: 0.5;
  pointer-events: none;
  cursor: not-allowed;
}

.permission-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  padding: 2rem;
  background-color: #fafafa;
  border: 1px dashed #d9d9d9;
  border-radius: 8px;
  color: #999;
}

.permission-placeholder-content {
  text-align: center;
}

.permission-placeholder-icon {
  margin-bottom: 1rem;
  opacity: 0.6;
}

.permission-placeholder-text {
  margin: 0 0 0.5rem 0;
  font-size: 14px;
  font-weight: 500;
}

.permission-placeholder-reason {
  margin: 0;
  font-size: 12px;
  color: #bbb;
}
</style> 