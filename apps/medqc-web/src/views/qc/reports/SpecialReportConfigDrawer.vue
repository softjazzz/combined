<template>
  <a-drawer :open="open" title="机构特殊病历代码配置" :width="640" @close="$emit('close')">
    <p>机构：{{ instituteId }}</p>
    <p v-if="loading" role="status">正在读取机构代码配置…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <form v-else-if="receipt && draft" class="config-form" @submit.prevent="save">
      <section v-for="group in groups" :key="group.key">
        <h3>{{ group.label }}</h3>
        <label
          >明确命中代码<a-select
            v-model:value="draft[group.key].positive_codes"
            mode="tags"
            :disabled="saving"
        /></label>
        <label
          >明确非该类型代码<a-select
            v-model:value="draft[group.key].negative_codes"
            mode="tags"
            :disabled="saving"
        /></label>
      </section>
      <section>
        <h3>院方手术等级代码</h3>
        <label v-for="level in levels" :key="level"
          >{{ level }}级代码<a-select
            v-model:value="draft.surgery_level_codes[level]"
            mode="tags"
            :disabled="saving"
        /></label>
      </section>
      <p>未配置、未映射代码保持未知。当前版本 {{ receipt.version_seq }}。</p>
      <a-button type="primary" html-type="submit" :loading="saving" :disabled="saving"
        >确认保存</a-button
      >
    </form>
    <p v-if="notice" role="status">{{ notice }}</p>
    <a-button :disabled="saving" @click="load">重新读取</a-button>
  </a-drawer>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import { getSpecialSourceConfig, saveSpecialSourceConfig } from '@/api/specialRecordReports'
import type { SpecialConfigReceipt, SpecialSourceConfig } from '@/api/specialRecordReports'
const props = defineProps<{ open: boolean; instituteId: string }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const groups = [
  { key: 'critical', label: '危重' },
  { key: 'difficult', label: '疑难' },
] as const
const levels = ['1', '2', '3', '4'] as const
const receipt = ref<SpecialConfigReceipt | null>(null)
const draft = ref<SpecialSourceConfig | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
let nonce = 0
async function load() {
  const ticket = ++nonce
  receipt.value = null
  draft.value = null
  loading.value = true
  saving.value = false
  error.value = ''
  try {
    const result = await getSpecialSourceConfig(props.instituteId)
    if (ticket !== nonce) return false
    receipt.value = result
    draft.value = structuredClone(result.config)
    return true
  } catch (cause) {
    if (ticket === nonce) error.value = cause instanceof Error ? cause.message : '配置读取失败'
  } finally {
    if (ticket === nonce) loading.value = false
  }
}
async function save() {
  if (!receipt.value || !draft.value || saving.value) return
  const ticket = nonce
  const institution = props.instituteId
  saving.value = true
  notice.value = ''
  try {
    const result = await saveSpecialSourceConfig(
      institution,
      receipt.value.version_seq,
      draft.value,
    )
    if (ticket !== nonce) return
    if (await load()) {
      if (receipt.value?.version_seq === result.version_seq) {
        notice.value = '配置已保存'
        emit('saved')
      } else notice.value = '配置已变化，请核对当前版本'
    }
  } catch (cause) {
    if (ticket !== nonce) return
    const conflict = isAxiosError(cause) && cause.response?.status === 409
    const reloadTicket = nonce + 1
    const verified = await load()
    if (reloadTicket === nonce)
      notice.value = verified
        ? conflict
          ? '配置已被修改，请核对并重新确认保存'
          : '保存结果未知，已重新读取，请核对当前代码'
        : '保存结果未知且回读失败，请重新读取后核对'
  } finally {
    if (ticket === nonce) saving.value = false
  }
}
watch(
  () => [props.open, props.instituteId],
  () => {
    nonce++
    notice.value = ''
    receipt.value = null
    draft.value = null
    if (props.open && props.instituteId) void load()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  nonce++
})
</script>
<style scoped>
.config-form {
  display: grid;
  gap: 16px;
}
.config-form section,
label {
  display: grid;
  gap: 8px;
}
h3 {
  margin: 0;
  font-size: 15px;
}
label {
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
