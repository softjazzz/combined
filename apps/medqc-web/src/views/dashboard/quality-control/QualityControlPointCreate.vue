<template>
  <div class="quality-control-point-create">
    <a-breadcrumb class="breadcrumb-nav">
      <a-breadcrumb-item><router-link to="/dashboard">首页</router-link></a-breadcrumb-item>
      <a-breadcrumb-item><router-link to="/dashboard/quality-control">非编码质控点管理</router-link></a-breadcrumb-item>
      <a-breadcrumb-item>新建质控点</a-breadcrumb-item>
    </a-breadcrumb>

    <header class="page-header">
      <div><h1>新建质控点</h1><p>基础信息草稿</p></div>
      <button class="secondary-button" type="button" title="刷新草稿" :disabled="listLoading" @click="refreshDrafts">
        <RefreshCw :size="15" aria-hidden="true" />刷新草稿
      </button>
    </header>

    <a-alert
      v-if="resultUnknown"
      type="warning"
      show-icon
      data-testid="draft-result-unknown"
      message="保存结果无法确认"
      description="请先刷新下方草稿列表核对，勿盲目重复提交。"
    />
    <a-alert
      v-else-if="formNotice"
      :type="formNoticeType"
      show-icon
      data-testid="draft-form-notice"
      :message="formNotice"
    />

    <main class="create-layout">
      <section class="editor-section" aria-labelledby="basic-info-title">
        <div class="section-heading">
          <div>
            <h2 id="basic-info-title">基础信息</h2>
            <span v-if="editingDraft" class="draft-code">{{ editingDraft.rule_code }}</span>
          </div>
          <button v-if="editingDraft" type="button" class="text-button" :disabled="conditionSaving" @click="startNewDraft">新建另一条</button>
        </div>

        <form class="basic-form" @submit.prevent="saveDraft">
          <label class="field field--wide">
            <span>质控点名称</span>
            <input v-model="form.name" data-testid="draft-name" maxlength="100" autocomplete="off" placeholder="请输入质控点名称" :disabled="formBusy" />
          </label>
          <label class="field">
            <span>质控大类</span>
            <input v-model="form.category" data-testid="draft-category" list="qc-point-category-options" maxlength="100" placeholder="请选择或输入" :disabled="formBusy" />
            <datalist id="qc-point-category-options"><option v-for="item in CATEGORY_OPTIONS" :key="item" :value="item" /></datalist>
          </label>
          <label class="field">
            <span>质控类型</span>
            <input v-model="form.rule_type" data-testid="draft-rule-type" list="qc-point-rule-type-options" maxlength="100" placeholder="请选择或输入" :disabled="formBusy" />
            <datalist id="qc-point-rule-type-options"><option v-for="item in RULE_TYPE_OPTIONS" :key="item" :value="item" /></datalist>
          </label>
          <label class="field field--wide">
            <span>质控文书</span>
            <select v-model="form.document_type" data-testid="draft-document" :disabled="formBusy || optionsLoading || documentOptions.length === 0">
              <option value="" disabled>{{ optionsLoading ? '正在读取文书目录' : '请选择' }}</option>
              <option v-for="item in documentOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
            <small v-if="optionsError" role="alert">{{ optionsError }}</small>
          </label>
          <div class="form-actions field--wide">
            <button class="primary-button" type="submit" data-testid="save-draft-basic-info" :disabled="formBusy || resultUnknown || editConflict || documentOptions.length === 0">
              {{ saving ? '正在保存' : editingDraft ? '保存修改' : '保存草稿' }}
            </button>
            <span class="scope-note">完成条件配置后进行固定病例测试</span>
          </div>
        </form>
      </section>

      <a-alert
        v-if="conditionNotice"
        :type="conditionNoticeType"
        show-icon
        data-testid="condition-notice"
        :message="conditionNotice"
      />
      <section v-if="editingDraft && conditionOptionsLoading" class="editor-section list-state" role="status">正在读取条件目录</section>
      <section v-else-if="editingDraft && conditionOptionsError" class="editor-section list-state is-error" role="alert">{{ conditionOptionsError }}</section>
      <section v-else-if="editingDraft && conditionLoading" class="editor-section list-state" role="status">正在读取条件配置</section>
      <VisualConditionEditor
        v-else-if="editingDraft && conditionOptions && conditionTree"
        :key="`${editingDraft.id}-${conditionEditorVersion}`"
        :model-value="conditionTree"
        :options="conditionOptions"
        :disabled="conditionSaving || conditionResultUnknown || conditionConflict || formBusy"
        @save="saveCondition"
        @dirty="conditionDirty = $event"
      />
      <FixedTestValidationPanel
        v-if="editingDraft"
        :key="`${editingDraft.id}-${actorKey}`"
        :draft-id="editingDraft.id"
        :draft-updated-at="editingDraft.updated_at"
        :actor-key="actorKey"
        :enabled="Boolean(conditionDraft?.visual_condition) && !basicInfoDirty && !conditionDirty && !conditionResultUnknown && !conditionConflict"
        @published="handlePublished"
        @refresh-drafts="refreshDrafts"
        @draft-updated="syncDraftUpdatedAt"
      />

      <section class="draft-section" aria-labelledby="recent-drafts-title">
        <div class="section-heading"><div><h2 id="recent-drafts-title">最近草稿</h2><span v-if="listTotal !== null">共 {{ listTotal }} 条</span></div></div>
        <div v-if="listLoading" class="list-state" role="status">正在读取草稿</div>
        <div v-else-if="listError" class="list-state is-error" role="alert">{{ listError }}</div>
        <div v-else-if="drafts.length === 0" class="list-state">暂无基础信息草稿</div>
        <div v-else class="draft-table-wrap">
          <table>
            <thead><tr><th>编码 / 名称</th><th>大类</th><th>类型</th><th>文书</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="draft in drafts" :key="draft.id">
                <td><strong>{{ displayText(draft.rule_code) }}</strong><span>{{ displayText(draft.name) }}</span></td>
                <td>{{ displayText(draft.category) }}</td>
                <td>{{ displayText(draft.rule_type) }}</td>
                <td>{{ displayText(draft.document_type) }}</td>
                <td>
                  <button v-if="isBasicInfoDraft(draft)" type="button" class="text-button" :data-testid="`open-draft-${draft.id}`" :disabled="detailLoadingId === draft.id || conditionSaving" @click="openDraft(draft.id)">
                    {{ detailLoadingId === draft.id ? '读取中' : '继续编辑' }}
                  </button>
                  <span v-else class="legacy-note">旧草稿不可在此编辑</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="listTotal !== null && listTotal > PAGE_SIZE" class="pagination-row">
          <button type="button" :disabled="listPage <= 1 || listLoading" @click="changePage(listPage - 1)">上一页</button>
          <span>第 {{ listPage }} 页</span>
          <button type="button" :disabled="listPage * PAGE_SIZE >= listTotal || listLoading" @click="changePage(listPage + 1)">下一页</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  createDraftBasicInfo, getDraftBasicInfo, getDraftBasicInfoOptions,
  getDraftCondition, getDraftConditionOptions, listWorkspaceDrafts,
  updateDraftBasicInfo, updateDraftCondition,
} from '@/services/custom-rule-workspace-service'
import VisualConditionEditor from './components/VisualConditionEditor.vue'
import FixedTestValidationPanel from './components/FixedTestValidationPanel.vue'
import type {
  CustomRuleDocumentOption, CustomRuleDraft, CustomRuleDraftBasicInfo, CustomRuleDraftBasicInfoInput,
  CustomRuleDraftCondition, VisualConditionOptions, VisualConditionTree,
} from '@/types/custom-rule-workspace'

const CATEGORY_OPTIONS = ['病历书写与管理基本规范', '诊疗规范', '医疗安全'] as const
const RULE_TYPE_OPTIONS = ['规范性', '完整性', '及时性'] as const
const PAGE_SIZE = 10
const authStore = useAuthStore()
const route = useRoute()
const documentOptions = ref<CustomRuleDocumentOption[]>([])
const optionsLoading = ref(false)
const optionsError = ref('')
const drafts = ref<CustomRuleDraft[]>([])
const listLoading = ref(false)
const listError = ref('')
const listTotal = ref<number | null>(null)
const listPage = ref(1)
const detailLoadingId = ref('')
const editingDraft = ref<CustomRuleDraftBasicInfo | null>(null)
const conditionOptions = ref<VisualConditionOptions | null>(null)
const conditionOptionsLoading = ref(false)
const conditionOptionsError = ref('')
const conditionDraft = ref<CustomRuleDraftCondition | null>(null)
const conditionTree = ref<VisualConditionTree | null>(null)
const conditionLoading = ref(false)
const conditionSaving = ref(false)
const conditionResultUnknown = ref(false)
const conditionConflict = ref(false)
const conditionNotice = ref('')
const conditionNoticeType = ref<'success' | 'error' | 'warning'>('success')
const conditionEditorVersion = ref(0)
const conditionDirty = ref(false)
const saving = ref(false)
const resultUnknown = ref(false)
const editConflict = ref(false)
const formNotice = ref('')
const formNoticeType = ref<'success' | 'error' | 'warning'>('success')
const form = reactive<CustomRuleDraftBasicInfoInput>({ name: '', category: '', rule_type: '', document_type: '' })
let mounted = false
let disposed = false
let contextRevision = 0
let detailRevision = 0
let listRevision = 0
let conditionRevision = 0

const actorKey = computed(() => {
  const owner = String(authStore.user?.id || authStore.user?.email || '').trim()
  const roles = Array.isArray(authStore.userRoles) ? [...authStore.userRoles].sort() : []
  return `${owner}|${roles.join(',')}`
})
const canManage = computed(() => {
  const roles = Array.isArray(authStore.userRoles) ? authStore.userRoles : []
  return roles.some((role) => role === 'admin' || role === 'qc_manager')
})
const formBusy = computed(() => saving.value || conditionSaving.value || Boolean(detailLoadingId.value) || !canManage.value)
const basicInfoDirty = computed(() => Boolean(editingDraft.value) && (
  form.name.trim() !== editingDraft.value?.name
  || form.category.trim() !== editingDraft.value?.category
  || form.rule_type.trim() !== editingDraft.value?.rule_type
  || form.document_type.trim() !== editingDraft.value?.document_type
))

function displayText(value: unknown) { return typeof value === 'string' && value.trim() ? value : '未知' }
function isBasicInfoDraft(draft: CustomRuleDraft) {
  const basic = draft.check_logic?.basic_info
  return Boolean(basic && typeof basic === 'object' && !Array.isArray(basic) && (basic as Record<string, unknown>).version === 1)
}
function contextCurrent(revision: number, actor: string) { return !disposed && revision === contextRevision && actor === actorKey.value }
function clearForm() {
  Object.assign(form, { name: '', category: '', rule_type: '', document_type: '' })
  editingDraft.value = null
  editConflict.value = false
  formNotice.value = ''
}
function emptyConditionTree(): VisualConditionTree {
  return {
    schema_version: 'visual-condition-v1', root_operator: 'all',
    groups: [{ id: `group-${Date.now()}`, operator: 'all', conditions: [] }],
  }
}
function clearCondition() {
  conditionRevision += 1
  conditionDraft.value = null
  conditionTree.value = null
  conditionLoading.value = false
  conditionSaving.value = false
  conditionResultUnknown.value = false
  conditionConflict.value = false
  conditionNotice.value = ''
  conditionDirty.value = false
  conditionEditorVersion.value += 1
}
function startNewDraft() {
  if (saving.value || conditionSaving.value) return
  detailRevision += 1
  detailLoadingId.value = ''
  clearCondition()
  clearForm()
}
function hydrateForm(draft: CustomRuleDraftBasicInfo) {
  editingDraft.value = draft
  Object.assign(form, { name: draft.name, category: draft.category, rule_type: draft.rule_type, document_type: draft.document_type })
  editConflict.value = false
  resultUnknown.value = false
  formNotice.value = ''
}
function validListPayload(value: unknown): value is { items: CustomRuleDraft[]; total: number; page: number; page_size: number } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const item = value as Record<string, unknown>
  return Array.isArray(item.items) && Number.isInteger(item.total) && Number(item.total) >= 0
    && Number.isInteger(item.page) && Number(item.page) >= 1 && item.page_size === PAGE_SIZE
    && item.items.every((draft) => Boolean(draft) && typeof draft === 'object'
      && typeof (draft as Record<string, unknown>).id === 'string'
      && typeof (draft as Record<string, unknown>).rule_code === 'string'
      && typeof (draft as Record<string, unknown>).name === 'string')
}
async function loadOptions(revision: number, actor: string) {
  optionsLoading.value = true
  optionsError.value = ''
  documentOptions.value = []
  const result = await getDraftBasicInfoOptions()
  if (!contextCurrent(revision, actor)) return
  optionsLoading.value = false
  if (!result.success || !result.data) {
    optionsError.value = result.message || '质控文书目录暂不可用'
    return
  }
  documentOptions.value = result.data.documents
}
async function loadConditionOptions(revision: number, actor: string) {
  conditionOptionsLoading.value = true
  conditionOptionsError.value = ''
  conditionOptions.value = null
  const result = await getDraftConditionOptions()
  if (!contextCurrent(revision, actor)) return
  conditionOptionsLoading.value = false
  if (!result.success || !result.data) {
    conditionOptionsError.value = result.message || '条件目录暂不可用'
    return
  }
  conditionOptions.value = result.data
}
async function loadCondition(draftId: string, revision = contextRevision, actor = actorKey.value) {
  const request = ++conditionRevision
  conditionLoading.value = true
  conditionNotice.value = ''
  conditionResultUnknown.value = false
  conditionConflict.value = false
  const result = await getDraftCondition(draftId)
  if (!contextCurrent(revision, actor) || request !== conditionRevision || editingDraft.value?.id !== draftId) return
  conditionLoading.value = false
  if (!result.success || !result.data) {
    conditionDraft.value = null
    conditionTree.value = null
    conditionNoticeType.value = 'error'
    conditionNotice.value = result.message || '读取条件配置失败'
    return
  }
  conditionDraft.value = result.data
  conditionTree.value = result.data.visual_condition ?? emptyConditionTree()
  conditionEditorVersion.value += 1
}
async function loadDrafts(revision = contextRevision, actor = actorKey.value) {
  const request = ++listRevision
  listLoading.value = true
  listError.value = ''
  drafts.value = []
  listTotal.value = null
  const result = await listWorkspaceDrafts({ status: 'draft', page: listPage.value, page_size: PAGE_SIZE })
  if (!contextCurrent(revision, actor) || request !== listRevision) return
  listLoading.value = false
  if (!result.success || !validListPayload(result.data)) {
    listError.value = result.message || '草稿列表回执格式异常'
    return
  }
  drafts.value = result.data.items
  listTotal.value = result.data.total
  listPage.value = result.data.page
}
/** 管理页“查看/编辑”通过 ?draftId= 进入；归属与状态仍由服务端校验。 */
function requestedDraftId() {
  const value = route?.query?.draftId
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}
async function initialize(revision: number, actor: string) {
  if (!canManage.value || !String(authStore.user?.id || authStore.user?.email || '').trim()) return
  await Promise.all([loadOptions(revision, actor), loadConditionOptions(revision, actor), loadDrafts(revision, actor)])
  const draftId = requestedDraftId()
  if (draftId && contextCurrent(revision, actor) && !editingDraft.value && !detailLoadingId.value) await openDraft(draftId)
}
function validateForm() {
  Object.assign(form, {
    name: form.name.trim(), category: form.category.trim(),
    rule_type: form.rule_type.trim(), document_type: form.document_type.trim(),
  })
  if (!form.name || !form.category || !form.rule_type || !form.document_type) return '请完整填写名称、大类、类型和文书'
  if (form.name.length > 100) return '质控点名称不能超过100个字符'
  if (form.category.length > 100 || form.rule_type.length > 100) return '大类或类型不能超过100个字符'
  if (!documentOptions.value.some((item) => item.value === form.document_type)) return '所选质控文书不在当前支持目录中'
  return ''
}
async function saveDraft() {
  if (formBusy.value || resultUnknown.value || editConflict.value) return
  if (conditionDirty.value) {
    formNoticeType.value = 'warning'
    formNotice.value = '条件配置尚未保存，请先保存条件配置后再修改基础信息'
    return
  }
  const error = validateForm()
  if (error) { formNoticeType.value = 'error'; formNotice.value = error; return }
  const revision = contextRevision
  const actor = actorKey.value
  const current = editingDraft.value
  saving.value = true
  formNotice.value = ''
  const result = current
    ? await updateDraftBasicInfo(current.id, { ...form, expected_updated_at: current.updated_at })
    : await createDraftBasicInfo({ ...form })
  if (!contextCurrent(revision, actor)) return
  saving.value = false
  if (result.success === false) {
    resultUnknown.value = result.resultUnknown
    editConflict.value = result.conflict
    formNoticeType.value = result.conflict ? 'warning' : 'error'
    formNotice.value = result.message
    return
  }
  clearCondition()
  hydrateForm(result.data)
  formNoticeType.value = 'success'
  formNotice.value = current ? '草稿基础信息已更新' : `草稿 ${result.data.rule_code} 已保存`
  listPage.value = 1
  await loadCondition(result.data.id, revision, actor)
  await loadDrafts(revision, actor)
}
async function openDraft(draftId: string) {
  if (saving.value || conditionSaving.value) return
  const revision = contextRevision
  const actor = actorKey.value
  const request = ++detailRevision
  detailLoadingId.value = draftId
  const result = await getDraftBasicInfo(draftId)
  if (!contextCurrent(revision, actor) || request !== detailRevision) return
  detailLoadingId.value = ''
  if (!result.success || !result.data) { formNoticeType.value = 'error'; formNotice.value = result.message || '读取草稿失败'; return }
  clearCondition()
  hydrateForm(result.data)
  if (!documentOptions.value.some((item) => item.value === result.data.document_type)) form.document_type = ''
  await loadCondition(result.data.id, revision, actor)
}
async function saveCondition(value: VisualConditionTree) {
  const current = conditionDraft.value
  const draftId = editingDraft.value?.id
  if (!canManage.value || formBusy.value || conditionResultUnknown.value || conditionConflict.value
    || !current || !draftId || current.id !== draftId || conditionSaving.value) return
  const revision = contextRevision
  const actor = actorKey.value
  const request = conditionRevision
  conditionSaving.value = true
  conditionNotice.value = ''
  const result = await updateDraftCondition(draftId, {
    expected_updated_at: current.updated_at,
    visual_condition: value,
  })
  if (!contextCurrent(revision, actor) || request !== conditionRevision || editingDraft.value?.id !== draftId) return
  conditionSaving.value = false
  if (result.success === false) {
    conditionResultUnknown.value = result.resultUnknown
    conditionConflict.value = result.conflict
    conditionNoticeType.value = result.conflict ? 'warning' : 'error'
    conditionNotice.value = result.message
    return
  }
  conditionDraft.value = result.data
  conditionTree.value = result.data.visual_condition
  if (editingDraft.value?.id === result.data.id) editingDraft.value = { ...editingDraft.value, updated_at: result.data.updated_at }
  conditionEditorVersion.value += 1
  conditionDirty.value = false
  conditionNoticeType.value = 'success'
  conditionNotice.value = '缺陷触发条件已保存'
}
function changePage(page: number) { if (page >= 1 && !listLoading.value) { listPage.value = page; void loadDrafts() } }
function refreshDrafts() {
  if (listLoading.value || !canManage.value) return
  void loadDrafts()
  if (optionsError.value) void loadOptions(contextRevision, actorKey.value)
  if (conditionOptionsError.value) void loadConditionOptions(contextRevision, actorKey.value)
}
function handlePublished() {
  clearCondition()
  clearForm()
  listPage.value = 1
  void loadDrafts()
}
function syncDraftUpdatedAt(updatedAt: string) {
  if (!editingDraft.value || !updatedAt || Number.isNaN(Date.parse(updatedAt))) return
  editingDraft.value = { ...editingDraft.value, updated_at: updatedAt }
  if (conditionDraft.value?.id === editingDraft.value.id) {
    conditionDraft.value = { ...conditionDraft.value, updated_at: updatedAt }
  }
}
function resetForActor() {
  contextRevision += 1; detailRevision += 1; listRevision += 1; conditionRevision += 1
  saving.value = false; optionsLoading.value = false; listLoading.value = false; detailLoadingId.value = ''
  conditionOptionsLoading.value = false; conditionOptions.value = null; conditionOptionsError.value = ''
  conditionDraft.value = null; conditionTree.value = null; conditionLoading.value = false; conditionSaving.value = false
  conditionResultUnknown.value = false; conditionConflict.value = false; conditionNotice.value = ''
  documentOptions.value = []; drafts.value = []; listTotal.value = null; listPage.value = 1
  optionsError.value = ''; listError.value = ''; resultUnknown.value = false
  clearForm()
  if (mounted) void initialize(contextRevision, actorKey.value)
}
watch(actorKey, resetForActor)
onMounted(() => { mounted = true; void initialize(contextRevision, actorKey.value) })
onUnmounted(() => { disposed = true; contextRevision += 1; detailRevision += 1; conditionRevision += 1 })
</script>

<style scoped>
.quality-control-point-create { min-height: 100vh; padding: 24px; background: #f5f5f7; color: #1d1d1f; }
.breadcrumb-nav { margin-bottom: 18px; }
.page-header,.section-heading,.form-actions,.pagination-row { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.page-header { margin-bottom:20px; }.page-header h1 { margin:0; font-size:24px; line-height:31px; font-weight:600; }.page-header p { margin:3px 0 0; color:rgba(29,29,31,.6); font-size:14px; }
.create-layout { display:grid; gap:18px; margin-top:18px; }.editor-section,.draft-section { padding:22px; border:1px solid rgba(0,0,0,.08); border-radius:8px; background:#fff; box-shadow:0 4px 18px rgba(38,58,86,.04); }
.section-heading { margin-bottom:18px; }.section-heading h2 { display:inline; margin:0; font-size:17px; line-height:22px; font-weight:600; }.section-heading span { margin-left:10px; color:rgba(29,29,31,.6); font-size:13px; }.draft-code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }
.basic-form { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:18px 20px; }.field { display:grid; gap:7px; min-width:0; }.field>span { font-size:14px; line-height:22px; }.field--wide { grid-column:1/-1; }
.field input,.field select { width:100%; min-height:38px; padding:0 11px; border:1px solid rgba(0,0,0,.14); border-radius:8px; background:#fff; color:#1d1d1f; font:inherit; }.field input:focus,.field select:focus { border-color:#007aff; outline:0; box-shadow:0 0 0 3px rgba(0,122,255,.08); }.field small { color:#b42318; font-size:12px; }
button { min-height:34px; border-radius:8px; font:inherit; cursor:pointer; }button:disabled { cursor:not-allowed; opacity:.55; }.primary-button { padding:0 16px; border:1px solid #007aff; background:#007aff; color:#fff; }.secondary-button { display:inline-flex; align-items:center; gap:6px; padding:0 14px; border:1px solid rgba(0,0,0,.12); background:#fff; color:#1d1d1f; }.text-button { min-height:30px; padding:0 6px; border:0; background:transparent; color:#007aff; }.scope-note,.legacy-note { color:rgba(29,29,31,.5); font-size:13px; }
.draft-table-wrap { max-width:100%; overflow-x:auto; }table { width:100%; min-width:760px; border-collapse:collapse; table-layout:fixed; }th,td { padding:11px 12px; border-bottom:1px solid rgba(0,0,0,.07); text-align:left; overflow-wrap:anywhere; font-size:14px; }th { background:#f7f8fa; color:rgba(29,29,31,.6); font-weight:500; }td:first-child { width:28%; }td strong,td span { display:block; }td span { margin-top:3px; color:rgba(29,29,31,.6); }
.list-state { padding:30px 12px; text-align:center; color:rgba(29,29,31,.6); }.list-state.is-error { color:#b42318; }.pagination-row { justify-content:flex-end; margin-top:14px; }.pagination-row button { padding:0 12px; border:1px solid rgba(0,0,0,.12); background:#fff; }.pagination-row span { color:rgba(29,29,31,.6); font-size:13px; }
@media (max-width:760px) { .quality-control-point-create { padding:16px; }.basic-form { grid-template-columns:1fr; }.field--wide { grid-column:auto; }.form-actions { align-items:flex-start; flex-direction:column; } }
</style>
