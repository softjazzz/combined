<template>
  <section
    class="custom-draft-panel"
    aria-labelledby="custom-draft-title"
  >
    <div class="panel-heading">
      <div>
        <h3 id="custom-draft-title">
          自定义质控点草稿
        </h3>
        <span v-if="total !== null">共 {{ total }} 条，仅显示本人创建且未上线的草稿</span>
      </div>
      <div class="panel-actions">
        <button
          type="button"
          class="secondary-button"
          data-testid="custom-draft-refresh"
          :disabled="loading || busy"
          @click="refresh"
        >
          刷新
        </button>
        <a-popconfirm
          v-if="canManage"
          :title="`确认上线所选 ${selectedIds.length} 个草稿？任一草稿校验失败时整批不上线。`"
          ok-text="上线"
          cancel-text="取消"
          @confirm="publishSelected"
        >
          <button
            type="button"
            class="primary-button"
            data-testid="custom-draft-batch-publish"
            :disabled="selectedIds.length === 0 || busy || resultUnknown"
          >
            {{ publishing ? '正在上线' : '批量上线' }}
          </button>
        </a-popconfirm>
      </div>
    </div>

    <a-alert
      v-if="resultUnknown"
      type="warning"
      show-icon
      data-testid="custom-draft-result-unknown"
      message="上次操作结果无法确认"
      description="请先刷新列表核对草稿状态，勿盲目重复提交。"
    />
    <a-alert
      v-else-if="notice"
      :type="noticeType"
      show-icon
      data-testid="custom-draft-notice"
      :message="notice"
    />

    <div
      v-if="loading"
      class="list-state"
      role="status"
    >
      正在读取草稿
    </div>
    <div
      v-else-if="loadError"
      class="list-state is-error"
      role="alert"
    >
      {{ loadError }}
    </div>
    <div
      v-else-if="drafts.length === 0"
      class="list-state"
    >
      暂无未上线的自定义草稿
    </div>
    <div
      v-else
      class="draft-table-wrap"
    >
      <table>
        <thead>
          <tr>
            <th
              v-if="canManage"
              class="select-col"
            >
              <span class="sr-only">选择</span>
            </th>
            <th>编码 / 名称</th>
            <th>大类 / 类型</th>
            <th>文书</th>
            <th>测试证明</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="draft in drafts"
            :key="draft.id"
            :data-id="draft.id"
          >
            <td
              v-if="canManage"
              class="select-col"
            >
              <input
                type="checkbox"
                :data-testid="`custom-draft-select-${draft.id}`"
                :aria-label="`选择 ${draft.rule_code}`"
                :checked="selectedIds.includes(draft.id)"
                :disabled="draft.publish_ready !== true || busy"
                :title="draft.publish_ready === true ? '' : '需先完成当前版本的固定测试病历验证'"
                @change="toggle(draft.id)"
              >
            </td>
            <td>
              <strong>{{ displayText(draft.rule_code) }}</strong>
              <span>{{ displayText(draft.name) }}</span>
            </td>
            <td>
              <strong>{{ displayText(draft.category) }}</strong>
              <span>{{ displayText(draft.rule_type) }}</span>
            </td>
            <td>{{ displayText(draft.document_type) }}</td>
            <td>
              <a-tag :color="proofTag(draft).color">
                {{ proofTag(draft).label }}
              </a-tag>
            </td>
            <td class="op-col">
              <button
                v-if="isBasicInfoDraft(draft)"
                type="button"
                class="text-button"
                :data-testid="`custom-draft-open-${draft.id}`"
                :disabled="busy"
                @click="openDraft(draft.id)"
              >
                {{ canManage ? '查看/编辑' : '查看' }}
              </button>
              <span
                v-else
                class="legacy-note"
              >旧草稿请在规则工作台查看</span>
              <a-popconfirm
                v-if="canManage"
                title="确认删除该草稿？删除后不能恢复。"
                ok-text="删除"
                cancel-text="取消"
                @confirm="removeDraft(draft)"
              >
                <button
                  type="button"
                  class="text-button danger"
                  :data-testid="`custom-draft-delete-${draft.id}`"
                  :disabled="busy || resultUnknown"
                >
                  {{ deletingId === draft.id ? '正在删除' : '删除' }}
                </button>
              </a-popconfirm>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-if="total !== null && total > PAGE_SIZE"
      class="pagination-row"
    >
      <button
        type="button"
        :disabled="page <= 1 || loading || busy"
        @click="changePage(page - 1)"
      >
        上一页
      </button>
      <span>第 {{ page }} 页</span>
      <button
        type="button"
        :disabled="page * PAGE_SIZE >= total || loading || busy"
        @click="changePage(page + 1)"
      >
        下一页
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  deleteWorkspaceDraftChecked,
  listWorkspaceDrafts,
  publishWorkspaceDraftsBatch,
} from '@/services/custom-rule-workspace-service'
import type { CustomRuleDraft } from '@/types/custom-rule-workspace'

const props = defineProps<{
  /** 当前操作人标识；变化时丢弃旧响应并重新读取。 */
  actorKey: string
  canManage: boolean
}>()

const PAGE_SIZE = 20
const router = useRouter()
const drafts = ref<CustomRuleDraft[]>([])
const total = ref<number | null>(null)
const page = ref(1)
const loading = ref(false)
const loadError = ref('')
const selectedIds = ref<string[]>([])
const publishing = ref(false)
const deletingId = ref('')
const resultUnknown = ref(false)
const notice = ref('')
const noticeType = ref<'success' | 'warning' | 'error'>('success')
const busy = computed(() => publishing.value || Boolean(deletingId.value))
let revision = 0
let disposed = false

const PROOF_LABEL: Record<string, string> = {
  not_tested: '未测试',
  draft_changed: '草稿已修改，需重测',
  draft_not_executable: '条件未配置',
  validation_incomplete: '测试未通过',
}

function displayText(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : '未知'
}
function isBasicInfoDraft(draft: CustomRuleDraft) {
  const basic = draft.check_logic?.basic_info
  return Boolean(basic && typeof basic === 'object' && !Array.isArray(basic)
    && (basic as Record<string, unknown>).version === 1)
}
function proofTag(draft: CustomRuleDraft) {
  if (draft.publish_ready === true) return { label: '可上线', color: 'green' }
  if (draft.publish_ready !== false) return { label: '未知', color: 'default' }
  return { label: PROOF_LABEL[draft.publish_blocked_reason || ''] || '不可上线', color: 'orange' }
}
function validationId(draft: CustomRuleDraft) {
  const value = draft.last_test_summary?.validation_id
  return typeof value === 'string' && value.trim() ? value : ''
}
function validListPayload(value: unknown): value is { items: CustomRuleDraft[]; total: number; page: number } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const data = value as Record<string, unknown>
  return Array.isArray(data.items) && Number.isInteger(data.total) && Number(data.total) >= 0
    && Number.isInteger(data.page) && Number(data.page) >= 1
    && data.items.every((item) => Boolean(item) && typeof item === 'object'
      && typeof (item as Record<string, unknown>).id === 'string'
      && typeof (item as Record<string, unknown>).updated_at === 'string'
      && (item as Record<string, unknown>).status === 'draft')
}

async function load() {
  if (!props.actorKey) return
  const request = ++revision
  const actor = props.actorKey
  loading.value = true
  loadError.value = ''
  drafts.value = []
  total.value = null
  selectedIds.value = []
  const result = await listWorkspaceDrafts({ status: 'draft', page: page.value, page_size: PAGE_SIZE })
  if (disposed || request !== revision || actor !== props.actorKey) return
  loading.value = false
  if (!result.success || !validListPayload(result.data)) {
    loadError.value = result.message || '草稿列表回执格式异常'
    return
  }
  drafts.value = result.data.items
  total.value = result.data.total
  page.value = result.data.page
}

function refresh() {
  if (busy.value) return
  resultUnknown.value = false
  notice.value = ''
  void load()
}
function changePage(next: number) {
  if (next < 1 || loading.value || busy.value) return
  page.value = next
  void load()
}
function toggle(draftId: string) {
  selectedIds.value = selectedIds.value.includes(draftId)
    ? selectedIds.value.filter((id) => id !== draftId)
    : [...selectedIds.value, draftId]
}
function openDraft(draftId: string) {
  void router.push({ path: '/dashboard/quality-control/create', query: { draftId } })
}
function setNotice(type: 'success' | 'warning' | 'error', text: string) {
  noticeType.value = type
  notice.value = text
}

async function publishSelected() {
  if (!props.canManage || busy.value || resultUnknown.value || selectedIds.value.length === 0) return
  const selected = drafts.value.filter((draft) => selectedIds.value.includes(draft.id))
  const items = selected.map((draft) => ({
    draft_id: draft.id, expected_updated_at: draft.updated_at, validation_id: validationId(draft),
  }))
  if (selected.length !== selectedIds.value.length || items.some((item) => !item.validation_id)) {
    setNotice('warning', '所选草稿缺少有效测试证明，请刷新后重新选择')
    return
  }
  const request = revision
  const actor = props.actorKey
  publishing.value = true
  notice.value = ''
  const result = await publishWorkspaceDraftsBatch(items)
  if (disposed || request !== revision || actor !== props.actorKey) return
  publishing.value = false
  if (result.success === false) {
    resultUnknown.value = result.resultUnknown
    setNotice(result.conflict ? 'warning' : 'error', result.message)
    if (!result.resultUnknown) await load()
    return
  }
  setNotice('success', `已上线 ${result.data.length} 个质控点：${result.data.map((item) => item.rule_code).join('、')}`)
  page.value = 1
  await load()
}

async function removeDraft(draft: CustomRuleDraft) {
  if (!props.canManage || busy.value || resultUnknown.value) return
  const request = revision
  const actor = props.actorKey
  deletingId.value = draft.id
  notice.value = ''
  const result = await deleteWorkspaceDraftChecked(draft.id, draft.updated_at)
  if (disposed || request !== revision || actor !== props.actorKey) return
  deletingId.value = ''
  if (result.success === false) {
    resultUnknown.value = result.resultUnknown
    setNotice(result.conflict ? 'warning' : 'error', result.message)
    if (!result.resultUnknown) await load()
    return
  }
  setNotice('success', `草稿 ${draft.rule_code} 已删除`)
  if (drafts.value.length === 1 && page.value > 1) page.value -= 1
  await load()
}

watch(() => props.actorKey, () => {
  revision += 1
  publishing.value = false
  deletingId.value = ''
  resultUnknown.value = false
  notice.value = ''
  page.value = 1
  void load()
})
onMounted(() => { void load() })
onUnmounted(() => { disposed = true; revision += 1 })
</script>

<style scoped>
.custom-draft-panel { margin-top: 20px; padding: 18px 20px; border: 1px solid rgba(0, 0, 0, .08); border-radius: 8px; background: #fff; box-shadow: 0 4px 18px rgba(38, 58, 86, .04); }
.panel-heading, .panel-actions, .pagination-row { display: flex; align-items: center; gap: 12px; }
.panel-heading { justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; }
.panel-heading h3 { display: inline; margin: 0; font-size: 16px; line-height: 22px; font-weight: 600; }
.panel-heading span { margin-left: 10px; color: rgba(29, 29, 31, .6); font-size: 13px; }
.custom-draft-panel :deep(.ant-alert) { margin-bottom: 12px; }
button { min-height: 32px; border-radius: 8px; font: inherit; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .55; }
.primary-button { padding: 0 14px; border: 1px solid #007aff; background: #007aff; color: #fff; }
.secondary-button { padding: 0 12px; border: 1px solid rgba(0, 0, 0, .12); background: #fff; color: #1d1d1f; }
.text-button { min-height: 28px; padding: 0 6px; border: 0; background: transparent; color: #007aff; }
.text-button.danger { color: #d92d20; }
.legacy-note { color: rgba(29, 29, 31, .5); font-size: 13px; }
.draft-table-wrap { max-width: 100%; overflow-x: auto; }
table { width: 100%; min-width: 820px; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 10px 12px; border-bottom: 1px solid rgba(0, 0, 0, .07); text-align: left; overflow-wrap: anywhere; font-size: 14px; vertical-align: top; }
th { background: #f7f8fa; color: rgba(29, 29, 31, .6); font-weight: 500; }
td strong, td span { display: block; }
td span { margin-top: 3px; color: rgba(29, 29, 31, .6); }
.select-col { width: 48px; }
.op-col { white-space: nowrap; }
.list-state { padding: 26px 12px; text-align: center; color: rgba(29, 29, 31, .6); }
.list-state.is-error { color: #b42318; }
.pagination-row { justify-content: flex-end; margin-top: 12px; }
.pagination-row button { padding: 0 12px; border: 1px solid rgba(0, 0, 0, .12); background: #fff; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
</style>
