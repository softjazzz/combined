<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import QrcodeVue from 'qrcode.vue'
import { RefreshCw, ShieldCheck, Smartphone } from 'lucide-vue-next'
import {
  cancelQrLogin,
  createQrLoginSession,
  exchangeQrLogin,
  getQrLoginStatus,
  type QrLoginSession,
  type QrLoginStatus,
} from '@/api/qrLogin'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(defineProps<{ tone?: 'light' | 'dark' }>(), { tone: 'light' })
const emit = defineEmits<{ authenticated: [] }>()

const authStore = useAuthStore()
const session = ref<QrLoginSession | null>(null)
const status = ref<QrLoginStatus | 'creating' | 'exchanging' | 'error'>('creating')
const errorMessage = ref('')
let generation = 0
let pollTimer: ReturnType<typeof setTimeout> | null = null

const qrUrl = computed(() => {
  if (!session.value) return ''
  const url = new URL('/auth/qr-confirm', window.location.origin)
  url.searchParams.set('session_id', session.value.session_id)
  return url.toString()
})

const statusText = computed(() => ({
  creating: '正在生成二维码',
  pending: '等待手机确认',
  approved: '手机已确认',
  exchanging: '正在完成登录',
  rejected: '手机已拒绝本次登录',
  cancelled: '本次登录已取消',
  expired: '二维码已过期',
  consumed: '二维码已使用',
  error: '扫码登录暂不可用',
}[status.value]))

function clearPoll() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
}

function discardCurrent(cancel = true) {
  clearPoll()
  generation += 1
  const current = session.value
  session.value = null
  if (cancel && current) void cancelQrLogin(current.session_id, current.browser_secret)
}

async function finishLogin(current: QrLoginSession, currentGeneration: number) {
  status.value = 'exchanging'
  session.value = null
  const exchanged = await exchangeQrLogin(current.session_id, current.browser_secret)
  if (currentGeneration !== generation) return
  if (exchanged.success === false) {
    status.value = 'error'
    errorMessage.value = '登录结果未确认，请重新生成二维码后再试'
    return
  }
  const completed = await authStore.completeQrLogin(
    exchanged.data,
    () => currentGeneration === generation,
  )
  if (currentGeneration !== generation) return
  if (!completed.success) {
    status.value = 'error'
    errorMessage.value = completed.error || '无法确认扫码登录用户'
    return
  }
  status.value = 'consumed'
  emit('authenticated')
}

async function poll(current: QrLoginSession, currentGeneration: number) {
  const result = await getQrLoginStatus(current.session_id, current.browser_secret)
  if (currentGeneration !== generation) return
  if (result.success === false) {
    status.value = 'error'
    errorMessage.value = result.message
    session.value = null
    return
  }
  if (result.data.session_id !== current.session_id) {
    status.value = 'error'
    errorMessage.value = '扫码登录状态与当前会话不一致'
    session.value = null
    return
  }
  status.value = result.data.status
  if (result.data.status === 'approved') {
    await finishLogin(current, currentGeneration)
    return
  }
  if (result.data.status !== 'pending') {
    session.value = null
    return
  }
  pollTimer = setTimeout(() => void poll(current, currentGeneration), current.poll_interval_ms)
}

async function createSession() {
  discardCurrent()
  const currentGeneration = generation
  status.value = 'creating'
  errorMessage.value = ''
  const result = await createQrLoginSession()
  if (currentGeneration !== generation) {
    if (result.success) void cancelQrLogin(result.data.session_id, result.data.browser_secret)
    return
  }
  if (result.success === false) {
    status.value = 'error'
    errorMessage.value = result.message
    return
  }
  session.value = result.data
  status.value = 'pending'
  pollTimer = setTimeout(
    () => void poll(result.data, currentGeneration),
    result.data.poll_interval_ms,
  )
}

onMounted(() => void createSession())
onBeforeUnmount(() => discardCurrent())
</script>

<template>
  <section class="qr-login" :class="`qr-login--${props.tone}`" aria-live="polite">
    <div class="qr-login__canvas">
      <QrcodeVue v-if="qrUrl" :value="qrUrl" :size="184" level="M" render-as="svg" />
      <a-spin v-else-if="status === 'creating'" size="large" />
      <Smartphone v-else :size="40" aria-hidden="true" />
    </div>

    <div class="qr-login__status">
      <ShieldCheck :size="17" aria-hidden="true" />
      <span>{{ statusText }}</span>
    </div>
    <p v-if="session" class="qr-login__code">
      电脑确认码 <strong>{{ session.verification_code }}</strong>
    </p>
    <p v-if="errorMessage" class="qr-login__error">{{ errorMessage }}</p>

    <button
      v-if="['rejected', 'cancelled', 'expired', 'consumed', 'error'].includes(status)"
      type="button"
      class="qr-login__refresh"
      @click="createSession"
    >
      <RefreshCw :size="15" aria-hidden="true" />
      重新生成
    </button>
  </section>
</template>

<style scoped>
.qr-login { display: grid; justify-items: center; gap: 12px; color: #1d1d1f; }
.qr-login--dark { color: #f8fafc; }
.qr-login__canvas { display: grid; place-items: center; width: 216px; height: 216px; padding: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,.08); border-radius: 8px; background: #fff; color: rgba(29,29,31,.38); }
.qr-login__status { display: flex; align-items: center; gap: 7px; font-size: 14px; font-weight: 600; }
.qr-login__code { margin: 0; font-size: 14px; }
.qr-login__code strong { margin-left: 6px; font-size: 18px; letter-spacing: 0; }
.qr-login__error { margin: 0; color: #ef4444; font-size: 13px; text-align: center; }
.qr-login__refresh { display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 0 14px; border: 1px solid rgba(0,122,255,.24); border-radius: 8px; background: transparent; color: #007aff; cursor: pointer; }
</style>
