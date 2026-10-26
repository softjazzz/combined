<template>
  <main class="mq-page" aria-labelledby="user-management-title">
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">数据与配置 · 用户管理</span>
        <h1 id="user-management-title" class="mq-page-title">用户管理</h1>
        <p class="mq-page-desc">查看用户、维护授权范围，并处理注册申请。</p>
      </div>
    </header>
    <section class="mq-card mq-card--padded">
      <AccountManagementPanel />
    </section>
  </main>
</template>

<script setup lang="ts">
import AccountManagementPanel from '@/views/workstation-v4/components/system-config/AccountManagementPanel.vue'
</script>
