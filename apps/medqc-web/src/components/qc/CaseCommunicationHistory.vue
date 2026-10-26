<template>
  <ul class="communication-history">
    <li
      v-for="event in items"
      :key="event.id"
      :class="{ 'is-active': event.id === activeId }"
    >
      <div class="communication-history__head">
        <MqIcon
          :name="communicationIcon(event.action)"
          :size="16"
        />
        <strong>{{ communicationLabels[event.action] }}</strong>
        <span
          class="mq-status"
          :class="communicationStatusClass(event)"
        >{{
          communicationStatus(event)
        }}</span>
        <span
          v-if="event.id === activeId"
          class="communication-history__active"
        >当前查看</span>
        <time :datetime="event.created_at">{{ formatCommunicationTime(event.created_at) }}</time>
      </div>
      <span
        v-if="recipientLabel"
        class="communication-history__recipient"
      >受领医生 · {{ recipientLabel(event.recipient_id) }}</span>
      <p class="communication-history__content">
        {{ event.content }}
      </p>
      <details class="communication-history__source">
        <summary>事件来源</summary>
        <dl>
          <div>
            <dt>事件ID</dt>
            <dd>{{ event.id }}</dd>
          </div>
          <div>
            <dt>发送人ID</dt>
            <dd>{{ event.actor_id }}</dd>
          </div>
          <div>
            <dt>受领人ID</dt>
            <dd>{{ event.recipient_id }}</dd>
          </div>
          <div>
            <dt>通知ID</dt>
            <dd>{{ event.notification_id }}</dd>
          </div>
        </dl>
        <p
          v-if="event.related_event_id"
          class="mq-mono"
        >
          原催办：{{ event.related_event_id }}
        </p>
      </details>
      <slot
        name="actions"
        :event="event"
      />
    </li>
  </ul>
</template>

<script setup lang="ts">
import type { Communication } from '@/api/caseCommunications'
import MqIcon from '@/components/icons/MqIcon.vue'
import {
  communicationLabels,
  communicationStatus,
  communicationStatusClass,
  communicationIcon,
  formatCommunicationTime,
} from './caseCommunicationPresentation'

defineProps<{
  items: Communication[]
  activeId?: string
  recipientLabel?: (id: string) => string
}>()
</script>

<style scoped src="./styles/case-communication-history.css"></style>
