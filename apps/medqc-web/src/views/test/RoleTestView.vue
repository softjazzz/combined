<template>
  <div class="p-6 max-w-4xl mx-auto">
    <div class="bg-white rounded-lg shadow-md p-6">
      <h1 class="text-2xl font-bold mb-6">
        用户角色测试页面
      </h1>
      
      <!-- 当前用户信息 -->
      <div class="mb-6 p-4 bg-blue-50 rounded-lg">
        <h2 class="text-lg font-semibold mb-3">
          当前用户信息
        </h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700">用户名</label>
            <p class="mt-1 text-sm text-gray-900">
              {{ authStore.userName }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">邮箱</label>
            <p class="mt-1 text-sm text-gray-900">
              {{ authStore.user?.email }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">部门</label>
            <p class="mt-1 text-sm text-gray-900">
              {{ authStore.userDepartment }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">角色</label>
            <p class="mt-1 text-sm text-gray-900">
              {{ authStore.userRoles?.join(', ') }}
            </p>
          </div>
        </div>
      </div>

      <!-- 角色权限测试 -->
      <div class="mb-6 p-4 bg-green-50 rounded-lg">
        <h2 class="text-lg font-semibold mb-3">
          角色权限测试
        </h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-gray-700">是否为管理员</label>
            <p
              class="mt-1 text-sm"
              :class="authStore.hasRole('admin') ? 'text-green-600' : 'text-red-600'"
            >
              {{ authStore.hasRole('admin') ? '是' : '否' }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">是否为医生</label>
            <p
              class="mt-1 text-sm"
              :class="authStore.hasRole('doctor') ? 'text-green-600' : 'text-red-600'"
            >
              {{ authStore.hasRole('doctor') ? '是' : '否' }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">是否为护士</label>
            <p
              class="mt-1 text-sm"
              :class="authStore.hasRole('nurse') ? 'text-green-600' : 'text-red-600'"
            >
              {{ authStore.hasRole('nurse') ? '是' : '否' }}
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700">是否为质控管理员</label>
            <p
              class="mt-1 text-sm"
              :class="authStore.hasRole('qc_manager') ? 'text-green-600' : 'text-red-600'"
            >
              {{ authStore.hasRole('qc_manager') ? '是' : '否' }}
            </p>
          </div>
        </div>
      </div>

      <!-- 推荐跳转页面 -->
      <div class="mb-6 p-4 bg-yellow-50 rounded-lg">
        <h2 class="text-lg font-semibold mb-3">
          推荐跳转页面
        </h2>
        <div class="text-sm text-gray-700">
          <p v-if="authStore.hasRole('doctor') || authStore.hasRole('nurse')">
            医务人员应该跳转到：<strong>/dashboard/doctor-workstation</strong>
          </p>
          <p v-else-if="authStore.hasRole('qc_manager')">
            质控管理员应该跳转到：<strong>/dashboard/qc</strong>
          </p>
          <p v-else-if="authStore.hasRole('admin')">
            系统管理员应该跳转到：<strong>/dashboard</strong>
          </p>
          <p v-else>
            未知角色，默认跳转到：<strong>/dashboard</strong>
          </p>
        </div>
      </div>

      <!-- 测试按钮 -->
      <div class="flex space-x-4">
        <button 
          class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          @click="testRedirect"
        >
          测试角色跳转
        </button>
        <button 
          class="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          @click="goBack"
        >
          返回
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

const testRedirect = () => {
  const userRoles = authStore.userRoles?.[0]
  
  if (userRoles.includes('doctor') || userRoles.includes('nurse')) {
    router.push('/dashboard/doctor-workstation')
  } else if (userRoles.includes('qc_manager')) {
    router.push('/dashboard/qc')
  } else if (userRoles.includes('admin')) {
    router.push('/dashboard')
  } else {
    router.push('/dashboard')
  }
}

const goBack = () => {
  router.back()
}
</script>
