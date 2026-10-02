<template>
  <section class="draft-panel">
    <div class="draft-header">
      <div class="draft-title">
        <span class="title-text">待发布草稿</span>
        <a-tag color="blue">
          基于版本 {{ draft.base_version }}
        </a-tag>
        <span class="draft-meta">修订号 {{ draft.version_seq }} · 创建人 {{ draft.created_by || UNKNOWN_TEXT }} · 创建时间
          {{ formatDateTime(draft.created_at) }}</span>
      </div>
      <div
        class="draft-actions"
      >
        <a-button
          class="export-btn"
          :loading="exporting"
          :disabled="discarding || publishing"
          @click="handleExport"
        >
          导出草稿
        </a-button>
        <template v-if="canWrite">
        <a-popconfirm
          title="确认放弃该草稿？草稿中的全部改动将被删除。"
          ok-text="放弃"
          cancel-text="取消"
          @confirm="handleDiscard"
        >
          <a-button
            class="discard-btn"
            :loading="discarding"
            :disabled="publishing"
          >
            放弃草稿
          </a-button>
        </a-popconfirm>
        <a-button
          type="primary"
          class="publish-btn"
          :disabled="discarding || diff?.length === 0"
          @click="openPublish"
        >
          发布新版本
        </a-button>
        </template>
      </div>
    </div>

    <a-alert
      v-if="draft.base_version !== currentVersion"
      type="warning"
      show-icon
      class="draft-alert"
      :message="`草稿基于版本 ${draft.base_version}，当前生效版本已是 ${currentVersion}；发布前请核对差异。`"
    />

    <div class="diff-body">
      <p
        v-if="diff === null"
        class="diff-empty"
      >
        基础版本内容读取失败，差异未知。
      </p>
      <p
        v-else-if="diff.length === 0"
        class="diff-empty"
      >
        草稿与基础版本无差异，修改质控点状态后可发布。
      </p>
      <ul
        v-else
        class="diff-list"
      >
        <li
          v-for="item in diff"
          :key="item.rule_id"
          class="diff-item"
        >
          <span class="diff-rule-id">{{ item.rule_id }}</span>
          <span class="diff-rule-name">{{ item.name || UNKNOWN_TEXT }}</span>
          <span class="diff-change">
            <a-tag v-if="item.coreChanged">核心制度归属变更</a-tag>
            <a-tag v-if="item.classificationChanged">缺陷分类变更</a-tag>
            <a-tag :color="item.from ? ENTRY_STATE_COLOR[item.from] : 'default'">
              {{ item.from ? ENTRY_STATE_LABEL[item.from] : '不在基础版本' }}
            </a-tag>
            <span class="diff-arrow">→</span>
            <a-tag :color="item.to ? ENTRY_STATE_COLOR[item.to] : 'default'">
              {{ item.to ? ENTRY_STATE_LABEL[item.to] : '不在草稿' }}
            </a-tag>
          </span>
        </li>
      </ul>
    </div>

    <a-modal
      :open="publishOpen"
      title="发布新版本"
      :footer="null"
      :mask-closable="false"
      @cancel="closePublish"
    >
      <div class="publish-form">
        <p class="publish-hint">
          发布后新建任务使用新版本；已建任务继续使用冻结时的版本。
        </p>
        <label class="field-label">版本号</label>
        <a-input
          v-model:value="versionInput"
          class="version-input"
          placeholder="如 2026-09-27.1，仅限字母、数字、点、下划线和连字符"
          :maxlength="64"
        />
        <label class="field-label">发布说明</label>
        <a-textarea
          v-model:value="noteInput"
          class="note-input"
          placeholder="说明本次上线、暂停或下线的原因（选填）"
          :rows="3"
          :maxlength="1000"
        />
        <a-alert
          v-if="problems.length"
          type="error"
          show-icon
          class="publish-problems"
          message="发布校验未通过"
        >
          <template #description>
            <ul class="problem-list">
              <li
                v-for="problem in problems"
                :key="problem"
              >
                {{ problem }}
              </li>
            </ul>
          </template>
        </a-alert>
        <p
          v-if="publishError"
          class="publish-error"
        >
          {{ publishError }}
        </p>
        <div class="publish-footer">
          <a-button
            class="publish-cancel"
            @click="closePublish"
          >
            取消
          </a-button>
          <a-button
            type="primary"
            class="publish-submit"
            :loading="publishing"
            @click="handlePublish"
          >
            确认发布
          </a-button>
        </div>
      </div>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { deleteRuleSetDraft, exportRuleSetDraft, publishRuleSetDraft, type RuleSetDraft } from '@/api/ruleSetVersions'
import { downloadBlob } from '@/views/workstation-v4/customer-sample-validation/batchExport'
import {
  ENTRY_STATE_COLOR,
  ENTRY_STATE_LABEL,
  UNKNOWN_TEXT,
  describeFailure,
  formatDateTime,
  needsRefresh,
  type EntryDiffItem,
} from '../ruleSetVersionModel'

const props = defineProps<{
  ruleSetKey: string
  draft: RuleSetDraft
  /** 与基础版本的差异；null 表示基础版本读取失败。 */
  diff: EntryDiffItem[] | null
  currentVersion: string
  canWrite: boolean
}>()

const emit = defineEmits<{
  (event: 'refresh'): void
}>()

const VERSION_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/

const discarding = ref(false)
const exporting = ref(false)
const publishing = ref(false)
const publishOpen = ref(false)
const versionInput = ref('')
const noteInput = ref('')
const problems = ref<string[]>([])
const publishError = ref('')

function openPublish() {
  versionInput.value = ''
  noteInput.value = props.draft.note ?? ''
  problems.value = []
  publishError.value = ''
  publishOpen.value = true
}

function closePublish() {
  if (publishing.value) return
  publishOpen.value = false
}

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  const result = await exportRuleSetDraft(props.ruleSetKey)
  exporting.value = false
  if (!result.success || !result.data) {
    message.error(result.message || '导出规则集草稿失败')
    return
  }
  downloadBlob(result.data, `${props.ruleSetKey}-draft-v${props.draft.version_seq}.xlsx`)
}

async function handleDiscard() {
  discarding.value = true
  try {
    const result = await deleteRuleSetDraft(props.ruleSetKey, props.draft.version_seq)
    if (result.success) {
      message.success('已放弃草稿')
      emit('refresh')
      return
    }
    message.warning(describeFailure(result, '放弃草稿失败'))
    if (needsRefresh(result) || result.status === 404) emit('refresh')
  } finally {
    discarding.value = false
  }
}

async function handlePublish() {
  const version = versionInput.value.trim()
  problems.value = []
  publishError.value = ''
  if (!VERSION_PATTERN.test(version)) {
    publishError.value = '版本号只能包含字母、数字、点、下划线和连字符，且以字母或数字开头，最长 64 个字符'
    return
  }
  publishing.value = true
  try {
    const result = await publishRuleSetDraft(props.ruleSetKey, {
      version,
      note: noteInput.value.trim() || null,
      version_seq: props.draft.version_seq,
    })
    if (result.success) {
      publishOpen.value = false
      message.success(`已发布版本 ${version}，新建任务将使用该版本`)
      emit('refresh')
      return
    }
    if (result.status === 422) {
      problems.value = result.problems?.length ? result.problems : [result.message || '发布校验未通过']
      return
    }
    publishError.value = describeFailure(result, '发布失败')
    if (result.status === undefined || result.status >= 500 || (result.status >= 200 && result.status < 300)) {
      publishOpen.value = false
      message.warning('发布结果未确认，已刷新规则集版本，请核对当前版本后再操作')
      emit('refresh')
      return
    }
    if (needsRefresh(result) || result.status === 404) {
      publishOpen.value = false
      message.warning(publishError.value)
      emit('refresh')
    }
  } finally {
    publishing.value = false
  }
}
</script>

<style scoped lang="less">
.draft-panel {
  background: #ffffff;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  padding: 16px 24px;
  margin-bottom: 16px;

  .draft-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .draft-title {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;

    .title-text {
      font-size: 16px;
      font-weight: 600;
      color: #333333;
    }

    .draft-meta {
      font-size: 12px;
      color: #999999;
    }
  }

  .draft-actions {
    display: flex;
    gap: 8px;

    .publish-btn {
      background: #2b6cf6;
      border-color: #2b6cf6;
    }
  }

  .draft-alert {
    margin-top: 12px;
  }

  .diff-body {
    margin-top: 12px;
  }

  .diff-empty {
    margin: 0;
    color: #999999;
    font-size: 13px;
  }

  .diff-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 8px;
  }

  .diff-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: #fafafa;
    border: 1px solid #f0f0f0;
    border-radius: 6px;
    min-width: 0;

    .diff-rule-id {
      font-weight: 500;
      color: #333333;
      white-space: nowrap;
    }

    .diff-rule-name {
      flex: 1;
      min-width: 0;
      color: #666666;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .diff-change {
      display: flex;
      align-items: center;
      white-space: nowrap;

      .diff-arrow {
        margin-right: 8px;
        color: #999999;
      }
    }
  }
}

.publish-form {
  display: flex;
  flex-direction: column;
  gap: 8px;

  .publish-hint {
    margin: 0 0 8px;
    color: #666666;
    font-size: 13px;
  }

  .field-label {
    font-weight: 500;
    color: #333333;
  }

  .problem-list {
    margin: 0;
    padding-left: 18px;
  }

  .publish-error {
    margin: 0;
    color: #ff4d4f;
  }

  .publish-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;
  }
}
</style>
