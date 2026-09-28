<template>
  <a-drawer
    :open="open"
    title="版本历史"
    width="560"
    @close="emit('update:open', false)"
  >
    <p class="history-hint">
      已建任务固定使用创建时的版本；已下线版本仍可被这些任务解析，但不再作为当前版本。
    </p>
    <p
      v-if="items.length === 0"
      class="history-empty"
    >
      暂无版本记录
    </p>
    <ul
      v-else
      class="history-list"
    >
      <li
        v-for="item in items"
        :key="item.version ?? item.id ?? 'builtin'"
        class="history-item"
      >
        <div class="history-head">
          <span class="history-version">{{ item.version || UNKNOWN_TEXT }}</span>
          <a-tag :color="sourceColor(item.source)">
            {{ item.source ? VERSION_SOURCE_LABEL[item.source] : UNKNOWN_TEXT }}
          </a-tag>
          <a-tag
            v-if="item.is_current"
            color="blue"
          >
            当前版本
          </a-tag>
          <span class="history-spacer" />
          <a-button
            v-if="item.version"
            size="small"
            class="export-btn"
            :loading="exporting === item.version"
            @click="handleExport(item.version)"
          >
            导出
          </a-button>
          <a-popconfirm
            v-if="canRetire && item.source === 'published' && !item.is_current && item.version"
            title="确认下线该版本？下线后不能再作为当前版本，已建任务不受影响。"
            ok-text="下线"
            cancel-text="取消"
            @confirm="handleRetire(item.version)"
          >
            <a-button
              size="small"
              danger
              class="retire-btn"
              :loading="retiring === item.version"
            >
              下线
            </a-button>
          </a-popconfirm>
        </div>
        <div class="history-meta">
          <template v-if="item.source === 'builtin'">
            系统内置版本，无发布人
          </template>
          <template v-else>
            发布人 {{ item.published_by || UNKNOWN_TEXT }} · 发布时间 {{ formatDateTime(item.published_at) }}
            <template v-if="item.source === 'retired'">
              · 下线人 {{ item.retired_by || UNKNOWN_TEXT }} · 下线时间 {{ formatDateTime(item.retired_at) }}
            </template>
          </template>
        </div>
        <div class="history-counts">
          开启 {{ item.active_count }} · 暂停 {{ item.paused_count }} · 下线 {{ item.offline_count }} · 删除 {{ item.deleted_count }}
          <template v-if="item.base_version">
            · 派生自 {{ item.base_version }}
          </template>
        </div>
        <div
          v-if="item.note"
          class="history-note"
        >
          {{ item.note }}
        </div>
      </li>
    </ul>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  exportRuleSetVersion,
  retireRuleSetVersion,
  type RuleSetVersionItem,
  type RuleSetVersionSource,
} from '@/api/ruleSetVersions'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  UNKNOWN_TEXT,
  VERSION_SOURCE_LABEL,
  describeFailure,
  formatDateTime,
  needsRefresh,
} from '../ruleSetVersionModel'

const props = defineProps<{
  open: boolean
  ruleSetKey: string
  items: RuleSetVersionItem[]
  /** 可版本化规则集且当前角色可写时为 true。 */
  canRetire: boolean
}>()

const emit = defineEmits<{
  (event: 'update:open', value: boolean): void
  (event: 'refresh'): void
}>()

const retiring = ref<string | null>(null)
const exporting = ref<string | null>(null)

function sourceColor(source: RuleSetVersionSource | null): string {
  if (source === 'published') return 'green'
  if (source === 'builtin') return 'purple'
  return 'default'
}

async function handleRetire(version: string) {
  retiring.value = version
  try {
    const result = await retireRuleSetVersion(props.ruleSetKey, version)
    if (result.success) {
      message.success(`版本 ${version} 已下线`)
      emit('refresh')
      return
    }
    message.warning(describeFailure(result, '下线版本失败'))
    if (needsRefresh(result)) emit('refresh')
  } finally {
    retiring.value = null
  }
}

async function handleExport(version: string) {
  if (exporting.value) return
  exporting.value = version
  const result = await exportRuleSetVersion(props.ruleSetKey, version)
  exporting.value = null
  if (!result.success || !result.data) {
    message.error(result.message || '导出规则集版本失败')
    return
  }
  downloadBlob(result.data, `${props.ruleSetKey}-${version}.xlsx`)
}
</script>

<style scoped lang="less">
.history-hint {
  margin: 0 0 16px;
  color: #666666;
  font-size: 13px;
}

.history-empty {
  color: #999999;
}

.history-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  padding: 12px 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  background: #ffffff;

  .history-head {
    display: flex;
    align-items: center;
    gap: 8px;

    .history-version {
      font-size: 15px;
      font-weight: 600;
      color: #333333;
    }

    .history-spacer {
      flex: 1;
    }
  }

  .history-meta,
  .history-counts {
    margin-top: 6px;
    font-size: 12px;
    color: #666666;
  }

  .history-note {
    margin-top: 6px;
    font-size: 13px;
    color: #333333;
    white-space: pre-wrap;
  }
}
</style>
