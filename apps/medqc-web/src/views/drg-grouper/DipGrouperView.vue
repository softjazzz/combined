<template>
  <div class="grouper-page">
    <section class="grouper-panel condition-panel">
      <header class="panel-heading">
        <div class="panel-title">
          <span class="heading-icon"><PartitionOutlined /></span>
          <div>
            <h2>分组条件</h2>
            <p>DIP 泸州版，录入诊断、手术和费用信息执行病种模拟。</p>
          </div>
        </div>
      </header>

      <div class="condition-body">
        <div class="form-section">
          <div class="section-title">
            <span class="section-title-main"><InfoCircleOutlined />模拟口径</span>
          </div>
          <div class="field-grid">
            <label class="field-card">
              <span>统筹区</span>
              <strong>泸州</strong>
            </label>
            <label class="field-card">
              <span>版本</span>
              <strong>{{ schemeInfo.version }}</strong>
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
            <span class="section-title-main"><FileSearchOutlined />主诊断</span>
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
            <span class="section-title-main"><FileAddOutlined />其他诊断</span>
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
                <DeleteOutlined />
              </button>
            </div>
            <button
              type="button"
              class="add-button"
              @click="addDiagnosis"
            >
              <PlusOutlined /> 添加诊断
            </button>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">
            <span class="section-title-main"><MedicineBoxOutlined />手术操作</span>
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
                <DeleteOutlined />
              </button>
              <span v-else />
            </div>
            <button
              type="button"
              class="add-button"
              @click="addProcedure"
            >
              <PlusOutlined /> 添加手术
            </button>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title">
            <span class="section-title-main"><PayCircleOutlined />费用信息（元）</span>
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
            费用信息用于页面模拟摘要，不参与本地 DIP 病种匹配。
          </p>
        </div>
      </div>

      <footer class="action-bar">
        <button
          class="secondary-button"
          type="button"
          @click="fillTestCase"
        >
          填入示例
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
          <LoadingOutlined v-if="grouping" />
          <ThunderboltOutlined v-else />
          {{ grouping ? '分组中...' : '执行分组' }}
        </button>
      </footer>
    </section>

    <section class="grouper-panel result-panel">
      <header class="panel-heading">
        <div class="panel-title">
          <span class="heading-icon"><BarChartOutlined /></span>
          <div>
            <h2>模拟结果</h2>
            <p>结构化展示 DIP 编码、分值、病种属性和费用摘要。</p>
          </div>
        </div>
        <span class="simulate-chip"><AlertOutlined />仅模拟</span>
      </header>

      <div class="result-body">
        <div
          v-if="!result && !grouping"
          class="empty-state"
        >
          <PartitionOutlined />
          <h3>等待 DIP 入组</h3>
          <p>输入主诊断和手术编码后，系统展示 DIP 编码、病种名称和分值。</p>
        </div>

        <div
          v-else-if="grouping"
          class="empty-state"
        >
          <LoadingOutlined class="spin-icon" />
          <h3>正在执行入组</h3>
          <p>系统正在按泸州 DIP 病种库匹配模拟结果。</p>
        </div>

        <div
          v-else-if="result"
          class="result-summary"
        >
          <div class="result-block">
            <div class="result-block-header">
              <span :class="['result-icon', result.status === '分组成功' ? 'success' : 'danger']">
                <CheckCircleOutlined v-if="result.status === '分组成功'" />
                <CloseCircleOutlined v-else />
              </span>
              <div>
                <h3>{{ result.status === '分组成功' ? 'DIP 模拟结果' : '未能入组' }}</h3>
                <p>泸州版 DIP</p>
              </div>
            </div>

            <template v-if="result.status === '分组成功'">
              <div class="result-row">
                <span>DIP 编码</span>
                <strong class="primary-value">{{ result.dipCode || '--' }}</strong>
              </div>
              <div class="result-row">
                <span>DIP 名称</span>
                <strong>{{ result.dipName || '暂无 DIP 病种名称' }}</strong>
              </div>
              <div class="result-row">
                <span>分值（分）</span>
                <strong class="success-value">{{ result.score ?? '--' }}</strong>
              </div>
              <div class="result-row">
                <span>病种属性</span>
                <strong>{{ result.diseaseAttribute || '--' }}</strong>
              </div>
              <div class="result-row">
                <span>基层病种标识</span>
                <strong>{{ result.primaryCareFlag || '否' }}</strong>
              </div>
              <div class="result-row">
                <span>费用合计</span>
                <strong>{{ formatMoney(formData.totalFee) }}</strong>
              </div>
            </template>

            <div
              v-else
              class="message-list"
            >
              <p
                v-for="(msg, idx) in result.messages"
                :key="idx"
              >
                {{ msg }}
              </p>
            </div>
          </div>

          <div class="result-block">
            <div class="result-row">
              <span>主诊断</span>
              <strong>{{ result.primaryZd || primaryDiagnosis }}
                {{ result.primaryZdName ? ` / ${result.primaryZdName}` : '' }}</strong>
            </div>
            <div class="result-row">
              <span>匹配手术</span>
              <strong>{{ result.matchedSs || primaryProcedure }}</strong>
            </div>
            <div class="result-row">
              <span>匹配方式</span>
              <strong>{{ result.matchType || '--' }}</strong>
            </div>
            <div class="result-row">
              <span>正式结果</span>
              <strong class="warning-value">不写入</strong>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="grouper-panel path-panel">
      <header class="panel-heading">
        <div class="panel-title">
          <span class="heading-icon"><ApartmentOutlined /></span>
          <div>
            <h3>入组路径解释</h3>
            <p>按诊断校验、手术匹配、病种确定、分值读取解释模拟过程。</p>
          </div>
        </div>
      </header>

      <div class="path-body">
        <div class="path-grid">
          <div
            v-for="step in pathSteps"
            :key="step.title"
            class="path-step"
          >
            <span class="step-badge">{{ step.index }}</span>
            <h4>{{ step.title }}</h4>
            <p>{{ step.description }}</p>
            <span class="step-status">{{ step.status }}</span>
          </div>
        </div>
        <div
          v-if="result?.messages.length"
          class="timeline"
        >
          <div
            v-for="(msg, idx) in result.messages"
            :key="idx"
            class="timeline-item"
          >
            <span class="timeline-dot">{{ idx + 1 }}</span>
            <span>{{ msg }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="grouper-panel mapping-panel">
      <header class="panel-heading">
        <div class="panel-title">
          <span class="heading-icon"><TableOutlined /></span>
          <div>
            <h3>编码映射</h3>
            <p>展示本次输入编码与泸州 DIP 病种口径。</p>
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
        <p class="mapping-footnote">
          查看全部映射记录
        </p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  AlertOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  FileAddOutlined,
  FileSearchOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  MedicineBoxOutlined,
  PartitionOutlined,
  PayCircleOutlined,
  PlusOutlined,
  TableOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { performDipGrouping, getDipSchemeInfo, type DipGrouperResult } from './dipGrouper'

interface MappingRow {
  item: string
  code: string
  standard: string
  version: string
}

const schemeInfo = getDipSchemeInfo()

const formData = reactive({
  days: 7,
  leavingType: '1',
  totalFee: 48360.25,
  drugFee: 15680.4,
  materialFee: 18543.3,
  otherFee: 14136.55,
  zdList: ['I25.110'] as string[],
  ssList: ['36.06'] as string[],
})

const grouping = ref(false)
const result = ref<DipGrouperResult | null>(null)

const otherDiagnosisIndexes = computed(() => formData.zdList.slice(1).map((_, index) => index + 1))
const primaryDiagnosis = computed(() => formData.zdList.find(Boolean) || '--')
const primaryProcedure = computed(() => formData.ssList.find(Boolean) || '--')
const groupingPath = computed(() => {
  if (!result.value || result.value.status !== '分组成功') return '--'
  if (result.value.matchedRelSs) return '主诊断 + 主手术 + 相关手术'
  if (result.value.matchedSs) return '主诊断 + 手术'
  return '主诊断'
})
const pathSteps = computed(() => [
  {
    index: 1,
    title: '校验诊断',
    description: `主诊断 ${primaryDiagnosis.value}，确认是否在泸州 DIP 病种库内。`,
    status: result.value ? '已校验' : '待执行',
  },
  {
    index: 2,
    title: '匹配手术',
    description:
      primaryProcedure.value === '--'
        ? '无手术时尝试纯诊断入组。'
        : `手术 ${primaryProcedure.value} 参与组合匹配。`,
    status: result.value?.matchedSs ? '命中' : result.value ? '已处理' : '待执行',
  },
  {
    index: 3,
    title: '确定 DIP',
    description: result.value?.dipCode
      ? `${result.value.dipCode} ${result.value.dipName || ''}`
      : '输出病种编码和病种名称。',
    status: result.value?.status === '分组成功' ? '完成' : result.value ? '未入组' : '待执行',
  },
  {
    index: 4,
    title: '读取分值',
    description: result.value?.score
      ? `分值 ${result.value.score}，路径 ${groupingPath.value}`
      : '执行后展示 DIP 分值和病种属性。',
    status: result.value?.score ? '完成' : result.value ? '无分值' : '待执行',
  },
])
const mappingRows = computed<MappingRow[]>(() => {
  const rows: MappingRow[] = []
  const zdList = formData.zdList.filter(Boolean)
  const ssList = formData.ssList.filter(Boolean)
  zdList.forEach((code, index) => {
    rows.push({
      item: index === 0 ? '主诊断' : `其他诊断${index}`,
      code,
      standard: 'ICD-10 与泸州 DIP 病种库',
      version: schemeInfo.version,
    })
  })
  ssList.forEach((code, index) => {
    rows.push({
      item: index === 0 ? '手术操作' : `其他手术${index}`,
      code,
      standard: '手术操作与 DIP 组合规则',
      version: schemeInfo.version,
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
  formData.days = 7
  formData.leavingType = '1'
  formData.totalFee = 0
  formData.drugFee = 0
  formData.materialFee = 0
  formData.otherFee = 0
  formData.zdList = ['']
  formData.ssList = ['']
  result.value = null
}

function fillTestCase() {
  formData.days = 7
  formData.leavingType = '1'
  formData.totalFee = 48360.25
  formData.drugFee = 15680.4
  formData.materialFee = 18543.3
  formData.otherFee = 14136.55
  formData.zdList = ['K80.501']
  formData.ssList = ['51.8803']
  result.value = null
  message.success('已填入示例病案')
}

function formatMoney(value: number) {
  return Number.isFinite(value) && value > 0
    ? value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '--'
}

function doGrouping() {
  const zdList = formData.zdList.filter((z) => z.trim())
  const ssList = formData.ssList.filter((s) => s.trim())
  if (zdList.length === 0) {
    message.warning('请至少输入一个诊断编码')
    return
  }

  grouping.value = true
  result.value = null
  try {
    result.value = performDipGrouping({
      zdList,
      ssList,
      days: formData.days,
      leavingType: formData.leavingType,
    })
    if (result.value.status === '分组成功') {
      message.success(`DIP 入组成功：${result.value.dipCode}`)
    } else {
      message.warning('未能入组，请复核编码和病种库范围')
    }
  } catch (err) {
    message.error('DIP 入组失败：' + (err instanceof Error ? err.message : String(err)))
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
@import './grouper-workbench.css';
</style>
