<template>
  <section
    class="mq-page message-center"
    :class="{ 'message-center--reading': mobileReading }"
    aria-label="消息中心"
  >
    <header class="mq-page-head">
      <div class="mq-page-head__copy">
        <span class="mq-page-eyebrow">质控作业 · 消息与反馈</span>
        <h1 class="mq-page-title">消息中心</h1>
      </div>
      <div class="mq-page-head__actions">
        <nav class="mq-segmented" aria-label="消息阅读状态">
          <button
            v-for="option in statuses"
            :key="option.value"
            type="button"
            class="mq-segmented__item"
            :class="{ 'is-active': status === option.value }"
            :aria-pressed="status === option.value"
            :disabled="!!busy"
            @click="setStatus(option.value)"
          >
            {{ option.label }}
          </button>
        </nav>
        <span class="mq-status" :class="unread ? 'mq-status--info' : ''"
          >未读 {{ unread ?? '—' }}</span
        >
        <a-tooltip title="刷新消息"
          ><a-button
            shape="circle"
            class="message-center__refresh"
            aria-label="刷新消息"
            :loading="loading"
            @click="load"
            ><template #icon><MqIcon name="sync" :size="16" /></template></a-button
        ></a-tooltip>
      </div>
    </header>

    <a-alert v-if="error" type="error" show-icon :message="error" class="message-center__error">
      <template #action><a-button size="small" @click="load">重试</a-button></template>
    </a-alert>

    <section class="mq-card message-center__workspace" :aria-busy="loading" aria-label="消息收件箱">
      <div class="message-center__list-pane">
        <div class="message-center__list-heading">
          <div class="message-center__list-title">
            <h2>{{ statusLabel }}消息</h2>
            <span class="message-center__total">{{ loading || error ? '—' : total }} 条</span>
          </div>
          <a-tooltip title="全部标为已读">
            <a-button
              type="text"
              shape="circle"
              class="message-center__refresh"
              aria-label="全部标为已读"
              :disabled="loading || !!busy || !!error || !unread"
              :loading="busy === '*'"
              @click="markAllRead"
              ><template #icon><MqIcon name="success" :size="18" /></template
            ></a-button>
          </a-tooltip>
        </div>
        <div class="message-center__filters">
          <a-select
            v-model:value="type"
            aria-label="消息类型"
            class="message-center__type"
            :options="typeOptions"
            :disabled="!!busy"
          />
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
                <MqIconTile
                  :name="messageIcon(item)"
                  :tone="!item.is_read ? 'brand' : 'neutral'"
                  :size="32"
                />
                <span class="message-center__row-copy">
                  <span class="message-center__row-top">
                    <span class="message-center__category">{{ messageTypeLabel(item) }}</span>
                    <span
                      v-if="!item.is_read"
                      class="message-center__dot"
                      role="img"
                      aria-label="未读"
                    />
                  </span>
                  <span class="message-center__subject">{{ item.title }}</span>
                  <span class="message-center__excerpt">{{ item.content }}</span>
                  <time :datetime="item.created_at">{{ messageTime(item.created_at, item.type) }}</time>
                </span>
              </button>
            </li>
          </ul>
          <div v-else class="message-center__empty">
            <MqIconTile name="pool" :size="48" />
            <strong>{{ emptyTitle }}</strong>
            <a-button
              v-if="!loading && !error && hasActiveFilter"
              data-testid="message-center-reset-filters"
              @click="resetFilters"
              >重置筛选</a-button
            >
            <a-button
              v-else-if="!loading && !error && status === 'unread'"
              data-testid="message-center-view-all"
              @click="setStatus('all')"
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
          ><MqIcon name="back" :size="16" />返回列表</a-button
        >
        <template v-if="selected">
          <div class="message-center__detail-head">
            <MqIconTile :name="messageIcon(selected)" tone="brand" :size="44" />
            <div class="message-center__detail-meta">
              <span>{{ messageTypeLabel(selected) }}</span>
              <span class="mq-status" :class="!selected.is_read ? 'mq-status--info' : ''">{{
                selected.is_read ? '已读' : '未读'
              }}</span>
            </div>
            <a-button
              v-if="!selected.is_read"
              class="message-center__command message-center__read"
              :disabled="loading || !!busy || !!error"
              :loading="busy === selected.id"
              @click="markRead(selected)"
              ><MqIcon v-if="busy !== selected.id" name="success" :size="16" />标为已读</a-button
            >
          </div>
          <h2>{{ selected.title }}</h2>
          <time :datetime="selected.created_at"
            >接收于 {{ messageTime(selected.created_at, selected.type) }} · 北京时间</time
          >
          <div class="message-center__body-label">消息内容</div>
          <div class="message-center__body">{{ selected.content }}</div>
          <div class="message-center__detail-actions">
            <a-button
              class="message-center__command"
              v-if="selected.interaction_target"
              type="primary"
              :disabled="loading || !!busy || !!error"
              @click="open(selected)"
              >{{ messageActionLabel(selected) }}<ChevronRight :size="16"
            /></a-button>
          </div>
          <p v-if="!selected.interaction_target" class="message-center__unlinked">
            该消息未提供精确处理对象。
          </p>
        </template>
        <div v-else class="message-center__empty">
          <MqIconTile name="doc" :size="56" /><span>暂无选中的消息</span>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import MqIcon from '@/components/icons/MqIcon.vue'
import MqIconTile from '@/components/icons/MqIconTile.vue'
import type { MqIconName } from '@/components/icons/mqIcons'
import type { NotificationVM } from '@/views/workstation-v4/types'
import {
  isAccountRegistrationNotification,
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
  hasActiveFilter,
  loading,
  error,
  busy,
  selected,
  mobileReading,
  load,
  setStatus,
  resetFilters,
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
const emptyTitle = computed(() => {
  if (loading.value) return '正在读取消息'
  if (error.value) return '消息暂不可用'
  if (hasActiveFilter.value) return '当前筛选条件下暂无匹配消息'
  if (status.value === 'unread' && (unread.value === 0 || unread.value === null)) {
    return '未读消息已处理完毕'
  }
  return '暂无消息'
})
const typeOptions = [
  { value: '', label: '全部类型' },
  ...Object.entries(MESSAGE_TYPE_LABELS).map(([value, label]) => ({ value, label })),
]
function messageIcon(item: NotificationVM): MqIconName {
  if (isAccountRegistrationNotification(item)) return 'settings'
  if (item.type === 'drg_alert') return 'drg'
  if (item.type === 'qc_result_ready') return 'fp_qc'
  if (item.type === 'system') return 'settings'
  if (item.type === 'task_assign') return 'task'
  return 'doc'
}
</script>

<style scoped src="./styles/message-center.css"></style>
<style scoped>
.message-center :deep(.ant-btn.message-center__refresh) {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  min-width: 36px;
  height: 36px;
  padding: 0;
  line-height: 1;
  box-sizing: border-box;
}

.message-center :deep(.ant-btn.message-center__refresh > span),
.message-center :deep(.ant-btn.message-center__refresh .mq-icon),
.message-center :deep(.ant-btn.message-center__refresh .ant-btn-loading-icon),
.message-center :deep(.ant-btn.message-center__refresh .anticon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  line-height: 1;
  transform: none;
}
</style>
