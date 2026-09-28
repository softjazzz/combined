<script setup lang="ts">
import { computed } from 'vue'
import MqIcon from './MqIcon.vue'
import { MQ_ICON_TONES, type MqIconName, type MqIconTone } from './mqIcons'

const props = withDefaults(
  defineProps<{
    name: MqIconName
    tone?: MqIconTone
    /** 底座边长 */
    size?: number
    /** 图标边长，默认约为底座的 0.6 */
    iconSize?: number
  }>(),
  { tone: 'neutral', size: 24, iconSize: undefined },
)

const palette = computed(() => MQ_ICON_TONES[props.tone])
const glyph = computed(() => props.iconSize ?? Math.round(props.size * 0.62))
const tileStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  borderRadius: `${Math.round(props.size * 0.3)}px`,
  background: `linear-gradient(160deg, rgba(${palette.value.rgb},0.18), rgba(${palette.value.rgb},0.06))`,
  boxShadow: `inset 0 1px 0 rgba(255,255,255,0.9), inset 0 0 0 0.5px rgba(${palette.value.rgb},0.18)`,
}))
</script>

<template>
  <span
    class="mq-icon-tile"
    :style="tileStyle"
  >
    <MqIcon
      :name="name"
      :color="palette.color"
      :size="glyph"
    />
  </span>
</template>

<style scoped>
.mq-icon-tile {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
}
</style>
