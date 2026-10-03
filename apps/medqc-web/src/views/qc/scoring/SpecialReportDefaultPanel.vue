<template>
  <section class="special-default" aria-label="特殊病历报表默认评分标准">
    <div class="heading">
      <h3>特殊病历报表默认评分标准</h3>
      <a-button :disabled="saving" :loading="loading" title="刷新专用默认标准" aria-label="刷新专用默认标准" @click="load"><RefreshCw :size="16" /></a-button>
    </div>
    <p v-if="loading" role="status">正在读取专用默认标准…</p>
    <p v-else-if="error" role="alert" class="error">{{ error }}</p>
    <template v-else-if="binding">
      <p data-testid="special-binding-status">
        {{ binding.status === 'configured' ? binding.standard?.name || '未知标准' : binding.status === 'unavailable' ? '已绑定标准不可用' : '未配置专用默认标准' }}
      </p>
      <p class="hint">用途：特殊病历报表 · 执行场景：终末病历</p>
      <p v-if="binding.status === 'unavailable'" class="hint">绑定已失效，请选择可用标准并确认保存，或解除绑定。</p>
      <form v-if="canWrite" @submit.prevent="save">
        <label for="special-default-choice">专用标准</label>
        <a-select id="special-default-choice" v-model:value="choice" :options="options" :disabled="saving" data-testid="special-default-choice" class="choice" />
        <a-button html-type="submit" type="primary" :loading="saving" :disabled="!changed || saving" data-testid="special-default-save">确认保存</a-button>
      </form>
      <p v-if="!candidates.length" class="hint">暂无可绑定的已启用终末标准</p>
    </template>
    <p v-if="notice" role="status" class="hint">{{ notice }}</p>
    <p v-if="saveError" role="alert" class="error">{{ saveError }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { getSpecialReportDefault, listScoringStandards, setSpecialReportDefault } from '@/api/scoring'
import type { SpecialReportDefaultBinding, ScoringStandardItem } from '@/api/scoring'

const props = defineProps<{ canWrite: boolean }>()
const auth = useAuthStore()
const binding = ref<SpecialReportDefaultBinding | null>(null)
const candidates = ref<ScoringStandardItem[]>([])
const choice = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const saveError = ref('')
const notice = ref('')
const options = computed(() => [
  { value: '', label: '解除绑定' },
  ...candidates.value.map((item) => ({ value: item.id, label: item.name })),
  ...(binding.value?.standard_id && !candidates.value.some((item) => item.id === binding.value?.standard_id)
    ? [{ value: binding.value.standard_id, label: `不可用标准（${binding.value.standard_id}）`, disabled: true }] : []),
])
const changed = computed(() => !!binding.value && (
  choice.value !== (binding.value.standard_id || '')
  || candidates.value.some((item) => item.id === choice.value && item.version_seq !== binding.value?.standard_version_seq)
))
let nonce = 0

async function load() {
  const ticket = ++nonce
  binding.value = null
  candidates.value = []
  choice.value = ''
  loading.value = true
  saving.value = false
  error.value = ''
  saveError.value = ''
  try {
    const [current, options] = await Promise.all([
      getSpecialReportDefault(), listScoringStandards({ scene: 'final', status: 'active' }),
    ])
    if (ticket !== nonce) return false
    if (!current.success || !current.data || !options.success || !options.data) {
      error.value = current.message || options.message || '读取专用默认标准失败'
      return false
    }
    binding.value = current.data
    candidates.value = options.data.items.filter((item) => item.scene === 'final' && item.status === 'active')
    // 失效绑定不伪造为候选，也不借用终末场景默认标准。
    choice.value = current.data.standard_id || ''
    return true
  } catch {
    if (ticket === nonce) error.value = '读取专用默认标准失败，请刷新重试'
  } finally {
    if (ticket === nonce) loading.value = false
  }
}

async function save() {
  if (!props.canWrite || !binding.value || saving.value || !changed.value) return
  const target = choice.value ? candidates.value.find((item) => item.id === choice.value) : null
  if (choice.value && !target) return
  const ticket = nonce
  saving.value = true
  saveError.value = ''
  notice.value = ''
  try {
    const result = await setSpecialReportDefault({
      version_seq: binding.value.version_seq,
      standard_id: target?.id ?? null,
      standard_version_seq: target?.version_seq ?? null,
    })
    if (ticket !== nonce) return
    if (!result.success || !result.data) {
      if (result.status === 409) {
        if (await load()) notice.value = '配置已变化，已刷新。请重新选择标准并确认保存。'
      } else if (!result.status || result.status >= 500 || result.status < 400) {
        await verifyUnknownWrite()
      } else saveError.value = result.message || '保存失败，请重新选择'
      return
    }
    const confirmed = result.data
    if (await load()) {
      const current = binding.value
      notice.value = current?.version_seq === confirmed.version_seq
        && current.standard_id === confirmed.standard_id
        && current.standard_version_seq === confirmed.standard_version_seq
        ? '专用默认标准已保存' : '保存后配置已被更新，请核对当前绑定。'
    }
  } catch {
    if (ticket === nonce) {
      await verifyUnknownWrite()
    }
  } finally {
    if (ticket === nonce) saving.value = false
  }
}

async function verifyUnknownWrite() {
  const reloadTicket = nonce + 1
  const verified = await load()
  if (reloadTicket !== nonce) return
  notice.value = verified
    ? '保存结果未确认，已回读配置。请核对当前绑定后重新选择。'
    : '保存结果未确认且回读失败，请刷新核对后再操作。'
}

watch(() => auth.user?.id, () => { notice.value = ''; void load() })
onMounted(() => { void load() })
onBeforeUnmount(() => { nonce++ })
</script>

<style scoped>
.special-default { padding: 14px 16px; background: var(--background-light); border: 1px solid var(--border-color); border-radius: 8px; }
.heading, form { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.heading { justify-content: space-between; }
h3 { margin: 0; font-size: 15px; color: var(--text-primary); }
p { margin: 8px 0; }
.hint { color: var(--text-secondary); font-size: 13px; }
.error { color: var(--error-color); }
.choice { width: 280px; max-width: 100%; }
</style>
