<template>
  <div class="ba-answer">
    <template v-for="(block, blockIndex) in visibleBlocks" :key="blockIndex">
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
    <button
      v-if="foldable"
      type="button"
      class="ba-answer__toggle"
      data-testid="business-agent-answer-toggle"
      @click="expanded = !expanded"
    >
      {{ expanded ? '收起' : '展开全文' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { parseAnswer, type AnswerBlock } from './businessAgentMarkdown'

const props = defineProps<{ text: string }>()
const blocks = computed(() => parseAnswer(props.text))

// 长回答默认只显示开头结论（约 120 字内的前几块），避免挤占卡片区域；正式结论以卡片为准。
const FOLD_CHARS = 200
const PREVIEW_CHARS = 120
function blockChars(block: AnswerBlock) {
  const parts = block.type === 'list' ? block.items.flat() : block.inline
  return parts.reduce((total, part) => total + part.text.length, 0)
}
const previewCount = computed(() => {
  let chars = 0
  let count = 0
  for (const block of blocks.value) {
    if (count > 0 && chars + blockChars(block) > PREVIEW_CHARS) break
    chars += blockChars(block)
    count += 1
  }
  return count
})
const foldable = computed(() => {
  const chars = blocks.value.reduce((total, block) => total + blockChars(block), 0)
  return chars > FOLD_CHARS && previewCount.value < blocks.value.length
})
const expanded = ref(false)
const visibleBlocks = computed(() =>
  foldable.value && !expanded.value ? blocks.value.slice(0, previewCount.value) : blocks.value,
)
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
.ba-answer__toggle {
  align-self: flex-start;
  padding: 0;
  border: 0;
  background: none;
  color: var(--mq-info-text);
  font-size: 12px;
  cursor: pointer;
}
.ba-answer__toggle:hover {
  text-decoration: underline;
}
.ba-answer code {
  padding: 0 4px;
  border-radius: 4px;
  font-family: var(--mq-font-mono);
  font-size: 12px;
  background: var(--mq-neutral-bg);
}
</style>
