<template>
  <div class="ba-answer">
    <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
      <h4 v-if="block.type === 'heading'" class="ba-answer__heading">
        <template v-for="(part, partIndex) in block.inline" :key="partIndex">
          <strong v-if="part.bold">{{ part.text }}</strong>
          <code v-else-if="part.code">{{ part.text }}</code>
          <span v-else>{{ part.text }}</span>
        </template>
      </h4>
      <p v-else-if="block.type === 'paragraph'" class="ba-answer__paragraph">
        <template v-for="(part, partIndex) in block.inline" :key="partIndex">
          <strong v-if="part.bold">{{ part.text }}</strong>
          <code v-else-if="part.code">{{ part.text }}</code>
          <span v-else>{{ part.text }}</span>
        </template>
      </p>
      <component :is="block.ordered ? 'ol' : 'ul'" v-else class="ba-answer__list">
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
          <template v-for="(part, partIndex) in item" :key="partIndex">
            <strong v-if="part.bold">{{ part.text }}</strong>
            <code v-else-if="part.code">{{ part.text }}</code>
            <span v-else>{{ part.text }}</span>
          </template>
        </li>
      </component>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { parseAnswer } from './businessAgentMarkdown'

const props = defineProps<{ text: string }>()
const blocks = computed(() => parseAnswer(props.text))
</script>

<style scoped>
.ba-answer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-wrap: anywhere;
  line-height: 1.75;
}
.ba-answer__paragraph,
.ba-answer__heading {
  margin: 0;
  white-space: pre-wrap;
}
.ba-answer__heading {
  font-size: 14px;
  font-weight: 700;
}
.ba-answer__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 1.4em;
}
.ba-answer__list li::marker {
  color: var(--mq-text-tertiary);
}
.ba-answer strong {
  font-weight: 600;
  color: var(--mq-text-primary);
}
.ba-answer code {
  padding: 0 4px;
  border-radius: 4px;
  font-family: var(--mq-font-mono);
  font-size: 12px;
  background: var(--mq-neutral-bg);
}
</style>
