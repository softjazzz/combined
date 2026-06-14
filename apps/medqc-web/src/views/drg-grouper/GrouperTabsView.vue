<template>
  <div class="grouper-shell">
    <header class="grouper-header">
      <div class="header-main">
        <div class="breadcrumb">
          <Home class="inline-icon" />
          <span>工作台</span>
          <span>/</span>
          <strong>分组器</strong>
        </div>
      </div>
    </header>

    <main class="grouper-content">
      <div class="grouper-page">
        <section class="grouper-panel condition-panel">
          <header class="panel-heading">
            <div class="panel-title">
              <span class="heading-icon"><ClipboardList class="panel-icon" /></span>
              <div>
                <h2>分组条件</h2>
                <p>同一病案输入会同时送入 CHS-DRG 四川 2.0、CN-DRG 绩效监测、DIP 泸州版。</p>
              </div>
            </div>
          </header>

          <div class="condition-body">
            <div class="form-section">
              <div class="section-title">
                <span class="section-title-main"><UserRound class="section-icon" />基本信息</span>
              </div>
              <div class="field-grid">
                <label class="field-card">
                  <span>性别</span>
                  <select v-model="formData.gender">
                    <option value="1">男</option>
                    <option value="2">女</option>
                  </select>
                </label>
                <label class="field-card">
                  <span>年龄（岁）</span>
                  <input
                    v-model.number="formData.age"
                    type="number"
                    placeholder="岁"
                  >
                </label>
                <label class="field-card">
                  <span>住院天数（天）</span>
                  <input
                    v-model.number="formData.days"
                    type="number"
                    placeholder="天"
                  >
                </label>
                <label class="field-card">
                  <span>离院方式</span>
                  <select v-model="formData.leavingType">
                    <option value="1">医嘱离院</option>
                    <option value="2">医嘱转院</option>
                    <option value="3">医嘱转社区</option>
                    <option value="4">非医嘱离院</option>
                    <option value="5">死亡</option>
                  </select>
                </label>
              </div>
            </div>

            <div class="form-section">
              <div class="section-title">
                <span class="section-title-main"><SearchCheck class="section-icon" />主诊断</span>
                <span class="optional-chip">必填</span>
              </div>
              <div class="code-list">
                <div class="code-row primary">
                  <span class="code-label">主诊断</span>
                  <input
                    v-model="formData.zdList[0]"
                    type="text"
                    placeholder="输入 ICD-10 编码"
                    @keyup.enter="addDiagnosis"
                  >
                  <span />
                </div>
              </div>
            </div>

            <div class="form-section">
              <div class="section-title">
                <span class="section-title-main"><FilePlus2 class="section-icon" />其他诊断</span>
                <span class="optional-chip">选填</span>
              </div>
              <div class="code-list">
                <div
                  v-for="(_, index) in otherDiagnosisIndexes"
                  :key="`zd-${index}`"
                  class="code-row"
                >
                  <span class="code-label">其他 {{ index }}</span>
                  <input
                    v-model="formData.zdList[index]"
                    type="text"
                    placeholder="输入 ICD-10 编码"
                    @keyup.enter="addDiagnosis"
                  >
                  <button
                    type="button"
                    class="icon-button"
                    @click="formData.zdList.splice(index, 1)"
                  >
                    <Trash2 class="button-icon" />
                  </button>
                </div>
                <button
                  type="button"
                  class="add-button"
                  @click="addDiagnosis"
                >
                  <Plus class="button-icon" /> 添加诊断
                </button>
              </div>
            </div>

            <div class="form-section">
              <div class="section-title">
                <span class="section-title-main"><BriefcaseMedical class="section-icon" />手术操作</span>
                <span class="optional-chip">选填</span>
              </div>
              <div class="code-list">
                <div
                  v-for="(_, index) in formData.ssList"
                  :key="`ss-${index}`"
                  class="code-row"
                >
                  <span class="code-label">{{ index === 0 ? '主手术' : `其他 ${index}` }}</span>
                  <input
                    v-model="formData.ssList[index]"
                    type="text"
                    placeholder="输入手术操作编码"
                    @keyup.enter="addProcedure"
                  >
                  <button
                    v-if="formData.ssList.length > 1 || formData.ssList[0]"
                    type="button"
                    class="icon-button"
                    @click="formData.ssList.splice(index, 1)"
                  >
                    <Trash2 class="button-icon" />
                  </button>
                  <span v-else />
                </div>
                <button
                  type="button"
                  class="add-button"
                  @click="addProcedure"
                >
                  <Plus class="button-icon" /> 添加手术
                </button>
              </div>
            </div>

            <div class="form-section">
              <div class="section-title">
                <span class="section-title-main"><CircleDollarSign class="section-icon" />费用信息（元）</span>
                <span class="optional-chip">选填</span>
              </div>
              <div class="field-grid">
                <label class="field-card">
                  <span>总费用</span>
                  <input
                    v-model.number="formData.totalFee"
                    type="number"
                    placeholder="0.00"
                  >
                </label>
                <label class="field-card">
                  <span>药品费用</span>
                  <input
                    v-model.number="formData.drugFee"
                    type="number"
                    placeholder="0.00"
                  >
                </label>
                <label class="field-card">
                  <span>材料费用</span>
                  <input
                    v-model.number="formData.materialFee"
                    type="number"
                    placeholder="0.00"
                  >
                </label>
                <label class="field-card">
                  <span>其他费用</span>
                  <input
                    v-model.number="formData.otherFee"
                    type="number"
                    placeholder="0.00"
                  >
                </label>
              </div>
              <p class="field-help">
                费用信息用于结果摘要；DRG、CN-DRG、DIP 的本地分组判定仍以诊断和手术编码为主。
              </p>
            </div>
          </div>

          <footer class="action-bar">
            <button
              class="secondary-button"
              type="button"
              @click="fillTestCase"
            >
              填入样例
            </button>
            <button
              class="secondary-button"
              type="button"
              @click="resetForm"
            >
              重置
            </button>
            <button
              class="primary-button"
              type="button"
              :disabled="grouping"
              @click="doGrouping"
            >
              <LoaderCircle
                v-if="grouping"
                class="button-icon spin-icon"
              />
              <Zap
                v-else
                class="button-icon"
              />
              {{ grouping ? '三分组器执行中...' : '执行分组' }}
            </button>
          </footer>
        </section>

        <section class="grouper-panel result-panel">
          <header class="panel-heading">
            <div class="panel-title">
              <span class="heading-icon"><ChartColumnBig class="panel-icon" /></span>
              <div>
                <h2>三分组器结果</h2>
                <p>同屏展示 CHS-DRG、CN-DRG 绩效监测、DIP 的入组结果。</p>
              </div>
            </div>
          </header>

          <div class="result-body">
            <div
              v-if="!hasAnyResult && !grouping"
              class="empty-state"
            >
              <FileSearch class="empty-icon" />
              <h3>等待分组</h3>
              <p>填写条件后点击执行分组，系统会一次生成 3 个分组器结果。</p>
            </div>

            <div
              v-else-if="grouping"
              class="empty-state"
            >
              <LoaderCircle class="empty-icon spin-icon" />
              <h3>正在执行分组</h3>
              <p>系统正在并行调用 CHS-DRG、CN-DRG 绩效监测、DIP 分组器。</p>
            </div>

            <div
              v-else
              class="result-summary"
            >
              <div
                v-for="card in resultCards"
                :key="card.key"
                class="result-block"
              >
                <div class="result-block-header">
                  <span :class="['result-icon', card.success ? 'success' : 'danger']">
                    <CircleCheck v-if="card.success" />
                    <CircleX v-else />
                  </span>
                  <div>
                    <h3>{{ card.title }}</h3>
                    <p>{{ card.subtitle }}</p>
                  </div>
                  <span :class="['status-chip', card.success ? 'success' : 'danger']">
                    {{ card.status }}
                  </span>
                </div>

                <template v-if="card.success">
                  <div class="result-row">
                    <span>{{ card.codeLabel }}</span>
                    <strong class="primary-value">{{ card.code || '--' }}</strong>
                  </div>
                  <div class="result-row">
                    <span>{{ card.nameLabel }}</span>
                    <strong>{{ card.name || '--' }}</strong>
                  </div>
                  <div class="result-row">
                    <span>{{ card.metricLabel }}</span>
                    <strong class="success-value">{{ card.metric || '--' }}</strong>
                  </div>
                  <div
                    v-for="row in card.detailRows"
                    :key="`${card.key}-${row.label}`"
                    class="result-row"
                  >
                    <span>{{ row.label }}</span>
                    <strong :class="row.className">{{ row.value }}</strong>
                  </div>
                </template>

                <div
                  v-else
                  class="message-list"
                >
                  <p
                    v-for="(msg, idx) in card.messages"
                    :key="idx"
                  >
                    {{ msg }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="grouper-panel path-panel">
          <header class="panel-heading">
            <div class="panel-title">
              <span class="heading-icon"><GitCompareArrows class="panel-icon" /></span>
              <div>
                <h3>入组对比</h3>
                <p>汇总三类分组器的编码、权重或分值、正式写入状态。</p>
              </div>
            </div>
          </header>

          <div class="mapping-body">
            <table class="mapping-table">
              <thead>
                <tr>
                  <th>分组器</th>
                  <th>状态</th>
                  <th>结果编码</th>
                  <th>权重/分值</th>
                  <th>正式结果</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in comparisonRows"
                  :key="row.name"
                >
                  <td>{{ row.name }}</td>
                  <td>{{ row.status }}</td>
                  <td class="mono">
                    {{ row.code }}
                  </td>
                  <td>{{ row.metric }}</td>
                  <td>{{ row.writeBack }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="grouper-panel mapping-panel">
          <header class="panel-heading">
            <div class="panel-title">
              <span class="heading-icon"><Table2 class="panel-icon" /></span>
              <div>
                <h3>编码映射</h3>
                <p>展示本次输入编码，三类分组器共用同一组诊断和手术输入。</p>
              </div>
            </div>
          </header>

          <div class="mapping-body">
            <table class="mapping-table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>输入编码</th>
                  <th>标准映射</th>
                  <th>版本</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in mappingRows"
                  :key="`${row.item}-${row.code}`"
                >
                  <td>{{ row.item }}</td>
                  <td class="mono">
                    {{ row.code }}
                  </td>
                  <td>{{ row.standard }}</td>
                  <td>{{ row.version }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  BriefcaseMedical,
  ChartColumnBig,
  CircleCheck,
  CircleDollarSign,
  CircleX,
  ClipboardList,
  FilePlus2,
  FileSearch,
  GitCompareArrows,
  Home,
  LoaderCircle,
  Plus,
  SearchCheck,
  Table2,
  Trash2,
  UserRound,
  Zap,
} from 'lucide-vue-next'
import {
  performGrouping as performDrgGrouping,
  getMdcName,
  type GrouperInput,
  type GrouperResult,
} from './drgGrouper'
import { performGrouping as performCnDrgGrouping } from './cnDrgGrouper'
import { performDipGrouping, getDipSchemeInfo, type DipGrouperResult } from './dipGrouper'

interface MappingRow {
  item: string
  code: string
  standard: string
  version: string
}

interface DetailRow {
  label: string
  value: string
  className?: string
}

interface ResultCard {
  key: string
  title: string
  subtitle: string
  status: string
  success: boolean
  codeLabel: string
  code?: string
  nameLabel: string
  name?: string
  metricLabel: string
  metric?: string
  detailRows: DetailRow[]
  messages: string[]
}

interface ComparisonRow {
  name: string
  status: string
  code: string
  metric: string
  writeBack: string
}

const dipSchemeInfo = getDipSchemeInfo()

const formData = reactive({
  gender: '2',
  age: 30,
  days: 15,
  leavingType: '1',
  totalFee: 48360.25,
  drugFee: 15680.4,
  materialFee: 18543.3,
  otherFee: 14136.55,
  zdList: ['K80.501', 'K80.100x001', 'K83.109', 'K72.905', 'E11.900'] as string[],
  ssList: ['51.8803', '51.8701', '51.2300'] as string[],
})

const grouping = ref(false)
const drgResult = ref<GrouperResult | null>(null)
const cnDrgResult = ref<GrouperResult | null>(null)
const dipResult = ref<DipGrouperResult | null>(null)

const hasAnyResult = computed(() => !!drgResult.value || !!cnDrgResult.value || !!dipResult.value)
const otherDiagnosisIndexes = computed(() => formData.zdList.slice(1).map((_, index) => index + 1))
const resultCards = computed<ResultCard[]>(() => [
  buildDrgCard('drg', 'CHS-DRG 四川 2.0', '本地 CHS-DRG 分组路径', drgResult.value),
  buildDrgCard(
    'cndrg',
    'CN-DRG 绩效监测',
    '复用 CHS-DRG 四川 2.0 分组路径，叠加 2024 绩效监测权重',
    cnDrgResult.value,
  ),
  buildDipCard(dipResult.value),
])
const comparisonRows = computed<ComparisonRow[]>(() => [
  buildDrgComparison('CHS-DRG 四川 2.0', drgResult.value),
  buildDrgComparison('CN-DRG 绩效监测', cnDrgResult.value),
  buildDipComparison(dipResult.value),
])
const mappingRows = computed<MappingRow[]>(() => {
  const rows: MappingRow[] = []
  const zdList = formData.zdList.filter(Boolean)
  const ssList = formData.ssList.filter(Boolean)
  zdList.forEach((code, index) => {
    rows.push({
      item: index === 0 ? '主诊断' : `其他诊断${index}`,
      code,
      standard: 'ICD-10 第10版 / DIP 病种库诊断',
      version: index === 0 ? `${dipSchemeInfo.version}；CHS-DRG 2.0` : 'CHS-DRG 2.0',
    })
  })
  ssList.forEach((code, index) => {
    rows.push({
      item: index === 0 ? '主手术' : `其他手术${index}`,
      code,
      standard: '手术操作分类代码 / DIP 组合规则',
      version: `${dipSchemeInfo.version}；CHS-DRG 2.0`,
    })
  })
  return rows.length > 0 ? rows : [{ item: '待输入', code: '--', standard: '--', version: '--' }]
})

function addDiagnosis() {
  formData.zdList.push('')
}

function addProcedure() {
  formData.ssList.push('')
}

function resetForm() {
  formData.gender = '1'
  formData.age = 58
  formData.days = 7
  formData.leavingType = '1'
  formData.totalFee = 0
  formData.drugFee = 0
  formData.materialFee = 0
  formData.otherFee = 0
  formData.zdList = ['']
  formData.ssList = ['']
  clearResults()
}

function fillTestCase() {
  formData.gender = '2'
  formData.age = 30
  formData.days = 15
  formData.leavingType = '1'
  formData.totalFee = 48360.25
  formData.drugFee = 15680.4
  formData.materialFee = 18543.3
  formData.otherFee = 14136.55
  formData.zdList = ['K80.501', 'K80.100x001', 'K83.109', 'K72.905', 'E11.900']
  formData.ssList = ['51.8803', '51.8701', '51.2300']
  clearResults()
  message.success('已填入样例病案，可一次生成 3 个分组器结果')
}

async function doGrouping() {
  const input = buildInput()
  if (input.zdList.length === 0) {
    message.warning('请至少输入一个诊断编码')
    return
  }

  grouping.value = true
  clearResults()
  try {
    const [drg, cndrg, dip] = await Promise.allSettled([
      performDrgGrouping(input),
      performCnDrgGrouping(input),
      Promise.resolve(performDipGrouping(input)),
    ])

    drgResult.value = unwrapDrgResult(drg, 'CHS-DRG 分组失败')
    cnDrgResult.value = unwrapDrgResult(cndrg, 'CN-DRG 绩效监测分组失败')
    dipResult.value = unwrapDipResult(dip)
    message.success('已生成 3 个分组器结果')
  } finally {
    grouping.value = false
  }
}

function buildInput(): GrouperInput {
  return {
    gender: formData.gender,
    age: formData.age,
    zdList: formData.zdList.map((item) => item.trim()).filter(Boolean),
    ssList: formData.ssList.map((item) => item.trim()).filter(Boolean),
    days: formData.days,
    leavingType: formData.leavingType,
  }
}

function clearResults() {
  drgResult.value = null
  cnDrgResult.value = null
  dipResult.value = null
}

function unwrapDrgResult(
  result: PromiseSettledResult<GrouperResult>,
  fallbackTitle: string,
): GrouperResult {
  if (result.status === 'fulfilled') return result.value
  const reason = result.reason instanceof Error ? result.reason.message : String(result.reason)
  return { status: '未入组', messages: [`${fallbackTitle}: ${reason}`], qcMessages: [] }
}

function unwrapDipResult(result: PromiseSettledResult<DipGrouperResult>): DipGrouperResult {
  if (result.status === 'fulfilled') return result.value
  const reason = result.reason instanceof Error ? result.reason.message : String(result.reason)
  return { status: '未入组', messages: [`DIP 入组失败: ${reason}`] }
}

function buildDrgCard(
  key: string,
  title: string,
  subtitle: string,
  result: GrouperResult | null,
): ResultCard {
  const success = result?.status === '分组成功'
  return {
    key,
    title,
    subtitle,
    status: result?.status || '待执行',
    success,
    codeLabel: 'DRG 编码',
    code: result?.drg,
    nameLabel: 'DRG 名称',
    name: result?.drgName,
    metricLabel: '权重',
    metric: result?.rw === undefined ? undefined : String(result.rw),
    detailRows: [
      { label: 'MDC', value: formatMdc(result) },
      { label: 'ADRG', value: result?.adrg || '--' },
      {
        label: '是否低风险',
        value: formatLowRisk(result?.isLowRisk),
        className: result?.isLowRisk ? 'success-value' : '',
      },
      { label: '权重来源', value: result?.weightSource || '本地分组器返回' },
      { label: '正式结果', value: '不写入', className: 'warning-value' },
    ],
    messages: result?.messages.length ? result.messages : ['等待执行分组'],
  }
}

function buildDipCard(result: DipGrouperResult | null): ResultCard {
  const success = result?.status === '分组成功'
  return {
    key: 'dip',
    title: 'DIP 泸州版',
    subtitle: dipSchemeInfo.version,
    status: result?.status || '待执行',
    success,
    codeLabel: 'DIP 编码',
    code: result?.dipCode,
    nameLabel: 'DIP 名称',
    name: result?.dipName,
    metricLabel: '分值',
    metric: result?.score === undefined ? undefined : String(result.score),
    detailRows: [
      { label: '主诊断', value: result?.primaryZd || '--' },
      { label: '匹配手术', value: result?.matchedSs || '--' },
      { label: '匹配方式', value: result?.matchType || '--' },
      { label: '病种属性', value: result?.diseaseAttribute || '--' },
      { label: '正式结果', value: '不写入', className: 'warning-value' },
    ],
    messages: result?.messages.length ? result.messages : ['等待执行分组'],
  }
}

function buildDrgComparison(name: string, result: GrouperResult | null): ComparisonRow {
  return {
    name,
    status: result?.status || '待执行',
    code: result?.drg || '--',
    metric: result?.rw === undefined ? '--' : String(result.rw),
    writeBack: '不写入',
  }
}

function buildDipComparison(result: DipGrouperResult | null): ComparisonRow {
  return {
    name: 'DIP 泸州版',
    status: result?.status || '待执行',
    code: result?.dipCode || '--',
    metric: result?.score === undefined ? '--' : String(result.score),
    writeBack: '不写入',
  }
}

function formatMdc(result: GrouperResult | null): string {
  if (!result?.mdc) return '--'
  return `${result.mdc} / ${getMdcName(result.mdc)}`
}

function formatLowRisk(value: boolean | undefined): string {
  if (value === undefined) return '--'
  return value ? '是' : '否'
}
</script>

<style scoped>
@import './grouper-workbench.css';

.status-chip {
  margin-left: auto;
}
</style>
