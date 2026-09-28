<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-vue-next'
import {
  confirmQrLogin,
  getQrLoginConfirmation,
  rejectQrLogin,
  type QrLoginState,
} from '@/api/qrLogin'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()
const state = ref<QrLoginState | null>(null)
const verificationCode = ref('')
const loading = ref(false)
const errorMessage = ref('')
let revision = 0

const sessionId = computed(() => typeof route.query.session_id === 'string' ? route.query.session_id.trim() : '')
const actorKey = computed(() => `${authStore.user?.id || ''}|${[...(authStore.userRoles || [])].sort().join(',')}`)
const canDecide = computed(() => state.value?.status === 'pending' && !loading.value)

async function load() {
  revision += 1
  const currentRevision = revision
  state.value = null
  verificationCode.value = ''
  errorMessage.value = ''
  if (!sessionId.value) {
    errorMessage.value = '扫码登录会话无效'
    return
  }
  loading.value = true
  const result = await getQrLoginConfirmation(sessionId.value)
  if (currentRevision !== revision) return
  loading.value = false
  if (result.success === false || result.data.session_id !== sessionId.value) {
    errorMessage.value = result.success === false ? result.message : '扫码登录会话不一致'
    return
  }
  state.value = result.data
  if (result.data.status !== 'pending') verificationCode.value = ''
}

async function decide(action: 'confirm' | 'reject') {
  if (!canDecide.value) return
  if (action === 'confirm' && !verificationCode.value.trim()) {
    errorMessage.value = '请输入电脑上显示的确认码'
    return
  }
  const currentRevision = ++revision
  loading.value = true
  errorMessage.value = ''
  const result = action === 'confirm'
    ? await confirmQrLogin(sessionId.value, verificationCode.value)
    : await rejectQrLogin(sessionId.value)
  if (currentRevision !== revision) return
  loading.value = false
  if (result.success === false || result.data.session_id !== sessionId.value) {
    errorMessage.value = result.success === false ? result.message : '扫码登录会话不一致'
    return
  }
  state.value = result.data
  verificationCode.value = ''
}

watch([sessionId, actorKey], () => void load())
onMounted(() => void load())
onBeforeUnmount(() => { revision += 1 })
</script>

<template>
  <main class="qr-confirm-page">
    <section class="qr-confirm-panel">
      <ShieldCheck :size="34" class="qr-confirm-panel__icon" aria-hidden="true" />
      <h1>确认电脑登录</h1>
      <p>请核对电脑页面上的确认码。只有本人正在操作时才允许登录。</p>

      <a-spin v-if="loading && !state" />
      <template v-else-if="state?.status === 'pending'">
        <label for="verification-code">电脑确认码</label>
        <a-input
          id="verification-code"
          v-model:value="verificationCode"
          :maxlength="12"
          autocomplete="one-time-code"
          placeholder="输入电脑上显示的确认码"
        />
        <div class="qr-confirm-panel__actions">
          <a-button :disabled="loading" @click="decide('reject')">
            <XCircle :size="16" /> 拒绝
          </a-button>
          <a-button type="primary" :loading="loading" @click="decide('confirm')">
            <CheckCircle2 :size="16" /> 允许登录
          </a-button>
        </div>
      </template>
      <a-result
        v-else-if="state?.status === 'approved'"
        status="success"
        title="已允许电脑登录"
        sub-title="可以返回电脑继续使用。"
      />
      <a-result
        v-else-if="state"
        status="info"
        :title="state.status === 'rejected' ? '已拒绝登录' : '本次登录已结束'"
      />
      <a-alert v-if="errorMessage" type="error" show-icon :message="errorMessage" />
    </section>
  </main>
</template>

<style scoped>
.qr-confirm-page { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: #f5f5f7; font-family: 'Source Han Sans SC','Microsoft YaHei UI','PingFang SC',sans-serif; }
.qr-confirm-panel { width: min(100%, 420px); padding: 28px; border: 1px solid rgba(0,0,0,.08); border-radius: 12px; background: #fff; box-shadow: 0 8px 28px rgba(38,58,86,.08); }
.qr-confirm-panel__icon { color: #007aff; }
.qr-confirm-panel h1 { margin: 14px 0 6px; color: #1d1d1f; font-size: 24px; line-height: 31px; }
.qr-confirm-panel p { margin: 0 0 22px; color: rgba(29,29,31,.60); font-size: 14px; line-height: 22px; }
.qr-confirm-panel label { display: block; margin-bottom: 7px; color: #1d1d1f; font-size: 14px; }
.qr-confirm-panel__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.qr-confirm-panel__actions :deep(.ant-btn) { display: inline-flex; align-items: center; gap: 6px; border-radius: 8px; }
.qr-confirm-panel :deep(.ant-alert) { margin-top: 16px; }
</style>
