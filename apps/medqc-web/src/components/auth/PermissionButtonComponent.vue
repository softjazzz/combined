<script setup lang="ts">
import { computed } from 'vue'
import { Button } from 'ant-design-vue'
// import { usePermissions } from '@/composables/usePermissions'

// 临时权限检查函数
const checkPermission = (resource: string, action: string, context?: any) => {
  // 临时实现，始终返回允许
  return { allowed: true, reason: '' }
}

interface Props {
  // 权限资源类型
  resource?: string
  // 权限操作
  action?: string
  // 权限上下文
  context?: Record<string, any>
  // 用户角色（可选，用于简单的角色检查）
  roles?: string[]
  // 按钮类型
  type?: 'primary' | 'default' | 'dashed' | 'text' | 'link'
  // 按钮大小
  size?: 'large' | 'middle' | 'small'
  // 按钮形状
  shape?: 'default' | 'circle' | 'round'
  // 是否危险按钮
  danger?: boolean
  // 是否幽灵按钮
  ghost?: boolean
  // 是否块级按钮
  block?: boolean
  // 是否禁用
  disabled?: boolean
  // 是否加载中
  loading?: boolean
  // 无权限时的提示文本
  noPermissionText?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'default',
  size: 'middle',
  shape: 'default',
  danger: false,
  ghost: false,
  block: false,
  disabled: false,
  loading: false,
  noPermissionText: '暂无权限'
})

// const { checkPermission, hasAnyRole } = usePermissions()

// 权限检查结果
const permissionResult = computed(() => {
  // 如果指定了角色，进行角色检查
  if (props.roles && props.roles.length > 0) {
    // const roleEnums = props.roles.map(role => role as any)
    // return hasAnyRole(roleEnums) ? { allowed: true } : { allowed: false, reason: '用户角色不足' }
    return { allowed: true, reason: '' } // 临时允许
  }
  
  // 如果指定了资源和操作，进行权限检查
  if (props.resource && props.action) {
    return checkPermission(props.resource, props.action, props.context)
  }
  
  // 默认允许
  return { allowed: true }
})

// 是否显示按钮
const shouldShow = computed(() => {
  return permissionResult.value.allowed
})

// 按钮是否禁用
const isDisabled = computed(() => {
  return props.disabled || !permissionResult.value.allowed
})

// 按钮提示文本
const buttonTitle = computed(() => {
  if (!permissionResult.value.allowed) {
    return permissionResult.value.reason || props.noPermissionText
  }
  return undefined
})

// 按钮点击事件
const emit = defineEmits<{
  click: [event: any]
}>()

const handleClick = (event) => {
  if (permissionResult.value.allowed) {
    emit('click', event)
  }
}
</script>

<template>
  <a-button
    v-if="shouldShow"
    :type="type"
    :size="size"
    :shape="shape"
    :danger="danger"
    :ghost="ghost"
    :block="block"
    :disabled="isDisabled"
    :loading="loading"
    :title="buttonTitle"
    @click="handleClick"
  >
    <slot />
  </a-button>
</template>

<style scoped>
/* 可以添加自定义样式 */
</style> 