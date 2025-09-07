<template>
  <a-layout style="min-height: 100vh">
    <a-layout-header style="display:flex;align-items:center;gap:16px;color:#fff">
      <div style="font-weight:600">Yibao QC</div>
      <a-menu mode="horizontal" theme="dark" :selectedKeys="[route.name as string]" style="flex:1">
        <a-menu-item key="home"><router-link to="/">首页</router-link></a-menu-item>
        <a-menu-item key="qc"><router-link to="/qc">质控</router-link></a-menu-item>
        <a-menu-item key="rules"><router-link to="/rules">规则</router-link></a-menu-item>
      </a-menu>
    </a-layout-header>
    <a-layout-content style="padding:16px">
      <router-view />
    </a-layout-content>
  </a-layout>
  </template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>


