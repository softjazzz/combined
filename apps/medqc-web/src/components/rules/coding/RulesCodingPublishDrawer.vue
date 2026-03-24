<template>
  <a-drawer
    :open="open"
    title="发布编码规则变更"
    width="420"
    @close="emit('close')"
  >
    <div class="space-y-3 text-[13px]">
      <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <div>
          本次变更规则：<strong>{{ changeCount }}</strong> 条
        </div>
        <div class="mt-1">
          预计影响病历：<strong>{{ estimatedImpactCount }}</strong> 条
        </div>
      </div>
      <a-alert
        v-for="(item, idx) in riskNotes"
        :key="idx"
        type="warning"
        :message="item"
        show-icon
      />
      <a-alert
        v-if="highRiskUnreviewedCount > 0"
        type="error"
        :message="`仍有 ${highRiskUnreviewedCount} 条高风险规则未复核`"
        show-icon
      />
      <a-space>
        <a-button @click="emit('close')">
          取消
        </a-button>
        <a-button
          type="primary"
          :loading="loading"
          :disabled="readonly"
          @click="emit('confirm-publish')"
        >
          确认发布
        </a-button>
      </a-space>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
defineProps<{
  open: boolean
  loading: boolean
  changeCount: number
  estimatedImpactCount: number
  riskNotes: string[]
  highRiskUnreviewedCount: number
  readonly: boolean
}>()

const emit = defineEmits<{
  close: []
  'confirm-publish': []
}>()
</script>
