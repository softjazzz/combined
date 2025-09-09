<template>
  <a-layout class="min-h-screen bg-gray-50">
    <!-- 左侧菜单（移植自 medqc 风格） -->
    <a-layout-sider
      v-model:collapsed="collapsed"
      collapsible
      class="sidebar-container shadow-2xl border-r border-blue-200/50 relative overflow-hidden"
      :style="{ background: 'linear-gradient(180deg, #3b82f6 0%, #1e40af 50%, #1d4ed8 100%)' }"
      width="260"
    >
      <!-- Logo 区域 -->
      <div class="logo-container relative p-6 text-center border-b border-white/20 backdrop-blur-sm">
        <div class="relative flex items-center justify-center">
          <div class="w-10 h-10 bg-gradient-to-br from-white/25 to-white/10 rounded-xl flex items-center justify-center shadow-lg backdrop-blur-sm border border-white/20">
            <MedicineBoxOutlined class="text-xl text-white drop-shadow-sm" />
          </div>
          <div v-if="!collapsed" class="text-left ml-3">
            <div class="text-white font-bold text-lg leading-tight drop-shadow-sm">医保规则质控</div>
            <div class="text-blue-100 text-xs mt-1 font-medium">AI-Powered QC</div>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <a-menu
        v-model:selectedKeys="selectedKeys"
        mode="inline"
        theme="dark"
        class="bg-transparent border-0 px-4 py-6 menu-container"
        style="background: transparent !important;"
        @select="handleMenuSelect"
      >
        <a-menu-item key="/dashboard" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-9 h-9 bg-gradient-to-br from-white/20 to-white/10 rounded-lg flex items-center justify-center shadow border border-white/20">
              <BarChartOutlined class="text-white text-base drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-2 drop-shadow-sm">仪表板</span>
        </a-menu-item>

        <a-menu-item key="/rules" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-9 h-9 bg-gradient-to-br from-white/20 to-white/10 rounded-lg flex items-center justify-center shadow border border-white/20">
              <FileTextOutlined class="text-white text-base drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-2 drop-shadow-sm">规则库</span>
        </a-menu-item>

        <a-menu-item key="/reminder-demo" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-9 h-9 bg-gradient-to-br from-white/20 to-white/10 rounded-lg flex items-center justify-center shadow border border-white/20">
              <SafetyCertificateOutlined class="text-white text-base drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-2 drop-shadow-sm">医生端提醒 Demo</span>
        </a-menu-item>

        <a-menu-item key="/audit" class="menu-item menu-item-primary mb-3 mx-2">
          <template #icon>
            <div class="w-9 h-9 bg-gradient-to-br from-white/20 to-white/10 rounded-lg flex items-center justify-center shadow border border-white/20">
              <SafetyCertificateOutlined class="text-white text-base drop-shadow-sm" />
            </div>
          </template>
          <span class="text-white font-semibold ml-2 drop-shadow-sm">违规与审计</span>
        </a-menu-item>
      </a-menu>

      <!-- 侧边栏底部 -->
      <div class="px-4 pb-6">
        <a-button block class="mt-2" @click="logout">退出登录</a-button>
      </div>
    </a-layout-sider>

    <!-- 主内容区域，无顶部黑条 -->
    <a-layout>
      <a-layout-content class="bg-gray-50 p-8">
        <div class="bg-white rounded-xl shadow-sm min-h-full border border-gray-100">
          <slot />
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
  </template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { BarChartOutlined, FileTextOutlined, SafetyCertificateOutlined, MedicineBoxOutlined } from '@ant-design/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapsed = ref(false)
const selectedKeys = ref<string[]>([])

function handleMenuSelect({ key }: { key: string }) {
  router.push(key)
}

async function logout() {
  try { await auth.signOut() } catch {}
  router.push({ name: 'login' })
}

watch(
  () => route.path,
  (newPath) => { selectedKeys.value = [newPath] },
  { immediate: true }
)
</script>

<style scoped>
.sidebar-container { position: relative; overflow: hidden; }
.menu-container { position: relative; z-index: 10; }
.menu-item-primary { margin: 8px 0; border-radius: 12px; transition: all .3s ease; }
.menu-item-primary:hover { background: rgba(255,255,255,.15) !important; transform: translateX(4px) scale(1.02); }
::deep(.ant-menu-dark) { background: transparent !important; }
::deep(.ant-menu-dark .ant-menu-item-selected) { background: rgba(255,255,255,.25) !important; color: #fff; }
</style>



