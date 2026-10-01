<template>
  <section v-if="allowed" class="case-inbox">
    <header><h2>病例沟通待办</h2><a-button :disabled="loading" aria-label="刷新病例沟通" @click="load()"><RefreshCw :size="16" /></a-button></header>
    <a-alert v-if="error" :message="error" type="error" show-icon />
    <a-spin :spinning="loading"><ul><li v-for="item in items" :key="item.id"><button @click="show(item)"><span>{{ item.department }} · {{ item.visit_id }} · {{ item.action === 'urge' ? '病历催办' : '质控意见' }}</span><span>{{ item.is_read === true ? '已读' : item.is_read === false ? '未读' : '未知' }}</span><span>{{ item.content }}</span></button></li></ul><p v-if="!loading && !error && !items.length">暂无病例沟通</p></a-spin>
    <a-button v-if="hasMore" :loading="loading" :disabled="loading" @click="load(false)">加载更多</a-button>
    <a-modal :open="!!selected" title="病例沟通" :footer="null" @cancel="close">
      <template v-if="selected"><p>{{ selected.scene === 'running' ? '运行病历' : '终末病历' }} · {{ selected.visit_id }}</p><p class="case-inbox__content">{{ selected.content }}</p><p>{{ selected.is_read === true ? '已读' : '已读状态待核实' }}</p><p>结果轮次：{{ selected.root_job_id }}</p></template>
      <a-alert v-if="readError" :message="readError" type="error" /><a-button v-if="readError" @click="checkRead">刷新核对</a-button>
    </a-modal>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { getCommunication, getCommunicationInbox, readCommunication } from '@/api/caseCommunications'
import type { Communication } from '@/api/caseCommunications'
const auth = useAuthStore()
const allowed = computed(() => Array.isArray(auth.userRoles) && auth.userRoles.includes('doctor'))
const items = ref<Communication[]>([]), selected = ref<Communication>()
const loading = ref(false), error = ref(''), readError = ref('')
let generation = 0
const page = ref(0), hasMore = ref(false)
async function load(reset = true) {
  const token = ++generation
  loading.value = true; error.value = ''
  try {
    const data = await getCommunicationInbox(reset ? 1 : page.value + 1)
    if (token !== generation) return
    items.value = reset ? data.items : [...items.value, ...data.items.filter(item => !items.value.some(old => old.id === item.id))]
    page.value = data.page; hasMore.value = data.has_more
    if (selected.value) { const updated = data.items.find(item => item.id === selected.value?.id); if (updated) selected.value = updated; if (selected.value?.is_read === true) readError.value = '' }
  } catch (reason) { if (token === generation) { error.value = reason instanceof Error ? reason.message : '读取失败'; if (reset) items.value = [] } }
  finally { if (token === generation) loading.value = false }
}
async function show(item: Communication) {
  const token = ++generation
  loading.value = false
  selected.value = item; readError.value = ''
  try {
    const data = await readCommunication(item.id)
    if (token !== generation) return
    if (data.id !== item.id || data.is_read !== true) throw new Error('已读结果无法确认，请刷新核对')
    selected.value = data
    items.value = items.value.map(value => value.id === item.id ? data : value)
  } catch (reason) { if (token === generation) readError.value = reason instanceof Error ? reason.message : '已读结果待核实' }
}
async function checkRead() {
  const item = selected.value
  if (!item) return
  const token = ++generation
  loading.value = false
  try {
    const data = await getCommunication(item.id)
    if (token !== generation) return
    if (data.id !== item.id) throw new Error('消息来源不一致，无法确认已读')
    selected.value = data
    items.value = items.value.map(value => value.id === item.id ? data : value)
    readError.value = data.is_read === true ? '' : '已读未确认，可关闭后重新查看'
  } catch (reason) { if (token === generation) readError.value = reason instanceof Error ? reason.message : '已读结果待核实' }
}
function close() { generation += 1; loading.value = false; selected.value = undefined }
watch(() => [auth.user?.id, ...(auth.userRoles || [])], () => { generation += 1; items.value = []; page.value = 0; hasMore.value = false; selected.value = undefined; error.value = ''; readError.value = ''; loading.value = false; if (allowed.value) void load() }, { immediate: true })
</script>
<style scoped>
.case-inbox { margin: 16px 0; padding: 16px 0; border-bottom: 1px solid #edf0f4; }
.case-inbox header { display: flex; align-items: center; justify-content: space-between; }
.case-inbox h2 { margin: 0; font-size: 17px; }
.case-inbox ul { padding: 0; list-style: none; }
.case-inbox li button { display: flex; flex-wrap: wrap; gap: 8px 16px; width: 100%; padding: 12px 0; text-align: left; background: none; border: 0; border-bottom: 1px solid #edf0f4; cursor: pointer; }
.case-inbox li button span:last-child { flex-basis: 100%; overflow-wrap: anywhere; }
.case-inbox__content { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
