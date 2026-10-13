<script setup lang="ts">
import { computed } from 'vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { WorkstationConfirmation } from './workstationConfirmation'

const props = defineProps<{ controller: WorkstationConfirmation }>()
const { current, busy, error } = props.controller
const titleContent = computed(() => () => current.value?.title)
const bodyContent = computed(() => () => current.value?.content)
const isDanger = computed(
  () => current.value?.okType === 'danger' || current.value?.okButtonProps?.danger,
)
</script>

<template>
  <a-modal
    :open="!!current"
    :width="460"
    :footer="null"
    :closable="false"
    :mask-closable="false"
    centered
    wrap-class-name="mq-modal"
    @cancel="controller.cancel"
  >
    <div class="mq-confirm">
      <MqIconTile name="issue" />
      <h2 class="mq-card__title">
        <component :is="titleContent" />
      </h2>
      <div class="mq-soft mq-confirm__summary">
        <component :is="bodyContent" />
      </div>
      <p v-if="error" role="alert" class="mq-confirm__error">
        {{ error }}
      </p>
      <div class="mq-confirm__actions">
        <a-button :disabled="busy" @click="controller.cancel">
          {{ current?.cancelText || '取消' }}
        </a-button>
        <a-button type="primary" :danger="isDanger" :loading="busy" @click="controller.accept">
          {{ current?.okText || '确认' }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<style scoped>
.mq-confirm {
  display: grid;
  justify-items: start;
  gap: var(--mq-space-4);
}
.mq-confirm__summary {
  width: 100%;
  padding: var(--mq-space-4);
  color: var(--mq-text-secondary);
}
.mq-confirm__actions {
  display: grid;
  width: 100%;
  grid-template-columns: 1fr 1fr;
  gap: var(--mq-space-3);
}
.mq-confirm__error {
  color: var(--mq-danger-text);
}
</style>
