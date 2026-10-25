<template>
  <main class="mq-page message-center" :class="{ 'message-center--reading': mobileReading }">
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 消息与反馈</span>
        <h1 class="mq-page-title">消息中心</h1>
      </div>
      <div class="mq-page-head__actions">
        <span class="mq-status" :class="unread ? 'mq-status--info' : ''"
          >未读 {{ unread ?? '—' }}</span
        >
        <a-tooltip title="刷新消息"
          ><a-button
            class="message-center__refresh"
            aria-label="刷新消息"
            :loading="loading"
            @click="load"
            ><RefreshCw v-if="!loading" :size="16" /></a-button
        ></a-tooltip>
        <a-button
          class="message-center__command"
          :disabled="loading || !!busy || !!error || !unread"
          :loading="busy === '*'"
          @click="markAllRead"
          ><CheckCheck v-if="busy !== '*'" :size="16" />全部标为已读</a-button
        >
      </div>
    </header>

    <div class="message-center__filters">
      <nav class="mq-segmented" aria-label="消息阅读状态">
        <button
          v-for="option in statuses"
          :key="option.value"
          type="button"
          class="mq-segmented__item"
          :class="{ 'is-active': status === option.value }"
          :aria-pressed="status === option.value"
          :disabled="!!busy"
          @click="status = option.value"
        >
          {{ option.label }}
        </button>
      </nav>
      <a-select
        v-model:value="type"
        aria-label="消息类型"
        class="message-center__type"
        :options="typeOptions"
        :disabled="!!busy"
      />
      <span class="message-center__total">当前筛选 {{ loading || error ? '—' : total }} 条</span>
    </div>
    <a-alert v-if="error" type="error" show-icon :message="error" class="message-center__error">
      <template #action><a-button size="small" @click="load">重试</a-button></template>
    </a-alert>

    <section class="mq-card message-center__workspace" :aria-busy="loading" aria-label="消息收件箱">
      <div class="message-center__list-pane">
        <div class="message-center__list-heading">
          <h2>收件箱</h2>
          <span>{{ statusLabel }}</span>
        </div>
        <a-spin :spinning="loading">
          <ul v-if="items.length" class="message-center__list" aria-label="消息列表">
            <li
              v-for="item in items"
              :key="item.id"
              :class="{ 'is-selected': selected?.id === item.id, 'is-unread': !item.is_read }"
            >
              <button
                type="button"
                class="message-center__row"
                :aria-pressed="selected?.id === item.id"
                :disabled="!!busy"
                @click="select(item)"
              >
                <span class="message-center__row-top"
                  ><span class="message-center__category">{{ messageTypeLabel(item) }}</span
                  ><time :datetime="item.created_at">{{ messageTime(item.created_at) }}</time></span
                >
                <span class="message-center__subject"
                  ><span v-if="!item.is_read" class="message-center__dot" aria-label="未读" />{{
                    item.title
                  }}</span
                >
                <span class="message-center__excerpt">{{ item.content }}</span>
              </button>
            </li>
          </ul>
          <div v-else class="message-center__empty">
            <Inbox :size="32" :stroke-width="1.5" aria-hidden="true" />
            <strong>{{
              loading
                ? '正在读取消息'
                : error
                  ? '消息暂不可用'
                  : status === 'unread'
                    ? '未读消息已处理完毕'
                    : '暂无消息'
            }}</strong>
            <a-button v-if="!loading && !error && status === 'unread'" @click="status = 'all'"
              >查看全部消息</a-button
            >
          </div>
        </a-spin>
        <div v-if="total > pageSize" class="message-center__pagination">
          <a-pagination
            v-model:current="page"
            :page-size="pageSize"
            :total="total"
            :show-size-changer="false"
            size="small"
            :disabled="loading || !!busy"
            @change="load"
          />
        </div>
      </div>

      <article class="message-center__detail" aria-label="消息详情">
        <a-button
          class="message-center__back message-center__command"
          @click="mobileReading = false"
          ><ArrowLeft :size="16" />返回列表</a-button
        >
        <template v-if="selected">
          <div class="message-center__detail-meta">
            <span class="mq-status" :class="!selected.is_read ? 'mq-status--info' : ''">{{
              selected.is_read ? '已读' : '未读'
            }}</span
            ><span>{{ messageTypeLabel(selected) }}</span>
          </div>
          <h2>{{ selected.title }}</h2>
          <time :datetime="selected.created_at"
            >{{ messageTime(selected.created_at) }} · 北京时间</time
          >
          <div class="message-center__body">{{ selected.content }}</div>
          <div class="message-center__detail-actions">
            <a-button
              class="message-center__command"
              v-if="selected.interaction_target"
              type="primary"
              :disabled="loading || !!busy || !!error"
              @click="open(selected)"
              >{{ messageActionLabel(selected) }}<ArrowUpRight :size="16"
            /></a-button>
            <a-button
              class="message-center__command"
              v-if="!selected.is_read"
              :disabled="loading || !!busy || !!error"
              :loading="busy === selected.id"
              @click="markRead(selected)"
              ><Check v-if="busy !== selected.id" :size="16" />标为已读</a-button
            >
          </div>
          <p v-if="!selected.interaction_target" class="message-center__unlinked">
            该消息未提供精确处理对象。
          </p>
        </template>
        <div v-else class="message-center__empty">
          <MailOpen :size="32" :stroke-width="1.5" aria-hidden="true" /><span>暂无选中的消息</span>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  CheckCheck,
  Inbox,
  MailOpen,
  RefreshCw,
} from 'lucide-vue-next'
import {
  MESSAGE_TYPE_LABELS,
  messageActionLabel,
  messageTime,
  messageTypeLabel,
  useMessageCenter,
} from './useMessageCenter'

const {
  items,
  total,
  unread,
  page,
  pageSize,
  status,
  type,
  loading,
  error,
  busy,
  selected,
  mobileReading,
  load,
  select,
  markRead,
  markAllRead,
  open,
} = useMessageCenter()
const statuses = [
  { value: 'unread' as const, label: '未读' },
  { value: 'all' as const, label: '全部' },
  { value: 'read' as const, label: '已读' },
]
const statusLabel = computed(() => statuses.find((option) => option.value === status.value)?.label)
const typeOptions = [
  { value: '', label: '全部类型' },
  ...Object.entries(MESSAGE_TYPE_LABELS).map(([value, label]) => ({ value, label })),
]
</script>

<style scoped src="./styles/message-center.css"></style>
