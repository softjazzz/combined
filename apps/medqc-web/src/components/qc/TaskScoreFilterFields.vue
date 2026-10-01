<template>
  <template v-if="scene === 'running' || scene === 'final'">
    <a-form-item label="评分标准">
      <a-select
        :value="modelValue?.standard_id"
        allow-clear
        :loading="loading"
        :disabled="disabled"
        placeholder="不限评分"
        :options="standards.map((item) => ({ value: item.id, label: item.name }))"
        @change="selectStandard"
      />
      <div v-if="error" class="text-xs text-red-500 mt-2">{{ error }}</div>
    </a-form-item>
    <template v-if="modelValue">
      <a-form-item label="得分区间">
        <div class="flex gap-2">
          <a-input-number
            :value="modelValue.score_min"
            :disabled="disabled"
            placeholder="最低得分"
            @change="(value) => update('score_min', value)"
          />
          <a-input-number
            :value="modelValue.score_max"
            :disabled="disabled"
            placeholder="最高得分"
            @change="(value) => update('score_max', value)"
          />
        </div>
      </a-form-item>
    </template>
  </template>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { listScoringStandards, type ScoringStandardItem } from '@/api/scoring'
import type { TaskScoreFilter, TaskScene } from '@/api/tasks'

const props = defineProps<{
  modelValue?: TaskScoreFilter
  scene: TaskScene | null
  disabled?: boolean
}>()
const emit = defineEmits<{
  (event: 'update:modelValue', value: TaskScoreFilter | undefined): void
}>()
const standards = ref<ScoringStandardItem[]>([])
const loading = ref(false)
const error = ref('')
let requestId = 0

function selectStandard(value?: string) {
  emit('update:modelValue', value ? { standard_id: value } : undefined)
}
function update(key: 'score_min' | 'score_max', value: unknown) {
  if (!props.modelValue) return
  const next = { ...props.modelValue }
  delete next[key]
  if (typeof value === 'number' && Number.isFinite(value)) next[key] = value
  emit('update:modelValue', next)
}
watch(
  () => props.scene,
  async (scene) => {
    const current = ++requestId
    standards.value = []
    error.value = ''
    loading.value = false
    if (scene !== 'running' && scene !== 'final') return
    loading.value = true
    try {
      const result = await listScoringStandards({ scene, status: 'active' })
      if (current !== requestId) return
      if (!result.success || !result.data) {
        error.value = result.message || '评分标准暂不可用'
        return
      }
      standards.value = result.data.items.filter(
        (item) => item.rule_set_key === 'luxian_0609_qc_v1',
      )
    } catch {
      if (current === requestId) error.value = '评分标准暂不可用'
    } finally {
      if (current === requestId) loading.value = false
    }
  },
  { immediate: true },
)
</script>
