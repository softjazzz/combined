<template>
  <a-layout style="min-height:100vh;">
    <a-layout-header style="display:flex;align-items:center;gap:16px;color:#fff;">
      <div style="font-weight:600;">医保规则质控</div>
      <a-menu theme="dark" mode="horizontal" :selectedKeys="[selected]" @click="onMenu" style="flex:1;">
        <a-menu-item key="home">首页</a-menu-item>
        <a-menu-item key="rules">规则库</a-menu-item>
        <a-menu-item key="sandbox">沙箱</a-menu-item>
        <a-menu-item key="audit">违规与审计</a-menu-item>
        <a-menu-item key="dashboard">看板</a-menu-item>
      </a-menu>
      <a-button type="link" @click="logout" style="color:#fff;">退出</a-button>
    </a-layout-header>
    <a-layout-content style="padding:16px;">
      <router-view />
    </a-layout-content>
  </a-layout>
  </template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const selected = computed(() => (route.name as string) || 'home')
const auth = useAuthStore()

function onMenu({ key }: any) {
  const mapping: Record<string, string> = {
    home: '/',
    rules: '/rules',
    sandbox: '/sandbox',
    audit: '/audit',
    dashboard: '/dashboard'
  }
  router.push(mapping[key] || '/')
}

async function logout() {
  await auth.signOut()
  router.push({ name: 'login' })
}
</script>



