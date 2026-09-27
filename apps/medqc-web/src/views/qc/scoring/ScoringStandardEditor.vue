<template>
  <a-drawer
    :open="open"
    placement="right"
    width="min(1080px, 100vw)"
    :title="editable ? '编辑评分标准草稿' : '查看评分标准'"
    class="scoring-standard-editor"
    @close="emit('close')"
  >
    <p
      v-if="loading"
      class="scoring-editor__hint"
      role="status"
    >
      正在读取评分标准…
    </p>
    <div
      v-else-if="loadError"
      class="scoring-editor__load-error"
      role="alert"
      data-testid="scoring-editor-load-error"
    >
      <span>{{ loadError }}</span>
      <a-button
        size="small"
        @click="load"
      >
        重试
      </a-button>
    </div>

    <template v-else-if="detail">
      <a-alert
        v-if="readonlyNotice"
        type="info"
        show-icon
        class="scoring-editor__alert"
        data-testid="scoring-editor-readonly"
        :message="readonlyNotice"
      />
      <a-alert
        v-if="conflict"
        type="warning"
        show-icon
        class="scoring-editor__alert"
        data-testid="scoring-editor-conflict"
        message="评分标准已被他人修改，本次未保存。请刷新后重新编辑。"
      />
      <div
        v-if="conflict"
        class="scoring-editor__alert-actions"
      >
        <a-button
          size="small"
          data-testid="scoring-editor-refresh"
          @click="load"
        >
          刷新
        </a-button>
      </div>
      <a-alert
        v-if="saveProblems.length"
        type="error"
        show-icon
        class="scoring-editor__alert"
        data-testid="scoring-editor-problems"
        :message="saveMessage || '保存未通过校验'"
      >
        <template #description>
          <ul class="scoring-editor__problems">
            <li
              v-for="problem in saveProblems"
              :key="problem"
            >
              {{ problem }}
            </li>
          </ul>
        </template>
      </a-alert>

      <!-- 基本信息 -->
      <section class="scoring-editor__section">
        <h3 class="scoring-editor__section-title">
          基本信息
        </h3>
        <div class="scoring-editor__meta-grid">
          <label class="scoring-editor__field">
            <span>标准名称</span>
            <a-input
              v-model:value="form.name"
              :disabled="!editable"
              :maxlength="100"
              data-testid="scoring-editor-name"
            />
          </label>
          <label class="scoring-editor__field">
            <span>满分</span>
            <a-input-number
              v-model:value="form.base_score"
              :disabled="!editable"
              :min="0.01"
              :max="9999.99"
              :precision="2"
              data-testid="scoring-editor-base-score"
            />
          </label>
          <div class="scoring-editor__field">
            <span>场景</span>
            <strong>{{ sceneLabel }}</strong>
          </div>
          <div class="scoring-editor__field">
            <span>规则集</span>
            <strong>{{ detail.rule_set_key || UNKNOWN_TEXT }}</strong>
          </div>
        </div>
      </section>

      <!-- 等级档位 -->
      <section class="scoring-editor__section">
        <header class="scoring-editor__section-header">
          <h3 class="scoring-editor__section-title">
            等级档位
          </h3>
          <span class="scoring-editor__section-hint">按分数从高到低排列，区间左闭右开、最高档含满分，需首尾相接覆盖 0 至满分</span>
        </header>
        <table class="scoring-editor__table">
          <thead>
            <tr>
              <th>档位名称</th>
              <th>下限（含）</th>
              <th>上限</th>
              <th v-if="editable">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(band, index) in form.bands"
              :key="index"
              data-testid="scoring-band-row"
            >
              <td>
                <a-input
                  v-model:value="band.name"
                  :disabled="!editable"
                  :maxlength="50"
                  data-testid="scoring-band-name"
                />
              </td>
              <td>
                <a-input-number
                  v-model:value="band.min_score"
                  :disabled="!editable"
                  :min="0"
                  :precision="2"
                  data-testid="scoring-band-min"
                />
              </td>
              <td>
                <a-input-number
                  v-model:value="band.max_score"
                  :disabled="!editable"
                  :min="0"
                  :precision="2"
                  data-testid="scoring-band-max"
                />
              </td>
              <td v-if="editable">
                <a-button
                  type="link"
                  danger
                  size="small"
                  :disabled="form.bands.length <= 1"
                  data-testid="scoring-band-remove"
                  @click="removeBand(index)"
                >
                  删除
                </a-button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="scoring-editor__row-actions">
          <a-button
            v-if="editable"
            size="small"
            :disabled="form.bands.length >= MAX_BANDS"
            data-testid="scoring-band-add"
            @click="addBand"
          >
            添加档位
          </a-button>
          <label class="scoring-editor__inline-field">
            <span>单项否决时强制档位</span>
            <a-select
              v-model:value="form.veto_grade"
              :disabled="!editable"
              :options="vetoOptions"
              class="scoring-editor__veto-select"
              data-testid="scoring-veto-grade"
            />
          </label>
        </div>
        <ul
          v-if="editable && bandProblems.length"
          class="scoring-editor__inline-problems"
          data-testid="scoring-band-problems"
        >
          <li
            v-for="problem in bandProblems"
            :key="problem"
          >
            {{ problem }}
          </li>
        </ul>
      </section>

      <!-- 项目组 -->
      <section class="scoring-editor__section">
        <header class="scoring-editor__section-header">
          <h3 class="scoring-editor__section-title">
            项目组
          </h3>
          <span class="scoring-editor__section-hint">封顶扣分留空表示不封顶</span>
        </header>
        <table class="scoring-editor__table">
          <thead>
            <tr>
              <th>项目组名称</th>
              <th>封顶扣分</th>
              <th>排序</th>
              <th>条目数</th>
              <th v-if="editable">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="group in form.groups"
              :key="group.key"
              data-testid="scoring-group-row"
            >
              <td>
                <a-input
                  :value="group.group_name"
                  :disabled="!editable"
                  :maxlength="100"
                  data-testid="scoring-group-name"
                  @update:value="renameGroup(group, $event)"
                />
              </td>
              <td>
                <a-input-number
                  v-model:value="group.max_deduction"
                  :disabled="!editable"
                  :min="0"
                  :precision="2"
                  placeholder="不封顶"
                  data-testid="scoring-group-cap"
                />
              </td>
              <td>
                <a-input-number
                  v-model:value="group.sort_order"
                  :disabled="!editable"
                  :min="0"
                  :precision="0"
                  data-testid="scoring-group-sort"
                />
              </td>
              <td>{{ groupItemCount(group.group_name) }}</td>
              <td v-if="editable">
                <a-button
                  type="link"
                  danger
                  size="small"
                  :disabled="groupItemCount(group.group_name) > 0"
                  :title="groupItemCount(group.group_name) > 0 ? '请先移除或改组该组条目' : undefined"
                  data-testid="scoring-group-remove"
                  @click="removeGroup(group.key)"
                >
                  删除
                </a-button>
              </td>
            </tr>
            <tr v-if="form.groups.length === 0">
              <td
                :colspan="editable ? 5 : 4"
                class="scoring-editor__empty"
              >
                暂无项目组
              </td>
            </tr>
          </tbody>
        </table>
        <div
          v-if="editable"
          class="scoring-editor__row-actions"
        >
          <a-button
            size="small"
            data-testid="scoring-group-add"
            @click="addGroup"
          >
            添加项目组
          </a-button>
        </div>
      </section>

      <!-- 扣分条目 -->
      <section class="scoring-editor__section">
        <header class="scoring-editor__section-header">
          <h3 class="scoring-editor__section-title">
            扣分条目
          </h3>
          <span class="scoring-editor__section-hint">仅对执行器判定的确定问题扣分；规则来自该规则集当前版本</span>
        </header>
        <p
          v-if="rulesError"
          class="scoring-editor__rules-error"
          data-testid="scoring-rules-error"
        >
          {{ rulesError }}
        </p>
        <table class="scoring-editor__table scoring-editor__table--items">
          <thead>
            <tr>
              <th>规则</th>
              <th>质控点</th>
              <th>项目组</th>
              <th>扣分</th>
              <th>单项否决</th>
              <th>启用</th>
              <th v-if="editable">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in form.items"
              :key="item.key"
              data-testid="scoring-item-row"
            >
              <td>
                <a-select
                  v-if="editable"
                  v-model:value="item.rule_id"
                  show-search
                  :options="ruleOptions"
                  :filter-option="filterRuleOption"
                  placeholder="选择规则"
                  class="scoring-editor__rule-select"
                  data-testid="scoring-item-rule"
                />
                <span
                  v-else
                  class="scoring-editor__rule-id"
                >{{ item.rule_id || UNKNOWN_TEXT }}</span>
              </td>
              <td
                class="scoring-editor__qc-point"
                data-testid="scoring-item-qc-point"
              >
                {{ qcPointOf(item.rule_id) }}
              </td>
              <td>
                <a-select
                  v-model:value="item.group_name"
                  :disabled="!editable"
                  :options="groupOptions"
                  class="scoring-editor__group-select"
                  data-testid="scoring-item-group"
                />
              </td>
              <td>
                <a-input-number
                  v-model:value="item.deduction"
                  :disabled="!editable"
                  :min="0"
                  :precision="2"
                  data-testid="scoring-item-deduction"
                />
              </td>
              <td>
                <a-checkbox
                  v-model:checked="item.is_veto"
                  :disabled="!editable"
                  data-testid="scoring-item-veto"
                />
              </td>
              <td>
                <a-checkbox
                  v-model:checked="item.enabled"
                  :disabled="!editable"
                  data-testid="scoring-item-enabled"
                />
              </td>
              <td v-if="editable">
                <a-button
                  type="link"
                  danger
                  size="small"
                  data-testid="scoring-item-remove"
                  @click="removeItem(item.key)"
                >
                  删除
                </a-button>
              </td>
            </tr>
            <tr v-if="form.items.length === 0">
              <td
                :colspan="editable ? 7 : 6"
                class="scoring-editor__empty"
              >
                暂无扣分条目
              </td>
            </tr>
          </tbody>
        </table>
        <div
          v-if="editable"
          class="scoring-editor__row-actions"
        >
          <a-button
            size="small"
            :disabled="form.groups.length === 0"
            :title="form.groups.length === 0 ? '请先添加项目组' : undefined"
            data-testid="scoring-item-add"
            @click="addItem"
          >
            添加条目
          </a-button>
        </div>
      </section>

      <footer class="scoring-editor__footer">
        <span class="scoring-editor__version">版本序号 {{ versionSeq }}</span>
        <a-button @click="emit('close')">
          {{ editable ? '取消' : '关闭' }}
        </a-button>
        <a-button
          v-if="editable"
          type="primary"
          :loading="saving"
          :disabled="conflict"
          data-testid="scoring-editor-save"
          @click="save"
        >
          保存草稿
        </a-button>
      </footer>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
/**
 * 评分标准编辑抽屉：草稿可编辑（基本信息、档位、项目组、条目），启用中/已归档只读。
 * 保存先写基本信息（有改动时），再整表保存项目组与条目，均带 version_seq CAS；
 * 409 version_conflict 提示刷新，422 逐条展示 problems（以后端为准）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  getScoringStandard,
  saveScoringItems,
  updateScoringStandard,
} from '@/api/scoring'
import type { ScoringApiResult, ScoringStandardDetail } from '@/api/scoring'
import { getRuleSetVersion, listRuleSetVersions } from '@/api/ruleSetVersions'
import {
  MAX_BANDS,
  SCENE_LABELS,
  UNKNOWN_TEXT,
  toBandWrites,
  toGroupWrites,
  toItemWrites,
  validateBands,
  validateGroupsAndItems,
} from './scoringStandardModel'
import type { EditableBand, EditableGroup, EditableItem } from './scoringStandardModel'

const props = defineProps<{
  open: boolean
  standardId: string | null
  canWrite: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: [detail: ScoringStandardDetail]
}>()

interface RuleOption {
  value: string
  label: string
}

const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const conflict = ref(false)
const saveProblems = ref<string[]>([])
const saveMessage = ref('')
const detail = ref<ScoringStandardDetail | null>(null)
const versionSeq = ref(0)
const headerSnapshot = ref('')
const rulesError = ref('')
const qcPoints = ref<Map<string, string | null>>(new Map())
let requestSequence = 0
let rowKey = 0

const form = reactive({
  name: '',
  base_score: null as number | null,
  bands: [] as EditableBand[],
  veto_grade: '',
  groups: [] as EditableGroup[],
  items: [] as EditableItem[],
})

const editable = computed(() => props.canWrite && detail.value?.status === 'draft')
const sceneLabel = computed(() => (detail.value ? SCENE_LABELS[detail.value.scene] ?? UNKNOWN_TEXT : UNKNOWN_TEXT))
const readonlyNotice = computed(() => {
  const status = detail.value?.status
  if (status === 'active') return '该标准正在启用，只读展示。如需修改请复制为新草稿。'
  if (status === 'archived') return '该标准已归档，只读展示。如需沿用请复制为新草稿。'
  if (!props.canWrite) return '当前角色只读：仅管理员或质控管理员可编辑评分标准。'
  return ''
})
const bandProblems = computed(() => validateBands(form.bands, form.base_score, form.veto_grade))
const vetoOptions = computed(() =>
  [...new Set(form.bands.map((band) => band.name.trim()).filter(Boolean))].map((name) => ({ value: name, label: name })),
)
const groupOptions = computed(() =>
  form.groups
    .map((group) => group.group_name.trim())
    .filter(Boolean)
    .map((name) => ({ value: name, label: name })),
)
const ruleOptions = computed<RuleOption[]>(() =>
  [...qcPoints.value.entries()].map(([ruleId, qcPoint]) => ({
    value: ruleId,
    label: `${ruleId} · ${qcPoint || UNKNOWN_TEXT}`,
  })),
)
const ruleUniverse = computed(() => new Set(qcPoints.value.keys()))

function nextKey(prefix: string): string {
  rowKey += 1
  return `${prefix}-${rowKey}`
}

function headerState(): string {
  return JSON.stringify({
    name: form.name.trim(),
    base_score: form.base_score,
    bands: toBandWrites(form.bands),
    veto_grade: form.veto_grade.trim(),
  })
}

function applyDetail(data: ScoringStandardDetail) {
  detail.value = data
  versionSeq.value = data.version_seq
  form.name = data.name
  form.base_score = data.base_score
  form.bands = data.grade_bands.map((band) => ({ ...band }))
  form.veto_grade = data.veto_grade
  form.groups = data.groups.map((group) => ({ key: nextKey('group'), ...group }))
  form.items = data.items.map((item) => ({ key: nextKey('item'), ...item }))
  headerSnapshot.value = headerState()
}

async function loadRules(ruleSetKey: string, sequence: number) {
  rulesError.value = ''
  qcPoints.value = new Map()
  const list = await listRuleSetVersions(ruleSetKey)
  if (sequence !== requestSequence) return
  if (!list.success || !list.data?.current_version) {
    rulesError.value = `规则清单读取失败：${list.message || '当前版本未知'}，质控点显示为未知`
    return
  }
  const version = await getRuleSetVersion(ruleSetKey, list.data.current_version)
  if (sequence !== requestSequence) return
  if (!version.success || !Array.isArray(version.data?.entries)) {
    rulesError.value = `规则清单读取失败：${version.message || '版本详情缺失'}，质控点显示为未知`
    return
  }
  qcPoints.value = new Map(
    version.data.entries.map((entry) => [entry.rule_id.trim().toUpperCase(), entry.qc_point]),
  )
}

async function load() {
  const id = props.standardId
  const sequence = ++requestSequence
  detail.value = null
  loadError.value = ''
  conflict.value = false
  saveProblems.value = []
  saveMessage.value = ''
  if (!props.open || !id) return
  loading.value = true
  try {
    const response = await getScoringStandard(id)
    if (sequence !== requestSequence) return
    if (!response.success || !response.data) {
      loadError.value = response.message || '读取评分标准详情失败'
      return
    }
    applyDetail(response.data)
    loading.value = false
    await loadRules(response.data.rule_set_key, sequence)
  } catch {
    if (sequence === requestSequence) loadError.value = '读取评分标准详情失败'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function qcPointOf(ruleId: string): string {
  const key = ruleId.trim().toUpperCase()
  if (!key) return UNKNOWN_TEXT
  return qcPoints.value.get(key) || UNKNOWN_TEXT
}

function filterRuleOption(input: string, option?: RuleOption): boolean {
  return Boolean(option?.label.toLowerCase().includes(input.trim().toLowerCase()))
}

function groupItemCount(name: string): number {
  const trimmed = name.trim()
  return form.items.filter((item) => item.group_name.trim() === trimmed).length
}

function addBand() {
  const last = form.bands[form.bands.length - 1]
  form.bands.push({ name: '', min_score: 0, max_score: last?.min_score ?? form.base_score ?? null })
}

function removeBand(index: number) {
  form.bands.splice(index, 1)
}

function addGroup() {
  const sortOrder = form.groups.reduce((max, group) => Math.max(max, group.sort_order ?? 0), 0) + 1
  form.groups.push({ key: nextKey('group'), group_name: '', max_deduction: null, sort_order: sortOrder })
}

/** 改组名时同步其条目的所属组，避免条目指向不存在的组。 */
function renameGroup(group: EditableGroup, value: string) {
  const previous = group.group_name
  for (const item of form.items) {
    if (previous && item.group_name === previous) item.group_name = value
  }
  group.group_name = value
}

function removeGroup(key: string) {
  form.groups = form.groups.filter((group) => group.key !== key)
}

function addItem() {
  form.items.push({
    key: nextKey('item'),
    rule_id: '',
    group_name: form.groups[0]?.group_name ?? '',
    deduction: 0,
    is_veto: false,
    enabled: true,
  })
}

function removeItem(key: string) {
  form.items = form.items.filter((item) => item.key !== key)
}

function handleFailure(result: ScoringApiResult<unknown>): void {
  if (result.status === 409 && result.code === 'version_conflict') {
    conflict.value = true
    return
  }
  if (result.status === 409 && result.code === 'not_draft') {
    conflict.value = true
    return
  }
  if (result.status === 422 && result.problems?.length) {
    saveMessage.value = result.message || '保存未通过校验'
    saveProblems.value = result.problems
    return
  }
  message.error(result.message || '保存评分标准失败')
}

async function save() {
  const current = detail.value
  if (!current || !editable.value || saving.value) return
  saveProblems.value = []
  saveMessage.value = ''
  const problems = [
    ...(form.name.trim() ? [] : ['标准名称不能为空']),
    ...bandProblems.value,
    ...validateGroupsAndItems(form.groups, form.items, ruleUniverse.value),
  ]
  if (problems.length) {
    saveMessage.value = '请先修正以下问题'
    saveProblems.value = problems
    return
  }
  saving.value = true
  try {
    if (headerState() !== headerSnapshot.value) {
      const header = await updateScoringStandard(current.id, {
        version_seq: versionSeq.value,
        name: form.name.trim(),
        base_score: form.base_score as number,
        grade_bands: toBandWrites(form.bands),
        veto_grade: form.veto_grade.trim(),
      })
      if (!header.success || !header.data) {
        handleFailure(header)
        return
      }
      // 基本信息已落库：推进 CAS 序号，条目保存失败后可直接重试。
      versionSeq.value = header.data.version_seq
      headerSnapshot.value = headerState()
    }
    const saved = await saveScoringItems(current.id, {
      version_seq: versionSeq.value,
      groups: toGroupWrites(form.groups),
      items: toItemWrites(form.items),
    })
    if (!saved.success || !saved.data) {
      handleFailure(saved)
      return
    }
    applyDetail(saved.data)
    message.success('评分标准草稿已保存')
    emit('saved', saved.data)
  } finally {
    saving.value = false
  }
}

watch(
  () => [props.open, props.standardId] as const,
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<style scoped>
.scoring-editor__hint {
  color: #64748b;
  font-size: 13px;
}

.scoring-editor__load-error,
.scoring-editor__alert-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  color: #b42318;
  font-size: 13px;
}

.scoring-editor__alert {
  margin-bottom: 12px;
}

.scoring-editor__problems,
.scoring-editor__inline-problems {
  margin: 4px 0 0;
  padding-left: 18px;
}

.scoring-editor__inline-problems {
  color: #b54708;
  font-size: 12px;
}

.scoring-editor__section {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #fff;
}

.scoring-editor__section-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}

.scoring-editor__section-title {
  margin: 0 0 10px;
  color: #1d1d1f;
  font-size: 14px;
  font-weight: 600;
}

.scoring-editor__section-header .scoring-editor__section-title {
  margin-bottom: 0;
}

.scoring-editor__section-hint {
  color: #64748b;
  font-size: 12px;
}

.scoring-editor__meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px 16px;
}

.scoring-editor__field {
  display: grid;
  gap: 4px;
  color: #64748b;
  font-size: 12px;
}

.scoring-editor__field strong {
  color: #1d1d1f;
  font-size: 13px;
  font-weight: 500;
  line-height: 32px;
}

.scoring-editor__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.scoring-editor__table th {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  background: #f8fafc;
  color: #64748b;
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
}

.scoring-editor__table td {
  padding: 6px 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  vertical-align: middle;
}

.scoring-editor__empty {
  color: #94a3b8;
  text-align: center;
}

.scoring-editor__rule-select {
  min-width: 220px;
}

.scoring-editor__group-select,
.scoring-editor__veto-select {
  min-width: 140px;
}

.scoring-editor__rule-id {
  font-variant-numeric: tabular-nums;
}

.scoring-editor__qc-point {
  min-width: 160px;
  color: #475569;
}

.scoring-editor__rules-error {
  margin: 0 0 8px;
  color: #b54708;
  font-size: 12px;
}

.scoring-editor__row-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-top: 10px;
}

.scoring-editor__inline-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 13px;
}

.scoring-editor__footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  padding: 12px 0 4px;
  background: #fff;
}

.scoring-editor__version {
  margin-right: auto;
  color: #94a3b8;
  font-size: 12px;
}
</style>
