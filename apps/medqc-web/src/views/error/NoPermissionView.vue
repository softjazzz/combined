<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// 所有登录用户均可访问的兜底页：守卫找不到任何可访问的角色默认页时落到这里，避免循环重定向
const router = useRouter()
const authStore = useAuthStore()

const handleLogout = async () => {
  await authStore.signOut()
  await router.push('/auth/login')
}
</script>

<template>
  <div class="no-permission-page">
    <a-result
      status="403"
      title="无权访问"
      sub-title="当前账号无可访问页面，请联系管理员"
    >
      <template #extra>
        <a-button
          type="primary"
          class="no-permission-logout"
          @click="handleLogout"
        >
          退出登录
        </a-button>
      </template>
    </a-result>
  </div>
</template>

<style scoped>
.no-permission-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}
</style>
