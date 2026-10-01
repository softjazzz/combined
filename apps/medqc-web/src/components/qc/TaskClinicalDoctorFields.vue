<template>
  <a-form-item v-if="scene === 'running' || scene === 'final'" label="临床医生（主治医师）">
    <a-checkbox :checked="!!modelValue" :disabled="disabled" @change="toggle($event.target.checked)"
      >指定主治医师</a-checkbox
    >
    <div v-for="(doctor, index) in modelValue || []" :key="index" class="flex gap-2 mt-2">
      <a-input
        :value="doctor.institute_id"
        :disabled="disabled"
        :maxlength="100"
        placeholder="机构 ID"
        aria-label="医生所属机构"
        @update:value="(value) => update(index, 'institute_id', value)"
      />
      <a-input
        :value="doctor.physician_name"
        :disabled="disabled"
        :maxlength="100"
        placeholder="主治医师签名"
        aria-label="主治医师签名"
        @update:value="(value) => update(index, 'physician_name', value)"
      />
      <a-button :disabled="disabled" title="移除医师" aria-label="移除医师" @click="remove(index)"
        ><Trash2 :size="16"
      /></a-button>
    </div>
    <a-button
      v-if="modelValue"
      class="mt-2"
      :disabled="disabled || modelValue.length >= 100"
      @click="add"
      ><Plus :size="16" />添加医师</a-button
    >
  </a-form-item>
</template>
<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'
import type { TaskClinicalDoctorRef, TaskScene } from '@/api/tasks'
const props = defineProps<{
  modelValue?: TaskClinicalDoctorRef[]
  scene: TaskScene | null
  disabled?: boolean
}>()
const emit = defineEmits<{
  (event: 'update:modelValue', value: TaskClinicalDoctorRef[] | undefined): void
}>()
const blank = (): TaskClinicalDoctorRef => ({ institute_id: '', physician_name: '' })
function toggle(enabled: boolean) {
  emit('update:modelValue', enabled ? [blank()] : undefined)
}
function add() {
  emit('update:modelValue', [...(props.modelValue || []), blank()])
}
function remove(index: number) {
  const next = props.modelValue?.filter((_, position) => position !== index)
  emit('update:modelValue', next?.length ? next : undefined)
}
function update(index: number, key: keyof TaskClinicalDoctorRef, value: string) {
  emit(
    'update:modelValue',
    props.modelValue?.map((item, position) =>
      position === index ? { ...item, [key]: value } : { ...item },
    ),
  )
}
</script>
