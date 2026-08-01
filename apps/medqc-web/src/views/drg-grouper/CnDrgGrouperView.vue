<template>
  <div class="grouper-page">
    <section class="grouper-panel condition-panel">
      <header class="panel-heading">
        <div class="panel-title">
          <span class="heading-icon"><ProfileOutlined /></span>
          <div>
            <h2>分组条件</h2>
            <p>
              CN-DRG 绩效监测：复用 CHS-DRG 四川 2.0 分组路径，叠加 2024 绩效监测 DRG
              权重与低风险组列表。
            </p>
          </div>
        </div>
      </header>

      <div class="condition-body">
        <div class="form-section">
          <div class="section-title">
            <span class="section-title-main"><UserOutlined />基本信息</span>
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
            费用信息用于页面费用摘要，不参与本地 CN-DRG 分组判定。
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
            <h2>分组结果</h2>
            <p>结构化展示 CN-DRG 编码、权重、费用和风险提示。</p>
          </div>
        </div>
        <span class="simulate-chip"><AlertOutlined />本地分组器和权重</span>
      </header>

      <div class="result-body">
        <div
          v-if="!result && !grouping"
          class="empty-state"
        >
          <FileSearchOutlined />
          <h3>等待分组</h3>
          <p>填写条件后点击执行分组，结果不会写入正式首页或结算清单。</p>
        </div>

        <div
          v-else-if="grouping"
          class="empty-state"
        >
          <LoadingOutlined class="spin-icon" />
          <h3>正在执行分组</h3>
          <p>系统正在执行 CN-DRG 绩效监测分组。</p>
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
                <h3>{{ result.status === '分组成功' ? 'CN-DRG 绩效监测结果' : '未能入组' }}</h3>
                <p>CN-DRG 绩效监测</p>
              </div>
            </div>

            <template v-if="result.status === '分组成功'">
              <div class="result-row">
                <span>DRG 编码</span>
                <strong class="primary-value">{{ result.drg || '--' }}</strong>
              </div>
              <div class="result-row">
                <span>DRG 名称</span>
                <strong>{{ result.drgName || '暂无 DRG 名称' }}</strong>
              </div>
              <div class="result-row">
                <span>权重</span>
                <strong class="primary-value">{{ result.rw ?? '--' }}</strong>
              </div>
              <div class="result-row">
                <span>是否低风险</span>
                <strong>{{
                  result.isLowRisk === undefined ? '--' : result.isLowRisk ? '是' : '否'
                }}</strong>
              </div>
              <div class="result-row">
                <span>费用合计</span>
                <strong>{{ formatMoney(formData.totalFee) }}</strong>
              </div>
              <div class="result-row">
                <span>风险提示</span>
                <strong class="warning-value">{{ riskLevel }}</strong>
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
              <span>MDC</span>
              <strong>{{ result.mdc || '--' }} {{ mdcName ? ` / ${mdcName}` : '' }}</strong>
            </div>
            <div class="result-row">
              <span>ADRG</span>
              <strong>{{ result.adrg || '--' }}
                {{ result.adrgName ? ` / ${result.adrgName}` : '' }}</strong>
            </div>
            <div class="result-row">
              <span>权重来源</span>
              <strong>{{
                result.weightSource || '2024年度三级公立医院绩效监测DRG权重和低风险组列表'
              }}</strong>
            </div>
            <div class="result-row">
              <span>正式结果</span>
              <strong class="warning-value">不写入</strong>
            </div>
          </div>

          <div
            v-if="result.qcMessages.length > 0"
            class="message-list"
          >
            <p
              v-for="(msg, idx) in result.qcMessages"
              :key="idx"
            >
              {{ msg }}
            </p>
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
            <p>按校验、MDC、ADRG、DRG 四步解释分组过程。</p>
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
            <p>展示本次输入编码与分组口径，不改写数据源。</p>
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
  LoadingOutlined,
  MedicineBoxOutlined,
  PayCircleOutlined,
  PlusOutlined,
  ProfileOutlined,
  TableOutlined,
  ThunderboltOutlined,
  UserOutlined,
} from '@ant-design/icons-vue'
import { performGrouping, getMdcName, type GrouperResult } from './cnDrgGrouper'

interface MappingRow {
  item: string
  code: string
  standard: string
  version: string
}

const formData = reactive({
  gender: '1',
  age: 58,
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
const result = ref<GrouperResult | null>(null)

const otherDiagnosisIndexes = computed(() => formData.zdList.slice(1).map((_, index) => index + 1))
const mdcName = computed(() => (result.value?.mdc ? getMdcName(result.value.mdc) : ''))
const primaryDiagnosis = computed(() => formData.zdList.find(Boolean) || '--')
const otherDiagnosisCount = computed(() => Math.max(formData.zdList.filter(Boolean).length - 1, 0))
const procedureCount = computed(() => formData.ssList.filter(Boolean).length)
const riskLevel = computed(() =>
  Number(result.value?.rw || 0) >= 2 ? '权重较高，建议关注费用结构与合理性' : '常规复核',
)
const pathSteps = computed(() => [
  {
    index: 1,
    title: '校验编码',
    description: `主诊断 ${primaryDiagnosis.value}，共 ${otherDiagnosisCount.value} 个其他诊断、${procedureCount.value} 个手术操作。`,
    status: result.value ? '已校验' : '待执行',
  },
  {
    index: 2,
    title: '匹配 MDC',
    description: result.value?.mdc
      ? `${result.value.mdc} ${mdcName.value}`
      : '执行后展示主要诊断类别。',
    status: result.value?.mdc ? '命中' : '待执行',
  },
  {
    index: 3,
    title: '匹配 ADRG',
    description: result.value?.adrg
      ? `${result.value.adrg} ${result.value.adrgName || ''}`
      : '结合手术、合并症与并发症匹配 ADRG。',
    status: result.value?.adrg ? '命中' : '待执行',
  },
  {
    index: 4,
    title: '确定 DRG',
    description: result.value?.drg
      ? `${result.value.drg}，权重 ${result.value.rw ?? '--'}`
      : '输出最终 DRG 分组结果。',
    status: result.value?.status === '分组成功' ? '完成' : result.value ? '未入组' : '待执行',
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
      standard: 'ICD-10 第10版',
      version: '2025-01',
    })
  })
  ssList.forEach((code, index) => {
    rows.push({
      item: index === 0 ? '手术操作' : `其他手术${index}`,
      code,
      standard: '手术操作分类代码国家临床版',
      version: '2024-01',
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
  result.value = null
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
  result.value = null
  message.success('已填入样例病案')
}

function formatMoney(value: number) {
  return Number.isFinite(value) && value > 0
    ? value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '--'
}

async function doGrouping() {
  const zdList = formData.zdList.filter((z) => z.trim())
  const ssList = formData.ssList.filter((s) => s.trim())
  if (zdList.length === 0) {
    message.warning('请至少输入一个诊断编码')
    return
  }

  grouping.value = true
  result.value = null
  try {
    result.value = await performGrouping({
      gender: formData.gender,
      age: formData.age,
      zdList,
      ssList,
      days: formData.days,
      leavingType: formData.leavingType,
    })
    if (result.value.status === '分组成功') {
      message.success(`CN-DRG 入组成功：${result.value.drg}`)
    } else {
      message.warning('未能入组，请复核编码和病案条件')
    }
  } catch (err) {
    message.error('分组失败：' + (err instanceof Error ? err.message : String(err)))
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
@import './grouper-workbench.css';
</style>
