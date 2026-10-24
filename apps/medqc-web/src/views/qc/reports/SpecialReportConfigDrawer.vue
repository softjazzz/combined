<template>
  <a-drawer
    :open="open"
    title="机构特殊病历代码配置"
    width="min(640px, 100vw)"
    class="special-config-drawer"
    @close="$emit('close')"
  >
    <div class="config-summary mq-soft">
      <span
        >机构 <strong class="mq-mono">{{ instituteId }}</strong></span
      >
      <span v-if="receipt"
        >当前版本 <strong class="mq-mono">{{ receipt.version_seq }}</strong></span
      >
    </div>
    <p v-if="loading" role="status" class="config-status">正在读取机构代码配置…</p>
    <p v-else-if="error" role="alert" class="config-status is-error">
      <MqIcon name="issue" :size="16" />{{ error }}
    </p>
    <form v-else-if="receipt && draft" class="config-form" @submit.prevent="save">
      <section v-for="group in groups" :key="group.key" class="config-group mq-inset">
        <h3>{{ group.label }}</h3>
        <div class="mq-field">
          <label class="mq-field__label" :for="`sr-${group.key}-positive`">明确命中代码</label
          ><a-select
            :id="`sr-${group.key}-positive`"
            v-model:value="draft[group.key].positive_codes"
            mode="tags"
            :disabled="saving"
          />
        </div>
        <div class="mq-field">
          <label class="mq-field__label" :for="`sr-${group.key}-negative`">明确非该类型代码</label
          ><a-select
            :id="`sr-${group.key}-negative`"
            v-model:value="draft[group.key].negative_codes"
            mode="tags"
            :disabled="saving"
          />
        </div>
      </section>
      <section class="config-group mq-inset">
        <h3>院方手术等级代码</h3>
        <div class="level-grid">
          <div v-for="level in levels" :key="level" class="mq-field">
            <label class="mq-field__label" :for="`sr-level-${level}`">{{ level }}级代码</label
            ><a-select
              :id="`sr-level-${level}`"
              v-model:value="draft.surgery_level_codes[level]"
              mode="tags"
              :disabled="saving"
            />
          </div>
        </div>
      </section>
      <p class="mq-field__hint">未配置、未映射代码保持未知。当前版本 {{ receipt.version_seq }}。</p>
    </form>
    <p v-if="notice" role="status" class="config-status">
      {{ notice }}
    </p>
    <div class="config-actions">
      <button class="mq-btn" type="button" :disabled="saving" @click="load">重新读取</button>
      <button
        v-if="!loading && !error && receipt && draft"
        class="mq-btn mq-btn--primary"
        type="button"
        :disabled="saving"
        @click="save"
      >
        {{ saving ? '正在保存…' : '确认保存' }}
      </button>
    </div>
  </a-drawer>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { isAxiosError } from 'axios'
import MqIcon from '@/components/icons/MqIcon.vue'
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
.config-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin-bottom: 16px;
  padding: 12px 16px;
  color: var(--mq-text-secondary);
  font-size: var(--mq-font-13);
}
.config-summary strong {
  color: var(--mq-text-primary);
}
.config-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px;
  color: var(--mq-text-tertiary);
}
.config-status.is-error {
  padding: 12px 16px;
  border-radius: var(--mq-radius-control);
  background: var(--mq-danger-bg);
  color: var(--mq-danger-text);
}
.config-form {
  display: grid;
  gap: 16px;
}
.config-group {
  display: grid;
  gap: 12px;
  padding: 16px;
}
.config-group h3 {
  margin: 0;
  font-size: var(--mq-font-16);
  font-weight: 600;
}
.level-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.config-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}
@media (max-width: 480px) {
  .level-grid {
    grid-template-columns: 1fr;
  }
}
</style>
