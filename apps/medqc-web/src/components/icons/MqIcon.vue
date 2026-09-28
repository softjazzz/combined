<script setup lang="ts">
import { computed } from 'vue'
import { MQ_ICONS, type MqIconName, type MqIconPart } from './mqIcons'

const props = withDefaults(
  defineProps<{
    name: MqIconName
    /** 描边与填充色；默认继承文字颜色 */
    color?: string
    size?: number
  }>(),
  { color: 'currentColor', size: 18 },
)

const STROKE_WIDTH = 1.6

const parts = computed<MqIconPart[]>(() => MQ_ICONS[props.name])

const BADGE_MARKS: Record<string, string> = {
  check: 'm15.4 17.6 1.5 1.5 2.8-3',
  plus: 'M17.5 15.4v4.2M15.4 17.5h4.2',
  bang: 'M17.5 15.3v2.6',
  question: 'M16.3 16.4a1.3 1.3 0 1 1 1.9 1.1c-.4.2-.7.5-.7.9',
}
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    class="mq-icon"
  >
    <template
      v-for="(part, index) in parts"
      :key="index"
    >
      <path
        v-if="part.kind === 'body'"
        :d="part.d"
        :fill="color"
        fill-opacity="0.16"
        :stroke="color"
        :stroke-width="STROKE_WIDTH"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
      <path
        v-else-if="part.kind === 'stroke'"
        :d="part.d"
        :stroke="color"
        :stroke-width="STROKE_WIDTH"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
      <path
        v-else-if="part.kind === 'line'"
        :d="part.d"
        :stroke="color"
        :stroke-width="STROKE_WIDTH"
        stroke-linejoin="round"
        stroke-linecap="round"
        :opacity="part.opacity ?? 0.55"
      />
      <path
        v-else-if="part.kind === 'solid'"
        :d="part.d"
        :fill="color"
        :fill-opacity="part.opacity"
        :stroke="color"
        :stroke-width="STROKE_WIDTH"
        stroke-linejoin="round"
      />
      <circle
        v-else-if="part.kind === 'dot'"
        :cx="part.cx"
        :cy="part.cy"
        :r="part.r"
        :fill="color"
      />
      <g v-else-if="part.kind === 'badge'">
        <circle
          cx="17.5"
          cy="17.5"
          r="4.6"
          :fill="color"
          stroke="#FFFFFF"
          stroke-width="1.4"
        />
        <path
          :d="BADGE_MARKS[part.mark]"
          stroke="#FFFFFF"
          :stroke-width="part.mark === 'question' ? 1.4 : 1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle
          v-if="part.mark === 'bang'"
          cx="17.5"
          cy="19.6"
          r="0.9"
          fill="#FFFFFF"
        />
        <circle
          v-if="part.mark === 'question'"
          cx="17.5"
          cy="20"
          r="0.8"
          fill="#FFFFFF"
        />
      </g>
    </template>
  </svg>
</template>

<style scoped>
.mq-icon {
  flex-shrink: 0;
  display: block;
}
</style>
