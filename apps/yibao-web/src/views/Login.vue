<template>
  <div style="max-width:360px;margin:80px auto;padding:24px;border:1px solid #eee;border-radius:8px;background:#fff;">
    <h2 style="margin-bottom:16px;">医保规则质控 - 登录</h2>
    <a-form layout="vertical" @submit.prevent="onSubmit">
      <a-form-item label="邮箱">
        <a-input v-model:value="email" placeholder="请输入邮箱" />
      </a-form-item>
      <a-form-item label="密码">
        <a-input-password v-model:value="password" placeholder="请输入密码" />
      </a-form-item>
      <a-button type="primary" block :loading="loading" @click="onSubmit">登录</a-button>
      <div v-if="error" style="color:red;margin-top:8px;">{{ error }}</div>
    </a-form>
  </div>
  </template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const email = ref('')
const password = ref('')
const router = useRouter()
const auth = useAuthStore()
const loading = computed(() => auth.loading)
const error = computed(() => auth.error)

async function onSubmit() {
  const ok = await auth.signInWithPassword(email.value, password.value)
  if (ok) router.push('/')
}
</script>



