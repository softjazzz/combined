<template>
  <div class="scoring-standards-page">
    <header class="scoring-standards-page__header">
      <div>
        <h2 class="scoring-standards-page__title">
          评分标准配置
        </h2>
        <p class="scoring-standards-page__subtitle">
          得分由计分服务按已保存的质控结果和场景默认标准实时计算，只对确定问题扣分；未启用标准的场景一律显示“未配置评分标准”。
        </p>
      </div>
    </header>

    <a-tabs
      :active-key="scene"
      class="scoring-standards-page__tabs"
      @update:active-key="switchScene"
    >
      <a-tab-pane
        v-for="option in sceneTabs"
        :key="option.value"
        :tab="option.label"
      />
    </a-tabs>

    <a-alert
      v-if="!canWrite"
      type="info"
      show-icon
      class="scoring-standards-page__alert"
      data-testid="scoring-readonly-role"
      message="当前角色只读：仅管理员或质控管理员可新建、编辑、启用或归档评分标准。"
    />
    <a-alert
      v-if="catalogLoaded && !sceneHasRuleSet"
      type="warning"
      show-icon
      class="scoring-standards-page__alert"
      data-testid="scoring-scene-unavailable"
      :message="`${sceneLabel}暂无可用规则集，不能新建评分标准。`"
    />
    <div
      v-if="loadError"
      class="scoring-standards-page__error"
      role="alert"
      data-testid="scoring-list-error"
    >
      <span>{{ loadError }}</span>
      <a-button
        size="small"
        @click="loadList"
      >
        重试
      </a-button>
    </div>

    <section class="scoring-standards-page__panel">
      <div class="scoring-standards-page__toolbar">
        <span class="scoring-standards-page__summary">
          <template v-if="listLoaded">
            共 {{ standards.length }} 个标准 · 默认标准：<strong data-testid="scoring-default-name">{{ defaultStandard?.name || '未配置评分标准' }}</strong>
          </template>
        </span>
        <a-button
          v-if="canWrite"
          type="primary"
          :disabled="!sceneHasRuleSet"
          data-testid="scoring-create"
          @click="openCreate"
        >
          新建标准
        </a-button>
      </div>

      <table class="scoring-standards-page__table">
        <thead>
          <tr>
            <th>名称</th>
            <th>状态</th>
            <th>默认</th>
            <th>满分</th>
            <th>档位</th>
            <th>更新时间</th>
            <th class="scoring-standards-page__actions-heading">
              操作
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="standard in standards"
            :key="standard.id"
            data-testid="scoring-standard-row"
            :data-id="standard.id"
          >
            <td class="scoring-standards-page__name">
              {{ standard.name || UNKNOWN_TEXT }}
            </td>
            <td>
              <span
                class="scoring-standards-page__status"
                :class="`is-${standard.status}`"
                data-testid="scoring-standard-status"
              >{{ STATUS_LABELS[standard.status] || UNKNOWN_TEXT }}</span>
            </td>
            <td>
              <span
                v-if="standard.is_default"
                class="scoring-standards-page__default"
                data-testid="scoring-standard-default"
              >默认</span>
              <span v-else>—</span>
            </td>
            <td>{{ formatScore(standard.base_score) }}</td>
            <td class="scoring-standards-page__bands">
              {{ bandsSummary(standard.grade_bands) }}
            </td>
            <td>{{ formatUtcTime(standard.updated_at) }}</td>
            <td class="scoring-standards-page__actions">
              <a-button
                type="link"
                size="small"
                data-testid="scoring-action-open"
                @click="openEditor(standard)"
              >
                {{ canWrite && standard.status === 'draft' ? '编辑' : '查看' }}
              </a-button>
              <template v-if="canWrite">
                <a-button
                  type="link"
                  size="small"
                  data-testid="scoring-action-copy"
                  @click="openCopy(standard)"
                >
                  复制
                </a-button>
                <a-button
                  v-if="standard.status === 'draft'"
                  type="link"
                  size="small"
                  data-testid="scoring-action-activate"
                  @click="openActivate(standard)"
                >
                  启用
                </a-button>
                <a-popconfirm
                  v-if="standard.status === 'draft'"
                  title="确定删除该草稿？删除后不可恢复。"
                  ok-text="删除"
                  cancel-text="取消"
                  @confirm="removeDraft(standard)"
                >
                  <a-button
                    type="link"
                    danger
                    size="small"
                    data-testid="scoring-action-delete"
                  >
                    删除
                  </a-button>
                </a-popconfirm>
                <a-popconfirm
                  v-if="standard.status === 'active'"
                  title="归档后该场景若无其他默认标准，得分将显示“未配置评分标准”。确定归档？"
                  ok-text="归档"
                  cancel-text="取消"
                  @confirm="archive(standard)"
                >
                  <a-button
                    type="link"
                    size="small"
                    data-testid="scoring-action-archive"
                  >
                    归档
                  </a-button>
                </a-popconfirm>
              </template>
            </td>
          </tr>
          <tr v-if="listLoaded && standards.length === 0">
            <td
              colspan="7"
              class="scoring-standards-page__empty"
            >
              该场景暂无评分标准
            </td>
          </tr>
          <tr v-if="loading">
            <td
              colspan="7"
              class="scoring-standards-page__empty"
            >
              正在读取评分标准…
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- 新建 / 复制 -->
    <a-modal
      :open="formModal.open"
      :title="formModal.mode === 'create' ? '新建评分标准草稿' : '复制为新草稿'"
      :confirm-loading="formModal.submitting"
      ok-text="确定"
      cancel-text="取消"
      data-testid="scoring-form-modal"
      @ok="submitFormModal"
      @cancel="formModal.open = false"
    >
      <div class="scoring-standards-page__form">
        <label class="scoring-standards-page__field">
          <span>标准名称</span>
          <a-input
            v-model:value="formModal.name"
            :maxlength="100"
            placeholder="例如：2026 版运行病历评分标准"
            data-testid="scoring-form-name"
          />
        </label>
        <template v-if="formModal.mode === 'create'">
          <label
            v-if="sceneRuleSets.length > 1"
            class="scoring-standards-page__field"
          >
            <span>规则集</span>
            <a-select
              v-model:value="formModal.ruleSetKey"
              :options="ruleSetOptions"
              data-testid="scoring-form-rule-set"
            />
          </label>
          <p
            v-else
            class="scoring-standards-page__form-hint"
          >
            规则集：{{ sceneRuleSets[0]?.rule_set_name || UNKNOWN_TEXT }}
          </p>
          <p class="scoring-standards-page__form-hint">
            草稿以满分 100、甲/乙/丙三档起步，否决时强制为丙；创建后可在编辑中调整档位与条目。
          </p>
        </template>
        <p
          v-else-if="formModal.source"
          class="scoring-standards-page__form-hint"
        >
          复制来源：{{ formModal.source.name }}（含档位、项目组与条目）
        </p>
        <ul
          v-if="formModal.problems.length"
          class="scoring-standards-page__problems"
          data-testid="scoring-form-problems"
        >
          <li
            v-for="problem in formModal.problems"
            :key="problem"
          >
            {{ problem }}
          </li>
        </ul>
      </div>
    </a-modal>

    <!-- 启用 -->
    <a-modal
      :open="activateModal.open"
      title="启用评分标准"
      :confirm-loading="activateModal.submitting"
      ok-text="启用并设为默认"
      cancel-text="取消"
      data-testid="scoring-activate-modal"
      @ok="submitActivate"
      @cancel="activateModal.open = false"
    >
      <p class="scoring-standards-page__form-hint">
        启用「{{ activateModal.target?.name }}」后，它将成为{{ sceneLabel }}的默认评分标准，启用后只读。
      </p>
      <template v-if="defaultStandard && defaultStandard.id !== activateModal.target?.id">
        <p class="scoring-standards-page__form-hint">
          原默认标准「{{ defaultStandard.name }}」的处理方式：
        </p>
        <a-radio-group
          v-model:value="activateModal.replaceMode"
          data-testid="scoring-activate-mode"
        >
          <a-radio value="archive">
            归档原默认标准
          </a-radio>
          <a-radio value="undefault">
            仅取消默认（保持启用状态）
          </a-radio>
        </a-radio-group>
      </template>
      <ul
        v-if="activateModal.problems.length"
        class="scoring-standards-page__problems"
        data-testid="scoring-activate-problems"
      >
        <li
          v-for="problem in activateModal.problems"
          :key="problem"
        >
          {{ problem }}
        </li>
      </ul>
    </a-modal>

    <ScoringStandardEditor
      :open="editor.open"
      :standard-id="editor.standardId"
      :can-write="canWrite"
      @close="editor.open = false"
      @saved="loadList"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * 评分标准管理页（沿用 qc/scoring-config 路由）。
 * 场景页签：运行/终末/门急诊；无可用规则集的场景不可新建。写操作仅 admin/qc_manager，
 * 其余角色只读。active 标准只读，修改须复制为新草稿；启用时选择原默认“归档”或“仅取消默认”。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  activateScoringStandard,
  archiveScoringStandard,
  copyScoringStandard,
  createScoringStandard,
  deleteScoringStandard,
  listScoringStandards,
} from '@/api/scoring'
import type {
  ScoringApiResult,
  ScoringReplaceMode,
  ScoringScene,
  ScoringSceneCatalogEntry,
  ScoringStandardItem,
} from '@/api/scoring'
import { useAuthStore } from '@/stores/auth'
import ScoringStandardEditor from './scoring/ScoringStandardEditor.vue'
import {
  SCENE_LABELS,
  SCENE_ORDER,
  STATUS_LABELS,
  UNKNOWN_TEXT,
  bandsSummary,
  defaultBands,
  formatScore,
  formatUtcTime,
  toBandWrites,
} from './scoring/scoringStandardModel'

const authStore = useAuthStore()
const canWrite = computed(() => authStore.hasRole('admin') || authStore.hasRole('qc_manager'))

const scene = ref<ScoringScene>('running')
const standards = ref<ScoringStandardItem[]>([])
const catalog = ref<ScoringSceneCatalogEntry[]>([])
const catalogLoaded = ref(false)
const listLoaded = ref(false)
const loading = ref(false)
const loadError = ref('')
let requestSequence = 0

const sceneTabs = SCENE_ORDER.map((value) => ({ value, label: SCENE_LABELS[value] }))
const sceneLabel = computed(() => SCENE_LABELS[scene.value])
const sceneRuleSets = computed(
  () => catalog.value.find((entry) => entry.scene === scene.value)?.rule_sets ?? [],
)
const sceneHasRuleSet = computed(() => catalogLoaded.value && sceneRuleSets.value.length > 0)
const ruleSetOptions = computed(() =>
  sceneRuleSets.value.map((item) => ({ value: item.rule_set_key, label: item.rule_set_name || item.rule_set_key })),
)
const defaultStandard = computed(
  () => standards.value.find((item) => item.status === 'active' && item.is_default) ?? null,
)

const formModal = reactive({
  open: false,
  mode: 'create' as 'create' | 'copy',
  name: '',
  ruleSetKey: '',
  source: null as ScoringStandardItem | null,
  submitting: false,
  problems: [] as string[],
})

const activateModal = reactive({
  open: false,
  target: null as ScoringStandardItem | null,
  replaceMode: 'archive' as ScoringReplaceMode,
  submitting: false,
  problems: [] as string[],
})

const editor = reactive({ open: false, standardId: null as string | null })

async function loadList() {
  const sequence = ++requestSequence
  const currentScene = scene.value
  loading.value = true
  loadError.value = ''
  listLoaded.value = false
  standards.value = []
  try {
    const response = await listScoringStandards({ scene: currentScene })
    if (sequence !== requestSequence) return
    if (!response.success || !response.data) {
      loadError.value = response.message || '读取评分标准失败'
      return
    }
    // 只展示当前场景的标准，防止跨场景串显。
    standards.value = response.data.items.filter((item) => item.scene === currentScene)
    catalog.value = Array.isArray(response.data.scenes) ? response.data.scenes : []
    catalogLoaded.value = true
    listLoaded.value = true
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}

function switchScene(value: string | number) {
  if (!SCENE_ORDER.includes(value as ScoringScene) || value === scene.value) return
  scene.value = value as ScoringScene
  void loadList()
}

function reportFailure(result: ScoringApiResult<unknown>, target: { problems: string[] }, fallback: string) {
  if (result.status === 409 && result.code === 'version_conflict') {
    message.warning('评分标准已被他人修改，已刷新列表，请重新操作')
    void loadList()
    return
  }
  if (result.problems?.length) {
    target.problems = result.problems
    return
  }
  message.error(result.message || fallback)
}

function openCreate() {
  if (!canWrite.value || !sceneHasRuleSet.value) return
  formModal.mode = 'create'
  formModal.name = ''
  formModal.ruleSetKey = sceneRuleSets.value[0]?.rule_set_key ?? ''
  formModal.source = null
  formModal.problems = []
  formModal.open = true
}

function openCopy(standard: ScoringStandardItem) {
  formModal.mode = 'copy'
  formModal.name = `${standard.name}（副本）`.slice(0, 100)
  formModal.ruleSetKey = ''
  formModal.source = standard
  formModal.problems = []
  formModal.open = true
}

async function submitFormModal() {
  const name = formModal.name.trim()
  if (!name) {
    formModal.problems = ['标准名称不能为空']
    return
  }
  formModal.problems = []
  formModal.submitting = true
  try {
    const result =
      formModal.mode === 'create'
        ? await createScoringStandard({
          name,
          scene: scene.value,
          rule_set_key: formModal.ruleSetKey || null,
          base_score: 100,
          grade_bands: toBandWrites(defaultBands(100)),
          veto_grade: '丙',
        })
        : await copyScoringStandard(formModal.source?.id ?? '', name)
    if (!result.success || !result.data) {
      reportFailure(result, formModal, formModal.mode === 'create' ? '新建评分标准失败' : '复制评分标准失败')
      return
    }
    message.success(formModal.mode === 'create' ? '评分标准草稿已创建' : '已复制为新草稿')
    formModal.open = false
    await loadList()
    editor.standardId = result.data.id
    editor.open = true
  } finally {
    formModal.submitting = false
  }
}

function openActivate(standard: ScoringStandardItem) {
  activateModal.target = standard
  activateModal.replaceMode = 'archive'
  activateModal.problems = []
  activateModal.open = true
}

async function submitActivate() {
  const target = activateModal.target
  if (!target) return
  activateModal.problems = []
  activateModal.submitting = true
  try {
    const result = await activateScoringStandard(target.id, {
      version_seq: target.version_seq,
      replace_mode: activateModal.replaceMode,
    })
    if (!result.success) {
      reportFailure(result, activateModal, '启用评分标准失败')
      if (result.status === 409) activateModal.open = false
      return
    }
    message.success('评分标准已启用并设为默认')
    activateModal.open = false
    await loadList()
  } finally {
    activateModal.submitting = false
  }
}

async function removeDraft(standard: ScoringStandardItem) {
  const result = await deleteScoringStandard(standard.id, standard.version_seq)
  if (!result.success) {
    reportFailure(result, { problems: [] }, '删除评分标准草稿失败')
    return
  }
  message.success('草稿已删除')
  await loadList()
}

async function archive(standard: ScoringStandardItem) {
  const result = await archiveScoringStandard(standard.id, standard.version_seq)
  if (!result.success) {
    reportFailure(result, { problems: [] }, '归档评分标准失败')
    return
  }
  message.success('评分标准已归档')
  await loadList()
}

function openEditor(standard: ScoringStandardItem) {
  editor.standardId = standard.id
  editor.open = true
}

onMounted(() => {
  void loadList()
})
</script>

<style scoped>
.scoring-standards-page {
  display: grid;
  gap: 12px;
  padding: 20px 24px;
  background: #f5f7fa;
  min-height: 100%;
}

.scoring-standards-page__title {
  margin: 0;
  color: #1d1d1f;
  font-size: 20px;
  font-weight: 600;
}

.scoring-standards-page__subtitle {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.scoring-standards-page__tabs {
  margin-bottom: -8px;
}

.scoring-standards-page__error {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #b42318;
  font-size: 13px;
}

.scoring-standards-page__panel {
  padding: 14px 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(15, 42, 74, 0.04);
  overflow-x: auto;
}

.scoring-standards-page__toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.scoring-standards-page__summary {
  color: #64748b;
  font-size: 13px;
}

.scoring-standards-page__summary strong {
  color: #1d1d1f;
  font-weight: 600;
}

.scoring-standards-page__table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
  font-size: 13px;
}

.scoring-standards-page__table th {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  background: #f8fafc;
  color: #64748b;
  font-weight: 500;
  text-align: left;
  white-space: nowrap;
}

.scoring-standards-page__table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.9);
  color: #1d1d1f;
  vertical-align: middle;
  white-space: nowrap;
}

.scoring-standards-page__name {
  font-weight: 600;
}

.scoring-standards-page__bands {
  max-width: 320px;
  overflow: hidden;
  color: #475569 !important;
  text-overflow: ellipsis;
}

.scoring-standards-page__status,
.scoring-standards-page__default {
  display: inline-block;
  padding: 0 8px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 6px;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  line-height: 20px;
}

.scoring-standards-page__status.is-active,
.scoring-standards-page__default {
  border-color: rgba(6, 118, 71, 0.24);
  background: #ecfdf3;
  color: #067647;
}

.scoring-standards-page__status.is-draft {
  border-color: rgba(43, 108, 246, 0.24);
  background: #eef5ff;
  color: #2456c7;
}

.scoring-standards-page__actions-heading {
  text-align: right !important;
}

.scoring-standards-page__actions {
  text-align: right;
}

.scoring-standards-page__empty {
  padding: 32px 12px !important;
  color: #94a3b8 !important;
  text-align: center;
}

.scoring-standards-page__form {
  display: grid;
  gap: 12px;
}

.scoring-standards-page__field {
  display: grid;
  gap: 4px;
  color: #64748b;
  font-size: 12px;
}

.scoring-standards-page__form-hint {
  margin: 0 0 8px;
  color: #64748b;
  font-size: 13px;
}

.scoring-standards-page__problems {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #b42318;
  font-size: 12px;
}
</style>
