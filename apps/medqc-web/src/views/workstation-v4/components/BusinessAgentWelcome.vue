<template>
  <div class="ba-welcome">
    <span class="ba-avatar ba-avatar--xl" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
        <path d="M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4z" />
        <path d="M19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
      </svg>
    </span>
    <h2 class="ba-welcome__title">
      {{ view === 'doctor' ? '你好，我是病历助手' : '你好，我是质控分析助手' }}
    </h2>
    <p class="ba-welcome__lead">
      {{
        view === 'doctor'
          ? '帮你看懂质控问题、找到原文和规范，再协助修改。'
          : '问指标、下钻病例、比较期间，或起草质量报告。'
      }}
    </p>
    <p class="ba-sr-only" data-testid="business-agent-readonly-notice">
      支持查询与解释、查看提醒与整改记录；异议反馈需本人填写理由并提交，不改变质控结论。
    </p>
    <div v-if="summary" class="ba-todo" data-testid="business-agent-todo">
      <div class="ba-todo__item ba-todo__item--danger">
        <span class="ba-todo__label">待处理问题</span>
        <strong class="ba-todo__value">{{ summary.pending }}</strong>
      </div>
      <button
        type="button"
        class="ba-todo__item ba-todo__item--link"
        data-testid="business-agent-todo-messages"
        @click="emit('open-tab', 'message')"
      >
        <span class="ba-todo__label">未读消息</span>
        <strong class="ba-todo__value">
          {{ summary.unread }}<span class="ba-todo__go">查看 ›</span>
        </strong>
      </button>
    </div>
    <div class="ba-welcome__cards">
      <button
        v-for="prompt in prompts"
        :key="prompt"
        type="button"
        class="ba-welcome__card"
        :disabled="disabled"
        @click="emit('pick', prompt)"
      >
        {{ prompt }}
      </button>
    </div>
    <a-button
      v-if="canOpenProfile"
      type="link"
      size="small"
      data-testid="business-agent-open-profile"
      @click="emit('open-profile')"
    >
      打开本病例画像面板
    </a-button>
    <span v-if="canOpenProfile" class="ba-muted">打开面板不会自动分析</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  view: 'doctor' | 'manager'
  prompts: string[]
  disabled: boolean
  canOpenProfile: boolean
  // 宿主提供的待办摘要；缺省时不显示。
  summary?: { pending: number; unread: number } | null
}>()
const emit = defineEmits<{
  pick: [prompt: string]
  'open-profile': []
  'open-tab': [tab: 'message']
}>()
</script>
